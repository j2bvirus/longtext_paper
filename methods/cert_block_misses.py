"""Break down certified-block misses. No LLM, no GPU.

For certified questions whose block lacks some core gold evidence, classify each missing evidence event:
  IN SCOPE   the queried subject is a participant of the event (so a paragraph about it should be indexed
             under the subject: a true mention-completeness failure, e.g. an unresolved pronoun or description)
  OUT OF SCOPE  the subject does not take part (e.g. a parent's birth paragraph for a grandparent question):
             outside a mention-completeness guarantee by construction.
python methods/cert_block_misses.py saga_v5_s7:d16:cmm4,saga_v5_s8:d16:cmm4,saga_v5_s4:d16:cmm2,saga_v5_s5:d16:cmm2
"""
import collections
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmm  # noqa: E402
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
llm.embed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline check must not embed (GPU)"))


def participants(ev):
    out = set()
    for k, v in ev.items():
        if k in ("id", "type", "chapter", "text", "where", "ref_deps", "place"):
            continue
        vs = v if isinstance(v, list) else [v]
        for x in vs:
            if isinstance(x, str) and len(x) >= 2 and x[0] == "P" and x[1:].isdigit():
                out.add(x)
    return out


def main():
    os.environ["MEM_WAIT_ONLY"] = "1"
    tot = collections.Counter()
    for spec in sys.argv[1].split(","):
        ds, d, v = spec.split(":")
        ddir = os.path.join(ROOT, "data", ds)
        text, spans, qs, world = core.load_dataset(ddir, d)
        events = {e["id"]: e for e in json.load(open(os.path.join(ddir, "events_GOLD.json"), encoding="utf-8"))}
        chunks = core.chunk_record(text, 300)
        m = cmm.REGISTRY[v](text, chunks, ddir, d, types.SimpleNamespace(
            builder="claude:claude-haiku-4-5-20251001", build_workers=1, budget=4000))
        m.build()
        c = collections.Counter()
        bytype = collections.Counter()
        for q in qs:
            ents = m.q_entities(q["question"])
            allp = sorted(set().union(*[set(m.ent_paras.get(e, [])) for e in ents])) if ents else []
            if not allp or sum(m.paras.items[i]["tokens"] for i in allp) > 4000 * 0.85:
                continue
            core_ev = q.get("evidence_core", q["evidence"])
            if not core_ev:
                continue
            block = m.paras.spans(allp)
            missing = [e for e in core_ev if (core.evidence_recall({"evidence": [e]}, spans, block) or 0) < 1]
            if not missing:
                c["complete"] += 1
                continue
            subj = q.get("subject")
            inscope = [e for e in missing if e in events and subj in participants(events[e])]
            if inscope:
                c["true_miss"] += 1
                bytype[q["qtype"]] += 1
            else:
                c["out_of_scope_only"] += 1
        n = c["complete"] + c["true_miss"] + c["out_of_scope_only"]
        print(f"{spec}: certified-with-evidence {n}; complete {c['complete']}; misses outside the guarantee "
              f"{c['out_of_scope_only']}; true mention misses {c['true_miss']} {dict(bytype)}; "
              f"mention-scope precision {100 * (n - c['true_miss']) / max(1, n):.1f}%", flush=True)
        tot.update(c)
    n = tot["complete"] + tot["true_miss"] + tot["out_of_scope_only"]
    print(f"pooled: complete {tot['complete']}/{n} = {100 * tot['complete'] / max(1, n):.1f}%; "
          f"mention-scope precision (only true misses count as failures) {100 * (n - tot['true_miss']) / max(1, n):.1f}%")


if __name__ == "__main__":
    main()
