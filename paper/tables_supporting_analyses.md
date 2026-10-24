# Supporting analyses cited in the supplement (outputs of the scripts named in each heading)

Written from the stored outputs, with model calls blocked. release/reproduce_tables.py reruns each command and checks that its output occurs unchanged below.

## compaction_survival_T1: S6.7 fact survival through compaction, world T1

`python methods/compaction_survival.py saga_v5_s7 d16`

```
saga_v5_s7 d16 compact4k: 270 compactions, 154 span-answer questions; run saga_v5_s7_d16_mem-compact4k_claude-claude-haiku-4-5-20251001_b4000 (deterministic)
  evidence in the raw tail (never compacted): 0
  answer in the summary right after its evidence was compacted: 34.4% of 154
  | compactions survived | n | entered | still in final summary | final given entered | reader acc |
  |---|---|---|---|---|---|
  | 1-4 | 5 | 80% | 0% | 0% | 0% |
  | 5-19 | 15 | 33% | 0% | 0% | 0% |
  | 20-79 | 39 | 18% | 5% | 29% | 0% |
  | 80- | 95 | 39% | 4% | 5% | 0% |
  reader accuracy when answer in final summary or tail: 0.0% (n=6)
  reader accuracy when answer in neither: 0.0% (n=148)
  written runs/compaction_survival_saga_v5_s7_d16_compact4k.json
```

## compaction_survival_T2: S6.7 fact survival through compaction, world T2

`python methods/compaction_survival.py saga_v5_s8 d16`

```
saga_v5_s8 d16 compact4k: 256 compactions, 140 span-answer questions; run saga_v5_s8_d16_mem-compact4k_claude-claude-haiku-4-5-20251001_b4000 (deterministic)
  evidence in the raw tail (never compacted): 2
  answer in the summary right after its evidence was compacted: 58.7% of 138
  | compactions survived | n | entered | still in final summary | final given entered | reader acc |
  |---|---|---|---|---|---|
  | 0-0 | 2 | 100% | 100% | 100% | 100% |
  | 1-4 | 3 | 100% | 100% | 100% | 33% |
  | 5-19 | 17 | 53% | 53% | 100% | 59% |
  | 20-79 | 35 | 57% | 26% | 35% | 11% |
  | 80- | 81 | 58% | 21% | 28% | 4% |
  reader accuracy when answer in final summary or tail: 40.0% (n=40)
  reader accuracy when answer in neither: 5.0% (n=100)
  written runs/compaction_survival_saga_v5_s8_d16_compact4k.json
```

## statement_scope: B.3 misses of the certified block

`python methods/cert_block_misses.py saga_v5_s7:d16:cmm4,saga_v5_s8:d16:cmm4,saga_v5_s4:d16:cmm2,saga_v5_s5:d16:cmm2`

```
saga_v5_s7:d16:cmm4: certified-with-evidence 150; complete 134; misses outside the guarantee 16; true mention misses 0 {}; mention-scope precision 100.0%
saga_v5_s8:d16:cmm4: certified-with-evidence 145; complete 129; misses outside the guarantee 15; true mention misses 1 {'ALIVE': 1}; mention-scope precision 99.3%
saga_v5_s4:d16:cmm2: certified-with-evidence 122; complete 109; misses outside the guarantee 11; true mention misses 2 {'LOC_NOW': 1, 'ALIVE': 1}; mention-scope precision 98.4%
saga_v5_s5:d16:cmm2: certified-with-evidence 161; complete 140; misses outside the guarantee 15; true mention misses 6 {'LOC_NOW': 2, 'LOC_AT_EVENT': 1, 'OCCUPATION_NOW': 3}; mention-scope precision 96.3%
pooled: complete 512/578 = 88.6%; mention-scope precision (only true misses count as failures) 98.4%
```

## statement_precision: B.3 precision on the certified block

