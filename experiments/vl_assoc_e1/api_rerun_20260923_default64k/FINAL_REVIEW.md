# E1 24-event default-64K exploratory rerun — final review

Date: 2026-09-23 (Asia/Shanghai). Execution host: `xiongxiong@10.2.212.110`, separate checkout `/home/xiongxiong/SAM3D-Z4Q-DeepSeek-FishMOT-vl-assoc-e1`. Fixed project base: `a566dc6d606ab77696f08f5490486d6f541ebe15`; rerun implementation commit: `6462984c45e9a25576bd0f297ad85b244401cfbd`. The earlier sealed E1 run and R0 records were not overwritten. This rerun used the original 24 frozen events from request 1, but some of those events had already been scored in the older run; **it is exploratory, not a fresh confirmatory blind test**. Inference itself read no GT. No E2 or full-sequence API loop was run.

## Disposition

- **Engineering PASS:** two technical smoke calls and 120/120 formal calls completed, all 122 provider responses ended with `stop`; 113/120 formal responses met the unchanged per-response contract (94.17%, above the new 90% batch gate). The independent scorer ran only after the 120 decisions, 122 responses, ledger and hashes were sealed. The model made five non-B0 main-arm selections; a legal preference perturbation changed the selection in 21 tests, so the model is not an explanation-only sidecar.
- **Exploratory safety FAIL:** on 19 scorable events, B0 was correct in 19, active numeric N in 18, L-T in 16, L-V-static in 16 and L-V-temporal in 15. The temporal arm damaged four B0-correct events and improved none. It was three correct choices below N, not two above. Repeat agreement was 21/24 and alias-permutation agreement 19/24, both below the frozen 90% diagnostic gate (at least 22/24). The `no_new_B0_correct_harm`, `temporal_minus_N_ge_2`, both consistency gates and `improvement_opportunities_ge_2` failed.
- **Scientific INCONCLUSIVE; E2 STOP:** there were zero scorable opportunities to improve B0, and the events are not fresh blind data. The predeclared overall exploratory gate therefore reports `INCONCLUSIVE`, despite the concrete harms above. An offline correct-choice count is **not** an IDF1/HOTA gain or a real tracking-loop result. Do not infer that E2 is authorized.

## Frozen setup and implementation delta

The inherited R0 repair used the original saved responses and sealed predictions without new old-study API calls. R0's fixed B0 was byte-equivalent across 2,888 validation rows, with the R000010 depth anchor source explicitly recovered; preview/commit epochs and atomic transaction invariants were tested. The independent post-seal scorer retained GT4/GT5 fragmented individuals in its relation denominator. See `../TEST_REPORT_FINAL.json`, `../R0_SCORE_AUDIT.json`, and `../r0_source/bridge.py` lines 68–79 and 128–140, `../r0_source/policy.py` lines 161–189, `../r0_source/runner.py` lines 24–61 and 154–192, `../r0_source/scoring.py` lines 37–113. This rerun did not change R0 or the original three-vote, five-frame or episode-budget rules.

The new E1 design remains a **research hypothesis**, not a retrospective R0 repair: compare complete legal association candidates using relative preferences and cited evidence, with B0 and active numeric N as controls. All five calls per event share a causal event, query time, candidate set and evidence cutoff. L-T is text-only; L-V-static sees the query RGB sheet; L-V-temporal sees the causal temporal sheet; repeat and alias-permuted calls diagnose stability, never select the best run. Each of 24 packets offered two complete candidates, including one executable non-B0 candidate. No arbitrary identity edit or invented probability was accepted.

The rerun-specific implementation is in `../e1_execute.py` lines 20, 62–100, 138–223 and 269–351; `../run_phase.sh` lines 7–21; `../prepare_rerun64.py` lines 25 onward; and `../e1_score.py` lines 17, 37–70 and 196–304. It uses a distinct `E1_RUN_ID`, freezes 120 exact request hashes, omits the wire `max_tokens` field, reserves the provider's documented 65,536-token thinking-mode default rather than claiming unlimited output, applies a $20 hard spending cap, requires normal finish plus the complete JSON/evidence/candidate contract, makes invalid replies fall back to B0, and stops after more than 12 invalid formal replies. The aggregate validity gate alone changed from 95% to 90%; individual response legality did not. `REQUEST_FREEZE.json` binds code and budget-plan hashes. `RUN_AUTHORIZATION.json` limits `allow_api=true` to this E1 rerun; the original frozen `CONFIG.json` and authorization remain false.

