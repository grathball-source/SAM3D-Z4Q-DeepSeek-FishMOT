# DS15 actual sealed group and birth output review

This is an independent **postseal, postscore** review of the actual frozen replay. It does not substitute the earlier DS14 snapshot plug-in calculations for DS15 output. No prediction, scorer, configuration, frozen source, or old result was edited in this review. Reference matches are used only to explain already sealed predictions. No trial was run by this reviewer.

## Evidence and scope

- `run/ALL_PREDICTIONS_SEALED.json`: all five arms, all eight segments, 20,098 frames sealed before reference scoring.
- `run/METRICS.json`: `SCORED_AFTER_ALL_FIVE_ARMS_EIGHT_SEALS`.
- `run/SCORE_PROVENANCE.json` and `run/SCORING_FREEZE.json`: reference opened after all seals; no GT used for predictions.
- Actual per-segment `public/EVENTS.json`, `TRANSACTIONS.jsonl.gz`, `BIRTHS.jsonl.gz`, `predictions.jsonl.gz`, `EVENT_AUDIT.json`, `AUTOMATIC_RECONNECT_AUDIT.json`, `SWITCHES.json`, and `REFERENCE_MATCHES.jsonl.gz`.
- `PRIVATE_VISUALS.json`: 24 private actual publication figures. Independently checked all image/file artifacts and 72 displayed prediction/assignment rows, including row byte hashes, canonical ledger hashes, and displayed IDs.

Code flow: `hybrid.py:17` retains an intact same-version event reference; `group_association.py:17` validates and expires the depth forecast; `group_association.py:100` calls the isolated unchanged DS9 chooser and applies changed-role depth admission. `runner.py:219` selects the actual arm rule; its group transaction or own-branch fallback is committed once before publication. There is no cross-arm state copying.

## Main outcome

| Actual arm | Group query frames | Extra group commits | Physical status of commits |
|---|---:|---:|---|
| R12_RAW | 47 | 5 | 2 CORRECT, 2 WRONG, 1 UNSCORABLE |
| Z4Q_SHARED | 50 | 0 | No extra group identity edit |
| Z4Q_DEPTH | 50 | 1 | Feeding local39: endpoint CORRECT; full pre-consensus UNSCORABLE |

The sole DEPTH group commit is Feeding local39/global1239, `n167→136`, with `n128→128` unchanged. The two R12 wrong exchanges at development4524 and L3 local1421 are avoided by **both SHARED and DEPTH**. DEPTH's actual depth arithmetic also rejects them, but their improvement over R12 is not an isolated depth contribution: SHARED already publishes the same protected-role mapping without that arithmetic. SHARED and DEPTH have identical actual development and validation predictions. Their original BIRTH_REFINE successes at3902 and11488 are both lost.

Of the 50 DEPTH group query decisions, 48 reach admission with H0, one additional edit passes (Feeding39), and one candidate is rejected by the changed-role preference check (validation2600). Neither development4524 nor L3q1421 reaches the changed-role gate: each already fails the unchanged `log(9)` joint threshold.

## Actual harmful-exchange arithmetic

All values below are saved causal decision fields, with cutoff strictly before the query for history and only the current query observation for the post pair. Scores are normalized plug-in contrasts, not calibrated physical identity probabilities.

### Development q4524

R12 swaps `n7→1,n1→7`; its original wrong margin is `4.183909583954591 − 0.071457885481 = 4.112451698474` and the swapped aliases persist through8400 (3,877 frames inclusive).

DS15 DEPTH retains A's intact9 samples4469–4477, previously lost by R12's `suspect4519−30` wall-frame crop. B retains30 samples4467–4496 and fits the last10,4487–4496. Both histories remain their own same-version contiguous fragments; no risk interval was joined.

| Quantity | A / public1 | B / public7 |
|---|---:|---:|
| Last real depth / forecast mean (mm) | 500.932662964 | 651.724639893 |
| Forecast scale (mm) | 90.675291739 | 51.246693563 |
| Query gap (s) | 1.565999985 | 0.933000088 |
| Noise-corrected median diffusion rate | 0 | 0 |

Current source depths: `n7=657.804199219`, MAD9.863342285; `n1=570.173645020`, MAD4.697631836.

| Depth edge log LR | n7 | n1 |
|---|---:|---:|
| A | -0.364857366415 | +0.338698090860 |
| B | +1.407233669063 | +0.087131553134 |

H0 has geometry `−0.846721617357`, depth `+1.745931759923`. Wrong H1 has geometry `+3.337187966598`, depth `−0.277725813281`. Therefore:

