
### fresh worlds 11-12 (after the v5 freeze)

| Method | Haiku 4.5: all / count 0 / count > 0 (tokens) | GPT-6.1-sol: all / count 0 / count > 0 (tokens) |
|---|---|---|
| event index v5 (frozen) | 78.7 / 92.3 / 75.8 (4,002) | 73.3 / 92.3 / 69.4 (4,002) |
|   same, no completeness statement | 76.0 / 84.6 / 74.2 (4,005) 2/0 | 70.7 / 84.6 / 67.7 (4,000) 3/1 |
|   same, no identity index | 58.7 / 84.6 / 53.2 (3,994) *17/2 | 58.7 / 92.3 / 51.6 (3,994) *13/2 |
| event index v4 | 76.0 / 92.3 / 72.6 (4,004) 2/0 | 70.7 / 92.3 / 66.1 (4,003) 2/0 |
| gold evidence paragraphs | 48.0 / 0.0 / 58.1 (197) *28/5 | 53.3 / 0.0 / 64.5 (197) *24/9 |
| CMM v4 | 44.0 / 76.9 / 37.1 (4,010) *27/1 | 42.7 / 69.2 / 37.1 (4,010) *27/4 |
| paragraph BM25 | 41.3 / 76.9 / 33.9 (4,002) *28/0 | 37.3 / 69.2 / 30.6 (4,002) *28/1 |
| hybrid RAG | 25.3 / 61.5 / 17.7 (4,177) *40/0 | 30.7 / 76.9 / 21.0 (4,177) *34/2 |

n = 75 questions per reader. w/l = questions the reference (first row) gets right and the method wrong / the reverse; * = Holm-corrected exact McNemar p < 0.05 over the 7 comparisons of each reader.

### worlds 9-10 (seen by v5)

| Method | Haiku 4.5: all / count 0 / count > 0 (tokens) | GPT-6.1-sol: all / count 0 / count > 0 (tokens) |
|---|---|---|
| event index v5 (frozen) | 76.0 / 92.3 / 72.6 (4,083) | 84.0 / 92.3 / 82.3 (4,084) |
|   same, no completeness statement | 72.0 / 53.8 / 75.8 (4,082) 6/3 | 82.7 / 76.9 / 83.9 (4,083) 3/2 |
|   same, no identity index | 54.7 / 76.9 / 50.0 (4,002) *20/4 | 61.3 / 92.3 / 54.8 (4,002) *19/2 |
| event index v4 | 68.0 / 92.3 / 62.9 (4,085) 8/2 | 73.3 / 92.3 / 69.4 (4,084) *8/0 |
| gold evidence paragraphs | 54.7 / 0.0 / 66.1 (182) 30/14 | 60.0 / 0.0 / 72.6 (182) *28/10 |
| CMM v4 | 41.3 / 61.5 / 37.1 (4,097) *31/5 | 42.7 / 61.5 / 38.7 (4,097) *36/5 |
| paragraph BM25 | 44.0 / 69.2 / 38.7 (3,979) *28/4 | 46.7 / 76.9 / 40.3 (3,979) *32/4 |
| hybrid RAG | 28.0 / 76.9 / 17.7 (4,178) *38/2 | 28.0 / 69.2 / 19.4 (4,178) *46/4 |

n = 75 questions per reader. w/l = questions the reference (first row) gets right and the method wrong / the reverse; * = Holm-corrected exact McNemar p < 0.05 over the 7 comparisons of each reader.

### worlds 7-8 (seen)

