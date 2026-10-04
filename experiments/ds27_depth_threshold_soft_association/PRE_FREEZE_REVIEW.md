# DS27 pre-freeze causal and scoring review

Review date: 2026-10-04. Scope: PLAN.md, CONFIG.json, common.py, evidence.py, history.py, runner.py, soft_controller.py, private measurement bindings and source hooks, scorer, guard and freeze flow. Reviewed source/code and experiment metadata only. No GT, tracking metrics or reference file contents were read. No prediction or scorer was run by this reviewer. Only this review document was written.

## Status

No remaining observed blocker in the reviewed causal, conditional-support, matrix and publication flow after the pre-freeze fixes listed below. Freeze and execute the prescribed finite six-arm/eight-segment experiment; zero intervention, unknown evidence and negative outcomes remain valid results. This is not a method-efficacy approval, a physical-accuracy claim or a requirement to obtain positive GT outcomes.

The original native and Z4Q paths stay separate from the four independently evolving soft policies. The four cells change the declared background-contrast and measurement-floor levels. No branch votes, carries another branch's history or chooses a best result after scoring.

## Corrected findings

1. The first scorer version filtered `depth_soft_checks` by `applied_delta`, while the actual controller writes `applied_delta_cost`. That would hide every real matrix update from ACTION_AUDIT. The refreshed scorer uses `applied_delta_cost`.
2. Raw source imports in evidence/history explicitly load the DS16 original raw adapter. The actual guard also imports `raw_source` from evidence, so its access inventory is the same `FIELD_READS` object used by the real raw cursor. An earlier additional guard warning came from a stale read and is withdrawn. Rechecked after freeze: guard, evidence, history and scorer bytes exactly match RUNTIME_FREEZE; the guard SHA is `1f9d6cd6dabb9323a6b0937af24c99baeb83ed7a99fde4fc1eea106b9c3ab690`. Import-only object identity verification opened neither a raw cursor nor GT. The fix was present before the prefixes and the 2026-10-04 11:59:47 UTC freeze.
3. The refreshed scorer binds endpoint references to the sealed per-arm measurement facts, checks their internal and full fact digests, checks evidence frames against q, asserts ORDER_CHECKS equals each transaction's soft checks, and recomputes actual-publication/durable-alias flags from the saved actual mapping and alias targets.

No root implementation files were changed by this reviewer.

## Source, anchor, version and q

- Sources admits only the saved original N0 mask population and exact DS14 row/frame/time bindings. Current or already acquired past raw reads are bounded by the current cutoff and 12-second retention; actual adapter binding must equal the saved binding. Source indices are frame-local and are never treated as temporal surface correspondence.
- Each arm has a separate History. Its version is native source, generation after a visibility gap, published ID and public epoch; segment and branch are separated by the owning History instance. Risk/gap/version changes end a live clean fragment.
- A pre reference comes from the exact branch bank anchor tuple and its stored actual clean snapshot. A partner must retain the same source generation/public epoch and mapping claim. At least five synchronized pre times from the last ten must include the anchor endpoint; all selected pre times remain in the probability median, including null measurements.
- Current q is an original candidate frame. History.observe runs after this branch's actual commit, so q cannot enter its own pre reference. No future observation is used to admit a cost change.
- Anonymous risk observations remain in the complete per-frame ANONYMOUS_RISK record. The shorter interval nested in a comparison is a source-filtered diagnostic view; it must not be interpreted as all merged objects or as reconstructed hidden fish. A missing layer is not manufactured into an observation.
- The current evidence implementation also conditions an increment on original query quality/isolation, current partner quality/isolation, pair separation, exact anchor provenance and partner version. These are coverage conditions for added evidence; unknown leaves the existing candidate and cost unchanged.

## Sole qualified support and common null

The endpoint consumer does not select the closest/largest peak or treat the DS25 producer's old two-layer status as an individual-fish certificate. It requires independent/inclusive partition and support agreement, no substantial unresolved support, exactly one qualified measured support and original-mask independent coverage. Zero or multiple qualified supports yield common null. Substantial unexplained mixtures yield common null. Missing, background-compatible and unselected support populations remain present in the bound fact.

The old producer can report UNKNOWN because its earlier contact task required two layers. The new individual-mask consumer uses the explicit support facts and its declared one-support condition. This is a new conditional measurement interpretation, not an assertion that all inherited UNKNOWN parent statuses now mean foreground.

A usable support has weight independent source N divided by original mask area, which includes missing and duplicate projected pixels in the denominator. It does not normalize to the selected foreground pixels. The remainder stays common null. The pair rejects any shared frame-local native source, then uses:

`p = 0.5 + rA*rB*(t4((zB-zA)/hypot(sigmaA,sigmaB))-0.5)`.

