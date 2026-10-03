## DS22 local-background measurement experiment completed (2026-10-04)

All90 original actions: correct5 compatible/10 unknown, wrong1 weak conflict/3 compatible/13 unknown, unscorable1 conflict/3 compatible/54 unknown. All171 endpoints were reopened and validated. No tracker replay, new scores or model HTTP. Engineering complete; depth increment insufficient; STOP this frozen representation. Original Z4Q remains the reference. See experiments/ds22_local_background_depth/FINAL_REVIEW.md and NEXT_STEP_PLAN.md. The single next plan is a fixed RGB-D spatial-correspondence audit, not yet run. Old seals remain read-only; pixels private.

## DS21 original Z4Q depth discriminability audit completed (2026-10-04)

All 90 original durable actions were audited symmetrically, including correct, wrong and unscorable cases. No new predictions, scoring or model HTTP were run. Measurement eligibility is not a tracking gain. See experiments/ds21_z4q_depth_discriminability_audit/FINAL_REVIEW.md and NEXT_STEP_PLAN.md for evidence and the single next action. Original Z4Q remains the performance reference; the current combined route is not automatically extended. Old seals are read-only; actual depth/mask figures remain private.

## DS20 pending confirmation isolation completed (2026-10-03)

主判定：COMPLETE_CONFIRMATION_REPAIR_DEPTH_GOAL_NOT_ESTABLISHED。六列八段，每列20098帧；模型HTTP/费用=0。
完整结果见 experiments/ds20_pending_confirmation_isolation/RESULTS.md、FINAL_REVIEW.md。确认隔离工程、事务恢复与深度增量分列，DS19旧seal只读。仅规划 NEXT_STEP_PLAN.md，不自动启动模型。

## DS19 protected event-local return completed (2026-10-03)

主判定：COMPLETE_TRIAL_PENDING_ISOLATION_GAP_DEPTH_GOAL_NOT_ACHIEVED。六列八段，每列20098帧；模型HTTP/费用=0。
完整结果见 experiments/ds19_protected_event_return/RESULTS.md、FINAL_REVIEW.md。共同事务恢复与深度增量分列，旧seal只读。仅规划 NEXT_STEP_PLAN.md，不自动启动模型。

## DS18 association evidence interface repair completed (2026-10-03)

主判定：COMPLETE_TRIAL_GOAL_NOT_ACHIEVED。六臂八段、每臂20098帧；模型HTTP/费用=0。
Feeding1471: MIXED_ORDER vs同源native ΔIDF1=+0.268647; vs原Z4Q=-0.471399; vs相同接口=-0.656411。
fishsa_development_8400: MIXED_ORDER vs同源native ΔIDF1=+7.930784; vs原Z4Q=-0.089400; vs相同接口=+0.031787。
fishsa_validation_2888: MIXED_ORDER vs同源native ΔIDF1=+3.957241; vs原Z4Q=-0.283902; vs相同接口=-0.278108。
L3: MIXED_ORDER vs同源native ΔIDF1=+0.000000; vs原Z4Q=-2.318468; vs相同接口=+0.000000。
LW: MIXED_ORDER vs同源native ΔIDF1=+0.000000; vs原Z4Q=-3.715862; vs相同接口=+0.000000。

Complete code/logs/results: experiments/ds18_association_evidence_interface_repair. Model HTTP/cost=0. Old seals immutable; private pixels inventoried locally. Follow NEXT_STEP_PLAN.md; no automatic new model run.

## DS17 mixed depth/activity repair completed (2026-10-02)

## 主判定

**已完成六分支、八片段、20098帧/分支的真实状态回放与独立评分。DS17没有可靠的新深度提点，并暴露两个明确的关联接口错误；冻结此版本。**

混合层记录、真实来源与逐发布记录可保留作诊断。当前版本不适合替换原Z4Q；不能将本轮失败外推为完整历史、深度或上下关系无效。

新增模型推理、smoke、训练、SAM3推理、补全服务和费用全部0。没有读取v3、选择新GT锚点、修改旧封存、改写已发布历史或少评任何ID。


Complete code/logs/results: experiments/ds17_mixed_depth_activity_repair. Model HTTP/cost=0. Old seals immutable; private pixels inventoried locally. Follow NEXT_STEP_PLAN.md; no automatic new model run.

# Latest: DS16 event-relative depth order (2026-10-02)

Completed six independent real-state branches, eight segments/20098 frames; all predictions and access sealed before reference scoring. Read experiments/ds16_relative_depth_order/PLAN.md, RESULTS.md, DEEP_REVIEW.md, MAIN_JUDGEMENT.json, POSTSEAL_ORDER_REVIEW.json and the state/order/pipeline audits. All181842 saved native masks conserved; original native/Z4Q all-frame and full metric parity exact. No new model HTTP, smoke, SAM3, training, completion, GPU, server or cost.

Common state repair advances real source/proposal continuity while freezing only protected public references. Original BirthRefine dev3902 n7->0 and validation global11488 n8->3 both retained; the ordinal inputs there are UNKNOWN, so these recoveries are common mechanism benefits. Group/unassigned post remain anonymous. The new event factor uses representative-core relative depth order, not verified local occlusion topology or a stable identity fingerprint.

Frozen judgement: FROZEN_ORDINAL_SUPPORT_RULE_NOT_MET; ordinal: NO_CERTIFIED_ORDINAL_SPECIFIC_RECOVERY.
fishsa_development_8400: ORDER IDF1/HOTA/AssA/IDSW 99.333472/77.829488/77.907638/6; versus original Z4Q +0.000000/+0.000000/+0.000000/+0.
fishsa_validation_2888: ORDER IDF1/HOTA/AssA/IDSW 80.697587/69.243869/60.074321/9; versus original Z4Q +0.000000/+0.000000/+0.000000/+0.
L3: ORDER IDF1/HOTA/AssA/IDSW 72.426787/75.362607/94.259655/1; versus original Z4Q -2.318468/-1.808950/-4.579391/-1.
LW: ORDER IDF1/HOTA/AssA/IDSW 64.329395/68.995155/83.813941/9; versus original Z4Q +0.000000/+0.003434/+0.008344/-1.
Feeding_pooled1471: ORDER IDF1/HOTA/AssA/IDSW 81.716806/79.859851/71.341782/132; versus original Z4Q +0.000000/+0.000000/+0.000000/+0.

Weak/UNKNOWN evidence, non-split events, stage rejection and unscorable reference are retained. Tiny negative ordinal support can veto an otherwise admitted geometric choice in this frozen version; its factor effect and admission-rule effect are reported separately. Raw adaptive-core pixel counts are not independent sensor-source counts or fish-surface accuracy. Feeding original four SOURCE_OLD ranges1471 only; another436 saved frames not tested. L3/LW dependent preannotation are weak diagnostics; exposed FishSA validation is not blind independent-video evidence. Private actual-pixel figures are inventoried and stay local.

Only next step, superseding the report generator preliminary suggestion: separate immutable bank identity references from live activity/partner state, keep this ordinal formula/trigger/q/quality thresholds fixed, then run one same-source full state-repair contrast. Local crossing measurement is a later candidate, not another concurrent next step. No new experiment started. Prior handoff bytes remain verbatim below.

# Latest: DS15 Z4Q/depth strategy repair (2026-10-02)

Completed five branches, eight segments,20098frames; all predictions/access sealed before original-reference scoring. Read experiments/ds15_z4q_depth_strategy_repair/DEEP_REVIEW.md, RESULTS.md, MAIN_JUDGEMENT.json, SUMMARY.json and three independent postseal audits. Original Z4Q19032 archived frames exact; native/R12 all20098 frame/event/metric parity exact;181842 mask tokens retained.1590 old files unchanged. Zero model HTTP/smoke/SAM3/training/completion/GPU/server/$0.24 private actual-ID/raw-depth figures are inventoried, not committed.

Target failed: DEPTH IDF1 dev92.002662 vsZ4Q99.333472; val76.641849 vs80.697587; Feeding81.820716 vs81.716806; L3weak72.426787 vs74.745256; LWweak60.613534 vs64.329395. Feeding small +0.103911/IDSW-2 does not meet native HOTA/AssA/IDSW superiority. Common protection loses original birth n7->0/dev3902 and n8->3/global11488 despite reopening both old hooks. It freezes source witness records while actual sources remain visible, creating artificial frame/time certificate gaps. Four original actions preserved; strict physical audit counts original six as5correct+1unknown, not6certifiedcorrect.3219 source-comparable checks/10850 total;0 depth vetoes. No rolling threshold search after negative results.

