"""Unified LLM backends with an on-disk cache and an append-only cost log.

Backends
  ollama:<model>   local Ollama (temperature 0, thinking off)
  claude:<model>   Claude Code CLI in headless mode (no tools, no MCP, no prompt
                   caching, thinking off) -> exact API usage and list-price USD.
Every real call is appended to runs/calls_log.jsonl (never overwritten). A cache
hit returns the stored response together with the ORIGINAL usage, flagged
cached=True, so method cost can be counted while spending is not double counted.
"""
import hashlib
import json
import os
import subprocess
import threading
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "runs", "llm_cache")
CALL_LOG = os.path.join(ROOT, "runs", "calls_log.jsonl")
_CLAUDE_GLOB = os.path.expandvars(
    r"%USERPROFILE%\.vscode\extensions\anthropic.claude-code-*-win32-x64\resources\native-binary\claude.exe")


def claude_exe():
    """newest installed Claude Code CLI.  The VS Code extension once updated itself from 2.1.296 to 2.1.301
    and removed the old binary, so a fixed path made every Claude call fail; the path is now looked up per call."""
    import glob
    import re as _re
    found = glob.glob(_CLAUDE_GLOB)
    if not found:
        raise FileNotFoundError(f"no Claude Code CLI found ({_CLAUDE_GLOB})")
    return max(found, key=lambda p: tuple(int(x) for x in _re.search(r"claude-code-(\d+)\.(\d+)\.(\d+)", p).groups()))


def _exe_or_none(find):
    """A machine without the client can still import this module (stored-output replay); every
    model call looks the client up again and fails there"""
    try:
        return find()
    except FileNotFoundError:
        return None


CLAUDE_EXE = _exe_or_none(claude_exe)
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")  # a second server pinned to one GPU
_lock = threading.Lock()
os.makedirs(CACHE_DIR, exist_ok=True)


