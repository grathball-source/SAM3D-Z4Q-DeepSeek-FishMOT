# DS15 replay and scoring integration audit

Audit base: `95f1a83172d6b90f36ff8bd5a7d948e74b42ae80`, 2026-10-02. Ponytail full. Read-only source/code/record inspection; no prediction, scorer, SAM3, training, API, GPU or server job was executed during this audit. The initial audit created only this document. The parent subsequently authorized this agent to implement the new `score.py`; syntax/import checks do not run a predictor or open reference raster. This document identifies integration seams; it does not freeze a scientific hybrid or authorize a parameter search.

## Smallest reusable design

Use one new DS15 runner with explicit branches and one separate scorer. Reuse the eight immutable DS14 prepared input directories by absolute path and SHA. Do not rerun `prepare_inputs.py` or copy raw NPY/H5 arrays. Keep DS14 and every old seal read-only. Make fresh DS15 numeric predictions, traces, publication/access ledgers and seals.

| Arm | Real state path | Necessary boundary |
|---|---|---|
| `SAM3_NATIVE` | Saved `row['native']` / `assignments.variants.N0` | Exact same masks, order and IDs; no controller |
| `Z4Q_FROZEN` | Original `online/closed_loop_2888/z4q_source/bridge.py:Bridge`, original CONFIG; `preview` then `commit_once(view)` once | No NE1 edge veto, group manager, R12 selector, new history or output relabeling |
| `R12_ARCHIVE` | Exact DS14 `DepthNativeBridge` + `DepthNativeManager` + state/memory/group/birth flow | Fresh own state; every prediction and decision must reproduce old DS14 `R12_RAW` |
| `HYBRID` | One explicitly frozen repaired controller/selector path | Own state and own lawful baseline; implement the mechanism selected from the comparison audit, never import another arm's engine/history |

If a mechanistic ablation is retained, change one named mechanism only and run it on all eight segments. A depth-zero arm would test depth necessity; a group-only forecast/admission ablation would distinguish group repair from automatic reconnect restoration. The four required arms already answer whether the repaired system improves against native and original Z4Q; adding several variants would become a search.

The segments must remain Feeding 0–199, 351–555, 701–1060 and 1201–1906; FishSA development 1–8400 and exposed validation 9301–12188; L3 0–3709; LW 0–3628. There are 20,098 frames, eight independent resets, and no continuous Feeding 0–1906 claim. L3/LW retain weak prediction-derived-reference status. No cross-dataset pooled headline is justified; Feeding alone is pooled with segment-specific ID namespaces.

## Exact control flow seams

Paths below are repository-relative and refer to the audit base.

| Current code | Actual role | DS15 integration consequence |
|---|---|---|
| `ds14_raw_multidataset/common.py:26–35` | ARMS, SEGMENTS, RUN and input_dir are fixed to DS14 | DS15 needs its own output root and explicit read-only DS14 input root |
| `ds14_raw_multidataset/runner.py:125–137` | Creates independent bridge/manager/depth/support/birth memory for every event arm | R12 and hybrid cannot share mutable state; Z4Q needs a plain Bridge branch |
| `runner.py:147–164` | Joins source rows with immutable depth measurements and extracts current contact pixels only on noninitial first-ever births | Reuse cached rows; retain same frame/time/raw field binding; contact certificates remain real current-frame measurements |
| `runner.py:172–182` | Manager classifies current event, freezes pre-risk depth, breaks risk member history, previews lawful own state, then constructs birth candidates | Do not freeze history after admitting q/current post or mix alias/public epochs |
| `runner.py:190–212` | At q, records one post sample; calls old DS9 group selector; stages a group restore or own-branch local fallback | This is the group repair seam; current DS14 is still old WLS here |
| `runner.py:214–219` | Birth choice and stage; group and birth transactions are mutually exclusive; exactly one commit | Keep atomic target-collision rejection and capacity limit; do not apply group and birth serially in one frame |
| `runner.py:224–234` | After commit, updates versioned depth, raw support and birth memory, then manager geometry history | A hybrid automatic alias must update these histories with its own committed public epoch; preview facts cannot enter clean history |
| `runner.py:235–280` | Emits all original masks, binds birth/transaction hashes to one prediction line, then publishes ledger | All four arms should enter this single publication line only after their decisions/commits |
| `runner.py:302–313` | Writes complete seal after final frame and logs | New arm/runtime/access files need coverage in fresh DS15 seals |

