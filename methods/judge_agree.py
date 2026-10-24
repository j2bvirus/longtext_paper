"""Agreement of two judges on the same answers (no LLM calls).

python methods/judge_agree.py runs/judged_sonnet_block runs/judged_gpt_block [--prefix ama_]
For every verdict file present in both directories, the per-question verdicts are paired.  Prints the number of
paired answers, raw agreement, Cohen's kappa, and the two kinds of disagreement, overall and per dataset prefix.
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main():
    d1, d2 = sys.argv[1], sys.argv[2]
    prefix = sys.argv[sys.argv.index("--prefix") + 1] if "--prefix" in sys.argv else ""
    groups = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(d1, prefix + "*.json"))):
        g = os.path.join(d2, os.path.basename(f))
        if not os.path.exists(g):
            continue
        a, b = json.load(open(f)), json.load(open(g))
        dom = re.sub(r"\d+$", "", os.path.basename(f).split("_full_")[0])
        for qid in set(a) & set(b):
            groups[dom].append((int(a[qid]), int(b[qid])))
            groups["all"].append((int(a[qid]), int(b[qid])))
    print(f"| Group | paired answers | agreement | kappa | first yes, second no | first no, second yes |")
    print("|---|---|---|---|---|---|")
    for k in sorted(groups, key=lambda x: (x != "all", x)):
        ps = groups[k]
        print(f"| {k} | {len(ps)} | {100 * sum(a == b for a, b in ps) / len(ps):.1f}% | {kappa(ps):.2f} | "
              f"{sum(1 for a, b in ps if a and not b)} | {sum(1 for a, b in ps if b and not a)} |")


if __name__ == "__main__":
    main()