`H1−H0 = geometry 4.183909583955 + depth(−2.023657573204) = 2.160252010750 < log(9)=2.197224577336`.

The reason is `INSUFFICIENT_JOINT_ODDS`; the chooser returns H0 before per-role admission. The distance to the fixed threshold is only0.036972566586. This is evidence about this actual decision, not evidence that the resulting contrast is generally calibrated.

Actual q−1/q/q+1 publications:

| Arm | n7 | n1 |
|---|---:|---:|
| Original Z4Q_FROZEN | 0 | 1 |
| SHARED | 7 | 1 |
| DEPTH | 7 | 1 |
| R12 at q and q+1 | 1 | 7 |

Avoiding the R12 exchange does **not** restore original ID0 success. At3902, original `n7→0` was correct; both hybrids publish7. The protected survivor's native run remains at3862 rather than original3901, so the original recent survivor witness is unavailable. The candidate0 remains depth UNKNOWN with vetoFalse; the loss is caused by shared protected-state interactions, not the depth veto. See `POSTSEAL_STRATEGY_REVIEW.md` for the detailed original candidate trace.

### L3 localq1421 / global1420

R12 swaps `n9→6,n6→9` with geometry margin2.321974410067 and no usable old depth. In DEPTH both pre-fragments1316–1345 survive the event freeze; each has30 observations, fitting1336–1345. A/public6 mean684.849639893, scale130.806922975; B/public9 mean634.687438965, scale132.078272171; both query gaps2.519000053s. Median noise-corrected diffusion is0 for each.

Current depths: `n9=624.343780518`, MAD18.710113525; `n6=672.963684082`, MAD15.250244141.

| Depth edge log LR | n9 | n6 |
|---|---:|---:|
| A | -0.081159112492 | -0.583659790045 |
| B | +0.019169407908 | -0.628470612300 |

H0 geometry4.894146375596, depth−0.564490382137; wrong H1 geometry7.216120785663, depth−0.709629724792:

`H1−H0 = 2.321974410067 − 0.145139342655 = 2.176835067412 < 2.197224577336`.

Again H0 is returned before per-role admission, only0.020389509925 below the fixed threshold. The A role's normalized depth contrast actually prefers wrong n9 to n6; the B opposition makes the total negative. Thus a depth log LR should not be read as a nearest-depth classifier or a verified physical posterior. Original, SHARED, and DEPTH all keep `n6→6,n9→9`; the physical audit calls R12's committed exchange WRONG, including its pre-consensus comparison, while the dataset's annotation coverage remains limited.

### Validation localq2600 / global11900

The DEPTH joint chooser would accept H1: geometry delta3.298573555248, depth delta−0.257511892960, total3.041061662287>log9. The changed-role gate rejects it:

- A/public1 selected n4 log LR2.069044781379 versus lawful baseline n1 log LR2.137602656029.
- A preference is−0.068557874650. B preference is also negative (−0.188954018310).
- `GROUP_CHANGED_IDENTITY_NONPOSITIVE_DEPTH_PREFERENCE`; no alternate candidate is then searched to force a swap.

This is the only actual non-H0 group proposal rejected by the new changed-role gate. Its R12 first-public endpoint status is UNSCORABLE, though its committed full-pre comparison is WRONG. Do not count this gate rejection as one additional verified physical success.

## Feeding local39: one changed identity, immediate output and later state effects

### Admission arithmetic

Unchanged A/public128 has only one clean sample, frame19. Its last-value mean is1163.571228027, uncertainty303.264018547mm; it is not invented two-identity evidence. Changed B/public136 has seven causal samples16–22, mean1155.730895996mm and scale49.530872456mm at query39.

The selected B:n167 depth log LR is+0.109409760565. The same role's alternative B:n128 is+0.031723862740. Its positive depth preference is+0.077685897825. Both current pair measurements and the background are usable. H2−H0 total depth margin is+0.109409760565 and the unchanged joint best-to-runner H1 margin is2.951595230034>log9.

Only B changes from H0, so only B is admitted. A's selected depth LR is−1.099370829214 and the H2 total depth LR is−0.989961068649; demanding all selected edges or both histories be strongly positive would incorrectly discard this allowed one-identity restore. Conversely, the one unchanged A observation cannot support a claim that both physical identities were verified by depth. Postscore endpoint mapping is CORRECT; the full-fragment pre-consensus is UNSCORABLE because A lacks the required three matched history observations.

### Actual divergence begins at39, not142

Saved predictions at39 and40 publish `n167→167` in FROZEN/SHARED versus `n167→136` in R12/DEPTH. The first SHARED↔DEPTH map difference is **local39/global1239**. At preframe40 SHARED alias targets are empty; DEPTH has `167:136`. There are exactly565 differing frames39–706, with gaps when the affected sources are absent:

