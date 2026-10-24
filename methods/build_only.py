"""Build a memory (and, for 'embed', the chunk embeddings) for a dataset without answering any question.

python methods/build_only.py <dataset> <density> <memory name | embed> [builder]
  e.g.  python methods/build_only.py saga_v5_s9 d16 cmm4 claude:claude-haiku-4-5-20251001
        python methods/build_only.py saga_v5_s9 d16 embed      (uses the local embedding model on the GPU)
Prints the build summary returned by the memory (costs, sizes).
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ds, d, what = sys.argv[1], sys.argv[2], sys.argv[3]
    builder = sys.argv[4] if len(sys.argv) > 4 else "claude:claude-haiku-4-5-20251001"
    ddir = os.path.join(ROOT, "data", ds)
    text, spans, qs, world = core.load_dataset(ddir, d)
    chunks = core.chunk_record(text, 300)
    if what == "embed":
        core.DenseIndex(chunks, os.path.join(ddir, f"emb_{d}_c300.npy"), llm.embed)
        print(json.dumps({"dataset": ds, "density": d, "embedded_chunks": len(chunks)}))
        return
    import memory  # noqa: E402
    mem = memory.make(what, text=text, chunks=chunks, ddir=ddir, density=d,
                      args=types.SimpleNamespace(builder=builder, build_workers=8, budget=4000, num_ctx=16384))
    print(json.dumps({"dataset": ds, "density": d, "memory": what, "build": mem.build()}, default=str)[:2000])


if __name__ == "__main__":
    main()
