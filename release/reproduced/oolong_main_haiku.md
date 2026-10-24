full: 20 of 600 questions infeasible (the reader could not read the window); left out below
| Method | 1 ep | 2 ep | 3 ep | 4 ep | 5 ep | 6 ep | 7 ep | 8 ep | 10 ep | 16 ep | 24 ep | all | 16+24 ep |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| index | 0.524 (200) | 0.417 (200) | 0.409 (200) | 0.389 (200) | 0.371 (200) | 0.398 (200) | 0.377 (200) | 0.375 (200) | 0.342 (200) | 0.330 (200) | 0.335 (200) | 0.388 (2200) | 0.333 (400) |
| index_bSonnet | 0.617 (200) | 0.531 (200) | 0.495 (200) | 0.493 (200) | 0.436 (200) | 0.464 (200) | 0.417 (200) | 0.397 (200) | 0.390 (200) | 0.379 (200) | 0.338 (200) | 0.451 (2200) | 0.358 (400) |
| bm25 | 0.351 (200) | 0.197 (200) | 0.166 (200) | 0.150 (200) | 0.150 (200) | 0.151 (200) | 0.154 (200) | 0.149 (200) | 0.117 (200) | 0.142 (200) | 0.116 (200) | 0.168 (2200) | 0.129 (400) |
| full | 0.553 (200) | 0.267 (200) | 0.164 (180) | – | – | – | – | – | – | – | – | 0.334 (580) | – |
| closed | 0.000 (200) | – | – | – | – | – | – | – | – | – | – | 0.000 (200) | – |

Paired differences, index minus each method (mean, 95% window-bootstrap interval):
- index_bSonnet: all -0.063 [-0.080, -0.047] (n=2200); 16+24 episodes -0.026 [-0.060, +0.007] (n=400)
- bm25: all +0.220 [+0.202, +0.239] (n=2200); 16+24 episodes +0.204 [+0.176, +0.232] (n=400)
- full: all +0.113 [+0.050, +0.174] (n=580)
- closed: all +0.524 [+0.463, +0.582] (n=200)

By question type (all windows):
- index: multidoc_rolls 0.277 (928), multidoc_spells 0.458 (1072), singledoc_rolls 0.458 (89), singledoc_spells 0.576 (111)
- index_bSonnet: multidoc_rolls 0.339 (928), multidoc_spells 0.517 (1072), singledoc_rolls 0.556 (89), singledoc_spells 0.667 (111)
- bm25: multidoc_rolls 0.124 (928), multidoc_spells 0.171 (1072), singledoc_rolls 0.280 (89), singledoc_spells 0.408 (111)
- full: multidoc_rolls 0.144 (180), multidoc_spells 0.285 (200), singledoc_rolls 0.470 (89), singledoc_spells 0.620 (111)
- closed: singledoc_rolls 0.000 (89), singledoc_spells 0.000 (111)
