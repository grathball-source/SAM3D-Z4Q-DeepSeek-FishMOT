# M3-L final review: local matches, no VLM increment

**Engineering/source: PASS with two citation-format failures retained. Input scoreability: PASS for this exposed window. Frozen local-choice signal: PASS only on accepted matches and raw repeat choices. Added value over both fixed numeric references: FAIL. Research decision: `HAS_LOCAL_CAPABILITY_NO_INCREMENT`; STOP this frozen local-VLM association definition.** This is one physical B01 interaction, not 12 independent recovery events, not a long-chain identity method, and not a new IDF1/HOTA result.

Fixed review base and starting fetched `origin/main`: `8ec0d3b8bd2e7c75dd2d6b3d15b1b0bb6341e16b`. New code/results live only under `experiments/m3l_local_correspondence/`; old M2-T/M2T-F request, response, source, score and seal hashes remain unchanged. Actual host `ps-ESC8000-G4`, user `xiongxiong`. The one-batch authorization was official `deepseek-flash`, at most 25 inference requests and USD 3. Actual: **24 formal + one real-image Files API smoke, no retry, all `stop`, USD 0.2951883 peak-rate upper accounting**. Formal latency sum 1,014.982 s; this is not a provider invoice. Exact model alias, returned model, per-request use/latency/content and immutable body/response seals are in `CALL_LEDGER.jsonl`, `responses/`, `REQUESTS_SEALED.json`, `RESPONSES_SEALED.json`, `PLAN.json` and `final_score/RESPONSE_MANIFEST.json`.

## Full fixed twelve-hop pairing

Every source and target set had six actual predicted ROI observations; G006–G018 are adjacent **sent sample times**, not every acquired frame. Scoreable sources are 66/72 (12/12 hops have at least one); the other six are preserved: two `TARGET_NOT_UNIQUE` at P07 and four `SOURCE_UNMATCHED_OR_AMBIGUOUS` at P08/P09. Table cells are *usable correct MATCH / scoreable source count*, not raw response accuracy. The complete 24 attempt rows including costs, latency, format status, abstentions and counts are in `final_score/PAIR_RESULTS.json`; all 144 source-attempt rows are in `final_score/TOKEN_MATCH_RESULTS.jsonl`.

| Pair (local frames) | Scoreable | First | Exact repeat | Principal retained limitation |
| --- | ---: | ---: | ---: | --- |
| P01 1300→1308 | 6 | 6/6 | 0/6 | Repeat raw targets all six correct, but all six citations have object-valued `observation`, so none usable. |
| P02 1308→1315 | 6 | 4/6 | 6/6 | First abstains on two scoreable sources, including both A/B path tokens. |
| P03 1315→1321 | 6 | 6/6 | 6/6 | No retained decision fault. |
| P04 1321→1323 | 6 | 6/6 | 6/6 | No retained decision fault. |
| P05 1323→1331 | 6 | 0/6 | 5/6 | First has six object-valued citations; repeat abstains once. N-C swaps two source targets, N-I gets both right. |
| P06 1331→1338 | 6 | 6/6 | 6/6 | No retained decision fault. |
| P07 1338→1346 | 4 | 4/4 | 4/4 | Two other source objects lack a unique target GT observation. |
| P08 1346→1353 | 4 | 4/4 | 4/4 | Two other source objects are GT-ambiguous/unmatched; first abstains on them. |
| P09 1353→1361 | 4 | 4/4 | 4/4 | Two other source objects remain GT-ambiguous/unmatched; first abstains on one. |
| P10 1361→1369 | 6 | 6/6 | 6/6 | No retained decision fault. |
| P11 1369→1376 | 6 | 6/6 | 6/6 | No retained decision fault. |
| P12 1376→1384 | 6 | 6/6 | 6/6 | No retained decision fault. |

Both attempts selected the correct target for every **accepted, uniquely scoreable** match: first 58/58 (coverage 58/66 = 87.88%), repeat 59/59 (59/66 = 89.39%). The complete decision structure parsed in 24/24 responses; P01-REPEAT and P05-FIRST separately failed citation format on 12 edges. No occupied-target conflict was present. Raw target/abstain repeat agreement was 63/66 = **95.45%**, whereas agreement on *usable-edge classification plus target* was 52/66 = **78.79%** because the two citation-format failures occur in opposite arms. Citation membership was checked automatically; not every prose statement was semantically confirmed by image inspection. The first scorer's initial 22/24 count, all original results, the narrower taxonomy correction and the new 24/24 count are preserved in `SCORER_CORRECTION.md`. No choice, prompt, sample or scoring GT was sent back to the model.

The identical-input fixed numerical baselines evaluated the same 66 uniquely scoreable source relations. N-C center-distance Hungarian: **64/66 correct, 100% coverage**; N-I original-mask-IoU Hungarian: **66/66 correct, 100% coverage**. N-C's two mistakes are P05 `f010:o03→f011:o04` and `f010:o04→f011:o03`; N-I correctly separates both. The model repeat gets the former right, but first P05 citations are invalid and there is no hop where **both** baselines err and **both** model attempts succeed. Because N-I is already perfect on this scoreable subset and covers more choices, M3-L provides **zero demonstrated incremental local association value** over the fixed references, despite meeting the narrow accepted-match precision, coverage and raw-repeat signal gates. These are local choices only and cannot be converted to tracking metric gains.

Strict composition of model edges does not reach G018. First A (`f006:o06`) and B (`f006:o02`) each reach only G007/local1308, then stop at P02 `UNRESOLVED`. Exact-repeat A/B stop at G006/local1300 because P01 citations are unusable. There is no certified wrong key-chain step before these stops, but absence of an observed wrong step is **not** successful long-range identity integration. No GT or native-ID bridge was used. `final_score/CHAIN_COMPOSITION.json` records every stop and the posthoc error boundary.

The post-score actual-pixel P05 panel visibly contrasts the model/N-I/GT `f011:o03` edge with wrong N-C `f011:o04`; the P08 panel shows an abstention and ambiguous GT source rather than manufacturing an answer. Both are private `POSTHOC_NOT_SENT` QA and were actually opened; `VISUAL_QA.md` limits what was seen. Work knew the score and is not an independent blind reviewer. `ARTIFACT_MANIFEST.json` lists exact paths/bytes/hashes for all 68 server-restricted items plus four local private copies; no private pixels, original GT raster, provider file IDs, raw wire or credentials enter Git.

Engineering checks: 8/8 regression tests, exact first/repeat body equality, sender isolation, source/ROI/time/token correspondence, two distinct baseline outputs, original-mask hashes, postseal GT ordering and unchanged old seals. See `TEST_REPORT.md`, `SLICE_AUDIT.json`, `SOURCE_MANIFEST.json`, `REQUEST_MANIFEST.json`, `final_score/RESPONSE_MANIFEST.json`, and `EXECUTION_LOG.md`. Remaining uncertainty: whether another independent interaction offers an opportunity where both transparent numeric rules fail; this exposed B01 window cannot establish generalization. No new tracker transaction, model tuning, additional image condition, training, hidden test GT, E2 or new IDF1/HOTA was performed.

**One next step:** seal M3-L as `HAS_LOCAL_CAPABILITY_NO_INCREMENT` and stop spending on this local matching definition; any new interaction or mechanism would need a separate, pre-registered user instruction.