| Source | SHARED ID → DEPTH ID | Number of affected frames | Inclusive range |
|---|---|---:|---|
| n167 | 167→136 | 101 | 39–139 |
| n170 | 167→136 | 25 | 160–184 |
| n168 | 136→168 | 11 | 204–214 |
| n176 | 167→136 | 414 | 266–679 |
| n197 | 167→136 | 14 | 693–706 |

The reference endpoint of n167 corresponds to GT4. Later automatic n170, then n176, inherit the corrected public136 history rather than a new167 chain. This is an actual immediate identity preservation followed by controller-state effects.

At203, SHARED bank136 still references native136/frame22. DEPTH bank136 references native170/frame166. At204, SHARED accepts wrong D1 `n168→136` using its stale frame22 bank: age6.048s, cost0.030686999, partner margin179.708862305mm. DEPTH's corresponding bank candidate now uses frame166: age1.263s, cost0.188883253, partner margin−1.020202637mm versus required25mm, so the **original partner_ambiguous rule** rejects it. DEPTH retains n168's lawful168. This is not an automatic depth veto: none of the10,850 saved DEPTH automatic candidate checks vetoes an edge.

The chain is not wholly safe. At693/global1893, both controllers accept wrong D1 n197; its target is167 in SHARED and136 in DEPTH. The actual native query is GT22, while the inherited bank/public origin is another fish. Correcting one earlier identity does not validate later automatic transfers of that public ID.

### Exact metric contribution

The last Feeding segment improves SHARED→DEPTH IDF1 from81.525934542378 to81.742716649923 (+0.216782107545 points), HOTA79.892513138026→80.047506792200, and IDSW54→52. All other Feeding segment predictions are equal between these arms. Consequently pooled Feeding IDF1 rises81.716805636516→81.820716222723 (+0.103910586208), IDSW132→130; FP/FN and detection counts are unchanged.

Using the reported GT/prediction denominators, these IDF1 values imply **41 more globally assigned ID true positives**: last segment15,419→15,460; pooled32,243→32,284. This is the arithmetic explanation of the reported IDF1 difference, not a count of41 independently established depth decisions.

`SWITCHES.json` identifies the two removed switches:

1. global1239, GT4, n167: SHARED136→167; DEPTH retains136 at the group query.
2. global1404, GT5, n168: SHARED168→136; DEPTH retains168 because the updated old bank candidate is partner-ambiguous.

Other switch records have different public labels along the136/167 chain but the same number of switch events. No fresh counterfactual replay was used to separate these downstream contributions. The current comparison establishes the contribution of the complete DEPTH arm relative to SHARED; it does not establish depth necessity at every causal step.

## Known correct R12 paths that DS15 does not reproduce

R12's Feedingq545 restore `n190→188` is endpoint/pre-consensus CORRECT. However, SHARED and DEPTH do not contain the same q545 episode: they enter a different episode at528, resolving at532 with native146/176. At545 both publish n190 as190. Therefore the actual loss is already present in the shared state trajectory; it is **not an actual q545 rejection by DEPTH's missing-depth gate**.

The old sealed snapshot remains a useful design counterexample: q545's n190 core MAD41.070556641 gives robust scale60.891207275>60, disabling common paired depth, despite a correct geometry restore. A strict extra-edit depth admission trades away such correct geometry-only cases in that snapshot. It was not repaired by threshold tuning or pretending missing data supports a match.

At local686/global1886, R12's additional `n198→176` birth is physically CORRECT; original/SHARED/DEPTH all publish198. The three-frame figure displays this loss as well as the earlier n190 alias difference. Do not claim DS15 preserves R12's two known correct repairs or original's actual birth strengths merely because the original automatic functions remain enabled.

## Three actual additional DEPTH births: unknown physical result

All three accepted additional DEPTH births pass the saved causal positive-depth and joint-log9 rule, yet **all are UNSCORABLE**, with query/bank/public-origin reference relations UNKNOWN. They are neither demonstrated successes nor demonstrated safe edits.

| Local/global query | Actual change | Geometry log LR | Depth log LR | Joint margin to NEW | History mean / scale (mm) | Current scored depth (mm) |
|---|---|---:|---:|---:|---|---:|
| L3 669/668 | n19→18 | 3.419664516481 | +0.121925343186 | 3.541589859667 | 543.266815186 /139.251333837 | 585.270812988 |
| L3 735/734 | n21→20 | 2.645860969978 | +0.106170730791 | 2.752031700769 | 588.668334961 /122.089194531 | 589.712646484 |
| LW 2065/2064 | n88→85 | 2.927416990303 | +0.212116087516 | 3.139533077819 | 778.404205322 /28.063294124 | 770.688507080 |

