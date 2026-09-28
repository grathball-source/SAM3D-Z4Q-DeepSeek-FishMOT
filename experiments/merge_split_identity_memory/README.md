# MS1 merge–split identity memory

This is the single authorized exposed-validation MS1 run based on `cb98902b61ec46a0f15ca17ff0d4d991f957352c`. Read [FINAL_REVIEW.md](FINAL_REVIEW.md) first. The public result is `run_ms1_20260928/public/`; the private prediction-mask source, raw API wire, provider file IDs and postseal GT matches remain outside Git and are enumerated in the two restricted inventories. Old B0/B1/B2 seals were not edited.

The detector scans actual prediction-mask RLE and past clean fragments for a strict local two-source/one-mask graph. `MergeSplitManager` activates group protection on the first suspect frame. `GroupBridge` keeps the two member banks untouched while the group mask is observed, then stages the full pair restore into its own running state. The B0, B-HOLD and B-VLM arms use independent controllers and the same source mask list. M and S use the copied [model prompt](MS1_MODEL_PROMPTS.md), actual geometry PNGs through the official Files API, and no RGB or appearance embedding.

The actual full-run outputs and independent TrackEval score are in [the sealed prediction](run_ms1_20260928/public/PREDICTIONS_SEALED.json), [metrics](run_ms1_20260928/public/METRICS.json), [physical audit](run_ms1_20260928/public/PHYSICAL_EVENT_AUDIT.json), [API ledger](run_ms1_20260928/public/CALL_LEDGER.jsonl) and [acceptance chain](run_ms1_20260928/public/ACCEPTANCE.json). The [three-branch contact sheet](run_ms1_20260928/public/MS1_THREE_BRANCH_CONTACT_SHEET.png) uses only prediction-mask geometry and actual sealed output IDs.

Reproduction without new inference:

1. Supply the prediction-only files at the exact paths or update the explicit paths in `source_scan.py` and `online/closed_loop_2888/preflight.py`, verifying their hashes in `SOURCE_MANIFEST.json`.
2. Run `python source_scan.py`, `python replay.py dry`, then `python test_ms1.py` in an empty output directory. The archived `dry_run/` is the completed no-API check; do not overwrite it.
3. To reproduce the postseal score, use `score.py` alongside the frozen `online/closed_loop_2888/score.py` copied as `original_score.py` in the lab TrackEval environment. Supply the sealed public predictions and restricted exposed-validation assignment/truth/matches listed in `REMOTE_RESTRICTED_INVENTORY.json`.

`replay.py real` is single-use and makes paid calls. The completed two-call batch is exhausted; do not rerun it, reuse provider IDs, or combine its responses with another input.
