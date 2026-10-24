"""Amortized cost of the event index against whole-window reading WITH provider prompt caching.  No model calls: token counts come
from the index build caches and the test run records.

For each 16/24-episode test window (gemini_web/manifest.json, W01-W20) with T window tokens and Q questions:
  index  per question = build / Q + route + reader          (build: the per-episode v2 tables, Haiku builder)
  full, no cache      = T + question
  full, cached        = (w * T + r * T * (Q - 1)) / Q + question   (first question writes the cache, the rest read it)
Output tokens are weighted by OUT (the output/input price ratio); input under cache by w (write) and r (read).
The multipliers are assumptions given on the command line, to be checked against current price pages before any
number goes into the paper.  All costs are in input-token equivalents of ONE price level: the index here is built and
read by Haiku while whole-window reading needs a 1M-context model, so a dollar comparison needs per-model prices.

python methods/oolong_cache_cost.py [--out 5] [--w 1.25] [--r 0.1] [--build_discount 1.0]
--build_discount 0.5 models building at idle time through a batch interface (half price).
"""
import argparse
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "methods"))
import core  # noqa: E402
import oolong_eval as oe  # noqa: E402
import oolong_index as oi  # noqa: E402

BUILDER = "claude:claude-haiku-4-5-20251001"


def build_cost(eps):
    """v2 build tokens of a window's episodes: (system-prompt tokens, chunk-text tokens, output tokens, recorded input).
    Input is recounted in cl100k from what the method sends (WRITE_SYS_V2 and the line-numbered chunk of each call):
    the recorded input is in Claude tokens and includes the CLI's own overhead, so it is kept apart.  Output is the
    recorded count (Claude tokens; the parsed rows are cached, not the raw replies).  None if a table is missing."""
    s = body = tout = rec = 0
    sys_tok = core.ntok(oi.WRITE_SYS_V2)
    for ep in eps:
        p = os.path.join(oi.CACHE, f"ep_{oi.ep_key(ep)}_v2_{BUILDER.replace(':', '-')}.json")
        if not os.path.exists(p):
            return None
        c = json.load(open(p, encoding="utf-8"))
        chs = oi.chunks_of(ep)
        assert len(chs) == c["chunks"]
        s += sys_tok * len(chs)
        body += sum(core.ntok("\n".join(f"L{i}: {ln}" for i, ln in ch)) for ch in chs)
        tout, rec = tout + c["cost"]["out"], rec + c["cost"]["in"]
    return s, body, tout, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=float, default=5.0, help="output/input price ratio")
    ap.add_argument("--w", type=float, default=1.25, help="cache write multiplier")
    ap.add_argument("--r", type=float, default=0.1, help="cache read multiplier")
    ap.add_argument("--build_discount", type=float, default=1.0)
    ap.add_argument("--sys_cached", action="store_true", help="the build system prompt is a cached prefix (read at r)")
    ap.add_argument("--hit", type=float, default=1.0,
                    help="share of later questions that find the whole-window cache still alive (it expires)")
    ap.add_argument("--qs", default="1,5,20,100,1000", help="question counts per window to tabulate")
    ap.add_argument("--batch", type=int, default=1,
                    help="questions answered per whole-window call (the Gemini runs asked "
                         "20 per call); the index still answers one question per call")
    a = ap.parse_args()
    man = json.load(open(os.path.join(ROOT, "gemini_web", "manifest.json")))
    recs = defaultdict(list)
    for l in open(os.path.join(ROOT, "runs", "results_oolong", "test_index_claude-claude-haiku-4-5-20251001.jsonl"),
                  encoding="utf-8"):
        x = json.loads(l)
        recs[x["window"]].append(x)
    sys_tok = core.ntok(oe.READER_SYS)
    rows = []
    for tag, m in sorted(man.items()):
        text, pmap, eps = oe.window_episodes("test", m["window"])
        T = m["cl100k_tokens"]
        b = build_cost(eps)
        rs = recs.get(m["window"], [])
        if b is None or not rs:
            print(tag, "missing build cache or run records; skipped")
            continue
        qtok = sum(core.ntok(x["question"]) for x in rs) / len(rs)
        route_in = core.ntok(oe.ROUTE_SYS.format(n=len(eps))) + qtok
        read_in = sum(x["ctx_tokens"] for x in rs) / len(rs) + sys_tok
        ans_out = sum(core.ntok(x["raw"]) for x in rs) / len(rs)  # raw is cut at 1,500 chars: a lower bound
        sys_in = (a.w + a.r * (b[0] / core.ntok(oi.WRITE_SYS_V2) - 1)) * core.ntok(oi.WRITE_SYS_V2) \
            if a.sys_cached else b[0]
        build = a.build_discount * (sys_in + b[1] + a.out * b[2])
        query_idx = route_in + a.out * 20 + read_in + a.out * ans_out
        query_full_in = T + qtok + sys_tok
        rows.append((tag, m["episodes"], T, b, build, query_idx, query_full_in, ans_out))
    qs = [int(x) for x in a.qs.split(",")]
    later = a.hit * a.r + (1 - a.hit) * a.w  # multiplier of the whole window for each question after the first
    print(f"assumptions: output x{a.out}, cache write x{a.w}, cache read x{a.r}, cache alive for {a.hit:.0%} of later "
          f"questions, build x{a.build_discount}, build system prompt cached: {a.sys_cached}")
    print("\n| window | episodes | window tokens | build sys | build chunks | build out | (recorded in) | "
          "build / window | index query | break-even Q (cached full) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for tag, n, T, b, build, qi, qf, ao in rows:
        # index cheaper than cached full when build + Q*qi < w*T + later*T*(Q-1) + Q*(qf - T) + Q*out*ao
        if a.batch == 1:
            per_q_gain = later * T + (qf - T) + a.out * ao - qi
            fixed = build - (a.w - later) * T
            be = "never" if per_q_gain <= 0 and fixed > 0 else ("1" if fixed <= 0 else f"{fixed / per_q_gain:.1f}")
        else:
            # with B questions per call the totals are step functions of Q; report the smallest whole Q
            # from which the index stays cheaper (checked up to 100,000)
            def full_total(Q):
                calls = -(-Q // a.batch)
                return a.w * T + later * T * (calls - 1) + calls * sys_tok + Q * ((qf - T - sys_tok) + a.out * ao)
            cheaper = [build + Q * qi < full_total(Q) for Q in range(1, 100001)]
            last_not = max((i for i, c in enumerate(cheaper) if not c), default=-1)
            be = "never" if last_not == len(cheaper) - 1 else str(last_not + 2)
        print(f"| {tag} | {n} | {T:,} | {b[0]:,} | {b[1]:,} | {b[2]:,} | ({b[3]:,}) | {build / T:.2f} | {qi:,.0f} | "
              f"{be} |")
    print("\nmean cost per question (input-token equivalents), all windows:")
    print("| questions per window | index (build amortized) | full, no cache | full, cached | full no cache / index | "
          "full cached / index |")
    print("|---|---|---|---|---|---|")
    B = a.batch
    if B > 1:
        print(f"\nwhole-window reading answers {B} questions per call (window and reader instruction once per call)")
    for Q in qs:
        ci = sum(build / Q + qi for _, _, _, _, build, qi, _, _ in rows) / len(rows)
        calls = -(-Q // B)
        # qf = T + question + reader instruction.  Per call: the window T and the instruction once; per question: its
        # text and its answer.  With B = 1 (calls = Q) both lines reduce to the earlier per-question formulas.
        cf = sum(calls * (T + sys_tok) / Q + (qf - T - sys_tok) + a.out * ao
                 for _, _, T, _, _, _, qf, ao in rows) / len(rows)
        cc = sum((a.w * T + later * T * (calls - 1)) / Q + calls * sys_tok / Q + (qf - T - sys_tok) + a.out * ao
                 for _, _, T, _, _, _, qf, ao in rows) / len(rows)
        print(f"| {Q} | {ci:,.0f} | {cf:,.0f} | {cc:,.0f} | {cf / ci:.1f} | {cc / ci:.1f} |")


if __name__ == "__main__":
    main()