`python methods/cert_block_precision.py saga_v5_s7:d16:cmm4,saga_v5_s8:d16:cmm4,saga_v5_s4:d16:cmm2,saga_v5_s5:d16:cmm2`

```
saga_v5_s7:d16:cmm4: n=236 certified=156 (66.1%) [no core evidence 6] block precision=134/150 = 89.3%
saga_v5_s8:d16:cmm4: n=223 certified=154 (69.1%) [no core evidence 9] block precision=129/145 = 89.0%
saga_v5_s4:d16:cmm2: n=226 certified=122 (54.0%) [no core evidence 0] block precision=109/122 = 89.3%
saga_v5_s5:d16:cmm2: n=235 certified=168 (71.5%) [no core evidence 7] block precision=140/161 = 87.0%
pooled block precision 512/578 = 88.6%
```

## statement_effect: B.3 value of the completeness statement

`python methods/statement_effect_ci.py .`

```
continuity Haiku: units 216 J diff (v4 - nocert) +0.5 [-1.9, +2.8]
aggregate A_ Haiku: n 100 acc 78.0 vs 80.0 diff -2.0 [-6.0, +2.0] +1/-3
aggregate G_ Haiku: n 46 acc 37.0 vs 32.6 diff +4.3 [-4.3, +13.0] +3/-1
continuity GPT: units 216 J diff (v4 - nocert) +1.4 [+0.0, +3.2]
aggregate A_ GPT: n 100 acc 84.0 vs 82.0 diff +2.0 [+0.0, +5.0] +2/-0
aggregate G_ GPT: n 46 acc 39.1 vs 41.3 diff -2.2 [-6.5, +0.0] +0/-1
```

## lifecycle_cost_D2_D3: S6.8 and B.1 lifecycle cost and break-even, worlds D2-D3

`python methods/costs.py --data saga_v5_s2,saga_v5_s3`

