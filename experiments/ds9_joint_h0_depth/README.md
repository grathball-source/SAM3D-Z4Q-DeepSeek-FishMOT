# DS9 reproducibility

One six-branch, 1471-frame SOURCE_OLD CPU replay. Read PLAN.md and CONFIG.json before execution. Reuse the DS8 adaptive measurement, current-frame v2 projection, DepthState, scanner, native-first/S0-P state transactions. No model, training, new SAM3 or completion-service calls.

Interpreter: `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`. Existing TrackEval/pycocotools dependencies: `E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps`. Source masks/raw depths/scan are at the original FEED and DS2 private input directories recorded in common.py; v2 H5 paths are in restored_source.py. Use fresh outputs; all writes are exclusive. Old archives remain read-only.

From this directory run: `preflight.py`, `controller_tests.py`, `measurement_tests.py`, `adaptive_tests.py`, `association_tests.py`, `score_checks.py`; then `launch.py slice`, validate REAL_SLICE and seal, create REAL_INPUT_CHECKS.json. Finally `launch.py full`, then `evaluate.py` only after ALL_PREDICTIONS_SEALED and ACCESS_SEALED. All native math/OpenCV threads=1, no CUDA. A fresh checkout/output is required for reproduction; do not overwrite run/slice.

The full-v2 dataset has upstream RGB and future-clean support; it is an exposed offline diagnostic. Runtime directly blocks GT/RGB/v3/network. All four predictions seal before independent official HOTA/Identity/CLEAR and physical event reference scoring. Same-frame uniqueness/all masks and native equality are checked, ZERO must be frame-exact with geometry. Public predictions contain mask tokens, never private RLE pixels. Private source and visualization files remain local and are inventoried by true path/bytes/SHA at delivery.
