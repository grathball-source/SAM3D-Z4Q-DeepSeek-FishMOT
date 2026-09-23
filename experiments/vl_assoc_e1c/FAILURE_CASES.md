# Four retained old E1 harms

These are the **previously scored, exposed** old E1 events, not new E1C success examples. Source: old `api_rerun_20260923_default64k/EVENT_RESULTS.json`, `DECISIONS.jsonl`, `responses/`, and four real temporal sheets verified in `PRIVATE_VISUAL_QA.json`.

| Packet / split, query | Saved result | What the case rules out |
| --- | --- | --- |
| `P4218132a1659f1e2`, development 8069, F31–F35 | B0/N C2 correct; L-T, static, temporal, repeat and permutation all chose wrong C1. Historical A has only frame 7866, B has 7880/85/90. | Repeated agreement is not correctness. Sparse asymmetric reference history and nearby fish remain hazards. |
| `P04c303d9612421d6`, validation 377, F67/F69/F70 | B0/N C2 correct; temporal F67 wrong C1, repeat and permutation C2. | A single visually prompted change is unstable; elongated crops and neighbors complicate interpretation. |
| `P175d295a01799fe5`, validation 2638, F76–F80 | B0 C2 correct; active N and T/static/temporal/repeat wrong C1. F80 selected C2 but failed the 80-character reason rule, so fallback kept B0. | Numerical and model agreement can be jointly wrong; format fallback must not be called semantic rescue. Blue light and other fish appear in the actual sheet. |
| `P1797ad89bd359331`, validation 2580, F81–F85 | B0/N C1 correct; T/static/temporal/repeat/permutation all wrong C2. | Alias/repeat invariance can preserve the same false association. Flash and neighboring fish enter the visual evidence. |

All four old harmful cases stay in every future hard-negative challenge if one is ever separately authorized. Their visual review is limited to the old crop sheets, not proof of true fish identity from pixels.