Only next step: separate anonymous real source continuity/proposal evidence from certified clean identity references. Preserve real target generation/epoch breaks, never update A/B clean from merged masks; jointly resolve and atomically publish current q. Do not force the known answers or copy whole B0 state. New version not started. Feeding only original4segments1471, notall1907; L3/LW prediction-dependent weak refs. Prior handoff remains verbatim below.

# Latest: DS14 original raw full performance validation (2026-10-02)

Completed all20098 frames: FishSA8400/2888, SOURCE_OLD Feeding1471, L3 3710, LW3629. Read experiments/ds14_raw_multidataset/RESULTS.md, RUN_NOTES.json, PLAN.md, FINAL_CHECKS.json, frozen code/input/state/publication/seals, METRICS and per-event audits. Same-source SAM3 vs frozen R12_RAW only; raw sensor throughout, zero model HTTP/smoke/SAM3/training/completion/GPU/server/$0. User's named-all-data instruction supersedes DS13's untuned two-clip/three-arm input block; no F9 or VLM result fabricated.

R12−native IDF1/HOTA/AssA/IDSW:8400 −10.211481/−5.452076/−9.902417/+2;2888 +1.373157/+0.166962/+0.280056/+2;Feeding +0.053222/+0.083103/+0.147373/−3;L3 −9.588185/−7.148416/−17.033664/+2;LW all0. L3/LW weak dependent preannotation diagnostic only; all data exposed, no independent-video claim. Whole 6-field old NATIVE parity exact and all1471 Feeding R12 frame/event parity exact. All181842 saved native masks conserved. Engineering/input/publication/scoring passed with append-only reference-pin/version errata; scientific stable-native target failed. Frozen R12 version stopped, not evidence all depth/history is ineffective.

Five group commits:2 correct/2 wrong/1 unscorable;three birth commits:1 correct/2 unscorable.8400 F4524 swapped1/7 and persisted3877 frames; A no clean history, B old group WLS predicted590.65mm with117.51mm scale vs current native7=657.80mm, native1=570.17mm. Geometry advantage+4.18391 overwhelms depth−0.07146. Birth uses repaired local level; group still frozen old DS9 WLS. L3 originalF1420 similarly swapped6/9. Do not label high candidate posterior physical truth or unscorable safe.

Prediction/parameter/old seal bytes unchanged;1334 old artifacts checked. Correct scoring uses original baseline inputs.zip GT version (AlignedDataset has one revisedF9398); all original baseline metrics exactly recovered. Failures and source errata retained. Fresh reproduction in an EMPTY copy uses score_protocol.py, not retired direct evaluate/score_remaining assumptions. Private pixels remain local with paths/bytes/SHA; public numeric performance SVG and records are complete. Actual main push/proof is appended separately.

One next step only: unify group and birth depth prediction and inspect per-identity support before joint restore; freeze a depth-identifiability admission repair, then same full-cohort test. Fixing back to native is loss prevention, not gain. Not automatically started; no LLM addition. Older handoff bytes preserved below.

Coverage: Feeding tests the original four SOURCE_OLD ranges only (1471 frames). All1907 saved native labels currently exist; the other436 frames in200-350,556-700,1061-1200 were NOT tested. Do not report them as missing or claim continuous1907 validation. See COVERAGE_BOUNDARIES.json.

# Latest: DS13 frozen validation source audit (2026-10-01)

User authorized start of DS12 NEXT_STEP_PLAN. Read experiments/ds13_frozen_validation/RESULTS.md, PLAN.md, INPUT_AVAILABILITY.json, source/use inventories and frozen/old byte locks. Status DS13_INPUT_BLOCKED; no new prediction/scoring/restore or scientific outcome. Feeding only old1471 used frames;1907 saved SAM3 includes436 gaps outside complete aligned-reference package. L3/LW have complete raw sources and fixed earlier evaluation, no DS tuning record found; do not falsely classify baseline exposure as tuning. Their reference is dependent preannotation; F9 native-v2 chain absent in inspected entries, explicit fresh-dev scope/external tuning history UNKNOWN. The two camera acquisition intervals overlap97.882s, not two disjoint time segments.

DS12 formal76 bindings and DS1-12 tracked1314 files verified unchanged. Five source-lineage checks PASS only; new source pixel/state/equivalence checks NOT_RUN. New metrics/success null; historical DS12 micro-gain stays old exposed development evidence, not DS13 validation. No HTTP/smoke/train/SAM3/completion/server/cost. Do not drop F9, substitute raw for v2, open sealed test or auto-tune R12. Questions about a new path or alternative L3/LW two-arm diagnosis await user reply; no dependent run started.

One next step: provide complete approved untuned saved cohort with reference and three-arm depth inputs, then execute unchanged frozen validation. All older handoff bytes preserved below.

# Latest: DS12 current-contact depth admission (2026-10-01)

Completed four SOURCE_OLD segments / 1471 exposed frames / four independent real-state branches. Read experiments/ds12_contact_depth_admission/RESULTS.md, PLAN.md, CONFIG.json, ENDPOINT_CONTRACT.json, checks/source/numerical reviews, all prediction/scoring seals, METRICS/BIRTH_AUDIT/SWITCH_LEDGER, three postrun reviews, actual visualization QA, restricted inventory and remote proof. Engineering/input/publication/scoring PASS; predeclared full birth-and-native target=True. R12_RAW/RESTORED IDF1/HOTA/AssA=81.029982/80.047159/71.677872, IDSW105 vs same-source SAM3=80.976760/79.964056/71.530499/108. Compared with F9, new birth adds +0.053222/+0.035110/+0.062108 percentage points and removes 1 switch. F9 shared group effect removes the other 2, not new depth credit.

Both arms one new certified restore: F1886 n198->public176, first publish before any temporary ID, actual mapping persists F1886-1906 (21 frames). Query/clean/bank/source-origin RGB reference all SAME; new wrong/unscorable commits0. Raw vs saved native-v2 outputs exact; restored increment0, depth necessity not isolated. Geometry LR3.816 alone exceeds log9; depth LR+.236/+.282 is weak supporting evidence. Native-v2 upstream RGB/future only exposed offline diagnostic; physical surfaces/mm calibration UNKNOWN. 105 noninitial births/arm:47 groupblocked/57 keep/1 commit. No GT trigger/q/anchor/action selection or frozen-rule tuning.

Initial engineering slice failed strict float32 EDT metadata reproducibility, preserved attempt1. Exact integer nearest-zero squared formula repair keeps all 2715 actual birth-frame mask cores pixel-identical; final slice/full strict checks passed with zero scorer precision exceptions. Postseal plot-check failure retained and repaired separately; no prediction/score replay. DS1-DS11 old tracked bytes/seals read-only. No HTTP/smoke/training/SAM3/completion/GPU/server/cost.

One next step only: freeze R12_RAW, select earliest complete authorized untuned time-nonoverlap saved segments by metadata, compare to same-source SAM3 full runs. First confirm input availability; no sealed test, result-based selection, parameter rolling or automatic model addition. NEXT_STEP_PLAN.md planned, not started.

# Latest: DS11 first-native-birth depth reconnection (2026-10-01)

Complete SOURCE_OLD 1471 exposed frames / four independent state branches. Read experiments/ds11_depth_birth_reconnect/RESULTS.md, PLAN.md, CONFIG.json, ENDPOINT_CONTRACT.json, exact source/census/checks, run/seals/metrics/BIRTH_AUDIT/SWITCH_LEDGER, private inventory and remote proof. Engineering/input/publication/scoring PASS. New birth COMMIT=0, all R11 frames exact F9; IDF1/HOTA/AssA 80.976760/80.012049/71.615763, IDSW106 vs native80.976760/79.964056/71.530499/108. Old group two restores explain all improvement; new birth increment zero and full native target False. Do not count common mechanism benefit as new depth contribution.

105 births/arm:47 groupblocked,55 currentquality/contact ineligible,1 depth-uninformative,2 NEW-best. F845 all qualified targets different fish; F1015 q IoU0 unscorable. 26 posthoc same-fish qualified candidates all blocked by current neighbors;25 usable raw core, not a predicted recoverable score. Source68 shows bank/clean reference physical mismatch despite matching engineering version. Native-v2 upstream RGB/future is offline diagnostic; physical ownership/calibration and independent video validation UNKNOWN. No HTTP/smoke/training/SAM3/completion/cost. Old DS1–DS10 files/seals read-only.

One next step only: current contact exclusive depth measurement certificate and narrow causal atomic admission, full105 triggers/four same clips; no GT-selected cases/threshold rolling/group bypass/LLM. NEXT_STEP_PLAN.md planned, not started. This supersedes the older DS10 confidence-only proposal for current execution; that version remains archived.

