# Direct checks before formal replay

2026-09-30, local CPU, `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`.

`tests.py -v`: **10/10 PASS**, 0.007 seconds on the recorded run. Checks cover positive finite measurements, irregular actual-time WLS at large epoch, full-gap uncertainty growth, one/two-point UNKNOWN slope, observed acquisition interval, segment/version boundaries, preserving a completed pre fragment without joining across risk, frozen A/B isolation from group/post, all-missing common model and one-post evidence, Student-t scale normalization/contamination limit, physical mapping under candidate reordering, atomic failed preview/local fallback and single first publication.

`tests.py --real`: **PASS**, three independent 65-frame prefixes of SOURCE_OLD segment 351–555, no GT. Future masks were replaced with invalid content and sensor access beyond original F415 was forbidden. Both ordinary prefixes produced identical predictions through the automatically selected first complete q (local65/original415). Depth NPZ access was instrumented to allow only depth_mm. Provider/infer was replaced by a throwing stub, model key was blank, socket connection and GT paths were blocked. The prediction pass completed. D1/native prefix matched archived EVENT_NUM/native exactly. A third prefix made all new depth evidence unavailable; D2 equalled D0 on every frame and retained every native mask. Actual maximum sensor frame read was415, future accesses0, model HTTP0.

The initial unsealed `slice/` retains outputs from an over-deleting-history implementation and is an engineering diagnostic only; that temporary source version was not separately snapshotted. `slice_v2/` is the corrected raw→measurement→frozen fragment→q forecast→candidate→transaction→first-publication slice. Its first complete legal pair is MS1-F59 at original415 (earlier MS1-F12 at398 includes a visible residual and uses local fallback). This selection used prediction/transaction scope, not GT. The formal run checks full D1/native equality separately before any label scoring.

No test is a claim of tracking gain or calibrated depth accuracy. No API qualification test was run.

## Completed formal acceptance

`run/VERIFICATION.json`: **405/405 same-source native exact and405/405 archived NE-1 EVENT_NUM exact**. Both full seals were checked before GT scoring.18 first-publication checks passed;384 group-observation checks found0 individual writes. All native mask references and detection counts were retained, public IDs one-to-one each frame. Prediction-row SHA binds the actual first-publication ledger; transitive code/source hashes are verified by the scorer.

`resource_check/`: the same frozen complete algorithm reproduced all four formal branch streams exactly over405 frames. Instrumentation altered only timings/object-size accounting, with no new model calls, scores, thresholds or event selection. This is a resource check, not independent research evidence.

The source/score seals are read-only. Private raw-depth/mask figures were actually opened, with hashes and findings in `run/VISUAL_INSPECTION.json`. The refined postseal residual qualification binds the actual q source version; its seven observations supersede only the preliminary eight-point residual subsection, never the sealed predictions or metrics.
