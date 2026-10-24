"""Figures for the combined manuscript (no model calls).  Each figure is written as PNG together with the
numbers it plots (CSV), so every point can be checked against the tables.

python methods/figures_v2.py
  paper/figures/fig_oolong_by_window.png  Oolong-real test: mean official score per window size (Haiku reader for the
                                          index and BM25; whole-window reading where it fits; Gemini on 16/24 windows)
  paper/figures/fig_cost_arrival.png      cost per question against questions per window, one question per call vs
                                          20 per call (methods/oolong_cache_cost.py model, one price level)
"""
import csv
import json
import os
import subprocess
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "methods"))
import oolong_score  # noqa: E402

OUT = os.environ.get("FIG_OUT") or os.path.join(ROOT, "paper", "figures")  # FIG_OUT: write elsewhere (release replay)
R = os.path.join(ROOT, "runs", "results_oolong")
W = json.load(open(os.path.join(ROOT, "data", "_external", "oolong_real", "test", "windows.json"), encoding="utf-8"))


def by_size(name):
    f = os.path.join(R, name + ".jsonl")
    acc = defaultdict(list)
    seen = set()
    for l in open(f, encoding="utf-8"):
        x = json.loads(l)
        if x["id"] in seen or x.get("error"):  # a window over the reader's limit is recorded with an error: left out
            continue
        seen.add(x["id"])
        # official score recomputed from the stored reply
        acc[len(W[x["window"]]["episodes"])].append(oolong_score.score(x["answer"], x.get("raw") or "")[0])
    return {n: sum(v) / len(v) for n, v in acc.items()}


def gemini(folder):
    """window size -> mean score of the Gemini answers in a folder (gemini_web layout)"""
    man = json.load(open(os.path.join(ROOT, "gemini_web", "manifest.json")))
    gold = {}
    for l in open(os.path.join(ROOT, "data", "_external", "oolong_real", "test", "questions.jsonl"), encoding="utf-8"):
        q = json.loads(l)
        gold[q["id"]] = q["answer"]
    import re
    qline = re.compile(r"\**\s*Q(\d{2})\s*[:.)]\s*\**")
    acc = defaultdict(list)
    for tag, m in man.items():
        p = os.path.join(folder, f"{tag}_answer.txt")
        if not os.path.exists(p) or not open(p, encoding="utf-8").read().strip():
            continue
        text = open(p, encoding="utf-8").read()
        marks = list(qline.finditer(text))
        parts = {}
        for i, mk in enumerate(marks):
            parts[int(mk.group(1))] = text[mk.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        s = [oolong_score.score(gold[q], parts.get(j, ""))[0] for j, q in enumerate(m["question_ids"], 1)]
        acc[m["episodes"]].append(sum(s) / len(s))
    return {n: sum(v) / len(v) for n, v in acc.items()}


def fig_oolong():
    # labels name the input (4k from the index or BM25, or the full window) and the reading model, so
    # that the same model (Haiku 4.5) with different inputs is not read as two models
    series = [("Event index (4k) → Haiku 4.5", by_size("test_index_claude-claude-haiku-4-5-20251001"), "o-"),
              ("BM25 (4k) → Haiku 4.5", by_size("test_bm25_claude-claude-haiku-4-5-20251001"), "s-"),
              ("Full context → GPT-6.1 Sol", by_size("test_full_codex-gpt-6.1-sol"), "^--"),
              ("Full context → Haiku 4.5", by_size("test_full_claude-claude-haiku-4-5-20251001"), "v--"),
              ("Full context → Gemini 4 Argon, API", gemini(os.path.join(ROOT, "gemini_api", "answers")), "D"),
              ("Full context → Gemini 4 Argon, web app", gemini(os.path.join(ROOT, "gemini_web", "answers")), "x")]
    sizes = sorted({n for _, d, _ in series for n in d})
    with open(os.path.join(OUT, "fig_oolong_by_window.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["episodes"] + [s for s, _, _ in series])
        for n in sizes:
            w.writerow([n] + [f"{d[n]:.4f}" if n in d else "" for _, d, _ in series])
    plt.figure(figsize=(6.4, 4.8))
    for label, d, st in series:
        xs = sorted(d)
        plt.plot(xs, [d[x] for x in xs], st, label=label, markersize=5, linewidth=1.5)
    plt.axvspan(12, 26, color="0.92", zorder=0)
    plt.text(13, 0.02, "primary analysis\n(16, 24 episodes)", fontsize=8, color="0.3")
    # input limits that decide where full-context reading exists: Haiku 4.5 200k tokens (3 episodes 125-179k,
    # 4 episodes 176-234k cl100k tokens); Gemini 4 Argon 1M (16 episodes 0.72-0.86M, 24 episodes 1.09-1.25M)
    for x, txt in ((3.5, "Haiku 4.5 limit\n(200k tokens)"), (20, "Gemini limit\n(1M tokens)")):
        plt.axvline(x, color="0.5", linestyle=":", linewidth=1)
        plt.text(x * 1.03, 0.635, txt, fontsize=6.5, color="0.35")
    plt.xscale("log")
    plt.xticks(sizes, [str(s) for s in sizes], fontsize=8)
    plt.xlabel("episodes per window (about 50k tokens each)")
    plt.ylabel("official score (mean)")
    plt.ylim(0, 0.7)
    plt.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_oolong_by_window.png"), dpi=200)
    plt.savefig(os.path.join(OUT, "fig_oolong_by_window.pdf"), metadata={"CreationDate": None})  # vector copy (line art as PDF)
    plt.close()


def fig_cost():
    def run(batch):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "methods", "oolong_cache_cost.py"), "--batch",
                              str(batch), "--qs", "1,2,5,10,20,50,100,200,500,1000,2000"],
                             capture_output=True, text=True, encoding="utf-8").stdout
        rows = [l for l in out.splitlines() if l.startswith("| ") and l.split("|")[1].strip().isdigit()]
        return [(int(r.split("|")[1]), *[float(c.strip().replace(",", "")) for c in r.split("|")[2:5]]) for r in rows]
    one, b20 = run(1), run(20)
    with open(os.path.join(OUT, "fig_cost_arrival.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["questions", "index", "whole_cached_one_per_call", "whole_cached_20_per_call"])
        for (q, i, _, c1), (_, _, _, c20) in zip(one, b20):
            w.writerow([q, i, c1, c20])
    plt.figure(figsize=(6.4, 4.0))
    plt.plot([r[0] for r in one], [r[1] for r in one], "o-", label="event index (build amortised)")
    plt.plot([r[0] for r in one], [r[3] for r in one], "s--", label="full context, cached, one question per call")
    plt.plot([r[0] for r in b20], [r[3] for r in b20], "^--", label="full context, cached, 20 questions per call")
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("questions per window")
    plt.ylabel("cost per question (input-token equivalents)")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_cost_arrival.png"), dpi=200)
    plt.savefig(os.path.join(OUT, "fig_cost_arrival.pdf"), metadata={"CreationDate": None})  # vector copy (line art as PDF)
    plt.close()


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_oolong()
    fig_cost()
    print("written", os.listdir(OUT))
