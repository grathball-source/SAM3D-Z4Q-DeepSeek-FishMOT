# Actual source and scope contract

- Base/fetched main: `b43a4ca62229e878b62ed81ea6c7327128636564`.
- Both complete, previously exposed DS2 development ranges: original frames
  701–1060/1201–1906, same FEEDING Orbbec recording;1066 frames total. This is
  development diagnosis on reused inputs, not fresh nonoverlap or independent
  validation. All original saved SOURCE_OLD masks are processed, including tiny,
  overlapping, fragmented and ultimately unscorable masks.
- Saved SAM3 source: `E:/CAU/D-MOT/data/AnnotationFeeding_20260924/ML/labels_raw`;
  original20-frame batches/15 stride/5 overlap with native-number stitching.
  Upstream SAM3 lookahead remains **UNKNOWN**. This filter reads only the current
  supplied mask/depth frame and does not claim to repair upstream causality.
- Depth source: `E:/CAU/D-MOT/data/AlignedFeeding_v1/depth_rgb_640x360/*.npz`.
  Only raw `depth_mm` is opened; its aligned RGB-camera Z is in mm on360×640 grid.
  Nonpositive/nonfinite values are missing. The NPZ annotation-derived
  `instance_id` plane is explicitly forbidden and blocked in the real run.
  No v3/filled plane, source-index-based fish selection or RGB texture is used.
- Frozen DS2 private assignments/profile RLE are read-only decoding inputs.
  Every original source polygon is freshly rasterized with its existing pixel
  center transform and compared exactly; old DS2 whole/core are independently
  recomputed and checked exactly on every object.
- Extraction exposes no GT, candidates, identity forecasts, source generations,
  group ownership or future frames. No tracker bank, reference or pre/post
  history is written. It produces current anonymous measurement evidence only;
  an AVAILABLE component is not an identity certification.
- Coordinate provenance: fact_id→frame-local token→private original native,
  original mask RLE, global crop `[x0,y0,x1,y1]`, local region RLE and source NPZ
  SHA. A selected local `(x,y)` maps to raw depth `[y+y0,x+x0]`. The fit stores its
  image-coordinate origin, scale and three mm coefficients; no fabricated
  physical velocity or corrected physical surface is asserted.
- References: authorized human-edited `labels_640x360/*.json`, opened only after
  complete measurement sealing and seal/code/source verification. No sealed
  test is read. Reference identities are used only to find one unambiguous
  same-frame silhouette for audit, not to alter extraction. There is no physical
  pixel-depth truth and no new tracking metric in this step.
- Whole/core/selected comparison includes the same accepted scorable objects.
  Coverage and every UNKNOWN/UNSCORABLE are retained separately. Missing never
  gets treated as correct or a zero-cost identity edge.
- All private pixels/RLE/references remain local. Public numerical statistics,
  code, checks, configs, source inventories, seals and reports are pushed main;
  restricted real paths/bytes/SHA and reproduction dependencies are listed.
