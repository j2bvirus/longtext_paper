"""Second check of the free-form judge.

The earlier check compared the GPT-6.1 Sol judge (reasoning effort low) with a blind judgment by the same model at
reasoning effort high on a stratified random sample of 300 answers. Here the 255 answers of that sample that belong to
the paper's domains (novels A-C, LoCoMo, AMA-Bench SWE-bench and GAIA) are judged
again by a model of another family, Claude Sonnet 5.5 (effort high), with exactly the prompts of the
primary judge (methods/judge.py: SYS for novels and LoCoMo, the AMA-Bench wording for ama_*), and 102 of them (17 per
domain, drawn with seed 0 from the 238 answers without a detected gold problem) are labelled by four people, blind to
method, reader and every model verdict. Primary analysis: the 238 answers without a detected gold problem; agreement
and Cohen's kappa for every pair of judges.

python methods/judge_check.py sample                       # data/judge_check/sample.json (ids, domain, gold status, blind verdict)
python methods/judge_check.py judge --judge claude:claude-sonnet-5-5 [--workers 4]   # runs/judge_check/<judge>.json
python methods/judge_check.py human                        # local labelling page paper/human_judge/index.html (not released)
python methods/judge_check.py report [--human data/judge_check/person_labels.json]
"""
import argparse
import collections
import hashlib
import html
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm  # noqa: E402
from judge import AMA_JUDGE, SYS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EARLIER = os.path.join(ROOT, "..", "codex_final_verify", "judge_reliability.json")
SAMPLE = os.path.join(ROOT, "data", "judge_check", "sample.json")
OUT = os.path.join(ROOT, "runs", "judge_check")
HUMAN_DIR = os.path.join(ROOT, "paper", "human_judge")
DOMAINS = ["novelA", "novelB", "novelC", "LoCoMo", "AMA_SWE", "AMA_GAIA"]
sha = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def load_item(s):
    """question, gold and the stored prediction of one sampled answer, from the prepared data and the result file"""
    qs = {}
    for line in open(os.path.join(ROOT, "data", s["dataset"], "questions_GOLD.jsonl"), encoding="utf-8"):
        q = json.loads(line)
        qs[q["qid"]] = q
    rec = next(json.loads(l) for l in open(os.path.join(ROOT, "runs", "results", s["name"] + ".jsonl"), encoding="utf-8")
               if json.loads(l)["qid"] == s["qid"])
    q = qs[s["qid"]]
    pred = (rec.get("pred") or "").strip()
    if sha(pred) != s["pred_sha"]:
        raise SystemExit(f"{s['id']}: stored prediction differs from the sampled one")
    return q["question"], q["answer"]["gold"], pred


def cmd_sample(a):
    rows = [r for r in json.load(open(EARLIER, encoding="utf-8"))["rows"] if r["domain"] in DOMAINS]
    out = [{"id": r["id"], "domain": r["domain"], "dataset": r["dataset"], "qid": r["qid"], "name": r["name"],
            "gold_status": r["gold_status"], "gpt_high_blind": r["verdict"], "pred_sha": sha((r["prediction"] or "").strip())}
           for r in rows]
    clean = [s for s in out if s["gold_status"] == "no_defect_detected"]
    rng = random.Random(0)
    human = []
    for dom in DOMAINS:
        pool = sorted((s for s in clean if s["domain"] == dom), key=lambda s: s["id"])
        human += [s["id"] for s in rng.sample(pool, 17)]
    os.makedirs(os.path.dirname(SAMPLE), exist_ok=True)
    json.dump({"items": out, "human_ids": human}, open(SAMPLE, "w", encoding="utf-8"), indent=1)
    print(len(out), "items,", len(clean), "without a detected gold problem,", len(human), "for the person")


def cmd_judge(a):
    S = json.load(open(SAMPLE, encoding="utf-8"))
    name = a.judge.replace(":", "-")

    def one(s):
        q, g, p = load_item(s)
        if not p or p.lower() in ("unknown", "unknown."):
            return s["id"], 0
        if s["dataset"].startswith("ama_"):
            r = llm.call(a.judge, "You are an expert evaluator.", AMA_JUDGE.format(q=q, g=g, p=p), max_tokens=5,
                         tag=f"judgecheck|{s['dataset']}")
            return s["id"], int(r["text"].strip().lower().startswith("yes"))
        r = llm.call(a.judge, SYS, f"Question: {q}\nGold answer: {g}\nModel answer: {p}\nVerdict:", max_tokens=5,
                     tag=f"judgecheck|{s['dataset']}")
        return s["id"], int(r["text"].strip().lower().startswith("correct"))

    with ThreadPoolExecutor(a.workers) as ex:
        verdicts = dict(ex.map(one, S["items"]))
    os.makedirs(OUT, exist_ok=True)
    json.dump(verdicts, open(os.path.join(OUT, name + ".json"), "w"), indent=0)
    print(name, len(verdicts), "verdicts,", sum(verdicts.values()), "correct")


# The labelling page template is kept with the local pages (paper/human_judge/page_template.html, not released);
# runs/judge_check/SETTINGS.md gives its instructions.
PAGE_TEMPLATE = os.path.join(HUMAN_DIR, "page_template.html")


