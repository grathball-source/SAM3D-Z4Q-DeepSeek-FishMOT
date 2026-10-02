# DS14 group depth audit for the DS15 strategy repair

Date: 2026-10-02. Audited repository HEAD: `95f1a83172d6b90f36ff8bd5a7d948e74b42ae80`.

This is a read-only audit of saved, already sealed DS14 decisions and post-seal reference analysis. No old source, prediction, threshold, state, or seal was changed. No controller trial, model inference, API, GPU, or server job was run. Local arithmetic substitutes the existing local-level forecast into each saved independent q snapshot; it is not a counterfactual sequential replay and does not establish end-to-end tracking gains.

## Actual code path and root cause

- `ds14_raw_multidataset/runner.py:19–20` explicitly loads the frozen DS9 group association module. At `runner.py:174–175` it freezes the existing DS1 depth history on the first suspect frame. At `runner.py:195` it calls that DS9 chooser, and at `runner.py:200–202` it either stages the selected group permutation or adopts its own lawful causal fallback.
- `ds9_joint_h0_depth/association.py:7` imports `depth_state.predict`, which resolves to DS1 through DS14's search paths (`ds14_raw_multidataset/common.py:10,26`). DS9 `choose` calls it at lines 167–174. DS1 `depth_state.py:80–131` estimates WLS slope with three or more samples. Its query mean extrapolates across the complete gap, unlike the capped geometry mean.
- Birth reconnect uses a different predictor: DS14 `reconnect.py:18–24` loads DS11, whose `reconnect.py:14` imports `forecast.predict`; DS14's same-named module provides the local-level forecast. Its one/two-sample path preserves the old last-value/gap-prior fallback, while `forecast.py:55–57` uses the last real measurement for longer fragments and leaves velocity UNKNOWN.
- DS9 computes a common depth background, makes paired current depth uninformative if either post measurement is unusable (`association.py:165,183–215`), and retains missing-role depth as LR 0. These are useful fairness rules. However, admission at `association.py:252–255` checks only the sum of geometry and depth against `log(9)`. It does not require any changed identity to have depth support, nor require depth to prefer the proposed permutation over the lawful baseline. Geometry can therefore force an exchange that depth opposes, and can force an exchange with both depth histories missing.
- The old pair cost in `ms1_s0_development_8400/merge_split_manager.py:232–291` has a separate modality policy: it requires both complete pre/post fragments and omits a missing modality for both pairings. DS9 replaces that pair decision with distinct H0/H1/H2 candidates and normalized densities. DS1's depth-only increment also previously retained the old pair cost with a weighted dynamic depth term (`ds1_depth_only/depth_score.py:34–80`). These are different decisions; the current group mechanism is not the original Z4Q rule with one extra depth feature.

The harmful group behavior has two separable causes: extrapolating a fragile short depth trend, and admitting a non-H0 edit without symmetric depth preference for the identities it changes. Repairing only the mean does not remove the second cause.

## Complete saved decision inventory

The eight DS14 `EVENTS.json` / `EVENT_AUDIT.json` pairs contain 87 group episodes: 40 without a first-split decision, 42 lawful local fallbacks, and five actual group commits. The five commits are two CORRECT, two WRONG, and one UNSCORABLE. These labels are post-seal reference conclusions, not admissible prediction inputs.

Across the 47 q decisions, actual first-publication physical labels are 29 CORRECT, 10 WRONG, and eight UNSCORABLE. Of the 42 fallbacks, 27 are CORRECT, eight WRONG, and seven UNSCORABLE. Retaining H0 therefore avoids some introduced harm but is not a complete identity repair. It cannot fix the eight already wrong lawful fallbacks.

| Segment / local q (global q) | Saved edit | Sealed physical status | Geometry delta vs H0 | Old depth delta vs H0 | Old best/runner margin |
| --- | --- | --- | ---: | ---: | ---: |
| Feeding 1201–1906 / 39 (1239) | n167→136; n128→128 | CORRECT | +3.423893272 | −0.145069987 | 2.816865140 |
| Feeding 1201–1906 / 545 (1745) | n190→188; n9→9 | CORRECT | +2.271278935 | 0 | 2.271278935 |
| FishSA development / 4524 (4524) | n7→1; n1→7 | WRONG | +4.183909584 | −0.071457885 | 4.112451698 |
| FishSA exposed validation / 2600 (11900) | n4→1; n1→4 | UNSCORABLE | +3.298573555 | −0.290771764 | 3.007801791 |
| L3 / 1421 (1420) | n9→6; n6→9 | WRONG, weak preannotation reference | +2.321974410 | 0 | 2.321974410 |

