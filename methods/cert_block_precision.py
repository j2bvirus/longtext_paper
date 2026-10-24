"""Certificate precision on the certified block itself. No LLM, no GPU.

The earlier figure checked core gold evidence against the WHOLE delivered context (certified block plus linked
paragraphs plus keyword fill) and counted questions without core evidence as successes.  Here, for every
question whose entity set fits 85% of the budget (the condition under which the statement is given), we check
whether every core gold evidence span lies inside the certified block, i.e. the paragraphs indexed under the
queried entities, and report questions without core evidence separately.

python methods/cert_block_precision.py saga_v5_s4:d16:cmm2,saga_v5_s5:d16:cmm2,saga_v5_s7:d16:cmm4,saga_v5_s8:d16:cmm4
"""
import collections
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cmm  # noqa: E402
import core  # noqa: E402
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _no_embed(*a, **k):
    raise RuntimeError("offline check must not embed (GPU)")


llm.embed = _no_embed


def main():
    os.environ["MEM_WAIT_ONLY"] = "1"
    rows = []
    for spec in sys.argv[1].split(","):
        ds, d, v = spec.split(":")
        ddir = os.path.join(ROOT, "data", ds)
        text, spans, qs, world = core.load_dataset(ddir, d)
        chunks = core.chunk_record(text, 300)
        m = cmm.REGISTRY[v](text, chunks, ddir, d, types.SimpleNamespace(
            builder="claude:claude-haiku-4-5-20251001", build_workers=1, budget=4000))
        m.build()
        c = collections.Counter()
        for q in qs:
            ents = m.q_entities(q["question"])
            allp = sorted(set().union(*[set(m.ent_paras.get(e, [])) for e in ents])) if ents else []
            tok = sum(m.paras.items[i]["tokens"] for i in allp)
            if not allp or tok > 4000 * 0.85:
                c["not_certified"] += 1
                continue
            c["certified"] += 1
            core_ev = q.get("evidence_core", q["evidence"])
            if not core_ev:
                c["certified_no_evidence"] += 1
                continue
            r = core.evidence_recall({"evidence": core_ev}, spans, m.paras.spans(allp))
            c["certified_with_evidence"] += 1
            c["block_complete"] += 1 if (r is not None and r >= 1) else 0
        n = len(qs)
        prec = c["block_complete"] / max(1, c["certified_with_evidence"])
        rows.append((spec, n, c["certified"], c["certified_no_evidence"], c["certified_with_evidence"], c["block_complete"], prec))
        print(f"{spec}: n={n} certified={c['certified']} ({100 * c['certified'] / n:.1f}%) "
              f"[no core evidence {c['certified_no_evidence']}] block precision="
              f"{c['block_complete']}/{c['certified_with_evidence']} = {100 * prec:.1f}%", flush=True)
    tot_w = sum(r[4] for r in rows)
    tot_c = sum(r[5] for r in rows)
    print(f"pooled block precision {tot_c}/{tot_w} = {100 * tot_c / max(1, tot_w):.1f}%")


if __name__ == "__main__":
    main()
