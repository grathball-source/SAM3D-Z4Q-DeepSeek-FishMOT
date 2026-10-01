# DS10 execution

Read PLAN.md and CONFIG.json. Four actual state branches across the unchanged SOURCE_OLD 1471 frames: SAM3_NATIVE / F9_RESTORED / D10_RAW / D10_RESTORED. Primary comparison is native; no geometry acceptance gate. New forecast and current-object depth null are a single frozen joint repair. No model HTTP, GPU, training, SAM3 or completion service.

Use `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe` and the existing dependencies recorded in common.py. All native math/OpenCV threads=1. Original masks/raw depth/scan and native-v2 H5/projector stay local. V2 includes upstream RGB and future cleaning; exposed offline diagnostic only, not online or independent-video evidence.

Before execution: necessary controller/adaptive/measurement/forecast/association/score checks, frozen code/source/config and source comparison contract. Then `execute.py launch.py slice`, `execute.py check_real_slice.py`; finally `execute.py launch.py full`. Prediction blocks direct GT/RGB/v3/network access. Run `execute.py evaluate.py` only after all four segment prediction/access seals. Scorer validates actual publication, references, source measurements, forecast components and semantic bindings before GT access.

Use a fresh output directory; writes are exclusive. Never overwrite DS1–9. F9 must frame-exactly reproduce sealed DS9.J2. Necessary predeclared float32-nextafter diagnostic exception only accepts unchanged operative thresholds; all used facts remain strict exact. The old failed source test is preserved in DS9.

Private failure plots/source pixels stay local with path/bytes/SHA inventory. Public code, numerical figures, log, predictions, metrics, full report and next-step plan require normal main push and actual remote ref/key-byte verification even on negative results. Do not roll parameters on GT until the target passes.
