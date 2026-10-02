# DS15 original-action preservation review

Independent review of completed sealed predictions and scorer audits. No raw GT or predictor was opened.

| Segment | Original global frame | Source→target | Arm | Published at original frame | Durable at original frame | First target publication | First durable alias | Publication differences for this source |
|---|---|---|---|---|---|---|---|---|
| fishsa_development_8400 | 1327 | 6→0 | Z4Q_FROZEN | 0 | 0 | 1327 | 1327 | 0 |
| fishsa_development_8400 | 1327 | 6→0 | R12_RAW | 6 | None | None | None | 2551 |
| fishsa_development_8400 | 1327 | 6→0 | Z4Q_SHARED | 0 | 0 | 1327 | 1327 | 0 |
| fishsa_development_8400 | 1327 | 6→0 | Z4Q_DEPTH | 0 | 0 | 1327 | 1327 | 0 |
| fishsa_development_8400 | 3902 | 7→0 | Z4Q_FROZEN | 0 | 0 | 3902 | 3902 | 0 |
| fishsa_development_8400 | 3902 | 7→0 | R12_RAW | 7 | None | None | None | 4499 |
| fishsa_development_8400 | 3902 | 7→0 | Z4Q_SHARED | 7 | None | None | None | 4499 |
| fishsa_development_8400 | 3902 | 7→0 | Z4Q_DEPTH | 7 | None | None | None | 4499 |
| fishsa_development_8400 | 8054 | 8→2 | Z4Q_FROZEN | 2 | 2 | 8054 | 8054 | 0 |
| fishsa_development_8400 | 8054 | 8→2 | R12_RAW | 8 | None | None | None | 347 |
| fishsa_development_8400 | 8054 | 8→2 | Z4Q_SHARED | 2 | 2 | 8054 | 8054 | 0 |
| fishsa_development_8400 | 8054 | 8→2 | Z4Q_DEPTH | 2 | 2 | 8054 | 8054 | 0 |
| fishsa_validation_2888 | 9580 | 6→2 | Z4Q_FROZEN | 2 | 2 | 9580 | 9580 | 0 |
| fishsa_validation_2888 | 9580 | 6→2 | R12_RAW | 6 | None | None | None | 2609 |
| fishsa_validation_2888 | 9580 | 6→2 | Z4Q_SHARED | 2 | 2 | 9580 | 9580 | 0 |
| fishsa_validation_2888 | 9580 | 6→2 | Z4Q_DEPTH | 2 | 2 | 9580 | 9580 | 0 |
| fishsa_validation_2888 | 11488 | 8→3 | Z4Q_FROZEN | 3 | 3 | 11488 | 11488 | 0 |
| fishsa_validation_2888 | 11488 | 8→3 | R12_RAW | 8 | None | None | None | 701 |
| fishsa_validation_2888 | 11488 | 8→3 | Z4Q_SHARED | 8 | None | None | None | 701 |
| fishsa_validation_2888 | 11488 | 8→3 | Z4Q_DEPTH | 8 | None | None | None | 701 |
| fishsa_validation_2888 | 12150 | 11→5 | Z4Q_FROZEN | 5 | 5 | 12150 | 12150 | 0 |
| fishsa_validation_2888 | 12150 | 11→5 | R12_RAW | 11 | None | None | None | 39 |
| fishsa_validation_2888 | 12150 | 11→5 | Z4Q_SHARED | 5 | 5 | 12150 | 12150 | 0 |
| fishsa_validation_2888 | 12150 | 11→5 | Z4Q_DEPTH | 5 | 5 | 12150 | 12150 | 0 |

Publication and durable state are separate. Full mapping/alias runs, active events, accepted candidates, actual commits, strong veto examples and scorer verdicts are retained in the JSON.

## DEPTH metric differences

| Unit | Compared with | ΔIDF1 | ΔHOTA | ΔAssA | ΔIDSW | ΔFP | ΔFN |
|---|---|---|---|---|---|---|---|
| fishsa_development_8400 | SAM3_NATIVE | +0.689374 | +1.144648 | +2.177282 | +2 | +0 | +0 |
| fishsa_development_8400 | Z4Q_FROZEN | -7.330810 | -3.338696 | -6.543589 | +1 | +0 | +0 |
| fishsa_development_8400 | Z4Q_SHARED | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 |
| fishsa_validation_2888 | SAM3_NATIVE | +0.185405 | -0.150168 | -0.140758 | +2 | +0 | +0 |
| fishsa_validation_2888 | Z4Q_FROZEN | -4.055737 | -2.958508 | -5.019020 | +1 | +0 | +0 |
| fishsa_validation_2888 | Z4Q_SHARED | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 |
| L3 | SAM3_NATIVE | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 |
| L3 | Z4Q_FROZEN | -2.318468 | -1.808950 | -4.579391 | -1 | +0 | +0 |
| L3 | Z4Q_SHARED | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 |
| LW | SAM3_NATIVE | +0.000000 | -0.080900 | -0.188955 | +0 | +0 | +0 |
| LW | Z4Q_FROZEN | -3.715862 | -2.703554 | -6.439431 | -3 | +0 | +0 |
| LW | Z4Q_SHARED | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 |
| Feeding_pooled1471 | SAM3_NATIVE | +0.843957 | -0.030058 | -0.057324 | +22 | +0 | +0 |
| Feeding_pooled1471 | Z4Q_FROZEN | +0.103911 | +0.074146 | +0.131393 | -2 | +0 | +0 |
| Feeding_pooled1471 | Z4Q_SHARED | +0.103911 | +0.074146 | +0.131393 | -2 | +0 | +0 |
