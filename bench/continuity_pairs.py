"""LongState-Continuity, minimal-pair version (test sets).

Paired items control for the prior plausibility of a
sentence and for a reader's response bias, so a reader that answers from the sentence alone scores 50% per item
and 0% per pair.

Every item comes in a pair that shares the sentence template and, wherever the type allows, the subject.  One
member is consistent with the end state of the record, the other contradicts it (STALE: a value that was true
earlier and has since changed; NEVER: a value that was never true).
  LOC, SPOUSE, TRADE, KIN   same person, current value vs a former or never-true value
  HOLDER                    same object, current holder vs a former or never holder
  KNOWS                     same secret and listener, a person who knows it vs one who never learned it
  ALIVE                     same sentence, a living person vs a dead one (the subject cannot be shared)
Scoring: per item (accuracy; TPR and FPR of 'contradiction'; J = TPR - FPR) and per pair (both members right).
A pair whose paragraphs repeat an earlier one is rejected and drawn again (up to 30 draws per wanted pair).

Differences from the dev generator bench/continuity.py (left unchanged; dev sets cont_s4/cont_s5 keep its format):
pairing, and two label fixes found while writing this file: the grandmother of a KIN item and the listener of a
KNOWS item must be alive at the end of the record ("visited his grandmother and stayed for supper" is not
consistent when she has died; bench/continuity.py did not check this, 7 and 8 dev items are affected).

The new dataset directory reuses the source world's record, spans and already built memories (copies only):
python bench/continuity_pairs.py --src saga_v5_s7 --out cont2_s7 --density d16 --seed 47
"""
import argparse
import glob
import json
import os
import random
import shutil
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASK = ("A writer continuing this record drafts the following paragraph to append at its end:\n\"{p}\"\n"
       "Is this paragraph consistent with what the record establishes as of its end? Answer exactly "
       "'consistent' or 'contradiction'.")
