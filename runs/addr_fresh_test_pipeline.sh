#!/bin/bash
# Address index version 4: FRESH TEST.
# Version 4 (structured action lines, methods/addrindex.py AddrMem4) was designed after the SWE-bench/GAIA test of
# version 2 and developed on the seen SWE-bench trajectories ama_w01-12 only (4: 33.3, 2: 27.8; audit-ok 70.8 vs
# 54.2, Sonnet judge).  This is its clean test.
# Data: the never-used AMA-Bench trajectories of at least 8,000 tokens: Spider 2.0 (25, 300 q)
#   and BALROG games (20, 240 q).
# Reader: Haiku 4.5, minimal prompt, budget 4k.  Conditions: addr4, addr2, addr_steponly, paragraph BM25, hybrid RAG,
#   full re-reading, CMM v4 (Haiku-built here), agentic search (agrep), Claude Code agent (ccagent).
# Judge: Claude Sonnet 5.5, AMA wording, whole answer (--block).  Gold audit: Sonnet 5.5 over the whole trajectory (AUDIT_MODEL), giving the audit-ok subset.
# Primary analysis: Haiku, all 540 questions, addr4 against every other condition, exact McNemar, Holm-corrected.
#   Secondary: per domain, audit-ok subset, addr4 vs addr2.
# Post hoc, reported separately and never as test evidence: addr4 on the SWE-bench/GAIA test trajectories
#   (ama_ws, ama_gs), whose results motivated version 4.
cd "$(dirname "$0")/.."  # release root
export PYTHONIOENCODING=utf-8
export PYTHONHASHSEED=0
H=claude:claude-haiku-4-5-20251001
FRESH=$(python -c "import json;print(' '.join(m['dataset'] for m in json.load(open('data/_external/ama_bench/manifest_fresh.json')) if m['tokens']>=8000))")
echo "fresh test trajectories: $(echo $FRESH | wc -w)"
(AUDIT_MODEL=claude:claude-sonnet-5-5 python bench/ama_gold_audit.py $FRESH > runs/_addr_fresh_audit.log 2>&1) &
(for ds in $FRESH; do python methods/build_only.py $ds full cmm4 $H > /dev/null 2>&1; echo "$ds cmm4 build exit $?"; done > runs/_addr_fresh_cmm_build.log 2>&1; echo FRESH_CMM_DONE >> runs/_addr_fresh_cmm_build.log) &
for m in mem:addr4 mem:addr2 mem:addr_steponly mem:pbm25 hybrid full; do
  for ds in $FRESH; do
    python methods/run_eval.py --data $ds --density full --method $m --reader $H --prompt minimal --workers 6 > /dev/null 2>&1
    echo "fresh $ds $m exit $? $(date +%H:%M:%S)"
  done
done
until grep -q FRESH_CMM_DONE runs/_addr_fresh_cmm_build.log; do sleep 60; done
for ds in $FRESH; do
  python methods/run_eval.py --data $ds --density full --method mem:cmm4 --reader $H --prompt minimal --builder $H --wait_only --workers 6 > /dev/null 2>&1
  echo "fresh $ds mem:cmm4 exit $? $(date +%H:%M:%S)"
done
for ds in $FRESH; do
  python methods/agentic_eval.py --data $ds --reader $H --workers 6 > /dev/null 2>&1
  echo "fresh $ds agrep exit $? $(date +%H:%M:%S)"
  python methods/cc_agent_eval.py --data $ds --workers 3 > /dev/null 2>&1
  echo "fresh $ds ccagent exit $? $(date +%H:%M:%S)"
done
python methods/judge.py --judge claude:claude-sonnet-5-5 --outdir runs/judged_sonnet_block --block --workers 8 --data $(echo $FRESH | tr ' ' ',') > runs/_addr_fresh_judge_sonnet.log 2>&1
echo "FRESH_TEST_DONE $(date +%H:%M:%S)"
# post hoc (not test evidence)
NEW="$(ls data | grep -E '^ama_(ws|gs)[0-9]+$' | tr '\n' ' ')"
for ds in $NEW; do
  python methods/run_eval.py --data $ds --density full --method mem:addr4 --reader $H --prompt minimal --workers 6 > /dev/null 2>&1
  echo "posthoc $ds mem:addr4 exit $? $(date +%H:%M:%S)"
done
python methods/judge.py --judge claude:claude-sonnet-5-5 --outdir runs/judged_sonnet_block --block --workers 8 --data $(echo $NEW | tr ' ' ',') --only "mem-addr4_p-minimal@claude" > runs/_addr_posthoc_judge_sonnet.log 2>&1
wait
echo "ADDR_FRESH_ALL_DONE $(date +%H:%M:%S)"
