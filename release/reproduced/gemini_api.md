| Window | episodes | status | Gemini full reading | items in per-episode lists | 'N episodes' in reply |
|---|---|---|---|---|---|
| W01 | 16 | scored | 0.261 |  |  |
| W02 | 16 | scored | 0.314 | 16 | 16 |
| W03 | 16 | scored | 0.300 | 16 | 16 |
| W04 | 16 | scored | 0.310 | 16 |  |
| W05 | 16 | scored | 0.468 | 16 |  |
| W06 | 16 | scored | 0.315 | 15 (fewer than episodes) |  |
| W07 | 16 | scored | 0.195 |  |  |
| W08 | 16 | scored | 0.248 | 16, 16 |  |
| W09 | 16 | scored | 0.221 |  |  |
| W10 | 16 | scored | 0.453 |  |  |
| W11 | 24 | not done |  |  |  |
| W12 | 24 | not done |  |  |  |
| W13 | 24 | not done |  |  |  |
| W14 | 24 | not done |  |  |  |
| W15 | 24 | not done |  |  |  |
| W16 | 24 | not done |  |  |  |
| W17 | 24 | not done |  |  |  |
| W18 | 24 | not done |  |  |  |
| W19 | 24 | not done |  |  |  |
| W20 | 24 | not done |  |  |  |

On the 200 questions answered through the web:
- Gemini 4 Argon, web, whole window: 0.309
- index Haiku on the same questions (200): 0.330
- index GPT on the same questions (200): 0.311
- BM25 GPT on the same questions (200): 0.131

Window subsets (mean of window means; difference = other - Gemini, window bootstrap 95%):
| subset | windows | Gemini | index Haiku | index GPT | BM25 GPT | index Haiku - Gemini | index GPT - Gemini | BM25 GPT - Gemini |
|---|---|---|---|---|---|---|---|---|
| 16 episodes | 10 | 0.309 | 0.330 | 0.311 | 0.131 | +0.022 [-0.041, +0.074] (7/10 ahead) | +0.002 [-0.066, +0.069] (6/10 ahead) | -0.177 [-0.221, -0.130] (0/10 ahead) |
| all windows | 10 | 0.309 | 0.330 | 0.311 | 0.131 | +0.022 [-0.039, +0.076] (7/10 ahead) | +0.002 [-0.069, +0.070] (6/10 ahead) | -0.177 [-0.221, -0.128] (0/10 ahead) |
partial reading: W06
