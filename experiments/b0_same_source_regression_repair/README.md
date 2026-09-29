# B0-R reproducibility and artifact map

Read [FINAL_REVIEW.md](FINAL_REVIEW.md) for the result and [REPAIR_DIFF.md](REPAIR_DIFF.md) for the single new policy. This trial uses the two saved SAM3 prediction sources on original frames 0–199 and 351–555. It performs no SAM3 inference or model HTTP. The fixed review base is `bfa141da4ffcb11aa47773b601379d0da88384c4`.

## Execution order

The original sealed files in this directory are immutable. To reproduce, copy this directory's `*.py` to a **new sibling directory under `experiments/`**, with the same repository checkout and listed private inputs available, then run with the local D-MOT Python environment:

```text
source.py
trace.py
score.py
counterfactual.py run
counterfactual.py score
test_onefix.py
onefix.py
score_onefix.py
postscore.py
visualize.py
latency.py
supplements.py
test_acceptance.py
```

`source.py`, `trace.py`, `counterfactual.py run`, and `onefix.py` do not open GT; each prediction batch is sealed before its scorer opens the edited reference. `score.py` and `score_onefix.py` verify the exact input/code/output/publication hashes first. `test_onefix.py` is a prefreeze causal state test. `postscore.py` and later files are explicitly postseal diagnostics. `save()` uses exclusive creation, so an accidental rerun in this directory fails instead of overwriting a seal.

## Key public artifacts

- [PREDICTION_SOURCE_MANIFEST.json](public/PREDICTION_SOURCE_MANIFEST.json): per-frame saved SAM3 source, hash, native count, RGB hash, depth hash, batch coverage and derived observation hashes.
- `public/SOURCE_*/feeding_*/PREDICTIONS_SEALED.json`: NATIVE/Z4Q_FROZEN/PASSTHROUGH prediction seal; neighboring `B0_ACTION_LEDGER.jsonl` and `PUBLISH_LEDGER.jsonl` hold the full trace and first publication.
- `public/SOURCE_*/feeding_*/onefix/SEAL.json`: independent Z4Q_ONEFIX state replay seal, prediction, action and publication logs.
- [BASELINE_SWITCH_DECOMPOSITION.json](public/BASELINE_SWITCH_DECOMPOSITION.json), [POSTSEAL_CAUSE_REVIEW.json](public/POSTSEAL_CAUSE_REVIEW.json): exact and occurrence-level CLEAR switch events plus trace links.
- [ONEFIX_METRICS.json](public/ONEFIX_METRICS.json): all source/segment/pooled metrics and both required deltas.
- [counterfactual_F159/PAIR_SEALED.json](public/counterfactual_F159/PAIR_SEALED.json): ALLOW/VETO true-state experiment; `POSTSEAL_SCORE.json` holds its separate diagnostic score.
- [TEST_REPORT.json](public/TEST_REPORT.json), [LATENCY_SUMMARY.json](public/LATENCY_SUMMARY.json), [RESTRICTED_INVENTORY.json](public/RESTRICTED_INVENTORY.json): verification, local replay timings, and exact private dependencies.
- [cases](public/cases): geometry-only, three-frame case sheets. They are postseal annotated and are not pixel evidence.

Prediction, depth, original RGB, GT polygon files and the new baseline-derived mask/observation archives remain at the absolute locations in the restricted inventory. Only public numeric/geometry/identity traces, hashes, code and reports belong in Git; no raw/private pixel material is copied here.
