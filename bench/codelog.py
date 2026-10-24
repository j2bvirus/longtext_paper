"""LongState-Code: a controlled long software-project record with exact ground truth.

Same principle as saga.py: a seeded simulator changes a project's state over sprints;
every change is an event rendered once into a commit message, review comment, chat line,
meeting note or design record; the record is assembled at any filler density (CI logs,
unrelated commits, chatter) so length changes while events, questions and answers stay
identical.  Gold evidence = event ids mapped to character spans.
"""
import argparse
import hashlib
import json
import os
import random
from collections import Counter, defaultdict

DOMAINS = ["billing", "auth", "search", "export", "sync", "notify", "report", "cache", "upload", "audit", "ledger", "geo"]
FILES = ["core", "api", "store", "worker", "handlers", "rules", "client", "jobs"]
VERBS = ["compute", "fetch", "resolve", "build", "sync", "load", "parse", "emit", "apply", "merge", "score", "flush",
         "render", "validate", "rotate", "index"]
NOUNS = ["invoice", "session", "token", "ledger", "batch", "quota", "report", "digest", "profile", "cursor", "bundle",
         "receipt", "shard", "policy", "snapshot", "tariff"]
PARAMS = ["user_id", "limit", "timeout", "retries", "region", "dry_run", "batch_size", "currency", "strict", "cursor",
          "max_age", "verbose", "tenant", "locale"]
FIRST = ["Dana", "Ilya", "Maren", "Tobin", "Sefa", "Oriel", "Kesh", "Lune", "Brann", "Pell", "Yara", "Corin", "Vesna",
         "Hadi", "Nilo", "Rhea"]
LAST = ["Kroll", "Abernet", "Voss", "Lindqvist", "Okafor", "Marchetti", "Tsang", "Halvorsen", "Quist", "Ibarra",
        "Delacroix", "Nakamura", "Ferro", "Brandt"]
LIBS = ["quarkjson", "fastlane-http", "tidepool", "ironcache", "glyphmail", "nimbus-orm", "velvetlog", "pikebus"]
SERVICES = ["api-gateway", "worker", "scheduler", "frontend", "reporting"]
CONFIGS = ["RETRY_LIMIT", "CACHE_TTL_SECONDS", "MAX_UPLOAD_MB", "SESSION_TIMEOUT_MIN", "BATCH_WINDOW_SEC", "RATE_LIMIT_RPS",
           "EXPORT_CHUNK_ROWS", "AUDIT_RETENTION_DAYS", "SEARCH_PAGE_SIZE", "SYNC_INTERVAL_SEC", "TOKEN_TTL_MIN",
           "NOTIFY_BATCH_SIZE"]
CI = ["CI build #{n} passed in {m}m{s}s.", "Nightly e2e suite: {n} tests, {m} flaky, rerun green.",
      "Dependabot opened a PR bumping a dev dependency; left for later.", "Lint job warning count dropped to {m}.",
      "Staging deploy {n} rolled out to 10% then 100% without alerts.", "Coverage report: {m}{s}.{n} percent lines covered."]
CHAT = ["{p}: anyone else seeing slow laptops after the OS update?", "{p}: lunch order is in the channel, last call.",
        "{p}: reminder that the retro is moved to Thursday.", "{p}: pushed a fix for the flaky date test, nothing else changed.",
        "{p}: the design review deck is in the shared drive.", "{p}: I'll be out Friday afternoon.",
        "{p}: renamed a few variables in the docs examples for readability; no API change."]
NOISE = ["Refactored the README badges and fixed a broken link.", "Updated copyright year in LICENSE headers.",
         "Tweaked the dashboard colour palette per the design team.", "Added a missing newline at end of file in several fixtures.",
         "Bumped the base image patch version; no code changes.", "Split a long unit test into two smaller ones.",
         "Cleaned up unused imports flagged by the linter."]


def srng(*p):
    return random.Random(int(hashlib.sha256("|".join(map(str, p)).encode()).hexdigest()[:16], 16))


