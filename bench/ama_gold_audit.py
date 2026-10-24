"""Gold-answer audit of the AMA-Bench questions we use (some expert gold answers disagree with the
trajectory, e.g. ama_w01 'At step 68, what exact action did the agent execute?' has gold 'grep for
has_add_permission' while turn_idx 68 of the source trajectory runs the tests and the grep is at turns 56-57).
No question or gold is edited; a second, documented label per question is added and results are reported on all
questions and on the gold-confirmed subset.

GPT (gpt-6.1-sol) reads the evidence and labels each (question, gold) pair ok / ambiguous / wrong:
  SWE trajectories (<= 90k tokens): the whole rendered record, all 12 questions of the trajectory in one call;
  GAIA trajectories (up to 1.06M tokens): per question, the task description plus every step the question or the
  gold names (with one step on each side) and the last two steps; a question that names no step is 'not auditable'.
Writes data/<ds>/gold_audit_gpt.json and prints a summary.

python bench/ama_gold_audit.py ama_w01 ama_w02 ...      (or: all)
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "methods"))
import core  # noqa: E402
import llm  # noqa: E402

G = os.environ.get("AUDIT_MODEL", "codex:gpt-6.1-sol")  # AUDIT_MODEL=claude:claude-sonnet-5-5 for the Sonnet audit
OUT = "gold_audit_gpt.json" if G.startswith("codex:") else "gold_audit_" + G.split(":")[1].split("-")[1] + ".json"
SYS = ("You check reference answers of a benchmark about an AI agent's trajectory (its steps, actions and "
       "observations). Use only the trajectory text you are given; steps are numbered as 'Step N'. For each "
       "question, compare the reference answer with what the trajectory shows. Labels: ok = the reference answer is "
       "correct for the question as asked; ambiguous = the question does not pin down one answer, or the trajectory "
       "supports several reasonable answers; wrong = the trajectory contradicts the reference answer (for example "
       "it names the wrong step, value or action). Judge the substance, not the wording.")
STEP_RE = re.compile(r"\b(?:step|turn)s?\s+(\d+)(?:\s*(?:-|–|to|and)\s*(\d+))?", re.I)


def steps_of(text):
    """record -> {step number: list of paragraphs of that step} (pieces 'Step N:' / 'Step N (continued):')"""
    out = {}
    for p in text.split("\n\n"):
        m = re.match(r"Step (\d+)(?: \(continued\))?:", p)
        if m:
            out.setdefault(int(m.group(1)), []).append(p)
    return out


def task_of(text):
    return "\n\n".join(p for p in text.split("\n\n") if p.startswith("Task description"))


def named_steps(s):
    ns = set()
    for a, b in STEP_RE.findall(s):
        a = int(a)
        b = int(b) if b else a
        if b < a or b - a > 30:
            b = a
        ns.update(range(a, b + 1))
    return ns


def parse_labels(txt, qids):
    lab = {}
    for line in txt.splitlines():
        m = re.match(r"\s*\**\s*(Q\d{4})\s*\**\s*[:\-–|]\s*\**\s*(ok|ambiguous|wrong)\b(.*)", line.strip(), re.I)
        if m and m.group(1) in qids:
            lab[m.group(1)] = (m.group(2).lower(), m.group(3).strip(" -–:|*")[:300])
    return lab


def audit(ds):
    d = os.path.join(ROOT, "data", ds)
    text = open(os.path.join(d, "record_full.txt"), encoding="utf-8").read()
    qs = [json.loads(l) for l in open(os.path.join(d, "questions_GOLD.jsonl"), encoding="utf-8")]
    res = {}
    fmt = ("Give one line per question, exactly in the form\nQ0000: ok|ambiguous|wrong - short reason\n")
    if ds.startswith(("ama_w", "ama_af", "ama_sp", "ama_gm")):  # whole trajectory (ALFWorld, Spider 2.0 and games added; at most 171k tokens)
        block = "\n\n".join(f"{q['qid']}\nQuestion: {q['question']}\nReference answer: {q['answer']['gold']}" for q in qs)
        r = llm.call(G, SYS, f"Trajectory:\n{text}\n\nQuestions with reference answers:\n\n{block}\n\n{fmt}",
                     max_tokens=3000, tag=f"build|ama_gold_audit|{ds}")
        lab = parse_labels(r["text"], {q["qid"] for q in qs})
        for q in qs:
            res[q["qid"]] = {"label": lab.get(q["qid"], ("unparsed", ""))[0], "reason": lab.get(q["qid"], ("", ""))[1],
                             "evidence": "whole trajectory"}
        return ds, res
    st = steps_of(text)
    last = sorted(st)[-2:]

    def one(q):
        ns = named_steps(q["question"] + " " + q["answer"]["gold"])
        if not ns:
            return q["qid"], {"label": "not auditable", "reason": "names no step", "evidence": ""}
        keep = sorted({k for n in ns for k in (n - 1, n, n + 1) if k in st} | set(last))
        ev = "\n\n".join(p for k in keep for p in st[k])
        if core.ntok(ev) > 60000 or len(ev) > 400_000:  # cap: keep the named steps only
            keep = sorted({n for n in ns if n in st} | set(last))
            ev = "\n\n".join(p for k in keep for p in st[k])
        if len(ev) > 400_000:  # the Codex CLI accepts at most 1,048,576 characters per input
            ev = ev[:400_000] + "\n[... the rest of the shown steps is cut for length ...]"
        prompt = (f"Task:\n{task_of(text)[:6000]}\n\nSelected steps of the trajectory (only these steps are shown):\n"
                  f"{ev}\n\n{q['qid']}\nQuestion: {q['question']}\nReference answer: {q['answer']['gold']}\n\n"
                  f"If the shown steps are not enough to decide, answer ambiguous. {fmt}")
        r = llm.call(G, SYS, prompt, max_tokens=600, tag=f"build|ama_gold_audit|{ds}")
        lab = parse_labels(r["text"], {q["qid"]})
        return q["qid"], {"label": lab.get(q["qid"], ("unparsed", ""))[0], "reason": lab.get(q["qid"], ("", ""))[1],
                          "evidence": f"steps {keep}"}
    with ThreadPoolExecutor(3) as ex:
        res = dict(ex.map(one, qs))
    return ds, res


def main():
    dss = sys.argv[1:]
    if dss == ["all"]:
        dss = sorted(x for x in os.listdir(os.path.join(ROOT, "data")) if re.fullmatch(r"ama_[gw]\d\d", x))
    tot = {}
    for ds in dss:
        _, res = audit(ds)
        json.dump(res, open(os.path.join(ROOT, "data", ds, OUT), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        c = {}
        for v in res.values():
            c[v["label"]] = c.get(v["label"], 0) + 1
            tot[v["label"]] = tot.get(v["label"], 0) + 1
        print(ds, c, flush=True)
    print("total", tot)


if __name__ == "__main__":
    main()
