
### Event-type index, G2 counting, fresh worlds 11-12

| Reader | n | mem-evx4v5 | oracle_para | mem-cmm4 | mem-pbm25 | hybrid | mem-evx4v5 vs oracle_para: w/l, p (Holm) | mem-evx4v5 vs mem-cmm4: w/l, p (Holm) | mem-evx4v5 vs mem-pbm25: w/l, p (Holm) | mem-evx4v5 vs hybrid: w/l, p (Holm) |
|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | 75 | 78.7 | 48.0 | 44.0 | 41.3 | 25.3 | 28/5, 6.6e-05 | 27/1, 4.3e-07 | 28/0, 2.2e-08 | 40/0, 7.3e-12 |
| GPT-6.1-sol | 75 | 73.3 | 53.3 | 42.7 | 37.3 | 30.7 | 24/9, 0.014 | 27/4, 6.8e-05 | 28/1, 3.4e-07 | 34/2, 7.8e-08 |
| Gemini 4 Argon | 75 | 81.3 | 50.7 | 54.7 | 42.7 | 30.7 | 26/3, 3e-05 | 22/2, 3.6e-05 | 29/0, 1.1e-08 | 38/0, 2.9e-11 |
| GPT-OSS 120B | 75 | 66.7 | 46.7 | 42.7 | 41.3 | 29.3 | 25/10, 0.017 | 23/5, 0.0018 | 21/2, 0.0002 | 30/2, 9.9e-07 |

Accuracy in % over the questions (pairs for continuity) answered under every method of the task by that reader; continuity cells are pair accuracy with J = TPR - FPR in brackets.

### State tracking, worlds 7-8, about 0.5M tokens

| Reader | n | mem-cmm4 | mem-pbm25 | hybrid | mem-cmm4 vs mem-pbm25: w/l, p (Holm) | mem-cmm4 vs hybrid: w/l, p (Holm) |
|---|---|---|---|---|---|---|
| Haiku 4.5 | 459 | 94.3 | 88.2 | 77.1 | 38/10, 6.2e-05 | 87/8, 1.3e-17 |
| GPT-6.1-sol | 459 | 96.7 | 90.6 | 82.6 | 31/3, 7.7e-07 | 67/2, 1.6e-17 |
| Gemini 4 Argon | 459 | 97.4 | 91.5 | 81.0 | 28/1, 1.1e-07 | 75/0, 1.1e-22 |
| GPT-OSS 120B | 459 | 92.6 | 83.4 | 76.9 | 52/10, 5.7e-08 | 82/10, 6.6e-15 |

Accuracy in % over the questions (pairs for continuity) answered under every method of the task by that reader; continuity cells are pair accuracy with J = TPR - FPR in brackets.

### Continuity checking, worlds 7-8 (pairs)

| Reader | n | mem-cmm4 | mem-pbm25 | hybrid | mem-cmm4 vs mem-pbm25: w/l, p (Holm) | mem-cmm4 vs hybrid: w/l, p (Holm) |
|---|---|---|---|---|---|---|
| Haiku 4.5 | 216 | 90.3 (J 90.3) | 81.0 (J 80.1) | 69.0 (J 64.4) | 28/8, 0.0012 | 54/8, 3.4e-09 |
| GPT-6.1-sol | 216 | 99.1 (J 99.1) | 91.2 (J 91.2) | 71.8 (J 68.1) | 17/0, 1.5e-05 | 60/1, 1.1e-16 |
| Gemini 4 Argon | 216 | 91.2 (J 91.2) | 88.0 (J 88.0) | 73.6 (J 69.4) | 13/6, 0.17 | 42/4, 1e-08 |
| GPT-OSS 120B | 216 | 86.1 (J 83.8) | 85.6 (J 83.8) | 63.9 (J 56.9) | 16/15, 1 | 59/11, 8.9e-09 |

Accuracy in % over the questions (pairs for continuity) answered under every method of the task by that reader; continuity cells are pair accuracy with J = TPR - FPR in brackets.
