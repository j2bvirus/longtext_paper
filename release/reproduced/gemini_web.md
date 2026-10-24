| Window | episodes | status | Gemini full reading | items in per-episode lists | 'N episodes' in reply |
|---|---|---|---|---|---|
| W01 | 16 | scored | 0.373 |  | 16 |
| W02 | 16 | scored | 0.302 | 16 | 16 |
| W03 | 16 | scored | 0.335 | 16 |  |
| W04 | 16 | scored | 0.322 | 16 | 16 |
| W05 | 16 | scored | 0.536 | 16 | 16 |
| W06 | 16 | scored | 0.243 | 16 | 16 |
| W07 | 16 | scored | 0.248 |  | 16 |
| W08 | 16 | scored | 0.321 | 16, 16 |  |
| W09 | 16 | scored | 0.294 |  | 16 |
| W10 | 16 | scored | 0.424 |  |  |
| W11 | 24 | scored | 0.261 | 15 (fewer than episodes) | 15 |
| W12 | 24 | scored | 0.324 | 24 | 24 |
| W13 | 24 | scored | 0.142 | 24 |  |
| W14 | 24 | scored | 0.184 | 24 | 24 |
| W15 | 24 | scored | 0.156 | 24 |  |
| W16 | 24 | scored | 0.456 | 24 | 24 |
| W17 | 24 | scored | 0.355 | 24 | 24 |
| W18 | 24 | scored | 0.213 |  | 18 |
| W19 | 24 | scored | 0.386 | 18 (fewer than episodes) |  |
| W20 | 24 | scored | 0.266 |  | 24 |

On the 400 questions answered through the web:
- Gemini 4 Argon, web, whole window: 0.307
- index Haiku on the same questions (400): 0.333
- index GPT on the same questions (400): 0.307
- BM25 GPT on the same questions (400): 0.128

Window subsets (mean of window means; difference = other - Gemini, window bootstrap 95%):
| subset | windows | Gemini | index Haiku | index GPT | BM25 GPT | index Haiku - Gemini | index GPT - Gemini | BM25 GPT - Gemini |
|---|---|---|---|---|---|---|---|---|
| 16 episodes | 10 | 0.340 | 0.330 | 0.311 | 0.131 | -0.010 [-0.089, +0.061] (5/10 ahead) | -0.029 [-0.114, +0.052] (5/10 ahead) | -0.209 [-0.263, -0.159] (0/10 ahead) |
| 24 episodes, all | 10 | 0.274 | 0.335 | 0.302 | 0.125 | +0.061 [+0.006, +0.112] (6/10 ahead) | +0.028 [-0.028, +0.083] (5/10 ahead) | -0.149 [-0.206, -0.091] (1/10 ahead) |
| 24 episodes, whole file seen | 7 | 0.269 | 0.324 | 0.286 | 0.102 | +0.054 [-0.006, +0.111] (4/7 ahead) | +0.017 [-0.043, +0.075] (3/7 ahead) | -0.168 [-0.234, -0.106] (0/7 ahead) |
| 24 episodes, partial reading | 3 | 0.287 | 0.363 | 0.341 | 0.180 | +0.076 [-0.049, +0.173] (2/3 ahead) | +0.054 [-0.086, +0.152] (2/3 ahead) | -0.106 [-0.223, +0.014] (1/3 ahead) |
| all windows | 20 | 0.307 | 0.333 | 0.307 | 0.128 | +0.026 [-0.025, +0.071] (11/20 ahead) | -0.000 [-0.056, +0.049] (10/20 ahead) | -0.179 [-0.220, -0.137] (1/20 ahead) |
partial reading: W11, W18, W19
