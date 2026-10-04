# DS26 phase ROI observability

Read PLAN.md first. This is a local read-only measurement audit, not a tracking replay, identity qualification platform, or model experiment. All old DS25 files/seals and original raw sources are immutable.

Use E:/researchsoftware/anaconda3/envs/D-MOT/python.exe with the existing dependencies recorded by common.py. COHORT.json contains the fixed prediction-only cohort and exact original check references. Execute test_measurement.py and measure.py slice through execute.py; freeze.py pins actual imports, sources and decisions, then measure.py all runs the same fixed cohort under the existing GT/RGB/network field guard. review.py runs only after all measurements are sealed. visualize.py renders raw depth and actual masks privately only after that seal. No GT/RGB is needed by any step.

Run in a new empty experiment directory when reproducing. Preserve the pinned older repository and restricted source paths; never overwrite this sealed directory. See RESTRICTED_ARTIFACTS.json for actual inventories and FINAL_REVIEW.md for limits. No HTTP, API key, cost, training, sensor completion, SAM3 inference or state commit occurs.
