# NE-1: native-first event association

Fixed review base: `da085bab0d6e486aab135262593881773484c587`. This is a new architecture ablation on the exposed FEEDING development source, not a general Z4Q repair or blind test. It reuses the exact `SOURCE_OLD` saved SAM3 batches, 405 original frames (0–199 and 351–555), original aligned `depth_mm`, prediction-only V4 scanner, S0-P protection/publication, event packet, numeric weights, and official DeepSeek Files route. Each segment starts from empty state. The saved SAM3 batches do not establish a continuous online SAM3 session.

## Branches and identity rule

- `SAM3_NATIVE`: original saved native IDs and masks.
- `Z4Q_FROZEN`: original frozen Bridge and controller, with full real action trace.
- `EVENT_NUM`: native-first controller and unchanged S0-P event flow; S0 uses the frozen numerical pair rule.
- `EVENT_VLM`: same controller and event flow; earliest eight confirmed events by global SOURCE_OLD time may receive one M and, if legal, one S0 DeepSeek call. S0 H1/H2 replaces only the pair selection. Invalid/DEFER/unsent uses the current VLM branch's numeric/local fallback.

`ne_controller.py` subclasses the original PX hook-compatible copy of the frozen Z4Q controller and rejects **both** D1_DELAYED and BIRTH_REFINE candidate edges before either assignment matrix can accept them. PX/PX-A co-visibility logic is not installed. Measurement updates, quality, depth and motion histories, native-return conflict handling, existing event alias lifecycle, group protection and local fallback continue. The group bridge is explicitly injected with this controller; `enabled=False` and output-only relabeling are not used.

One frame is published once, after S0 choice and transaction. The packet at q contains only evidence through q. Group/residual observations remain present, one public ID per mask. No RGB appearance, repaired v3 depth, GT selection, new SAM3 run, training, old response reuse, retry, voting or prompt adjustment is part of this run.

## Reproduction and records

Use `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe` from the repository root, and the exact restricted source paths/hashes in `RESTRICTED_INVENTORY.json`. These commands create exclusive output directories and must be directed to fresh locations for repetition; the checked-in `run/` and earlier experiment seals are read-only.

1. `python experiments/ne1_native_first_event_association/test_ne.py -v`
2. `python experiments/ne1_native_first_event_association/replay.py preflight` constructs causal packets with zero HTTP using the numeric shadow path. This checked-in preflight was run before the formal calls.
3. `python experiments/ne1_native_first_event_association/replay.py real` freezes code/config/source manifests, replays all branches and seals both predictions; it requires a separately authorized and configured `DEEPSEEK_API_KEY` and has a 16 chat request, USD 4 runtime cap.
4. `python experiments/ne1_native_first_event_association/verify.py` checks actual body/START/response/END/seal, exact frozen output, source input hashes and first publication without opening GT.
5. `python experiments/ne1_native_first_event_association/score.py run`, then `postseal.py`, `visualize.py` for GT metrics/physical audit/switches and geometry-only sheets.

`run/*/public` contains packet text, response summaries, action trace, publication and cost ledgers, predictions and seals. `run/*/private_api` contains raw provider responses and file IDs; `run/*/private_source` contains geometry PNGs. These two directories are deliberately Git-ignored and inventoried by absolute path, byte count and SHA-256. Source observations/profiles/assignments and GT labels remain in the existing private FEEDING location; no raster or credential is committed. The public SVG sheets show actual prediction boxes and published ID labels only, not image pixels.

The first preliminary `dry/` stopped before a seal because the frozen Z4Q event trace lacked an explicit `origin_rule` on some old reconnect events. `dry_v2/` completed after the trace-only classification was corrected and is a no-HTTP numerical diagnostic. Neither is a model result. The formal `run/` has independent new requests and responses.

Current [final report](FINAL_REVIEW.md) gives the actual result and limits. The same-source comparison is with `SAM3_NATIVE` and with `EVENT_NUM`; beating only `Z4Q_FROZEN` is insufficient.