| Method | Haiku 4.5: all / count 0 / count > 0 (tokens) | GPT-6.1-sol: all / count 0 / count > 0 (tokens) |
|---|---|---|
| event index v5 (frozen) | 83.1 / 86.7 / 82.3 (4,014) | 85.7 / 93.3 / 83.9 (4,014) |
|   same, no completeness statement | 87.0 / 86.7 / 87.1 (4,015) 3/6 | 87.0 / 86.7 / 87.1 (4,016) 1/2 |
|   same, no identity index | 72.7 / 80.0 / 71.0 (3,994) 11/3 | 75.3 / 86.7 / 72.6 (3,994) 10/2 |
| event index v4 | 77.9 / 86.7 / 75.8 (4,017) 6/2 | 80.5 / 93.3 / 77.4 (4,017) 5/1 |
| gold evidence paragraphs | 59.7 / 0.0 / 74.2 (189) *24/6 | 64.9 / 0.0 / 80.6 (189) *22/6 |
| CMM v4 | 48.1 / 73.3 / 41.9 (4,027) *30/3 | 50.6 / 73.3 / 45.2 (4,027) *31/4 |
| paragraph BM25 | 40.3 / 73.3 / 32.3 (3,985) *36/3 | 41.6 / 80.0 / 32.3 (3,985) *39/5 |
| hybrid RAG | 33.8 / 93.3 / 19.4 (4,174) *41/3 | 28.6 / 73.3 / 17.7 (4,174) *46/2 |

n = 77 questions per reader. w/l = questions the reference (first row) gets right and the method wrong / the reverse; * = Holm-corrected exact McNemar p < 0.05 over the 7 comparisons of each reader.

### Event-tagger recall of the world's events and wrong zeros (event index v4)

| World | deaths found | births found | weddings found | wrong zeros Haiku / GPT |
|---|---|---|---|---|
| agg2_s11 | 22/23 | 12/12 | 16/17 | 0 / 0 |
| agg2_s12 | 15/15 | 21/21 | 17/17 | 0 / 0 |
| agg2_s9 | 18/18 | 19/19 | 13/14 | 0 / 0 |
| agg2_s10 | 23/24 | 20/20 | 16/17 | 0 / 0 |
| agg2_s7 | 13/14 | 30/31 | 18/18 | 0 / 0 |
| agg2_s8 | 15/15 | 21/21 | 18/18 | 0 / 0 |

A gold event paragraph is found if the tagger gave it a narrated event of a kind the router chose for questions about that event (all questions of the world pooled).

### Selected event set against the gold evidence, per question (event index v4)

| Worlds | questions | statement given | statement true (all gold selected) | gold paragraphs selected | extra paragraphs selected |
|---|---|---|---|---|---|
| fresh worlds 11-12 (after the v5 freeze) | 75 | 75 | 62 | 292/307 | 229 |
  complete selection by question type: G2_FAM_BIRTHS 12/12, G2_FAM_DEATHS 7/9, G2_FAM_WED 7/8, G2_NBIRTHS 2/2, G2_NDEATHS 0/2, G2_NWED 1/2, G2_RANGE_DEATHS 2/8, G2_RANGE_WED 8/8, G_PLACE_BIRTHS 12/12, G_PLACE_DEATHS 11/12
| worlds 9-10 (seen by v5) | 75 | 75 | 68 | 272/279 | 276 |
  complete selection by question type: G2_FAM_BIRTHS 12/12, G2_FAM_DEATHS 7/8, G2_FAM_WED 9/9, G2_NBIRTHS 2/2, G2_NDEATHS 1/2, G2_NWED 1/2, G2_RANGE_DEATHS 8/8, G2_RANGE_WED 5/8, G_PLACE_BIRTHS 12/12, G_PLACE_DEATHS 11/12
| worlds 7-8 (seen) | 77 | 77 | 70 | 284/291 | 280 |
  complete selection by question type: G2_FAM_BIRTHS 12/12, G2_FAM_DEATHS 9/10, G2_FAM_WED 8/9, G2_NBIRTHS 1/2, G2_NDEATHS 1/2, G2_NWED 2/2, G2_RANGE_DEATHS 7/8, G2_RANGE_WED 8/8, G_PLACE_BIRTHS 11/12, G_PLACE_DEATHS 11/12
