"""Reading-budget sweep with two more readers (runs/budget_sweep_gpt_sonnet.sh).

State tracking on the held-out worlds T1-T2 (saga_v5_s7, saga_v5_s8, density d16), CMM v4, paragraph BM25 and hybrid
retrieval, budgets 2k, 4k, 8k and 16k, readers Claude Haiku 4.5 (the earlier sweep), GPT-6.1 Sol (reasoning effort low)
and Claude Sonnet 5.5 (effort high). For every reader: accuracy and mean rendered tokens per question; at every budget,
exact McNemar tests between the methods (CMM v4 against each other method); and the two cross-budget tests of the
manuscript (CMM v4 at 4k against paragraph BM25 at 16k, and CMM v4 at 2k against paragraph BM25 at 8k and 16k), with the
95% subject-cluster bootstrap interval of the 4k-against-16k difference. Holm correction within each reader's family.
A condition with a missing question is reported as missing, not on a smaller set.

python methods/budget_sweep_report.py [--out paper/tables_budget_sweep.md]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from final_report import boot, pooled  # noqa: E402
from review_stats import holm, mcnemar  # noqa: E402

DSS = ("saga_v5_s7", "saga_v5_s8")
D = "d16"
N_EXPECTED = 459  # questions of T1-T2 that are not excluded
METHODS = [("mem-cmm4", "CMM v4"), ("mem-pbm25", "Paragraph BM25"), ("hybrid", "Hybrid retrieval")]
READERS = [("claude-claude-haiku-4-5-20251001", "Claude Haiku 4.5 (no effort setting)"),
           ("codex-gpt-6.1-sol", "GPT-6.1 Sol (reasoning effort low)"),
           ("claude-claude-sonnet-5-5", "Claude Sonnet 5.5 (effort high)")]
BUDGETS = (2000, 4000, 8000, 16000)


def get(m, r, b):
    X = pooled(DSS, D, m, r, b)
    return X if X and len(X) == N_EXPECTED else None


def acc(X):
    return 100 * sum(v["c"] for v in X.values()) / len(X)


def pair(X, Y):
    keys = sorted(set(X) & set(Y))
    w = sum(X[k]["c"] and not Y[k]["c"] for k in keys)
    l = sum(Y[k]["c"] and not X[k]["c"] for k in keys)
    return w, l, mcnemar(w, l)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    lines = ["# Reading-budget sweep on state tracking (T1-T2, 459 questions), three readers", "",
             "Accuracy % (mean rendered tokens per question); – = condition not complete.", ""]
    for r, rname in READERS:
        lines += [f"## {rname}", "", "| Method | 2k | 4k | 8k | 16k |", "|---|---|---|---|---|"]
        for m, mname in METHODS:
            cells = []
            for b in BUDGETS:
                X = get(m, r, b)
                cells.append(f"{acc(X):.1f} ({sum(v['tok'] for v in X.values()) / len(X):,.0f})" if X else "–")
            lines.append(f"| {mname} | " + " | ".join(cells) + " |")
        tests = []  # (label, wins, losses, p)
        for b in BUDGETS:
            C = get("mem-cmm4", r, b)
            for m, mname in METHODS[1:]:
                Y = get(m, r, b)
                if C and Y:
                    tests.append((f"CMM v4 vs {mname}, both {b // 1000}k", *pair(C, Y)))
        for bc, bp in ((4000, 16000), (2000, 8000), (2000, 16000)):
            C, Y = get("mem-cmm4", r, bc), get("mem-pbm25", r, bp)
            if C and Y:
                tests.append((f"CMM v4 {bc // 1000}k vs Paragraph BM25 {bp // 1000}k", *pair(C, Y)))
        if tests:
            adj = holm([t[3] for t in tests])
            lines += ["", "| Test | wins/losses | exact McNemar p | Holm p |", "|---|---|---|---|"]
            for t, h in zip(tests, adj):
                lines.append(f"| {t[0]} | +{t[1]}/−{t[2]} | {t[3]:.2g} | {h:.2g} |")
        C, Y = get("mem-cmm4", r, 4000), get("mem-pbm25", r, 16000)
        if C and Y:
            keys = sorted(C)
            val = {k: C[k]["c"] - Y[k]["c"] for k in keys}
            lo, hi = boot(keys, val, {k: C[k]["subj"] for k in keys})
            lines.append(f"\nCMM v4 4k minus Paragraph BM25 16k: {acc(C) - acc(Y):.1f} points, 95% subject-cluster "
                         f"bootstrap interval {100 * lo:.1f} to {100 * hi:.1f}.")
        lines.append("")
    text = "\n".join(lines)
    print(text)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
