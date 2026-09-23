# VL_ASSOC_E1 status: INCONCLUSIVE / READY_FOR_E1_API

R0 engineering passes. E1's model hypothesis is untested because this round has no explicit paid-call authorization: `allow_api=false`, zero E1 HTTP calls, zero actual E1 cost or measured latency, no model decisions, and no E1 GT scoring. This is not a PASS for temporal vision-language association. The older sealed run's zero edits and equal B0/B1 metrics are historical facts, not E1 gains.

Fixed base: `a566dc6d606ab77696f08f5490486d6f541ebe15`. Work is in new `codex/vl-assoc-r0-e1` branch and an independent server checkout; old sources, predictions and API responses were read-only. The new commit is recorded in the handoff/final task response after synchronization. `PROTOCOL_DIFF.md` marks the new E1 event, candidate, input and response contract as a new research hypothesis, not an R0 repair. Neither the old three votes, five frames nor episode budget changed.

## R0 and real inputs

`REPLAY_AUDIT.json`: 2888 frames/global 9301–12188, 33 exact request-response bindings, 33 valid saved responses (32 DEFER, one H0), zero true commits and zero B0/B1 difference frames. The original sealed gzip file hashes were checked separately from exact decompressed-row replay; there was no historical API rerun. Historical estimate was $0.364797, not an E1 charge.

`TEST_REPORT_FINAL.json`: 23 repair/atomic/scoring checks pass and fixed B0 remains identical for 2888 frames. Frame-241 `R000010` verifies the old null provenance anchor and repaired actual D1 history source. `R0_SCORE_AUDIT.json` is a separate post-seal process: actual TrackEval source tree hash and original IDF1 80.6976/HOTA 69.2439/IDSW 9 are retained for both identical old branches. Relation audit includes 102479 scorable plus 6504 unscorable historical pairs, including GT4/GT5 (16458/17176 scorable pairs), with zero incremental harm/improvement because predictions match. It does not equate an unscorable observation with safety.

`ASSET_INVENTORY.json`: 8400 development and 2888 validation source frames; 8399/8400 and 2888/2888 paired real RGB. Existing 256-D FPN covers 48896/50271 and 16872/17197 observations; 48-bin RGB histograms cover 50268/50271 and 17179/17197. Predicted masks, original/repaired depth and appearance align by mask key and area, not the sometimes-disagreeing feature ID. The archived SLR-2 HSV extractor was inspected but no HSV vector was present, so none was fabricated. True RGB is 1920×1080 and mask 640×360, with manifest and pixel-scale validation. Forty-eight private visual sheets were made from actual RGB; automated provenance/geometry checks cover all, human visual inspection covers two temporal and matching static sheets only (`LOCAL_VISUAL_QA.md`).

## Candidate reachability and paired event outputs

The final causal V4 probe logged 185 development / 104 validation contacts; 159 / 83 reached a query; 42 / 18 had at least one clone-stage-executable nonbaseline candidate. SHA selection fixed 12 + 12 events before any E1 model output or GT. All selected packets have two complete candidates and the same per-event causal history, query time, candidate set and evidence cutoff across B0, N and the three model arms. Every packet has one executable nonbaseline alternative; no model is called for B0-only events. Five packets retain an empty historical reference. Two development events share frame 8069 but have separate episode keys and are correlated, not independent videos. The saved earlier probe revisions are prefreeze development records; V4 alone determines this run. Protocol selection before formal calls weakens claims of strict preregistration, and the one-video sample cannot establish cross-video generality.

In the table, `?` means all L-T/L-V-static/L-V-temporal, repeat and alias-permutation responses are unsent; GT correctness/candidate coverage are likewise unopened. `N` is active: it changes the physical mapping only on `P175d295a01799fe5`. D-only/A-only/M-only change B0 on 2/3/6 events respectively, but are diagnostics, not a handpicked weak baseline. Candidate aliases are packet-local.

