"""Address-indexed verbatim memory for agent trajectories.

Questions about agent trajectories point into the record by address rather than by name: a step or turn number
("between step 72 and step 76", "at Turn 10"), an identifier (element [3675], options.py, _check_ordering_item,
cabinet 1) or a quoted observation.  Entity-indexed memory (CMM) finds few named entities there, and similarity
retrieval does not know that "step 72" is a position.  This memory keeps the record verbatim (paragraphs as rendered
by bench/ama_prepare.py, each starting with "Step N:") and builds, with no LLM call:
  step index        step number -> its paragraphs; the first paragraph holds the action
  action table      one line per step: the action, cut to fit (a table of contents of the whole trajectory)
  identifier scan   identifier-shaped strings of the question (bracketed numbers, paths and code names, object
                    names with an index, quoted strings) -> every step whose text contains them, split into steps
                    whose action contains them and steps whose observation does; the step lists are complete for
                    the literal string and are stated as such
At question time the context, within the reader budget, holds the task description, the action table (restricted
to the step range the question names, at most a fixed share of the budget), the identifier step lists, the
paragraphs of the named steps (first paragraph first, then those with the question's identifiers), the paragraphs
of quoted observations and of the step after them, paragraphs where the identifiers occur, and keyword (BM25)
paragraphs for the rest.

Variants (ablations): addr (all parts), addr_notab (no action table), addr_noid (no identifier scan),
addr_nostep (no step references from the question).
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import cmm  # noqa: E402

STEP_HEAD = re.compile(r"^Step (\d+)( \(continued\))?:")
REF = re.compile(r"(?i)\b(?:step|turn)s?\s*(?:#\s*)?(\d+)((?:\s*(?:,|,?\s*and|,?\s*or|&)\s*(?:(?:step|turn)s?\s*)?\d+)*)")
RANGE = re.compile(r"(?i)\b(?:between|from)\s+(?:step|turn)s?\s*(\d+)\s*(?:and|to|-|–|through|until)\s*"
                   r"(?:(?:step|turn)s?\s*)?(\d+)")
RANGE2 = re.compile(r"(?i)\b(?:step|turn)s?\s*(\d+)\s*(?:to|-|–|through)\s*(?:(?:step|turn)s?\s*)?(\d+)")
UPPER = re.compile(r"(?i)\b(?:before|until|up to|by|through|prior to|till)\s+(?:the\s+)?(?:step|turn)s?\s*(\d+)")
LOWER = re.compile(r"(?i)\b(?:after|since|following|from)\s+(?:the\s+)?(?:step|turn)s?\s*(\d+)")
NEXT_WORDS = re.compile(r"(?i)\b(next|result|resulting|outcome|subsequent|following|then|would|will|lead|transform)")
BRACKET = re.compile(r"\[\d+\]")
DQUOTE = re.compile(r"\"([^\"]{3,3000})\"|“([^”]{3,3000})”")
SQUOTE = re.compile(r"(?:(?<=\s)|^|(?<=\())['‘]([^'’\n]{2,120})['’](?=[\s.,;:?)!]|$)")
BTICK = re.compile(r"`([^`\n]{2,120})`")
CODE = re.compile(r"(?<![\w/.\-])(?:[A-Za-z_][\w\-]*(?:(?:\.|/|::|:)[\w\-]+)+|_+[A-Za-z]\w*|[a-z][a-z0-9]*_\w+|"
                  r"[a-z]+[A-Z]\w*|[A-Z][a-z0-9]+[A-Z]\w*|--?[a-z][\w\-]{2,})")
OBJNUM = re.compile(r"\b([a-z]{3,})\s(\d{1,3})\b")
OBJ_STOP = {"step", "steps", "turn", "turns", "line", "lines", "level", "than", "and", "the", "from", "with", "about",
            "after", "before", "until", "between", "times", "time", "count", "number", "top", "first", "last",
            "items", "total", "least", "most", "only", "were", "was", "are", "has", "had", "have", "all", "over",
            "under", "into", "onto", "for", "its", "their", "his", "her", "this", "that", "these", "those", "there"}


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def cut(s, max_tok):
    s = re.sub(r"\s+", " ", s).strip()
    if core.ntok(s) <= max_tok:
        return s
    ids = core.ENC.encode(s)[:max_tok]
    return core.ENC.decode(ids).rstrip() + " ..."


class AddrMem(cmm.ParaBase):
    name = "addr"
    use_table = True
    use_ids = True
    use_steps = True
    table_share = 0.4
    max_ids = 8

    def build(self):
        items = self.paras.items
        self.step_of = []
        self.steps = defaultdict(list)
        cur = -1
        for it in items:
            m = STEP_HEAD.match(it["text"])
            if m:
                cur = int(m.group(1))
            elif it["text"].startswith("Task description"):
                cur = -1
            self.step_of.append(cur)
            self.steps[cur].append(it["pid"])
        self.step_ids = sorted(s for s in self.steps if s >= 0)
        self.action, self.obs_head = {}, {}
        for s in self.step_ids:
            t = items[self.steps[s][0]]["text"]
            body = STEP_HEAD.sub("", t, count=1).strip()
            a, _, o = body.partition("\nObservation:")
            self.action[s] = a.replace("Action:", "", 1).strip()
            self.obs_head[s] = o.strip().split("\n")[0] if o else ""
        self.norm_text = [norm(it["text"]) for it in items]
        # action part of each step's first paragraph, for 'in the action' versus 'in the observation'
        self.norm_action = {s: norm(self.action[s]) for s in self.step_ids}
        return {"llm_in": 0, "llm_out": 0, "usd": 0.0, "steps": len(self.step_ids), "paras": len(items)}

    # ------------------------------------------------------------ question parsing
    def step_refs(self, qt):
        refs, lo, hi = [], None, None
        if self.use_steps:
            for m in REF.finditer(qt):
                refs.append(int(m.group(1)))
                refs += [int(x) for x in re.findall(r"\d+", m.group(2) or "")]
            for rx in (RANGE, RANGE2):
                for m in rx.finditer(qt):
                    a, b = sorted((int(m.group(1)), int(m.group(2))))
                    lo = a if lo is None else min(lo, a)
                    hi = b if hi is None else max(hi, b)
            if lo is None:
                ups = [int(m.group(1)) for m in UPPER.finditer(qt)]
                los = [int(m.group(1)) for m in LOWER.finditer(qt) if not re.match(r"(?i)from", m.group(0))]
                if ups:
                    hi = max(ups)
                if los:
                    lo = min(los)
        known = set(self.step_ids)
        refs = [r for r in dict.fromkeys(refs) if r in known]
        return refs, lo, hi

    def identifiers(self, qt):
        if not self.use_ids:
            return [], []
        ids = []
        quotes = []
        for m in DQUOTE.finditer(qt):
            s = (m.group(1) or m.group(2)).strip()
            (quotes if len(s) > 60 else ids).append(s)
        qt = DQUOTE.sub(" ", qt)  # the inside of a quotation is matched as a whole, not word by word
        for rx in (SQUOTE, BTICK):
            ids += [m.group(1).strip() for m in rx.finditer(qt)]
        ids += BRACKET.findall(qt)
        ids += [m.group(0) for m in CODE.finditer(qt) if len(m.group(0)) >= 4]
        ids += [f"{m.group(1)} {m.group(2)}" for m in OBJNUM.finditer(qt) if m.group(1).lower() not in OBJ_STOP]
        out, seen = [], set()
        for s in ids:
            k = norm(s).strip(".,;:")
            if len(k) < 2 or k in seen or re.fullmatch(r"(?:step|turn)s?\s*\d+", k):
                continue
            seen.add(k)
            out.append(k)
        return out, quotes

    def mentions(self, ident):
        """pids whose text contains the identifier (word boundaries at alphanumeric ends)"""
        pat = re.compile((r"(?<!\w)" if ident[0].isalnum() else "") + re.escape(ident) +
                         (r"(?!\w)" if ident[-1].isalnum() else ""))
        return [i for i, t in enumerate(self.norm_text) if ident in t and pat.search(t)]

    def locate_quote(self, quote):
        q = norm(quote)
        for n in (80, 50, 30):
            k = q[:n]
            ps = [i for i, t in enumerate(self.norm_text) if k in t]
            if ps:
                return ps
        return []

    # ------------------------------------------------------------ context
    def _id_lines(self, id_pids, id_act, id_obs):
        lines = []
        for k in id_pids:
            a, o = id_act[k], id_obs[k]
            ln = f"'{k}': in the action of {len(a)} step(s)" + (f" ({', '.join(map(str, a[:40]))}{', ...' if len(a) > 40 else ''})" if a else "")
            ln += f"; elsewhere in the text of {len(o)} other step(s)" + (f" ({', '.join(map(str, o[:25]))}{', ...' if len(o) > 25 else ''})" if 0 < len(o) <= 60 else "")
            lines.append(ln)
        return lines

    def action_table(self, scope, cap, keep):
        if not scope:
            return "", 0
        for a_tok, o_tok in ((40, 30), (30, 15), (24, 0), (16, 0), (10, 0), (6, 0)):
            lines = []
            for s in scope:
                ln = f"Step {s}: {cut(self.action[s], a_tok)}"
                if o_tok and self.obs_head.get(s):
                    ln += f" -> {cut(self.obs_head[s], o_tok)}"
                lines.append(ln)
            body = "\n".join(lines)
            tok = core.ntok(body)
            if tok <= cap:
                return body, tok
        # still too long: keep the steps near the question's addresses, mark the gaps
        lines, prev = [], None
        for s in scope:
            if s in keep:
                if prev is not None and s != prev + 1:
                    lines.append("...")
                lines.append(f"Step {s}: {cut(self.action[s], 10)}")
                prev = s
        body = "\n".join(lines)
        while lines and core.ntok(body) > cap:
            lines = lines[:-1]
            body = "\n".join(lines)
        return body, core.ntok(body)

    def context(self, q, budget):
        qt = q["question"]
        items = self.paras.items
        refs, lo, hi = self.step_refs(qt)
        ids, quotes = self.identifiers(qt)
        ids = ids[: self.max_ids]
        head, used, t = [], [], 0

        def add(pids):
            nonlocal t
            for i in pids:
                if i in used:
                    continue
                tk = items[i]["tokens"]
                if t + tk > budget:
                    continue
                used.append(i)
                t += tk
        # task description (first paragraph)
        if self.steps.get(-1):
            add(self.steps[-1][:1])
        # identifier step lists (complete for the literal string)
        id_act, id_obs, id_pids = {}, {}, {}
        for k in ids:
            ps = self.mentions(k)
            if not ps:
                continue
            id_pids[k] = ps
            st = sorted({self.step_of[i] for i in ps if self.step_of[i] >= 0})
            id_act[k] = [s for s in st if k in self.norm_action.get(s, "")]
            id_obs[k] = [s for s in st if s not in set(id_act[k])]
        lines = self._id_lines(id_pids, id_act, id_obs)
        if lines:
            hdr = ("[Step index: every step whose text contains each string from the question (exact match, complete "
                   "lists)]\n" + "\n".join(lines))
            head.append(hdr)
            t += core.ntok(hdr)
        # action table over the question's step range
        if self.use_table and self.step_ids:
            a = lo if lo is not None else self.step_ids[0]
            b = hi if hi is not None else self.step_ids[-1]
            scope = [s for s in self.step_ids if a <= s <= b]
            keep = set()
            for r in refs:
                keep |= set(range(r - 3, r + 4))
            for k in id_act:
                keep |= set(id_act[k])
            body, tok = self.action_table(scope, int(budget * self.table_share), keep)
            if body:
                rng = "" if (lo is None and hi is None) else f" (steps {a} to {b}, the range the question names)"
                hdr = f"[Action list: the agent's action at every step{rng}, cut to fit]\n" + body
                head.append(hdr)
                t += core.ntok(hdr)
        # paragraphs of the named steps: first paragraph (action) first
        nxt = bool(NEXT_WORDS.search(qt))
        firsts = [self.steps[r][0] for r in refs]
        if refs and nxt and (refs[-1] + 1) in self.steps:
            firsts.append(self.steps[refs[-1] + 1][0])
        add(firsts)
        # small named ranges: every step in the range
        if lo is not None and hi is not None and hi - lo <= 8:
            add([self.steps[s][0] for s in range(lo, hi + 1) if s in self.steps])
        # quoted observations and the step after them
        for qu in quotes:
            ps = self.locate_quote(qu)[:3]
            add(ps)
            for i in ps:
                s = self.step_of[i]
                if s >= 0:
                    add(self.steps[s][:1])
                    if (s + 1) in self.steps:
                        add(self.steps[s + 1][:1])
        # paragraphs of the named steps that contain the question's identifiers, then the rest by keyword score
        scores = self.paras.bm25_scores(qt)
        if refs:
            rest = [i for r in refs for i in self.steps[r][1:]]
            with_id = [i for i in rest if any(k in self.norm_text[i] for k in id_pids)]
            add(sorted(with_id, key=lambda i: -scores[i]))
        # paragraphs where identifiers occur in the action, then in the observation (rarer identifiers first)
        for k in sorted(id_pids, key=lambda k: len(id_pids[k])):
            add([self.steps[s][0] for s in id_act[k]][:20])
        for k in sorted(id_pids, key=lambda k: len(id_pids[k])):
            if len(id_pids[k]) <= 40:
                add(sorted(id_pids[k], key=lambda i: -scores[i])[:10])
        if refs:
            add(sorted([i for r in refs for i in self.steps[r][1:]], key=lambda i: -scores[i]))
        body = "[Record paragraphs, in order]\n" + self.paras.render(used) if used else ""
        ctx = "\n\n".join(head + ([body] if body else []))
        ctx, used = self.fill(q, ctx, used, budget - core.ntok(ctx))
        return ctx, self.paras.spans(used)


class AddrNoTable(AddrMem):
    name = "addr_notab"
    use_table = False


class AddrNoIds(AddrMem):
    name = "addr_noid"
    use_ids = False


class AddrNoSteps(AddrMem):
    name = "addr_nostep"
    use_steps = False


class AddrMem2(AddrMem):
    """Version 2: (a) a string that occurs in more than half of the steps
    is listed only by the steps whose action contains it, with its step count; (b) the action list starts with a
    count of the actions by their first word (the tool or verb) over the question's step range."""
    name = "addr2"
    target_index = False

    def _id_lines(self, id_pids, id_act, id_obs):
        lines, n_steps = [], max(1, len(self.step_ids))
        for k in id_pids:
            a, o = id_act[k], id_obs[k]
            if len(a) + len(o) > 0.5 * n_steps:
                ln = (f"'{k}': in the action of {len(a)} step(s)" +
                      (f" ({', '.join(map(str, a[:60]))}{', ...' if len(a) > 60 else ''})" if a else "") +
                      f"; occurs in the text of {len(a) + len(o)} of the {n_steps} steps")
            else:
                ln = (f"'{k}': in the action of {len(a)} step(s)" +
                      (f" ({', '.join(map(str, a[:60]))}{', ...' if len(a) > 60 else ''})" if a else "") +
                      f"; elsewhere in the text of {len(o)} other step(s)" +
                      (f" ({', '.join(map(str, o[:40]))}{', ...' if len(o) > 40 else ''})" if o else ""))
            lines.append(ln)
        return lines

    @staticmethod
    def verb(action):
        m = re.match(r"\s*([A-Za-z_][\w\-]*)", action)
        return m.group(1).lower() if m else "(none)"

    def _targets(self, scope):
        """identifier-shaped targets of the actions in scope -> [(step, verb)]"""
        out = defaultdict(list)
        for s in scope:
            a = self.action[s]
            ts = set(BRACKET.findall(a)) | {f"{m.group(1)} {m.group(2)}" for m in OBJNUM.finditer(a.lower())
                                             if m.group(1) not in OBJ_STOP}
            ts |= {m.group(0) for m in CODE.finditer(a) if len(m.group(0)) >= 4 and ("/" in m.group(0) or
                                                                                    "." in m.group(0))}
            for t_ in ts:
                out[t_].append((s, self.verb(a)))
        return out

    def action_table(self, scope, cap, keep):
        from collections import Counter
        cnt = Counter(self.verb(self.action[s]) for s in scope)
        head = ("Action counts by first word over these steps: " +
                ", ".join(f"{v} {n}" for v, n in cnt.most_common(15)) + "\n") if scope else ""
        extra = ""
        if self.target_index and scope:
            tg = self._targets(scope)
            rows = [f"{t_}: " + ", ".join(f"{s} {v}" for s, v in xs[:30]) for t_, xs in
                    sorted(tg.items(), key=lambda kv: kv[1][0][0]) if len(xs) >= 1]
            extra = "Actions grouped by their target (step and verb):\n" + "\n".join(rows) + "\n"
            if core.ntok(extra) > cap * 0.4:
                extra = ""
        body, tok = super().action_table(scope, cap - core.ntok(head + extra), keep)
        if not body:
            return "", 0
        body = head + extra + body
        return body, core.ntok(body)


