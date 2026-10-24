"""Replay of the manuscript's tables and figures from stored outputs only.

python release/reproduce_tables.py      # writes release/reproduced/*, release/REPRODUCE_REPORT.md, the two hash lists

Model calls are blocked: runs/NO_CLAUDE and runs/NO_GPT are created for the duration (methods/llm.py refuses Claude
and GPT calls while they exist) and removed afterwards; only report scripts are run, none of which calls Ollama, agy or
Gemini.  (methods/evx_report.py rebuilds index objects through their build code, which reads the stored caches; with
a cache missing it would reach a Claude call, which the flag stops.)

Checks, per table: the command must exit 0 and print something; its whole output (line endings and trailing spaces
normalised) must occur as one contiguous block in the paper table file it is compared with, so any changed number,
denominator, condition label, missing or extra row fails.  Figures are written to release/reproduced/figures and
compared byte for byte (CSV) and by sha256 (PNG) with paper/figures.  The run fails as a whole if any check fails.
The report lists what each table covers in the manuscript; tables not listed are not covered by this replay.
"""
import fnmatch
import glob
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "release", "reproduced")
NEW = ",".join([f"ama_ws{i:02d}" for i in range(1, 25)] + [f"ama_gs{i:02d}" for i in range(1, 17)])
FRESH = ",".join(sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "data", "ama_sp[0-9]*")) +
                        glob.glob(os.path.join(ROOT, "data", "ama_gm[0-9]*"))))
ADDR9 = "mem-addr2,mem-addr_steponly,mem-addr_notab,mem-addr_noid,mem-pbm25,hybrid,mem-cmm4,mem-cmm4a,full,agrep"
ADDR_V4 = "mem-addr4,mem-addr2,mem-addr_steponly,full,hybrid,mem-pbm25,mem-cmm4,agrep,ccagent"
P = "paper/"
# (name, script and arguments, extra environment, paper file, what it covers: "Main" = main text, "Supp." =
# supplementary material)
TABLES = [
    ("state_continuity_counting_final", ["methods/final_report.py"], {}, P + "tables_final.md",
     "Main 7.1 Table 4, 7.3 Table 8, 7.4; Supp. 6.1-6.3 state tables (0.5M, 1.9M, budgets), continuity, anchored counting, B.1"),
    ("continuity_stats", ["methods/continuity_stats.py", "--sets", "cont2_s7,cont2_s8"], {},
     P + "tables_continuity.md", "Main 7.3; Supp. 6.2 per-set J, TPR, FPR, pair accuracy"),
    ("replication_4readers", ["methods/agy_replication_report.py"], {}, P + "tables_replication_4readers.md",
     "Main 7.1 Table 5; Supp. 6.1-6.3 four reader families"),
    ("added_baselines", ["methods/added_baselines_report.py"], {}, P + "tables_added_baselines.md",
     "Main 7.1 Table 6; Supp. 6.1 post-hoc baselines (before the 18-comparison Holm family; that family is in cluster_stats' source data)"),
    ("event_index_v5", ["methods/evx_report.py", "--v5"], {}, P + "tables_evx5_test.md", "Main 7.4 Table 9; Supp. 6.3 G2 table"),
    ("cluster_stats", ["methods/cluster_stats.py"], {}, P + "tables_cluster_stats.md",
     "Main 7.1, 7.3-7.4; Supp. 6.2-6.3 per-world and cluster intervals, zero split, oracle-certificate control"),
    ("oolong_main_haiku", ["methods/oolong_report.py", "--split", "test", "--methods", "index,index_bSonnet,bm25,full,closed"],
     {}, P + "tables_oolong_main.md", "Main 7.6 Table 10; Supp. 6.4 main table and primary analysis (Haiku)"),
    ("oolong_main_gpt", ["methods/oolong_report.py", "--split", "test", "--methods", "index,bm25,full,closed",
                         "--reader", "codex-gpt-6.1-sol"], {}, P + "tables_oolong_main.md", "Main 7.6 Table 10; Supp. 6.4 (GPT reader)"),
    ("oolong_error_decomp", ["methods/oolong_error_decomp.py"], {}, P + "tables_oolong_error_decomp.md",
     "Main 7.6; Supp. 6.4 where the index loses"),
    ("oolong_exact", ["methods/oolong_exact_report.py"], {}, P + "tables_oolong_exact.md", "Main 7.6; Supp. 6.4 exact answers on numeric questions"),
    ("oolong_disjoint", ["methods/oolong_disjoint.py"], {}, P + "tables_oolong_disjoint.md",
     "Main 7.6; Supp. 6.4 shared episodes"),
    ("gemini_api", ["methods/oolong_gemini_web_score.py"], {"GEMINI_ANSWERS_DIR": "gemini_api/answers"},
     P + "tables_oolong_gemini_full.md", "Main 7.7 Table 12; Supp. 6.5 API run"),
    ("gemini_web", ["methods/oolong_gemini_web_score.py"], {}, P + "tables_oolong_gemini_full.md",
     "Main 7.7 Table 12; Supp. 6.5 web run, Appendix D"),
    ("cost_per_question", ["methods/oolong_cache_cost.py"], {}, P + "tables_oolong_cost_arrival.md",
     "Main 7.9 Fig. 3; Supp. 6.8 cost, one question per call"),
    ("cost_batch20", ["methods/oolong_cache_cost.py", "--batch", "20", "--qs", "1,5,20,100,200,300,400,500,1000,2000"],
     {}, P + "tables_oolong_cost_arrival.md", "Main 7.9 Fig. 3; Supp. 6.8 cost, 20 questions per call"),
]
for j, jn in (("runs/judged_gpt_block", "gpt"), ("runs/judged_sonnet_block", "sonnet")):
    TABLES += [(f"addr_primary_{jn}", ["methods/addr_report.py", "--data", NEW, "--judged", j, "--methods", ADDR9,
                                       "--audit"], {}, P + "tables_addr_test_primary_haiku.md",
                f"Main 7.10; Supp. Appendix C primary analysis, {jn} judge"),
               (f"addr_agent_{jn}", ["methods/addr_report.py", "--data", NEW, "--judged", j, "--methods",
                                     "mem-addr2,ccagent", "--audit"], {},
                P + "tables_addr_test_primary_haiku.md", f"Supp. Appendix C Claude Code agent, {jn} judge"),
               (f"addr_v4_{jn}", ["methods/addr_report.py", "--data", FRESH, "--judged", j, "--methods", ADDR_V4,
                                  "--audit", "--audit_file", "gold_audit_sonnet.json"], {},
                P + "tables_addr_v4_test_two_judges.md", f"Supp. Appendix C version-4 test, {jn} judge")]
