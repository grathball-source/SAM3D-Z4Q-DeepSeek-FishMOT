# Current status (2026-09-23)

The immutable preauthorization `RESULTS.md` describes the state before the user's paid E1 approval. Its historical `READY_FOR_E1_API` status is superseded for this authorized run by [api_run_20260923/RESULTS.md](api_run_20260923/RESULTS.md).

R0 engineering: **PASS**. E1 paid execution: **STOP / ENGINEERING_FAILURE** after seven length-truncated responses made the frozen 95% legality gate unreachable. Scientific conclusion: **INCONCLUSIVE**. Thirty-four formal responses completed; one in-flight request has unknown final billing and is conservatively reserved. No E2 or retuned replay occurred.

The subsequent independent 24-event default-64K rerun is archived at [api_rerun_20260923_default64k/FINAL_REVIEW.md](api_rerun_20260923_default64k/FINAL_REVIEW.md): 113/120 format-legal and four harmful temporal selections among 19 scorable old events. It remains exploratory. The newer read-only-plus-diagnostic [E1C-A audit](../vl_assoc_e1c/RESULTS.md) stopped on candidate-protocol noncompliance and zero confirmed correct executable recovery; it did not rerun old API or enter E1C-B/E2. This addendum updates navigation, not either sealed result.
