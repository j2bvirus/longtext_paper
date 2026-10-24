"""Run one (dataset, density, method, reader, budget) cell of the benchmark.

Every method gets the same reader prompt and the same per-question reader-token
budget (except FULL, which by definition reads everything, and ORACLE, which
reads only the gold-evidence chunks).  Results are appended per question.
"""
import argparse
import collections
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

READER_SYSTEM = (
    "You answer questions about a long chronological story record. You are given excerpts from the "
    "record (each labeled with its chapter) and sometimes memory notes derived from it. Use only this "
    "material. When a state changes over time (people move, marry, die, change trade, give things away), "
    "the latest information wins. Rumors, gossip and unrealized plans are not facts. If the material gives "
    "no information about what is asked, answer 'unknown'; otherwise answer from the latest relevant "
    "information in the material, even if later changes cannot be ruled out. Think briefly if needed, then "
    "give the final answer on "
    "the last line exactly as: Answer: <answer>. For a person, give the full name."
)
READER_VARIANTS = {
    "default": READER_SYSTEM,
    # no guidance about states, rumors or abstention
    "minimal": ("Answer the question using the material provided. Give the final answer on the last line exactly as: "
                "Answer: <answer>. For a person, give the full name."),
    # answer-time state tracing (re-implementation of StateMemWrapper, Fan et al. 2026, Section 6.4 / App. F.1,
    # applied to the memory context because whole records do not fit the window)
    "statetrace": ("You answer questions about a long chronological record from the excerpts given (each labeled with "
                   "its chapter and paragraph number) and any memory notes. Work in two committed sections.\n"
                   "Section 1 - TRACE (at most 250 words): in chronological order, list every paragraph that establishes, "
                   "updates or supersedes the entities the question touches, citing each as [para N]; include the standing "
                   "rules that govern the decision and the most recent stated value of every input those rules apply to; "
                   "note derived values whose inputs later changed; end with the current operative value of each relevant "
                   "entity. Commit to this trace before answering.\n"
                   "Section 2 - RESOLVE: answer under four precedence rules: later supersedes earlier; standing rules "
                   "outrank past instances, applied to current inputs; derived values are recomputed, never quoted; a fact "
                   "is retired only by explicit supersession or expiry. Rumors and unrealized plans are not facts. If the "
                   "material gives no information about what is asked, answer 'unknown'. End with one final line exactly "
                   "as: Answer: <answer>. For a person, give the full name."),
    # domain-neutral wording that discourages abstention
    "decisive": ("You are given excerpts from a long record and possibly notes derived from it. Answer the question from "
                 "them. When facts change, prefer the most recent information. Treat reported rumors and plans as "
                 "unconfirmed. Answer 'unknown' only if nothing in the material relates to the question; otherwise give "
                 "your best answer. Give the final answer on the last line exactly as: Answer: <answer>. For a person, "
                 "give the full name."),
}


