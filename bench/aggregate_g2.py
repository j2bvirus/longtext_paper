"""LongState-Aggregate G2: global counting questions restricted to the saga's families.

Why: the filler of LongState-Saga is half Project Gutenberg prose, which narrates its own deaths and weddings (in
world 4 an LLM event tagger marks 57 filler paragraphs as narrating a death, against 21 deaths of the world). The
first global questions ("How many people died during the record?", chapter-range counts) therefore had an ambiguous
literal reading, while their gold counted world events only. G2 names the population explicitly: the people whose
family name is one of the world's family names. No filler prose uses these invented names. Place questions keep the
original form (place names are invented as well).

Question types (count answers, scored by core.score kind 'count'):
  G2_NDEATHS, G2_NBIRTHS, G2_NWED      totals over the record, restricted to the families
  G2_FAM_DEATHS, G2_FAM_BIRTHS, G2_FAM_WED   one family name; 4 names with a non-zero count + 2 with zero, if possible
  G2_RANGE_DEATHS, G2_RANGE_WED         restricted to the families, Chapter a..a+9
  G_PLACE_DEATHS, G_PLACE_BIRTHS        as in bench/aggregate.py (4 places with a non-zero count + 2 with zero)
Definitions follow bench/aggregate.py: weddings are MARRY events after Chapter 1 (couples introduced as married do
not count); a wedding counts for a family if either partner has the family name; rumoured deaths do not count; a
birth counts for the family name of the child.

Independent gold checks (not from the event fields used to write the gold):
  deaths per family name = people of that name who are not alive in the world's final state;
  births and weddings per family name = names read from the text of the event paragraphs in the record.
Any disagreement stops the generator.

python bench/aggregate_g2.py --src saga_v5_s4 --out agg2_s4 --density d16 --seed 42
"""
import argparse
import glob
import json
import os
import random
import re
import shutil
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUM = " Answer with a single number."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--density", default="d16")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    src, out = os.path.join(ROOT, "data", a.src), os.path.join(ROOT, "data", a.out)
    rng = random.Random(a.seed)
    world = json.load(open(os.path.join(src, "world_GOLD.json"), encoding="utf-8"))
    events = json.load(open(os.path.join(src, "events_GOLD.json"), encoding="utf-8"))
    spans = json.load(open(os.path.join(src, f"spans_{a.density}_GOLD.json"), encoding="utf-8"))
    text = open(os.path.join(src, f"record_{a.density}.txt"), encoding="utf-8").read()
    persons = world["persons"]
    fams = list(world["surnames"])
    famlist = ", ".join(fams)
    pop = f"people whose family name is one of {famlist}"
    place = {x["id"]: x["label"] for x in world["places"]}
    deaths = [e for e in events if e["type"] == "DEATH"]
    births = [e for e in events if e["type"] == "BIRTH"]
    weds = [e for e in events if e["type"] == "MARRY" and e["chapter"] > 1]
    sn = lambda pid: persons[pid]["surname"]  # noqa: E731
    full = {f"{p['first']} {p['surname']}": pid for pid, p in persons.items()}

    # ---- independent checks
    dead_final = Counter(p["surname"] for pid, p in persons.items() if not world["final"]["alive"].get(pid, True))
    dead_ev = Counter(sn(e["person"]) for e in deaths)
    assert dead_final == dead_ev, ("deaths", dead_final, dead_ev)

    def names_in(e):
        s, t = spans[e["id"]]
        seg = text[s:t]
        return [pid for nm, pid in full.items() if re.search(r"\b" + re.escape(nm) + r"\b", seg)]
    for e in births:  # the child is named in the paragraph with the family name used for the gold
        m = re.search(r"(?:called the child|named) ([A-Z][\w'-]+ [A-Z][\w'-]+)", text[spans[e["id"]][0]:spans[e["id"]][1]])
        assert m and full.get(m.group(1)) == e["child"], ("birth", e["id"], m and m.group(1))
    n_desc = 0
    for e in weds:  # each partner must be referred to in the paragraph: full name, first name, nickname or 'X of <parent>'
        s, t = spans[e["id"]]
        seg = text[s:t]
        for pid in (e["a"], e["b"]):
            pp = persons[pid]
            forms = [f"{pp['first']} {pp['surname']}", pp["first"]] + ([pp["nick"]] if pp.get("nick") else [])
            if any(re.search(r"\b" + re.escape(x) + r"\b", seg) for x in forms):
                continue
            assert re.search(r"\b(daughter|son|child) of\b", seg), ("wedding", e["id"], pid, seg)
            n_desc += 1

    qs = []

    def add(qt, subj, question, gold, evid):
        qs.append({"qtype": qt, "subject": subj, "question": question,
                   "answer": {"kind": "count", "gold": gold, "aliases": [str(gold)]},
                   "evidence": evid, "evidence_core": evid})

    add("G2_NDEATHS", "FAMILIES", f"During the record, how many {pop} died? Count only deaths the record reports as "
        "having happened, not rumours." + NUM, len(deaths), [e["id"] for e in deaths])
    add("G2_NBIRTHS", "FAMILIES", f"During the record, how many children were born whose family name is one of "
        f"{famlist}? Do not count children who were already alive when the record begins." + NUM,
        len(births), [e["id"] for e in births])
    add("G2_NWED", "FAMILIES", f"During the record, how many weddings took place in which at least one partner's "
        f"family name is one of {famlist}? Do not count couples who were already married when the record begins."
        + NUM, len(weds), [e["id"] for e in weds])

    def fam_qs(qt, evs, key, phrase):
        cnt = Counter()
        for e in evs:
            for s in set(key(e)):
                cnt[s] += 1
        hit = sorted(f for f in fams if cnt[f])
        zero = sorted(f for f in fams if not cnt[f])
        for f in rng.sample(hit, min(4, len(hit))) + rng.sample(zero, min(2, len(zero))):
            add(qt, f, phrase.format(f=f) + NUM, cnt[f], [e["id"] for e in evs if f in key(e)])
    fam_qs("G2_FAM_DEATHS", deaths, lambda e: [sn(e["person"])],
           "During the record, how many people with the family name {f} died? Count only deaths the record reports "
           "as having happened, not rumours.")
    fam_qs("G2_FAM_BIRTHS", births, lambda e: [sn(e["child"])],
           "During the record, how many children with the family name {f} were born? Do not count children who were "
           "already alive when the record begins.")
    fam_qs("G2_FAM_WED", weds, lambda e: [sn(e["a"]), sn(e["b"])],
           "During the record, how many weddings took place in which at least one partner has the family name {f}? "
           "Do not count couples who were already married when the record begins.")

    last = max(e["chapter"] for e in events)
    for evs, what, qt in ((deaths, f"How many {pop} died", "G2_RANGE_DEATHS"),
                          (weds, f"How many weddings in which at least one partner's family name is one of {famlist} "
                                 f"took place", "G2_RANGE_WED")):
        for _ in range(4):
            c0 = rng.randint(2, max(2, last - 10))
            c1 = c0 + 9
            n = [e for e in evs if c0 <= e["chapter"] <= c1]
            add(qt, f"CH{c0}-{c1}", f"{what} between Chapter {c0} and Chapter {c1} (both chapters included)?" + NUM,
                len(n), [e["id"] for e in n])

    dpl, bpl = Counter(e["place"] for e in deaths), Counter(e["place"] for e in births)
    for cnt, what, qt, evs in ((dpl, "died or were buried", "G_PLACE_DEATHS", deaths),
                               (bpl, "were born", "G_PLACE_BIRTHS", births)):
        hit = sorted(l for l in cnt)
        zero = sorted(l for l in place if l not in cnt)
        for l in rng.sample(hit, min(4, len(hit))) + rng.sample(zero, min(2, len(zero))):
            add(qt, l, f"During the record, how many people {what} at {place[l]}?" + NUM, cnt.get(l, 0),
                [e["id"] for e in evs if e["place"] == l])

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
        for k, q in enumerate(qs):
            f.write(json.dumps(dict(qid=f"H{k:04d}", **q), ensure_ascii=False) + "\n")
    pats = [f"record_{a.density}.txt", f"spans_{a.density}_GOLD.json", "world_GOLD.json", "events_GOLD.json",
            f"cmm_write_{a.density}_*", f"cmm_idle3_{a.density}_*", f"cmm_cards_{a.density}_*", f"emb_{a.density}_c300.npy",
            f"ledger_write_{a.density}_*", f"compact_*_{a.density}_*", f"ng_cards_{a.density}_*", f"cmm_audit_{a.density}_*",
            f"evx_write_{a.density}_*", f"evx_idle_{a.density}_*"]
    for pat in pats:
        for fpath in glob.glob(os.path.join(src, pat)):
            if not fpath.endswith(".lock") and not os.path.exists(fpath + ".lock"):
                shutil.copy2(fpath, os.path.join(out, os.path.basename(fpath)))
    print(a.out, len(qs), "questions", dict(Counter(q["qtype"] for q in qs)),
          "zero-count", sum(1 for q in qs if q["answer"]["gold"] == 0), "partners by description", n_desc)


if __name__ == "__main__":
    main()
