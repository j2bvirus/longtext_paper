"""Further analyses, from stored outputs only (no model calls).

python methods/revision_analyses.py length      accuracy across record length on the same worlds, questions and
                                                method versions (D2-D3 at 44k/0.49M/1.96M; T1-T2 at 0.5M/1.9M)
python methods/revision_analyses.py clusters    CMM v4 minus paragraph BM25 / hybrid on T1-T2 with intervals from a
                                                bootstrap over clusters of questions that share gold evidence
python methods/revision_analyses.py oolong      Oolong-real: index minus BM25 split by answer type
python methods/revision_analyses.py full44k     full-context reading at 44k against the memories on the same questions
python methods/revision_analyses.py figure      writes the length figure (FIG_OUT, default paper/figures)

Accuracy is the deterministic `correct` of the result records over the questions not marked excluded in
data/<world>/questions_GOLD.jsonl. Paired tests are exact two-sided McNemar tests; Holm correction where stated.
"""
import ast
import collections
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oolong_score  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "runs", "results")
H, G = "claude-claude-haiku-4-5-20251001", "codex-gpt-6.1-sol"
Q14, Q8 = "ollama-qwen3-14b", "ollama-qwen3-8b"
ARGON, OSS = "agy-gemini-4-argon-low", "agy-gpt-oss-120b-medium"
NAMES = {H: "Haiku 4.5", G: "GPT-6.1 Sol", Q14: "Qwen3-14B", Q8: "Qwen3-8B", ARGON: "Gemini 4 Argon",
         OSS: "gpt-oss-120b", "mem-cmm4": "CMM v4", "mem-cmm4a": "CMM v4-adaptive", "mem-cmm2c": "CMM v2 + cards",
         "mem-cmmc": "CMM v1 + cards", "mem-cmm": "CMM v1", "mem-pbm25": "Paragraph BM25",
         "mem-namegrep_co": "NameGrep+co", "hybrid": "Hybrid retrieval", "bm25": "Chunk BM25"}


def questions(world):
    out = {}
    for l in open(os.path.join(ROOT, "data", world, "questions_GOLD.jsonl"), encoding="utf-8"):
        q = json.loads(l)
        if not q.get("excluded"):
            out[q["qid"]] = q
    return out


def results(world, d, method, reader, tag=""):
    """{(world, qid): correct} or None if the result file does not exist."""
    p = os.path.join(RES, f"{world}_{d}_{method}_{reader}_b4000{tag}.jsonl")
    if not os.path.exists(p):
        return None
    qs = questions(world)
    out = {}
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        if r["qid"] in qs:
            out[(world, r["qid"])] = int(r["correct"])
    return out


def pooled(worlds, d, method, reader, tag=""):
    out = {}
    for w in worlds:
        r = results(w, d, method, reader, tag)
        if r is None:
            return None
        out.update(r)
    return out


def mcnemar(a, b, keys):
    w = sum(1 for k in keys if a[k] and not b[k])
    l = sum(1 for k in keys if b[k] and not a[k])
    n = w + l
    p = 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n)
    return w, l, p


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def record_tokens(worlds, d):
    ts = []
    for w in worlds:
        p = os.path.join(RES, f"{w}_{d}_hybrid_{H}_b4000.summary.json")
        if os.path.exists(p):
            ts.append(json.load(open(p, encoding="utf-8")).get("record_tokens"))
    ts = [t for t in ts if t]
    return sum(ts) / len(ts) if ts else None


def length_rows():
    """(set label, densities, {reader: {method: [acc per density]}}, n per cell, tokens per density)."""
    out = []
    for label, worlds, ds, readers, methods in (
            ("D2-D3", ("saga_v5_s2", "saga_v5_s3"), ("d1", "d16", "d64"), (H, Q14, Q8),
             ("mem-cmm2c", "mem-pbm25", "mem-namegrep_co", "hybrid", "bm25")),
            ("T1-T2", ("saga_v5_s7", "saga_v5_s8"), ("d16", "d64"), (H, G),
             ("mem-cmm4a", "mem-cmm4", "mem-pbm25", "mem-namegrep_co", "hybrid"))):
        cells = {}
        for rd in readers:
            for m in methods:
                rs = [pooled(worlds, d, m, rd) for d in ds]
                if any(r is None for r in rs):
                    continue
                keys = set.intersection(*(set(r) for r in rs))
                cells[(rd, m)] = ([100 * sum(r[k] for k in keys) / len(keys) for r in rs], len(keys))
        out.append((label, worlds, ds, readers, methods, cells, [record_tokens(worlds, d) for d in ds]))
    return out