def cmd_human(a):
    """--annotator "" is the author's page (index.html, order seed 1); A, B, C are the further annotators
    (index_<X>.html, own storage key and file name, own order); items and instructions are the same for all"""
    S = json.load(open(SAMPLE, encoding="utf-8"))
    by = {s["id"]: s for s in S["items"]}
    ids = list(S["human_ids"])
    who = a.annotator
    kinds = json.load(open(os.path.join(HUMAN_DIR, "page_labels.json"), encoding="utf-8"))  # item labels of the page
    random.Random(1 if not who else f"order-{who}").shuffle(ids)  # mixed order, so domains and methods are not read in blocks
    items = []
    for i in ids:
        q, g, p = load_item(by[i])
        kind = kinds["ama"] if by[i]["dataset"].startswith("ama_") else kinds["text"]
        items.append({"key": i, "kind": kind, "q": html.escape(q), "g": html.escape(g), "p": html.escape(p)})
    os.makedirs(HUMAN_DIR, exist_ok=True)
    key, fname, page_name = ("human_judge_labels_v1", "labels.json", "index.html") if not who else (
        f"human_judge_labels_v1_{who}", f"labels_{who}.json", f"index_{who}.html")
    PAGE = open(PAGE_TEMPLATE, encoding="utf-8", newline="").read()
    page = (PAGE.replace("__ITEMS__", json.dumps(items, ensure_ascii=False)).replace("__KEY__", key)
            .replace("__FILE__", fname).replace("__WHO__", f" {who}" if who else ""))
    open(os.path.join(HUMAN_DIR, page_name), "w", encoding="utf-8").write(page)
    print(len(items), "items in", os.path.join(HUMAN_DIR, page_name))


def kappa(x, y):
    n = len(x)
    po = sum(a == b for a, b in zip(x, y)) / n
    px, py = sum(x) / n, sum(y) / n
    pe = px * py + (1 - px) * (1 - py)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def cmd_report(a):
    S = json.load(open(SAMPLE, encoding="utf-8"))
    items = [s for s in S["items"] if s["gold_status"] == "no_defect_detected"]
    clean = {s["id"] for s in items}
    J = {"GPT-6.1 Sol, low (primary judge)": {}, "GPT-6.1 Sol, high (blind)": {}}
    # the first judge's verdicts of these answers, taken from runs/judged/ (not released) into an id-only file
    haiku = json.load(open(os.path.join(os.path.dirname(SAMPLE), "haiku_first_judge.json")))
    for s in items:
        J["GPT-6.1 Sol, low (primary judge)"][s["id"]] = json.load(open(os.path.join(ROOT, "runs", "judged_gpt", s["name"] + ".json")))[s["qid"]]
        if s["gpt_high_blind"] is not None:
            J["GPT-6.1 Sol, high (blind)"][s["id"]] = s["gpt_high_blind"]
        if s["id"] in haiku:
            J.setdefault("Claude Haiku 4.5 (first judge)", {})[s["id"]] = haiku[s["id"]]
    for f in sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []:
        if f.endswith(".json"):  # the folder also holds SETTINGS.md
            J[f[:-5]] = {k: v for k, v in json.load(open(os.path.join(OUT, f))).items() if k in clean}
    persons = []
    files = [("Person (author)", a.human)] + [(f"Person {x}", os.path.join(os.path.dirname(SAMPLE), f"person_labels_{x}.json"))
                                              for x in "ABC"]
    for pname, pf in files:
        if pf and os.path.exists(pf):
            lab = json.load(open(pf, encoding="utf-8"))
            J[pname] = {k: int(v) for k, v in lab.items() if v in ("0", "1") and k in clean}
            persons.append(pname)
            print(f"{pname}: {len(lab)} labels, {sum(v == 'x' for v in lab.values())} 'cannot tell'")
    if len(persons) >= 2:
        # majority of the people who decided an answer (a tie gives no majority); Fleiss' kappa over the answers
        # that every person decided
        maj = {}
        for k in clean:
            vs = [J[p][k] for p in persons if k in J[p]]
            if len(vs) >= 2 and sum(vs) * 2 != len(vs):
                maj[k] = int(sum(vs) * 2 > len(vs))
        J["People, majority"] = maj
        allk = [k for k in clean if all(k in J[p] for p in persons)]
        m, n_items = len(persons), len(allk)
        if n_items:
            p1 = sum(J[p][k] for p in persons for k in allk) / (m * n_items)
            pbar = sum((sum(J[p][k] for p in persons) ** 2 + (m - sum(J[p][k] for p in persons)) ** 2 - m) / (m * (m - 1))
                       for k in allk) / n_items
            pe = p1 ** 2 + (1 - p1) ** 2
            print(f"Fleiss' kappa among {m} people on the {n_items} answers all decided: {(pbar - pe) / (1 - pe):.2f}")
    names = list(J)
    print(f"# Judge check on {len(items)} answers without a detected gold problem (agreement %, Cohen's kappa, n)\n")
    print("| Judge A | Judge B | n | agreement % | kappa |\n|---|---|---|---|---|")
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            common = [k for k in J[x] if k in J[y]]
            if len(common) < 10:
                continue
            po, k = kappa([J[x][c] for c in common], [J[y][c] for c in common])
            print(f"| {x} | {y} | {len(common)} | {100 * po:.1f} | {k:.2f} |")
    print("\nAccepted share: " + "; ".join(f"{n} {100 * sum(J[n].values()) / len(J[n]):.1f}% of {len(J[n])}" for n in names))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "judge", "human", "report"])
    ap.add_argument("--judge", default="claude:claude-sonnet-5-5")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--annotator", default="", help="A, B or C for the further annotators")
    ap.add_argument("--human", default=os.path.join(os.path.dirname(SAMPLE), "person_labels.json"))  # ids and labels only
    a = ap.parse_args()
    {"sample": cmd_sample, "judge": cmd_judge, "human": cmd_human, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
