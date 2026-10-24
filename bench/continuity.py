"""LongState-Continuity: does a memory catch a continuation that contradicts the record?

For a LongState-Saga world, write short "draft continuation" paragraphs about the end state of the world, half
consistent with the record and half contradicting it, and ask the system whether the paragraph may be appended.
Contradictions are either STALE (a value that was true earlier and has since changed: a former residence,
spouse, holder or trade, a person who has died) or NEVER (a value that was never true).  Seven types: alive,
residence, spouse, holder, trade, knows-secret, grandparent (two-step).  Gold evidence = the events that establish
the relevant end state (and, for stale contradictions, the change).  Answers: 'consistent' / 'contradiction'.

The new dataset directory reuses the world's record, spans and already built memories (copied, never modified):
python bench/continuity.py --src saga_v5_s4 --out cont_s4 --density d16 --seed 41
"""
import argparse
import glob
import json
import os
import random
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASK = ("A writer continuing this record drafts the following paragraph to append at its end:\n\"{p}\"\n"
       "Is this paragraph consistent with what the record establishes as of its end? Answer exactly "
       "'consistent' or 'contradiction'.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--density", default="d16")
    ap.add_argument("--seed", type=int, default=41)
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

    # subjects whose end state the answer key had to exclude (not narrated, quarrel template, ...) are skipped
    # for the corresponding type, using the same v5.2 decisions as the QA benchmark
    excl = {}
    for line in open(os.path.join(src, "questions_GOLD.jsonl"), encoding="utf-8"):
        q = json.loads(line)
        if q.get("excluded") and q.get("subject"):
            excl.setdefault({"LOC_NOW": "LOC", "SPOUSE_NOW": "SPOUSE", "KNOWS": "KNOWS", "RULE_BRIDGE": "SPOUSE"}
                            .get(q["qtype"], q["qtype"]), set()).add(q["subject"])
    alive = [p for p, v in F["alive"].items() if v and P[p].get("adult", True)]
    dead = [p for p, v in F["alive"].items() if not v]
    rumored_dead = {e["claim"]["target"] for e in ev if e["type"] == "RUMOR" and e["claim"].get("kind") == "dead"}
    items_out = []

    def add(kind, label, subtype, subj, para, evid):
        items_out.append({"kind": kind, "label": label, "subtype": subtype, "subject": subj, "para": para,
                          "evidence": sorted(set(evid))})

    def events_of(pid, types):
        return [e for e in ev if e["type"] in types and pid in
                [e.get(k) for k in ("person", "a", "b", "src", "dest", "child", "mother", "father", "teller")]
                + list(e.get("children", []) or [])]

    # residence history per person: (event id, place) in order
    res_hist = {}
    for e in ev:
        if e["type"] == "INIT_FAMILY":
            for c in [e["father"], e["mother"]] + list(e.get("children", [])):
                if c:
                    res_hist.setdefault(c, []).append((e["id"], e["place"]))
        elif e["type"] == "BIRTH":
            res_hist.setdefault(e["child"], []).append((e["id"], e["place"]))
        elif e["type"] == "TRAVEL":
            res_hist.setdefault(e["person"], []).append((e["id"], e["dest"]))
    # 1. alive
    for _ in range(40):
        if rng.random() < 0.5:
            pid = rng.choice([p for p in alive if p in rumored_dead] or alive) if rng.random() < 0.4 else rng.choice(alive)
            add("ALIVE", "consistent", "rumor_target" if pid in rumored_dead else "alive", pid,
                f"{name(pid)} came down to the market at dawn and bought bread for the week.",
                [e["id"] for e in ev if e["type"] == "RUMOR" and e["claim"].get("target") == pid])
        else:
            pid = rng.choice(dead)
            add("ALIVE", "contradiction", "stale", pid,
                f"{name(pid)} came down to the market at dawn and bought bread for the week.",
                [e["id"] for e in ev if e["type"] == "DEATH" and e["person"] == pid])
    # 2. residence
    cands = [p for p in alive if F["loc"].get(p) and p in res_hist and res_hist[p][-1][1] == F["loc"][p]
             and p not in excl.get("LOC", set())]
    for _ in range(50):
        pid = rng.choice(cands)
        hist = res_hist[pid]
        cur = F["loc"][pid]
        last = [eid for eid, l in hist if l == cur][-1:] or [hist[-1][0]]
        tmpl = rng.choice(["That evening {n} sat by the fire in {h} house at {pl}, mending a net.",
                           "{n} spent the winter at home in {pl}, as {he} had for some time now."])
        if rng.random() < 0.5:
            add("LOC", "consistent", "current", pid, tmpl.format(n=name(pid), h=his(pid), he=he(pid), pl=place[cur]), last)
        else:
            former = [(eid, l) for eid, l in hist if l != cur]
            if former and rng.random() < 0.7:
                eid, l = rng.choice(former)
                add("LOC", "contradiction", "stale", pid, tmpl.format(n=name(pid), h=his(pid), he=he(pid), pl=place[l]),
                    last + [eid])
            else:
                been = {l for _, l in hist}
                l = rng.choice([x for x in place if x not in been])
                add("LOC", "contradiction", "never", pid, tmpl.format(n=name(pid), h=his(pid), he=he(pid), pl=place[l]), last)
    # 3. spouse
    marr = [e for e in ev if e["type"] == "MARRY"]
    married = [p for p in alive if F["spouse"].get(p) and p not in excl.get("SPOUSE", set())]
    for _ in range(40):
        pid = rng.choice(married)
        sp = F["spouse"][pid]
        rel = "wife" if P[pid]["gender"] == "M" else "husband"
        mev = [e["id"] for e in marr if pid in (e["a"], e["b"])]
        if rng.random() < 0.5:
            add("SPOUSE", "consistent", "current", pid,
                f"{name(pid)} and {his(pid)} {rel} {name(sp)} walked together to the spring fair.", mev)
        else:
            former = [e["b"] if e["a"] == pid else e["a"] for e in marr if pid in (e["a"], e["b"])]
            former = [x for x in former if x != sp]
            if former and rng.random() < 0.7:
                o = rng.choice(former)
                add("SPOUSE", "contradiction", "stale", pid,
                    f"{name(pid)} and {his(pid)} {rel} {name(o)} walked together to the spring fair.",
                    mev + [e["id"] for e in ev if e["type"] == "DEATH" and e["person"] == o])
            else:
                g = "F" if P[pid]["gender"] == "M" else "M"
                o = rng.choice([x for x in P if P[x]["gender"] == g and x != sp and P[x].get("adult", True)])
                add("SPOUSE", "contradiction", "never", pid,
                    f"{name(pid)} and {his(pid)} {rel} {name(o)} walked together to the spring fair.", mev)
    # 4. holder of an object
    held = [(i, o) for i, o in F["owner"].items() if o and F["alive"].get(o)]
    for _ in range(30):
        iid, own = rng.choice(held)
        hist = [e for e in ev if e.get("item") == iid and e["type"] in ("INIT_ITEM", "GIVE")]
        holders = [e.get("owner") or e.get("dest") for e in hist]
        tmpl = "{n} took {it} from the chest where {he} kept it and turned it over in {h} hands."
        ids = [e["id"] for e in hist] + [e["id"] for e in ev if e["type"] in ("RULE_HEIR", "DEATH") and
                                         (e["type"] == "RULE_HEIR" and e["item"] == iid or e.get("person") in holders)]
        if rng.random() < 0.5:
            add("HOLDER", "consistent", "current", own, tmpl.format(n=name(own), it=item[iid], he=he(own), h=his(own)), ids)
        else:
            prev = [h for h in holders if h and h != own and F["alive"].get(h)]
            if prev and rng.random() < 0.7:
                o, st = rng.choice(prev), "stale"
            else:
                o, st = rng.choice([x for x in alive if x not in holders]), "never"
            add("HOLDER", "contradiction", st, o, tmpl.format(n=name(o), it=item[iid], he=he(o), h=his(o)), ids)
    # 5. trade
    occ_ev = [e for e in ev if e["type"] == "OCCUPATION"]
    with_occ = [p for p in alive if F["occupation"].get(p)]
    trades = sorted({v for v in F["occupation"].values() if v} | {e["old"] for e in occ_ev if e["old"]})
    for _ in range(40):
        pid = rng.choice(with_occ)
        cur = F["occupation"][pid]
        ids = [e["id"] for e in ev if e["type"] in ("OCCUPATION", "INIT_PERSON") and e["person"] == pid]
        tmpl = "{n}, who now worked as a {t}, rose early to begin the day's work."
        if rng.random() < 0.5:
            add("TRADE", "consistent", "current", pid, tmpl.format(n=name(pid), t=cur), ids)
        else:
            old = [e["old"] for e in occ_ev if e["person"] == pid and e["old"] and e["old"] != cur]
            if old and rng.random() < 0.7:
                add("TRADE", "contradiction", "stale", pid, tmpl.format(n=name(pid), t=old[-1]), ids)
            else:
                add("TRADE", "contradiction", "never", pid,
                    tmpl.format(n=name(pid), t=rng.choice([t for t in trades if t != cur])), ids)
    # 6. knows a secret
    for _ in range(20):
        sid = rng.choice(list(secret))
        knowers = [p for p in F["knows"].get(sid, []) if F["alive"].get(p)]
        other = rng.choice(alive)
        tmpl = "{n} quietly told {o} what {he} had long known: {s}."
        if knowers and rng.random() < 0.5:
            pid = rng.choice(knowers)
            ids = [e["id"] for e in ev if e.get("secret") == sid and (e.get("dest") == pid or e.get("person") == pid)]
            add("KNOWS", "consistent", "current", pid, tmpl.format(n=name(pid), o=name(other), he=he(pid), s=secret[sid]), ids)
        else:
            pid = rng.choice([p for p in alive if p not in F["knows"].get(sid, [])])
            add("KNOWS", "contradiction", "never", pid, tmpl.format(n=name(pid), o=name(other), he=he(pid), s=secret[sid]),
                [e["id"] for e in ev if e.get("secret") == sid])
    # 7. grandparent (two-step)
    with_gp = [p for p in alive if P[p].get("mother") and P[P[p]["mother"]].get("mother")]
    for _ in range(20):
        pid = rng.choice(with_gp)
        m = P[pid]["mother"]
        gm = P[m]["mother"]
        ids = [e["id"] for e in ev if e["type"] in ("BIRTH", "INIT_FAMILY") and
               (e.get("child") in (pid, m) or pid in (e.get("children") or []) or m in (e.get("children") or []))]
        if rng.random() < 0.5:
            add("KIN", "consistent", "current", pid,
                f"{name(pid)} walked over to visit {his(pid)} grandmother {name(gm)} and stayed for supper.", ids)
        else:
            pgm = P[P[pid]["father"]].get("mother") if P[pid].get("father") else None
            o = rng.choice([x for x in P if P[x]["gender"] == "F" and P[x]["gen"] == P[gm]["gen"] and x not in (gm, pgm)])
            add("KIN", "contradiction", "never", pid,
                f"{name(pid)} walked over to visit {his(pid)} grandmother {name(o)} and stayed for supper.", ids)
    # de-duplicate identical paragraphs
    seen, items = set(), []
    for it in items_out:
        if it["para"] in seen:
            continue
        seen.add(it["para"])
        items.append(it)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
        for k, it in enumerate(items):
            f.write(json.dumps({"qid": f"C{k:04d}", "qtype": it["kind"], "subtype": it["subtype"], "subject": it["subject"],
                                "question": ASK.format(p=it["para"]),
                                "answer": {"kind": "verdict", "gold": it["label"], "aliases": [it["label"]]},
                                "evidence": it["evidence"], "evidence_core": it["evidence"]}, ensure_ascii=False) + "\n")
    # reuse the source world's record, gold spans and built memories (copies; the source is never modified)
    pats = [f"record_{a.density}.txt", f"spans_{a.density}_GOLD.json", "world_GOLD.json", "events_GOLD.json",
            f"cmm_write_{a.density}_*", f"cmm_idle3_{a.density}_*", f"cmm_cards_{a.density}_*", f"emb_{a.density}_c300.npy",
            f"ledger_write_{a.density}_*", f"compact_*_{a.density}_*", f"ng_cards_{a.density}_*"]
    for pat in pats:
        for fpath in glob.glob(os.path.join(src, pat)):
            if not fpath.endswith(".lock"):
                shutil.copy2(fpath, os.path.join(out, os.path.basename(fpath)))
    from collections import Counter
    print(a.out, len(items), "items", dict(Counter((i["kind"], i["label"]) for i in items)),
          dict(Counter(i["subtype"] for i in items)))


if __name__ == "__main__":
    main()
