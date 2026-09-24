# M2-T frozen offline association results

Fixed base `a27720ff313a27037eb5cbdd9d629506911af7d2`; five *exposed* AO1/M1 cases, not a new tracker continuation or hidden holdout. `C` = correct complete association against the exposed event key, `W` = wrong replacement, `A` = abstention, `U` = N-M unavailable. Repeat columns are diagnostics, never a vote.

| Case | B0 | N-M | G-SEQ | G repeat | G+AP | AP repeat | G-END |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B01 positive | W | U | A | A | W | W | A |
| B02 old harm | C | U | C | C | A | A | A |
| B03 old harm | C | W | A | W | C | C | W |
| B04 old harm | C | W | A | W | A | A | W |
| B05 old harm | C | U | A | A | A | A | A |

The [full 25-attempt four-edge record](ATTEMPT_RESULTS.jsonl) retains raw relations, citation legality, decoded complete relation, true status, latency and cost. [Five paired event records](EVENT_RESULTS.jsonl) preserve the original answer, B0 and endpoint N-M. B0 labels were checked against the old immutable M1 event record in `B0_PARITY.json`; they are not model messages. N-M uses only frozen endpoint samples: B01/B02/B05 have too few distinct historical times; B03/B04 are available but choose the wrong complete association. This weak endpoint-only comparator is not a same-information full-sequence numeric competitor.

All 25 model responses stopped normally and passed the frozen JSON/four-edge schema; all 80 directional edges passed *source/time/token* citation validation. Ten calls produced a non-abstaining complete mapping (four correct, six wrong); 15 abstained. G-SEQ first answers were 1C/0W/4A, but G repeats were 1C/2W/2A: only 3/5 repeated the first decoded choice. G+AP first and repeat each yielded 1C/1W/3A and agreed 5/5; B01's stable G+AP answer was stably **wrong**, so stability alone is not progress. G-END gave 0C/2W/3A. These counts are *calls on five cases*, not 25 independent events.

B01 fails the preregistered recovery gate: both geometry-sequence calls abstain, while both appearance-augmented calls wrongly select the B0 relation. The old four harms all remain: B03/B04 G-SEQ repeats make wrong changes even though first answers abstain; B02 is a correct geometry-sequence choice; B05 abstains. The four failures cannot be discarded to highlight B02. G-SEQ versus G+AP is mixed: adding endpoint RGB helps B03 but harms B01, and neither alone establishes static texture causality. G-SEQ first differs favorably from G-END on B02–B04, but repeat instability and no B01 recovery prevent a robust middle-interaction claim. B04/B05 belong to overlapping longer interaction context; do not count them as independent confirmations.

The decoder is not decorative: model-off and legal-edge permutation tests give ABSTAIN versus different complete mappings, and ten real model outputs selected a mapping. This is **offline VLM participation**, not a tracker edit. Every non-abstaining decisive citation (106) was checked against actual sent G-image SHA/pixels and mask geometry, 106/106 source-valid; a source-valid pixel does not verify the model's asserted cross-time identity. Work manually opened 14 restricted images across input and failure QA; [VISUAL_QA.md](VISUAL_QA.md) states exposure and limitations. No independent semantic reviewer or full-video identity observability judgment is claimed.

Engineering outcome: **PASS** for source fidelity, frozen request/response integrity, 26/26 traceable inference attempts and 25/25 schema-valid responses. Input identity observability: **INCONCLUSIVE**. Model evidence / preregistered motion-first gate: **FAIL / STOP_FROZEN_M2T**. Method or E2: **NOT ADVANCED**. The actual official `deepseek-flash` run had 25 formal calls plus one same-route synthetic smoke; price-rate upper accounting was **USD 1.2293283** against USD 3 (not a provider invoice), with 3,475.95 s total formal latency, 139.04 s mean and 216.81 s maximum. No new IDF1/HOTA, training, test GT, tracker stage/commit or extra API call was performed.
