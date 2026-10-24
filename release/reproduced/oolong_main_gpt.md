| Method | 1 ep | 2 ep | 3 ep | 4 ep | 5 ep | 6 ep | 7 ep | 8 ep | 10 ep | 16 ep | 24 ep | all | 16+24 ep |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| index | 0.499 (200) | 0.370 (200) | 0.404 (200) | 0.367 (200) | 0.374 (200) | 0.401 (200) | 0.366 (200) | 0.363 (200) | 0.327 (200) | 0.311 (200) | 0.302 (200) | 0.371 (2200) | 0.307 (400) |
| bm25 | 0.357 (200) | 0.186 (200) | 0.180 (200) | 0.156 (200) | 0.152 (200) | 0.149 (200) | 0.143 (200) | 0.147 (200) | 0.107 (200) | 0.131 (200) | 0.125 (200) | 0.167 (2200) | 0.128 (400) |
| full | 0.644 (200) | 0.479 (200) | 0.513 (200) | – | – | – | – | – | – | – | – | 0.545 (600) | – |
| closed | 0.000 (200) | – | – | – | – | – | – | – | – | – | – | 0.000 (200) | – |

Paired differences, index minus each method (mean, 95% window-bootstrap interval):
- bm25: all +0.205 [+0.186, +0.223] (n=2200); 16+24 episodes +0.178 [+0.149, +0.209] (n=400)
- full: all -0.121 [-0.154, -0.087] (n=600)
- closed: all +0.499 [+0.445, +0.553] (n=200)

By question type (all windows):
- index: multidoc_rolls 0.256 (928), multidoc_spells 0.448 (1072), singledoc_rolls 0.412 (89), singledoc_spells 0.569 (111)
- bm25: multidoc_rolls 0.105 (928), multidoc_spells 0.185 (1072), singledoc_rolls 0.255 (89), singledoc_spells 0.438 (111)
- full: multidoc_rolls 0.338 (191), multidoc_spells 0.639 (209), singledoc_rolls 0.495 (89), singledoc_spells 0.764 (111)
- closed: singledoc_rolls 0.000 (89), singledoc_spells 0.000 (111)
