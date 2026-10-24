# Final test (frozen v4; splits never used for design)

### LongState-Saga, fresh worlds s7+s8, ~0.5M tokens

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | 96.9 [95,99] (6,166) | 95.2 [93,97] (6,166) | 65.1 [60,70] (6,166) | 60.3 [56,65] (6,166) |
| CMM v4-adaptive+cards | – | 95.2 [93,97] (6,619) 6/6 | 74.9 [70,79] (6,619) *8/53 | 67.1 [63,72] (6,620) *13/44 |
| CMM v4 | 96.7 [95,98] (4,095) 1/0 | 94.3 [92,96] (4,095) 7/3 | 65.4 [60,70] (4,095) 5/6 | 58.4 [54,63] (4,095) 13/4 |
| CMM v4+cards | – | 94.8 [93,97] (4,092) 9/7 | 75.6 [71,79] (4,092) *11/59 | 65.8 [61,70] (4,092) 24/49 |
| CMM v3 | – | 92.6 [90,95] (4,093) 14/2 | – | – |
| CMM v3+cards | – | 93.0 [90,95] (4,091) 16/6 | – | – |
| CMM v2 | – | 91.1 [88,94] (4,126) *21/2 | – | – |
| CMM v2-lean | – | 91.3 [89,94] (2,973) 25/7 | 64.9 [60,69] (2,972) 20/19 | 62.7 [58,67] (2,973) 23/34 |
| CMM v2+cards | 94.1 [92,96] (4,120) 18/5 | 93.2 [91,95] (4,121) 21/12 | 81.7 [78,85] (4,120) *16/92 | 67.5 [63,72] (4,120) 39/72 |
| CMM v1 | – | 87.6 [84,91] (4,122) *37/2 | – | – |
| CMM v1+cards | – | 92.8 [90,95] (4,117) 23/12 | – | – |
| NameGrep+co | 96.3 [94,98] (4,082) 8/5 | 92.4 [90,95] (4,082) 24/11 | 64.9 [60,69] (4,082) 37/36 | 59.5 [55,64] (4,082) 30/26 |
| Paragraph BM25 | 90.6 [88,93] (3,974) *31/2 | 88.2 [85,91] (3,974) *40/8 | 68.0 [64,72] (3,974) 34/47 | 59.7 [55,64] (3,974) 34/31 |
| State ledger | 74.7 [70,79] (4,422) *103/1 | 71.0 [67,75] (4,422) *115/4 | 61.2 [56,66] (4,422) 78/60 | 55.3 [50,60] (4,422) 80/57 |
| CMM v2+cards by Qwen3-14B | – | – | 73.0 [69,77] (4,121) *32/68 | 59.9 [56,64] (4,121) 45/43 |
| CMM v2+cards by Qwen3-8B | – | – | – | 59.9 [55,64] (4,121) 39/37 |
| Hybrid RAG | 82.6 [79,86] (4,156) *68/2 | 77.1 [73,81] (4,156) *89/6 | 62.1 [57,67] (4,156) 62/48 | 61.0 [56,66] (4,156) 49/52 |
| BM25 chunks | – | 73.2 [69,77] (4,157) *108/7 | 59.7 [55,64] (4,157) 75/50 | 57.1 [53,61] (4,157) 63/48 |
| Gold paragraphs | 98.0 [97,99] (124) 7/12 | 89.8 [87,93] (124) 43/18 | 91.3 [89,94] (124) *11/131 | 87.1 [84,90] (124) *14/137 |

n = 459 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 48 tests of this table.

### LongState-Saga, fresh worlds s7+s8, ~1.9M tokens

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | 95.0 [93,97] (9,241) | 92.4 [90,95] (9,241) | – | – |
| CMM v4-adaptive+cards | – | 92.2 [89,95] (9,342) 6/5 | – | – |
| CMM v4 | 93.2 [91,96] (4,135) *8/0 | 89.3 [86,92] (4,135) *19/5 | 67.3 [63,72] (4,135) | – |
| CMM v4+cards | – | 90.0 [87,93] (4,127) 18/7 | 73.0 [68,77] (4,127) | – |
| CMM v3 | – | – | – | – |
| CMM v3+cards | – | – | – | – |
| CMM v2 | – | 87.4 [84,90] (4,163) *28/5 | – | – |
| CMM v2-lean | – | – | 68.0 [64,72] (3,674) | – |
| CMM v2+cards | – | 89.8 [87,92] (4,149) 21/9 | 77.3 [73,81] (4,149) | – |
| CMM v1 | – | – | – | – |
| CMM v1+cards | – | – | – | – |
| NameGrep+co | 89.8 [86,93] (4,145) *36/12 | 86.9 [83,90] (4,145) *42/17 | – | – |
| Paragraph BM25 | 89.1 [86,92] (4,001) *27/0 | 86.1 [82,89] (4,001) *35/6 | 63.8 [59,68] (4,001) | – |
| State ledger | – | 63.2 [58,68] (4,549) *142/8 | 51.9 [47,57] (4,549) | – |
| CMM v2+cards by Qwen3-14B | – | – | – | – |
| CMM v2+cards by Qwen3-8B | – | – | – | – |
| Hybrid RAG | 75.4 [71,79] (4,165) *91/1 | 72.8 [69,77] (4,165) *97/7 | 55.6 [51,61] (4,165) | – |
| BM25 chunks | – | – | – | – |
| Gold paragraphs | – | – | – | – |