def _key(backend, system, prompt, params):
    blob = json.dumps([backend, system, prompt, params], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_path(k):
    return os.path.join(CACHE_DIR, k[:2], k + ".json")


def _log(rec):
    """One line per call. Several processes append to the same file, so the write holds an OS-level byte lock
    (msvcrt on Windows)."""
    line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
    with _lock:
        try:
            import msvcrt
        except ImportError:
            msvcrt = None
        lk = open(CALL_LOG + ".lock", "a+b")
        try:
            got = False
            if msvcrt is not None:
                lk.seek(0)
                for _ in range(500):  # byte 0 of a separate lock file: a fixed region every process contends for
                    try:
                        msvcrt.locking(lk.fileno(), msvcrt.LK_NBLCK, 1)
                        got = True
                        break
                    except OSError:
                        time.sleep(0.01)
            with open(CALL_LOG, "ab") as f:
                f.write(line)
            if got:
                lk.seek(0)
                msvcrt.locking(lk.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            lk.close()


def call(backend, system, prompt, max_tokens=256, num_ctx=16384, tag="", json_mode=False, retries=3):
    params = {"max_tokens": max_tokens, "num_ctx": num_ctx, "json": json_mode}
    k = _key(backend, system, prompt, params)
    cp = _cache_path(k)
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            r = json.load(f)
        r["cached"] = True
        return r
    last_err = None
    limit_waits = 0
    attempt = 0
    while attempt < retries:
        try:
            if backend.startswith("ollama:"):
                r = _ollama(backend[7:], system, prompt, max_tokens, num_ctx, json_mode)
            elif backend.startswith("ollamathink:"):  # thinking on; output allowance raised for the thinking
                r = _ollama(backend[12:], system, prompt, max(max_tokens, THINK_PREDICT), num_ctx, json_mode, think=True)
            elif backend.startswith("claude:"):
                r = _claude(backend[7:], system, prompt)
            elif backend.startswith("claudethink"):  # claudethink<budget>:<model>, extended thinking on
                budget, model = backend[len("claudethink"):].split(":", 1)
                r = _claude(model, system, prompt, thinking=int(budget))
            elif backend.startswith("codex:"):
                r = _codex(backend[6:], system, prompt)
            elif backend.startswith("agy:"):
                r = _agy(backend[4:], system, prompt)
            else:
                raise ValueError(backend)
            r.update({"backend": backend, "key": k, "tag": tag, "attempt": attempt, "ts": time.time()})
            os.makedirs(os.path.dirname(cp), exist_ok=True)
            with open(cp, "w", encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False)
            _log({x: r[x] for x in r if x != "text"} | {"text_len": len(r["text"])})
            r["cached"] = False
            return r
        except Exception as e:  # noqa: BLE001
            last_err = e
            _log({"backend": backend, "key": k, "tag": tag, "attempt": attempt, "error": repr(e)[:500], "ts": time.time()})
            msg = repr(e).lower()
            if "disabled" in msg or "prompt is too long" in msg:  # too long: waiting cannot help
                raise
            if ("limit" in msg or "429" in msg or "overloaded" in msg or "authenticate" in msg or "oauth" in msg
                 or "expecting value" in msg)                     and limit_waits < 144:  # usage limits and transient login/token-refresh failures: wait and retry, up to 24 h
                limit_waits += 1
                time.sleep(600)  # usage/session limit: wait and retry without consuming an attempt
                continue
            attempt += 1
            time.sleep(3 * attempt)
    raise RuntimeError(f"LLM call failed after {retries} attempts: {last_err!r}")


THINK_PREDICT = 8192  # output tokens allowed when thinking is on (thinking plus answer)


def _ollama(model, system, prompt, max_tokens, num_ctx, json_mode, think=False):
    body = {"model": model, "stream": False, "think": bool(think),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "options": {"temperature": 0, "seed": 0, "num_ctx": num_ctx, "num_predict": max_tokens}}
    if json_mode:
        body["format"] = "json"
    t0 = time.time()
    resp = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=3600)
    resp.raise_for_status()
    d = resp.json()
    return {"text": d["message"]["content"], "in_tokens": d.get("prompt_eval_count", 0),
            "out_tokens": d.get("eval_count", 0), "usd": 0.0, "wall_s": time.time() - t0,
            "gpu_s": d.get("total_duration", 0) / 1e9, "truncated": d.get("done_reason") == "length",
            "thinking_chars": len(d["message"].get("thinking") or "")}


def _claude(model, system, prompt, thinking=0):
    """thinking: extended-thinking budget in tokens (0 = off, the setting of every run except the thinking-on runs of the robustness study)"""
    if os.path.exists(os.path.join(ROOT, "runs", "NO_CLAUDE")):
        raise RuntimeError("Claude calls disabled (runs/NO_CLAUDE exists)")
    env = dict(os.environ, DISABLE_PROMPT_CACHING="1", MAX_THINKING_TOKENS=str(int(thinking)))
    cmd = [claude_exe(), "-p", "--model", model, "--output-format", "json", "--system-prompt", system,
           "--tools", "", "--strict-mcp-config", "--no-session-persistence",
           "--exclude-dynamic-system-prompt-sections"]
    t0 = time.time()
    p = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, timeout=900, env=env,
                       cwd=os.environ.get("TEMP", None))
    out = p.stdout.decode("utf-8", errors="replace")
    d = json.loads(out)
    if d.get("is_error"):
        raise RuntimeError(f"claude error: {d.get('result')!r} {d.get('api_error_status')}")
    u = d["usage"]
    mu = d.get("modelUsage", {}).get(model, {})
    return {"text": d["result"], "in_tokens": u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"],
            "out_tokens": u["output_tokens"], "usd": mu.get("costUSD", d.get("total_cost_usd", 0.0)),
            "usd_total_reported": d.get("total_cost_usd", 0.0), "wall_s": time.time() - t0,
            "api_ms": d.get("duration_api_ms"), "truncated": d.get("stop_reason") == "max_tokens"}


_CODEX_GLOB = os.path.expandvars(
    r"%USERPROFILE%\.vscode\extensions\openai.chatgpt-*-win32-x64\bin\windows-x86_64\codex.exe")


