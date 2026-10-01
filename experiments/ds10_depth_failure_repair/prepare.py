"""Copy the existing replay; four arms, one depth forecast repair."""
from pathlib import Path
import json,subprocess,hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=HERE.parent/'ds9_joint_h0_depth'
assert not (HERE/'run').exists()
for name in ('common.py','controller.py','controller_tests.py','measurement.py','measurement_tests.py',
             'restored_source.py','adaptive_core.py','adaptive_tests.py','execute.py','launch.py',
             'preflight.py'):
    (HERE/name).write_bytes((OLD/name).read_bytes())
arms=('SAM3_NATIVE','F9_RESTORED','D10_RAW','D10_RESTORED')
common=(HERE/'common.py').read_text(encoding='utf-8').replace('DS9 shared paths','DS10 shared paths')
common=common.replace("ARMS=('SAM3_NATIVE', 'J0_GEOMETRY', 'J1_RAW_DEPTH', 'J2_RESTORED_DEPTH', 'J2_DEPTH_ZERO', 'J2_DEPTH_PERMUTE')",'ARMS='+repr(arms))
(HERE/'common.py').write_text(common,encoding='utf-8',newline='\n')
cfg=json.loads((OLD/'CONFIG.json').read_text(encoding='utf-8'))
cfg.update(trial='DS10',arms=list(arms),single_change='depth forecast repair; same geometry, measurements, trigger/q and state transactions',
           target='Same-source SAM3 native improvement; geometry comparison is not an acceptance gate')
(HERE/'CONFIG.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
r=(OLD/'runner.py').read_text(encoding='utf-8')
r=r.replace('ds9_native_controller','ds10_native_controller')
r=r.replace(" 'CONFIG.json','PLAN.md','README.md','runner.py','prepare_trial.py','common.py',", " 'CONFIG.json','PLAN.md','README.md','runner.py','prepare.py','common.py',")
r=r.replace("'association.py','association_tests.py','ASSOCIATION_CHECKS.json','PREFLIGHT_REVIEW.md'", "'association.py','forecast.py','forecast_tests.py','FORECAST_CHECKS.json','association_tests.py','ASSOCIATION_CHECKS.json','PREFLIGHT_REVIEW.md'")
r=r.replace('from association import choose','from association import choose\n_spec9=importlib.util.spec_from_file_location("ds9_frozen_association",HERE.parent/"ds9_joint_h0_depth/association.py")\n_old9=importlib.util.module_from_spec(_spec9)\n_spec9.loader.exec_module(_old9)')
r=r.replace("state_measured=restored_measured if arm.startswith('J2_') else adaptive_measured", "state_measured=adaptive_measured if arm=='D10_RAW' else restored_measured")
old="""                    mode={'J0_GEOMETRY':'GEOMETRY','J1_RAW_DEPTH':'RAW_DEPTH',
                        'J2_RESTORED_DEPTH':'RESTORED_DEPTH','J2_DEPTH_ZERO':'DEPTH_ZERO',
                        'J2_DEPTH_PERMUTE':'DEPTH_PERMUTE'}[arm]
                    choice,detail=choose(episode,episode['depth_frozen'],state_measured,
                        restored_full if arm.startswith('J2_') else adaptive_full,
                        view['mapping'],mode,name)"""
new="""                    mode='RAW_DEPTH' if arm=='D10_RAW' else 'RESTORED_DEPTH'
                    selector=_old9.choose if arm=='F9_RESTORED' else choose
                    choice,detail=selector(episode,episode['depth_frozen'],state_measured,
                        adaptive_full if arm=='D10_RAW' else restored_full,
                        view['mapping'],mode,name)"""
assert old in r;r=r.replace(old,new)
r=r.replace("arm=='J2_RESTORED_DEPTH'", "arm=='D10_RESTORED'")
r=r.replace('ALL_SIX_BRANCHES_FOUR_SEGMENTS_SEALED','ALL_FOUR_BRANCHES_FOUR_SEGMENTS_SEALED')
r=r.replace("CODE += [DS1/n", "CODE += [HERE.parent/'ds9_joint_h0_depth/association.py',HERE.parent/'ds9_joint_h0_depth/CONFIG.json']\nCODE += [DS1/n")
(HERE/'runner.py').write_text(r,encoding='utf-8',newline='\n')
files=json.loads((OLD/'OLD_READONLY_LOCK.json').read_text(encoding='utf-8'))['files']
tracked=subprocess.check_output(['git','ls-files','experiments/ds9_joint_h0_depth'],cwd=ROOT,text=True).splitlines()
for name in tracked:files[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
lock=dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),count=len(files),files=files)
(HERE/'OLD_READONLY_LOCK.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
(HERE/'ENVIRONMENT.json').write_bytes((OLD/'ENVIRONMENT.json').read_bytes())
print('DS10 four-arm replay scaffold and old read-only lock prepared')
