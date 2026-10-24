"""Event-type index over the verbatim record (designed on development worlds 4-5 of LongState-Aggregate).

Motivation: on global counting questions every memory and retrieval method scored
28-41%, the gold evidence about 81%, and the gold condition failed only when the true count was 0 (an empty context
makes the reader answer "unknown").  Counting and asserting absence need the complete set of paragraphs that narrate
one KIND of event, together with a statement that the set is complete.  The entity index cannot give this: the
question names no single entity.  CMM gives "every paragraph that mentions X"; this index gives "every paragraph that
narrates an event of kind T"; their intersection gives "every T event involving X".

write time   segments of about 1,500 tokens of paragraphs (labelled ¶<n>); the builder lists every event a paragraph
             reports as a change:   E|<¶n>|<event type>|<status>|<who or what>|<where>
             status: narrated (the text states it happens), reported (rumoured, claimed or planned), earlier (it
             happened before the document begins or long before this point).  States, opinions and scenery are not
             events.  The example types in the prompt are generic, not this benchmark's question types.
idle time    grounding: an event line counts only if its ¶ number belongs to the segment it was written for;
             normalisation: one builder call groups type labels that name the same kind of event.
query time   routing: one builder call maps the question to (a) the event kinds it asks to count, list or order and
             (b) the names (families, people, places) it restricts them to; only strings that occur in the question
             are accepted; the reader's answer is never seen.
             selection: every paragraph with a narrated event of those kinds that matches a restricting name, in the
             paragraph text or among the people the identity index resolved in it (evx4 only);
             context: that set in record order, each paragraph followed by the people the identity index resolved in
             it (evx4), under a statement that the set is complete (or that there is no such event); then paragraphs
             where those kinds are only reported or earlier, labelled as such; then the base method (CMM v4 for evx4,
             paragraph BM25 for evx) in the remaining budget.  If the set exceeds 60% of the budget, no statement is
             given and the paragraphs most relevant to the question (BM25) are kept.
Versions (development on worlds 4-5 only):
  v1 (results tagged _dev1 and _dev1code): routing on kinds only, no resolved names;
  v2 (class evx4v2, results tagged _dev2): restricting names, identity annotation, explicit 'no such event';
  v3 (classes evx/evx4, files evx3_*): the write prompt names the change itself rather than its cause and keeps
      'earlier' for explicit statements only (in world 4, v2 tagged 5 of 21 deaths by their cause and 2 as earlier);
      restricting names are reduced to the proper names they contain.
All calls go through the LLM cache.  Write and idle costs are stored with the index; routing calls are logged per
question to data/<ds>/evx_route_<builder>.jsonl (query-time builder calls, not reader tokens).
"""
import json
import os
import re
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import cmm
import core
import llm

SEG_TOK = 1500
STATUSES = ("narrated", "reported", "earlier")
ANN_TOK = 15  # allowance per shown paragraph for the resolved-names annotation

EVX_SYS_V1 = (  # write prompt of v1 and v2 (files evx_write_*, evx_idle_*)
    "You index a long document by the events it narrates, so that events of one kind can later be counted and "
    "listed. For each paragraph given (marked ¶<number>), list every event the paragraph reports as a change that "
    "takes place, one line per event, nothing else:\n"
    "E|<¶ number>|<event type>|<status>|<who or what, as named>|<where, if stated>\n"
    "<event type>: a short lowercase noun for the kind of change, reused consistently across the document (for "
    "example: arrival, departure, hiring, dismissal, purchase, sale, release, failure, appointment, injury).\n"
    "<status>: 'narrated' if the text states that the event happens; 'reported' if it is only rumoured, claimed, "
    "feared, promised or planned; 'earlier' if the text describes it as having happened before the document begins "
    "or long before this point.\n"
    "Do not list unchanging states, descriptions, opinions or scenery. Be complete and terse.")
EVX_SYS = (  # v3 (files evx3_*): name the change, not its cause; 'earlier' only when the text says so explicitly
    "You index a long document by the events it narrates, so that events of one kind can later be counted and "
    "listed. For each paragraph given (marked ¶<number>), list every event the paragraph reports as a change that "
    "takes place, one line per event, nothing else:\n"
    "E|<¶ number>|<event type>|<status>|<who or what, as named>|<where, if stated>\n"
    "<event type>: a short lowercase noun for the kind of change, reused consistently across the document (for "
    "example: arrival, departure, hiring, dismissal, purchase, sale, release, failure, appointment, injury). Name "
    "the change itself, not its cause or its circumstances (for example 'dismissal', not 'argument'; 'closure', not "
    "'flood'). If one sentence reports a change and what followed from it, list each change.\n"
    "<status>: 'narrated' if the text states that the event happens, including ordinary past-tense narration; "
    "'reported' if it is only rumoured, claimed, feared, promised or planned; 'earlier' only if the text says "
    "explicitly that it happened before the time being narrated (for example 'had ... some years before', "
    "'long ago').\n"
    "Do not list unchanging states, descriptions, opinions or scenery. Be complete and terse.")