```
len           method               n    acc %  ctx/q   $read/q  $write  $idle  $cards  $build  Q* vs full
d1 (44k)      bm25                 440  80.5   4,139   0.0056   0.00    0.00   0.00    0.00    0
d1 (44k)      full_s100            201  92.0   46,090  0.0476   0.00    0.00   0.00    0.00    -
d1 (44k)      hybrid               440  83.6   4,142   0.0057   0.00    0.00   0.00    0.00    0
d1 (44k)      mem-cmm              440  96.1   4,027   0.0053   0.17    nan    0.00    nan     n/a
d1 (44k)      mem-cmm2             440  96.1   4,027   0.0053   0.17    nan    0.00    nan     n/a
d1 (44k)      mem-cmm2c            440  96.8   4,032   0.0051   0.17    nan    0.40    nan     n/a
d1 (44k)      mem-cmm_abl-resolve  440  95.7   4,022   0.0053   0.17    nan    0.00    nan     n/a
d1 (44k)      mem-cmmc             440  96.8   4,032   0.0051   0.17    nan    0.40    nan     n/a
d1 (44k)      mem-cmml             440  95.9   1,910   0.0031   0.17    nan    0.00    nan     n/a
d1 (44k)      mem-cmmn             440  95.5   3,982   0.0053   0.17    nan    0.00    nan     n/a
d1 (44k)      mem-namegrep_co      440  95.5   3,980   0.0053   0.00    0.00   0.00    0.00    0
d1 (44k)      mem-pbm25            440  95.9   3,894   0.0053   0.00    0.00   0.00    0.00    0
d1 (44k)      mem-summary          440  26.1   4,038   0.0049   0.89    0.00   0.00    0.89    20.9
d1 (44k)      oracle               440  95.2   623     0.0016   0.00    0.00   0.00    0.00    0
d1 (44k)      oracle_para          440  88.4   122     0.0010   0.00    0.00   0.00    0.00    0
d1 (44k)      oracle_para_cert     440  90.7   151     0.0010   0.00    0.00   0.00    0.00    0
d1 (44k)      oracle_plain         440  92.0   595     0.0015   0.00    0.00   0.00    0.00    0
d16 (494k)    bm25                 440  73.4   4,156   0.0056   0.00    0.00   0.00    0.00    0*
d16 (494k)    hybrid               440  77.7   4,157   0.0056   0.00    0.00   0.00    0.00    0*
d16 (494k)    mem-cmm              440  91.4   4,129   0.0054   1.54    4.15   0.00    5.69    11.6*
d16 (494k)    mem-cmm2             440  94.5   4,132   0.0054   1.54    4.15   0.00    5.69    11.6*
d16 (494k)    mem-cmm2c            440  93.0   4,123   0.0053   1.54    4.15   0.47    6.16    12.6*
d16 (494k)    mem-cmm4             440  95.0   4,098   0.0054   1.54    4.15   0.00    5.69    11.6*
d16 (494k)    mem-cmm_abl-resolve  440  90.9   4,130   0.0054   1.54    4.15   0.00    5.69    11.6*
d16 (494k)    mem-cmmc             440  93.2   4,120   0.0053   1.54    4.15   0.47    6.16    12.6*
d16 (494k)    mem-cmml             440  91.6   2,921   0.0042   1.54    4.15   0.00    5.69    11.6*
d16 (494k)    mem-cmmn             440  92.0   4,095   0.0054   1.54    4.15   0.00    5.69    11.6*
d16 (484k)    mem-ledger_dev3      218  71.1   4,488   0.0057   0.00    0.00   0.00    0.00    0*
d16 (494k)    mem-namegrep_co      440  93.4   4,088   0.0054   0.00    0.00   0.00    0.00    0*
d16 (494k)    mem-pbm25            440  89.5   3,974   0.0053   0.00    0.00   0.00    0.00    0*
d64 (1,955k)  bm25                 440  61.6   4,162   0.0056   0.00    0.00   0.00    0.00    0*
d64 (1,955k)  hybrid               440  67.5   4,163   0.0056   0.00    0.00   0.00    0.00    0*
d64 (1,955k)  mem-cmm              440  70.0   4,113   0.0055   5.94    19.21  0.00    25.15   12.9*
d64 (1,955k)  mem-cmm2             440  87.3   4,156   0.0055   5.94    19.21  0.00    25.15   12.9*
d64 (1,955k)  mem-cmm2c            440  90.5   4,146   0.0053   5.94    19.21  0.61    25.76   13.2*
d64 (1,955k)  mem-cmm4             440  89.8   4,130   0.0055   5.94    19.21  0.00    25.15   12.9*
d64 (1,955k)  mem-cmm4a            440  93.2   10,088  0.0115   5.94    19.21  0.00    25.15   12.9*
d64 (1,955k)  mem-cmml             440  70.2   3,690   0.0050   5.94    19.21  0.00    25.15   12.9*
d64 (1,955k)  mem-cmmn             440  70.0   4,103   0.0055   5.94    19.21  0.00    25.15   12.9*
d64 (1,955k)  mem-namegrep_co      440  85.0   4,133   0.0054   0.00    0.00   0.00    0.00    0*
d64 (1,955k)  mem-pbm25            440  85.5   4,005   0.0053   0.00    0.00   0.00    0.00    0*

Q* = questions after which the memory's total cost (build + reading) is below re-reading the whole record for every question; '*' = counterfactual full re-reading (does not fit the reader's window).
```

## lifecycle_cost_D4_D5: S6.8 and B.1 lifecycle cost and break-even, worlds D4-D5

`python methods/costs.py --data saga_v5_s4,saga_v5_s5`

