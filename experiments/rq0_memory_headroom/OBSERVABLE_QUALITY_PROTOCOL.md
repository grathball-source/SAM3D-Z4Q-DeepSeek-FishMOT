# RQ0 observable reference quality — frozen before GT

The unit is an original `(split, frame, native_id, mask=n:<native_id>)` observation which the frozen Z4Q actually admitted as an association reference. The image reviewer sees the original RGB, the predicted mask overlay and at most two preceding frames for context; no future image, GT identity, score, or tracking outcome is shown. The reviewer must open real pixels, not infer them from hashes or reports. This is a new RQ0 research assumption, not an E1C repair.

- `VISIBLY_UNUSABLE`: the predicted single-fish reference visibly contains two or more fish, appreciable foreign fish pixels, or a severe visible mask/image artifact that makes its single-fish appearance or shape misleading. Cite the inspected observation key and what is visible.
- `VISIBLY_USABLE`: a discernible single fish with a mask mostly following that fish, suitable as a reference in the supplied causal view. It does not certify that the public ID or depth is correct.
- `UNKNOWN`: cannot decide from the supplied RGB and mask, including occlusion, poor illumination, ambiguous touching bodies, missing actual pixels, or depth uncertainty. Default action is ALLOW.
- `IDENTITY_ONLY_CONTRADICTION`: separate post-score diagnostic, never an image-quality veto. It means exposed GT identity disagrees while the visible fish reference itself is usable. A GT-only mismatch cannot be relabeled `VISIBLY_UNUSABLE`.

Review selection is prediction-only: among B0-allowed writes 1–150 frames after a predicted contact, rank by `(2 if contact age <=30 else 1) + (1 - min(1, mask area / bounding-box area))`, break ties by frame/native, retain at most 48 per split with 45-frame spacing per public ID. This ranking is for audit coverage, not a gate. Unreviewed writes are `UNKNOWN` for the limited oracle; its coverage must be reported.

The frozen simple quality rule `Q-rule` adds a veto only to B0-admitted writes when `box_fill < 0.45` or finite predicted `presence < 0.65`. It uses the same current predicted mask geometry/presence that the reviewer receives, plus no GT. No threshold search is permitted. The visible oracle vetoes only reviewed `VISIBLY_UNUSABLE` keys; `UNKNOWN` and identity-only contradictions remain ALLOW. The quota control orders B0-admitted writes by SHA-256 of `split:frame:native_id` and vetoes the same total number as the oracle; that quota is post-hoc, not an online deployable policy.

All branches retain B0's own quality, neighbor, area, latent-merge and depth filters. A veto affects only a coherent association-reference write; it cannot edit an ID, mask, alias, or SAM3 internal memory. Continuous branch states are independent. No API call or VLM quality claim is made in RQ0.
