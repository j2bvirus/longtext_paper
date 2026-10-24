"""Lifecycle cost and break-even (no LLM calls).

Per condition: reader cost per question at list price computed from the method's own
input (ctx_tokens + reader system prompt) and output tokens, i.e. WITHOUT the constant
overhead of the CLI harness; plus memory build (write), idle (consolidation) and lazy
(profile cards) costs taken from the build caches.  Break-even against full re-reading:
Q* = build_total / (full_cost_per_q - method_cost_per_q), when positive.  When no full
re-reading run exists at a length (it does not fit the reader window), its per-question
cost is the counterfactual record_tokens + system prompt + question at list price plus
the mean output of the method itself ("full*").
Haiku 4.5 list price: $1 / M input, $5 / M output.

python methods/costs.py --data saga_v5_s4,saga_v5_s5 [--reader claude-claude-haiku-4-5-20251001]
Several datasets are pooled per (density, method): reader cost is averaged over all
questions, build costs are averaged per record.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIN, POUT = 1e-6, 5e-6
SYS_TOK = 180
B = "claude-claude-haiku-4-5-20251001"
NAME_RE = re.compile(r"^(?P<d>d[\d.]+|full)_(?P<m>.+?)_(?P<r>claude-.+?|ollama-.+?)_b(?P<b>\d+)(?P<tag>.*)$")
CARD_METHODS = ("mem-cmmc", "mem-cmm2c", "mem-cmm3c")


def dkey(d):
    return 1e9 if d == "full" else float(d[1:])


def build_costs(ddir, density, method):
    """USD of building the memory used by `method` at `density` (Haiku builder), per record."""
    out = {"write_usd": 0.0, "idle_usd": 0.0, "lazy_usd": 0.0, "n_cards": 0}
    if method.startswith("mem-cmm"):
        p = os.path.join(ddir, f"cmm_write_{density}_{B}.json")
        if os.path.exists(p):
            out["write_usd"] = json.load(open(p, encoding="utf-8"))["cost"]["usd"]
        p = os.path.join(ddir, f"cmm_idle3_{density}_{B}_cost.json")
        if os.path.exists(p):
            out["idle_usd"] = json.load(open(p, encoding="utf-8"))["usd"]
        else:
            out["idle_usd"] = float("nan")  # built before idle costs were logged per record
        if method in CARD_METHODS:
            cp = os.path.join(ddir, f"cmm_cards_{density}_{B}.json")
            if os.path.exists(cp):
                cs = json.load(open(cp, encoding="utf-8")).values()
                out["lazy_usd"] = sum(v["usd"] for v in cs)  # all cards built at this length (upper bound for gated cards)
                out["n_cards"] = len(cs)
    elif method in ("mem-summary",):
        for p in glob.glob(os.path.join(ddir, f"mem_summary_{density}_{B}_w*.json")):
            out["write_usd"] = json.load(open(p, encoding="utf-8"))["cost"]["usd"]
    elif method in ("mem-facts", "mem-ecm", "mem-ecm2", "mem-ecm2n", "mem-ecm2c"):
        p = os.path.join(ddir, f"mem_ecm2_{density}_{B}.json")
        if os.path.exists(p):
            out["write_usd"] = json.load(open(p, encoding="utf-8"))["cost"]["usd"]
    return out


def collect(data, reader):
    rows = []
    for ds in data:
        ddir = os.path.join(ROOT, "data", ds)
        qs = {json.loads(l)["qid"]: json.loads(l) for l in open(os.path.join(ddir, "questions_GOLD.jsonl"), encoding="utf-8")}
        for f in glob.glob(os.path.join(ROOT, "runs", "results", f"{ds}_*{reader}*.jsonl")):
            m = NAME_RE.match(os.path.basename(f)[len(ds) + 1:-6])
            if not m or m["b"] != "4000":
                continue
            # smoke tests, debugging and pilot runs, and the two variants dropped from the study
            if re.search(r"_(smoke|dbg|pilot\d+)$", m["tag"]) or m["m"] in ("mem-ngcc", "mem-qnotes"):
                continue
            recs = [json.loads(l) for l in open(f, encoding="utf-8")]
            recs = [r for r in recs if r["qid"] in qs and not qs[r["qid"]].get("excluded")]
            if not recs:
                continue
            sp = f[:-6] + ".summary.json"
            summ = json.load(open(sp)) if os.path.exists(sp) else {}
            rec_tok = summ.get("record_tokens")
            if rec_tok is None and os.path.exists(os.path.join(ddir, f"record_{m['d']}.txt")):
                rec_tok = core.ntok(open(os.path.join(ddir, f"record_{m['d']}.txt"), encoding="utf-8").read())
            rows.append({"ds": ds, "d": m["d"], "m": m["m"] + m["tag"], "recs": recs, "record_tokens": rec_tok,
                         **build_costs(ddir, m["d"], m["m"])})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="saga_v5_s1")
    ap.add_argument("--reader", default=B)
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()
    rows = collect(a.data.split(","), a.reader)
    grp = collections.defaultdict(list)
    for r in rows:
        grp[(r["d"], r["m"])].append(r)
    out = []
    for (d, m), rs in grp.items():
        recs = [x for r in rs for x in r["recs"]]
        n = len(recs)
        rq = sum((x["ctx_tokens"] + SYS_TOK) * PIN + x["out_tokens"] * POUT for x in recs) / n
        acc = sum(x["correct"] for x in recs) / n
        k = len(rs)
        rt = [r["record_tokens"] for r in rs if r["record_tokens"]]
        out.append({"d": d, "m": m, "n": n, "acc": acc, "ctx": sum(x["ctx_tokens"] for x in recs) / n,
                    "out": sum(x["out_tokens"] for x in recs) / n, "reader_usd_q": rq,
                    "write": sum(r["write_usd"] for r in rs) / k, "idle": sum(r["idle_usd"] for r in rs) / k,
                    "lazy": sum(r["lazy_usd"] for r in rs) / k, "cards": sum(r["n_cards"] for r in rs) / k,
                    "record_tokens": sum(rt) / len(rt) if rt else None, "worlds": k})
    full = {r["d"]: r for r in out if r["m"] in ("full", "full_s100")}
    hdr = ["len", "method", "n", "acc %", "ctx/q", "$read/q", "$write", "$idle", "$cards", "$build", "Q* vs full"]
    lines = []
    for r in sorted(out, key=lambda r: (dkey(r["d"]), r["m"])):
        build = r["write"] + r["idle"] + r["lazy"]
        if r["m"] in ("full", "full_s100"):
            q = "-"
        elif build != build:  # NaN: idle cost of this record was not logged (built before per-record logging)
            q = "n/a"
        else:
            if r["d"] in full:
                fq, star = full[r["d"]]["reader_usd_q"], ""
            elif r["record_tokens"]:
                fq, star = (r["record_tokens"] + SYS_TOK + 40) * PIN + r["out"] * POUT, "*"
            else:
                fq, star = None, ""
            if fq is None:
                q = "?"
            else:
                diff = fq - r["reader_usd_q"]
                q = (f"{build / diff:.1f}{star}" if build > 0 else f"0{star}") if diff > 0 else "never"
        lt = f"{r['record_tokens'] / 1000:,.0f}k" if r["record_tokens"] else r["d"]
        lines.append([f"{r['d']} ({lt})", r["m"], str(r["n"]), f"{100 * r['acc']:.1f}", f"{r['ctx']:,.0f}",
                      f"{r['reader_usd_q']:.4f}", f"{r['write']:.2f}", f"{r['idle']:.2f}", f"{r['lazy']:.2f}",
                      f"{build:.2f}", q])
    if a.markdown:
        print("| " + " | ".join(hdr) + " |")
        print("|" + "---|" * len(hdr))
        for l in lines:
            print("| " + " | ".join(l) + " |")
    else:
        w = [max(len(h), *(len(l[i]) for l in lines)) for i, h in enumerate(hdr)] if lines else [len(h) for h in hdr]
        print("  ".join(h.ljust(w[i]) for i, h in enumerate(hdr)))
        for l in lines:
            print("  ".join(x.ljust(w[i]) for i, x in enumerate(l)))
    print("\nQ* = questions after which the memory's total cost (build + reading) is below re-reading the whole record "
          "for every question; '*' = counterfactual full re-reading (does not fit the reader's window).")


if __name__ == "__main__":
    main()
