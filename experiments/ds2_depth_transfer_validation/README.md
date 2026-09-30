# DS2 — frozen depth validation on new temporal segments

Review base: `fb1234bf7210a9a5e97f6d1b01d8b2cc7bd395f4`. New tracking model HTTP, smoke, SAM3 inference, completion, training and cost: **0**.

The cohort is fixed by metadata, earliest production batch ownership and file existence before feature derivation or reference contents. Original SOURCE_OLD raw predictions and original aligned `depth_mm` are used on **701–1060 (360 frames)** and **1201–1906 (706 frames)**. These are the earliest remaining complete annotated work ranges in the same recording, after excluding DS1 and its shared producer support. They are **TEMPORAL_NONOVERLAP_SAME_RECORDING**, with previously exposed native baseline references; they are not another independent dataset or a blind holdout. Upstream batched SAM3 lookahead is **UNKNOWN**. Current user DS2 instructions authorize their development validation. No sealed test directory is opened.

## Executed method

`runner.py` keeps the frozen DS1 causal state/control flow and measurement/association functions. Four separate event controllers and depth states plus the native stream execute every frame. No persistent automatic D1_DELAYED/BIRTH_REFINE inheritance is enabled. Each event is selected, atomically staged/committed or locally rolled back, then first published at the first split frame. All original masks and residuals survive; public IDs are one-to-one within each frame.

`adapter.py` calls original DS1 `predict`. For WLS only, D3 replaces the scoring mean with the fitted last-reference intercept. The score function is the **identical DS1 bytecode with its own globals dictionary** containing this predictor, without mutating any old module. Fitted slope, covariance, gamma, scale, Student-t background, missing information and weights remain unchanged. D2 calls the original function directly. The separate D3 branch continues its own state; D3 shadow scores at D2 q are explicitly non-submitted.

`EFFECTIVE_SETTINGS.json` stores actual frozen source functions, numeric literals, paths and SHA, plus checked constants. CONFIG documents them; it does not dynamically control DS1. DS1 files are read-only and byte-equal to the review Git base (`DS1_READONLY_BASE_LOCK.json`).

## Reproduction

Installed interpreter: `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`. Local CPU, single-thread native math/vision, no CUDA. Reproduction requires the original local SOURCE_OLD polygons, aligned raw depth and authorized manual references, plus private derived masks, existing feature helpers and TrackEval dependencies documented in the inventory. New artifacts must go into a new checkout/directory; commands intentionally refuse to overwrite old outputs.

1. `cohort.py`: metadata selection, original DS1 `build_frame`, unchanged V4 scanner; private assignments hold RLE masks, public source inventory holds paths/bytes/SHA only.
2. `checks.py`: 12 numerical/state tests, three real 65-frame causal/missing prefixes with network/key/reference/future-depth blocks, and fresh full405 regression replay. Frozen expected outputs are only compared, never copied to new predictions.
3. `runner.py`: validates source/code hashes, freezes both segments, executes all five branches and seals every prediction/state/transaction/publication/evidence/timing stream.
4. `evaluate.py` plus `finish_scoring.py`: validates **both** seals and all publication/state checks before opening references; official TrackEval per segment and pooled disjoint identity namespaces. The completion adapter corrects inherited provenance/audit paths in a private context, recomputes and compares any existing metrics, and runs the original actual-bank-anchor physical audit and exact CLEAR switch recomputation. For a fresh reproduction, use `finish_scoring.py` directly; frozen `evaluate.py` retains the recorded bookkeeping failure.
5. `diagnostics.py`: coverage, all-edge facts and missing reasons, common-state D3 shadow, strict same-q-version postseal residuals, timing/state/log growth and original raw-depth/core QA images.

`run/` is the only formal new validation. `regression_405/` is **EXPOSED_REGRESSION_REFERENCE**, kept separate from new metrics. Early preparation/interface failures happened before formal prediction and are recorded in execution notes; they are not model or research outcomes. A directory-label correction retained the initial cohort metadata and changed neither selection nor any actual source path (`COHORT_METADATA_CORRECTION.json`).

## Sharing boundary

Public prediction streams contain persistent ID→frame-local native token mappings, never mask pixels. Public states, transactions, measurement statistics, SVG and results are numeric. Raw depth, RLE, RGB, reference polygons/GT raster and credentials are not published. Restricted files have real paths, bytes, SHA and reproduction dependencies in `RESTRICTED_INVENTORY.json`; `VISUALIZATION_INSPECTION.json` records actual local viewing. Git synchronization is permitted and is separate from the network-disabled tracking test.

See [RESULTS.md](RESULTS.md) for complete scores and limits, [EXECUTION_LOG.md](EXECUTION_LOG.md) for execution, [ARTIFACT_MANIFEST.json](ARTIFACT_MANIFEST.json) for public hashes, and `run/REMOTE_VERIFICATION.json` for delivery commit and actual pushed ref/file checks.
