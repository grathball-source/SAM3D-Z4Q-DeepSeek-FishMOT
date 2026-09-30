# DS6 complete multi-fragment depth tracking

Read PLAN.md and CONFIG.json. 1471 exposed SOURCE_OLD frames, all four original
segments, five actual independent tracking branches. This is a complete
performance trial, not blind validation. No model/API/key/training/SAM3 or
completion service; raw depth only.

Existing local Python: E:/researchsoftware/anaconda3/envs/D-MOT/python.exe.
Existing pycocotools/TrackEval dependency path is listed in ENVIRONMENT.
Use OMP/OPENBLAS/MKL/NUMEXPR=1, CUDA_VISIBLE_DEVICES empty. launch.py sets these
and one OpenCV thread. No install/server is required.

Reproduce into a fresh sibling checkout/output directory with the recorded
source paths and private caches, retaining DS1-DS5 parent layout. Never run
into completed seals or delete old output to rerun:
1. preflight.py (old byte lock/runtime constants)
2. tests.py, score_checks.py
3. launch.py slice (real first split, no GT)
4. launch.py full (1471 frames/five branches/all seals)
5. evaluate.py (all seals/legacy exact checks before manual references)
6. postrun.py and failure_analysis.py (postscore coverage/actual QA/causal facts)

The source path guard's initial substring failure and its correction are
preserved. Final guards record actual depth_mm/source_index field access and
block RGB/manual/v3/network calls during prediction. Old original core and
geometry outputs exactly reproduce all1471 frames, and F6 selector reproduces
all28382 old DS4 objects. No old responses/seals/state are reused as a new trial.

D4/D5 share the history/gate rules but own actual state. D5's scalar shadow
compares the q representation on exactly the same branch state.
Physical surface labels and depth-mm calibration are UNKNOWN.
First accepted mappings, actual COMMIT/no-change/fallback, first-public
unscorable outcomes and every official CLEAR switch are kept separately.
See RESULTS.md, METRICS, CAUSAL_EVIDENCE_ANALYSIS and three POSTRUN reviews.

The four raw-depth/mask QA figures were actually viewed. Public PERFORMANCE.svg
is numerical only. Private original raster/RLE/GT label files and QA remain
local; RESTRICTED_INVENTORY gives actual paths/bytes/SHA and dependencies.
All code/config/checks/logs/public predictions/results/report and figures are
normally pushed to main with actual remote byte proof. Remote proof is an
append-only follow-up commit; no force push or old archive changes.
