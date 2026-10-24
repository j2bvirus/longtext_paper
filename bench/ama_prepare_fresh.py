"""The remaining, never-used AMA-Bench trajectories, as a fresh test set for later versions of the address index.

Selection:
  ama_sp01-51  all 51 Spider 2.0 trajectories (text-to-SQL agents; tool calls with paths and SQL; 0.6k-17.5k tokens)
  ama_gm01-30  all 30 BALROG game trajectories (2048, BabaIsAI, Candy Crush, Crafter, MiniHack; 3k-38k tokens)
With bench/ama_prepare.py (26) and bench/ama_prepare_more.py (101) this uses all 208 trajectories of the
open-ended set.  Rendering and question format as in bench/ama_prepare.py.

python bench/ama_prepare_fresh.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "methods"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
from ama_prepare import render  # noqa: E402
from ama_prepare_more import write  # noqa: E402


def main():
    ext = os.path.join(ROOT, "data", "_external", "ama_bench")
    eps = [json.loads(l) for l in open(os.path.join(ext, "open_end_qa_set.jsonl"), encoding="utf-8")]
    used = {m["episode_id"] for m in json.load(open(os.path.join(ext, "manifest.json")))}
    used |= {m["episode_id"] for m in json.load(open(os.path.join(ext, "manifest_more.json")))}
    games = {"2048", "babaisai", "candy_crush", "crafter", "minihack"}
    groups = [("ama_sp", sorted(e["episode_id"] for e in eps if e["task_type"] == "spider2" and e["episode_id"] not in used)),
              ("ama_gm", sorted(e["episode_id"] for e in eps if e["task_type"] in games and e["episode_id"] not in used))]
    by_id = {e["episode_id"]: e for e in eps}
    manifest = []
    for prefix, ids in groups:
        for k, eid in enumerate(ids, 1):
            e = by_id[eid]
            text = render(e)
            ds = f"{prefix}{k:02d}"
            write(ds, e, text)
            manifest.append({"dataset": ds, "split": "fresh test", "episode_id": eid, "task_type": e["task_type"],
                             "tokens": core.ntok(text), "turns": e["num_turns"], "questions": len(e["qa_pairs"]),
                             "success": e["success"]})
    json.dump(manifest, open(os.path.join(ext, "manifest_fresh.json"), "w"), indent=1)
    for prefix, ids in groups:
        ms = [m for m in manifest if m["dataset"].startswith(prefix)]
        print(prefix, len(ms), "trajectories,", sum(m["questions"] for m in ms), "questions, tokens",
              min(m["tokens"] for m in ms), "-", max(m["tokens"] for m in ms))
    print("all used:", len(used) + len(manifest), "of", len(eps))


if __name__ == "__main__":
    main()
