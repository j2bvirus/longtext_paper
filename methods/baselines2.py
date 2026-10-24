"""Additional baselines.

ledger  Extraction-based state ledger (MemStrata/Mem0-style competitor): at write time the builder
        extracts (subject | attribute | value | status) lines per 1,500-token segment; no raw text is
        kept.  At query time the facts about the entities named in the question are shown grouped by
        (subject, attribute) in record order, with the last entry of each group marked (latest), i.e.
        deterministic supersession; remaining budget is filled with BM25 over all fact lines.
"""
import collections
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import cmm
import core
import llm

LEDGER_SYS = (
    "You maintain a fact ledger for a long document. For the excerpts given, write one line per fact that they state, "
    "nothing else:\n"
    "F|<excerpt number>|<subject>|<attribute>|<value>|<status>\n"
    "subject: the person, object, place, group or rule the fact is about, written as its fullest name in the excerpts "
    "(resolve pronouns and descriptions such as 'her husband' to that name when the excerpts make it clear). "
    "attribute: a short lower-case attribute name; use one of these when it applies: lives in, moved to, born in, "
    "married to, widowed, alive, died, child of, parent of, sibling of, trade, holds, gave to, received from, "
    "inherited from, knows, told, promised, promise kept, promise broken, planned, rule, other. "
    "value: a name, place, item, secret or short phrase. status: fact, rumor (claimed but not confirmed), plan "
    "(intended but not done), or negated. Record every change of state and every relation, also ones that seem minor. "
    "Be terse."
)


ATTR_NORM = {  # attributes that supersede each other (same state, different wording)
    "lives in": "residence", "moved to": "residence", "lived in": "residence", "location": "residence",
    "resides in": "residence", "residence": "residence", "settled in": "residence", "travelled to": "residence",
    "traveled to": "residence", "returned to": "residence",
    "married to": "spouse", "spouse": "spouse", "wife of": "spouse", "husband of": "spouse", "widowed": "spouse",
    "trade": "trade", "occupation": "trade", "works as": "trade", "profession": "trade",
    "alive": "alive", "died": "alive", "dead": "alive", "status": "alive",
}


