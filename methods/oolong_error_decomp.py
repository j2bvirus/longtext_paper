"""Error decomposition of the Oolong transcript index (no model calls).

For the question templates whose answer is a deterministic function of the event tables (counts of rolls or spells in
total, per character or player, per roll type or natural value, cumulative up to an episode, and the first, second or
third spell of an episode), three scores are computed per question with the official scorer:
  S_e  the tables' own answer over the episode range the question asks for  (extraction and representation only)
  S_r  the tables' own answer over the range the routing call chose         (+ routing)
  S    the reader's actual answer                                            (+ reading)
so that 1 - S_e is the shortfall of the tables themselves (missed, wrong or misattributed events, split names, field
  mismatches, gold tallies that differ from the transcripts; not separated), S_e - S_r the net change by routing and S_r - S
in reading.  Representation is also measured directly: the share of indexed rolls and spells whose filled character is
not one of the window's characters (the header's player-character map).  Only cached Haiku-built tables are read.

python methods/oolong_error_decomp.py [--split test] [--reader claude-claude-haiku-4-5-20251001]
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oolong_eval as oe  # noqa: E402
import oolong_index as oi  # noqa: E402
import oolong_score  # noqa: E402

BUILDER = "claude-claude-haiku-4-5-20251001"
ORD = {"first": 1, "second": 2, "third": 3}


def tables_of(split, wid):
    text, pmap, eps = oe.window_episodes(split, wid)
    out = []
    for ep in eps:
        p = os.path.join(oi.CACHE, f"ep_{oi.ep_key(ep)}_v2_{BUILDER}.json")
        if not os.path.exists(p):
            return None, pmap
        out.append(json.load(open(p, encoding="utf-8")))
    return out, pmap


def parse(q, n):
    """(kind, episodes 1-based, selector, value) or None for templates not handled"""
    s = q.replace("cummulative", "cumulative")
    allep = list(range(1, n + 1))
    m = re.search(r"cumulative total of (rolls|spells cast) by the character (.+?) at the end of episode (\d+)", s)
    if m:
        return ("rolls" if m.group(1) == "rolls" else "spells", list(range(1, int(m.group(3)) + 1)), "character", m.group(2))
    m = re.search(r"cumulative total of (rolls|spells cast) by the end of episode (\d+)", s)
    if m:
        return ("rolls" if m.group(1) == "rolls" else "spells", list(range(1, int(m.group(2)) + 1)), "total", None)
    m = re.search(r"What is the (first|second|third) spell cast in the episode (\d+)", s)
    if m:
        return ("spells", [int(m.group(2))], "nth", ORD[m.group(1)])
    scope_all = re.search(r"across all( the)? episodes|in this episode|all episodes|during this episode", s)
    if not scope_all:
        return None
    m = re.search(r"Total number of rolls by the (character|player) (.+?) (?:across|in this)", s)
    if m:
        return ("rolls", allep, m.group(1), m.group(2))
    m = re.search(r"How many spells were cast by the (character|player) (.+?) (?:across|in this)", s)
    if m:
        return ("spells", allep, m.group(1), m.group(2))
    if re.search(r"How many spells were cast (across all episodes|during this episode)", s):
        return ("spells", allep, "total", None)
    if re.search(r"Total number of rolls (across all( the)? episodes|in this episode)", s):
        return ("rolls", allep, "total", None)
    m = re.search(r"Number of rolls of natural value (\d+)", s)
    if m:
        return ("rolls", allep, "natural", {m.group(1)})
    if "Nat20s" in s:
        return ("rolls", allep, "natural", {"20"})
    if "Nat1s" in s:
        return ("rolls", allep, "natural", {"1"})
    if "count of Crits" in s:
        return ("rolls", allep, "natural", {"1", "20"})
    m = re.search(r"Total number of rolls of type (.+?) (?:across )?(?:all episodes|in this episode)", s)
    if m:
        return ("rolls", allep, "type", m.group(1).strip())
    return None


def same(a, b):
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or a.split()[0] == b.split()[0]


def canon(name, mapped):
    """post-hoc representation fix (not part of the frozen method): a short name that begins a mapped character's
    name ('Vax' for "Vax'ildan", 'Vex' for "Vex'ahlia") is merged into that character"""
    n = name.strip().lower()
    for m in mapped:
        ml = m.lower()
        if n == ml or (len(n) >= 3 and (ml.startswith(n + "'") or ml.split()[0] == n or ml.startswith(n))):
            return m
    return name


def answer(tables, kind, eps, sel, val, mapped=None):
    rows = [(e, x) for e in eps if 1 <= e <= len(tables) for x in tables[e - 1][kind]]
    if mapped is not None:
        rows = [(e, dict(x, character_filled=canon(x["character_filled"], mapped))) for e, x in rows]
    if sel == "total":
        return str(len(rows))
    if sel == "character":
        return str(sum(1 for _, x in rows if same(x["character_filled"], val)))
    if sel == "player":
        return str(sum(1 for _, x in rows if same(x["player"], val)))
    if sel == "natural":
        return str(sum(1 for _, x in rows if x["natural"] in val))
    if sel == "type":
        return str(sum(1 for _, x in rows if x["type"].strip().lower() == val.lower()))
    if sel == "nth":
        sp = [x["spell"] for _, x in rows]
        return sp[val - 1] if len(sp) >= val else "none"
    raise ValueError(sel)


def score(gold, ans):
    return oolong_score.score(gold, "\\boxed{" + ans + "}")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--reader", default="claude-claude-haiku-4-5-20251001")
    a = ap.parse_args()
    recs = [json.loads(l) for l in open(os.path.join(oe.OUT, f"{a.split}_index_{a.reader}.jsonl"), encoding="utf-8")]
    for r in recs:  # official score recomputed from the stored reply, not the stored score
        r["score"] = oolong_score.score(r["answer"], r.get("raw") or "")[0]
    byw = defaultdict(list)
    for r in recs:
        byw[r["window"]].append(r)
    rows, rep, skipped = [], Counter(), Counter()
    for wid, rs in byw.items():
        tables, pmap = tables_of(a.split, wid)
        if tables is None:
            skipped["no cached table"] += len(rs)
            continue
        chars = {c.lower() for c in pmap.values()}
        for t in tables:
            for kind in ("rolls", "spells"):
                for x in t[kind]:
                    rep[(kind, "in map" if x["character_filled"].lower() in chars else "not in map")] += 1
        n = len(tables)
        for r in rs:
            p = parse(r["question"], n)
            if p is None:
                skipped["template not handled"] += 1
                continue
            kind, eps, sel, val = p
            rk, rscope, rkk = r.get("route", [kind, "all", None])
            reps = ([rkk] if rscope == "episode" else list(range(1, (rkk or n) + 1)) if rscope == "upto"
                    else list(range(1, n + 1)))
            s_e = score(r["answer"], answer(tables, kind, eps, sel, val))
            s_r = score(r["answer"], answer(tables, rk if rk in ("rolls", "spells") else kind, reps, sel, val))
            route_ok = (rk == kind) and sorted(set(reps)) == sorted(set(eps))
            s_a = score(r["answer"], answer(tables, kind, eps, sel, val, mapped=list(pmap.values())))
            rows.append({"n": n, "sel": sel, "s_e": s_e, "s_r": s_r, "s": r["score"], "route_ok": route_ok, "s_a": s_a,
                         "id": r["id"]})
    print(f"{a.split}, reader {a.reader}: {len(rows)} questions decomposed; skipped {dict(skipped)}")

    def summ(rr, label):
        k = len(rr)
        if not k:
            return
        e = sum(x["s_e"] for x in rr) / k
        rt = sum(x["s_r"] for x in rr) / k
        s = sum(x["s"] for x in rr) / k
        ok = sum(x["route_ok"] for x in rr) / k
        al = sum(x["s_a"] for x in rr) / k
        print(f"| {label} | {k} | {ok:.3f} | {e:.3f} | {rt:.3f} | {s:.3f} | {1 - e:.3f} | {e - rt:+.3f} | {rt - s:+.3f} | {al:.3f} |")
    print("\n| subset | questions | routing correct | tables, right range (S_e) | tables, chosen range (S_r) | reader (S) | "
          "shortfall of the tables (1 - S_e) | net loss by routing (S_e - S_r) | net loss by reading (S_r - S) | tables, right range, short names merged (post hoc) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    summ(rows, "all handled")
    for lab, f in (("1 episode", lambda x: x["n"] == 1), ("2-10 episodes", lambda x: 2 <= x["n"] <= 10),
                   ("16-24 episodes", lambda x: x["n"] >= 16)):
        summ([x for x in rows if f(x)], lab)
    for sel in sorted({x["sel"] for x in rows}):
        summ([x for x in rows if x["sel"] == sel], f"selector: {sel}")
    # per question: a small mean difference can hide gains and losses that cancel
    print("\nPer-question changes between stages (score difference beyond 1e-9):")
    print("| step | worse | better | unchanged | mean loss among worse | mean gain among better |")
    print("|---|---|---|---|---|---|")
    for lab, a_, b_ in (("routing (S_e -> S_r)", "s_e", "s_r"), ("reading (S_r -> S)", "s_r", "s"),
                        ("routing and reading (S_e -> S)", "s_e", "s")):
        d = [x[b_] - x[a_] for x in rows]
        wo, be = [v for v in d if v < -1e-9], [v for v in d if v > 1e-9]
        print(f"| {lab} | {len(wo)} | {len(be)} | {len(d) - len(wo) - len(be)} | "
              f"{-sum(wo) / max(1, len(wo)):.3f} | {sum(be) / max(1, len(be)):.3f} |")
    print(f"Questions whose tables' own answer is already exact (S_e = 1): {sum(1 for x in rows if x['s_e'] >= 1 - 1e-9)}"
          f" of {len(rows)}; questions not handled by the templates: {sum(skipped.values())}")
    # the tables' own answer as a baseline, against BM25 on the same questions and on the rest
    bm = {}
    bf = os.path.join(oe.OUT, f"{a.split}_bm25_{a.reader}.jsonl")
    if os.path.exists(bf):
        for l in open(bf, encoding="utf-8"):
            x = json.loads(l)
            bm.setdefault(x["id"], oolong_score.score(x["answer"], x.get("raw") or "")[0])
        ids = {x["id"] for x in rows}
        hb = [bm[i] for i in ids if i in bm]
        rest = [(r["score"], bm[r["id"]]) for r in recs if r["id"] not in ids and r["id"] in bm]
        print()
        print(f"Same {len(hb)} handled questions: tables' own answer {sum(x['s_e'] for x in rows) / len(rows):.3f}, "
              f"index reader {sum(x['s'] for x in rows) / len(rows):.3f}, BM25 reader {sum(hb) / max(1, len(hb)):.3f}.")
        if rest:
            print(f"The other {len(rest)} questions (templates not handled): index reader "
                  f"{sum(s for s, _ in rest) / len(rest):.3f}, BM25 reader {sum(b for _, b in rest) / len(rest):.3f}.")
    tot = defaultdict(int)
    for (kind, st), v in rep.items():
        tot[kind] += v
    print("\nRepresentation: indexed events whose filled character is not one of the window's characters:")
    for kind in ("rolls", "spells"):
        print(f"- {kind}: {rep[(kind, 'not in map')]} of {tot[kind]} ({rep[(kind, 'not in map')] / max(1, tot[kind]):.1%}),"
              " counted per window (episodes shared by windows count again)")


if __name__ == "__main__":
    main()
