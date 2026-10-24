
## Saga s7+s8, 0.5M, reader claude-claude-haiku-4-5-20251001
  mem-cmm4           n=459 acc=94.3 tokens=4,095
  mem-cmm4a          n=459 acc=95.2 tokens=6,166
  mem-cmm4_escU3     n=459 acc=95.9 tokens=4,878
  mem-pbm25          n=459 acc=88.2 tokens=3,974
  mem-pbm25_escU3    n=459 acc=90.4 tokens=5,381
  hybrid             n=459 acc=77.1 tokens=4,156
  hybrid_escU3       n=459 acc=81.9 tokens=6,198
  mem-cmm4a vs mem-cmm4_escU3: +4/-7 p=0.5488; difference -0.7 [-2.1, +0.7] (175 clusters)
  mem-cmm4_escU3 vs mem-cmm4: +8/-1 p=0.0391; difference +1.5 [+0.4, +2.8] (175 clusters)
  mem-cmm4_escU3 vs mem-pbm25_escU3: +30/-5 p=0.0000; difference +5.4 [+3.0, +8.2] (175 clusters)
  mem-cmm4_escU3 vs hybrid_escU3: +69/-5 p=0.0000; difference +13.9 [+10.8, +17.3] (175 clusters)
  mem-cmm4a vs mem-pbm25_escU3: +30/-8 p=0.0005; difference +4.8 [+2.0, +7.7] (175 clusters)
  mem-cmm4a vs hybrid_escU3: +68/-7 p=0.0000; difference +13.3 [+10.0, +16.6] (175 clusters)

## Saga s7+s8, 0.5M, reader ollama-qwen3-14b

## Saga s7+s8, 1.9M, reader claude-claude-haiku-4-5-20251001
  mem-cmm4           n=459 acc=89.3 tokens=4,135
  mem-cmm4a          n=459 acc=92.4 tokens=9,241
  mem-cmm4_escU3     n=459 acc=91.3 tokens=5,189
  mem-pbm25          n=459 acc=86.1 tokens=4,001
  mem-pbm25_escU3    n=459 acc=88.7 tokens=5,569
  hybrid             n=459 acc=72.8 tokens=4,165
  hybrid_escU3       n=459 acc=78.4 tokens=6,638
  mem-cmm4a vs mem-cmm4_escU3: +13/-8 p=0.3833; difference +1.1 [-0.7, +2.9] (175 clusters)
  mem-cmm4_escU3 vs mem-cmm4: +12/-3 p=0.0352; difference +2.0 [+0.2, +3.7] (175 clusters)
  mem-cmm4_escU3 vs mem-pbm25_escU3: +23/-11 p=0.0576; difference +2.6 [+0.2, +5.2] (175 clusters)
  mem-cmm4_escU3 vs hybrid_escU3: +68/-9 p=0.0000; difference +12.9 [+9.3, +16.4] (175 clusters)
  mem-cmm4a vs mem-pbm25_escU3: +28/-11 p=0.0095; difference +3.7 [+1.3, +6.2] (175 clusters)
  mem-cmm4a vs hybrid_escU3: +73/-9 p=0.0000; difference +13.9 [+10.6, +17.2] (175 clusters)

## Novels C, reader claude-claude-haiku-4-5-20251001
  mem-cmm4           n=349 acc=58.5 tokens=4,068
  mem-cmm4a          n=349 acc=70.5 tokens=11,719
  mem-cmm4_escU3     n=349 acc=62.5 tokens=4,938
  mem-pbm25          n=349 acc=56.2 tokens=3,950
  mem-pbm25_escU3    n=349 acc=61.0 tokens=5,449
  hybrid             n=349 acc=63.9 tokens=4,137
  hybrid_escU3       n=349 acc=67.9 tokens=5,050
  mem-cmm4a vs mem-cmm4_escU3: +44/-16 p=0.0004; difference +8.0 [+4.3, +12.3] (349 clusters)
  mem-cmm4_escU3 vs mem-cmm4: +14/-0 p=0.0001; difference +4.0 [+2.0, +6.3] (349 clusters)
  mem-cmm4_escU3 vs mem-pbm25_escU3: +36/-31 p=0.6254; difference +1.4 [-3.2, +6.0] (349 clusters)
  mem-cmm4_escU3 vs hybrid_escU3: +22/-41 p=0.0226; difference -5.4 [-10.0, -1.1] (349 clusters)
  mem-cmm4a vs mem-pbm25_escU3: +54/-21 p=0.0002; difference +9.5 [+4.9, +14.3] (349 clusters)
  mem-cmm4a vs hybrid_escU3: +36/-27 p=0.3135; difference +2.6 [-2.0, +6.9] (349 clusters)
