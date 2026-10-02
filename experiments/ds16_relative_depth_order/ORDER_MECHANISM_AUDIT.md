# DS16 relative-order mechanism audit

Read-only audit after every prediction branch was sealed. No GT, metric files, private pixels or new scientific configurations were read. This audit assesses source bindings and decision mechanics, not physical identity correctness.

## Actual coverage

| Segment | Q events | Eligible paired order | UNKNOWN | OFF accepts | ORDER accepts | PERMUTE accepts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| feeding_000000_000199 | 0 | 0 | 0 | 0 | 0 | 0 |
| feeding_000351_000555 | 6 | 2 | 4 | 0 | 0 | 0 |
| feeding_000701_001060 | 5 | 3 | 2 | 0 | 0 | 0 |
| feeding_001201_001906 | 9 | 5 | 4 | 1 | 0 | 1 |
| fishsa_development_8400 | 9 | 3 | 6 | 0 | 0 | 0 |
| fishsa_validation_2888 | 7 | 3 | 4 | 1 | 0 | 1 |
| L3 | 4 | 2 | 2 | 1 | 0 | 1 |
| LW | 10 | 4 | 6 | 0 | 0 | 0 |

Across 50 Q events: 22 eligible and 28 UNKNOWN. Reasons: {"VALID_SOFT_ORDER_EVIDENCE": 22, "NO_SAME_FRAME_PRE_PAIR": 16, "INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING": 11, "INVALID_OR_MISSING_CURRENT_PAIRED_DEPTH": 1}.

Only 1 eligible pre order proxy has confidence >= 0.9; 16 are below 0.6. Median confidence 0.540677. These are uncalibrated confidence proxies, not physical accuracy.

## The factor and the hard admission rule

The frozen score uses one ordinal factor: compatibility = p_pre*p_post + (1-p_pre)*(1-p_post); L = 0.05 + 0.9*compatibility; logLR = log(L/0.5). Absolute per-role group depth scores are zero. UNKNOWN gives every mapping exactly zero ordinal score. OFF applies the same input eligibility and geometry, with ordinal zero.

The additional positive-support/preference admission condition is distinct from the soft factor. It rejects a best candidate with any nonpositive ordinal support or lack of ordinal preference over H0, even if the combined geometry plus ordinal margin exceeds log9. It must be reported separately from a reliable physical order contradiction.

| Original frame | Pre pairs | p(A nearer) | Pre delta / q scale (mm) | Geometry delta | Selected ordinal LR | H0 ordinal LR | Combined margin | Mechanism |
| ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1239 | 1 | 0.499457 | -0.619812 / 428.384560 | 3.423893 | -0.000150 | 0.000000 | 2.803268 | Positive-sign gate, not insufficient joint odds |
| 11900 | 10 | 0.731125 | 39.737366 / 59.033053 | 3.298574 | -0.164241 | 0.141033 | 2.993299 | Positive-sign gate, not insufficient joint odds |

Both rows have OFF and PERMUTE acceptance but ORDER rejection. At Feeding F1239 the pre difference is below 1 mm, confidence is effectively 0.5, and ordinal magnitude is about 0.00015. Its gate rejection cannot be described as a high-confidence near/far constraint. FishSA F11900 has pre confidence about 0.731 and a current depth separation about 10.85 mm; it is also weak evidence. Correct/wrong outcomes belong to independent postseal scoring.

## Third branch difference: soft-factor threshold

At L3 original F1420 (local q1421), OFF accepts the joint swap {9:6,6:9} with geometry margin 2.321974. ORDER reduces this to 2.049657, below log9=2.197225. This is a soft-factor effect, distinct from the two hard-sign gate rejections above. Its propagated pre near-order proxy is p(A nearer)=0.400313 and compatibility is H0=0.575180 versus swap=0.424820. The permuted factor increases margin to 2.594292 and commits. Physical correct/wrong is intentionally not assessed in this source-only audit.

## Why evidence often remains weak

- Same-frame clean pre history is necessary to establish an actual measured relation. Most retained fragments contain only 1 to 10 paired samples, spanning about 0 to 0.3 seconds.
- Existing gap uncertainty grows with event/reference time divided by this short observed span. For example development F1274 has 2 paired samples, span 0.033 s, gap 9.596 s and propagated pair scale 6168.7 mm; the ordinal factor is effectively neutral.
- This uncertainty model is inherited conservatively from previous modules; it is not a calibrated physical model of topological order reversal. The trial does not establish that near/far order physically changed.
- A complete-pair ordinal factor has maximum likelihood ratio 19 between opposing orders. An incomplete-old-pair H0 has neutral factor and a compatible complete restore gets at most log(1.9), so geometry must support the restore.

## Source and control checks

- Adaptive exclusive-mask core excludes overlapping mask pixels geometrically; fish surface/background ownership remains UNKNOWN.
- Measured n is valid aligned-depth PIXELS, not guaranteed independent native sensor source points.
- CONTACT_CERTIFICATES is deliberately empty raw={} and not used as deduplicated contact qualification.
- Ordinal evidence is paired representative core medians, not direct local occlusion topology.
- Only frozen pre and current first split frame determine ordinal factor; hidden individual depth is not fabricated.
- Full geometry/history/automatic event policy persists, but ordinal factor does not infer the full hidden crossing path.

Actual log backchecks: 594 pre sample bindings, 132 current bindings and 156 candidate factor/score checks. Errors: zero. Every one of 44 permuted source bindings changed its current median (44 nontrivial perturbations). Actual state source/fact/core remained original in the binding tables.

Source-binding UNKNOWN commonly arises because one manager geometry history is empty while DepthState retains an old clean fragment. The JSON audit lists exact roles, sources and frame ranges; it does not relabel this as poor sensor quality. No discarded fragment is stitched back into this frozen trial.

## Interpretation boundary

This frozen version has no additional ORDER group restore. That result concerns this representative-core order factor, its uncertainty propagation, available source histories and extra positive-sign admission. It does not demonstrate that local occlusion topology is unusable, nor does it establish physical order invariance. Independent performance and identity audits determine whether the two prevented geometry restores were beneficial or harmful.

One next method question: separate the effect of near-neutral sign admission from evidence for actual continuous occlusion order; do not silently change the completed frozen trial.
