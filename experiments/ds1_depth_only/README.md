# DS1 — raw-depth-only event association

Completed 2026-09-30. Start and fetched main: `2fe9e0c8eb497432ae5e4c676f09b8d67bff9474`.

**PASS for the measured depth-module increment on these exposed 405 frames.** Engineering/source/score checks pass; WLS slope contribution and independent-data generalization remain inconclusive. The tested tracker contains no model/service inference: **0 HTTP, $0**, no request preparation or smoke. No new SAM3 inference, training, repaired depth or GPU/server job.

Read [RESULTS.md](RESULTS.md) first. D2 pooled IDF1/HOTA/AssA are **88.6276 / 85.5692 / 82.3297**, IDSW32. D2 minus D0/D1 is **+1.7086 / +1.3158 / +2.4794**, IDSW−4; minus same-source SAM3 is **+0.7900 / +0.3817 / +0.7203**, IDSW unchanged. F419/F519 choose H2 before first publication and avoid the numerical H1 swaps. Both changes use last-value weak forecasts, with UNKNOWN slope. The prescribed combination of uncertainty and missing-evidence likelihood handling was tested; its parts were not independently ablated.

## Inputs and branches

SOURCE_OLD saved SAM3 raw polygons, original frames 0–199 and 351–555, raw aligned `depth_mm` only. Each segment starts empty with disjoint scoring IDs. NE-1 native-first, V4 scanner, S0-P first-split publication and local transactions are reused. Only the event decision depth component changes. D0 still inherits the common controller's quality/history rules and is not an end-to-end no-depth tracker.

| Branch | Selection |
| --- | --- |
| SAM3_NATIVE | Exact same-source native polygons/IDs |
| D0_GEOMETRY | Original position + 0.25 motion |
| D1_STATIC_LEGACY | Unmodified legacy numeric_choice; all405 frames exactly archived NE-1 EVENT_NUM |
| D2_DYNAMIC | Same geometry + frozen WLS/last-value, uncertainty, shared Student-t background likelihood ratio |

See [SOURCE_CONTRACT.md](SOURCE_CONTRACT.md) and [CONFIG.json](CONFIG.json). Absolute physical depth accuracy, sensor technology and underwater refraction calibration remain UNKNOWN. Saved batched SAM3 predictions do not certify a zero-lookahead frontend.

## Code and evidence

- `depth_measurement.py`, `depth_state.py`, `depth_score.py`: measurements, versioned fragments, forecasts and two complete pairings.
- `replay.py`: raw measurements → independent branch states → first q → transaction → one first publication → continued own state.
- `tests.py`, [TEST_REPORT.md](TEST_REPORT.md), [EXECUTION_LOG.md](EXECUTION_LOG.md): focused and real causal checks.
- `run/*/public/`: exclusive input/code freezes, measurements/states/transactions, events, predictions, publication hash ledger and prediction seals.
- [run/VERIFICATION.json](run/VERIFICATION.json): native/legacy exact405, group-to-individual writes0, removed detections0.
- [run/METRICS.json](run/METRICS.json), [SCORE_PROVENANCE.json](run/SCORE_PROVENANCE.json), [EVENT_AUDIT.json](run/EVENT_AUDIT.json), [SWITCH_LEDGER.json](run/SWITCH_LEDGER.json): independent postseal score and physical/public outcomes.
- [DEPTH_DIAGNOSTICS.json](run/DEPTH_DIAGNOSTICS.json): coverage and actual choices. Its preliminary eight-observation forecast subsection is superseded by the append-only [FORECAST_DIAGNOSTICS_VERSIONED.json](run/FORECAST_DIAGNOSTICS_VERSIONED.json): seven strict q-version observations. No tracking result changed.
- [CHANGE_PERSISTENCE.json](run/CHANGE_PERSISTENCE.json), [RESOURCE_DIAGNOSTICS.json](run/RESOURCE_DIAGNOSTICS.json): actual continued mappings and exact-frozen resource replay, which is not another independent dataset/trial.
- `run/visualizations/*.svg`: public numeric figures only. Actual local depth/mask QA was opened; [VISUAL_INSPECTION.json](run/VISUAL_INSPECTION.json) records it.
- [RESTRICTED_INVENTORY.json](run/RESTRICTED_INVENTORY.json): actual local paths, bytes, SHA and dependencies for restricted inputs/QA. [ENVIRONMENT.json](run/ENVIRONMENT.json) and [DEPENDENCIES.json](run/DEPENDENCIES.json) record the local runtime.
- [ARTIFACT_MANIFEST.json](run/ARTIFACT_MANIFEST.json): public delivery byte/hash inventory, excluding itself and later remote proof to avoid recursive hashes.

The unsealed initial `slice/` is a retained engineering diagnostic. Corrected `slice_v2/` is the actual first legal slice; `run/` is the only scored research replay. `resource_check/` repeats the frozen algorithm solely for instrumentation and exactly matches all formal predictions. Old experimental outputs, VLM responses and seals were not changed or reused.

## Reproduction

Run from the repository root with `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`; packages and the already installed TrackEval/pycocotools source are inventoried. Restore the exact SOURCE_OLD private inputs and original dataset paths/hashes first. Pixel sources are not included in Git.

```powershell
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/tests.py -v
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/tests.py --real
```

Prediction/analysis output creation is deliberately exclusive. In a separate reproduction copy with fresh `slice_v2/` and `run/` output locations, run the following sequence; do not run it over the delivered seals. Preserve/move copied archives before creating fresh outputs, rather than deleting historical results.

```powershell
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/replay.py slice
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/replay.py full
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/verify.py
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/score.py
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/postseal.py
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/analyze.py
& 'E:/researchsoftware/anaconda3/envs/D-MOT/python.exe' experiments/ds1_depth_only/forecast_review.py
```

The scorer verifies source/code/body-equivalent prediction rows and both full seals before GT access. Hashes refer to exact bytes; root `.gitattributes` disables line-ending conversion. Measurements are apparent camera-Z in mm; proxy scales are not calibrated confidence intervals.

## Delivery and boundary

This frozen trial is complete. Public code/config/checks/logs/predictions/results/figures are committed to main; actual pushed ref and key-file bytes are recorded in `run/REMOTE_VERIFICATION.json`. Private raster, raw polygons, GT pixels and credentials are excluded, with actual inventory instead. No automatic model stage or parameter tuning follows.

One next step: validate the unchanged DS1 on another independent segment set, retaining purely numerical association and frozen parameters.
