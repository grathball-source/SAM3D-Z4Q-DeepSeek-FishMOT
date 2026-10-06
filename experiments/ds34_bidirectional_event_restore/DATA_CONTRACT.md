# DS34 saved-source and event history contract

Reviewed from prediction-only source records at `cdec46035f730e7166e175f8df5aab2a9f3deb31`. No GT raster, annotation instance ID, service, API or old response was read for this source/scan review. Old sources and seals remain read-only.

## Fixed source cohort

| Source | Global frames | Frames | Original V4 suspects | Unique suspect frames | Observed gap generations |
|---|---|---:|---:|---:|---:|
| Feeding first | 0–199 | 200 | 8 | 7 | 5 |
| Feeding second | 351–555 | 205 | 47 | 40 | 11 |
| Feeding third | 701–1060 | 360 | 41 | 40 | 7 |
| Feeding fourth | 1201–1906 | 706 | 45 | 45 | 4 |
| FishSA development | 1–8400 | 8400 | 15 | 15 | 3 |
| FishSA validation | 9301–12188 | 2888 | 16 | 16 | 18 |
| L3 | 0–3709 | 3710 | 22 | 22 | 22 |
| LW | 0–3628 | 3629 | 70 | 70 | 77 |
| Total | eight separate state resets | 20098 | 264 | 255 | 147 |

All sources use `experiments/ds14_raw_multidataset/private/<name>/observations.jsonl.gz`, `profiles.jsonl.gz`, `assignments.jsonl.gz`, original raw measurement bindings and `scan_v4.json`. DS14's `SOURCE_MANIFEST.json` pins their real upstream paths and bytes/SHA. Do not replace Feeding SOURCE_OLD with another saved SAM3 producer or restored v3. DS33's RGB source inventory and raw sensor adapter provide actual image/timestamp/calibration bindings; no source availability claim establishes underwater physical accuracy.

## What the verified scan covers

`experiments/ms1_s0_development_8400/source_scan_v4.py` selects prediction-only local area collapse or direct source loss. Its actual constants are 30-frame area history, at least ten area observations, donor area ratio below .5, group ratio at least .95, pair mass at least .65, direct/soft mask support .15, and duplicate prior-mask IoU below .25. A previous-frame contact is required. Ambiguous multi-group cases are retained as diagnostics. These are suspect opportunities, not verified physical merges.

Both initial entrances require the surviving carrier to exist in the previous frame with sufficient history. Therefore an initial merge into a completely new source is outside this V4 scope. The earlier MS1 compatibility-graph scanner can propose such carriers, but is a different broader rule. Do not silently combine it with V4 or call it the same frozen trigger.

The old manager confirms two group frames, rejects persistent donor size at cancellation, and uses the earliest two adequately sized compatible detections as first split q. New post sources and members emerging from residuals receive an 8-pixel proximity allowance; unrelated persistent sources do not. It can report cancellation, out-of-scope, timeout, missing reference and unfinished EOF. Do not use GT or successful numerical/model results to select a different event or q. V4 has nine extra same-frame pairs; old DS16/DS29 dictionaries overwrite them and their single active manager further limits admitted episodes. A new runner must make any such conflict disposition explicit rather than silently claim all 264 are completed events.

Prediction-only DS29 geometry records contain 51 first-split q windows: 34 retain the old member native set and 17 have a changed post native set. This is evidence that the event scanner/manager already reaches both persistent and new post sources; it is not a physical identity result. DS31 uses the same suspects but only one first-split association occurred in its actual eight-source run. Its complete identity and protected-group candidate logic must not be substituted for the original Z4Q bottom layer.

## Reference and fragment provenance

`history.py` adapts DS29 History and its exact `freeze_pre` contract. The version is `[native, observed_gap_generation, actual_public, public_epoch]`; continuous frame, increasing real time and equal versions are required within a fragment. Each recorded clean point must coincide with this branch's exact current bank anchor, pass the original engine quality, have no neighbors, and not be retired. Explicit GROUP, RESIDUAL, pending POST or unresolved classes are anonymous even if their neighbors are empty. Their observations remain in `frames.objects` and never enter pre.

Live history holds at most 30 points and snapshot fragments contain the latest ten. Risk or absence drops live continuity while exact immutable anchor records and historical snapshots survive for twelve real seconds. `freeze_pre` looks up the episode's exact protected bank anchor and that source's actual snapshot fragment; it cannot fall back to another native or an older anchor merely because public integers match. All pre points precede suspect; future/same-frame anchors and missing references return UNKNOWN. Raw depth entries are scalar provenance references and original numerical summaries, never pixel arrays or GT.

The runner must capture needed source rows/masks/raw packets at the first suspect. History retains frame snapshots for twelve seconds; a snapshot's ten-point fragment can begin slightly earlier than the snapshot's own retention cutoff. If such source data has expired from the runner cache, retain UNKNOWN or fetch the exactly pinned already-acquired source row; do not interpolate, join across risk or substitute a newer reference. Post remains an independent anonymous same-version fragment until a mapping is admitted; future observations are limited to the declared unpublished lag cache.

## Known limitations

| Boundary | Actual knowledge |
|---|---|
| Local timestamps | All 20098 local frame sequences complete and times strictly increasing. L3 observed delta-t .005–.442 seconds; other sources approximately .032–.035 seconds. Use real times, not assumed 30 FPS. |
| Native source generation | No observation row has producer generation/reset/session fields. A disappearance and reappearance is an observable generation boundary; an invisible upstream reset or physical identity swap under a continuous native token is UNKNOWN. |
| Public identity | A committed public/epoch mapping supplies a versioned reference contract; it is not GT certification. Earlier wrong Z4Q aliases can be inherited and must be scored separately from the new physical restoration. |
| Feeding producer | Saved 2026-09-24 SAM3 20-frame batches, five-frame overlap; earliest sorted batch owns overlap frames, followed by historical overlap stitching. Upstream lookahead is UNKNOWN. |
| Independent data | Feeding segments are time-nonoverlapping parts of one recording, with shared producer/stitching dependencies. L3/LW evaluation reference quality is limited. No fresh blind or independent cross-dataset validation is claimed. |
| Short or missing history | In old DS29's 51 q windows, 27 have both pre sides at least three points, 19 have a one/two-point side, and five have a missing side. Keep missing velocity/reference UNKNOWN. |
| Five missing-pre examples | Feeding fourth F496→q499; FishSA development F3863→q3902 and F5927→q5939; LW F932→q1156 and F1277→q1281. These are prediction-record diagnostics, not GT-selected samples. |
| RGB-D physical motion | Measured XYZ differences use real optical correspondences and distinct depth timestamps. Same-coordinate depth differences are not motion; reliable depth support is not identity or occlusion truth. |

GT may be opened only after all new prediction/access seals, for independent scoring and separate actual-reference/public-origin diagnosis. Unscorable, missing, cancellation and no-change outcomes remain explicit.
