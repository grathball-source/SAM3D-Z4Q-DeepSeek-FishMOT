# DeepSeek + Z4Q Fish MOT research archive

This repository isolates the **DeepSeek + Z4Q** work from the discontinued Jev validation. It contains the two completed offline studies and the completed 2,888-frame API closed-loop feasibility run, with source, frozen prompts/configurations, checks, per-event decisions, call records, predictions, metrics, and analyses. It does **not** contain a new experiment or claim an untouched holdout.

| Study | Design | Result | What it measures |
| --- | --- | --- | --- |
| [SLR-1](offline/slr1_text/RESULTS.md) | Text evidence, 36 original and 36 reordered requests | `STOP_SLR1`; 11/18 local correct events vs Z4Q 13/18 | Offline shadow association only |
| [SLR-2](offline/slr2_text_vs_image/RESULTS.md) | Text-only T vs text + RGB/mask V, 144 responses | `STOP_SLR2`; T single 17/18, V single 15/18; guarded consensus T 15/18, V 14/18 | Offline, oracle-selected exposed events |
| [Closed loop](online/closed_loop_2888/RESULTS.md) | Text-only `deepseek-flash`, independent Z4Q state, real API, 2,888 exposed frames | `COMPLETE_NO_MEASURED_GAIN`; 0 edits, B0=B1 on all frames, IDF1 80.6975868362, HOTA 69.2438689597 | Continuous replay with sealed predictions and independent scoring |

The offline 17/18 result is **not** a tracking metric and did not transfer into a measured closed-loop gain. In the final run, 11 eligible checks produced 33 valid HTTP responses: 32 `DEFER`, one `H0`, no edit choice, and no commit. No extra identity harm occurred because the branches produced identical predictions. The validation segment had already been exposed, so none of these results establish performance on untouched video or real-time deployment.

Start with [EXPERIMENT_INDEX.md](EXPERIMENT_INDEX.md) for the stage-by-stage record and [ARCHIVE_SCOPE.md](ARCHIVE_SCOPE.md) for artifact provenance and intentional media/credential exclusions. [MANIFEST.json](MANIFEST.json) gives source and archived SHA-256 hashes for every packaged file.

Newer research extensions: [E1 R0/E1 and exploratory rerun](experiments/vl_assoc_e1/README.md), and [E1C-A recovery audit](experiments/vl_assoc_e1c/RESULTS.md). The root `MANIFEST.json` covers the original packaged archive, not these later extension files; E1C-A has its own prediction-only exposure manifest. The E1C-A audit stops with an engineering failure and no confirmed correct executable recovery candidate; it made no API call and does not authorize E1C-B or E2.

The independent [RQ0 association-reference quality go/no-go](experiments/rq0_memory_headroom/RESULTS.md) starts from E1C-A commit `6320f29`, changes real Z4Q reference admission without any model/API call, and stops before a VLM pilot: two visibly bad admitted references changed later readers but no output identity or full-sequence score. Its original-source archive and prior conclusions remain unchanged.

The online bridge preserves its actual historical source, including an inherited `jev-1.13.0` metadata field and Jev-style questions in the DeepSeek user payload. The **outer HTTP model was `deepseek-flash`**. These inherited fields are a documented prompt-design limitation of this DeepSeek run, not evidence of a Jev API call or a Jev experiment in this repository. The Jev evaluation remains stopped.
