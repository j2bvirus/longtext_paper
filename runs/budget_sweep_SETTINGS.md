# Budget sweep with GPT-6.1 Sol and Claude Sonnet 5.5: reasoning and thinking settings

Run script: runs/budget_sweep_gpt_sonnet.sh; analysis: methods/budget_sweep_report.py.

| Reader | Model ID | Access | Reasoning / effort | Thinking | Budgets run here |
|---|---|---|---|---|---|
| GPT-6.1 Sol | gpt-6.1-sol | Codex command-line client (`codex exec ... -c model_reasoning_effort="low"`), as every GPT reader run | reasoning effort low | the model's own reasoning at the low setting | 2k, 8k, 16k (4k from the main study) |
| Claude Sonnet 5.5 | claude-sonnet-5-5 | Claude Code command-line client 2.1.304, as every Claude reader run (methods/llm.py) | effort high (client settings file `effortLevel: "high"`, the model's API default) | adaptive: the model's thinking is set by the effort level, and it has no separate thinking budget; prompt caching off | 2k, 4k, 8k, 16k |
| Claude Haiku 4.5 (earlier sweep) | claude-haiku-4-5-20251001 | as above | none (the model has no effort setting) | off (MAX_THINKING_TOKENS=0) | 2k, 4k, 8k, 16k |

Common to all: state tracking on worlds T1-T2 (saga_v5_s7, saga_v5_s8, density d16, 459 questions); CMM v4, paragraph
BM25 and hybrid retrieval; the default reader prompt; memories built by Claude Haiku 4.5 (cached); dense embeddings from
the stored caches; each question answered once per condition.
