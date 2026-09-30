# DS4 source-quality/background-noise repair

User-authorized failure review and a new measurement-only experiment. DS3 stays
read-only. See PLAN.md, CONFIG.json and independent SOURCE_AUDIT,
COMPONENT_AUDIT/EVALUATION_REVIEW. Same exposed1066 SOURCE_OLD frames; no new
tracker/API/GT pixels in public output. Model HTTP/smoke/cost0.

source_audit.py traces F766 to original BAG/native pixels and exact reprojection.
component_audit.py traces all original component/geometry/noise-floor failures.
bootstrap.py reuses frozen helpers. selector.py separates background floor from
unchanged foreground scale. runner.py will recompute raw whole/core/DS3 and all
new controlled arms, seal them, then score.py computes fixed-population proxies.
checks.py and score_checks.py are directly runnable.

Interpreter E:/researchsoftware/anaconda3/envs/D-MOT/python.exe; existing local
NumPy/OpenCV/pycocotools/Matplotlib only. Run checks, runner, score and reporting
in order, in a fresh output directory/check-out. All outputs refuse overwrite.
Reproduction requires original depth_mm/source_index NPZ and native NPY, saved
SAM3 polygons, frozen DS2/DS3 derived masks and postseal authorized manual polygons.
No instance_id, restored/v3, RGB or future input is read by the measurement run.

After scoring: report_artifacts.py emits only numeric SVG publicly and real
raw-depth QA privately; finalize.py is postscore reporting/inventory only.
RESULTS.md is the complete failure review and actual controlled result, with
individual rows in the two *_occupancy.jsonl.gz files. Formal runtime/ref proof
is separate from prior DS3; no old score, mask, seal or response is overwritten.

Safe read-only revalidation: python -B -m unittest checks score_checks;
python -B -c "import score; score.check_seal()" verifies code, sources and seals.
The original output directory refuses a second run. Full regeneration requires
a fresh sibling copy of code/config/plan and review/audit proofs (without old
generated FREEZE, inventories, measurements or scored outputs), retaining the
repository-relative parent layout and original source dependencies. Record its
new paths and hashes; this run remains immutable. SOURCE_AUDIT gives raw BAG
slice binding and the previously recorded full-BAG hash; it did not rehash the
entire recording. A review-status/launcher schema mismatch before FREEZE is
preserved in PRE_FREEZE_ATTEMPT_LOG/PREFREEZE_REPAIR.