class Sim:
    def __init__(self, seed, sprints=40):
        self.seed, self.n = seed, sprints
        r = self.r = srng("code", seed)
        firsts = r.sample(FIRST, 12)
        self.devs = []
        for i, f in enumerate(firsts):
            self.devs.append({"id": f"D{i:02d}", "first": f, "surname": r.choice(LAST)})
        self.dname = {d["id"]: f"{d['first']} {d['surname']}" for d in self.devs}
        mods = set()
        while len(mods) < 14:
            mods.add(f"{r.choice(DOMAINS)}/{r.choice(FILES)}.py")
        self.modules = sorted(mods)
        r.shuffle(self.modules)
        fns = set()
        while len(fns) < 30:
            fns.add(f"{r.choice(VERBS)}_{r.choice(NOUNS)}")
        self.fn_ids = []
        self.fn = {}           # fid -> current state
        for i, nm in enumerate(sorted(fns)):
            fid = f"F{i:02d}"
            ps = r.sample(PARAMS, r.choice([2, 3, 3, 4]))
            params = [[p, None if j == 0 else str(r.choice([1, 2, 3, 5, 10, 30, 60, 100]))] for j, p in enumerate(ps)]
            self.fn[fid] = {"orig": nm, "name": nm, "module": r.choice(self.modules), "params": params,
                            "deprecated": False, "replacement": None}
            self.fn_ids.append(fid)
        self.config = {k: str(r.choice([3, 5, 10, 15, 30, 60, 90, 120, 300])) for k in CONFIGS}
        self.owner = {m: r.choice(self.devs)["id"] for m in self.modules}
        self.reviewer = {m: r.choice([d["id"] for d in self.devs if d["id"] != self.owner[m]]) for m in self.modules}
        self.active = {d["id"]: True for d in self.devs}
        self.access = {d["id"]: r.random() < 0.3 for d in self.devs}
        self.libs = {s: {} for s in SERVICES}      # service -> lib -> version
        self.bugs = {}
        self.decisions = {}
        self.proposals = []
        self.claims = []
        self.events = []
        self.scenes = []
        self.hist = defaultdict(list)              # key -> [(eid, value)]
        self.eid = 0
        self.sprint = 0
        self.bill_mod = next((m for m in self.modules if m.startswith("billing")), self.modules[0])
        self.rule_call = {"domain": self.bill_mod.split("/")[0], "services": sorted(r.sample(SERVICES, 2))}
        self.rule_flag = {"flag": "ENABLE_PREFETCH", "key": "CACHE_TTL_SECONDS", "min": 60}

    def ev(self, kind, text, **data):
        e = {"id": f"E{self.eid:04d}", "type": kind, "sprint": self.sprint, "text": text[0].upper() + text[1:]}
        e.update(data)
        self.eid += 1
        self.events.append(e)
        self.scenes[-1]["events"].append(e["id"])
        return e["id"]

    def sig(self, fid):
        f = self.fn[fid]
        return ", ".join(p if v is None else f"{p}={v}" for p, v in f["params"])

    # ---------------------------------------------------------------- prologue
    def prologue(self):
        self.sprint = 1
        self.scenes.append({"sprint": 1, "kind": "prologue", "events": []})
        team = ", ".join(self.dname[d["id"]] for d in self.devs)
        self.ev("INIT_TEAM", f"Project kickoff notes. The team: {team}.", devs=[d["id"] for d in self.devs])
        for m in self.modules:
            e = self.ev("INIT_MODULE", f"Module ownership table: {m} is owned by {self.dname[self.owner[m]]}, "
                                       f"with {self.dname[self.reviewer[m]]} as designated reviewer.",
                        module=m, owner=self.owner[m], reviewer=self.reviewer[m])
            self.hist[("owner", m)].append((e, self.owner[m]))
        for fid in self.fn_ids:
            f = self.fn[fid]
            e = self.ev("INIT_FN", f"Initial import: `{f['name']}({self.sig(fid)})` lives in {f['module']}.", fn=fid)
            self.hist[("name", fid)].append((e, f["name"]))
            self.hist[("module", fid)].append((e, f["module"]))
            self.hist[("sig", fid)].append((e, self.sig(fid)))
        for k, v in self.config.items():
            e = self.ev("INIT_CONFIG", f"config/defaults.yaml sets {k}: {v}.", key=k, value=v)
            self.hist[("config", k)].append((e, v))
        for d in self.devs:
            if self.access[d["id"]]:
                e = self.ev("INIT_ACCESS", f"{self.dname[d['id']]} holds production database access.", dev=d["id"])
                self.hist[("access", d["id"])].append((e, True))
        rc = self.rule_call
        self.rule_call["eid"] = self.ev("RULE_CALL", f"Architecture rule (ADR-001): functions in the {rc['domain']} package may only "
                                                     f"be called by the {rc['services'][0]} and {rc['services'][1]} services.", **rc)
        rf = self.rule_flag
        self.rule_flag["eid"] = self.ev("RULE_FLAG", f"Ops rule: the {rf['flag']} feature flag may be turned on only while "
                                                     f"{rf['key']} is at least {rf['min']}.", **rf)
        self.rule_owner_eid = self.ev("RULE_OWNER", "Team policy: when a module owner leaves the team, ownership passes "
                                                    "automatically to that module's designated reviewer; no announcement is made.")

    # ------------------------------------------------------------------- events
    def step(self):
        r = self.r
        self.scenes.append({"sprint": self.sprint, "kind": "sprint", "events": []})
        for _ in range(r.choice([6, 7, 8, 9])):
            k = r.choices(["rename", "sig", "move", "config", "deprecate", "owner", "leave", "lib", "bug", "decision",
                           "proposal", "claim", "access"],
                          weights=[3, 3, 2, 4, 1, 2, 0.6 if self.sprint > 6 else 0, 3, 4, 1, 2, 1.5, 1.5])[0]
            getattr(self, "do_" + k)(srng("ev", self.seed, self.eid))

    def act(self, er):
        return er.choice([d["id"] for d in self.devs if self.active[d["id"]]])

    def do_rename(self, er):
        fid = er.choice([f for f in self.fn_ids if not self.fn[f]["deprecated"]])
        f = self.fn[fid]
        new = f"{er.choice(VERBS)}_{er.choice(NOUNS)}"
        if new in {x["name"] for x in self.fn.values()}:
            return
        old = f["name"]
        who = self.dname[self.act(er)]
        t = er.choice([f"[commit by {who}] Rename `{old}` to `{new}` in {f['module']}; all call sites updated.",
                       f"{who} merged a refactor: `{old}` is now called `{new}` (same behaviour).",
                       f"Code review ({who}): approved renaming `{old}` → `{new}`."])
        f["name"] = new
        e = self.ev("RENAME", t, fn=fid, old=old, new=new)
        self.hist[("name", fid)].append((e, new))

    def do_sig(self, er):
        fid = er.choice([f for f in self.fn_ids if not self.fn[f]["deprecated"]])
        f = self.fn[fid]
        who = self.dname[self.act(er)]
        opts = [p for p, v in f["params"] if v is not None]
        if opts and er.random() < 0.5:
            p = er.choice(opts)
            nv = str(er.choice([1, 2, 3, 5, 10, 20, 30, 45, 60, 100, 250]))
            for pv in f["params"]:
                if pv[0] == p:
                    pv[1] = nv
            t = f"[commit by {who}] `{f['name']}`: default {p} changed to {nv}."
            kind = "DEFAULT"
        elif len(f["params"]) < 5 and er.random() < 0.6:
            p = er.choice([x for x in PARAMS if x not in [q for q, _ in f["params"]]])
            v = str(er.choice([0, 1, 5, 10, 50]))
            f["params"].append([p, v])
            t = er.choice([f"[commit by {who}] `{f['name']}` gains an optional parameter {p} (default {v}).",
                           f"{who}: added keyword argument {p}={v} to `{f['name']}`."])
            kind = "ADD_PARAM"
        elif len(f["params"]) > 2:
            p, _ = f["params"].pop()
            t = f"[commit by {who}] Removed the unused parameter {p} from `{f['name']}`."
            kind = "DROP_PARAM"
        else:
            return
        e = self.ev(kind, t, fn=fid)
        self.hist[("sig", fid)].append((e, self.sig(fid)))

    def do_move(self, er):
        fid = er.choice([f for f in self.fn_ids if not self.fn[f]["deprecated"]])
        f = self.fn[fid]
        dest = er.choice([m for m in self.modules if m != f["module"]])
        who = self.dname[self.act(er)]
        t = er.choice([f"[commit by {who}] Moved `{f['name']}` from {f['module']} to {dest}.",
                       f"{who} relocated `{f['name']}` into {dest} to break an import cycle."])
        f["module"] = dest
        e = self.ev("MOVE", t, fn=fid, dest=dest)
        self.hist[("module", fid)].append((e, dest))

    def do_config(self, er):
        k = er.choice(CONFIGS)
        v = str(er.choice([3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 300, 600]))
        if v == self.config[k]:
            return
        who = self.dname[self.act(er)]
        t = er.choice([f"[ops] {who} set {k} to {v} in production after the load test.",
                       f"Config PR by {who} merged: {k} = {v}.",
                       f"Incident follow-up ({who}): {k} changed from {self.config[k]} to {v}."])
        self.config[k] = v
        e = self.ev("CONFIG", t, key=k, value=v)
        self.hist[("config", k)].append((e, v))

    def do_deprecate(self, er):
        live = [f for f in self.fn_ids if not self.fn[f]["deprecated"]]
        if len(live) < 6:
            return
        fid, rep = er.sample(live, 2)
        f = self.fn[fid]
        who = self.dname[self.act(er)]
        t = f"[commit by {who}] Deprecated `{f['name']}`; callers should use `{self.fn[rep]['name']}` instead."
        f["deprecated"], f["replacement"] = True, rep
        e = self.ev("DEPRECATE", t, fn=fid, replacement=rep, replacement_name=self.fn[rep]["name"])
        self.hist[("deprecated", fid)].append((e, True))

    def do_owner(self, er):
        m = er.choice(self.modules)
        new = self.act(er)
        if new == self.owner[m]:
            return
        t = er.choice([f"Ownership update: {self.dname[new]} takes over {m}.",
                       f"From this sprint {m} is maintained by {self.dname[new]} (previously {self.dname[self.owner[m]]})."])
        self.owner[m] = new
        e = self.ev("OWNER", t, module=m, owner=new)
        self.hist[("owner", m)].append((e, new))

    def do_leave(self, er):
        cand = [d for d, a in self.active.items() if a]
        if len(cand) < 7:
            return
        d = er.choice(cand)
        t = er.choice([f"{self.dname[d]} has left the company; farewell lunch on Friday.",
                       f"HR note: {self.dname[d]}'s last day was today."])
        self.active[d] = False
        e = self.ev("LEAVE", t, dev=d)
        self.hist[("active", d)].append((e, False))
        for m in self.modules:  # implicit transfer by rule (not narrated)
            if self.owner[m] == d:
                rv = self.reviewer[m] if self.active[self.reviewer[m]] else None
                if rv:
                    self.owner[m] = rv
                    self.hist[("owner", m)].append((e, rv))
        if self.access.get(d):
            self.access[d] = False
            self.hist[("access", d)].append((e, False))

    def do_lib(self, er):
        s = er.choice(SERVICES)
        lib = er.choice(LIBS)
        who = self.dname[self.act(er)]
        cur = self.libs[s].get(lib)
        if cur is None:
            v = f"{er.choice([1, 2, 3])}.{er.choice(range(10))}.{er.choice(range(10))}"
            t = f"[commit by {who}] The {s} service now depends on {lib} {v}."
            kind = "LIB_ADD"
        elif er.random() < 0.7:
            a, b, c = map(int, cur.split("."))
            v = f"{a}.{b + 1}.0" if er.random() < 0.6 else f"{a + 1}.0.0"
            t = f"[dependency] {who} upgraded {lib} in {s} from {cur} to {v}."
            kind = "LIB_UPGRADE"
        else:
            v = None
            t = f"[commit by {who}] Removed {lib} from the {s} service; it is no longer used there."
            kind = "LIB_REMOVE"
        if v:
            self.libs[s][lib] = v
        else:
            self.libs[s].pop(lib, None)
        e = self.ev(kind, t, service=s, lib=lib, version=v)
        self.hist[("lib", s, lib)].append((e, v))

    def do_bug(self, er):
        if self.bugs and er.random() < 0.55:
            bid = er.choice(sorted(self.bugs))
            b = self.bugs[bid]
            who = self.dname[self.act(er)]
            if b["status"] in ("open", "reopened"):
                if er.random() < 0.8:
                    b["status"] = "fixed"
                    t = f"[commit by {who}] Fixes {bid} ({b['title']})."
                else:
                    b["status"] = "wontfix"
                    t = f"{bid} closed as won't-fix by {who}: {b['title']} is expected behaviour."
            elif b["status"] == "fixed" and er.random() < 0.5:
                b["status"] = "reopened"
                t = f"QA reopened {bid} ({b['title']}): it reproduces again on staging."
            else:
                return
            e = self.ev("BUG_" + b["status"].upper(), t, bug=bid, status=b["status"])
        else:
            bid = f"PRJ-{100 + len(self.bugs)}"
            fid = er.choice(self.fn_ids)
            title = er.choice(["wrong rounding", "timeout under load", "duplicate rows", "stale cache entry",
                               "crash on empty input", "locale mix-up", "missing audit record"])
            b = {"status": "open", "title": f"{title} in `{self.fn[fid]['name']}`", "fn": fid}
            self.bugs[bid] = b
            t = f"New ticket {bid} opened: {b['title']} (reported by {self.dname[self.act(er)]}); status open."
            e = self.ev("BUG_OPEN", t, bug=bid, status="open", fn=fid)
            self.bugs[bid]["open_eid"] = e
        self.hist[("bug", bid)].append((e, self.bugs[bid]["status"]))

    def do_decision(self, er):
        topic = er.choice(["caching", "message queue", "JSON parsing", "HTTP client", "ORM"])
        lib = er.choice(LIBS)
        who = self.dname[self.act(er)]
        prev = self.decisions.get(topic)
        if prev and prev == lib:
            return
        t = (f"ADR by {who}: we will use {lib} for {topic}" + (f", superseding the earlier choice of {prev}." if prev else "."))
        self.decisions[topic] = lib
        e = self.ev("DECISION", t, topic=topic, lib=lib)
        self.hist[("decision", topic)].append((e, lib))

    def do_proposal(self, er):
        fid = er.choice(self.fn_ids)
        who = self.dname[self.act(er)]
        dest = er.choice([m for m in self.modules if m != self.fn[fid]["module"]])
        n = 400 + len(self.proposals)
        t = er.choice([f"PR #{n} by {who} proposes moving `{self.fn[fid]['name']}` to {dest}; closed without merging after review.",
                       f"{who} opened PR #{n} to move `{self.fn[fid]['name']}` into {dest}, but it was abandoned."])
        e = self.ev("PROPOSAL", t, fn=fid, dest=dest, pr=n)
        self.proposals.append({"eid": e, "fn": fid, "dest": dest, "pr": n})

    def do_claim(self, er):
        k = er.choice(CONFIGS)
        wrong = str(er.choice([7, 25, 40, 75, 150, 250, 900]))
        if wrong == self.config[k]:
            return
        who = self.dname[self.act(er)]
        t = er.choice([f"Chat — {who}: pretty sure {k} is {wrong} now, someone told me in standup.",
                       f"{who} mentioned in passing that {k} had been set to {wrong}, but nobody checked."])
        e = self.ev("CLAIM", t, key=k, claimed=wrong)
        self.claims.append({"eid": e, "key": k})

    def do_access(self, er):
        d = self.act(er)
        grant = not self.access.get(d)
        who = self.dname[self.act(er)]
        t = (f"Security: {who} granted {self.dname[d]} production database access for the migration."
             if grant else f"Security: {self.dname[d]}'s production database access was revoked by {who}.")
        self.access[d] = grant
        e = self.ev("ACCESS", t, dev=d, granted=grant)
        self.hist[("access", d)].append((e, grant))

    def run(self):
        self.prologue()
        for s in range(2, self.n + 1):
            self.sprint = s
            self.step()


