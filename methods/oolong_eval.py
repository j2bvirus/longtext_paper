"""Oolong-real evaluation.

python methods/oolong_eval.py --split validation --method index|full|bm25|closed --reader claude:claude-haiku-4-5-20251001
       [--max_eps 4] [--per_window 0] [--workers 6] [--budget 4000]

Methods
  index   event-table index (methods/oolong_index.py, v2): one routing call maps the question to the event kind
          (rolls or spells) and the episode range (a single episode, the episodes up to k, or the whole window); the
          complete aggregates of that range are computed from the episode tables and given to the reader under a
          statement that they come from a complete index of the transcripts
  full    the whole window text (as the benchmark gives it), when it fits the reader
  bm25    paragraph-free BM25 over 300-token chunks of the window, up to the budget, in record order
  closed  no context (contamination probe)
Every reader answers with the benchmark's own instruction (final answer in \\boxed{}); scoring is the official one
(methods/oolong_score.py).  Results: runs/results_oolong/<split>_<method>_<reader>.jsonl.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import llm  # noqa: E402
import oolong_index as oi  # noqa: E402
import oolong_score  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "_external", "oolong_real")
OUT = os.path.join(ROOT, "runs", "results_oolong")


def line_chunks(text, target=300):
    """300-token chunks packed line by line, (core.chunk_record packs blank-line
    paragraphs, and a transcript has almost none, so a whole episode (~50k tokens) would become one chunk over the budget).  A line longer than the target is cut into target-sized pieces.
    Each chunk knows its episode (the number of '[START OF EPISODE]' markers before it; 0 = the header)."""
    out, cur, cur_tok, pos = [], [], 0, 0
    # only marker lines count: the instruction header itself mentions '[START OF EPISODE]' inside a sentence
    starts = [m.start() for m in re.finditer(r"(?m)^\[START OF EPISODE\][ \t]*$", text)]

    def flush():
        nonlocal cur, cur_tok
        if cur:
            st, en = cur[0][0], cur[-1][1]
            body = text[st:en]
            out.append({"cid": len(out), "start": st, "end": en, "episode": sum(1 for s in starts if s <= st),
                        "text": body, "tokens": core.ntok(body)})
        cur, cur_tok = [], 0
    for m in re.finditer(r"[^\n]*\n?", text):
        st, en = m.start(), m.end()
        if st == en:
            break
        t = core.ntok(text[st:en])
        if t > target:  # a very long line: its own pieces
            flush()
            ids = core.ENC.encode(text[st:en], disallowed_special=())
            p = st
            for k in range(0, len(ids), target):
                piece = core.ENC.decode(ids[k:k + target])
                cur, cur_tok = [(p, p + len(piece))], len(ids[k:k + target])
                flush()
                p += len(piece)
            continue
        if cur and cur_tok + t > target:
            flush()
        cur.append((st, en))
        cur_tok += t
    flush()
    return out


def render_line_chunks(chunks):
    return "\n\n".join(f"[Excerpt {c['cid']} | {'Episode ' + str(c['episode']) if c['episode'] else 'Header'}]\n"
                       f"{c['text'].strip()}" for c in sorted(chunks, key=lambda x: x["cid"]))
READER_SYS = ("You answer a question about the statistics of a Dungeons and Dragons game (dice rolls and spells) "
              "from the material given. Do not try to guess, estimate or approximate the result. Do step-by-step "
              "reasoning if needed. Return the final answer in \\boxed{}. For a list, give the items separated by "
              "commas inside the box.")
ROUTE_SYS = ("You route a question about a Dungeons and Dragons game transcript to an index of events. The context "
             "window holds {n} episode transcripts, numbered 1 to {n} in order. Answer with one line of JSON only: "
             "{{\"kind\": \"rolls\" or \"spells\", \"scope\": \"all\" or \"episode\" or \"upto\", \"k\": <episode "
             "number or null>}}. scope 'episode' = only episode k; 'upto' = episodes 1 to k cumulatively (e.g. 'by "
             "the end of episode k'); 'all' = the whole window (also for 'this episode' when there is one episode).")


def window_episodes(split, wid):
    text = open(os.path.join(DATA, split, "windows", wid + ".txt"), encoding="utf-8").read()
    pmap, eps = oi.split_window(text)
    return text, pmap, eps


def route(q, n, builder):
    r = llm.call(builder, ROUTE_SYS.format(n=n), q["question"], max_tokens=60, tag=f"build|oolong_route|{q['id']}")
    m = re.search(r"\{.*\}", r["text"], re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except ValueError:
        d = {}
    kind = d.get("kind") if d.get("kind") in ("rolls", "spells") else ("spells" if "spell" in q["question"].lower()
                                                                     else "rolls")
    scope = d.get("scope") if d.get("scope") in ("all", "episode", "upto") else "all"
    k = d.get("k") if isinstance(d.get("k"), int) else None
    if scope != "all" and (k is None or not 1 <= k <= n):
        scope, k = "all", None
    return kind, scope, k


def fmt_counter(c, top=60):
    return ", ".join(f"{k} {v}" for k, v in c.most_common(top)) or "none"


def index_context(tables, kind, scope, k, budget):
    n = len(tables)
    eps = [k] if scope == "episode" else (list(range(1, k + 1)) if scope == "upto" else list(range(1, n + 1)))
    rows = [(e, x) for e in eps for x in tables[e - 1][kind]]
    what = "die rolls" if kind == "rolls" else "spells cast"
    rng = (f"episode {k}" if scope == "episode" else f"episodes 1 to {k}" if scope == "upto" else
           (f"all {n} episodes" if n > 1 else "this episode"))
    lines = [f"[Event index: every {what[:-1] if what.endswith('s') else what} found in the transcripts of {rng}, from a "
             f"complete index of the window's {n} episode(s) built when the transcripts were read. The counts below "
             f"cover the whole range.]",
             f"Total {what} in {rng}: {len(rows)}"]
    if n > 1:
        per = Counter(e for e, _ in rows)
        lines.append("Per episode: " + ", ".join(f"episode {e} {per.get(e, 0)}" for e in eps))
    lines.append("By character: " + fmt_counter(Counter(x["character_filled"] for _, x in rows)))
    lines.append("By player: " + fmt_counter(Counter(x["player"] for _, x in rows)))
    if kind == "rolls":
        lines.append("By roll type: " + fmt_counter(Counter(x["type"] for _, x in rows)))
        nat = Counter(x["natural"] for _, x in rows if x["natural"] != "-")
        lines.append("By natural die value (where stated): " + fmt_counter(nat) +
                     f"; rolls without a stated natural value: {sum(1 for _, x in rows if x['natural'] == '-')}")
    else:
        lines.append("By spell: " + fmt_counter(Counter(x["spell"] for _, x in rows)))
        seq = [f"{x['spell']} (episode {e}, {x['character_filled']})" for e, x in rows]
        lines.append("Spells in order of casting: " + "; ".join(seq))
    ctx = "\n".join(lines)
    if core.ntok(ctx) > budget:
        ctx = core.ENC.decode(core.ENC.encode(ctx)[:budget])
    return ctx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="validation")
    ap.add_argument("--method", required=True)
    ap.add_argument("--reader", default="claude:claude-haiku-4-5-20251001")
    ap.add_argument("--builder", default="claude:claude-haiku-4-5-20251001")
    ap.add_argument("--max_eps", type=int, default=99)
    ap.add_argument("--per_window", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--budget", type=int, default=4000)
    ap.add_argument("--tag", default="")
    ap.add_argument("--version", default="v2", choices=["v2", "v3"], help="index version (v3: v2 plus a recall recheck)")
    a = ap.parse_args()
    qs = [json.loads(l) for l in open(os.path.join(DATA, a.split, "questions.jsonl"), encoding="utf-8")]
    byw = defaultdict(list)
    for q in qs:
        if len(q["episodes"]) <= a.max_eps:
            byw[q["context_window_id"]].append(q)
    if a.per_window:
        byw = {w: sorted(v, key=lambda q: q["id"])[:a.per_window] for w, v in byw.items()}
    os.makedirs(OUT, exist_ok=True)
    name = f"{a.split}_{a.method}_{a.reader.replace(':', '-')}{a.tag}"
    out = os.path.join(OUT, name + ".jsonl")
    done = {json.loads(l)["id"] for l in open(out, encoding="utf-8")} if os.path.exists(out) else set()
    for wid, wq in sorted(byw.items(), key=lambda kv: len(kv[1][0]["episodes"])):
        todo = [q for q in wq if q["id"] not in done]
        if not todo:
            continue
        text, pmap, eps = window_episodes(a.split, wid)
        idx_fn = oi.index_episode_v3 if a.version == "v3" else oi.index_episode_v2
        tables = [idx_fn(ep, a.builder) for ep in eps] if a.method == "index" else None
        chunks = line_chunks(text, 300) if a.method == "bm25" else None
        bm = core.BM25Index(chunks) if chunks else None

        def one(q):
            if a.method == "index":
                kind, scope, k = route(q, len(eps), a.builder)
                ctx = index_context(tables, kind, scope, k, a.budget)
                extra = {"route": [kind, scope, k]}
            elif a.method == "full":
                ctx, extra = text, {}
            elif a.method == "bm25":
                s = bm.scores(q["question"])
                used = core.take_budget(chunks, sorted(range(len(chunks)), key=lambda i: -s[i]), a.budget)
                ctx, extra = render_line_chunks(used), {"bm25_chunks": len(used)}
            else:
                ctx, extra = "(No transcript is provided. Answer from what you know about this show if you can.)", {}
            prompt = f"{ctx}\n\nQuestion: {q['question']}"
            try:
                r = llm.call(a.reader, READER_SYS, prompt, max_tokens=800, tag=f"read|oolong|{name}|{q['id']}")
                txt, err = r["text"], None
            except Exception as e:  # noqa: BLE001  (e.g. a window over the reader's limit)
                # only a window over the reader's limit is a result ('infeasible'); any other failure (a
                # missing CLI binary was recorded as 1,286 answered questions) must stop the run, not be recorded
                if not any(s in str(e).lower() for s in ("prompt is too long", "context length", "context_length",
                                                         "maximum context", "too many tokens")):
                    raise
                txt, err, r = "", repr(e)[:200], {"in_tokens": 0, "out_tokens": 0}
            sc, conf = oolong_score.score(q["answer"], txt)
            return {"id": q["id"], "window": wid, "n_eps": len(eps), "question_type": q["question_type"],
                    "question": q["question"], "answer": q["answer"], "raw": txt[-1500:], "score": sc,
                    "parse": conf, "ctx_tokens": core.ntok(prompt), "error": err, **extra}
        with open(out, "a", encoding="utf-8") as f, ThreadPoolExecutor(a.workers) as ex:
            for rec in ex.map(one, todo):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
        print(f"window {wid} ({len(eps)} episodes) done", flush=True)
    recs = [json.loads(l) for l in open(out, encoding="utf-8")]
    byn = defaultdict(list)
    for r in recs:
        byn[r["n_eps"]].append(r["score"])
    print(name, "n", len(recs), "mean score", round(sum(r["score"] for r in recs) / max(1, len(recs)), 3),
          {k: round(sum(v) / len(v), 3) for k, v in sorted(byn.items())})


if __name__ == "__main__":
    main()
