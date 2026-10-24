test, reader claude-claude-haiku-4-5-20251001: 1352 questions decomposed; skipped {'template not handled': 848}

| subset | questions | routing correct | tables, right range (S_e) | tables, chosen range (S_r) | reader (S) | shortfall of the tables (1 - S_e) | net loss by routing (S_e - S_r) | net loss by reading (S_r - S) | tables, right range, short names merged (post hoc) |
|---|---|---|---|---|---|---|---|---|---|
| all handled | 1352 | 0.999 | 0.345 | 0.345 | 0.344 | 0.655 | +0.000 | +0.001 | 0.363 |
| 1 episode | 69 | 1.000 | 0.503 | 0.503 | 0.530 | 0.497 | +0.000 | -0.027 | 0.536 |
| 2-10 episodes | 1035 | 0.998 | 0.349 | 0.349 | 0.347 | 0.651 | +0.000 | +0.001 | 0.367 |
| 16-24 episodes | 248 | 1.000 | 0.287 | 0.287 | 0.278 | 0.713 | +0.000 | +0.009 | 0.296 |
| selector: character | 379 | 0.995 | 0.368 | 0.367 | 0.365 | 0.632 | +0.000 | +0.002 | 0.431 |
| selector: natural | 172 | 1.000 | 0.213 | 0.213 | 0.210 | 0.787 | +0.000 | +0.003 | 0.213 |
| selector: nth | 303 | 1.000 | 0.518 | 0.518 | 0.518 | 0.482 | +0.000 | +0.000 | 0.518 |
| selector: player | 147 | 1.000 | 0.387 | 0.387 | 0.387 | 0.613 | +0.000 | +0.000 | 0.387 |
| selector: total | 272 | 1.000 | 0.162 | 0.162 | 0.162 | 0.838 | +0.000 | +0.000 | 0.162 |
| selector: type | 79 | 1.000 | 0.415 | 0.415 | 0.413 | 0.585 | +0.000 | +0.002 | 0.415 |

Per-question changes between stages (score difference beyond 1e-9):
| step | worse | better | unchanged | mean loss among worse | mean gain among better |
|---|---|---|---|---|---|
| routing (S_e -> S_r) | 1 | 0 | 1351 | 0.133 | 0.000 |
| reading (S_r -> S) | 44 | 42 | 1266 | 0.274 | 0.252 |
| routing and reading (S_e -> S) | 44 | 42 | 1266 | 0.277 | 0.252 |
Questions whose tables' own answer is already exact (S_e = 1): 256 of 1352; questions not handled by the templates: 848

Same 1352 handled questions: tables' own answer 0.345, index reader 0.344, BM25 reader 0.097.
The other 848 questions (templates not handled): index reader 0.458, BM25 reader 0.280.

Representation: indexed events whose filled character is not one of the window's characters:
- rolls: 42277 of 88838 (47.6%), counted per window (episodes shared by windows count again)
- spells: 7481 of 18663 (40.1%), counted per window (episodes shared by windows count again)
