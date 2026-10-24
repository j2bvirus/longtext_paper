#!/bin/bash
# Oracle-certificate control of the event index.
# Question: does the event index beat the gold evidence paragraphs on G2 counting only because it states that its set
# is complete and that a zero means none?  Control: the gold evidence paragraphs WITH the existing completeness
# statement (method oracle_para_cert, methods/run_eval.py: "[Memory guarantee: the paragraphs below are ALL passages of
# the record that are relevant to the question. Anything not shown here did not happen.]"; for a gold count of zero the
# context is that statement alone).  Data: fresh worlds agg2_s11, agg2_s12 (75 questions), d16, budget 4k, same reader
# prompt as every G2 run.  Readers: Haiku 4.5 and GPT-6.1-sol (the two primary readers); Gemini 4 Argon and GPT-OSS
# 120B through agy (secondary).
# Primary analysis: per reader, event index v5 (mem-evx4v5, existing runs) vs oracle_para_cert, exact McNemar,
# Holm over the two primary readers.  Secondary: the same split by gold = 0 / gold > 0, and oracle_para_cert vs
# oracle_para (the effect of the statement itself).  Report whatever comes out; no other condition is changed.
cd "$(dirname "$0")/.."  # release root
export PATH=/usr/bin:/mingw64/bin:$PATH
export PYTHONIOENCODING=utf-8
export PYTHONHASHSEED=0
H=claude:claude-haiku-4-5-20251001
for R in $H codex:gpt-6.1-sol; do
  for ds in agg2_s11 agg2_s12; do
    python methods/run_eval.py --data $ds --density d16 --method oracle_para_cert --reader $R --workers 4 > /dev/null 2>&1
    echo "$ds oracle_para_cert $R exit $? $(date +%H:%M:%S)"
  done
done
echo "G2_ORACLE_CERT_PRIMARY_DONE $(date +%H:%M:%S)"
for R in agy:gemini-4-argon-low agy:gpt-oss-120b-medium; do
  for ds in agg2_s11 agg2_s12; do
    timeout 3600 python methods/run_eval.py --data $ds --density d16 --method oracle_para_cert --reader $R --workers 2 > /dev/null 2>&1
    echo "$ds oracle_para_cert $R exit $? $(date +%H:%M:%S)"
  done
done
echo "G2_ORACLE_CERT_ALL_DONE $(date +%H:%M:%S)"
