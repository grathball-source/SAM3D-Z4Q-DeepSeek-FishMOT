"""DS20 metadata only; preserve all DS19 scientific depth constants."""
import json, hashlib, platform, subprocess, sys, shutil
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS19 = ROOT / 'experiments/ds19_protected_event_return'


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write(filename, value):
    with (HERE / filename).open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def main():
    old = json.loads((DS19 / 'CONFIG.json').read_text(encoding='utf-8'))
    new = dict(old, trial='DS20', single_change='ISOLATE_EVENT_EDGE_AND_ORDINARY_CONFIRMATIONS',
               arms=['SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_RETURN','ACTIVITY_ISOLATED','MIXED_RETURN','MIXED_ISOLATED'])
    assert all(new[key] == value for key, value in old.items() if key not in ('trial','single_change','arms'))
    write('CONFIG.json', new)
    write('STRATEGY.json', dict(status='DESIGN_BEFORE_NEW_PREDICTIONS',
        authorized_by='Human: 开始; execute sole DS19 NEXT_STEP_PLAN',
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        source='DS14 original raw same source; DS18 sealed current-frame measurement cache',
        variables={'only_changed':'event edge confirmation state isolated from ordinary pending',
                   'fixed':'depth measurements/quality/ordinal/2D/trigger/q/reference/masks/weights/timing'},
        physics={'physical_single_fish':'UNKNOWN','surface_layers_are_identities':False},
        cache_sha_dependencies='All actual DS18 sealed cache parts and row/source/ROI/scalar/mask bindings',
        config_note='CONFIG inherited fields include historical descriptive policy; actual effective constants from engine and original frozen configurations are recorded separately',
        protocol='Original D1 candidate matrix, natural confirmations and local atomic return; event/source/identity generation plus exact anchor/target distinguish private counters',
        prediction_before_reference=True,new_model_http=0,smoke=0,training=0,sam3=0,completion_service=0,cost_usd=0,
        primary_rule='MIXED_ISOLATED vs native/original Z4Q, matching archived MIXED_RETURN and same-base ACTIVITY_ISOLATED; no retrospective best arm selection',
        no_result_conditioned_retuning=True,sole_plan_sha256=sha(DS19/'NEXT_STEP_PLAN.md')))
    write('CONFIG_INHERITANCE.json', dict(status='ONLY_TRIAL_ARM_NAMES_AND_SINGLE_CHANGE_DESCRIPTION_DIFFER',
        parent_config={'path':str(DS19/'CONFIG.json'),'bytes':(DS19/'CONFIG.json').stat().st_size,'sha256':sha(DS19/'CONFIG.json')},
        changed_keys=['trial','arms','single_change'],all_depth_and_numeric_configuration_fields_identical=True))
    disk = shutil.disk_usage(ROOT)
    write('ENVIRONMENT_INITIAL.json', dict(checked_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.executable,python_version=platform.python_version(),platform=platform.platform(),
        disk_free_bytes=disk.free,disk_total_bytes=disk.total,model_http=0,cost_usd=0,
        execution_environment='LOCAL_CPU_ONLY; no laboratory server/GPU jobs',maximum_jobs=6,threads_per_job=1))
    print('DS20 initialized; DS19 numeric/depth CONFIG unchanged')


if __name__ == '__main__':
    main()
