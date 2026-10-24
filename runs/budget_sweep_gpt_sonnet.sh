#!/bin/bash
# Budget sweep with two more readers. State tracking on the held-out
# worlds T1-T2 (saga_v5_s7, saga_v5_s8, density d16, 459 questions), the three methods of the Haiku sweep without cards
# (CMM v4, paragraph BM25, hybrid retrieval), the default reader prompt, memories built by Claude Haiku 4.5 and read from
# the caches (--wait_only), dense embeddings from the stored caches (no GPU).
#   GPT-6.1 Sol: Codex command-line client, reasoning effort low (methods/llm.py), budgets 2k, 8k, 16k (4k exists).
#   Claude Sonnet 5.5: Claude Code command-line client, effort high (client settings); the model's thinking is adaptive
#   and set by the effort level; prompt caching off (methods/llm.py); budgets 2k, 4k, 8k, 16k (not used as a reader before).
# Stage "pilot" answers the first questions of world T1 only; "full" completes every condition
# (run_eval skips the questions already answered, so the pilot answers are kept and not asked again). An optional third
# argument limits the budgets of this call (e.g. "2000"), so that the runs can be done in steps; it changes nothing else.
#
# bash runs/budget_sweep_gpt_sonnet.sh pilot|full gpt|sonnet|both ["2000 4000 ..."]
cd "$(dirname "$0")/.." || exit 1
STAGE=$1; WHO=${2:-both}; ONLY=$3
H=claude:claude-haiku-4-5-20251001
run() {  # reader budget workers limit
  for ds in saga_v5_s7 saga_v5_s8; do
    [ "$STAGE" = pilot ] && [ "$ds" = saga_v5_s8 ] && continue
    for m in mem:cmm4 mem:pbm25 hybrid; do
      python methods/run_eval.py --data $ds --density d16 --method $m --reader "$1" --builder $H --wait_only \
        --budget $2 --workers $3 $4 > /dev/null 2>> runs/_budget_sweep_errors.log || echo "FAILED $ds $m $1 $2"
    done
  done
}
pick() { [ -z "$ONLY" ] && echo "$1" || for b in $1; do case " $ONLY " in *" $b "*) echo $b;; esac; done; }
if [ "$WHO" = gpt ] || [ "$WHO" = both ]; then
  for b in $(pick "2000 8000 16000"); do run codex:gpt-6.1-sol $b 8 "$([ "$STAGE" = pilot ] && echo --limit 10)"; done &
fi
if [ "$WHO" = sonnet ] || [ "$WHO" = both ]; then
  for b in $(pick "2000 4000 8000 16000"); do run claude:claude-sonnet-5-5 $b 6 "$([ "$STAGE" = pilot ] && echo --limit 5)"; done &
fi
wait
echo "SWEEP_${STAGE}_DONE"