The unchanged admission threshold is `log(9)=2.1972245773362196`. At Feeding q39 the strongest runner is H1 rather than H0; its geometry/depth margin is `2.8035691619491127 + 0.0132959775765888 = 2.8168651395257015`. The H2/H0 margin is `3.278823285036215` and should not be mislabeled the best/runner margin.

## FishSA development F4524 decomposition

The event is suspect F4519, confirm F4520, and split q F4524. Protected public identities are A=1, B=7. Lawful H0 is n7→7, n1→1; H1 swaps both.

Identity A has no clean pre-geometry fragment and no frozen depth history. DS9 correctly records `NO_CLEAN_PRE_HISTORY` and `NO_HISTORY` rather than inventing an A forecast. The pre-frame depth state at F4518 still records an old A fragment F4469–4477, but DS1 `freeze` selects only samples at/after `suspect_frame−30=4489`, so none survive. This is missing evidence under the frozen policy, not a measured absence of depth separation.

B's frozen eight-depth sample fragment is F4489–4496. WLS estimates slope `−70.98626674207806 mm/s`, predicts `590.6499203759107 mm`, and reports scale `117.50667672261997 mm` across gap `0.9330000877380371 s`. Its last real depth is `651.7246398925781 mm`, MAD `5.310455322265625 mm`. Current depths are n7=`657.80419921875 mm` (MAD 9.86334228515625) and n1=`570.1736450195312 mm` (MAD 4.6976318359375), both usable. Old residuals relative to the forecast are n7=+67.154278843 and n1=−20.476275356 mm.

B geometry uses the last measured center `[232,247]`, because A's velocity is UNKNOWN and the old geometry policy needs both velocities to extrapolate. Current centers are n7=`[198.5,199.5]`, n1=`[212,237]`. Its normalized geometry LR is −0.846721617 for n7 and +3.337187967 for n1. A contributes exactly zero geometry and depth LR to either candidate.

Thus H1−H0 is:

```text
geometry:  +3.3371879665980453 − (−0.8467216173565454) = +4.1839095839545907
depth:     +0.3939072381465945 − (+0.4653651236222046) = −0.0714578854756101
combined:  +4.1124516984789806 > log(9)
```

Both H0 and H1 have a positive selected-edge LR against the global depth background. Therefore a guard that asks only for positive selected depth LR would still accept the wrong n1→7 edge. It must compare depth preference against the lawful alternative and require both changed identities to be supported.

The group commit immediately creates two post-seal switches at F4524. Saved output aliases remain active through the rest of the segment, 3877 frames inclusive. This is publication and state persistence from the committed mapping; a single uncertain group decision is not automatically repaired by later depth observations.

## Minimal unified local-level forecast

Use one shared causal local-level predictor for both the proposed extra group edits and the existing depth birth association. Reuse DS14 `forecast.predict` rather than add a second model. Preserve history selection, current measurement policy, version separation, gap prior, Student-t4 density, background and geometry in the first experiment.

For up to the latest ten real, same-version samples in the selected clean fragment:

```text
mu(tq) = last measured z
sigma_i = max(15 mm, 1.4826 × MAD_i)
gap = tq − time_last
prior_process = 15² × (1 + (gap / existing_time_scale)²)
increment_rate_i = max(0, (z_i−z_(i−1))² − sigma_i² − sigma_(i−1)²) / dt_i
rate = median(increment_rate_i), only if at least three legal increments
variance = sigma_last² + max(prior_process, rate × gap), if rate is available
variance = sigma_last² + prior_process, otherwise
```

No history yields UNKNOWN, not a forecast from a group centroid or another identity. One/two real samples use the same last-value mean and prior with no fitted velocity; do not require three samples for every protected identity. A short history gives a broad, uncalibrated predictive scale, not certainty. Invalid finite/time/MAD/version/causality checks should cover these short-sample fallbacks too: DS14 `forecast.py:16–19` currently returns before the longer-fragment checks at lines 20–32. Do not recover an invalid fragment by joining older fragments across risk or version breaks.

