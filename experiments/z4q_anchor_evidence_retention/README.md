# PX-A frozen-anchor evidence retention

This isolated experiment starts from main `85f71d854f8d9b0bcc6d7bf1d200d1a01dd8de08`. Read [FINAL_REVIEW.md](FINAL_REVIEW.md) first. Old PX, B0-R, ONEFIX, v3, model outputs and seals are read only. This run adds no model HTTP, SAM3 inference or training.

## Reproduction order

Use `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe` from the repository root and the exact local files in [public/RESTRICTED_INVENTORY.json](public/RESTRICTED_INVENTORY.json). The `SOURCE_OLD` and `SOURCE_BASELINE` saved SAM3 batches and original-depth observations are selected by the unchanged B0-R [manifest](../b0_same_source_regression_repair/public/PREDICTION_SOURCE_MANIFEST.json). No v3 or repaired-depth input is used. Reproduce into a fresh sibling directory because all public result writers create exclusively and the present seals must remain unchanged.

1. `python experiments/z4q_anchor_evidence_retention/test_pairwise.py` (13 focused checks, including actual controller, F159 D1, F468 BirthRefine, preview isolation).
2. `python experiments/z4q_anchor_evidence_retention/run.py slice` (real SOURCE_OLD from segment start through F159, no GT).
3. Save `public/TEST_REPORT.json`; run `freeze.py` to hash source, runner, scorer, tests, original inputs, and slice before full replay.
4. `python experiments/z4q_anchor_evidence_retention/run.py run` (two sources × two segments, independent empty Bridge state for each segment). All four `SEAL.json` files precede scoring.
5. `python experiments/z4q_anchor_evidence_retention/score.py` (checks seals and input/code hashes, then opens the already exposed reference).
6. `python experiments/z4q_anchor_evidence_retention/audit.py`, `accept.py`, `visualize.py` (postseal diagnosis, integrity, geometry-only diagrams).

## Artifact map

- [public/FREEZE.json](public/FREEZE.json), [public/TEST_REPORT.json](public/TEST_REPORT.json), [public/SLICE_F159.json](public/SLICE_F159.json): frozen methods, relevant tests, actual no-GT source slice.
- `public/SOURCE_*/feeding_*/{PREDICTIONS.jsonl.gz,ACTION_LEDGER.jsonl,PUBLISH_LEDGER.jsonl,SEAL.json}`: all 810 processed frames, candidate queries, lifecycle events, actual publications and state writes.
- [public/METRICS.json](public/METRICS.json), [public/EDGE_AUDIT.json](public/EDGE_AUDIT.json), [public/SWITCH_LEDGER.json](public/SWITCH_LEDGER.json): postseal full metrics and physical/switch diagnostics.
- [public/SOURCE_AUDIT.json](public/SOURCE_AUDIT.json): archived PX old-state query coverage and new PX-A outcomes, explicitly separated; all checked prefixes happen to remain state-identical in this run.
- [public/ACCEPTANCE.json](public/ACCEPTANCE.json) and [public/RESTRICTED_INVENTORY.json](public/RESTRICTED_INVENTORY.json): integrity and local dependency hashes.
- [public/cases](public/cases): actual-box geometry schematics for F159 and earliest restored anchor lookup F157. They contain no RGB or mask pixels.

The original saved SAM3 batches are not evidence of an online zero-lookahead front end. The two source variants share the same 405 original frames and reference; they are source controls, not independent datasets.
