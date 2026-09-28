# MS1-S0 final review — first split before first publish

**Main verdict: FAIL for physical identity recovery in this frozen one-event trial.** The engineering timing contract passed: F2600 was decided and committed before its only public write, with evidence ending at F2600. Both model and numeric branches chose H1, which is wrong relative to the pre-event physical members under the separately stated clean-fragment consensus. B-VLM-S0 had **zero incremental tracking benefit** over B-HOLD-S0. This is an exposed-validation, single-event result and does not establish a general impossibility for event-history association.

## Contract and actual first publication

The unchanged prediction-only scanner yielded one selected opportunity: first suspect F2586, two-frame merge confirmation F2587, first two-candidate split F2600. Both protected branches set `q=split_first_frame=evidence_cutoff_frame=2600` and used exactly one post observation each for X and Y. The S0 user body contains the frozen pre histories, group/risk record, geometry/depth quality, one current X/Y observation, pre OLS estimates, pairwise comparisons and the new M hypothesis marked as such. Its post velocity is UNKNOWN and it has no F2601–F2604 measurement. Changing every later assignment in the test copy left the S0 request byte-identical. The M/S0 images are actual prediction-mask geometry and anonymous context; RGB and GT were not sent.

`Bridge.preview` only produced an internal uncommitted mapping. At F2600 the branch selected, staged and committed its one-to-one restore before `publish_once` wrote the current prediction. The publication ledger has one hash-bound entry for each of 2,888 frames, including the first X/Y public IDs; the scorer rechecked every row hash. No frame was rewritten after a later answer. This is a **synchronous causal replay**: S0 took 113.890 seconds and the F2600 receive-to-first-publish time was 115.421 seconds. It is not real-time deployment.

| Frozen reference or current observation | Public ID at the event | Postseal physical GT |
| --- | ---: | ---: |
| Pre A, F2580:O01 | 1 | last anchor UNSCORABLE; 13-frame clean-fragment consensus 6 (8 matched) |
| Pre B, F2580:O02 | 4 | last anchor 2; 13-frame consensus 2 (13 matched) |
| First split X, F2600:O01 | 1 | 2 |
| First split Y, F2600:O02 | 4 | 6 |

Thus H1 (A→X, B→Y) was **WRONG** against the pre-fragment consensus; H2 (A→Y, B→X) was **CORRECT** in this postseal audit. The literal last pre anchor alone cannot score A, so its candidate verdict remains UNSCORABLE. This H2 result was never supplied to the predictor or used to select the event, reference, q or action. The actual first publication was X→1 and Y→4 in both protected branches. The model's original H1 was parseable; all ten cited frame-local facts existed in the S0 input, but citation existence does not validate its interpretation.

The entry state already associated public ID 1 with physical GT6 and ID 4 with GT2, while long-run first-matched public-ID diagnostics associated ID 1 with GT2 and ID 4 with GT6. The H1 swap at the event consequently improved whole-video agreement with long-run labels while **breaking continuity with the two physical members entering this event**. The global metric gain is an accidental repair of pre-existing public-ID error, not a correct merge–split physical restore. There were zero later public-ID switches for those physical members in the exposed postseal follow-up; no three consecutive correct pair frames appeared through F2888 (282 pair-assessable frames). No later strict predicted merge opportunity was selected; unobserved physical remerge is not ruled out.

## Full 2,888-frame result

All three arms ran independent controller states on the same masks. B0 exactly reproduced the archived Z4Q branch. Mask sets, FP and FN were unchanged. The all-DEFER dry B-VLM-S0 exactly matched B-HOLD-S0.

| Branch | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 80.6976 | 69.2439 | 60.0743 | 9 | 298 | 423 |
| B-HOLD-S0 | 82.0707 | 69.4101 | 60.3642 | 11 | 298 | 423 |
| B-VLM-S0 | 82.0707 | 69.4101 | 60.3642 | 11 | 298 | 423 |
| B-VLM-S0 − B0 | +1.3732 | +0.1662 | +0.2899 | +2 | 0 | 0 |
| B-VLM-S0 − B-HOLD-S0 | 0 | 0 | 0 | 0 | 0 | 0 |

