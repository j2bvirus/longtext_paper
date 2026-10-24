# Release: data, code and stored outputs of "Entity and Event Indexes for State, Continuity and Counting Questions over Verbatim Million-Token Records"

Paths are relative to the root of the release. The manuscript and the
supplementary material are paper/manuscript_final_en.md and paper/supplement_final_en.md.

## What is here

| File or folder | What it is |
|---|---|
| `bench/` | Generators of LongState-Saga, -Continuity, -Aggregate and -Code, and the scripts that prepare the third-party data |
| `data/` | The generated records, questions, gold answers and gold evidence of every world used in the paper; the memory build caches that the report scripts read (caches of earlier method versions are not included); Oolong episode tables and gold-answer audits that we made from third-party data (no source text) |
| `methods/` | Methods, baselines, the evaluation runner, the judge and every report script |
| `runs/results/`, `runs/results_oolong/`, `runs/judged_*/`, `gemini_api/`, `gemini_web/` | Stored model outputs and judge verdicts. In the result files of third-party benchmarks the question and gold-answer fields are empty, and passages of the model reasoning that repeat the source data word for word (runs of 20 words or more, or the item's question) were replaced by `[source text removed]` or `[question removed]`. The final answers (`pred`, the text after the last `Answer:`, and in Oolong replies everything from the first boxed answer on; Oolong replies without a boxed answer are not screened) are kept as produced, apart from the replaced user-folder names, because the stored verdicts and scores refer to them. Non-answer reasoning that repeats the reader client's execution environment (its instruction lines or its temporary scratchpad path) was replaced by `[execution-environment text removed]`; see `RELEASE_NOTES.md`. |
| `runs/llm_cache/` | Cached model responses that the fact-survival analysis replays (compaction steps of worlds T1-T2) and the query-time cache entries the reports read |
| `paper/` | Manuscript, supplement, the table files the replay checks against, and the figures |
| `release/reproduce_tables.py` | Replays the 39 reported tables and analyses and the 3 figures from the stored outputs, with Claude and GPT calls blocked (it sets `runs/NO_CLAUDE` and `runs/NO_GPT` while it runs; only report scripts are run). Each output must exit 0, be non-empty and occur as one contiguous block in its table file (so a changed number, label or row fails); figures are rebuilt elsewhere and compared with paper/figures (CSV text, PNG sha256). The run exits 1 if any check fails. |
| `release/REPRODUCE_REPORT.md` | The replay of this release (run in a copy of it after the third-party data were prepared and the fields restored): per output, the main-text and supplementary sections it covers, the command, the table file, PASS or FAIL, and the sha256 of the output. Tables of the manuscript not listed there are not covered. |
| `release/reproduced/` | The replayed outputs. |
| `release/STORED_OUTPUTS_SHA256.txt`, `release/CURRENT_FILES_SHA256.txt` | sha256 of the inputs the replay reads (after preparation and restoring) and of the code it runs, written by that replay. |
| `release/RELEASE_FILES_SHA256.txt` | sha256 of every file of this release as published (before preparation). |
| `release/THIRD_PARTY_DATA.md` | Where to get Oolong-real, AMA-Bench, NovelHopQA, LoCoMo and the Gutenberg texts, and how to prepare them. |
| `release/restore_third_party_fields.py`, `release/STRIPPED_FILES.tsv` | Puts the removed question and gold-answer fields back from the prepared data and checks each file against the sha256 recorded when the release was made. |
| `release/EXPERIMENT_REGISTRY_PUBLIC.md`, `release/make_public_registry.py` | One row per answer file of this release (3,041 files, 149 data sets): length, method, reader, budget, tag, number of answers, judge files; generated from the files themselves. |
| `release/requirements_replay.txt` | The Python packages and versions of the replay. |
| `release/ADDED_BASELINES_SETTINGS.md` | The settings of the post-hoc baselines. |
| `RELEASE_NOTES.md` | Every change made when this copy was made from the working tree. |
| `README.md`, `LICENSE`, `.gitattributes` | Front page; licence (code MIT, data and outputs CC BY 4.0, with exceptions); git setting that stores every file byte for byte, so the hash lists hold for every clone. |

## Replaying the tables

1. Install the packages of `release/requirements_replay.txt` and prepare the third-party data as
   `release/THIRD_PARTY_DATA.md` describes. No model client or model access is needed for the steps below.
2. `python release/restore_third_party_fields.py` (every restored file must match the sha256 in
   `release/STRIPPED_FILES.tsv`).
3. `python release/reproduce_tables.py` (no model calls; rewrites `release/REPRODUCE_REPORT.md` and the two hash
   lists of the replay).

## Re-running one condition

The replay recomputes tables from the stored outputs. Running a condition again calls the models and gives new
outputs of the same method, not the stored ones (see the last section), so the numbers can differ.

**Before a run**

- Model clients, as `methods/llm.py` calls them: `claude:` and `claudethink<budget>:` the Claude Code command-line
  client, signed in (`claude_exe()`); `codex:` the Codex command-line client (`codex_exe()`); `agy:` the Antigravity
  command-line client (`AGY_EXE`); `ollama:` and `ollamathink:` a local Ollama server (`OLLAMA_URL`, default
  http://127.0.0.1:11434) with the model pulled. The lookup paths are those of the authors' Windows machine; change
  them in `methods/llm.py` for another set-up.
- Delete `runs/NO_CLAUDE`, `runs/NO_GPT` and `runs/NO_AGY` if they exist; while one exists, calls to that client fail.
- Prepare the third-party data first (`release/THIRD_PARTY_DATA.md`).
- Dense retrieval, hybrid RAG and the memory methods that fill their budget by hybrid retrieval (CMM among them)
  need embeddings (Ollama, `qwen3-embedding:0.6b`); a missing embedding file is computed on first use, or beforehand
  with
  `python methods/precompute_embeddings.py <data set> <length> [<length> ...]` and
  `python methods/precompute_qemb.py <data set>`. The post-hoc baselines (`mem:hippo2`, `mem:ctxhdr`, `mem:s2b`) read
  indexes built by `methods/build_added.py` (settings in `release/ADDED_BASELINES_SETTINGS.md`).
- Each runner appends to its result file and skips the questions already in it. Give a new tag (`--tag _rerun1`) or
  move the stored file away. Model responses are cached in `runs/llm_cache/` by prompt; a repeated prompt returns
  the stored response, marked `"cached": true`. To force new calls, rename that folder, and put it back before
  replaying the tables.
- Memories are cached in `data/<data set>/` under names that include the builder (for example
  `cmm_write_d16_claude-claude-haiku-4-5-20251001.json`). `--wait_only` uses these and never builds. Without it a
  missing memory is built by `--builder`. To build a memory again, move its files away and leave out `--wait_only`.
  The registry does not record the builder. It is Claude Haiku 4.5 (`--builder claude:claude-haiku-4-5-20251001`)
  except where the tag or the supplement says otherwise (tags `built-gpt` and `built-q14`; Supplementary Sections
  6.7, 6.10 and B.7). The script's own default builder is a local model, so always pass `--builder`.

**From a registry row to a command.** A row of `release/EXPERIMENT_REGISTRY_PUBLIC.md` stands for the file
`runs/results/<data set>_<length>_<method>_<reader>_b<budget><tag>.jsonl`, written by `methods/run_eval.py` unless
the list after the table names another script. In file names `:` became `-`; put it back:

| Registry | `run_eval.py` option | Example |
|---|---|---|
| section heading (data set) | `--data` | `saga_v5_s7` |
| length | `--density` | `d16` |
| method | `--method`; `mem-<name>` becomes `mem:<name>`, the others stay | `mem-cmm4` → `mem:cmm4`; `hybrid` |
| reader | `--reader`; the first `-` becomes `:`, and for Ollama also the first `-` of the model name | `claude-claude-haiku-4-5-20251001` → `claude:claude-haiku-4-5-20251001`; `codex-gpt-6.1-sol` → `codex:gpt-6.1-sol`; `agy-gemini-4-argon-low` → `agy:gemini-4-argon-low`; `claudethink8000-claude-haiku-4-5-20251001` → `claudethink8000:claude-haiku-4-5-20251001`; `ollama-qwen3-14b` → `ollama:qwen3:14b`; `ollamathink-qwen3-14b-q8_0` → `ollamathink:qwen3:14b-q8_0` |
| budget | `--budget` | `4000` |
| tag `p-<name>` | `--prompt <name>` | `p-minimal` → `--prompt minimal` |
| tag `escU<k>` | `--escalate_unknown <k>` | `escU3` → `--escalate_unknown 3` |
| tag `qboth` | `--qboth` | |
| tag `abl-<a>+<b>` | `--cmm_abl <a>,<b>` | `abl-anchor+rlines` → `--cmm_abl anchor,rlines` |
| tag `built-gpt`, `built-q14` | `--builder codex:gpt-6.1-sol --tag _built-gpt`, `--builder ollama:qwen3:14b --tag _built-q14` | |
| other tags | `--tag _<tag>` | `dev…` are development versions of the event index whose code was revised later, so a re-run uses the current code. `s100` is a sample of 100 questions: write the `qid`s of the stored file to a file and pass it with `--sample`. |

The run prints its accuracy and writes `runs/results/<name>.summary.json`. For the synthetic tasks this is the
score. Free-form answers are scored by the judge afterwards (next list).

Other scripts:

- Free-form answers: `python methods/judge.py --data <data set> --judge codex:gpt-6.1-sol --outdir runs/judged_gpt`
  (novels, LoCoMo, the AMA-Bench trajectories of the main study), and the same with `--block --outdir
  runs/judged_gpt_block` for the AMA-Bench trajectories of Supplementary Appendix C. Verdicts are written per result
  file of the data set.
- Oolong-real (`runs/results_oolong/<split>_<method>_<reader><tag>.jsonl`; registry sections `test` and
  `validation`): `python methods/oolong_eval.py --split test --method index|full|bm25|closed --reader <reader>
  --per_window 20`; tag `bSonnet` is `--builder claude:claude-sonnet-5-5 --tag _bSonnet`.
- Method `agrep` (agentic search): `python methods/agentic_eval.py --data <data set> --reader <reader>`.
- Method `ccagent` (Claude Code agent): `python methods/cc_agent_eval.py --data <data set> --model
  claude-haiku-4-5-20251001`. These two scripts have no tag option, so move the stored file away first.
- `runs/addr_test_pipeline.sh` and the other shell files in `runs/` document the command sequences of some studies as they were run (with their method-selection input `runs/addr_choice.txt` and build scripts); they are a record, not standalone rerun scripts. To run a condition, use the per-condition commands above.

Example, from the release root (one cell of LongState-Saga, CMM v4 with the Haiku reader at the 0.5M-token length):

```
python methods/run_eval.py --data saga_v5_s7 --density d16 --method mem:cmm4 \
  --reader claude:claude-haiku-4-5-20251001 --builder claude:claude-haiku-4-5-20251001 --wait_only \
  --budget 4000 --workers 6 --tag _rerun1
```

This writes `runs/results/saga_v5_s7_d16_mem-cmm4_claude-claude-haiku-4-5-20251001_b4000_rerun1.jsonl`, next to the
stored `..._b4000.jsonl`. For a NovelHopQA book, judged by GPT (`--only <method><tag>@<reader prefix>` limits the
judging to the new file):

```
python methods/run_eval.py --data nhq_emma --density full --method hybrid --reader codex:gpt-6.1-sol \
  --budget 4000 --workers 6 --tag _rerun1
python methods/judge.py --data nhq_emma --judge codex:gpt-6.1-sol --outdir runs/judged_gpt --only hybrid_rerun1@codex
```

## Scoring and denominators

- Synthetic tasks (state, continuity, counting, code): deterministic scoring against `data/*/questions_GOLD.jsonl`; excluded questions are marked in those files; continuity label errors are dropped by `methods/continuity_stats.py` / `bench/check_continuity_labels.py`.
- Free-form answers (novels, agent trajectories, chat): GPT-6.1 Sol judge verdicts in `runs/judged_gpt*/`; the judge prompt is in `methods/judge.py`.
- Oolong-real: the authors' scoring rule re-implemented in `methods/oolong_score.py` (behaviour of their commit 0bb7eab); every Oolong table is rescored from the stored replies.
- Each report script prints its own denominators (n per cell).

## What is not included and what cannot be replayed

- Paragraph and question embeddings (about 620 MB) are not included; `methods/precompute_embeddings.py` and `methods/precompute_qemb.py` recompute them.
- The exact reading context of past runs was not stored, and CMM's packing order depends on Python's set order for ties, so re-running a condition reproduces the method, not the identical inputs. Re-running needs the model clients and is not part of the replay.
