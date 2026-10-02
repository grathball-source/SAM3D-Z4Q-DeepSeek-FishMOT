# DS15 final evaluation and publication-binding review

2026-10-02. Review of the completed frozen DS15 run, following all five-arm/eight-segment prediction and access seals. This review independently streamed the saved numeric predictions, transactions, birth/contact/publication records and old DS14 records with standard-library assertions. It verified saved scores and scorer-produced identity diagnostics; it did not run a predictor, duplicate the scorer, parse GT raster/polygon contents, or edit frozen code.

## Decision

**Engineering and scoring reproducibility: PASS. The frozen strategy's declared performance goal: not achieved.**

The new depth branch exceeds original Z4Q IDF1 only on Feeding pooled1471, by **0.103911 percentage points**, and changes IDSW 132→130. Its Feeding HOTA/AssA remain below native by 0.030058/0.057324 points; IDSW remains above native108. It loses to original Z4Q on both FishSA units and both camera units. Its official metrics equal SHARED on FishSA, L3 and LW. This frozen version therefore provides no general gain over original Z4Q, and no evidence that depth is independently necessary.

## Seals, immutable sources and baseline equality

- Independently checked eight prediction seals and eight access seals, **96 sealed artifact entries**, **63 frozen source/code files**, and **1,590 protected old files**, covering **1,768 unique file hashes**. All passed.
- Independently streamed all **20,098 frames / 181,842 original mask tokens**. Native masks/order/IDs equal the immutable prepared `N0` records and old DS14 native predictions exactly. R12 predictions and complete R12 `EVENTS.json` equal old DS14 exactly.
- All eight native/R12 segment score dictionaries and their namespaced Feeding pooled score dictionaries equal the final old DS14 scores exactly.
- Canonical original Z4Q archive parity is **PASS on all six available archives / 19,032 frames**. This includes L3/LW, so the provisional camera-adapter mismatch concern did not occur. This review rehashed the canonical prediction and metric artifacts against the recorded SHA pins, then checked all six saved six-field metric dictionaries against the freshly scored original-Z4Q branch: exact.
- Historical full original-Z4Q archives remain unavailable for the final two Feeding segments (1,066 frames). Their new frozen original-Z4Q branch was scored normally; no historical score was fabricated.
- Scorer provenance artifacts and the five-arm summary values were verified. `masked_or_ignored_ids=0`, no GT was used for predictions, and reference access follows all eight seals.

## Exact publication and commit binding

The independent stream check covered **80,392 state-arm transaction rows**, **60,294 birth rows**, and **20,098 contact/prediction/publication records**.

Every state-arm transaction's actual published mapping equals that arm's actual prediction row. Every original mask token is preserved in every arm, public IDs remain unique, and every arm's FP/FN and prediction count equal native. Every saved switch count equals official IDSW.

Every birth/contact row SHA equals its first-publication ledger binding. Birth decisions use current q, exactly one current post sample, and the actual first-public ID/version. Joint event publication rows bind the actual q pair. R12 parity deliberately checks mappings/events instead of an overall log digest: the five-arm prediction serialization makes the new combined birth/trace bytes differ legitimately.

For every accepted reconnect trace event, the review independently recomputed first-publication adoption, actual alias target, and explicit-transaction override. The saved durable lists match the predicates exactly. Counts are **90 original / 0 R12 / 78 SHARED / 77 DEPTH durable automatic commits**. All accepted preview candidates in this completed run were adopted; none was overridden or left unpublished. The distinction is still preserved in telemetry and scoring, so an accepted preview is not assumed to be a commit.

## Reference and scoring contract

The scorer reuses frozen DS14 mask/raster/TrackEval mathematics: CLEAR at IoU0.5, Identity at0.5 and HOTA over the same19 alphas. It keeps every mask/ID, including residuals and negative IDs. Only Feeding is pooled, with four independent segment namespaces; there is no cross-dataset pooled headline.

- FishSA8400 uses the authoritative development reference SHA from `ms1_s0_development_8400/score.py`: `ab6bc733911cc07dc4be70ef3a893c1475aca6908fc6ce8bc376923597eed5d1`. The malformed historical DS14 constant was not reused.
- FishSA2888 uses the original `sam3_trackeval_20260912_1705/inputs.zip`, SHA `169b9875102d62345958a077d5ebcc1f433044bd380da470b953dc88d53b0631`, with per-entry SHA checking, original1080 polygon rasterization and nearest640 scaling. The later aligned-package annotation version was not substituted.
- Feeding uses the same original640 references. L3/LW use the same declared recovered weak references and original1080 prediction/reference rasterization.
- Exact native/R12 and canonical original-Z4Q score parity independently confirms the final baseline scoring contract. Deltas were recomputed from saved metrics; every switch count and every FP/FN conservation assertion passed.

## Numeric result check

IDF1 below is in percent. The full six-field five-arm tables remain in `RESULTS.md` and `run/METRICS.json`.

| Unit | SAM3_NATIVE | Z4Q_FROZEN | R12_RAW | Z4Q_SHARED | Z4Q_DEPTH |
|---|---|---|---|---|---|
| fishsa_development_8400 | 91.313288 | 99.333472 | 81.101807 | 92.002662 | 92.002662 |
| fishsa_validation_2888 | 76.456444 | 80.697587 | 77.829601 | 76.641849 | 76.641849 |
| L3 | 72.426787 | 74.745256 | 62.838603 | 72.426787 | 72.426787 |
| LW | 60.613534 | 64.329395 | 60.613534 | 60.613534 | 60.613534 |
| Feeding_pooled1471 | 80.976760 | 81.716806 | 81.029982 | 81.716806 | 81.820716 |

