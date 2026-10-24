"""Write-time memories.  Build products are cached per (record, builder) so the
same memory can be read by different readers; build cost is recorded once.

summary  : rolling notes of fixed size, rewritten after every segment
           (recursive-summarization / core-memory style baseline).
ecm      : entity-indexed complete memory (proposed).  The raw record is kept
           verbatim and stays searchable.
           write time  - every segment: an LLM lists entity mentions and atomic
                         facts (independent per segment, parallelisable).
           idle time   - aliases merged into a canonical registry; relational
                         descriptions ("the eldest son of X") resolved by an LLM
                         from the facts about X; every resolved name/alias is
                         re-scanned over the raw text so the mention index is
                         complete with respect to the registry; per-entity fact
                         timelines are built.
           query time  - question entities -> every passage mentioning them.
                         If they fit the budget they are given with a
                         completeness certificate; otherwise a fact timeline
                         covering all mentions plus the most relevant passages.
                         Leftover budget: introductions of linked entities, then
                         hybrid retrieval.
"""
import collections
import json
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import core
import llm

GENERIC_NOTE_RULES = (
    "Keep every durable fact about entities (people, places, organizations, objects, documents), their "
    "relations and attributes, every change of state and when it happened, commitments and whether they "
    "were fulfilled, rules or conditions, and claims or rumors (marked as unconfirmed)."
)


def segments(chunks, seg_tokens):
    segs, cur, tot = [], [], 0
    for c in chunks:
        if cur and tot + c["tokens"] > seg_tokens:
            segs.append(cur)
            cur, tot = [], 0
        cur.append(c)
        tot += c["tokens"]
    if cur:
        segs.append(cur)
    return segs


class Base:
    def __init__(self, text, chunks, ddir, density, args):
        self.text, self.chunks, self.ddir, self.density, self.args = text, chunks, ddir, density, args
        self.builder = getattr(args, "builder", None) or "ollama:qwen3:8b"
        self.workers = getattr(args, "build_workers", 1) if self.builder.startswith("claude:") else 1
        self.cost = {"llm_in": 0, "llm_out": 0, "usd": 0.0, "llm_wall_s": 0.0, "calls": 0}

    def _acc(self, r):
        self.cost["llm_in"] += r["in_tokens"]
        self.cost["llm_out"] += r["out_tokens"]
        self.cost["usd"] += r["usd"]
        self.cost["llm_wall_s"] += r["wall_s"]
        self.cost["calls"] += 1


