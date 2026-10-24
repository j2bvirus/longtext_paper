"""Precompute dense embeddings for every density (GPU job, run alone)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core, llm
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = sys.argv[1]
for d in sys.argv[2:]:
    ddir = os.path.join(ROOT, "data", data)
    text = open(os.path.join(ddir, f"record_{d}.txt"), encoding="utf-8").read()
    chunks = core.chunk_record(text, 300)
    t0 = time.time()
    core.DenseIndex(chunks, os.path.join(ddir, f"emb_{d}_c300.npy"), llm.embed)
    print(d, len(chunks), "chunks", round(time.time() - t0, 1), "s", flush=True)
