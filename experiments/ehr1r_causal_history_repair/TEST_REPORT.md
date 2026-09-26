# Source and execution checks

The source-host tests ran with `/home/data2/xiongxiong/dmot-annotation/env/bin/python`, without a model answer or GT:

| Check | Result |
| --- | --- |
| Actual old EHR-1 packets independently reread | B01 A/B reject (21/4 contact), B02 A/B reject (30/30 contact plus old anchor), B04-A reject (22 contact); B03/B05 remain recorded |
| Tampered packet risk flag | Rejected from original observation stream |
| One bad frame between clean islands | Rejected; no fit across contact/gap |
| New pre and post segments | All five cases source-connected, clean and at or before q |
| Anonymous event coverage | Every source observation in the bounded windows belongs to a named clean fragment or an anonymous event record |
| Image binding | 55 actual images; ROI/dimensions/time/hash/endpoint boxes verified |
| Raw depth parity | 727 new frames, 4332 mask profiles rechecked against raw HDF5, predicted masks, synchronized features and sampled original RGB dimensions |
| Condition pairing | 25 requests; H-D/repeat identical, permutation candidate-only, H-2D/H-D identical after removing depth, E event-free |
| Numeric comparator | B05 and synthetic one-edge missing-depth cases use symmetric H2D fallback; short B01-A and B05-Y fragments return UNKNOWN motion |
| v5 budget | 26-request peak reserve USD 2.782218 under USD 3 cap, using actual payload lengths, 1024 tokens per image and full output allowance |
| v5 missing quality regression | **FAIL after request freeze**: 15 H-D logical packets omitted anonymous event `sensor_available`, `synchronized`, core n/MAD and related quality. Preflight missed it and the batch stopped. |
| Corrected unsent package | All five source checks, 727 frames, 4332 profiles, 25 logical requests and explicit missing-quality rejection pass; reserve USD 2.968511. Zero model calls. |
| Repair diff | 10 E/H-2D texts byte-identical, 15 H-D texts differ only by eight added anonymous depth-quality columns; all references and images unchanged |

The v5 regression suite passed but did not test complete anonymous depth quality. The revised suite also rejects a missing quality column, a source version change and a time discontinuity; the corrected package passed. Both depth runs printed `DEPTH_AUDIT_PASS 727 4332`. `PREFLIGHT.json`, `OLD_PACKET_REJECTION.json`, `INPUT_CONTRACT_CHECKS.json`, `DEPTH_INPUT_AUDIT.json`, and `SOURCE_FAILURE_AUDIT.json` hold machine-readable details. A passing v5 audit is retained as evidence of the original checker gap, not as proof of a valid trial.
