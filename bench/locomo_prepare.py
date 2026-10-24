"""Chat-memory domain: LoCoMo (Maharana et al., 2024; snap-research/locomo, locomo10.json).

Each of the 10 conversations becomes one record (data/locomo_<i>/record_full.txt): a dated
header paragraph per session and one paragraph per turn ("Speaker: text", shared-photo
captions appended).  Questions: a fixed stratified sample of 60 per category
(1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop, 5 adversarial/unanswerable),
seed 7.  Categories 1-4 are free-form (LLM-judged); category 5 is scored deterministically
as 'unknown'.  Gold evidence = the dialogue turns listed by the dataset.
"""
import collections
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "sources_extra", "LOCOMO", "locomo10.json")
CAT = {1: "MULTI_HOP", 2: "TEMPORAL", 3: "OPEN_DOMAIN", 4: "SINGLE_HOP", 5: "ADVERSARIAL"}


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    pool = []
    for ci, s in enumerate(data):
        for qi, q in enumerate(s["qa"]):
            pool.append((ci, qi, q))
    rng = random.Random(7)
    by = collections.defaultdict(list)
    for x in pool:
        by[x[2]["category"]].append(x)
    chosen = set()
    for c, xs in by.items():
        rng.shuffle(xs)
        for ci, qi, q in xs[:60]:
            chosen.add((ci, qi))
    for ci, s in enumerate(data):
        conv = s["conversation"]
        ddir = os.path.join(ROOT, "data", f"locomo_{ci}")
        os.makedirs(ddir, exist_ok=True)
        parts, spans = [], {}
        pos = 0
        k = 1
        while f"session_{k}" in conv:
            hdr = f"Session {k} ({conv.get(f'session_{k}_date_time', '')})"
            parts.append(hdr)
            pos += len(hdr) + 2
            date = conv.get(f"session_{k}_date_time", "")
            for t in conv[f"session_{k}"]:
                txt = f"[{date}] {t['speaker']}: {t['text']}"
                if t.get("blip_caption"):
                    txt += f" [shares a photo: {t['blip_caption']}]"
                spans[t["dia_id"]] = [pos, pos + len(txt)]
                parts.append(txt)
                pos += len(txt) + 2
            k += 1
        record = "\n\n".join(parts)
        for did, (a, b) in spans.items():
            assert record[a:b].split("] ", 1)[1].split(":")[0] in (conv["speaker_a"], conv["speaker_b"]), did
        open(os.path.join(ddir, "record_full.txt"), "w", encoding="utf-8").write(record)
        json.dump(spans, open(os.path.join(ddir, "spans_full_GOLD.json"), "w"), indent=0)
        qs = []
        for qi, q in enumerate(s["qa"]):
            if (ci, qi) not in chosen:
                continue
            cat = q["category"]
            if cat == 5:
                ans = {"kind": "unknown", "gold": "unknown", "aliases": ["unknown"]}
            else:
                ans = {"kind": "free", "gold": str(q.get("answer", "")), "aliases": [str(q.get("answer", ""))]}
            ev = [e for e in q.get("evidence", []) if e in spans]
            qs.append({"qid": f"Q{qi:04d}", "qtype": CAT[cat], "question": q["question"], "answer": ans,
                       "evidence": ev, "evidence_core": ev})
        with open(os.path.join(ddir, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
            for q in qs:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        json.dump({"persons": {}, "source": "LoCoMo locomo10.json", "sample_id": s.get("sample_id"),
                   "speakers": [conv["speaker_a"], conv["speaker_b"]]},
                  open(os.path.join(ddir, "world_GOLD.json"), "w", encoding="utf-8"), indent=1)
        print(ci, s.get("sample_id"), "sessions", k - 1, "chars", len(record), "questions", len(qs),
              dict(collections.Counter(q["qtype"] for q in qs)))


if __name__ == "__main__":
    main()