n = 459 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 13 tests of this table.

### LongState-Saga s7, filler without names (~0.5M)

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | – | – | – | – |
| CMM v4-adaptive+cards | – | – | – | – |
| CMM v4 | – | 94.5 [92,97] (4,058) | 64.4 [58,70] (4,058) | – |
| CMM v4+cards | – | 93.2 [89,96] (4,059) | 76.7 [71,82] (4,060) | – |
| CMM v3 | – | – | – | – |
| CMM v3+cards | – | – | – | – |
| CMM v2 | – | 88.6 [84,92] (4,074) | – | – |
| CMM v2-lean | – | – | – | – |
| CMM v2+cards | – | 92.4 [88,95] (4,080) | 85.2 [80,89] (4,080) | – |
| CMM v1 | – | – | – | – |
| CMM v1+cards | – | – | – | – |
| NameGrep+co | – | 92.8 [89,96] (4,043) | 65.7 [59,71] (4,043) | – |
| Paragraph BM25 | – | 86.0 [81,91] (3,963) | 64.4 [58,71] (3,963) | – |
| State ledger | – | – | – | – |
| CMM v2+cards by Qwen3-14B | – | – | – | – |
| CMM v2+cards by Qwen3-8B | – | – | – | – |
| Hybrid RAG | – | 78.4 [73,83] (4,162) | 65.7 [59,72] (4,162) | – |
| BM25 chunks | – | 82.2 [77,87] (4,162) | – | – |
| Gold paragraphs | – | 88.6 [85,92] (126) | – | – |

n = 236 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 0 tests of this table.

### Real novels, group C (Emma, Wuthering Heights, Sense and Sensibility; judged)

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | 73.4 [69,78] (11,719) | 70.5 [66,75] (11,719) | – | – |
| CMM v4 | 67.0 [62,72] (4,068) *34/12 | 58.5 [53,63] (4,068) *58/16 | – | 51.6 [46,57] (4,068) |
| CMM v4+cards | – | 59.0 [54,64] (4,068) *56/16 | – | 51.9 [47,57] (4,068) |
| CMM v3 | – | 61.9 [57,67] (4,061) *52/22 | – | – |
| CMM v3+cards | – | 61.3 [56,66] (4,061) *54/22 | – | – |
| CMM v2 | – | 55.0 [50,60] (4,078) *68/14 | – | – |
| CMM v2+cards | – | 55.3 [50,60] (4,077) *68/15 | – | – |
| CMM v2-lean | – | – | – | 46.1 [41,51] (4,059) |
| NameGrep+co | – | 48.1 [43,53] (3,968) *92/14 | – | – |
| Paragraph BM25 | 61.6 [56,66] (3,950) *56/15 | 56.2 [51,61] (3,950) *69/19 | – | 47.9 [43,53] (3,950) |
| State ledger | – | 15.5 [12,19] (4,743) *198/6 | – | – |
| Hybrid RAG | 65.6 [61,71] (4,137) *45/18 | 63.9 [59,68] (4,137) *47/24 | – | 49.0 [44,54] (4,137) |
| BM25 chunks | – | 52.1 [47,57] (4,139) *77/13 | – | – |
| Gold paragraphs | 83.7 [80,87] (583) *9/45 | 75.1 [71,79] (583) 30/46 | – | 69.3 [64,74] (583) |
| Closed book | 44.7 [40,50] (47) *110/10 | 21.5 [17,26] (47) *180/9 | – | 12.0 [9,16] (47) |

n = 349 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 18 tests of this table.

### LongState-Code, test worlds s2+s3, d4

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | – | 77.5 [74,81] (4,069) | – | – |
| CMM v4 | – | 77.2 [73,81] (3,982) 2/1 | – | – |
| CMM v4+cards | – | 77.9 [74,81] (3,993) 15/17 | – | – |
| CMM v2 | – | 78.9 [75,82] (4,005) 1/8 | – | – |
| CMM v2-lean | – | 70.8 [67,75] (784) *47/15 | – | – |
| CMM v2+cards | – | 77.9 [74,82] (4,019) 22/24 | – | – |
| NameGrep+co | – | 83.1 [80,86] (3,923) *8/35 | – | – |
| Paragraph BM25 | – | 82.7 [79,86] (3,923) *10/35 | 59.7 [55,64] (3,923) | 52.4 [48,57] (3,923) |
| State ledger | – | – | – | – |
| Hybrid RAG | – | 57.6 [53,62] (4,021) *114/19 | 47.0 [43,51] (4,021) | 45.9 [41,51] (4,021) |
| BM25 chunks | – | 54.1 [50,58] (4,012) *140/28 | 46.6 [42,51] (4,012) | 42.2 [38,47] (4,012) |
| Gold paragraphs | – | 92.9 [91,95] (106) *21/95 | 85.2 [82,89] (106) | 82.3 [79,86] (106) |

