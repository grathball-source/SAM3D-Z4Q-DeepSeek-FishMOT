# E1C-A recovery audit (stopped)

Fixed review base: `12c6dcf60df86deedc71c719b867d56e8ab53838`. This directory belongs to the independent `codex/vl-assoc-e1c-recovery` branch. Start at [RESULTS.md](RESULTS.md), then [EVENT_FUNNEL.md](EVENT_FUNNEL.md) and [HANDOFF.md](HANDOFF.md). Old E1 sealed outputs and old conclusions are read-only.

`allow_api=false`. No new or old-model API call, no test GT, no E1C-B or E2. Prediction-only candidates were frozen in `EXPOSURE_MANIFEST.json` before `score_exposed.py` opened the *already exposed* development/validation GT. The stage failed the candidate cap and found no confirmed correct executable recovery; the failed probe remains archived rather than retuned after scoring. Source RGB, masks, depth, appearance, old wire and exposed GT were present on the actual lab server. Private image/wire bytes are not committed.
