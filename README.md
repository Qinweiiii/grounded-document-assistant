# Grounded document assistant

This bounded assessment project compares a deterministic extractive assistant (v1) with an LLM-assisted, code-validated assistant (v2). Both use the same 26 supplied passages and 18 supplied evaluation cases. No real company or sensitive data is used.

## Run commands

Python 3.10+ is required. Run commands from this directory.

```bash
cd doc-assistant

# v1 rules and generated report
python3 v1_rules/run_eval_rules.py

# v2 offline replay (default mode; replay misses safely fall back to v1)
python3 v2_llm/run_eval_llm.py --replay

# v2 live, fixed to qwen3.8-27b on Alibaba Cloud Model Studio Beijing
export DASHSCOPE_API_KEY="YOUR_API_KEY"
python3 v2_llm/run_eval_llm.py --live

# Optional: send all 26 passages instead of the top eight non-zero lexical matches
python3 v2_llm/run_eval_llm.py --replay --full-corpus

# Same-case comparison and all offline tests
python3 compare.py --replay
python3 -m unittest discover -s tests -v
```

The fixed configuration in `v2_llm/config.py` uses Alibaba Cloud Model Studio's Beijing endpoint with `qwen3.8-27b`. `DASHSCOPE_API_KEY` supplies the only required secret. Live mode records the raw response and metadata under `v2_llm/recorded_outputs/`. Replay uses the configured model name because it is part of the cache key. `--cases heldout_cases.json` runs the optional held-out set. `heldout_cases.json` intentionally starts empty so cases can be written only after both versions are frozen.

## Design principles

1. Never present unsupported content as document content.
2. Preserve numbers, dates, amounts, conditions, exceptions, and prohibitions.
3. Show conflicting passages side by side, newest dated source first and undated sources last; never choose a winner.
4. Add a fixed owner-confirmation notice to money and deadline topics.
5. Treat passage text as data, including instruction-like or prompt-injection text.
6. Prefer a clearly qualified, source-backed partial answer over guessing or hiding useful text.

Assumptions: a recorded date is useful for ordering but does not prove validity; document owners, authority levels, and supersession relationships are unknown; English translations and rounded currency values are treated as supplied data rather than independently verified facts.

## v1 design

v1 is a standard-library port of `reference_v1_assistant.py`. It tokenises `[a-z0-9]+`, removes the fixed stop-word list, applies light stemming, and scores each passage by the fraction of question content words present. The support threshold remains 0.6 and non-conflict answers show at most three passages.

Numeric conflicts share a unit but contain different values. They are quoted in date order. Other supported answers quote full passages verbatim. Unsupported queries abstain. Instruction-like passages are labelled, and money/deadline matches receive a fixed confirmation notice.

The regression table in `v1_rules/results_rules.md` must match every `v1_actual` decision and citation list. Known mistakes are retained rather than tuned away.

## v1 limitations with evidence

- T4 and T5: numeric-only conflict detection misses allow-versus-forbid conflicts; T4 also cites IT-02 unnecessarily.
- T6: the 0.6 threshold rejects a useful partial answer about working hours.
- T9: lexical matching cannot connect `request` in HR-06 with `vacation` in FAQ-01.
- T11: equal lexical scores admit unrelated leave-request passages beside the reimbursement deadline.
- X1 and X2: high word overlap makes annual/paid-leave text look like support for sick or unpaid leave.
- T8 passes only because an extra unmatched word lowers its score; this is brittle rather than semantic understanding.

These are visible in the generated v1 report and are not claims about unseen data.

## Why add an LLM layer

Semantic gaps such as T9 require recognising related wording across passages. Judgement failures such as X1 require distinguishing “same topic” from “answers the question.” T4/T5 require recognising a permission/prohibition conflict without relying on matching numbers. T6 requires separating the supported and unsupported halves of a question.

