# Frozen diagnostic construction

The first source/ROI/future and visual-selection checks passed before freeze. Static independent review then added stricter packet/frame binding and caught a local variable that could point the BEGIN record at the wrong freeze metadata, plus a missing per-object profile-frame assertion. Source frame is now bound from the actual original profile-row container and checked explicitly. The original CHECKS output is preserved as CHECKS_ATTEMPT1.json, with its real stdout/stderr/exit in EXECUTION_LOG; it does not certify later code.

Run the directly relevant updated semantic checks once, verify their actual code/source hashes and only then freeze. No labels were used to change a measurement formula, screen threshold, candidate, anchor or action. The full audit has not run at this construction stage. There is no prediction replay or API request.