The process variance proxy is not calibrated underwater physical uncertainty. Preserve `velocity_status=UNKNOWN_NOT_ESTIMATED`, physical accuracy UNKNOWN, and surface/background identity UNKNOWN. A valid raw sensor lineage does not establish which physical fish surface generated the measurement.

## Frozen-input local-level arithmetic

Substituting this predictor into all 47 saved q snapshots, without changing their states or downstream frames, leaves exactly the same five non-H0 candidates over the original joint threshold. No other saved fallback becomes an above-threshold edit. Forecast-only replacement therefore still admits both wrong exchanges.

| Decision | Local means/scales mm, A then B | Local depth delta H−H0 | Local best/runner joint margin | Changed identity depth preference |
| --- | --- | ---: | ---: | --- |
| Feeding q39 | 1163.571228 / 303.264019; 1155.730896 / 49.530872 | +0.109409761 | 2.951595230 | ID136: n167 vs alternative n128 = +0.077685898 |
| Feeding q545 | 855.937134 / 45.306477; 1108.456726 / 56.786778 | 0 | 2.271278935 | ID188: n190 vs n9 = UNKNOWN; common paired depth is uninformative |
| FishSA F4524 | A UNKNOWN; 651.724640 / 63.700305 | −1.010603561 | 3.173306023 | ID1 UNKNOWN; ID7: n1 vs n7 = −1.010603561 |
| FishSA validation q2600 | 787.742157 / 43.886346; 827.479523 / 39.482781 | −0.257511893 | 3.041061662 | ID1: n4 vs n1 = −0.068557875; ID4: n1 vs n4 = −0.188954018 |
| L3 q1421 | A UNKNOWN; B UNKNOWN | 0 | 2.321974410 | Both changed identities UNKNOWN |

All five longer fragments have a zero median noise-corrected increment rate, so the unchanged gap prior determines process variance here. F4524's local B mean now strongly prefers keeping n7, but the original geometry advantage is still large enough to overrule it in the sum.

L3 pre-frame state contains fragments F1316–1345 for both identities. The suspect is F1403, so the frozen depth cutoff window starts F1373 and produces two missing histories. Geometry still has its last thirty samples ending F1345 and uses a 2.519 s gap with a one-second mean cap. Do not relax the history window after observing this reference error in the first targeted experiment; the admission rule must safely handle the missing depth that the frozen policy actually provides.

## Preregisterable symmetric admission rule for extra group edits

Keep the existing distinct physical candidates, equal prior, ranking and `log(9)` best-versus-runner threshold. Use the proposed forecast in their existing normalized depth likelihood. After the same best candidate is selected, require all of the following before making any extra group edit:

1. The candidate is non-H0 and its joint margin is at least `log(9)`.
2. Current paired raw depth is usable under the unchanged measurement policy; a usable common background exists.
3. Define affected protected identity roles by comparing the selected candidate's occupying post source with lawful H0's occupant. Check each changed role symmetrically. An unchanged identity is not required to have three samples or positive foreground/background LR merely because it is adjacent to an edit.
4. Each changed role has a usable, causal, same-version local-level depth forecast. Require its selected edge's depth LR against the common background to be strictly positive. For its selected post source `s`, also require depth LR strictly greater than the role's lawful H0 source `a`: `LR_depth(r,s)−LR_depth(r,a)>0`. If H0 has no occupant of that protected public identity because it publishes a new outside public ID, compare against each other post source that can occupy that identity in the distinct candidate set; do not treat the missing H0 edge as a made-up favorable forecast. Both compared edges must be informative under the same query/background rules.
5. Also require candidate total depth LR minus H0 total depth LR strictly positive. This is a preference margin, not a requirement that the candidate's total foreground/background depth LR be positive.
6. If any check fails, retain the lawful own-branch H0. Do not try a second permutation, borrow another branch's bank, refresh the frozen past using anonymous group depth, or use GT for admission. Stage/occupation/version/atomic transaction checks still apply.

The rule contains no frame numbers, native IDs, reference labels, learned threshold or per-dataset exceptions. Source-order/role-label permutations must leave acceptance and the physical mapping unchanged. Missing depth remains a common uninformative likelihood during scoring and yields an explicit insufficient-evidence admission status; it must not turn into a zero-cost preferred edge. Retain forecast facts, compared source facts, per-role LR preferences, total depth preference, joint margin, and rejection reason in the transaction audit.

