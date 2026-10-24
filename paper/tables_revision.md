# Analyses added in the final revision (outputs of the scripts named in each heading)

Written from the stored outputs, with model calls blocked. release/reproduce_tables.py reruns each command and checks that its output occurs unchanged below.

## revision_length: accuracy across length on the same questions (Fig. 1)

`python methods/revision_analyses.py length`

```
Accuracy % across record length; each row uses the same questions at every length (n), the same method version and the same reader. Change = last length minus first.

Worlds D2-D3; record length d1 0.04M, d16 0.49M, d64 1.96M
| Reader | Method | n | d1 | d16 | d64 | Change |
|---|---|---|---|---|---|---|
| Haiku 4.5 | CMM v2 + cards | 440 | 96.8 | 93.0 | 90.5 | -6.4 |
| Haiku 4.5 | Paragraph BM25 | 440 | 95.9 | 89.5 | 85.5 | -10.5 |
| Haiku 4.5 | NameGrep+co | 440 | 95.5 | 93.4 | 85.0 | -10.5 |
| Haiku 4.5 | Hybrid retrieval | 440 | 83.6 | 77.7 | 67.5 | -16.1 |
| Haiku 4.5 | Chunk BM25 | 440 | 80.5 | 73.4 | 61.6 | -18.9 |
| Qwen3-14B | Paragraph BM25 | 440 | 67.5 | 68.0 | 63.9 | -3.6 |
| Qwen3-14B | NameGrep+co | 440 | 70.9 | 66.1 | 63.4 | -7.5 |
| Qwen3-14B | Hybrid retrieval | 440 | 66.6 | 63.0 | 58.0 | -8.6 |
| Qwen3-14B | Chunk BM25 | 440 | 65.9 | 60.0 | 52.0 | -13.9 |
| Qwen3-8B | Paragraph BM25 | 440 | 59.1 | 57.5 | 57.0 | -2.0 |
| Qwen3-8B | NameGrep+co | 440 | 62.5 | 58.9 | 58.9 | -3.6 |
| Qwen3-8B | Hybrid retrieval | 440 | 62.0 | 59.8 | 53.6 | -8.4 |
| Qwen3-8B | Chunk BM25 | 440 | 61.6 | 53.4 | 46.6 | -15.0 |

Worlds T1-T2; record length d16 0.49M, d64 1.91M
| Reader | Method | n | d16 | d64 | Change |
|---|---|---|---|---|---|
| Haiku 4.5 | CMM v4-adaptive | 459 | 95.2 | 92.4 | -2.8 |
| Haiku 4.5 | CMM v4 | 459 | 94.3 | 89.3 | -5.0 |
| Haiku 4.5 | Paragraph BM25 | 459 | 88.2 | 86.1 | -2.2 |
| Haiku 4.5 | NameGrep+co | 459 | 92.4 | 86.9 | -5.4 |
| Haiku 4.5 | Hybrid retrieval | 459 | 77.1 | 72.8 | -4.4 |
| GPT-6.1 Sol | CMM v4-adaptive | 459 | 96.9 | 95.0 | -2.0 |
| GPT-6.1 Sol | CMM v4 | 459 | 96.7 | 93.2 | -3.5 |
| GPT-6.1 Sol | Paragraph BM25 | 459 | 90.6 | 89.1 | -1.5 |
| GPT-6.1 Sol | NameGrep+co | 459 | 96.3 | 89.8 | -6.5 |
| GPT-6.1 Sol | Hybrid retrieval | 459 | 82.6 | 75.4 | -7.2 |
```

## revision_clusters: state tracking: intervals over clusters of questions sharing gold evidence

`python methods/revision_analyses.py clusters`

```
CMM v4 minus another method on worlds T1-T2 (459 questions, 0.5M, 4k budget), accuracy points, with 95% intervals from a bootstrap over clusters (20,000 resamples, seed 0). Clusters: each question alone; questions that share any core gold evidence event; questions that share any gold evidence event (evidence closed over the references needed to interpret it), linked transitively within a world.
Clusters: 459 questions; core evidence 193 clusters (largest 102); all evidence 121 clusters (largest 170).

| Reader | Comparison | Difference | Per question | Core-evidence clusters | All-evidence clusters |
|---|---|---|---|---|---|
| Haiku 4.5 | CMM v4 − Paragraph BM25 | +6.1 | [+3.3, +9.2] | [+0.4, +9.2] | [-1.5, +9.5] |
| Haiku 4.5 | CMM v4 − Hybrid retrieval | +17.2 | [+13.3, +21.1] | [+11.9, +20.4] | [+6.7, +20.0] |
| GPT-6.1 Sol | CMM v4 − Paragraph BM25 | +6.1 | [+3.7, +8.5] | [+0.8, +9.2] | [+0.0, +8.3] |
| GPT-6.1 Sol | CMM v4 − Hybrid retrieval | +14.2 | [+10.9, +17.4] | [+9.5, +17.2] | [+4.3, +17.1] |
| Gemini 4 Argon | CMM v4 − Paragraph BM25 | +5.9 | [+3.7, +8.3] | [+0.8, +8.5] | [+0.0, +7.9] |
| Gemini 4 Argon | CMM v4 − Hybrid retrieval | +16.3 | [+13.1, +19.8] | [+12.1, +19.2] | [+5.0, +19.1] |
| gpt-oss-120b | CMM v4 − Paragraph BM25 | +9.2 | [+6.1, +12.4] | [+4.4, +12.1] | [+3.5, +12.2] |
| gpt-oss-120b | CMM v4 − Hybrid retrieval | +15.7 | [+12.0, +19.6] | [+10.9, +18.7] | [+6.9, +18.0] |
```

## revision_oolong: Oolong-real: index minus BM25 by answer type