for rd in ("claude-claude-haiku-4-5-20251001", "codex-gpt-6.1-sol", "agy-gemini-4-argon-low"):
    TABLES.append((f"addr_3readers_{rd.split('-')[1]}", ["methods/addr_report.py", "--data", NEW, "--judged",
                   "runs/judged_gpt_block", "--reader", rd, "--methods", "mem-addr2,mem-addr_steponly,mem-pbm25,hybrid",
                   "--audit"], {}, P + "tables_addr_test_3readers_gptjudge.md",
                   "Supp. Appendix C three readers"))
# analyses cited in the supplement that have no table file of their own: their outputs are kept in one file
S = P + "tables_supporting_analyses.md"
CERT = "saga_v5_s7:d16:cmm4,saga_v5_s8:d16:cmm4,saga_v5_s4:d16:cmm2,saga_v5_s5:d16:cmm2"
TABLES += [
    ("reader_robustness", ["methods/reader_robust_report.py"], {}, P + "tables_reader_robust.md",
     "Main 7.2 Table 7: reader robustness, 11 readers on worlds T1-T2"),
    ("compaction_survival_T1", ["methods/compaction_survival.py", "saga_v5_s7", "d16"], {}, S,
     "Main 7.8; Supp. 6.7 fact survival through compaction, world T1"),
    ("compaction_survival_T2", ["methods/compaction_survival.py", "saga_v5_s8", "d16"], {}, S,
     "Main 7.8; Supp. 6.7 fact survival through compaction, world T2"),
    ("statement_scope", ["methods/cert_block_misses.py", CERT], {}, S, "Supp. B.3 misses of the certified block"),
    ("statement_precision", ["methods/cert_block_precision.py", CERT], {}, S, "Supp. B.3 precision on the certified block"),
    ("statement_effect", ["methods/statement_effect_ci.py", "."], {}, S, "Main 7.5; Supp. B.3 value of the completeness statement"),
    ("lifecycle_cost_D2_D3", ["methods/costs.py", "--data", "saga_v5_s2,saga_v5_s3"], {}, S,
     "Main 7.9; Supp. 6.8 and B.1 lifecycle cost and break-even, worlds D2-D3"),
    ("lifecycle_cost_D4_D5", ["methods/costs.py", "--data", "saga_v5_s4,saga_v5_s5"], {}, S,
     "Main 7.9; Supp. 6.8 and B.1 lifecycle cost and break-even, worlds D4-D5"),
    ("escalation", ["methods/escalation_compare.py"], {}, S, "Main 7.5; Supp. 6.6 and B.9 certificate-gated against reader-triggered budgets"),
]
# further analyses (methods/revision_analyses.py)
R = P + "tables_revision.md"
TABLES += [(f"revision_{c}", ["methods/revision_analyses.py", c], {}, R, cov) for c, cov in (
    ("length", "Main 7.1 Fig. 1: accuracy across length on the same questions"),
    ("clusters", "Main 7.1: state-tracking intervals over clusters of questions sharing gold evidence"),
    ("oolong", "Main 7.6 Table 11: Oolong-real index minus BM25 by answer type"),
    ("full44k", "Supp. 6.8 and B.1: full-context reading at 44k on the same questions"),
    ("added18", "Main 7.1 Table 6: Holm over the 18 post-hoc comparisons"))]
