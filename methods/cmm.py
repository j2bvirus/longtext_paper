"""Certified Mention Memory (CMM) and paragraph-level baselines.

CMM (proposed)
  raw store  : the record is kept verbatim; the unit of recall is the paragraph.
  write time : per segment, an LLM lists entity names (N), aliases (A) and
               referring phrases (R: an entity referred to by a description
               instead of a name).  No fact extraction.
  idle time  : (1) grounding - a name or alias enters the registry only if it
               occurs verbatim (case-sensitive) in the record; (2) each referring
               phrase occurrence is resolved by an LLM that reads its paragraph,
               the paragraphs introducing the names it contains and the people
               co-mentioned there; (3) an exhaustive scan builds the paragraph
               mention index (entity -> every paragraph naming it by name, alias,
               or resolved phrase); (4) co-mention links between registry names.
  query time : entities named in the question -> ALL their paragraphs plus the
               first and latest paragraphs of linked people, with a statement of
               exactly what is guaranteed (mention completeness).  Over budget:
               first + most recent paragraphs per entity, no guarantee.
Baselines on the same paragraph index (no LLM build):
  namegrep    : paragraphs containing the proper names that occur in the question
                (+ guarantee for those names), paragraph-BM25 fill.
  namegrep_co : namegrep + co-mention expansion from a zero-cost capitalised-name
                registry.
  pbm25       : paragraph-level BM25 within the budget.
"""
import collections
import json
import os
import re
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from rank_bm25 import BM25Okapi

import core
import llm

FUNC_CAPS = set("""The A An In At On By For From To Of And But Or After Before Late Among That This These Those It
Its He She His Her They Their We Our You Your I Then When While Where Who Whom Whose What Which Why How Did Do
Does Is Are Was Were Be Been Being Has Have Had If As Since Until Though Although Because So Yet Not No Yes Only
Folk Chapter Epilogue Answer Question Memory Excerpt There Here Every Each Some Any All Both One Two Three First
Second Third Last Next Once Twice Long Little Late Early Near Far""".split())
CAP_SEQ = re.compile(r"\b[A-Z][a-z']+(?:\s+[A-Z][a-z']+){1,2}\b")


def low(s):
    return " " + " ".join(re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split()) + " "


def nm(s):
    s = re.sub(r"^(the|a|an)\s+", "", (s or "").strip().lower())
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


class Paras:
    """Paragraph index with absolute character spans."""

    def __init__(self, chunks):
        self.items = []
        for c in chunks:
            pos = 0
            for part in c["text"].split("\n\n"):
                st = pos
                pos += len(part) + 2
                if part.strip():
                    self.items.append({"pid": len(self.items), "cid": c["cid"], "chapter": c["chapter"],
                                       "start": c["start"] + st, "end": c["start"] + st + len(part),
                                       "text": part.strip(), "norm": low(part), "tokens": core.ntok(part) + 8})
        self._bm = None

    def render(self, pids):
        out = []
        ann = getattr(self, "annot", None) or {}
        for i in sorted(set(pids)):
            p = self.items[i]
            ch = "Epilogue" if p["chapter"] == 999 else f"Chapter {p['chapter']}"
            t = p["text"]
            for ph, name in ann.get(i, []):
                k = t.find(ph)
                if k >= 0 and t[k + len(ph):k + len(ph) + 3] != " [=":
                    t = t[:k + len(ph)] + f" [= {name}]" + t[k + len(ph):]
            out.append(f"[{ch} | ¶{i}] {t}")
        return "\n".join(out)

    def spans(self, pids):
        return [{"cid": self.items[i]["cid"], "start": self.items[i]["start"], "end": self.items[i]["end"]}
                for i in sorted(set(pids))]

    def bm25_scores(self, question):
        if self._bm is None:
            self._bm = BM25Okapi([core.toks(p["text"]) or ["_"] for p in self.items])
        return self._bm.get_scores(core.toks(question))

    def bm25_order(self, question):
        if self._bm is None:
            self._bm = BM25Okapi([core.toks(p["text"]) or ["_"] for p in self.items])
        s = self._bm.get_scores(core.toks(question))
        return sorted(range(len(self.items)), key=lambda i: -s[i])

    def scan(self, patterns):
        """patterns: entity -> set of normalised phrases; returns entity -> sorted pids."""
        out = {}
        for e, pats in patterns.items():
            ps = [" " + p + " " for p in pats if p]
            out[e] = [it["pid"] for it in self.items if any(x in it["norm"] for x in ps)]
        return out


