"""Score the Gemini web answers of the Oolong full-context contrast (gemini_web/answers/Wnn_answer.txt) with the
official scorer, and compare with the index and BM25 runs on the same questions (no LLM calls).

python methods/oolong_gemini_web_score.py
An answer file that is empty is 'not done'; one without any 'Qnn:' line is 'infeasible' (refused, cut or truncated;
its text is kept).  For each Qnn the text after 'Qnn:' up to the next 'Q..:' line is scored like a model output.
"""
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "methods"))
import oolong_score  # noqa: E402

W = os.path.join(ROOT, "gemini_web")
R = os.path.join(ROOT, "runs", "results_oolong")
# not anchored to line starts: text copied from the web app can lose its line breaks ('...}Q02: \boxed{...')
QLINE = re.compile(r"\**\s*Q(\d{2})\s*[:.)]\s*\**")


def split_items(s):
    return s if isinstance(s, list) else [x for x in str(s).split(",") if x.strip()]


def load_run(name):
    f = os.path.join(R, name + ".jsonl")
    out = {}
    if os.path.exists(f):
        for l in open(f, encoding="utf-8"):
            x = json.loads(l)
            out.setdefault(x["id"], oolong_score.score(x["answer"], x.get("raw") or "")[0])
    return out


def main():
    man = json.load(open(os.path.join(W, "manifest.json")))
    gold, qtext = {}, {}
    for l in open(os.path.join(ROOT, "data", "_external", "oolong_real", "test", "questions.jsonl"), encoding="utf-8"):
        q = json.loads(l)
        gold[q["id"]], qtext[q["id"]] = q["answer"], q["question"]
    others = {"index Haiku": load_run("test_index_claude-claude-haiku-4-5-20251001"),
              "index GPT": load_run("test_index_codex-gpt-6.1-sol"),
              "BM25 GPT": load_run("test_bm25_codex-gpt-6.1-sol")}
    rows, scored = [], defaultdict(dict)
    for tag, m in sorted(man.items()):
        # GEMINI_ANSWERS_DIR selects another answer folder (gemini_api/answers for the API run)
        p = os.path.join(os.environ.get("GEMINI_ANSWERS_DIR", os.path.join(W, "answers")), f"{tag}_answer.txt")
        text = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        if not text.strip():
            rows.append((tag, m["episodes"], "not done", None))
            continue
        marks = list(QLINE.finditer(text))
        if not marks:
            rows.append((tag, m["episodes"], "infeasible (no Qnn answers)", None))
            continue
        # the last occurrence of each Qnn is the final answer
        parts = {}
        for i, mk in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            parts[int(mk.group(1))] = text[mk.end():end]
        s, seen = [], []
        for j, qid in enumerate(m["question_ids"], 1):
            sc = oolong_score.score(gold[qid], parts.get(j, ""))[0]
            scored["Gemini web full"][qid] = sc
            s.append(sc)
            # whole-file check (W11 try 1 listed 12 items for 24 episodes): a list asked 'in each
            # episode' whose gold has one item per episode must have as many items as the window has episodes
            if "each episode" in qtext[qid] and len(split_items(gold[qid])) == m["episodes"]:
                seen.append(len(split_items(oolong_score.parse_response(parts.get(j, ""))[0])))
        said = sorted({int(x) for x in re.findall(r"(\d+)\s+episodes", text)})
        rows.append((tag, m["episodes"], "scored", sum(s) / len(s), seen, said))
    print("| Window | episodes | status | Gemini full reading | items in per-episode lists | 'N episodes' in reply |")
    print("|---|---|---|---|---|---|")
    for tag, n, st, v, *chk in rows:
        seen, said = chk if chk else ([], [])
        flag = " (fewer than episodes)" if any(k < n for k in seen) else ""
        print(f"| {tag} | {n} | {st} | {'' if v is None else f'{v:.3f}'} | {', '.join(map(str, seen))}{flag} | "
              f"{', '.join(map(str, said))} |")
    keys = list(scored["Gemini web full"])
    if keys:
        print(f"\nOn the {len(keys)} questions answered through the web:")
        g = sum(scored["Gemini web full"][k] for k in keys) / len(keys)
        print(f"- Gemini 4 Argon, web, whole window: {g:.3f}")
        for name, d in others.items():
            ks = [k for k in keys if k in d]
            if ks:
                print(f"- {name} on the same questions ({len(ks)}): {sum(d[k] for k in ks) / len(ks):.3f}")
    subsets(rows, man, scored["Gemini web full"], others)


def partial(n, seen, said):
    """the reply shows fewer episodes than the window has: a per-episode list is short, or the largest episode count
    the reply states is below n (a smaller count alone can be legitimate, e.g. 'appears in 3 episodes')"""
    return any(k < n for k in seen) or (bool(said) and max(said) < n)


def subsets(rows, man, gem, others, reps=10000, seed=0):
    """per-window means and the window-level paired bootstrap of (other - Gemini) on subsets of windows.  Windows
    share episodes, so the intervals are conditional on these windows (as in oolong_report.py)."""
    import random
    win = {}
    for tag, n, st, v, *chk in rows:
        if st != "scored":
            continue
        ids = man[tag]["question_ids"]
        means = {"Gemini": sum(gem[q] for q in ids) / len(ids)}
        for name, d in others.items():
            if all(q in d for q in ids):
                means[name] = sum(d[q] for q in ids) / len(ids)
        win[tag] = (n, partial(n, *chk), means)
    groups = [("16 episodes", lambda n, p: n == 16), ("24 episodes, all", lambda n, p: n == 24),
              ("24 episodes, whole file seen", lambda n, p: n == 24 and not p),
              ("24 episodes, partial reading", lambda n, p: n == 24 and p), ("all windows", lambda n, p: True)]
    rng = random.Random(seed)
    print("\nWindow subsets (mean of window means; difference = other - Gemini, window bootstrap 95%):")
    print("| subset | windows | Gemini | " + " | ".join(others) + " | " +
          " | ".join(f"{o} - Gemini" for o in others) + " |")
    print("|" + "---|" * (3 + 2 * len(others)))
    for label, f in groups:
        ws = [w for w, (n, p, _) in sorted(win.items()) if f(n, p)]
        if not ws:
            continue
        g = sum(win[w][2]["Gemini"] for w in ws) / len(ws)
        cells, diffs = [], []
        for o in others:
            ok = [w for w in ws if o in win[w][2]]
            dd = [win[w][2][o] - win[w][2]["Gemini"] for w in ok]
            cells.append(f"{sum(win[w][2][o] for w in ok) / len(ok):.3f}")
            boots = sorted(sum(rng.choice(dd) for _ in dd) / len(dd) for _ in range(reps))
            ahead = sum(1 for x in dd if x > 0)
            diffs.append(f"{sum(dd) / len(dd):+.3f} [{boots[int(0.025 * reps)]:+.3f}, {boots[int(0.975 * reps) - 1]:+.3f}]"
                         f" ({ahead}/{len(dd)} ahead)")
        print(f"| {label} | {len(ws)} | {g:.3f} | " + " | ".join(cells) + " | " + " | ".join(diffs) + " |")
    print("partial reading:", ", ".join(w for w, (n, p, _) in sorted(win.items()) if p) or "none")


if __name__ == "__main__":
    main()
