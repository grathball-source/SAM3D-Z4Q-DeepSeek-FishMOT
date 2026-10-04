"""One renderer-contract repair in a fresh directory; never changes v1 bytes."""
import run

def main():
    run.verify_freeze();d=run.old.read(run.HERE/'NUMERIC_REPEAT_DIAGNOSIS.json')
    assert d['numeric_metrics_all_exact_equal'] and d['observed_change_confined_to_unrendered_distance_maps']
    for item in d['diagnostics']:
        assert item['actual_inputs_unchanged']
        for r in item['repeats']:
            for k,v in r['maps'].items():
                if not k.endswith('_distance_px'):assert v['exact_equal']
    target=run.HERE/'attempt2';assert not target.exists();target.mkdir()
    replacements={
        'run.py': [('ROOT = HERE.parents[1]','ROOT = HERE.parents[2]')],
        'spatial.py': [("for key in maps), 'Figure raster mismatch'", "for key in maps if not key.endswith('_distance_px')), 'Figure raster mismatch'")],
        'test_spatial.py':[(".parents[2] / 'experiments/ds20", ".parents[3] / 'experiments/ds20")],
    }
    copied=[]
    for name in ('run.py','spatial.py','checks.py','test_spatial.py','execute.py','review.py','PROJECTION_CHECKS.json','MASK_TIME_CHECKS.json'):
        source=run.HERE/name;data=source.read_text(encoding='utf-8')
        changes=[]
        for before,after in replacements.get(name,[]):
            assert data.count(before)==1,(name,before)
            data=data.replace(before,after);changes.append(dict(before=before,after=after))
        with (target/name).open('x',encoding='utf-8',newline='\n') as f:f.write(data)
        copied.append(dict(source=run.old.artifact(source),target=run.old.artifact(target/name),exact_changes=changes))
    run.save('TECHNICAL_REPAIR.json',dict(status='ONE_NARROW_RENDERER_CHECK_REPAIR_IN_FRESH_ATTEMPT',copied_files=copied,
        actual_repeat_diagnosis=run.old.artifact(run.HERE/'NUMERIC_REPEAT_DIAGNOSIS.json'),
        preserved_failed_v1_freeze=run.old.artifact(run.HERE/'FREEZE.json'),
        preserved_failed_v1_partial=run.old.artifact(run.HERE/'ENDPOINTS.jsonl.gz'),
        metadata_math_checks_reused_from_actual_parent_execution=True,
        repair='Still exactly compare numeric metrics and every rendered boolean map. Do not require bit equality of unrendered full-frame float32 EDT arrays; they are not shown by this figure. No numerical algorithm or threshold changes.',
        measurements_changed=False,transform_changed=False,state_changed=False,new_model_http=0,cost_usd=0))
    print('Fresh attempt2 created; every v1 frozen byte and partial output preserved',flush=True)

if __name__=='__main__':main()
