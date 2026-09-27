# Real API protocol qualification

Two preregistered artificial geometry packets were sent through the official `deepseek-flash` Files API, under the same system contract, thinking/high, JSON mode, canonical parser and physical scorer as formal requests. They are `SYNTHETIC_TEST_ONLY`; they contain no real B01–B05 fish image, private GT or old answer. S01 has visibly distinguishable shapes; S02 has ambiguous identical circles. A wrong fixture choice was diagnostic, while format, references and transport were qualification gates.

| Smoke | Transport/finish | Raw choice | Strict | Normalized | Fact references | Qualification |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | returned / stop | H1 | valid | valid | valid | PASS; synthetic mapping H1 matched fixture |
| S02 | returned / stop | DEFER | invalid | invalid | unassessable under invalid structure | FAIL |

S02's JSON copied schema metadata into the *response object*: top-level `version: EHR-CF-output-v1` and `type: object`. The four required response fields and both `id` assessments were also present, but the frozen target schema has exactly four top-level fields. Removing metadata is not a permitted lossless normalization. The raw DEFER remains a model-proposed abstention; it is **not** a qualified safe event decision. `run/public/API_PROTOCOL_SMOKE.json`, `responses/S01.json`, `responses/S02.json`, `CALL_LEDGER.jsonl` and `PARTIAL_RESPONSES_SEALED.json` retain the exact public evidence.

The second smoke ended at 2026-09-27 09:07:45 UTC. The sender sealed `INTERFACE_QUALIFICATION_FAILURE` and sent **zero** formal requests. No third smoke, retry, prompt edit, or old-response substitution occurred. The next interface requirement is an exact four-key response with two assessment objects and in-packet fact references; any revised instruction must be a separately frozen trial.
