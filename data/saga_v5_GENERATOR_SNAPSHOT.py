"""LongState-Saga: a controlled long-record benchmark with exact ground truth.

A fictitious world (families, places, heirlooms, secrets, rules) evolves over
chapters.  Every state change is an event with an id.  Events are rendered once
into fixed prose (event RNG), then the record is assembled at any filler density
(filler RNG), so record length changes while events, questions and answers stay
identical.  Gold evidence = event ids, mapped to character spans in each render.
"""
import argparse
import hashlib
import json
import os
import random
from collections import defaultdict

SEASONS = ["spring", "summer", "autumn", "winter"]
ORD = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
       "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth"]

F_START = ["Ma", "Ri", "Il", "Ves", "Ae", "Bre", "Co", "Da", "El", "Fe", "Ga", "Ha", "Is",
           "Jo", "Ka", "Lu", "Mo", "Ne", "Or", "Pe", "Ro", "Se", "Ta", "Ul", "Vo", "We",
           "Ye", "Za", "Thi", "Ny"]
F_END_F = ["ra", "lia", "rine", "dette", "wyn", "lis", "nelle", "ssa", "mira", "lde", "ena", "vie"]
F_END_M = ["ric", "dan", "mor", "bin", "rald", "ten", "vus", "drek", "lan", "tho", "nar", "zek"]
S_START = ["Holl", "Brack", "Thorn", "Corr", "Ash", "Fell", "Grim", "Orl", "Quill", "Sten",
           "Wex", "Dorn", "Lind", "Marr", "Vell", "Hask", "Pryd", "Tallow"]
S_END = ["oway", "enridge", "ett", "ley", "ick", "wood", "ner", "ford", "aby", "son", "mere", "worth"]
P_START = ["Ost", "Harrow", "Kel", "Bryn", "Wil", "Cold", "Fen", "Gul", "Raven", "Sal", "Brae",
           "Dun", "Elm", "Mire", "Stave", "Tor", "Wend", "Yarl", "Quen", "Lark"]
P_END = ["mere", "ford", "holt", "wick", "stead", "ton", "haven", "combe", "by", "gate"]
P_KIND = ["the village of {}", "the harbor town of {}", "the market town of {}", "{}",
          "the hill farms of {}", "the river crossing at {}"]
MATERIAL = ["copper", "silver", "bone", "jade", "iron", "amber", "glass", "oak", "brass",
            "ivory", "pewter", "garnet"]
OBJECT = ["astrolabe", "ledger", "ring", "compass", "flute", "seal", "lantern", "map", "dagger",
          "chalice", "locket", "mirror", "bell", "comb", "spyglass"]
OCCUPATIONS = ["miller", "ferryman", "scribe", "weaver", "smith", "herbalist", "cooper",
               "shepherd", "chandler", "mason", "fisher", "tanner", "glazier", "brewer"]
CAUSES = ["a winter fever", "a fall from the mill loft", "drowning in the flood",
          "a long wasting sickness", "a kick from a cart horse", "the coughing sickness",
          "old age, quietly in sleep", "a wound that festered"]
EPITHETS = ["Old {}", "Red {}", "{} the Younger", "Quiet {}", "Tall {}", "Lame {}"]
PROMISE_ACTIONS = ["to repair the roof of the chapel at {place}", "to carry a sealed letter to {place}",
                   "to plant an orchard on the slope above {place}", "to pay the old debt owed to the {surname} family",
                   "to teach the children of {place} their letters", "to rebuild the fallen wall at {place}"]
SECRET_TEMPLATES = ["that the fire at the {place} granary was set on purpose",
                    "that a chest of silver lies buried beneath the well at {place}",
                    "that the deed to the {place} pastures was forged",
                    "that the {surname} family once owed a blood debt to the {surname2} family",
                    "that the bridge toll at {place} is skimmed every month",
                    "that the old abbey at {place} hides a second cellar",
                    "that the {surname} mill ledger was rewritten after the flood",
                    "that the harbor master of {place} takes bribes"]


def stable_rng(*parts):
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


class World:
    def __init__(self, seed, n_families=10, n_places=16, n_items=12, n_secrets=8, n_chapters=40):
        self.seed = seed
        self.rng = stable_rng("world", seed)
        self.n_chapters = n_chapters
        self.persons = {}       # pid -> dict
        self.places = []
        self.items = []
        self.secrets = []
        self.rules = []
        self.events = []        # list of event dicts (state changes + statements)
        self.scenes = []        # list of scene dicts referencing event ids
        self.chapter_meta = []
        self._names_used = set()
        self._build_static(n_families, n_places, n_items, n_secrets)

    # ------------------------------------------------------------------ names
    def _new_first(self, gender, allow_dup=False):
        pool = F_END_F if gender == "F" else F_END_M
        for _ in range(1000):
            n = self.rng.choice(F_START) + self.rng.choice(pool)
            if allow_dup or n not in self._names_used:
                self._names_used.add(n)
                return n
        raise RuntimeError("names exhausted")

    def _build_static(self, n_families, n_places, n_items, n_secrets):
        r = self.rng
        surnames = set()
        while len(surnames) < n_families:
            surnames.add(r.choice(S_START) + r.choice(S_END))
        self.surnames = sorted(surnames)
        r.shuffle(self.surnames)
        pnames = set()
        while len(pnames) < n_places:
            pnames.add(r.choice(P_START) + r.choice(P_END))
        self.places = []
        for i, pn in enumerate(sorted(pnames)):
            self.places.append({"id": f"L{i:02d}", "name": pn, "label": r.choice(P_KIND).format(pn)})
        r.shuffle(self.places)
        combos = set()
        while len(combos) < n_items:
            combos.add((r.choice(MATERIAL), r.choice(OBJECT)))
        self.items = [{"id": f"I{i:02d}", "name": f"the {m} {o}"} for i, (m, o) in enumerate(sorted(combos))]
        r.shuffle(self.items)
        used_t = list(range(len(SECRET_TEMPLATES)))
        r.shuffle(used_t)
        for i in range(n_secrets):
            t = SECRET_TEMPLATES[used_t[i % len(used_t)]]
            s2 = r.sample(self.surnames, 2)
            text = t.format(place=r.choice(self.places)["name"], surname=s2[0], surname2=s2[1])
            self.secrets.append({"id": f"S{i:02d}", "text": text})

    # ----------------------------------------------------------- persons
    def add_person(self, gender, surname, father=None, mother=None, gen=0, first=None, adult=True):
        pid = f"P{len(self.persons):03d}"
        first = first or self._new_first(gender)
        p = {"id": pid, "first": first, "surname": surname, "gender": gender, "father": father,
             "mother": mother, "gen": gen, "adult": adult, "nick": None, "birthplace": None,
             "occupation": None, "birth_order": None}
        self.persons[pid] = p
        return pid

    def full(self, pid):
        p = self.persons[pid]
        return f"{p['first']} {p['surname']}"


def pronoun(p, case="subj"):
    if p["gender"] == "F":
        return {"subj": "she", "obj": "her", "poss": "her"}[case]
    return {"subj": "he", "obj": "him", "poss": "his"}[case]