EVX_SYS_V4 = EVX_SYS.replace(
    "If one sentence reports a change and what followed from it, list each change.",
    "If one sentence reports a change and what followed from it, list each change. Also list a change that the "
    "paragraph implies without naming it (for example, a shop that 'reopened' had closed; a ship that 'went down "
    "with all hands' was lost and its crew too).")
NORM_SYS = ("You group the labels of an event index. Labels that name the same kind of event (synonyms, inflections, "
            "near-paraphrases) form one group. Do not merge different kinds of events.")
ROUTE_SYS = ("You decide which kinds of events a question asks about. You never answer the question itself.")
LINE = re.compile(r"^\s*E\s*\|\s*¶?\s*(\d+)\s*\|([^|]*)\|([^|]*)\|?([^|]*)\|?(.*)$")


def _norm_label(s):
    return re.sub(r"\s+", " ", s.strip().lower().strip(".'\"`"))


def _key(s):
    return " " + " ".join(re.sub(r"[^a-z0-9' ]+", " ", s.lower()).split()) + " "


class EventIndex(cmm.ParaBase):
    name = "evx"
    narrated_share = 0.60
    other_share = 0.15
    prefix = "evx3"          # cache files of this version
    write_sys = EVX_SYS
    proper_filter = True     # v3: restricting names are reduced to the proper names they contain
    route_extra = ""         # v4: also the kinds whose events necessarily involve such an event
    certify = True           # False: control without any statement about completeness or absence

    def _paths(self):
        tag = f"{self.density}_{self.builder.replace(':', '-')}"
        return (os.path.join(self.ddir, f"{self.prefix}_write_{tag}.json"),
                os.path.join(self.ddir, f"{self.prefix}_idle_{tag}.json"),
                os.path.join(self.ddir, f"{self.prefix}_route_{tag}.jsonl"))

    # ------------------------------------------------------------------ write time
    seg_tok = SEG_TOK

    def _segments(self):
        segs, cur, tot = [], [], 0
        for it in self.paras.items:
            if cur and tot + it["tokens"] > self.seg_tok:
                segs.append(cur)
                cur, tot = [], 0
            cur.append(it["pid"])
            tot += it["tokens"]
        if cur:
            segs.append(cur)
        return segs

    def _write(self, p_write):
        if not core.build_lock(p_write):
            d = json.load(open(p_write, encoding="utf-8"))
            self.events, self.cost = d["events"], d["cost"]
            return True
        segs = self._segments()

        def one(i_seg):
            i, pids = i_seg
            prompt = f"Paragraphs:\n{self.paras.render(pids)}\n\nWrite the E lines now."
            r = llm.call(self.builder, self.write_sys, prompt, max_tokens=1500, num_ctx=16384,
                         tag=f"build|{self.prefix}|{os.path.basename(self.ddir)}|{self.density}|{i}")
            valid, out, bad = set(pids), [], 0
            for ln in r["text"].splitlines():
                m = LINE.match(ln)
                if not m:
                    continue
                pid, typ, st = int(m.group(1)), _norm_label(m.group(2)), _norm_label(m.group(3))
                if pid not in valid or not typ:
                    bad += 1  # grounding: the paragraph must belong to this segment
                    continue
                st = st if st in STATUSES else "narrated"
                out.append({"pid": pid, "type": typ, "status": st, "who": m.group(4).strip(),
                            "where": m.group(5).strip().strip("|").strip()})
            return r, out, bad
        try:
            with ThreadPoolExecutor(self.workers) as ex:
                res = list(ex.map(one, enumerate(segs)))
        except BaseException:
            core.build_unlock(p_write)
            raise
        self.events, self.ungrounded = [], 0
        for r, out, bad in res:
            self._acc(r, self.cost)
            self.events += out
            self.ungrounded += bad
        json.dump({"events": self.events, "cost": self.cost, "ungrounded": self.ungrounded, "segments": len(segs)},
                  open(p_write, "w", encoding="utf-8"), ensure_ascii=False)
        core.build_unlock(p_write)
        return False

    # ------------------------------------------------------------------ idle time
    def _normalise(self, p_idle):
        if os.path.exists(p_idle):
            d = json.load(open(p_idle, encoding="utf-8"))
            self.canon, self.idle_cost = d["canon"], d.get("cost", self.idle_cost)
            return
        cnt = Counter(e["type"] for e in self.events)
        labels = [f"{t} ({n})" for t, n in cnt.most_common()]
        prompt = ("Event-type labels of one document, with how many events carry each label:\n" + "\n".join(labels) +
                  "\n\nFor every label, write one line `<label>|<group name>`, where the group name is the most "
                  "frequent label of its group. Write every label exactly once.")
        r = llm.call(self.builder, NORM_SYS, prompt, max_tokens=4000, num_ctx=16384,
                     tag=f"idle|evxnorm|{os.path.basename(self.ddir)}|{self.density}")
        self._acc(r, self.idle_cost)
        canon = {t: t for t in cnt}
        for ln in r["text"].splitlines():
            if "|" in ln:
                a, b = (_norm_label(x) for x in ln.split("|", 1))
                a = re.sub(r"\s*\(\d+\)$", "", a)
                b = re.sub(r"\s*\(\d+\)$", "", b)
                if a in canon and b:
                    canon[a] = b
        self.canon = canon
        json.dump({"canon": canon, "cost": self.idle_cost, "labels": len(cnt)}, open(p_idle, "w", encoding="utf-8"),
                  ensure_ascii=False)

    def build(self):
        p_write, p_idle, self.p_route = self._paths()
        cached = self._write(p_write)
        self._normalise(p_idle)
        self.by_type = defaultdict(lambda: defaultdict(set))  # type -> status -> pids
        for e in self.events:
            self.by_type[self.canon.get(e["type"], e["type"])][e["status"]].add(e["pid"])
        self.type_counts = Counter({t: len(v["narrated"]) for t, v in self.by_type.items() if v["narrated"]})
        self._route_lock = threading.Lock()
        base = self._base_build()
        return dict(self.cost, cached_build=cached, idle=self.idle_cost, events=len(self.events),
                    types=len(self.type_counts), base=base)

    def _base_build(self):
        return {}

    # ------------------------------------------------------------------ query time
    def route(self, q):
        """event kinds, and the names (families, people, places) the question restricts them to"""
        vocab = ", ".join(f"{t} ({n})" for t, n in self.type_counts.most_common(150))
        prompt = (f"Kinds of events indexed in a long document, with how many paragraphs narrate each:\n{vocab}\n\n"
                  f"Question: {q['question']}\n\nWrite exactly two lines.\n"
                  f"TYPES: the kinds, exactly as listed, of the events that must be counted, listed or ordered across "
                  f"the document to answer the question{self.route_extra}; or none.\n"
                  f"FILTER: the names of people, families or places to which the question restricts these events, "
                  f"copied exactly as written in the question; or none.")
        r = llm.call(self.builder, ROUTE_SYS, prompt, max_tokens=200, num_ctx=16384,
                     tag=f"query|evxroute2|{os.path.basename(self.ddir)}|{q['qid']}")
        types, names = [], []
        m = re.search(r"TYPES:\s*(.*)", r["text"])
        if m and m.group(1).strip().lower() != "none":
            for x in m.group(1).split(","):
                x = _norm_label(x)
                x = self.canon.get(x, x)
                if x in self.type_counts and x not in types:
                    types.append(x)
        m = re.search(r"FILTER:\s*(.*)", r["text"])
        if m and m.group(1).strip().lower() != "none":
            for x in re.split(r",|;|\band\b|\bor\b", m.group(1)):
                x = x.strip().strip(".'\"`")
                if len(x) < 3 or _key(x) not in _key(q["question"]):
                    continue  # only strings that occur in the question are accepted
                cands = re.findall(r"[A-Z][\w'-]+(?: [A-Z][\w'-]+)*", x) if self.proper_filter else []
                for y in (cands or [x]):
                    if y not in names:
                        names.append(y)
        with self._route_lock:
            with open(self.p_route, "a", encoding="utf-8") as f:
                f.write(json.dumps({"qid": q["qid"], "types": types, "filter": names, "in": r["in_tokens"],
                                    "out": r["out_tokens"], "usd": r["usd"], "cached": r.get("cached", False)}) + "\n")
        return types, names

    def _base_context(self, q, budget):
        ctx, used = self.fill(q, "[Other paragraphs retrieved by keyword search, in order]", [], budget)
        return ctx, used

    def _who(self, pid):
        """people the identity index resolved in a paragraph (none without an identity index)"""
        return []

    def _matches(self, pid, names):
        if not names:
            return True
        hay = _key(self.paras.items[pid]["text"]) + " ".join(_key(w) for w in self._who(pid))
        return any(_key(n) in hay for n in names)

    def _render(self, pids):
        out = []
        for i in pids:
            line = self.paras.render([i])
            who = self._who(i)
            if who:
                line += f"  [people named here, as resolved by the index: {'; '.join(who)}]"
            out.append(line)
        return "\n".join(out)

    def context(self, q, budget):
        types, names = self.route(q)
        if not types:
            ctx, used = self._base_context(q, budget)
            return ctx, self.paras.spans(used) if used and isinstance(used[0], int) else used
        nar = [i for i in sorted(set().union(*(self.by_type[t]["narrated"] for t in types)))
               if self._matches(i, names)]
        oth = [i for i in sorted(set().union(*(self.by_type[t]["reported"] | self.by_type[t]["earlier"]
                                               for t in types)) - set(nar)) if self._matches(i, names)]
        kinds = " or ".join(f"'{t}'" for t in types)
        scope = f" that involves {', '.join(names)}" if names else ""
        tok = sum(self.paras.items[i]["tokens"] + ANN_TOK for i in nar)
        if not nar:
            hdr = (f"[Event index: the record narrates NO {kinds} event{scope}. No paragraph of the record narrates "
                   f"such an event as happening.]")
            keep = []
        elif tok <= budget * self.narrated_share:
            hdr = (f"[Event index: ALL {len(nar)} paragraphs of the record that narrate a {kinds} event{scope} as "
                   f"happening are listed below, in record order. An event of this kind{scope} that is not in this "
                   f"list is not narrated in the record.]")
            keep = nar
        else:
            s = self.paras.bm25_scores(q["question"])
            keep, t = [], 0
            for i in sorted(nar, key=lambda i: -s[i]):
                tk = self.paras.items[i]["tokens"] + ANN_TOK
                if t + tk <= budget * self.narrated_share:
                    keep.append(i)
                    t += tk
            keep.sort()
            hdr = (f"[Event index: {len(nar)} paragraphs of the record narrate a {kinds} event{scope}; the "
                   f"{len(keep)} most relevant to the question are listed below in record order. This list is NOT "
                   f"complete.]")
        if not self.certify:  # control: the same paragraphs, no statement about completeness or absence
            hdr = (f"[Event index: paragraphs of the record that narrate a {kinds} event{scope}, in record order]"
                   if keep else "")
        ctx = hdr + ("\n" + self._render(keep) if keep else "")
        used = list(keep)
        rem = budget - core.ntok(ctx)
        if oth:
            lim, ok, t = min(rem, budget * self.other_share), [], 0
            for i in oth:
                tk = self.paras.items[i]["tokens"] + ANN_TOK
                if t + tk <= lim:
                    ok.append(i)
                    t += tk
            if ok:
                blk = (f"\n\n[Paragraphs where a {kinds} event{scope} is only rumoured, claimed or planned, or "
                       f"described as having happened before the record (not narrated as happening)]\n" +
                       self._render(ok))
                ctx += blk
                used += ok
                rem -= core.ntok(blk)
        if rem > 300:
            bctx, bused = self._base_context(q, rem)
            ctx += "\n\n" + bctx
            if bused and isinstance(bused[0], dict):
                return ctx, self.paras.spans(used) + bused
            used += [i for i in bused if i not in set(used)]
        return ctx, self.paras.spans(used)