```
len           method                 n    acc %  ctx/q  $read/q  $write  $idle  $cards  $build  Q* vs full
d16 (473k)    bm25                   461  68.5   4,153  0.0056   0.00    0.00   0.00    0.00    0*
d16 (473k)    hybrid                 461  75.7   4,155  0.0056   0.00    0.00   0.00    0.00    0*
d16 (473k)    mem-cmm                461  85.7   4,129  0.0055   1.46    3.30   0.00    4.76    10.2*
d16 (473k)    mem-cmm2               461  91.1   4,134  0.0055   1.46    3.30   0.00    4.76    10.2*
d16 (473k)    mem-cmm2c              461  93.1   4,129  0.0053   1.46    3.30   0.51    5.27    11.2*
d16 (473k)    mem-cmm2l              461  90.7   3,089  0.0044   1.46    3.30   0.00    4.76    10.1*
d16 (473k)    mem-cmm4               461  95.0   4,104  0.0055   1.46    3.30   0.00    4.76    10.2*
d16 (467k)    mem-cmm4_built-q14     226  96.5   4,131  0.0055   1.43    2.49   0.00    3.92    8.5*
d16 (473k)    mem-cmm4_qboth         461  96.1   4,136  0.0057   1.46    3.30   0.00    4.76    10.2*
d16 (467k)    mem-cmm4auH_built-q14  226  96.9   4,133  0.0055   1.43    2.49   0.00    3.92    8.5*
d16 (473k)    mem-cmm4r              461  93.1   4,117  0.0055   1.46    3.30   0.00    4.76    10.2*
d16 (473k)    mem-cmmc               461  91.1   4,124  0.0053   1.46    3.30   0.51    5.27    11.2*
d16 (473k)    mem-namegrep_co        461  92.2   4,090  0.0054   0.00    0.00   0.00    0.00    0*
d16 (473k)    mem-pbm25              461  88.5   3,981  0.0053   0.00    0.00   0.00    0.00    0*
d16 (473k)    mem-pbm25_qboth        461  89.8   4,013  0.0055   0.00    0.00   0.00    0.00    0*
d16 (473k)    mem-pbm25r             461  87.6   3,994  0.0054   0.00    0.00   0.00    0.00    0*
d16 (473k)    oracle_para            461  88.9   121    0.0010   0.00    0.00   0.00    0.00    0*
d64 (1,841k)  bm25                   226  61.5   4,166  0.0057   0.00    0.00   0.00    0.00    0*
d64 (1,841k)  hybrid                 226  65.5   4,171  0.0056   0.00    0.00   0.00    0.00    0*
d64 (1,841k)  mem-cmm2               226  85.8   4,170  0.0055   5.59    14.92  0.00    20.50   11.2*
d64 (1,841k)  mem-cmm2c              226  89.8   4,150  0.0054   5.59    14.92  0.61    21.12   11.5*
d64 (1,841k)  mem-namegrep_co        226  83.6   4,167  0.0055   0.00    0.00   0.00    0.00    0*
d64 (1,841k)  mem-pbm25              226  84.5   4,007  0.0054   0.00    0.00   0.00    0.00    0*

Q* = questions after which the memory's total cost (build + reading) is below re-reading the whole record for every question; '*' = counterfactual full re-reading (does not fit the reader's window).
```

## escalation: B.9 certificate-gated against reader-triggered budgets

`python methods/escalation_compare.py`