def pack(paras, ents, ent_paras, link_order, budget, guarantee, link_share=0.35):
    """Shared context packer for CMM and NameGrep variants."""
    per = {e: ent_paras.get(e, []) for e in ents}
    allp = sorted(set().union(*map(set, per.values()))) if per else []
    tok = sum(paras.items[i]["tokens"] for i in allp)
    names = ", ".join(e.title() for e in ents)
    if allp and tok <= budget * 0.85:
        body = paras.render(allp)
        if guarantee:
            hdr = (f"[Memory guarantee: the first block contains ALL {len(allp)} paragraphs of the record in which "
                   f"{names} {'is' if len(ents) == 1 else 'are'} named or referred to{guarantee}. Something that "
                   f"affects them without naming them (for example an event that happens to a relative) appears only "
                   f"under that other person; see the linked paragraphs.]")
        else:
            hdr = f"[Memory: paragraphs of the record that mention {names}, in order.]"
        rem = budget - tok
        lim = min(rem, budget * link_share)
        lp, t = [], 0
        for i in link_order:
            if i in allp or i in lp:
                continue
            tk = paras.items[i]["tokens"]
            if t + tk > lim:
                continue
            lp.append(i)
            t += tk
        ctx = hdr + "\n" + body
        if lp:
            ctx += "\n\n[First and latest paragraphs about closely linked people]\n" + paras.render(lp)
        used = allp + lp
        rem2 = budget - tok - t
        return ctx, used, rem2, True
    if not allp:
        return "", [], budget, False
    keep, t = set(), 0
    for e in ents:
        if per[e]:
            keep.add(per[e][0])
    t = sum(paras.items[i]["tokens"] for i in keep)
    queues = {e: list(reversed(per[e])) for e in ents}
    lim = budget * 0.8
    progress = True
    while progress and t < lim:
        progress = False
        for e in ents:
            while queues[e] and queues[e][0] in keep:
                queues[e].pop(0)
            if queues[e]:
                i = queues[e].pop(0)
                if t + paras.items[i]["tokens"] <= lim:
                    keep.add(i)
                    t += paras.items[i]["tokens"]
                    progress = True
    for i in link_order:
        if i in keep:
            continue
        if t + paras.items[i]["tokens"] > budget:
            continue
        keep.add(i)
        t += paras.items[i]["tokens"]
    hdr = (f"[Memory: {len(allp)} paragraphs mention {names}; shown are the first and the most recent ones "
           f"(older ones omitted), plus paragraphs about linked people.]")
    return hdr + "\n" + paras.render(sorted(keep)), sorted(keep), 0, False


def pack_v2(paras, ents, ent_paras, link_order, budget, guarantee, question, link_share=0.35):
    per = {e: ent_paras.get(e, []) for e in ents}
    allp = sorted(set().union(*map(set, per.values()))) if per else []
    tok = sum(paras.items[i]["tokens"] for i in allp)
    if not allp or tok <= budget * 0.85:
        return pack(paras, ents, ent_paras, link_order, budget, guarantee, link_share)
    names = ", ".join(e.title() for e in ents)
    sc = paras.bm25_scores(question)
    cnt = {}
    for e in ents:
        for i in per[e]:
            cnt[i] = cnt.get(i, 0) + 1
    keep, t = [], 0
    lim = budget * 0.85

    def add(i):
        nonlocal t
        if i in keep:
            return
        tk = paras.items[i]["tokens"]
        if t + tk <= lim:
            keep.append(i)
            t += tk
    for e in ents:
        if per[e]:
            add(per[e][0])
            for i in per[e][-2:]:
                add(i)
    for i in sorted(allp, key=lambda i: (cnt[i] >= 2, sc[i]), reverse=True):
        if t >= lim * 0.98:
            break
        add(i)
    for i in link_order:
        if t + paras.items[i]["tokens"] > budget:
            continue
        if i not in keep:
            keep.append(i)
            t += paras.items[i]["tokens"]
    hdr = (f"[Memory: {len(allp)} paragraphs mention {names}; shown are their first and latest ones and those most "
           f"relevant to the question, in record order. Others are omitted.]")
    return hdr + "\n" + paras.render(sorted(keep)), sorted(keep), 0, False


STATE_RE = re.compile(r"\b(now|currently|current|at the end|still|latest|presently|today|these days)\b", re.I)


# v4: generic English cues for a question about a state at the end / at present (v3's list kept frozen above)
STATE_RE4 = re.compile(r"\b(now|currently|current|at the end|by the end|as of|so far|still|latest|presently|today|"
                       r"these days|any ?more|any longer|yet)\b", re.I)


def pack_v3(paras, ents, ent_paras, link_order, budget, guarantee, question, dense_chunk):
    """v3: like v2, but the over-budget ranking fuses BM25 and dense relevance, and candidates include the
    global hybrid top paragraphs (for entities mentioned in a large share of the record)."""
    per = {e: ent_paras.get(e, []) for e in ents}
    allp = sorted(set().union(*map(set, per.values()))) if per else []
    tok = sum(paras.items[i]["tokens"] for i in allp)
    if allp and tok <= budget * 0.85:
        return pack(paras, ents, ent_paras, link_order, budget, guarantee)
    bm = paras.bm25_scores(question)
    dn = [dense_chunk[p["cid"]] for p in paras.items] if dense_chunk is not None else [0.0] * len(paras.items)
    n = len(paras.items)
    rb = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: -bm[i]))}
    rd = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: -dn[i]))}
    cnt = {}
    for e in ents:
        for i in per[e]:
            cnt[i] = cnt.get(i, 0) + 1
    glob = sorted(range(n), key=lambda i: -(1 / (60 + rb[i]) + 1 / (60 + rd[i])))[:300]
    cand = set(allp) | set(glob)

    def score(i):
        return 1 / (60 + rb[i]) + 1 / (60 + rd[i]) + (0.01 if i in cnt else 0) + (0.01 if cnt.get(i, 0) >= 2 else 0)
    keep, t = [], 0
    lim = budget * 0.85

    def add(i):
        nonlocal t
        if i in keep:
            return
        tk = paras.items[i]["tokens"]
        if t + tk <= lim:
            keep.append(i)
            t += tk
    for e in ents:
        if per[e] and len(per[e]) <= 400:  # bookends only for entities that are not ubiquitous
            add(per[e][0])
            for i in per[e][-2:]:
                add(i)
    for i in sorted(cand, key=score, reverse=True):
        if t >= lim * 0.98:
            break
        add(i)
    for i in link_order:
        if t + paras.items[i]["tokens"] > budget:
            continue
        if i not in keep:
            keep.append(i)
            t += paras.items[i]["tokens"]
    names = ", ".join(e.title() for e in ents) if ents else "the question"
    hdr = (f"[Memory: {len(allp)} paragraphs mention {names}; shown are those most relevant to the question "
           f"(keyword and meaning), plus first and latest ones, in record order. Others are omitted.]")
    return hdr + "\n" + paras.render(sorted(keep)), sorted(keep), 0, False


