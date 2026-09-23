# DeepSeek + Z4Q closed-loop feasibility on exposed 2,888-frame validation

Status: COMPLETE_NO_MEASURED_GAIN. Authoritative run and scoring were performed on the lab server in this directory on 2026-09-23. This is not an untouched holdout and not a real-time deployment.

## Frozen implementation and inputs

- Source repository: grathball-source/SAM3D-Z4Q-JEV-FishMOT, copied from local HEAD `4f2280efbfc3223a9ea5a20da9227d3a235aeada` into isolated `z4q_source/`. Original repository and prior experiment outputs were unchanged.
- Frozen source/config/input manifest: `SOURCE_FREEZE.json`, SHA-256 `69f3ab9c45e14e487aaa9297415be4c4ce57517cd49dec523459d2ac67449a62`.
- Exposed validation: global frames 9301-12188, 2,888 frames. Frozen upstream observations/features and native masks were shared by B0 and B1.
- B0: original Z4Q_STABLE. B1: independent repaired Z4Q engine with the copied causal transaction bridge and real text-only `deepseek-flash` decisions. Three independent votes had to unanimously select one complete edit and affirm all changed and displaced claims; existing five-frame confirmation, three-check episode cap, stage and commit_once then governed execution. B1 continued from its own state.
- The DeepSeek system prompt and configuration are `PROMPT.txt` and `MODEL_CONFIG.json`. This is a new prompt/decision protocol; it is not the earlier SLR-2 offline 17/18 protocol.

## Verification and commands

Before API calls, `preflight.py` reproduced all 2,888 archived B0 predictions exactly without GT or API access (`PREFLIGHT_V2.json`). `contract_checks.py` passed end-to-end engineering fixtures for reconnect, swap, candidate withdrawal, confirmation timing, commit_once, and next-frame state (`CONTRACT_CHECKS_V2.json`); fixtures are not model accuracy. `score.py --fixture` detected a deliberately wrong synthetic B1 identity assignment (`SCORER_FIXTURE.json`).

Run on the lab host using `/home/data2/xiongxiong/dmot-annotation/env/bin/python` with `CUDA_VISIBLE_DEVICES=`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and `MKL_NUM_THREADS=1`:

```text
python preflight.py
python contract_checks.py
python score.py --fixture
python freeze.py
python run_closed_loop.py > run.log 2>&1
python score.py
```

The real run was launched in detached Screen `deepseek_z4q_side_20260923`; `exit_code.txt` is 0. The API credential was delivered to a FIFO over SSH, never written to a regular file or a report. Inference installed a scoring-data read guard. The full prediction and transaction streams were sealed before `score.py` accessed GT. The seal is `PREDICTIONS_SEALED.json`; predictions SHA-256 `c06e17ac42a95434e35460268c5f1513efabf906d3c3f49fc167830486dbdbc5`.

## Actual results

| Metric | B0 Z4Q | B1 DeepSeek + Z4Q |
| --- | ---: | ---: |
| IDF1 | 80.6975868362 | 80.6975868362 |
| HOTA | 69.2438689597 | 69.2438689597 |
| AssA | 60.0743214554 | 60.0743214554 |
| DetA | 79.8327346447 | 79.8327346447 |
| IDSW | 9 | 9 |
| FP / FN | 298 / 423 | 298 / 423 |

The two branches differed on **0 frames**. B1 committed **0 transactions**; correct/wrong/unscorable commits were 0/0/0. Full-timeline additional scorable harms and improvements were both 0. Identical masks were enforced in every frame.

There were 11 eligible decision checks across five episode keys, causing 33 HTTP attempts. All 33 returned valid responses: 32 `DEFER`, one `H0`, and zero edit choices. One three-vote check disagreed (`DEFER, DEFER, H0`). No first confirmation or second confirmation occurred. Estimated charge from returned token usage was USD 0.364797 for 142,638 input and 268,338 output tokens. Median request latency was 35.73 s; p95 75.03 s, maximum 80.84 s. These are replay call latencies, not real-time tracking latency.

Frame statuses: 2,790 `NO_LEGAL_PROPOSAL`, 22 `WAIT_NEW_OBSERVATION`, 48 `EPISODE_SEALED`, 17 `OUT_OF_SCOPE`, 10 `DEFER`, and one `vote_disagreement`. Statuses sum to 2,888.

## Mechanism and representative cases

The model was cautious on both wrong and locally plausible candidates. At frame 190 (global 9490), proposed native 5 -> public 2 conflicted with post-seal GT (individual 5 versus public 2's fixed individual 4). Its depth residual was about 79 mm against about 39 mm tolerance, while appearance was missing; all three votes deferred. At frames 241 and 246, native 7 -> public 2 agreed with the local GT individual, but the model still deferred; another alternative native 5 -> public 2 was locally wrong. At frame 251, the votes were two deferrals and one H0, so no edit passed. Near frame 2832, one candidate had missing depth and a motion distance outside its radius; the other local edge agreed with GT but shared an ambiguous fixed public-ID lineage. Frames 2834, 2844 and 2849 again deferred. The local post-seal audit records 7 matching, 8 conflicting, and 1 unscorable proposal edges across all checked alternatives (`POSTSEAL_EVENT_AUDIT.json`). These are **not** counterfactual closed-loop gains: no rejected proposal was committed, and some GT individuals have multiple fixed public IDs.

No tracking-failure visualization is needed to explain a B0/B1 difference because there is none. The frame-specific transaction traces and post-seal event audit provide the failure-case evidence.

## Interpretation and limits

For this frozen protocol on this exposed segment, DeepSeek added no measured tracking benefit and no additional identity harm. The earlier 17/18 offline text result measured a different selection task and cannot be treated as the closed-loop result. The copied Z4Q bridge serializes its original `model: jev-1.13.0` metadata and Jev-style questions inside the DeepSeek user payload; the outer HTTP model was verified as `deepseek-flash`. This inherited metadata is a prompt-design limitation and may confuse the comparison. Changing it or the unanimity/confirmation rules would define a new protocol and needs a separate decision and frozen run. Also, because validation was previously exposed, the result does not establish generalization to untouched video.

The server-side final metrics are `METRICS.json`, full-timeline audit is `FULL_TIMELINE_HARM_AUDIT.json`, raw call evidence is `CALL_LEDGER.jsonl` plus `requests/` and `responses/`, and transaction/prediction streams are the sealed gz files. No Git commit or push was performed for this side experiment.