Pre-call checks passed on the server: R0's 23 semantic/atomicity and damage-coverage cases in `../TEST_REPORT_FINAL.json`, the no-API execution preflight, the synthetic independent-scorer test without real GT, and exact real-image request-hash / omitted-field / $20-budget checks. The two paid technical smoke tests then passed text schema and real-image routing. The final 120-call run, GT-after-seal scoring, 122-response checksum verification, source/manifest checks and zero exit codes passed. The provider default is documented in the [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/); price assumptions are from its [official pricing page](https://api-docs.deepseek.com/quick_start/pricing/).

## Inputs, provenance and visual-check scope

The server-side asset inventory verified real RGB, predicted masks, causal depth and existing appearance features. Development has 8,399 RGB frames of 8,400 (the first is unpaired), 50,271 observations, 48,896 available 256-D FPN features and 50,268 available 48-bin RGB histogram features. Validation has 2,888/2,888 RGB frames, 17,197 observations, 16,872 FPN features and 17,179 histograms. Source hashes are in `../ASSET_INVENTORY.json`. Ten sample frame RGB hashes and mask alignment/area were checked by code (six development, four validation); two case sheets, query frames 377 and 2638, were visually examined in `../CASE_REVIEW.md`. This is **not** a claim of human visual review of all frames or all 48 sheets. The 48 frozen real-RGB sheets were hashed on the actual execution host and used in 96 image-bearing formal requests; 24 L-T requests were text-only. No synthetic image was substituted. `../FREEZE.json` binds 235 input files; the technical image-route smoke passed. Image bytes, raw wire requests/responses and the transient key mechanism remain in server-private storage, not in the public Git repository.

## Sealing, validity, cost and latency

`DECISIONS_SEALED.json` records `E1_GT_read=false`, 120 decisions, two smoke calls, 122 public response hashes, freeze hash `549ecbba6bd675247f89cd54282dd26bb610a1ffaee0517165525bc6c2c86579`, ledger hash `12f0b01e49c0fb4106d0276ca84db1abb28dfc22af20f95571180c42d50ce224`, decision hash `21e2d51414462fb5b6e05acdc5a68260fc5b772edf3f5a6260c09e8e673b3782`, and authorization hash `fa4440df7b714cee522a252918a6ae442b4f13ebf322bea7704951a86c1415f6`. Server exit code was zero and no E1 screen/job remained. After sealing, a separate CPU scorer read the GT and emitted `SUMMARY.json`, `EVENT_RESULTS.json`, and `UNSCORABLE.json`. All 122 copied public responses and four seal-bound local files were independently hash-checked.

Seven invalid replies: five `INVALID_EVIDENCE_REFERENCE`, two `INVALID_REASON`; all seven still had provider `finish_reason=stop`. Four invalid replies clustered on event `P505e5ce82c20bdd0`, including a near-miss evidence ID with one wrong character. The exact input ID is required; it was not silently repaired. The original 8,192-token truncation failure did not recur in this batch. All provider replies identified `deepseek-flash`.

The frozen peak-price reservation for 122 calls was $10.8568242, under the authorized $20 hard cap. Sum of reported-token charges at the conservative peak-rate formula was **$1.4613543**; this is an estimate, not an invoice or proof of account billing. Across all 122 calls: 944,921 prompt and 981,565 completion tokens, including 961,760 reasoning tokens. Formal-call median/mean/max latency was 36.07/37.66/91.13 seconds; formal-call latency sum was 4,519.21 seconds. Run wall clock was about 19:41:45–20:58:42 Shanghai time, including smoke, gaps and sealing.

## Paired event results