def codex_exe():
    """newest installed Codex CLI, looked up per call (the extension updates itself; see claude_exe)"""
    import glob
    import re as _re
    found = glob.glob(_CODEX_GLOB)
    if not found:
        raise FileNotFoundError(f"no Codex CLI found ({_CODEX_GLOB})")
    return max(found, key=lambda p: tuple(int(x) for x in _re.search(r"openai\.chatgpt-(\d+)\.(\d+)\.(\d+)", p).groups()))


CODEX_EXE = _exe_or_none(codex_exe)


def _codex(model, system, prompt):
    """GPT reader through the Codex CLI (ChatGPT account): user config, rules and AGENTS.md are excluded by running
    in an empty directory outside the project with --ignore-user-config/--ignore-rules; no tools are used. The
    system text is given at the top of the input because the CLI has no system-prompt flag."""
    if os.path.exists(os.path.join(ROOT, "runs", "NO_GPT")):
        raise RuntimeError("GPT calls disabled (runs/NO_GPT exists)")
    wd = os.path.join(os.environ.get("TEMP", ROOT), "codex_empty")
    os.makedirs(wd, exist_ok=True)
    cmd = [codex_exe(), "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
           "-s", "read-only", "--json", "-m", model, "-c", 'model_reasoning_effort="low"', "-"]
    text_in = (f"[Instructions]\n{system}\nDo not run any commands or use any tools; answer directly from the text "
               f"below.\n\n[Input]\n{prompt}")
    t0 = time.time()
    p = subprocess.run(cmd, input=text_in.encode("utf-8"), capture_output=True, timeout=900, cwd=wd)
    out = p.stdout.decode("utf-8", errors="replace")
    msg, usage, err = None, {}, None
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "item.completed" and (ev.get("item") or {}).get("type") == "agent_message":
            msg = ev["item"].get("text", "")
        elif ev.get("type") == "turn.completed":
            usage = ev.get("usage", {})
        elif ev.get("type") in ("error", "turn.failed"):
            err = json.dumps(ev)[:400]
    if msg is None:
        raise RuntimeError(f"codex error: {err or out[-300:]!r} {p.stderr.decode('utf-8', 'replace')[-200:]!r}")
    return {"text": msg, "in_tokens": usage.get("input_tokens", 0), "out_tokens": usage.get("output_tokens", 0),
            "usd": 0.0, "wall_s": time.time() - t0, "cached_in": usage.get("cached_input_tokens", 0),
            "truncated": False}


AGY_EXE = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe")
AGY_MAX_CHARS = 150_000  # a 2.1M-character message arrived as about 43k tokens; longer inputs are refused