# reading-budget sweep with three readers
TABLES.append(("budget_sweep_3readers", ["methods/budget_sweep_report.py"], {}, P + "tables_budget_sweep.md",
               "Main 4 and 7.1; Supp. 6.1 Table S6: budget sweep with Haiku, GPT and Sonnet readers"))
FIGS = [("fig_length", "Main Fig. 1", ["methods/revision_analyses.py", "figure"]),
        ("fig_oolong_by_window", "Main Fig. 2 (Supp. Figure S1)", ["methods/figures_v2.py"]),
        ("fig_cost_arrival", "Main Fig. 3 (Supp. Figure S2)", ["methods/figures_v2.py"])]
STORED = ["runs/results/*.jsonl", "runs/results_oolong/*.jsonl", "runs/judged_gpt_block/*.json",
          "runs/judged_sonnet_block/*.json", "runs/judged_gpt/*.json", "gemini_api/answers/*.txt",
          "gemini_api/raw/*.json", "gemini_web/answers/*.txt", "gemini_web/manifest.json",
          "gemini_web/windows/*.txt", "gemini_web/prompts/*.txt", "data/*/questions_GOLD.jsonl",
          "data/*/world_GOLD.json", "data/*/events_GOLD.json", "data/*/gold_audit_*.json",
          "data/_external/oolong_real/test/*.json*", "data/_external/oolong_real/index/*.json"]
CODE = ["methods/*.py", "bench/*.py", "release/*.py", "runs/*.sh"]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _list(name):
    p = os.path.join(ROOT, "release", name)
    return [l.strip() for l in open(p, encoding="utf-8") if l.strip() and not l.startswith("#")] if os.path.exists(p) \
        else None


# the hash lists cover the files of the public release only: in the working tree, those of release/PUBLIC_FILES.txt
# (and the prepared third-party data, whose hashes let users check their own preparation); in the release, every file
_EXCL, _PUB = [e.rstrip("/") for e in _list("PUBLIC_EXCLUDE.txt") or []], _list("PUBLIC_FILES.txt")
_PUB = set(_PUB) if _PUB is not None else None


def released(r):
    if any(r == e or r.startswith(e + "/") or fnmatch.fnmatch(r, e) for e in _EXCL):
        return False
    return _PUB is None or r in _PUB or r.startswith(("data/_external/", "data/ama_", "data/locomo_", "data/nhq_"))


