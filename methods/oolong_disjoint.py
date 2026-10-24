"""Shared episodes in Oolong-real (no model calls): windows share episodes, so the window bootstrap is
conditional on this split's episodes.  This report (1) counts the overlap, and (2) repeats the primary comparison
(index minus BM25, Haiku reader, official score) on sets of windows that share no episode.

python methods/oolong_disjoint.py > paper/tables_oolong_disjoint.md

Disjoint sets are chosen without looking at scores: for each window size, windows are taken in order of their first
episode, skipping any that shares an episode with one already taken (greedy, deterministic); and over all sizes,
largest windows first.  Scores are the official ones stored with each record (same as methods/oolong_report.py).
"""
import json
import os
from collections import defaultdict
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "runs", "results_oolong")
W = json.load(open(os.path.join(ROOT, "data", "_external", "oolong_real", "test", "windows.json"), encoding="utf-8"))


def scores(name):
    """official score recomputed from the stored reply with the authors' scorer"""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "methods"))
    import oolong_score
    out = {}
    for l in open(os.path.join(R, name + ".jsonl"), encoding="utf-8"):
        x = json.loads(l)
        out.setdefault(x["id"], (x["window"], oolong_score.score(x["answer"], x.get("raw") or "")[0]))
    return out


def greedy(ws):
    taken, used = [], set()
    for w in ws:
        e = set(W[w]["episodes"])
        if not e & used:
            taken.append(w)
            used |= e
    return taken


def main():
    reader = "claude-claude-haiku-4-5-20251001"
    idx, bm = scores(f"test_index_{reader}"), scores(f"test_bm25_{reader}")
    byw = defaultdict(list)
    for q, (w, s) in idx.items():
        if q in bm:
            byw[w].append(s - bm[q][1])
    wins = sorted(byw, key=lambda w: (len(W[w]["episodes"]), min(W[w]["episodes"])))
    print("# Oolong-real test: episode overlap and episode-disjoint windows (Haiku reader, index minus BM25)\n")
    big = [w for w in wins if len(W[w]["episodes"]) >= 16]
    pairs = list(combinations(big, 2))
    shared = sum(1 for a, b in pairs if set(W[a]["episodes"]) & set(W[b]["episodes"]))
    eps = sorted({e for w in big for e in W[w]["episodes"]})
    print(f"- 16- and 24-episode windows: {len(big)}; window pairs sharing an episode: {shared} of {len(pairs)}; "
          f"distinct episodes covered: {len(eps)} ({min(eps)}–{max(eps)}).\n")
    print("| windows | n windows | questions | mean of window means (index − BM25) | windows ahead |")
    print("|---|---|---|---|---|")

    def row(label, ws):
        if not ws:
            return
        m = [sum(byw[w]) / len(byw[w]) for w in ws]
        nq = sum(len(byw[w]) for w in ws)
        print(f"| {label} | {len(ws)} | {nq} | {sum(m) / len(m):+.3f} | {sum(1 for x in m if x > 0)}/{len(m)} |")
    row("all 16+24 (primary set)", big)
    for n in sorted({len(W[w]["episodes"]) for w in wins}):
        ws = [w for w in wins if len(W[w]["episodes"]) == n]
        g = greedy(ws)
        row(f"{n} episodes, disjoint ({', '.join(str(min(W[w]['episodes'])) for w in g)} first ep.)", g)
    g = greedy(sorted(wins, key=lambda w: (-len(W[w]["episodes"]), min(W[w]["episodes"]))))
    row("all sizes, disjoint, largest first", g)
    print("\nEach disjoint set uses every episode at most once, so no episode is counted twice within a set; "
          "the sets are small, so they show direction rather than a tight interval.")


if __name__ == "__main__":
    main()
