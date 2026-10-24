"""Paired differences CMM v4 minus v4 without the completeness statement (cmm4n), with 95% bootstrap intervals.
Continuity: J difference, resampling pairs. Aggregate: anchored (A_) and global (G_) accuracy difference,
resampling questions. Read-only on runs/ and data/."""
import json
import os
import random
import re
import sys
from collections import defaultdict

ROOT = sys.argv[1]
READERS = {"Haiku": "claude-claude-haiku-4-5-20251001", "GPT": "codex-gpt-6.1-sol"}


def says_contradiction(pred):
    w = re.sub(r"[^a-z0-9 ]+", " ", (pred or "").lower()).split()
    return bool(w) and w[0] == "contradiction"


def qs(ds):
    return {json.loads(l)["qid"]: json.loads(l) for l in open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"), encoding="utf-8")}


def res(ds, m, r):
    f = os.path.join(ROOT, "runs", "results", f"{ds}_d16_{m}_{r}_b4000.jsonl")
    return {json.loads(l)["qid"]: json.loads(l) for l in open(f, encoding="utf-8")}


def j_of(items):  # items: list of (gold_is_contra, says_contra)
    pos = [s for g, s in items if g]
    neg = [s for g, s in items if not g]
    return 100 * (sum(pos) / len(pos) - sum(neg) / len(neg))


for rn, r in READERS.items():
    units = defaultdict(lambda: {"a": [], "b": []})
    for ds in ["cont2_s7", "cont2_s8"]:
        Q = qs(ds)
        A, B = res(ds, "mem-cmm4", r), res(ds, "mem-cmm4n", r)
        for qid, q in Q.items():
            if q.get("excluded") or qid not in A or qid not in B:
                continue
            g = q["answer"]["gold"] == "contradiction"
            u = (ds, q.get("pair", qid))
            units[u]["a"].append((g, says_contradiction(A[qid]["pred"])))
            units[u]["b"].append((g, says_contradiction(B[qid]["pred"])))
    us = list(units.values())
    d0 = j_of([x for u in us for x in u["a"]]) - j_of([x for u in us for x in u["b"]])
    rng = random.Random(0)
    st = []
    for _ in range(2000):
        smp = [us[rng.randrange(len(us))] for _ in us]
        try:
            st.append(j_of([x for u in smp for x in u["a"]]) - j_of([x for u in smp for x in u["b"]]))
        except ZeroDivisionError:
            pass
    st.sort()
    n = len(st)
    print(f"continuity {rn}: units {len(us)} J diff (v4 - nocert) {d0:+.1f} [{st[int(0.025 * n)]:+.1f}, {st[int(0.975 * n) - 1]:+.1f}]")

    for scope in ["A_", "G_"]:
        pairs = []
        for ds in ["agg_s7", "agg_s8"]:
            Q = qs(ds)
            A, B = res(ds, "mem-cmm4", r), res(ds, "mem-cmm4n", r)
            for qid, q in Q.items():
                if q.get("excluded") or not q["qtype"].startswith(scope) or qid not in A or qid not in B:
                    continue
                pairs.append((A[qid]["correct"], B[qid]["correct"]))
        d0 = 100 * sum(a - b for a, b in pairs) / len(pairs)
        st = []
        for _ in range(2000):
            smp = [pairs[rng.randrange(len(pairs))] for _ in pairs]
            st.append(100 * sum(a - b for a, b in smp) / len(smp))
        st.sort()
        w = sum(1 for a, b in pairs if a and not b)
        l = sum(1 for a, b in pairs if b and not a)
        print(f"aggregate {scope} {rn}: n {len(pairs)} acc {100 * sum(a for a, _ in pairs) / len(pairs):.1f} vs "
              f"{100 * sum(b for _, b in pairs) / len(pairs):.1f} diff {d0:+.1f} [{st[50]:+.1f}, {st[1949]:+.1f}] +{w}/-{l}")
