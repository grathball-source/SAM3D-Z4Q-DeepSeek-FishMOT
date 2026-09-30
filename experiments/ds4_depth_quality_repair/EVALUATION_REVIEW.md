# DS4 independent evaluation review

Date: 2026-09-30. This is a read-only review of DS3 and advice for the separately
authorized DS4 experiment. The reviewed DS3 files are `PLAN.md`, `evaluate.py`,
`SUMMARY.json`, `RESULTS.md`, `FAILURE_CASE_AUDIT.json`, `checks.py`,
`foreground.py`, `CONFIG.json`, and `POSTSCORE_DIAGNOSTICS.json`. No DS3 source,
output, score, threshold, or seal was changed. This document does not choose a
new success threshold, tune a parameter, or claim a DS4 outcome.

## 1. What the DS3 result establishes

DS3 completed the engineering chain: fixed source decoding, original mask and
F0/F1 reproduction, candidate-independent current-frame measurement, sealed
pixel output, and postseal silhouette scoring. Its fixed measurement hypothesis
failed. Preserve `FAIL_FROZEN_MEASUREMENT_HYPOTHESIS` unchanged.

The paired core purity was 99.6213%. Its maximum possible improvement under this
proxy is only 0.3787 percentage points; the frozen requirement of at least
10 percentage points was mathematically unattainable on this population. This
is a limitation of the original design, not permission to retrospectively
change the DS3 gate. The measured change was also negative: -0.7049 percentage
points, with 139 paired objects improving, 8,886 worsening, and 9,416 equal.

Silhouette occupancy cannot identify all depth failures inside a silhouette.
At F766/o012, F2 selected 57 original positive samples with median
12,254.6191 mm, versus the legacy core median of 1,141.7869 mm. Yet 55/57 selected
pixels were inside the matched manual silhouette, giving 96.4912% occupancy
purity. At F704/o013, F2 selected 20 points outside all manual silhouettes:
significant contrast, connected support, sample count, and 74.07% dominance did
not establish that the selected component belonged to the fish.

These cases motivate source-quality and geometry checks. They do not provide
certified physical depth truth, and they do not identify a sensor failure cause
by themselves. Existing manual polygons are silhouette references, not labels
of the physical surface responsible for each depth measurement. Dense stable
positive values, low MAD, and constructional valid_fraction=1 are insufficient
to certify distance accuracy.

## 2. Conditional and unconditional statistics

The old paired population contains 18,441 objects with a unique scorable manual
match, F2 AVAILABLE, at least one core sample, and at least one original valid
matched-silhouette pixel. This is a conditional quality comparison. It does not
require `core_usable`; F704's seven-point core can therefore enter this pair set.
The old calculations are internally consistent with that definition.

The reported retention of **50.5329%** is conditional on this accepted pair set:

```
3,754,678 selected matched-silhouette pixels
------------------------------------------------ = 50.5329%
7,430,169 original matched-silhouette pixels in the paired accepted objects
```

For the fixed population of **all 28,088 scorable objects**, F2 UNKNOWN contributes
zero selected samples, and the corresponding unconditional retention is
**35.3371%**:

```
3,778,889 selected matched-silhouette pixels
------------------------------------------------ = 35.3371%
10,693,823 original matched-silhouette pixels in all scorable objects
```

Neither denominator includes unpredicted fish pixels outside the original SAM3
mask, or original missing depth. These numbers must not be described as recovery
of the entire fish or restoration of missing depth.

On all scorable objects, legacy core retention is 12.8710%; F2 samples 2.7630
times as many valid pixels as core. Nonmatched samples increase from 6,345 for
core to 41,620 for F2. F2 therefore expanded sampling while increasing measured
silhouette contamination. This tradeoff is distinct from the conditional
50.5329% figure and is not evidence of corrected physical depth.

The DS3 engineering coverage populations also differ:

| Statistic | Numerator / denominator | Value |
| --- | --- | ---: |
| F2 acceptance over all original objects | 18,862 / 28,382 | 66.4576% |
| F2 acceptance over scorable objects | 18,791 / 28,088 | 66.9005% |
| F2 acceptance over original core_usable objects | 15,974 / 21,908 | 72.9140% |