DEPTH deltas are percentage points:

| Unit | ΔIDF1 vs native | ΔIDF1 vs original | ΔIDF1 vs SHARED | ΔHOTA vs native | ΔAssA vs native |
|---|---|---|---|---|---|
| fishsa_development_8400 | 0.689374 | -7.330810 | 0.000000 | 1.144648 | 2.177282 |
| fishsa_validation_2888 | 0.185405 | -4.055737 | 0.000000 | -0.150168 | -0.140758 |
| L3 | 0.000000 | -2.318468 | 0.000000 | 0.000000 | 0.000000 |
| LW | 0.000000 | -3.715862 | 0.000000 | -0.080900 | -0.188955 |
| Feeding_pooled1471 | 0.843957 | 0.103911 | 0.103911 | -0.030058 | -0.057324 |

On L3 and LW, DEPTH does change saved mappings relative to SHARED on28 and46 frames, respectively, but all official metrics remain identical. An output difference is therefore not automatically an identity-score benefit. FishSA outputs are exactly identical between SHARED and DEPTH.

## Identity-relation diagnostics

C/W/U means correct / wrong / unscorable under the scorer's unique-IoU reference relation checks. Bank endpoints, public origins, clean endpoints and at least3-frame continuous same-version consensus remain separate. These are reference-based identity diagnoses, not physical depth-surface truth. Unknown is never counted as correct.

| Arm | Durable automatic C/W/U | Explicit group C/W/U | Additional birth C/W/U |
|---|---|---|---|
| Z4Q_FROZEN | 15/17/58 | N/A | N/A |
| R12_RAW | 0/0/0 | 2/2/1 | 1/0/2 |
| Z4Q_SHARED | 11/17/50 | 0/0/0 | 0/0/0 |
| Z4Q_DEPTH | 11/16/50 | 1/0/0 | 0/0/3 |

R12 has five explicit group commits: two correct, two wrong and one unscorable under literal bank anchors. DEPTH has one explicit group commit, Feeding last segment `MS1-F35`, q39, H2: literal-bank and clean-endpoint relations are correct, but its pre-fragment consensus verdict is **unscorable**. The three added DEPTH birth commits are all **unscorable**; zero known-wrong added births is not evidence that these three are correct or safe.

The alternate consensus at R12 validation event q2600 is wrong while the literal bank verdict is unscorable; this evidence remains visible and must not be collapsed into a single confident correctness label.

## Causal contribution boundaries and common protection regression

DEPTH differs from SHARED on **639 frames**: Feeding last segment565, L3 28 and LW46. Both FishSA units and the first three Feeding units are exactly equal. **Automatic depth vetoes are zero.** The observed differences therefore come from additional group/birth transactions and their subsequent own-state consequences, rather than executed automatic-edge rejection.

The five arms change three depth-related additions together. They do not identify the independent effect of the forecast, group admission, birth logic or depth necessity. Avoidance of known R12 wrong group swaps also occurs in SHARED, whose extra group choice is always H0; improvements over R12 cannot be assigned exclusively to added depth.

Two original FishSA birth recoveries are lost in both SHARED and DEPTH, one in each segment:

| Segment / q | Missing original mapping | Survivor | Original last native observation | SHARED/DEPTH stale last | Actual intervening visibility |
|---|---|---|---|---|---|
| fishsa_development_8400 / 3902 | 7→0 | 4 | 3901 | 3862 | Every frame (39) |
| fishsa_validation_2888 / 2188 | 8→3 | 7 | 2187 | 2124 | Every frame (63) |

At development q3902, original Z4Q qualifies survivor4 and commits7→0. Both shared branches retain a stale survivor continuity record ending3862 although source4 is present in all39 intervening saved native frames; they report `native_frame_gap/native_time_gap`, missing survivor core requalification, `partner_4_related_identity_unresolved` and `no_verified_local_survivor`.

At validation q2188, original Z4Q qualifies survivor7 and reserves it by its native prior, committing8→3. Both shared branches retain last2124 despite source7 being present in all63 intervening frames. Their stale native certificate fails the same gap checks and the partner becomes `joint_core_opposed_or_ambiguous`.

Both added depth-veto records explicitly have `veto=false`. These losses therefore demonstrate a common protection/state-bookkeeping regression, not new depth rejection. Source visibility here is a recorded source fact; it is not being relabeled as clean physical identity evidence. The frozen run is preserved; this review performs no post-score repair or new trial.

## Resources and limits

The completed formal replay used at most three local single-thread prediction processes. Recorded replay wall time was **881.33s (14.69min)**; summed segment replay time **2007.77s**. Scorer elapsed time including source verification was **814.08s** (the enclosing recorded scoring command is about815.44s). Peak resident RAM was not measured. No new raw-array preparation or duplication was required.

Model HTTP, new SAM3 inference, training, completion service, GPU and server jobs are all0; experiment model cost is$0. This does not imply that the original saved SAM3/raw input generation had no cost.

All inputs are exposed development/diagnostic material. Feeding remains the original four segments1471; the other436 saved frames were not selected. L3/LW remain prediction-derived weak references. There is no independent-video blind test, underwater fish-surface depth truth or proof of physical depth accuracy.

The evaluation run is reproducible and fully reported, including its unsuccessful performance outcome. Its engineering PASS does not imply method success or authorize changing frozen parameters to improve the same run.

