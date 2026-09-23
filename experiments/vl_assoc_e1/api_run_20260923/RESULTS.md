# E1 paid execution: STOP / ENGINEERING_FAILURE; research INCONCLUSIVE

Fixed base: `a566dc6d606ab77696f08f5490486d6f541ebe15`. This is the authorized continuation of the immutable `FREEZE.json` snapshot (`549ecbba6...`), on branch `codex/vl-assoc-r0-e1`. R0's historical replay, repair tests, true-input inventory and preauthorization outputs remain unchanged. The E1 API and candidate contract are new research hypotheses, not repairs to the historical three-vote, five-frame, episode-budget protocol. No E2 or trajectory edit was run.

## Stop decision and provenance

The user explicitly approved this E1 paid run. `RUN_AUTHORIZATION.json` records a $5 hard cap, at most 120 formal and two nonresearch smoke calls. The old `CONFIG.json` and `API_AUTHORIZATION.json` remain `allow_api=false`; the new authorization is a separate overlay tied to the freeze hash. Both smoke calls passed: a structured-text response and transport of a hash-checked, original RGB image. Server-only wire bodies, raw API responses and key ingress are under ignored `private_api/`; no credential or base64 image was committed.

Formal calls followed the frozen `CALL_SCHEDULE.json`, with the same causal event, query instant, legal candidates and evidence cutoff across B0, active numeric N, L-T, L-V-static and L-V-temporal. The latter two controls, repeat and alias permutation, were diagnostic only. At completed call 33, the seventh `finish_reason=length` made the 95% response-validity gate mathematically impossible: even 113 valid of 120 would be only 94.17%. The process was stopped, with 34 formal completions, one unresolved in-flight start (`F000035`), and no subsequent requests. Exit code was 143. The seven invalid responses are `F000012`, `F000018`, `F000019`, `F000028`, `F000029`, `F000031` and `F000033`. They remain in the denominator and were not retried, selected from repeats, or repaired by prompt/parameter changes.

`EARLY_STOP_SEALED.json` binds the freeze, authorization, request-body hashes, raw/public response hashes, ledger and decisions before any E1 GT read. It records 34 decisions, 36 completed API responses including two smoke calls, and the one unresolved request. The independent `e1_score.py --partial-stop` process then verified the seal and opened GT only for 28 required development frames. `PARTIAL_EVENT_RESULTS.json`, `PARTIAL_SUMMARY.json` and `PARTIAL_UNSCORABLE.json` are descriptive partial results, not the planned full E1 test. `PARTIAL_SUMMARY.json` uses `ENGINEERING_FAILURE` as a stage outcome; the scientific claim remains **INCONCLUSIVE** because the run stopped on an engineering gate. The remaining 5 development and all 12 validation events are uncalled and unscored; one of the seven development events lacks its permutation diagnostic.

## Completed paired events (offline candidate choice only)

All seven queried development events were scorable under the independent GT matching policy; none offered a correct non-B0 improvement opportunity. `✓`/`✗` refer only to local candidate correctness, not IDF1/HOTA. Invalid model responses fall back to B0. Full per-arm validity, citations, mappings and unscorable reasons are in `PARTIAL_EVENT_RESULTS.json` and the public response records.

| Packet | Query | B0 | N | L-T | L-V-static | L-V-temporal | Temporal repeat | Alias permutation |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| P06bd8bc948a32f66 | 192 | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ |
| P0b875d6f45a74deb | 6685 | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ |
| P1cb7cbe50698e6d0 | 8069 | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ |
| P268a2bf76437ad61 | 398 | C1 ✓ | C1 ✓ | C1 ✓ | C1 ✓ | C1 ✓ | C1 ✓ | C1 ✓ |
| P296608a3986eefc0 | 4755 | C1 ✓ | C1 ✓ | C1 ✓ | C1 ✓ | C1 ✓ | C1 ✓ | C1 ✓ |
| P2ae9988375c21d4b | 5314 | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ | C2 ✓ |
| P4218132a1659f1e2 | 8069 | C2 ✓ | C2 ✓ | C1 ✗ | C2 ✓ | C2 ✓ | C1 ✗ | not called |

Main-arm counts on this stopped, selection-biased prefix: B0 7/7, N 7/7, L-T 6/7, L-V-static 7/7, L-V-temporal 7/7. These counts do **not** show a temporal-image gain: B0 and N were already correct on every scored event, and the temporal arm changed no physical decision from B0. Four controlled legal preference flips on valid temporal outputs changed the decoder choice, so the interface can let a model affect association; the observed temporal outputs did not do so. One L-T choice and one temporal repeat on packet `P421...` were wrong relative to B0. Repeats and alias permutations were never best-of selections; incomplete/invalid responses count against the frozen diagnostic gates. A citation-valid response is not proof of image grounding.

## Real-input coverage, limits and cost

The preauthorization server inventory located 8399/8400 paired development RGB frames and 2888/2888 validation RGB frames, original/repaired depth, fixed predicted masks, and actual FPN/RGB-histogram features. SLR-2 HSV vectors were absent and were not fabricated. Twenty-four frozen packets each had two full legal candidates and one clone-stage-executable nonbaseline alternative; 48 true-RGB private visual sheets were hash/provenance checked. Automated sheet/geometry QA covered all 48; human visual inspection covered two temporal sheets and their static counterparts only. Technical image transport was proven with an original RGB frame, but no validation event was sent to the model before the early stop. This is one video, with two development packets sharing frame 8069, not cross-video evidence.

The conservative, undiscounted usage-price estimate for 36 completed calls is `$0.3597186`; reserving the unresolved in-flight call raises the upper accounting estimate to `$0.3792579`, below the authorized `$5` cap. Provider billing for `F000035` is unknown. The 34 completed formal calls had 12.25 s minimum, 35.20 s median, 41.02 s maximum latency, 1078.25 s summed latency; smoke calls were 23.93 s and 1.26 s. Pricing basis: official DeepSeek vision and pricing documentation, with no cached-token discount assumed.

R0 engineering remains **PASS**. E1 execution is **STOP** with **ENGINEERING_FAILURE** on the response-validity gate; the language/vision identity-association hypothesis is **INCONCLUSIVE**, not FAIL or PASS. No full-schedule IDF1/HOTA change, real association gain, temporal reasoning contribution, or cost-effectiveness conclusion follows from this partial prefix. The single next step is to preregister a separate, new-event E1 engineering pilot that addresses output truncation without changing or replaying this frozen batch; it is not launched here.