def cmd_length():
    print("Accuracy % across record length; each row uses the same questions at every length (n), the same method "
          "version and the same reader. Change = last length minus first.")
    for label, worlds, ds, readers, methods, cells, toks in length_rows():
        print(f"\nWorlds {label}; record length " + ", ".join(f"{d} {t / 1e6:.2f}M" if t else d for d, t in zip(ds, toks)))
        print("| Reader | Method | n | " + " | ".join(ds) + " | Change |")
        print("|---|---|---|" + "---|" * len(ds) + "---|")
        for rd in readers:
            for m in methods:
                if (rd, m) not in cells:
                    continue
                acc, n = cells[(rd, m)]
                print(f"| {NAMES[rd]} | {NAMES[m]} | {n} | " + " | ".join(f"{a:.1f}" for a in acc) +
                      f" | {acc[-1] - acc[0]:+.1f} |")


def components(qs_by_key, field):
    """Connected components of questions linked by any shared item of `field` (per world)."""
    parent = {k: k for k in qs_by_key}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    first = {}
    for k, q in qs_by_key.items():
        items = q.get(field) or []
        items = ast.literal_eval(items) if isinstance(items, str) else items
        for e in items:
            e = (k[0], e)
            if e in first:
                parent[find(k)] = find(first[e])
            else:
                first[e] = k
    groups = collections.defaultdict(list)
    for k in qs_by_key:
        groups[find(k)].append(k)
    return list(groups.values())


def cluster_ci(diff, clusters, reps=20000, seed=0):
    rnd = random.Random(seed)
    sums = [(sum(diff[k] for k in c), len(c)) for c in clusters]
    vals = []
    for _ in range(reps):
        s = n = 0
        for _ in range(len(sums)):
            a, b = sums[rnd.randrange(len(sums))]
            s += a
            n += b
        vals.append(100 * s / n)
    vals.sort()
    return vals[int(0.025 * reps)], vals[int(0.975 * reps) - 1]


def cmd_clusters():
    worlds = ("saga_v5_s7", "saga_v5_s8")
    qs = {(w, k): q for w in worlds for k, q in questions(w).items()}
    defs = [("question", [[k] for k in qs]), None,
            ("shared core evidence", components(qs, "evidence_core")),
            ("shared gold evidence (all)", components(qs, "evidence"))]
    print("CMM v4 minus another method on worlds T1-T2 (459 questions, 0.5M, 4k budget), accuracy points, with 95% "
          "intervals from a bootstrap over clusters (20,000 resamples, seed 0). Clusters: each question alone; "
          "questions that share any core gold evidence event; questions that share any gold evidence event "
          "(evidence closed over the references needed to interpret it), linked transitively within a world.")
    print(f"Clusters: {len(qs)} questions; core evidence {len(defs[2][1])} clusters (largest "
          f"{max(map(len, defs[2][1]))}); all evidence {len(defs[3][1])} clusters (largest {max(map(len, defs[3][1]))}).")
    print("\n| Reader | Comparison | Difference | Per question | Core-evidence clusters | All-evidence clusters |")
    print("|---|---|---|---|---|---|")
    for rd in (H, G, ARGON, OSS):
        a = pooled(worlds, "d16", "mem-cmm4", rd)
        for other in ("mem-pbm25", "hybrid"):
            b = pooled(worlds, "d16", other, rd)
            keys = sorted(set(a) & set(b) & set(qs))
            diff = {k: a[k] - b[k] for k in keys}
            cells = []
            for name, cl in (defs[0], defs[2], defs[3]):
                cl = [[k for k in c if k in diff] for c in cl]
                lo, hi = cluster_ci(diff, [c for c in cl if c])
                cells.append(f"[{lo:+.1f}, {hi:+.1f}]")
            d = 100 * sum(diff.values()) / len(keys)
            print(f"| {NAMES[rd]} | CMM v4 − {NAMES[other]} | {d:+.1f} | " + " | ".join(cells) + " |")