```
## Saga s7+s8, 0.5M, reader claude-claude-haiku-4-5-20251001
  mem-cmm4           n=459 acc=94.3 tokens=4,095
  mem-cmm4a          n=459 acc=95.2 tokens=6,166
  mem-cmm4_escU3     n=459 acc=95.9 tokens=4,878
  mem-pbm25          n=459 acc=88.2 tokens=3,974
  mem-pbm25_escU3    n=459 acc=90.4 tokens=5,381
  hybrid             n=459 acc=77.1 tokens=4,156
  hybrid_escU3       n=459 acc=81.9 tokens=6,198
  mem-cmm4a vs mem-cmm4_escU3: +4/-7 p=0.5488; difference -0.7 [-2.1, +0.7] (175 clusters)
  mem-cmm4_escU3 vs mem-cmm4: +8/-1 p=0.0391; difference +1.5 [+0.4, +2.8] (175 clusters)
  mem-cmm4_escU3 vs mem-pbm25_escU3: +30/-5 p=0.0000; difference +5.4 [+3.0, +8.2] (175 clusters)
  mem-cmm4_escU3 vs hybrid_escU3: +69/-5 p=0.0000; difference +13.9 [+10.8, +17.3] (175 clusters)
  mem-cmm4a vs mem-pbm25_escU3: +30/-8 p=0.0005; difference +4.8 [+2.0, +7.7] (175 clusters)
  mem-cmm4a vs hybrid_escU3: +68/-7 p=0.0000; difference +13.3 [+10.0, +16.6] (175 clusters)

## Saga s7+s8, 0.5M, reader ollama-qwen3-14b

## Saga s7+s8, 1.9M, reader claude-claude-haiku-4-5-20251001
  mem-cmm4           n=459 acc=89.3 tokens=4,135
  mem-cmm4a          n=459 acc=92.4 tokens=9,241
  mem-cmm4_escU3     n=459 acc=91.3 tokens=5,189
  mem-pbm25          n=459 acc=86.1 tokens=4,001
  mem-pbm25_escU3    n=459 acc=88.7 tokens=5,569
  hybrid             n=459 acc=72.8 tokens=4,165
  hybrid_escU3       n=459 acc=78.4 tokens=6,638
  mem-cmm4a vs mem-cmm4_escU3: +13/-8 p=0.3833; difference +1.1 [-0.7, +2.9] (175 clusters)
  mem-cmm4_escU3 vs mem-cmm4: +12/-3 p=0.0352; difference +2.0 [+0.2, +3.7] (175 clusters)
  mem-cmm4_escU3 vs mem-pbm25_escU3: +23/-11 p=0.0576; difference +2.6 [+0.2, +5.2] (175 clusters)
  mem-cmm4_escU3 vs hybrid_escU3: +68/-9 p=0.0000; difference +12.9 [+9.3, +16.4] (175 clusters)
  mem-cmm4a vs mem-pbm25_escU3: +28/-11 p=0.0095; difference +3.7 [+1.3, +6.2] (175 clusters)
  mem-cmm4a vs hybrid_escU3: +73/-9 p=0.0000; difference +13.9 [+10.6, +17.2] (175 clusters)

## Novels C, reader claude-claude-haiku-4-5-20251001
  mem-cmm4           n=349 acc=58.5 tokens=4,068
  mem-cmm4a          n=349 acc=70.5 tokens=11,719
  mem-cmm4_escU3     n=349 acc=62.5 tokens=4,938
  mem-pbm25          n=349 acc=56.2 tokens=3,950
  mem-pbm25_escU3    n=349 acc=61.0 tokens=5,449
  hybrid             n=349 acc=63.9 tokens=4,137
  hybrid_escU3       n=349 acc=67.9 tokens=5,050
  mem-cmm4a vs mem-cmm4_escU3: +44/-16 p=0.0004; difference +8.0 [+4.3, +12.3] (349 clusters)
  mem-cmm4_escU3 vs mem-cmm4: +14/-0 p=0.0001; difference +4.0 [+2.0, +6.3] (349 clusters)
  mem-cmm4_escU3 vs mem-pbm25_escU3: +36/-31 p=0.6254; difference +1.4 [-3.2, +6.0] (349 clusters)
  mem-cmm4_escU3 vs hybrid_escU3: +22/-41 p=0.0226; difference -5.4 [-10.0, -1.1] (349 clusters)
  mem-cmm4a vs mem-pbm25_escU3: +54/-21 p=0.0002; difference +9.5 [+4.9, +14.3] (349 clusters)
  mem-cmm4a vs hybrid_escU3: +36/-27 p=0.3135; difference +2.6 [-2.0, +6.9] (349 clusters)
```
