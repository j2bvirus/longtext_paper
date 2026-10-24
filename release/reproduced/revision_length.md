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