def _agy(model, system, prompt):
    """Models of the authors' Google AI Ultra subscription (Gemini 4 Argon, GPT-OSS 120B, ...) through the Antigravity
    CLI (agy 1.3.5, signed in with the Google account; no API key, no per-token billing).  Print mode with
    stream-json input (the text path does not read the prompt from stdin), terminal sandbox, plan mode, run in an
    empty directory outside the project.  The CLI adds its own agent instructions (about 12.8k input tokens per call)
    and each call waits about 2 minutes on the service side.  An empty answer (e.g. the agent tried a tool) is an
    error, so the call is retried."""
    if os.path.exists(os.path.join(ROOT, "runs", "NO_AGY")):
        raise RuntimeError("agy calls disabled (runs/NO_AGY exists)")
    text_in = (f"Everything you need is in this message. Do not call any tool, command, file reader or browser. Do not "
               f"plan. Reply directly in plain text.\n\n[Instructions]\n{system}\n\n[Input]\n{prompt}")
    if len(text_in) > AGY_MAX_CHARS:
        raise ValueError(f"agy input of {len(text_in)} characters would be truncated by the CLI")
    wd = os.path.join(os.environ.get("TEMP", ROOT), "agy_empty")
    os.makedirs(wd, exist_ok=True)
    msg = json.dumps({"event": "user", "message": {"content": text_in}}, ensure_ascii=False) + "\n"
    cmd = [AGY_EXE, "-p", "", "--input-format", "stream-json", "--output-format", "stream-json", "--model", model,
           "--sandbox", "--mode", "plan", "--disable-slash-commands", "--print-timeout", "900s"]
    t0 = time.time()
    p = subprocess.run(cmd, input=msg.encode("utf-8"), capture_output=True, timeout=1200, cwd=wd)
    res = None
    for line in p.stdout.decode("utf-8", errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("event") == "result":
            res = ev.get("result") or {}
    if not res or res.get("status") != "SUCCESS" or not (res.get("response") or "").strip():
        err = (res or {}).get("error") or (res or {}).get("denied_actions") or p.stderr.decode("utf-8", "replace")[-300:]
        if "output token" in repr(err).lower() or "was cut off" in repr(err).lower():
            # 'response was cut off because it exceeded the output token limit' contains 'limit', which call() would
            # treat as a usage limit and retry.  It is a truncated answer, as with max_tokens on the other backends:
            # keep what came back (if anything) and mark it.
            return {"text": (res or {}).get("response") or "", "in_tokens": (res or {}).get("usage", {}).get("input_tokens", 0),
                    "out_tokens": (res or {}).get("usage", {}).get("output_tokens", 0), "usd": 0.0,
                    "wall_s": time.time() - t0, "service_s": (res or {}).get("duration_seconds"),
                    "cached_in": 0, "truncated": True, "agy_error": repr(err)[:300]}
        if any(w in repr(err).lower() for w in ("quota", "exhaust", "rate", "capacity", "high traffic", "503",
                                                "unavailable")):
            raise RuntimeError(f"agy usage limit: {err!r}")  # 'limit' makes call() wait and retry
        raise RuntimeError(f"agy error: {err!r}")
    u = res.get("usage", {})
    return {"text": res["response"], "in_tokens": u.get("input_tokens", 0), "out_tokens": u.get("output_tokens", 0),
            "usd": 0.0, "wall_s": time.time() - t0, "service_s": res.get("duration_seconds"),
            "cached_in": u.get("cache_read_tokens", 0), "truncated": False}


EMBED_HOSTS = []  # set by a caller that runs one Ollama server per granted GPU (methods/build_added.py)


def embed_multi(texts, hosts, model="qwen3-embedding:0.6b", batch=32):
    """embeddings spread over several Ollama servers, one per GPU: each server takes the next batch when it is done,
    so the faster GPU does more (dynamic split)"""
    import queue
    q = queue.Queue()
    for i in range(0, len(texts), batch):
        q.put(i)
    out, errs, done_by = [None] * len(texts), [], {h: 0 for h in hosts}

    def worker(h):
        while not errs:
            try:
                i = q.get_nowait()
            except queue.Empty:
                return
            try:
                r = requests.post(f"{h}/api/embed", json={"model": model, "input": texts[i:i + batch]}, timeout=3600)
                r.raise_for_status()
                out[i:i + batch] = r.json()["embeddings"]
                done_by[h] += 1
            except Exception as e:  # noqa: BLE001
                errs.append(f"{h}: {e!r}")
                return
    ths = [threading.Thread(target=worker, args=(h,)) for h in hosts]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    if errs or any(v is None for v in out):
        raise RuntimeError(f"embed_multi failed: {errs[:2]}")
    print(f"embed_multi: {len(texts)} texts, batches per server {done_by}", flush=True)
    return out


def embed(texts, model="qwen3-embedding:0.6b", batch=32):
    """Dense embeddings via Ollama; returns list of vectors (not cached here)."""
    if EMBED_HOSTS:
        return embed_multi(texts, EMBED_HOSTS, model, batch)
    out = []
    for i in range(0, len(texts), batch):
        resp = requests.post(f"{OLLAMA}/api/embed", json={"model": model, "input": texts[i:i + batch]}, timeout=3600)
        resp.raise_for_status()
        out.extend(resp.json()["embeddings"])
    return out
