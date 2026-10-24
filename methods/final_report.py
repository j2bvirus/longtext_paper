"""Final-test report (no LLM calls): every table of Section 6.11 from the result files.

python methods/final_report.py > paper/tables_final.md

Correctness: deterministic `correct` for LongState-Saga and LongState-Code; LLM-judged verdicts
(runs/judged/<name>.json) for free-form datasets (novels, LoCoMo, agent trajectories).  CIs: cluster bootstrap over
question subjects (saga) or questions (others); paired tests: exact McNemar, Holm-corrected within each table.
"""
import collections
import glob
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from review_stats import holm, mcnemar  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RD = {"codex-gpt-6.1-sol": "GPT-6.1-sol", "claude-claude-haiku-4-5-20251001": "Haiku 4.5", "ollama-qwen3-14b": "Qwen3-14B",
      "ollama-qwen3-8b": "Qwen3-8B"}
FREE = ("nhq_", "locomo_", "ama_")
KEEP = {}  # dataset -> set of qids to keep (subset tables), set by subset()
# primary judge for free-form answers (in a blind check the GPT judge agreed with an
# independent reading far more often than the Haiku judge); `--judge haiku` reproduces the earlier tables
JUDGE_DIR = "runs/judged" if "--judge" in sys.argv and sys.argv[sys.argv.index("--judge") + 1] == "haiku" else "runs/judged_gpt"
LABEL = {"mem-cmm4a": "CMM v4-adaptive", "mem-cmm4ac": "CMM v4-adaptive+cards", "mem-cmm4": "CMM v4",
         "mem-cmm4c": "CMM v4+cards", "mem-cmm3": "CMM v3", "mem-cmm3c": "CMM v3+cards", "mem-cmm2": "CMM v2",
         "mem-cmm2l": "CMM v2-lean", "mem-cmm2c": "CMM v2+cards", "mem-cmm": "CMM v1", "mem-cmmc": "CMM v1+cards",
         "mem-namegrep_co": "NameGrep+co", "mem-pbm25": "Paragraph BM25",
         "mem-ledger": "State ledger", "hybrid": "Hybrid RAG", "bm25": "BM25 chunks",
         "oracle_para": "Gold paragraphs", "closedbook": "Closed book", "full": "Full re-reading",
         "mem-cmm2cq14": "CMM v2+cards by Qwen3-14B", "mem-cmm2cq8": "CMM v2+cards by Qwen3-8B",
         "mem-ledger2": "State ledger (status-aware)", "mem-compact4k": "Compaction 4k (2k summary + 2k tail)",
         "mem-compact16k": "Compaction 16k (8k summary + 8k tail)", "mem-cmm4au": "CMM v4 + idle-time index review",
         "mem-cmm4r": "CMM v4, newest first", "mem-pbm25r": "Paragraph BM25, newest first",
         "mem-cmm2cw14": "cards: 14B writes, 14B corrects", "mem-cmm2cw14H": "cards: 14B writes, Haiku corrects",
         "mem-cmm2cwH14": "cards: Haiku writes, 14B corrects", "mem-cmm2cv14": "cards: 14B writes, 14B drops",
         "mem-cmm2cw8": "cards: 8B writes, 8B corrects", "mem-cmm2cw8H": "cards: 8B writes, Haiku corrects",
         "mem-cmm2cv8": "cards: 8B writes, 8B drops",
         "mem-cmm4map": "Map + archive (2k compacted summary + CMM v4)",
         "mem-cmm4map16": "Map + archive (8k compacted summary + CMM v4)",
         "mem-compact4kq": "Compaction 4k, questions known in advance (oracle)"}
NAME = re.compile(r"^(?P<ds>.+?)_(?P<d>d[\d.]+|full)_(?P<m>.+?)_(?P<r>claude-claude-haiku-4-5-20251001|ollama-qwen3-14b|"
                  r"ollama-qwen3-8b|codex-gpt-6.1-sol)_b(?P<b>\d+)(?P<tag>.*)\.jsonl$")


