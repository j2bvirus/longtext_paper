"""Event-table index for Oolong-real.

write time   each episode transcript once: chunks of about 1,500 tokens of numbered lines; the builder lists every
             die roll actually made and every spell actually cast:
               R|<line>|<who rolled, as named>|<roll type>|<natural value or ->|<total or ->
               S|<line>|<caster, as named>|<spell name>|<level or ->
             names are mapped to characters with the window's player-to-character table; an event counts only if
             its line number lies in the chunk it was written for.  Episode tables are cached by the episode text's
             hash, so every window that contains an episode reuses its table.
query time   (see oolong_eval.py) the question's event kind and episode range are chosen by one builder call; the
             complete aggregates of that range are computed from the tables and given to the reader.
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "_external", "oolong_real", "index")
CHUNK_TOK = 1500
WRITE_SYS = (
    "You index the transcript of a Dungeons and Dragons game session so that dice rolls and spells can later be "
    "counted. The lines are numbered (L<number>). List every die roll a player actually makes and every spell a "
    "player character actually casts in these lines, one per line, nothing else:\n"
    "R|<line number>|<who rolled: the character or the player, as named>|<roll type>|<natural value or ->|<total or ->\n"
    "S|<line number>|<who cast it: the character or the player, as named>|<spell name>|<spell level or ->\n"
    "<roll type>: the check, save or roll as called, e.g. Perception, Stealth, Insight, Dexterity Save, Attack, "
    "Damage, Initiative, Persuasion. A roll is made when a player reports its result (for example 'Natural 20', "
    "'16', 'that's a 19', 'nine total'); a roll that is only asked for, or a number that is not a die result, is not "
    "listed. <natural value>: the number on the die if stated (a 'natural 20' or 'nat one' gives 20 or 1), "
    "otherwise '-'. <total>: the stated total if any, otherwise '-'. Rolls by the game master (Matt) are not listed. "
    "A spell is cast when the caster declares it and it takes effect or is resolved; talk about spells, spells "
    "considered but not cast, and abilities that are not spells are not listed. Be complete and terse.")


WRITE_SYS_V2 = (  # development v2: player and character apart; results stated by the game master count
    "You index the transcript of a Dungeons and Dragons game session so that dice rolls and spells can later be "
    "counted. Each line starts with the speaking player's name and is numbered (L<number>). List every die roll a "
    "player makes and every spell a player character casts in these lines, one per line, nothing else:\n"
    "R|<line number>|<player who rolled>|<their character, if the context shows it, else ->|<roll type>|"
    "<natural value or ->|<total or ->\n"
    "S|<line number>|<player who cast it>|<their character, if the context shows it, else ->|<spell name>|"
    "<spell level or ->\n"
    "<player>: the real person's first name as it appears at the start of lines (the game master is Matt; his own "
    "rolls are not listed). <character>: the in-game name of that player's character in this session, from how "
    "others address them or from the game master's narration; '-' if unclear.\n"
    "<roll type>: the check, save or roll as called, e.g. Perception, Stealth, Insight, Dexterity Save, Attack, "
    "Damage, Initiative, Persuasion. A roll counts when its result is stated, by the player ('Natural 20', '16', "
    "'that's a 19', 'nine total') or by the game master about that player ('she rolled a 22'); list each roll once, "
    "at the line where its result is first stated. Several attack or damage rolls stated together count separately. "
    "A roll that is only asked for, and numbers that are not die results, are not listed. <natural value>: the "
    "number on the die if stated ('natural 20', 'nat one' give 20 and 1), otherwise '-'. <total>: the stated total "
    "if any, otherwise '-'.\n"
    "A spell counts when the caster declares it and it takes effect or is resolved (cantrips included); talk about "
    "spells, spells considered but not cast, and abilities that are not spells are not listed. Use the spell's "
    "standard name. Use a plain hyphen '-' for unknown fields. Be complete and terse.")
LINE_V2 = re.compile(r"^\s*(R)\|\s*L?(\d+)\s*\|" + r"([^|]*)\|" * 4 + r"([^|]*?)\s*$")
LINE_V2S = re.compile(r"^\s*(S)\|\s*L?(\d+)\s*\|" + r"([^|]*)\|" * 3 + r"([^|]*?)\s*$")
DASHES = {"–", "—", "−", "->", "", "n/a", "none", "?"}


def clean(v):
    v = (v or "").strip()
    return "-" if v.lower() in DASHES else v


def split_window(text):
    """(player->character map, [episode texts]) of a context window"""
    pmap = dict(re.findall(r"^(\S[^\n]*?) plays the character ([^\n]+?)\.\s*$", text, re.M))
    eps = re.findall(r"\[START OF EPISODE\]\n(.*?)\n\[END OF EPISODE\]", text, re.S)
    return pmap, eps


def ep_key(ep):
    return hashlib.sha1(ep.encode("utf-8")).hexdigest()[:16]


def chunks_of(ep, chunk_tok=CHUNK_TOK):
    lines = ep.split("\n")
    out, cur, t = [], [], 0
    for i, ln in enumerate(lines):
        k = core.ntok(ln) + 4
        if cur and t + k > chunk_tok:
            out.append(cur)
            cur, t = [], 0
        cur.append((i, ln))
        t += k
    if cur:
        out.append(cur)
    return out


LINE = re.compile(r"^\s*([RS])\|\s*L?(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)(?:\|([^|]*))?\s*$")


def index_episode_v2(ep, builder="claude:claude-haiku-4-5-20251001", workers=6, chunk_tok=CHUNK_TOK):
    """development v2 event table of one episode (player and character apart), cached by text hash"""
    key = ep_key(ep)
    suffix = "" if chunk_tok == CHUNK_TOK else f"c{chunk_tok}_"
    path = os.path.join(CACHE, f"ep_{key}_v2_{suffix}{builder.replace(':', '-')}.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    chs = chunks_of(ep, chunk_tok)

    def one(ch):
        lo, hi = ch[0][0], ch[-1][0]
        prompt = "\n".join(f"L{i}: {ln}" for i, ln in ch)
        r = llm.call(builder, WRITE_SYS_V2, prompt, max_tokens=2500, tag=f"build|oolong2|{key}|{lo}")
        rolls, spells, bad = [], [], 0
        for raw in r["text"].splitlines():
            m = LINE_V2.match(raw) or LINE_V2S.match(raw)
            if not m:
                continue
            kind, li = m.group(1), int(m.group(2))
            if not lo <= li <= hi:
                bad += 1
                continue
            f = [clean(x) for x in m.groups()[2:]]
            if kind == "R":
                rolls.append({"line": li, "player": f[0], "character": f[1], "type": f[2], "natural": f[3],
                              "total": f[4]})
            else:
                spells.append({"line": li, "player": f[0], "character": f[1], "spell": f[2], "level": f[3]})
        return rolls, spells, bad, r["in_tokens"], r["out_tokens"]
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, chs))
    rolls = sorted([x for r in res for x in r[0]], key=lambda x: x["line"])
    spells = sorted([x for r in res for x in r[1]], key=lambda x: x["line"])
    # idle time: each player's character in this episode = the name most often given for that player
    votes = {}
    for e in rolls + spells:
        if e["character"] != "-":
            votes.setdefault(e["player"].lower(), Counter())[e["character"]] += 1
    cast = {p: c.most_common(1)[0][0] for p, c in votes.items()}
    for e in rolls + spells:
        e["character_filled"] = e["character"] if e["character"] != "-" else cast.get(e["player"].lower(), "-")
    out = {"rolls": rolls, "spells": spells, "cast": cast,
           "ungrounded": sum(r[2] for r in res), "chunks": len(chs),
           "cost": {"in": sum(r[3] for r in res), "out": sum(r[4] for r in res)}}
    os.makedirs(CACHE, exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return out


RECHECK_SYS = (WRITE_SYS_V2 + "\n\nYou are given the lines and the events already listed for them. List ONLY the rolls "
               "and spells that are missing from that list, in the same format; if nothing is missing, answer NONE.")


def index_episode_v3(ep, builder="claude:claude-haiku-4-5-20251001", workers=6):
    """development v3: v2, then one recheck call per chunk that sees the lines and the events already
    listed and adds only missing ones (a recall pass; nothing is deleted)"""
    key = ep_key(ep)
    path = os.path.join(CACHE, f"ep_{key}_v3_{builder.replace(':', '-')}.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    base = index_episode_v2(ep, builder, workers)
    chs = chunks_of(ep)

    def one(ch):
        lo, hi = ch[0][0], ch[-1][0]
        have = [e for e in base["rolls"] if lo <= e["line"] <= hi]
        haves = [e for e in base["spells"] if lo <= e["line"] <= hi]
        listed = "\n".join([f"R|{e['line']}|{e['player']}|{e['character']}|{e['type']}|{e['natural']}|{e['total']}"
                            for e in have] + [f"S|{e['line']}|{e['player']}|{e['character']}|{e['spell']}|{e['level']}"
                                              for e in haves]) or "(none)"
        prompt = ("Lines:\n" + "\n".join(f"L{i}: {ln}" for i, ln in ch) + "\n\nEvents already listed:\n" + listed)
        r = llm.call(builder, RECHECK_SYS, prompt, max_tokens=1500, tag=f"build|oolong3|{key}|{lo}")
        rolls, spells = [], []
        for raw in r["text"].splitlines():
            m = LINE_V2.match(raw) or LINE_V2S.match(raw)
            if not m:
                continue
            kind, li = m.group(1), int(m.group(2))
            if not lo <= li <= hi:
                continue
            f = [clean(x) for x in m.groups()[2:]]
            if kind == "R":
                rolls.append({"line": li, "player": f[0], "character": f[1], "type": f[2], "natural": f[3],
                              "total": f[4], "recheck": True})
            else:
                spells.append({"line": li, "player": f[0], "character": f[1], "spell": f[2], "level": f[3],
                               "recheck": True})
        return rolls, spells, r["in_tokens"], r["out_tokens"]
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, chs))
    rolls = sorted(base["rolls"] + [x for r in res for x in r[0]], key=lambda x: x["line"])
    spells = sorted(base["spells"] + [x for r in res for x in r[1]], key=lambda x: x["line"])
    votes = {}
    for e in rolls + spells:
        if e["character"] != "-":
            votes.setdefault(e["player"].lower(), Counter())[e["character"]] += 1
    cast = {p: c.most_common(1)[0][0] for p, c in votes.items()}
    for e in rolls + spells:
        e["character_filled"] = e["character"] if e["character"] != "-" else cast.get(e["player"].lower(), "-")
    out = {"rolls": rolls, "spells": spells, "cast": cast, "ungrounded": base["ungrounded"], "chunks": len(chs),
           "added": {"rolls": sum(len(r[0]) for r in res), "spells": sum(len(r[1]) for r in res)},
           "cost": {"in": base["cost"]["in"] + sum(r[2] for r in res),
                    "out": base["cost"]["out"] + sum(r[3] for r in res)}}
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def index_episode(ep, builder="claude:claude-haiku-4-5-20251001", workers=6):
    """event table of one episode, cached by text hash: {'rolls': [...], 'spells': [...], 'cost': {...}}"""
    key = ep_key(ep)
    path = os.path.join(CACHE, f"ep_{key}_{builder.replace(':', '-')}.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    chs = chunks_of(ep)

    def one(ch):
        lo, hi = ch[0][0], ch[-1][0]
        prompt = "\n".join(f"L{i}: {ln}" for i, ln in ch)
        r = llm.call(builder, WRITE_SYS, prompt, max_tokens=2000, tag=f"build|oolong|{key}|{lo}")
        rolls, spells, bad = [], [], 0
        for raw in r["text"].splitlines():
            m = LINE.match(raw)
            if not m:
                continue
            kind, li = m.group(1), int(m.group(2))
            if not lo <= li <= hi:
                bad += 1
                continue
            f = [(x or "").strip() for x in m.groups()[2:]]
            if kind == "R":
                rolls.append({"line": li, "who": f[0], "type": f[1], "natural": f[2], "total": f[3] or "-"})
            else:
                spells.append({"line": li, "who": f[0], "spell": f[1], "level": f[2]})
        return rolls, spells, bad, r["in_tokens"], r["out_tokens"]
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, chs))
    out = {"rolls": sorted([x for r in res for x in r[0]], key=lambda x: x["line"]),
           "spells": sorted([x for r in res for x in r[1]], key=lambda x: x["line"]),
           "ungrounded": sum(r[2] for r in res), "chunks": len(chs),
           "cost": {"in": sum(r[3] for r in res), "out": sum(r[4] for r in res)}}
    os.makedirs(CACHE, exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def to_character(name, pmap):
    n = name.strip()
    for p, c in pmap.items():
        if n.lower() == p.lower() or n.lower() == p.split()[0].lower():
            return c
    for c in pmap.values():
        if n.lower() == c.lower() or n.lower() == c.split()[0].lower():
            return c
    return n


if __name__ == "__main__":
    # development check: one single-episode window against its gold totals
    wid = sys.argv[1]
    split = sys.argv[2] if len(sys.argv) > 2 else "validation"
    text = open(os.path.join(ROOT, "data", "_external", "oolong_real", split, "windows", wid + ".txt"),
                encoding="utf-8").read()
    pmap, eps = split_window(text)
    t = index_episode(eps[0])
    print("chunks", t["chunks"], "rolls", len(t["rolls"]), "spells", len(t["spells"]), "ungrounded", t["ungrounded"],
          "cost", t["cost"])
    print("rolls by character", Counter(to_character(r["who"], pmap) for r in t["rolls"]).most_common())
    print("spells by character", Counter(to_character(s["who"], pmap) for s in t["spells"]).most_common())
    print("roll types", Counter(r["type"] for r in t["rolls"]).most_common(12))
    print("naturals", Counter(r["natural"] for r in t["rolls"]).most_common(8))
    print("spells", [s["spell"] for s in t["spells"]])
