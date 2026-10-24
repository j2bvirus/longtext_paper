"""Additional statistics (no LLM calls).

python methods/review_stats.py saga  --data saga_v5_s4,saga_v5_s5 --density d16 --ref mem-cmm2c \
       --methods hybrid,mem-pbm25,mem-namegrep_co,mem-cmm2l,mem-cmm2 [--readers ...]
    per-world accuracy, paired McNemar vs the reference with Holm correction over every test printed,
    and cluster-bootstrap 95% CIs (clusters = (world, question subject)) for accuracy and paired difference.
python methods/review_stats.py certsplit --data saga_v5_s4,saga_v5_s5 --density d16 --cert mem-cmm2 \
       --methods mem-pbm25,hybrid,mem-namegrep_co,mem-cmm2,oracle_para
    accuracy of every method split by whether the CMM context for that question carried a guarantee
    (is the certified/uncertified gap a property of the questions or of the statement?).
python methods/review_stats.py novels --data nhq_mid,nhq_karam,nhq_pride
    judged accuracy overall and restricted to questions the closed-book reader got wrong.
"""
import argparse
import collections
import json
import os
import random
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READERS = {"claude-claude-haiku-4-5-20251001": "Haiku", "ollama-qwen3-8b": "Qwen3-8B", "ollama-qwen3-14b": "Qwen3-14B"}