class SummaryMemory(Base):
    name = "summary"

    def build(self):
        words = max(200, int(self.args.budget * 0.7))
        path = os.path.join(self.ddir, f"mem_summary_{self.density}_{self.builder.replace(':', '-')}_w{words}.json")
        if not core.build_lock(path):
            d = json.load(open(path, encoding="utf-8"))
            self.notes, self.cost = d["notes"], d["cost"]
            return dict(self.cost, cached_build=True)
        notes = "(empty)"
        sysmsg = ("You maintain memory notes about a long document so that someone can later answer questions "
                  "about it without rereading it. " + GENERIC_NOTE_RULES)
        try:
            notes = self._roll(notes, sysmsg, words)
        except BaseException:
            core.build_unlock(path)
            raise
        for i, seg in enumerate([]):
            prompt = (f"Current notes:\n{notes}\n\nNew text:\n{core.render_chunks(seg)}\n\n"
                      f"Rewrite the complete updated notes (at most {words} words). Keep earlier facts unless the "
                      f"new text changes them; when something changes, state the new value and the chapter. "
                      f"Output only the notes.")
            r = llm.call(self.builder, sysmsg, prompt, max_tokens=int(words * 1.6), num_ctx=16384,
                         tag=f"build|summary|{self.density}|{i}")
            self._acc(r)
            notes = r["text"].strip()
        self.notes = notes
        json.dump({"notes": notes, "cost": self.cost}, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        core.build_unlock(path)
        return dict(self.cost, cached_build=False)

    def _roll(self, notes, sysmsg, words):
        for i, seg in enumerate(segments(self.chunks, 3000)):
            prompt = (f"Current notes:\n{notes}\n\nNew text:\n{core.render_chunks(seg)}\n\n"
                      f"Rewrite the complete updated notes (at most {words} words). Keep earlier facts unless the "
                      f"new text changes them; when something changes, state the new value and the chapter. "
                      f"Output only the notes.")
            r = llm.call(self.builder, sysmsg, prompt, max_tokens=int(words * 1.6), num_ctx=16384,
                         tag=f"build|summary|{os.path.basename(self.ddir)}|{self.density}|{i}")
            self._acc(r)
            notes = r["text"].strip()
        return notes

    def context(self, q, budget):
        notes = self.notes
        toks = core.ENC.encode(notes, disallowed_special=())
        if len(toks) > budget:  # same reader budget as every other method
            notes = core.ENC.decode(toks[:budget]) + "\n(notes truncated to the memory budget)"
        return "[Memory notes]\n" + notes, []


EXTRACT_SYS = (
    "You index a long document for later lookup. Write one line per item, nothing else:\n"
    "F|<excerpt number>|<subject>|<relation>|<object>|<status>   for every atomic fact the excerpt states "
    "(status: fact = stated by the narrator or record; claim = asserted by someone, rumor; plan = intended, "
    "not done; rule = a general law or condition). Use canonical full names for people, places and objects.\n"
    "E|<excerpt number>|<surface>|<canonical full name>   whenever the text refers to an entity by a first "
    "name, nickname, title or description (e.g. 'the widow of X', 'the eldest son of Y', 'Old Z') instead "
    "of its full name; copy the surface phrase exactly; if unsure of the full name repeat the phrase.\n"
    "A|<alias>|<canonical full name>   when the text says someone is called or known by another name.\n"
    "Be complete and terse."
)
EXTRACT_FMT = "Write the F, E and A lines now."


def parse_lines(txt, valid):
    d = {"entities": [], "facts": [], "aliases": []}
    for ln in txt.splitlines():
        parts = [x.strip() for x in ln.strip().strip("`").split("|")]
        if len(parts) < 3:
            continue
        tag = parts[0].upper()[:1]
        try:
            if tag == "F" and len(parts) >= 5:
                ex = int(re.sub(r"\D", "", parts[1]) or -1)
                if ex in valid:
                    d["facts"].append({"ex": ex, "subject": parts[2], "relation": parts[3], "object": parts[4],
                                       "status": (parts[5] if len(parts) > 5 else "fact").lower()})
            elif tag == "E" and len(parts) >= 4:
                ex = int(re.sub(r"\D", "", parts[1]) or -1)
                if ex in valid:
                    d["entities"].append({"ex": ex, "surface": parts[2], "canonical": parts[3]})
            elif tag == "A":
                d["aliases"].append({"alias": parts[1], "canonical": parts[2]})
        except ValueError:
            continue
    return d


DESC_RE = re.compile(r"\b(?:[Tt]he\s+)?(?:(eldest|youngest|only|second|third|fourth|fifth|elder|younger)\s+)?"
                     r"(son|daughter|wife|husband|widow|widower|child|brother|sister|mother|father)\s+of\s+"
                     r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})")
DESC_LOW = re.compile(r"\b(son|daughter|wife|husband|widow|widower|child|brother|sister|mother|father)\s+of\s+\w+", re.I)
SPOUSE_ROLES = {"wife", "husband", "widow", "widower"}


def is_desc(x):
    return bool(DESC_LOW.search(x or ""))
RESOLVE_SYS = ("You resolve references in a document. Given a descriptive reference and facts extracted from the "
               "document, name the single entity it refers to. Reply with the full name only, or 'unknown'.")


def normname(s):
    s = (s or "").lower()
    s = re.sub(r"^(the|a|an)\s+", "", s.strip())
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


