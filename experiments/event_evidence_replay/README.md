# Event-evidence B2 replay

This is one new, sealed, exposed-validation event-history representation trial based on `2dc96df40f2d20b74610a924d26d6210bcf1aedd`. It retains the four old cases, A/B anchors, q frames, images and X/Y candidate meanings. It changes only the model's event evidence: source-contiguous clean fragments, anonymous risk observations, measured motion and core/whole depth series, plus a geometry-only event overview. `online/closed_loop_2888/z4q_source` and prediction masks are unchanged.

The result is in [`FINAL_REVIEW.md`](FINAL_REVIEW.md). The API batch is exhausted: four new official `deepseek-flash` inference calls, no smoke and no retries. `replay.py` is single-use and makes paid calls; do not rerun it from this sealed directory or treat any saved key/file IDs as new authorization.

## Evidence chain

1. `preflight.py` checks the actual observation/depth sources, reproduces B0 for all 2,888 frames without GT or API, compiles the four case packets, and tests real Bridge stage/next-frame semantics. Its final report is `PREFLIGHT_REPORT.json`; the source/native debug map remains in ignored `preflight_output_v7/private/`.
2. `test_evidence.py` checks no cross-risk fragment lines, UNKNOWN short velocities, observed versus projected time alignment, fact references, candidate relabeling, q+1 isolation, source tamper rejection and parser behavior. Results are `TEST_REPORT.json`.
3. `replay.py` froze source/code/request/budget commitments in `public/FREEZE.json` before the first inference. It reused the old 11 images per event and uploaded one new, geometry-only overview. It then ran B0/B2 through the same `Bridge`; B2 used its own committed state for later anchors, current assignments and transaction targets. Every new request, public response, START/END ledger, event and prediction is in `public/`. Body/raw wire, provider IDs and source/native debug bindings remain under ignored `private_api/`.
4. `public/PREDICTIONS_SEALED.json` precedes scoring. `score.py` passed a postseal B2-as-B1 *name alias* to the unchanged official TrackEval scorer; `public/SCORE_ADAPTER.json` binds the two hashes. `postscore.py` separately checks frozen A/B physical identities against q-local X/Y on exposed validation matches. Neither step feeds the model or changes its choice.
5. `verify.py` checks the complete chain and produces `public/SUMMARY.json`, `public/ACCEPTANCE.json` and the local restricted inventory. `mechanism.py` explains the B04 metric/reference mismatch. `visualize.py` produces four clearly marked postscore diagrams; these were never model inputs. The four `public/overviews/*.png` **were** sent as the twelfth image per request.

## Reproduction boundary

Run the no-model source checks in a fresh checkout with the same local OBS/PROFILES/ARCHIVED files and original H-D media listed in `public/RESTRICTED_INVENTORY.json`:

```text
python experiments/event_evidence_replay/preflight.py
python experiments/event_evidence_replay/test_evidence.py
```

The frozen official scorer needs the exposed-validation assignment, truth and match files listed in `public/REMOTE_RESTRICTED_INVENTORY.json`, the TrackEval environment in `public/SCORE_PROVENANCE.json`, and the already sealed public predictions. The raw API bodies/responses and original RGB crops stay local/private; published request JSON is the exact model-visible text, with body and media hashes bound in `public/request_bindings/`. No hidden test GT, GT raster, private pixels, provider file IDs or credentials are in Git.