Columns `B/N/T/S/V` mean B0, active numeric N, L-T, L-V-static, L-V-temporal. `R/P` are temporal repeat and alias-permuted selections mapped back to original candidate IDs. `correct` is a five-digit B/N/T/S/V correctness vector (`1` correct, `0` wrong); `-----` means retained but unscorable. `valid` is T/S/V/R/P response legality. All packets have two complete candidates, one executable non-B0 candidate, and preserved mappings for uninvolved identities.

| Packet | Split/frame | B/N/T/S/V | R/P | correct | valid |
| --- | --- | --- | --- | --- | --- |
| P06bd8bc948a32f66 | D 192 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P0b875d6f45a74deb | D 6685 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P1cb7cbe50698e6d0 | D 8069 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P268a2bf76437ad61 | D 398 | C1/C1/C1/C1/C1 | C1/C1 | 11111 | 11111 |
| P296608a3986eefc0 | D 4755 | C1/C1/C1/C1/C1 | C1/C1 | 11111 | 11111 |
| P2ae9988375c21d4b | D 5314 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P4218132a1659f1e2 | D 8069 | C2/C2/C1/C1/C1 | C1/C1 | 11000 | 11111 |
| P4f984757cb073766 | D 7102 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P505e5ce82c20bdd0 | D 2663 | C1/C1/C1/C1/C1 | C1/C1 | 11111 | 00001 |
| P6093da8587bc16c7 | D 287 | C2/C2/C2/C2/C2 | C2/C2 | ----- | 11111 |
| P6dd51c7c657f38ac | D 5179 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P7191b96390a1ca1c | D 4574 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P017ea2eb5b2a8a48 | V 2677 | C1/C1/C2/C2/C2 | C2/C2 | ----- | 11111 |
| P04c303d9612421d6 | V 377 | C2/C2/C2/C2/C1 | C2/C2 | 11110 | 11111 |
| P0bb5b6c537eb526b | V 1375 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P175d295a01799fe5 | V 2638 | C2/C1/C1/C1/C1 | C1/C2 | 10000 | 11110 |
| P1797ad89bd359331 | V 2580 | C1/C1/C2/C2/C2 | C2/C2 | 11000 | 11111 |
| P188c6571ae22ff20 | V 2841 | C1/C1/C1/C1/C1 | C1/C1 | ----- | 11111 |
| P396d217afb3e0fac | V 2718 | C1/C1/C1/C1/C1 | C1/C1 | ----- | 10111 |
| P538a7a4638462254 | V 2846 | C1/C1/C1/C1/C1 | C1/C1 | ----- | 11111 |
| P56d853b682c8b43d | V 1832 | C2/C2/C2/C2/C2 | C2/C1 | 11111 | 11111 |
| P7517e6637bc947e6 | V 2461 | C1/C1/C1/C1/C1 | C1/C1 | 11111 | 11111 |
| P8111d40d0ad38d57 | V 427 | C2/C2/C2/C2/C2 | C2/C2 | 11111 | 11111 |
| P81c6f08460d3827c | V 2379 | C1/C1/C1/C1/C1 | C1/C1 | 11111 | 11011 |

Five events remain unscorable rather than being dropped: `P6093da8587bc16c7` lacks both historical GT identity links; `P017ea2eb5b2a8a48`, `P188c6571ae22ff20`, `P396d217afb3e0fac`, and `P538a7a4638462254` lack historical B linkage. This is an explicit fragmentation/coverage limitation, not evidence of no harm. Four temporal harms among scorable events are `P4218132a1659f1e2`, `P04c303d9612421d6`, `P175d295a01799fe5`, and `P1797ad89bd359331`. Event `P04c303d9612421d6` changed only in the first temporal call, not its repeat or alias permutation; it is not stable evidence of temporal benefit. `P175d295a01799fe5` is the only numeric N mistake; L-T, static and temporal also chose that wrong non-B0 candidate.

## One next step

Design **one genuinely new, unscored event set with verified B0-error opportunities and complete historical identity coverage**, freeze it before any GT reading, and request a separate authorization before any new paid call. Do not reuse these 24 events as confirmatory evidence or advance to E2 on this result.
