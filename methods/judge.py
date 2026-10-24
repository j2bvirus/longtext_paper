"""LLM judging of free-form answers (NovelHopQA) + per-method table.

python methods/judge.py --data nhq_anna,nhq_dracula,nhq_moby,nhq_great [--judge claude:claude-haiku-4-5-20251001]
Judgements are cached per (question, gold, prediction) by the llm cache and written to
runs/judged/<result file>.json.  A judged answer is correct when it conveys the gold
answer; 'unknown' and contradicting answers are incorrect.
"""
import argparse
import collections
import glob
import json
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYS = ("You grade answers to reading-comprehension questions about novels. Compare the model answer with the gold "
       "answer. It is correct if it conveys the same answer (paraphrases, synonyms, and answers that contain the gold "
       "answer's essential content count). It is incorrect if it is different, contradicts the gold answer, is "
       "'unknown', or hedges between several answers. Reply with exactly one word: correct or incorrect.")
# AMA-Bench datasets (ama_*) are judged with the benchmark's own judge wording (AMA-Bench utils/evaluation_metrics.py,
# compute_llm_as_judge; task context lines omitted), so that our numbers are comparable to the benchmark's protocol
AMA_JUDGE = ("You are an expert evaluator. You will be given a question, a reference answer, and a predicted answer.\n"
             "Your task is to determine if the predicted answer is correct based on:\n"
             "1. Factual correctness compared to the reference\n2. Completeness of the answer\n"
             "3. Relevance to the question\n\nQuestion: {q}\n\nReference Answer: {g}\n\nPredicted Answer: {p}\n\n"
             "Is the predicted answer correct? Respond with ONLY \"yes\" or \"no\". Do not include any thinking "
             "process, explanation, or additional text.\n\nAnswer:")
NAME_RE = re.compile(r"^(?P<ds>(?:nhq|locomo|ama)_[a-z0-9]+)_(?P<d>full)_(?P<m>.+?)_(?P<r>claude-.+?|ollama-.+?|codex-.+?|agy-.+?)_b(?P<b>\d+)(?P<tag>.*)\.jsonl$")


def boot(xs, n=2000):
    r = random.Random(0)
    m = len(xs)
    v = sorted(sum(xs[r.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return v[int(0.025 * n)], v[int(0.975 * n) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="nhq_anna,nhq_dracula,nhq_moby,nhq_great")
    ap.add_argument("--judge", default="claude:claude-haiku-4-5-20251001")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--outdir", default="runs/judged", help="e.g. runs/judged_q14 for a second judge")
    ap.add_argument("--only", default="", help="comma list of '<method+tag>@<reader prefix>' to judge (second-judge sample)")
    ap.add_argument("--block", action="store_true",
                    help="judge everything after the last 'Answer:' marker of the reader output (multi-line answers, e.g. "
                         "lists of steps), not only its first line; uses the stored output tail")
    a = ap.parse_args()
    os.makedirs(os.path.join(ROOT, a.outdir), exist_ok=True)
    pooled = collections.defaultdict(list)
    ctx = collections.defaultdict(list)
    for ds in a.data.split(","):
        qs = {json.loads(l)["qid"]: json.loads(l) for l in open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"), encoding="utf-8")}
        for f in sorted(glob.glob(os.path.join(ROOT, "runs", "results", f"{ds}_*.jsonl"))):
            m = NAME_RE.match(os.path.basename(f))
            if m and a.only and not any(m["m"] + m["tag"] == x.split("@")[0] and m["r"].startswith(x.split("@")[1])
                                        for x in a.only.split(",")):
                continue
            if not m:
                continue
            recs = [json.loads(l) for l in open(f, encoding="utf-8")]
            if not recs:  # e.g. a run that could not read anything (record over the window)
                continue

            def one(r):
                q = qs[r["qid"]]
                pred = (r.get("pred") or "").strip()
                if a.block:
                    ms = list(re.finditer(r"answer\s*[:：]", r.get("raw") or "", re.I))
                    if ms:
                        pred = (r["raw"][ms[-1].end():]).strip().strip("*").strip()
                if q["answer"]["kind"] != "free":  # e.g. unanswerable questions: deterministic scoring
                    return r["qid"], core.score(pred, q["answer"])
                if not pred or pred.lower() in ("unknown", "unknown."):
                    return r["qid"], 0
                if ds.startswith("ama_"):
                    out = llm.call(a.judge, "You are an expert evaluator.", AMA_JUDGE.format(q=q["question"], g=q["answer"]["gold"], p=pred),
                                   max_tokens=5, tag=f"judge|{ds}")
                    return r["qid"], int(out["text"].strip().lower().startswith("yes"))
                prompt = f"Question: {q['question']}\nGold answer: {q['answer']['gold']}\nModel answer: {pred}\nVerdict:"
                out = llm.call(a.judge, SYS, prompt, max_tokens=5, tag=f"judge|{ds}")
                v = out["text"].strip().lower()
                return r["qid"], int(v.startswith("correct"))
            with ThreadPoolExecutor(a.workers) as ex:
                verdicts = dict(ex.map(one, recs))
            json.dump(verdicts, open(os.path.join(ROOT, a.outdir, os.path.basename(f)[:-6] + ".json"), "w"))
            key = (m["m"] + m["tag"], m["r"])
            pooled[key] += list(verdicts.values())
            ctx[key] += [r["ctx_tokens"] for r in recs]
            print(f"{ds:12s} {m['m'] + m['tag']:16s} {m['r'][:24]:24s} n={len(verdicts):4d} acc={100*sum(verdicts.values())/len(verdicts):5.1f}")
    print("\nPooled over books")
    for (meth, rd), xs in sorted(pooled.items(), key=lambda kv: (kv[0][1], -sum(kv[1]) / len(kv[1]))):
        lo, hi = boot(xs)
        print(f"{meth:16s} {rd[:24]:24s} n={len(xs):4d} acc={100*sum(xs)/len(xs):5.1f} [{100*lo:.0f},{100*hi:.0f}] ctx/q={sum(ctx[(meth, rd)])/len(ctx[(meth, rd)]):,.0f}")


if __name__ == "__main__":
    main()
