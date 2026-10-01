"""One-time DS12 scaffold; old DS11 and all prior seals stay byte immutable."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=HERE.parent/'ds11_depth_birth_reconnect'
assert not (HERE/'run').exists()
copies=('common.py','controller.py','controller_tests.py','birth_memory.py','runner.py',
    'launch.py','execute.py','forecast.py','forecast_tests.py','input_contract.py','preflight.py',
    'freeze_review.py','postseal_delivery.py','postseal_manifest.py','verify_remote.py')
for name in copies:
    assert not (HERE/name).exists(),name
    text=(BASE/name).read_text(encoding='utf8').replace('DS11','DS12').replace('ds11','ds12')
    text=text.replace('R11_RAW','R12_RAW').replace('R11_RESTORED','R12_RESTORED')
    (HERE/name).write_text(text,encoding='utf8',newline='\n')
config=json.loads((BASE/'CONFIG.json').read_text(encoding='utf8'))
config.update(trial='DS12',arms=['SAM3_NATIVE','F9_RESTORED','R12_RAW','R12_RESTORED'],
    single_change='Current contact exclusive measurement certificate admission; past history and frozen F9 unchanged',
    contact_component_policy='ALL_ACTUAL_ADAPTIVE_CORE_8_CONNECTED_PIECES_REPORTED; EQUAL_WEIGHT_QUALIFIED_COMPONENTS',
    contact_measured_support='RAW_SENSOR_OR_V2_RETAINED_ONLY; UNIQUE_SENSOR_SOURCES_AND_EXCLUSIVE_MASK_CORE',
    contact_identity_qualification='MEASUREMENT_PROVENANCE_ONLY; PHYSICAL_SURFACE_AND_BACKGROUND_UNKNOWN',
    contact_missing_policy='COMMON_QUERY_UNINFORMATIVE; NO_COMMIT',
    contact_stage_policy='KEEP_REAL_NEIGHBORS_RISK_CLASS; ATOMIC_RECHECK_CERTIFICATE_AND_BANK; NO_GROUP_BYPASS',
    birth_group_policy='NO_BIRTH_STAGE_ON_ANY_ACTIVE_GROUP_FRAME_INCLUDING_Q')
(HERE/'CONFIG.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf8',newline='\n')
lock=json.loads((BASE/'OLD_READONLY_LOCK.json').read_text(encoding='utf8'))
for name in subprocess.check_output(['git','ls-files','experiments/ds11_depth_birth_reconnect'],cwd=ROOT,text=True).splitlines():
    lock['files'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
lock.update(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),count=len(lock['files']))
(HERE/'OLD_READONLY_LOCK.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf8',newline='\n')
print('DS12 scaffold prepared; previous tracked artifacts byte locked',lock['count'])