Relative to archived MS1-R, moving q from F2604 to F2600 changed **zero** output frames in either protected branch. This trial establishes the new first-publish timing and one-point request semantics; it cannot claim a metric improvement from earlier timing, and the old S response was never used for this run. One event is one recovery opportunity.

## Mechanism and limits

The numerical comparison now uses eligible pre OLS extrapolation even with a single post point: `pre_prediction_available=true`, `post_velocity_available=false`, `velocity_comparison_available=false`. For this event the frozen scores were H1 1.9264 and H2 2.3055. Core depth failed the existing symmetric quality rule, so depth contributed to neither candidate. The pre predicted centers were ESTIMATED, with in-sample residuals about 10.00 px for A and 4.05 px for B; they were not treated as observed paths inside the merge. The model also chose H1, emphasizing its reading of B→Y continuity despite acknowledging UNKNOWN post velocity and group-internal uncertainty. The physical crossing/identity outcome at F2600 shows that this one-point spatial explanation was wrong here. No prompt, history window, threshold, numeric weight, anchor or model backend was adjusted after observing the result.

The main evidence is [the first-split result](run_ms1s0_20260928/public/FIRST_SPLIT_RESULTS.json), [physical audit](run_ms1s0_20260928/public/PHYSICAL_EVENT_AUDIT.json), [full metrics](run_ms1s0_20260928/public/METRICS.json), [follow-up](run_ms1s0_20260928/public/FOLLOWUP_AUDIT.json), [old-run comparison](run_ms1s0_20260928/public/OLD_MS1R_COMPARISON.json), [prediction seal](run_ms1s0_20260928/public/PREDICTIONS_SEALED.json), [publication ledger](run_ms1s0_20260928/public/PUBLISH_LEDGER.jsonl), and [geometry-only contact sheet](run_ms1s0_20260928/public/MS1_THREE_BRANCH_CONTACT_SHEET.png). [Acceptance](run_ms1s0_20260928/public/ACCEPTANCE.json) checks the frozen source/code, request/body START, response/END, prediction/score and image hashes. The optional scorer import warning about missing `tabulate` did not affect required TrackEval metrics.

## Requests, reproducibility and boundaries

Official `deepseek-flash` made 2 inference HTTP requests: one M and one S0 for the only eligible event; 0 smoke, 0 retries, 0 unknown HTTP, 0 selected unsent. Recorded tokens were 70,628 input and 29,202 output. The [current official pricing](https://api-docs.deepseek.com/quick_start/pricing/) gives a conservative peak-rate usage upper bound of **$0.0562308**, below the separately authorized 16-request/$4 cap; actual provider billing was not independently fetched. M latency was 30.062 seconds, S0 latency 113.890 seconds, and the full replay wall time was 172.25 seconds. Every logical request and response is new to this run.

The code, config, tests, prompt, budget, public request/response records, ledgers, full predictions, scores, visuals and reports are in this directory. [Local](run_ms1s0_20260928/public/RESTRICTED_INVENTORY.json) and [lab-host](run_ms1s0_20260928/public/REMOTE_RESTRICTED_INVENTORY.json) metadata give actual restricted paths, byte counts, SHA-256 and reproduction dependencies. API key, private wire and provider file IDs, private RGB and GT raster are excluded from Git. The score used exposed validation GT only after the prediction seal; it is not a blind-test result. This experiment did not train, add a tracking module, change the merge trigger or alter old seals.

**One next step:** audit whether F2600's frozen pre/group/first-split geometry and depth contain enough causal information to distinguish H1 from H2 without tuning on this event; use that audit to decide whether the S0 protocol merits another frozen validation set.
