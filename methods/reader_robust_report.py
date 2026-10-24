"""Reader robustness: state tracking on worlds 7-8 (saga_v5_s7, saga_v5_s8,
d16, 4k budget), the same three methods (CMM v4, paragraph BM25, hybrid retrieval) read by each reader. Prints accuracy,
answers cut at the output limit, and paired comparisons (wins/losses and exact McNemar p, uncorrected and
Holm-corrected over the 22 comparisons of the table) over the questions answered under all three methods by that reader.

python methods/reader_robust_report.py
"""
import json
import os
import sys
from math import comb

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "runs", "results")
METHODS = [("CMM v4", "mem-cmm4"), ("Paragraph BM25", "mem-pbm25"), ("Hybrid", "hybrid")]
READERS = [  # (label, file reader tag)
    ("Claude Haiku 4.5, thinking off", "claude-claude-haiku-4-5-20251001"),
    ("Claude Haiku 4.5, thinking on (8k)", "claudethink8000-claude-haiku-4-5-20251001"),
    ("Qwen3-8B Q4, thinking off", "ollama-qwen3-8b"),
    ("Qwen3-14B Q4, thinking off", "ollama-qwen3-14b"),
    ("Qwen3-14B Q4, thinking on", "ollamathink-qwen3-14b"),
    ("Qwen3-14B Q8, thinking off", "ollama-qwen3-14b-q8_0"),
    ("Qwen3-14B Q8, thinking on", "ollamathink-qwen3-14b-q8_0"),
    ("Qwen3-32B Q4, thinking off", "ollama-qwen3-32b-q4_K_M"),
    ("Gemma 4 e4b Q4, thinking off", "ollama-gemma4-e4b-it-q4_K_M"),
    ("Gemma 4 12b Q4, thinking off", "ollama-gemma4-12b"),
    ("Gemma 4 31b Q4, thinking off", "ollama-gemma4-31b-it-q4_K_M"),
]


def load(method, reader):
    out = {}
    for s in ("saga_v5_s7", "saga_v5_s8"):
        f = os.path.join(R, f"{s}_d16_{method}_{reader}_b4000.jsonl")
        if not os.path.exists(f):
            return None
        for line in open(f, encoding="utf-8"):
            x = json.loads(line)
            out[(s, x["qid"])] = x
    return out


def mcnemar(w, l):
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


rows = []
for label, tag in READERS:
    d = [load(m, tag) for _, m in METHODS]
    if any(x is None for x in d):
        rows.append((label, None))
        continue
    keys = sorted(set(d[0]) & set(d[1]) & set(d[2]))
    acc = [100 * sum(x[k]["correct"] for k in keys) / len(keys) for x in d]
    cut = [sum(1 for k in keys if x[k].get("truncated")) for x in d]
    tests = []
    for b in (d[1], d[2]):
        w = sum(1 for k in keys if d[0][k]["correct"] and not b[k]["correct"])
        lo = sum(1 for k in keys if b[k]["correct"] and not d[0][k]["correct"])
        tests.append((w, lo, mcnemar(w, lo)))
    rows.append((label, (len(keys), acc, cut, tests)))
adj = iter(holm([t[2] for _, r in rows if r for t in r[3]]))
print("| Reader | n | CMM v4 | Paragraph BM25 | Hybrid | cut (CMM/BM25/hyb) | CMM vs BM25 w/l, p (Holm) | "
      "CMM vs hybrid w/l, p (Holm) |")
print("|---|---|---|---|---|---|---|---|")
for label, r in rows:
    if r is None:
        print(f"| {label} | not complete | | | | | | |")
        continue
    n, acc, cut, tests = r
    cells = [f"{w}/{lo}, p = {p:.2g} ({next(adj):.2g})" for w, lo, p in tests]
    print(f"| {label} | {n} | {acc[0]:.1f} | {acc[1]:.1f} | {acc[2]:.1f} | {cut[0]}/{cut[1]}/{cut[2]} | "
          f"{cells[0]} | {cells[1]} |")