class EventIndexCMM4(EventIndex):
    """event-type index with the identity index of CMM v4: names resolved in each event paragraph are used to
    select and are shown; CMM v4 fills the remaining budget"""
    name = "evx4"

    def _base_build(self):
        self.cmm = cmm.CMM4(self.text, self.chunks, self.ddir, self.density, self.args)
        self.cmm.paras = self.paras
        return self.cmm.build()

    def _base_context(self, q, budget):
        return self.cmm.context(q, budget)  # (ctx, spans)

    def _who(self, pid):
        ents = self.cmm.para_ents.get(pid, ())
        return sorted(self.cmm.raw_name.get(e, e.title()) for e in ents if e in self.cmm.persons)


class EventIndexCMM4V2(EventIndexCMM4):
    """version 2 (development results tagged _dev2): v1 write prompt and cache files, names used as written"""
    name = "evx4v2"
    prefix = "evx"
    write_sys = EVX_SYS_V1
    proper_filter = False


class EventIndexCMM4V4(EventIndexCMM4):
    """development variant v4: implied changes are listed too, segments of about 800 tokens (files evx4w_*)"""
    name = "evx4v4"
    prefix = "evx4w"
    write_sys = EVX_SYS_V4
    seg_tok = 800
    route_extra = (", together with every listed kind whose events necessarily involve such an event, so that an "
                   "event indexed under a related kind is not missed")


