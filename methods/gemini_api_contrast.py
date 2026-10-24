"""Whole-window reading through the Gemini API (Gemini 4 Argon, Gemini Enterprise Agent Platform, formerly Vertex AI),
on the 16-episode Oolong test windows only (decision: within the 1M-token window; beyond it the limit
is documented, so no API run is needed there).  Paid from the Google Developer Program credits of the billing account.

python methods/gemini_api_contrast.py --probe          # one tiny call: checks the model and the thinking setting
python methods/gemini_api_contrast.py --windows W01    # one window
python methods/gemini_api_contrast.py --windows all16  # the 10 windows of 16 episodes

Same materials as the web contrast (gemini_web/: window text and prompts/Wnn_prompt.txt with the window's 20 test
questions); the window text is given as the first part, labelled as the attached file, then the prompt.  Highest
thinking level.  Before every call the input is counted (free); a call is skipped if the input exceeds the 1M window
or if the cumulative cost would pass the cap.  Costs use the list prices WITHOUT the promotional credit-back
($4 per million input tokens, $20 per million output tokens including thinking; Vertex AI pricing page at the time
of the runs) and an assumed rate of 1,400 KRW per USD.  Writes gemini_api/answers/Wnn_answer.txt,
gemini_api/raw/Wnn.json and gemini_api/usage.jsonl.  Never prints credentials.
"""
import argparse
import datetime
import json
import os
import time

from google import genai
from google.genai import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "gemini_web")
OUT = os.path.join(ROOT, "gemini_api")
MODEL = "gemini-4-argon"
USD_IN, USD_CACHED, USD_OUT, KRW = 4.0, 0.20, 20.0, 1400.0
CAP_KRW = 80000.0
LIMIT = 1_000_000
KST = datetime.timezone(datetime.timedelta(hours=9))
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "project-e3336f64-935e-43a7-945")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")


def now():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


LEVEL = "MEDIUM"


def config():
    """thinking level MEDIUM, as in the web contrast (at HIGH the W01 call spent 65,533 of the
    65,536 output tokens on thinking and returned an empty answer; kept in gemini_api/_failed/)"""
    return types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=LEVEL), temperature=1.0,
                                       max_output_tokens=65536)


def spent():
    """recomputed from the usage of every call made, including failed ones kept in gemini_api/_failed/"""
    tot = 0.0
    for d in ("raw", "_failed"):
        p = os.path.join(OUT, d)
        for f in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            if f.endswith(".json"):
                tot += cost(json.load(open(os.path.join(p, f), encoding="utf-8")).get("usage") or {})[1]
    return tot


def cost(u):
    """list price; cached prompt tokens at the cached rate (W01 reported 1,691,230 prompt tokens of
    which 829,232 cached, although count_tokens gave 831,283)"""
    pin = u.get("prompt_token_count") or 0
    cached = u.get("cached_content_token_count") or 0
    pout = (u.get("candidates_token_count") or 0) + (u.get("thoughts_token_count") or 0)
    usd = (pin - cached) / 1e6 * USD_IN + cached / 1e6 * USD_CACHED + pout / 1e6 * USD_OUT
    return usd, usd * KRW