class Sim:
    """Simulates the world, records events with exact state, renders event prose."""

    def __init__(self, world):
        self.w = world
        self.r = stable_rng("sim", world.seed)
        self.alive = {}
        self.loc = {}
        self.spouse = {}
        self.owner = {}
        self.knows = defaultdict(set)     # secret -> set(pid)
        self.occupation = {}
        self.promises = []                # dicts
        self.visited = defaultdict(set)
        self.children = defaultdict(list)  # parent -> [child ordered by birth]
        self.ever_married = defaultdict(set)
        self.hist_loc = defaultdict(list)     # pid -> [(eid, place)]
        self.hist_spouse = defaultdict(list)  # pid -> [(eid, spouse or None)]
        self.hist_owner = defaultdict(list)   # item -> [(eid, pid)]
        self.death_eid = {}
        self.knows_eid = defaultdict(dict)    # secret -> pid -> eid
        self.rumors = []
        self.plans = []
        self.eid = 0
        self._deps = []
        self.intro_eid = {}
        self.nick_eid = {}
        self.marry_eid = {}
        self.chapter = 0
        self.cur_scene = None
        self.heir_rule = None
        self.vault_rule = None
        self.bridge_rule = None

    # ------------------------------------------------------------- helpers
    def P(self, pid):
        return self.w.persons[pid]

    def new_event(self, etype, text, where=None, **data):
        text = text[0].upper() + text[1:]
        if self.cur_scene is None or (self.cur_scene["kind"] == "scene" and where and where != self.cur_scene["place"]):
            if self.cur_scene is not None:
                self.end_scene()
            self.start_scene(where)
        e = {"id": f"E{self.eid:04d}", "type": etype, "chapter": self.chapter, "text": text, "where": where,
             "ref_deps": sorted(set(self._deps))}
        self._deps = []
        e.update(data)
        self.eid += 1
        self.w.events.append(e)
        self.cur_scene["events"].append(e["id"])
        return e["id"]

    def unique_first(self, pid):
        f = self.P(pid)["first"]
        return sum(1 for q in self.w.persons.values() if q["first"] == f) == 1

    def ref(self, pid, rng, allow_desc=True):
        """Unambiguous reference to a person, varied in surface form."""
        p = self.P(pid)
        opts = [("full", 0.55)]
        if self.unique_first(pid) and pid in self.intro_eid:
            opts.append(("first", 0.2))
        if p["nick"] and pid in self.nick_eid:
            opts.append(("nick", 0.12))
        if allow_desc:
            if p["father"] is not None and p["gen"] <= 1 and pid in self.intro_eid:
                opts.append(("desc_parent", 0.08))
            sp = self.spouse.get(pid)
            if sp is not None and pid in self.marry_eid:
                opts.append(("desc_spouse", 0.05))
        tot = sum(w for _, w in opts)
        x = rng.random() * tot
        kind = opts[-1][0]
        for k, wgt in opts:
            if x < wgt:
                kind = k
                break
            x -= wgt
        if kind == "full":
            return self.w.full(pid)
        if kind == "first":
            self._deps.append(self.intro_eid[pid])
            return p["first"]
        if kind == "nick":
            self._deps.append(self.nick_eid[pid])
            return p["nick"]
        if kind == "desc_parent":
            self._deps.append(self.intro_eid[pid])
            par = p["father"] if rng.random() < 0.5 else p["mother"]
            same = [c for c in self.children[p["father"]] if self.P(c)["gender"] == p["gender"]]
            k = same.index(pid)
            role = "daughter" if p["gender"] == "F" else "son"
            if len(same) == 1:
                return f"the only {role} of {self.w.full(par)}"
            word = "eldest" if k == 0 else ("youngest" if k == len(same) - 1 else ORD[k])
            return f"the {word} {role} of {self.w.full(par)}"
        sp = self.spouse[pid]
        self._deps.append(self.marry_eid[pid])
        role = "wife" if p["gender"] == "F" else "husband"
        return f"the {role} of {self.w.full(sp)}"

    def place_label(self, lid):
        return next(x for x in self.w.places if x["id"] == lid)

    def item(self, iid):
        return next(x for x in self.w.items if x["id"] == iid)

    def kin_close(self, a, b):
        pa, pb = self.P(a), self.P(b)
        if a == b:
            return True
        if pa["father"] and pa["father"] in (pb["father"], b):
            return True
        if pb["father"] == a or pa["father"] == b or pa["mother"] == b or pb["mother"] == a:
            return True
        # first cousins / grandparent
        def parents(x):
            q = self.P(x)
            return [y for y in (q["father"], q["mother"]) if y]
        gpa = set(sum((parents(y) for y in parents(a)), []))
        gpb = set(sum((parents(y) for y in parents(b)), []))
        if gpa & gpb:
            return True
        if b in gpa or a in gpb:
            return True
        return False

    def alive_adults(self):
        return [pid for pid, a in self.alive.items() if a and self.P(pid)["adult"]]

    # ------------------------------------------------------------- prologue
    def prologue(self, n_families):
        w, r = self.w, self.r
        self.chapter = 1
        self.start_scene(None, "prologue")
        fam_heads = []
        for s in w.surnames[:n_families]:
            f = w.add_person("M", s, gen=0)
            m = w.add_person("F", s, gen=0)
            fam_heads.append((f, m))
            for x in (f, m):
                self.alive[x] = True
            self.spouse[f], self.spouse[m] = m, f
            self.ever_married[f].add(m)
            self.ever_married[m].add(f)
            nkids = r.choice([2, 3, 3, 4])
            kids = []
            for k in range(nkids):
                g = r.choice("MF")
                c = w.add_person(g, s, father=f, mother=m, gen=1)
                self.P(c)["birth_order"] = k
                self.alive[c] = True
                self.children[f].append(c)
                self.children[m].append(c)
                kids.append(c)
            home = r.choice(w.places)["id"]
            for x in [f, m] + kids:
                self.loc[x] = home
                self.visited[x].add(home)
        # confusable first names: re-use some gen1 first names across families
        gen1 = [p for p in w.persons.values() if p["gen"] == 1]
        r.shuffle(gen1)
        for a, b in zip(gen1[0:12:2], gen1[1:12:2]):
            if a["gender"] == b["gender"] and a["surname"] != b["surname"]:
                b["first"] = a["first"]
        for p in w.persons.values():
            if r.random() < 0.18:
                p["nick"] = r.choice(EPITHETS).format(p["first"])
            if r.random() < 0.5:
                p["birthplace"] = r.choice(w.places)["id"]
            if p["adult"] and r.random() < 0.75:
                p["occupation"] = r.choice(OCCUPATIONS)
        # make nicknames unique
        seen = set()
        for p in w.persons.values():
            if p["nick"] in seen:
                p["nick"] = None
            elif p["nick"]:
                seen.add(p["nick"])
        # render family introductions as separate events (spread over prologue scenes)
        for (f, m) in fam_heads:
            er = stable_rng("ev", w.seed, self.eid)
            kids = self.children[f]
            kid_txt = []
            for i, c in enumerate(kids):
                cp = self.P(c)
                role = "daughter" if cp["gender"] == "F" else "son"
                kid_txt.append(f"{'the eldest' if i == 0 else 'then'} a {role}, {self.w.full(c)}")
            fn, mn = w.full(f), w.full(m)
            home = self.place_label(self.loc[f])["label"]
            t = er.choice([
                f"The {self.P(f)['surname']} household lived in {home}. {fn} and his wife {mn} had {len(kids)} children, all living at home: {'; '.join(kid_txt)}.",
                f"In {home} lived {fn}, married to {mn}, with their children. In order of birth these were {'; '.join(kid_txt)}.",
            ])
            fe = self.new_event("INIT_FAMILY", t, father=f, mother=m, children=list(kids), place=self.loc[f])
            for x in [f, m] + kids:
                self.intro_eid[x] = fe
            self.marry_eid[f] = fe
            self.marry_eid[m] = fe
            for x in [f, m] + kids:
                self.hist_loc[x].append((f"E{self.eid-1:04d}", self.loc[x]))
            self.hist_spouse[f].append((f"E{self.eid-1:04d}", m))
            self.hist_spouse[m].append((f"E{self.eid-1:04d}", f))
        # gen1 marriages across families
        gen1_ids = [p["id"] for p in w.persons.values() if p["gen"] == 1]
        r.shuffle(gen1_ids)
        married = 0
        for a in gen1_ids:
            if married >= 6:
                break
            if self.spouse.get(a):
                continue
            cands = [b for b in gen1_ids if b != a and not self.spouse.get(b)
                     and self.P(b)["gender"] != self.P(a)["gender"]
                     and self.P(b)["surname"] != self.P(a)["surname"]]
            if not cands:
                continue
            b = r.choice(cands)
            self.do_marry(a, b, init=True)
            married += 1
        # initial occupations / birthplaces as statements
        for p in list(w.persons.values()):
            er = stable_rng("ev", w.seed, self.eid)
            bits = []
            if p["occupation"]:
                bits.append(er.choice([f"{self.w.full(p['id'])} worked as a {p['occupation']}.",
                                       f"By trade {self.w.full(p['id'])} was a {p['occupation']}."]))
                self.occupation[p["id"]] = p["occupation"]
            if p["birthplace"]:
                bl = self.place_label(p["birthplace"])["name"]
                bits.append(er.choice([f"{self.w.full(p['id'])} had been born in {bl}.",
                                       f"{self.w.full(p['id'])} was born at {bl}."]))
            if p["nick"]:
                bits.append(f"Folk called {self.w.full(p['id'])} \"{p['nick']}\".")
            if bits:
                pe = self.new_event("INIT_PERSON", " ".join(bits), person=p["id"],
                               occupation=p["occupation"], birthplace=p["birthplace"], nick=p["nick"])
                if p["nick"]:
                    self.nick_eid[p["id"]] = pe
        # items
        holders = [pid for pid in w.persons if self.P(pid)["adult"]]
        for it in w.items:
            h = r.choice(holders)
            self.owner[it["id"]] = h
            er = stable_rng("ev", w.seed, self.eid)
            t = er.choice([f"{it['name'].capitalize()} belonged to {self.w.full(h)}.",
                           f"{self.w.full(h)} kept {it['name']} in a cedar box.",
                           f"Among the possessions of {self.w.full(h)} was {it['name']}."])
            eid = self.new_event("INIT_ITEM", t, item=it["id"], owner=h)
            self.hist_owner[it["id"]].append((eid, h))
        # secrets
        for s in w.secrets:
            k = r.choice(holders)
            self.knows[s["id"]].add(k)
            er = stable_rng("ev", w.seed, self.eid)
            t = er.choice([f"Only {self.w.full(k)} knew {s['text']}.",
                           f"{self.w.full(k)} alone carried the knowledge {s['text']}."])
            eid = self.new_event("INIT_SECRET", t, secret=s["id"], person=k)
            self.knows_eid[s["id"]][k] = eid
        # rules
        keys = r.sample(w.items, 2)
        vault_place = r.choice(w.places)
        self.vault_rule = {"place": vault_place["id"], "items": [keys[0]["id"], keys[1]["id"]]}
        t = (f"It was an old law of {vault_place['name']} that the vault beneath its chapel would open "
             f"only for a living person who held both {keys[0]['name']} and {keys[1]['name']} at once.")
        self.vault_rule["eid"] = self.new_event("RULE_VAULT", t, **self.vault_rule)
        bridge_place = r.choice([p for p in w.places if p["id"] != vault_place["id"]])
        bfam = r.choice(w.surnames)
        self.bridge_rule = {"place": bridge_place["id"], "surname": bfam}
        t = (f"The toll bridge at {bridge_place['name']} belonged to the {bfam} family, and only those born "
             f"a {bfam}, or presently married to one, were allowed to cross it.")
        self.bridge_rule["eid"] = self.new_event("RULE_BRIDGE", t, **self.bridge_rule)
        heir_item = r.choice([it for it in w.items if it["id"] not in self.vault_rule["items"]])
        heir_fam = fam_heads[0]
        self.heir_rule = {"item": heir_item["id"], "surname": self.P(heir_fam[0])["surname"]}
        # make the heirloom belong to the family head
        self.owner[heir_item["id"]] = heir_fam[0]
        self.hist_owner[heir_item["id"]] = [(self.hist_owner[heir_item["id"]][0][0], heir_fam[0])]
        # patch the INIT_ITEM event text/owner for the heirloom
        for e in w.events:
            if e["type"] == "INIT_ITEM" and e["item"] == heir_item["id"]:
                e["owner"] = heir_fam[0]
                e["text"] = f"{heir_item['name'].capitalize()} belonged to {self.w.full(heir_fam[0])}, head of the {self.heir_rule['surname']} household."
        t = (f"By custom, {heir_item['name']} always passed, on the death of whoever held it, to the eldest "
             f"living child of that holder; no will could change this, and it passed without ceremony.")
        self.heir_rule["eid"] = self.new_event("RULE_HEIR", t, **self.heir_rule)
        self.end_scene()

    # ------------------------------------------------------------ actions
    def do_marry(self, a, b, init=False):
        er = stable_rng("ev", self.w.seed, self.eid)
        if not init:
            ra, rb = self.ref(a, er), self.ref(b, er)   # references use the state BEFORE the wedding
        self.spouse[a], self.spouse[b] = b, a
        self.ever_married[a].add(b)
        self.ever_married[b].add(a)
        if init:
            t = er.choice([f"{self.w.full(a)} had married {self.w.full(b)} some years before.",
                           f"{self.w.full(a)} and {self.w.full(b)} were husband and wife."])
            t += f" The couple lived in {self.place_label(self.loc[a])['name']}."
        else:
            place = self.place_label(self.loc[a])["name"]
            t = er.choice([f"In the chapel at {place}, {ra} married {rb}.",
                           f"{ra} and {rb} were wed at {place}, with half the parish looking on.",
                           f"Before the {SEASONS[(self.chapter) % 4]} was out, {ra} took {rb} in marriage at {place}."])
            t += f" The couple lived in {place} from then on."
        # spouses move together (to a's place)
        moved = None
        if self.loc[b] != self.loc[a]:
            moved = (b, self.loc[a])
        eid = self.new_event("MARRY", t, where=self.loc[a], a=a, b=b, place=self.loc[a])
        self.marry_eid[a] = eid
        self.marry_eid[b] = eid
        self.hist_spouse[a].append((eid, b))
        self.hist_spouse[b].append((eid, a))
        if moved:
            self.loc[b] = self.loc[a]
            self.visited[b].add(self.loc[a])
            self.hist_loc[b].append((eid, self.loc[a]))
        return eid

    def do_travel(self, p, dest):
        er = stable_rng("ev", self.w.seed, self.eid)
        src = self.loc[p]
        rp = self.ref(p, er)
        dl = self.place_label(dest)["name"]
        sl = self.place_label(src)["name"]
        t = er.choice([f"{rp} left {sl} and settled in {dl}.",
                       f"{rp} packed a single trunk and moved from {sl} to {dl}.",
                       f"After the quarrel, {rp} quit {sl} for good and took lodgings in {dl}.",
                       f"{rp} found work in {dl}, moved there, and did not return to {sl}.",
                       f"{rp} rode out of {sl}; by the next market day {pronoun(self.P(p))} was living in {dl}."])
        eid = self.new_event("TRAVEL", t, where=src, person=p, src=src, dest=dest)
        self.loc[p] = dest
        self.visited[p].add(dest)
        self.hist_loc[p].append((eid, dest))
        # spouse moves too, explicitly
        sp = self.spouse.get(p)
        if sp and self.alive.get(sp) and self.loc[sp] != dest:
            er2 = stable_rng("ev2", self.w.seed, self.eid)
            rsp = self.ref(sp, er2, allow_desc=False)
            t2 = er2.choice([f"{rsp} followed {pronoun(self.P(p), 'obj')} to {dl} within the month.",
                             f"{rsp} went along to live in {dl} as well."])
            eid2 = self.new_event("TRAVEL", t2, where=src, person=sp, src=self.loc[sp], dest=dest)
            self.loc[sp] = dest
            self.visited[sp].add(dest)
            self.hist_loc[sp].append((eid2, dest))
        return eid

    def do_death(self, p):
        er = stable_rng("ev", self.w.seed, self.eid)
        rp = self.ref(p, er)
        cause = er.choice(CAUSES)
        place = self.place_label(self.loc[p])["name"]
        t = er.choice([f"{rp} died of {cause} at {place}.",
                       f"That {SEASONS[self.chapter % 4]}, {cause} took {rp}; {pronoun(self.P(p), 'subj')} was buried at {place}.",
                       f"They laid {rp} in the churchyard at {place}, dead of {cause}."])
        eid = self.new_event("DEATH", t, where=self.loc[p], person=p, cause=cause, place=self.loc[p])
        self.alive[p] = False
        self.death_eid[p] = eid
        sp = self.spouse.get(p)
        if sp:
            self.spouse[sp] = None
            self.spouse[p] = None
            self.hist_spouse[sp].append((eid, None))
            self.hist_spouse[p].append((eid, None))
        # items held by the dead
        for iid, o in list(self.owner.items()):
            if o != p:
                continue
            if self.heir_rule and iid == self.heir_rule["item"]:
                heirs = [c for c in self.children[p] if self.alive.get(c)]
                if heirs:
                    h = heirs[0]
                    self.owner[iid] = h
                    self.hist_owner[iid].append((eid, h))   # implicit transfer by rule (not narrated)
                else:
                    self.owner[iid] = None
                    self.hist_owner[iid].append((eid, None))
                continue
            cands = [x for x in ([sp] if sp else []) + self.children[p] if x and self.alive.get(x)]
            if not cands:
                cands = [x for x in self.alive_adults() if self.loc[x] == self.loc[p]] or self.alive_adults()
            h = cands[0]
            er3 = stable_rng("ev3", self.w.seed, self.eid, iid)
            rh = self.ref(h, er3)
            t3 = er3.choice([f"{self.item(iid)['name'].capitalize()}, which {self.w.full(p)} had owned, went to {rh}.",
                             f"Among the things left by {self.w.full(p)}, {self.item(iid)['name']} was handed to {rh}."])
            eid3 = self.new_event("GIVE", t3, where=self.loc[p], item=iid, src=p, dest=h, inherit=True)
            self.owner[iid] = h
            self.hist_owner[iid].append((eid3, h))
        return eid

    def do_birth(self, mother):
        father = self.spouse[mother]
        er = stable_rng("ev", self.w.seed, self.eid)
        g = er.choice("MF")
        c = self.w.add_person(g, self.P(father)["surname"], father=father, mother=mother,
                              gen=self.P(mother)["gen"] + 1, adult=False)
        self.P(c)["birth_order"] = len(self.children[father])
        self.children[father].append(c)
        if c not in self.children[mother]:
            self.children[mother].append(c)
        self.alive[c] = True
        self.loc[c] = self.loc[mother]
        self.visited[c].add(self.loc[mother])
        role = "daughter" if g == "F" else "son"
        if er.random() < 0.5:
            t = f"{self.ref(mother, er, allow_desc=False)} gave birth to a {role}, named {self.w.full(c)}; the father was {self.w.full(father)}. The family lived in {self.place_label(self.loc[mother])['name']}."
        else:
            t = f"A {role} was born to {self.w.full(mother)} and {self.w.full(father)}, and they called the child {self.w.full(c)}. The family lived in {self.place_label(self.loc[mother])['name']}."
        eid = self.new_event("BIRTH", t, where=self.loc[mother], child=c, mother=mother, father=father, place=self.loc[mother])
        self.intro_eid[c] = eid
        self.hist_loc[c].append((eid, self.loc[c]))
        return eid

    def do_give(self, iid, dest):
        src = self.owner[iid]
        er = stable_rng("ev", self.w.seed, self.eid)
        rs, rd = self.ref(src, er), self.ref(dest, er)
        it = self.item(iid)["name"]
        same = self.loc[src] == self.loc[dest]
        if same:
            t = er.choice([f"{rs} pressed {it} into the hands of {rd} and would take nothing for it.",
                           f"{rs} gave {it} to {rd}.",
                           f"{rd} won {it} from {rs} at cards, fairly, and kept it."])
        else:
            t = er.choice([f"{rs} sent {it} by carrier to {rd}, who received it safely.",
                           f"A parcel from {rs} reached {rd}; inside was {it}, now {'hers' if self.P(dest)['gender'] == 'F' else 'his'} to keep."])
        eid = self.new_event("GIVE", t, where=self.loc[src], item=iid, src=src, dest=dest)
        self.owner[iid] = dest
        self.hist_owner[iid].append((eid, dest))
        return eid

    def do_tell(self, sid, a, b):
        er = stable_rng("ev", self.w.seed, self.eid)
        ra, rb = self.ref(a, er), self.ref(b, er)
        st = next(s for s in self.w.secrets if s["id"] == sid)["text"]
        t = er.choice([f"Late one night {ra} confided to {rb} {st}.",
                       f"{ra} could keep it no longer and told {rb} {st}.",
                       f"In a letter that {rb} burned after reading, {ra} revealed {st}."])
        eid = self.new_event("TELL", t, where=self.loc[a], secret=sid, src=a, dest=b)
        self.knows[sid].add(b)
        self.knows_eid[sid][b] = eid
        return eid

    def do_promise(self, a, b):
        er = stable_rng("ev", self.w.seed, self.eid)
        act = er.choice(PROMISE_ACTIONS).format(place=er.choice(self.w.places)["name"],
                                                surname=er.choice(self.w.surnames))
        ra, rb = self.ref(a, er), self.ref(b, er)
        t = er.choice([f"{ra} gave {rb} a solemn promise {act}.",
                       f"{ra} swore to {rb} {act}, and shook on it."])
        pr = {"id": f"R{len(self.promises):02d}", "a": a, "b": b, "act": act, "status": "pending"}
        eid = self.new_event("PROMISE", t, where=self.loc[a], promise=pr["id"], a=a, b=b, act=act)
        pr["eid"] = eid
        pr["resolve_eid"] = None
        self.promises.append(pr)
        return eid

    def do_resolve(self, pr, kept):
        er = stable_rng("ev", self.w.seed, self.eid)
        ra = self.ref(pr["a"], er)
        if kept:
            t = er.choice([f"True to {pronoun(self.P(pr['a']), 'poss')} word to {self.w.full(pr['b'])}, {ra} finished what {pronoun(self.P(pr['a']))} had promised ({pr['act'][3:]}).",
                           f"{ra} kept the promise made to {self.w.full(pr['b'])}: the task ({pr['act'][3:]}) was done by harvest."])
        else:
            t = er.choice([f"{ra} never did keep the promise made to {self.w.full(pr['b'])} ({pr['act'][3:]}); the matter was abandoned.",
                           f"{ra} broke faith with {self.w.full(pr['b'])}, and the promised work ({pr['act'][3:]}) was never begun."])
        eid = self.new_event("RESOLVE", t, where=self.loc[pr["a"]], promise=pr["id"], kept=kept)
        pr["status"] = "kept" if kept else "broken"
        pr["resolve_eid"] = eid
        return eid

    def do_occupation(self, p):
        er = stable_rng("ev", self.w.seed, self.eid)
        old = self.occupation.get(p)
        new = er.choice([o for o in OCCUPATIONS if o != old])
        t = er.choice([f"{self.ref(p, er)} gave up {'being a ' + old if old else 'idleness'} and took work as a {new}.",
                       f"{self.ref(p, er)} was apprenticed anew and became a {new}."])
        eid = self.new_event("OCCUPATION", t, where=self.loc[p], person=p, old=old, new=new)
        self.occupation[p] = new
        return eid

    def do_rumor(self, teller, target):
        er = stable_rng("ev", self.w.seed, self.eid)
        kind = er.choice(["dead", "married"])
        rt, rg = self.ref(teller, er), self.w.full(target)
        if kind == "dead":
            t = er.choice([f"{rt} told everyone at the inn that {rg} had drowned crossing the estuary, though no body was ever seen.",
                           f"A rumor started by {rt} had it that {rg} was dead of plague; {rt} had it from a peddler."])
            claim = {"kind": "dead", "target": target}
        else:
            cands = [x for x in self.alive_adults() if x != target and self.P(x)["gender"] != self.P(target)["gender"]
                     and self.spouse.get(target) != x]
            other = er.choice(cands)
            t = er.choice([f"{rt} whispered that {rg} had secretly married {self.w.full(other)}, but nobody could say where or when.",
                           f"Gossip from {rt} claimed {rg} and {self.w.full(other)} had been wed in secret."])
            claim = {"kind": "married", "target": target, "other": other}
        eid = self.new_event("RUMOR", t, where=self.loc[teller], teller=teller, claim=claim)
        self.rumors.append({"eid": eid, "teller": teller, **claim})
        return eid

    def do_plan(self, p, dest):
        er = stable_rng("ev", self.w.seed, self.eid)
        dl = self.place_label(dest)["name"]
        t = er.choice([f"{self.ref(p, er)} meant to go to {dl} before the frost, but the roads flooded and the journey was put off.",
                       f"{self.ref(p, er)} talked for weeks of going to {dl}, yet in the end stayed where {pronoun(self.P(p))} was."])
        eid = self.new_event("PLAN", t, where=self.loc[p], person=p, dest=dest)
        self.plans.append({"eid": eid, "person": p, "dest": dest})
        return eid

    # ------------------------------------------------------------- scenes
    def start_scene(self, place, kind="scene"):
        start = {x for x in self.alive if self.alive[x] and place and self.loc[x] == place}
        self.cur_scene = {"chapter": self.chapter, "place": place, "kind": kind, "events": [], "_start": start}

    def end_scene(self):
        sc = self.cur_scene
        end = {x for x in self.alive if self.alive[x] and sc["place"] and self.loc[x] == sc["place"]}
        sc["present"] = sorted(sc.pop("_start") & end)
        if sc["events"]:
            self.w.scenes.append(sc)
        self.cur_scene = None

    def step_chapter(self, ch):
        self.chapter = ch
        r = self.r
        self.cur_scene = None
        for _ in range(r.choice([5, 6, 7, 8])):
            self.random_event()
        if self.cur_scene is not None:
            self.end_scene()
        # scripted: around 55% of the story, one person comes to hold both vault keys
        if ch == int(self.w.n_chapters * 0.55):
            k1, k2 = self.vault_rule["items"]
            h1, h2 = self.owner.get(k1), self.owner.get(k2)
            if h1 and h2 and h1 != h2 and self.alive.get(h1) and self.alive.get(h2):
                self.do_give(k1, h2)
                self.end_scene()

    def random_event(self):
        r = self.r
        ch = self.chapter
        weights = {"travel": 5, "give": 4, "tell": 4, "promise": 3, "resolve": 1.5, "marry": 2,
                   "death": 2 if ch > 4 else 0, "birth": 2, "occupation": 1, "rumor": 1.2, "plan": 1.2}
        kinds = list(weights)
        k = r.choices(kinds, weights=[weights[x] for x in kinds])[0]
        adults = self.alive_adults()
        if len(adults) < 6:
            return
        a = r.choice(adults)
        if self.cur_scene is not None and self.cur_scene["place"] and r.random() < 0.6:
            here = [x for x in adults if self.loc[x] == self.cur_scene["place"]]
            if here:
                a = r.choice(here)
        local = [x for x in adults if x != a and self.loc[x] == self.loc[a]]
        if k == "travel":
            dest = r.choice([p["id"] for p in self.w.places if p["id"] != self.loc[a]])
            self.do_travel(a, dest)
        elif k == "give":
            movable = [(i, o) for i, o in self.owner.items() if o and self.alive.get(o)
                       and not (self.heir_rule and i == self.heir_rule["item"])
                       and not (self.vault_rule and i in self.vault_rule["items"])]
            if not movable:
                return
            iid, src = r.choice(movable)
            loc_c = [x for x in adults if x != src and self.loc[x] == self.loc[src]]
            dest = r.choice(loc_c) if loc_c and r.random() < 0.7 else r.choice([x for x in adults if x != src])
            self.do_give(iid, dest)
        elif k == "tell":
            opts = [(s_, kn) for s_, ks in self.knows.items() for kn in sorted(ks) if self.alive.get(kn)]
            if not opts:
                return
            sid, kn = r.choice(opts)
            cands = [x for x in adults if x not in self.knows[sid] and x != kn]
            if not cands:
                return
            near = [x for x in cands if self.loc[x] == self.loc[kn]]
            self.do_tell(sid, kn, r.choice(near or cands))
        elif k == "promise":
            b = r.choice(local or [x for x in adults if x != a])
            self.do_promise(a, b)
        elif k == "resolve":
            pend = [p for p in self.promises if p["status"] == "pending" and self.alive.get(p["a"])]
            if not pend:
                return
            self.do_resolve(r.choice(pend), r.random() < 0.55)
        elif k == "marry":
            single = [x for x in adults if not self.spouse.get(x)]
            if not single:
                return
            a = r.choice(single)
            cands = [x for x in single if x != a and self.P(x)["gender"] != self.P(a)["gender"] and not self.kin_close(a, x)]
            if not cands:
                return
            self.do_marry(a, r.choice(cands))
        elif k == "death":
            older = [x for x in adults if self.P(x)["gen"] == 0]
            pool = older if older and r.random() < 0.6 else adults
            self.do_death(r.choice(pool))
        elif k == "birth":
            mothers = [x for x in adults if self.P(x)["gender"] == "F" and self.spouse.get(x)
                       and self.alive.get(self.spouse[x]) and self.P(x)["gen"] >= 1]
            if not mothers:
                return
            self.do_birth(r.choice(mothers))
        elif k == "occupation":
            self.do_occupation(a)
        elif k == "rumor":
            self.do_rumor(a, r.choice([x for x in adults if x != a]))
        elif k == "plan":
            dest = r.choice([p["id"] for p in self.w.places if p["id"] not in self.visited[a]] or
                            [p["id"] for p in self.w.places])
            self.do_plan(a, dest)

    def grow_up(self, ch):
        # children born in the story become adults after 12 chapters (for marriage etc.)
        for pid, p in self.w.persons.items():
            if not p["adult"] and self.alive.get(pid):
                be = next((e for e in self.w.events if e["type"] == "BIRTH" and e["child"] == pid), None)
                if be and ch - be["chapter"] >= 12:
                    p["adult"] = True

    def run(self):
        self.prologue(len(self.w.surnames))
        for ch in range(2, self.w.n_chapters + 1):
            self.grow_up(ch)
            self.step_chapter(ch)
        # guarantee: rumor-dead targets reappear alive in a narrator event after the rumor
        self.chapter = self.w.n_chapters + 1
        self.start_scene(None, "epilogue")
        for ru in self.rumors:
            tgt = ru["target"]
            if ru["kind"] == "dead" and self.alive.get(tgt):
                later = [e for e in self.w.events if e["id"] > ru["eid"] and tgt in
                         (e.get("person"), e.get("a"), e.get("b"), e.get("src"), e.get("dest"), e.get("mother"))]
                if not later:
                    er = stable_rng("ev", self.w.seed, self.eid)
                    t = f"{self.w.full(tgt)}, whatever the gossips said, was seen hale and well at the {SEASONS[self.chapter % 4]} fair in {self.place_label(self.loc[tgt])['name']}."
                    self.new_event("SEEN_ALIVE", t, where=self.loc[tgt], person=tgt, place=self.loc[tgt])
        self.end_scene()


