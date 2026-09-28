# MS1-R final review: observation and state repair, full 2,888-frame replay

**Judgment:** the requested state and measurement repair passed targeted checks and the three full state replays completed. The one selected event still produced a physically wrong H1 mapping in both protected branches; B-VLM-R had **zero incremental output or metric effect** over B-HOLD-R. The numerical improvement over B0 is real on this exposed validation segment, but remains an accidental public-label correction. Stop this frozen MS1-R version. This is not an event-recall or blind-test claim.

## Scope and state evidence

The prediction-only scan output is byte-identical to MS1 (`609ce573…76e453d`) and contains one strict qualifying opportunity, F2586. The same local graph, coverage, area/presence rules, 30-frame cache, 2-frame merge confirmation, 5-frame post window and 10-second timeout were used. The raw F2586 output still includes a large group mask **and a small residual mask**; the residual was not deleted. Fifteen count-drop transitions remain lost/out of scope. The trigger's total event recall is unknown.

`MergeSplitManager` now labels measured group, unassigned post and source observations separately. Even a large group mask with no reported neighbor cannot enter either member's `clean` or `last_clean`. The pending X/Y observations stay in the event's temporary post store until the atomic restore; failure, timeout or scope exit clears local reference candidates. Source continuity, source generation, public mapping epoch and controller bank history have separate meanings. Sensor synchronization and independent source epoch certification were unavailable. The old pre-entry anchors were not changed. `GroupBridge` protects public-keyed banks/views and native-keyed aliases/runs separately; the collision tests keep reserved banks and unrelated aliases intact. The q transaction releases protection even when its output-ID delta is empty.

The model packet uses intercept OLS on the latest ten contiguous observed points with actual timestamps. It reports samples, time span, velocities, speed, axis and 2D RMS residuals, prediction interval and the fact that residuals are *in-sample*, not calibrated forecast bounds. At F2580 the pre A/B 2D RMS residuals were 10.003/4.046 px. F2604 Y's actual mask had 26 eight-connected pieces and a 57.16 px mask-centroid/bbox-center offset; these degrade position interpretation. Its raw/core depth summaries retain `n`, valid fraction and MAD, with mixture status `UNKNOWN_FROM_AGGREGATES`. One valid pixel at fraction 1 is marked insufficient under the existing Z4Q 16-point rule. B's pre core depth had `n=0`, so numerical core depth was omitted **for both H1 and H2**. The unchanged source scanner's short-term prediction formula and the new association-evidence OLS are distinct; their effects are not conflated.

Eight focused tests passed. The dry 2,888-frame all-DEFER run reproduced archived B0 exactly and made the two protected arms identical, with every raw mask retained. Actual token→source bindings were checked against RLE mask order, including zero-area masks. See [TEST_REPORT.json](TEST_REPORT.json), [budget preflight](BUDGET_PREFLIGHT.json), [freeze](run_ms1r_20260928/public/FREEZE.json) and [acceptance](run_ms1r_20260928/public/ACCEPTANCE.json).

## Actual event and decisions

| Frame | Observed transition and branch action |
| ---: | --- |
| 2586 | First suspect. Freeze two old public banks and local pre references before the step. One group mask and a small anonymous residual are kept. |
| 2587 | Merge confirmed. One new M call; M only offers a revisable hypothesis. |
| 2600 | Two actual post masks start X/Y; the numerical H1 mapping is provisional. |
| 2602 | Three-frame split confirmation. No identity reference is certified from temporary post. |
| 2604 | Five-frame q. One new S call returns raw H1; numerical choice is also H1. Each branch commits `stage_group_restore` with zero q-frame ID delta and continues its own state. |
| 2888 | All three branches finish and their predictions are sealed before GT scoring. |

M's complete 1,400-character parsed JSON and `uncertainty` field were passed to S, without the old raw 1,000-character cutoff. The S raw choice was H1 with parser status OK. Eight of nine model `evidence_refs` were present; `time_alignment:H1/H2` was not an actual provided fact ID. This citation defect is reported separately; the one-shot H1 action was not replaced after seeing the score. Numerical H1 had score 2.974739 versus H2 3.539524 under the frozen weights; the depth term was absent from both. No vote, retry, response reuse or GT-guided action occurred.

## Full-sequence TrackEval result

