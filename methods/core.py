"""Shared pieces: chunking, token counting, retrieval indexes, answer scoring."""
import json
import os
import re

import numpy as np
import tiktoken
from rank_bm25 import BM25Okapi

ENC = tiktoken.get_encoding("cl100k_base")


def ntok(s):
    return len(ENC.encode(s, disallowed_special=()))


# ------------------------------------------------------------------ chunking
CH_RE = re.compile(r"\n\nChapter (\d+)\n\n|\n\nEpilogue\n\n|\n\n(?:Sprint|Session) (\d+)[^\n]*\n\n")


def chunk_record(text, target_tokens=300):
    """Paragraph-packed chunks of ~target_tokens; each knows its chapter."""
    heads = [(m.start(), int(m.group(1) or m.group(2)) if (m.group(1) or m.group(2)) else 999) for m in CH_RE.finditer(text)]

    def chapter_at(pos):
        ch = 0
        for st, c in heads:
            if st <= pos:
                ch = c
            else:
                break
        return ch

    paras = []
    pos = 0
    for m in re.finditer(r"\n\n+", text):
        if m.start() > pos:
            paras.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        paras.append((pos, len(text)))
    chunks = []
    cur = []
    cur_tok = 0
    for st, en in paras:
        t = ntok(text[st:en])
        if cur and cur_tok + t > target_tokens:
            chunks.append((cur[0][0], cur[-1][1]))
            cur, cur_tok = [], 0
        cur.append((st, en))
        cur_tok += t
    if cur:
        chunks.append((cur[0][0], cur[-1][1]))
    out = []
    for i, (st, en) in enumerate(chunks):
        body = text[st:en]
        out.append({"cid": i, "start": st, "end": en, "chapter": chapter_at(st), "text": body, "tokens": ntok(body)})
    return out


def render_chunks(chunks):
    parts = []
    for c in sorted(chunks, key=lambda x: x["cid"]):
        ch = "Epilogue" if c["chapter"] == 999 else f"Chapter {c['chapter']}"
        parts.append(f"[Excerpt {c['cid']} | {ch}]\n{c['text']}")
    return "\n\n".join(parts)


# ----------------------------------------------------------------- retrieval
WORD = re.compile(r"[A-Za-z][A-Za-z']+")
STOP = set("the a an of and or to in on at for with by from was were is are be been it its that this as he she his her him they them their not but had has have did do does who whom which what where when why how into out up any all".split())


def toks(s):
    return [w for w in (x.lower() for x in WORD.findall(s)) if w not in STOP]


class BM25Index:
    def __init__(self, chunks):
        self.chunks = chunks
        self.bm = BM25Okapi([toks(c["text"]) for c in chunks])

    def scores(self, query):
        return self.bm.get_scores(toks(query))


class DenseIndex:
    def __init__(self, chunks, cache_file, embed_fn):
        self.chunks = chunks
        self.cache_file = cache_file
        if os.path.exists(cache_file):
            self.mat = np.load(cache_file)
        else:
            vecs = embed_fn([c["text"] for c in chunks])
            self.mat = np.asarray(vecs, dtype=np.float32)
            self.mat /= np.linalg.norm(self.mat, axis=1, keepdims=True) + 1e-9
            np.save(cache_file, self.mat)
        self.embed_fn = embed_fn

    def scores(self, query):
        qc = getattr(self, "_qcache", None)
        if qc is None:
            qc = {}
            qp = os.path.join(os.path.dirname(self.cache_file), "qemb.json")
            if os.path.exists(qp):
                qc = json.load(open(qp, encoding="utf-8"))
            self._qcache = qc
        if query in qc:
            q = np.asarray(qc[query], dtype=np.float32)
        else:
            q = np.asarray(self.embed_fn([query])[0], dtype=np.float32)
        q /= np.linalg.norm(q) + 1e-9
        return self.mat @ q


def rrf(score_lists, k=60):
    n = len(score_lists[0])
    fused = np.zeros(n)
    for s in score_lists:
        order = np.argsort(-np.asarray(s))
        ranks = np.empty(n)
        ranks[order] = np.arange(n)
        fused += 1.0 / (k + ranks + 1)
    return fused


def take_budget(chunks, order, budget):
    picked, used = [], 0
    for i in order:
        c = chunks[i]
        if used + c["tokens"] > budget:
            continue
        picked.append(c)
        used += c["tokens"]
        if used >= budget * 0.97:
            break
    return picked


# ------------------------------------------------------------------- scoring
ANS_RE = re.compile(r"answer\s*[:：]\s*(.+)", re.I)
NONE_SYN = ["none", "no one", "nobody", "no living spouse", "not married", "unmarried", "no spouse", "widowed"]
NUM_WORDS = {"zero": 0, "none": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
             "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
             "thirty": 30, "forty": 40, "fifty": 50}


def parse_answer(text):
    lines = [x.strip() for x in text.strip().splitlines() if x.strip()]
    for ln in reversed(lines):
        m = ANS_RE.search(ln)
        if m:
            return m.group(1).strip().strip("*").strip()
    return lines[-1] if lines else ""


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split()


