# VL_ASSOC_E1B: prospective new-event token-cap design (NO API AUTHORIZATION)

Status: **DESIGN_ONLY / allow_api=false / zero E1B calls**. This is a new research protocol after E1 stopped on output truncation, not an amendment, replay, or retroactive reclassification of the sealed E1 run. The previous `FREEZE.json`, `EARLY_STOP_SEALED.json`, decisions, GT audit and conclusions remain read-only. No E2, SAM3 rerun, trajectory edit, training, or paid call is authorized by this plan.

Parent repository state: fixed original base `a566dc6d606ab77696f08f5490486d6f541ebe15`; E1 stopped-run commit `c7f2fe73250ef92e79651daac4f2d2b5ebe438d1`. All E1B code, inputs and outputs must be in a separate directory and a newly frozen commit before any request. The user explicitly chose new, previously E1-unscored events; `max_tokens=16384`; a **90% whole-batch valid-response gate**; and cost authorization only after a future exact preflight. These choices do not authorize spending.

## 1. Falsifiable hypotheses and scope

| ID | Question | Preregistered test | Interpretation limit |
| --- | --- | --- | --- |
| H-ENG | Can the same high-thinking VLM complete the E1 association contract with a larger output cap? | At least 108/120 primary 16,384-token responses valid; all failures retained. | Engineering feasibility only, not identity gain. |
| H-CAP | Does a larger cap reduce truncation on identical *new* temporal packets? | Pair 16,384 vs 8,192 for each of 24 new events; report discordant truncation pairs and token/latency/cost differences, without best-of selection. | API stochasticity remains; randomize order and report repeat. Do not compare old vs new event rates causally. |
| H-ASSOC | Does VLM evidence change legal association choices and outperform active numeric N when opportunities exist? | Same-event B0/N/L-T/L-V-static/L-V-temporal, independently scored only after seal; require at least 8 scorable events, 2 B0-wrong/correct-alternative opportunities, temporal minus N at least 2, no new harm to B0-correct events, and nonzero real model influence. | Offline correct choices are not IDF1/HOTA or closed-loop benefit. |

The model must compare **complete legal association hypotheses**, rank them relatively and cite packet evidence; no invented probability, arbitrary identity edit, unreferenced preference or free-form override. `model_off` and a legal within-packet preference flip must alter the tested selector when appropriate. B0 and N remain genuine baselines; the project does not become a numerical-only tracker.

## 2. New events and variable control

Read only `EVENT_PROBE_V4_{development,validation}.json`, excluding **all 24** E1 packet source episode IDs (not merely the seven scored events). Keep only `status=QUERY` and exactly one clone-stage-executable nonbaseline alternative. The current, GT-blind inventory has 29 eligible unused development events and 5 validation events. Sort each split by SHA-256 of the UTF-8 string `VL_ASSOC_E1B_20260923|{episode_id}`; take the first 19 development and all 5 validation events. Do not substitute events after seeing GT or model responses. If any source, two full mappings, original RGB, predicted mask, time-valid history or needed appearance/depth data fails preflight, stop with `INPUT_BLOCKED`; do not silently replace it. The 24 planned query frames are distinct, though one video and temporally adjacent development events remain correlated.

| Split | Episode IDs in frozen hash order (query frame in parentheses) |
| --- | --- |
| Development 1–10 | `2-5:11` (7399), `2-3:7` (3534), `2-4:8` (4366), `0-1:7` (6032), `0-3:3` (4360), `0-1:6` (5004), `2-3:10` (4569), `2-4:6` (1355), `4-5:10` (4744), `0-2:4` (3807) |
| Development 11–19 | `3-4:3` (2658), `3-4:2` (2193), `2-4:7` (4165), `3-5:8` (4653), `2-3:16` (7619), `1-2:9` (4683), `1-2:11` (5514), `2-5:1` (628), `3-4:8` (4210) |
| Validation 1–5 | `2-5:1` (455), `4-5:5` (2852), `3-5:7` (2454), `3-5:8` (2723), `1-4:6` (2367) |

Each shorthand has the indicated split prefix (`development:` or `validation:`). Before freezing, machine-check the exact episode ID, global/local frame, fixed baseline mapping, one executable alternative, no overlap with E1 IDs, all evidence source times `<= query_time`, identical query/candidate/evidence cutoff across arms, and no GT field or future frame in model input. Packet aliases and their inverse maps are frozen before calls. The E1B selection rule differs from E1 only to obtain **new events** with the same two-candidate difficulty; it is a new sampling hypothesis, not an R0 repair. Development/validation imbalance (19/5) and within-video clustering must be disclosed.

| Variable | Frozen E1B value |
| --- | --- |
| VLM/API | `deepseek-flash`, Chat Completions image route, thinking enabled, `reasoning_effort=high`, JSON output; record returned model/fingerprint. |
| Primary model arms | L-T, L-V-static, L-V-temporal, temporal repeat, temporal alias permutation: all `max_tokens=16384`. |
| Cap diagnostic | One additional L-V-temporal request per event, byte-identical input and prompt except `max_tokens=8192`; never substituted for the primary temporal choice. |
| Controls | B0 native frozen association; active equal-weight D/A/M numeric N on the exact same packet; diagnostics never chosen as the best run. |
| Prompt/evidence | Retain the E1 relative-comparison response schema and source-cutoff policy; freeze exact E1B prompt, media hashes and serialized request-body hashes anew. |
| Ordering | Seeded, frozen per-event permutation of the three primary arms and three diagnostics; no response-dependent scheduling. |