def main():
    # closed: the API runs reported in the paper are stored in gemini_api/
    raise SystemExit("Gemini API runs are closed; use the OAuth CLI (agy) instead.")
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--windows", default="")
    a = ap.parse_args()
    os.makedirs(os.path.join(OUT, "answers"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
    client = genai.Client(http_options=types.HttpOptions(api_version="v1"))
    if a.probe:
        r = client.models.generate_content(model=MODEL, contents="Reply with the single word: ready", config=config())
        u = r.usage_metadata.model_dump() if r.usage_metadata else {}
        print("probe:", (r.text or "").strip()[:40], {k: v for k, v in u.items() if "count" in k and v})
        usd, krw = cost(u)
        print(f"probe cost about ${usd:.5f} = {krw:.1f} KRW")
        return
    man = json.load(open(os.path.join(WEB, "manifest.json")))
    tags = [t for t, m in sorted(man.items()) if m["episodes"] == 16] if a.windows == "all16" else a.windows.split(",")
    for tag in tags:
        ans = os.path.join(OUT, "answers", f"{tag}_answer.txt")
        if os.path.exists(ans) and os.path.getsize(ans) > 0:
            print(tag, "already done")
            continue
        m = man[tag]
        text = open(os.path.join(WEB, "windows", f"{tag}_{m['episodes']}ep.txt"), encoding="utf-8").read()
        prompt = open(os.path.join(WEB, "prompts", f"{tag}_prompt.txt"), encoding="utf-8").read()
        contents = [types.Content(role="user", parts=[
            types.Part.from_text(text=f"[Attached file: {tag}_{m['episodes']}ep.txt]\n{text}"),
            types.Part.from_text(text=prompt)])]
        n_in = client.models.count_tokens(model=MODEL, contents=contents).total_tokens
        # W01 at HIGH was billed the prompt twice (once cached) and a full output allowance; estimate the same
        est = (n_in / 1e6 * (USD_IN + USD_CACHED) + 65536 / 1e6 * USD_OUT) * KRW
        print(f"{now()} {tag}: {n_in:,} input tokens (Gemini count); estimate {est:,.0f} KRW; spent so far {spent():,.0f}")
        if n_in > LIMIT:
            print(tag, "over the 1M window; skipped")
            continue
        if spent() + est > CAP_KRW:
            print(tag, f"would pass the cap of {CAP_KRW:,.0f} KRW; stopped")
            break
        t0 = time.time()
        r = None
        for wait in (120, 300, 600, 1200, None):  # the first W01 call returned 429 RESOURCE_EXHAUSTED
            try:
                r = client.models.generate_content(model=MODEL, contents=contents, config=config())
                break
            except Exception as e:  # noqa: BLE001
                if "429" not in str(e) or wait is None:
                    raise
                print(f"{now()} {tag}: 429, waiting {wait}s", flush=True)
                time.sleep(wait)
        u = r.usage_metadata.model_dump() if r.usage_metadata else {}
        usd, krw = cost(u)
        if not (r.text or "").strip():
            # an empty answer (e.g. thinking used the whole output allowance) stops the run: no further spending
            json.dump({"tag": tag, "model": MODEL, "thinking_level": LEVEL, "time": now(), "wall_s": time.time() - t0,
                       "usage": u, "finish": str(r.candidates[0].finish_reason) if r.candidates else None, "text": r.text},
                      open(os.path.join(OUT, "_failed", f"{tag}_{LEVEL.lower()}_{int(t0)}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, default=str)
            print(f"{now()} {tag}: EMPTY answer ({krw:,.0f} KRW); run stopped")
            break
        open(ans, "w", encoding="utf-8").write(r.text or "")
        json.dump({"tag": tag, "model": MODEL, "thinking_level": LEVEL, "time": now(), "wall_s": time.time() - t0, "usage": u,
                   "finish": str(r.candidates[0].finish_reason) if r.candidates else None, "text": r.text},
                  open(os.path.join(OUT, "raw", f"{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str)
        with open(os.path.join(OUT, "usage.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"tag": tag, "time": now(), "prompt": u.get("prompt_token_count"),
                                "cached": u.get("cached_content_token_count"),
                                "output": u.get("candidates_token_count"), "thoughts": u.get("thoughts_token_count"),
                                "usd": usd, "krw": krw}) + "\n")
        print(f"{now()} {tag}: done in {time.time() - t0:.0f}s; in {u.get('prompt_token_count')}, out "
              f"{u.get('candidates_token_count')}, thoughts {u.get('thoughts_token_count')}; {krw:,.0f} KRW; "
              f"total {spent():,.0f} KRW")


if __name__ == "__main__":
    main()
