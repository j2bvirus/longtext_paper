#!/bin/bash
# Address index, validation round B:
# ALFWorld ama_af11-30 and WebArena ama_wa11-31 (41 trajectories, 492 questions), Haiku 4.5 reader, minimal prompt,
# budget 4k.  Purpose: choose between the two tied development candidates addr (v1) and addr2 by pooled accuracy
# (Sonnet 5.5 judge, whole answer), and check that the dev-round ordering against the baselines holds.  The chosen
# version is then frozen for the test on SWE-bench and GAIA.  Rule: addr2 is chosen if its pooled accuracy is at
# least that of v1, otherwise v1.
cd "$(dirname "$0")/.."  # release root
export PYTHONIOENCODING=utf-8
export PYTHONHASHSEED=0
H=claude:claude-haiku-4-5-20251001
DS="$(ls data | grep -E '^ama_af(1[1-9]|2[0-9]|30)$|^ama_wa(1[1-9]|2[0-9]|3[01])$' | tr '\n' ' ')"
for m in mem:addr mem:addr2 mem:addr_steponly mem:pbm25 hybrid full; do
  for ds in $DS; do
    python methods/run_eval.py --data $ds --density full --method $m --reader $H --prompt minimal --workers 6 > /dev/null 2>&1
    echo "$ds $m exit $? $(date +%H:%M:%S)"
  done
done
for ds in $DS; do
  python methods/agentic_eval.py --data $ds --reader $H --workers 6 > /dev/null 2>&1
  echo "$ds agrep exit $? $(date +%H:%M:%S)"
done
python methods/judge.py --judge claude:claude-sonnet-5-5 --outdir runs/judged_sonnet_block --block --workers 8 --data $(echo $DS | tr ' ' ',') > runs/_addr_dev_b_judge_sonnet.log 2>&1
echo "ADDR_DEV_B_DONE $(date +%H:%M:%S)"