n = 479 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 10 tests of this table.

### LongState-Code, test worlds s2+s3, d16

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | – | 79.5 [76,83] (4,392) | – | – |
| CMM v4 | 82.7 [79,86] (4,009) | 79.1 [75,83] (4,009) 2/0 | 57.2 [53,62] (4,009) | 49.5 [45,54] (4,009) |
| CMM v4+cards | – | 79.1 [76,83] (4,011) 13/11 | 63.3 [59,68] (4,011) | 61.4 [57,66] (4,011) |
| CMM v2 | – | 79.5 [76,83] (4,038) 16/16 | – | – |
| CMM v2-lean | – | 71.6 [68,76] (762) *52/14 | – | – |
| CMM v2+cards | – | 76.6 [73,80] (4,040) 29/15 | – | – |
| NameGrep+co | – | 81.0 [77,84] (3,962) 20/27 | – | – |
| Paragraph BM25 | 82.7 [79,86] (4,002) | 81.2 [78,85] (4,002) 17/25 | 59.1 [55,63] (4,002) | 52.6 [48,57] (4,002) |
| State ledger | – | 49.3 [45,54] (4,058) *156/11 | – | – |
| Hybrid RAG | 51.4 [47,56] (4,081) | 51.4 [47,56] (4,081) *146/11 | 44.1 [40,49] (4,081) | 40.9 [36,45] (4,081) |
| BM25 chunks | – | 49.1 [45,54] (4,077) *158/12 | 48.2 [44,53] (4,077) | 40.5 [36,45] (4,077) |
| Gold paragraphs | 95.0 [93,97] (107) | – | – | – |

n = 479 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 10 tests of this table.

### LongState-Code, test worlds s2+s3, d64

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | – | 76.6 [73,80] (4,349) | – | – |
| CMM v4 | 80.0 [76,84] (4,004) | 76.2 [72,80] (4,004) 2/0 | 55.9 [52,61] (4,004) | 49.7 [46,54] (4,004) |
| CMM v4+cards | – | 76.2 [72,80] (4,006) 15/13 | 61.8 [58,66] (4,006) | 62.0 [58,67] (4,006) |
| CMM v2 | – | 77.2 [73,81] (4,061) 12/15 | – | – |
| CMM v2-lean | – | 73.1 [69,77] (1,090) 38/21 | – | – |
| CMM v2+cards | – | 76.8 [73,81] (4,065) 20/21 | – | – |
| NameGrep+co | – | 77.0 [73,81] (3,984) 22/24 | – | – |
| Paragraph BM25 | 80.8 [77,84] (4,025) | 80.0 [76,84] (4,025) *7/23 | 58.9 [54,63] (4,025) | 50.9 [47,56] (4,025) |
| State ledger | – | – | – | – |
| Hybrid RAG | 42.6 [38,47] (3,997) | 42.8 [39,47] (3,997) *176/14 | 39.9 [36,44] (3,997) | 39.5 [35,44] (3,997) |
| BM25 chunks | – | 47.2 [43,52] (3,979) *152/11 | 44.9 [40,49] (3,979) | 40.5 [36,45] (3,979) |
| Gold paragraphs | 94.6 [92,96] (108) | – | – | – |

n = 479 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 9 tests of this table.

### LongState-Code, test worlds s2+s3, d256

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | – | 74.5 [71,78] (4,401) | – | – |
| CMM v4 | – | 73.3 [69,77] (4,025) 6/0 | – | – |
| CMM v4+cards | – | 74.3 [70,78] (4,026) 11/10 | – | – |
| CMM v2 | – | 76.0 [72,80] (4,100) 8/15 | – | – |
| CMM v2-lean | – | 70.1 [66,74] (1,600) 39/18 | – | – |
| CMM v2+cards | – | 76.0 [72,80] (4,103) 15/22 | – | – |
| NameGrep+co | – | 73.9 [70,78] (4,008) 24/21 | – | – |
| Paragraph BM25 | – | 77.7 [74,81] (4,049) 7/22 | 58.0 [54,62] (4,049) | 47.8 [43,52] (4,049) |
| State ledger | – | – | – | – |
| Hybrid RAG | – | 45.9 [42,51] (4,099) *148/11 | 42.4 [38,47] (4,099) | 41.1 [37,46] (4,099) |
| BM25 chunks | – | 43.8 [39,48] (4,083) *157/10 | 43.2 [39,48] (4,083) | 38.6 [34,43] (4,083) |
| Gold paragraphs | – | – | – | – |

n = 479 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 9 tests of this table.

