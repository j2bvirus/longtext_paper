# Reading-budget sweep on state tracking (T1-T2, 459 questions), three readers

Accuracy % (mean rendered tokens per question); – = condition not complete.

## Claude Haiku 4.5 (no effort setting)

| Method | 2k | 4k | 8k | 16k |
|---|---|---|---|---|
| CMM v4 | 91.5 (2,099) | 94.3 (4,095) | 93.7 (8,018) | 93.7 (15,731) |
| Paragraph BM25 | 86.9 (2,020) | 88.2 (3,974) | 89.8 (7,859) | 89.1 (15,586) |
| Hybrid retrieval | 69.5 (2,096) | 77.1 (4,156) | 85.2 (8,256) | 85.6 (16,366) |

| Test | wins/losses | exact McNemar p | Holm p |
|---|---|---|---|
| CMM v4 vs Paragraph BM25, both 2k | +38/−17 | 0.0065 | 0.026 |
| CMM v4 vs Hybrid retrieval, both 2k | +114/−13 | 2.5e-21 | 2.8e-20 |
| CMM v4 vs Paragraph BM25, both 4k | +38/−10 | 6.2e-05 | 0.00043 |
| CMM v4 vs Hybrid retrieval, both 4k | +87/−8 | 6.7e-18 | 6.7e-17 |
| CMM v4 vs Paragraph BM25, both 8k | +31/−13 | 0.0096 | 0.029 |
| CMM v4 vs Hybrid retrieval, both 8k | +51/−12 | 7.5e-07 | 6.7e-06 |
| CMM v4 vs Paragraph BM25, both 16k | +31/−10 | 0.0015 | 0.0073 |
| CMM v4 vs Hybrid retrieval, both 16k | +48/−11 | 1.2e-06 | 9.9e-06 |
| CMM v4 4k vs Paragraph BM25 16k | +31/−7 | 0.00012 | 0.0007 |
| CMM v4 2k vs Paragraph BM25 8k | +31/−23 | 0.34 | 0.34 |
| CMM v4 2k vs Paragraph BM25 16k | +31/−20 | 0.16 | 0.32 |

CMM v4 4k minus Paragraph BM25 16k: 5.2 points, 95% subject-cluster bootstrap interval 2.6 to 8.0.

## GPT-6.1 Sol (reasoning effort low)

| Method | 2k | 4k | 8k | 16k |
|---|---|---|---|---|
| CMM v4 | 95.2 (2,099) | 96.7 (4,095) | 96.9 (8,018) | 97.4 (15,731) |
| Paragraph BM25 | 90.2 (2,020) | 90.6 (3,974) | 91.9 (7,859) | 93.7 (15,586) |
| Hybrid retrieval | 72.3 (2,096) | 82.6 (4,156) | 88.9 (8,256) | 91.1 (16,366) |

| Test | wins/losses | exact McNemar p | Holm p |
|---|---|---|---|
| CMM v4 vs Paragraph BM25, both 2k | +30/−7 | 0.00019 | 0.00076 |
| CMM v4 vs Hybrid retrieval, both 2k | +107/−2 | 1.8e-29 | 2e-28 |
| CMM v4 vs Paragraph BM25, both 4k | +31/−3 | 7.7e-07 | 5.4e-06 |
| CMM v4 vs Hybrid retrieval, both 4k | +67/−2 | 8.2e-18 | 8.2e-17 |
| CMM v4 vs Paragraph BM25, both 8k | +24/−1 | 1.5e-06 | 9.3e-06 |
| CMM v4 vs Hybrid retrieval, both 8k | +37/−0 | 1.5e-11 | 1.3e-10 |
| CMM v4 vs Paragraph BM25, both 16k | +17/−0 | 1.5e-05 | 7.6e-05 |
| CMM v4 vs Hybrid retrieval, both 16k | +29/−0 | 3.7e-09 | 3e-08 |
| CMM v4 4k vs Paragraph BM25 16k | +17/−3 | 0.0026 | 0.0077 |
| CMM v4 2k vs Paragraph BM25 8k | +24/−9 | 0.014 | 0.027 |
| CMM v4 2k vs Paragraph BM25 16k | +17/−10 | 0.25 | 0.25 |

CMM v4 4k minus Paragraph BM25 16k: 3.1 points, 95% subject-cluster bootstrap interval 1.1 to 5.2.

## Claude Sonnet 5.5 (effort high)

| Method | 2k | 4k | 8k | 16k |
|---|---|---|---|---|
| CMM v4 | 93.9 (2,099) | 96.1 (4,095) | 96.7 (8,018) | 97.2 (15,732) |
| Paragraph BM25 | 88.9 (2,020) | 89.5 (3,974) | 91.3 (7,859) | 92.6 (15,586) |
| Hybrid retrieval | 71.9 (2,096) | 81.3 (4,156) | 88.7 (8,256) | 90.2 (16,366) |

| Test | wins/losses | exact McNemar p | Holm p |
|---|---|---|---|
| CMM v4 vs Paragraph BM25, both 2k | +31/−8 | 0.00029 | 0.0012 |
| CMM v4 vs Hybrid retrieval, both 2k | +107/−6 | 5.1e-25 | 5.7e-24 |
| CMM v4 vs Paragraph BM25, both 4k | +32/−2 | 6.9e-08 | 4.9e-07 |
| CMM v4 vs Hybrid retrieval, both 4k | +71/−3 | 7.2e-18 | 7.2e-17 |
| CMM v4 vs Paragraph BM25, both 8k | +26/−1 | 4.2e-07 | 2.5e-06 |
| CMM v4 vs Hybrid retrieval, both 8k | +39/−2 | 7.8e-10 | 7.1e-09 |
| CMM v4 vs Paragraph BM25, both 16k | +22/−1 | 5.7e-06 | 2.9e-05 |
| CMM v4 vs Hybrid retrieval, both 16k | +33/−1 | 4.1e-09 | 3.3e-08 |
| CMM v4 4k vs Paragraph BM25 16k | +21/−5 | 0.0025 | 0.0075 |
| CMM v4 2k vs Paragraph BM25 8k | +26/−14 | 0.081 | 0.16 |
| CMM v4 2k vs Paragraph BM25 16k | +20/−14 | 0.39 | 0.39 |

CMM v4 4k minus Paragraph BM25 16k: 3.5 points, 95% subject-cluster bootstrap interval 1.3 to 5.9.

