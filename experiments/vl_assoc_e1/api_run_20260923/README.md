# E1 authorized execution

This directory records the user's new explicit paid-call authorization for the already frozen `VL_ASSOC_E1` inputs. The `allow_api=true` overlay is `RUN_AUTHORIZATION.json`; original `CONFIG.json`, `API_AUTHORIZATION.json`, packets, prompt and `FREEZE.json` remain the preauthorization immutable snapshot. The execution code validates all 235 frozen files and the overlay's freeze hash before any call. Runtime keys arrive through an ephemeral owner-only FIFO, are never logged or committed, and are removed after reading.

Run order: two non-research technical smoke requests (schema, then actual image transport) followed by at most 120 formal calls in `CALL_SCHEDULE.json` order, only if smoke passes. Public `requests/` stores payload/image hashes and metadata, not image base64. Complete wire requests and raw server image files stay under ignored `private_api/` on the execution host. `responses/` and `CALL_LEDGER.jsonl` preserve all attempts, including invalid or failed requests; no semantic retry or best-repeat selection. `DECISIONS_SEALED.json` is written only after the full formal schedule completes. An independent scorer may read E1 GT only after that seal.

The hard reservation gate is $5 and 122 total attempts. Every attempt consumes a slot, even on transport failure; a missing usage record is charged its reserved upper estimate. E2 is out of scope.
