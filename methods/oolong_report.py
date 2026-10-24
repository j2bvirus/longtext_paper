"""Report of the Oolong-real runs (no LLM calls).

python methods/oolong_report.py --split test [--methods index,index_bSonnet,bm25,full,closed]
Mean official score (harness-identical scorer, recomputed from the stored outputs) by window size (episodes), by question type, and paired differences of the first method against
each other method on the questions both answered, with 95% bootstrap intervals over windows (2,000 resamples, seed 0;
questions of one window stay together).  Windows share episodes (one campaign per split), so these are intervals conditional on the episodes of the split, not intervals for new episodes or campaigns.
"""
import argparse
import json
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oolong_score  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "runs", "results_oolong")


def load(split, m, reader):
    tag = ""
    if "_b" in m:
        m, tag = m.split("_b", 1)
        tag = "_b" + tag
    f = os.path.join(R, f"{split}_{m}_{reader}{tag}.jsonl")
    if not os.path.exists(f):
        return {}
    out = {}
    for l in open(f, encoding="utf-8"):
        x = json.loads(l)
        if x["id"] in out:
            continue
        # score again from the stored output with the harness-identical scorer;
        # a run that could not read the window (error, e.g. over the reader's input limit) is 'infeasible' and is
        # kept out of the accuracy means (reported as a count)
        x["score_stored"] = x["score"]
        x["score"], _ = oolong_score.score(x["answer"], x.get("raw") or "")
        x["infeasible"] = bool(x.get("error"))
        out[x["id"]] = x
    return out


def feasible(d):
    return {k: v for k, v in d.items() if not v["infeasible"]}


def boot_diff(a, b, keys, B=2000, seed=0):
    byw = defaultdict(list)
    for k in keys:
        byw[a[k]["window"]].append(a[k]["score"] - b[k]["score"])
    ws = sorted(byw)
    rng = random.Random(seed)
    vals = []
    for _ in range(B):
        s = [d for _ in ws for d in byw[ws[rng.randrange(len(ws))]]]
        vals.append(sum(s) / len(s))
    vals.sort()
    return sum(sum(v) for v in byw.values()) / len(keys), vals[int(0.025 * B)], vals[int(0.975 * B) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--methods", default="index,index_bSonnet,bm25,full,closed")
    ap.add_argument("--reader", default="claude-claude-haiku-4-5-20251001")
    a = ap.parse_args()
    ms = a.methods.split(",")
    raw = {m: load(a.split, m, a.reader) for m in ms}
    data = {m: feasible(raw[m]) for m in ms}
    for m in ms:
        n_inf = len(raw[m]) - len(data[m])
        if n_inf:
            print(f"{m}: {n_inf} of {len(raw[m])} questions infeasible (the reader could not read the window); left out below")
    sizes = sorted({x["n_eps"] for d in data.values() for x in d.values()})
    print("| Method | " + " | ".join(f"{s} ep" for s in sizes) + " | all | 16+24 ep |")
    print("|---|" + "---|" * (len(sizes) + 2))
    for m in ms:
        d = data[m]
        if not d:
            continue
        cells = []
        for s in sizes:
            v = [x["score"] for x in d.values() if x["n_eps"] == s]
            cells.append(f"{sum(v) / len(v):.3f} ({len(v)})" if v else "–")
        big = [x["score"] for x in d.values() if x["n_eps"] >= 16]
        print(f"| {m} | " + " | ".join(cells) + f" | {sum(x['score'] for x in d.values()) / len(d):.3f} ({len(d)}) | "
              + (f"{sum(big) / len(big):.3f} ({len(big)})" if big else "–") + " |")
    ref = data[ms[0]]
    print(f"\nPaired differences, {ms[0]} minus each method (mean, 95% window-bootstrap interval):")
    for m in ms[1:]:
        d = data[m]
        keys = [k for k in ref if k in d]
        if not keys:
            continue
        mean, lo, hi = boot_diff(ref, d, keys)
        big = [k for k in keys if ref[k]["n_eps"] >= 16]
        line = f"- {m}: all {mean:+.3f} [{lo:+.3f}, {hi:+.3f}] (n={len(keys)})"
        if big:
            mb, lb, hb = boot_diff(ref, d, big)
            line += f"; 16+24 episodes {mb:+.3f} [{lb:+.3f}, {hb:+.3f}] (n={len(big)})"
        print(line)
    print("\nBy question type (all windows):")
    for m in ms:
        d = data[m]
        if not d:
            continue
        g = defaultdict(list)
        for x in d.values():
            g[x["question_type"]].append(x["score"])
        print(f"- {m}: " + ", ".join(f"{t} {sum(v) / len(v):.3f} ({len(v)})" for t, v in sorted(g.items())))


if __name__ == "__main__":
    main()
