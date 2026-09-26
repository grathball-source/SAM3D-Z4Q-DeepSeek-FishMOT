# EHR-1R final review — 2026-09-26

## Decision

**Engineering/source: `ENGINEERING_FAILURE_STOP` for the only sent v5 batch. Scientific effect of full event history or depth: `INCONCLUSIVE_NOT_TESTED`.** The old EHR-1 stays `ENGINEERING_FAILURE_STOP`; its five B01 `DEFER` answers and 20 unsent bodies were never reused. This EHR-1R run made new calls, but its H-D anonymous event table omitted mandatory sensor and quality fields. The batch was stopped and partially sealed. A corrected v6 25-request package passed source checks but was **never sent**, so it supplies no model result. No tracker ID update, HOTA/IDF1, training, DAA restart or E2 occurred.

## Source and event contract

The new hard checker first rejected actual old EHR-1 B01/B02/B04-A packets using the original predicted observation streams. B01's old A/B histories contained 21/4 contact-risk observations and the old 1321 anchors were risky; B02's sent 30/30 histories were risky; B04-A contained 22 earlier contact-risk observations despite a clean anchor-to-trigger suffix. The same audit retains B03/B05 risk records. Risk frames were not silently discarded: 4848 actual source observations are indexed, with named clean fragments or anonymous event facts, fixed source frames/times, source mask hashes and depth provenance.

The new B01 A reference is one clean frame at 1314, and B is a 31-frame clean fragment ending 1317. Neither can be claimed source-connected to its old contact-frame anchor at 1321; the old-to-new relation is `ORIGINAL_REFERENCE_UNRESOLVED`. B01-A velocity is UNKNOWN. B05-Y has only two q-ending clean frames, so its velocity is UNKNOWN. Other named fragments, derived velocities, loss/return intervals, pair-joint cleanliness and relative motion use measured frames only. The compact sources expose no alias epoch/generation fields; the corrected checker splits on those if available and does not pretend they were measured here.

All 727 actual v5 depth-bearing frames and 4332 mask profiles matched raw HDF5 arrays, synchronized feature rows and predicted masks. This verifies pipeline mm values; water-surface calibration remains unverified. The failure was in the **model-visible anonymous event depth**: all 15 H-D logical packets carried only core median and valid fraction, omitting `sensor_available`, `synchronized`, core n/MAD, whole n/MAD, overlap and quality/risk. `SOURCE_FAILURE_AUDIT.json` enumerates the 15 failures. The v5 preflight PASS is preserved as evidence that its checker was incomplete. Current code and `corrected_unsent/` add these fields and a regression that fails when one is removed.

All five fixed triggers had a predicted pair-contact proxy. None has a verified full online Z4Q hard-event gate in this package, so **all five are offline diagnostic controls**, as enumerated in `TRIGGER_SCOPE_AUDIT.json`. Neither the trigger nor q nor anchor was selected with GT.

## Requests, raw outputs and limits

The 25 v5 logical requests and budget were frozen before the first formal response. One same-route smoke succeeded. Seven formal responses returned, one formal call (B02-H-D) was interrupted with **unknown HTTP outcome**, and 17 formal requests were never sent. There is no full 25-response seal. The partial seal protects the original 17-line call ledger and each saved response hash. The unknown call is counted against the request ceiling and reserved budget; there was no retry.

| Case | New A/B end frames | X/Y clean frames | E | H-2D | H-D | Repeat | Permute |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B01 | 1314 / 1317 | 15 / 15 | DEFER | DEFER | H1 | DEFER | DEFER |
| B02 | 7866 / 7890 | 6 / 15 | DEFER | H2† | unknown HTTP | unsent | unsent |
| B03 | 306 / 315 | 15 / 15 | unsent | unsent | unsent | unsent | unsent |
| B04 | 2544 / 2525 | 7 / 7 | unsent | unsent | unsent | unsent | unsent |
| B05 | 2469 / 2525 | 13 / 2 | unsent | unsent | unsent | unsent | unsent |