### LoCoMo chat (10 conversations; judged)

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4 | 69.0 [64,74] (3,643) | 61.7 [56,67] (3,643) | 51.0 [46,56] (3,643) | 47.0 [41,53] (3,643) |
| CMM v4+cards | – | 61.7 [56,67] (3,643) 0/0 | 51.0 [46,56] (3,643) 0/0 | 47.0 [41,53] (3,643) 0/0 |
| CMM v2 | – | 54.7 [49,61] (3,683) 38/17 | – | – |
| CMM v2-lean | – | 54.7 [49,60] (3,609) 38/17 | – | – |
| CMM v2+cards | – | 56.3 [51,62] (3,701) 36/20 | – | – |
| Paragraph BM25 | 65.0 [59,70] (3,860) 25/13 | 54.7 [49,60] (3,860) 35/14 | 44.0 [39,50] (3,860) *30/9 | 44.0 [39,50] (3,860) 28/19 |
| State ledger | – | 36.3 [31,42] (4,193) *107/31 | – | – |
| Hybrid RAG | 71.7 [66,77] (4,066) 8/16 | 62.0 [56,67] (4,066) 21/22 | 52.7 [47,58] (4,066) 17/22 | 48.7 [43,55] (4,066) 15/20 |
| BM25 chunks | – | – | – | – |
| Gold paragraphs | 74.7 [70,80] (143) 23/40 | 64.3 [59,70] (143) 36/44 | 64.0 [59,69] (143) *25/64 | 54.7 [49,60] (143) 30/53 |
| Full re-reading | 76.7 [72,81] (30,486) *6/29 | 67.0 [62,72] (30,486) 21/37 | – | 27.7 [23,33] (30,486) *80/22 |

n = 300 questions per reader. w/l = questions the reference (CMM v4) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 22 tests of this table.

### Reading-budget sweep: accuracy (tokens per question)


Haiku 4.5

| Method | 2k | 4k | 8k | 16k |
|---|---|---|---|---|
| Paragraph BM25 | 86.9 (2,020) | 88.2 (3,974) | 89.8 (7,859) | 89.1 (15,586) |
| Hybrid RAG | 69.5 (2,096) | 77.1 (4,156) | 85.2 (8,256) | 85.6 (16,366) |
| CMM v4 | 91.5 (2,099) | 94.3 (4,095) | 93.7 (8,018) | 93.7 (15,731) |
| CMM v4+cards | 91.1 (2,088) | 94.8 (4,092) | 93.9 (8,023) | 94.3 (15,749) |
| CMM v4-adaptive (budget 4k, x3 when uncertified) | 95.2 (6,166) | | | |

Qwen3-14B

| Method | 2k | 4k | 8k | 16k |
|---|---|---|---|---|
| Paragraph BM25 | – | 68.0 (3,974) | 63.2 (7,859) | – |
| Hybrid RAG | – | 62.1 (4,156) | 62.5 (8,256) | – |
| CMM v4 | – | 65.4 (4,095) | 63.8 (8,018) | – |
| CMM v4+cards | – | 75.6 (4,092) | 75.8 (8,023) | – |
| CMM v4-adaptive (budget 4k, x3 when uncertified) | 65.1 (6,166) | | | |

### Reader-prompt sensitivity (s7+s8, 0.5M)

| Reader | Method | default | _p-minimal | _p-decisive |
|---|---|---|---|---|
| Haiku 4.5 | Paragraph BM25 | 88.2 | 88.2 | 89.1 |
| Haiku 4.5 | Hybrid RAG | 77.1 | 78.9 | 78.0 |
| Haiku 4.5 | CMM v4+cards | 94.8 | 94.1 | 94.8 |
| Haiku 4.5 | CMM v2+cards | 93.2 | 92.8 | 93.7 |
| Qwen3-14B | Paragraph BM25 | 68.0 | 66.2 | – |
| Qwen3-14B | Hybrid RAG | 62.1 | 62.7 | – |
| Qwen3-14B | CMM v4+cards | 75.6 | 75.8 | – |
| Qwen3-14B | CMM v2+cards | 81.7 | 80.0 | – |

### Storage-time ablations of v4 (s7+s8, 0.5M, Haiku)

| Reader | Method | default | _abl-resolve | _abl-anchor+rlines | _abl-ground+vote+demote |
|---|---|---|---|---|---|
| Haiku 4.5 | CMM v4 | 94.3 | 94.1 | 94.1 | 95.0 |

### Compaction and extraction baselines, s7+s8 ~0.5M (agent-style compaction reads 4k or 16k tokens)

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | 96.9 [95,99] (6,166) | 95.2 [93,97] (6,166) | 65.1 [60,70] (6,166) | 60.3 [56,65] (6,166) |
| CMM v4 | 96.7 [95,98] (4,095) 1/0 | 94.3 [92,96] (4,095) 7/3 | 65.4 [60,70] (4,095) 5/6 | 58.4 [54,63] (4,095) 13/4 |
| CMM v4 + idle-time index review | – | 94.3 [92,96] (4,095) 10/6 | – | – |
| Map + archive (2k compacted summary + CMM v4) | – | 91.9 [89,94] (6,123) 22/7 | – | – |
| Compaction 4k (2k summary + 2k tail) | 15.5 [11,20] (3,995) *374/0 | 15.5 [11,20] (3,995) *366/0 | 13.3 [10,17] (3,995) *253/15 | 12.9 [10,16] (3,995) *240/22 |
| Compaction 4k, questions known in advance (oracle) | – | – | – | – |
| Compaction 16k (8k summary + 8k tail) | 19.0 [15,23] (15,629) *358/0 | 18.1 [14,22] (15,629) *354/0 | – | – |
| State ledger | 74.7 [70,79] (4,422) *103/1 | 71.0 [67,75] (4,422) *115/4 | 61.2 [56,66] (4,422) 78/60 | 55.3 [50,60] (4,422) 80/57 |
| State ledger (status-aware) | – | 71.2 [67,76] (4,519) *114/4 | 61.0 [56,65] (4,519) 76/57 | 55.6 [50,61] (4,519) 79/57 |
| Hybrid RAG | 82.6 [79,86] (4,156) *68/2 | 77.1 [73,81] (4,156) *89/6 | 62.1 [57,67] (4,156) 62/48 | 61.0 [56,66] (4,156) 49/52 |
| Paragraph BM25 | 90.6 [88,93] (3,974) *31/2 | 88.2 [85,91] (3,974) *40/8 | 68.0 [64,72] (3,974) 34/47 | 59.7 [55,64] (3,974) 34/31 |

