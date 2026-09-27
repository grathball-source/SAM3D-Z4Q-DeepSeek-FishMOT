# Direct event-history 2,888-frame replay — final review

## Decision

**ENGINEERING COMPLETE; EXPOSED DEVELOPMENT RESULT NEGATIVE; STOP this frozen intervention.** Four fixed opportunities produced four valid `deepseek-flash` choices and two genuine `Bridge.stage`/`commit_once` state changes. Independent official TrackEval scoring of all 2,888 frames shows lower identity metrics than original Z4Q. This is a completed exposed validation replay, not a blind test, a proof that history/depth cannot help, or an automatic difficult-event trigger result. The previous EHR-CF 25-request batch remains stopped and untouched.

| Metric | B0 original Z4Q | B1 history model + Z4Q | B1 − B0 |
| --- | ---: | ---: | ---: |
| IDF1 | 80.697587 | 77.667372 | **−3.030215** points |
| HOTA | 69.243869 | 66.357032 | **−2.886837** points |
| AssA | 60.074321 | 55.152279 | **−4.922042** points |
| IDSW | 9 | 12 | **+3** |
| FP | 298 | 298 | 0 |
| FN | 423 | 423 | 0 |

The masks and frame range were identical. B1 differs in public IDs on **2,512 frames**, every frame from the first commit at 377 through 2888. The second event operated on the B1 state already changed by B03; these are not independent oracle gains or losses to sum. The original scorer checked the prediction seal and unchanged assignment/truth/match hashes, then reproduced the historical B0 baseline exactly. See `public/PREDICTIONS_SEALED.json`, `public/METRICS.json`, `public/SCORE_PROVENANCE.json`, and `public/ACCEPTANCE.json`.

## Event results and cause

| Case | q | Raw choice | Action in B1 | Postseal reference check |
| --- | ---: | --- | --- | --- |
| B03 | 377 | H2 | **COMMIT**, two-fish public ID swap | Wrong on both changed identity edges. Model favored bbox shape and relative order across contact; those cues did not establish identity. |
| B01 | 1498 | H2 | KEEP | No new edit. Its A reference was public ID 5 in B1 after B03, demonstrating branch-specific rebind. |
| B05 | 2580 | H2 | KEEP | No new edit; evaluated before the overlapping B04 event. |
| B04 | 2638 | H1 | **COMMIT**, two-fish remap | Wrong on both changed reference edges. The model preferred motion/depth continuity, but that comparison crossed an anonymous risk interval; earlier B03 state also changed the A public ID to 5. |

Both changes passed real quality, occupancy, past-anchor, native-priority and lifecycle checks in `Bridge.stage`, and were committed atomically to B1's engine. Those checks established a legal state transition, not physical identity truth. Postseal exposed GT binding found **0 correct, 2 wrong, 0 unscorable** committed events; full-timeline fixed-public-ID audit counted 967 harmed and 251 improved individual mask assignments. The first wrong swap propagated for most of the segment and the second did not undo it. The main observed cause is that the model treated fragment shape/relative order in B03 and motion/depth across B04's uncertain interaction as sufficient to swap identities. The evidence package explicitly represented those intermediate observations as anonymous, so this is a method failure under the frozen decision rule, not a license to relabel them as observed paths.

No selection was made with GT or future frames. The q values were inherited from exposed offline case manifests and are **not** a verified prediction-driven trigger. B02 was a development case and was not called. There was no new synthetic qualification, repetition, majority vote, choice optimization after scoring, training, DAA, or E2. Static color/texture was not the requested primary signal. The output parser ignored extra metadata fields while rejecting duplicate/conflicting/unknown choices and truncated output; old S02's extra-field DEFER passed locally. Zero fallback occurred in this run.

## Calls, reproduction, and delivery

Four event inference HTTP calls, no retries or smoke, all four returned `deepseek-flash`; no unknown HTTP. Returned usage was 429,519 input and 82,098 output tokens. Official rate-based **peak no-cache upper charge USD 0.2273733** against the independently authorized 4-call/USD 4 cap; Sunday off-peak estimate USD 0.11368665. This is not a provider invoice. Full synchronous replay wall time was 390.328 seconds. Public per-call START/END, request text/body hash, response content/usage/hash and run seal are in `public/`; raw wire, actual file-ID bodies, uploaded-ID ledger and pixels remain restricted.

`replay.py` uses the existing Z4Q `Bridge` and original input hashes; `test_replay.py` and model-off full parity passed before calls. The new `score.py` invokes the existing official scorer after sealing. Reproduction requires the previously audited EHR-CF H-D logical packets and media, Z4Q validation observation/depth streams, original RGB only for the two diagnostic sheets, the original TrackEval/GT environment for postseal scoring, and **a separate new authorization** for any new paid inference. Reusing these four responses would reproduce only this completed run. Restricted artifacts are listed with real paths, bytes and hashes in `public/RESTRICTED_INVENTORY.json` (55 files, 8,333,253 bytes); private consecutive-frame sheets are indexed in `public/VISUAL_MANIFEST.json`. No private RGB, GT raster, raw provider wire/file IDs or key is in Git.

The full public prediction and transaction streams, test/acceptance results, scorer outputs, summary, source and this report are delivered together. One next step: analyze the two wrong swaps against their anonymous interaction evidence without new model calls, then design a separately frozen veto rule before any other state replay.
