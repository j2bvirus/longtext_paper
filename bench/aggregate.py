"""LongState-Aggregate: counting, enumeration and ordering questions with exact gold.

Memory methods are weak on counting and enumeration, and the LongState-Saga questions are almost all
single-fact questions.  This generator writes aggregation questions for a
saga world and reuses its record, spans and built memories (copies only, like bench/continuity_pairs.py).

Entity-anchored (one named subject; a complete per-entity index should help):
  A_NCHILD   how many children X had over the whole record (family introduction + births)
  A_HOMES    every place X lived, in order (residence history; v5.2 residence exclusions apply)
  A_NMARRY   how many times X married (couples introduced as married count once)
  A_HOLDERS  everyone who held an object, in order (objects that pass by an inheritance rule are skipped)
  A_ORDER    which of two people died first
Global (no named subject, or a place / a chapter range):
  G_NDEATHS, G_NWED, G_NBIRTHS          totals over the record (weddings: chapter > 1; rumoured deaths do not count)
  G_PLACE_DEATHS, G_PLACE_BIRTHS        per place
  G_RANGE_DEATHS, G_RANGE_WED           per chapter range
Answer kinds: 'count' (one integer) and 'olist' (names in order); scored in methods/core.py.

python bench/aggregate.py --src saga_v5_s7 --out agg_s7 --density d16 --seed 71
"""
import argparse
import glob
import json
import os
import random
import shutil
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUM = " Answer with a single number."
LST = " Answer with the names in order, separated by commas."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--density", default="d16")
    ap.add_argument("--seed", type=int, default=71)
    a = ap.parse_args()
    src, out = os.path.join(ROOT, "data", a.src), os.path.join(ROOT, "data", a.out)
    w = json.load(open(os.path.join(src, "world_GOLD.json"), encoding="utf-8"))
    ev = json.load(open(os.path.join(src, "events_GOLD.json"), encoding="utf-8"))
    rng = random.Random(a.seed)
    P = w["persons"]
    place = {p["id"]: p["name"] for p in w["places"]}
    item = {i["id"]: i["name"] for i in w["items"]}

    def name(pid):
        return f"{P[pid]['first']} {P[pid]['surname']}"
    excl = {}
    for line in open(os.path.join(src, "questions_GOLD.jsonl"), encoding="utf-8"):
        q = json.loads(line)
        if q.get("excluded") and q.get("subject"):
            excl.setdefault({"LOC_NOW": "LOC", "LOC_AT_EVENT": "LOC", "EVER_VISITED": "LOC"}.get(q["qtype"], q["qtype"]),
                            set()).add(q["subject"])
    qs = []
    person_vocab = sorted(name(p) for p in P)
    place_vocab = sorted(place.values())

    def add(qt, subj, question, gold, kind, evid, vocab=None):
        ans = {"kind": kind, "gold": gold, "aliases": [str(gold)] if kind == "count" else [", ".join(gold)]}
        if vocab is not None:
            ans["vocab"] = vocab
        qs.append({"qtype": qt, "subject": subj, "question": question, "answer": ans,
                   "evidence": sorted(set(evid)), "evidence_core": sorted(set(evid))})
    # ---- entity-anchored
    kids, kid_ev = {}, {}
    for e in ev:
        if e["type"] == "INIT_FAMILY":
            for par in (e.get("father"), e.get("mother")):
                if par:
                    kids.setdefault(par, set()).update(e.get("children") or [])
                    kid_ev.setdefault(par, []).append(e["id"])
        elif e["type"] == "BIRTH":
            for par in (e.get("father"), e.get("mother")):
                if par:
                    kids.setdefault(par, set()).add(e["child"])
                    kid_ev.setdefault(par, []).append(e["id"])
    adults = [p for p in P if P[p].get("adult", True)]
    with_k = sorted(p for p in adults if kids.get(p))
    without = sorted(p for p in adults if not kids.get(p))
    for pid in rng.sample(with_k, min(10, len(with_k))) + rng.sample(without, min(2, len(without))):
        add("A_NCHILD", pid, f"Over the whole record, how many children did {name(pid)} have in total (count every "
            f"child, including any who died)?" + NUM, len(kids.get(pid, ())), "count", kid_ev.get(pid, []))
    res = {}  # residence history: family introduction, birth, travel, and marriage ("the couple lived in X from then on")
    for e in sorted(ev, key=lambda e: (e["chapter"], e["id"])):
        if e["type"] == "INIT_FAMILY":
            for c in [e["father"], e["mother"]] + list(e.get("children", [])):
                if c:
                    res.setdefault(c, []).append((e["id"], e["place"]))
        elif e["type"] == "BIRTH":
            res.setdefault(e["child"], []).append((e["id"], e["place"]))
        elif e["type"] == "TRAVEL":
            res.setdefault(e["person"], []).append((e["id"], e["dest"]))
        elif e["type"] == "MARRY" and e.get("place"):
            for x in (e["a"], e["b"]):
                res.setdefault(x, []).append((e["id"], e["place"]))

    def seq(h):
        s = []
        for _, l in h:
            if not s or s[-1] != l:
                s.append(l)
        return s
    F = w["final"]  # the history must end where the world's end state puts the person (living people only)
    movers = sorted(p for p in adults if p in res and p not in excl.get("LOC", set()) and 2 <= len(seq(res[p])) <= 5
                    and F["alive"].get(p) and F["loc"].get(p) == seq(res[p])[-1])
    for pid in rng.sample(movers, min(12, len(movers))):
        add("A_HOMES", pid, f"List every place where {name(pid)} lived during the record, in order, starting with the "
            f"first." + LST, [place[l] for l in seq(res[pid])], "olist", [i for i, _ in res[pid]], place_vocab)
    nmar, mar_ev = Counter(), {}
    for e in ev:
        if e["type"] == "MARRY":
            for x in (e["a"], e["b"]):
                nmar[x] += 1
                mar_ev.setdefault(x, []).append(e["id"])
        elif e["type"] == "INIT_FAMILY" and e.get("father") and e.get("mother"):
            for x in (e["father"], e["mother"]):
                nmar[x] += 1
                mar_ev.setdefault(x, []).append(e["id"])
    multi = sorted(p for p in nmar if nmar[p] >= 2)
    once = sorted(p for p in nmar if nmar[p] == 1)
    pick = rng.sample(multi, min(4, len(multi)))
    pick += rng.sample(once, min(8 - len(pick), len(once)))
    for pid in pick:
        add("A_NMARRY", pid, f"Over the whole record, how many times did {name(pid)} marry (count a couple who are "
            f"introduced as already married as one marriage)?" + NUM, nmar[pid], "count", mar_ev[pid])
    heir_items = {e["item"] for e in ev if e["type"] == "RULE_HEIR"}
    hold = []
    for iid in item:
        if iid in heir_items:
            continue
        h = [e for e in ev if e.get("item") == iid and e["type"] in ("INIT_ITEM", "GIVE")]
        names = []
        for e in h:
            x = e.get("owner") or e.get("dest")
            if x and (not names or names[-1] != x):
                names.append(x)
        if len(names) >= 2:
            hold.append((iid, names, [e["id"] for e in h]))
    for iid, names, ids in rng.sample(hold, min(8, len(hold))):
        add("A_HOLDERS", iid, f"List everyone who held {item[iid]} during the record, in order, starting with its "
            f"first owner." + LST, [name(x) for x in names], "olist", ids, person_vocab)
    deaths = [e for e in ev if e["type"] == "DEATH"]
    pairs = [(x, y) for i, x in enumerate(deaths) for y in deaths[i + 1:] if x["chapter"] != y["chapter"]]
    for x, y in rng.sample(pairs, min(10, len(pairs))):
        first = x if x["chapter"] < y["chapter"] else y
        aa, bb = (x, y) if rng.random() < 0.5 else (y, x)
        add("A_ORDER", aa["person"], f"Who died first, {name(aa['person'])} or {name(bb['person'])}?",
            name(first["person"]), "person", [x["id"], y["id"]])
        qs[-1]["answer"]["aliases"] = [name(first["person"])]
    # ---- global
    weds = [e for e in ev if e["type"] == "MARRY" and e["chapter"] > 1]
    births = [e for e in ev if e["type"] == "BIRTH"]
    add("G_NDEATHS", "GLOBAL", "How many people died during the record? Count only deaths the record reports as "
        "having happened, not rumours." + NUM, len(deaths), "count", [e["id"] for e in deaths])
    add("G_NWED", "GLOBAL", "How many weddings took place during the record? Do not count couples who were already "
        "married when the record begins." + NUM, len(weds), "count", [e["id"] for e in weds])
    add("G_NBIRTHS", "GLOBAL", "How many children were born during the record (not counting children who were "
        "already alive when the record begins)?" + NUM, len(births), "count", [e["id"] for e in births])
    dpl, bpl = Counter(e["place"] for e in deaths), Counter(e["place"] for e in births)
    for cnt, what, qt, evs in ((dpl, "died or were buried", "G_PLACE_DEATHS", deaths),
                               (bpl, "were born", "G_PLACE_BIRTHS", births)):
        hit = sorted(l for l in cnt)
        zero = sorted(l for l in place if l not in cnt)
        for l in rng.sample(hit, min(4, len(hit))) + rng.sample(zero, min(2, len(zero))):
            add(qt, l, f"During the record, how many people {what} at {place[l]}?" + NUM, cnt.get(l, 0), "count",
                [e["id"] for e in evs if e["place"] == l])
    last = max(e["chapter"] for e in ev)
    for evs, what, qt in ((deaths, "How many people died", "G_RANGE_DEATHS"),
                          (weds, "How many weddings took place", "G_RANGE_WED")):
        for _ in range(4):
            c0 = rng.randint(2, max(2, last - 10))
            c1 = c0 + 9
            n = [e for e in evs if c0 <= e["chapter"] <= c1]
            add(qt, f"CH{c0}-{c1}", f"{what} between Chapter {c0} and Chapter {c1} (both chapters included)?" + NUM,
                len(n), "count", [e["id"] for e in n])
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
        for k, q in enumerate(qs):
            f.write(json.dumps(dict(qid=f"G{k:04d}", **q), ensure_ascii=False) + "\n")
    pats = [f"record_{a.density}.txt", f"spans_{a.density}_GOLD.json", "world_GOLD.json", "events_GOLD.json",
            f"cmm_write_{a.density}_*", f"cmm_idle3_{a.density}_*", f"cmm_cards_{a.density}_*", f"emb_{a.density}_c300.npy",
            f"ledger_write_{a.density}_*", f"compact_*_{a.density}_*", f"ng_cards_{a.density}_*", f"cmm_audit_{a.density}_*"]
    for pat in pats:
        for fpath in glob.glob(os.path.join(src, pat)):
            if not fpath.endswith(".lock") and not os.path.exists(fpath + ".lock"):
                shutil.copy2(fpath, os.path.join(out, os.path.basename(fpath)))
    print(a.out, len(qs), "questions", dict(Counter(q["qtype"] for q in qs)))


if __name__ == "__main__":
    main()
