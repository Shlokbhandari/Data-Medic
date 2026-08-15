# DataMedic — Failure Benchmark

This file tracks every failure scenario DataMedic is expected to handle, and what "success" looks like for each one. It's used to measure progress as the project grows.

| Failure Type | Description | Expected Diagnosis | Expected Fix | Expected Validation Result | Status |
|---|---|---|---|---|---|
| Duplicate transaction ID | Two rows share the same `transaction_id` | Duplicate `transaction_id` detected, likely caused by an upstream retry or resend | Resolve deterministically by sorting on `order_date` and keeping the row with the earliest date; do not leave selection arbitrary | No duplicate `transaction_id`s remain, the kept row has the earliest `order_date`, row count drops by exactly the number of duplicates | Detected, diagnosed, patched, validated, and proposed via a real pull request ([PR #1](https://github.com/Shlokbhandari/Data-Medic/pull/1)) |
| Missing price | A row has a null/empty `price` value | Missing price value, likely an incomplete upstream record | Exclude the row from the normal output so it isn't processed downstream, but preserve it by writing it to a separate `data/flagged_orders.csv` file with a `flag_reason` of "missing price"; do not drop it permanently | The missing-price row is absent from `processed_orders.csv` but exists in a newly created (or appended) `flagged_orders.csv` with the correct `flag_reason`; no other rows are affected | Detected, diagnosed, patched, validated, and proposed via a real pull request ([PR #3](https://github.com/Shlokbhandari/Data-Medic/pull/3)) |
| Suspicious zero price | A row has a `price` of exactly 0, which is unusual but not necessarily wrong | Needs more context to know if this is a real promotion or a data bug — should be low confidence by default | Exclude the row from the normal output so it isn't processed downstream, but preserve it by writing it to a separate `data/flagged_orders.csv` file with a `flag_reason` of "suspicious zero price"; do not drop it permanently | The $0 row is absent from `processed_orders.csv` but exists in a newly created (or appended) `flagged_orders.csv` with the correct `flag_reason`; no other rows are affected | Detected, diagnosed, patched, validated, and proposed via a real pull request ([PR #2](https://github.com/Shlokbhandari/Data-Medic/pull/2)) |

---

More failure types will be added here as the project grows, including messier real-world-like ones later (e.g. a column silently renamed, a date format flipping from MM/DD to DD/MM).