class EntityMemory(Base):
    name = "ecm"

    def _paths(self):
        tag = f"{self.density}_{self.builder.replace(':', '-')}"
        return (os.path.join(self.ddir, f"mem_ecm2_{tag}.json"), os.path.join(self.ddir, f"mem_ecm3_{tag}_idle.json"))

    def build(self):
        p_write, p_idle = self._paths()
        if os.path.exists(p_write):
            d = json.load(open(p_write, encoding="utf-8"))
            self.raw, self.cost = d["raw"], d["cost"]
            cached = True
        else:
            segs = segments(self.chunks, 1200)

            def one(i_seg):
                i, seg = i_seg
                prompt = f"Excerpts:\n{core.render_chunks(seg)}\n\n{EXTRACT_FMT}"
                r = llm.call(self.builder, EXTRACT_SYS, prompt, max_tokens=3000, num_ctx=16384,
                             tag=f"build|ecm2|{self.density}|{i}")
                d = parse_lines(r["text"], {c["cid"] for c in seg})
                d["valid"] = [c["cid"] for c in seg]
                return r, d

            raw = []
            if self.workers > 1:
                with ThreadPoolExecutor(self.workers) as ex:
                    res = list(ex.map(one, enumerate(segs)))
            else:
                res = [one(x) for x in enumerate(segs)]
            for r, d in res:
                self._acc(r)
                raw.append(d)
            self.raw = raw
            json.dump({"raw": raw, "cost": self.cost}, open(p_write, "w", encoding="utf-8"), ensure_ascii=False)
            cached = False
        self.idle_cost = {"llm_in": 0, "llm_out": 0, "usd": 0.0, "calls": 0}
        self._consolidate(p_idle)
        self.hybrid = (core.BM25Index(self.chunks),
                       core.DenseIndex(self.chunks, os.path.join(self.ddir, f"emb_{self.density}_c300.npy"), llm.embed))
        out = dict(self.cost, cached_build=cached)
        out["idle"] = self.idle_cost
        return out

    # ---------------------------------------------------------- idle time
    def _consolidate(self, p_idle):
        self.cid2chunk_ = {c["cid"]: c for c in self.chunks}
        ents, facts_raw, alias_pairs = [], [], []
        for d in self.raw:
            valid = set(d.get("valid", []))
            for e in d.get("entities", []) or []:
                if isinstance(e, dict) and e.get("ex") in valid:
                    ents.append(e)
            for f in d.get("facts", []) or []:
                if isinstance(f, dict) and f.get("ex") in valid:
                    facts_raw.append(f)
            for a in d.get("aliases", []) or []:
                if isinstance(a, dict) and a.get("alias") and a.get("canonical"):
                    alias_pairs.append((normname(a["alias"]), normname(a["canonical"])))
        full_names = set()
        name_src = [{"canonical": f.get("subject")} for f in facts_raw] + [{"canonical": f.get("object")} for f in facts_raw] + ents
        for e in name_src:
            for k in ("canonical", "surface"):
                n = normname(e.get(k))
                if 2 <= len(n.split()) <= 3 and all(w[:1].isalpha() for w in n.split()) and not any(
                        w in ("of", "the", "and", "s") for w in n.split()):
                    raw_s = (e.get(k) or "").strip()
                    if raw_s[:1].isupper():
                        full_names.add(n)
        # grounding: a name enters the registry only if it literally occurs in the raw record
        alltext = " ".join(" " + " ".join(re.sub(r"[^a-z0-9 ]+", " ", c["text"].lower()).split()) + " "
                           for c in self.chunks)
        self.ungrounded = sorted(fn for fn in full_names if f" {fn} " not in alltext)
        full_names = {fn for fn in full_names if f" {fn} " in alltext}
        canon_of = {}
        for al, cn in alias_pairs:
            if al and cn and al != cn and not is_desc(al):
                canon_of.setdefault(al, cn)
        for e in ents:
            s_, c = normname(e.get("surface")), normname(e.get("canonical"))
            # write-time guesses for relational descriptions are not trusted (resolved at idle time instead)
            if s_ and c and s_ != c and c in full_names and not is_desc(s_):
                canon_of.setdefault(s_, c)
        firsts = defaultdict(set)
        for fn in full_names:
            firsts[fn.split()[0]].add(fn)

        def canon(x):
            n = normname(x)
            seen = 0
            while n in canon_of and seen < 5 and canon_of[n] != n:
                n = canon_of[n]
                seen += 1
            if n in full_names:
                return n
            if len(n.split()) == 1 and len(firsts.get(n, ())) == 1:
                return next(iter(firsts[n]))
            # ungrounded multi-word name (e.g. a mistyped surname): map to the only grounded name with that first name
            if len(n.split()) in (2, 3) and len(firsts.get(n.split()[0], ())) == 1:
                return next(iter(firsts[n.split()[0]]))
            return n

        facts_by = defaultdict(list)
        for f in facts_raw:
            for k in {canon(f.get("subject")), canon(f.get("object"))} - {""}:
                facts_by[k].append(f)
        low = [(c["cid"], " " + " ".join(re.sub(r"[^a-z0-9 ]+", " ", c["text"].lower()).split()) + " ")
               for c in self.chunks]
        name_chunks = defaultdict(list)
        for fn in full_names:
            for cid, t in low:
                if f" {fn} " in t:
                    name_chunks[fn].append(cid)
        # idle time: find relational descriptions in the raw text and resolve them with raw context
        occ = defaultdict(list)   # key -> [cid]
        inner_of = {}
        for c in self.chunks:
            for m in DESC_RE.finditer(c["text"]):
                inner = normname(m.group(3))
                if inner not in full_names:
                    continue
                desc = normname(m.group(0))
                key = f"{desc}@{c['cid']}" if m.group(2).lower() in SPOUSE_ROLES else desc
                occ[key].append(c["cid"])
                inner_of[key] = inner
        cache = json.load(open(p_idle, encoding="utf-8")) if os.path.exists(p_idle) else {}
        todo = [k for k in occ if k not in cache]

        def resolve(key):
            desc = key.split("@")[0]
            cid = occ[key][0]
            inner = inner_of[key]
            intro = [self.cid2chunk_[x] for x in name_chunks.get(inner, [])[:2] if x != cid]
            flines = []
            for f in sorted(facts_by.get(inner, []), key=lambda f: f.get("ex", 0))[:80]:
                ch = self.cid2chunk_[f["ex"]]["chapter"] if f.get("ex") in self.cid2chunk_ else "?"
                flines.append(f"- ch{ch}: {f.get('subject')} | {f.get('relation')} | {f.get('object')}")
            prompt = (f"Reference: \"{desc}\" as used in this passage:\n{core.render_chunks([self.cid2chunk_[cid]])}\n\n"
                      f"Passages introducing {inner.title()}:\n{core.render_chunks(intro) if intro else '(none)'}\n\n"
                      f"Facts about {inner.title()}:\n" + "\n".join(flines) +
                      "\n\nWhich person does the reference denote at that point in the document? Full name only.")
            r = llm.call(self.builder, RESOLVE_SYS, prompt, max_tokens=30, num_ctx=8192,
                         tag=f"idle|resolve2|{self.density}")
            return key, r
        if todo:
            if self.workers > 1:
                with ThreadPoolExecutor(self.workers) as ex:
                    res = list(ex.map(resolve, todo))
            else:
                res = [resolve(x) for x in todo]
            for key, r in res:
                self.idle_cost["llm_in"] += r["in_tokens"]
                self.idle_cost["llm_out"] += r["out_tokens"]
                self.idle_cost["usd"] += r["usd"]
                self.idle_cost["calls"] += 1
                lines_ = [x for x in r["text"].strip().splitlines() if x.strip()]
                ans = normname(lines_[-1]) if lines_ else ""
                cache[key] = ans if ans in full_names else None
            json.dump(cache, open(p_idle, "w", encoding="utf-8"), ensure_ascii=False)
        # mention index from extraction
        mentions = defaultdict(set)
        for e in ents:
            s_ = normname(e.get("surface"))
            if is_desc(s_):
                continue
            c = canon(e.get("canonical"))
            if c not in full_names:
                c = canon(e.get("surface"))
            mentions[c].add(e["ex"])
            if s_ and c in full_names:
                canon_of.setdefault(s_, c)
        for key, cids in occ.items():
            fn = cache.get(key)
            if fn:
                for cid in cids:
                    mentions[fn].add(cid)
        facts = defaultdict(list)
        for f in facts_raw:
            rec = (f["ex"], f.get("subject", ""), f.get("relation", ""), f.get("object", ""), f.get("status", "fact"))
            for k in {canon(f.get("subject")), canon(f.get("object"))} - {""}:
                facts[k].append(rec)
                mentions[k].add(f["ex"])
        # completeness pass: rescan raw text for every full name and every alias that maps to one
        patterns = defaultdict(set)
        for fn in full_names:
            patterns[fn].add(fn)
            first = fn.split()[0]
            if len(firsts[first]) == 1 and len(first) >= 4:
                patterns[fn].add(first)
        for al, cn in canon_of.items():
            c = canon(cn)
            if c in full_names and len(al) >= 5 and not is_desc(al):
                patterns[c].add(al)
        for fn, pats in patterns.items():
            for cid, t in low:
                if any(f" {p} " in t for p in pats):
                    mentions[fn].add(cid)
        self.full_names = full_names
        self._canon_of = canon_of
        self._desc_cache = cache
        self.mentions = {k: sorted(v) for k, v in mentions.items() if k}
        self.facts = {k: sorted(v, key=lambda x: x[0]) for k, v in facts.items()}
        self.links = defaultdict(set)
        for k, fs in self.facts.items():
            for ex, s, r, o, st in fs:
                for other in (canon(s), canon(o)):
                    if other != k and other in self.mentions:
                        self.links[k].add(other)
        self.cid2chunk = {c["cid"]: c for c in self.chunks}
        self.names = sorted(self.mentions, key=lambda x: -len(x))
        self.canon = canon
        self.hybrid = None

    # --------------------------------------------------------- query time
    def q_entities(self, question):
        qn = " " + normname(question) + " "
        found = []
        for n in self.names:
            if len(n) >= 4 and f" {n} " in qn and not any(n in f for f in found):
                found.append(n)
        return found

    def _hybrid_order(self, question):
        if self.hybrid is None:
            ddir = self.ddir
            self.hybrid = (core.BM25Index(self.chunks),
                           core.DenseIndex(self.chunks, os.path.join(ddir, f"emb_{self.density}_c300.npy"), llm.embed))
        s = core.rrf([self.hybrid[0].scores(question), self.hybrid[1].scores(question)])
        return sorted(range(len(self.chunks)), key=lambda i: -s[i])

    def context(self, q, budget):
        ents = self.q_entities(q["question"])
        if not ents:
            order = self._hybrid_order(q["question"])
            used = core.take_budget(self.chunks, order, budget)
            return "[Memory: no indexed entity matched; retrieved passages follow.]\n\n" + core.render_chunks(used), used
        per = {e: set(self.mentions.get(e, [])) for e in ents}
        allc = set().union(*per.values())
        tok = sum(self.cid2chunk[c]["tokens"] for c in allc)
        names = ", ".join(e.title() for e in ents)
        qwords = set(core.toks(q["question"]))
        if tok <= budget:
            used = [self.cid2chunk[c] for c in sorted(allc)]
            hdr = (f"[Memory guarantee: the first block below contains ALL {len(used)} passages of the record that "
                   f"mention {names}, in order. Anything about them not shown there is not in the record.]")
            rem = budget - tok
            extra = []
            linked = set().union(*(self.links.get(e, set()) for e in ents)) - set(ents)
            intros = sorted({min(self.mentions[l]) for l in linked if self.mentions.get(l)} - allc)
            for c in intros:
                ck = self.cid2chunk[c]
                if ck["tokens"] <= rem:
                    extra.append(ck)
                    rem -= ck["tokens"]
            if rem > 300:
                have = allc | {c["cid"] for c in extra}
                order = [i for i in self._hybrid_order(q["question"]) if i not in have]
                extra += core.take_budget(self.chunks, order, rem)
            ctx = hdr + "\n\n" + core.render_chunks(used)
            if extra:
                ctx += "\n\n[Other possibly relevant passages (introductions of linked entities, search results)]\n\n" + core.render_chunks(extra)
            return ctx, used + extra
        # over budget: complete fact timeline + most relevant raw passages
        lines = []
        for e in ents:
            fs = self.facts.get(e, [])
            lines.append(f"Timeline for {e.title()} (facts extracted from all {len(per[e])} passages mentioning it):")
            for ex, s, r, o, st in fs:
                ch = self.cid2chunk[ex]["chapter"]
                tag = "" if st == "fact" else f" [{st}]"
                lines.append(f"- ch{ch} ex{ex}: {s} {r} {o}{tag}")
        tl = "\n".join(lines)
        if core.ntok(tl) > budget * 0.5:
            keep, t = [], 0
            for ln in reversed(lines):
                lt = core.ntok(ln)
                if t + lt > budget * 0.5:
                    break
                keep.append(ln)
                t += lt
            tl = "(earliest timeline lines omitted for space)\n" + "\n".join(reversed(keep))
        rem = budget - core.ntok(tl)
        multi = {c for c in allc if sum(c in v for v in per.values()) >= 2}

        def prio(c):
            ch = self.cid2chunk[c]
            return (c in multi, len(qwords & set(core.toks(ch["text"]))), c)
        used, t = [], 0
        for c in sorted(allc, key=prio, reverse=True):
            ck = self.cid2chunk[c]
            if t + ck["tokens"] > rem:
                continue
            used.append(ck)
            t += ck["tokens"]
        hdr = (f"[Memory: {names} are mentioned in {len(allc)} passages. The timeline lists the facts extracted "
               f"from all of them; the most relevant passages follow verbatim.]")
        return hdr + "\n\n" + tl + "\n\n" + core.render_chunks(used), used


