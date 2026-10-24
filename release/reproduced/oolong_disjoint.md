# Oolong-real test: episode overlap and episode-disjoint windows (Haiku reader, index minus BM25)

- 16- and 24-episode windows: 20; window pairs sharing an episode: 187 of 190; distinct episodes covered: 105 (2–115).

| windows | n windows | questions | mean of window means (index − BM25) | windows ahead |
|---|---|---|---|---|
| all 16+24 (primary set) | 20 | 400 | +0.204 | 20/20 |
| 1 episodes, disjoint (2, 6, 16, 19, 20, 54, 64, 72, 91, 101 first ep.) | 10 | 200 | +0.173 | 10/10 |
| 2 episodes, disjoint (2, 5, 6, 8, 16, 19, 31, 95 first ep.) | 8 | 160 | +0.227 | 8/8 |
| 3 episodes, disjoint (2, 5, 6, 13, 31, 56 first ep.) | 6 | 120 | +0.238 | 6/6 |
| 4 episodes, disjoint (2, 3, 5, 6, 19, 27, 28 first ep.) | 7 | 140 | +0.250 | 7/7 |
| 5 episodes, disjoint (2, 3, 5, 13, 19 first ep.) | 5 | 100 | +0.232 | 5/5 |
| 6 episodes, disjoint (2, 3, 7, 13 first ep.) | 4 | 80 | +0.285 | 4/4 |
| 7 episodes, disjoint (2, 3, 7, 28 first ep.) | 4 | 80 | +0.222 | 4/4 |
| 8 episodes, disjoint (2, 3, 5 first ep.) | 3 | 60 | +0.240 | 3/3 |
| 10 episodes, disjoint (2, 3, 7 first ep.) | 3 | 60 | +0.175 | 3/3 |
| 16 episodes, disjoint (2, 4 first ep.) | 2 | 40 | +0.199 | 2/2 |
| 24 episodes, disjoint (2 first ep.) | 1 | 20 | +0.182 | 1/1 |
| all sizes, disjoint, largest first | 2 | 40 | +0.188 | 2/2 |

Each disjoint set uses every episode at most once, so no episode is counted twice within a set; the sets are small, so they show direction rather than a tight interval.