n = 459 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 27 tests of this table.

### Compaction by compactor model (default = Haiku compacts; _built-gpt = GPT compacts)

| Reader | Method | default | _built-gpt |
|---|---|---|---|
| Haiku 4.5 | Compaction 4k (2k summary + 2k tail) | 15.5 | 20.5 |
| GPT-6.1-sol | Compaction 4k (2k summary + 2k tail) | 15.5 | 33.6 |

### Real novels C: compaction and extraction (judged)

| Method | GPT-6.1-sol acc [95% CI] (tokens/q) | Haiku 4.5 acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) | Qwen3-8B acc [95% CI] (tokens/q) |
|---|---|---|---|---|
| CMM v4-adaptive | 73.4 [69,78] (11,719) | 70.5 [66,75] (11,719) | – | – |
| CMM v4 | 67.0 [62,72] (4,068) *34/12 | 58.5 [53,63] (4,068) *58/16 | – | 51.6 [46,57] (4,068) |
| Map + archive (2k compacted summary + CMM v4) | – | 60.7 [56,66] (6,096) *54/20 | – | – |
| Compaction 4k (2k summary + 2k tail) | 12.6 [9,16] (4,047) *213/1 | 4.9 [3,7] (4,047) *232/3 | – | 11.5 [8,15] (4,047) |
| Compaction 16k (8k summary + 8k tail) | 24.9 [21,30] (15,605) *171/2 | 14.0 [10,18] (15,605) *202/5 | – | – |
| State ledger | – | 15.5 [12,19] (4,743) *198/6 | – | – |
| State ledger (status-aware) | – | 13.8 [10,17] (4,633) *203/5 | – | – |
| Hybrid RAG | 65.6 [61,71] (4,137) *45/18 | 63.9 [59,68] (4,137) *47/24 | – | 49.0 [44,54] (4,137) |

n = 349 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 11 tests of this table.

### AMA-Bench GAIA trajectories (14, 0.19M-1.06M tokens; expert questions; benchmark judge wording)

| Method | Haiku 4.5 acc [95% CI] (tokens/q) | GPT-6.1-sol acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) |
|---|---|---|---|
| CMM v4-adaptive | 53.0 [45,61] (7,376) | 62.5 [55,70] (7,377) | – |
| CMM v4 | 48.8 [41,57] (3,735) 12/5 | 60.1 [53,67] (3,735) 7/3 | 43.5 [36,51] (3,735) |
| Map + archive (8k compacted summary + CMM v4) | 48.2 [40,55] (7,265) 22/14 | – | – |
| NameGrep+co | 45.8 [39,54] (3,970) 26/14 | – | – |
| Paragraph BM25 | 48.2 [40,56] (3,969) 22/14 | 57.7 [50,65] (3,969) 20/12 | 39.9 [33,48] (3,969) |
| Hybrid RAG | 55.4 [48,63] (4,187) 11/15 | 60.7 [54,68] (4,187) 14/11 | 48.2 [40,56] (4,187) |
| BM25 chunks | 45.8 [38,54] (4,190) 27/15 | – | – |
| Compaction 16k (8k summary + 8k tail) | 25.0 [19,32] (11,831) *59/12 | – | – |
| Full re-reading | – | – | – |

n = 168 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 10 tests of this table.

### AMA-Bench SWE-bench trajectories (12, 69k-90k tokens)

| Method | Haiku 4.5 acc [95% CI] (tokens/q) | GPT-6.1-sol acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) |
|---|---|---|---|
| CMM v4-adaptive | 29.9 [22,38] (7,940) | 36.1 [28,44] (7,940) | – |
| CMM v4 | 34.7 [27,42] (3,575) 6/13 | 34.7 [27,42] (3,575) 7/5 | 27.8 [21,35] (3,575) |
| Map + archive (8k compacted summary + CMM v4) | 27.8 [20,35] (5,082) 12/9 | – | – |
| NameGrep+co | 28.5 [22,36] (3,941) 15/13 | – | – |
| Paragraph BM25 | 31.2 [24,39] (3,952) 13/15 | 33.3 [26,42] (3,952) 15/11 | 24.3 [17,31] (3,952) |
| Hybrid RAG | 30.6 [23,38] (4,165) 12/13 | 34.7 [27,42] (4,165) 9/7 | 30.6 [23,38] (4,165) |
| BM25 chunks | 32.6 [25,40] (4,162) 14/18 | – | – |
| Compaction 16k (8k summary + 8k tail) | 24.3 [17,31] (9,771) 19/11 | – | – |
| Full re-reading | 25.7 [19,33] (83,184) 21/15 | 38.9 [31,47] (83,184) 11/15 | – |

