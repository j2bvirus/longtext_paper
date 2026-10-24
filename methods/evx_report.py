"""Report of the event-type index test (no LLM calls).

Accuracy per method and reader on the G2 counting questions, pooled over the fresh worlds 9-10 (generated after the
freeze) and, separately, over worlds 7-8 (other questions on them were seen before); bins: true count 0 / non-zero;
exact McNemar (two-sided) of the frozen evx4v4 against every other method, Holm-corrected within each reader and
world group.  Index quality: per world, the recall of the event tagger for the world's deaths, births and weddings
(a gold event paragraph counts as found if it carries a narrated event of the routed kind), and the number of
'wrong zero' answers (true count > 0, answer 0).

python methods/evx_report.py
"""
import bisect
import json
import os
import sys
from collections import defaultdict
from math import comb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import cmm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READERS = {"Haiku 4.5": "claude-claude-haiku-4-5-20251001", "GPT-6.1-sol": "codex-gpt-6.1-sol"}
METHODS = [("mem-evx4v4", "event index v4 (frozen)"), ("mem-evx4v4n", "  same, no completeness statement"),
           ("mem-evxv4", "  same, no identity index"), ("oracle_para", "gold evidence paragraphs"),
           ("mem-cmm4", "CMM v4"), ("mem-pbm25", "paragraph BM25"), ("hybrid", "hybrid RAG")]
GROUPS = {"fresh worlds 9-10": ["agg2_s9", "agg2_s10"], "worlds 7-8 (seen)": ["agg2_s7", "agg2_s8"]}
if "--v5" in sys.argv:  # v5 test (runs/evx5_test_pipeline.sh): v5 is the reference
    METHODS = [("mem-evx4v5", "event index v5 (frozen)"), ("mem-evx4v5n", "  same, no completeness statement"),
               ("mem-evxv5", "  same, no identity index"), ("mem-evx4v4", "event index v4"),
               ("oracle_para", "gold evidence paragraphs"), ("mem-cmm4", "CMM v4"), ("mem-pbm25", "paragraph BM25"),
               ("hybrid", "hybrid RAG")]
    GROUPS = {"fresh worlds 11-12 (after the v5 freeze)": ["agg2_s11", "agg2_s12"],
              "worlds 9-10 (seen by v5)": ["agg2_s9", "agg2_s10"], "worlds 7-8 (seen)": ["agg2_s7", "agg2_s8"]}
REF = METHODS[0][0]
MEMNAME = REF.replace("mem-", "")


