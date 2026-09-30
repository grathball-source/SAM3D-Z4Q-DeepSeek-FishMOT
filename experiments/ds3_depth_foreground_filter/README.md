# DS3 — foreground depth measurement validation

This measurement-only next step uses the exposed DS2 SOURCE_OLD1066 frames.
No identity association or tracker is changed. All model HTTP, smoke, training,
SAM3 inference, depth completion and cost are0. Old DS1/DS2 files remain read-only.

## Reproduce in a fresh output directory/check-out

Interpreter: `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`; local CPU.
Existing requirements: NumPy, OpenCV, pycocotools, Matplotlib; the existing
`feeding_first_two_s0p/prepare.py` and DS1 depth measurement helper; local original
SAM3 polygon files and original aligned raw depth, plus frozen DS2 assignments
and profiles. Only postseal scoring needs authorized human polygon references.
Scripts refuse to overwrite freezes, measurements, checks and scores.

1. `checks.py` runs10 direct checks including real F701, with network/reference
   access and NPZ keys other than depth_mm blocked.
2. `runner.py` verifies all source hashes, freezes actual CONFIG/code, confirms
   original saved polygons equal cached masks and reproduces every DS2 whole/core
   statistic. It computes the one fixed filter on every mask and seals all output.
3. `evaluate.py` validates both full measurements and code/source binding before
   opening human polygons. It computes occupancy purity/retention and explicit
   UNKNOWN/UNSCORABLE, then produces three private diagnostic visualizations.

`foreground.py` is stateless: current raw depth, source mask and union of other
current predicted masks are its only inputs. Local-plane coefficients, real
sample counts, support fractions, signs, competing components and failure
reasons are public numerical facts. Connected closing never supplies synthetic
depth. Frame-local tokens bind numeric facts to private crop/RLE/source tables.

F0_WHOLE/F1_LEGACY_CORE/F2_LOCAL_FOREGROUND are measurement comparisons, not new
tracking branches. Silhouette occupancy is not physical depth calibration or an
IDF1/HOTA test. See frozen [PLAN.md](PLAN.md) and [CONFIG.json](CONFIG.json).

Sharing: `private/` contains source/annulus/candidate/support/selected RLE and
depth QA images, and is Git-ignored. No RGB, GT raster, raw pixel plane, API key
or old provider response is published. Reference/source inventories contain
paths, bytes and SHA only. Restricted artifacts are listed with reproduction
dependencies; old files are verified against `OLD_READONLY_LOCK.json`.


## Completed outcome

See RESULTS.md, SUMMARY.json, FAILURE_CASE_AUDIT.json and MEASUREMENT_SUMMARY.svg.
Engineering/input PASS. Fixed silhouette proxy FAIL:99.6213% core versus98.9165%
filtered,50.5329% fish retention and72.9140% old-core-usable coverage. No new
tracker result. The proxy misses a12254.6mm component inside a fish silhouette;
physical correctness remains UNKNOWN. Postscore reporting/failure/inventory
scripts do not re-run the filter or change scoring. Three private images were
actually viewed. Delivery proof: REMOTE_VERIFICATION.json (actual result push).
