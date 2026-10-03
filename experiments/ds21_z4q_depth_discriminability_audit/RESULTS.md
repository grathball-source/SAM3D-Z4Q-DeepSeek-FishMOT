# DS21 complete original Z4Q action audit

This is a retrospective diagnostic of sealed actions. No new tracking predictions, metrics, veto or model calls.

All 90 original durable actions: strict grades {'WRONG': 17, 'UNSCORABLE': 58, 'CORRECT': 15}; literal bank grades {'WRONG': 17, 'UNSCORABLE': 57, 'CORRECT': 16}.

## Fixed additional measurement screens

Counts below describe measurement eligibility only. Screened correct actions are losses of available original recovery opportunities; screened unknown actions are not safety successes.

| ROI | Scope | Original physical grade | Total | Eligible | Screened | Unbound |
|---|---|---|---:|---:|---:|---:|
|whole|current_eligible|CORRECT|15|14|1|0|
|whole|current_eligible|WRONG|17|13|4|0|
|whole|current_eligible|UNSCORABLE|58|57|1|0|
|whole|anchor_eligible|CORRECT|15|14|1|0|
|whole|anchor_eligible|WRONG|17|15|2|0|
|whole|anchor_eligible|UNSCORABLE|58|53|5|0|
|whole|both_eligible|CORRECT|15|13|2|0|
|whole|both_eligible|WRONG|17|12|5|0|
|whole|both_eligible|UNSCORABLE|58|53|5|0|
|birth_core|current_eligible|CORRECT|15|14|1|0|
|birth_core|current_eligible|WRONG|17|13|4|0|
|birth_core|current_eligible|UNSCORABLE|58|45|13|0|
|birth_core|anchor_eligible|CORRECT|15|15|0|0|
|birth_core|anchor_eligible|WRONG|17|12|5|0|
|birth_core|anchor_eligible|UNSCORABLE|58|44|14|0|
|birth_core|both_eligible|CORRECT|15|14|1|0|
|birth_core|both_eligible|WRONG|17|10|7|0|
|birth_core|both_eligible|UNSCORABLE|58|37|21|0|
|core|current_eligible|CORRECT|15|15|0|0|
|core|current_eligible|WRONG|17|16|1|0|
|core|current_eligible|UNSCORABLE|58|56|2|0|
|core|anchor_eligible|CORRECT|15|15|0|0|
|core|anchor_eligible|WRONG|17|17|0|0|
|core|anchor_eligible|UNSCORABLE|58|55|3|0|
|core|both_eligible|CORRECT|15|15|0|0|
|core|both_eligible|WRONG|17|16|1|0|
|core|both_eligible|UNSCORABLE|58|53|5|0|

## Every original Birth action

| Segment | Original frame | Physical grade | Core residual mm | Whole residual mm | Survivor witnesses | Assignment margin |
|---|---:|---|---:|---:|---:|---:|
|feeding_000351_000555|468|WRONG|9.796692|2.631592|1|0.318158|
|feeding_001201_001906|1390|WRONG|13.716431|32.741394|1|0.426230|
|fishsa_development_8400|3902|CORRECT|29.121552|20.228027|1|0.191238|
|fishsa_validation_2888|11488|CORRECT|6.238953|12.114868|1|0.600692|

## Historical performance only

| Unit | SAM3 IDF1 | Original Z4Q IDF1 | Archived DS20 IDF1 | DS21 new IDF1 |
|---|---:|---:|---:|---|
|Feeding_pooled1471|80.976760|81.716806|81.245406|NOT_RUN|
|fishsa_development_8400|91.313288|99.333472|99.244072|NOT_RUN|
|fishsa_validation_2888|76.456444|80.697587|80.413685|NOT_RUN|
|L3|72.426787|74.745256|74.745256|NOT_RUN|
|LW|60.613534|64.329395|60.613534|NOT_RUN|

Full six-field historical scores, all action features and distributions are in DIAGNOSTIC_RESULTS.json.

## Limits

D1 rejected matrix edges do not export exact old anchors. No public integer or age is used to reconstruct alternative histories. Current observations, actual accepted anchors and explicit Birth view anchors are bound to frozen facts; qualified identity continuity remains UNKNOWN.

Single layers, independent-source eligibility and depth agreement do not certify physical identity. Local depth-layer ownership and continuous occlusion order are not measured by this audit. L3/LW reference is weak prediction-derived; every source cohort is exposed. No new accuracy, physical depth calibration, independent generalization or tracking gain is claimed.

PRIVATE_VISUALS.json inventories actual old-anchor/before/commit/after pixel figures and exact source bindings. Pictures stay private; the last column is postseal diagnosis only.
