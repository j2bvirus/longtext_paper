"""Exact-match rate on Oolong numeric questions, and a diagnostic share within 10% of the gold (decision of
the official score stays the primary metric; exact match is reported beside it; the 10% share is only a
diagnostic of near misses, never a performance claim).  No model calls.

python methods/oolong_exact_report.py [--split test]
"""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oolong_eval as oe  # noqa: E402
import oolong_score  # noqa: E402

RUNS = [("Index, Haiku-built, Haiku reader", "index_claude-claude-haiku-4-5-20251001"),
        ("Index, Sonnet-built, Haiku reader", "index_claude-claude-haiku-4-5-20251001_bSonnet"),
        ("Index, Haiku-built, GPT reader", "index_codex-gpt-6.1-sol"),
        ("BM25, Haiku reader", "bm25_claude-claude-haiku-4-5-20251001"),
        ("BM25, GPT reader", "bm25_codex-gpt-6.1-sol"),
        ("Full window, Haiku reader (1-3 episodes)", "full_claude-claude-haiku-4-5-20251001"),
        ("Full window, GPT reader (1-3 episodes)", "full_codex-gpt-6.1-sol")]


def as_int(x):
    try:
        return int(str(x).strip())
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    a = ap.parse_args()
    print("| Run | numeric questions | official score | exact match | within 10% of gold (diagnostic) | 16+24 episodes: exact |")
    print("|---|---|---|---|---|---|")
    for label, name in RUNS:
        p = os.path.join(oe.OUT, f"{a.split}_{name}.jsonl")
        if not os.path.exists(p):
            continue
        rows = []
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            g = as_int(r["answer"])
            if g is None or r.get("error"):
                continue
            pred, _ = oolong_score.parse_response(r["raw"] or "")
            v = as_int(pred) if not isinstance(pred, list) else None
            ex = v is not None and v == g
            near = v is not None and abs(v - g) <= 0.1 * abs(g)
            rows.append((r["n_eps"], r["score"], ex, near))
        n = len(rows)
        big = [x for x in rows if x[0] >= 16]
        print(f"| {label} | {n} | {sum(x[1] for x in rows) / n:.3f} | {sum(x[2] for x in rows) / n:.1%} | "
              f"{sum(x[3] for x in rows) / n:.1%} | "
              f"{(sum(x[2] for x in big) / len(big)):.1%} (n={len(big)})" if big else
              f"| {label} | {n} | {sum(x[1] for x in rows) / n:.3f} | {sum(x[2] for x in rows) / n:.1%} | "
              f"{sum(x[3] for x in rows) / n:.1%} | – |")


if __name__ == "__main__":
    main()
