"""Put the removed question and gold-answer text back into the released result files of third-party benchmarks.
Run it in the release after preparing the third-party data (release/THIRD_PARTY_DATA.md) and before
release/reproduce_tables.py.

python release/restore_third_party_fields.py [--check]

release/STRIPPED_FILES.tsv (written when the release was made) lists every result file whose question and gold-answer
fields were set to null, with the sha256 the file had before (after its model answers were screened for quoted
source text), its line ending and the JSON layout of each line. For
each file the fields are filled again from the prepared data by question identifier:
  runs/results_oolong/<split>_*.jsonl                question, answer  <- data/_external/oolong_real/<split>/questions.jsonl (id)
  runs/results/<dataset>_*.jsonl (ama_, nhq_, locomo_)  gold  <- data/<dataset>/questions_GOLD.jsonl (qid, answer['gold'])
The file is then written in its original layout and its sha256 must equal the recorded one, so a different version of
the third-party data, a missing or duplicated question, or a wrong match fails. --check only reports, writing nothing.
Exit code 1 if any file fails.
"""
import collections
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = "--check" in sys.argv
_src = {}


def source(r):
    """(question rows by identifier, identifier field, duplicated identifiers) for result file r."""
    name = os.path.basename(r)
    if r.startswith("runs/results_oolong/"):
        p, key = os.path.join("data", "_external", "oolong_real", name.split("_")[0], "questions.jsonl"), "id"
    else:
        parts, ds = name.split("_"), None
        for i in range(len(parts), 0, -1):
            if os.path.isdir(os.path.join(ROOT, "data", "_".join(parts[:i]))):
                ds = "_".join(parts[:i])
                break
        if ds is None:
            raise FileNotFoundError(f"no prepared data folder for {r}")
        p, key = os.path.join("data", ds, "questions_GOLD.jsonl"), "qid"
    if p not in _src:
        rows = [json.loads(l) for l in open(os.path.join(ROOT, p), encoding="utf-8") if l.strip()]
        ids = collections.Counter(q[key] for q in rows)
        _src[p] = ({q[key]: q for q in rows}, key, sorted(k for k, v in ids.items() if v > 1), p)
    return _src[p]


def value(r, q, k):
    if k == "gold" and not r.startswith("runs/results_oolong/"):
        a = q["answer"]
        return a.get("gold") if isinstance(a, dict) else a
    return q[k]


def main():
    listing = os.path.join(ROOT, "release", "STRIPPED_FILES.tsv")
    rows = [l.rstrip("\n").split("\t") for l in open(listing, encoding="utf-8") if l.strip() and not l.startswith("#")]
    ok, fails = 0, []
    for r, want, nl, modes, fields in rows:
        fields = fields.split(",")
        try:
            src, key, dup, p = source(r)
        except (OSError, FileNotFoundError) as e:
            fails.append(f"{r}: prepared data missing ({e})")
            continue
        text = open(os.path.join(ROOT, r), "rb").read().decode("utf-8")
        if not text and not modes:  # a condition that produced no answers
            if hashlib.sha256(b"").hexdigest() == want:
                ok += 1
            else:
                fails.append(f"{r}: empty in the release but not before")
            continue
        lines = text.replace("\r\n", "\n").split("\n")
        tail = lines[-1] == ""
        lines = lines[:-1] if tail else lines
        if len(lines) != len(modes):
            fails.append(f"{r}: {len(lines)} lines, {len(modes)} recorded")
            continue
        out, err = [], None
        for line, mode in zip(lines, modes):
            x = json.loads(line)
            ident = x.get(key)
            if ident in dup:
                err = f"identifier {ident} occurs more than once in {p}"
                break
            if ident not in src:
                err = f"identifier {ident} not in {p}"
                break
            for k in fields:
                if k in x and x[k] is None:
                    x[k] = value(r, src[ident], k)
            out.append(json.dumps(x, ensure_ascii=mode == "a"))
        if err:
            fails.append(f"{r}: {err}")
            continue
        sep = "\r\n" if nl == "crlf" else "\n"
        data = (sep.join(out) + (sep if tail else "")).encode("utf-8")
        if hashlib.sha256(data).hexdigest() != want:
            fails.append(f"{r}: restored file differs from the original (sha256)")
            continue
        if not CHECK:
            open(os.path.join(ROOT, r), "wb").write(data)
        ok += 1
    print(f"{ok} of {len(rows)} files restored{' (check only)' if CHECK else ''} with the original sha256")
    for f in fails[:50]:
        print("FAIL", f)
    if len(fails) > 50:
        print(f"... and {len(fails) - 50} more")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
