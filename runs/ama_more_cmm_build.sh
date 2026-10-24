#!/bin/bash
# CMM v4 memories (Haiku 4.5 builder) of the 40 new AMA-Bench test trajectories (SWE-bench ama_ws, GAIA ama_gs),
# built once; the test runs only read them
cd "$(dirname "$0")/.."  # release root
export PYTHONIOENCODING=utf-8
export PYTHONHASHSEED=0
for ds in $(ls data | grep -E "^ama_(ws|gs)[0-9]+$"); do
  python methods/build_only.py $ds full cmm4 claude:claude-haiku-4-5-20251001 > runs/_cmm_build_last.log 2>&1
  echo "$ds cmm4 build exit $? $(date +%H:%M:%S)"
done
echo "AMA_MORE_CMM_BUILD_DONE $(date +%H:%M:%S)"