class StateLedger(cmm.ParaBase):
    name = "ledger"

    def build(self):
        cb = self.builder.replace(":", "-")
        p = os.path.join(self.ddir, f"ledger_write_{self.density}_{cb}.json")
        if not core.build_lock(p):
            d = json.load(open(p, encoding="utf-8"))
            cached = True
        else:
            segs, cur, tot = [], [], 0
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
                prompt = f"Excerpts:\n{core.render_chunks(seg)}\n\nWrite the F lines now."
                r = llm.call(self.builder, LEDGER_SYS, prompt, max_tokens=2500, num_ctx=16384,
                             tag=f"build|ledger|{os.path.basename(self.ddir)}|{self.density}|{i}")
                valid = {c["cid"] for c in seg}
                facts = []
                for ln in r["text"].splitlines():
                    parts = [x.strip() for x in ln.strip().strip("`").split("|")]
                    if len(parts) < 5 or parts[0].upper()[:1] != "F":
                        continue
                    try:
                        ex = int(re.sub(r"\D", "", parts[1]) or -1)
                    except ValueError:
                        continue
                    if ex not in valid:
                        continue
                    facts.append({"ex": ex, "s": parts[2], "a": parts[3].lower(), "v": parts[4],
                                  "st": (parts[5].lower() if len(parts) > 5 else "fact") or "fact"})
                return r, facts
            try:
                with ThreadPoolExecutor(self.workers) as ex:
                    res = list(ex.map(one, enumerate(segs)))
            except BaseException:
                core.build_unlock(p)
                raise
            facts = []
            for r, fs in res:
                self._acc(r, self.cost)
                facts += fs
            d = {"facts": facts, "cost": self.cost}
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            core.build_unlock(p)
            cached = False
        self.cost = d["cost"]
        cid2ch = {c["cid"]: c.get("chapter", 0) for c in self.chunks}
        self.facts = []
        for k, f in enumerate(sorted(d["facts"], key=lambda f: f["ex"])):
            st = "" if f["st"] in ("fact", "") else f" [{f['st']}]"
            f = dict(f, k=k, ch=cid2ch.get(f["ex"], 0))
            f["text"] = f"{f['s']} | {f['a']} | {f['v']}{st}"
            f["tokens"] = core.ntok(f["text"]) + 5
            self.facts.append(f)
        from rank_bm25 import BM25Okapi
        self.bm = BM25Okapi([core.toks(f["text"]) for f in self.facts] or [["empty"]])
        self.qn = cmm.NameGrep(self.text, self.chunks, self.ddir, self.density, self.args)
        self.qn.build()
        return dict(self.cost, cached_build=cached, n_facts=len(self.facts))

    def _subjects(self):
        if not hasattr(self, "_subj"):
            self._subj = {f["s"].lower() for f in self.facts if len(f["s"]) >= 4}
        return self._subj

    def context(self, q, budget):
        ql = q["question"].lower()
        # entities: capitalised names in the question, plus any ledger subject written in the question
        # (covers lower-case objects such as 'the bone seal')
        ents = {e.lower() for e in self.qn.q_names(q["question"])} | {s for s in self._subjects() if s in ql}
        mine = [f for f in self.facts if any(e in f["s"].lower() or e in f["v"].lower() for e in ents)]
        # one relational hop (as CMM's linked people): facts whose subject is a value of the entity's own facts
        hop = {f["v"].lower() for f in mine if f["s"].lower() in ents or any(e in f["s"].lower() for e in ents)}
        hop = {h for h in hop if h in self._subjects() and h not in ents}
        mk = {f["k"] for f in mine}
        near = [f for f in self.facts if f["k"] not in mk and (f["s"].lower() in hop or f["v"].lower() in hop)]
        groups = collections.OrderedDict()
        for f in mine + near:
            groups.setdefault((f["s"].lower(), ATTR_NORM.get(f["a"], f["a"])), []).append(f)
        for g in groups.values():
            g.sort(key=lambda f: f["k"])
        latest = {g[-1]["k"] for g in groups.values()}
        # own facts first (latest of every group, then older ones from the most recent backwards), then the
        # one-hop facts in the same order
        def ordered(fs):
            return [f for f in fs if f["k"] in latest] + sorted([f for f in fs if f["k"] not in latest], key=lambda f: -f["k"])
        order = ordered(mine) + ordered(near)
        keep, t = set(), 0
        for f in order:
            if t + f["tokens"] > budget * 0.85:
                continue
            keep.add(f["k"])
            t += f["tokens"]
        lines = []
        for (s, a), g in groups.items():
            for f in g:
                if f["k"] in keep:
                    lines.append((f["k"], f"[Ch {f['ch']}] {f['text']}" + ("  (latest)" if f["k"] in latest else "")))
        lines.sort()
        body = "\n".join(x for _, x in lines)
        rest = budget - t
        sc = self.bm.get_scores(core.toks(q["question"]))
        extra, t2 = [], 0
        for i in sorted(range(len(self.facts)), key=lambda i: -sc[i]):
            f = self.facts[i]
            if f["k"] in keep:
                continue
            if t2 + f["tokens"] > rest:
                continue
            extra.append(f)
            t2 += f["tokens"]
            if t2 >= rest * 0.95:
                break
        extra.sort(key=lambda f: f["k"])
        ctx = ("[Memory: fact ledger extracted from the record (subject | attribute | value). Entries about the "
               "entities in the question, in record order; within each subject and attribute the last entry is marked "
               "(latest).]\n" + body)
        if extra:
            ctx += "\n\n[Other possibly relevant facts (keyword search)]\n" + "\n".join(
                f"[Ch {f['ch']}] {f['text']}" for f in extra)
        return ctx, []


