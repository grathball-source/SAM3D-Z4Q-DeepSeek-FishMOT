# Same-information numeric comparator status

The frozen E1 numerical N was active, but `build_packets.py:66-89` used the final history sample and final current sample for D/A and only the final current point for M. Its temporal model arm received more current-short-segment information. That is a determined **information-parity failure**; old N's 18/19 correct choices cannot be read as a controlled temporal-model comparison.

`contract.py:29-66` computes D/A/M medians over all eligible causal history/current samples and a history-to-current motion fit. `contract.py:141-180` ranks the same complete candidates presented to a model, with explicit missing-modality treatment, an ex ante null-association cost and four outcomes: `UNIQUE_KEEP`, `TIE_KEEP`, `NO_EVIDENCE_KEEP`, `CHANGE`. The null cost is a **new research assumption**, not calibrated from GT. Synthetic checks passed for active change, a depth/appearance conflict tie, and missing-data fallback; see `EVIDENCE_CONTRACT_TESTS.json`.

No real E1C packet was frozen under the compliant two-tracklet/lineage/visual contract and no real paired E1C N-versus-model score exists. The current A stage therefore **does not** establish the numerical baseline's effectiveness or model advantage.