def norm(t):
    return "\n".join(l.rstrip() for l in t.replace("\r\n", "\n").split("\n")).strip("\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    made = []
    for f in (os.path.join(ROOT, "runs", n) for n in ("NO_CLAUDE", "NO_GPT")):
        if not os.path.exists(f):
            open(f, "w").write("set by release/reproduce_tables.py during a replay\n")
            made.append(f)
    rep = [f"# Replay of tables and figures from stored outputs\n\nPYTHONHASHSEED=0, "
           f"Python {sys.version.split()[0]}. Model calls blocked (NO_CLAUDE, NO_GPT).\n",
           "| table | covers in the manuscript | command | paper file | check | output sha256 |", "|---|---|---|---|---|---|"]
    fails = 0
    try:
        for name, cmd, env, target, covers in TABLES:
            e = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONHASHSEED="0", **env)
            p = subprocess.run([sys.executable] + cmd, cwd=ROOT, env=e, capture_output=True, text=True,
                               encoding="utf-8", timeout=3600)
            out = os.path.join(OUT, name + ".md")
            open(out, "w", encoding="utf-8").write(p.stdout)
            got = norm(p.stdout)
            tgt = norm(open(os.path.join(ROOT, target), encoding="utf-8").read())
            ok = p.returncode == 0 and bool(got) and got in tgt
            fails += not ok
            why = "PASS" if ok else ("FAIL: exit " + str(p.returncode) if p.returncode else
                                     "FAIL: empty output" if not got else "FAIL: output not found as one block")
            short = " ".join(c if len(c) <= 50 else c[:47] + "..." for c in cmd)
            env_s = " ".join(f"{k}={v}" for k, v in env.items())
            rep.append(f"| {name} | {covers} | `{(env_s + ' ') if env_s else ''}python {short}` | {target} | {why} | "
                       f"{sha(out)[:16]} |")
        figdir = os.path.join(OUT, "figures")
        os.makedirs(figdir, exist_ok=True)
        rc = {}
        for cmd in {tuple(c) for _, _, c in FIGS}:
            rc[cmd] = subprocess.run([sys.executable] + list(cmd), cwd=ROOT, capture_output=True, text=True,
                                     encoding="utf-8", env=dict(os.environ, FIG_OUT=figdir, PYTHONIOENCODING="utf-8",
                                                                PYTHONHASHSEED="0"), timeout=3600).returncode
        for f, label, cmd in FIGS:
            code_ = rc[tuple(cmd)]
            res = []
            for ext in ("csv", "png"):
                a_, b_ = os.path.join(figdir, f"{f}.{ext}"), os.path.join(ROOT, "paper", "figures", f"{f}.{ext}")
                same = os.path.exists(a_) and os.path.exists(b_) and (
                    norm(open(a_, encoding="utf-8").read()) == norm(open(b_, encoding="utf-8").read())
                    if ext == "csv" else sha(a_) == sha(b_))
                res.append(f"{ext} {'same' if same else 'DIFFERENT'}")
                fails += not same
            fails += code_ != 0
            rep.append(f"| {f} | {label} | `FIG_OUT=... python {' '.join(cmd)}` | "
                       f"paper/figures/{f}.* | {'PASS' if all('same' in r for r in res) and code_ == 0 else 'FAIL'} "
                       f"({', '.join(res)}){'' if code_ == 0 else ', exit ' + str(code_)} | "
                       f"{sha(os.path.join(figdir, f + '.csv'))[:16] if os.path.exists(os.path.join(figdir, f + '.csv')) else '-'} |")
    finally:
        for f in made:
            os.remove(f)
    rel = lambda f: os.path.relpath(f, ROOT).replace(os.sep, "/")
    files = sorted({f for g in STORED for f in glob.glob(os.path.join(ROOT, g)) if released(rel(f))})
    with open(os.path.join(ROOT, "release", "STORED_OUTPUTS_SHA256.txt"), "w", encoding="utf-8") as w:
        w.write("# sha256 of the stored inputs read by the replay\n")
        for f in files:
            w.write(f"{sha(f)}  {os.path.relpath(f, ROOT).replace(os.sep, '/')}\n")
    code = sorted({f for g in CODE for f in glob.glob(os.path.join(ROOT, g)) if released(rel(f))})
    with open(os.path.join(ROOT, "release", "CURRENT_FILES_SHA256.txt"), "w", encoding="utf-8") as w:
        w.write("# sha256 of the code at this replay\n")
        for f in code:
            w.write(f"{sha(f)}  {os.path.relpath(f, ROOT).replace(os.sep, '/')}\n")
    rep.append(f"\n**{'ALL CHECKS PASSED' if not fails else str(fails) + ' CHECK(S) FAILED'}.** Stored inputs hashed: "
               f"{len(files)} files (release/STORED_OUTPUTS_SHA256.txt); code hashed: {len(code)} files "
               "(release/CURRENT_FILES_SHA256.txt), both written by this run. A table of the manuscript that is not "
               "listed above is not covered by this replay.")
    open(os.path.join(ROOT, "release", "REPRODUCE_REPORT.md"), "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
