"""Answer-key correction v5.2 = v5.1 + exclusions for ill-posed questions (record unchanged).

Applied on top of the v5.0 backup (questions_GOLD_v50.jsonl), so it is idempotent.
v5.1: in-story children: birthplace stated in the BIRTH paragraph; their later
      residence is not narrated (location questions about them excluded).
v5.2: (a) KNOWS / PROMISE questions whose subject is dead at the end (knowledge or a
      pending promise of a dead person is ill-defined);
      (b) SPOUSE_NOW / RULE_BRIDGE questions about a person whose move (or whose
      spouse's move) was narrated with the 'After the quarrel ... quit ... for good'
      template, which invites an unmodelled separation inference.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for ds in sys.argv[1:]:
    ddir = os.path.join(ROOT, "data", ds)
    bak = os.path.join(ddir, "questions_GOLD_v50.jsonl")
    if not os.path.exists(bak):
        import shutil
        shutil.copy(os.path.join(ddir, "questions_GOLD.jsonl"), bak)
    qs = [json.loads(l) for l in open(bak, encoding="utf-8")]
    ev = json.load(open(os.path.join(ddir, "events_GOLD.json"), encoding="utf-8"))
    world = json.load(open(os.path.join(ddir, "world_GOLD.json"), encoding="utf-8"))
    lname = {p["id"]: p["name"] for p in world["places"]}
    alive = world["final"]["alive"]
    birth = {e["child"]: e for e in ev if e["type"] == "BIRTH"}
    quarrel = set()
    for e in ev:
        if e["type"] == "TRAVEL" and "After the quarrel" in e["text"]:
            quarrel.add(e["person"])
    spouses = {}
    for e in ev:
        if e["type"] in ("MARRY",):
            spouses.setdefault(e["a"], set()).add(e["b"])
            spouses.setdefault(e["b"], set()).add(e["a"])
        if e["type"] == "INIT_FAMILY":
            spouses.setdefault(e["father"], set()).add(e["mother"])
            spouses.setdefault(e["mother"], set()).add(e["father"])
    cnt = {"bp": 0, "child_loc": 0, "dead_subject": 0, "quarrel": 0}
    for q in qs:
        s = q.get("subject")
        if q["qtype"] == "BIRTHPLACE" and q["answer"]["kind"] == "unknown" and s in birth:
            pl = lname[birth[s]["place"]]
            q["answer"] = {"kind": "place", "gold": pl, "aliases": [pl]}
            q["evidence"] = [birth[s]["id"]]
            q["evidence_core"] = [birth[s]["id"]]
            q["fix"] = "v51 birthplace stated in BIRTH paragraph"
            cnt["bp"] += 1
        if q["qtype"] in ("LOC_NOW", "LOC_AT_EVENT", "EVER_VISITED") and s in birth:
            q["excluded"] = True
            q["fix"] = "v51 child residence after parents move is not narrated"
            cnt["child_loc"] += 1
        if q["qtype"] in ("KNOWS", "PROMISE") and s and not alive.get(s, True):
            q["excluded"] = True
            q["fix"] = "v52 subject dead at the end"
            cnt["dead_subject"] += 1
        if q["qtype"] in ("SPOUSE_NOW", "RULE_BRIDGE") and s and ({s} | spouses.get(s, set())) & quarrel:
            q["excluded"] = True
            q["fix"] = "v52 quarrel-template move invites separation inference"
            cnt["quarrel"] += 1
    with open(os.path.join(ddir, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(ds, cnt, "scored", sum(1 for q in qs if not q.get("excluded")), "of", len(qs))
