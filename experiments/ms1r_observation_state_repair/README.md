# MS1-R observation and state repair

This is the separately authorized MS1-R run from `a5c640d17500c58400b57ef11279a10a6387832b`. Read [FINAL_REVIEW.md](FINAL_REVIEW.md) first. The copied [plan](PLAN.md) is task provenance; the user's request governs execution. The copied [M/S prompts](MS1_MODEL_PROMPTS.md) are byte-identical to MS1.

The original prediction-only `source_scan.py` algorithm and thresholds were retained. Its new scan output is SHA-identical to the old scan: one selected opportunity at F2586. The new `MergeSplitManager` keeps group and unassigned post observations separate from local individual clean history, and `GroupBridge` treats public banks and native state as distinct key domains. `event_packet.py` adds ten-point OLS residuals, actual mask degradation and depth sample diagnostics, a parsed M projection, and neutral context geometry. No RGB, appearance embedding, GT-directed choice or new tracking module is used.

`dry_run_ms1r/public/` is the zero-API 2,888-frame all-DEFER engineering check. `run_ms1r_20260928/public/` is the single real two-call run. Both have a prediction seal; only the latter was scored. Its public request/response records, ledgers, metrics, physical audit, visual and acceptance chain are in that directory. `private_source/` and every `private_api/` directory are ignored by Git; [local](run_ms1r_20260928/public/RESTRICTED_INVENTORY.json) and [remote](run_ms1r_20260928/public/REMOTE_RESTRICTED_INVENTORY.json) inventories give actual paths, bytes, SHA-256 and reproduction dependencies. Old MS1 outputs and seals remain untouched.

Reproduction without a new paid inference:

1. Supply the prediction-only observations, profiles, archived B0 and assignment RLE at the paths and hashes in `SOURCE_MANIFEST.json`; the private mask source is required to rebuild the scan and geometry.
2. In an isolated copy of this experiment directory, run `source_scan.py`, `replay.py dry`, then `test_ms1r.py with-dry` using an environment with NumPy, SciPy and Pillow. The checked-in dry output is the completed reference and is not overwritten.
3. For scoring, provide the sealed real predictions, private S token binding, the frozen `online/closed_loop_2888/score.py` as `original_score.py`, and exposed-validation assignment/truth/matches in the lab TrackEval environment. The scorer reads GT only after `PREDICTIONS_SEALED.json` exists. The private binding is checked against independently rebuilt mask order.

`replay.py real` is single-use and makes new paid requests. This run's authority was used; do not rerun it or reuse its responses for another input.