class AddrMem3(AddrMem2):
    """Development version 3: version 2 plus the actions grouped by their target (object, element id, path)."""
    name = "addr3"
    target_index = True


TOOL_JSON = re.compile(r"^\s*([A-Za-z_][\w.\-]*)\s*(?::\s*|\()\s*(\{.*\})\s*\)?\s*$", re.S)
TOOL_TEXT = re.compile(r"^\s*([A-Za-z_][\w.\-]*)\s*:\s*(.+)$", re.S)
CD_PREFIX = re.compile(r"^\s*cd\s+\S+\s*&&\s*")


def short_path(v, keep=3):
    parts = [p for p in v.split("/") if p]
    return v if len(parts) <= keep else ".../" + "/".join(parts[-keep:])


def compress_action(a):
    """One informative line for a structured tool call (version 4): the tool name and its
    short argument values, long paths cut to their last components, a leading 'cd <dir> &&' dropped, long text
    arguments (code, file contents) replaced by their size.  Plain actions are returned unchanged."""
    a = a.strip()
    m = TOOL_JSON.match(a)
    if m:
        name, js = m.group(1), m.group(2)
        try:
            args = json.loads(js)
        except ValueError:
            args = dict(re.findall(r"\"(\w+)\"\s*:\s*\"((?:[^\"\\]|\\.){0,200})\"", js))
        out = [name]
        if isinstance(args, dict):
            for k, v in args.items():
                v = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
                v = CD_PREFIX.sub("", v.strip())
                if "\n" in v or len(v) > 160:
                    out.append(f"{k}=<{v.count(chr(10)) + 1} lines>")
                elif "/" in v and " " not in v:
                    out.append(short_path(v))
                elif k in ("command", "cmd", "query", "action", "operation") or len(v) <= 60:
                    out.append(v)
                else:
                    out.append(f"{k}={v[:60]}...")
        return " ".join(out)
    m = TOOL_TEXT.match(a)
    if m and len(a) > 60:
        rest = CD_PREFIX.sub("", m.group(2).strip())
        rest = " ".join(short_path(w) if "/" in w and len(w) > 30 else w for w in rest.split(" "))
        return f"{m.group(1)}: {rest}"
    return a