def intro_links(ents, ent_paras, para_ents, persons, k_intro=2):
    """First paragraphs of the people named in the queried entities' introductions (their first k paragraphs).
    Introductions state identity and relations (parents, employer, owning module), so the introductions of the
    people they name are what a two-step relational question needs."""
    out = []
    for e in ents:
        for i in ent_paras.get(e, [])[:k_intro]:
            for o in sorted(para_ents.get(i, ())):
                if o in ents or o not in persons:
                    continue
                ps = ent_paras.get(o, [])
                if ps:
                    out.append(ps[0])
    return list(dict.fromkeys(out))


def pack_v4(paras, ents, ent_paras, link_order, budget, guarantee, question, dense_chunk, intro, intro_share=0.12):
    """v4 = v3 + the introductions of people named in the entity's introduction come first among the links
    (within budget) or are reserved before relevance filling (over budget)."""
    lo = list(dict.fromkeys(list(intro) + list(link_order)))
    per = {e: ent_paras.get(e, []) for e in ents}
    allp = sorted(set().union(*map(set, per.values()))) if per else []
    tok = sum(paras.items[i]["tokens"] for i in allp)
    if allp and tok <= budget * 0.85:
        return pack(paras, ents, ent_paras, lo, budget, guarantee)
    bm = paras.bm25_scores(question)
    dn = [dense_chunk[p["cid"]] for p in paras.items] if dense_chunk is not None else [0.0] * len(paras.items)
    n = len(paras.items)
    rb = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: -bm[i]))}
    rd = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: -dn[i]))}
    cnt = {}
    for e in ents:
        for i in per[e]:
            cnt[i] = cnt.get(i, 0) + 1
    glob = sorted(range(n), key=lambda i: -(1 / (60 + rb[i]) + 1 / (60 + rd[i])))[:300]
    cand = set(allp) | set(glob)

    def score(i):
        return 1 / (60 + rb[i]) + 1 / (60 + rd[i]) + (0.01 if i in cnt else 0) + (0.01 if cnt.get(i, 0) >= 2 else 0)
    keep, t = [], 0
    lim = budget * 0.85

    def add(i, cap=None):
        nonlocal t
        if i in keep:
            return
        tk = paras.items[i]["tokens"]
        if t + tk <= (lim if cap is None else cap):
            keep.append(i)
            t += tk
    for e in ents:
        if per[e] and len(per[e]) <= 400:
            add(per[e][0])
            for i in per[e][-2:]:
                add(i)
    t0 = t
    for i in intro:
        add(i, cap=t0 + budget * intro_share)
    for i in sorted(cand, key=score, reverse=True):
        if t >= lim * 0.98:
            break
        add(i)
    for i in lo:
        if t + paras.items[i]["tokens"] > budget:
            continue
        if i not in keep:
            keep.append(i)
            t += paras.items[i]["tokens"]
    names = ", ".join(e.title() for e in ents) if ents else "the question"
    hdr = (f"[Memory: {len(allp)} paragraphs mention {names}; shown are those most relevant to the question "
           f"(keyword and meaning), plus first and latest ones and the introductions of people named in "
           f"{'its' if len(ents) == 1 else 'their'} introduction, in record order. Others are omitted.]")
    return hdr + "\n" + paras.render(sorted(keep)), sorted(keep), 0, False


def link_order_for(ents, ent_paras, para_ents, registry, cap=200):
    """First+latest paragraphs of people co-mentioned with the question entities,
    ranked by co-mention count + bonus for the entity's introduction and its last
    three paragraphs (identity and current state)."""
    w = collections.Counter()
    for e in ents:
        ps = ent_paras.get(e, [])
        for k, i in enumerate(ps):
            bonus = 1
            if k == 0:
                bonus += 3
            if k >= len(ps) - 3:
                bonus += 2
            for o in para_ents.get(i, ()):
                if o not in ents and o in registry and len(ent_paras.get(o, [])) <= cap:
                    w[o] += bonus
    order = []
    for o, _ in w.most_common():
        ps = ent_paras.get(o, [])
        if ps:
            order += [ps[0], ps[-1]]
    return list(dict.fromkeys(order))


class ParaBase:
    name = "para"

    def __init__(self, text, chunks, ddir, density, args):
        self.text, self.chunks, self.ddir, self.density, self.args = text, chunks, ddir, density, args
        self.builder = getattr(args, "builder", None) or "ollama:qwen3:8b"
        self.workers = getattr(args, "build_workers", 8) if self.builder.startswith("claude:") else 1
        self.cost = {"llm_in": 0, "llm_out": 0, "usd": 0.0, "llm_wall_s": 0.0, "calls": 0}
        self.idle_cost = {"llm_in": 0, "llm_out": 0, "usd": 0.0, "calls": 0}
        self.lazy_cost = {"llm_in": 0, "llm_out": 0, "usd": 0.0, "calls": 0}
        self.paras = Paras(chunks)

    def _acc(self, r, bucket):
        if r.get("cached") and bucket is self.idle_cost:
            return  # idle cost counts only calls actually made in this run (sidecar file accumulates)
        bucket["llm_in"] += r["in_tokens"]
        bucket["llm_out"] += r["out_tokens"]
        bucket["usd"] += r["usd"]
        bucket["calls"] += 1

    def final_cost(self):
        return {"lazy": self.lazy_cost}

    def fill(self, q, ctx, used, rem):
        if rem > 200:
            have = set(used)
            extra, t = [], 0
            for i in self.paras.bm25_order(q["question"]):
                if i in have:
                    continue
                tk = self.paras.items[i]["tokens"]
                if t + tk > rem:
                    continue
                extra.append(i)
                t += tk
                if t >= rem * 0.95:
                    break
            if extra:
                ctx += "\n\n[Other possibly relevant paragraphs (keyword search)]\n" + self.paras.render(extra)
                used = used + extra
        return ctx, used