def questions(sim, rng, per=22):
    Q = []
    D = sim.dname

    def add(t, q, ans, ev, fid=None):
        if fid is not None:  # the whole rename chain is needed to link old names to the current one
            ev = list(ev) + [e for e, _ in sim.hist[("name", fid)]]
        Q.append({"qtype": t, "question": q, "answer": ans, "evidence": sorted(set(ev)), "evidence_core": sorted(set(ev))})

    tok = lambda v: {"kind": "token", "gold": str(v), "aliases": [str(v)]}
    yn = lambda b: {"kind": "yesno", "gold": "yes" if b else "no", "aliases": ["yes" if b else "no"]}
    pers = lambda d: {"kind": "person", "gold": D[d], "aliases": [D[d]]}
    fids = list(sim.fn_ids)
    rng.shuffle(fids)
    renamed = [f for f in fids if len(sim.hist[("name", f)]) >= 2]
    for f in renamed[:per]:
        add("FN_NAME_NOW", f"What is the current name of the function originally introduced as `{sim.fn[f]['orig']}`?",
            tok(sim.fn[f]["name"]), [e for e, _ in sim.hist[("name", f)]], f)
    for f in fids[:per]:
        nm = sim.fn[f]["name"]
        add("FN_MODULE_NOW", f"In which module is the function now called `{nm}` defined at the end of the record?",
            tok(sim.fn[f]["module"]), [e for e, _ in sim.hist[("module", f)]], f)
    withdef = [(f, p, v) for f in fids for p, v in sim.fn[f]["params"] if v is not None]
    rng.shuffle(withdef)
    for f, p, v in withdef[:per]:
        add("FN_DEFAULT_NOW", f"What is the current default value of the {p} parameter of the function now called "
                              f"`{sim.fn[f]['name']}`?", tok(v), [e for e, _ in sim.hist[("sig", f)]], f)
    for f in fids[:per]:
        add("FN_NPARAMS", f"How many parameters does the function now called `{sim.fn[f]['name']}` take?",
            tok(len(sim.fn[f]["params"])), [e for e, _ in sim.hist[("sig", f)]], f)
    keys = list(CONFIGS)
    rng.shuffle(keys)
    claimed = {c["key"] for c in sim.claims}
    for k in sorted(keys, key=lambda k: k not in claimed)[:per]:
        add("CONFIG_NOW", f"What is the current production value of {k}?", tok(sim.config[k]),
            [sim.hist[("config", k)][-1][0]] + [c["eid"] for c in sim.claims if c["key"] == k])
    bugs = sorted(sim.bugs)
    rng.shuffle(bugs)
    n = 0
    for bid in bugs:
        oe = sim.bugs[bid]["open_eid"]
        k = rng.choice(CONFIGS)
        prior = [(e, v) for e, v in sim.hist[("config", k)] if e < oe]
        if not prior or any(sim.events[int(e[1:])]["sprint"] == sim.events[int(oe[1:])]["sprint"] for e, _ in sim.hist[("config", k)]):
            continue
        add("CONFIG_AT_TICKET", f"What was the production value of {k} when ticket {bid} was opened?", tok(prior[-1][1]),
            [prior[-1][0], oe])
        n += 1
        if n >= per:
            break
    for m in sim.modules:
        add("OWNER_NOW", f"Who owns {m} at the end of the record?", pers(sim.owner[m]),
            [e for e, _ in sim.hist[("owner", m)]] + [sim.rule_owner_eid])
    for bid in bugs[:per]:
        st = sim.bugs[bid]["status"]
        add("BUG_STATUS", f"What is the status of ticket {bid}? Answer open, fixed, reopened or wontfix.",
            {"kind": "label4", "gold": st, "aliases": [st]}, [e for e, _ in sim.hist[("bug", bid)]])
    dep = [f for f in fids if sim.fn[f]["deprecated"]]
    for f in dep[:per]:
        rep = sim.fn[f]["replacement"]
        add("DEPRECATED_BY", f"Which function should callers of the deprecated `{sim.fn[f]['name']}` use instead "
                             f"(give its current name)?", tok(sim.fn[rep]["name"]),
            [e for e, _ in sim.hist[("deprecated", f)]] + [e for e, _ in sim.hist[("name", rep)]], f)
    pairs = [(s, l) for s in SERVICES for l in LIBS if sim.hist[("lib", s, l)]]
    rng.shuffle(pairs)
    for s, l in pairs[:per]:
        v = sim.libs[s].get(l)
        add("LIB_VERSION", f"Which version of {l} does the {s} service use now? Answer 'none' if it no longer uses it.",
            tok(v) if v else {"kind": "none", "gold": "none", "aliases": ["none"]}, [e for e, _ in sim.hist[("lib", s, l)]])
    rc = sim.rule_call
    cand = [(f, s) for f in fids for s in SERVICES]
    rng.shuffle(cand)
    n_yes = n_no = 0
    for f, s in cand:
        inside = sim.fn[f]["module"].startswith(rc["domain"] + "/")
        ok = (not inside) or (s in rc["services"])
        if not inside and rng.random() < 0.7:
            continue
        if ok and n_yes >= per // 2 or (not ok) and n_no >= per // 2:
            continue
        add("RULE_CALL", f"Under the architecture rules, may the {s} service call the function now called "
                         f"`{sim.fn[f]['name']}` at the end of the record? Answer yes or no.",
            yn(ok), [rc["eid"]] + [e for e, _ in sim.hist[("module", f)]], f)
        n_yes += ok
        n_no += not ok
    rf = sim.rule_flag
    v = int(sim.config[rf["key"]])
    add("RULE_FLAG", f"May the {rf['flag']} flag be turned on at the end of the record? Answer yes or no.", yn(v >= rf["min"]),
        [rf["eid"], sim.hist[("config", rf["key"])][-1][0]])
    n_no = 0
    for p in sim.proposals:
        moved = any(m == p["dest"] for _, m in sim.hist[("module", p["fn"])])
        if moved or n_no >= per // 2:
            continue
        add("EVER_IN_MODULE", f"Was the function now called `{sim.fn[p['fn']]['name']}` ever located in {p['dest']} "
                              f"(under any of its names)? Answer yes or no.", yn(False),
            [p["eid"]] + [e for e, _ in sim.hist[("module", p["fn"])]], p["fn"])
        n_no += 1
    past = [(f, m, e) for f in fids for (e, m) in sim.hist[("module", f)][:-1] if m != sim.fn[f]["module"]]
    rng.shuffle(past)
    seen = set()
    for f, m, e in past:
        if (f, m) in seen or len(seen) >= n_no:
            continue
        seen.add((f, m))
        add("EVER_IN_MODULE", f"Was the function now called `{sim.fn[f]['name']}` ever located in {m} "
                              f"(under any of its names)? Answer yes or no.", yn(True),
            [e for e, _ in sim.hist[("module", f)]], f)
    devs = [d["id"] for d in sim.devs]
    rng.shuffle(devs)
    for d in devs[:per]:
        ev = [e for e, _ in sim.hist[("access", d)]] + [e for e, _ in sim.hist[("active", d)]]
        add("ACCESS_NOW", f"Does {D[d]} have production database access at the end of the record? Answer yes or no.",
            yn(bool(sim.access.get(d))), ev or [sim.events[0]["id"]])
    for t in sorted(sim.decisions)[:per]:
        add("DECISION_NOW", f"Which library is the current team decision for {t}?", tok(sim.decisions[t]),
            [e for e, _ in sim.hist[("decision", t)]])
    for f in fids[:per // 2]:
        add("ABSTAIN", f"Which developer wrote the original implementation of `{sim.fn[f]['name']}`? "
                       f"Answer 'unknown' if the record never says.", {"kind": "unknown", "gold": "unknown", "aliases": ["unknown"]}, [])
    for i, q in enumerate(Q):
        q["qid"] = f"Q{i:04d}"
    return Q


def assemble(sim, density, seed=0):
    fr = srng("codefill", sim.seed, density, seed)
    out, spans, pos = [], {}, 0
    byid = {e["id"]: e for e in sim.events}

    def emit(s):
        nonlocal pos
        out.append(s)
        pos += len(s)

    def filler():
        x = fr.random()
        if x < 0.35:
            return fr.choice(CI).format(n=fr.randrange(1000, 9999), m=fr.randrange(1, 40), s=fr.randrange(0, 59))
        if x < 0.7:
            return fr.choice(CHAT).format(p=fr.choice(list(sim.dname.values())))
        if x < 0.9:
            return f"[commit by {fr.choice(list(sim.dname.values()))}] " + fr.choice(NOISE)
        a, b = fr.sample(VERBS, 2)
        return (f"Snippet from an unrelated helper:\n    def _{a}_{fr.choice(NOUNS)}_tmp(x):\n        return x  # TODO "
                f"remove after the {b} migration")
    cur = None
    for sc in sim.scenes:
        if sc["sprint"] != cur:
            cur = sc["sprint"]
            emit(f"\n\nSprint {cur}\n\n")
        evs = sc["events"]
        base = density * len(evs)
        nf = int(base) + (1 if fr.random() < base - int(base) else 0)
        slots = [0] * (len(evs) + 1)
        for _ in range(nf):
            slots[fr.randrange(len(slots))] += 1
        for i in range(len(evs) + 1):
            for _ in range(slots[i]):
                emit(filler() + "\n\n")
            if i < len(evs):
                e = byid[evs[i]]
                st = pos
                emit(e["text"])
                spans[e["id"]] = [st, pos]
                emit("\n\n")
    return "".join(out), spans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--densities", default="0,1,4,16")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sim = Sim(a.seed)
    sim.run()
    Q = questions(sim, srng("q", a.seed))
    persons = {d["id"]: {"id": d["id"], "first": d["first"], "surname": d["surname"]} for d in sim.devs}
    json.dump({"seed": a.seed, "persons": persons, "modules": sim.modules, "fn": sim.fn, "config": sim.config,
               "owner": sim.owner, "rules": {"call": sim.rule_call, "flag": sim.rule_flag}},
              open(os.path.join(a.out, "world_GOLD.json"), "w", encoding="utf-8"), indent=1)
    json.dump(sim.events, open(os.path.join(a.out, "events_GOLD.json"), "w", encoding="utf-8"), indent=1)
    with open(os.path.join(a.out, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
        for q in Q:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    stats = {"events": len(sim.events), "questions": len(Q), "qtypes": Counter(q["qtype"] for q in Q),
             "event_types": Counter(e["type"] for e in sim.events)}
    for d in [float(x) for x in a.densities.split(",")]:
        text, spans = assemble(sim, d)
        tag = f"d{d:g}"
        open(os.path.join(a.out, f"record_{tag}.txt"), "w", encoding="utf-8").write(text)
        json.dump(spans, open(os.path.join(a.out, f"spans_{tag}_GOLD.json"), "w"), indent=0)
        stats[tag] = {"chars": len(text), "tokens_cl100k": len(enc.encode(text, disallowed_special=()))}
    json.dump(stats, open(os.path.join(a.out, "stats.json"), "w"), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
