# MS1-S0 first split before first publish

This is the separately authorized S0 experiment based on `70812be385cde8e08340b5f3940ab1c121b54ad0`. Read [FINAL_REVIEW.md](FINAL_REVIEW.md) first. The supplied plan in [PLAN.md](PLAN.md) records the requested protocol; the user's message governs execution.

The frozen prediction-only source scan selected one F2586 opportunity. Three independent 2,888-frame states ran: B0, B-HOLD-S0, and B-VLM-S0. On the first split frame F2600, each protected branch used the saved pre history, group interval and one current X/Y observation to stage and commit before its sole public prediction write. The M and S0 model calls each happened once; no old S answer was reused. `PUBLISH_LEDGER.jsonl` binds each published row to one monotonic timestamp and row hash. [TEST_REPORT.json](TEST_REPORT.json) includes the full zero-call all-DEFER replay and future-data mutation test.

The formal run is [run_ms1s0_20260928/public](run_ms1s0_20260928/public). Its [seal](run_ms1s0_20260928/public/PREDICTIONS_SEALED.json), [first-split audit](run_ms1s0_20260928/public/FIRST_SPLIT_RESULTS.json), [metrics](run_ms1s0_20260928/public/METRICS.json), [transactions](run_ms1s0_20260928/public/TRANSACTIONS.jsonl.gz), [API ledger](run_ms1s0_20260928/public/CALL_LEDGER.jsonl), [publish ledger](run_ms1s0_20260928/public/PUBLISH_LEDGER.jsonl), and [geometry sheet](run_ms1s0_20260928/public/MS1_THREE_BRANCH_CONTACT_SHEET.png) are separate from earlier MS1 and MS1-R seals. Raw API wire, provider file IDs, native token bindings, private prediction-mask source and GT raster remain off Git. Local and lab-host restricted files have actual paths, byte counts and SHA-256 in `RESTRICTED_INVENTORY.json` and `REMOTE_RESTRICTED_INVENTORY.json`.

Reproduction without a new paid inference:

1. Supply prediction-only observations, profiles, archived B0, assignment RLE and scan at the paths and hashes in `SOURCE_MANIFEST.json`. Run `replay.py dry` in an isolated copy without an existing `dry_run_s0`, then `test_s0.py with-dry`. The checked-in dry run is the completed reference and must not be overwritten.
2. Compare the sealed current and old MS1-R public outputs with `postseal_compare.py`; `followup_audit.py` requires the private exposed-validation offline matches after prediction seal.
3. To independently score, use the frozen `score.py`, the original `online/closed_loop_2888/score.py` as `original_score.py`, the sealed public prediction files, private S0 token binding and exposed-validation assignment/truth/matches in the lab TrackEval interpreter. The scorer reads GT only after the prediction seal. A real `replay.py real` is single-use and would consume a new paid batch; do not rerun this one.

This is a synchronous causal replay with an approximately 115-second first-split publication wait, not a real-time deployment.