class ParaBM25(ParaBase):
    name = "pbm25"

    def build(self):
        return {"llm_in": 0, "llm_out": 0, "usd": 0.0}

    def context(self, q, budget):
        ctx, used = self.fill(q, "[Memory: paragraphs retrieved by keyword search, in order]", [], budget)
        return ctx, self.paras.spans(used)


class NameGrep(ParaBase):
    """Zero-build baseline: proper names copied from the question, exact string scan."""
    name = "namegrep"
    expand = False

    def build(self):
        # zero-cost registry of capitalised 2-3 word sequences (for co-mention expansion only)
        cnt = collections.Counter()
        for m in CAP_SEQ.finditer(self.text):
            ws = m.group(0).split()
            while ws and ws[0] in FUNC_CAPS:
                ws = ws[1:]
            if len(ws) >= 2:
                cnt[" ".join(ws)] += 1
        self.registry = {nm(k) for k, v in cnt.items() if v >= 2}
        self.ent_paras = self.paras.scan({e: {e} for e in self.registry})
        self.para_ents = defaultdict(set)
        for e, ps in self.ent_paras.items():
            for i in ps:
                self.para_ents[i].add(e)
        return {"llm_in": 0, "llm_out": 0, "usd": 0.0, "registry": len(self.registry)}

    def q_names(self, question):
        out = []
        for m in CAP_SEQ.finditer(question):
            ws = m.group(0).split()
            while ws and ws[0] in FUNC_CAPS:
                ws = ws[1:]
            for k in range(len(ws)):
                cand = " ".join(ws[k:])
                if len(cand.split()) >= 2 and cand in self.text:
                    out.append(nm(cand))
                    break
        return list(dict.fromkeys(out))

    def context(self, q, budget):
        ents = self.q_names(q["question"])
        ep = dict(self.ent_paras)
        for e in ents:
            if e not in ep:
                ep[e] = self.paras.scan({e: {e}})[e]
        lo = link_order_for(ents, ep, self.para_ents, self.registry) if self.expand else []
        ctx, used, rem, cert = pack(self.paras, ents, ep, lo, budget, guarantee=" by this exact name")
        if not ents:
            rem = budget
        ctx, used = self.fill(q, ctx, used, rem)
        return ctx, self.paras.spans(used)


class NameGrepCo(NameGrep):
    name = "namegrep_co"
    expand = True


CMM_SYS = (
    "You index a long document for later lookup. For the excerpts given, write one line per item, nothing else:\n"
    "N|<excerpt number>|<name>|<type>   once for each distinct named entity (person, place, organization, "
    "object or artifact, document, code identifier) in each excerpt; write the name exactly as it appears in its "
    "fullest form in the excerpts.\n"
    "A|<alias>|<name>   when the text shows that an entity is also called by another name (a nickname, title, "
    "short form or first name) and the excerpts make clear whose name it is.\n"
    "R|<excerpt number>|<phrase>   each time an entity is referred to by a description instead of a name "
    "(e.g. 'the boy from the mill', 'her late husband'); copy the phrase exactly as written.\n"
    "Be complete and terse."
)
RESOLVE_SYS = ("You resolve a descriptive reference in a document to the entity it denotes, using only the given "
               "paragraphs. Rumors and gossip are not facts. Reason briefly, then give the final line exactly as: "
               "Answer: <the entity's name as written in the paragraphs, or unknown>")


def parse_cmm(txt, valid):
    d = {"names": [], "aliases": [], "refs": []}
    for ln in txt.splitlines():
        parts = [x.strip() for x in ln.strip().strip("`").split("|")]
        if len(parts) < 3:
            continue
        tag = parts[0].upper()[:1]
        try:
            if tag == "N":
                ex = int(re.sub(r"\D", "", parts[1]) or -1)
                if ex in valid:
                    d["names"].append({"ex": ex, "name": parts[2], "type": (parts[3] if len(parts) > 3 else "").lower()})
            elif tag == "A":
                d["aliases"].append({"alias": parts[1], "name": parts[2]})
            elif tag == "R":
                ex = int(re.sub(r"\D", "", parts[1]) or -1)
                if ex in valid:
                    d["refs"].append({"ex": ex, "phrase": parts[2]})
        except ValueError:
            continue
    return d


