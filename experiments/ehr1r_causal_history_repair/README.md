# EHR-1R causal event-history repair

Fixed review base: `869d9812a6549307e8e4502d1ee17d6881494626`. The original EHR-1 remains `ENGINEERING_FAILURE_STOP`; its five B01 `DEFER` answers and 20 unsent bodies are excluded from this experiment.

**Outcome: `ENGINEERING_FAILURE_STOP`.** The v5 sender froze 25 new bodies, but a later check found missing quality fields for anonymous event depth in all 15 H-D logical packets. One smoke and seven formal calls returned, one formal HTTP outcome is unknown after stopping, and 17 formal requests were never sent. The returned choices are diagnostic raw records, not a valid paired trial. `corrected_unsent/` contains a repaired, independently checked 25-request logical package; it has zero calls and is never combined with v5 answers.

This directory contains the source-backed packets, independent old-packet rejection, raw depth audits, both preparation versions, numeric endpoint-history references, call ledger, partial seal, postseal reference-semantic diagnostic, and final review. Restricted RGB/mask images, provider file IDs, raw wire, and GT raster stay on the authorized host. The v5 sender consumed only its `PLAN.json`, image media, and a digest-bound gate; it had no answer key or repository mount.

Read `PROTOCOL.md`, `IMPLEMENTATION_DIFF.md`, `TEST_REPORT.md`, `FINAL_REVIEW.md`, and `ARTIFACT_MANIFEST.json` before interpreting any raw model choice. Exact execution state and source paths are in `EXECUTION_LOG.md`.