class StateLedgerRaw(StateLedger):
    """Facts + raw (Engram-style read path): the ledger view of the question's entities in up to half the budget,
    the rest filled with raw paragraphs by keyword search instead of more facts.  Same build as `ledger`."""
    name = "ledgerraw"

    def context(self, q, budget):
        ctx, _ = StateLedger.context(self, q, budget // 2)
        rem = budget - core.ntok(ctx)
        ctx, used = self.fill(q, ctx, [], rem)
        return ctx, self.paras.spans(used)


class StateLedgerStatus(StateLedger):
    """Within a (subject, attribute) group the '(latest)' mark goes to the last
    entry with status 'fact'; rumors, plans and negated entries never supersede a fact and are shown as such."""
    name = "ledger2"

    def context(self, q, budget):
        orig = [dict(f) for f in self.facts]
        try:
            # mark non-facts so that the parent's 'last entry of the group' rule skips them
            for f in self.facts:
                f["_nonfact"] = f["st"] not in ("fact", "")
            groups = collections.defaultdict(list)
            for f in self.facts:
                groups[(f["s"].lower(), ATTR_NORM.get(f["a"], f["a"]))].append(f)
            self._latest_fact = set()
            for g in groups.values():
                facts = [f for f in g if not f["_nonfact"]]
                if facts:
                    self._latest_fact.add(max(facts, key=lambda f: f["k"])["k"])
            ctx, sp = StateLedger.context(self, q, budget)
        finally:
            self.facts = orig
        # rewrite the latest marks: keep '(latest)' only on the last FACT of each group
        out = []
        for line in ctx.split("\n"):
            if line.endswith("  (latest)"):
                line = line[: -len("  (latest)")]
            out.append(line)
        ctx = "\n".join(out)
        marked = []
        for line in ctx.split("\n"):
            m = re.match(r"^\[Ch (\d+)\] (.*)$", line)
            if m:
                for f in self.facts:
                    if f["k"] in self._latest_fact and line.endswith(f["text"]) and f"[Ch {f['ch']}]" == f"[Ch {m.group(1)}]":
                        line = line + "  (latest)"
                        break
            marked.append(line)
        return "\n".join(marked).replace("the last entry is marked", "the last confirmed fact is marked"), sp


COMPACT_SYS = ("You compact the working context of a long-running task so that the work can continue without the "
               "original text. Preserve every fact, name, relation, decision, rule, commitment and changing state, "
               "with the latest value of each state and when it changed; keep rumors, plans and claims marked as such. "
               "Never invent anything.")


class Compaction(cmm.ParaBase):
    """Agent-style context compaction (as in coding agents' auto-compact): the record is read in order with a
    window of `summary` + `tail` tokens; whenever `tail` new tokens have arrived, the previous summary and that
    text are compacted into a new summary of at most `summary` tokens.  At question time the reader gets the
    final summary plus the most recent `tail` tokens of raw record.  Built once per record by the builder."""
    name = "compact4k"
    summary_tok = 2000
    tail_tok = 2000
    path_suffix = ""  # subclasses with a different compaction instruction keep their own cache file
    tag_suffix = ""
    cut_summary = True  # read only the first summary_tok tokens of a summary that overran its word limit

    def prompt_extra(self):
        return ""  # appended to every compaction prompt; empty for the production-style baseline

    def build(self):
        cb = self.builder.replace(":", "-")
        p = os.path.join(self.ddir, f"compact_{self.summary_tok}_{self.tail_tok}_{self.density}_{cb}{self.path_suffix}.json")
        if not core.build_lock(p):
            d = json.load(open(p, encoding="utf-8"))
            self.summary, self.cost = d["summary"], d["cost"]
            cached = True
        else:
            segs, cur, tot = [], [], 0
            for c in self.chunks:
                if cur and tot + c["tokens"] > self.tail_tok:
                    segs.append(cur)
                    cur, tot = [], 0
                cur.append(c)
                tot += c["tokens"]
            if cur:
                segs.append(cur)
            summary = "(nothing yet)"
            words = int(self.summary_tok * 0.7)
            try:
                for i, seg in enumerate(segs[:-1]):  # the last segment stays raw as the recent tail
                    prompt = (f"Summary of everything before:\n{summary}\n\nNew text:\n{core.render_chunks(seg)}\n\n"
                              f"Write the new compacted summary of everything so far (at most {words} words). "
                              f"Output only the summary.") + self.prompt_extra()
                    r = llm.call(self.builder, COMPACT_SYS, prompt, max_tokens=int(self.summary_tok * 1.3),
                                 num_ctx=32768, tag=f"build|compact{self.summary_tok}{self.tag_suffix}|{os.path.basename(self.ddir)}|{self.density}|{i}")
                    self._acc(r, self.cost)
                    summary = r["text"].strip()
            except BaseException:
                core.build_unlock(p)
                raise
            self.summary = summary
            json.dump({"summary": summary, "cost": self.cost, "n_compactions": max(0, len(segs) - 1)},
                      open(p, "w", encoding="utf-8"), ensure_ascii=False)
            core.build_unlock(p)
            cached = False
        toks = core.ENC.encode(self.summary, disallowed_special=())
        if self.cut_summary and len(toks) > self.summary_tok:
            self.summary = core.ENC.decode(toks[:self.summary_tok]) + " (summary cut at its size limit)"
        tail, t = [], 0
        for c in reversed(self.chunks):
            if t + c["tokens"] > self.tail_tok:
                break
            tail.append(c)
            t += c["tokens"]
        self.tail = list(reversed(tail))
        return dict(self.cost, cached_build=cached)

    def context(self, q, budget):
        ctx = (f"[Compacted summary of the earlier record]\n{self.summary}\n\n"
               f"[Most recent part of the record, verbatim]\n{core.render_chunks(self.tail)}")
        used = [{"cid": c["cid"], "start": c["start"], "end": c["end"]} for c in self.tail]
        return ctx, used


class Compaction16k(Compaction):
    name = "compact16k"
    summary_tok = 8000
    tail_tok = 8000


class CompactionNoCut(Compaction):
    """The compactor often overruns its word limit (24 of 54 final summaries
    exceed summary_tok; up to 3.5x), and Compaction then shows the reader only the first summary_tok tokens.  This
    variant reads the same cached summary in full; the extra reading tokens are counted as usual."""
    name = "compact4kn"
    cut_summary = False


class Compaction16kNoCut(Compaction16k):
    name = "compact16kn"
    cut_summary = False


class QuestionAwareCompaction(Compaction):
    """ORACLE upper bound of compaction (does compaction fail because importance cannot be
    judged before the need arises?).  Identical to compact4k except that every compaction step is told the questions
    that will be asked later, so the compactor knows what matters.  A real compactor cannot know them; the gap to
    compact4k measures the loss due to not knowing future needs, the gap to the memory measures the capacity limit."""
    name = "compact4kq"
    path_suffix = "_qaware"
    tag_suffix = "q"

    def prompt_extra(self):
        if not hasattr(self, "_qlist"):
            qs = [json.loads(l) for l in open(os.path.join(self.ddir, "questions_GOLD.jsonl"), encoding="utf-8")]
            self._qlist = "\n".join(f"- {q['question']}" for q in qs if not q.get("excluded"))
        return ("\n\nThese questions will be asked about the record later. Keep in the summary everything needed to "
                f"answer them, and drop what they do not need:\n{self._qlist}")


class QuestionAwareCompactionNoCut(QuestionAwareCompaction):
    name = "compact4kqn"
    cut_summary = False


VERIFY_SYS = ("You are a strict fact checker for a memory system. You check claims against source paragraphs and "
              "never accept a claim the paragraphs do not state. Later paragraphs override earlier ones.")


class VerifiedCards(cmm.CMM2Cards):
    """A small local model writes the profile
    card (as cmm2cq14/cmm2cq8) and the same model then checks every line adversarially in two independent passes
    against the entity's complete paragraph set (first, latest and cited paragraphs):
      pass A in record order: SUPPORTED / STALE (a later paragraph changed it; give the correction) / UNSUPPORTED;
      pass B latest-first, asking only whether the most recent relevant paragraph overrides the claim.
    A line is kept if both passes support it, replaced by the correction if either pass finds it stale, and dropped
    otherwise.  The certified set is what makes 'no later paragraph overrides it' checkable."""
    name = "cmm2cv14"
    card_builder = "ollama:qwen3:14b"
    drop_unsupported = True  # dev iteration 2 (correct-only) sets this to False
    verifier = None  # None: the writer verifies its own card

    def build(self):
        out = super().build()
        suffix = "" if self.drop_unsupported else "_correctonly"
        ver = "" if not self.verifier else "_by-" + self.verifier.replace(":", "-")
        wr = (self.card_builder or self.builder).replace(":", "-")
        self.vcard_path = os.path.join(self.ddir, f"cmm_vcards{suffix}_{self.density}_{wr}{ver}.json")
        self.vstore = json.load(open(self.vcard_path, encoding="utf-8")) if os.path.exists(self.vcard_path) else {}
        return out

    def _claims(self, card):
        out = []
        for ln in card.splitlines():
            t = ln.strip().lstrip("-*• ").strip()
            if len(t) < 6 or (t.startswith("**") and t.endswith("**")) or t.endswith(":**") or t.endswith(":"):
                continue
            out.append(t)
        return out[:40]

    def _verdicts(self, e, claims, pids, reverse):
        order = sorted(pids, reverse=reverse)
        paras = "\n".join(self.paras.render([i]) for i in order)
        numbered = "\n".join(f"{k + 1}. {c}" for k, c in enumerate(claims))
        how = ("Read the paragraphs from the most recent one backwards. For each claim about a current or final state, "
               "check whether the most recent relevant paragraph agrees with it." if reverse else
               "Check each claim against the paragraphs in record order.")
        prompt = (f"Entity: {e.title()}\n\nParagraphs ({'most recent first' if reverse else 'in record order'}):\n{paras}\n\n"
                  f"Claims from a memory card about {e.title()}:\n{numbered}\n\n{how} A claim is SUPPORTED only if a "
                  f"paragraph states it and no later paragraph changes it. If a later paragraph changes it, it is STALE: "
                  f"give the corrected claim with its paragraph number. If no paragraph states it, it is UNSUPPORTED. "
                  f"Output exactly one line per claim and nothing else:\n<number>|SUPPORTED\n<number>|STALE|<corrected "
                  f"claim>\n<number>|UNSUPPORTED")
        r = llm.call(self.verifier or self.card_builder or self.builder, VERIFY_SYS, prompt, max_tokens=1200, num_ctx=16384,
                     tag=f"idle|vcard{'B' if reverse else 'A'}|{os.path.basename(self.ddir)}|{self.density}")
        if not r.get("cached"):
            self._acc(r, self.lazy_cost)
        v = {}
        for ln in r["text"].splitlines():
            parts = [x.strip() for x in ln.strip().strip("`").split("|")]
            if len(parts) >= 2 and re.sub(r"\D", "", parts[0]):
                k = int(re.sub(r"\D", "", parts[0])) - 1
                tag = parts[1].upper()
                if tag.startswith("SUPPORT"):
                    v[k] = ("S", None)
                elif tag.startswith("STALE"):
                    v[k] = ("T", parts[2] if len(parts) > 2 and parts[2] else None)
                elif tag.startswith("UNSUPPORT"):
                    v[k] = ("U", None)
        return v

    def card(self, e):
        with self._lock:
            if e in self.vstore:
                return self.vstore[e]["text"]
        base = cmm.CMM.card(self, e)
        claims = self._claims(base)
        ps = self.ent_paras.get(e, [])
        cited = [int(x) for x in re.findall(r"(?:¶\s*\d+\s*\|\s*|¶\s*)(\d+)", base)]
        cited = [i for i in cited if 0 <= i < len(self.paras.items)][:20]
        pids, tok = [], 0
        for i in list(dict.fromkeys(list(reversed(ps[-12:])) + cited + ps[:2])):
            tk = self.paras.items[i]["tokens"]
            if tok + tk > 7000:
                continue
            pids.append(i)
            tok += tk
        va = self._verdicts(e, claims, pids, reverse=False)
        vb = self._verdicts(e, claims, pids, reverse=True)
        kept, n_stale, n_drop = [], 0, 0
        for k, c in enumerate(claims):
            a, b = va.get(k, ("U", None)), vb.get(k, ("U", None))
            if a[0] == "T" or b[0] == "T":
                corr = b[1] if b[0] == "T" and b[1] else a[1]
                if corr:
                    kept.append(f"- {corr} (corrected: a later paragraph changed this)")
                n_stale += 1
            elif (a[0] == "S" and b[0] == "S") or not self.drop_unsupported:
                kept.append(f"- {c}")
            else:
                n_drop += 1
        text = "\n".join(kept) if kept else "(no claim survived verification)"
        with self._lock:
            self.vstore[e] = {"text": text, "n_claims": len(claims), "stale": n_stale, "dropped": n_drop}
            json.dump(self.vstore, open(self.vcard_path, "w", encoding="utf-8"), ensure_ascii=False)
        return text


class VerifiedCards8(VerifiedCards):
    name = "cmm2cv8"
    card_builder = "ollama:qwen3:8b"


class CorrectOnlyCards(VerifiedCards):
    """Dev iteration 2: the verifier only replaces lines it finds STALE (with the correction); nothing is dropped.
    (Iteration 1 dropped 29-42% of lines, mostly true relations that the entity's own paragraphs cannot confirm.)"""
    name = "cmm2cw14"
    drop_unsupported = False


class CorrectOnlyCards8(VerifiedCards8):
    name = "cmm2cw8"
    drop_unsupported = False


# writer x verifier strength: small writer + large verifier, large writer + small verifier
class SmallWriteLargeFix14(CorrectOnlyCards):
    name = "cmm2cw14H"
    verifier = "claude:claude-haiku-4-5-20251001"


class SmallWriteLargeFix8(CorrectOnlyCards8):
    name = "cmm2cw8H"
    verifier = "claude:claude-haiku-4-5-20251001"


class LargeWriteSmallFix14(CorrectOnlyCards):
    name = "cmm2cwH14"
    card_builder = None  # cards written by the builder (Haiku), as cmm2c
    verifier = "ollama:qwen3:14b"


class AuditMixin:
    """(Naming: 'audit' here = idle-time index REVIEW, a step of the method under study; not the independent
    verification audit of our results.)
    Use the index reviewed at idle time by a second model (methods/audit_index.py): the reference resolutions
    are the audited ones (verifier, builder adjudication, widened-context retry) and pronoun-initial paragraphs
    resolved by the verifier are added to the person's index.  Everything else is the base version."""
    audit_by = "codex-gpt-6.1-sol"

    def _paths(self):
        p_write, p_idle = super()._paths()
        built = "" if self.builder == "claude:claude-haiku-4-5-20251001" else "_built-" + self.builder.replace(":", "-")
        audit = os.path.join(self.ddir, f"cmm_audit_{self.density}_{self.audit_by}{built}.json")
        if not os.path.exists(audit):
            raise RuntimeError(f"run methods/audit_index.py first: {audit}")
        a = json.load(open(audit, encoding="utf-8"))
        p_aud = p_idle.replace(".json", f"_audit-{self.audit_by}.json")
        if not os.path.exists(p_aud):
            json.dump(a["final"], open(p_aud, "w", encoding="utf-8"), ensure_ascii=False)
        self._repairs = {int(k): v for k, v in a.get("pronoun_repairs", {}).items()}
        return p_write, p_aud

    def build(self):
        out = super().build()
        for pid, e in getattr(self, "_repairs", {}).items():
            if e in self.persons:
                s = set(self.ent_paras.get(e, []))
                s.add(pid)
                self.ent_paras[e] = sorted(s)
                self.para_ents.setdefault(pid, set()).add(e)
        out["pronoun_repairs"] = len(getattr(self, "_repairs", {}))
        return out


class AuditedCMM4(AuditMixin, cmm.CMM4):
    name = "cmm4au"


class AuditedCMM1(AuditMixin, cmm.CMM):
    name = "cmmau"


class AuditedCMM4Q14(AuditMixin, cmm.CMM4):
    name = "cmm4auq"
    audit_by = "ollama-qwen3-14b"


class AuditedCMM4H(AuditMixin, cmm.CMM4):
    """For an index BUILT by a small model (--builder ollama:...) and audited by Haiku."""
    name = "cmm4auH"
    audit_by = "claude-claude-haiku-4-5-20251001"


class NewestFirstMixin:
    """Reading-order control (post-hoc analysis, after methods/position_analysis.py showed that
    the Qwen readers use the start of the context much better than its end, while chronological packing puts the
    latest state last).  Exactly the same paragraphs, header and certificate; inside every block the paragraphs
    are listed newest first, and one line says so.  Not part of the frozen method."""
    def build(self):
        out = super().build()
        P = self.paras

        def render(pids):
            res = []
            ann = getattr(P, "annot", None) or {}
            for i in sorted(set(pids), reverse=True):
                p = P.items[i]
                ch = "Epilogue" if p["chapter"] == 999 else f"Chapter {p['chapter']}"
                t = p["text"]
                for ph, name in ann.get(i, []):
                    k = t.find(ph)
                    if k >= 0 and t[k + len(ph):k + len(ph) + 3] != " [=":
                        t = t[:k + len(ph)] + f" [= {name}]" + t[k + len(ph):]
                res.append(f"[{ch} | ¶{i}] {t}")
            return "\n".join(res)
        P.render = render
        return out

    def context(self, q, budget):
        ctx, used = super().context(q, budget)
        return "[Within each block below, paragraphs are listed newest first.]\n" + ctx, used


class MapPlusCMM4(cmm.CMM4):
    """'Map + archive' (recall the whole while keeping details).  The reader gets the
    agent-style compacted summary of the whole record (the map; built once by Compaction, reused from its cache)
    followed by the CMM v4 context (the archive: complete, certified raw paragraphs of the queried entities).
    Reading tokens = summary (<= 2k, or <= 8k for the 16k variant) + the v4 budget."""
    name = "cmm4map"
    map_cls = Compaction

    def build(self):
        out = super().build()
        comp = self.map_cls(self.text, self.chunks, self.ddir, self.density, self.args)
        comp.build()
        self.map_summary = comp.summary
        return out

    def context(self, q, budget):
        ctx, used = super().context(q, budget)
        return (f"[Map: compacted summary of the whole record so far]\n{self.map_summary}\n\n"
                f"[Archive: verbatim paragraphs]\n{ctx}"), used


class MapPlusCMM4x16(MapPlusCMM4):
    name = "cmm4map16"
    map_cls = Compaction16k


class CMM4NoCert(cmm.CMM4):
    """CMM v4 with exactly the same paragraphs but without the completeness
    statement, to separate the statement from the content on continuity and aggregation (cf. cmmn for v1)."""
    name = "cmm4n"
    certify = False


class NewestFirstCMM4(NewestFirstMixin, cmm.CMM4):
    name = "cmm4r"


class NewestFirstParaBM25(NewestFirstMixin, cmm.ParaBM25):
    name = "pbm25r"


REGISTRY = {"cmm4r": NewestFirstCMM4, "pbm25r": NewestFirstParaBM25, "cmm4n": CMM4NoCert, "compact4kq": QuestionAwareCompaction, "compact4kn": CompactionNoCut,
            "compact16kn": Compaction16kNoCut, "compact4kqn": QuestionAwareCompactionNoCut, "cmm4map": MapPlusCMM4, "cmm4map16": MapPlusCMM4x16,
            "ledger": StateLedger, "ledgerraw": StateLedgerRaw,
            "ledger2": StateLedgerStatus, "compact4k": Compaction, "compact16k": Compaction16k,
            "cmm2cv14": VerifiedCards, "cmm2cv8": VerifiedCards8, "cmm2cw14": CorrectOnlyCards, "cmm2cw8": CorrectOnlyCards8, "cmm2cw14H": SmallWriteLargeFix14, "cmm2cw8H": SmallWriteLargeFix8, "cmm2cwH14": LargeWriteSmallFix14, "cmm4au": AuditedCMM4, "cmm4auq": AuditedCMM4Q14, "cmmau": AuditedCMM1, "cmm4auH": AuditedCMM4H}


from eventindex import REGISTRY as _EVX  # noqa: E402  (event-type index)
REGISTRY.update(_EVX)

from addrindex import REGISTRY as _ADDR  # noqa: E402  (address index for agent trajectories)
REGISTRY.update(_ADDR)

from addedbase import REGISTRY as _ADDED  # noqa: E402  (HippoRAG 2, contextual headers, small-to-big)
REGISTRY.update(_ADDED)
