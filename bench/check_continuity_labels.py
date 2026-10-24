"""Independent label check for LongState-Continuity items: re-derive each verdict from the world's end state by
parsing the paragraph (not from the generator's choices).  python bench/check_continuity_labels.py cont2_s7"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(ds):
    """list of (qid, type, subtype, gold, paragraph start) whose gold verdict disagrees with the world's end state"""
    d = os.path.join(ROOT, "data", ds)
    w = json.load(open(os.path.join(d, "world_GOLD.json"), encoding="utf-8"))
    P, F = w["persons"], w["final"]
    pid_of = {f"{p['first']} {p['surname']}": k for k, p in P.items()}
    place_of = {p["name"]: p["id"] for p in w["places"]}
    item_of = {i["name"]: i["id"] for i in w["items"]}
    secret_of = {s["text"]: s["id"] for s in w["secrets"]}
    NM = r"([A-Z][a-z]+ [A-Z][a-z]+)"
    bad, n = [], 0
    for line in open(os.path.join(d, "questions_GOLD.jsonl"), encoding="utf-8"):
        q = json.loads(line)
        para = q["question"].split('"')[1]
        t, gold = q["qtype"], q["answer"]["gold"]
        if t == "ALIVE":
            m = re.match(NM + " came down", para)
            ok = bool(F["alive"][pid_of[m.group(1)]])
        elif t == "LOC":
            m = re.match(r"(?:That evening )?" + NM + r" (?:sat by the fire in (?:his|her) house at|spent the winter at home in) (.+?)[,.]", para)
            p = pid_of[m.group(1)]
            ok = F["alive"][p] and F["loc"].get(p) == place_of[m.group(2)]
        elif t == "SPOUSE":
            m = re.match(NM + r" and (?:his|her) (?:wife|husband) " + NM + " walked", para)
            a, b = pid_of[m.group(1)], pid_of[m.group(2)]
            ok = F["alive"][a] and F["alive"][b] and F["spouse"].get(a) == b
        elif t == "HOLDER":
            m = re.match(NM + r" took (.+?) from the chest", para)
            p = pid_of[m.group(1)]
            ok = F["alive"][p] and F["owner"].get(item_of[m.group(2)]) == p
        elif t == "TRADE":
            m = re.match(NM + r", who now worked as an? (.+?), rose", para)
            p = pid_of[m.group(1)]
            ok = F["alive"][p] and F["occupation"].get(p) == m.group(2)
        elif t == "KNOWS":
            m = re.match(NM + r" quietly told " + NM + r" what (?:he|she) had long known: (.+)\.$", para)
            p, o = pid_of[m.group(1)], pid_of[m.group(2)]
            ok = F["alive"][p] and F["alive"][o] and p in F["knows"].get(secret_of[m.group(3)], [])
        elif t == "KIN":
            m = re.match(NM + r" walked over to visit (?:his|her) grandmother " + NM + " and", para)
            p, g = pid_of[m.group(1)], pid_of[m.group(2)]
            mo = P[p].get("mother")
            fa = P[p].get("father")
            gms = {P[mo].get("mother") if mo else None, P[fa].get("mother") if fa else None} - {None}
            ok = F["alive"][p] and F["alive"][g] and g in gms
        else:
            raise ValueError(t)
        n += 1
        if ("consistent" if ok else "contradiction") != gold:
            bad.append((q["qid"], t, q["subtype"], gold, para[:90]))
    return bad, n


def main():
    ds = sys.argv[1]
    bad, n = check(ds)
    print(f"{ds}: {n} items checked, {len(bad)} label disagreements")
    for b in bad:
        print("  ", b)


if __name__ == "__main__":
    main()
