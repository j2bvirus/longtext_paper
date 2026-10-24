# Judge check: who judged, with which reasoning and thinking settings

Code: methods/judge_check.py; sample:
data/judge_check/sample.json (255 answers; primary analysis on the 238 without a detected gold problem).

| Judge | Model ID | Access | Reasoning / effort | Thinking | Prompt and output | Verdicts |
|---|---|---|---|---|---|---|
| Primary judge | gpt-6.1-sol | Codex command-line client (`codex exec ... -c model_reasoning_effort="low"`, empty working directory, user config and rules ignored) | reasoning effort low | the model's own reasoning at the low setting | methods/judge.py: `SYS` for novels and LoCoMo, the AMA-Bench wording `AMA_JUDGE` for ama_*; one word read (correct / yes) | runs/judged_gpt/ |
| Blind second judgment (earlier check) | gpt-6.1-sol | Codex command-line client, reading question, gold answer and prediction directly | reasoning effort high | the model's own reasoning at the high setting | direct reading against the same criteria (a 150-answer and a 300-answer sample) | `gpt_high_blind` in data/judge_check/sample.json |
| First judge (reference only) | claude-haiku-4-5-20251001 | Claude Code command-line client | none (the model has no effort setting) | off (MAX_THINKING_TOKENS=0) | same prompts as the primary judge | runs/judged/ |
| New judge of another family | claude-sonnet-5-5 | Claude Code command-line client 2.1.304: `-p --model claude-sonnet-5-5 --output-format json --system-prompt <prompt> --tools "" --strict-mcp-config --no-session-persistence --exclude-dynamic-system-prompt-sections` (methods/llm.py) | effort high (client settings file `effortLevel: "high"` at run time, the model's API default; no per-model override for Sonnet) | adaptive: the model's thinking is set by the effort level (it has no separate thinking budget); prompt caching off (DISABLE_PROMPT_CACHING=1) | same prompts and reading as the primary judge; no output limit passed to the client | runs/judge_check/claude-claude-sonnet-5-5.json |
| Person (author) | – | one of the authors; local page paper/human_judge/index.html (not released: it holds third-party text) | – | – | 102 answers (17 per domain, seed 0), shown in mixed order with question, gold answer and model answer only; method, reader and every model verdict hidden; labels correct / incorrect / cannot tell | paper/human_judge/labels.json; released as ids and labels only in data/judge_check/person_labels.json (first-judge verdicts of the sample likewise in data/judge_check/haiku_first_judge.json) |

## Claude Sonnet 5.5 run

- 255 answers: 13 empty or "unknown" predictions scored 0 without a call (as in methods/judge.py); 40 prompts were
  identical to earlier Claude Sonnet 5.5 judge calls of Supplementary Appendix C (same model, effort high, same prompt)
  and were answered from the call cache; 202 new calls, 0 errors.
- New calls: 228,734 input tokens and 2,468 output tokens in total (about 1,130 and 12 per call, client overhead
  included), USD 0.48 at list price; output of one word, so no visible thinking.
- Verdicts: runs/judge_check/claude-claude-sonnet-5-5.json; report: python methods/judge_check.py report.

## Further annotators

- Three people besides the author above, who are not authors of the paper (colleagues of one author). All four people hold a bachelor's degree.
- Pages paper/human_judge/index_A.html, index_B.html, index_C.html (local, not released): the same 102 answers and the same
  instructions as the author's page, each with its own storage key, export file (labels_<X>.json) and random order.
- Their labels are kept as ids and labels only in data/judge_check/person_labels_<X>.json. Analysis: every pair of judges
  and people (agreement, Cohen's kappa), Fleiss' kappa among the four people on the answers all decided, and the majority of
  the people who decided an answer (ties give no majority) against each model judge.

## Instructions on the labelling page

Each item shows its number, the kind of record (novel or conversation record / agent record (AMA)), the question, the
gold answer and the model answer. The instructions at the top read:

- Novels and conversation records: the model answer is *correct* if it conveys the same answer as the gold answer
  (paraphrases, synonyms and answers containing the gold answer's essential content are correct). It is *incorrect* if
  it differs from the gold answer, contradicts it, is "unknown", or hedges between several answers.
- Agent records (AMA): *correct* if, compared with the gold answer, the facts are right, nothing is missing and the
  answer fits the question; otherwise *incorrect*.
- If the gold answer itself looks odd or the item cannot be judged: *cannot tell*. Labels are saved in the browser;
  at the end, "export results" writes the file. Keys: 1 correct, 2 incorrect, 3 cannot tell.

These follow the primary judge's prompts (methods/judge.py: SYS and AMA_JUDGE). The page template and its item labels
are kept with the local pages (paper/human_judge/page_template.html and page_labels.json, not released).