Each uses three unique candidates including NEW, equal log prior−1.098612288668, with NEW runner-up. The geometric term alone already exceeds log9 in all three; depth satisfies the required positive admission and adds the listed modest margin. There is no basis for claiming that depth was numerically necessary to beat the ranking threshold.

L3n19 uses10 clean samples581–590, gap2.616999865s; bank/reference endpoint590. L3n21 uses7 clean samples684–690, gap1.490999937s; bank/reference endpoint690. LWn88 uses10 clean depth samples2045–2054, gap0.365000010s, while its actual geometric bank anchor is2052 and clean reference endpoint2054. Anonymous risk observations after the last clean sample are retained as risk, not fed into the forecast.

Actual changed publications persist22 frames669–690,6 frames735–740, and46 frames2065–2110 respectively. Independent reference-row inspection found **zero unique physical matches for every affected source in all those frames**. DEPTH and SHARED L3/LW aggregate metrics are equal, because this score does not resolve those modified fragments. Unchanged metrics cannot validate edits outside physical-reference coverage.

## Metric comparison and shared-state limitation

| Segment | Original IDF1 | R12 IDF1 | SHARED IDF1 | DEPTH IDF1 |
|---|---:|---:|---:|---:|
| Development8400 | 99.333472 | 81.101807 | 92.002662 | 92.002662 |
| Validation2888 | 80.697587 | 77.829601 | 76.641849 | 76.641849 |
| L3 | 74.745256 | 62.838603 | 72.426787 | 72.426787 |
| LW | 64.329395 | 60.613534 | 60.613534 | 60.613534 |
| Feeding pooled | 81.716806 | 81.029982 | 81.716806 | 81.820716 |

DEPTH gives the measured small Feeding gain over SHARED. It preserves the same inferior shared trajectory on development/validation and has no verified L3/LW metric gain over SHARED. Both hybrids lose original correct BIRTH_REFINE `n7→0` at3902 and `n8→3` at global11488 because protection freezes survivor witnesses used by those automatic paths. Original successful automatic edges outside protection cannot be treated as preserved outcomes without inspecting the protected state they later consume.

## Private figure and binding review

The frozen `visualize.py` failed before its first figure: it compared the actual uncompressed gzip row bytes (Windows CRLF) with the runner's canonical JSON+LF ledger hash. The frozen source and failure record were preserved. A new presentation-only `visualize_postseal.py` binds these separately: actual uncompressed row-byte SHA, canonical JSON body SHA, and canonical JSON+LF SHA. Only the canonical LF SHA is compared to the publication ledger; the complete saved gzip artifact remains seal-pinned.

The parent generated the new figures after scoring. This reviewer verified all24 figure inventories and72 row bindings and viewed the fixed development4524/L3q1421 failures, both lost original births, and all three unscorable additional births. Their q−1/q/q+1 labels agree with actual sealed mappings and common raw-depth/mask crops. The L3q669 label lies close to the left crop boundary; the exact mapping is also fully retained in the inventory. Displayed contours/pixels alone are not physical identity ground truth. Gray context contours also have their actual published IDs; they are not promoted to verified physical endpoints.

The figures use raw depth, no RGB/reference pixels, identical depth scales across arms in each case, and actual published IDs. The displayed q+1 is postscore explanation only, never prediction input. `PRIVATE_VISUALS.json` records absolute file paths, bytes, SHA256, actual mappings, raw source bindings, and the verified seal chain. No pixel/RLE artifact is placed in a public numeric plot.

## Interpretation to retain

1. Actual event history retention makes depth available where the wall-frame crop lost it; local-level means avoid the old WLS extrapolation failure.
2. The two wrong exchanges fail the existing joint threshold before the changed-role gate. They are already avoided by SHARED; their repair cannot be solely attributed to depth.
3. Positive changed-role preference blocks one actual extra candidate at validation2600 and permits one physically correct one-role Feeding edit without requiring impossible perfect history for the unchanged role.
4. Feeding's +0.103910586 pooled IDF1 and−2 IDSW are traceable to the actual q39 alias and the subsequent q204 old-rule rejection; later wrong automatic commits remain.
5. Missing paired depth and protected survivor-state changes have real false-negative costs. Both original correct BIRTH_REFINE successes and R12's correct q545/1886 paths are not reproduced.
6. Three additional births alter74 unscorable source-frames. The present score cannot certify their safety. No threshold was retuned from these outcomes.

