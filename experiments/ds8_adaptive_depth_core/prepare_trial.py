"""Create one ROI-only trial from immutable DS7; no old prediction is edited."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'ds7_depth_native_recovery'
assert not (HERE/'run').exists()
for name in ('common.py','controller.py','controller_tests.py','association.py',
             'restored_source.py','launch.py'):
    (HERE/name).write_bytes((OLD/name).read_bytes())
cfg=json.loads((OLD/'CONFIG.json').read_text(encoding='utf-8'))
cfg.update(trial='DS8',core_kernel='NOT_USED_BY_P1_P2',
    core_roi='exclusive 8-connected components; distance >= max(1.5,min(3,0.5*component_max_distance))',
    single_change='ROI geometry only versus DS7; D2 retains original 7x7 control')
(HERE/'CONFIG.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
runner=(OLD/'runner.py').read_text(encoding='utf-8')
def replace(old,new):
    global runner
    assert runner.count(old)==1,old
    runner=runner.replace(old,new)
replace('from measurement import measure_restored','from measurement import measure_restored, measure_raw')
replace('"ds7_native_controller"','"ds8_native_controller"')
a=runner.index("CODE = [HERE/n")
b=runner.index("CODE += [DS1/n",a)
runner=runner[:a]+"""CODE = [HERE/n for n in (
 'CONFIG.json','PLAN.md','README.md','runner.py','prepare_trial.py','common.py',
 'controller.py','controller_tests.py','CONTROLLER_CHECKS.json','measurement.py',
 'association.py','restored_source.py','adaptive_core.py','adaptive_tests.py',
 'ADAPTIVE_CHECKS.json','measurement_tests.py','MEASUREMENT_CHECKS.json',
 'REAL_INPUT_CHECKS.json','launch.py','evaluate.py','event_audit.py','score_checks.py',
 'SCORE_CHECKS.json','ENVIRONMENT.json','OLD_READONLY_LOCK.json')]
"""+runner[b:]
replace('restored_full,restored_measured=measure_restored',
        'adaptive_full,adaptive_measured=measure_raw(depth,masks,occupancy,name,frame)\n            restored_full,restored_measured=measure_restored')
replace('objects=measured,restored_full=restored_full',
        'objects=measured,adaptive_raw=adaptive_measured,adaptive_full=adaptive_full,restored_full=restored_full')
replace("state_measured=restored_measured if arm=='P2_RESTORED_DEPTH' else measured",
        "state_measured=(restored_measured if arm=='P2_RESTORED_DEPTH' else adaptive_measured if arm=='P1_RAW_DEPTH' else measured)")
replace("restored_full if arm=='P2_RESTORED_DEPTH' else full",
        "restored_full if arm=='P2_RESTORED_DEPTH' else adaptive_full")
(HERE/'runner.py').write_text(runner,encoding='utf-8',newline='\n')
print('Prepared ROI-only trial')
