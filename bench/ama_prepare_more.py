"""Further AMA-Bench trajectories for the address-index study, rendered exactly as bench/ama_prepare.py.

Selection:
  development  ama_af01-30  all 30 ALFWorld trajectories (embodied household tasks, 11k-63k tokens)
               ama_wa01-31  all 31 WebArena trajectories (web navigation, 10k-171k tokens)
               Neither domain was used before; the method is designed and tuned on these only.
  test (new)   ama_ws01-24  the 24 SWE-bench (OpenHands) trajectories not among the 12 longest already used
               ama_gs01-16  the 16 GAIA trajectories not used before: all 10 of level 1 and the 6 of level 2 below
                            150k tokens
               No method, prompt or setting is chosen on these.  The 26 trajectories of bench/ama_prepare.py
               (ama_g01-14, ama_w01-12) were seen in the earlier study and are reported separately.
Episodes are numbered by episode_id within each group.

python bench/ama_prepare_more.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "methods"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
from ama_prepare import render  # noqa: E402


def write(ds, e, text):
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


def main():
    ext = os.path.join(ROOT, "data", "_external", "ama_bench")
    eps = [json.loads(l) for l in open(os.path.join(ext, "open_end_qa_set.jsonl"), encoding="utf-8")]
    used = {m["episode_id"] for m in json.load(open(os.path.join(ext, "manifest.json")))}
    rendered = {e["episode_id"]: (e, render(e)) for e in eps}
    ntok = {k: core.ntok(t) for k, (e, t) in rendered.items()}

    def pick(cond):
        return sorted([k for k, (e, t) in rendered.items() if cond(e) and k not in used])
    groups = [("ama_af", "dev", pick(lambda e: e["task_type"] == "alfworld")),
              ("ama_wa", "dev", pick(lambda e: e["task_type"] == "webarena")),
              ("ama_ws", "test", pick(lambda e: e["task_type"] == "swebench")),
              ("ama_gs", "test", pick(lambda e: e["task_type"] == "gaia_level1" or
                                      (e["task_type"] == "gaia_level2" and ntok[e["episode_id"]] < 150_000)))]
    manifest = []
    for prefix, split, ids in groups:
        for k, eid in enumerate(ids, 1):
            e, text = rendered[eid]
            ds = f"{prefix}{k:02d}"
            write(ds, e, text)
            manifest.append({"dataset": ds, "split": split, "episode_id": eid, "task_type": e["task_type"],
                             "tokens": ntok[eid], "turns": e["num_turns"], "questions": len(e["qa_pairs"]),
                             "success": e["success"]})
    json.dump(manifest, open(os.path.join(ext, "manifest_more.json"), "w"), indent=1)
    for prefix, split, ids in groups:
        ms = [m for m in manifest if m["dataset"].startswith(prefix)]
        print(prefix, split, len(ms), "trajectories,", sum(m["questions"] for m in ms), "questions, tokens",
              min(m["tokens"] for m in ms), "-", max(m["tokens"] for m in ms))


if __name__ == "__main__":
    main()