The last denominator includes 97 unscorable objects. It is a valid engineering
availability measure, but must not be called the acceptance rate of the
scorable quality population.

`pooled()` ignores zero-sample contributions. Thus UNKNOWN is not counted as
correct, but pooled purity alone imposes no refusal penalty. DS3 correctly
excludes UNSCORABLE rows from quality summaries. Their internal `fish=0` is an
empty-match placeholder, not a finding that these objects contain no fish.
New downstream summaries must preserve that distinction; matched quality
should be null or explicitly unavailable for UNSCORABLE objects.

## 3. Review of the authorized DS4 contrasts

The intended experiment retains the same exposed 1,066 SOURCE_OLD frames and
all 28,382 original masks. It is development on existing exposed data, not a
new blind validation set. The expected controls are:

| Arm | Native-depth SUSPECT admission | Source-mask main-component geometry qualification | Background scale floor |
| --- | --- | --- | --- |
| DS3 reproduction / 00 | Original DS3 behavior | Original DS3 behavior | Original 15 mm |
| 10 | Frozen native >5 m SUSPECT rule | Original DS3 behavior | Original 15 mm |
| 01 | Original DS3 behavior | Frozen main-component rule | Original 15 mm |
| 11 | Frozen native >5 m SUSPECT rule | Frozen main-component rule | Original 15 mm |
| 10 + background-floor ablation (F6 primary) | Same as 10 | Original DS3 geometry | SDK-derived 1 mm |

This table records the requested contrasts; it does not select their thresholds
or dictate the exact placement of the admission and geometry rules. Their
implementation and affected pixel domains must be explicit in the actual plan,
configuration, and freeze before the full run. The 2x2 comparison can distinguish
admission effects, geometry effects, and their interaction. After the full
component audit found substantial matched-fish losses from main restriction,
the final approved PLAN keeps that restriction diagnostic. F6 differs from10
(F3_RANGE) only in the declared background scale floor, isolating its effect.

Specific interpretation checks:

- Use the original native source value for the native >5 m flag, linked through
  the verified source_index. Aligned camera-Z can differ from native distance;
  do not silently substitute one for the other. A source-derived SUSPECT flag
  is an admission policy, not a certified per-pixel physical error label.
- Define geometry qualification from the original source-mask topology. Record
  which component is primary, deterministic tie handling, the qualification
  predicate, and the reason for refusal. Do not infer fish ownership solely
  from component size, and do not use manual reference geometry in extraction.
- State whether admission affects background fitting, significant candidates,
  component measurements, or all of them. Preserve the original raw F0/F1
  diagnostics and report any admitted variants under separate names; otherwise
  the reproduction control and the intervention become confounded.
- Preserve the 30 mm contrast floor and 15 mm component scale floor in the
  background-floor ablation. DS3's shared `scale()` helper serves both
  background and components; changing its single floor globally would alter
  two mechanisms. The code must maintain distinct effective floors.
- SDK depth units of 1 mm establish a quantization scale, not necessarily the
  physical background noise standard deviation or water-calibrated accuracy.
  The arm should be described as a numerical background scale-floor ablation.
  With a 15 mm background floor, the 3x scale rule gives a minimum 45 mm contrast;
  with a 1 mm floor and the retained 30 mm contrast floor, it can fall to 30 mm.
  If this floor also changes IRLS weights, its effect includes background plane
  fitting as well as contrast selection; record that scope explicitly.

No model call, training, tracker transaction, identity remapping, or new IDF1/HOTA
score follows from these measurement contrasts.

## 4. Population definitions for DS4 reporting

Let S be all original source objects and Q be the uniquely scorable subset under
the frozen postseal silhouette matching rule. S and Q must be shared by every
arm. Do not redefine Q according to a method's acceptance or observed score.

