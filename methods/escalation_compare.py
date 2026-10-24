"""Certificate-triggered against reader-triggered budget escalation (no LLM calls; read-only).

CMM v4-adaptive (mem-cmm4a) rebuilds the context at 3x the budget when the completeness guarantee fails.
The `_escU3` runs (run_eval --escalate_unknown 3) re-read at 3x the budget when the reader answers 'unknown'.
For each split and reader: accuracy and mean reader tokens of each condition, and exact McNemar (two-sided) for
the listed pairs.  Free-form splits use the GPT judge (runs/judged_gpt), as in paper/tables_final.md.

python methods/escalation_compare.py
"""
import json
import random
import os
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H, Q14 = "claude-claude-haiku-4-5-20251001", "ollama-qwen3-14b"
SPLITS = [("Saga s7+s8, 0.5M", ["saga_v5_s7", "saga_v5_s8"], "d16", [H, Q14]),
          ("Saga s7+s8, 1.9M", ["saga_v5_s7", "saga_v5_s8"], "d64", [H]),
          ("Novels C", ["nhq_emma", "nhq_wuther", "nhq_sense"], "full", [H])]
CONDS = [("mem-cmm4", ""), ("mem-cmm4a", ""), ("mem-cmm4", "_escU3"), ("mem-pbm25", ""), ("mem-pbm25", "_escU3"),
         ("hybrid", ""), ("hybrid", "_escU3")]
PAIRS = [(("mem-cmm4a", ""), ("mem-cmm4", "_escU3")), (("mem-cmm4", "_escU3"), ("mem-cmm4", "")),
         (("mem-cmm4", "_escU3"), ("mem-pbm25", "_escU3")), (("mem-cmm4", "_escU3"), ("hybrid", "_escU3")),
         (("mem-cmm4a", ""), ("mem-pbm25", "_escU3")), (("mem-cmm4a", ""), ("hybrid", "_escU3"))]


def mcnemar(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def load(dss, d, m, r, tag):
    out = {}
    for ds in dss:
        f = os.path.join(ROOT, "runs", "results", f"{ds}_{d}_{m}_{r}_b4000{tag}.jsonl")
        if not os.path.exists(f):
            return None
        qs = {json.loads(l)["qid"]: json.loads(l) for l in open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"), encoding="utf-8")}
        judged = None
        if ds.startswith("nhq_"):
            jf = os.path.join(ROOT, "runs", "judged_gpt", os.path.basename(f)[:-6] + ".json")
            if not os.path.exists(jf):
                return None
            judged = json.load(open(jf))
        for l in open(f, encoding="utf-8"):
            x = json.loads(l)
            if qs[x["qid"]].get("excluded"):
                continue
            c = judged.get(x["qid"]) if judged is not None else x["correct"]
            if c is None:
                continue
            out[(ds, x["qid"])] = (int(c), x["ctx_tokens"], (ds, qs[x["qid"]].get("subject", x["qid"])))
    return out


def boot_diff(a, b, n=2000, seed=0):
    """paired accuracy difference a - b in points with a 95% bootstrap interval over question subjects (questions
    without a subject are their own cluster); clusters are sorted so that the interval does not depend on file order"""
    ks = sorted(set(a) & set(b))
    cl = {}
    for k in ks:
        cl.setdefault(a[k][2], []).append(a[k][0] - b[k][0])
    cls = [cl[c] for c in sorted(cl)]
    r = random.Random(seed)
    st = []
    for _ in range(n):
        s = m = 0
        for _ in cls:
            g = cls[r.randrange(len(cls))]
            s += sum(g)
            m += len(g)
        st.append(100 * s / m)
    st.sort()
    return 100 * sum(sum(g) for g in cls) / len(ks), st[int(0.025 * n)], st[int(0.975 * n) - 1], len(cls)


def name(mt):
    return mt[0] + mt[1]


for title, dss, d, readers in SPLITS:
    for r in readers:
        res = {mt: load(dss, d, mt[0], r, mt[1]) for mt in CONDS}
        print(f"\n## {title}, reader {r}")
        for mt, v in res.items():
            if v:
                print(f"  {name(mt):18s} n={len(v)} acc={100 * sum(x[0] for x in v.values()) / len(v):.1f} "
                      f"tokens={sum(x[1] for x in v.values()) / len(v):,.0f}")
        for a, b in PAIRS:
            if not res.get(a) or not res.get(b):
                continue
            ks = set(res[a]) & set(res[b])
            w = sum(1 for k in ks if res[a][k][0] and not res[b][k][0])
            l_ = sum(1 for k in ks if res[b][k][0] and not res[a][k][0])
            d, lo, hi, ncl = boot_diff(res[a], res[b])
            print(f"  {name(a)} vs {name(b)}: +{w}/-{l_} p={mcnemar(w, l_):.4f}; "
                  f"difference {d:+.1f} [{lo:+.1f}, {hi:+.1f}] ({ncl} clusters)")