def score(pred_raw, ans, persons_by_first=None, all_names=None):
    """Return 1/0 correctness for a parsed answer against gold spec."""
    p = " ".join(norm(pred_raw))
    kind = ans["kind"]
    g = str(ans["gold"]).lower()
    if kind == "yesno":
        w = norm(pred_raw)
        return int(bool(w) and w[0] == g)
    if kind == "verdict":  # continuity check: the answer line must start with the gold verdict
        w = norm(pred_raw)
        return int(bool(w) and w[0] == g)
    if kind == "label":
        w = set(norm(pred_raw))
        others = {"kept", "broken", "pending"} - {g}
        return int(g in w and not (w & others))
    if kind == "none":
        return int(any(x in p for x in NONE_SYN) or p in ("no", "n a"))
    if kind == "unknown":
        return int("unknown" in p or "not stated" in p or "never says" in p or "does not say" in p
                   or "not mentioned" in p)
    if kind in ("place", "word"):
        return int(" ".join(norm(g)) in p)
    if kind == "token":  # identifiers and values: exact token-sequence match (30 must not match 300)
        g = " ".join(norm(ans["gold"]))
        return int(bool(g) and f" {g} " in f" {p} ")
    if kind == "label4":
        w = set(norm(pred_raw))
        labels = {"open", "fixed", "reopened", "wontfix"}
        gl = ans["gold"]
        if gl == "wontfix" and ("won t fix" in p or "wont fix" in p):
            w.add("wontfix")
        return int(gl in w and not (w & (labels - {gl})))
    if kind == "free":  # provisional lexical check; judged answers come from methods/judge.py
        g = " ".join(norm(ans["gold"]))
        return int(bool(g) and g in p)
    if kind == "count":  # LongState-Aggregate: the first number in the answer line must equal the gold count
        # (digits win over a leading 'no'; thousands separators and
        # compound number words such as 'twenty one' are read as one number)
        s = re.sub(r"(?<=\d),(?=\d{3})", "", pred_raw.lower())
        m = re.search(r"\d+", s)
        if m:
            return int(int(m.group()) == int(ans["gold"]))
        w = norm(s)
        for i, t in enumerate(w):
            if t in NUM_WORDS:
                v = NUM_WORDS[t]
                if 20 <= v and i + 1 < len(w) and NUM_WORDS.get(w[i + 1], 99) < 10:
                    v += NUM_WORDS[w[i + 1]]
                return int(v == int(ans["gold"]))
        if w and w[0] == "no":
            return int(int(ans["gold"]) == 0)
        return 0
    if kind == "olist":  # LongState-Aggregate: the known names found in the answer, in order of appearance and with
        # immediate repeats collapsed, must equal the gold sequence exactly
        p2 = f" {p} "
        hits = []
        for v in {" ".join(norm(x)) for x in ans["vocab"]}:
            k = p2.find(f" {v} ")
            while k >= 0:
                hits.append((k, v))
                k = p2.find(f" {v} ", k + 1)
        got = []
        for _, v in sorted(hits):
            if not got or got[-1] != v:
                got.append(v)
        return int(got == [" ".join(norm(x)) for x in ans["gold"]])
    if kind == "person":
        if all_names:  # a hedged answer naming another person as well is wrong
            g = " ".join(norm(ans["gold"]))
            if any(n != g and f" {n} " in f" {p} " for n in all_names):
                return 0
        for al in ans["aliases"]:
            if " ".join(norm(al)) in p:
                return 1
        first = norm(g)[0]
        if persons_by_first is not None and persons_by_first.get(first, 0) == 1 and p.split()[:1] == [first]:
            return 1
        return 0
    raise ValueError(kind)


def evidence_recall(q, spans, chunks_used):
    """Fraction of gold evidence events whose span overlaps any provided chunk."""
    ev = q["evidence"]
    if not ev:
        return None
    hit = 0
    for e in ev:
        st, en = spans[e]
        if any(c["start"] <= st < c["end"] or c["start"] < en <= c["end"] for c in chunks_used):
            hit += 1
    return hit / len(ev)


def load_dataset(ddir, density_tag):
    text = open(os.path.join(ddir, f"record_{density_tag}.txt"), encoding="utf-8").read()
    spans = json.load(open(os.path.join(ddir, f"spans_{density_tag}_GOLD.json")))
    qs = [json.loads(l) for l in open(os.path.join(ddir, "questions_GOLD.jsonl"), encoding="utf-8")]
    qs = [q for q in qs if not q.get("excluded")]
    world = json.load(open(os.path.join(ddir, "world_GOLD.json"), encoding="utf-8"))
    return text, spans, qs, world


def build_lock(path):
    """Cross-process build lock: if another process is building `path`, wait for it.
    Returns True if the caller must build (and later call build_unlock), False if
    the finished file now exists."""
    import time as _t
    lk = path + ".lock"
    while True:
        if os.path.exists(path):
            return False
        if os.environ.get("MEM_WAIT_ONLY") and not path.endswith(".done"):
            nc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs", "NO_CLAUDE")
            if os.path.exists(nc):  # nobody will build it while Claude is disabled: skip this condition
                raise RuntimeError(f"memory not built and Claude disabled: {path}")
            _t.sleep(30)  # this process only reads memories built elsewhere
            continue
        try:
            fd = os.open(lk, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            if _t.time() - os.path.getmtime(lk) > 4 * 3600:
                os.remove(lk)
                continue
            _t.sleep(20)


def build_unlock(path):
    try:
        os.remove(path + ".lock")
    except OSError:
        pass
