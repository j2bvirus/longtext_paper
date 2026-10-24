"""Practitioner-style agentic baseline: Claude Code (headless) with its own Grep / Read / Glob tools over the raw
trajectory file.

This is what a user of a coding agent does when asked about a long log: the log is a file, and the agent searches
and reads it with its native tools for as many turns as it likes.  The trajectory (record_full.txt, rendered as for
every other method) is copied alone into an empty directory; the CLI runs there in restricted mode (file tools
confined to that directory, no shell, no web, no MCP servers, no settings files), with only Read, Grep and Glob
available and pre-approved, and a short instruction instead of the default system prompt.  Reader tokens are the
input tokens the CLI reports over all turns (cache reads included), i.e. everything the model processed.

python methods/cc_agent_eval.py --data ama_af01 [--model claude-haiku-4-5-20251001] [--workers 4]
Result file: runs/results/<ds>_full_ccagent_claude-<model>_b4000_p-minimal.jsonl (read by judge.py and
addr_report.py like any other run).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM = ("You answer a question about the recorded trajectory of an AI agent. The whole trajectory is the file "
          "trajectory.txt in the current directory: a task description, then numbered steps, each starting with "
          "'Step N:' and holding the agent's action and the observation it received. Use the Grep, Read and Glob "
          "tools to find what you need in that file; it is long, so search rather than reading it all. Use only the "
          "file. When you are done, give the final answer on a line starting with 'Answer:' (it may continue on the "
          "following lines).")


def run_one(wd, q, model):
    if os.path.exists(os.path.join(ROOT, "runs", "NO_CLAUDE")):  # same block as llm.py
        raise RuntimeError("Claude calls disabled (runs/NO_CLAUDE exists)")
    cmd = [llm.CLAUDE_EXE, "-p", "--model", model, "--output-format", "json", "--system-prompt", SYSTEM,
           "--restricted", "--strict-mcp-config", "--tools", "Read,Grep,Glob", "--allowedTools", "Read Grep Glob",
           "--permission-mode", "dontAsk", "--no-session-persistence"]
    env = dict(os.environ, MAX_THINKING_TOKENS="0")
    t0 = time.time()
    for attempt in range(3):
        p = subprocess.run(cmd, input=q["question"].encode("utf-8"), capture_output=True, timeout=1800, cwd=wd,
                           env=env)
        try:
            d = json.loads(p.stdout.decode("utf-8", errors="replace"))
        except ValueError:
            d = {"is_error": True, "result": p.stderr.decode("utf-8", "replace")[-300:]}
        if not d.get("is_error"):
            break
        time.sleep(30 * (attempt + 1))
    u = d.get("usage", {})
    tin = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    text = d.get("result") or ""
    return {"qid": q["qid"], "qtype": q["qtype"], "gold": q["answer"]["gold"], "pred": core.parse_answer(text),
            "correct": 0, "raw": text[-2000:], "ctx_tokens": tin, "escalated": False, "in_tokens": tin,
            "out_tokens": u.get("output_tokens", 0), "usd": d.get("total_cost_usd", 0.0), "wall_s": time.time() - t0,
            "cached": False, "truncated": False, "ev_recall": None, "n_chunks": d.get("num_turns", 0),
            "certified": False, "core_recall": None, "rounds": d.get("num_turns", 0),
            "error": d.get("result") if d.get("is_error") else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    ddir = os.path.join(ROOT, "data", a.data)
    qs = [json.loads(l) for l in open(os.path.join(ddir, "questions_GOLD.jsonl"), encoding="utf-8")]
    wd = os.path.join(os.environ.get("TEMP", ROOT), "cc_agent", a.data)
    os.makedirs(wd, exist_ok=True)
    shutil.copyfile(os.path.join(ddir, "record_full.txt"), os.path.join(wd, "trajectory.txt"))
    name = f"{a.data}_full_ccagent_claude-{a.model}_b4000_p-minimal"
    out = os.path.join(ROOT, "runs", "results", name + ".jsonl")
    done = {json.loads(l)["qid"] for l in open(out, encoding="utf-8")} if os.path.exists(out) else set()
    todo = [q for q in qs if q["qid"] not in done]
    with open(out, "a", encoding="utf-8") as f, ThreadPoolExecutor(a.workers) as ex:
        for rec in ex.map(lambda q: run_one(wd, q, a.model), todo):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    recs = [json.loads(l) for l in open(out, encoding="utf-8")]
    summ = {"name": name, "n": len(recs), "errors": sum(1 for r in recs if r.get("error")),
            "mean_ctx_tokens": sum(r["ctx_tokens"] for r in recs) / max(1, len(recs)),
            "mean_turns": sum(r["rounds"] for r in recs) / max(1, len(recs)), "sum_usd": sum(r["usd"] for r in recs)}
    json.dump(summ, open(os.path.join(ROOT, "runs", "results", name + ".summary.json"), "w"), indent=1)
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
