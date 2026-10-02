# Prefreeze review resolutions

The independent implementation review identified a three-point versus five-point automatic-edge history discrepancy. The operative `HybridReturn.auto_min_history` now reads the original Z4Q `min_history_count=5`. The actual `bind_depth` test rejects three and four observations and admits five; no observation was manually qualified.

Accepted preview candidates are separated from first-published and durable alias commits. Reconnect telemetry reads the original event's `canonical_id`. Tests cover adopted, publication-reverted, and explicitly overridden candidates. A test-only import collision was corrected with an explicit local module path. Failed and successful technical test logs remain preserved; no formal replay had started during these fixes.

Verified logs: `test_group.txt` (seven group admission checks), `check_prefix.txt` (150 real frames; native and old R12 exact; five-arm mask conservation), `test_hybrid_binding.txt` (three/four/five boundary), and `test_hybrid_adoption_verified.txt` (candidate and commit distinction plus all hybrid state checks).

Known tradeoff before observing new full results: the old Feeding q545 core fails the existing MAD quality gate. Its archived correct group action is not forced into the new strategy. Old-case plug-in decisions are arithmetic diagnostics, not sequential results of the new reference-retention state.

Formal rules are frozen once `freeze.py` succeeds. No result-dependent threshold search, branch mixing, or repeat selection is authorized by this implementation.