The original Z4Q flow is already demonstrated without contamination in `ne1_native_first_event_association/replay.py:179–209`: instantiate `Bridge`, `preview`, `commit_once` and record the real trace. Its accepted automatic reconnect events lack `origin_rule` in some original records; classify for **logging only** as BIRTH_REFINE when `birth_frame == frame`, otherwise D1_DELAYED. Do not modify original scientific code merely to label traces.

`bridge.py:Bridge.preview` deep-copies the engine and runs one actual controller step on that clone. It returns the prospective engine and mapping, plus effective epochs. `commit_once` installs that engine and updates epochs, provenance and previous IDs. Therefore preview is not publication, and reusing the trial for a different arm or calling the authoritative engine directly before staging would break branch purity. Use a direct original-controller replay for Z4Q parity and assert preview leaves authoritative state/version unchanged.

## Native-first versus original automatic rules

`ne1_native_first_event_association/ne_controller.py:NativeFirstProtectedReturn.edge_veto` rejects every `D1_DELAYED` and `BIRTH_REFINE` candidate **before assignment**. This keeps measurements and native-return rules while disabling the original automatic identity edges. DS14 inherits that controller through `DepthNativeBridge`; it is not the original full Z4Q. DS14's current assertions at runner lines 220–221 are correct only for R12/native-first arms and must not be imposed on Z4Q_FROZEN or on a hybrid that deliberately reinstates selected automatic edges.

For a hybrid that borrows automatic Z4Q rules, the existing PX hook-compatible classes offer the narrow pre-assignment `edge_veto` seam. Inject the selected controller explicitly into the hybrid bridge; do not toggle `enabled=False` or repair IDs after publication. Preserve the original frozen Bridge unmodified for the baseline. Freeze and trace which rule is enabled/vetoed and why, including accepted edges, target occupancy and qualified native-return outcomes.

Original Z4Q profile consumers use `whole`/`core` plus actual scores/presence and observation quality. DS14 prepared rows are suitable: Feeding and FishSA SOURCE_MANIFEST records report `raw_profile_changed_objects=0`; masks/order/geometry/scores/presence were preserved, and only unpublished auxiliary RLEs were excluded (60 development and 20 validation archive entries). L3/LW are deterministic polygon/raw-depth adapters, not a previously continuous SAM3 session. A new Z4Q result on these inputs is an original-code same-source raw replay; historical scores are comparable only when the historical input/raster/version and segment reset match.

## Source, history and version safeguards

The existing history key is `(segment, arm, source_generation, public_id, public_epoch)`. `DepthState` lives in `ds1_depth_only/depth_state.py`; it starts a new record on version change, clears current samples on gaps/risk, retains one latest clean fragment and never stitches around group or pending observations. `freeze` also checks current epoch and generation and excludes frames after `suspect-1`.

`MergeSplitManager._history_update` at `ms1_s0_development_8400/merge_split_manager.py:341–389` resets clean/risk histories after source generation, public epoch/public ID or native-run restart changes. Group/residual/post samples stay classified separately. `BirthMemory` binds immutable disappearance fragments and actual bank-anchor versions independently. Its candidate checks reject no bank, changed bank/source/version, occupied/aliased/group-reserved public, noncontiguous clean history, depth/geometry mismatch and full reference-to-query gap beyond the frozen limit.

There is a concrete group forecast gap. `runner.py:195` dynamically loads `ds9_joint_h0_depth/association.py`; that module imports the old `depth_state.predict` WLS. Birth reconnect instead reaches DS11 and DS14 `forecast.py` local-level prediction. Copying or changing only `forecast.py` cannot fix group recovery. The new group selector must explicitly call the chosen shared forecast with the frozen role/key/source/cutoff and report those facts. Each role must remain UNKNOWN when its valid history is absent. `forecast.predict` currently defaults missing per-sample `version_key` and observation class to the enclosing frozen key/clean class; BirthMemory supplies explicit version keys, whereas DepthState group samples do not. A new shared validator should bind group samples to the existing checked record key without inventing missing history, and record the qualification decision explicitly.

The old DS9 selector's `used_edges` counts depth cells across all role×post pairings, not the number of separately supported identities. A role with no history has zero/common-uninformative evidence, yet another role's geometry can still select a two-ID permutation. Do not use `used_edges >= 2` as a two-identity safeguard. Any per-identity admission must inspect the actual changed source→target assignment, its clean role history and its depth-versus-lawful alternative evidence. Record no support, contradiction, ambiguity and rejected transaction as distinct outcomes. This is a scientific policy change that belongs in the new freeze only.