n = 144 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 12 tests of this table.

### AMA-Bench GAIA, gold-confirmed questions only (80 questions labelled ok by the GPT gold audit)

| Method | Haiku 4.5 acc [95% CI] (tokens/q) | GPT-6.1-sol acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) |
|---|---|---|---|
| CMM v4-adaptive | 63.8 [54,74] (7,599) | 76.2 [66,86] (7,601) | – |
| CMM v4 | 57.5 [46,68] (3,722) 7/2 | 70.0 [60,79] (3,722) 5/0 | 56.2 [45,66] (3,722) |
| Map + archive (8k compacted summary + CMM v4) | 60.0 [50,70] (7,097) 10/7 | – | – |
| NameGrep+co | 52.5 [41,64] (3,971) 16/7 | – | – |
| Paragraph BM25 | 53.8 [42,65] (3,966) 14/6 | 68.8 [59,79] (3,966) 12/6 | 47.5 [36,59] (3,966) |
| Hybrid RAG | 63.8 [52,75] (4,186) 6/6 | 72.5 [62,82] (4,186) 6/3 | 57.5 [46,69] (4,186) |
| BM25 chunks | 53.8 [42,65] (4,191) 16/8 | – | – |
| Compaction 16k (8k summary + 8k tail) | 31.2 [21,41] (11,677) *34/8 | – | – |
| Full re-reading | – | – | – |

n = 80 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 10 tests of this table.

### AMA-Bench SWE-bench, gold-confirmed questions only (48 questions labelled ok by the GPT gold audit)

| Method | Haiku 4.5 acc [95% CI] (tokens/q) | GPT-6.1-sol acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) |
|---|---|---|---|
| CMM v4-adaptive | 60.4 [48,73] (8,290) | 68.8 [54,81] (8,290) | – |
| CMM v4 | 56.2 [42,71] (3,624) 5/3 | 64.6 [52,79] (3,624) 3/1 | 47.9 [35,62] (3,624) |
| Map + archive (8k compacted summary + CMM v4) | 50.0 [38,65] (5,124) 8/3 | – | – |
| NameGrep+co | 45.8 [31,60] (3,952) 12/5 | – | – |
| Paragraph BM25 | 50.0 [35,65] (3,963) 11/6 | 54.2 [40,67] (3,963) 9/2 | 43.8 [29,58] (3,963) |
| Hybrid RAG | 54.2 [42,69] (4,161) 8/5 | 58.3 [44,71] (4,161) 5/0 | 47.9 [33,62] (4,161) |
| BM25 chunks | 47.9 [35,62] (4,167) 10/4 | – | – |
| Compaction 16k (8k summary + 8k tail) | 39.6 [27,54] (9,744) 16/6 | – | – |
| Full re-reading | 47.9 [33,62] (82,926) 13/7 | 85.4 [75,94] (82,926) 1/9 | – |

n = 48 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 12 tests of this table.

### LongState-Continuity, paired test sets (worlds 7+8, ~0.5M tokens)

| Method | Haiku 4.5 J [95% CI] / pair acc (tokens/q) | GPT-6.1-sol J [95% CI] / pair acc (tokens/q) | Qwen3-14B J [95% CI] / pair acc (tokens/q) |
|---|---|---|---|
| CMM v4-adaptive | 90.3 [87,94] / 90.3 (7,442) 3/3 | 99.1 [98,100] / 99.1 (7,442) 0/0 | – |
| CMM v4 | 90.3 [86,94] / 90.3 (4,197) | 99.1 [98,100] / 99.1 (4,197) | 38.9 [32,46] / 40.7 (4,197) |
| CMM v4+cards | 87.0 [82,91] / 87.0 (4,185) 22/15 | 96.8 [94,99] / 96.8 (4,185) 5/0 | 70.4 [64,77] / 71.8 (4,185) *8/75 |
| CMM v4 + idle-time index review | 91.7 [88,95] / 91.7 (4,196) 5/8 | – | – |
| Map + archive (2k compacted summary + CMM v4) | 79.2 [73,85] / 80.1 (6,225) *27/5 | – | – |
| CMM v2 | 88.4 [84,93] / 88.9 (4,190) 9/6 | – | – |
| NameGrep+co | 81.9 [76,87] / 82.9 (4,149) 27/11 | 93.1 [89,96] / 93.1 (4,149) *13/0 | 39.4 [32,47] / 42.6 (4,149) 35/39 |
| Paragraph BM25 | 80.1 [74,85] / 81.0 (4,017) *28/8 | 91.2 [88,95] / 91.2 (4,017) *17/0 | 40.7 [33,48] / 43.5 (4,017) 32/38 |
| State ledger | 56.5 [49,64] / 62.0 (4,572) *69/8 | – | – |
| Compaction 4k (2k summary + 2k tail) | 11.6 [4,19] / 21.3 (4,037) *154/5 | 13.4 [8,19] / 14.8 (4,037) *182/0 | – |
| Hybrid RAG | 64.4 [56,71] / 69.0 (4,197) *54/8 | 68.1 [61,75] / 71.8 (4,197) *60/1 | 27.3 [20,35] / 33.8 (4,197) 44/29 |
| BM25 chunks | 48.1 [41,56] / 51.9 (4,194) *89/6 | – | – |
| Gold paragraphs | 70.8 [64,77] / 64.4 (129) *61/5 | 88.0 [83,93] / 88.9 (129) *22/0 | 63.4 [56,70] / 65.7 (129) *21/75 |
| Closed book | -0.5 [-1,0] / 0.0 (83) *195/0 | 0.5 [0,1] / 0.5 (83) *213/0 | -1.9 [-6,1] / 1.9 (83) *87/3 |