N_PAIRS = {"ALIVE": 20, "LOC": 25, "SPOUSE": 20, "HOLDER": 15, "TRADE": 20, "KNOWS": 10, "KIN": 10}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--density", default="d16")
    ap.add_argument("--seed", type=int, default=47)
    a = ap.parse_args()
    src, out = os.path.join(ROOT, "data", a.src), os.path.join(ROOT, "data", a.out)
    w = json.load(open(os.path.join(src, "world_GOLD.json"), encoding="utf-8"))
    ev = json.load(open(os.path.join(src, "events_GOLD.json"), encoding="utf-8"))
    rng = random.Random(a.seed)
    P = w["persons"]
    F = w["final"]
    place = {p["id"]: p["name"] for p in w["places"]}
    item = {i["id"]: i["name"] for i in w["items"]}
    secret = {s["id"]: s["text"] for s in w["secrets"]}

    def name(pid):
        return f"{P[pid]['first']} {P[pid]['surname']}"

    def his(pid):
        return "his" if P[pid]["gender"] == "M" else "her"

    def he(pid):
        return "he" if P[pid]["gender"] == "M" else "she"

    # same v5.2 exclusions as the QA benchmark (end state not narrated, quarrel template, ...)
    excl = {}
    for line in open(os.path.join(src, "questions_GOLD.jsonl"), encoding="utf-8"):
        q = json.loads(line)
        if q.get("excluded") and q.get("subject"):
            excl.setdefault({"LOC_NOW": "LOC", "SPOUSE_NOW": "SPOUSE", "KNOWS": "KNOWS", "RULE_BRIDGE": "SPOUSE"}
                            .get(q["qtype"], q["qtype"]), set()).add(q["subject"])
    alive = [p for p, v in F["alive"].items() if v and P[p].get("adult", True)]
    dead = [p for p, v in F["alive"].items() if not v]
    rumored_dead = {e["claim"]["target"] for e in ev if e["type"] == "RUMOR" and e["claim"].get("kind") == "dead"}
    pairs, seen, got = [], set(), Counter()

    def pair(kind, c, x):
        """c, x = (subtype, subject, paragraph, evidence) of the consistent and of the contradicting member;
        a pair whose paragraphs repeat an earlier one is rejected and the type is drawn again"""
        if c[2] in seen or x[2] in seen or c[2] == x[2]:
            return
        seen.update((c[2], x[2]))
        pairs.append((kind, c, x))
        got[kind] += 1

    def draws(kind):  # draw until the type has its pairs or the candidate pool is exhausted
        for _ in range(30 * N_PAIRS[kind]):
            if got[kind] >= N_PAIRS[kind]:
                return
            yield

    res_hist = {}  # residence history per person: (event id, place) in order
    for e in ev:
        if e["type"] == "INIT_FAMILY":
            for c in [e["father"], e["mother"]] + list(e.get("children", [])):
                if c:
                    res_hist.setdefault(c, []).append((e["id"], e["place"]))
        elif e["type"] == "BIRTH":
            res_hist.setdefault(e["child"], []).append((e["id"], e["place"]))
        elif e["type"] == "TRAVEL":
            res_hist.setdefault(e["person"], []).append((e["id"], e["dest"]))
    # 1. alive: the same sentence about a living and about a dead person
    s_alive = "{n} came down to the market at dawn and bought bread for the week."
    for _ in draws("ALIVE"):
        pid = rng.choice([p for p in alive if p in rumored_dead] or alive) if rng.random() < 0.4 else rng.choice(alive)
        d = rng.choice(dead)
        pair("ALIVE", ("rumor_target" if pid in rumored_dead else "alive", pid, s_alive.format(n=name(pid)),
                       [e["id"] for e in ev if e["type"] == "RUMOR" and e["claim"].get("target") == pid]),
             ("stale", d, s_alive.format(n=name(d)), [e["id"] for e in ev if e["type"] == "DEATH" and e["person"] == d]))
    # 2. residence
    cands = [p for p in alive if F["loc"].get(p) and p in res_hist and res_hist[p][-1][1] == F["loc"][p]
             and p not in excl.get("LOC", set())]
    for _ in draws("LOC"):
        pid = rng.choice(cands)
        hist, cur = res_hist[pid], F["loc"][pid]
        last = [eid for eid, l in hist if l == cur][-1:] or [hist[-1][0]]
        tmpl = rng.choice(["That evening {n} sat by the fire in {h} house at {pl}, mending a net.",
                           "{n} spent the winter at home in {pl}, as {he} had for some time now."])
        para = {l: tmpl.format(n=name(pid), h=his(pid), he=he(pid), pl=place[l]) for l in place}
        former = [(eid, l) for eid, l in hist if l != cur]
        if former and rng.random() < 0.7:
            eid, l = rng.choice(former)
            x = ("stale", pid, para[l], last + [eid])
        else:
            been = {l for _, l in hist}
            l = rng.choice([q for q in place if q not in been])
            x = ("never", pid, para[l], last)
        pair("LOC", ("current", pid, para[cur], last), x)
    # 3. spouse
    marr = [e for e in ev if e["type"] == "MARRY"]
    married = [p for p in alive if F["spouse"].get(p) and F["alive"].get(F["spouse"][p])
               and p not in excl.get("SPOUSE", set())]
    for _ in draws("SPOUSE"):
        pid = rng.choice(married)
        sp = F["spouse"][pid]
        rel = "wife" if P[pid]["gender"] == "M" else "husband"
        mev = [e["id"] for e in marr if pid in (e["a"], e["b"])]

        def s(o):
            return f"{name(pid)} and {his(pid)} {rel} {name(o)} walked together to the spring fair."
        former = [e["b"] if e["a"] == pid else e["a"] for e in marr if pid in (e["a"], e["b"])]
        former = [q for q in former if q != sp]
        if former and rng.random() < 0.7:
            o = rng.choice(former)
            x = ("stale", pid, s(o), mev + [e["id"] for e in ev if e["type"] == "DEATH" and e["person"] == o])
        else:
            g = "F" if P[pid]["gender"] == "M" else "M"
            o = rng.choice([q for q in P if P[q]["gender"] == g and q != sp and q not in former
                            and P[q].get("adult", True)])
            x = ("never", pid, s(o), mev)
        pair("SPOUSE", ("current", pid, s(sp), mev), x)
    # 4. holder of an object: the same object, current holder vs another person
    held = [(i, o) for i, o in F["owner"].items() if o and F["alive"].get(o)]
    for _ in draws("HOLDER"):
        iid, own = rng.choice(held)
        hist = [e for e in ev if e.get("item") == iid and e["type"] in ("INIT_ITEM", "GIVE")]
        holders = [e.get("owner") or e.get("dest") for e in hist]
        ids = [e["id"] for e in hist] + [e["id"] for e in ev if e["type"] in ("RULE_HEIR", "DEATH") and
                                         (e["type"] == "RULE_HEIR" and e["item"] == iid or e.get("person") in holders)]

        def s(o):
            return f"{name(o)} took {item[iid]} from the chest where {he(o)} kept it and turned it over in {his(o)} hands."
        prev = [h for h in holders if h and h != own and F["alive"].get(h)]
        if prev and rng.random() < 0.7:
            o, st = rng.choice(prev), "stale"
        else:
            o, st = rng.choice([q for q in alive if q not in holders]), "never"
        pair("HOLDER", ("current", own, s(own), ids), (st, o, s(o), ids))
    # 5. trade
    occ_ev = [e for e in ev if e["type"] == "OCCUPATION"]
    with_occ = [p for p in alive if F["occupation"].get(p)]
    trades = sorted({v for v in F["occupation"].values() if v} | {e["old"] for e in occ_ev if e["old"]})
    for _ in draws("TRADE"):
        pid = rng.choice(with_occ)
        cur = F["occupation"][pid]
        ids = [e["id"] for e in ev if e["type"] in ("OCCUPATION", "INIT_PERSON") and e["person"] == pid]

        def s(t):
            return f"{name(pid)}, who now worked as a {t}, rose early to begin the day's work."
        old = [e["old"] for e in occ_ev if e["person"] == pid and e["old"] and e["old"] != cur]
        if old and rng.random() < 0.7:
            x = ("stale", pid, s(old[-1]), ids)
        else:
            x = ("never", pid, s(rng.choice([t for t in trades if t != cur and t not in old])), ids)
        pair("TRADE", ("current", pid, s(cur), ids), x)
    # 6. knows a secret: same secret and listener, a living person who learned it vs one who never did
    known = [sid for sid in secret if any(F["alive"].get(p) and P[p].get("adult", True)
                                          for p in F["knows"].get(sid, []))]
    for _ in draws("KNOWS"):
        sid = rng.choice(known)
        knowers = [p for p in F["knows"].get(sid, []) if F["alive"].get(p) and P[p].get("adult", True)]
        pid = rng.choice(knowers)
        non = rng.choice([p for p in alive if p not in F["knows"].get(sid, [])])
        other = rng.choice([p for p in alive if p not in (pid, non)])

        def s(n):
            return f"{name(n)} quietly told {name(other)} what {he(n)} had long known: {secret[sid]}."
        pair("KNOWS", ("current", pid, s(pid),
                       [e["id"] for e in ev if e.get("secret") == sid and (e.get("dest") == pid or e.get("person") == pid)]),
             ("never", non, s(non), [e["id"] for e in ev if e.get("secret") == sid]))
    # 7. grandparent (two-step): same grandchild, living maternal grandmother vs another woman of her generation
    with_gp = [p for p in alive if P[p].get("mother") and P[P[p]["mother"]].get("mother")
               and F["alive"].get(P[P[p]["mother"]]["mother"])]
    for _ in draws("KIN"):
        pid = rng.choice(with_gp)
        m = P[pid]["mother"]
        gm = P[m]["mother"]
        ids = [e["id"] for e in ev if e["type"] in ("BIRTH", "INIT_FAMILY") and
               (e.get("child") in (pid, m) or pid in (e.get("children") or []) or m in (e.get("children") or []))]

        def s(o):
            return f"{name(pid)} walked over to visit {his(pid)} grandmother {name(o)} and stayed for supper."
        pgm = P[P[pid]["father"]].get("mother") if P[pid].get("father") else None
        o = rng.choice([q for q in P if P[q]["gender"] == "F" and P[q]["gen"] == P[gm]["gen"] and q not in (gm, pgm)])
        pair("KIN", ("current", pid, s(gm), ids), ("never", pid, s(o), ids))
    items = []
    for k, (kind, c, x) in enumerate(pairs):
        for label, (st, subj, para, evid) in (("consistent", c), ("contradiction", x)):
            items.append({"kind": kind, "label": label, "subtype": st, "subject": subj, "para": para,
                          "evidence": sorted(set(evid)), "pair": f"P{k:03d}"})
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
        for k, it in enumerate(items):
            f.write(json.dumps({"qid": f"C{k:04d}", "qtype": it["kind"], "subtype": it["subtype"], "subject": it["subject"],
                                "pair": it["pair"], "question": ASK.format(p=it["para"]),
                                "answer": {"kind": "verdict", "gold": it["label"], "aliases": [it["label"]]},
                                "evidence": it["evidence"], "evidence_core": it["evidence"]}, ensure_ascii=False) + "\n")
    # reuse the source world's record, gold spans and built memories (copies; the source is never modified)
    pats = [f"record_{a.density}.txt", f"spans_{a.density}_GOLD.json", "world_GOLD.json", "events_GOLD.json",
            f"cmm_write_{a.density}_*", f"cmm_idle3_{a.density}_*", f"cmm_cards_{a.density}_*", f"emb_{a.density}_c300.npy",
            f"ledger_write_{a.density}_*", f"compact_*_{a.density}_*", f"ng_cards_{a.density}_*",
            f"cmm_audit_{a.density}_*"]
    for pat in pats:
        for fpath in glob.glob(os.path.join(src, pat)):
            if not fpath.endswith(".lock"):
                shutil.copy2(fpath, os.path.join(out, os.path.basename(fpath)))
    print(a.out, len(items), "items,", len(items) // 2, "pairs", dict(Counter(i["kind"] for i in items[::2])),
          dict(Counter(i["subtype"] for i in items)))


if __name__ == "__main__":
    main()
