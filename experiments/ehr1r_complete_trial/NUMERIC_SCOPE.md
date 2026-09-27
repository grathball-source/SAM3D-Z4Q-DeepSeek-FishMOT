# Frozen numerical comparator scope

The inherited [v6 numerical reference](../ehr1r_causal_history_repair/corrected_unsent/NUMERIC_REFERENCE.json) uses the same qualified A/B pre fragments and X/Y post fragments as EHR-1R-C. It is endpoint-history only; it does not consume all anonymous interaction observations or their image evidence. No two-frame IoU baseline replaces a full-history control. Consequently this trial **does not test VLM necessity relative to a full same-information numerical algorithm**, regardless of model accuracy.

Frozen raw choices, recorded here without judging GT, are:

| Case | N-H2D | N-HD | Depth mode |
| --- | --- | --- | --- |
| B01 | H2 | H2 | all four edges |
| B02 | H2 | H2 | all four edges |
| B03 | H2 | H1 | all four edges |
| B04 | H1 | H1 | all four edges |
| B05 | H1 | H1 | symmetric depth unavailable fallback |

H1/H2 are the unpermuted packet's labels. A permuted model request must be evaluated by its physical mapping; this table is not relabelled to pretend that a label is an identity. No new numeric run, tracker update, HOTA/IDF1 or E2 is included.