units (pairs, or items on unpaired sets) per reader: {'claude-claude-haiku-4-5-20251001': 216, 'codex-gpt-6.1-sol': 216, 'ollama-qwen3-14b': 216}. J in points; 95% bootstrap CI over units. w/l = units CMM v4 gets right and the method wrong / the reverse; * = Holm-corrected exact McNemar p < 0.05 over the 27 tests of this table.

### LongState-Continuity, development sets (worlds 4+5; unpaired; label errors dropped)

| Method | Haiku 4.5 J [95% CI] / pair acc (tokens/q) |
|---|---|
| CMM v4-adaptive | 91.7 [87,96] / n/a (7,312) 6/7 |
| CMM v4 | 91.5 [87,96] / n/a (4,207) |
| CMM v4+cards | 90.0 [85,94] / n/a (4,196) 10/8 |
| CMM v4 + idle-time index review | – |
| Map + archive (2k compacted summary + CMM v4) | – |
| CMM v2 | 90.9 [86,95] / n/a (4,204) 8/7 |
| NameGrep+co | 87.1 [81,92] / n/a (4,161) 14/7 |
| Paragraph BM25 | 84.9 [79,90] / n/a (4,026) 19/7 |
| State ledger | 57.6 [49,66] / n/a (4,557) *59/7 |
| Compaction 4k (2k summary + 2k tail) | – |
| Hybrid RAG | 58.9 [50,67] / n/a (4,195) *68/10 |
| BM25 chunks | 47.1 [38,56] / n/a (4,193) *94/8 |
| Gold paragraphs | 73.1 [66,80] / n/a (136) *60/9 |
| Closed book | – |

units (pairs, or items on unpaired sets) per reader: {'claude-claude-haiku-4-5-20251001': 377}. J in points; 95% bootstrap CI over units. w/l = units CMM v4 gets right and the method wrong / the reverse; * = Holm-corrected exact McNemar p < 0.05 over the 9 tests of this table.

### LongState-Aggregate, worlds 7+8 (~0.5M tokens): entity-anchored counting, enumeration and ordering

| Method | Haiku 4.5 acc [95% CI] (tokens/q) | GPT-6.1-sol acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) |
|---|---|---|---|
| CMM v4-adaptive | 86.0 [78,92] (7,738) | 92.0 [86,97] (7,738) | – |
| CMM v4 | 78.0 [70,86] (4,102) 8/0 | 84.0 [77,91] (4,102) 8/0 | 60.0 [51,69] (4,102) |
| CMM v4+cards | 78.0 [70,86] (4,102) 8/0 | – | – |
| Map + archive (2k compacted summary + CMM v4) | 77.0 [69,85] (6,130) 11/2 | – | – |
| NameGrep+co | 78.0 [70,86] (4,079) 10/2 | 86.0 [79,93] (4,079) 10/4 | – |
| Paragraph BM25 | 77.0 [69,85] (3,980) 13/4 | 83.0 [75,90] (3,980) 13/4 | 43.0 [33,54] (3,980) |
| State ledger | 54.0 [43,64] (4,433) *33/1 | – | – |
| Compaction 4k (2k summary + 2k tail) | 5.0 [1,10] (4,002) *82/1 | 2.0 [0,5] (4,002) *90/0 | – |
| Hybrid RAG | 63.0 [54,72] (4,165) *27/4 | 65.0 [55,74] (4,165) *27/0 | 46.0 [35,56] (4,165) |
| BM25 chunks | 47.0 [37,57] (4,165) *40/1 | – | – |
| Gold paragraphs | 84.0 [77,91] (135) 10/8 | 89.0 [83,95] (135) 5/2 | 84.0 [76,90] (135) |
| Closed book | 0.0 [0,0] (49) *86/0 | 9.0 [3,15] (49) *83/0 | – |

n = 100 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 18 tests of this table.