class EntityMemory2(EntityMemory):
    """ECM v2: paragraph-level mention index (verbatim paragraphs instead of whole
    300-token chunks, so filler around a mention is not paid for), recency-first
    packing when over budget, and first/last paragraphs of strongly linked
    entities (e.g. a spouse whose death ends a marriage)."""
    name = "ecm2"

    def build(self):
        out = super().build()
        self._para_index()
        return out

    def _para_index(self):
        paras = []
        for c in self.chunks:
            pos = 0
            for blk in re.split(r"\n\n+", c["text"]):
                if blk.strip():
                    nt = " " + " ".join(re.sub(r"[^a-z0-9 ]+", " ", blk.lower()).split()) + " "
                    paras.append({"pid": len(paras), "cid": c["cid"], "chapter": c["chapter"], "text": blk.strip(),
                                  "norm": nt, "tokens": core.ntok(blk)})
        self.paras = paras
        pats = defaultdict(set)
        firsts = defaultdict(set)
        for fn in self.full_names:
            firsts[fn.split()[0]].add(fn)
        for fn in self.full_names:
            pats[fn].add(fn)
            f0 = fn.split()[0]
            if len(firsts[f0]) == 1 and len(f0) >= 4:
                pats[fn].add(f0)
        for e in self.mentions:
            if e not in self.full_names and len(e) >= 4:
                pats[e].add(e)
        for al, cn in self._canon_of.items():
            c = self.canon(cn)
            if c in self.full_names and len(al) >= 5 and not is_desc(al):
                pats[c].add(al)
        for key, fn in self._desc_cache.items():
            if fn:
                pats[fn].add(key.split("@")[0])
        self.pats = pats
        self.ent_paras = {}
        for e, ps in pats.items():
            hits = [p["pid"] for p in paras if any(f" {x} " in p["norm"] for x in ps)]
            self.ent_paras[e] = hits
        # links = people co-mentioned in the same paragraph (robust to extraction errors);
        # people in an entity's first paragraph (its introduction: parents, household) come first
        para_ents = defaultdict(set)
        for e, ps in self.ent_paras.items():
            if e in self.full_names:
                for i in ps:
                    para_ents[i].add(e)
        self.link_w = defaultdict(collections.Counter)
        self.intro_links = {}
        for e, ps in self.ent_paras.items():
            for i in ps:
                for o in para_ents[i]:
                    if o != e:
                        self.link_w[e][o] += 1
            if ps:
                self.intro_links[e] = sorted(para_ents[ps[0]] - {e})

    def _render_paras(self, pids):
        out = []
        for i in sorted(set(pids)):
            p = self.paras[i]
            ch = "Epilogue" if p["chapter"] == 999 else f"Chapter {p['chapter']}"
            out.append(f"[{ch} | ex {p['cid']}] {p['text']}")
        return "\n".join(out)

    def context(self, q, budget):
        ents = [e for e in self.q_entities(q["question"]) if self.ent_paras.get(e)]
        if not ents:
            return super().context(q, budget)
        names = ", ".join(e.title() for e in ents)
        per = {e: self.ent_paras[e] for e in ents}
        allp = sorted(set().union(*map(set, per.values())))
        tok = sum(self.paras[i]["tokens"] + 8 for i in allp)
        linked = collections.Counter()
        for e in ents:
            for l, w in self.link_w.get(e, {}).items():
                if l not in ents and l in self.full_names and len(self.ent_paras.get(l, [])) <= 200:
                    linked[l] += w
            for l in self.intro_links.get(e, []):
                if l not in ents:
                    linked[l] += 1000  # introduction partners first
        link_p = []
        for l, _ in linked.most_common(8):
            ps = self.ent_paras.get(l, [])
            if ps:
                link_p += [ps[0], ps[-1]]
        link_p = [x for x in dict.fromkeys(link_p) if x not in allp]
        used_cids = set()
        if tok <= budget * 0.85:
            if getattr(self, "certify", True):
                hdr = (f"[Memory guarantee: the first block contains ALL {len(allp)} paragraphs of the record that mention "
                       f"{names}, in order. Anything about them not shown there is not in the record.]")
            else:
                hdr = f"[Memory: paragraphs of the record that mention {names}, in order.]"
            body = self._render_paras(allp)
            rem = budget - tok
            lp, t = [], 0
            for i in link_p:
                if t + self.paras[i]["tokens"] + 8 > rem:
                    break
                lp.append(i)
                t += self.paras[i]["tokens"] + 8
            ctx = hdr + "\n" + body
            if lp:
                ctx += "\n\n[First and latest paragraphs about closely linked entities]\n" + self._render_paras(lp)
            used_cids = {self.paras[i]["cid"] for i in allp + lp}
        else:
            # recency-first, round robin over entities, always keep each entity's first paragraph
            keep, t = set(), 0
            for e in ents:
                i = per[e][0]
                if i not in keep:
                    keep.add(i)
                    t += self.paras[i]["tokens"] + 8
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
                        if t + self.paras[i]["tokens"] + 8 <= lim:
                            keep.add(i)
                            t += self.paras[i]["tokens"] + 8
                            progress = True
            for i in link_p:
                if t + self.paras[i]["tokens"] + 8 > budget:
                    break
                keep.add(i)
                t += self.paras[i]["tokens"] + 8
            hdr = (f"[Memory: {len(allp)} paragraphs mention {names}; shown are each one's first paragraph and its "
                   f"most recent ones, plus linked entities. Older paragraphs are omitted.]")
            ctx = hdr + "\n" + self._render_paras(sorted(keep))
            used_cids = {self.paras[i]["cid"] for i in keep}
        return ctx, [self.cid2chunk[c] for c in sorted(used_cids)]


