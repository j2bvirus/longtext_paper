"""How much do reader contexts change between reruns because of Python's hash seed? (offline: cached memories and embeddings only, no model or GPU call.)

dump:    PYTHONHASHSEED=<s> python methods/tiebreak_context_check.py dump <dataset> <out.json> [density]
         rebuilds the context of every question for each method and stores the ordered paragraph labels (¶ numbers)
         and an md5 of the full context text.
compare: python methods/tiebreak_context_check.py compare <a.json> <b.json>
         counts, per method, the questions whose paragraph list differs and whose full context text differs, and
         whether CMM v4 and CMM v4 without the statement pack the same paragraphs within each run.
"""
import hashlib
import json
import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = "claude:claude-haiku-4-5-20251001"
PARA = re.compile(r"¶(\d+)")
METHODS = ["mem:cmm4", "mem:cmm4n", "mem:cmm4a", "hybrid", "bm25", "mem:pbm25", "mem:namegrep", "mem:namegrep_co"]


def dump(ds, out, d):
    import core  # noqa: E402
    import llm  # noqa: E402
    import run_eval  # noqa: E402

    def _no(*a, **k):
        raise RuntimeError("offline check: a model or embedding call would be needed")
    llm.embed = _no
    llm.call = _no
    os.environ["MEM_WAIT_ONLY"] = "1"
    ddir = os.path.join(ROOT, "data", ds)
    text, spans, qs, world = core.load_dataset(ddir, d)
    qs = [q for q in qs if not q.get("excluded")]
    chunks = core.chunk_record(text, 300)
    idx = {"bm25": core.BM25Index(chunks),
           "dense": core.DenseIndex(chunks, os.path.join(ddir, f"emb_{d}_c300.npy"), llm.embed)}
    import memory  # noqa: E402
    res = {}
    for meth in METHODS:
        mem = None
        if meth.startswith("mem:"):
            mem = memory.make(meth[4:], text=text, chunks=chunks, ddir=ddir, density=d,
                              args=types.SimpleNamespace(builder=H, build_workers=1, budget=4000, num_ctx=16384))
            mem.build()
        for q in qs:
            ctx, used = run_eval.build_context(meth, q, chunks, spans, 4000, idx, mem)
            res.setdefault(meth, {})[q["qid"]] = {"paras": [int(x) for x in PARA.findall(ctx)],
                                                  "md5": hashlib.md5(ctx.encode("utf-8")).hexdigest()}
    json.dump({"seed": os.environ.get("PYTHONHASHSEED"), "python": sys.version.split()[0], "ds": ds, "density": d,
               "res": res}, open(out, "w"))
    print("dumped", ds, d, "seed", os.environ.get("PYTHONHASHSEED"))


def compare(fa, fb):
    a, b = json.load(open(fa)), json.load(open(fb))
    print(f"{a['ds']} {a['density']}: seed {a['seed']} vs {b['seed']} (Python {a['python']} / {b['python']})")
    print("| method | questions | paragraph list differs | full context text differs |")
    print("|---|---|---|---|")
    for m in METHODS:
        x, y = a["res"][m], b["res"][m]
        qs = sorted(set(x) & set(y))
        print(f"| {m} | {len(qs)} | {sum(x[q]['paras'] != y[q]['paras'] for q in qs)} | "
              f"{sum(x[q]['md5'] != y[q]['md5'] for q in qs)} |")
    for run in (a, b):
        v4, nc = run["res"]["mem:cmm4"], run["res"]["mem:cmm4n"]
        print(f"seed {run['seed']}: CMM v4 and no-statement pack the same paragraphs in "
              f"{sum(v4[q]['paras'] == nc[q]['paras'] for q in v4)} of {len(v4)} questions")


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        dump(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "d16")
    else:
        compare(sys.argv[2], sys.argv[3])