Only the token cap is varied within each 16,384-vs-8,192 paired temporal diagnostic. Across E1 and E1B, event sampling and the aggregate gate also differ, so old/new score or validity rates are not a single-variable causal comparison.

## 3. Measures, gates and independent scoring

Per response, validity still requires `finish_reason=stop`, parseable JSON, exact packet/snapshot IDs, every legal candidate pair exactly once, legal relation/reason/applicability, and in-packet evidence references for directional preferences. Invalid, truncated, incomplete, unobservable, cyclic or tied outputs fall back to B0 under the same decoder rules; invalid responses are never judged as a wrong model preference. The **only** loosened legality condition is the *aggregate* primary-arm validity threshold from 95% to 90%: at least 108 of 120 primary 16,384-token calls must be valid. The 24 legacy-cap diagnostics and two smoke calls have separately reported validity and are not hidden or folded into this primary denominator. If primary invalid count exceeds 12, the stage cannot pass and new calls stop; an in-flight request is reserved and sealed as unresolved. No retries, prompt edits, cap changes or event substitutions inside the frozen batch.

Pre-API gates: two technical smoke checks (structured schema, real original RGB route); true RGB/mask/depth/appearance source hashes; automated validation of every sheet/pixel provenance; human review of all 24 static/temporal image pairs; exact worst-cost/body-size preflight; model-off, legal flip, alias permutation and atomic preview/commit state tests. A missing original image is `INPUT_BLOCKED`, never fabricated visual evidence.

After all outputs (or an early-stop prefix) are hash-sealed, a **separate process** alone may open GT. Retain every unscorable event with explicit cause and assess fragmented individuals rather than dropping their harm. Report per-event full candidate correctness for B0, N and all three primary model arms; paired differences, 16k-vs-8k validity/truncation, repeat/alias physical-choice agreement (at least 22/24 each, invalid counts against denominator), legal flip/model-off effect, evidence-citation syntactic validity and separately audited visual grounding. If fewer than eight events are scorable or fewer than two offer a correct alternative to a wrong B0, label research `INCONCLUSIVE`; do not relabel this as model failure. Primary temporal minus N must be at least two correct choices, with zero newly wrong B0-correct events, for an E1 *offline* PASS. V vs static and V vs L-T are separately reported; even a V win does not prove temporal reasoning because image count and compute differ. No E2 or IDF1/HOTA claim follows automatically.

Do not choose the best repeat, alias, cap or split; report all predeclared cells. With 24 correlated events from one video, show exact paired counts and event clusters rather than a misleading independent-sample p-value; a confidence interval may be descriptive only. Future cross-video validation is outside this batch.

## 4. Resource and authorization preflight

The provisional schedule is `24 × (5 primary 16k + 1 diagnostic 8k) + 2 smoke = 146` maximum paid requests, versus 120+2 in E1. This is **a proposed new budget envelope, not authorization**. Using a deliberately illustrative 16,000 prompt tokens/request, current peak uncached input `$0.30/M` and output `$1.20/M`, the ceiling calculation is about `$3.34`; a 1.5× planning margin is about `$5.00`. The actual media/token estimate, provider price and hard cap must be recalculated from every frozen E1B request and separately approved before changing `allow_api=false`. The public [DeepSeek model/pricing](https://api-docs.deepseek.com/quick_start/pricing/) page currently lists a 384K maximum output for Flash and these peak rates; its [thinking-mode guide](https://api-docs.deepseek.com/guides/thinking_mode/) explains that reasoning precedes final content. The observed E1 truncations used all 8,192 tokens in reasoning, so 16,384 is plausible to test, not guaranteed to pass.

Execution host remains the user's lab server. Before any future job, recheck host/user, project path, free memory/disk, processes, actual environment and API connectivity; use CPU-only inference orchestration unless a separately justified GPU task is needed. Preserve old predictions, experiment directories and private media. Record request/response hashes, returned token usage, uncached-cost upper accounting, per-call latency and unresolved attempts. Freeze inputs and budget first; **request explicit new paid authorization** second; then execute at most this one E1B batch. No external write/API call has been made for E1B.

## 5. Reproducibility and decision

Before freezing, record: repo commit, source probe and prediction hashes, exact 24 episode IDs, server interpreter/package versions, model identifier/fingerprint, prompt and schema hashes, image/source manifests, randomized arm order seed, full payload hashes, GT-blind selection checks, hard cost reservation, stop conditions and scorer version. Independent post-seal scoring must record GT source hashes and all unscorable cases. If any engineering gate fails, stop and report `ENGINEERING_FAILURE`/`STOP`; if inputs or improvement opportunities are insufficient, report research `INCONCLUSIVE`; if opportunities are sufficient but temporal adds no legal influence or fails paired thresholds, report `FAIL` for this E1B hypothesis without retuning these events.

Current decision: **DESIGN_ONLY**. The only next step is GT-blind input/payload preflight and freeze for these new events; do not send API requests until the resulting exact cost plan receives a separate explicit authorization.