CARD_SYS = ("You consolidate memory about one entity of a long document so that a reader can later use it without "
            "rereading. Use only the given passages; never guess.")


class CardEntityMemory(EntityMemory):
    """ECM + consolidated profile cards for queried entities.

    A card is written once per entity by the builder model from ALL passages that
    mention the entity (plus introductions of linked entities) and cached, so its
    cost is amortised over every later question about that entity.  This moves
    multi-step reasoning (relations two steps away, current state after many
    changes) from query time to consolidation time.
    """
    name = "ecmc"

    def build(self):
        out = super().build()
        import threading
        self._lock = threading.Lock()
        self.card_path = os.path.join(self.ddir, f"mem_cards2_{self.density}_{self.builder.replace(':', '-')}.json")
        self.cards = json.load(open(self.card_path, encoding="utf-8")) if os.path.exists(self.card_path) else {}
        out["cards_cached"] = len(self.cards)
        return out

    def card(self, e):
        with self._lock:
            if e in self.cards:
                return self.cards[e]["text"]
        cids = sorted(self.mentions.get(e, []))
        tot = sum(self.cid2chunk[c]["tokens"] for c in cids)
        if tot > 12000:
            keep, t = [], 0
            for c in reversed(cids):
                ck = self.cid2chunk[c]
                if t + ck["tokens"] > 12000:
                    break
                keep.append(c)
                t += ck["tokens"]
            first = cids[:2]
            cids = sorted(set(keep) | set(first))
            note = f"(Only the earliest and the most recent of {len(self.mentions.get(e, []))} passages are shown.)\n"
        else:
            note = ""
        lw = getattr(self, "link_w", {}).get(e)
        top = [l for l, _ in lw.most_common(6)] if lw else sorted(self.links.get(e, set()))[:6]
        linked = sorted({x for l in top if self.mentions.get(l) for x in (min(self.mentions[l]), max(self.mentions[l]))} - set(cids))
        prompt = (f"Entity: {e.title()}\n\n{note}Passages that mention it:\n{core.render_chunks([self.cid2chunk[c] for c in cids])}\n\n"
                  f"First and latest passages of linked entities:\n{core.render_chunks([self.cid2chunk[c] for c in linked]) if linked else '(none)'}\n\n"
                  f"Write a compact profile card for {e.title()} (at most 220 words): identity and aliases; relations, "
                  f"including relatives or links two steps away when the passages allow; the CURRENT value of every "
                  f"changing state as of the end of the passages, each with the excerpt number that establishes it; a "
                  f"short dated list of changes; commitments and whether they were fulfilled; rules that apply to it; "
                  f"claims or rumors marked as unconfirmed. Write 'not stated' for anything the passages do not establish.")
        r = llm.call(self.builder, CARD_SYS, prompt, max_tokens=500, num_ctx=16384, tag=f"idle|card|{self.density}")
        with self._lock:
            self.cards[e] = {"text": r["text"].strip(), "in": r["in_tokens"], "out": r["out_tokens"], "usd": r["usd"],
                             "n_passages": len(self.mentions.get(e, []))}
            json.dump(self.cards, open(self.card_path, "w", encoding="utf-8"), ensure_ascii=False)
        return self.cards[e]["text"]

    def context(self, q, budget):
        ents = self.q_entities(q["question"])
        cards = [f"[Profile card: {e.title()} - consolidated from all {len(self.mentions.get(e, []))} passages mentioning it]\n{self.card(e)}"
                 for e in [x for x in ents if len(self.mentions.get(x, [])) <= 80][:3]]
        ctext = "\n\n".join(cards)
        ctx, used = super().context(q, max(800, budget - core.ntok(ctext)))
        return (ctext + "\n\n" + ctx if ctext else ctx), used


