# DS4 — source admission and background-noise measurement experiment

Review base: ace9a37b1c6a2a59d3d5397f335d081f1a5a8ae8,2026-09-30.
User requests deep failure review, improvement plan and immediate experiment.
All DS3 and earlier experiment files are read-only. New outputs are separate.

## Evidence before this freeze

SOURCE_AUDIT verifies the57 F766 points all exist in original mono16 BAG records,
native exports are exact, and complete current-frame calibrated depth/source
reprojection is exact. No decode, byte order, alignment replacement or fill
caused the12254mm component. Device valid range and hardware cause are UNKNOWN.
The original dataset README already labels >5m as anomaly candidates; this is
the source of the new **SUSPECT policy**, not a manufacturer range.

COMPONENT_AUDIT covers all28382 masks. Main-only rejection would remove164 old
accepted components, including many matched-fish pixels; touching core also
fails to reject F766. The main-only constraint remains a diagnostic ablation,
not the primary rule. The15mm scale floor enforces a45mm minimum contrast and
blocks some30–45mm coherent signal; the same15mm floor originally describes
association/measurement uncertainty, not necessarily background residual noise.
The existing SDK depth quantization is1mm. Reducing only the background floor
to that value is a new explicit hypothesis; it does not calibrate underwater
depth accuracy. Foreground dispersion floor15mm and contrast floor30mm stay fixed.

DS3's99.62% core silhouette proxy has a ceiling, so the frozen10pp gain target
cannot discriminate this problem. DS3 FAIL stays unchanged. Its50.53% fish
retention is conditional on accepted paired objects; unconditional retention on
all28088 scorable objects is35.3371%. A new score must expose rejection costs.

## Fixed cohort, controls and variables

All original SOURCE_OLD frames701–1060/1201–1906:1066 frames, every original
mask; already exposed measurement-development diagnosis in the same recording.
No new blind validation or independent dataset claim. No GT-based selection of
frame, q, trigger, anchor, mask or branch action. Upstream SAM3 lookahead UNKNOWN.
No RGB, instance_id, v3, restored plane, future observation, identity forecast or
old model response is an extraction input. Original native depth and source_index
are used only to trace raw aligned values and apply current-frame source quality.
No tracker/DepthState/event controller, q, candidate, reference, motion, weight,
state transaction or publication rule is changed. No new tracking score.
Inference HTTP, smoke, SAM3 inference, completion service, training and cost0.

|Arm|Original native >5000mm SUSPECT admission|Unique largest source component|Background scale floor|
|---|---|---|---:|
|F2_DS3|off|off|15mm|
|F3_RANGE|on|off|15mm|
|F4_MAIN|off|on|15mm|
|F5_RANGE_MAIN|on|on|15mm|
|F6_BG_NOISE (primary)|on|off|1mm|

The first four form a2×2 controlled diagnostic. F6 compared with F3 isolates
background-noise floor, and F6 compared with F2 is the combined primary test.
Other DS3 annulus/Huber/connectivity/component/dominance constants unchanged.
F0 whole and F1 exclusive7×7 core are recomputed exactly as raw controls.
F2 recomputes its original algorithm; numerical facts AND pixel selections must
match the sealed DS3 on every object. No copied old outputs are new runs.

SUSPECT values are excluded from a **working admission copy** only, before fit
and sampling. Raw aligned/native inputs, raw whole/core, all source masks and
rejected pixel provenance remain intact. No replacement, interpolation or
sentinel decoding. Main restriction changes eligibility within a source mask,
retaining all other fragments as anonymous evidence. The annulus remains outside
the whole source contour; removed fragments never become background samples.
Equal largest components imply no eligible pixels, not an arbitrary tie winner.
The selector still considers nearer/farther components; no min-depth shortcut.
Selected sample n is the count of actual admitted raw pixels, never closed-hole
support. AVAILABLE means rule-qualified component, not certified fish identity.

## Tests and order

1. Unit tests: dense12m component, short side branch, legitimate nearer/farther
   components under5m, no contrast/holes, main tie, raw source invariance and no
   mutation,15mm-clone equivalence, the independent1mm background floor while
   component scale remains15mm. Real F701/F704/F766 are **exposed regressions**,
   without manual references. Block model network, instance_id/v3/test/GT.
2. Freeze all measurement/scoring code, actual effective constants, source/raw
   native metadata/hash inventories and old read-only locks. Process all1066
   frames once; the five current-only arms share only immutable source inputs.
   Data-equivalent input contexts may reuse the same computation within an
   object, with exact context equality; this is neither voting nor result choice.
3. Seal all method facts, private pixels and timing before any new reference
   scoring. Then independently validate every seal/code/source binding.
4. Postseal matching uses the unchanged unique IoU≥.5/margin≥.1 rules and must
   reproduce the old28088/294 matching population. Never rematch only survivors.

## Fixed populations and decision

S: all28382 original source masks, includes UNKNOWN and UNSCORABLE.
Q: all uniquely matched manual silhouettes, fixed independently of method.
R: Q with an available independent reference on original raw depth: remove other
manual silhouette overlaps, erode7×7, then require n≥16, valid fraction≥.2 and
max(15mm,1.4826MAD)≤60mm. Reference median/MAD/scale never uses selected pixels,
SUSPECT admission or a method answer. References with no samples are unavailable.
All methods share Q/R; reference eligibility does not change with acceptance.

Reference consistency = |selected raw median−reference raw median|
≤max(30mm,3×reference scale). It is **postseal raw-silhouette consensus**, not
physical depth GT, independently measured fish distance or manual depth labels.
Stable sensor errors within reference can fool it; record this limitation.

For fixed R report compatible/discordant/UNKNOWN counts and yields over |R|.
For fixed Q report matched-fish pixel yield over original valid matched-fish
pixels, nonmatched pixel yield with that same denominator, accepted/UNKNOWN,
pixel counts and reference-unavailable outcomes. Conditional accepted purity
and error remain descriptive, with explicit denominators and all-object costs.
UNSCORABLE match-quality fields are null, never wrong or safe. No-sample error
is null, never zero. Missing physical truth remains UNKNOWN.

Primary proxy gain requires F6's discordant yield strictly below F2 and
compatible yield not below F2 on fixed R. Discordance down but compatible down
means TRADEOFF; otherwise NO_PROXY_GAIN. All-reject cannot gain. No10pp silhouette
gate, no claim of depth accuracy or tracking gain. Each arm is reported whether
good, bad or unchanged; no postscore winner is inserted into tracking.
Known F704/F766 fixes are reported separately from full-population evidence.

## Resources, visualization and delivery

Existing local D-MOT Python/NumPy/OpenCV/pycocotools/Matplotlib, no new installs,
no server/GPU. Native math/vision1 thread. Process original frames in order;
output refuses overwrite. Expect~5–12min measurement, plus~2–5min source/scoring
and report, comfortably below current available memory/storage. No randomness.
No significance/generalization inference from repeated masks in one recording.

Private QA shows F704/F766 before/after, earliest newly available primary,
and earliest newly discordant primary (if any), including rejected source pixels
and explicit over5m coloring. No clipping of12m into background colors.
These are diagnostics selected after seal, not new cohort or parameter tuning.
Public numerical audit/report and actual restricted paths/bytes/SHA reproducibility
are committed and nonforce pushed main; real remote ref/files verified even on
FAIL or TRADEOFF. Keep old results and private pixel data off public Git.
After this one frozen experiment, stop; physical pixel truth and tracker effects
are reported as unfinished, not filled with invented labels or old scores.
