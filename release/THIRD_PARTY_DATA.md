# Third-party data: where to get it and how to prepare it

The four benchmarks below were made by other authors and are not redistributed here. In the released result files of
these benchmarks the question and gold-answer fields are empty and passages of the models' reasoning that repeat the
source data word for word were removed; question identifiers, the final answers and the scores are kept, so the records can be matched to the original questions by identifier after the data below are
prepared. Follow the preparation and version-pinning steps below, then restore the removed fields
(release/restore_third_party_fields.py). In the prepared release copy, all 6,644 files listed in
release/STORED_OUTPUTS_SHA256.txt matched their recorded hashes and all 42 replay checks passed; this list includes the
stored results as well as the prepared data.
See each dataset page for its terms of use.

## Oolong-real (Bertsch et al., 2026)

- Page: https://huggingface.co/datasets/oolongbench/oolong-real
- Files: `dnd/validation.jsonl` and `dnd/test.jsonl`
  (https://huggingface.co/datasets/oolongbench/oolong-real/resolve/main/dnd/test.jsonl, and the same path with
  `validation`)
- Prepare: `python bench/oolong_prepare.py test` and `python bench/oolong_prepare.py validation` download the files
  themselves and write `data/_external/oolong_real/<split>/` (one text per context window, the questions, the window
  list).
- Matching: result records carry the question `id` and the context `window` of the dataset.

## AMA-Bench (Zhao et al., 2026)

- Page: https://huggingface.co/datasets/AMA-bench/AMA-bench
- Dataset, revision used: https://huggingface.co/datasets/AMA-bench/AMA-bench/tree/a5777378066f53229a94557a7b192435cd027909
- File: `test/open_end_qa_set.jsonl` (SHA-256 45c36052e1520d87ad9de4114f71c9df42d4aac9cf158c0c353e800b653d65ff)
- Prepare: `python bench/ama_prepare.py <path to open_end_qa_set.jsonl>` (copies the file to
  `data/_external/ama_bench/` and renders the 26 trajectories of the main study), then `python bench/ama_prepare_more.py`
  and `python bench/ama_prepare_fresh.py` for the trajectories of Supplementary Appendix C. The selection rules are in
  the docstrings of these scripts.
- Matching: one data directory per trajectory (`data/ama_<group><nn>`, with the trajectory's `episode_id` in its
  `world_GOLD.json`); `Q<n>` is the n-th entry (from 0) of the trajectory's `qa_pairs`.

## NovelHopQA (Gupta et al., 2025) and the Project Gutenberg texts

- Dataset, pinned revision: https://huggingface.co/datasets/abhaygupta1266/novelhopqa/tree/c642bf8ab04edcc23441b179799a0984a8a49eee
- Files: `data/hop_1-*.parquet` to `data/hop_4-*.parquet` of that revision
- Novels (full text in UTF-8 from each book page): Project Gutenberg
  https://www.gutenberg.org/ebooks/<id> for the ids below.
- Layout: put the four parquet files in `<dir>/DATA_NOVELHOPQA_HF_PINNED/` and each novel as
  `<dir>/PG<id>/original.txt`, then run `python bench/gutenberg_pin.py <dir>`, then
  `NHQ_SRC=<dir> python bench/novelhop_prepare.py` (development books A), `--test` (books B) and `--test2` (books C,
  the unseen books of the main paper).
- The prepared record is the Gutenberg body between the START and END markers. Gutenberg files are occasionally
  updated; the SHA-256 of the body we used is given so that the same version can be checked. A later download
  matched for eight books; Moby Dick (stage directions now in parentheses, one epigraph laid out line by
  line; 9 places) and Sense and Sensibility (two commas removed) had changed. `bench/gutenberg_pin.py` turns those
  two texts back into the versions we used (the edits are in `bench/gutenberg_versions.json`) and checks the hash; a
  text in any other version is reported and left unchanged.

| Key | Book | Gutenberg id | Group | SHA-256 of the body |
|---|---|---|---|---|
| anna | Anna Karenina | 1399 | A (development) | efd89b9c54b82d56f88faf33ff09de3c016307aa2dca3476b57be42a47384fa2 |
| dracula | Dracula | 345 | A | 03d79f9803e7ad67cecfd6d0951d8cf4cb64944ce19ecf5a0c305ace5705aaaf |
| moby | Moby Dick | 2701 | A | 556dbd579bb3c187e61681f20004f8ec9a30fd36c5375f2ee04fa362af09ab85 |
| great | Great Expectations | 1400 | A | c6196113039a054e075999518fd4f081838335b58cc0371f04b99080de03e7fe |
| mid | Middlemarch | 145 | B | 9d0ce5c0b701c05b38198f6fab45b8ebf2eb3645a81aa55794ccd0aa66cdaf0d |
| karam | The Brothers Karamazov | 28054 | B | 3c8dd95a93f7bd34e4f0a000d3da96a5e9f369d200bc109f2b6177387db836a2 |
| pride | Pride and Prejudice | 1342 | B | 870cdcf3be55d66cc4b20816d8c7ed81ef55727b67299ef373b71e40a364aac4 |
| emma | Emma | 158 | C (unseen, main paper) | d0153981996f9dae46463d63110cbf9937ce92f7835a21434c8bd11b9444fe3e |
| wuther | Wuthering Heights | 768 | C | d23b4feab29dcfa7411bbb8041e825dd48e3e1c1721c61c392ccfb46968fd6fd |
| sense | Sense and Sensibility | 161 | C | 32f74fa37f9cc801f44783663a2391797b0e7ff0e496d86d1cdd7a95ff1cc89d |

- Matching: questions are numbered `Q<row>` in the order of the dataset rows of that book.

## LoCoMo (Maharana et al., 2024)

- Repository: https://github.com/snap-research/locomo
- File: `data/locomo10.json` (https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json)
- Prepare: put the file at `data/sources_extra/LOCOMO/locomo10.json` and run `python bench/locomo_prepare.py`
  (writes `data/locomo_0` to `data/locomo_9`, one per conversation).
- Matching: `Q<n>` is the n-th entry (from 0) of the conversation's `qa` list; only the questions selected by the
  script are kept.
