"""Answer-key correction v5.1 (record text unchanged).

1. Children born during the story: the BIRTH paragraph states where they were born
   ("In Coldwick. A daughter was born ..."), so their birthplace is known, not
   'unknown'.  Gold becomes the BIRTH place; evidence becomes the BIRTH event.
2. Children born during the story are not narrated as moving with their parents,
   so their later residence is ambiguous for a reader.  Location questions about
   them (LOC_NOW, LOC_AT_EVENT, EVER_VISITED) are excluded from scoring.
The original key is kept as questions_GOLD_v50.jsonl.
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for ds in sys.argv[1:]:
    ddir = os.path.join(ROOT, "data", ds)
    src = os.path.join(ddir, "questions_GOLD.jsonl")
    bak = os.path.join(ddir, "questions_GOLD_v50.jsonl")
    if not os.path.exists(bak):
        shutil.copy(src, bak)
    qs = [json.loads(l) for l in open(bak, encoding="utf-8")]
    ev = json.load(open(os.path.join(ddir, "events_GOLD.json"), encoding="utf-8"))
    world = json.load(open(os.path.join(ddir, "world_GOLD.json"), encoding="utf-8"))
    lname = {p["id"]: p["name"] for p in world["places"]}
    birth = {e["child"]: e for e in ev if e["type"] == "BIRTH"}
    n_bp = n_ex = 0
    for q in qs:
        s = q.get("subject")
        if q["qtype"] == "BIRTHPLACE" and q["answer"]["kind"] == "unknown" and s in birth:
            pl = lname[birth[s]["place"]]
            q["answer"] = {"kind": "place", "gold": pl, "aliases": [pl]}
            q["evidence"] = [birth[s]["id"]]
            q["evidence_core"] = [birth[s]["id"]]
            q["fix_v51"] = "birthplace stated in BIRTH paragraph"
            n_bp += 1
        if q["qtype"] in ("LOC_NOW", "LOC_AT_EVENT", "EVER_VISITED") and s in birth:
            q["excluded"] = True
            q["fix_v51"] = "child residence after parents move is not narrated"
            n_ex += 1
    with open(src, "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(ds, "birthplace fixed", n_bp, "excluded", n_ex, "of", len(qs))
