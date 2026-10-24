CMM v4 minus another method on worlds T1-T2 (459 questions, 0.5M, 4k budget), accuracy points, with 95% intervals from a bootstrap over clusters (20,000 resamples, seed 0). Clusters: each question alone; questions that share any core gold evidence event; questions that share any gold evidence event (evidence closed over the references needed to interpret it), linked transitively within a world.
Clusters: 459 questions; core evidence 193 clusters (largest 102); all evidence 121 clusters (largest 170).

| Reader | Comparison | Difference | Per question | Core-evidence clusters | All-evidence clusters |
|---|---|---|---|---|---|
| Haiku 4.5 | CMM v4 − Paragraph BM25 | +6.1 | [+3.3, +9.2] | [+0.4, +9.2] | [-1.5, +9.5] |
| Haiku 4.5 | CMM v4 − Hybrid retrieval | +17.2 | [+13.3, +21.1] | [+11.9, +20.4] | [+6.7, +20.0] |
| GPT-6.1 Sol | CMM v4 − Paragraph BM25 | +6.1 | [+3.7, +8.5] | [+0.8, +9.2] | [+0.0, +8.3] |
| GPT-6.1 Sol | CMM v4 − Hybrid retrieval | +14.2 | [+10.9, +17.4] | [+9.5, +17.2] | [+4.3, +17.1] |
| Gemini 4 Argon | CMM v4 − Paragraph BM25 | +5.9 | [+3.7, +8.3] | [+0.8, +8.5] | [+0.0, +7.9] |
| Gemini 4 Argon | CMM v4 − Hybrid retrieval | +16.3 | [+13.1, +19.8] | [+12.1, +19.2] | [+5.0, +19.1] |
| gpt-oss-120b | CMM v4 − Paragraph BM25 | +9.2 | [+6.1, +12.4] | [+4.4, +12.1] | [+3.5, +12.2] |
| gpt-oss-120b | CMM v4 − Hybrid retrieval | +15.7 | [+12.0, +19.6] | [+10.9, +18.7] | [+6.9, +18.0] |
