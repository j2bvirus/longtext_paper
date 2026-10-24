"""Filler-without-names variant: the same world, events, event text and questions as an
existing LongState-Saga world, but every filler unit is a public-domain prose paragraph (prose_ratio=1.0),
so filler never names a character.  Separates record length from distractor mentions of the queried people.

python bench/nonames_variant.py --seed 7 --src data/saga_v5_s7 --out data/saga_v5n_s7 --target d16 --densities 8,10,12,16 \
       --prose <same prose files as the source world>
Writes record_<tag>.txt / spans_<tag>_GOLD.json for the density whose length is closest to the source
record at --target (renamed to that target tag), and copies questions, world and events from --src.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import saga  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", default="d16")
    ap.add_argument("--densities", default="8,10,12,16")
    ap.add_argument("--prose", nargs="*", default=[])
    a = ap.parse_args()
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    src_text = open(os.path.join(a.src, f"record_{a.target}.txt"), encoding="utf-8").read()
    target_tok = len(enc.encode(src_text, disallowed_special=()))
    w = saga.World(a.seed, n_families=10, n_chapters=40)
    sim = saga.Sim(w)
    sim.run()
    pool = saga.load_prose_pool(a.prose)
    best = None
    for d in [float(x) for x in a.densities.split(",")]:
        text, spans = saga.assemble(sim, d, pool, prose_ratio=1.0)
        n = len(enc.encode(text, disallowed_special=()))
        print(f"d{d:g}: {n:,} tokens (target {target_tok:,})")
        if best is None or abs(n - target_tok) < abs(best[2] - target_tok):
            best = (d, (text, spans), n)
    d, (text, spans), n = best
    src_spans = json.load(open(os.path.join(a.src, f"spans_{a.target}_GOLD.json")))
    same = sum(1 for e, (s0, e0) in src_spans.items() if e in spans and
               src_text[s0:e0] == text[spans[e][0]:spans[e][1]])
    print(f"chosen d{d:g} ({n:,} tokens); event texts identical to source: {same}/{len(src_spans)}")
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, f"record_{a.target}.txt"), "w", encoding="utf-8").write(text)
    json.dump(spans, open(os.path.join(a.out, f"spans_{a.target}_GOLD.json"), "w"), indent=0)
    for f in ("questions_GOLD.jsonl", "world_GOLD.json", "events_GOLD.json", "questions_reader.jsonl"):
        if os.path.exists(os.path.join(a.src, f)):
            shutil.copy(os.path.join(a.src, f), os.path.join(a.out, f))
    json.dump({a.target: {"tokens_cl100k": n, "chars": len(text), "sha256": hashlib.sha256(text.encode()).hexdigest(),
                          "filler_density": d, "prose_ratio": 1.0, "source": a.src}},
              open(os.path.join(a.out, "stats.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
