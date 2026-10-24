"""Fact survival through agent-style context compaction (is the loss in the summarizer or in the reader?).

Replays a finished compaction chain of baselines2.Compaction from the LLM cache (reads cached responses only;
never calls a model; stops if a step is missing).  For every question whose gold answer is a span (person, place,
word, label, free text; not yes/no) the answer SURVIVES at step i when the gold string occurs in summary i together
with the subject's name in the same line or sentence (saga sets; for records whose questions have no subject id,
the gold string alone, with its numbers, must occur).  This is a proxy of fact survival, reported as such.

Output per question: the compaction step at which its last evidence entered the summary, whether the answer was
in the summary right after that step, whether it is in the final summary or the raw tail, how many compactions
it went through, and the reader's correctness on the compaction run (if the result file exists).  Prints survival
by number of compactions survived and accuracy conditional on survival.

python methods/compaction_survival.py saga_v5_s7 d16 [--summary 2000 --tail 2000 --builder claude:claude-haiku-4-5-20251001]
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baselines2  # noqa: E402
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s.lower())  # 1,587,852 -> 1587852
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.,%/ -]", " ", s)).strip()


def replay(chunks, builder, summary_tok, tail_tok, ds, density):
    segs, cur, tot = [], [], 0
    for c in chunks:
        if cur and tot + c["tokens"] > tail_tok:
            segs.append(cur)
            cur, tot = [], 0
        cur.append(c)
        tot += c["tokens"]
    if cur:
        segs.append(cur)
    summary, words, out = "(nothing yet)", int(summary_tok * 0.7), []
    params = {"max_tokens": int(summary_tok * 1.3), "num_ctx": 32768, "json": False}
    for seg in segs[:-1]:
        prompt = (f"Summary of everything before:\n{summary}\n\nNew text:\n{core.render_chunks(seg)}\n\n"
                  f"Write the new compacted summary of everything so far (at most {words} words). "
                  f"Output only the summary.")
        cp = llm._cache_path(llm._key(builder, baselines2.COMPACT_SYS, prompt, params))
        if not os.path.exists(cp):
            raise SystemExit(f"step {len(out)} of {len(segs) - 1} not in the cache: chain unfinished for {ds} {density}")
        summary = json.load(open(cp, encoding="utf-8"))["text"].strip()
        out.append(summary)
    return segs, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("density")
    ap.add_argument("--summary", type=int, default=2000)
    ap.add_argument("--tail", type=int, default=2000)
    ap.add_argument("--builder", default="claude:claude-haiku-4-5-20251001")
    ap.add_argument("--run", default="", help="result file glob of the compaction run (default: guessed)")
    a = ap.parse_args()
    ddir = os.path.join(ROOT, "data", a.data)
    text, spans, qs, world = core.load_dataset(ddir, a.density)
    chunks = core.chunk_record(text, 300)
    segs, summ = replay(chunks, a.builder, a.summary, a.tail, a.data, a.density)
    # segment index of a character offset
    bounds = [(s[0]["start"], s[-1]["end"]) for s in segs]

    def seg_of(pos):
        for i, (b0, b1) in enumerate(bounds):
            if b0 <= pos < b1 or (i == len(bounds) - 1 and pos >= b0):
                return i
        return len(bounds) - 1
    tail_text = norm(" ".join(c["text"] for c in segs[-1]))
    P = (world or {}).get("persons", {})
    tag = {2000: "compact4k", 8000: "compact16k"}[a.summary] + ("" if a.builder.startswith("claude:") else "_built-gpt")
    run = a.run or f"{a.data}_{a.density}_mem-{tag.split('_')[0]}_claude-claude-haiku-4-5-20251001_b4000" + (
        "_built-gpt" if "_built-gpt" in tag else "")
    correct = {}
    jf = os.path.join(ROOT, "runs", "judged", run + ".json")
    rf = os.path.join(ROOT, "runs", "results", run + ".jsonl")
    if os.path.exists(jf):
        correct = {k: int(v) for k, v in json.load(open(jf, encoding="utf-8")).items()}  # qid -> judge verdict
    elif os.path.exists(rf):
        for line in open(rf, encoding="utf-8"):
            r = json.loads(line)
            correct[r["qid"]] = int(r["correct"])
    norm_summ = [norm(s) for s in summ]
    rows = []
    for q in qs:
        if q.get("excluded") or q["answer"]["kind"] in ("yesno", "verdict", "none", "unknown"):
            continue
        # alternatives, each a list of strings that must all occur: an answer with numbers survives when all its
        # numbers survive (units and wording may be rephrased); otherwise the whole answer string must occur
        golds = []
        for g in [q["answer"]["gold"]] + q["answer"].get("aliases", []):
            g = norm(g)
            if g:
                golds.append(re.findall(r"\d[\d.]*\d|\d", g) or [g])
        ev = [spans[e][1] for e in q.get("evidence_core") or q.get("evidence") or [] if e in spans]
        if not ev or not golds:
            continue
        s_ev = seg_of(max(ev) - 1)
        subj = None
        if q.get("subject") in P:
            p = P[q["subject"]]
            subj = [norm(f"{p['first']} {p['surname']}"), norm(p["first"])]

        def has(t):
            if subj is None:
                return any(all(n in t for n in alt) for alt in golds)
            for unit in re.split(r"(?<=[.;\n])\s+", t):
                if any(all(n in unit for n in alt) for alt in golds) and any(s in unit for s in subj):
                    return True
            return False
        n_comp = len(summ)
        if s_ev >= n_comp:  # evidence lies in the raw tail: never compacted
            rows.append({"qid": q["qid"], "s_ev": s_ev, "through": 0, "entered": None, "final": None,
                         "tail": has(tail_text), "correct": correct.get(q["qid"])})
            continue
        entered = has(norm_summ[s_ev])
        final = has(norm_summ[-1])
        rows.append({"qid": q["qid"], "s_ev": s_ev, "through": n_comp - 1 - s_ev, "entered": entered, "final": final,
                     "tail": has(tail_text), "correct": correct.get(q["qid"])})
    print(f"{a.data} {a.density} {tag}: {len(summ)} compactions, {len(rows)} span-answer questions; run {run} "
          f"({'judged' if os.path.exists(jf) else 'deterministic' if os.path.exists(rf) else 'no result file'})")
    comp = [r for r in rows if r["entered"] is not None]
    print(f"  evidence in the raw tail (never compacted): {len(rows) - len(comp)}")
    if comp:
        print(f"  answer in the summary right after its evidence was compacted: "
              f"{100 * sum(r['entered'] for r in comp) / len(comp):.1f}% of {len(comp)}")
    bins = [(0, 0), (1, 4), (5, 19), (20, 79), (80, 10 ** 6)]
    print("  | compactions survived | n | entered | still in final summary | final given entered | reader acc |")
    print("  |---|---|---|---|---|---|")
    for lo, hi in bins:
        b = [r for r in comp if lo <= r["through"] <= hi]
        if not b:
            continue
        ent = [r for r in b if r["entered"]]
        acc = [r["correct"] for r in b if r["correct"] is not None]
        print(f"  | {lo}-{hi if hi < 10 ** 6 else ''} | {len(b)} | {100 * len(ent) / len(b):.0f}% | "
              f"{100 * sum(r['final'] for r in b) / len(b):.0f}% | "
              f"{100 * sum(r['final'] for r in ent) / max(1, len(ent)):.0f}% | "
              f"{100 * sum(acc) / len(acc) if acc else float('nan'):.0f}% |")
    for name, cond in (("answer in final summary or tail", lambda r: bool(r["final"]) or r["tail"]),
                       ("answer in neither", lambda r: not (bool(r["final"]) or r["tail"]))):
        b = [r["correct"] for r in rows if cond(r) and r["correct"] is not None]
        if b:
            print(f"  reader accuracy when {name}: {100 * sum(b) / len(b):.1f}% (n={len(b)})")
    out = os.path.join(ROOT, "runs", f"compaction_survival_{a.data}_{a.density}_{tag}.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), indent=0)
    print("  written", os.path.relpath(out, ROOT).replace(os.sep, "/"))


if __name__ == "__main__":
    main()
