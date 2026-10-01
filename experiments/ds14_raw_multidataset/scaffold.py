"""One-time orchestration adaptation; scientific kernel bytes remain DS12."""
from common import *
assert not RUN.exists()
assert not (HERE/'runner.py').exists()
r=(DS12/'runner.py').read_text(encoding='utf-8')
r=r.replace('Same-source DS12 first-birth depth reconnect','DS14 original-raw multi-dataset first-birth depth reconnect')
r=r.replace('from input_contract import verify_cached_segment\n','')
r=r.replace('from contact_measurement import load_raw_frame,measure_contact,array_binding','from contact_measurement import measure_contact,array_binding\nfrom source import RawDepth')
r=r.replace("CACHE=HERE.parent/'ds10_depth_failure_repair/run'\n",'')
begin=r.index('_source_spec=');end=r.index('\ndef emit(',begin)
r=r[:begin]+'''def build_contact_frame(row,assignment,measured,reader):
    """Current actual raw pixels, preserved masks and original source index."""
    f,g,now=row['frame'],row['global_frame'],row['time']
    depth,index,native,binding=reader(g,now)
    masks={int(n[2:]):decode(rle) for n,rle in assignment['masks'].items()}
    assert set(masks)=={o['id'] for o in row['observations']}
    binding.update(frame=f,time=now,global_frame=g,
        assignment_row_sha256=hashlib.sha256(json.dumps(assignment,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        declared_observation_neighbors={str(o['id']):list(o.get('neighbors',[])) for o in row['observations']},
        measurement_fact_ids={str(n):m['fact_id'] for n,m in measured['adaptive_raw'].items()})
    raw=measure_contact(depth,index,masks,row['segment'],f,g,source_binding=binding,native_depth=native)
    return dict(frame=f,global_frame=g,time=now,status='ACTUAL_CURRENT_BIRTH_FRAME_MEASUREMENTS',
        raw={str(n):c for n,c in raw.items()},raw_source_binding=binding)

''' +r[end:]
begin=r.index('def freeze_inputs(');end=r.index('\ndef state_summary(',begin)
r=r[:begin]+'''def freeze_inputs(output):
    assert not output.exists(),output
    output.mkdir(parents=True)
    dependencies={Path(m.__file__).resolve() for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and str(m.__file__).endswith('.py')
        and str(Path(m.__file__).resolve()).lower().startswith(str(ROOT).lower())}
    dependencies.update((OLD/'score.py',OLD/'source_scan_v4.py',OLD/'source_scan.py',
        HERE.parent/'ds9_joint_h0_depth/association.py',HERE.parent/'ds9_joint_h0_depth/CONFIG.json',
        HERE.parent/'ds10_depth_failure_repair/association.py',HERE.parent/'ds11_depth_birth_reconnect/reconnect.py',
        HERE.parent/'ds10_depth_failure_repair/adaptive_core.py',
        WORK/'tools/depth_restoration/geometry.py',WORK/'tools/depth_restoration/build_aligned_dataset.py',
        WORK/'tools/sam3_depth_birth_inherit_20260917/features.py',WORK/'tools/annotation/run_sam3_trackeval.py',
        CONFIG_PATH,EVENT_CONFIG))
    files=set(HERE.glob('*.py'))|set(HERE.glob('*.json'))|set(HERE.glob('*.md'))|dependencies
    code={str(p.resolve()):sha(p) for p in files}
    for name,(start,stop) in SEGMENTS.items():
        manifest=read(input_dir(name)/'SOURCE_MANIFEST.json')
        for item in manifest['derived_inputs'].values():verify_item(item)
        for key in ('scan','raw_sources','field_access'):verify_item(manifest[key])
        frozen=dict(status='FROZEN_BEFORE_PREDICTION',segment=name,original_frames=[start,stop],frames=stop-start+1,
            arms=list(ARMS),code_sha256=code,source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),
            source_chain=manifest,config_scientific_sha256=sha(HERE/'CONFIG.json'),
            config_metadata_note='CONFIG is byte-identical DS12; DS14 common defines actual 2 arms and 8 ranges. Restored descriptive metadata is inactive.',
            branch_policy='Independent real state; byte-identical DS12 R12_RAW measurements, group, birth and transactions',
            new_model_http=0,model_cost_usd=0,no_gt_before_seal=True)
        public=output/name/'public';public.mkdir(parents=True)
        write_new(public/'FREEZE.json',frozen)

''' +r[end:]
r=r.replace("rows(CACHE/name/'public/DEPTH_OBSERVATIONS.jsonl.gz')","rows(base/'DEPTH_OBSERVATIONS.jsonl.gz')")
old="""    actual_sources={s['frame']:s for s in read(base/'sources.json')}
    restored_sources=read(public/'FREEZE.json')['restored_sources']
    reader=RestoredDepth();native_seen=set()"""
assert old in r;r=r.replace(old,'    reader=RawDepth(name);native_seen=set()')
r=r.replace("            restored={int(n):v for n,v in measured['restored'].items()}\n",'')
r=r.replace("assert set(raw)==set(restored)==","assert set(raw)==")
old="""build_contact_frame(dict(row,segment=name),assignments[frame],measured,
                    actual_sources[row['global_frame']],reader,restored_sources)"""
assert old in r;r=r.replace(old,'build_contact_frame(dict(row,segment=name),assignments[frame],measured,reader)')
r=r.replace("status='NO_NONINITIAL_FIRST_EVER_BIRTH',raw={},restored={},\n                    raw_source_binding=None,restored_source_binding=None)","status='NO_NONINITIAL_FIRST_EVER_BIRTH',raw={},raw_source_binding=None)")
r=r.replace("state_measured=raw if arm=='R12_RAW' else restored","state_measured=raw")
r=r.replace("full=measured['adaptive_full' if arm=='R12_RAW' else 'restored_full']","full=measured['adaptive_full']")
r=r.replace("mode='RAW_DEPTH' if arm=='R12_RAW' else 'RESTORED_DEPTH'","mode='RAW_DEPTH'")
r=r.replace("contact_row['raw' if arm=='R12_RAW' else 'restored']","contact_row['raw']")
r=r.replace("disabled=arm=='F9_RESTORED'","disabled=False")
r=r.replace('EXACT_SEALED_DS10_HISTORY_GROUP_CACHE_PLUS_ACTUAL_CURRENT_CONTACT_DEPTH','SOURCE_BOUND_RAW_HISTORY_GROUP_CACHE_PLUS_ACTUAL_CURRENT_CONTACT_DEPTH')
r=r.replace('exact history/group cache','raw source-bound history/group cache')
begin=r.index('def main(')
r=r[:begin]+"if __name__=='__main__':freeze_inputs(RUN)\n"
assert 'RestoredDepth' not in r and 'restored_sources' not in r and 'CACHE/' not in r
(HERE/'runner.py').write_text(r,encoding='utf-8',newline='\n')
print('DS14 orchestration created; DS12 scientific files unchanged')
