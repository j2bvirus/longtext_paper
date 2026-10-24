"""Continuity-check statistics (LongState-Continuity, dev cont_s* and paired test cont2_s*).

'contradiction' is the positive class.  Per run: accuracy, TPR (contradictions caught), FPR (consistent paragraphs
flagged), J = TPR - FPR with Wilson 95% intervals for TPR and FPR and a bootstrap interval for J (resampling pairs
on paired sets, items otherwise), pair accuracy (both members right) on paired sets, and mean reader context tokens.
Items whose gold label disagrees with the world's end state (bench/check_continuity_labels.py) are dropped and the
number dropped is shown; --keep_bad keeps them.

python methods/continuity_stats.py [--sets cont_s4,cont_s5] [--by_type] [--keep_bad]
"""
import argparse
import glob
import json
import math
import os
import random
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import check_continuity_labels  # noqa: E402


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * (c - h), 100 * (c + h)


def says_contradiction(pred):
    """the verdict is the first normalised word of the answer line, exactly as core.score scores 'verdict' answers
    (an exact string comparison disagreed with the scorer on punctuated answers)"""
    w = re.sub(r"[^a-z0-9 ]+", " ", (pred or "").lower()).split()
    return bool(w) and w[0] == "contradiction"


def rates(recs):
    pos = [r for r in recs if r["gold"] == "contradiction"]
    neg = [r for r in recs if r["gold"] == "consistent"]
    tp = sum(says_contradiction(r["pred"]) for r in pos)
    fp = sum(says_contradiction(r["pred"]) for r in neg)
    return tp, len(pos), fp, len(neg)


def j_of(recs):
    tp, npos, fp, nneg = rates(recs)
    return 100 * (tp / max(1, npos) - fp / max(1, nneg))


def boot_j(units, B=2000, seed=0):
    rng = random.Random(seed)
    vals = []
    for _ in range(B):
        s = [r for _ in units for r in units[rng.randrange(len(units))]]
        vals.append(j_of(s))
    vals.sort()
    return vals[int(0.025 * B)], vals[int(0.975 * B) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="")
    ap.add_argument("--by_type", action="store_true")
    ap.add_argument("--keep_bad", action="store_true")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(ROOT, "runs", "results", "cont*_d16_*.jsonl")))
    want = set(a.sets.split(",")) if a.sets else None
    rows = defaultdict(list)
    for f in files:
        base = os.path.basename(f)[:-6]
        ds = re.match(r"(cont2?_s\d+)_", base).group(1)
        if want and ds not in want:
            continue
        rows[ds].append((base[len(ds) + 5:], f))
    for ds in sorted(rows):
        gold = {}
        for line in open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"), encoding="utf-8"):
            q = json.loads(line)
            gold[q["qid"]] = q
        bad = set() if a.keep_bad else {b[0] for b in check_continuity_labels.check(ds)[0]}
        paired = any("pair" in q for q in gold.values())
        print(f"\n## {ds}: {len(gold)} items{' in ' + str(len({q['pair'] for q in gold.values()})) + ' pairs' if paired else ''}"
              f"; label errors dropped: {len(bad)}")
        print("| run | n | acc | TPR [95% CI] | FPR [95% CI] | J [95% CI] |" + (" pair acc |" if paired else "") + " ctx tok |")
        print("|---|---|---|---|---|---|" + ("---|" if paired else "") + "---|")
        for run, f in sorted(rows[ds]):
            recs = [json.loads(l) for l in open(f, encoding="utf-8")]
            recs = [r for r in recs if r["qid"] in gold and r["qid"] not in bad]
            if paired:  # a pair counts only when both members were answered (and neither was dropped)
                by = defaultdict(list)
                for r in recs:
                    by[gold[r["qid"]]["pair"]].append(r)
                units = [v for v in by.values() if len(v) == 2]
                recs = [r for u in units for r in u]
            else:
                units = [[r] for r in recs]
            if not recs:
                continue
            tp, npos, fp, nneg = rates(recs)
            lo_t, hi_t = wilson(tp, npos)
            lo_f, hi_f = wilson(fp, nneg)
            lo_j, hi_j = boot_j(units)
            acc = 100 * sum(r["correct"] for r in recs) / len(recs)
            tok = sum(r.get("ctx_tokens") or 0 for r in recs) / len(recs)
            line = (f"| {run} | {len(recs)} | {acc:.1f} | {100 * tp / max(1, npos):.1f} [{lo_t:.0f}, {hi_t:.0f}] | "
                    f"{100 * fp / max(1, nneg):.1f} [{lo_f:.0f}, {hi_f:.0f}] | {j_of(recs):.1f} [{lo_j:.0f}, {hi_j:.0f}] |")
            if paired:
                line += f" {100 * sum(all(r['correct'] for r in u) for u in units) / len(units):.1f} |"
            print(line + f" {tok:.0f} |")
            if a.by_type:
                for t in sorted({r["qtype"] for r in recs}):
                    sub = [r for r in recs if r["qtype"] == t]
                    tp, npos, fp, nneg = rates(sub)
                    print(f"|   {t} | {len(sub)} | {100 * sum(r['correct'] for r in sub) / len(sub):.1f} | "
                          f"{100 * tp / max(1, npos):.1f} | {100 * fp / max(1, nneg):.1f} | {j_of(sub):.1f} |"
                          + (" |" if paired else "") + " |")


if __name__ == "__main__":
    main()
