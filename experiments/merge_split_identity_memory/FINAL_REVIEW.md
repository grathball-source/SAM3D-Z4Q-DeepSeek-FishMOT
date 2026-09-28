# MS1 final review: automatic merge–split, full 2,888-frame replay

**Judgment: the three full state replays and two real model stages completed; the exposed output score rose, but the selected physical identity explanation was wrong and B-VLM added zero over B-HOLD. Stop this frozen MS1 run.** This is one exposed validation sequence, not a blind generalization result. No fixed B01/B03/B04/B05 trigger, RGB texture, ReID feature, GT-directed action or saved old model answer was used.

## Full-sequence result

The three arms began with separate Z4Q states, consumed the same 2,888 raw mask lists, and were scored only after the full predictions were sealed. B0 matched the archived Z4Q output exactly. The original official TrackEval path and prediction/GT source hashes are in `run_ms1_20260928/public/SCORE_PROVENANCE.json`.

| Arm | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 80.697587 | 69.243869 | 60.074321 | 9 | 298 | 423 |
| B-HOLD | 82.070744 | 69.410059 | 60.364198 | 11 | 298 | 423 |
| B-VLM | 82.070744 | 69.410059 | 60.364198 | 11 | 298 | 423 |
| B-HOLD − B0 | +1.373157 | +0.166190 | +0.289876 | +2 | 0 | 0 |
| B-VLM − B-HOLD | **0** | **0** | **0** | 0 | 0 | 0 |

B-HOLD and B-VLM were identical in all 2,888 prediction frames. Both differed from B0 in 297 frames, only on the two group member source handles; all other objects' output IDs and every raw mask key stayed unchanged. B-HOLD and B-VLM each executed one real atomic group-restore transaction. Its q-frame output-ID delta was empty because the provisional split mapping already equaled the selected H1, but the transaction cleared group protection, installed the pair association in the controller, and affected subsequent state. `RESOLVE_NO_ID_CHANGE` is a committed resolution, not an output-file rewrite. The protected pre-entry bank records were equal to their first-suspect snapshots until this transaction; the synthetic new-native and next-frame state tests also passed.

## Automatic event and model decisions

The quality-gated, actual-mask compatibility scan found **one** strict two-source/one-mask opportunity. It was selected as the earliest qualifying confirmed episode; no later event was substituted. Fifteen other quality-count-drop transitions were explicitly logged as lost or out of scope. A high count of contact/third-compatible *frames* in the diagnostic graph is not a count of independent events.

| Event phase | Validation frame | Action |
| --- | ---: | --- |
| First suspect | 2586 | Freeze A/B branch-local public IDs and individual references before the Z4Q step; one measured group mask, residual tiny mask anonymous. |
| Merge confirmed | 2587 | M request; descriptive, no ID edit. |
| Two-mask short fragment starts | 2600 | X/Y named by first split spatial order; fixed numerical provisional mapping. |
| Split confirmed | 2602 | Third consecutive valid two-mask frame. |
| Final association q | 2604 | Fifth consecutive post frame; S requested and H1 returned. |
| Full run ends | 2888 | Both protected branches continue from their own resolved state. |

The actual model M response analyzed a merge hypothesis and alternatives; it did not assign X/Y. At S, the model chose `H1` (`A→X, B→Y`) with nine provided fact references, all syntactically present. Its stated support leaned on pre/post depth and motion/directional proximity; it acknowledged unobserved internal trajectories, yet the complete choice was wrong against the fixed clean-segment physical identities. The frozen numeric selector also chose H1. Core depth was unavailable on one pre member, so the numeric paired comparison omitted its depth term for **both** H1/H2; no missing edge received a zero-cost advantage. B-VLM therefore supplied no incremental state or metric effect in this run. M's independent contribution cannot be inferred because there was no M ablation.

## Postseal physical audit and why the metric rose

The literal last clean A reference at F2580 has no GT match; the anchor-only verdict remains **UNSCORABLE** in both scorer records. The *entire already frozen, source-contiguous clean fragment* F2568–F2580 gives 8 matched A frames, all GT 6, and 13 matched B frames, all GT 2; the five post frames give X=GT 2 and Y=GT 6 throughout. This fixed-fragment consensus makes H1 wrong on both physical edges and H2 correct. The scorer did not move the reference, choose a better frame, or feed GT back into the action. Both the literal missing anchor and the segment-consensus inference are displayed in `PHYSICAL_EVENT_AUDIT.json`.

At entry A carried public ID 1 but its clean segment was GT 6; B carried public ID 4 but was GT 2. In the full B0 sequence's first-matched public-ID diagnostic, public 1 corresponded to GT 2 and public 4 to GT 6. Applying the **physically wrong** H1 assigned X=GT 2 to public 1 and Y=GT 6 to public 4, accidentally fixing those already reversed public labels. Across the sealed B0→B-VLM diff, 571 matched changed detections moved toward those public-ID labels, none moved away, and 15 changed detections were unscorable under that diagnostic. This explains the genuine IDF1/HOTA gain without claiming successful physical re-identification. ID switches increased by two. `MECHANISM_AUDIT.json` and `OTHER_FISH_AUDIT.json` give the frame and member counts.

This result separates three claims: the group-state protection was genuinely implemented and exercised; the exposed output metric improved; neither the model's physical mapping nor its increment over the same protected numeric arm succeeded. A return to or rise above B0 is not by itself proof of a correct identity mechanism.

## Calls, source, and limits

Exactly two official `deepseek-flash` inference HTTP requests were sent: M at 21.609 seconds and S at 57.516 seconds; total inference latency 79.125 seconds, synchronous replay wall time 99.328 seconds. Both returned normally, with no technical smoke, retry, unknown HTTP or unsent selected request. They used 29,530 input and 16,302 output tokens in total. By the current [official peak rates](https://api-docs.deepseek.com/quick_start/pricing/) of USD 0.30/M cache-miss input and USD 1.20/M output, the usage-based upper estimate is **USD 0.0284214**, well below the 16-request/USD 4 cap. Actual provider billing was not separately retrieved. Seventeen image references came from thirteen unique geometry PNGs uploaded through Files API; no RGB or provider file ID is public.

The 30-frame history capacity was respected; the actual pre-entry clean fragments contained 13 consecutive frames each, and post fragments five each. The model received every measured group time, low-quality residuals as anonymous observations, core/whole depth and quality fields, fixed-coordinate actual mask diagrams, and explicit fact IDs. The code uses a first-to-last secant over up to the latest ten consecutive valid points, with fewer than three marked `UNKNOWN`. **This is a recorded protocol limitation:** it uses the specified window and never crosses risk, but it is not a least-squares fit through all ten points as the plan's word “fit” could require. The strict graph's frequent third-compatible diagnostic frames also limit event recall. These are frozen implementation facts, not parameters adjusted after seeing the score.

Seven pre-call engineering checks passed. The original masks, old B1/B2 seals, model budget, source hashes and prompt copy are preserved. The run did not train, restart DAA, read hidden test GT or enter E2. The contact sheet `run_ms1_20260928/public/MS1_THREE_BRANCH_CONTACT_SHEET.png` shows pre-merge, first protection, group, split pending, q and post-q across all three arms; it contains no RGB or GT raster. The model-visible 17 geometry images, request text, public responses, ledger, freeze, prediction seal, score and full restricted-source paths/sizes/hashes are listed in the public manifests and `ACCEPTANCE.json`.

**One next step:** before a new paid trial, make the ten-point motion fit and local third-member gate pass a GT-free source-contract audit on fresh event opportunities; keep this MS1 seal unchanged.
