
### Event-type index, G2 counting, fresh worlds 11-12

| Reader | n | mem-evx4v5 | oracle_para | mem-cmm4 | mem-pbm25 | hybrid | mem-hippo2 | mem-ctxhdr | mem-s2b | mem-evx4v5 vs oracle_para: w/l, p (Holm) | mem-evx4v5 vs mem-cmm4: w/l, p (Holm) | mem-evx4v5 vs mem-pbm25: w/l, p (Holm) | mem-evx4v5 vs hybrid: w/l, p (Holm) | mem-evx4v5 vs mem-hippo2: w/l, p (Holm) | mem-evx4v5 vs mem-ctxhdr: w/l, p (Holm) | mem-evx4v5 vs mem-s2b: w/l, p (Holm) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | 75 | 78.7 | 48.0 | 44.0 | 41.3 | 25.3 | 58.7 | 32.0 | 28.0 | 28/5, 0.00013 | 27/1, 6.5e-07 | 28/0, 3e-08 | 40/0, 1.3e-11 | 20/5, 0.0041 | 35/0, 3.5e-10 | 39/1, 3.7e-10 |
| GPT-6.1-sol | 75 | 73.3 | 53.3 | 42.7 | 37.3 | 30.7 | 57.3 | 28.0 | 26.7 | 24/9, 0.027 | 27/4, 0.0001 | 28/1, 4.5e-07 | 34/2, 9.7e-08 | 18/6, 0.027 | 36/2, 3.2e-08 | 35/0, 4.1e-10 |

Accuracy in % over the questions (pairs for continuity) answered under every method of the task by that reader; continuity cells are pair accuracy with J = TPR - FPR in brackets.

### State tracking, worlds 7-8, about 0.5M tokens

| Reader | n | mem-cmm4 | mem-pbm25 | hybrid | mem-hippo2 | mem-ctxhdr | mem-s2b | mem-cmm4 vs mem-pbm25: w/l, p (Holm) | mem-cmm4 vs hybrid: w/l, p (Holm) | mem-cmm4 vs mem-hippo2: w/l, p (Holm) | mem-cmm4 vs mem-ctxhdr: w/l, p (Holm) | mem-cmm4 vs mem-s2b: w/l, p (Holm) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | 459 | 94.3 | 88.2 | 77.1 | 88.7 | 78.0 | 75.8 | 38/10, 0.00012 | 87/8, 2.7e-17 | 36/10, 0.00016 | 82/7, 7.3e-17 | 92/7, 2.5e-19 |
| GPT-6.1-sol | 459 | 96.7 | 90.6 | 82.6 | 92.4 | 81.3 | 78.9 | 31/3, 1.5e-06 | 67/2, 2.5e-17 | 24/4, 0.00018 | 73/2, 6e-19 | 83/1, 4.4e-23 |

Accuracy in % over the questions (pairs for continuity) answered under every method of the task by that reader; continuity cells are pair accuracy with J = TPR - FPR in brackets.

### Continuity checking, worlds 7-8 (pairs)

| Reader | n | mem-cmm4 | mem-pbm25 | hybrid | mem-hippo2 | mem-ctxhdr | mem-s2b | mem-cmm4 vs mem-pbm25: w/l, p (Holm) | mem-cmm4 vs hybrid: w/l, p (Holm) | mem-cmm4 vs mem-hippo2: w/l, p (Holm) | mem-cmm4 vs mem-ctxhdr: w/l, p (Holm) | mem-cmm4 vs mem-s2b: w/l, p (Holm) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 | 216 | 90.3 (J 90.3) | 81.0 (J 80.1) | 69.0 (J 64.4) | 77.8 (J 76.4) | 70.4 (J 67.1) | 68.5 (J 64.4) | 28/8, 0.0012 | 54/8, 6.8e-09 | 39/12, 0.0004 | 51/8, 2.7e-08 | 53/6, 8.8e-10 |
| GPT-6.1-sol | 216 | 99.1 (J 99.1) | 91.2 (J 91.2) | 71.8 (J 68.1) | 87.5 (J 87.0) | 73.6 (J 71.3) | 69.4 (J 68.1) | 17/0, 1.5e-05 | 60/1, 2.2e-16 | 26/1, 8.3e-07 | 55/0, 2.2e-16 | 65/1, 9.1e-18 |

Accuracy in % over the questions (pairs for continuity) answered under every method of the task by that reader; continuity cells are pair accuracy with J = TPR - FPR in brackets.