class FactMemory(Base):
    """Baseline: structured fact memory without raw text (Mem0-style store).

    Uses exactly the same write-time extraction as ECM (same cost), keeps only the
    extracted fact lines, and retrieves them by BM25 within the reader budget,
    shown in chronological order with chapter and status."""
    name = "facts"

    def build(self):
        p_write = os.path.join(self.ddir, f"mem_ecm2_{self.density}_{self.builder.replace(':', '-')}.json")
        if not os.path.exists(p_write):
            raise RuntimeError("build ECM first: the fact store reuses its write-time extraction")
        d = json.load(open(p_write, encoding="utf-8"))
        self.cost = d["cost"]
        cid2ch = {c["cid"]: c["chapter"] for c in self.chunks}
        lines = []
        for x in d["raw"]:
            valid = set(x.get("valid", []))
            for f in x.get("facts", []) or []:
                if isinstance(f, dict) and f.get("ex") in valid:
                    st = f.get("status", "fact")
                    lines.append({"ex": f["ex"], "ch": cid2ch.get(f["ex"], 0),
                                  "text": f"{f.get('subject','')} | {f.get('relation','')} | {f.get('object','')}"
                                          + ("" if st == "fact" else f" [{st}]")})
        for i, l in enumerate(lines):
            l["i"] = i
            l["tokens"] = core.ntok(l["text"]) + 6
        self.lines = lines
        from rank_bm25 import BM25Okapi
        self.bm = BM25Okapi([core.toks(l["text"]) for l in lines] or [["empty"]])
        return dict(self.cost, cached_build=True, n_facts=len(lines))

    def context(self, q, budget):
        s = self.bm.get_scores(core.toks(q["question"]))
        order = sorted(range(len(self.lines)), key=lambda i: -s[i])
        picked, t = [], 0
        for i in order:
            l = self.lines[i]
            if t + l["tokens"] > budget:
                continue
            picked.append(l)
            t += l["tokens"]
            if t >= budget * 0.97:
                break
        picked.sort(key=lambda l: (l["ex"], l["i"]))
        body = "\n".join(f"[Chapter {l['ch']} | ex {l['ex']}] {l['text']}" for l in picked)
        used = [{"cid": l["ex"], "start": -1, "end": -1} for l in picked]
        return "[Memory: facts extracted from the record (subject | relation | object), in order]\n" + body, []


