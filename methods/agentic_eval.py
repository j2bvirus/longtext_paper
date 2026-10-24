"""Agentic search baseline over a raw agent trajectory.

A query-time alternative to a precomputed index, in the spirit of grep/read agents over raw text (DCI-Lite, Li et
al. 2026, arXiv 2605.05242; AutoMEM's rg/read tools, arXiv 2606.04315; AMA-Agent's NEED_CODE path).  No build step.
The reader gets the task description and the number of steps, and may issue up to MAX_ROUNDS commands, one per
turn, before answering:
  SEARCH: <text>     literal, case-insensitive search; returns how many steps contain it and up to 15 hits as
                     'Step N: <the matching line, cut>'
  READ: <N> or READ: <N>-<M>   the verbatim text of those steps, cut to 1,500 tokens
  LIST: <N>-<M>      one line per step with the action, cut to 1,000 tokens
  Answer: <answer>   final answer (may continue on the following lines)
The backends are single-shot command-line calls, so each turn resends the instruction and the whole transcript so
far; ctx_tokens is the sum of the prompts of all turns (what the reader actually reads).  The result file has the
same format as run_eval.py (method name 'agrep'), so judge.py and addr_report.py read it unchanged.

python methods/agentic_eval.py --data ama_af01 --reader claude:claude-haiku-4-5-20251001 [--workers 6]
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import llm  # noqa: E402
from addrindex import STEP_HEAD, cut  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_ROUNDS = 6
SYSTEM = ("You answer a question about the recorded trajectory of an AI agent (its numbered steps, each with an action "
          "and an observation). You cannot see the trajectory, but you can query it with commands, one per turn:\n"
          "SEARCH: <text>  - literal, case-insensitive search; shows how many steps contain the text and up to 15 hits\n"
          "READ: <N> or READ: <N>-<M>  - the full text of step N (or steps N to M), cut to about 1,500 tokens\n"
          "LIST: <N>-<M>  - the action of every step from N to M, one line each\n"
          "Answer: <answer>  - your final answer\n"
          f"You may use at most {MAX_ROUNDS} commands. Each reply contains exactly ONE command and then stops: the "
          "system runs it and shows you the result in the next turn. Never write a command's result yourself and "
          "never write more than one command. Write the command as plain text on its own line, for example "
          "'SEARCH: safe 1' or 'READ: 12-14'; do not use XML or function-call syntax. Think briefly if needed before "
          "the command. When you answer, give the final answer after 'Answer:' (it may continue on the following "
          "lines).")
CMD = re.compile(r"(?im)^\s*\**\s*(SEARCH|READ|LIST|ANSWER)\s*\**\s*:\s*(.*)$")
CMD_ANY = re.compile(r"(?i)\b(SEARCH|READ|LIST)\s*:\s*([^\n<]+)")
XML_CMD = re.compile(r"(?is)<invoke name=\"(search|read|list)\">.*?<parameter[^>]*>([^<]+)</parameter>")


def first_command(raw):
    """(kind, argument, match start, match end) of the first command in a reply, or None"""
    found = []
    for rx in (CMD, CMD_ANY, XML_CMD):
        m = rx.search(raw)
        if m:
            found.append((m.start(), m.group(1).upper(), m.group(2), m.end()))
    if not found:
        return None
    st, kind, arg, en = min(found)
    return kind, arg, st, en


class Trajectory:
    def __init__(self, text):
        self.task, self.steps = "", {}
        cur = None
        for part in text.split("\n\n"):
            if not part.strip():
                continue
            m = STEP_HEAD.match(part)
            if m:
                cur = int(m.group(1))
                self.steps.setdefault(cur, []).append(part)
            elif part.startswith("Task description"):
                self.task += part + "\n"
                cur = None
            elif cur is not None:
                self.steps[cur].append(part)
        self.ids = sorted(self.steps)
        self.action = {}
        for s in self.ids:
            body = STEP_HEAD.sub("", self.steps[s][0], count=1).strip()
            self.action[s] = body.partition("\nObservation:")[0].replace("Action:", "", 1).strip()

    def search(self, q):
        q = q.strip().strip("\"'`")
        if not q:
            return "Empty search."
        ql = q.lower()
        hits = []
        for s in self.ids:
            for part in self.steps[s]:
                k = part.lower().find(ql)
                if k >= 0:
                    line_start = part.rfind("\n", 0, k) + 1
                    line_end = part.find("\n", k)
                    line = part[line_start: line_end if line_end >= 0 else len(part)]
                    hits.append((s, line))
                    break
        if not hits:
            return f"No step contains '{q}'."
        out = [f"{len(hits)} step(s) contain '{q}'" + (" (first 15 shown)" if len(hits) > 15 else "") + ":"]
        out += [f"Step {s}: {cut(line, 25)}" for s, line in hits[:15]]
        return "\n".join(out)

    def _range(self, arg):
        m = re.match(r"\s*(\d+)\s*(?:-|to|–)\s*(\d+)", arg)
        if m:
            a, b = sorted((int(m.group(1)), int(m.group(2))))
            return [s for s in self.ids if a <= s <= b]
        m = re.match(r"\s*(\d+)", arg)
        return [int(m.group(1))] if m and int(m.group(1)) in self.steps else []

    def read(self, arg):
        ss = self._range(arg)
        if not ss:
            return "No such step."
        txt = "\n\n".join(p for s in ss for p in self.steps[s])
        return cut(txt, 1500) if core.ntok(txt) > 1500 else txt

    def list(self, arg):
        ss = self._range(arg)
        if not ss:
            return "No such steps."
        txt = "\n".join(f"Step {s}: {cut(self.action[s], 30)}" for s in ss)
        return cut(txt, 1000) if core.ntok(txt) > 1000 else txt


def run_one(tr, q, reader, name):
    head = (f"Task of the agent:\n{cut(tr.task, 300)}\n\nThe trajectory has {len(tr.ids)} steps, numbered "
            f"{tr.ids[0]} to {tr.ids[-1]}.\n\nQuestion: {q['question']}")
    transcript, tot_in, tot_out, usd, wall, raw = [], 0, 0, 0.0, 0.0, ""
    rounds, nudged = 0, False
    for rnd in range(MAX_ROUNDS + 2):
        last = rounds >= MAX_ROUNDS or rnd == MAX_ROUNDS + 1
        prompt = head + ("\n\n" + "\n\n".join(transcript) if transcript else "")
        if last:
            prompt += "\n\nNo commands are left. Give your final answer now, as 'Answer: <answer>'."
        r = llm.call(reader, SYSTEM, prompt, max_tokens=400, tag=f"read|{name}|{q['qid']}|r{rnd}")
        tot_in += core.ntok(prompt)
        tot_out += r["out_tokens"]
        usd += r["usd"]
        wall += r["wall_s"]
        raw = r["text"]
        c = first_command(raw)
        if c is None:
            if last or nudged:
                break
            nudged = True  # once per question: remind the reader of the command format
            transcript.append("(No command was found in your reply. Reply with exactly one command line, e.g. "
                              "'SEARCH: <text>', or 'Answer: <answer>'.)")
            continue
        kind, arg, st, en = c  # only the first command runs; anything after it is discarded
        if kind == "ANSWER":
            nxt = first_command(raw[en:])
            raw = raw[st: en + nxt[2] if nxt else len(raw)]
            break
        if last:
            break
        rounds += 1
        res = {"SEARCH": tr.search, "READ": tr.read, "LIST": tr.list}[kind](arg)
        transcript.append(f"Your command {rounds}: {kind}: {arg.strip()}\nResult:\n{res}")
    pred = core.parse_answer(raw)
    return {"qid": q["qid"], "qtype": q["qtype"], "gold": q["answer"]["gold"], "pred": pred, "correct": 0,
            "raw": raw[-2000:], "ctx_tokens": tot_in, "escalated": False, "in_tokens": tot_in, "out_tokens": tot_out,
            "usd": usd, "wall_s": wall, "cached": False, "truncated": False, "ev_recall": None, "n_chunks": rounds,
            "certified": False, "core_recall": None, "rounds": rounds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--reader", default="claude:claude-haiku-4-5-20251001")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    ddir = os.path.join(ROOT, "data", a.data)
    text = open(os.path.join(ddir, "record_full.txt"), encoding="utf-8").read()
    qs = [json.loads(l) for l in open(os.path.join(ddir, "questions_GOLD.jsonl"), encoding="utf-8")]
    tr = Trajectory(text)
    name = f"{a.data}_full_agrep_{a.reader.replace(':', '-')}_b4000_p-minimal"
    out = os.path.join(ROOT, "runs", "results", name + ".jsonl")
    done = {json.loads(l)["qid"] for l in open(out, encoding="utf-8")} if os.path.exists(out) else set()
    todo = [q for q in qs if q["qid"] not in done]
    with open(out, "a", encoding="utf-8") as f, ThreadPoolExecutor(a.workers) as ex:
        for rec in ex.map(lambda q: run_one(tr, q, a.reader, name), todo):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    recs = [json.loads(l) for l in open(out, encoding="utf-8")]
    summ = {"name": name, "n": len(recs), "mean_ctx_tokens": sum(r["ctx_tokens"] for r in recs) / max(1, len(recs)),
            "mean_rounds": sum(r["rounds"] for r in recs) / max(1, len(recs)),
            "sum_in_tokens": sum(r["in_tokens"] for r in recs), "sum_usd": sum(r["usd"] for r in recs)}
    json.dump(summ, open(os.path.join(ROOT, "runs", "results", name + ".summary.json"), "w"), indent=1)
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
