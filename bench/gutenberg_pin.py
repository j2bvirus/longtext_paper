"""Turn current Project Gutenberg texts back into the versions used in the paper.

python bench/gutenberg_pin.py <dir>      (<dir> as in release/THIRD_PARTY_DATA.md: <dir>/PG<id>/original.txt)

Gutenberg corrects its texts from time to time. In a later download two of the ten books differed from the versions
we had used: Moby Dick (2701; stage directions now in parentheses, one epigraph of the Extracts laid
out line by line) and Sense and Sensibility (161; two commas removed). bench/gutenberg_versions.json holds, for
each such book, the sha256 of the body we used and of the body found in the later download, and the line edits from the
second to the first. For a book whose body has the later hash the edits are applied and the result is checked
against the hash we used; the downloaded file is kept as original_current.txt. A body with any other hash is left
unchanged and reported. The body is the text between the START and END markers, as in bench/novelhop_prepare.py.
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sha = lambda t: hashlib.sha256(t.encode()).hexdigest()


def body(txt):  # identical to bench/novelhop_prepare.py
    txt = txt.replace("\r\n", "\n")
    s = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG[^\n]*\n", txt)
    e = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", txt)
    return txt[s.end() if s else 0: e.start() if e else len(txt)].strip("\n")


def main():
    src = sys.argv[1]
    versions = json.load(open(os.path.join(HERE, "gutenberg_versions.json"), encoding="utf-8"))
    bad = 0
    for gid, v in sorted(versions.items()):
        p = os.path.join(src, f"PG{gid}", "original.txt")
        if not os.path.exists(p):
            print(f"PG{gid}: no {p}")
            bad += 1
            continue
        txt = open(p, encoding="utf-8").read().replace("\r\n", "\n")
        h = sha(body(txt))
        if h == v["used_sha256"]:
            print(f"PG{gid}: already the version used")
            continue
        if h != v["current_sha256"]:
            print(f"PG{gid}: unknown version (body sha256 {h}); left unchanged")
            bad += 1
            continue
        for old, new in v["edits"]:
            if txt.count(old) != 1:
                raise SystemExit(f"PG{gid}: an edit does not apply once")
            txt = txt.replace(old, new)
        if sha(body(txt)) != v["used_sha256"]:
            raise SystemExit(f"PG{gid}: the edited body does not have the sha256 used")
        os.replace(p, os.path.join(src, f"PG{gid}", "original_current.txt"))
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        print(f"PG{gid}: {len(v['edits'])} edits applied; body now has the sha256 used")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