def oolong_kind(gold):
    g = oolong_score.parse_answer(gold)
    return "number" if isinstance(g, int) else "list" if isinstance(g, list) else "string"


def cmd_oolong():
    print("Oolong-real test: index minus BM25 (official score), split by the type of the gold answer. Contribution = "
          "sum of the per-question differences of that type divided by all questions of the set, so the rows add up "
          "to the total difference. For numbers, the exact part counts answers equal to the gold and the "
          "partial part the rest of the 0.75^|error| credit. For lists, the official score is the number of distinct "
          "items shared by the gold and predicted lists divided by the length of the gold list: order and extra "
          "predicted items are not penalized, and a gold list with repeated items cannot reach 1.0 even when "
          "predicted exactly.")
    for rd in (H, G):
        recs = {}
        for m in ("index", "bm25"):
            for l in open(os.path.join(ROOT, "runs", "results_oolong", f"test_{m}_{rd}.jsonl"), encoding="utf-8"):
                x = json.loads(l)
                recs.setdefault(m, {})[x["id"]] = x
        ids = sorted(set(recs["index"]) & set(recs["bm25"]))
        for set_name, keep in (("all windows", lambda x: True), ("16- and 24-episode windows",
                                                                  lambda x: int(x["n_eps"]) in (16, 24))):
            sel = [i for i in ids if keep(recs["index"][i])]
            parts = collections.Counter()
            count = collections.Counter()
            right = collections.Counter()
            for i in sel:
                gold = recs["index"][i]["answer"]
                kind = oolong_kind(gold)
                count[kind] += 1
                for m, sign in (("index", 1), ("bm25", -1)):
                    raw = recs[m][i].get("raw") or ""
                    s = oolong_score.score(gold, raw)[0]
                    if kind == "number":
                        exact = float(s == 1.0)
                        parts["number, exact"] += sign * exact
                        parts["number, partial credit"] += sign * (s - exact)
                        right[(m, kind)] += exact
                    else:
                        parts[kind] += sign * s
                        right[(m, kind)] += s == 1.0
            total = sum(parts.values()) / len(sel)
            print(f"\n{NAMES[rd]} reader, {set_name} ({len(sel)} questions: " +
                  ", ".join(f"{count[k]} {k}" for k in ("number", "string", "list")) + f"); total {total:+.3f}")
            print("| Answer type | Contribution | Share of the total | Official score 1.0: index / BM25 |")
            print("|---|---|---|---|")
            for k in ("string", "number, exact", "number, partial credit", "list"):
                c = parts[k] / len(sel)
                kind = k.split(",")[0]
                fr = f"{int(right[('index', kind)])} / {int(right[('bm25', kind)])}" if k != "number, partial credit" \
                    else "–"
                print(f"| {k} | {c:+.3f} | {100 * c / total:.0f}% | {fr} |")


def cmd_full44k():
    worlds = ("saga_v5_s2", "saga_v5_s3")
    full = pooled(worlds, "d1", "full", H, "_s100")
    print("Full-context reading at 44k (worlds D2-D3, Haiku, the questions it was run on) against the memories on the "
          f"same {len(full)} questions; exact McNemar, Holm over the four comparisons.")
    print("\n| Method | Accuracy % (same questions) | Full context | w/l against full context | p | Holm p |")
    print("|---|---|---|---|---|---|")
    rows = []
    for m in ("mem-pbm25", "mem-cmm", "mem-cmmc", "mem-namegrep_co"):
        a = pooled(worlds, "d1", m, H)
        keys = sorted(set(full) & set(a))
        w, l, p = mcnemar(a, full, keys)
        rows.append((m, 100 * sum(a[k] for k in keys) / len(keys), 100 * sum(full[k] for k in keys) / len(keys), w, l, p))
    adj = holm([r[5] for r in rows])
    for (m, acc, fa, w, l, p), pa in zip(rows, adj):
        print(f"| {NAMES[m]} | {acc:.1f} | {fa:.1f} | {w}/{l} | {p:.3f} | {pa:.3f} |")


