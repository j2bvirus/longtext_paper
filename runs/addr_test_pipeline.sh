#!/bin/bash
# Address index: TEST
#
# Version under test: the one chosen by the rule in runs/addr_dev_b.sh (addr2 if its pooled validation accuracy is at
# least that of addr v1, otherwise v1), written as 'mem:addr' or 'mem:addr2' to runs/addr_choice.txt before this runs.
# Data:
#   new test   SWE-bench ama_ws01-24 (288 questions) and GAIA ama_gs01-16 (192 questions); never used before, no
#              method choice was made on them (bench/ama_prepare_more.py).
#   seen       ama_w01-12 and ama_g01-14 (312 questions) of the earlier study, reported separately.
# Reader 1, Haiku 4.5, minimal prompt, budget 4k:
#   chosen version; addr_steponly (prior-art step lookup of AMA-Agent's released code and MESA's temporal view);
#   addr_notab and addr_noid (ablations); paragraph BM25; hybrid RAG; CMM v4 and v4-adaptive (built beforehand by
#   runs/ama_more_cmm_build.sh); full re-reading where the record fits the window; agentic search (agrep, at most 6
#   commands).  On the seen trajectories only the conditions not run before (chosen version, steponly, agrep).
# Reader 2, Gemini 4 Argon (low) through agy: chosen version, addr_steponly, paragraph BM25, hybrid RAG.
# Judging: Claude Sonnet 5.5 with the AMA-Bench wording on the whole text after the last 'Answer:' (--block), for all
#   answers; GPT-6.1 Sol as a second judge on the answers in its released judge files, with agreement reported (methods/judge_agree.py).
# Primary analysis: Haiku reader, pooled new test (480 questions): the chosen version against every other condition,
#   exact McNemar, Holm-corrected over those comparisons; secondary: per domain, Argon reader, seen trajectories,
#   the subset whose gold the GPT audit labels ok (bench/ama_gold_audit.py), reader tokens per question.
cd "$(dirname "$0")/.."  # release root
export PYTHONIOENCODING=utf-8
export PYTHONHASHSEED=0
ADDR=$(cat runs/addr_choice.txt)
H=claude:claude-haiku-4-5-20251001
A=agy:gemini-4-argon-low
NEW="$(ls data | grep -E '^ama_(ws|gs)[0-9]+$' | tr '\n' ' ')"
SEEN="$(ls data | grep -E '^ama_(w|g)[0-9]+$' | tr '\n' ' ')"
echo "version under test: $ADDR"
argon () {
  for m in $ADDR mem:addr_steponly mem:pbm25 hybrid; do
    for ds in $NEW; do
      python methods/run_eval.py --data $ds --density full --method $m --reader $A --prompt minimal --builder $H --wait_only --workers 8 > /dev/null 2>&1
      echo "argon $ds $m exit $? $(date +%H:%M:%S)"
    done
  done
}
argon > runs/_addr_test_argon.log 2>&1 &
until grep -q "AMA_MORE_CMM_BUILD_DONE" runs/_ama_more_cmm_build.log; do sleep 60; done
for m in $ADDR mem:addr_steponly mem:pbm25 hybrid mem:cmm4 mem:cmm4a mem:addr_notab mem:addr_noid full; do
  for ds in $NEW; do
    python methods/run_eval.py --data $ds --density full --method $m --reader $H --prompt minimal --builder $H --wait_only --workers 6 > /dev/null 2>&1
    echo "haiku $ds $m exit $? $(date +%H:%M:%S)"
  done
done
for ds in $NEW; do
  python methods/agentic_eval.py --data $ds --reader $H --workers 6 > /dev/null 2>&1
  echo "haiku $ds agrep exit $? $(date +%H:%M:%S)"
done
for m in $ADDR mem:addr_steponly; do
  for ds in $SEEN; do
    python methods/run_eval.py --data $ds --density full --method $m --reader $H --prompt minimal --workers 6 > /dev/null 2>&1
    echo "haiku seen $ds $m exit $? $(date +%H:%M:%S)"
  done
done
for ds in $SEEN; do
  python methods/agentic_eval.py --data $ds --reader $H --workers 6 > /dev/null 2>&1
  echo "haiku seen $ds agrep exit $? $(date +%H:%M:%S)"
done
python methods/judge.py --judge claude:claude-sonnet-5-5 --outdir runs/judged_sonnet_block --block --workers 8 --data $(echo $NEW | tr ' ' ',') > runs/_addr_test_judge_sonnet_haiku.log 2>&1
AM=$(echo $ADDR | tr ':' '-')
ONLY=""
for m in $AM mem-addr_steponly agrep mem-pbm25 hybrid mem-cmm4 mem-cmm4a full; do ONLY="$ONLY,${m}_p-minimal@claude"; done
python methods/judge.py --judge claude:claude-sonnet-5-5 --outdir runs/judged_sonnet_block --block --workers 8 --data $(echo $SEEN | tr ' ' ',') --only ${ONLY#,} > runs/_addr_test_judge_sonnet_seen.log 2>&1
wait
python methods/judge.py --judge claude:claude-sonnet-5-5 --outdir runs/judged_sonnet_block --block --workers 8 --data $(echo $NEW | tr ' ' ',') > runs/_addr_test_judge_sonnet_all.log 2>&1
echo "ADDR_TEST_DONE $(date +%H:%M:%S)"
