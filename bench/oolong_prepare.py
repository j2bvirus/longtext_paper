"""Oolong-real (Bertsch et al., arXiv 2511.02817, COLM 2026; HF oolongbench/oolong-real, config dnd) as a real-text
test of the event-type index: Critical Role transcripts (CRD3, CC BY-SA 4.0), questions on dice rolls and spells
counted over windows of 1-24 episodes, gold from CritRoleStats.

The published jsonl repeats the whole context window on every question line (9.3 GB per split).  This script
streams a split once and writes, without keeping the raw file:
  data/_external/oolong_real/<split>/windows/<context_window_id>.txt   each window text once
  data/_external/oolong_real/<split>/questions.jsonl                   every question without its context
  data/_external/oolong_real/<split>/windows.json                      window id -> episodes, campaign, characters
Nothing is edited; questions keep their id, answer and question_type.

python bench/oolong_prepare.py validation|test
"""
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://huggingface.co/datasets/oolongbench/oolong-real/resolve/main/dnd/{}.jsonl"


def main():
    split = sys.argv[1]
    out = os.path.join(ROOT, "data", "_external", "oolong_real", split)
    os.makedirs(os.path.join(out, "windows"), exist_ok=True)
    seen, meta, n = set(), {}, 0
    t0 = time.time()
    r = urllib.request.urlopen(URL.format(split), timeout=300)
    buf = b""
    with open(os.path.join(out, "questions.jsonl"), "w", encoding="utf-8") as qf:
        while True:
            chunk = r.read(8 << 20)
            if chunk:
                buf += chunk
            lines = buf.split(b"\n")
            buf = lines.pop() if chunk else b""
            for line in lines:
                if not line.strip():
                    continue
                x = json.loads(line)
                wid = x["context_window_id"]
                if wid not in seen:
                    seen.add(wid)
                    with open(os.path.join(out, "windows", wid + ".txt"), "w", encoding="utf-8") as wf:
                        wf.write(x["context_window_text"])
                    meta[wid] = {"episodes": x.get("episodes"), "campaign": x.get("campaign"),
                                 "chars": len(x["context_window_text"])}
                q = {k: v for k, v in x.items() if k != "context_window_text"}
                qf.write(json.dumps(q, ensure_ascii=False) + "\n")
                n += 1
                if n % 1000 == 0:
                    print(f"{n} questions, {len(seen)} windows, {time.time() - t0:.0f} s", flush=True)
            if not chunk:
                break
    json.dump(meta, open(os.path.join(out, "windows.json"), "w"), indent=1)
    print(f"done: {n} questions, {len(seen)} windows, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
