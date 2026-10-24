"""Embed every question text once (GPU job) so query-time dense retrieval never touches the GPU."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ddir = os.path.join(ROOT, "data", sys.argv[1])
qs = [json.loads(l)["question"] for l in open(os.path.join(ddir, "questions_GOLD.jsonl"), encoding="utf-8")]
vec = llm.embed(qs)
json.dump(dict(zip(qs, vec)), open(os.path.join(ddir, "qemb.json"), "w"))
print(len(qs), "question embeddings")