# ----------------------------------------------------------------- questions
def build_questions(sim, rng, per_type=25):
    w = sim.w
    Q = []
    full = w.full
    persons = list(w.persons)
    alive_end = {p: sim.alive.get(p, False) for p in persons}

    def person_ans(pid):
        p = w.persons[pid]
        al = [full(pid)]
        if p["nick"]:
            al.append(p["nick"])
        return {"kind": "person", "gold": full(pid), "aliases": al, "pid": pid}

    def place_ans(lid):
        pl = next(x for x in w.places if x["id"] == lid)
        return {"kind": "place", "gold": pl["name"], "aliases": [pl["name"]]}

    ev_ch = {e["id"]: e["chapter"] for e in w.events}

    def involves(e, pid):
        return pid in (e.get("person"), e.get("a"), e.get("b"), e.get("src"), e.get("dest"), e.get("mother"),
                       e.get("father"), e.get("child"), e.get("teller"))

    def add(qtype, text, ans, ev, subject=None):
        Q.append({"qtype": qtype, "question": text, "answer": ans, "evidence": sorted(set(ev)), "subject": subject})

    # LOC_NOW
    cands = [p for p in persons if alive_end[p] and sim.hist_loc[p]]
    rng.shuffle(cands)
    moved = [p for p in cands if len(sim.hist_loc[p]) >= 2]
    stay = [p for p in cands if len(sim.hist_loc[p]) == 1]
    for p in (moved[: per_type * 2 // 3] + stay[: per_type // 3])[:per_type]:
        ev = [sim.hist_loc[p][-1][0]]
        add("LOC_NOW", f"Where does {full(p)} live at the end of the record?", place_ans(sim.loc[p]), ev, p)
    # LOC_AT_DEATH: where was X when Y died
    deaths = [(p, e) for p, e in sim.death_eid.items()]
    rng.shuffle(deaths)
    n = 0
    for y, de in deaths:
        others = [x for x in persons if x != y and sim.hist_loc[x] and sim.hist_loc[x][0][0] < de]
        rng.shuffle(others)
        for x in others[:2]:
            prior = [(e, l) for e, l in sim.hist_loc[x] if e < de]
            if not prior:
                continue
            e_last, lid = prior[-1]
            if not (sim.death_eid.get(x) is None or sim.death_eid[x] > de):
                continue
            if any(ev_ch[e] == ev_ch[de] for e, _ in sim.hist_loc[x]):
                continue  # same-chapter move and death: order would be ambiguous
            add("LOC_AT_EVENT", f"Where was {full(x)} living at the time {full(y)} died?", place_ans(lid), [e_last, de], x)
            n += 1
            break
        if n >= per_type:
            break
    # SPOUSE_NOW
    cands = [p for p in persons if w.persons[p]["adult"] and alive_end[p]]
    rng.shuffle(cands)
    widowed = [p for p in cands if len(sim.hist_spouse[p]) >= 2]
    married = [p for p in cands if sim.spouse.get(p) and p not in widowed]
    single = [p for p in cands if not sim.spouse.get(p) and not sim.hist_spouse[p]]
    pick = widowed[: per_type // 2] + married[: per_type - min(len(widowed), per_type // 2)]
    for p in pick[:per_type]:
        sp = sim.spouse.get(p)
        ev = [e for e, _ in sim.hist_spouse[p]]
        if sp:
            ans = person_ans(sp)
        else:
            ans = {"kind": "none", "gold": "none", "aliases": ["none"]}
            if not sim.hist_spouse[p]:
                ans = {"kind": "none", "gold": "none", "aliases": ["none"]}
        add("SPOUSE_NOW", f"Who is {full(p)} married to at the end of the record? Answer 'none' if {full(p)} has no living spouse.", ans, ev, p)
    # ALIVE (includes rumor targets)
    dead = list(sim.death_eid)
    rumor_alive = [ru["target"] for ru in sim.rumors if ru["kind"] == "dead" and alive_end[ru["target"]]]
    plain_alive = [p for p in persons if alive_end[p] and w.persons[p]["adult"] and p not in rumor_alive]
    rng.shuffle(dead)
    rng.shuffle(plain_alive)
    sel = [(p, "no") for p in dead[: per_type // 2]] + [(p, "yes") for p in rumor_alive[: per_type // 4]]
    sel += [(p, "yes") for p in plain_alive[: per_type - len(sel)]]
    for p, a in sel:
        ev = [sim.death_eid[p]] if a == "no" else [e for e in (sim.hist_loc[p][-1][0],)]
        if a == "yes":
            rs = [ru["eid"] for ru in sim.rumors if ru["kind"] == "dead" and ru["target"] == p]
            ev += rs
            if rs:
                later = [e["id"] for e in w.events if e["id"] > max(rs) and involves(e, p)]
                ev += later[:1]
        add("ALIVE", f"Is {full(p)} alive at the end of the record? Answer yes or no.", {"kind": "yesno", "gold": a, "aliases": [a]}, ev, p)
    # OWNER_NOW
    for it in w.items:
        o = sim.owner.get(it["id"])
        ev = [sim.hist_owner[it["id"]][-1][0]]
        if sim.heir_rule and it["id"] == sim.heir_rule["item"]:
            ev.append(sim.heir_rule["eid"])
            # the full chain of deaths that moved it, plus who the children were and which died
            ev += [e for e, _ in sim.hist_owner[it["id"]]]
            for _, holder in sim.hist_owner[it["id"]]:
                if not holder:
                    continue
                for c in sim.children[holder]:
                    if c in sim.intro_eid:
                        ev.append(sim.intro_eid[c])
                    if c in sim.death_eid:
                        ev.append(sim.death_eid[c])
        ans = person_ans(o) if o else {"kind": "none", "gold": "none", "aliases": ["none"]}
        add("OWNER_NOW", f"Who holds {it['name']} at the end of the record?", ans, ev, it["id"])
    # OWNER_PREV
    for it in w.items:
        h = sim.hist_owner[it["id"]]
        if len(h) >= 2 and h[-2][1] and not (sim.heir_rule and it["id"] == sim.heir_rule["item"]):
            add("OWNER_PREV", f"Who held {it['name']} immediately before its current holder?", person_ans(h[-2][1]),
                [h[-2][0], h[-1][0]], it["id"])
    # GRANDPARENT
    gc = [p for p in persons if w.persons[p]["father"] and w.persons[w.persons[p]["father"]]["father"]]
    gc += [p for p in persons if w.persons[p]["mother"] and w.persons[w.persons[p]["mother"]]["father"]]
    gc = sorted(set(gc))
    rng.shuffle(gc)
    for p in gc[:per_type]:
        side = rng.choice(["father", "mother"])
        par = w.persons[p][side]
        if not par or not w.persons[par]["father"]:
            side = "father" if side == "mother" else "mother"
            par = w.persons[p][side]
        if not par or not w.persons[par]["father"]:
            continue
        gp = w.persons[par]["father"] if rng.random() < 0.5 else w.persons[par]["mother"]
        role = "grandfather" if w.persons[gp]["gender"] == "M" else "grandmother"
        sidew = "paternal" if side == "father" else "maternal"
        ev = []
        for e in w.events:
            if e["type"] == "BIRTH" and e["child"] in (p, par):
                ev.append(e["id"])
            if e["type"] == "INIT_FAMILY" and (p in e["children"] or par in e["children"]):
                ev.append(e["id"])
        add("GRANDPARENT", f"Who is the {sidew} {role} of {full(p)}?", person_ans(gp), ev, p)
    # KNOWS
    kq = []
    for s in w.secrets:
        knowers = sorted(sim.knows[s["id"]])
        nonk = [x for x in persons if x not in sim.knows[s["id"]] and w.persons[x]["adult"]]
        for k in knowers:
            kq.append((s, k, "yes", [sim.knows_eid[s["id"]][k]]))
        rng.shuffle(nonk)
        for x in nonk[:2]:
            ev = [sim.knows_eid[s["id"]][k] for k in knowers] + ([sim.intro_eid[x]] if x in sim.intro_eid else [])
            kq.append((s, x, "no", ev))
    rng.shuffle(kq)
    yes = [q for q in kq if q[2] == "yes"][: per_type // 2]
    no = [q for q in kq if q[2] == "no"][: per_type - len(yes)]
    for s, x, a, ev in yes + no:
        add("KNOWS", f"By the end of the record, does {full(x)} know {s['text']}? Answer yes or no.",
            {"kind": "yesno", "gold": a, "aliases": [a]}, ev, x)
    # PROMISE
    prs = list(sim.promises)
    rng.shuffle(prs)
    for pr in prs[:per_type]:
        ev = [pr["eid"]] + ([pr["resolve_eid"]] if pr["resolve_eid"] else [])
        add("PROMISE", f"{full(pr['a'])} promised {full(pr['b'])} {pr['act']}. Was that promise kept, broken, or still pending at the end of the record? Answer kept, broken, or pending.",
            {"kind": "label", "gold": pr["status"], "aliases": [pr["status"]]}, ev, pr["a"])
    # RULE_VAULT: who could open the vault now
    vr = sim.vault_rule
    k1, k2 = vr["items"]
    vplace = next(x for x in w.places if x["id"] == vr["place"])["name"]
    holders = {sim.owner.get(k1), sim.owner.get(k2)} | {o for _, o in sim.hist_owner[k1]} | {o for _, o in sim.hist_owner[k2]}
    holders = sorted(h for h in holders - {None} if sim.alive.get(h))
    for h in holders:
        a = "yes" if sim.owner.get(k1) == h and sim.owner.get(k2) == h and sim.alive.get(h) else "no"
        ev = [vr["eid"], sim.hist_owner[k1][-1][0], sim.hist_owner[k2][-1][0]]
        add("RULE_VAULT", f"At the end of the record, could {full(h)} open the vault beneath the chapel at {vplace}? Answer yes or no.",
            {"kind": "yesno", "gold": a, "aliases": [a]}, ev, h)
    # RULE_BRIDGE
    br = sim.bridge_rule
    bplace = next(x for x in w.places if x["id"] == br["place"])["name"]
    cand = [p for p in persons if alive_end[p] and w.persons[p]["adult"]]
    rng.shuffle(cand)
    born = [p for p in cand if w.persons[p]["surname"] == br["surname"] and w.persons[p]["father"] and w.persons[w.persons[p]["father"]]["surname"] == br["surname"]]
    by_marr = [p for p in cand if sim.spouse.get(p) and w.persons[sim.spouse[p]]["surname"] == br["surname"] and p not in born]
    widowed_out = [p for p in cand if not sim.spouse.get(p) and any(w.persons[s]["surname"] == br["surname"] for s in sim.ever_married[p]) and p not in born]
    others = [p for p in cand if p not in born and p not in by_marr and p not in widowed_out]
    for grp, a in ((born[:3], "yes"), (by_marr[:4], "yes"), (widowed_out[:4], "no"), (others[:4], "no")):
        for p in grp:
            ev = [br["eid"]] + [e for e, _ in sim.hist_spouse[p][-1:]] + ([sim.intro_eid[p]] if p in sim.intro_eid else [])
            add("RULE_BRIDGE", f"At the end of the record, is {full(p)} allowed to cross the toll bridge at {bplace}? Answer yes or no.",
                {"kind": "yesno", "gold": a, "aliases": [a]}, ev, p)
    # PLAN_VS_TRAVEL
    pq = []
    for pl in sim.plans:
        a = "yes" if pl["dest"] in sim.visited[pl["person"]] else "no"
        ev = [pl["eid"]] + [e for e, l in sim.hist_loc[pl["person"]] if l == pl["dest"]]
        if a == "no":
            ev += [e for e, _ in sim.hist_loc[pl["person"]]]
        pq.append((pl["person"], pl["dest"], a, ev))
    tv = [e for e in w.events if e["type"] == "TRAVEL"]
    rng.shuffle(tv)
    for e in tv[: per_type // 2]:
        pq.append((e["person"], e["dest"], "yes", [e["id"]]))
    rng.shuffle(pq)
    seen = set()
    for p, d, a, ev in pq:
        if (p, d) in seen or len([q for q in Q if q["qtype"] == "EVER_VISITED"]) >= per_type:
            continue
        seen.add((p, d))
        dn = next(x for x in w.places if x["id"] == d)["name"]
        add("EVER_VISITED", f"Did {full(p)} ever live in {dn} at any point in the record? Answer yes or no.",
            {"kind": "yesno", "gold": a, "aliases": [a]}, ev, p)
    # ABSTAIN / occupation & birthplace
    unk_birth = [p for p in persons if not w.persons[p]["birthplace"]]
    known_birth = [p for p in persons if w.persons[p]["birthplace"]]
    rng.shuffle(unk_birth)
    rng.shuffle(known_birth)
    for p in unk_birth[: per_type // 2]:
        add("BIRTHPLACE", f"Where was {full(p)} born? Answer 'unknown' if the record never says.",
            {"kind": "unknown", "gold": "unknown", "aliases": ["unknown"]}, [], p)
    for p in known_birth[: per_type // 2]:
        ev = [e["id"] for e in w.events if e["type"] == "INIT_PERSON" and e["person"] == p]
        add("BIRTHPLACE", f"Where was {full(p)} born? Answer 'unknown' if the record never says.", place_ans(w.persons[p]["birthplace"]), ev, p)
    # OCCUPATION_NOW
    occ = [p for p in persons if sim.occupation.get(p) and alive_end[p]]
    rng.shuffle(occ)
    changed = [p for p in occ if any(e["type"] == "OCCUPATION" and e["person"] == p for e in w.events)]
    for p in (changed + [x for x in occ if x not in changed])[: per_type]:
        ev = [e["id"] for e in w.events if e.get("person") == p and e["type"] in ("OCCUPATION", "INIT_PERSON")][-1:]
        o = sim.occupation[p]
        add("OCCUPATION_NOW", f"What is the trade of {full(p)} at the end of the record? Answer with a single word.",
            {"kind": "word", "gold": o, "aliases": [o]}, ev, p)
    ev_by = {e["id"]: e for e in w.events}
    for i, q in enumerate(Q):
        q["qid"] = f"Q{i:04d}"
        core = list(q["evidence"])
        full_ev = set(core)
        frontier = list(core)
        for _ in range(4):
            nxt = []
            for e in frontier:
                for d in ev_by[e].get("ref_deps", []):
                    if d not in full_ev:
                        full_ev.add(d)
                        nxt.append(d)
            frontier = nxt
        q["evidence_core"] = sorted(core)
        q["evidence"] = sorted(full_ev)
    return Q


# ------------------------------------------------------------------ filler
NEUTRAL = [
    "The wind came off the water with a smell of salt and tar.",
    "Rain had been threatening since morning, but it held off.",
    "Somewhere a dog barked at nothing and then went quiet.",
    "The bell for vespers rang thinly across the roofs.",
    "Smoke from the chimneys lay flat over the fields.",
    "A cart loaded with turnips creaked past the well.",
    "The light went early, as it did that time of year.",
    "Children chased a hoop down the lane, shrieking.",
    "Frost had silvered the hedges overnight.",
    "The baker's boy was late again, and the line at the oven grew long.",
    "Someone had chalked a crooked sun on the wall of the forge.",
    "Gulls quarreled over a heap of fish heads by the steps.",
    "The road was all ruts and puddles after the thaw.",
    "Bees hummed in the lavender behind the parsonage.",
]
MUNDANE = [
    "{p} mended a torn sleeve by the window and said little.",
    "{p} argued with the carter over the price of a sack of oats.",
    "{p} spent the evening sorting old letters by candlelight.",
    "{p} walked the long way round to avoid the muddy square.",
    "{p} laughed at a story nobody else found funny.",
    "{p} counted the coins twice and still came up a penny short.",
    "{p} fell asleep in the chair before the fire had caught.",
    "{p} hummed a tune from childhood while scrubbing the step.",
    "{p} watched the clouds and predicted rain, wrongly.",
    "{p} bought a ribbon at the stall and then regretted it.",
    "{p} complained of an aching back, as usual.",
    "{p} read the almanac aloud, mispronouncing half the saints.",
]
DIALOGUE = [
    "\"The price of salt is a scandal,\" said {p}. \"A scandal,\" agreed {q}.",
    "\"Will it rain, do you think?\" asked {p}. {q} only shrugged.",
    "\"I heard the river is up again,\" {p} remarked, and {q} said it always was in spring.",
    "{p} and {q} talked of nothing much — the weather, the harvest, a lame horse.",
    "\"You look tired,\" {q} told {p}, who did not deny it.",
]


def load_prose_pool(paths, min_len=300, max_len=1200, limit=60000):
    pool = []
    for pth in paths:
        try:
            txt = open(pth, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        paras = [" ".join(x.split()) for x in txt.replace("\r\n", "\n").split("\n\n")]
        for p in paras:
            if min_len <= len(p) <= max_len and not p.isupper() and "CHAPTER" not in p.upper()[:30] \
                    and "gutenberg" not in p.lower():
                pool.append(p)
    return pool[:limit] if limit else pool


def assemble(sim, density, prose_pool, prose_ratio=0.5, seed=0):
    """Return (text, spans{eid:[start,end]}, chapters)."""
    w = sim.w
    fr = stable_rng("filler", w.seed, density, seed)
    ev_by_id = {e["id"]: e for e in w.events}
    out = []
    pos = 0
    spans = {}
    prose_i = fr.randrange(len(prose_pool)) if prose_pool else 0

    def emit(s):
        nonlocal pos
        out.append(s)
        pos += len(s)

    def filler_unit(scene):
        nonlocal prose_i
        present = [w.full(x) if fr.random() < 0.5 else w.persons[x]["first"] for x in scene.get("present", [])]
        if prose_pool and fr.random() < prose_ratio:
            s = prose_pool[prose_i % len(prose_pool)]
            prose_i += 1
            return s
        x = fr.random()
        if present and x < 0.45:
            return fr.choice(MUNDANE).format(p=fr.choice(present))
        if len(present) >= 2 and x < 0.65:
            a, b = fr.sample(present, 2)
            return fr.choice(DIALOGUE).format(p=a, q=b)
        return " ".join(fr.sample(NEUTRAL, 2))

    cur_ch = None
    for sc in w.scenes:
        if sc["chapter"] != cur_ch:
            cur_ch = sc["chapter"]
            year = (cur_ch - 1) // 4
            if sc["kind"] == "epilogue":
                emit(f"\n\nEpilogue\n\n")
            else:
                emit(f"\n\nChapter {cur_ch}\n\nIt was the {SEASONS[(cur_ch - 1) % 4]} of the {ORD[min(year, len(ORD)-1)]} year.\n\n")
        if sc["place"]:
            pl = next(x for x in w.places if x["id"] == sc["place"])
            emit(f"In {pl['label']}. ")
        evs = list(sc["events"])
        base = density * len(evs)
        n_fill = int(base) + (1 if fr.random() < base - int(base) else 0)
        # distribute filler units before / between / after events
        slots = [0] * (len(evs) + 1)
        for _ in range(n_fill):
            slots[fr.randrange(len(slots))] += 1
        for i in range(len(evs) + 1):
            for _ in range(slots[i]):
                emit(filler_unit(sc) + "\n\n")
            if i < len(evs):
                e = ev_by_id[evs[i]]
                start = pos
                emit(e["text"])
                spans[e["id"]] = [start, pos]
                emit("\n\n")
    return "".join(out), spans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--chapters", type=int, default=40)
    ap.add_argument("--families", type=int, default=10)
    ap.add_argument("--densities", type=str, default="0,2,8,32")
    ap.add_argument("--per_type", type=int, default=25)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--prose", type=str, nargs="*", default=[])
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    w = World(args.seed, n_families=args.families, n_chapters=args.chapters)
    sim = Sim(w)
    sim.run()
    qrng = stable_rng("questions", args.seed)
    Q = build_questions(sim, qrng, per_type=args.per_type)
    world_dump = {"seed": args.seed, "persons": w.persons, "places": w.places, "items": w.items,
                  "secrets": w.secrets, "surnames": w.surnames,
                  "rules": {"vault": sim.vault_rule, "bridge": sim.bridge_rule, "heir": sim.heir_rule},
                  "final": {"alive": sim.alive, "loc": sim.loc, "spouse": sim.spouse, "owner": sim.owner,
                            "occupation": sim.occupation, "knows": {k: sorted(v) for k, v in sim.knows.items()}},
                  "promises": sim.promises, "rumors": sim.rumors, "plans": sim.plans}
    json.dump(world_dump, open(os.path.join(args.out, "world_GOLD.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(w.events, open(os.path.join(args.out, "events_GOLD.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, "questions_GOLD.jsonl"), "w", encoding="utf-8") as f:
        for q in Q:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    with open(os.path.join(args.out, "questions_reader.jsonl"), "w", encoding="utf-8") as f:
        for q in Q:
            f.write(json.dumps({"qid": q["qid"], "qtype": q["qtype"], "question": q["question"]}, ensure_ascii=False) + "\n")
    prose_pool = load_prose_pool(args.prose) if args.prose else []
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    stats = {}
    for d in [float(x) for x in args.densities.split(",")]:
        text, spans = assemble(sim, d, prose_pool)
        tag = f"d{d:g}"
        open(os.path.join(args.out, f"record_{tag}.txt"), "w", encoding="utf-8").write(text)
        json.dump(spans, open(os.path.join(args.out, f"spans_{tag}_GOLD.json"), "w"), indent=0)
        ntok = len(enc.encode(text, disallowed_special=()))
        stats[tag] = {"chars": len(text), "tokens_cl100k": ntok, "sha256": hashlib.sha256(text.encode()).hexdigest()}
    from collections import Counter
    stats["n_events"] = len(w.events)
    stats["event_types"] = Counter(e["type"] for e in w.events)
    stats["n_persons"] = len(w.persons)
    stats["n_questions"] = len(Q)
    stats["qtypes"] = Counter(q["qtype"] for q in Q)
    stats["answer_dist"] = {t: Counter(q["answer"]["gold"] for q in Q if q["qtype"] == t and q["answer"]["kind"] in ("yesno", "label", "none", "unknown"))
                            for t in sorted(set(q["qtype"] for q in Q))}
    json.dump(stats, open(os.path.join(args.out, "stats.json"), "w"), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