class EventIndexV4(EventIndex):
    """control for the frozen v4: the same event index and routing, without the identity index (no resolved names
    for selection or display; paragraph BM25 fills the remaining budget)"""
    name = "evxv4"
    prefix = "evx4w"
    write_sys = EVX_SYS_V4
    seg_tok = 800
    route_extra = EventIndexCMM4V4.route_extra


IMPLY_SYS = ("You complete the vocabulary of an event index. You state which kinds of events necessarily include an "
             "event of another listed kind, so that a search for the second kind also finds them.")


class ImplyMixin:
    """v5 (development after the v4 test): at idle time one builder call states, over the kind vocabulary, which kinds
    necessarily include another listed kind (an event of kind B cannot happen unless an event of kind A happened to
    the same participant); every paragraph with a B event of a status then also counts as an A event of that status.
    Uses the v4 write pass (files evx4w_*); the implication map is stored in evx5_imply_*."""

    def build(self):
        out = super().build()
        tag = f"{self.density}_{self.builder.replace(':', '-')}"
        p_imp = os.path.join(self.ddir, f"evx5_imply_{tag}.json")
        if os.path.exists(p_imp):
            imp = json.load(open(p_imp, encoding="utf-8"))["imply"]
        else:
            kinds = [t for t, _ in self.type_counts.most_common(300)]
            prompt = ("Kinds of events indexed in one document:\n" + ", ".join(kinds) +
                      "\n\nFor every kind B in this list whose events necessarily include an event of another listed "
                      "kind A (B cannot happen to someone unless A happens to them), write one line `B|A`. Write "
                      "nothing for kinds that do not necessarily include another listed kind.")
            r = llm.call(self.builder, IMPLY_SYS, prompt, max_tokens=3000, num_ctx=16384,
                         tag=f"idle|evx5imply|{os.path.basename(self.ddir)}|{self.density}")
            self._acc(r, self.idle_cost)
            imp = defaultdict(list)
            for ln in r["text"].splitlines():
                if "|" in ln:
                    b, a = (_norm_label(x) for x in ln.split("|", 1))
                    if b in self.type_counts and a in self.type_counts and a != b and a not in imp[b]:
                        imp[b].append(a)
            imp = dict(imp)
            json.dump({"imply": imp, "cost": {k: r[k] for k in ("in_tokens", "out_tokens", "usd")}},
                      open(p_imp, "w", encoding="utf-8"), ensure_ascii=False)
        for b, targets in imp.items():
            for st, pids in list(self.by_type[b].items()):
                for a in targets:
                    self.by_type[a][st] |= pids
        self.type_counts = Counter({t: len(v["narrated"]) for t, v in self.by_type.items() if v["narrated"]})
        out["implications"] = sum(len(v) for v in imp.values())
        return out


class EventIndexCMM4V4NoCert(EventIndexCMM4V4):
    """control for v4: the same selected paragraphs and annotations, but no
    statement that the set is complete and none that an event is absent"""
    name = "evx4v4n"
    certify = False


class EventIndexCMM4V5(ImplyMixin, EventIndexCMM4V4):
    """v5 = v4 + the idle-time implication map (frozen after development on worlds 4-5, 67 vs 56 of 75)"""
    name = "evx4v5"


class EventIndexV5(ImplyMixin, EventIndexV4):
    """control for v5: the same index and implications, without the identity index"""
    name = "evxv5"


class EventIndexCMM4V5NoCert(EventIndexCMM4V5):
    """control for v5: the same selected paragraphs, no statement about completeness or absence"""
    name = "evx4v5n"
    certify = False


REGISTRY = {"evx": EventIndex, "evx4": EventIndexCMM4, "evx4v2": EventIndexCMM4V2, "evx4v4": EventIndexCMM4V4,
            "evxv4": EventIndexV4, "evx4v4n": EventIndexCMM4V4NoCert, "evx4v5": EventIndexCMM4V5,
            "evxv5": EventIndexV5, "evx4v5n": EventIndexCMM4V5NoCert}