class AddrMem4(AddrMem2):
    """Version 4 (action lines of structured tool calls were cut to
    'str_replace_editor: {"command ...'): the action list shows compress_action() of each action instead of its
    prefix.  Everything else as version 2."""
    name = "addr4"

    def build(self):
        out = super().build()
        self.action_line = {s: compress_action(self.action[s]) for s in self.step_ids}
        return out

    def _plain_table(self, scope, cap, keep):
        if not scope:
            return "", 0
        for a_tok, o_tok in ((40, 30), (30, 15), (24, 0), (16, 0), (10, 0), (6, 0)):
            lines = []
            for s in scope:
                ln = f"Step {s}: {cut(self.action_line[s], a_tok)}"
                if o_tok and self.obs_head.get(s):
                    ln += f" -> {cut(self.obs_head[s], o_tok)}"
                lines.append(ln)
            body = "\n".join(lines)
            tok = core.ntok(body)
            if tok <= cap:
                return body, tok
        lines, prev = [], None
        for s in scope:
            if s in keep:
                if prev is not None and s != prev + 1:
                    lines.append("...")
                lines.append(f"Step {s}: {cut(self.action_line[s], 10)}")
                prev = s
        body = "\n".join(lines)
        while lines and core.ntok(body) > cap:
            lines = lines[:-1]
            body = "\n".join(lines)
        return body, core.ntok(body)

    def action_table(self, scope, cap, keep):
        from collections import Counter
        cnt = Counter(self.verb(self.action[s]) for s in scope)
        head = ("Action counts by first word over these steps: " +
                ", ".join(f"{v} {n}" for v, n in cnt.most_common(15)) + "\n") if scope else ""
        body, tok = self._plain_table(scope, cap - core.ntok(head), keep)
        if not body:
            return "", 0
        body = head + body
        return body, core.ntok(body)


class AddrStepOnly(AddrMem):
    """Prior-art control (AMA-Agent released code, commit 5acf87f, 2026-05-25; MESA's temporal view): the steps the
    question names (single steps, lists, short ranges) as raw paragraphs, the rest by keyword search; no action
    table, no identifier scan."""
    name = "addr_steponly"
    use_table = False
    use_ids = False


REGISTRY = {"addr": AddrMem, "addr_notab": AddrNoTable, "addr_noid": AddrNoIds, "addr_nostep": AddrNoSteps,
            "addr_steponly": AddrStepOnly, "addr2": AddrMem2, "addr3": AddrMem3, "addr4": AddrMem4}