This is an uncalibrated relative-order proxy with a conditional support-reliability assumption. It is not a fish-surface identity or physical-depth likelihood. Neither endpoint uncertainty nor history aggregation divides by sqrt(N). All pre pair probabilities, including0.5 nulls, enter the median; historical probabilities are not multiplied. Unknown partners contribute0 to the mean over the complete enumerated partner set.

A coverage consequence of the declared null mixture is that the pre distance0.1 can only be met when rA*rB is at least0.2, even with a maximally decisive raw order proxy. This follows from the frozen formula; it is not a proposed new eligibility gate or a reason to lower a threshold after seeing the rollout.

## Effective parameter levels

The four measurement instances have private producer/background/layer dictionaries. Their effective per-arm parameters change the actual five IRLS steps, residual/layer scale floors and background qualification, while preserving support populations,30mm layer splitting, independent N16, original-area fraction0.2 and maximum scale60mm.

| Cell | Contrast floor / sigma multiplier | Variability floor | Minimum effective contrast |
|---|---|---|---|
| C0_S15 |30mm /3 |15mm |45mm |
| C1_S15 |10mm /2 |15mm |30mm |
| C0_S5 |30mm /3 |5mm |30mm |
| C1_S5 |10mm /2 |5mm |10mm |

The revised5mm level comes from the declared old PRE-only descriptive rule; it is not sensor accuracy, temporal repeatability or a calibrated physical confidence interval. The actual combined endpoint sigma also includes the support, background and leverage terms and need not equal the floor.

The two factorial contrasts describe parameter-level effects. The floor also changes the effective background threshold and qualification through sigma, so an observed scale-cell difference cannot be interpreted as an isolated physical-precision effect. All cells share the same association rule, age attenuation6 seconds, median aggregation and soft weight0.15.

## Genuine matrix policy and state

Both original D1 and birth matrices invoke the hook after constructing original eligible terms and before their original global assignment. The competition set is fixed from original legal costs and the own dummy=1. Only original legal identity terms within0.15 of the row minimum are considered, and at least two alternatives including the dummy are required. Original depth/motion-rejected terms and illegal1e6 entries do not become new candidates.

The hook changes only those legal costs, by bounded signed soft evidence with floor0. Dummy, original global margin, D1 confirmation5, original birth eligibility and original trigger remain unchanged. The effective selected cost still has to beat dummy1. There is no new hard veto. A legal D1 matrix term that originally loses to dummy can become competitive through the declared cost adjustment; this is the intended soft association, not revival of an original rejected term.

Preview executes on a clone and actual commit precedes the shared prediction line. History and branch ownership evolve from the committed own state. Shared Sources is a cache of numerical raw facts and per-policy measurements, not identity state.

Disabled or a whole prefix without any previous nonzero effective update reproduces original scientific state. After a genuine earlier intervention, a later null increment is zero in that branch's existing state; it need not reset that branch to original Z4Q. The runner correctly scopes exact baseline equality to disabled/no-prior-update prefixes.

## Scoring and publication ledger

The scorer first requires the all-eight prediction/access manifest and validates every segment seal and frozen code before opening reference rows. Its reused original scoring helper reads GT only inside postseal reference iteration; importing the helper reads code, not GT contents.

Predictions, ORDER_CHECKS and all five state-arm transactions are bound to the first-publication ledger by row SHA. Each saved actual mapping equals the published objects. Soft checks equal the transaction's controller trace; actual accepted-action adoption/durable flags are checked against the saved mapping/aliases. The fact reference join is keyed by arm, fact ID and full measurement digest.

The planned scorer preserves every original mask and public ID, produces every switch, separates unknown bank/public-origin relations and compares native/original scores to the old source. Added/eliminated switch records retain the warning that a changed ID label can list one transition in both sets. Feeding alone is pooled with segment namespaces. L3/LW remain weak preannotation diagnostics and all data remain exposed development material.

## Remaining interpretation and execution limits

- The reported real prefix had competitive checks but no measurements because earlier provenance/version conditions returned null. That is an acceptable coverage result. A nonzero measurement count or positive GT result is not an execution gate.
- Original candidate competition coverage is limited, including the declared old birth competition count0 and absent FishSA8400 competition. Report the limitation rather than expand q/trigger after results.
- Lowered variability/background thresholds can qualify bent surfaces, undetected fish or nonplanar background. Common null and support agreement mitigate ambiguity but do not establish physical ownership.
- A soft cost update is not necessarily a changed assignment, and a changed assignment is not necessarily an actual durable alias. Keep all three counts separately.
- The finite2×2 experiment can assess these declared parameter levels on this exposed source set. It cannot select a universally optimal threshold, establish blind generalization or certify physical depth precision.
- Complete necessary source/state checks and freeze all effective parameters/code before the formal run. Finish all eight segments, seal access, then score every arm and preserve zero/negative outcomes. No post-score threshold revision belongs to this frozen run.

