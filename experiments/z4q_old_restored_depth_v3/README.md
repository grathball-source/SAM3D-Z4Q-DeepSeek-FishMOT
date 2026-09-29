# OLD source with restored v3 depth

This isolated diagnostic keeps the saved OLD SAM3 masks, times, source generations,
controller configuration, and two 405-frame segment boundaries. It replaces only
the depth statistics supplied to the frozen Z4Q and pairwise controllers using
`AlignedFeeding_v1/depth_restored_rgb_640x360/NNNNNN.npz:depth_mm`.

The v3 depth includes a small annotation-assisted fill (`provenance=4`). Results
are therefore **exposed, label-assisted diagnostics**, not a causal or blind
online tracking claim. The controller does not read `instance_id`,
`fish_interior_mask`, future frames, or GT. The postseal scorer alone reads the
edited reference labels. No model HTTP or new SAM3 inference is used.

Run with `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe` from this directory:

```text
test_depth_input.py
run.py freeze
run.py run
score.py
analyze.py
sensitivity.py
case_depth.py
accept.py
inventory.py
manifest.py
```

Every output is exclusive-create. Reproduction requires a fresh output directory
and the private OLD derived streams, SAM3 masks, and v3 depth files inventoried
in `public/FREEZE.json`; old predictions and seals stay read only.

`public/FAILED_ATTEMPT_1` preserves an unscored 200-frame first attempt. Its
seal creation stopped on a frozen-controller state-hash bug; no GT was opened.
The corrected code was frozen anew before the completed replay.

[`FINAL_REVIEW.md`](FINAL_REVIEW.md) gives the metric and physical interpretation;
`public/ACCEPTANCE.json` binds the principal seals and audits. The postscore
`sensitivity.py` check reruns all 405 frames with `provenance=4` depth pixels
zeroed, comparing every public mapping to the sealed v3 run.
`public/RESTRICTED_INVENTORY.json` lists private source paths, bytes and SHA
without publishing pixels or reference raster data.
