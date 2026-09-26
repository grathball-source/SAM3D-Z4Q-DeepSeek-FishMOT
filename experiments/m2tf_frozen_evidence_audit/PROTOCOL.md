# M2T-F sealed evidence-chain audit

Review base `cef0f894c715f18d856d404a7dd7e6c9b4b0c5dd`; old M2-T experiment commit `104e3a482d43601338ae589ca9b94df032c66ef5`. This is a **post-score audit**, not a new model experiment. External model calls, tracker transactions, training, hidden test GT and new IDF1/HOTA are zero. The 25 frozen model decisions and original scorer remain unchanged.

Run one real B01 longitudinal slice first, then all 25 attempts. Before opening the already exposed AO1 score key, check the old 333-file restricted inventory, source/plan and request/response seals, 26 START/END ledger pairs, each response hash, each body's exact image-block order against the private upload ledger and actual pixel SHA, and repeat-body equality. Map frame-local tokens through the private ledger to original predicted mask/native IDs and frozen AO1 endpoint roles. Only then read the exposed answer and ambiguity-filtered `offline_matches_{validation,development}` for posthoc attribution. `objects.gt_id` is accepted only for one unambiguous prediction; mixed, missing and competing matches stay UNKNOWN.

`audit.py` imports the sealed decoder without editing it. Its local adapter corrects only the non-list-evidence two-value return contract, rejects empty evidence/nonfinite time and duplicate JSON keys, and conservatively distinguishes endpoint references, explicit source-role path steps, comparison objects and ambiguous use. Text parsing is a reproducible **claim-use screen**, not a semantic oracle. It never links all tokens in a citation into a track. `test_audit.py` exercises invalid cases; `REPLAY_PARITY.json` demands exact equality on the 25 legal frozen responses.

All 100 edge records retain raw relation, cue, competing explanation, gap statement, every citation/token, sent image/frame/time, original mask/native, endpoint role and posthoc match status. `FIRST_DIVERGENCE.jsonl` localizes only explicit, unambiguous path steps. A last-certified to first-inconsistent pair is a bounded interval; a missing intermediate witness, unknown match or endpoint-only compatibility is not converted into an observed identity transition. No QA result is fed back to the model or decoder.

`visual_scan.py` decodes every cited support and contradiction image for the ten non-abstaining outputs, checks actual bytes and token bounding regions, but cannot certify identity. `VISUAL_AUDIT.md` separately records the images Work opened, including raw RGB explicitly marked `AUDIT_ONLY_NOT_SENT`; this answer-exposed QA is not independent blind review. Restricted pixels, provider file IDs, raw wire and the private token ledger stay off Git; see `ARTIFACT_MANIFEST.json`.

Reproduce on the authorized host using the old read-only run and a fresh output directory:

```text
python3 audit.py --run /home/xiongxiong/m2t_motion_first_20260924/full_run --repo /home/xiongxiong/m2tf_frozen_evidence_audit_20260926 --out <new-output-directory>
/home/data2/xiongxiong/dmot-annotation/env/bin/python3 visual_scan.py --run /home/xiongxiong/m2t_motion_first_20260924/full_run --old /home/xiongxiong/m2tf_frozen_evidence_audit_20260926/experiments/m2t_motion_first --audited <new-output-directory> --out <new-output-directory>/DECISIVE_PIXEL_SCAN.jsonl
```

The `--repo` host directory is a temporary copy of public repository files for hash comparison, not a new source of answers. `audit.py` writes once and refuses to overwrite outputs.