### LongState-Aggregate, worlds 7+8 (~0.5M tokens): global counting (totals, per place, per chapter range)

| Method | Haiku 4.5 acc [95% CI] (tokens/q) | GPT-6.1-sol acc [95% CI] (tokens/q) | Qwen3-14B acc [95% CI] (tokens/q) |
|---|---|---|---|
| CMM v4-adaptive | 32.6 [19,48] (4,390) | 39.1 [24,56] (4,390) | – |
| CMM v4 | 37.0 [22,53] (3,872) 1/3 | 39.1 [24,56] (3,870) 0/0 | 30.4 [16,48] (3,868) |
| CMM v4+cards | 37.0 [21,54] (3,870) 0/2 | – | – |
| Map + archive (2k compacted summary + CMM v4) | 37.0 [21,54] (5,898) 1/3 | – | – |
| NameGrep+co | 30.4 [18,45] (3,960) 3/2 | 34.8 [20,50] (3,960) 4/2 | – |
| Paragraph BM25 | 34.8 [21,51] (3,971) 2/3 | 34.8 [21,50] (3,971) 4/2 | 13.0 [4,24] (3,971) |
| State ledger | 28.3 [14,45] (4,094) 5/3 | – | – |
| Compaction 4k (2k summary + 2k tail) | 8.7 [2,18] (3,996) 14/3 | 8.7 [2,18] (3,996) *17/3 | – |
| Hybrid RAG | 28.3 [15,43] (4,152) 7/5 | 28.3 [15,43] (4,152) 8/3 | 17.4 [8,30] (4,152) |
| BM25 chunks | 19.6 [8,33] (4,162) 10/4 | – | – |
| Gold paragraphs | 80.4 [66,92] (194) *4/26 | 82.6 [68,94] (194) *4/24 | 69.6 [54,85] (194) |
| Closed book | 0.0 [0,0] (42) *15/0 | 4.3 [0,11] (42) *17/1 | – |

n = 46 questions per reader. w/l = questions the reference (CMM v4-adaptive) gets right and the method wrong / the reverse; * = Holm-corrected McNemar p < 0.05 over the 18 tests of this table.

### Reading-order control (post-hoc; same paragraphs, newest first)

| Split | Reader | CMM v4 | CMM v4, newest first | Paragraph BM25 | Paragraph BM25, newest first |
|---|---|---|---|---|---|
| dev s4+s5 | Haiku 4.5 | 95.0 | 93.1 | 88.5 | 87.6 |
| dev s4+s5 | Qwen3-14B | – | 57.5 | 65.5 | – |
| dev s4+s5 | Qwen3-8B | – | 50.5 | 57.7 | – |
| test s7+s8 | Haiku 4.5 | 94.3 | 91.3 | 88.2 | 86.5 |
| test s7+s8 | Qwen3-14B | 65.4 | 58.4 | 68.0 | – |
| test s7+s8 | Qwen3-8B | 58.4 | 56.2 | 59.7 | – |

### Question placed before and after the context (Lost-in-the-Middle mitigation; dev s4+s5)

| Reader | Method | default | _qboth |
|---|---|---|---|
| Haiku 4.5 | CMM v4 | 95.0 | 96.1 |
| Haiku 4.5 | Paragraph BM25 | 88.5 | 89.8 |
| Haiku 4.5 | CMM v2+cards | 93.1 | – |
| Qwen3-14B | CMM v4 | – | – |
| Qwen3-14B | Paragraph BM25 | 65.5 | 70.3 |
| Qwen3-14B | CMM v2+cards | 80.7 | 83.9 |
| Qwen3-8B | CMM v4 | – | – |
| Qwen3-8B | Paragraph BM25 | 57.7 | 66.4 |
| Qwen3-8B | CMM v2+cards | 72.5 | 76.1 |

### Who writes and who corrects the cards (dev s4+s5, ~0.5M)

| Reader | Condition | Accuracy |
|---|---|---|
| Qwen3-14B | CMM v2-lean | 67.2 (n=461) |
| Qwen3-14B | CMM v2+cards by Qwen3-14B | 75.5 (n=461) |
| Qwen3-14B | cards: 14B writes, 14B corrects | 74.4 (n=461) |
| Qwen3-14B | cards: 14B writes, Haiku corrects | 73.5 (n=461) |
| Qwen3-14B | cards: 14B writes, 14B drops | 71.6 (n=461) |
| Qwen3-14B | CMM v2+cards | 80.7 (n=461) |
| Qwen3-14B | cards: Haiku writes, 14B corrects | 79.8 (n=461) |
| Qwen3-8B | CMM v2-lean | 63.8 (n=461) |
| Qwen3-8B | CMM v2+cards by Qwen3-8B | 64.0 (n=461) |
| Qwen3-8B | cards: 8B writes, 8B corrects | 63.6 (n=461) |
| Qwen3-8B | cards: 8B writes, Haiku corrects | 65.3 (n=461) |
| Qwen3-8B | cards: 8B writes, 8B drops | 63.3 (n=461) |
| Qwen3-8B | CMM v2+cards | 72.5 (n=461) |
