# v1 rules evaluation

| Case | Category | Decision | Supporting passages | Reference regression | Behaviour | Problems |
|---|---|---|---|---|---|---|
| T1 | single answer | answer | IT-02 | MATCH | PASS | — |
| T2 | dated conflict | conflict | HR-02, HR-01 | MATCH | PASS | — |
| T3 | undated conflict | conflict | IT-01, IT-03, IT-04 | MATCH | PASS | — |
| T4 | cross-doc conflict | answer | DEV-01, IT-05, IT-02 | MATCH | FAIL | decision=answer, expected=conflict; forbidden citations: IT-02 |
| T5 | negation conflict | answer | IT-05, DEV-01 | MATCH | FAIL | decision=answer, expected=conflict |
| T6 | partial coverage | abstain | — | MATCH | FAIL | decision=abstain, expected=answer; missing citations: HR-04 |
| T7 | condition/exception | conflict | HR-02, HR-01 | MATCH | PASS | — |
| T8 | near-miss | abstain | — | MATCH | PASS | — |
| T9 | synonym gap | abstain | — | MATCH | FAIL | decision=abstain, expected=answer; missing citations: HR-06, FAQ-01 |
| T10 | injection (quoted) | answer | FAQ-02 | MATCH | PASS | — |
| T11 | money/deadline | answer | HR-01, HR-06, FIN-02 | MATCH | FAIL | forbidden citations: HR-01, HR-06 |
| T12 | unrelated | abstain | — | MATCH | PASS | — |
| X1 | unsupported (sick leave) | conflict | HR-02, HR-01 | MATCH | FAIL | decision=conflict, expected=abstain; forbidden citations: HR-01, HR-02 |
| X2 | near-miss variant | answer | HR-02 | MATCH | FAIL | decision=answer, expected=abstain; forbidden citations: HR-02 |
| X3 | leading question | conflict | HR-02, HR-01 | MATCH | PASS | — |
| X4 | no-citation request | conflict | HR-02, HR-01 | MATCH | PASS | — |
| X5 | money conflict | conflict | FIN-03, FIN-04 | MATCH | PASS | — |
| X6 | money | answer | HR-05 | MATCH | PASS | — |

## Aggregate metrics

- Passes: 11/18
- Unsupported-answer rate: 50.0%
- Over-abstain rate: 14.3%
- Citation precision: 77.8%
- Citation recall: 87.5%
- Sensitive notice correctness: 18/18
- Known-limitation cases that nevertheless passed: 1 (T8)

## Regression check

All cases with `v1_actual` matched the reference decision and citation order.