def mcnemar(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run = [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        out[i] = run
    return out


def load(ds, m, r):
    f = os.path.join(ROOT, "runs", "results", f"{ds}_d16_{m}_{r}_b4000.jsonl")
    if not os.path.exists(f):
        return None
    qs = {json.loads(l)["qid"]: json.loads(l) for l in open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"),
                                                              encoding="utf-8")}
    out = {}
    for l in open(f, encoding="utf-8"):
        x = json.loads(l)
        q = qs[x["qid"]]
        out[(ds, x["qid"])] = {"c": int(x["correct"]), "gold": q["answer"]["gold"], "pred": x["pred"],
                               "qtype": q["qtype"], "tok": x["ctx_tokens"]}
    return out


def accuracy_tables():
    for gname, dss in GROUPS.items():
        print(f"\n### {gname}\n")
        print("| Method | " + " | ".join(f"{r}: all / count 0 / count > 0 (tokens)" for r in READERS) + " |")
        print("|---|" + "---|" * len(READERS))
        res = {(m, r): {} for m, _ in METHODS for r in READERS.values()}
        for m, _ in METHODS:
            for r in READERS.values():
                for ds in dss:
                    d = load(ds, m, r)
                    if d:
                        res[(m, r)].update(d)
        tests = {}
        for rn, r in READERS.items():
            ref = res[(REF, r)]
            ps, keys = [], []
            for m, _ in METHODS[1:]:
                o = res[(m, r)]
                ks = set(ref) & set(o)
                if not ks:
                    continue
                w = sum(1 for k in ks if ref[k]["c"] and not o[k]["c"])
                l_ = sum(1 for k in ks if o[k]["c"] and not ref[k]["c"])
                ps.append(mcnemar(w, l_))
                keys.append((m, w, l_))
            for (m, w, l_), p in zip(keys, holm(ps)):
                tests[(m, r)] = (w, l_, p)
        for m, label in METHODS:
            cells = []
            for rn, r in READERS.items():
                d = res[(m, r)]
                if not d:
                    cells.append("–")
                    continue
                z = [v for v in d.values() if v["gold"] == 0]
                nz = [v for v in d.values() if v["gold"] != 0]
                pct = lambda xs: f"{100 * sum(v['c'] for v in xs) / len(xs):.1f}" if xs else "–"  # noqa: E731
                tok = sum(v["tok"] for v in d.values()) / len(d)
                t = tests.get((m, r))
                sig = f" {'*' if t[2] < 0.05 else ''}{t[0]}/{t[1]}" if t else ""
                cells.append(f"{pct(list(d.values()))} / {pct(z)} / {pct(nz)} ({tok:,.0f}){sig}")
            print(f"| {label} | " + " | ".join(cells) + " |")
        n = len(res[(REF, READERS['Haiku 4.5'])])
        print(f"\nn = {n} questions per reader. w/l = questions the reference (first row) gets right and the method wrong / the "
              f"reverse; * = Holm-corrected exact McNemar p < 0.05 over the {len(METHODS) - 1} comparisons of each reader.")


def index_quality():
    print("\n### Event-tagger recall of the world's events and wrong zeros (event index v4)\n")
    print("| World | deaths found | births found | weddings found | wrong zeros Haiku / GPT |")
    print("|---|---|---|---|---|")
    for ds in [d for g in GROUPS.values() for d in g]:
        ddir = os.path.join(ROOT, "data", ds)
        text, spans, qs, world = core.load_dataset(ddir, "d16")
        paras = cmm.Paras(core.chunk_record(text, 300))
        starts = [it["start"] for it in paras.items]
        w = json.load(open(os.path.join(ddir, "evx4w_write_d16_claude-claude-haiku-4-5-20251001.json"), encoding="utf-8"))
        canon = json.load(open(os.path.join(ddir, "evx4w_idle_d16_claude-claude-haiku-4-5-20251001.json"),
                               encoding="utf-8"))["canon"]
        tags = defaultdict(set)
        for e in w["events"]:
            if e["status"] == "narrated":
                tags[e["pid"]].add(canon.get(e["type"], e["type"]))
        route = defaultdict(set)  # kinds the router chose for each question kind
        rp = os.path.join(ddir, "evx4w_route_d16_claude-claude-haiku-4-5-20251001.jsonl")
        qtype = {q["qid"]: q["qtype"] for q in qs}
        for l in open(rp, encoding="utf-8"):
            x = json.loads(l)
            t = qtype.get(x["qid"], "")
            key = "DEATH" if "DEATH" in t else "BIRTH" if "BIRTH" in t else "MARRY" if "WED" in t else None
            if key:
                route[key] |= set(x["types"])
        ev = json.load(open(os.path.join(ddir, "events_GOLD.json"), encoding="utf-8"))
        cells = []
        for key in ("DEATH", "BIRTH", "MARRY"):
            gold = [e for e in ev if e["type"] == key and not (key == "MARRY" and e["chapter"] == 1)]
            found = 0
            for e in gold:
                pid = bisect.bisect_right(starts, spans[e["id"]][0]) - 1
                found += bool(tags[pid] & route[key])
            cells.append(f"{found}/{len(gold)}")
        wz = []
        for r in READERS.values():
            d = load(ds, REF, r) or {}
            wz.append(str(sum(1 for v in d.values() if v["gold"] != 0 and str(v["pred"]).strip().startswith("0"))))
        print(f"| {ds} | " + " | ".join(cells) + f" | {' / '.join(wz)} |")
    print("\nA gold event paragraph is found if the tagger gave it a narrated event of a kind the router chose for "
          "questions about that event (all questions of the world pooled).")


def statement_precision():
    """per question: the event paragraphs selected by the frozen evx4v4 (offline, cached routing only) against the
    gold evidence paragraphs; a complete-set statement is true if every gold paragraph is selected"""
    import types
    import llm
    import memory
    orig = llm.call

    def cached_only(*a, **k):
        r = orig(*a, **k)
        if not r.get("cached"):
            raise RuntimeError("offline report: a non-cached LLM call would be needed")
        return r
    llm.call = cached_only
    os.environ["MEM_WAIT_ONLY"] = "1"
    print("\n### Selected event set against the gold evidence, per question (event index v4)\n")
    print("| Worlds | questions | statement given | statement true (all gold selected) | gold paragraphs selected | "
          "extra paragraphs selected |")
    print("|---|---|---|---|---|---|")
    for gname, dss in GROUPS.items():
        n = given = true = 0
        g_tot = g_sel = extra = 0
        per_type = defaultdict(lambda: [0, 0])
        for ds in dss:
            ddir = os.path.join(ROOT, "data", ds)
            text, spans, qs, world = core.load_dataset(ddir, "d16")
            chunks = core.chunk_record(text, 300)
            m = memory.make(MEMNAME, text=text, chunks=chunks, ddir=ddir, density="d16",
                            args=types.SimpleNamespace(builder="claude:claude-haiku-4-5-20251001", build_workers=1,
                                                       budget=4000, num_ctx=16384))
            m.build()
            m.p_route = os.devnull  # do not append to the routing log
            starts = [it["start"] for it in m.paras.items]
            for q in qs:
                types_, names = m.route(q)
                if not types_:
                    continue
                nar = {i for i in set().union(*(m.by_type[t]["narrated"] for t in types_)) if m._matches(i, names)}
                tok = sum(m.paras.items[i]["tokens"] + 15 for i in nar)
                gold = {bisect.bisect_right(starts, spans[e][0]) - 1 for e in q["evidence"] if e in spans}
                n += 1
                stated = tok <= 4000 * m.narrated_share
                given += stated
                ok = gold <= nar
                true += stated and ok
                g_tot += len(gold)
                g_sel += len(gold & nar)
                extra += len(nar - gold)
                per_type[q["qtype"]][0] += ok
                per_type[q["qtype"]][1] += 1
        print(f"| {gname} | {n} | {given} | {true} | {g_sel}/{g_tot} | {extra} |")
        print("  complete selection by question type: " +
              ", ".join(f"{t} {a}/{b}" for t, (a, b) in sorted(per_type.items())))


if __name__ == "__main__":
    accuracy_tables()
    index_quality()
    statement_precision()
