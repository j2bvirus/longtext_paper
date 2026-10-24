"""Materials for the full-context contrast on Oolong-real through the Gemini web app:
Gemini 4 Argon reads a whole 16- or 24-episode test window (0.72M-1.25M cl100k tokens) uploaded as a file and
answers the window's 20 test questions (the same 20 per window as runs/oolong_test_pipeline.sh) in one message.

Writes gemini_web/:
  windows/Wnn_<episodes>ep.txt   the window text exactly as the benchmark gives it (instruction header, player map,
                                 episodes)
  prompts/Wnn_prompt.txt         the message to send with the file (20 numbered questions, answer format)
  answers/Wnn_answer.txt         empty; the operator pastes Gemini's whole reply here
  manifest.json                  Wnn -> window id, episodes, tokens, question ids in order
Condition (reported apart from every other reader): one web chat per window, file upload, the 20 questions in one
message, Argon at the highest thinking level, no web search or other tools.

python bench/oolong_gemini_web_prepare.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "methods"))
import core  # noqa: E402

D = os.path.join(ROOT, "data", "_external", "oolong_real", "test")
OUT = os.path.join(ROOT, "gemini_web")
PROMPT = """The attached file is a transcript of Dungeons and Dragons game sessions, with instructions at its top (read them; they include the mapping between players and characters). Answer the {n} questions below using ONLY the attached file. Do not search the web and do not use any other knowledge. Do not guess, estimate or approximate: count from the transcript. You may reason step by step, but at the end give the final answers, one per line, in order, exactly in this form:
Q01: \\boxed{{answer}}
...
Q{n:02d}: \\boxed{{answer}}
For a list, put the items inside the box separated by commas. "Episode k" means the k-th transcript in the attached file.

Questions:
{questions}
"""


def main():
    qs = [json.loads(l) for l in open(os.path.join(D, "questions.jsonl"), encoding="utf-8")]
    byw = {}
    for q in qs:
        byw.setdefault(q["context_window_id"], []).append(q)
    big = sorted([(len(v[0]["episodes"]), w) for w, v in byw.items() if len(v[0]["episodes"]) >= 16])
    for sub in ("windows", "prompts", "answers"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    manifest = {}
    for i, (n, w) in enumerate(big, 1):
        tag = f"W{i:02d}"
        text = open(os.path.join(D, "windows", w + ".txt"), encoding="utf-8").read()
        sel = sorted(byw[w], key=lambda q: q["id"])[:20]  # the same 20 questions as the test runs (per_window 20)
        open(os.path.join(OUT, "windows", f"{tag}_{n}ep.txt"), "w", encoding="utf-8").write(text)
        ql = "\n".join(f"Q{j:02d}. {q['question']}" for j, q in enumerate(sel, 1))
        open(os.path.join(OUT, "prompts", f"{tag}_prompt.txt"), "w", encoding="utf-8").write(
            PROMPT.format(n=len(sel), questions=ql))
        ap = os.path.join(OUT, "answers", f"{tag}_answer.txt")
        if not os.path.exists(ap):
            open(ap, "w", encoding="utf-8").close()
        manifest[tag] = {"window": w, "episodes": n, "cl100k_tokens": core.ntok(text), "chars": len(text),
                         "question_ids": [q["id"] for q in sel]}
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
    print(len(manifest), "windows written to", OUT)


if __name__ == "__main__":
    main()