def build_context(method, q, chunks, spans, budget, idx, mem=None):
    """Return (context_text, chunks_used)."""
    if method == "closedbook":  # no record at all: measures what the reader already knows
        return "(No excerpts are provided. Answer from your own knowledge of the work if you can.)", []
    if method == "full":
        used = chunks
        return core.render_chunks(used), used
    if method == "recent":
        used, tot = [], 0
        for c in reversed(chunks):
            if tot + c["tokens"] > budget:
                break
            used.append(c)
            tot += c["tokens"]
        return core.render_chunks(used), used
    if method in ("oracle", "oracle_plain"):
        ev = q["evidence"]
        used = []
        for e in ev:
            st, en = spans[e]
            for c in chunks:
                if c["start"] <= st < c["end"] or c["start"] < en <= c["end"]:
                    if c not in used:
                        used.append(c)
        ctx = core.render_chunks(used)
        if method == "oracle":
            ctx = ("[Memory guarantee: the excerpts below are ALL passages of the record that are relevant to "
                   "the question. Anything not shown here did not happen.]\n\n" + ctx)
        return ctx, used
    if method in ("oracle_para", "oracle_para_cert"):
        # paragraph-level oracle: only the paragraphs that contain gold evidence
        import cmm as _cmm
        if not hasattr(build_context, "_paras"):
            build_context._paras = _cmm.Paras(chunks)
        P = build_context._paras
        pids = [p["pid"] for p in P.items for e in q["evidence"]
                if p["start"] <= spans[e][0] < p["end"] or p["start"] < spans[e][1] <= p["end"]]
        ctx = P.render(pids)
        if method == "oracle_para_cert":
            ctx = ("[Memory guarantee: the paragraphs below are ALL passages of the record that are relevant to "
                   "the question. Anything not shown here did not happen.]\n" + ctx)
        return ctx, P.spans(pids)
    if method in ("bm25", "dense", "hybrid", "hybrid_cert"):
        if method == "bm25":
            s = idx["bm25"].scores(q["question"])
        elif method == "dense":
            s = idx["dense"].scores(q["question"])
        else:
            s = core.rrf([idx["bm25"].scores(q["question"]), idx["dense"].scores(q["question"])])
        order = sorted(range(len(chunks)), key=lambda i: -s[i])
        used = core.take_budget(chunks, order, budget)
        ctx = core.render_chunks(used)
        if method == "hybrid_cert":  # control: the same retrieval with an (unverified) completeness claim
            ctx = ("[Memory guarantee: the excerpts below are ALL passages of the record that are relevant to "
                   "the question. Anything not shown here did not happen.]\n\n" + ctx)
        return ctx, used
    if method.startswith("mem:"):
        return mem.context(q, budget)
    raise ValueError(method)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="saga_s1")
    ap.add_argument("--density", default="d1")
    ap.add_argument("--method", required=True)
    ap.add_argument("--reader", default="ollama:qwen3:8b")
    ap.add_argument("--budget", type=int, default=4000)
    ap.add_argument("--chunk", type=int, default=300)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--qtypes", default="")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--num_ctx", type=int, default=16384)
    ap.add_argument("--tag", default="")
    ap.add_argument("--sample", default="", help="file with qids to use")
    ap.add_argument("--builder", default="", help="LLM that builds write-time memory")
    ap.add_argument("--build_workers", type=int, default=8)
    ap.add_argument("--wait_only", action="store_true", help="never build memories; wait for them")
    ap.add_argument("--cmm_abl", default="", help="CMM storage-time ablation switches (read-only)")
    ap.add_argument("--qboth", action="store_true",
                    help="also place the question BEFORE the context (Lost in the Middle mitigation); adds _qboth")
    ap.add_argument("--escalate_unknown", type=int, default=0,
                    help="model-side trigger baseline: if the first answer is 'unknown', rebuild the context at this "
                         "multiple of the budget and ask again (adds _escU<k> to the tag)")
    ap.add_argument("--prompt", default="default", choices=sorted(READER_VARIANTS),
                    help="reader instruction variant (prompt-sensitivity check); non-default adds _p-<name> to the tag")
    args = ap.parse_args()
    if args.wait_only:
        os.environ["MEM_WAIT_ONLY"] = "1"
    if args.cmm_abl:
        os.environ["CMM_ABL"] = args.cmm_abl
        os.environ["MEM_WAIT_ONLY"] = "1"
        args.tag = args.tag + "_abl-" + args.cmm_abl.replace(",", "+")
    if args.prompt != "default":
        args.tag = args.tag + "_p-" + args.prompt
    if args.escalate_unknown:
        args.tag = args.tag + f"_escU{args.escalate_unknown}"
    if args.qboth:
        args.tag = args.tag + "_qboth"

    ddir = os.path.join(ROOT, "data", args.data)
    text, spans, qs, world = core.load_dataset(ddir, args.density)
    chunks = core.chunk_record(text, args.chunk)
    persons_by_first = collections.Counter(p["first"].lower() for p in world["persons"].values())
    all_names = {f"{p['first']} {p['surname']}".lower() for p in world["persons"].values()}
    if args.qtypes:
        keep = set(args.qtypes.split(","))
        qs = [q for q in qs if q["qtype"] in keep]
    if args.sample:
        keep = set(open(args.sample).read().split())
        qs = [q for q in qs if q["qid"] in keep]
    if args.limit:
        qs = qs[: args.limit]

    idx = {}
    t_build = time.time()
    build = {"embed_tokens": 0, "llm_in": 0, "llm_out": 0, "usd": 0.0, "wall_s": 0.0}
    if args.method in ("bm25", "hybrid", "hybrid_cert"):
        idx["bm25"] = core.BM25Index(chunks)
    if args.method in ("dense", "hybrid", "hybrid_cert"):
        cache = os.path.join(ddir, f"emb_{args.density}_c{args.chunk}.npy")
        idx["dense"] = core.DenseIndex(chunks, cache, llm.embed)
        build["embed_tokens"] = sum(c["tokens"] for c in chunks)
    mem = None
    if args.method.startswith("mem:"):
        import memory  # noqa: E402
        mem = memory.make(args.method[4:], text=text, chunks=chunks, ddir=ddir, density=args.density,
                          args=args)
        build.update(mem.build())
    build["wall_s"] = time.time() - t_build

    name = f"{args.data}_{args.density}_{args.method.replace(':', '-')}_{args.reader.replace(':', '-')}_b{args.budget}{args.tag}"
    out_dir = os.path.join(ROOT, "runs", "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, name + ".jsonl")
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["qid"] for l in open(out_path, encoding="utf-8")}

    def one(q):
        ctx, used = build_context(args.method, q, chunks, spans, args.budget, idx, mem)
        prompt = (f"Question (keep it in mind while reading): {q['question']}\n\n" if args.qboth else "") + f"{ctx}\n\nQuestion: {q['question']}"
        system = READER_VARIANTS[args.prompt] if args.method != "closedbook" else (
            "You answer questions about a well-known novel from your own knowledge of it. Think briefly if needed, "
            "then give the final answer on the last line exactly as: Answer: <answer>.")
        mt = 800 if args.prompt == "statetrace" else 400
        r = llm.call(args.reader, system, prompt, max_tokens=mt, num_ctx=args.num_ctx,
                     tag=f"read|{name}|{q['qid']}")
        pred = core.parse_answer(r["text"])
        escalated, extra_tok = False, 0
        if args.escalate_unknown and pred.strip().lower().rstrip(".") in ("unknown", ""):
            extra_tok = core.ntok(prompt)
            ctx, used = build_context(args.method, q, chunks, spans, args.budget * args.escalate_unknown, idx, mem)
            prompt = (f"Question (keep it in mind while reading): {q['question']}\n\n" if args.qboth else "") + f"{ctx}\n\nQuestion: {q['question']}"
            r2 = llm.call(args.reader, system, prompt, max_tokens=mt, num_ctx=args.num_ctx,
                          tag=f"read|{name}|{q['qid']}|esc")
            r = dict(r2, in_tokens=r2["in_tokens"] + r["in_tokens"], out_tokens=r2["out_tokens"] + r["out_tokens"],
                     usd=r2["usd"] + r["usd"], wall_s=r2["wall_s"] + r["wall_s"])
            pred = core.parse_answer(r["text"])
            escalated = True
        ok = core.score(pred, q["answer"], persons_by_first, all_names)
        rec = {"qid": q["qid"], "qtype": q["qtype"], "gold": q["answer"]["gold"], "pred": pred, "correct": ok,
               "raw": r["text"][-2000:], "ctx_tokens": core.ntok(prompt) + extra_tok, "escalated": escalated,
               "in_tokens": r["in_tokens"],
               "out_tokens": r["out_tokens"], "usd": r["usd"], "wall_s": r["wall_s"], "cached": r["cached"],
               "truncated": r.get("truncated", False),
               "ev_recall": core.evidence_recall(q, spans, used) if not args.method.startswith("mem:") or used else None,
               "n_chunks": len(used),
               "certified": "Memory guarantee" in ctx,
               "core_recall": core.evidence_recall({"evidence": q.get("evidence_core", q["evidence"])}, spans, used)
               if used else None}
        return rec

    todo = [q for q in qs if q["qid"] not in done]
    with open(out_path, "a", encoding="utf-8") as f:
        if args.workers > 1:
            with ThreadPoolExecutor(args.workers) as ex:
                for rec in ex.map(one, todo):
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    f.flush()
        else:
            for q in todo:
                rec = one(q)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
    if mem is not None and hasattr(mem, "final_cost"):
        build.update(mem.final_cost())
    recs = [json.loads(l) for l in open(out_path, encoding="utf-8")]
    by = collections.defaultdict(list)
    for r in recs:
        by[r["qtype"]].append(r["correct"])
    summ = {"name": name, "n": len(recs), "acc": sum(r["correct"] for r in recs) / max(1, len(recs)),
            "by_qtype": {k: round(sum(v) / len(v), 3) for k, v in sorted(by.items())},
            "mean_ctx_tokens": sum(r["ctx_tokens"] for r in recs) / max(1, len(recs)),
            "sum_in_tokens": sum(r["in_tokens"] for r in recs), "sum_out_tokens": sum(r["out_tokens"] for r in recs),
            "sum_usd": sum(r["usd"] for r in recs), "sum_wall_s": sum(r["wall_s"] for r in recs),
            "build": build, "record_tokens": sum(c["tokens"] for c in chunks), "n_chunks": len(chunks)}
    rr = [r["ev_recall"] for r in recs if r.get("ev_recall") is not None]
    if rr:
        summ["mean_ev_recall"] = sum(rr) / len(rr)
    json.dump(summ, open(os.path.join(out_dir, name + ".summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
