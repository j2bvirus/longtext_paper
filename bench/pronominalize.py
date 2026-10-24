"""Robustness variant: facts stated in pronoun-only paragraphs (record post-processing).

For a fixed random subset (p) of story events whose text begins with the actor's name,
a fact-free paragraph that names the actor is inserted before the event paragraph, and
the event paragraph's leading name is replaced by He/She:

    Zadette Corrmere had been restless all season.

    She rode out of Ostgate; by the next market day she was living in Harrowford.

A name/alias index finds the first paragraph but not the one that carries the fact,
as in real prose.  The gold span of the event is the pronoun paragraph; the naming
paragraph is recorded as its antecedent (and added to question evidence through the
event's reference dependencies).  World and questions are otherwise identical.
"""
import argparse
import hashlib
import json
import os
import random
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTOR_KEYS = ("person", "a", "src", "teller", "mother")
NEUTRAL = ["had been restless all season.", "had much to think about that year.", "was not one to sit idle for long.",
           "kept {pos} own counsel in those days.", "had grown tired of waiting for news.",
           "was often seen walking alone by the water.", "had little patience left for idle talk."]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--p", type=float, default=0.4)
    ap.add_argument("--densities", default="d0,d1,d4,d16,d64")
    a = ap.parse_args()
    sdir, ddir = os.path.join(ROOT, "data", a.src), os.path.join(ROOT, "data", a.dst)
    os.makedirs(ddir, exist_ok=True)
    events = json.load(open(os.path.join(sdir, "events_GOLD.json"), encoding="utf-8"))
    persons = json.load(open(os.path.join(sdir, "world_GOLD.json"), encoding="utf-8"))["persons"]
    firsts = {}
    for p in persons.values():
        firsts[p["first"]] = firsts.get(p["first"], 0) + 1
    rng = random.Random(int(hashlib.sha256(a.dst.encode()).hexdigest()[:8], 16))
    chosen = {}
    for e in events:
        if e["chapter"] < 2:
            continue
        actor = next((e.get(k) for k in ACTOR_KEYS if e.get(k)), None)
        if not actor:
            continue
        p = persons[actor]
        forms = [f"{p['first']} {p['surname']}"] + ([p["first"]] if firsts[p["first"]] == 1 else []) + ([p["nick"]] if p["nick"] else [])
        lead = next((f for f in sorted(forms, key=len, reverse=True) if e["text"].startswith(f + " ")), None)
        if lead and rng.random() < a.p:
            pos = "his" if p["gender"] == "M" else "her"
            naming = f"{p['first']} {p['surname']} " + rng.choice(NEUTRAL).format(pos=pos)
            chosen[e["id"]] = {"naming": naming, "text": ("He" if p["gender"] == "M" else "She") + e["text"][len(lead):]}
    print("events rewritten:", len(chosen), "of", len(events))
    for d in a.densities.split(","):
        text = open(os.path.join(sdir, f"record_{d}.txt"), encoding="utf-8").read()
        spans = json.load(open(os.path.join(sdir, f"spans_{d}_GOLD.json")))
        order = sorted(spans, key=lambda k: spans[k][0])
        out, cur, nsp, shift = [], 0, {}, 0
        for k in order:
            st, en = spans[k]
            if k in chosen:
                out.append(text[cur:st])
                pre = len("".join(out))
                ins = chosen[k]["naming"] + "\n\n"
                out.append(ins + chosen[k]["text"])
                nsp[k] = [pre + len(ins), pre + len(ins) + len(chosen[k]["text"])]
                cur = en
            else:
                out.append(text[cur:st])
                pre = len("".join(out))
                out.append(text[st:en])
                nsp[k] = [pre, pre + en - st]
                cur = en
        out.append(text[cur:])
        rec = "".join(out)
        for k, (s0, e0) in nsp.items():
            want = chosen[k]["text"] if k in chosen else text[spans[k][0]:spans[k][1]]
            assert rec[s0:e0] == want, (d, k)
        open(os.path.join(ddir, f"record_{d}.txt"), "w", encoding="utf-8").write(rec)
        json.dump(nsp, open(os.path.join(ddir, f"spans_{d}_GOLD.json"), "w"), indent=0)
        print(d, "chars", len(rec))
    for e in events:
        if e["id"] in chosen:
            e["text_original"] = e["text"]
            e["text"] = chosen[e["id"]]["text"]
            e["naming_paragraph"] = chosen[e["id"]]["naming"]
            e["pronoun_only"] = True
    json.dump(events, open(os.path.join(ddir, "events_GOLD.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.copy(os.path.join(sdir, "world_GOLD.json"), ddir)
    for fn in ("questions_GOLD.jsonl", "questions_GOLD_v50.jsonl"):
        shutil.copy(os.path.join(sdir, fn), ddir)
    json.dump({"source": a.src, "p": a.p, "rewritten": sorted(chosen)},
              open(os.path.join(ddir, "pronoun_variant.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