For a baseline whose public ID is outside the protected role set, requiring the alternate-source comparison is material. Feeding q39's selected ID136/n167 LR is +0.109409761, while alternative n128 LR is +0.031723863. The preference is +0.077685898. Its unchanged ID128 edge has LR −1.099370829; demanding a positive LR for that unchanged edge, or positive total candidate depth LR (−0.989961069), would wrongly block this known correct restore.

## Counterexamples and explicit recall cost

- **Only replace WLS with local level:** F4524 still has joint margin +3.173306023, so it still swaps incorrectly. The depth forecast fix alone is insufficient.
- **Only require a positive selected depth LR:** F4524's wrong B/n1 LR is +0.201337005 under local level, yet B/n7 is +1.211940566. Foreground/background support is not preference for a permutation.
- **Require at least three history samples for both identities:** Feeding q39 is a known correct restore with only one A sample. It would be rejected even though A's mapping is unchanged and the changed B role has seven samples. More history everywhere is not a minimal safety condition.
- **Mandatory informative depth and positive changed-role preference:** Feeding q545 is the concrete false-negative counterexample to the proposed guard. n190 has median 956.397644 and MAD 41.070556, so `1.4826×MAD=60.891207275 mm>60 mm` and `core_usable=False`. Both histories are available, but paired post depth is correctly disabled. Its known correct n190→188 restore is geometry-only with margin 2.271278935. The guard rejects it. Do not bypass the missing-depth condition or tune the 60 mm limit to preserve this exposed correct event.
- **Retain H0:** Eight existing saved q fallbacks are already physically wrong. The extra-edit guard does not claim to solve their identity losses. Baseline automatic D1/birth behavior should be measured separately from the extra group mechanism, as proposed for DS15.

On the saved independent q snapshots, the complete guard admits only Feeding q39: one CORRECT commit, no scored WRONG commit, and no UNSCORABLE commit. It suppresses the other CORRECT commit and all three other actual edits. This is mechanistic audit evidence, not sequential DS15 output, and not proof of a tracking benefit.

The implementation in `group_association.py` reproduces those 47 independent saved-input checks using their exact `DEPTH_OBSERVATIONS.jsonl.gz` raw measurements and full-frame backgrounds: 42 `H0_NO_EXTRA_GROUP_EDIT`, one `GROUP_CHANGED_IDENTITIES_DEPTH_ADMITTED`, one `GROUP_DEPTH_PAIR_UNINFORMATIVE` (Feeding q545), two `GROUP_CHANGED_IDENTITY_HISTORY_UNKNOWN` (FishSA F4524 and L3 q1421), and one `GROUP_CHANGED_IDENTITY_NONPOSITIVE_DEPTH_PREFERENCE` (exposed validation q2600). Seven focused synthetic tests passed. The final source must still be frozen and checked by the main DS15 experiment before any sequential run.

## Targeted experiment obligations

Freeze original Z4Q automatic association behavior outside protected group events separately from the extra group edit rule. Do not interpret its restoration as a tested improvement in this audit. Compare the same saved masks and exact data/ranges, and use separate empty-start branches.

Preregister baseline original Z4Q, current DS14, local-level-only group replacement, guard-only with old WLS, and combined local-level plus symmetric admission. These component comparisons distinguish the forecast correction from mere rejection of edits. Preserve the original geometry, measurement limits, background, unique-map priors and joint threshold in this targeted test. Any later relaxation is a new experiment.

Prediction code must have no access to references; seal full numeric outputs, states, transactions, fact provenance and effective code before post-seal evaluation. Test no-history, one-point history, current invalid depth, one changed identity with an outside H0 public ID, two-role exchange, positive selected LR with negative alternative preference, and order invariance. Include the exact five exposed numerical cases as regression inputs without embedding their labels or desired frame-specific answers in the algorithm.

Report all event admission counts and physical statuses, lost correct restores, persistence of every wrong committed mapping, and pooled/per-segment IDF1, HOTA, AssA and IDSW. FishSA validation has prior exposure; L3/LW reference is weaker preannotation; neither should be called independent clean generalization. A depth-zero control that is denied by a depth-mandatory admission rule demonstrates the rule's dependency by construction, not empirical necessity of depth. End-to-end depth value requires the full causal replay and component comparison.
