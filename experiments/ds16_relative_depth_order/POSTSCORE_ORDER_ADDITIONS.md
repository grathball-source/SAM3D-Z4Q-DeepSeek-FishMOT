# DS16 postscore additions to the order mechanism audit

This is a new postseal addition. ORDER_MECHANISM_AUDIT.json/.md remain the source-only audit; their no-GT/no-metric statement describes that earlier audit. This addition reads independently generated GT-derived EVENT_AUDIT and METRICS, without reading GT pixels or changing the frozen predictions.

## Opposite effects of the same sign admission

| Event | Criterion | ORDER actual first publication | OFF/PERMUTE actual first publication | Boundary |
| --- | --- | --- | --- | --- |
| Feeding original F1239 | Bank and clean reference endpoint | WRONG | CORRECT | ORDER blocks {167:136}; unchanged reference A only has 1 pre observation, so full pre consensus remains UNSCORABLE for every branch |
| FishSA original F11900 | Bank and last-clean endpoints | UNSCORABLE | UNSCORABLE | A endpoint best IoU about 0.266 prevents endpoint scoring |
| FishSA original F11900 | Pre-fragment consensus | CORRECT | WRONG | A has 13 observations / 8 known all GT 6; B 13 / 13 all GT 2; expected {4:4,1:1}, OFF instead swaps them |

For F11900, committed_pre_consensus_verdict is **WRONG** for OFF/PERMUTE, not UNSCORABLE. ORDER has NOT_COMMITTED for the committed-only column, while its actual first-public pre-consensus verdict is CORRECT. Current posts both uniquely match their physical identities, and q through q+10 diagnostic agreement is 11/11 for each source. Those future frames are postseal diagnostics, not prediction inputs.

## Whole-segment metrics answer a different question

On the 2888-frame validation segment, OFF/PERMUTE IDF1 82.070744 versus ORDER/original Z4Q 80.697587 is +1.373157 points; HOTA +0.160704 and AssA +0.280318. IDSW increases from 9 to 11. The event-relative fragment audit still judges the F11900 swap WRONG. Full-segment metrics use sequence identity correspondences, whereas the event audit checks preservation of the physical pre reference; the observed improvement cannot be advertised as correct physical restoration.

The ORDER publication here already equals original Z4Q and STATE_FIXED. Avoiding the OFF swap is not an additional improvement over them. At Feeding F1239 the gate demonstrably blocks an endpoint-correct restore, so describing all H0 outcomes as safe protection would discard adverse evidence.

## Other difference

L3 original F1420 is a soft-factor odds effect rather than the hard sign gate. Its independent score status is recorded in the JSON addition; the earlier source-only audit documents margins without assigning physical correctness.

No new experiment, prompt, API call or prediction modification was made.

L3 independent event verdicts: {"ORDER_OFF": {"physical": "WRONG", "first_public_clean_endpoint_verdict": "WRONG", "first_public_pre_consensus_verdict": "WRONG", "committed_pre_consensus_verdict": "WRONG"}, "DEPTH_ORDER": {"physical": "NOT_COMMITTED", "first_public_clean_endpoint_verdict": "CORRECT", "first_public_pre_consensus_verdict": "CORRECT", "committed_pre_consensus_verdict": "NOT_COMMITTED"}, "ORDER_PERMUTE": {"physical": "WRONG", "first_public_clean_endpoint_verdict": "WRONG", "first_public_pre_consensus_verdict": "WRONG", "committed_pre_consensus_verdict": "WRONG"}}