| Arm | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 80.697587 | 69.243869 | 60.074321 | 9 | 298 | 423 |
| B-HOLD-R | 82.070744 | 69.410059 | 60.364198 | 11 | 298 | 423 |
| B-VLM-R | 82.070744 | 69.410059 | 60.364198 | 11 | 298 | 423 |
| B-VLM-R − B0 | +1.373157 | +0.166190 | +0.289876 | +2 | 0 | 0 |
| B-VLM-R − B-HOLD-R | **0** | **0** | **0** | 0 | 0 | 0 |

B-HOLD-R and B-VLM-R are identical in all 2,888 frames. Each differs from B0 in 297 frames, only on the two event-member source handles; nonmembers and all raw mask keys are unchanged. Relative to the *old* MS1 protected branches, each repaired branch differs in only eight group-frame residual output IDs. Within the first continuous residual source run the temporary ID is stable at `-1000000`; after a gap it is `-1000001`. The full metrics remain numerically identical to old MS1. The new state contracts and richer model evidence therefore did not yield a different final mapping in this episode. See [metrics](run_ms1r_20260928/public/METRICS.json), [old/new diff](run_ms1r_20260928/public/POSTSEAL_OLD_NEW_COMPARISON.json), [transaction log](run_ms1r_20260928/public/TRANSACTIONS.jsonl.gz) and the [three-arm contact sheet](run_ms1r_20260928/public/MS1_THREE_BRANCH_CONTACT_SHEET.png).

## Physical identity versus public labels

The literal last A reference at F2580 has no unique GT match, so the **last-anchor verdict stays UNSCORABLE**. The already frozen, contiguous F2568–F2580 pre fragment separately has A matched to GT 6 in all 8 matchable frames and B to GT 2 in all 13; the fixed post F2600–F2604 fragments give X=GT 2 and Y=GT 6 in all 5 frames each. That *postseal fragment consensus*, not a substituted last-frame truth, judges H1 wrong on both physical edges and H2 correct. The pre source and public epochs are stable; X/Y remain explicitly unassigned, so their recorded null public epochs do not certify identity. The private sent-time token binding is cross-checked against rebuilt mask order. See [physical audit](run_ms1r_20260928/public/PHYSICAL_EVENT_AUDIT.json).

At entry A had public 1 while its fragment corresponds to physical GT 6, and B had public 4 while its fragment corresponds to GT 2. In the full B0 sequence the first matched public-label diagnostic maps public 1→GT 2 and public 4→GT 6. The physically wrong H1 put X=GT 2 onto public 1 and Y=GT 6 onto public 4, incidentally aligning the exposed public labels. Of 586 changed B0→B-VLM-R detections, 571 moved toward these first-matched labels, none away, and 15 were unscorable by this diagnostic. IDSW still increased by two. Thus the shared score gain does not establish physical identity recovery, and none of it is uniquely attributable to VLM. See [mechanism audit](run_ms1r_20260928/public/MECHANISM_AUDIT.json).

## Requests, provenance and limits

Two fresh official `deepseek-flash` inference HTTP requests completed: M 32.375 s and S 84.625 s; synchronous full replay wall time 138.36 s. There was no smoke, retry, unknown HTTP or selected unsent request. Recorded usage was 76,314 input and 23,056 output tokens. At the [current official peak rates](https://api-docs.deepseek.com/quick_start/pricing/) the usage-based upper estimate is **USD 0.0505614**, below the 16-request/USD 4 cap; actual provider billing was not separately retrieved. Seventeen geometry image references used thirteen unique Files API uploads. No RGB texture, private file ID, credential, GT raster, hidden-test GT, training, DAA or E2 entered the model or Git.

The scorer ran only after the prediction seal, on the lab host with the original TrackEval implementation and unchanged exposed-validation assignment/truth/matches. The [score provenance](run_ms1r_20260928/public/SCORE_PROVENANCE.json) and [source manifest](run_ms1r_20260928/public/SOURCE_MANIFEST.json) bind the hashes. The [restricted local](run_ms1r_20260928/public/RESTRICTED_INVENTORY.json) and [remote](run_ms1r_20260928/public/REMOTE_RESTRICTED_INVENTORY.json) inventories list real paths, bytes, SHA-256 and reproduction requirements without publishing their content. The 30-frame history capacity, five post frames and maximum ten-point motion fit were respected. OLS does not certify fish identity or a hidden path, and one strict event cannot establish general merge–split coverage.

**One next step:** perform a read-only, GT-free audit of how the degraded Y mask geometry and uncalibrated depth evidence influenced the H1 comparison and S citations; preserve this seal and make no new paid call in that audit.