## Protection, local rollback and first publication

Use the DS14 lawful own-branch publication behavior, not the older temporary H1 baseline. `DepthNativeBridge.causal_view/preview` (controller.py:115–157) runs the complete own-branch lifecycle before restoring the protected event stores. It preserves outside ownership/native-return semantics and keeps protected member banks intact. `DepthNativeManager.before` refreshes protected outputs from that same own-branch causal view.

At rejected q, `DepthNativeBridge.local_fallback` (controller.py:159–181) releases protection by adopting the full **same arm's pre-frame causal engine**, asserts identical lawful mapping and logs outside equivalence. This differs from original `GroupBridgeP.local_fallback`'s transplant/UNRESOLVED behavior; the older S0-P implementation cannot be substituted silently into R12_ARCHIVE. Neither may call `rollback_to_baseline` with another arm.

`GroupBridge.stage_group_restore` (old manager:147–204) checks version/generation, protected bank equality, exact two-member bijection, actual observations and unique public targets before changing alias stores. It keeps bank/public keys separate from native source keys. Real q can seed the resolved bank only after the chosen mapping; group centroid/depth never seeds both identities. Retain visible-member-residual rejection, exact one current post per role, and transaction-versus-first-publication equality.

For Z4Q automatic actions, log both the original trace and mapping/public epoch. For hybrid decisions, log lawful baseline, selected candidate, per-role support, failed stage reason, admitted changes and committed mapping. All raw masks/fragments and negative unresolved/quarantine IDs stay in predictions and scoring. Score improvement alone cannot establish physical identity success.

## Integration obstacles and minimal fixes

1. **Module resolution is stateful.** DS14 and older kernels use plain `common`, `controller`, `forecast`, `source`, `association` names and sys.path manipulation. Loading DS14 runner by a unique importlib name does not isolate the imports inside it. Avoid running DS14 and DS15 common modules side by side in one interpreter. Use one DS15 entry process with explicit common/input/output pins and explicitly loaded classes/functions. Log resolved `__file__` paths and hash the actual loaded closure before freezing. A tiny wrapper may reuse old files, but module origin and archive parity must be demonstrated before trusting it.
2. **Several parameters are bound at module import.** `CFG=read(HERE/'CONFIG.json')` occurs in multiple scientific modules, including the old dynamically loaded group association. A late reassignment of `common.HERE` cannot reliably swap configuration. Pass/inject the selected forecast/selector at the explicit call site, keep archive modules/config fixed, and place new scientific parameters in DS15 only.
3. **Outputs are not overwrite-safe by themselves.** DS14 opens most GZIP files with `wt`; output directory exclusivity comes from prior freeze and x-mode publication files. DS15 should reject any preexisting prediction attempt and use fresh attempt roots, preferably x/xt for new ledgers. Keep failed attempts intact. Do not point common.RUN at DS14 even temporarily.
4. **Scorer is two-arm specific.** `evaluate.delta`, `event_audit`, transaction iteration, event publication checks and changed-frame accounting hardcode R12_RAW. Adapt those to an explicit arm list and arm-keyed transactions; keep masks/reference/matching/official metric math unchanged. Native has no state transaction; each real state arm needs exactly one per frame. Verify all arm rows and unique mask/public counts before GT opens.
5. **Correct reference adapter is essential.** `evaluate.py` still contains a malformed development GT digest and an incorrect aligned-package validation assumption. DS14's documented reproducible entry is `score_protocol.py`, which extracts the 64-character old scorer digest and calls `finish_scoring.py`. For DS15, pin the corrected original development SHA directly from the authoritative old scorer and use the final original `inputs.zip` GT entries for validation. Do not compare them to aligned-package annotation versions; F9398 differs. L3/LW use recovered weak references and original1080 polygon masks for scoring; prediction source remains scaled640, with the original source labels used only in the independent scorer.
6. **All-seal/access contract is hardcoded.** DS14 requires `ALL_TWO_BRANCHES_EIGHT_SEGMENTS_SEALED`. DS15 must seal all four/five arms and all eight access inventories under a new status, then only run scoring. Copy the prediction guard's blocked paths and NPZ/H5 field whitelist rather than weakening it. Avoid importing a provider module at all.

## Required parity and meaningful checks before the full run

Prediction-only checks, with no reference raster opened:

