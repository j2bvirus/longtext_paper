# Changes made when this release was copied from the working tree

- `runs/addr_dev_b.sh`: local 'cd' line replaced by a 'cd' to the release root
- `runs/addr_fresh_test_pipeline.sh`: local 'cd' line replaced by a 'cd' to the release root
- `runs/addr_test_pipeline.sh`: local 'cd' line replaced by a 'cd' to the release root
- `runs/ama_more_cmm_build.sh`: local 'cd' line replaced by a 'cd' to the release root
- `runs/g2_oracle_cert_control.sh`: local 'cd' line replaced by a 'cd' to the release root
- 752 files of the model-call cache (runs/llm_cache/): the time of the call removed
- 11 passages of non-answer reasoning in third-party result files that repeat the reader client's execution environment (its instruction lines or its temporary scratchpad path) replaced by [execution-environment text removed]; final answers used for scoring are unchanged
- 5 files: local user folder, a user folder of another machine or an account e-mail address replaced: `runs/results/ama_g06_full_mem-compact16k_claude-claude-haiku-4-5-20251001_b4000_p-minimal.jsonl`, `runs/results/ama_gs12_full_mem-addr2_claude-claude-haiku-4-5-20251001_b4000_p-minimal.jsonl`, `runs/results/ama_gs15_full_full_claude-claude-haiku-4-5-20251001_b4000_p-minimal.jsonl`, `runs/results/ama_sp23_full_mem-cmm4_claude-claude-haiku-4-5-20251001_b4000_p-minimal.jsonl`, `runs/results/ama_ws08_full_agrep_claude-claude-haiku-4-5-20251001_b4000_p-minimal.jsonl`
- 1957 result files of third-party benchmarks: the reasoning before each final answer was screened for passages that repeat the source data (3297 passages of at least 20 words or repeated questions replaced, in 786 files); the final answers are kept as produced because the stored verdicts and scores refer to them (224 of them repeat at least 20 words of the source); then question and gold-answer text set to null (release/STRIPPED_FILES.tsv; release/restore_third_party_fields.py puts the fields back)
- `release/REPRODUCE_REPORT.md`, `release/CURRENT_FILES_SHA256.txt`, `release/STORED_OUTPUTS_SHA256.txt` and `release/reproduced/` come from the replay of a copy of this release after the third-party data were prepared and the fields restored (42 checks passed); `release/RELEASE_FILES_SHA256.txt` lists every file of the release as published