These are **raw** choices, not valid method scores. All seven returned decisions parse structurally; six have legal fact citations. †B02-H-2D cites one invalid supporting fact ID. In B01, H-D's first raw H1 was not repeat/permute stable even before considering the source failure. Every v5 arm is `UNSCORABLE_SOURCE_CONTRACT` as a paired trial; `EVENT_RESULTS.json` keeps raw choice, citation legality, correct/wrong/valid-abstention fields and missing transport statuses separate. Unsent and unknown are never counted as DEFER or safe negatives.

After the partial seal, the exposed relation timeline was used only to audit the **actual new reference semantics**. All five A/B/X/Y endpoint bindings were unique in that retrospective source and the physical mapping labels happened to match each old answer. For B01 this does **not** repair the uncertified source bridge to old frame 1321. `CASE_SCORE_BINDING.json` records the role GT IDs, IoUs, source hashes and old/new semantic relation; it is not a score of v5 responses. An initial binding script compared pair-only mappings to complete X/Y/U candidate dictionaries and falsely labelled all five unscorable. That exact output is retained as `CASE_SCORE_BINDING_INITIAL_INVALID.json`; the corrected binding never altered packets, responses or the partial seal.

Known returned-plus-smoke peak-rate accounting is **USD 0.2983608**. Reserving USD 0.1280376 for the unknown B02-H-D call gives an upper account of **USD 0.4263984**, under the USD 3 cap and 9 attempted inference HTTP requests including smoke. The seven formal returned latencies sum to 584.215 seconds. The original v5 26-request pre-reserve was USD 2.782218. The corrected **unsent** v6 package reserves USD 2.968511 for a hypothetical fresh 26-request batch and has zero actual calls. The rate assumptions are DeepSeek's official peak cache-miss input USD 0.30/M and output USD 1.20/M; the input reserve uses twice the published English-character token heuristic plus the documented 1024-token upper bound per image and full 65,536 output tokens ([pricing](https://api-docs.deepseek.com/quick_start/pricing/), [vision](https://api-docs.deepseek.com/guides/vision/), [token usage](https://api-docs.deepseek.com/quick_start/token_usage/)).

N-H2D/N-HD are transparent **endpoint-history** comparators on the same qualified pre/post fragments. Four cases have all-four-edge comparable depth; B05 uses a symmetric `DEPTH_UNAVAILABLE_FALLBACK`. They do not consume all anonymous intermediate event evidence, so VLM necessity is **NOT_TESTED**. `REPAIR_DIFF_AUDIT.json` verifies that v6 kept all references and images fixed, left all 10 E/H-2D texts byte-identical, and added only eight anonymous depth-quality columns to each of 15 H-D texts. The repaired package was prepared after the partial v5 outputs became accessible, so it remains an exposed diagnostic, not a fresh unexposed test. A corrected but uncalled v6 package cannot establish depth increment, model failure, stable recovery, negative-case safety, or generalization. M3-L's local two-frame no-increment result remains intact and does not settle full event-history association.

## Delivery boundary

The full public v5 logical plan, source facts, source and image indices, tests, preflight, raw response contents, per-event missing-status results, ledger, partial seal, failure audit and this report are in this directory. `frozen_v5/` preserves the exact sent input/audit/sender code. `corrected_unsent/` contains v6 facts, quality-complete logical requests, preflight, depth audit, numerical reference and an explicit zero-call offline freeze. Earlier preparation runs v1–v4 have exact remote path/byte/SHA records in `PREPARATION_INVENTORY.json`. Restricted pixels, GT raster, provider file IDs, raw wire and private reasoning remain off Git; `RESTRICTED_INVENTORY.json` and `ARTIFACT_MANIFEST.json` list real paths, bytes, SHA-256 and reproduction requirements.

**One next step:** if a new independent call budget is authorized, run only the sealed corrected v6 inputs as a fresh exposed-case diagnostic, with all 25 new responses and a full response seal before scoring; never combine them with the seven v5 returns.
