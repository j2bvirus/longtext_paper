"""Build the added baselines (methods/addedbase.py) for some datasets, in two phases:
  1. LLM phase (GPT through Codex, no GPU): HippoRAG 2 open triples, contextual chunk headers;
  2. embedding phase (Ollama qwen3-embedding:0.6b; through an optional GPU scheduler): paragraph,
     header-chunk, phrase and triple embeddings, and every question of the dataset (data/<ds>/qemb_added.json).
Records shared between datasets are built once (cache keyed by record text).

python methods/build_added.py --data saga_v5_s7,saga_v5_s8 [--density d16] [--methods hippo2,ctxhdr,s2b] [--phase both|llm|embed]
"""
import argparse
import json
import os
import subprocess
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addedbase  # noqa: E402
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "gpu_control", "gpu_gate.py")


def objects(ds, density, methods, workers):
    ddir = os.path.join(ROOT, "data", ds)
    text, spans, qs, world = core.load_dataset(ddir, density)
    chunks = core.chunk_record(text, 300)
    args = types.SimpleNamespace(builder=addedbase.BUILDER_DEFAULT, build_workers=workers)
    return ddir, qs, [addedbase.REGISTRY[m](text, chunks, ddir, density, args) for m in methods]


def embed_questions(ddir, qs):
    p = os.path.join(ddir, "qemb_added.json")
    have = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    todo = sorted({q["question"] for q in qs} - set(have))
    if todo:
        for qtext, v in zip(todo, llm.embed(todo)):
            have[qtext] = v
        json.dump(have, open(p, "w", encoding="utf-8"))
    return len(todo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--density", default="d16")
    ap.add_argument("--methods", default="hippo2,ctxhdr,s2b")
    ap.add_argument("--phase", default="both", choices=["both", "llm", "embed"])
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    sets = [objects(ds, a.density, a.methods.split(","), a.workers) for ds in a.data.split(",")]
    if a.phase in ("both", "llm"):
        for ddir, _, objs in sets:
            for o in objs:
                o.build_llm()
                print("llm phase done:", os.path.basename(ddir), o.name, flush=True)
    if a.phase in ("both", "embed"):
        # ask for GPU 0; if both cards are free, use both at once.  One Ollama server per free GPU, pinned with CUDA_VISIBLE_DEVICES, and the
        # embedding batches split dynamically between them (llm.embed_multi).
        sys.path.insert(0, os.path.dirname(GATE))
        try:  # optional GPU scheduler; without it, GPU 0 is used directly
            import gpu_gate
        except ImportError:
            gpu_gate = None
        free = gpu_gate.request("build_added.py embeddings (longtextpaper)", gpus=(0,)) if gpu_gate else [0]
        procs = []
        try:
            procs, hosts = start_servers(free)
            llm.EMBED_HOSTS = hosts
            for ddir, qs, objs in sets:
                print("questions embedded:", os.path.basename(ddir), embed_questions(ddir, qs), flush=True)
                for o in objs:
                    print("built:", os.path.basename(ddir), o.name, json.dumps(o.build()), flush=True)
        finally:
            llm.EMBED_HOSTS = []
            for p in procs:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            if gpu_gate:
                gpu_gate.release()


def start_servers(gpus):
    """one 'ollama serve' per GPU on its own port; checks with nvidia-smi that each server's model is on its GPU"""
    import time
    import requests
    procs, hosts = [], []
    log = open(os.path.join(ROOT, "runs", "_added_ollama_servers.log"), "a")
    for g in gpus:
        port = 11440 + g
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g), OLLAMA_HOST=f"127.0.0.1:{port}")
        procs.append(subprocess.Popen(["ollama", "serve"], env=env, stdout=log, stderr=log,
                                      creationflags=0x00000200))
        hosts.append(f"http://127.0.0.1:{port}")
    for h in hosts:
        for _ in range(60):
            try:
                if requests.get(f"{h}/api/tags", timeout=5).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(2)
        llm.embed_multi(["warm-up"], [h])
    uu = dict(x.split(", ") for x in subprocess.run(["nvidia-smi", "--query-gpu=uuid,index", "--format=csv,noheader"],
                                                     capture_output=True, text=True).stdout.splitlines() if x)
    apps = subprocess.run(["nvidia-smi", "--query-compute-apps=gpu_uuid,process_name", "--format=csv,noheader"],
                          capture_output=True, text=True).stdout.splitlines()
    on = sorted({int(uu[a.split(", ")[0]]) for a in apps if "llama" in a.lower() or "ollama" in a.lower()})
    print(f"granted GPUs {gpus}; Ollama servers {hosts}; GPUs holding an Ollama runner now {on}", flush=True)
    return procs, hosts


if __name__ == "__main__":
    main()
