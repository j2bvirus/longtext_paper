"""Post-hoc baselines (settings in release/ADDED_BASELINES_SETTINGS.md):

  hippo2  HippoRAG 2 re-implementation (Gutierrez et al., 2025, "From RAG to Memory", Sections 3.1-3.5 and Appendix
          G.1): open triples per paragraph, phrase and passage nodes, synonym edges at cosine >= 0.8, query-to-triple
          top-5, recognition-memory filter by the builder LLM, at most 5 phrase seeds, all passages as seeds with
          reset weight 0.05 x similarity, personalized PageRank with damping 0.5, passages ranked by PageRank.
  ctxhdr  contextual retrieval: a 1-2 sentence context header per 300-token chunk (from the 3,000 tokens before a
          group of 10 chunks and the chunks themselves), BM25 + embedding fused by RRF over header + chunk.
  s2b     small-to-big: paragraphs ranked by BM25 + embedding (RRF), each hit shown with its neighbouring paragraphs
          up to about 500 tokens on each side.
All read with the same reader prompt and the same 4,000-token budget as every other method (run_eval.py).

Builds are cached by record text (data/_added_cache/<md5>/), so the continuity sets that share a record with the
state-tracking sets reuse them.  The LLM part (GPT, no GPU) and the embedding part (Ollama qwen3-embedding:0.6b, GPU,
taken through an optional GPU scheduler where it exists) are separate: methods/build_added.py runs both; reading runs (--wait_only) never
embed and fail if an embedding is missing.
"""
import hashlib
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import scipy.sparse as sp
from rank_bm25 import BM25Okapi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmm  # noqa: E402
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDER_DEFAULT = "codex:gpt-6.1-sol"


def _btag(b):
    return b.replace(":", "-")


def _norm(s):
    return " ".join(str(s).lower().split())


def _embed_cached(texts, path):
    if os.path.exists(path):
        m = np.load(path)
        assert m.shape[0] == len(texts), (path, m.shape, len(texts))
        return m
    if os.environ.get("MEM_WAIT_ONLY"):
        raise RuntimeError(f"embeddings missing ({path}); run methods/build_added.py under the GPU gate first")
    m = np.asarray(llm.embed(texts), dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-9
    np.save(path, m)
    return m


def _minmax(x):
    lo, hi = float(np.min(x)), float(np.max(x))
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)


