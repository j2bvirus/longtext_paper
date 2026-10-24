"""Replication with further readers (runs/agy_replication_pipeline.sh): report (no LLM calls).

Per task and reader, accuracy of each method pooled over the two worlds, and exact McNemar of the first method of
the task against each other method, Holm-corrected within reader and task (the analysis fixed in the pipeline).
  event index   G2 counting, fresh worlds 11-12 (agg2_s11, agg2_s12): evx4v5 vs oracle_para, cmm4, pbm25, hybrid
  state         worlds 7-8 at about 0.5M tokens (saga_v5_s7, saga_v5_s8): cmm4 vs pbm25, hybrid
  continuity    worlds 7-8 (cont2_s7, cont2_s8): cmm4 vs pbm25, hybrid; pair accuracy (both members right), J, and
                McNemar on pairs; label errors dropped as in methods/continuity_stats.py
Readers: Haiku 4.5 and GPT-6.1-sol (earlier runs) and the replication readers Gemini 4 Argon (low) and GPT-OSS 120B
(medium).  Only questions answered under every method of a task for that reader are compared; n is printed.

python methods/agy_replication_report.py
"""
import json
import os
import sys
from collections import defaultdict
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
sys.path.insert(0, os.path.join(ROOT, "methods"))
READERS = [("Haiku 4.5", "claude-claude-haiku-4-5-20251001"), ("GPT-6.1-sol", "codex-gpt-6.1-sol"),
           ("Gemini 4 Argon", "agy-gemini-4-argon-low"), ("GPT-OSS 120B", "agy-gpt-oss-120b-medium")]
TASKS = [("Event-type index, G2 counting, fresh worlds 11-12", ["agg2_s11", "agg2_s12"],
          ["mem-evx4v5", "oracle_para", "mem-cmm4", "mem-pbm25", "hybrid"], False),
         ("State tracking, worlds 7-8, about 0.5M tokens", ["saga_v5_s7", "saga_v5_s8"],
          ["mem-cmm4", "mem-pbm25", "hybrid"], False),
         ("Continuity checking, worlds 7-8 (pairs)", ["cont2_s7", "cont2_s8"], ["mem-cmm4", "mem-pbm25", "hybrid"], True)]


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


def load(ds, m, r):
    f = os.path.join(ROOT, "runs", "results", f"{ds}_d16_{m}_{r}_b4000.jsonl")
    if not os.path.exists(f):
        return {}
    out = {}
    for l in open(f, encoding="utf-8"):
        x = json.loads(l)
        out.setdefault(x["qid"], x)  # first record of a question (a second runner may have appended a duplicate)
    return out


def main():
    import check_continuity_labels
    from continuity_stats import says_contradiction
    for title, dss, methods, paired in TASKS:
        print(f"\n### {title}\n")
        print("| Reader | n | " + " | ".join(methods) + " | " + " | ".join(f"{methods[0]} vs {m}: w/l, p (Holm)"
                                                                  for m in methods[1:]) + " |")
        print("|---|---|" + "---|" * (2 * len(methods) - 1))
        for rname, r in READERS:
            units = defaultdict(dict)  # method -> unit -> correct (question, or pair when paired)
            j = {}
            for m in methods:
                recs_all = []
                for ds in dss:
                    d = load(ds, m, r)
                    if paired:
                        gold = {json.loads(l)["qid"]: json.loads(l) for l in
                                open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"), encoding="utf-8")}
                        bad = {b[0] for b in check_continuity_labels.check(ds)[0]}
                        by = defaultdict(list)
                        for qid, x in d.items():
                            if qid in gold and qid not in bad:
                                by[gold[qid]["pair"]].append(x)
                        for p, xs in by.items():
                            if len(xs) == 2:
                                units[m][(ds, p)] = int(all(x["correct"] for x in xs))
                                recs_all += xs
                    else:
                        for qid, x in d.items():
                            units[m][(ds, qid)] = int(x["correct"])
                if paired and recs_all:
                    pos = [x for x in recs_all if x["gold"] == "contradiction"]
                    neg = [x for x in recs_all if x["gold"] == "consistent"]
                    j[m] = 100 * (sum(says_contradiction(x["pred"]) for x in pos) / max(1, len(pos)) -
                                  sum(says_contradiction(x["pred"]) for x in neg) / max(1, len(neg)))
            common = set.intersection(*[set(units[m]) for m in methods]) if all(units[m] for m in methods) else set()
            if not common:
                have = ", ".join(f"{m} {len(units[m])}" for m in methods)
                print(f"| {rname} | – | (incomplete: {have}) |")
                continue
            accs = [f"{100 * sum(units[m][k] for k in common) / len(common):.1f}" +
                    (f" (J {j[m]:.1f})" if paired and m in j else "") for m in methods]
            wl, ps = [], []
            for m in methods[1:]:
                w = sum(1 for k in common if units[methods[0]][k] and not units[m][k])
                l_ = sum(1 for k in common if units[m][k] and not units[methods[0]][k])
                wl.append((w, l_))
                ps.append(mcnemar(w, l_))
            hp = holm(ps)
            tests = [f"{w}/{l_}, {p:.2g}" for (w, l_), p in zip(wl, hp)]
            print(f"| {rname} | {len(common)} | " + " | ".join(accs) + " | " + " | ".join(tests) + " |")
        print("\nAccuracy in % over the questions (pairs for continuity) answered under every method of the task by "
              "that reader; continuity cells are pair accuracy with J = TPR - FPR in brackets.")


if __name__ == "__main__":
    main()
