"""Split prompts for the Gemini web contrast: Argon at the highest thinking level ran about 10 minutes on
20 questions and then reloaded without an answer, so each window's 20 questions are also given as four messages of
five (sent one after another in the same chat), plus a light diagnostic prompt.

python bench/oolong_gemini_web_split.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, "gemini_web")
HEAD = ("The attached file is a transcript of Dungeons and Dragons game sessions, with instructions at its top (read "
        "them; they include the mapping between players and characters). Answer the questions below using ONLY the "
        "attached file. Do not search the web and do not use any other knowledge. Do not guess, estimate or "
        "approximate: count from the transcript. You may reason step by step, but at the end give the final answers, "
        "one per line, exactly in this form:\n"
        "Qnn: \\boxed{answer}\n"
        "For a list, put the items inside the box separated by commas. \"Episode k\" means the k-th transcript in the "
        "attached file.\n\nQuestions:\n")
DIAG = ("The attached file contains transcripts of several Dungeons and Dragons episodes, each between [START OF "
        "EPISODE] and [END OF EPISODE]. How many episode transcripts are in the attached file, and what are the first "
        "five words of the last episode? Use only the file. Give the count as \\boxed{n}.\n")


def main():
    man = json.load(open(os.path.join(W, "manifest.json")))
    qs = {}
    for l in open(os.path.join(ROOT, "data", "_external", "oolong_real", "test", "questions.jsonl"), encoding="utf-8"):
        q = json.loads(l)
        qs[q["id"]] = q
    out = os.path.join(W, "prompts_split")
    os.makedirs(out, exist_ok=True)
    for tag, m in man.items():
        ids = m["question_ids"]
        for part, (a, b) in enumerate(((0, 5), (5, 10), (10, 15), (15, 20)), 1):
            ql = "\n".join(f"Q{j + 1:02d}. {qs[ids[j]]['question']}" for j in range(a, min(b, len(ids))))
            open(os.path.join(out, f"{tag}_part{part}.txt"), "w", encoding="utf-8").write(HEAD + ql + "\n")
    # two messages of ten (used if ten questions finish within the web time limit)
    half = os.path.join(W, "prompts_half")
    os.makedirs(half, exist_ok=True)
    for tag, m in man.items():
        ids = m["question_ids"]
        for part, (a, b) in enumerate(((0, 10), (10, 20)), 1):
            ql = "\n".join(f"Q{j + 1:02d}. {qs[ids[j]]['question']}" for j in range(a, min(b, len(ids))))
            open(os.path.join(half, f"{tag}_half{part}.txt"), "w", encoding="utf-8").write(HEAD + ql + "\n")
    open(os.path.join(out, "DIAGNOSTIC.txt"), "w", encoding="utf-8").write(DIAG)
    bad = [f for f in os.listdir(out) if "\x08" in open(os.path.join(out, f), encoding="utf-8").read()]
    print(len(os.listdir(out)), "files; files with a backspace character:", bad)


if __name__ == "__main__":
    main()