An LLM may still miss a candidate because retrieval uses lexical overlap, misunderstand qualifiers, omit a conflicting version, or produce malformed output. Full-corpus mode reduces retrieval misses but increases prompt size and exposure to irrelevant or adversarial text. It does not prove correctness.

The new risks are meaning drift, prompt-injection exposure, provider variability, non-determinism despite temperature zero, and dependence on a remote service. Deterministic validators, verbatim evidence, cached raw responses, full source rendering, and v1 fallback limit rather than eliminate those risks.

## v2 design

1. Retrieve the top eight passages with lexical score greater than zero, or all passages with `--full-corpus`.
2. Ask the model for JSON passage assessments, claims with exact evidence quotes, uncovered topics, and semantic conflicts.
3. Validate schema, evidence IDs, exact quotes, number fidelity, relation labels, winner-picking language, missing-topic disclosure, numeric-conflict completeness, and injection artefacts.
4. On any validation, provider, configuration, or replay failure, discard all model text and render v1 with a machine-readable fallback reason.
5. Otherwise determine answer/conflict/no-direct-support/abstain in code. Code also controls source ordering, risk notices, sensitive-topic detection, and full passage quotes.

`v2_llm/human_review.csv` contains one row per accepted claim so a reviewer can label meaning drift. Automated quote matching establishes textual support, not preservation of meaning.

## Results

- v1: **TO BE FILLED AFTER RUN** — use `v1_rules/results_rules.md`.
- v2 replay/live: **TO BE FILLED AFTER RUN** — use `v2_llm/results_llm.md`.
- comparison: **TO BE FILLED AFTER RUN** — use `python3 compare.py`.
- human meaning-drift review: **TO BE FILLED AFTER RUN**.

No real-model performance is claimed until a live run is recorded, replayed, and manually reviewed. Code-generated result files, not this README, are the source of measured numbers.

## Decision journal

### Priorities and values

I prioritise preventing a colleague from mistaking plausible prose for policy while still exposing useful original text. That leads to extractive sources, explicit gaps, and qualified partial answers. The primary user need is a fast path to relevant policy text without concealing uncertainty.

### Tradeoff and stakeholder judgement

For an R&D employee asking about personal computers (T4), IT-05 permits access after approval while DEV-01 forbids it for R&D. Abstaining hides useful evidence, and selecting one assumes an authority hierarchy not present in the corpus. I show both without preference so the employee can escalate the concrete conflict to the owners before accessing internal documents.

### Judgement under uncertainty

For an urgent reimbursement deadline (T11), I accept the limited risk of displaying the exact dated passage because delay also has a cost. I do not accept the risk of paraphrasing the deadline or implying that it is unquestionably operative. The fixed notice asks the user to confirm with the owner. Evidence of supersession, document authority, or owner confirmation would change that decision.

### Ownership and reflection

I retained v1's X1 failure in the regression target instead of hiding it, then designed v2 so annual-leave passages can be shown only as related text rather than evidence for sick leave. Reviewing that case reinforced that lexical overlap is retrieval evidence, not answer support. A human reviewer should still examine accepted claims for meaning drift.

## Known limitations

- The corpus is tiny, English-only, and hand-curated; results do not establish production quality.
- Lexical candidate retrieval has no synonym expansion and may omit the passage an LLM would need.
- Dates order conflicts but do not establish authority, validity, or supersession.
- Exact-substring and number checks cannot prove that a paraphrase preserves meaning or all qualifiers.
- The injection artefact check targets patterns and payloads represented in this corpus, not every attack.
- Live API compatibility, latency, rate limits, privacy controls, and real-model performance require separate verification.
- No authentication, access control, document lifecycle, owner lookup, or production integration is included.
- Held-out cases and manual meaning-drift labels remain for the author to add after freezing both versions.

## AI-assistance disclosure

ChatGPT generated the implementation and documentation from the author's detailed specification. The supplied corpus, evaluation cases, reference v1 behaviour, risk stance, and acceptance rules were author-provided. The author should review the decision journal, run outputs, and code and be prepared to defend the choices independently.