- All eight SAM3_NATIVE prediction rows equal immutable DS14 and assignments.N0, including mask order, time and original frame IDs.
- All eight R12_ARCHIVE mappings, events, selections and publication decisions equal DS14 R12_RAW. Arm-name/provenance labels can be normalized explicitly; JSON/GZIP hashes are not expected identical when arm labels or gzip metadata differ. Scientific floating values and decisions must be exact, including any recorded inert OpenCV distance metadata.
- Z4Q_FROZEN equals a direct untouched Bridge replay on the same rows; where old same-input archives exist, compare every frame and automatic action too. Do not require its output equal native. No model/provider code or new rule may enter its actual call stack.
- Preview purity, stage rejection no-mutation, one commit per frame, no alias stealing, qualified native return, disjoint public/source key domains and outside-state preservation on local fallback. Reuse existing focused DS10–12/NE1/S0-P checks rather than inventing a new harness.
- New group-specific regression: missing A clean history cannot masquerade as two supported identities; both admissible swapped roles retain fact/key/cutoff binding; current q never contaminates pre; gap/public-epoch/source-generation changes cannot stitch history; depth contradiction and indistinguishable evidence keep lawful baseline. Tests must match the actually frozen hybrid mechanism.

After all eight formal seals, native six-field metric parity must match DS14 at its original references, R12_ARCHIVE must match DS14 metrics, and complete mask counts/FP/FN must match across arms. Compute each arm versus both native and Z4Q. Report each segment, Feeding pooled result, committed correct/wrong/unscorable mappings, changed frames, alias persistence, cancelled/no-effect events, raw-core coverage and publication timing. Postseal physical scoring should retain literal clean/bank/origin relations and UNKNOWN rather than relabel unknown as success.

## Local resources measured from the existing records

No raw array duplication is required. The eight prepared private directories total **120,650,844 bytes (115.06 MiB)**. Their DS14 public run outputs, including postseal records, total **123,269,348 bytes (117.56 MiB)**. These exclude old failed prepares, private visualizations and the large original data dependencies. On inspection the local E: volume had **17,452,466,176 bytes (~16.25 GiB) free**; this is a one-time observation, not a reservation.

| Segment | Masks/observations | DS14 one-state-arm replay seconds | Prepared bytes |
|---|---:|---:|---:|
| Feeding0–199 | 5,332 | 11.88 | 2,720,074 |
| Feeding351–555 | 5,494 | 19.18 | 2,862,532 |
| Feeding701–1060 | 9,596 | 27.79 | 4,970,959 |
| Feeding1201–1906 | 18,786 | 42.62 | 9,547,702 |
| FishSA8400 | 50,271 | 118.61 | 39,097,400 |
| FishSA2888 | 17,197 | 41.47 | 13,455,875 |
| L3 | 36,927 | 146.36 | 23,977,712 |
| LW | 38,239 | 210.04 | 24,018,590 |

The total is 181,842 preserved masks. DS14 summed replay time was **617.94 seconds** for native plus one stateful R12 arm, with at most three independent single-thread local processes. Preparation would cost ~52.6 summed minutes and is avoidable. DS14 final scoring wrapper took **470.22 seconds**, in addition to the earlier preserved partial/failing score attempts; this is a historical timing, not a fresh benchmark.

For native plus three stateful DS15 arms, allow roughly 3× the DS14 state work before considering parallel segment scheduling; traces and deep-copy/assignment cost can differ for original Z4Q. A practical conservative budget is **30–60 minutes** for frozen full replay, checks and independent scoring with three local single-thread segment processes, and **at least 1 GiB** free for numeric outputs/logs/optional bounded QA. Do not promise this as runtime. A first causal engineering slice can measure elapsed/resident memory without GT or policy tuning. Python 3.12 at `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe -B` and existing NumPy/SciPy/OpenCV/h5py/pycocotools/TrackEval suffice. No new environment, GPU or server allocation is needed. DS14 peak resident RAM is unmeasured; assignments are loaded segment-wide and should be included in a new process resource record.

## Audit conclusion

There is no data or scorer-format obstacle requiring new SAM3 or raw-depth preparation. The substantive work is one hybrid controller/selector injection, explicit versioned source qualification, a four-arm first-publication runner, and an arm-aware scorer using the final corrected reference contract. Original Z4Q and frozen R12 must each remain scientifically pure and exactly reproducible. A repaired result that only removes the known R12 swaps is damage prevention; performance gain requires comparison with the same-source native and original Z4Q, alongside physical mapping outcomes and the existing exposure/weak-reference limits.
