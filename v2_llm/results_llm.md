# v2 LLM evaluation

| Case | Category | Decision | Supporting passages | Fallback | Behaviour | Problems |
|---|---|---|---|---|---|---|
| T1 | single answer | answer | IT-02 | — | PASS | — |
| T2 | dated conflict | conflict | HR-02, HR-01 | — | PASS | — |
| T3 | undated conflict | conflict | IT-01, IT-03, IT-04 | replay_miss | PASS | — |
| T4 | cross-doc conflict | conflict | DEV-01, IT-05 | — | PASS | — |
| T5 | negation conflict | conflict | DEV-01, IT-05 | — | PASS | — |
| T6 | partial coverage | answer | HR-04, DEV-02 | — | PASS | — |
| T7 | condition/exception | conflict | HR-02, HR-01 | replay_miss | PASS | — |
| T8 | near-miss | no_direct_support | — | — | PASS | — |
| T9 | synonym gap | answer | HR-01, HR-06, FAQ-01 | — | PASS | — |
| T10 | injection (quoted) | answer | FAQ-02 | validator_9_injection_artifact | PASS | — |
| T11 | money/deadline | answer | FIN-02 | — | PASS | — |
| T12 | unrelated | abstain | — | — | PASS | — |
| X1 | unsupported (sick leave) | no_direct_support | — | — | PASS | — |
| X2 | near-miss variant | no_direct_support | — | — | PASS | — |
| X3 | leading question | conflict | HR-02, HR-01 | replay_miss | PASS | — |
| X4 | no-citation request | conflict | HR-02, HR-01 | — | PASS | — |
| X5 | money conflict | conflict | FIN-03, FIN-04 | — | PASS | — |
| X6 | money | answer | HR-05 | — | PASS | — |

## Aggregate metrics

- Passes: 18/18
- Unsupported-answer rate: 0.0%
- Over-abstain rate: 0.0%
- Citation precision: 92.3%
- Citation recall: 100.0%
- Sensitive notice correctness: 18/18
- Fallback rate: 22.2%
- Claims per answer: 1.64
- Number-fidelity violations: 0
- `must_not_claim_regex` violations: 0
- Failed validator counts: validator_9_injection_artifact=1