# Latest: DS10 depth failure repair (2026-10-01)

See experiments/ds10_depth_failure_repair/RESULTS.md, PLAN.md and diagnosis/*.md. Four independent real state branches, full same-source 1471 exposed development frames. New v2 IDF1/HOTA/AssA 80.890590/79.890848/71.401213, IDSW 108; native 80.976760/79.964056/71.530499, IDSW 108. Native target rule=False. Geometry is not an acceptance gate. Joint last-measurement depth forecast and current-object normalized null repair; no separate component attribution. All predictions/inputs/code sealed before scoring, F9 exact DS9 reproduction, predeclared inert diagnostic precision contract. V2 upstream RGB/future support: offline diagnostic only. No physical surface truth/independent-video validation. No model HTTP, training, SAM3/completion service or cost; old DS1-9 tracked bytes unchanged. One next step only in NEXT_STEP_PLAN.md, not started.

# Latest: DS9 lawful H0 normalized joint geometry/depth trial (2026-10-01)

See experiments/ds9_joint_h0_depth/RESULTS.md and PLAN.md. Six independent genuine state branches, 1471 same-source exposed frames, sealed before TrackEval and physical reference audit. J2 IDF1/HOTA/AssA 80.976760/80.012049/71.615763, IDSW 106; native 80.976760/79.964056/71.530499, IDSW 108. Frozen native-target rule=False. Compare geometry/zero/permutation before claiming independent depth gain. Original strict diagnostic metadata comparison failed; scoring completed with a separately sealed 281 one-ULP inert metadata exception. V2 has upstream RGB/future cleaning: offline diagnostic only; physical depth truth and independent-video validation unestablished. No model HTTP/smoke/training/SAM3/completion service or cost. DS1–8 old tracked files remain byte-exact. Public delivery requires normal main push and actual ref/key-byte checks. One next step only in latest report.

# Latest: DS7/DS8 depth failure audit and adaptive-core trial (2026-10-01)

See experiments/ds8_adaptive_depth_core/RESULTS.md / PLAN.md and experiments/ds7_depth_native_recovery/RESULTS.md. Two complete 1471-frame five-branch SOURCE_OLD replays; no model/API/SMOKE/training/SAM3/completion calls or cost. DS7 fixes lawful own-branch native publication and source-separated depth; DS8 changes only current-mask core geometry. P2 IDF1/HOTA/AssA 80.976760/79.964056/71.530499, IDSW 108; same-source native 80.976760/79.964056/71.530499, IDSW 108. Frozen full depth support=False. P0 native exact, old D2 exact, all masks preserved; sealed then independent official scoring and switch accounting. Restored native v2 has no annotation fill but upstream RGB+future cleaning: exposed offline diagnostic. No physical-mm truth or independent video validation; private artifacts inventoried by actual path/bytes/SHA. One next step is defined in latest RESULTS.md; no automatic model addition.

# Active handoff — DS6 full performance trial,2026-09-30

Read experiments/ds6_multifragment_depth_tracking/RESULTS.md/PLAN/CONFIG,
INPUT_REVIEW/old lock/effective settings,16unit+11scoring checks, all four segment
FREEZE/PREDICTIONS_SEALED and ALL_PREDICTIONS_SEALED/access audit,
METRICS/actual EVENT_AUDIT/SWITCH_LEDGER/FRAGMENT_REFERENCE_AUDIT,
SUMMARY/postrun reviews, private QA inspection/restricted inventory/remote proof.
Baseced663d97cadc23138c538f5784df7ed4e835fe2; complete1471 exposed frames/five branches/39208 masks.
Engineering/source PASS; depth increment FROZEN_SUPPORT_RULE_NOT_MET. Surface identity UNKNOWN.
Scalar vs multi shared-history same-state q choices changed0/18.
Old three controls fully exact; all prediction seals precede GT scoring.
No model/API/training/SAM3/completion/cost. No private pixel or old seal change.
One next step: 在固定四段上只消融“必须四边全部可用”的缺测门，验证候选一致的缺测边际化能否保留有效单身份深度证据；触发、历史资格、权重与事务保持冻结。
Not started automatically; do not retune this frozen version or add models.

# Historical handoff — DS5 surface/spatial observational audit,2026-09-30

Read experiments/ds5_surface_registration_audit/RESULTS.md, PLAN/CONFIG/FREEZE,
COHORT/SOURCE_INVENTORY/OLD_READONLY_LOCK, three initial independent reviews,
CHECKS/AUDIT_SEALED/REPORT_SEALED, CENSUS/REGISTRATION, SUMMARY/KNOWN_CASES,
three POSTAUDIT reviews, actual caption-v2 QA inspection, restricted inventory,
EXECUTION_LOG and REMOTE_VERIFICATION. Base56c2ea61682edea71328976c4fed27230f334c2a.
All1066frames/28382objects,73cases+59uniquecontrols;14missingcontrols retained.
Engineering/source-contract PASS; physical surfaces/water calibration UNKNOWN.
No extractor/tracker/model/DepthState intervention; HTTP/training/SAM3/completion/cost0.
Largest30mm depth-piece shadow not promoted: C−92/D−14/U+106 vs original F6;
multiple pieces may be spatial fragments at same depth, not different surfaces.
F1821 old20/14 depth clusters become20/66; median flips while MAD falls.
No uniform nonzero shift improves either fixed aggregate queue; local/subpixel
misregistration/refraction/physical ownership unresolved.
recordedR nonorthogonal; SO3 shadow is no certified correction/data substitution.
DS1–DS4 files/seals and source hashes preserved; pixels private.
One next step: multiple provenance-bound depth pieces and causal same-version
history disambiguation; uncertain choice staysUNKNOWN. Not yet implemented.
Do not retune DS5, select GT warps or automatically add VLM/tracking.

# Historical handoff — DS4 frozen depth-quality measurement,2026-09-30

Read experiments/ds4_depth_quality_repair/RESULTS.md, PLAN/CONFIG/FREEZE,
SOURCE_AUDIT/COMPONENT_AUDIT/EVALUATION_REVIEW, CHECKS/SCORE_CHECKS/READONLY_ACCEPTANCE,
MEASUREMENTS_SEALED/SCORING_SEALED/SUMMARY, both per-object occupancy streams,
POSTSCORE_REVIEW/POSTSCORE_DIAGNOSTICS, CASES_POSTSEAL, source/restricted/public
inventories, all logs, original and caption-repaired QA metadata/actual inspection,
and REMOTE_VERIFICATION. Base ace9a37b1c6a2a59d3d5397f335d081f1a5a8ae8.

All1066 exposed SOURCE_OLD frames701–1060/1201–1906 and28382 masks completed.
Engineering/input PASS; PROXY_GAIN_ONLY; physical depth/registration/tracking UNKNOWN.
Q28088+294unscorable exact to DS3; fixed raw-silhouette R21817.
F2→F6 compatible15766→17655, discordant202→143, UNKNOWN5849→4019.
44new discordances (39old-compatible,5old-UNKNOWN), fish yield35.3371→41.2397%,
nonmatched samples41620→58240; conditional purity98.9106→98.6966%.
F6 is frozen native>5m SUSPECT admission plus separate1mm background floor;
foregound floor15mm, contrast floor30mm and other DS3 rules unchanged.
F3 range-only/F4 main-only/F5 combination are controls, no postscore winner.
F4 actually reselects:272restored/137rejected, matched pixels net+9012;
do not substitute the earlier static164old-component veto cost for real results.

F76657 native12m points verified in original BAG, decoding and reprojection exact;
F6 selects91 raw1.1425m points. Sensor range/hardware cause UNKNOWN.
F704 primary refuses ambiguous side branch. F1821 mixes two depth modes in one
connected component, with lower MAD but shifted median; F1044 selects other fish;
F1385wrong-fish selection still proxy-compatible; F1319raw reference shares anomaly.
Low-depth strips not fully covered by RGB source contours need physical spatial
audit; byte/code reprojection equality does not prove calibrated surface alignment.
Raw-silhouette consensus and occupancy are not physical distance/surface GT.

18unit checks + bounded read-only scorer acceptance + exact every-object DS3
reproduction pass. A launcher review-field mismatch was fixed before FREEZE;
attempt log retained. All outputs sealed before new manual reference reads.
Postscore caption rerenders only fix clipped text; original figures preserved.
Eight latest QA figures actually opened. All pixels private. Old DS1/2/3 untouched.
HTTP/smoke/training/SAM3/completion/cost0, no tracker/DepthState/q/trigger changes,
no new IDF1/HOTA/AssA. Main/ref delivery follows actual REMOTE_VERIFICATION.

One next step: independently audit fish/background/anomalous surfaces and spatial
registration on sealed new-conflict/low-retention cases before background-fit or
DepthState decisions. Do not retune DS4 or automatically add VLM/tracking.

# Historical handoff — DS3 foreground depth measurement,2026-09-30

Read experiments/ds3_depth_foreground_filter/RESULTS.md, PLAN/CONFIG/SOURCE_CONTRACT,
CHECKS/FREEZE/SOURCE_INVENTORY/OLD_READONLY_LOCK, MEASUREMENTS_SEALED/SCORING_SEALED,
SUMMARY/OCCUPANCY_AUDIT, FAILURE_CASE_AUDIT, restricted/visualization/public inventories,
execution/timing/logs and actual remote proof. Base:b43a4ca62229e878b62ed81ea6c7327128636564.
Measurement development on reused, exposed DS2 frames701–1060/1201–1906; not new validation.

Engineering/input PASS; fixed silhouette proxy FAIL; physical depth and tracking
increment UNKNOWN.28,382 masks:18,862 AVAILABLE/9,520 UNKNOWN;28,088 scorable/294
unscorable.18,441 paired objects:99.6213% core→98.9165% F2 (−0.7049pp), retention
50.5329%, core-usable coverage72.9140%. Core proxy ceiling makes the frozen10pp
target unattainable; FAIL unchanged. This does not prove background inside a
fish silhouette absent. F704 picks20 wrong-side pixels; F766 selects57 raw pixels
at12254.619mm versus1141.787mm core, despite96.49% silhouette purity.

All original masks and whole/core exact;10 tests pass; extraction blocks network,
manual references and non-depth_mm keys; sealing precedes human labels. The
new stateless filter retains uncertainty/pixel provenance. DS1/DS2, tracking,
triggers/q/references/candidates/weights/publication unchanged. Three QA images
actually viewed; pixels private. API/smoke/training/SAM3/completion/cost0.
No new tracking score. Reporting/failure/inventory scripts are postscore only.

One next step: independent foreground/background/anomalous-depth per-pixel audit
on these sealed selections before deciding on DepthState integration.
Do not retune this frozen run or automatically add VLM.

# Historical handoff — DS2 frozen temporal depth validation, 2026-09-30

Read `experiments/ds2_depth_transfer_validation/RESULTS.md`, `README.md`, `SOURCE_CONTRACT.md`, `EXECUTION_LOG.md`, `VALIDATION_COHORT.json`, `EFFECTIVE_SETTINGS.json`, `REGRESSION_405.json`, `CAUSAL_CHECKS.json`, `run/ALL_PREDICTIONS_SEALED.json`, `METRICS.json`, `EVENT_AUDIT.json`, `COMPLETE_AUDIT.json`, `DEPTH_DIAGNOSTICS.json`, `FORECAST_DIAGNOSTICS_VERSIONED.json`, `SCORER_METADATA_REPAIR.json`, `LEGACY_DEPTH_STATUS_CORRECTION.json`, restricted/visualization/public inventories and `run/REMOTE_VERIFICATION.json`. Actual review/fetched main was `fb1234bf7210a9a5e97f6d1b01d8b2cc7bd395f4`. The earliest remaining complete original SOURCE_OLD work ranges701–1060/1201–1906 were fixed by metadata/existence/producer support, before features/GT. Same recording, previously exposed native baseline, upstream lookahead UNKNOWN; no sealed test or repaired depth. This is temporal nonoverlap rather than independent dataset validation.

All1066 frames and five branches completed; both prediction seals preceded reference score. Fresh old405 state replay reproduces native/D0/D1/D2 exactly;12 tests and real blocked-network/key/GT/future prefixes pass.48 first publications and824 group checks pass, no masks deleted. Postscore inherited provenance/audit paths were repaired in separate private function contexts; frozen code/predictions and first metrics preserved, exact metric recomputation verified. All110 old DS1 tracked files remain byte-equal to review base.

**FAIL / STOP this frozen version.** NATIVE/D0/D1/D2/D3 pooled IDF1 **78.3627/77.0992/76.4411/77.0992/77.0992**, HOTA77.6802/76.6065/76.0237/76.6065/76.6065, AssA67.1279/65.2912/64.3032/65.2912/65.2912, IDSW76/78/80/78/78, FP/FN263/641. D2−native−1.2635/−1.0737/−1.8367/+2switches; D2−D0/D3zero; D2−D1+0.6580/+0.5828/+0.9880/−2. D2 has6 correct,3 wrong accepted pair restores,3 unsubmitted local fallbacks,1 no-split and3 cancelled events. F1280 depth changes selection but residual blocks submission; F1390 avoids a static-depth wrong swap already avoided by geometry. No mean-extrapolation choice/publication effect.52 later raw residuals belong to6 event/roles;23 WLS points in3 event/roles are worse than last value, not depth GT/calibrated accuracy. Three raw-depth/valid/core images actually opened; all pixels local. Model HTTP, smoke, training, SAM3/completion and spend0.

One next step only: separately validate candidate-independent local-background/foreground-depth/connectivity measurement filtering with explicit UNKNOWN and pixel provenance; do not retune this sealed DS2 or automatically introduce VLM. Main delivery/ref proof identifies actual commits rather than a self-referential guessed SHA.

# Historical handoff — DS1 raw-depth-only trial, 2026-09-30

Read `experiments/ds1_depth_only/RESULTS.md`, `README.md`, `SOURCE_CONTRACT.md`, `TEST_REPORT.md`, `EXECUTION_LOG.md`, `run/METRICS.json`, `VERIFICATION.json`, `EVENT_AUDIT.json`, `CHANGE_PERSISTENCE.json`, `FORECAST_DIAGNOSTICS_VERSIONED.json`, `RESOURCE_DIAGNOSTICS.json`, `RESTRICTED_INVENTORY.json`, `ARTIFACT_MANIFEST.json` and the actual pushed-ref/file proof `run/REMOTE_VERIFICATION.json`. Actual starting/fetched main was `2fe9e0c8eb497432ae5e4c676f09b8d67bff9474`; delivery commit is identified by that remote proof rather than inventing a self-referential final SHA in this text. SOURCE_OLD original0–199/351–555, raw depth_mm only, NE-1 native-first and S0-P first-split state/publication/local transactions remain fixed. No PX/age ONEFIX, new SAM3 inference, training, repaired depth or model stage. Three new numerical branches and same-source SAM3 completed405 frames with seals before GT. D1 exactly reproduces old EVENT_NUM; native exactly reproduces same-source input. Engineering checks pass,384 group checks find0 individual writes and all masks remain.

Pooled NATIVE/D0/D1/D2 IDF1 **87.8376/86.9190/86.9190/88.6276**, HOTA **85.1875/84.2534/84.2534/85.5692**, AssA **81.6094/79.8502/79.8502/82.3297**, IDSW **32/36/36/32**, FP/FN224/344. D2 has two real H2 commits before first publication, original F419/F519, both physically correct against its actual references and preserving native correspondence. D2 minus D0/D1 is+1.7086 IDF1/+1.3158 HOTA/+2.4794 AssA and−4 switches; minus native is+0.7900/+0.3817/+0.7203 with unchanged switches. Four legal restores correct, two local fallbacks not staged/unscorable; no-split/out-of-scope cases remain separate. **PASS only for the measured depth-module combination on this exposed set.** Both changed events use one-point last-value forecasts with UNKNOWN slope; among seven strictly same-q-version later-observation residuals, three WLS forecasts are worse than last value. This does not prove slope efficacy, physical depth calibration, safety on new data or real-time deployment. New model HTTP, smoke and cost **0**. Numeric SVGs are public; actual opened raw-depth/mask QA and private source/GT files remain local with byte/SHA inventory. Frozen trial complete; one next step is unchanged purely numerical DS1 validation on another independent segment set, without automatic VLM introduction.

# Historical handoff — NE-1 native-first event association, 2026-09-29

Read `experiments/ne1_native_first_event_association/FINAL_REVIEW.md` and its original seals/call ledgers. Its same-source405-frame EVENT_NUM IDF1/HOTA/AssA86.9190/84.2534/79.8502, IDSW36 is DS1's exact D1 control. Old EVENT_VLM was87.0568/84.5581/80.3964, IDSW32: finite increment over EVENT_NUM but still below same-source native. Four actual S0 H2 responses were correct at415/419, wrong at470, and unable to form a same-reference physical pairing at519 after that branch's earlier divergence. Those original responses/results remain unchanged and are not inputs or scores of DS1. Native-first changed the architecture, with no continuing PX expansion; it did not establish a globally repaired Z4Q or generic VLM efficacy.

# Historical handoff — PX-A frozen anchor retention, 2026-09-29

Read `experiments/z4q_anchor_evidence_retention/FINAL_REVIEW.md`, `README.md`, `EXECUTION_LOG.md`, `public/FREEZE.json`, `public/SOURCE_AUDIT.json`, `public/METRICS.json`, `public/EDGE_AUDIT.json`, `public/ACCEPTANCE.json` and `public/RESTRICTED_INVENTORY.json`. Fixed base `85f71d854f8d9b0bcc6d7bf1d200d1a01dd8de08`. The actual PX module now retains a genuinely registered, exact bank anchor when its current target observation becomes unqualified, while source continuity, generation, five-frame separated-mask witness, 12-second TTL and both one-edge matrix hooks remain frozen. Thirteen focused tests including actual controller and F159/F468 paths passed; real F159 had no legitimate veto. Both saved-SAM3 sources × two original-depth segments completed 810 state-processed frames with four prediction seals before independent score. Old PX had 573 target-unknown checks; 561 become exact registered lookups, but all 1688 checked candidate edges lack the corresponding qualified pair witness. **Engineering and scoring PASS; true veto 0, publication change 0, metrics exactly archived PX; NO_EFFECT / STOP this frozen rule.** SOURCE_OLD PX-A minus native pooled IDF1/HOTA/AssA −0.3950/−0.6641/−1.2466, IDSW +4; SOURCE_BASELINE +0.2489/−0.1874/−0.3131, IDSW +7. Sources share 405 original frames, so they are controls rather than independent datasets. The historical v3 run remains an annotation/future-frame diagnostic and is not input to PX-A; old VLM responses are not reused and there is no new VLM score. New model HTTP, cost, SAM3 inference and training are all zero. Private pixels, raw RLE, GT raster and credentials remain local. The one next step is a preregistered qualified-witness coverage test on an independent continuous SAM3 source before any new exclusion trial.

# Historical handoff — OLD + restored v3 depth diagnostic, 2026-09-29

Read `experiments/z4q_old_restored_depth_v3/FINAL_REVIEW.md`, `README.md`, `EXECUTION_LOG.md`, `public/FREEZE.json`, `public/METRICS.json`, `public/DELTA_AUDIT.json`, `public/F374_DEPTH_SOURCE.json`, `public/PROVENANCE4_SENSITIVITY.json`, and `public/ACCEPTANCE.json`. The user selected the final v3 repaired depth as an **annotation-assisted diagnostic**, not a blind causal tracking input. The two original OLD saved-SAM3 segments (0–199 and 351–555) were independently replayed with only per-mask depth statistics replaced. Both 405-frame branches sealed before GT scoring. NATIVE remains IDF1/HOTA/AssA 87.8376/85.1875/81.6094, IDSW32; old raw-depth Z4Q was 87.4426/84.5234/80.3627, IDSW36; v3-depth frozen Z4Q and PX both became 87.4610/84.5544/80.3979, IDSW35. Thus the tiny score gain is a **shared depth-input change**, with 0 PX veto and 0 PX increment, and Z4Q remains below same-source native in IDF1/HOTA/AssA with +3 switches. F194/F374 reconnects disappear, both physically UNKNOWN; F159/F190/F468/F522 wrong reattachments remain. F374's model-filled and measured depth conflict materially. Five annotation-fill pixels inside prediction masks changed input summaries, but a fixed 405-frame full-state ablation produced identical publications; the v2 precursor still used future frames. No new model HTTP, SAM3 inference, training, private pixels, or old seal edits. One unscored first-attempt seal failure is preserved separately. This exposed diagnostic does not authorize a claim of causal depth or correct physical recovery.

# Historical handoff — Z4Q-PX pairwise reconnect repair, 2026-09-29

Start with `experiments/z4q_pairwise_reconnect_repair/FINAL_REVIEW.md`, `README.md`, `EXECUTION_LOG.md`, `public/FREEZE.json`, `public/SLICE_F159.json`, `public/METRICS.json`, `public/EDGE_AUDIT.json`, `public/ACCEPTANCE.json`, and `public/RESTRICTED_INVENTORY.json`. Fixed review base `3e4101b54e99dbf7cb246cdb673cc6e2becdfe35`. An isolated StableReturn copy now checks explicitly versioned, qualified past co-visibility for each candidate edge before Hungarian assignment in both D1 delayed and BirthRefine birth paths. The attached candidate component/tests were not supplied; seven local focused checks passed. Real F159 yielded no legitimate exclusion evidence. Two saved-SAM3 sources × two segments × 405 frames each completed fresh state replay and postseal TrackEval scoring, with 0 model HTTP, 0 SAM3 inference and 0 training. There were 1688 candidate-edge checks, **0 real vetoes**, and all 810 processed frame predictions exactly equal archived frozen Z4Q. On SOURCE_OLD, pairwise minus same-source NATIVE IDF1/HOTA/AssA = −0.3950/−0.6641/−1.2466 points, IDSW +4; on SOURCE_BASELINE = +0.2489/−0.1874/−0.3131, IDSW +7. Thus **engineering/source/score PASS, research NO_EFFECT; frozen Z4Q-PX does not repair the FEEDING regression**. OLD F468 is `BIRTH_REFINE`, `phase=birth`, not D1; F372/F506/F409 correct physical reconnections remain, F194 follows original B0 rather than age ONEFIX's alternate target. Old B0-R and ONEFIX seals, responses and scores remain unchanged. Private pixel/RLE inputs and edited reference stay local and are inventoried, not published. The one next step is a preregistered new continuous-source test with explicitly traceable source/target versions and same-source NATIVE/physical evaluation; no threshold rolling on these exposed 405 frames.

# Historical handoff — B0-R same-source SAM3→Z4Q regression repair, 2026-09-29

Start with `experiments/b0_same_source_regression_repair/FINAL_REVIEW.md`, `REPAIR_DIFF.md`, `README.md`, `EXECUTION_LOG.md`, `public/ONEFIX_METRICS.json`, `public/POSTSEAL_CAUSE_REVIEW.json`, `public/TEST_REPORT.json`, and `public/RESTRICTED_INVENTORY.json`. Fixed fetched base `bfa141da4ffcb11aa47773b601379d0da88384c4`. This is the **FEEDING405 saved-SAM3 prediction replay**, separate from the S0-P 8400-frame identity-publication engineering work below. `SOURCE_OLD` uses `AnnotationFeeding_20260924/ML/labels_raw` for both original frame ranges 0–199 and 351–555. `SOURCE_BASELINE` uses that same first segment and the original `2.baseline` protocol's `ML/segments_v2/resegmented_000351_001906/labels_raw` for the second; all 205 second-segment raw JSON files differ. Comparisons are source-internal only. Two full source×segment NATIVE/B0 replays and one fixed ONEFIX replay each were sealed before independent GT scoring. Source OLD pooled NATIVE/B0/ONEFIX IDF1 **87.8376/87.4426/87.8376**, HOTA **85.1875/84.5234/85.0448**, AssA **81.6094/80.3627/81.3397**, IDSW **32/36/32**. Source BASELINE pooled NATIVE/B0/ONEFIX IDF1 **86.2344/86.4832/86.6584**, HOTA **87.6345/87.4471/87.9328**, AssA **81.2212/80.9081/81.7749**, IDSW **38/45/39**. F159 D1 aliases a 135-frame continuous native 26 to old GT16 while its current mask is GT26; a one-action VETO delays the error by only one frame. ONEFIX protects mature certified native IDs after two confirmation windows; it is a `NEW_HYPOTHESIS`, not a bugfix, and also blocks physically correct baseline-source F372/F506 reconnects. **Engineering/score PASS, method full-regression objective FAIL**; OLD HOTA/AssA remain below native and BASELINE IDSW remains one above native. The archived F419/F519 VLM H2 choices preserve native mappings and are not reused as new answers. New model HTTP, cost, SAM3 inference, training: zero. Saved 20-frame SAM3 batches do not establish zero-lookahead raw-RGB production. All private pixels, GT raster, provider IDs and credentials stay off Git. The one next step is a preregistered independent continuous-SAM3 input check of mature-native protection versus legitimate reconnects with same-source native and physical/public outcomes separately reported.

# Historical handoff — S0-P identity publication and local rollback, 2026-09-29

Start with `experiments/s0p_identity_publication/FINAL_REVIEW.md`, `README.md`, `EXECUTION_LOG.md`, `TEST_REPORT.json`, and `run_8400_v2/public/` freeze, predictions seal, publication ledger, metrics, switch audit, physical reference audit, outside-state audit, acceptance and restricted inventory. Fixed review base `9eca43e8ee35bbbc2949bcefb5ddbc653361d666`. The 8400-frame exposed development B0/OLD-HOLD/HOLD-P IDF1 is 99.333472/99.317579/99.474526; HOTA 77.829488/77.848487/77.953763; AssA 77.907638/77.947244/78.157296; IDSW **6/18/2**, FP/FN all 194/323. The 16 old negative temporary-ID switches disappeared, and the four B0 switches suppressed by protection remained suppressed. Two remaining switches at F5933/F5939 are shared with B0. The F2145 cancelled event now first-publishes ID4 continuously. Active-frame outside state is exact in 299/299 comparisons. Nine q events: seven numerical resolutions and two `LOCAL_FALLBACK_UNRESOLVED`; the latter are not counted as physical successes. Seven direct-anchor verdicts are correct and two unscorable; clean-fragment consensus yields four correct and five unscorable. **Common mechanism engineering benefit on exposed development; new VLM increment NOT TESTED.** The first full attempt had IDSW8 due unresolved q publishing a provisional H1 for one frame; its seal, score and hash-matched source are retained in `run_8400/` and `attempt1_source/`. Final code corrects this general publication contract, then independently reruns and scores; neither branch uses GT to choose actions. New model HTTP and spend: 0. The original paid V7 has 16 START/15 END and F5927-S0 UNKNOWN, while the old complete recovery replay has 0 new HTTP; neither old artifact was changed or called again. No new B-VLM result exists. Private pixels, wire, provider IDs, GT raster and credentials remain off Git; actual restricted paths/bytes/SHA are inventoried. The one next step is a fresh preregistered event-set check of this shared mechanism with physical and public-label outcomes separated before any new VLM test.

# Historical handoff — MS1-R observation/state repair, 2026-09-28

Start with `experiments/ms1r_observation_state_repair/FINAL_REVIEW.md`, `README.md`, `EXECUTION_LOG.md`, `TEST_REPORT.json`, and `run_ms1r_20260928/public/` freeze, requests, responses, ledger, seal, TrackEval metrics, physical audit, old/new diff, contact sheet, acceptance and restricted inventories. Fixed base `a5c640d17500c58400b57ef11279a10a6387832b`. The trigger scan remained byte-identical, finding one F2586 event. Group and unassigned post observations no longer enter individual clean history; bank/native key domains and ten-point OLS/quality summaries were repaired. Three independent full 2,888-frame state replays and independent postseal score completed. Two new `deepseek-flash` calls returned, with peak usage upper USD 0.0505614. B0 IDF1/HOTA/AssA 80.697587/69.243869/60.074321; B-HOLD-R and B-VLM-R both 82.070744/69.410059/60.364198; IDSW 9→11. B-VLM-R equals B-HOLD-R frame by frame, so model increment is zero. S and numeric H1 are physically wrong by the fixed clean-fragment consensus; A's literal last anchor remains unscorable. The public score gain is accidental label correction. One S citation is not an input fact. **State engineering complete; exposed numeric gain; physical identity mechanism FAIL; STOP the frozen version.** No further inference, reuse, GT-guided tuning, hidden test GT, training, DAA or E2. Old MS1/B2/EHR seals unchanged. Publish no private RGB/GT/API material. Public delivery belongs on non-force `main`, with actual remote SHA/file verification.

# Historical handoff — MS1 automatic merge–split identity memory, 2026-09-28

Start with `experiments/merge_split_identity_memory/FINAL_REVIEW.md`, `README.md`, `EXECUTION_LOG.md`, `TEST_REPORT.json`, and the `run_ms1_20260928/public/` freeze, requests, responses, ledger, seal, TrackEval metrics, physical audit, mechanism audit, contact sheet, acceptance and restricted inventories. Fixed base `cb98902b61ec46a0f15ca17ff0d4d991f957352c`. One strict prediction-mask 2→1→2 episode was automatically selected; its two old references were protected at F2586, M was called at F2587 and S at F2604. Exactly two new official `deepseek-flash` calls returned, with no smoke/retry/unknown and peak usage-based upper USD 0.0284214. Three independent 2,888-frame state replays finished and official postseal TrackEval scored B0 IDF1/HOTA/AssA 80.697587/69.243869/60.074321 versus both B-HOLD and B-VLM 82.070744/69.410059/60.364198; IDSW 9→11. B-VLM equals B-HOLD in every frame, so model increment is zero. S and numeric H1 are physically wrong by the fixed continuous clean-segment consensus; A's literal last reference lacks GT match and remains separately unscorable. The score gain is an accidental correction of already inverted public labels. The latest-ten-point motion estimate is a secant, not a full regression fit, and the conservative graph found only one episode. **Engineering replay and score complete; physical identity mechanism FAIL; STOP this frozen MS1 version.** The batch is exhausted. Do not rerun paid calls, reuse responses, tune on this result, read hidden test GT, train, restart DAA or enter E2. Old B0/B1/B2/EHR seals remain unchanged. Public delivery belongs on non-force `main`; private pixels, file IDs, wire, key and GT raster remain off Git.

# Historical handoff — B2 event-evidence representation replay, 2026-09-28

Start with `experiments/event_evidence_replay/FINAL_REVIEW.md`, `public/SUMMARY.json`, `public/METRICS.json`, `public/PHYSICAL_REFERENCE_AUDIT.json`, `public/MECHANISM_AUDIT.json`, `public/PREDICTIONS_SEALED.json`, `public/FREEZE.json`, `public/ACCEPTANCE.json` and the two restricted inventories. The separately authorized four-call `deepseek-flash` batch is complete: 4/4 returned, no smoke/retry/unknown, peak usage-based upper USD 0.2326314. The full exposed-validation B2 replay changed only F2638–F2888 outputs (251 frames), with unchanged masks: B0→B2 IDF1 80.6976→81.6304, HOTA 69.2439→69.3346, AssA 60.0743→60.2323, IDSW 9→11. B03 H1 KEEP was physically correct, B01 H2 KEEP was a missed association, B05 DEFER made no edit, and B04 H1 was a real commit but physically wrong against the frozen A/B references. Its output-label swap accidentally corrected 495 matched object-frames because those public IDs were already reversed at the B04 anchors. **Engineering complete; real exposed numeric gain; historical-identity mechanism FAIL/STOP.** No further calls or prompt rolling on these four cases are authorized. The one next step is to separate physical-reference correctness from public-ID correction in a preregistered, new-event evaluation before seeking fresh authorization. Old direct history replay and its post hoc audit remain sealed and read-only.

# Historical handoff — post hoc cause review of direct 2888-frame replay, 2026-09-27

Start with `experiments/direct_history_replay/posthoc/POSTHOC_CAUSE_REVIEW.md`, `COUNTERFACTUAL_METRICS.json`, `CLAIM_AND_MAPPING_AUDIT.json`, `MATCHED_ID_COUNTS.json`, `B03_ONLY_SEAL.json`, `EXECUTION_LOG.md` and `POSTHOC_MANIFEST.json`. This read-only audit added **zero** DeepSeek calls. The B03-only true Bridge replay exactly matches the original B1 through frame 2637 and retains identical masks throughout; the original scorer was rerun only after its prediction seal, reproducing old B0/B1 exactly. B03 alone changes full IDF1/HOTA by −1.7845/−2.7368; adding B04 in that state changes them by another −1.2457/−0.1501. Event-level local physical mapping checks find B03 and B04 wrong commits, B01 wrong KEEP, B05 correct KEEP; only commits cause new state effects. The full-run loss is cross-window identity continuity, which isolated window scores conceal under pure public-ID permutations. The frozen intervention remains stopped. No new API, hidden test GT, training, DAA, E2 or prompt retuning follows. Old direct replay seals and prior batches remain untouched; public posthoc code/results/report belong on main, while original private pixels, wire, keys and GT raster stay off Git.

# Historical handoff — direct 2888-frame history replay, 2026-09-27

Read `experiments/direct_history_replay/FINAL_REVIEW.md`, `EXECUTION_LOG.md`, `TEST_REPORT.json`, `public/ACCEPTANCE.json`, `public/EVENTS.json`, `public/SUMMARY.json`, `public/PREDICTIONS_SEALED.json`, `public/METRICS.json`, `public/SCORE_PROVENANCE.json`, and `public/RESTRICTED_INVENTORY.json`. Fixed review base `ce4a7514e97784952e447cca7914d313239133d8`. The user explicitly allowed this new state replay with four official `deepseek-flash` calls under USD 4; those four calls are complete, peak no-cache upper USD 0.2273733. Four fixed exposed validation events B03/B01/B05/B04 were called once each and the full 2,888 frames scored. Two B1 Bridge commits (B03 and B04) were both wrong postseal. B1 IDF1 77.6674 versus B0 80.6976 (−3.0302); HOTA 66.3570 versus 69.2439 (−2.8868); AssA −4.9220, IDSW +3, FP/FN unchanged. **ENGINEERING COMPLETE; NEGATIVE EXPOSED DEVELOPMENT RESULT; STOP this frozen intervention.** This neither validates automatic event triggering nor disproves event history/depth in general. B0/B1 predictors, requests, decisions, original official scorer results and private artifact inventory are preserved. No old EHR-CF response was used as a research answer; S02 was only a local extra-field parser regression. Model output extra version/type does not block a unique H1/H2/DEFER in this new run. The old EHR-CF and earlier STOPs remain historical. No unused allowance or key authorizes new paid work, training, hidden test GT, DAA or E2. Public artifacts require non-force main delivery and remote verification; private RGB, provider IDs, raw wire, key and GT raster stay off Git.

# Historical handoff — EHR-CF, 2026-09-27

Read `experiments/ehr_contract_first_trial/FINAL_REVIEW.md`, `PROTOCOL.md`, `API_PROTOCOL_SMOKE.md`, `SOURCE_TO_BODY_AUDIT.md`, `run/public/REQUESTS_SEALED.json`, `run/public/API_PROTOCOL_SMOKE.json`, `run/public/CALL_LEDGER.jsonl`, `run/public/PARTIAL_RESPONSES_SEALED.json`, `run/public/ATTEMPT_RESULTS.json` and `run/public/RESTRICTED_INVENTORY.json`. Fixed review base `f68552be88c20cc500be8281f6f1ec04db34b4ee`. The new explicit E whitelist removed all ten old stale anchors, complete source/body and self-consistent semantic checks passed, and 27 actual bodies were sealed before inference. The first synthetic protocol smoke returned a valid H1, but the second returned raw DEFER with extra schema metadata keys at the top level, violating the frozen contract. **INTERFACE_QUALIFICATION_FAILURE / STOP this frozen batch**: two technical inference calls returned, zero formal calls, 25 formal UNSENT, zero unknown HTTP; USD 0.016233 peak no-cache upper account. No complete event-history or depth method result exists. The old EHR-1R-C results and scores remain untouched. No old response reuse, formal continuation, third smoke, prompt revision in this batch, tracker edit, training, DAA, E2, hidden test GT or new HOTA/IDF1. Private pixels, provider file IDs, wire/reasoning and credentials stay off Git. Any new paid work needs a separately frozen authorization after fixing the interface and requalifying it.

# Historical handoff — EHR-1R-C, 2026-09-27

Read `experiments/ehr1r_complete_trial/FINAL_REVIEW.md`, `EXECUTION_LOG.md`, `PROTOCOL.md`, `public/POSTSTOP_SOURCE_FAILURE_AUDIT.json`, `public/ATTEMPT_RESULTS.json`, `public/EVENT_RESULTS.json`, `public/CALL_LEDGER.jsonl`, `public/PARTIAL_RESPONSES_SEALED.json` and `public/RESTRICTED_INVENTORY.json`. The fixed review base is `e95f1a776c62028a7f0d6d5e8a48d26b7c7f4f37`. The independently checked new scorer compares full physical mappings, and a real B01 synthetic slice plus five-case source/depth audit passed. All 25 file-ID bodies were sealed before calls. A postfreeze audit then found that all five E inputs retained earlier X/Y post `anchor_frame` metadata despite endpoint-only projection. Ordinary stop yielded ten formal returns, 15 unsent, one smoke, no unknown HTTP, and a partial response seal. Peak no-cache upper USD 0.4973583; actual invoice unavailable. Nine returned assessments fail the frozen `id` list schema; the only structurally valid B01 H-D response is DEFER. **ENGINEERING_FAILURE_STOP; complete paired history/depth effect INCONCLUSIVE_NOT_TESTED; no VLM necessity or safety claim.** Do not send the 15 unsent requests, reuse responses, or infer fresh paid authority from the remaining cap. Five cases remain exposed offline controls. Old v5 and zero-call v6 remain unchanged. Private pixels, source/native bridge, provider file IDs, raw wire, credentials and GT raster remain off Git. No tracker edit, training, DAA restart, E2 or new HOTA/IDF1. Next step only with a separate authorization: remove E's stale post anchor, specify the assessment `id` schema explicitly, add both regressions, then freeze a new complete batch.

# Historical handoff — EHR-1R, 2026-09-26

Read `experiments/ehr1r_causal_history_repair/FINAL_REVIEW.md`, `EXECUTION_LOG.md`, `SOURCE_FAILURE_AUDIT.json`, `PARTIAL_RESPONSES_SEALED.json`, `EVENT_RESULTS.json`, `CASE_SCORE_BINDING.json`, `corrected_unsent/OFFLINE_REQUESTS_FROZEN.json` and `ARTIFACT_MANIFEST.json`. Fixed base `869d9812a6549307e8e4502d1ee17d6881494626`. The user authorized one new 25-formal plus at-most-one-smoke official `deepseek-flash` batch under USD 3. The source-backed checker caught old real B01/B02/B04-A packets, and v5 froze 25 new bodies, but a missed anonymous H-D depth-quality omission caused **ENGINEERING_FAILURE_STOP**. Seven formal responses and one smoke returned, one formal HTTP outcome is unknown, 17 formal requests were unsent; USD 0.4263984 upper charged/reserved. There is no full response seal or valid paired score. A corrected v6 25-request logical package passed all offline checks and has zero calls; never combine old answers with it or infer new authority from remaining budget. All five cases have only a pair-contact proxy, not a verified full online hard-event trigger; they are offline controls. No new tracker metrics, E2, training or DAA. The old EHR-1 and M3-L conclusions stay intact. Restricted pixels, provider file IDs, raw wire, credentials and GT raster remain off Git. Commit and remotely verify all public final artifacts on main even for this failure.

# Historical handoff — EHR-1, 2026-09-26

Read `experiments/ehr1_event_history_reassociation/FINAL_REVIEW.md`, `PROTOCOL.md`, `EXECUTION_LOG.md`, `LINEAGE_AUDIT_V2.json`, `SUMMARY.json`, `ATTEMPT_RESULTS.json`, both seals, and `ARTIFACT_MANIFEST.json`. The user separately authorized a fixed exposed B01–B05 complete-history probe: 25 formal official `deepseek-flash` requests, at most one image smoke, USD 3, and non-force main delivery even on failure. Fetched base `0b65e95ce41ef67978fad08fdd098532112b79b4`. All 25 request bodies were frozen, but the B01-first independent source check found PRE_HISTORY native-lineage contamination by contact-risk observations. **ENGINEERING_FAILURE_STOP; complete-history and depth value INCONCLUSIVE.** Only five B01 formal requests and one smoke were made, USD 0.1407354 peak-rate upper accounting; all five B01 raw choices were `DEFER` but are protocol-unscorable. The remaining 20 outcomes are explicitly unsent, not counted as failures or correct controls. A partial five-response seal preceded exposed-key reading; no full response seal exists. All old M3-L results remain sealed and its local no-increment conclusion does not test this full event-history hypothesis. No old budgets roll forward, no same-case prompt repair/retry, hidden test GT, training, DAA restart, tracker transaction, E2 or new IDF1/HOTA. The only next step is a separately authorized preflight-valid freeze with anchor-connected clean histories and a full same-information numeric comparator. Private pixels, provider file IDs, raw wire, credentials and GT raster remain off Git. All public code, configuration, tests, call records, missing outcomes and reports require main sync and remote verification.

# Historical handoff — M3-L, 2026-09-26

Start with `experiments/m3l_local_correspondence/FINAL_REVIEW.md`, `PROTOCOL.md`, `SCORER_CORRECTION.md`, `final_score/SUMMARY.json`, `final_score/PAIR_RESULTS.json`, `final_score/TOKEN_MATCH_RESULTS.jsonl`, `CALL_LEDGER.jsonl`, both seals and `ARTIFACT_MANIFEST.json`. Fixed base `8ec0d3b8bd2e7c75dd2d6b3d15b1b0bb6341e16b`. The separately authorized B01 G006–G018 adjacent local probe completed 24 new official DeepSeek inference calls plus one image-route smoke, USD 0.2951883 peak-rate upper accounting. Accepted local matches on 66 scoreable sources had no mistakes, but N-I mask IoU got 66/66 at full coverage; two model attempts had invalid evidence descriptions, and A/B chains stopped early. **Engineering/source PASS; narrow local signal only; `HAS_LOCAL_CAPABILITY_NO_INCREMENT` / STOP this frozen task, not a method or tracking pass.** Initial and corrected scorer records are both preserved; old M2-T/M2T-F seals and conclusions are unchanged. No key or leftover budget grants more calls. This batch's public code and outputs must be non-force integrated and verified on `origin/main`; private pixels/wire/file IDs/GT raster remain off Git. The M2T-F handoff below is historical.

# Historical handoff — M2T-F, 2026-09-26

Read `experiments/m2tf_frozen_evidence_audit/FINAL_REVIEW.md`, `PROTOCOL.md`, `EXECUTION_LOG.md`, `SOURCE_BINDING_AUDIT.json`, `REPLAY_PARITY.json`, `OBSERVATION_COVERAGE.jsonl`, `EDGE_CLAIM_BINDINGS.jsonl`, `FIRST_DIVERGENCE.jsonl`, `VISUAL_AUDIT.md` and `ARTIFACT_MANIFEST.json`. Fixed audit base `cef0f894c715f18d856d404a7dd7e6c9b4b0c5dd`. The 25 old responses and 100 edges were audited, not rerun. Request/image/role/answer binding and 25-response replay parity pass. B01 had 22 sent intermediate G images inside a repeat-described unobserved gap; its wrong G+AP outputs have posthoc identity path mismatches. **Audit PASS; source binding PASS; frozen M2-T method still FAIL/STOP; identity identifiability remains INCONCLUSIVE.** No new API, tracker edit, hidden test GT, training, M3/E2 or new IDF1/HOTA. Current user authority requires all public final records and reports to be non-force integrated, pushed and verified on `origin/main`; restricted pixels, provider IDs, wire and GT raster remain off Git. The M2-T handoff below is historical; neither key nor prior paid budget grants new calls.

# Historical handoff — M2-T, 2026-09-24

Read `experiments/m2t_motion_first/FINAL_REVIEW.md`, `RESULTS.md`, `PROTOCOL.md`, `EXECUTION_LOG.md`, `EVENT_RESULTS.jsonl`, `ATTEMPT_RESULTS.jsonl`, both request/response seals and `ARTIFACT_MANIFEST.json`. Fixed base `a27720ff313a27037eb5cbdd9d629506911af7d2`. M2-T completed 25 frozen official `deepseek-flash` image calls plus one same-route smoke, USD 1.2293283 rate-based upper accounting of its USD 3 cap. The full engineering/source-fidelity chain passed; B01 geometry-sequence first and exact repeat both abstained, B03/B04 geometry repeats made wrong associations, and B01 appearance-augmented first/repeat were wrong. **FAIL / STOP this frozen method definition.** All five cases were pre-exposed; no new tracker stage, IDF1/HOTA, E2, training or hidden test GT. The user authorization applied only to this batch: do not infer permission for additional paid calls from the key or old M1/M2-T budget. Source media and private wire stay on the lab server with exact path/size/hash inventory, while all public records must be non-force synced to `origin/main` even for failure. The M1 handoff below is historical, not active permission.

# Historical handoff — M1, 2026-09-24

The completed outcome and one next step are in `experiments/m1_real_vlm_pilot/FINAL_REVIEW.md`: engineering PASS, frozen model-evidence gate FAIL, scientific `INCONCLUSIVE_UNSTABLE / STOP`. Thirty formal choices and two smoke attempts were sealed at upper-accounted USD 1.1983182; the lone B01 first P2 rescue was not repeat-stable. Read the full review before any continuation.

Start with `experiments/m1_real_vlm_pilot/README.md`, `PROTOCOL.md`, `RESULTS.md`, `SUMMARY.json`, `EVENT_RESULTS.jsonl`, `REQUESTS_SEALED.json`, `DECISIONS_SEALED.json` and `ARTIFACT_MANIFEST.json`. Fixed review base is AO1 main commit `bdf1ba5a1406be136fb65acd085592503e35865c`. M1 is a one-batch, expressly authorized official DeepSeek `deepseek-flash` association-choice probe: 30 frozen research calls plus up to two technical smoke calls, total paid upper bound USD 5. Its five cases were already exposed; they do not constitute fresh generalization or a continuous tracker update. The sender is isolated from the answer key; all requests are frozen before research calls and outputs sealed before independent exposed-key scoring. Private media and raw API wire remain at `/home/xiongxiong/m1_real_vlm_pilot_20260924/run_v4/`, inventoried but not in Git. No E2, test GT, training, retuning on model answers or additional paid API batch is authorized by this handoff. This batch's public code, records and reports require non-force synchronization and verification on `origin/main` even for a negative outcome. The AO1 handoff below is historical and its no-API limit does not apply to the explicit M1 authorization.

# Historical AO1 handoff — 2026-09-24

Start with `experiments/ao1_input_fidelity/RESULTS.md`, `DECISION.md`, `PROTOCOL.md`, `SOURCE_MANIFEST.json`, `BLIND_STATUS.json`, `EXECUTION_LOG.md` and `ARTIFACT_MANIFEST.json`. Fixed review base is AO0 main commit `9e70e02`. AO1 preserves AO0's one real stage/commit recoverability positive, pairs its input with four fixed old E1 harms under V0/V1/V2 and does **not** produce a new identity edit, model judgment or TrackEval score. Actual original RGB/masks/times and exact old crop fields were checked; the authoritative restricted blind media are at `/home/xiongxiong/ao1_input_fidelity_20260924/range_corrected_run/blind/` and are not in Git. Status: engineering PASS; one-case recoverability EXISTENCE_ONLY; input signal INCONCLUSIVE_REVIEW_PENDING because independent first judgments are 0/15; model NOT_TESTED; formal method STOP_NOT_READY. User explicitly requires all AO1 public outputs and reports be committed and remotely verified in `origin/main` even for STOP. No API, training, E2, unexposed test GT or private-pixel publication is authorized. The AO0 handoff below is preserved as historical context, not overwritten authority.

# Historical AO0 handoff — 2026-09-24

Start with `experiments/ao0_association_observability/RESULTS.md`, `DECISION.md`, `PROTOCOL.md`, `CASE_MANIFEST.json`, `METRICS.json` and `ARTIFACT_MANIFEST.json`. AO0's fixed review base is `6d090f9`; it identifies one exposed validation GT2/GT6 swap with both relation-oracle headroom and a real stage/commit continuation. It has no new VLM/model result and no independent query-cutoff identity verification or second qualifying interaction. Status: engineering PASS for one slice; scientific EXISTENCE_ONLY / INCONCLUSIVE_INPUT / STOP_NOT_READY. The four old harmful E1 cases and all older sealed outputs remain unchanged. AO0's latest user authorization requires all public outputs and reports be committed and verified in `origin/main`; it does not grant API calls, E2 or use of private pixels/GT raster in Git. This section supersedes the older handoff as the active entry; the older text below is preserved as historical guidance under its original permissions.

# Historical VL_ASSOC_E1 handoff — 2026-09-23

Fixed base `a566dc6d606ab77696f08f5490486d6f541ebe15`; branch `codex/vl-assoc-r0-e1`. This branch contains only isolated R0 repair copies and E1 offline feasibility preparation under `experiments/vl_assoc_e1/`. Historical public archives and server side inputs/results were read-only. Execution occurred in an independent checkout on the authorized laboratory server. Private image sheets stay in that checkout's `experiments/vl_assoc_e1/images/` and are ignored by Git; do not copy original RGB, base64, credentials or raw predicted masks into the public repository.

Current engineering state: R0 `PASS`; E1 `READY_FOR_E1_API`. Scientific conclusion: `INCONCLUSIVE`, because `allow_api=false`, zero E1 model calls, no E1 decision seal and no E1 GT scoring. `RESULTS.md`, `SUMMARY.json`, `EVENT_RESULTS.json`, `REPLAY_AUDIT.json`, `TEST_REPORT_FINAL.json`, `R0_SCORE_AUDIT.json` and `FREEZE.json` are the main evidence. `COST_PLAN_FINAL.json` reserves a conservative peak $2.4617 under a proposed $5 cap; actual E1 spend is $0. The old closed-loop run's 33 saved responses were replayed without network calls and must not be represented as answers to new repaired/E1 packets.

Before any authorized continuation, recheck the host, disk, account processes, dataset/source hashes and `FREEZE.json` against server-private images. Then require explicit permission for this E1's paid calls; existing keys and historical authorization do not suffice. Do not edit the frozen packet, prompt, candidate set or conditions based on output. All main-arm requests must remain paired at the same event/cutoff and fixed order, with repeat and alias permutation diagnostic only. Seal requests, responses and decisions before any independent E1 GT process. Do not move into E2 automatically. This document and `research/NEXT_EXPERIMENT.md` describe one next step only.
