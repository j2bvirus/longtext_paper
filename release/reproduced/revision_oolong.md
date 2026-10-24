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