def cmd_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = os.environ.get("FIG_OUT", os.path.join(ROOT, "paper", "figures"))
    os.makedirs(out, exist_ok=True)
    rows = length_rows()
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    style = {"mem-cmm4a": ("#1f4e79", "-", "o"), "mem-cmm4": ("#1f77b4", "-", "o"), "mem-cmm2c": ("#1f77b4", "-", "o"),
             "mem-pbm25": ("#d95f02", "--", "s"), "mem-namegrep_co": ("#7570b3", ":", "^"),
             "hybrid": ("#666666", "-.", "D"), "bm25": ("#aaaaaa", "-.", "v")}
    csv = ["set,reader,method,n,length_tokens,accuracy"]
    for ax, (label, worlds, ds, readers, methods, cells, toks) in zip(axes, rows):
        rd = H
        for m in methods:
            if (rd, m) not in cells:
                continue
            acc, n = cells[(rd, m)]
            c, ls, mk = style[m]
            ax.plot([t / 1e6 for t in toks], acc, color=c, linestyle=ls, marker=mk, linewidth=1.6, markersize=5,
                    label=NAMES[m])
            csv += [f"{label},{NAMES[rd]},{NAMES[m]},{n},{t:.0f},{a:.2f}" for t, a in zip(toks, acc)]
        ax.set_xscale("log")
        ax.set_xticks([t / 1e6 for t in toks])
        ax.set_xticklabels([f"{t / 1e3:.0f}k" if t < 1e5 else f"{t / 1e6:.2f}M" for t in toks])
        ax.minorticks_off()
        ax.set_xlabel("Record length (tokens)")
        ax.set_title(f"Worlds {label}, Haiku 4.5 reader", fontsize=10)
        ax.grid(axis="y", color="#dddddd", linewidth=0.6)
        ax.legend(fontsize=7.5, frameon=False, loc="lower left")
    axes[0].set_ylabel("Accuracy (%)")
    axes[0].set_ylim(40, 100)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out, f"fig_length.{ext}"), dpi=200 if ext == "png" else None,
                    metadata={"CreationDate": None} if ext == "pdf" else {"Software": None})
    open(os.path.join(out, "fig_length.csv"), "w", encoding="utf-8", newline="\n").write("\n".join(csv) + "\n")
    print("written fig_length.png, fig_length.pdf, fig_length.csv")


def cmd_added18():
    """Table 6 of the main text: Holm over all 18 post-hoc comparisons (3 baselines x 3 tasks x 2 readers), from the
    win/loss counts that methods/added_baselines_report.py writes (paper/tables_added_baselines.md, which
    corrects within each task and reader instead)."""
    import re
    from math import comb
    t = open(os.path.join(ROOT, "paper", "tables_added_baselines.md"), encoding="utf-8").read()
    rows = []
    for sec in re.split(r"\n### ", t)[1:]:
        lines = [l for l in sec.splitlines() if l.startswith("|")]
        head = [c.strip() for c in lines[0].strip("|").split("|")]
        for l in lines[2:]:
            cells = [c.strip() for c in l.strip("|").split("|")]
            for b in ("mem-hippo2", "mem-ctxhdr", "mem-s2b"):
                i = next(i for i, h in enumerate(head) if h.endswith("vs " + b + ": w/l, p (Holm)"))
                w, lo = map(int, re.match(r"(\d+)/(\d+)", cells[i]).groups())
                k, n = min(w, lo), w + lo
                rows.append((sec.splitlines()[0].split(",")[0], cells[0], b[4:], w, lo,
                             min(1.0, 2 * sum(comb(n, j) for j in range(k + 1)) / 2 ** n)))
    m = len(rows)
    order = sorted(range(m), key=lambda i: rows[i][5])
    adj, run = [0.0] * m, 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * rows[i][5]))
        adj[i] = run
    print(f"Post-hoc baselines (main text, Table 6): exact two-sided McNemar on the win/loss counts of "
          f"paper/tables_added_baselines.md, Holm over all {m} comparisons (3 baselines x 3 tasks x 2 readers).")
    print("| Task | Reader | Baseline | w/l | p | Holm p (18) |")
    print("|---|---|---|---|---|---|")
    for (task, rd, b, w, lo, p), a in zip(rows, adj):
        print(f"| {task} | {rd} | {b} | {w}/{lo} | {p:.2g} | {a:.2g} |")


if __name__ == "__main__":
    {"length": cmd_length, "clusters": cmd_clusters, "oolong": cmd_oolong, "full44k": cmd_full44k,
     "figure": cmd_figure, "added18": cmd_added18}[sys.argv[1]]()
