# DS3 — candidate-independent foreground depth measurement

Authorized next step, 2026-09-30; review state `b43a4ca62229e878b62ed81ea6c7327128636564`.
This is measurement development on the **already exposed DS2** SOURCE_OLD ranges
701–1060 and1201–1906: all1066 frames and every saved original mask. It is neither
fresh validation nor another dataset. No tracker, event trigger, q, candidate,
reference, two-dimensional motion, identity mapping or publication rule changes.
No RGB, annotation-derived instance_id, repaired v3, future observation, model
answer, training, SAM3 inference, completion service or inference HTTP is used.
Model HTTP/smoke/cost:0. Local CPU; existing NumPy/OpenCV/pycocotools only.

## Frozen hypothesis and contrasts

H1: valid background inside a loose SAM3 contour can bias a stable median.
Compare F0_WHOLE and the **unchanged DS1 F1_LEGACY_CORE** (exclusive area eroded
7×7) with one F2_LOCAL_FOREGROUND rule. No parameter search or re-run after scores.
CONFIG.json contains the actual used constants. Every F0/F1 n, fraction, median
and MAD must reproduce DS2; original polygons must reproduce cached masks.

F2 fits a robust image-coordinate depth plane to a5–20px outside annulus,
excluding all other predicted masks plus3px margin and nonpositive/nonfinite
depth. It requires64 raw samples,20% valid coverage, full rank, condition≤100,
and MAD-derived residual scale≤60mm. Five deterministic Huber reweighting steps
use scale floor15mm and c=1.5. This is a local background approximation, not a
calibrated physical surface. In the exclusive source contour, candidates on
**each** side of this plane need absolute contrast≥max(30mm,3×background scale).
3×3 closing is used only for connected support, then clipped to the exclusive
mask; it never supplies a measured or imputed depth. Actual retained pixels must
already have significant, finite, positive raw depth. Components require16
samples,20% selected/support coverage and raw-depth scale≤60mm. The largest
qualified component must cover≥70% of **all** significant pixels of both signs.
Otherwise output UNKNOWN, not a confident whole/core fallback. Neither the
nearest depth nor the largest unqualified mode is treated as fish automatically.

Both baselines, annulus, selected pixels, connected support, candidates and
failure reasons remain traceable. A selected-pixel valid_fraction of1 is a
construction property; reliability also needs support coverage, contrast,
sample size, dominance and background fit. No native/public integer or identity
prediction participates in pixel selection.

## Order, tests and primary measurement decision

1. Direct synthetic unit checks and one real F701 source→mask→measurement slice.
   Block network, manual labels and every NPZ key except depth_mm. Test missing
   depth/background, comparable components, isolated extreme noise, neighbor
   exclusion, tilted background, invalid holes, label order and statelessness.
2. Freeze code, CONFIG, plan, old-source hashes and original source inventory.
   Run all masks once; seal measurement, pixel and timing streams **before** any
   manual polygon is opened. Seals bind sources and code, not only result hashes.
3. After both streams are sealed, independently rasterize authorized human
   polygons on the640×360 grid. Source-mask matching uses IoU≥0.5 and best-vs-next
   margin≥0.1; also require that no other source mask claims that same reference.
   Missing or ambiguous matches stay UNSCORABLE. Group_id is only a postseal
   reference namespace, never an extraction input. These manually edited labels
   are not independently certified and provide **silhouette occupancy**, not
   physical depth truth. Main baseline comparisons use the identical matched
   accepted objects; all-object baseline and UNKNOWN coverage are also shown.
4. Fixed decision: measurement proxy PASS requires pooled pixel purity gain
   versus F1≥10pp, retained valid matched-fish pixels/original valid matched-fish
   pixels≥50%, and F2 acceptance among original core-usable objects≥50%.
   All three must hold; unavailable denominators mean INCONCLUSIVE. Show per
   segment and paired per-object changes, signed contrast and foreground loss.
   Do not infer depth accuracy or IDF1/HOTA improvement from occupancy PASS.

Pixel purity = valid sampled pixels within the matched human silhouette /
all valid sampled pixels. Other fish and outside-all-fish are reported separately.
Retention uses valid same-frame source-mask pixels inside that silhouette as
denominator, not the entire fish outside the SAM3 mask. Report both micro pooled
and object means, pre-existing missing depth and unmatched objects. Foreground
selection may lose fish with weak contrast; its refusal is a real availability
cost. Neighbor contours, water effects, depth/RGB alignment, missing pixels and
reference-boundary uncertainty limit causal interpretation.

Visualizations: earliest accepted, earliest UNKNOWN with significant pixels,
and maximum paired F1→F2 purity decrease (deterministic tie: frame/token). These
are diagnostic displays, not additional selection or tuning. Show raw depth,
whole/core/selected/annulus and postseal manual outlines; keep pixels private.
Public numeric SVG summarizes purity/retention/coverage. Restricted inventory
lists actual paths, bytes, SHA and reproduction dependencies. Seal old files,
commit all public work, nonforce push main and verify actual remote ref/files.
This step ends with a measurement conclusion; it does not insert F2 into tracking.
