# DataMedic — Failure Benchmark

This file tracks every failure scenario DataMedic is expected to handle, and what "success" looks like for each one. It's used to measure progress as the project grows.

| Failure Type | Description | Expected Diagnosis | Expected Fix | Expected Validation Result | Status |
|---|---|---|---|---|---|
| Duplicate transaction ID | Two rows share the same `transaction_id` | Duplicate `transaction_id` detected, likely caused by an upstream retry or resend | Resolve deterministically by sorting on `order_date` and keeping the row with the earliest date; do not leave selection arbitrary | No duplicate `transaction_id`s remain, the kept row has the earliest `order_date`, row count drops by exactly the number of duplicates | Detected (diagnosis and fix not built yet) |
| Missing price | A row has a null/empty `price` value | Missing price value, likely an incomplete upstream record | Either fill with a sensible default or exclude the row, depending on context | No null prices remain | Detected (diagnosis and fix not built yet) |
| Suspicious zero price | A row has a `price` of exactly 0, which is unusual but not necessarily wrong | Needs more context to know if this is a real promotion or a data bug — should be low confidence by default | None proposed automatically; escalate to a human with the finding | Not applicable, this case should not be auto-fixed | Detected (diagnosis and fix not built yet) |

---

More failure types will be added here as the project grows, including messier real-world-like ones later (e.g. a column silently renamed, a date format flipping from MM/DD to DD/MM).
