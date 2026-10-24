# Post-hoc baselines: settings

Code: `methods/addedbase.py`,
`methods/build_added.py`, `methods/added_baselines_report.py`.

## Common conditions (as for the other baselines)

- Reading: `methods/run_eval.py`, the same reader prompt, 4,000 tokens per question.
- Paragraph unit: the same paragraphs as paragraph BM25 and the entity index.
- Embeddings: `qwen3-embedding:0.6b` (Ollama), as for hybrid retrieval. HippoRAG 2 used NV-Embed-v2 (7B); the
  difference is stated in the paper.
- Builder: GPT-6.1 Sol. The other built baselines were built by Claude Haiku 4.5; giving these baselines a stronger
  builder works against our method.
- Data and questions: state tracking on worlds T1–T2 (saga_v5_s7, saga_v5_s8, density 16, 459 questions); continuity
  on cont2_s7 and cont2_s8 (216 pairs, the same record text, so built memories are shared); event counting on agg2_s11
  and agg2_s12 (worlds E3–E4, 75 questions). Oolong is out of scope.
- Readers: Claude Haiku 4.5 (primary), GPT-6.1 Sol (secondary).
- Scoring: as for every other condition.
- Analysis: exact McNemar tests against the entity index (CMM v4) and the event index (v5); Holm correction over the
  comparisons of the added baselines only.

## A. `hippo2`: HippoRAG 2 re-implementation (Gutiérrez et al., 2025, Section 3 and Appendix G.1)

Build
- One call per ten paragraphs; for each paragraph, free-form (subject, relation, object) triples with the paragraph
  number. The paper ran OpenIE per paragraph; batching is for cost, and each triple keeps its source paragraph.
- Graph nodes: concepts (subject and object phrases) and paragraphs.
- Edges: relation edges (subject–object); synonym edges where the concept embeddings have cosine similarity of at least
  0.8 (paper, Table 13); containment edges between a paragraph and the concepts taken from it.

Query
1. Choose the top 5 triples by question embedding (paper, Section 4.4).
2. Recognition memory: the builder (GPT) removes triples unrelated to the question (the role in the paper's Section 3.4,
   following the intent of the prompt in its Appendix A).
3. From the remaining triples choose at most 5 concept seed nodes, scored by the mean score of the triples in which the
   concept occurs.
4. Every paragraph node is also a seed; its reset probability is its question-embedding similarity times 0.05 (paper,
   Table 5 and Section 6.2).
5. Personalised PageRank with damping 0.5 (Table 13), computed by power iteration on a scipy sparse matrix (the paper
   used python-igraph).
6. Fill 4,000 tokens with paragraphs in PageRank order and show them in record order.
7. If no triple remains after filtering, choose paragraphs by embedding rank (Appendix G.1).

The recognition-memory call is counted as query-time cost.

## B. `ctxhdr`: contextual retrieval (Anthropic's Contextual Retrieval)

- Build: for every 300-token chunk (the chunks of hybrid retrieval), write a one- or two-sentence header saying where
  in the record the chunk is and what it is about; the text itself is not changed. The whole record (about 0.5M
  tokens) does not fit one call, so the builder sees about 3,000 tokens of the preceding text together with ten chunks
  and writes a header for each chunk number.
- Retrieval: BM25 and embeddings over "header + chunk", fused by reciprocal rank fusion (as in hybrid retrieval).
- Reading: headers are shown with the original chunks and count towards the budget.

## C. `s2b`: small-to-big retrieval

- Retrieval unit: the paragraph; BM25 and paragraph embeddings fused by reciprocal rank fusion.
- Reading: each retrieved paragraph is shown with its neighbouring paragraphs, about 500 tokens of original text on
  each side; overlapping windows are merged; up to 4,000 tokens.
- No builder model is needed.