def load(ds, d, m, r, b=4000, tag=""):
    f = os.path.join(ROOT, "runs", "results", f"{ds}_{d}_{m}_{r}_b{b}{tag}.jsonl")
    if not os.path.exists(f):
        return None
    qf = os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl")
    qs = {json.loads(l)["qid"]: json.loads(l) for l in open(qf, encoding="utf-8")}
    recs = [json.loads(l) for l in open(f, encoding="utf-8")]
    judged = None
    if ds.startswith(FREE):
        jf = os.path.join(ROOT, JUDGE_DIR, os.path.basename(f)[:-6] + ".json")
        if not os.path.exists(jf):
            return None
        judged = json.load(open(jf))
    out = {}
    for x in recs:
        q = qs.get(x["qid"])
        if q is None or q.get("excluded") or (ds in KEEP and x["qid"] not in KEEP[ds]):
            continue
        c = judged.get(x["qid"]) if judged is not None else x["correct"]
        if c is None:
            continue
        out[(ds, x["qid"])] = {"c": int(c), "tok": x["ctx_tokens"], "subj": (ds, q.get("subject", x["qid"])),
                               "cert": x.get("certified")}
    return out


def boot(keys, val, subj, n=2000, seed=0):  # 2,000 resamples as stated in the manuscript
    cl = collections.defaultdict(list)
    for k in keys:
        cl[subj[k]].append(k)
    cls = list(cl.values())
    r = random.Random(seed)
    st = []
    for _ in range(n):
        t = c = 0
        for _ in cls:
            g = cls[r.randrange(len(cls))]
            t += sum(val[k] for k in g)
            c += len(g)
        st.append(t / c)
    st.sort()
    return st[int(0.025 * n)], st[int(0.975 * n) - 1]


def pooled(dss, d, m, r, b=4000, tag=""):
    out = {}
    for ds in dss:
        x = load(ds, d, m, r, b, tag)
        if x is None:
            return None
        out.update(x)
    return out


def table(title, dss, d, methods, readers=RD, ref="mem-cmm4a", b=4000, tag=""):
    print(f"\n### {title}\n")
    cols = [r for r in readers]
    print("| Method | " + " | ".join(f"{RD[r]} acc [95% CI] (tokens/q)" for r in cols) + " |")
    print("|---|" + "---|" * len(cols))
    data = {(m, r): pooled(dss, d, m, r, b, tag) for m in methods for r in cols}
    tests = []
    for r in cols:
        A = data.get((ref, r))
        if not A:
            continue
        for m in methods:
            B = data.get((m, r))
            if m == ref or not B:
                continue
            ks = [k for k in A if k in B]
            w = sum(1 for k in ks if A[k]["c"] and not B[k]["c"])
            l = sum(1 for k in ks if B[k]["c"] and not A[k]["c"])
            tests.append((m, r, w, l, mcnemar(w, l)))
    adj = dict(((m, r), p) for (m, r, _, _, _), p in zip(tests, holm([t[4] for t in tests]))) if tests else {}
    wl = {(m, r): (w, l) for m, r, w, l, _ in tests}
    for m in methods:
        cells = []
        for r in cols:
            X = data.get((m, r))
            if not X:
                cells.append("–")
                continue
            ks = list(X)
            lo, hi = boot(ks, {k: X[k]["c"] for k in ks}, {k: X[k]["subj"] for k in ks})
            acc = 100 * sum(X[k]["c"] for k in ks) / len(ks)
            tok = sum(X[k]["tok"] for k in ks) / len(ks)
            s = f"{acc:.1f} [{100 * lo:.0f},{100 * hi:.0f}] ({tok:,.0f})"
            if (m, r) in adj:
                w, l = wl[(m, r)]
                s += f" {'*' if adj[(m, r)] < 0.05 else ''}{w}/{l}"
            cells.append(s)
        print(f"| {LABEL.get(m, m)} | " + " | ".join(cells) + " |")
    n = len(next(iter([v for v in data.values() if v] or [{}])))
    print(f"\nn = {n} questions per reader. w/l = questions the reference ({LABEL.get(ref, ref)}) gets right and the "
          f"method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the {len(tests)} tests of this table.")


