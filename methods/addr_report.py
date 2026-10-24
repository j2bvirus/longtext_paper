"""Report of the address-index study on AMA-Bench trajectories (no LLM calls; reads judged verdicts).

python methods/addr_report.py --data ama_af01,...  [--judged runs/judged_gpt_block] [--reader claude-claude-haiku-4-5-20251001]
       [--methods mem-addr,mem-pbm25,hybrid,full] [--audit]   (--audit: also the subset whose gold the GPT audit labels ok)

Accuracy per domain (dataset prefix) and pooled, per AMA question type (A recall, B causal inference, C state
updating, D state abstraction), reader-context tokens per question, and exact McNemar of the first method against
each other method (Holm-corrected over the comparisons of each table).
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mcnemar(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run = [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        out[i] = run
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--judged", default="runs/judged_gpt_block")
    ap.add_argument("--reader", default="claude-claude-haiku-4-5-20251001")
    ap.add_argument("--methods", default="mem-addr,mem-pbm25,hybrid,full")
    ap.add_argument("--tag", default="_p-minimal")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--audit_file", default="gold_audit_gpt.json", help="e.g. gold_audit_sonnet.json")
    a = ap.parse_args()
    dss = a.data.split(",")
    methods = a.methods.split(",")
    v = {}  # (method, ds, qid) -> 0/1
    tok = defaultdict(list)
    qtype = {}
    ok_gold = set()
    for ds in dss:
        for l in open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"), encoding="utf-8"):
            q = json.loads(l)
            qtype[(ds, q["qid"])] = q["qtype"].replace("AMA_", "")
        ap_ = os.path.join(ROOT, "data", ds, a.audit_file)
        if os.path.exists(ap_):
            for qid, x in json.load(open(ap_, encoding="utf-8")).items():
                if x["label"] == "ok":
                    ok_gold.add((ds, qid))
        for m in methods:
            name = f"{ds}_full_{m}_{a.reader}_b4000{a.tag}"
            jf = os.path.join(ROOT, a.judged, name + ".json")
            rf = os.path.join(ROOT, "runs", "results", name + ".jsonl")
            if not os.path.exists(jf):
                continue
            for qid, c in json.load(open(jf)).items():
                v[(m, ds, qid)] = c
            for l in open(rf, encoding="utf-8"):
                x = json.loads(l)
                tok[m].append(x["ctx_tokens"])
    subsets = [("all questions", None)] + ([("gold labelled ok by the GPT audit", ok_gold)] if a.audit else [])
    doms = sorted({re.sub(r"\d+$", "", ds) for ds in dss})
    for sname, keep in subsets:
        print(f"\n### {sname}\n")
        print("| Method | " + " | ".join(doms) + " | pooled | A | B | C | D | tokens/q | w/l vs first | p (Holm) |")
        print("|---|" + "---|" * (len(doms) + 9))
        keys_all = {(ds, qid) for (m, ds, qid) in v if m == methods[0]}
        if keep is not None:
            keys_all &= keep
        rows, ps = [], []
        for m in methods:
            ks = [k for k in keys_all if (m,) + k in v]
            if not ks:
                continue
            cells = []
            for d in doms:
                kd = [k for k in ks if re.sub(r"\d+$", "", k[0]) == d]
                cells.append(f"{100 * sum(v[(m,) + k] for k in kd) / len(kd):.1f} ({len(kd)})" if kd else "–")
            pooled = f"{100 * sum(v[(m,) + k] for k in ks) / len(ks):.1f}"
            for t in "ABCD":
                kt = [k for k in ks if qtype[k] == t]
                cells.append(f"{100 * sum(v[(m,) + k] for k in kt) / len(kt):.1f}" if kt else "–")
            w = sum(1 for k in ks if v[(methods[0],) + k] and not v[(m,) + k])
            l_ = sum(1 for k in ks if v[(m,) + k] and not v[(methods[0],) + k])
            rows.append([m, cells[:len(doms)], pooled, cells[len(doms):], sum(tok[m]) / max(1, len(tok[m])), w, l_])
            ps.append(mcnemar(w, l_) if m != methods[0] else 1.0)
        hp = holm(ps[1:]) if len(ps) > 1 else []
        for i, (m, dc, pooled, tc, tk, w, l_) in enumerate(rows):
            p = "" if i == 0 else f"{hp[i - 1]:.3g}"
            wl = "" if i == 0 else f"{w}/{l_}"
            print(f"| {m} | " + " | ".join(dc) + f" | {pooled} | " + " | ".join(tc) + f" | {tk:,.0f} | {wl} | {p} |")


if __name__ == "__main__":
    main()