For method j and object i, let A_ij indicate AVAILABLE, T_i be the count of
original valid source-mask pixels in the matched silhouette, F_ij the selected
valid pixels in that silhouette, and C_ij the selected valid pixels outside the
matched silhouette. C includes both other-fish and outside-all-fish pixels;
report these two categories separately as well.

Recommended descriptive outputs, without selecting a new PASS gate:

```
All-source acceptance_j = sum over S of A_ij / |S|
Scorable acceptance_j  = sum over Q of A_ij / |Q|
Unconditional retention_j = sum over Q of F_ij / sum over Q of T_i
Nonmatched yield_j         = sum over Q of C_ij / sum over Q of T_i
Accepted pixel purity_j    = sum over Q of F_ij / sum over Q of (F_ij + C_ij)
```

UNKNOWN has no selected pixels and remains in the unconditional denominator.
If a denominator is zero, report unavailable, not zero or success. Include
SCORABLE/UNSCORABLE crossed with AVAILABLE/UNKNOWN and the frozen refusal
reasons. Conditional paired purity and median changes remain useful, but each
pair population must be named and its count reported. In particular, using each
arm's own accepted subset is not a fair all-source improvement comparison.

Report pooled pixel measures and object-level changes separately. Pixels in a
large object are not independent events, and objects in neighboring frames are
not independent recordings. Do not infer significance or cross-video
generalization from the large pixel count. Report both original segments and
the pooled result, retaining known-case regression results separately.

An optional later postseal reference could use the raw-depth median/MAD in an
eroded, exclusive manual silhouette to quantify agreement with a label-defined
raw-depth consensus. Its eligibility would have to be independent of method
outputs and fixed across arms; UNKNOWN would remain in a shared denominator.
Even that reference would be a consistency proxy, not physical depth ground
truth. This review does not add that scorer, choose its tolerance, or authorize
using it to tune DS4.

## 5. Minimum useful checks

Engineering checks should reproduce DS3 with the original configuration before
interpreting any intervention: same original mask inventory, same F0/F1 facts,
same F2 status/reasons/statistics and selected pixels, and unchanged source
hashes. Full frame and object coverage is required, not merely the two failures.

The regression set should include the exposed F704 and F766 cases, but name
them as known failures. Their correction is a regression result, not fresh
scientific validation. Focused synthetic checks can use explicitly constructed
surface values without pretending that real pixels have artificial truth:
dense stable extreme components, a wrong disconnected side branch, a legitimate
far-side component, tilted background, missing holes, and neighboring contours.
Also test the exact native admission boundary and main-component tie behavior
specified by the frozen implementation.

The background-floor arm needs a direct check that changing only that floor
leaves the contrast floor and component floor unchanged. Source order, object
order, source_index linkage, current-frame-only access, and input nonmutation
remain required invariants.

A small hand-computed scoring fixture should contain an accepted supported
output, an accepted contaminated output, UNKNOWN, and UNSCORABLE. Check that:

- adding a refusal cannot improve unconditional matched-pixel retention;
- zero selected samples produce unavailable purity rather than a correct score;
- UNSCORABLE does not become a matched-fish error;
- changing acceptance does not change S, Q, or the original-pixel denominator;
- selected matched, other-fish, and outside-all-fish counts sum to selected n;
- all-accepted, all-UNKNOWN, and all-unscorable cases have explicit outcomes.

Maintain the experiment's no-network, no-annotation-during-measurement, no
instance_id, no repaired-v3, no sealed-test, no old-model-answer, and no-tracker
boundaries. Authorized native/source_index lineage reads must be distinguished
from annotation-plane reads. Seal measurement code, configuration, complete
source inventory, output streams, and pixels before any new reference scoring.

## 6. Claim boundary

Engineering correctness, silhouette occupancy quality, raw-depth admission
safety, physical distance accuracy, and tracking benefit are separate claims.
DS4 can test a frozen engineering and measurement-quality repair on the exposed
source population. Original BAG/native provenance can establish where an
extreme value entered the chain; it does not establish the object's physical
distance or the cause of the value. Physical depth truth and water calibration
are absent, and tracking benefit is not tested in this experiment. Report those
limitations even if the new rule rejects both known failures.