def sweep(dss, d, methods, readers=("claude-claude-haiku-4-5-20251001", "ollama-qwen3-14b")):
    print("\n### Reading-budget sweep: accuracy (tokens per question)\n")
    for r in readers:
        print(f"\n{RD[r]}\n")
        print("| Method | 2k | 4k | 8k | 16k |")
        print("|---|---|---|---|---|")
        for m in methods:
            cells = []
            for b in (2000, 4000, 8000, 16000):
                X = pooled(dss, d, m, r, b)
                cells.append(f"{100 * sum(v['c'] for v in X.values()) / len(X):.1f} ({sum(v['tok'] for v in X.values()) / len(X):,.0f})"
                             if X else "–")
            print(f"| {LABEL.get(m, m)} | " + " | ".join(cells) + " |")
        X = pooled(dss, d, "mem-cmm4a", r)
        if X:
            print(f"| {LABEL['mem-cmm4a']} (budget 4k, x3 when uncertified) | " +
                  f"{100 * sum(v['c'] for v in X.values()) / len(X):.1f} ({sum(v['tok'] for v in X.values()) / len(X):,.0f}) | | | |")


def variants(title, dss, d, methods, tags, readers=("claude-claude-haiku-4-5-20251001", "ollama-qwen3-14b")):
    print(f"\n### {title}\n")
    print("| Reader | Method | " + " | ".join(t or "default" for t in tags) + " |")
    print("|---|---|" + "---|" * len(tags))
    for r in readers:
        for m in methods:
            cells = []
            for t in tags:
                X = pooled(dss, d, m, r, 4000, t)
                cells.append(f"{100 * sum(v['c'] for v in X.values()) / len(X):.1f}" if X else "–")
            print(f"| {RD[r]} | {LABEL.get(m, m)} | " + " | ".join(cells) + " |")


