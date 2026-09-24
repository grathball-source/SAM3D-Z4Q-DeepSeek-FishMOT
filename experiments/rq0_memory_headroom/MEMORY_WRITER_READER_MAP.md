# Which memory RQ0 actually changes

```text
Original RGB + fixed SAM3 masks/depth features
  A  SAM3 internal pixel/object memory -> already-frozen native masks (not run or edited by RQ0)
  B  native observation + depth profile -> StableReturn.step
       -> D1 bank writer -> motion/depth/eligibility readers -> future old/new association
       -> Z2 view_bank writer -> core/whole history readers -> birth association
       -> Q recent_core writer -> recent isolated core reader -> birth association
       -> RQ0 coherent post-step reference admission (only B0-allowed writes)
  C  E1/E1C packet history cache -> text/image request construction only; not a Z4Q reader
```

Actual inherited controller chain: `StableReturn` in `controller_return.py:12-20` → `QualityBirth` in `controller_z4.py:12-20` → `NativePrior` in `controller_z3.py:12-20` → `BirthRefine` in `controller_z2.py:11-18` → `DepthRepair` in `repair_controller_r3.py:14-20` → `DepthIdentityBalance` in `controller.py:19-34`. `Bridge.preview/commit_once` in `experiments/vl_assoc_e1/r0_source/bridge.py:64-69,119-138` clones and commits the full engine, not the E1 packet history.

| Real field / source | Writer and existing admission | Later reader and association consequence | RQ0 treatment |
| --- | --- | --- | --- |
| `bank[k].last_seen/last_frame`, `birth`, `native_seen`, alias, partners/contact | `DepthRepair.step:35-44,132-133,150`, ordinary observation/lifecycle | `DepthRepair.step:46-49`, `BirthRefine.step:127-138`, partner reservation | Never vetoed; current mask and public output remain intact. |
| `bank[k].clean_box/motion/areas/clean_time/clean_count/anchor/depth_history/ema` | `DepthRepair.step:134-149`: original quality, no neighbor, area ratio 0.5–1.8, no latent merge, valid depth | `DepthIdentityBalance.motion:43-53`, `z:34`; `DepthRepair.step:46-49,69-98`; `BirthRefine.step:131-137`, native/partner eligibility | One coherent value/provenance/count/time transaction; VETO restores pre-write reference, not lifecycle. |
| `view_bank[k][core,whole]` measurement, anchor, time, count | `BirthRefine.step:161-184`: original quality, no neighbor, area ratio 0.5–1.8, no latent merge; per-view profile measurement threshold in `measurement:17-21` | `BirthRefine.history:23-28`, `edge:41-114` core/whole and partner comparisons | Same observation-key veto as bank, including anchor/time/count. |
| `recent_core[k]` measurement, anchor, time, count | `QualityBirth.step:69-92`: certified native run, original quality and area/neighbor/risk checks | `QualityBirth.history:22-41` may substitute a recent isolated core in birth comparison | Same observation-key veto; ordinary expiry/deletion remains in engine control. |

New implementation: `quality_gate.py:18,26-111` snapshots only real reference fields, calls the unchanged `StableReturn.step`, detects writes by `anchor.frame/native_id`, and restores all referenced values plus their source anchor/time/count only for a selected VETO. This post-step position is valid for the recorded chain because the original readers run before the writer sections inside a frame; the next frame starts from each branch's own engine. It does not create a SAM3 memory experiment or a direct ID edit.

Real canary `CANARY_DEVELOPMENT.json`: B0-allowed write `development:986:n:0` changed bank, view_bank and recent_core atomically. ALLOW matched B0 output and full engine state for all 8400 frames. VETO preserved the current output, target `last_seen/last_frame`, all non-target reference state and alias/birth/pending/native state (`ATOMIC_TESTS.json`). At frame 1274, the real `history:core` reader used anchor 986 in ALLOW but 985 in VETO. This proves write → later reader propagation, not improvement. The 2 visible-oracle vetoes in validation similarly changed later reader/trace records but **zero output-ID frames**; their cumulative later-reader counts must not be added per veto as independent causal effects.

`SCORER_CROSSWALK.json` confirms the old `native_to_gt` field and the new `objects.gt_id` with ambiguity withholding use the same frame-local max-cardinality/IoU≥0.5 protocol on all 11,288 exposed frames: 50,271 development and 17,197 validation object rows, no missing/extra keys or differing bindings. The 194 and 298 unknown object rows remain unknown, not forced into association truth. This is a scoring-input crosswalk, not validation of hidden fish identity from RGB.