class _Added(cmm.ParaBase):
    def __init__(self, text, chunks, ddir, density, args):
        super().__init__(text, chunks, ddir, density, args)
        self.builder = getattr(args, "builder", None) or BUILDER_DEFAULT
        self.workers = getattr(args, "build_workers", 8)
        self.cdir = os.path.join(ROOT, "data", "_added_cache", hashlib.md5(text.encode("utf-8")).hexdigest()[:12])
        os.makedirs(self.cdir, exist_ok=True)
        self._qc = None
        self._lock = threading.Lock()

    def _qvec(self, question):
        if self._qc is None:
            p = os.path.join(self.ddir, "qemb_added.json")
            self._qc = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        if question not in self._qc:
            raise RuntimeError("query embedding missing: run methods/build_added.py first")
        v = np.asarray(self._qc[question], dtype=np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    def para_emb(self):
        return _embed_cached([p["text"] for p in self.paras.items], os.path.join(self.cdir, f"emb_paras.npy"))

    def build_llm(self):
        """the LLM part of the build (no GPU); nothing for methods without one"""
        return None

    def _pack(self, order, budget):
        chosen, used = [], 0
        for i in order:
            i = int(i)
            t = self.paras.items[i]["tokens"]
            if used + t > budget:
                continue
            chosen.append(i)
            used += t
            if used >= budget * 0.97:
                break
        return chosen


class SmallToBig(_Added):
    name = "s2b"
    side = 500

    def build(self):
        self.pemb = self.para_emb()
        return {"llm_in": 0, "llm_out": 0, "usd": 0.0}

    def context(self, q, budget):
        items = self.paras.items
        s = core.rrf([self.paras.bm25_scores(q["question"]), self.pemb @ self._qvec(q["question"])])
        chosen, used = set(), 0
        for i in np.argsort(-s):
            i = int(i)
            if i in chosen:
                continue
            win, side = [i], 0
            j = i - 1
            while j >= 0 and side + items[j]["tokens"] <= self.side:
                win.append(j)
                side += items[j]["tokens"]
                j -= 1
            side, j = 0, i + 1
            while j < len(items) and side + items[j]["tokens"] <= self.side:
                win.append(j)
                side += items[j]["tokens"]
                j += 1
            new = [k for k in win if k not in chosen]
            t = sum(items[k]["tokens"] for k in new)
            if used + t > budget:  # the whole window does not fit: take the hit paragraph alone if it does
                if used + items[i]["tokens"] <= budget:
                    chosen.add(i)
                    used += items[i]["tokens"]
            else:
                chosen.update(new)
                used += t
            if used >= budget * 0.97:
                break
        pids = sorted(chosen)
        ctx = ("[Memory: paragraphs found by keyword and embedding search, each shown with the paragraphs around it "
               "(about 500 tokens on each side), in record order]\n" + self.paras.render(pids))
        return ctx, self.paras.spans(pids)


class CtxHeader(_Added):
    name = "ctxhdr"
    group, before = 10, 3000
    SYS = ("You help a search engine index a long chronological record. For each numbered excerpt, write one or two "
           "sentences (at most 50 words) that situate it within the record: who and what it is about and where it "
           "stands in the story, using names exactly as written. Do not repeat the excerpt and do not add facts that "
           "are not in the text shown. Output one line per excerpt exactly as 'E<number>: <context>'.")

    def _path(self):
        return os.path.join(self.cdir, f"ctxhdr_{_btag(self.builder)}.json")

    def build_llm(self):
        path = self._path()
        if not core.build_lock(path):
            return
        try:
            groups = [self.chunks[i:i + self.group] for i in range(0, len(self.chunks), self.group)]

            def one(g):
                toks = core.ENC.encode(self.text[:g[0]["start"]], disallowed_special=())
                pre = core.ENC.decode(toks[-self.before:]) if toks else "(start of the record)"
                prompt = (f"[Text just before the excerpts]\n{pre}\n\n[Excerpts]\n" +
                          "\n\n".join(f"E{c['cid']}:\n{c['text']}" for c in g))
                r = llm.call(self.builder, self.SYS, prompt, max_tokens=1500,
                             tag=f"build|ctxhdr|{os.path.basename(self.cdir)}|{g[0]['cid']}")
                valid, out = {c["cid"] for c in g}, {}
                for line in r["text"].splitlines():
                    m = re.match(r"\s*\**E(\d+)\**\s*[:：]\s*(.+)", line)
                    if m and int(m.group(1)) in valid:
                        out[int(m.group(1))] = m.group(2).strip()
                return out, r["in_tokens"], r["out_tokens"]
            with ThreadPoolExecutor(self.workers) as ex:
                res = list(ex.map(one, groups))
            hdr = {}
            for o, _, _ in res:
                hdr.update(o)
            json.dump({"headers": {str(k): v for k, v in sorted(hdr.items())},
                       "cost": {"in": sum(r[1] for r in res), "out": sum(r[2] for r in res), "calls": len(groups)},
                       "missing": [c["cid"] for c in self.chunks if c["cid"] not in hdr]},
                      open(path, "w", encoding="utf-8"), ensure_ascii=False)
        finally:
            core.build_unlock(path)

    def build(self):
        self.build_llm()
        d = json.load(open(self._path(), encoding="utf-8"))
        self.hdr = {int(k): v for k, v in d["headers"].items()}
        docs = [self.hdr.get(c["cid"], "") + "\n" + c["text"] for c in self.chunks]
        self.bm = BM25Okapi([core.toks(x) or ["_"] for x in docs])
        self.emb = _embed_cached(docs, os.path.join(self.cdir, f"emb_ctxhdr_{_btag(self.builder)}.npy"))
        self.htok = {c["cid"]: core.ntok(self.hdr.get(c["cid"], "")) + 4 for c in self.chunks}
        return {"llm_in": d["cost"]["in"], "llm_out": d["cost"]["out"], "usd": 0.0,
                "headers_missing": len(d["missing"])}

    def context(self, q, budget):
        s = core.rrf([self.bm.get_scores(core.toks(q["question"])), self.emb @ self._qvec(q["question"])])
        picked, used = [], 0
        for i in np.argsort(-s):
            c = self.chunks[int(i)]
            t = c["tokens"] + self.htok[c["cid"]]
            if used + t > budget:
                continue
            picked.append(c)
            used += t
            if used >= budget * 0.97:
                break
        parts = []
        for c in sorted(picked, key=lambda x: x["cid"]):
            ch = "Epilogue" if c["chapter"] == 999 else f"Chapter {c['chapter']}"
            h = self.hdr.get(c["cid"], "")
            parts.append(f"[Excerpt {c['cid']} | {ch}]\n" + (f"(Context: {h})\n" if h else "") + c["text"])
        return "\n\n".join(parts), picked


class Hippo2(_Added):
    name = "hippo2"
    group, syn, damping, ptw, topk, max_seeds = 10, 0.8, 0.5, 0.05, 5, 5
    OPENIE_SYS = ("You extract a knowledge graph from paragraphs of a long record (open information extraction, no "
                  "fixed schema). For each numbered paragraph, list every fact it states as triples (subject | "
                  "relation | object): people, places, objects, events, states and their changes, times, quantities. "
                  "Use names exactly as written in the paragraph; when a pronoun clearly refers to someone named in "
                  "the same paragraph, use that name. Do not add facts that are not in the paragraph. Output one "
                  "triple per line exactly as 'P<number> | subject | relation | object'.")
    FILTER_SYS = ("You are the recognition step of a question-answering system. You are given a question and candidate "
                  "facts (triples) retrieved from a knowledge graph. Keep only the facts that are relevant to answering "
                  "the question, copied exactly. Output JSON only: {\"fact\": [[subject, relation, object], ...]}; "
                  "output {\"fact\": []} if none is relevant.")

    def _path(self):
        return os.path.join(self.cdir, f"hippo2_openie_{_btag(self.builder)}.json")

    def build_llm(self):
        path = self._path()
        if not core.build_lock(path):
            return
        try:
            items = self.paras.items
            groups = [items[i:i + self.group] for i in range(0, len(items), self.group)]

            def one(g):
                prompt = "\n\n".join(f"P{p['pid']}: {p['text']}" for p in g)
                r = llm.call(self.builder, self.OPENIE_SYS, prompt, max_tokens=4000,
                             tag=f"build|hippo2|{os.path.basename(self.cdir)}|{g[0]['pid']}")
                valid, trs, bad = {p["pid"] for p in g}, [], 0
                for line in r["text"].splitlines():
                    f = [x.strip().strip("*").strip() for x in line.split("|")]
                    if len(f) != 4:
                        continue
                    m = re.match(r"P(\d+)$", f[0])
                    if not m or int(m.group(1)) not in valid or not f[1] or not f[3]:
                        bad += 1
                        continue
                    trs.append([int(m.group(1)), f[1], f[2], f[3]])
                return trs, bad, r["in_tokens"], r["out_tokens"]
            with ThreadPoolExecutor(self.workers) as ex:
                res = list(ex.map(one, groups))
            json.dump({"triples": [t for r in res for t in r[0]], "bad_lines": sum(r[1] for r in res),
                       "cost": {"in": sum(r[2] for r in res), "out": sum(r[3] for r in res), "calls": len(groups)}},
                      open(path, "w", encoding="utf-8"), ensure_ascii=False)
        finally:
            core.build_unlock(path)

    def build(self):
        self.build_llm()
        d = json.load(open(self._path(), encoding="utf-8"))
        src, phr = {}, {}
        for pid, s, r, o in d["triples"]:
            key = (_norm(s), _norm(r), _norm(o))
            src.setdefault(key, set()).add(pid)
            for x in (key[0], key[2]):
                phr.setdefault(x, len(phr))
        self.triples, self.tri_src, self.phr = list(src), [sorted(src[k]) for k in src], phr
        P, N = len(phr), len(self.paras.items)
        bt = _btag(self.builder)
        ph_emb = _embed_cached(list(phr), os.path.join(self.cdir, f"emb_hippo2_phrases_{bt}.npy"))
        self.tr_emb = _embed_cached([f"{s} {r} {o}" for s, r, o in self.triples],
                                    os.path.join(self.cdir, f"emb_hippo2_triples_{bt}.npy"))
        self.pemb = self.para_emb()
        w = {}

        def add(a, b, v):
            if a != b:
                k = (a, b) if a < b else (b, a)
                w[k] = w.get(k, 0.0) + v
        ctx_pairs = set()
        for (s, r, o), ps in zip(self.triples, self.tri_src):
            add(phr[s], phr[o], 1.0)  # relation edge
            for pid in ps:
                ctx_pairs.add((phr[s], P + pid))
                ctx_pairs.add((phr[o], P + pid))
        for a, b in ctx_pairs:  # context edge: passage contains phrase
            add(a, b, 1.0)
        nsyn = 0
        for st in range(0, P, 1024):  # synonym edges between phrase pairs at cosine >= 0.8
            S = ph_emb[st:st + 1024] @ ph_emb.T
            ii, jj = np.nonzero(S >= self.syn)
            for i, j in zip(ii.tolist(), jj.tolist()):
                if st + i < j:
                    add(st + i, j, float(S[i, j]))
                    nsyn += 1
        rows = [k[0] for k in w] + [k[1] for k in w]
        cols = [k[1] for k in w] + [k[0] for k in w]
        vals = list(w.values()) * 2
        A = sp.csr_matrix((vals, (rows, cols)), shape=(P + N, P + N))
        deg = np.asarray(A.sum(axis=0)).ravel()
        deg[deg == 0] = 1.0
        self.M = A.multiply(1.0 / deg).tocsr()  # column-stochastic transition matrix
        self.P, self.N = P, N
        self.stats = {"phrases": P, "passages": N, "triples": len(self.triples), "synonym_edges": nsyn,
                      "context_edges": len(ctx_pairs), "bad_lines": d["bad_lines"]}
        return {"llm_in": d["cost"]["in"], "llm_out": d["cost"]["out"], "usd": 0.0, "graph": self.stats}

    def _filter(self, question, cand):
        prompt = f"Question: {question}\n\nCandidate facts:\n" + json.dumps({"fact": cand}, ensure_ascii=False)
        r = llm.call(self.builder, self.FILTER_SYS, prompt, max_tokens=600, tag="query|hippo2_filter")
        with self._lock:
            self._acc(r, self.lazy_cost)
        m = re.search(r"\{.*\}", r["text"], re.S)
        try:
            facts = json.loads(m.group(0))["fact"] if m else []
        except (ValueError, KeyError, TypeError):
            facts = []
        keep = {tuple(_norm(x) for x in f) for f in facts if isinstance(f, (list, tuple)) and len(f) == 3}
        return [i for i, c in enumerate(cand) if tuple(c) in keep]

    def context(self, q, budget):
        qv = self._qvec(q["question"])
        ts = self.tr_emb @ qv
        top = [int(t) for t in np.argsort(-ts)[:self.topk]]
        kept = self._filter(q["question"], [list(self.triples[t]) for t in top])
        sim = self.pemb @ qv
        if not kept:  # Appendix G.1: no filtered triple -> dense passage ranking without graph search
            order, how = np.argsort(-sim), "embedding fallback"
        else:
            sc = {}
            for k in kept:
                s, r, o = self.triples[top[k]]
                for x in (s, o):
                    sc.setdefault(self.phr[x], []).append(float(ts[top[k]]))
            seeds = sorted(((float(np.mean(v)), n) for n, v in sc.items()), reverse=True)[:self.max_seeds]
            reset = np.zeros(self.P + self.N)
            for v, n in seeds:
                reset[n] = max(v, 0.0)
            reset[self.P:] = _minmax(sim) * self.ptw
            reset /= reset.sum()
            p = reset.copy()
            for _ in range(200):
                pn = self.damping * (self.M @ p) + (1 - self.damping) * reset
                pn /= pn.sum()
                if np.abs(pn - p).sum() < 1e-10:
                    p = pn
                    break
                p = pn
            order, how = np.argsort(-p[self.P:]), "personalized PageRank"
        pids = sorted(self._pack(order, budget))
        ctx = f"[Memory: paragraphs retrieved by knowledge-graph search ({how}), in record order]\n" + self.paras.render(pids)
        return ctx, self.paras.spans(pids)


REGISTRY = {"hippo2": Hippo2, "ctxhdr": CtxHeader, "s2b": SmallToBig}
