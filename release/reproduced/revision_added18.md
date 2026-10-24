Post-hoc baselines (main text, Table 6): exact two-sided McNemar on the win/loss counts of paper/tables_added_baselines.md, Holm over all 18 comparisons (3 baselines x 3 tasks x 2 readers).
| Task | Reader | Baseline | w/l | p | Holm p (18) |
|---|---|---|---|---|---|
| Event-type index | Haiku 4.5 | hippo2 | 20/5 | 0.0041 | 0.0082 |
| Event-type index | Haiku 4.5 | ctxhdr | 35/0 | 5.8e-11 | 7e-10 |
| Event-type index | Haiku 4.5 | s2b | 39/1 | 7.5e-11 | 7.5e-10 |
| Event-type index | GPT-6.1-sol | hippo2 | 18/6 | 0.023 | 0.023 |
| Event-type index | GPT-6.1-sol | ctxhdr | 36/2 | 5.4e-09 | 4.3e-08 |
| Event-type index | GPT-6.1-sol | s2b | 35/0 | 5.8e-11 | 7e-10 |
| State tracking | Haiku 4.5 | hippo2 | 36/10 | 0.00016 | 0.00078 |
| State tracking | Haiku 4.5 | ctxhdr | 82/7 | 2.4e-17 | 3.4e-16 |
| State tracking | Haiku 4.5 | s2b | 92/7 | 5.1e-20 | 8.6e-19 |
| State tracking | GPT-6.1-sol | hippo2 | 24/4 | 0.00018 | 0.00078 |
| State tracking | GPT-6.1-sol | ctxhdr | 73/2 | 1.5e-19 | 2.4e-18 |
| State tracking | GPT-6.1-sol | s2b | 83/1 | 8.8e-24 | 1.6e-22 |
| Continuity checking | Haiku 4.5 | hippo2 | 39/12 | 0.0002 | 0.00078 |
| Continuity checking | Haiku 4.5 | ctxhdr | 51/8 | 9.1e-09 | 6.3e-08 |
| Continuity checking | Haiku 4.5 | s2b | 53/6 | 1.8e-10 | 1.6e-09 |
| Continuity checking | GPT-6.1-sol | hippo2 | 26/1 | 4.2e-07 | 2.5e-06 |
| Continuity checking | GPT-6.1-sol | ctxhdr | 55/0 | 5.6e-17 | 7.2e-16 |
| Continuity checking | GPT-6.1-sol | s2b | 65/1 | 1.8e-18 | 2.7e-17 |