def mcnemar(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        adj[i] = run
    return adj


def load_saga(ds, d, m, rd):
    f = os.path.join(ROOT, "runs", "results", f"{ds}_{d}_{m}_{rd}_b4000.jsonl")
    if not os.path.exists(f):
        return None
    qs = {json.loads(l)["qid"]: json.loads(l) for l in open(os.path.join(ROOT, "data", ds, "questions_GOLD.jsonl"), encoding="utf-8")}
    out = {}
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        q = qs[r["qid"]]
        if q.get("excluded"):
            continue
        out[(ds, r["qid"])] = {"c": r["correct"], "cert": r.get("certified"), "subj": (ds, q.get("subject", r["qid"])),
                               "qtype": q["qtype"]}
    return out


def cluster_boot(keys, val, subj, n=2000, seed=0):
    """95% CI of mean(val) resampling clusters of keys sharing a subject."""
    cl = collections.defaultdict(list)
    for k in keys:
        cl[subj[k]].append(k)
    cls = list(cl.values())
    r = random.Random(seed)
    stats = []
    for _ in range(n):
        tot = cnt = 0
        for _ in range(len(cls)):
            g = cls[r.randrange(len(cls))]
            tot += sum(val[k] for k in g)
            cnt += len(g)
        stats.append(tot / cnt)
    stats.sort()
    return stats[int(0.025 * n)], stats[int(0.975 * n) - 1]


def saga(a):
    data = a.data.split(",")
    tests, blocks = [], []
    for rd in a.readers.split(","):
        ref = {}
        for ds in data:
            x = load_saga(ds, a.density, a.ref, rd)
            if x:
                ref.update(x)
        if not ref:
            continue
        subj = {k: v["subj"] for k, v in ref.items()}
        rows = []
        for m in [a.ref] + a.methods.split(","):
            per, pooled = [], {}
            for ds in data:
                x = load_saga(ds, a.density, m, rd)
                if x:
                    pooled.update(x)
                    per.append(f"{100 * sum(v['c'] for v in x.values()) / len(x):.1f}")
                else:
                    per.append("–")
            ks = [k for k in pooled if k in ref]
            if not ks:
                continue
            acc = {k: pooled[k]["c"] for k in ks}
            lo, hi = cluster_boot(ks, acc, subj)
            accs = f"{100 * sum(acc.values()) / len(ks):.1f} [{100 * lo:.0f},{100 * hi:.0f}]"
            if m == a.ref:
                rows.append((m, per, accs, "", "", None))
                continue
            dif = {k: ref[k]["c"] - pooled[k]["c"] for k in ks}
            dlo, dhi = cluster_boot(ks, dif, subj)
            w = sum(1 for k in ks if ref[k]["c"] and not pooled[k]["c"])
            l = sum(1 for k in ks if pooled[k]["c"] and not ref[k]["c"])
            tests.append(mcnemar(w, l))
            rows.append((m, per, accs, f"{100 * sum(dif.values()) / len(ks):+.1f} [{100 * dlo:+.0f},{100 * dhi:+.0f}]",
                         f"{w}/{l}", len(tests) - 1))
        blocks.append((READERS.get(rd, rd), rows))
    adj = holm(tests) if tests else []
    for rn, rows in blocks:
        print()
        print(f"### {rn}, {a.density}, reference {a.ref} (n per world, pooled CI by subject clusters)")
        hdr = "| method | " + " | ".join(data) + " | pooled [95% CI] | ref minus method [95% CI] | ref wins/losses | p | p Holm |"
        print(hdr)
        print("|" + "---|" * (hdr.count("|") - 1))
        for m, per, accs, difs, wl, ti in rows:
            p = f"{tests[ti]:.2g}" if ti is not None else ""
            pa = f"{adj[ti]:.2g}" if ti is not None else ""
            print(f"| {m} | " + " | ".join(per) + f" | {accs} | {difs} | {wl} | {p} | {pa} |")
    print()
    print(f"Holm correction over all {len(tests)} paired tests printed above.")


def certsplit(a):
    data = a.data.split(",")
    for rd in a.readers.split(","):
        cert = {}
        for ds in data:
            x = load_saga(ds, a.density, a.cert, rd) or load_saga(ds, a.density, a.cert, "claude-claude-haiku-4-5-20251001")
            if x:
                cert.update({k: bool(v["cert"]) for k, v in x.items()})
        if not cert:
            continue
        print(f"\n### {READERS.get(rd, rd)}, {a.density}: accuracy split by the guarantee flag of {a.cert} on the same question")
        print("| method | certified (n) | not certified (n) | gap |")
        print("|---|---|---|---|")
        for m in a.methods.split(","):
            res = {}
            for ds in data:
                x = load_saga(ds, a.density, m, rd)
                if x:
                    res.update(x)
            if not res:
                continue
            c1 = [v["c"] for k, v in res.items() if cert.get(k) is True]
            c0 = [v["c"] for k, v in res.items() if cert.get(k) is False]
            if c1 and c0:
                print(f"| {m} | {100 * sum(c1) / len(c1):.1f} ({len(c1)}) | {100 * sum(c0) / len(c0):.1f} ({len(c0)}) | "
                      f"{100 * (sum(c1) / len(c1) - sum(c0) / len(c0)):+.1f} |")


def novels(a):
    data = a.data.split(",")
    for rd in a.readers.split(","):
        def load(m):
            out = {}
            for ds in data:
                f = os.path.join(ROOT, "runs", "judged", f"{ds}_full_{m}_{rd}_b4000.json")
                if not os.path.exists(f):
                    return None
                out.update({(ds, k): v for k, v in json.load(open(f)).items()})
            return out
        cb = load("closedbook") or load_cb_haiku(data)
        if not cb:
            continue
        print(f"\n### {READERS.get(rd, rd)}: judged accuracy, all questions vs questions the closed-book reader got wrong")
        print("| method | all (n) | closed-book wrong (n) |")
        print("|---|---|---|")
        for m in a.methods.split(","):
            x = load(m)
            if not x:
                continue
            hard = [v for k, v in x.items() if cb.get(k) == 0]
            print(f"| {m} | {100 * sum(x.values()) / len(x):.1f} ({len(x)}) | {100 * sum(hard) / max(1, len(hard)):.1f} ({len(hard)}) |")


def load_cb_haiku(data):
    out = {}
    for ds in data:
        f = os.path.join(ROOT, "runs", "judged", f"{ds}_full_closedbook_claude-claude-haiku-4-5-20251001_b4000.json")
        if not os.path.exists(f):
            return None
        out.update({(ds, k): v for k, v in json.load(open(f)).items()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["saga", "certsplit", "novels"])
    ap.add_argument("--data", required=True)
    ap.add_argument("--density", default="d16")
    ap.add_argument("--ref", default="mem-cmm2c")
    ap.add_argument("--cert", default="mem-cmm2")
    ap.add_argument("--methods", default="hybrid,mem-pbm25,mem-namegrep_co,mem-cmm2l,mem-cmm2,oracle_para")
    ap.add_argument("--readers", default=",".join(READERS))
    a = ap.parse_args()
    {"saga": saga, "certsplit": certsplit, "novels": novels}[a.mode](a)


if __name__ == "__main__":
    main()
