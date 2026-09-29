# Z4Q-PX artifact map

Start with [FINAL_REVIEW.md](FINAL_REVIEW.md). This is a new isolated controller branch from base `3e4101b54e99dbf7cb246cdb673cc6e2becdfe35`; the archived B0-R/ONEFIX code and seals are read only. No model HTTP, SAM3 inference, training or private pixel export occurs.

## Order used

Run in the repository root with `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe` and the private inputs listed in [`public/RESTRICTED_INVENTORY.json`](public/RESTRICTED_INVENTORY.json):

```text
test_pairwise.py
run.py slice
FREEZE.json (exclusive creation of code/config/input/test/slice hashes)
run.py run
score.py
test_diagnostic_safety.py
accept.py
visualize.py
```

The scripts create outputs exclusively and refuse to overwrite this run. For reproduction, copy the code to a fresh sibling experiment directory and update the output location, retaining the same frozen source manifests and environment; compare its hashes, predictions and metrics to this run. The code reads the four old derived input streams and old scorer rather than copying private RLE masks or reference polygons into Git. Each controller copy receives current-frame RLE transiently to test 7×7 mask separation. Prediction files in Git contain only `n:<native>` mask tokens and public IDs.

## Main artifacts

- [`public/FREEZE.json`](public/FREEZE.json), [`public/SLICE_F159.json`](public/SLICE_F159.json), [`public/TEST_REPORT.json`](public/TEST_REPORT.json): prereplay freeze and the real no-GT slice.
- `public/SOURCE_*/feeding_*/{PREDICTIONS.jsonl.gz,ACTION_LEDGER.jsonl,PUBLISH_LEDGER.jsonl,SEAL.json}`: all four complete state replays and per-frame candidate checks.
- [`public/METRICS.json`](public/METRICS.json), [`public/EDGE_AUDIT.json`](public/EDGE_AUDIT.json), [`public/SWITCH_LEDGER.json`](public/SWITCH_LEDGER.json): postseal scores, physical/source audit and CLEAR events.
- [`public/ACCEPTANCE.json`](public/ACCEPTANCE.json), [`public/RESTRICTED_INVENTORY.json`](public/RESTRICTED_INVENTORY.json): input/code/output integrity and private dependency map.
- [`public/cases`](public/cases): geometry-only F159/F372 before, decision and after sheets.

No old `SEAL.json`, archived model answer, raw RGB, mask pixels, GT raster, key or provider file ID is part of this directory.
