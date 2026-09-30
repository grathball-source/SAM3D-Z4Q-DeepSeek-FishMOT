# DS7 full postmortem and targeted depth replay

Read PLAN.md, CONFIG.json and the three independent POSTMORTEM/source reviews.
Use existing E:/researchsoftware/anaconda3/envs/D-MOT/python.exe, local CPU only.
No new services, inference, training or API. Old DS1–DS6 sealed outputs are read only.

Execution: build_runner.py; tests.py; controller_tests.py; launch.py slice; launch.py full;
evaluate.py; report.py; delivery.py. Fresh output directories only. Reproduction requires
the same recorded SOURCE_OLD private masks and current raw/restored AlignedFeeding files.
P2 is exposed offline diagnostic with upstream future/RGB/annotation support; see PLAN.

Public numeric mask-token predictions are included; RLE/raster/RGB/GT and credentials stay
private. Final manifests provide real paths, bytes and SHA. Same-source native is the target.