class CMM(ParaBase):
    name = "cmm"
    certify = True
    cards = False
    card_builder = None  # None: cards are written by the same builder as the index

    def _paths(self):
        tag = f"{self.density}_{self.builder.replace(':', '-')}"
        return (os.path.join(self.ddir, f"cmm_write_{tag}.json"), os.path.join(self.ddir, f"cmm_idle3_{tag}.json"))

    def build(self):
        p_write, p_idle = self._paths()
        if not core.build_lock(p_write):
            d = json.load(open(p_write, encoding="utf-8"))
            self.raw, self.cost = d["raw"], d["cost"]
            cached = True
        else:
            segs = []
            cur, tot = [], 0
            for c in self.chunks:
                if cur and tot + c["tokens"] > 1500:
                    segs.append(cur)
                    cur, tot = [], 0
                cur.append(c)
                tot += c["tokens"]
            if cur:
                segs.append(cur)

            def one(i_seg):
                i, seg = i_seg
                prompt = f"Excerpts:\n{core.render_chunks(seg)}\n\nWrite the N, A and R lines now."
                r = llm.call(self.builder, CMM_SYS, prompt, max_tokens=1500, num_ctx=16384,
                             tag=f"build|cmm|{os.path.basename(self.ddir)}|{self.density}|{i}")
                d = parse_cmm(r["text"], {c["cid"] for c in seg})
                return r, d
            try:
                with ThreadPoolExecutor(self.workers) as ex:
                    res = list(ex.map(one, enumerate(segs)))
            except BaseException:
                core.build_unlock(p_write)
                raise
            self.raw = []
            for r, d in res:
                self._acc(r, self.cost)
                self.raw.append(d)
            json.dump({"raw": self.raw, "cost": self.cost}, open(p_write, "w", encoding="utf-8"), ensure_ascii=False)
            core.build_unlock(p_write)
            cached = False
        idle_new = core.build_lock(p_idle + ".done")
        try:
            self._consolidate(p_idle)
        except BaseException:
            if idle_new:
                core.build_unlock(p_idle + ".done")
            raise
        if idle_new:
            open(p_idle + ".done", "w").write("ok")
            core.build_unlock(p_idle + ".done")
        out = dict(self.cost, cached_build=cached, idle=self.idle_cost, registry=len(self.registry),
                   persons=len(self.persons), refs_llm=self.n_refs_llm,
                   ungrounded=len(self.ungrounded), refs_resolved=self.n_resolved, refs_total=self.n_refs)
        if self.cards:
            cb = (self.card_builder or self.builder).replace(':', '-')
            self.card_path = os.path.join(self.ddir, f"cmm_cards_{self.density}_{cb}.json")
            self.cardstore = json.load(open(self.card_path, encoding="utf-8")) if os.path.exists(self.card_path) else {}
            self._lock = threading.Lock()
        return out

    # ------------------------------------------------------------ idle time
    def _consolidate(self, p_idle):
        # storage-time verification ablations (read-only: no new LLM calls, no cache writes)
        abl = set(x for x in os.environ.get("CMM_ABL", "").split(",") if x)
        names, aliases, refs = [], [], []
        for d in self.raw:
            names += d.get("names", [])
            aliases += [] if "alias" in abl else d.get("aliases", [])
            refs += [] if "rlines" in abl else d.get("refs", [])
        # (1) grounding: verbatim, case-sensitive occurrence in the record
        reg = {}
        self.ungrounded = []
        for n in names:
            raw = n["name"].strip().strip(".,;:\"'")
            raw = re.sub(r"^(the|The|a|A|an|An)\s+", "", raw)
            if len(raw) < 3:
                continue
            if raw in self.text or "ground" in abl:
                reg.setdefault(nm(raw), raw)
            else:
                self.ungrounded.append(raw)
        alias_of = {}
        # an alias declaration demotes a registry "name" that is really another entity's alias
        surnames = {k.split()[-1] for k in reg if len(k.split()) >= 2}
        for a in aliases:
            al_n, tgt_n = nm(a["alias"]), nm(a["name"])
            if al_n in reg and tgt_n in reg and al_n != tgt_n and len(tgt_n.split()) >= len(al_n.split())                     and any(w in tgt_n.split() for w in al_n.split()):
                extra = [w for w in al_n.split() if w not in tgt_n.split()]
                if not any(w in surnames for w in extra) and "demote" not in abl:  # an epithet, not another surname
                    del reg[al_n]
        for a in aliases:
            al = a["alias"].strip().strip(".,;:\"'")
            tgt = nm(a["name"])
            if al and al in self.text and tgt in reg and nm(al) != tgt and len(al) >= 3:
                alias_of.setdefault(nm(al), tgt)
        # a single-word registry name that is the unique first word of a longer registry name is an alias
        firsts = defaultdict(set)
        for k in reg:
            if len(k.split()) >= 2:
                firsts[k.split()[0]].add(k)
        for k in list(reg):
            if len(k.split()) == 1 and len(firsts.get(k, ())) == 1:
                alias_of.setdefault(k, next(iter(firsts[k])))
                del reg[k]
        self.registry = set(reg)
        # aliases never override registry names; follow alias chains to a registry name
        clean = {}
        for al, tgt in alias_of.items():
            if al in self.registry:
                continue
            seen = 0
            while tgt not in self.registry and tgt in alias_of and seen < 5:
                tgt = alias_of[tgt]
                seen += 1
            if tgt in self.registry:
                clean[al] = tgt
        alias_of = clean
        patterns = {e: {e} for e in self.registry}
        for al, tgt in alias_of.items():
            if tgt in patterns:
                patterns[tgt].add(al)
        base_paras = self.paras.scan(patterns)
        # (1b) type verification by consistency: majority vote over the types given at every write-time
        # occurrence; a "person name" containing lower-case words is a description, not a name
        votes = defaultdict(collections.Counter)
        for n in names:
            votes[nm(re.sub(r"^(the|The|a|A|an|An)\s+", "", n["name"].strip().strip(".,;:\"'")))][n.get("type") or "other"] += 1
        types = {}
        for e in self.registry:
            if "vote" in abl:  # single judgment: the first write-time label only
                t = next((n.get("type") or "other" for n in names if nm(n["name"]) == e), "other")
            else:
                t = votes[e].most_common(1)[0][0] if votes.get(e) else "other"
            t = {"people": "person", "character": "person", "location": "place", "organization": "group",
                 "organisation": "group", "family": "group", "artifact": "object", "item": "object"}.get(t, t)
            raw = reg[e]
            if t == "person" and any(w[:1].islower() for w in raw.split()) and "vote" not in abl:
                t = "not_a_name"
                refs.append({"ex": None, "phrase": raw})
            types[e] = t
        self.types = types
        for e in [e for e in self.registry if types.get(e) == "not_a_name"]:
            self.registry.discard(e)
            base_paras.pop(e, None)
        alias_of = {al: t for al, t in alias_of.items() if t in self.registry}
        self.persons = {e for e in self.registry if types.get(e) == "person"}
        para_ents = defaultdict(set)
        for e, ps in base_paras.items():
            for i in ps:
                para_ents[i].add(e)
        # (2) resolve referring phrases with raw context (per occurrence paragraph)
        cache = json.load(open(p_idle, encoding="utf-8")) if os.path.exists(p_idle) else {}
        occ = {}
        for rf in refs:
            ph = rf["phrase"].strip().strip(".,;:\"'")
            if len(ph) < 6 or ph not in self.text:
                continue
            lp = low(ph)
            if not any(f" {e} " in lp for e in self.registry):
                continue  # only anchored references (the phrase names another entity) are resolvable
            for it in self.paras.items:
                if (rf["ex"] is None or it["cid"] == rf["ex"]) and lp in it["norm"]:
                    occ[f"{nm(ph)}@{it['pid']}"] = (ph, it["pid"])
        self.n_refs_llm = len(occ)
        # generic anchored relational references missed at write time: "the <1-4 words> of <Person>",
        # "<Person>'s <1-2 words>" (English syntax, anchored on verified person names only)
        if self.persons and "anchor" not in abl:
            alt = "|".join(sorted((re.escape(reg[e]) for e in self.persons), key=len, reverse=True))
            pat = re.compile(r"\b(?:[Tt]he|[Aa]n?)\s+(?:[a-z]+\s+){0,3}?[a-z]+\s+of\s+(?:" + alt + r")\b|\b(?:" + alt +
                             r")'s\s+(?:[a-z]+\s+)?[a-z]+")
            for it in self.paras.items:
                for mt in pat.finditer(it["text"]):
                    ph = mt.group(0)
                    k = f"{nm(ph)}@{it['pid']}"
                    if k not in occ:
                        occ[k] = (ph, it["pid"])
        if "resolve" in abl:
            occ = {}
        self.n_refs = len(occ)
        # kept for the idle-time index audit (methods/audit_index.py); no effect on the index itself
        self._occ, self._base_paras, self._para_ents0, self._alias_of = occ, base_paras, para_ents, alias_of
        todo = [k for k in occ if k not in cache] if not abl else []

        def resolve(key):
            ph, pid = occ[key]
            ctx_p = [pid]
            inner = [e for e in self.registry if f" {e} " in low(ph)]
            for e in inner:
                ps = base_paras.get(e, [])
                if ps:
                    ctx_p.append(ps[0])
                    ctx_p += [x for x in ps if x < pid][-4:]
            for e in sorted(para_ents.get(pid, ())):
                ps = base_paras.get(e, [])
                if ps:
                    ctx_p.append(ps[0])
            ctx_p = sorted(set(ctx_p))[:20]
            prompt = (f"Reference: \"{ph}\" in paragraph ¶{pid}.\n\nParagraphs:\n{self.paras.render(ctx_p)}\n\n"
                      f"Which entity does \"{ph}\" denote in ¶{pid}?")
            r = llm.call(self.builder, RESOLVE_SYS, prompt, max_tokens=30, num_ctx=8192,
                         tag=f"idle|cmmref|{os.path.basename(self.ddir)}|{self.density}")
            return key, r
        if todo:
            with ThreadPoolExecutor(self.workers) as ex:
                res = list(ex.map(resolve, todo))
            dbg = {}
            for key, r in res:
                dbg[key] = r["text"][:200]
                self._acc(r, self.idle_cost)
                lines = [x for x in r["text"].strip().splitlines() if x.strip()]
                fin = [core.parse_answer(r["text"])]
                ans = None
                for ln in fin + lines[:1]:
                    a = nm(ln.strip().strip("*").strip())
                    a = a if a in self.registry else alias_of.get(a, a)
                    if a in self.registry:
                        ans = a
                        break
                cache[key] = ans
            json.dump(cache, open(p_idle, "w", encoding="utf-8"), ensure_ascii=False)
            json.dump(dbg, open(p_idle.replace(".json", "_answers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        self.n_resolved = 0
        ent_paras = {e: set(v) for e, v in base_paras.items()}
        for key, (ph, pid) in occ.items():
            tgt = cache.get(key)
            if tgt:
                ent_paras.setdefault(tgt, set()).add(pid)
                para_ents[pid].add(tgt)
                self.n_resolved += 1
        if getattr(self, "pron_cont", False):
            # a paragraph that opens with a third-person pronoun continues the people named just before it
            pr = re.compile(r"^(?:In [^.]{0,60}\.\s+)?(He|She|They|His|Her|Their)\b")
            for it in self.paras.items[1:]:
                i = it["pid"]
                prev = self.paras.items[i - 1]
                if prev["chapter"] == it["chapter"] and pr.match(it["text"]):
                    for e in list(para_ents.get(i - 1, ())):
                        if e in self.persons:
                            ent_paras.setdefault(e, set()).add(i)
                            para_ents[i].add(e)
        self.ent_paras = {e: sorted(v) for e, v in ent_paras.items()}
        self.para_ents = para_ents
        # exact idle-time cost per record, accumulated across runs that made new calls
        pc = p_idle.replace(".json", "_cost.json")
        prev = json.load(open(pc, encoding="utf-8")) if os.path.exists(pc) else {"llm_in": 0, "llm_out": 0, "usd": 0.0, "calls": 0}
        if self.idle_cost["calls"] and not abl:
            for k in prev:
                prev[k] += self.idle_cost[k]
            json.dump(prev, open(pc, "w", encoding="utf-8"))
        self.idle_total = prev
        self.names_by_len = sorted(set(self.registry) | set(alias_of), key=lambda x: -len(x))
        self.alias_of = alias_of
        self.raw_name = reg
        if getattr(self, "annotate", False):
            ann = defaultdict(list)
            for key, (ph, pid) in occ.items():
                tgt = cache.get(key)
                if tgt and f" {tgt} " not in f" {nm(ph)} ":
                    ann[pid].append((ph, reg.get(tgt, tgt.title())))
            # surface forms of aliases (nicknames, unique first names) occurring in indexed paragraphs
            alias_raw = {}
            for a_ in aliases:
                al = a_["alias"].strip().strip(".,;:\"'")
                if nm(al) in alias_of:
                    alias_raw[al] = alias_of[nm(al)]
            for al, tgt in alias_raw.items():
                full = reg.get(tgt, tgt.title())
                # multi-word aliases (epithets, nicknames) only; never re-annotate a name with itself
                if len(al.split()) < 2 or nm(al) == nm(full) or nm(al) in nm(full) or tgt not in self.persons:
                    continue
                pat_ = re.compile(r"(?<![A-Za-z])" + re.escape(al) + r"(?![A-Za-z])")
                for pid in self.ent_paras.get(tgt, []):
                    txt = self.paras.items[pid]["text"]
                    m_ = pat_.search(txt)
                    full = reg.get(tgt, tgt.title())
                    if m_ and not txt.startswith(full, m_.start()) and full not in txt[m_.start():m_.start() + len(full) + 2]:
                        ann[pid].append((m_.group(0), full))
            self.paras.annot = ann

    # ----------------------------------------------------------- query time
    def q_entities(self, question):
        qn = low(question)
        found = []
        for n in self.names_by_len:
            if len(n) >= 4 and f" {n} " in qn:
                e = self.alias_of.get(n, n)
                if e in self.registry and e not in found and not any(n in f for f in found):
                    found.append(e)
        return found

    def card(self, e):
        with self._lock:
            if e in self.cardstore:
                return self.cardstore[e]["text"]
        ps = self.ent_paras.get(e, [])
        tot, keep = 0, []
        for i in reversed(ps):
            tk = self.paras.items[i]["tokens"]
            if tot + tk > 9000:
                break
            keep.append(i)
            tot += tk
        keep = sorted(set(keep) | set(ps[:2]))
        lo = link_order_for([e], self.ent_paras, self.para_ents, self.persons)[:16]
        note = "" if len(keep) == len(ps) else f"(earliest and most recent of {len(ps)} paragraphs shown)\n"
        prompt = (f"Entity: {e.title()}\n\n{note}Paragraphs that name or refer to it:\n{self.paras.render(keep)}\n\n"
                  f"First and latest paragraphs of linked people:\n{self.paras.render(lo) if lo else '(none)'}\n\n"
                  f"Write a compact profile card for {e.title()} (at most 220 words): identity and aliases; relations, "
                  f"including relatives or links two steps away when the paragraphs allow; the CURRENT value of every "
                  f"changing state as of the end of the paragraphs, each with the ¶ number that establishes it; a short "
                  f"dated list of changes; commitments and whether they were fulfilled; rules that apply to it; claims "
                  f"or rumors marked as unconfirmed. Write 'not stated' for anything the paragraphs do not establish.")
        r = llm.call(self.card_builder or self.builder, "You consolidate memory about one entity of a long document so that a reader can "
                     "later use it without rereading. Use only the given paragraphs; never guess.", prompt,
                     max_tokens=500, num_ctx=16384, tag=f"idle|cmmcard|{os.path.basename(self.ddir)}|{self.density}")
        with self._lock:
            if not r.get("cached"):
                self._acc(r, self.lazy_cost)
            self.cardstore[e] = {"text": r["text"].strip(), "in": r["in_tokens"], "out": r["out_tokens"],
                                 "usd": r["usd"], "n_paragraphs": len(ps)}
            json.dump(self.cardstore, open(self.card_path, "w", encoding="utf-8"), ensure_ascii=False)
        return self.cardstore[e]["text"]

    def context(self, q, budget):
        ents = self.q_entities(q["question"])
        if not ents and (getattr(self, "v3", False) or getattr(self, "v4", False)):
            if not hasattr(self, "_dense"):
                self._dense = core.DenseIndex(self.chunks, os.path.join(self.ddir, f"emb_{self.density}_c300.npy"), llm.embed)
            ctx, used, _, _ = pack_v3(self.paras, [], {}, [], budget, "", q["question"], self._dense.scores(q["question"]))
            return ctx, self.paras.spans(used)
        if not ents:
            ctx, used = self.fill(q, "[Memory: no indexed entity named in the question; keyword search results]", [], budget)
            return ctx, self.paras.spans(used)
        ctext = ""
        if getattr(self, "v4", False):
            use_cards = self.cards and bool(STATE_RE4.search(q["question"]))
        else:
            use_cards = self.cards and (not getattr(self, "v3", False) or STATE_RE.search(q["question"]))
        if use_cards:
            cs = [f"[Profile card: {e.title()} - consolidated from all {len(self.ent_paras.get(e, []))} paragraphs "
                  f"naming it]\n{self.card(e)}" for e in ents if len(self.ent_paras.get(e, [])) <= 300][:3]
            ctext = "\n\n".join(cs)
        b2 = max(800, budget - core.ntok(ctext)) if ctext else budget
        lo = link_order_for(ents, self.ent_paras, self.para_ents, self.persons, cap=getattr(self, "link_cap", 200))
        g = " (by name, alias or resolved description)" if self.certify else ""
        if getattr(self, "v4", False):
            if not hasattr(self, "_dense"):
                self._dense = core.DenseIndex(self.chunks, os.path.join(self.ddir, f"emb_{self.density}_c300.npy"), llm.embed)
            cap = getattr(self, "intro_cap", None)
            iex = [e for e in ents if cap is None or len(self.ent_paras.get(e, [])) <= cap]
            intro = intro_links(iex, self.ent_paras, self.para_ents, self.persons) if self.intro_res else []
            ctx, used, rem, cert = pack_v4(self.paras, ents, self.ent_paras, lo, b2, g, q["question"],
                                           self._dense.scores(q["question"]), intro)
        elif getattr(self, "v3", False):
            if not hasattr(self, "_dense"):
                self._dense = core.DenseIndex(self.chunks, os.path.join(self.ddir, f"emb_{self.density}_c300.npy"), llm.embed)
            ctx, used, rem, cert = pack_v3(self.paras, ents, self.ent_paras, lo, b2, g, q["question"],
                                           self._dense.scores(q["question"]))
        elif getattr(self, "v2", False):
            ctx, used, rem, cert = pack_v2(self.paras, ents, self.ent_paras, lo, b2, g, q["question"])
        else:
            ctx, used, rem, cert = pack(self.paras, ents, self.ent_paras, lo, b2, guarantee=g)
        if getattr(self, "fill_rest", True) or not cert:
            ctx, used = self.fill(q, ctx, used, rem)
        if ctext:
            ctx = ctext + "\n\n" + ctx
        return ctx, self.paras.spans(used)


class CMMNoCert(CMM):
    name = "cmmn"
    certify = False


class CMMLean(CMM):
    """CMM without keyword-search filling when the guarantee holds (minimal context)."""
    name = "cmml"
    fill_rest = False


class CMMPron(CMM):
    """CMM + pronoun-continuation rule (no LLM): robustness variant for pronoun-only paragraphs."""
    name = "cmmp"
    pron_cont = True


class CMMAnnot(CMM):
    """CMM whose shown paragraphs carry the identities resolved at idle time
    ("the second son of X [= Gaten Haskson]", "Red Nedan [= Nedan Haskson]")."""
    name = "cmma"
    annotate = True


class CMM2(CMM):
    """CMM v2: relevance-ranked packing inside the complete entity set when it exceeds the budget."""
    name = "cmm2"
    v2 = True


class CMM2Lean(CMM2):
    name = "cmm2l"
    fill_rest = False


class CMM3(CMM):
    """CMM v3: fused keyword+meaning ranking within (and around) the complete entity set; cards gated."""
    name = "cmm3"
    v3 = True


class CMM4(CMM):
    """CMM v4: v3 + introductions of the people named in the entity's introduction (relational two-step
    evidence) placed first among links / reserved over budget; link cap configurable."""
    name = "cmm4"
    v4 = True
    intro_res = True
    link_cap = 200


class CMM4B(CMM4):
    """v4 with the same ubiquity rule as the bookends: introductions are prioritised only for queried entities
    named in at most 400 paragraphs (a protagonist's introduction says little about a given question)."""
    name = "cmm4b"
    intro_cap = 400


class CMM4NoCap(CMM4):
    name = "cmm4nc"
    link_cap = 10 ** 9


class CMM4CapOnly(CMM4):
    name = "cmm4co"
    intro_res = False
    link_cap = 10 ** 9


class CMMCards(CMM):
    name = "cmmc"
    cards = True


class CMM2Cards(CMMCards):
    name = "cmm2c"
    v2 = True


class CMM2CardsQ14(CMM2Cards):
    """Control: same index (Haiku-built), but cards written by the local Qwen3-14B."""
    name = "cmm2cq14"
    card_builder = "ollama:qwen3:14b"


class CMM2CardsQ8(CMM2Cards):
    """Control: same index (Haiku-built), but cards written by the local Qwen3-8B."""
    name = "cmm2cq8"
    card_builder = "ollama:qwen3:8b"


class CMM3Cards(CMMCards):
    """CMM v3 + profile cards only for questions about a current state."""
    name = "cmm3c"
    v3 = True


class AdaptiveMixin:
    """Certificate-gated reading budget: if the context at the base budget cannot carry a completeness
    guarantee although the question names indexed entities, rebuild it once at `escalate` x the budget.
    Questions whose entity set fits the base budget cost exactly what they cost before."""
    escalate = 3

    def context(self, q, budget):
        ctx, sp = super().context(q, budget)
        if "Memory guarantee" in ctx or not self.q_entities(q["question"]):
            return ctx, sp
        return super().context(q, budget * self.escalate)


class CMM2Adaptive(AdaptiveMixin, CMM2):
    name = "cmm2a"


class CMM4Cards(CMMCards):
    name = "cmm4c"
    v4 = True
    intro_res = True
    link_cap = 200


class CMM4Adaptive(AdaptiveMixin, CMM4):
    name = "cmm4a"


class CMM4AdaptiveCards(AdaptiveMixin, CMM4Cards):
    name = "cmm4ac"


REGISTRY = {"cmm4b": CMM4B, "cmm2a": CMM2Adaptive, "cmm4a": CMM4Adaptive, "cmm4ac": CMM4AdaptiveCards, "cmm4": CMM4, "cmm4nc": CMM4NoCap, "cmm4co": CMM4CapOnly, "cmm4c": CMM4Cards,
            "cmm3": CMM3, "cmm3c": CMM3Cards, "cmm2cq14": CMM2CardsQ14, "cmm2cq8": CMM2CardsQ8, "cmm2": CMM2, "cmm2l": CMM2Lean, "cmm2c": CMM2Cards, "cmma": CMMAnnot, "cmmp": CMMPron, "cmm": CMM, "cmmn": CMMNoCert, "cmmc": CMMCards, "cmml": CMMLean, "namegrep": NameGrep, "namegrep_co": NameGrepCo,
            "pbm25": ParaBM25}
