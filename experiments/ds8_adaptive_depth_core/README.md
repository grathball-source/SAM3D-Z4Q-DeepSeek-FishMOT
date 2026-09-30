# DS8 adaptive depth core

Read PLAN.md before running. Uses saved SOURCE_OLD SAM3 masks, raw aligned depth and actual native v2 restored H5; no new inference or network during prediction. Private source paths are recorded in FREEZE and inventories.

Execution: prepare_trial.py (before outputs), adaptive_tests.py, measurement_tests.py, controller_tests.py, score_checks.py, preflight.py, launch.py slice, launch.py full, evaluate.py, postrun_review.py. Use the recorded D-MOT interpreter and existing TrackEval/pycocotools dependencies; all math/OpenCV threads one, CUDA disabled.

GT access is only permitted after ALL_PREDICTIONS_SEALED and ACCESS_SEALED. The four segments are exposed same-video development diagnostics, not sealed test. No private pixels or annotation rasters are published.
