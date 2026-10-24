"""Report of the post-hoc baselines (release/ADDED_BASELINES_SETTINGS.md): the same analysis as
methods/agy_replication_report.py (exact McNemar of the reference method against each other method, Holm within
reader and task; continuity on pairs with label errors dropped), with the added methods in the lists.

python methods/added_baselines_report.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agy_replication_report as rep  # noqa: E402

rep.READERS = [("Haiku 4.5", "claude-claude-haiku-4-5-20251001"), ("GPT-6.1-sol", "codex-gpt-6.1-sol")]
ADDED = ["mem-hippo2", "mem-ctxhdr", "mem-s2b"]
rep.TASKS = [("Event-type index, G2 counting, fresh worlds 11-12", ["agg2_s11", "agg2_s12"],
              ["mem-evx4v5", "oracle_para", "mem-cmm4", "mem-pbm25", "hybrid"] + ADDED, False),
             ("State tracking, worlds 7-8, about 0.5M tokens", ["saga_v5_s7", "saga_v5_s8"],
              ["mem-cmm4", "mem-pbm25", "hybrid"] + ADDED, False),
             ("Continuity checking, worlds 7-8 (pairs)", ["cont2_s7", "cont2_s8"],
              ["mem-cmm4", "mem-pbm25", "hybrid"] + ADDED, True)]

if __name__ == "__main__":
    rep.main()
