"""AMA-Bench (Zhao et al., ICML 2026; arXiv 2602.22769; data MIT license, huggingface.co/datasets/AMA-bench/AMA-bench)
as a public agent-log domain with expert-written questions.  One dataset directory per trajectory, questions
unchanged, one record per trajectory.

Selection:
  all GAIA level 2 and level 3 trajectories whose rendered record has at least 150k tokens (14 long single-episode
  records, 0.19M-1.06M tokens, the scale this study is about; no upper bound),
  and the 12 longest SWE-bench (OpenHands) trajectories (software engineering, ~65k-100k tokens).
Rendering follows the benchmark's harness (src/memory_interface.py: "Step {turn_idx}:", "Action: ...",
"Observation: ..."), preceded by the task description.  Blank lines inside an action or observation are folded and
long steps are cut at line boundaries into pieces of at most ~250 tokens, each piece starting with
"Step N:" or "Step N (continued):", so that every paragraph shows its step number to every method alike.
Answers are free-form; judging uses the benchmark's own judge wording (methods/judge.py, AMA_JUDGE).

python bench/ama_prepare.py <path to open_end_qa_set.jsonl>
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "methods"))
import core  # noqa: E402

PIECE = 250


def fold(s):
    return re.sub(r"\n\s*\n+", "\n", (s or "").strip())


def pieces(label, body):
    """Cut `body` at line boundaries into pieces of at most PIECE tokens; very long lines are cut by characters."""
    lines = []
    for ln in body.split("\n"):
        if len(ln) > 600:  # very long lines (web pages, JSON) are cut into 600-character slices first
            lines += [ln[i:i + 600] for i in range(0, len(ln), 600)]
        else:
            lines.append(ln)
    out, cur, t = [], [], 0
    for ln in lines:
        k = core.ntok(ln) + 1
        if cur and t + k > PIECE:
            out.append(cur)
            cur, t = [], 0
        cur.append(ln)
        t += k
    if cur:
        out.append(cur)
    return [(f"{label}:" if i == 0 else f"{label} (continued):") + "\n" + "\n".join(p) for i, p in enumerate(out)]


def render(ep):
    paras = pieces("Task description", fold(ep["task"]))
    for st in ep["trajectory"]:
        body = f"Action: {fold(st.get('action'))}\nObservation: {fold(st.get('observation'))}"
        paras += pieces(f"Step {st.get('turn_idx', 0)}", body)
    return "\n\n".join(paras) + "\n"


def main():
    src = sys.argv[1]
    eps = [json.loads(l) for l in open(src, encoding="utf-8")]
    ext = os.path.join(ROOT, "data", "_external", "ama_bench")
    os.makedirs(ext, exist_ok=True)
    if not os.path.exists(os.path.join(ext, "open_end_qa_set.jsonl")):
        shutil.copy2(src, os.path.join(ext, "open_end_qa_set.jsonl"))
    rendered = []
    for e in eps:
        if e["task_type"] in ("gaia_level2", "gaia_level3", "swebench"):
            text = render(e)
            rendered.append((e, text, core.ntok(text)))
    gaia = sorted([r for r in rendered if r[0]["task_type"] != "swebench" and r[2] >= 150_000],
                  key=lambda r: r[0]["episode_id"])
    swe = sorted([r for r in rendered if r[0]["task_type"] == "swebench"], key=lambda r: -r[2])[:12]
    swe = sorted(swe, key=lambda r: r[0]["episode_id"])
    manifest = []
    for prefix, group in (("ama_g", gaia), ("ama_w", swe)):
        for k, (e, text, ntok) in enumerate(group, 1):
            ds = f"{prefix}{k:02d}"
            d = os.path.join(ROOT, "data", ds)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "record_full.txt"), "w", encoding="utf-8").write(text)
            json.dump({}, open(os.path.join(d, "spans_full_GOLD.json"), "w"))
            json.dump({"persons": {}, "source": "AMA-Bench open_end_qa_set.jsonl", "episode_id": e["episode_id"],
                       "task_type": e["task_type"], "domain": e["domain"], "success": e["success"],
                       "num_turns": e["num_turns"]}, open(os.path.join(d, "world_GOLD.json"), "w"), indent=1)
            with open(os.path.join(d, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
                for i, q in enumerate(e["qa_pairs"]):
                    f.write(json.dumps({"qid": f"Q{i:04d}", "qtype": "AMA_" + q["type"], "question": q["question"],
                                        "answer": {"kind": "free", "gold": q["answer"], "aliases": [q["answer"]]},
                                        "evidence": [], "evidence_core": [], "question_uuid": q["question_uuid"],
                                        "task": e["task"][:2000]}, ensure_ascii=False) + "\n")
            manifest.append({"dataset": ds, "episode_id": e["episode_id"], "task_type": e["task_type"],
                             "tokens": ntok, "turns": e["num_turns"], "questions": len(e["qa_pairs"]),
                             "success": e["success"]})
    json.dump(manifest, open(os.path.join(ext, "manifest.json"), "w"), indent=1)
    for m in manifest:
        print(m)
    print(len(manifest), "trajectories,", sum(m["questions"] for m in manifest), "questions,",
          sum(m["tokens"] for m in manifest), "tokens")


if __name__ == "__main__":
    main()
