"""One fixed order experiment; all older tracked experiments remain immutable."""
from common import *
import subprocess

def main():
    assert read(HERE/'PREFIX_CHECKS.json')['status']=='PASS'
    assert read(HERE/'CHECKS.json')['status']=='PASS'
    assert read(HERE/'CHECKS_R5.json')['status']=='PASS'
    for p,digest in read(HERE/'CHECKS_R5.json')['actual_test_sources'].items():assert sha(p)==digest,p
    assert read(HERE/'IMMUTABLE_EQUIVALENCE.json')['status']=='PASS'
    assert read(HERE/'IMMUTABLE_RECORD_EQUIVALENCE.json')['status']=='PASS'
    for proof in ('IMMUTABLE_RECORDS_REVIEW.json','IMMUTABLE_RECORD_PROFILE.json'):
        for filename in ('controller.py','mixed_depth.py'):
            assert read(HERE/proof)['current_sources'][filename]['sha256']==sha(HERE/filename)
    assert read(HERE/'REAL_SLICE_CHECKS.json')['status']=='PASS'
    assert read(HERE/'REAL_SLICE_SOURCE_SCORER.json')['status']=='PASS'
    assert read(HERE/'SCORER_CONTRACT_FINAL_CHECKS.json')['status']=='PASS'
    assert read(HERE/'SCORER_CONTRACT_FINAL_CHECKS.json')['current_score_sha256']==sha(HERE/'score.py')
    paths=subprocess.check_output(['git','ls-files','experiments','online','offline'],cwd=ROOT,text=True).splitlines()
    old={p:sha(ROOT/p) for p in paths if not p.startswith('experiments/ds18_association_evidence_interface_repair/')}
    write_new(HERE/'OLD_READONLY_LOCK.json',dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),count=len(old),files=old))
    write_new(HERE/'EFFECTIVE_RUNTIME.json',dict(status='FIXED_BEFORE_FORMAL_PREDICTIONS',arms=list(ARMS),
        segments=SEGMENTS,frames=20098,scientific_strategy=read(HERE/'STRATEGY.json'),
        original_config=read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'),
        runtime_order_parameters={k:read(HERE/'CONFIG.json')[k] for k in (
            'raw_scale_floor_mm','max_raw_scale_mm','min_points','min_fraction','history_frames',
            'fit_observations','signal_fraction','minimum_joint_odds','depth_diffusion_min_increments','birth_max_gap_seconds')},
        measurement='DS14 original whole/fixed-core/adaptive-core scalars with corresponding separately certified ROI/source populations; no restored depth',
        local_parallel=6,threads=1,segment_schedule='LW,L3,development,validation,feeding; source work only; no sample or event changes',GT_before_all_seals=False,model_http=0,cost_usd=0))
    import runner
    runner.freeze_inputs(RUN)
    print('FROZEN six arms20098frames; protected oldfiles',len(old))

if __name__=='__main__':main()
