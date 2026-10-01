"""Reuse the completed replay without changing any earlier experiment."""
from pathlib import Path
import json, hashlib, subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=HERE.parent/'ds10_depth_failure_repair'
assert not (HERE/'run').exists()
for name in ('common.py','controller.py','runner.py','launch.py','execute.py','forecast.py'):
    assert not (HERE/name).exists(),name
    (HERE/name).write_bytes((BASE/name).read_bytes())
arms=('SAM3_NATIVE','F9_RESTORED','R11_RAW','R11_RESTORED')
common=(HERE/'common.py').read_text(encoding='utf-8').replace('DS10 shared paths','DS11 shared paths')
common=common.replace("ARMS=('SAM3_NATIVE', 'F9_RESTORED', 'D10_RAW', 'D10_RESTORED')",'ARMS='+repr(arms))
(HERE/'common.py').write_text(common,encoding='utf-8',newline='\n')
cfg=json.loads((BASE/'CONFIG.json').read_text(encoding='utf-8'))
cfg.update(trial='DS11',arms=list(arms),single_change='Add depth-supported first-ever-native birth reconnection; keep native-first and frozen F9 group decisions',
    birth_max_gap_seconds=12.,birth_min_history_samples=3,birth_min_area=64,
    birth_trigger='FIRST_EVER_NATIVE_IN_SEGMENT; INITIAL_FRAME_RECORDED_NOT_ASSOCIATED',
    birth_depth_support='RAW_SAME_VERSION_CONTIGUOUS_CLEAN_ENDING_AT_LAST_APPEARANCE',
    birth_restored_query_policy='RETAINED_ONLY; INFERRED_RECORDED_COMMON_UNINFORMATIVE_NO_COMMIT',
    birth_prior='UNIFORM_UNIQUE_OLD_PUBLIC_AND_NEW_FISH_DUMMY',
    birth_positive_depth_lr_required=True,birth_max_transaction_edits=2,
    birth_target_claim_policy='REJECT_CURRENT_OCCUPIED_ANY_ALIAS_OR_GROUP_RESERVED_TARGET',
    birth_collision_policy='REJECT_ALL_QUERIES_SHARING_BEST_TARGET; IF_MORE_THAN_TWO_REJECT_BATCH',
    birth_group_policy='NO_BIRTH_STAGE_ON_ANY_ACTIVE_GROUP_FRAME_INCLUDING_Q',
    birth_history_policy='FREEZE_ON_DISAPPEARANCE; NO_WINDOW_STITCHING_OR_CURRENT_POST_IN_PRE',
    target='At least one new correct birth restore and pooled IDF1/HOTA/AssA greater than same-source native; IDSW not increased')
(HERE/'CONFIG.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8',newline='\n')
lock=json.loads((BASE/'OLD_READONLY_LOCK.json').read_text(encoding='utf-8'))
for name in subprocess.check_output(['git','ls-files','experiments/ds10_depth_failure_repair'],cwd=ROOT,text=True).splitlines():
    lock['files'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
lock.update(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),count=len(lock['files']))
(HERE/'OLD_READONLY_LOCK.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8',newline='\n')
(HERE/'ENVIRONMENT.json').write_bytes((BASE/'ENVIRONMENT.json').read_bytes())
print('DS11 scaffold prepared; previous experiment bytes untouched')