`python methods/revision_analyses.py oolong`

```
Oolong-real test: index minus BM25 (official score), split by the type of the gold answer. Contribution = sum of the per-question differences of that type divided by all questions of the set, so the rows add up to the total difference. For numbers, the exact part counts answers equal to the gold and the partial part the rest of the 0.75^|error| credit. For lists, the official score is the number of distinct items shared by the gold and predicted lists divided by the length of the gold list: order and extra predicted items are not penalized, and a gold list with repeated items cannot reach 1.0 even when predicted exactly.

Haiku 4.5 reader, all windows (2200 questions: 1378 number, 437 string, 385 list); total +0.220
| Answer type | Contribution | Share of the total | Official score 1.0: index / BM25 |
|---|---|---|---|
| string | +0.100 | 46% | 241 / 20 |
| number, exact | +0.004 | 2% | 188 / 180 |
| number, partial credit | +0.075 | 34% | – |
| list | +0.041 | 19% | 19 / 1 |

Haiku 4.5 reader, 16- and 24-episode windows (400 questions: 253 number, 81 string, 66 list); total +0.204
| Answer type | Contribution | Share of the total | Official score 1.0: index / BM25 |
|---|---|---|---|
| string | +0.115 | 56% | 48 / 2 |
| number, exact | +0.000 | 0% | 28 / 28 |
| number, partial credit | +0.060 | 30% | – |
| list | +0.028 | 14% | 0 / 0 |

GPT-6.1 Sol reader, all windows (2200 questions: 1378 number, 437 string, 385 list); total +0.205
| Answer type | Contribution | Share of the total | Official score 1.0: index / BM25 |
|---|---|---|---|
| string | +0.090 | 44% | 230 / 31 |
| number, exact | +0.003 | 2% | 191 / 184 |
| number, partial credit | +0.070 | 34% | – |
| list | +0.041 | 20% | 20 / 1 |

GPT-6.1 Sol reader, 16- and 24-episode windows (400 questions: 253 number, 81 string, 66 list); total +0.178
| Answer type | Contribution | Share of the total | Official score 1.0: index / BM25 |
|---|---|---|---|
| string | +0.113 | 63% | 48 / 3 |
| number, exact | +0.000 | 0% | 29 / 29 |
| number, partial credit | +0.039 | 22% | – |
| list | +0.027 | 15% | 0 / 0 |
```

## revision_full44k: full-context reading at 44k on the same questions

`python methods/revision_analyses.py full44k`

```
Full-context reading at 44k (worlds D2-D3, Haiku, the questions it was run on) against the memories on the same 201 questions; exact McNemar, Holm over the four comparisons.

| Method | Accuracy % (same questions) | Full context | w/l against full context | p | Holm p |
|---|---|---|---|---|---|
| Paragraph BM25 | 95.0 | 92.0 | 12/6 | 0.238 | 0.476 |
| CMM v1 | 95.5 | 92.0 | 12/5 | 0.143 | 0.430 |
| CMM v1 + cards | 96.5 | 92.0 | 13/4 | 0.049 | 0.196 |
| NameGrep+co | 94.0 | 92.0 | 9/5 | 0.424 | 0.476 |
```

## revision_added18: Main 7.1 Table 6: Holm over the 18 post-hoc comparisons

`python methods/revision_analyses.py added18`

```
Post-hoc baselines (main text, Table 6): exact two-sided McNemar on the win/loss counts of paper/tables_added_baselines.md, Holm over all 18 comparisons (3 baselines x 3 tasks x 2 readers).
| Task | Reader | Baseline | w/l | p | Holm p (18) |
|---|---|---|---|---|---|
| Event-type index | Haiku 4.5 | hippo2 | 20/5 | 0.0041 | 0.0082 |
| Event-type index | Haiku 4.5 | ctxhdr | 35/0 | 5.8e-11 | 7e-10 |
| Event-type index | Haiku 4.5 | s2b | 39/1 | 7.5e-11 | 7.5e-10 |
| Event-type index | GPT-6.1-sol | hippo2 | 18/6 | 0.023 | 0.023 |
| Event-type index | GPT-6.1-sol | ctxhdr | 36/2 | 5.4e-09 | 4.3e-08 |
| Event-type index | GPT-6.1-sol | s2b | 35/0 | 5.8e-11 | 7e-10 |
| State tracking | Haiku 4.5 | hippo2 | 36/10 | 0.00016 | 0.00078 |
| State tracking | Haiku 4.5 | ctxhdr | 82/7 | 2.4e-17 | 3.4e-16 |
| State tracking | Haiku 4.5 | s2b | 92/7 | 5.1e-20 | 8.6e-19 |
| State tracking | GPT-6.1-sol | hippo2 | 24/4 | 0.00018 | 0.00078 |
| State tracking | GPT-6.1-sol | ctxhdr | 73/2 | 1.5e-19 | 2.4e-18 |
| State tracking | GPT-6.1-sol | s2b | 83/1 | 8.8e-24 | 1.6e-22 |
| Continuity checking | Haiku 4.5 | hippo2 | 39/12 | 0.0002 | 0.00078 |
| Continuity checking | Haiku 4.5 | ctxhdr | 51/8 | 9.1e-09 | 6.3e-08 |
| Continuity checking | Haiku 4.5 | s2b | 53/6 | 1.8e-10 | 1.6e-09 |
| Continuity checking | GPT-6.1-sol | hippo2 | 26/1 | 4.2e-07 | 2.5e-06 |
| Continuity checking | GPT-6.1-sol | ctxhdr | 55/0 | 5.6e-17 | 7.2e-16 |
| Continuity checking | GPT-6.1-sol | s2b | 65/1 | 1.8e-18 | 2.7e-17 |
```
