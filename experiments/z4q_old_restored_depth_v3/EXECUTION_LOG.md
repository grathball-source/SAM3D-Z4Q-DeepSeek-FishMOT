# Execution log

All commands used `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe` from the
repository root. No model HTTP, SAM3 inference, training, or server job occurred.

1. Read the OLD same-source manifest and verified that all 405 restored v3 NPZ
   files exist in `E:/CAU/D-MOT/data/AlignedFeeding_v1`. The dataset's own
   `restoration/verification.json` and `restoration/v3/verification.json` pass.
2. `test_depth_input.py`: exit 0. Six real frames reproduced every old raw-depth
   summary, preserved all non-depth fields, and rejected a tampered NPZ hash.
3. `run.py freeze`: exit 0. The first `run.py run` processed the 200-frame first
   segment, then exited 1 while sealing because the frozen engine lacks the
   pairwise-only `co_visibility` attribute. No GT was opened. The unscored
   first freeze and its prediction/action/publication files were moved intact
   to `public/FAILED_ATTEMPT_1`; it has no `SEAL.json`.
4. Corrected only the frozen-controller final-state hash, then reran
   `run.py freeze` and `run.py run`: exits 0. Both segments were processed
   independently from empty frozen and pairwise Bridges. Both `SEAL.json`
   files and `RUN_SUMMARY.json` were written before GT access.
5. `score.py`: exit 0. It verified code/input/output/publication hashes before
   reading edited reference polygons. TrackEval printed an optional BURST
   import warning (`tabulate` absent); CLEAR, Identity and HOTA scoring passed.
6. `analyze.py`, `sensitivity.py`, `case_depth.py`, `accept.py`: exits 0.
   The five annotation-fill pixels changed some depth input summaries but the
   full-state ablation changed no public mapping. Acceptance verified 405
   frames, native parity, both seals and zero pairwise vetoes.
7. `inventory.py`: exit 0; private source/reference paths, byte counts and SHA
   were listed without copying any pixel arrays into Git.

Original OLD, B0-R, ONEFIX, and PX seals and results were not rewritten.
