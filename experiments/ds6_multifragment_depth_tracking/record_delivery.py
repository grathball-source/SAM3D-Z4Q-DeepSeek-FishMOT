"""Record inspected figures, execution exits and reproduction instructions."""
from common import HERE,RUN,read,write_new,artifact,sha

def main():
    visuals=read(HERE/'VISUALIZATION_INVENTORY.json')
    write_new(HERE/'VISUALIZATION_INSPECTION.json',dict(
        status='ALL_FOUR_RAW_DEPTH_QA_IMAGES_ACTUALLY_VIEWED_BY_ROOT',
        files=visuals['private_raw_depth'],
        observations=[
            'F398 actual source masks/public IDs and selected samples visible; empty holes remain empty',
            'F764 residual native118 public100 and disjoint source regions retained; single qualified graph piece is not ownership truth',
            'F1239 second source no qualified samples; blank histogram explicitly has zero qualified pieces',
            'F1821 two qualified raw-value modes near823/1138mm retained, not replaced by largest mode'],
        private_pixels_uploaded=False,no_rgb_used=True,no_gt_raster_used=True))
    write_new(HERE/'EXECUTION_LOG.json',dict(
        date_client='2026-09-30',base='ced663d97cadc23138c538f5784df7ed4e835fe2',
        preflight_exit=0,unit_tests=16,scoring_tests=11,
        initial_slice_exit=1,initial_slice_frames=0,
        initial_slice_failure='RGB directory substring matched depth_rgb; no FREEZE/measurement created; original log preserved',
        successful_slice_exit=0,successful_slice_first_legal_q=415,successful_slice_local_q=65,
        full_prediction_exit=0,formal_frames=1471,formal_branch_rows=7355,formal_objects=39208,
        independent_score_exit=0,
        first_postrun_exit=1,first_postrun_failure='NO_NUMERIC_PAIR early return has no joint_available; reporting helper KeyError only',
        final_postrun_exit=0,
        frozen_trial_code_unchanged_after_successful_slice=True,
        original_and_sealed_predictions_unchanged=True,
        bookkeeping_repair='postrun .get(false) preserves two NO_NUMERIC_PAIR cases instead of deleting them; frozen trial/scorer unchanged',
        model_http=0,smoke_http=0,training=0,sam3_inference=0,depth_service=0,cost_usd=0,
        server_used=False,
        actual_loop_seconds=sum(read(RUN/name/'public/RUN_SUMMARY.json')['elapsed_seconds']
                                for name in read(RUN/'ALL_PREDICTIONS_SEALED.json')['seals']),
        bound_logs=[artifact(HERE/name) for name in (
            'SLICE_LOG.txt','SLICE_FINAL_LOG.txt','RUN_LOG.txt','SCORE_LOG.txt',
            'POSTRUN_LOG.txt','POSTRUN_FINAL_LOG.txt','FAILURE_ANALYSIS_LOG.txt')]))
    text="""# DS6 complete multi-fragment depth tracking

Read PLAN.md and CONFIG.json. 1471 exposed SOURCE_OLD frames, all four original
segments, five actual independent tracking branches. This is a complete
performance trial, not blind validation. No model/API/key/training/SAM3 or
completion service; raw depth only.

Existing local Python: E:/researchsoftware/anaconda3/envs/D-MOT/python.exe.
Existing pycocotools/TrackEval dependency path is listed in ENVIRONMENT.
Use OMP/OPENBLAS/MKL/NUMEXPR=1, CUDA_VISIBLE_DEVICES empty. launch.py sets these
and one OpenCV thread. No install/server is required.

Reproduce into a fresh sibling checkout/output directory with the recorded
source paths and private caches, retaining DS1-DS5 parent layout. Never run
into completed seals or delete old output to rerun:
1. preflight.py (old byte lock/runtime constants)
2. tests.py, score_checks.py
3. launch.py slice (real first split, no GT)
4. launch.py full (1471 frames/five branches/all seals)
5. evaluate.py (all seals/legacy exact checks before manual references)
6. postrun.py and failure_analysis.py (postscore coverage/actual QA/causal facts)

The source path guard's initial substring failure and its correction are
preserved. Final guards record actual depth_mm/source_index field access and
block RGB/manual/v3/network calls during prediction. Old original core and
geometry outputs exactly reproduce all1471 frames, and F6 selector reproduces
all28382 old DS4 objects. No old responses/seals/state are reused as a new trial.

D4/D5 share the history/gate rules but own actual state. D5's scalar shadow
compares the q representation on exactly the same branch state.
Physical surface labels and depth-mm calibration are UNKNOWN.
First accepted mappings, actual COMMIT/no-change/fallback, first-public
unscorable outcomes and every official CLEAR switch are kept separately.
See RESULTS.md, METRICS, CAUSAL_EVIDENCE_ANALYSIS and three POSTRUN reviews.

The four raw-depth/mask QA figures were actually viewed. Public PERFORMANCE.svg
is numerical only. Private original raster/RLE/GT label files and QA remain
local; RESTRICTED_INVENTORY gives actual paths/bytes/SHA and dependencies.
All code/config/checks/logs/public predictions/results/report and figures are
normally pushed to main with actual remote byte proof. Remote proof is an
append-only follow-up commit; no force push or old archive changes.
"""
    with (HERE/'README.md').open('x',encoding='utf-8',newline='\n') as handle:handle.write(text)
if __name__=='__main__':main()