| Split | Packet | Query frame | B0 | N | Model/GT |
| --- | --- | ---: | --- | --- | --- |
| dev | P06bd8bc948a32f66 | 192 | C2 | C2 | ? |
| dev | P0b875d6f45a74deb | 6685 | C2 | C2 | ? |
| dev | P1cb7cbe50698e6d0 | 8069 | C2 | C2 | ? |
| dev | P268a2bf76437ad61 | 398 | C1 | C1 | ? |
| dev | P296608a3986eefc0 | 4755 | C1 | C1 | ? |
| dev | P2ae9988375c21d4b | 5314 | C2 | C2 | ? |
| dev | P4218132a1659f1e2 | 8069 | C2 | C2 | ? |
| dev | P4f984757cb073766 | 7102 | C2 | C2 | ? |
| dev | P505e5ce82c20bdd0 | 2663 | C1 | C1 | ? |
| dev | P6093da8587bc16c7 | 287 | C2 | C2 | ? |
| dev | P6dd51c7c657f38ac | 5179 | C2 | C2 | ? |
| dev | P7191b96390a1ca1c | 4574 | C2 | C2 | ? |
| val | P017ea2eb5b2a8a48 | 2677 | C1 | C1 | ? |
| val | P04c303d9612421d6 | 377 | C2 | C2 | ? |
| val | P0bb5b6c537eb526b | 1375 | C2 | C2 | ? |
| val | P175d295a01799fe5 | 2638 | C2 | C1 | ? |
| val | P1797ad89bd359331 | 2580 | C1 | C1 | ? |
| val | P188c6571ae22ff20 | 2841 | C1 | C1 | ? |
| val | P396d217afb3e0fac | 2718 | C1 | C1 | ? |
| val | P538a7a4638462254 | 2846 | C1 | C1 | ? |
| val | P56d853b682c8b43d | 1832 | C2 | C2 | ? |
| val | P7517e6637bc947e6 | 2461 | C1 | C1 | ? |
| val | P8111d40d0ad38d57 | 427 | C2 | C2 | ? |
| val | P81c6f08460d3827c | 2379 | C1 | C1 | ? |

`EVENT_RESULTS.json` holds the full per-event B0/N/D-only/A-only/M-only choices and explicit pending model/GT fields. It must not be read as correct-choice counts, IDF1 or HOTA. Candidate generation/stage exclusions for every registered event are in `EVENT_PROBE_V4_*.json`; selected full mappings and stage evidence are in `CANDIDATE_AUDIT.jsonl`.

## Model action and request freeze

`e1_protocol.py` validates all legal candidate comparisons, citations, reason codes, applicability and exact packet/snapshot version. A complete candidate that strictly beats every other candidate is selected; tie/cycle/unobservable/invalid falls back to B0. Model-off, legal preference reversal, nonzero synthetic association impact, numeric missing-data fallback and alias-permutation invariance pass. This is an interface test, not evidence that a real model used the images. The actual-model removal/permutation effect, grounding, response validity, repeat agreement, cost and latency remain unmeasured.

`preflight_e1.py` verified 24 packets, 120 frozen request manifests, true in-memory `image_url` content blocks (not filenames masquerading as images), 48 server-private sheet hashes, all 354 visual rows, snapshot/cutoff alignment, payload hashes and fixed seeded per-event main-arm order. `SANITIZATION_AUDIT.json` documents prefreeze removal of native mask IDs from model-visible packets. `FREEZE.json` records final code/prompt/packet/manifest/private-image hashes. Official [DeepSeek vision](https://api-docs.deepseek.com/guides/vision/) and [pricing](https://api-docs.deepseek.com/quick_start/pricing/) rules underpin `COST_PLAN_FINAL.json`: conservative peak reservation $2.4617 for at most 120 formal + 2 technical-smoke calls, below the proposed $5 cap. Actual E1 charge is $0; there are no API timing samples. A key or prior budget is not authorization. `API_AUTHORIZATION.json` remains false, so requests are frozen but not sent.

## Boundary and decision

Engineering: R0 **PASS**, E1 preparation **READY_FOR_E1_API**. Research: **INCONCLUSIVE**; no paid authorization, no model decisions or post-decision E1 GT scoring. No E2, SAM3 rerun, new network training, official trajectory edit or full-sequence metric claim. The single next step is to obtain explicit authorization (or refusal) for this frozen E1 paid-call budget; if authorized, execute only the 120/2-call E1 plan and independent post-seal scoring, without retuning on these events.
