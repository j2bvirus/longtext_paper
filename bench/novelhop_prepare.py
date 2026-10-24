"""External validity: real novels from NovelHopQA (Gupta et al.), full Gutenberg text as the record.

For each book: data/nhq_<key>/record_full.txt (Gutenberg body, CRLF->LF), questions_GOLD.jsonl
(free-form answers), spans_full_GOLD.json (each gold paragraph located in the book).
The pinned dataset copy is given by NHQ_SRC (release/THIRD_PARTY_DATA.md).
"""
import glob
import hashlib
import json
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# with NHQ_SRC set (release users), the sources are <NHQ_SRC>/DATA_NOVELHOPQA_HF_PINNED/hop_*.parquet and
# <NHQ_SRC>/PG<gutenberg id>/original.txt (release/THIRD_PARTY_DATA.md); without it, the authors' working layout
NHQ_SRC = os.environ.get("NHQ_SRC")
SRC = NHQ_SRC or os.path.join(ROOT, "..", "full_review", "sources")


def book_file(corp):
    if NHQ_SRC:
        return os.path.join(SRC, "PG" + re.search(r"(\d+)$", corp).group(1), "original.txt")
    return os.path.join(SRC, corp, "original.txt")
BOOKS = {"anna": ("Anna Karenina", "CORPUS_PG_1399"), "dracula": ("Dracula", "CORPUS_PG_345"),
         "moby": ("Moby Dick", "CORPUS_PG_2701"), "great": ("Great Expectations", "CORPUS_PG_1400")}
# held-out test books (used only after CMM v2 was frozen)
TEST_BOOKS = {"mid": ("Middlemarch", "CORPUS_PG_145"), "karam": ("The Brothers Karamazov", "CORPUS_PG_28054"),
              "pride": ("Pride and Prejudice", "../../claude_restart/data/sources_extra/PG1342")}


def body(txt):
    txt = txt.replace("\r\n", "\n")
    s = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG[^\n]*\n", txt)
    e = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", txt)
    return txt[s.end() if s else 0: e.start() if e else len(txt)].strip("\n")


def locate(par, text):
    words = re.findall(r"\S+", par)
    if len(words) < 4:
        return None
    for n in (14, 8, 5):
        pat = r"\s+".join(re.escape(w) for w in words[:n])
        m = re.search(pat, text)
        if m:
            end_pat = r"\s+".join(re.escape(w) for w in words[-min(n, len(words)):])
            m2 = re.search(end_pat, text[m.start():m.start() + len(par) * 3])
            return [m.start(), m.start() + (m2.end() if m2 else len(par))]
    return None


def main():
    df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(SRC, "DATA_NOVELHOPQA_HF_PINNED", "hop_*.parquet")))])
    import sys
    books = TEST_BOOKS if "--test" in sys.argv else BOOKS
    if "--test2" in sys.argv:  # held-out books for CMM v3 (never used before v3 was frozen)
        books = {"emma": ("Emma", "../../claude_restart/data/sources_extra/PG158"),
                 "wuther": ("Wuthering Heights", "../../claude_restart/data/sources_extra/PG768"),
                 "sense": ("Sense and Sensibility", "../../claude_restart/data/sources_extra/PG161")}
    for key, (title, corp) in books.items():
        text = body(open(book_file(corp), encoding="utf-8", errors="ignore").read())
        ddir = os.path.join(ROOT, "data", f"nhq_{key}")
        os.makedirs(ddir, exist_ok=True)
        open(os.path.join(ddir, "record_full.txt"), "w", encoding="utf-8").write(text)
        sub = df[df.book == title].reset_index(drop=True)
        spans, qs, miss = {}, [], 0
        for i, r in sub.iterrows():
            if not isinstance(r["answer"], str) or not r["answer"].strip():
                print("  skipped (no gold answer in the release):", title, i)
                continue
            pars = [p.strip() for p in re.split(r"Paragraph \d+:\s*", r["context"]) if p.strip()]
            ev = []
            for j, p in enumerate(pars):
                sp = locate(p, text)
                if sp:
                    eid = f"E{i:04d}_{j}"
                    spans[eid] = sp
                    ev.append(eid)
                else:
                    miss += 1
            qs.append({"qid": f"Q{i:04d}", "qtype": f"HOP{int(r['number_of_hops'])}", "question": r["question"],
                       "answer": {"kind": "free", "gold": r["answer"], "aliases": [r["answer"]]},
                       "evidence": ev, "evidence_core": ev, "keywords": r["keywords"],
                       "gold_context": r["context"]})
        json.dump(spans, open(os.path.join(ddir, "spans_full_GOLD.json"), "w"), indent=0)
        with open(os.path.join(ddir, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
            for q in qs:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        json.dump({"persons": {}, "source": "NovelHopQA (abhaygupta1266/novelhopqa @ c642bf8)", "book": title,
                   "gutenberg": corp, "sha256": hashlib.sha256(text.encode()).hexdigest()},
                  open(os.path.join(ddir, "world_GOLD.json"), "w", encoding="utf-8"), indent=1)
        print(key, title, "chars", len(text), "questions", len(qs), "gold paragraphs unlocated", miss)


if __name__ == "__main__":
    main()
