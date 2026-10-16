# v1 vs v2 comparison

| Case | v1 | v2 | v1 decision | v2 decision | v2 fallback |
|---|---|---|---|---|---|
| T1 | PASS | PASS | answer | answer | — |
| T2 | PASS | PASS | conflict | conflict | — |
| T3 | PASS | PASS | conflict | conflict | replay_miss |
| T4 | FAIL | PASS | answer | conflict | — |
| T5 | FAIL | PASS | answer | conflict | — |
| T6 | FAIL | PASS | abstain | answer | — |
| T7 | PASS | PASS | conflict | conflict | replay_miss |
| T8 | PASS | PASS | abstain | no_direct_support | — |
| T9 | FAIL | PASS | abstain | answer | — |
| T10 | PASS | PASS | answer | answer | validator_9_injection_artifact |
| T11 | FAIL | PASS | answer | answer | — |
| T12 | PASS | PASS | abstain | abstain | — |
| X1 | FAIL | PASS | conflict | no_direct_support | — |
| X2 | FAIL | PASS | answer | no_direct_support | — |
| X3 | PASS | PASS | conflict | conflict | replay_miss |
| X4 | PASS | PASS | conflict | conflict | — |
| X5 | PASS | PASS | conflict | conflict | — |
| X6 | PASS | PASS | answer | answer | — |

## Aggregate

| Metric | v1 | v2 |
|---|---:|---:|
| Passes | 11/18 | 18/18 |
| Unsupported-answer rate | 50.0% | 0.0% |
| Over-abstain rate | 14.3% | 0.0% |
| Citation precision | 77.8% | 92.3% |
| Citation recall | 87.5% | 100.0% |
| Fallback rate | — | 22.2% |