NAMES_SYS = (
    "You index a long document for later lookup. For the excerpts given, write one line per item, nothing else:\n"
    "N|<excerpt number>|<canonical full name>|<type>   once for each distinct named entity (person, place, "
    "organization, object or artifact with a proper name, document, code identifier) in each excerpt.\n"
    "A|<alias>|<canonical full name>   when the text says an entity is called or known by another name, or "
    "refers to it by a first name, nickname or title whose full name these excerpts make clear.\n"
    "Be complete and terse."
)


def parse_names(txt, valid):
    d = {"entities": [], "facts": [], "aliases": []}
    for ln in txt.splitlines():
        parts = [x.strip() for x in ln.strip().strip("`").split("|")]
        if len(parts) < 3:
            continue
        tag = parts[0].upper()[:1]
        if tag == "N" and len(parts) >= 3:
            try:
                ex = int(re.sub(r"\D", "", parts[1]) or -1)
            except ValueError:
                continue
            if ex in valid:
                d["entities"].append({"ex": ex, "surface": parts[2], "canonical": parts[2]})
        elif tag == "A":
            d["aliases"].append({"alias": parts[1], "canonical": parts[2]})
    return d


class EntityMemory3(EntityMemory2):
    """ECM v3 = ECM v2 query/consolidation with a names-and-aliases-only write pass
    (no fact extraction): the complete mention index needs only a grounded name
    registry, aliases and idle-time descriptor resolution from raw text."""
    name = "ecm3"

    def _paths(self):
        tag = f"{self.density}_{self.builder.replace(':', '-')}"
        return (os.path.join(self.ddir, f"mem_names_{tag}.json"), os.path.join(self.ddir, f"mem_names_{tag}_idle.json"))

    def build(self):
        p_write, p_idle = self._paths()
        if os.path.exists(p_write):
            d = json.load(open(p_write, encoding="utf-8"))
            self.raw, self.cost = d["raw"], d["cost"]
            cached = True
        else:
            segs = segments(self.chunks, 1500)

            def one(i_seg):
                i, seg = i_seg
                prompt = f"Excerpts:\n{core.render_chunks(seg)}\n\nWrite the N and A lines now."
                r = llm.call(self.builder, NAMES_SYS, prompt, max_tokens=1500, num_ctx=16384,
                             tag=f"build|names|{self.density}|{i}")
                d = parse_names(r["text"], {c["cid"] for c in seg})
                d["valid"] = [c["cid"] for c in seg]
                return r, d
            if self.workers > 1:
                with ThreadPoolExecutor(self.workers) as ex:
                    res = list(ex.map(one, enumerate(segs)))
            else:
                res = [one(x) for x in enumerate(segs)]
            raw = []
            for r, d in res:
                self._acc(r)
                raw.append(d)
            self.raw = raw
            json.dump({"raw": raw, "cost": self.cost}, open(p_write, "w", encoding="utf-8"), ensure_ascii=False)
            cached = False
        self.idle_cost = {"llm_in": 0, "llm_out": 0, "usd": 0.0, "calls": 0}
        self._consolidate(p_idle)
        self.hybrid = (core.BM25Index(self.chunks),
                       core.DenseIndex(self.chunks, os.path.join(self.ddir, f"emb_{self.density}_c300.npy"), llm.embed))
        self._para_index()
        out = dict(self.cost, cached_build=cached)
        out["idle"] = self.idle_cost
        return out


class EntityMemory2NoCert(EntityMemory2):
    """Ablation: identical context, but without the completeness statement."""
    name = "ecm2n"
    certify = False


class CardEntityMemory2(CardEntityMemory, EntityMemory2):
    """ECM v2 + consolidated profile cards."""
    name = "ecm2c"


def make(name, **kw):
    a = kw.pop("args")
    import cmm
    import baselines2
    if name in baselines2.REGISTRY:
        return baselines2.REGISTRY[name](kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name in cmm.REGISTRY:
        return cmm.REGISTRY[name](kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name == "ecm2":
        return EntityMemory2(kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name == "ecm3":
        return EntityMemory3(kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name == "facts":
        return FactMemory(kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name == "ecm2n":
        return EntityMemory2NoCert(kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name == "ecm2c":
        return CardEntityMemory2(kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name == "summary":
        return SummaryMemory(kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name == "ecm":
        return EntityMemory(kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    if name == "ecmc":
        return CardEntityMemory(kw["text"], kw["chunks"], kw["ddir"], kw["density"], a)
    raise ValueError(name)
