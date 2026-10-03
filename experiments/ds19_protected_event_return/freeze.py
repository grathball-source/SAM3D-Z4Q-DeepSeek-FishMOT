"""Freeze one DS19 trial; all prior tracked science and sealed records remain read-only."""
from common import *
import subprocess


def main():
    for filename in ('CHECKS.json','CACHE_CHECKS.json','PREFIX_CHECKS.json','REAL_PREFIX_SOURCE_CHECKS.json'):
        proof=read(HERE/filename)
        assert proof['status']=='PASS',(filename,proof['status'])
        for path,digest in proof.get('actual_test_sources',{}).items():
            assert sha(path)==digest,path
    paths=subprocess.check_output(['git','ls-files','experiments','online','offline'],cwd=ROOT,text=True).splitlines()
    old={p:sha(ROOT/p) for p in paths if not p.startswith('experiments/ds19_protected_event_return/')}
    write_new(HERE/'OLD_READONLY_LOCK.json',dict(base_commit=subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),count=len(old),files=old))
    import runner
    config=read(runner.CONFIG_PATH)
    baseline=runner.EventBridge(config,local_return=False)
    treatment=runner.EventBridge(config,local_return=True)
    assert baseline.engine.birth_config==treatment.engine.birth_config
    actual_order=runner.order_choice.__globals__['CFG']
    old_order=read(DS18/'CONFIG.json')
    labels={'trial','arms','single_change','target'}
    assert {k:v for k,v in actual_order.items() if k not in labels}=={k:v for k,v in old_order.items() if k not in labels}
    from mixed_depth import PARAMETERS
    write_new(HERE/'EFFECTIVE_RUNTIME.json',dict(status='FIXED_BEFORE_FORMAL_PREDICTIONS',
        arms=list(ARMS),new_event_state_arms=list(EVENT_ARMS),segments=SEGMENTS,frames=20098,
        scientific_strategy=read(HERE/'STRATEGY.json'),original_config=config,
        actual_birth_config=baseline.engine.birth_config,
        actual_birth_enabled=baseline.engine.birth_enabled,actual_S0_order_config=actual_order,
        actual_mixed_measurement_parameters=PARAMETERS,
        actual_event_max_episode_seconds=read(runner.EVENT_CONFIG)['max_episode_seconds'],
        depth_effective_invariance='Original D1/Birth/S0 formulas, candidate parameters and exact same sealed per-frame three-ROI facts',
        descriptive_CONFIG_birth_notes_do_not_override_actual_loop_constants=True,
        local_parallel=6,threads=1,cache='SEALED_DS18_THREE_ROI; ALL_PARTS_HASHED; EACH_ROW_BOUND_TO_ORIGINAL_LEDGER_MASK_AND_SCALAR',
        GT_before_all_seals=False,model_http=0,cost_usd=0))
    runner.freeze_inputs(RUN)
    print('FROZEN four event states20098frames plus native/original controls; protected oldfiles',len(old))


if __name__=='__main__':main()
