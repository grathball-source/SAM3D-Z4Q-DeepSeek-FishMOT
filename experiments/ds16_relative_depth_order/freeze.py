"""One fixed order experiment; all older tracked experiments remain immutable."""
from common import *
import subprocess

def main():
    assert read(HERE/'PREFIX_CHECKS.json')['status']=='PASS'
    assert read(HERE/'CHECKS.json')['status']=='PASS'
    paths=subprocess.check_output(['git','ls-files','experiments','online','offline'],cwd=ROOT,text=True).splitlines()
    old={p:sha(ROOT/p) for p in paths if not p.startswith('experiments/ds16_relative_depth_order/')}
    write_new(HERE/'OLD_READONLY_LOCK.json',dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),count=len(old),files=old))
    write_new(HERE/'EFFECTIVE_RUNTIME.json',dict(status='FIXED_BEFORE_FORMAL_PREDICTIONS',arms=list(ARMS),
        segments=SEGMENTS,frames=20098,scientific_strategy=read(HERE/'STRATEGY.json'),
        original_config=read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'),
        runtime_order_parameters={k:read(HERE/'CONFIG.json')[k] for k in (
            'raw_scale_floor_mm','max_raw_scale_mm','min_points','min_fraction','history_frames',
            'fit_observations','signal_fraction','minimum_joint_odds','depth_diffusion_min_increments','birth_max_gap_seconds')},
        measurement='DS14 immutable original raw source-bound adaptive core; no new extraction or restored depth',
        local_parallel=3,threads=1,GT_before_all_seals=False,model_http=0,cost_usd=0))
    import runner
    runner.freeze_inputs(RUN)
    print('FROZEN six arms20098frames; protected oldfiles',len(old))

if __name__=='__main__':main()
