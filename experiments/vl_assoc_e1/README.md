# VL_ASSOC_E1 server experiment

Execution host: the authorized laboratory server in a separate checkout. This branch starts at `a566dc6d606ab77696f08f5490486d6f541ebe15`. Original online/offline studies and the sealed-run side directory are read-only. The experiment uses the existing observation, depth, appearance, RGB and predicted-mask streams; it does not rerun SAM3.

Run order: `replay_original.py` → `r0_checks.py` → `r0_score_audit.py` (independent post-seal GT audit) → `asset_inventory.py` → `event_probe.py` for both splits → `build_packets.py` for both splits → `e1_protocol.py` → `finalize_requests.py` → `sanitize_packets.py` → `preflight_e1.py`. The final V4 event probe and 120 manifests are frozen in `FREEZE.json`. E1 preparation and preflight read no GT and have no API transport. `r0_score_audit.py` is a separate process and only scores the already sealed historical R0 predictions. See `PLAN.md`, `PROTOCOL_DIFF.md` and `CONFIG.json` for the registered E1 choices. Image sheets are private server files under `images/` and excluded from Git.

No GPU is needed for this preparation. Do not launch E2 or resume Jev. Before any later job, recheck server resources and the current task status. `API_AUTHORIZATION.json` is false; a key on the server does not authorize calls.

The earlier `EVENT_PROBE*` and `TEST_REPORT*` files are preserved prefreeze development records; V4 and `TEST_REPORT_FINAL.json` are the final inputs/checks. No E1 model request or GT scoring has occurred. Public `EVENT_RESULTS.json` lists B0/N choices and pending model arms, not correctness. The 48 real RGB sheets remain on the execution host; their hashes and row provenance are frozen, but image bytes are not published.