def continuity(title, dss, methods, readers=RD):
    """LongState-Continuity: J = TPR - FPR on 'contradiction' (bootstrap over pairs, or items on unpaired sets) and
    pair accuracy (both members right); items whose gold label fails the independent label check are dropped."""
    import continuity_stats as cs
    print(f"\n### {title}\n")
    print("| Method | " + " | ".join(f"{RD[r]} J [95% CI] / pair acc (tokens/q)" for r in readers) + " |")
    print("|---|" + "---|" * len(readers))
    npairs = {}
    unit_ok = {}
    rows = []
    for m in methods:
        cells = []
        for r in readers:
            units, ok = [], True
            for ds in dss:
                f = os.path.join(ROOT, "runs", "results", f"{ds}_d16_{m}_{r}_b4000.jsonl")
                if not os.path.exists(f):
                    ok = False
                    break
                gold = {json.loads(l)["qid"]: json.loads(l) for l in
                        open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"), encoding="utf-8")}
                bad = {b[0] for b in cs.check_continuity_labels.check(ds)[0]}
                rs = [json.loads(l) for l in open(f, encoding="utf-8")]
                rs = [x for x in rs if x["qid"] in gold and x["qid"] not in bad]
                if any("pair" in q for q in gold.values()):
                    by = collections.defaultdict(list)
                    for x in rs:
                        by[(ds, gold[x["qid"]]["pair"])].append(x)
                    for k, v in by.items():
                        if len(v) == 2:
                            units.append(v)
                            unit_ok.setdefault((m, r), {})[k] = all(x["correct"] for x in v)
                else:
                    units += [[x] for x in rs]
                    for x in rs:
                        unit_ok.setdefault((m, r), {})[(ds, x["qid"])] = bool(x["correct"])
            if not ok or not units:
                cells.append("–")
                continue
            recs = [x for u in units for x in u]
            lo, hi = cs.boot_j(units)
            pa = (f"{100 * sum(all(x['correct'] for x in u) for u in units) / len(units):.1f}"
                  if len(units[0]) == 2 else "n/a")
            tok = sum(x.get("ctx_tokens") or 0 for x in recs) / len(recs)
            cells.append(f"{cs.j_of(recs):.1f} [{lo:.0f},{hi:.0f}] / {pa} ({tok:,.0f})")
            npairs[r] = max(npairs.get(r, 0), len(units))
        rows.append((m, cells))
    # exact McNemar on unit correctness (pair right = both members right) against CMM v4, Holm within the table
    ref = "mem-cmm4"
    tests = []
    for m, _ in rows:
        for r in readers:
            A, B = unit_ok.get((ref, r)), unit_ok.get((m, r))
            if m == ref or not A or not B:
                continue
            ks = [k for k in A if k in B]
            w = sum(1 for k in ks if A[k] and not B[k])
            l = sum(1 for k in ks if B[k] and not A[k])
            tests.append((m, r, w, l, mcnemar(w, l)))
    adj = {(m, r): p for (m, r, _, _, _), p in zip(tests, holm([t[4] for t in tests]))} if tests else {}
    wl = {(m, r): (w, l) for m, r, w, l, _ in tests}
    for m, cells in rows:
        out = []
        for r, c in zip(readers, cells):
            if (m, r) in wl:
                w, l = wl[(m, r)]
                c += f" {'*' if adj[(m, r)] < 0.05 else ''}{w}/{l}"
            out.append(c)
        print(f"| {LABEL.get(m, m)} | " + " | ".join(out) + " |")
    print(f"\nunits (pairs, or items on unpaired sets) per reader: {npairs}. J in points; 95% bootstrap CI over units. "
          f"w/l = units CMM v4 gets right and the method wrong / the reverse; * = Holm-corrected exact McNemar p < 0.05 "
          f"over the {len(tests)} tests of this table.")


def subset(ds, qids):
    KEEP[ds] = set(qids)


def main():
    W = ["saga_v5_s7", "saga_v5_s8"]
    saga_m = ["mem-cmm4a", "mem-cmm4ac", "mem-cmm4", "mem-cmm4c", "mem-cmm3", "mem-cmm3c", "mem-cmm2", "mem-cmm2l",
              "mem-cmm2c", "mem-cmm", "mem-cmmc", "mem-namegrep_co", "mem-pbm25",
              "mem-ledger", "mem-cmm2cq14", "mem-cmm2cq8", "hybrid", "bm25", "oracle_para"]
    print("# Final test (frozen v4; splits never used for design)")
    table("LongState-Saga, fresh worlds s7+s8, ~0.5M tokens", W, "d16", saga_m)
    table("LongState-Saga, fresh worlds s7+s8, ~1.9M tokens", W, "d64", saga_m)
    table("LongState-Saga s7, filler without names (~0.5M)", ["saga_v5n_s7"], "d16", saga_m)
    table("Real novels, group C (Emma, Wuthering Heights, Sense and Sensibility; judged)",
          ["nhq_emma", "nhq_wuther", "nhq_sense"], "full",
          ["mem-cmm4a", "mem-cmm4", "mem-cmm4c", "mem-cmm3", "mem-cmm3c", "mem-cmm2", "mem-cmm2c", "mem-cmm2l",
           "mem-namegrep_co", "mem-pbm25", "mem-ledger", "hybrid", "bm25", "oracle_para", "closedbook"])
    for d in ("d4", "d16", "d64", "d256"):
        table(f"LongState-Code, test worlds s2+s3, {d}", ["code_s2", "code_s3"], d,
              ["mem-cmm4a", "mem-cmm4", "mem-cmm4c", "mem-cmm2", "mem-cmm2l", "mem-cmm2c", "mem-namegrep_co",
               "mem-pbm25", "mem-ledger", "hybrid", "bm25", "oracle_para"])
    table("LoCoMo chat (10 conversations; judged)", [f"locomo_{i}" for i in range(10)], "full",
          ["mem-cmm4", "mem-cmm4c", "mem-cmm2", "mem-cmm2l", "mem-cmm2c", "mem-pbm25", "mem-ledger", "hybrid", "bm25",
           "oracle_para", "full"], ref="mem-cmm4")
    # two exploratory variants that no claim uses are no longer printed
    sweep(W, "d16", ["mem-pbm25", "hybrid", "mem-cmm4", "mem-cmm4c"])
    variants("Reader-prompt sensitivity (s7+s8, 0.5M)", W, "d16", ["mem-pbm25", "hybrid", "mem-cmm4c", "mem-cmm2c"],
             ["", "_p-minimal", "_p-decisive"])
    variants("Storage-time ablations of v4 (s7+s8, 0.5M, Haiku)", W, "d16", ["mem-cmm4"],
             ["", "_abl-resolve", "_abl-anchor+rlines", "_abl-ground+vote+demote"],
             readers=("claude-claude-haiku-4-5-20251001",))
    # --- additions ---
    H, G = "claude-claude-haiku-4-5-20251001", "codex-gpt-6.1-sol"
    Q14, Q8 = "ollama-qwen3-14b", "ollama-qwen3-8b"
    table("Compaction and extraction baselines, s7+s8 ~0.5M (agent-style compaction reads 4k or 16k tokens)", W, "d16",
          ["mem-cmm4a", "mem-cmm4", "mem-cmm4au", "mem-cmm4map", "mem-compact4k", "mem-compact4kq", "mem-compact16k",
           "mem-ledger", "mem-ledger2", "hybrid", "mem-pbm25"])
    variants("Compaction by compactor model (default = Haiku compacts; _built-gpt = GPT compacts)", W, "d16",
             ["mem-compact4k"], ["", "_built-gpt"], readers=(H, G))
    table("Real novels C: compaction and extraction (judged)", ["nhq_emma", "nhq_wuther", "nhq_sense"], "full",
          ["mem-cmm4a", "mem-cmm4", "mem-cmm4map", "mem-compact4k", "mem-compact16k", "mem-ledger", "mem-ledger2", "hybrid"])
    KEEP.clear()
    ama_m = ["mem-cmm4a", "mem-cmm4", "mem-cmm4map16", "mem-namegrep_co", "mem-pbm25", "hybrid", "bm25", "mem-compact16k",
             "full"]
    table("AMA-Bench GAIA trajectories (14, 0.19M-1.06M tokens; expert questions; benchmark judge wording)",
          [f"ama_g{k:02d}" for k in range(1, 15)], "full", ama_m, readers=(H, G, Q14), tag="_p-minimal")
    table("AMA-Bench SWE-bench trajectories (12, 69k-90k tokens)", [f"ama_w{k:02d}" for k in range(1, 13)], "full",
          ama_m, readers=(H, G, Q14), tag="_p-minimal")
    # gold-confirmed subsets: the GPT gold audit (bench/ama_gold_audit.py) labels each reference answer ok / ambiguous
    # / wrong against the trajectory; AMA-Bench issue #15 reports the same kind of conflict for SOFTWARE
    for name, dss in (("GAIA", [f"ama_g{k:02d}" for k in range(1, 15)]), ("SWE-bench", [f"ama_w{k:02d}" for k in range(1, 13)])):
        n_ok = 0
        for ds in dss:
            p = os.path.join(ROOT, "data", ds, "gold_audit_gpt.json")
            if os.path.exists(p):
                ok = [k for k, v in json.load(open(p, encoding="utf-8")).items() if v["label"] == "ok"]
                subset(ds, ok)
                n_ok += len(ok)
        table(f"AMA-Bench {name}, gold-confirmed questions only ({n_ok} questions labelled ok by the GPT gold audit)",
              dss, "full", ama_m, readers=(H, G, Q14), tag="_p-minimal")
        KEEP.clear()
    cont_m = ["mem-cmm4a", "mem-cmm4", "mem-cmm4c", "mem-cmm4au", "mem-cmm4map", "mem-cmm2", "mem-namegrep_co", "mem-pbm25",
              "mem-ledger", "mem-compact4k", "hybrid", "bm25", "oracle_para", "closedbook"]
    continuity("LongState-Continuity, paired test sets (worlds 7+8, ~0.5M tokens)", ["cont2_s7", "cont2_s8"], cont_m,
               readers=(H, G, Q14))
    continuity("LongState-Continuity, development sets (worlds 4+5; unpaired; label errors dropped)",
               ["cont_s4", "cont_s5"], cont_m, readers=(H,))
    agg_m = ["mem-cmm4a", "mem-cmm4", "mem-cmm4c", "mem-cmm4map", "mem-namegrep_co", "mem-pbm25", "mem-ledger",
             "mem-compact4k", "hybrid", "bm25", "oracle_para", "closedbook"]
    for part, pre in (("entity-anchored counting, enumeration and ordering", "A_"),
                      ("global counting (totals, per place, per chapter range)", "G_")):
        for ds in ("agg_s7", "agg_s8"):
            subset(ds, [json.loads(l)["qid"] for l in open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"),
                                                           encoding="utf-8") if json.loads(l)["qtype"].startswith(pre)])
        table(f"LongState-Aggregate, worlds 7+8 (~0.5M tokens): {part}", ["agg_s7", "agg_s8"], "d16", agg_m,
              readers=(H, G, Q14))
        KEEP.clear()
    print("\n### Reading-order control (post-hoc; same paragraphs, newest first)\n")
    print("| Split | Reader | CMM v4 | CMM v4, newest first | Paragraph BM25 | Paragraph BM25, newest first |")
    print("|---|---|---|---|---|---|")
    for name, dss in (("dev s4+s5", ["saga_v5_s4", "saga_v5_s5"]), ("test s7+s8", W)):
        for r in (H, Q14, Q8):
            cells = []
            for m in ("mem-cmm4", "mem-cmm4r", "mem-pbm25", "mem-pbm25r"):
                X = pooled(dss, "d16", m, r)
                cells.append(f"{100 * sum(v['c'] for v in X.values()) / len(X):.1f}" if X else "–")
            print(f"| {name} | {RD[r]} | " + " | ".join(cells) + " |")
    variants("Question placed before and after the context (Lost-in-the-Middle mitigation; dev s4+s5)",
             ["saga_v5_s4", "saga_v5_s5"], "d16", ["mem-cmm4", "mem-pbm25", "mem-cmm2c"], ["", "_qboth"],
             readers=(H, Q14, Q8))
    print("\n### Who writes and who corrects the cards (dev s4+s5, ~0.5M)\n")
    print("| Reader | Condition | Accuracy |")
    print("|---|---|---|")
    for r, ms in ((Q14, ["mem-cmm2l", "mem-cmm2cq14", "mem-cmm2cw14", "mem-cmm2cw14H", "mem-cmm2cv14", "mem-cmm2c",
                         "mem-cmm2cwH14"]),
                  (Q8, ["mem-cmm2l", "mem-cmm2cq8", "mem-cmm2cw8", "mem-cmm2cw8H", "mem-cmm2cv8", "mem-cmm2c"])):
        for m in ms:
            X = pooled(["saga_v5_s4", "saga_v5_s5"], "d16", m, r)
            print(f"| {RD[r]} | {LABEL.get(m, m)} | "
                  f"{(f'{100 * sum(v[chr(99)] for v in X.values()) / len(X):.1f} (n={len(X)})') if X else '–'} |")


if __name__ == "__main__":
    main()
