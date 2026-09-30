"""Derive replay from the byte-frozen DS6 flow; fail if any expected block moved."""
from common import *
def replace(source,a,b):
    assert a in source,a[:120]
    return source.replace(a,b)
assert not RUN.exists() and not (HERE/'slice').exists(), 'never regenerate sealed replay code'
source=(DS6/'runner.py').read_text(encoding='utf-8')
source=replace(source,'Causal, CPU-only SOURCE_OLD replay with three independent event branches.',
    'Current-frame state replay with saved offline RGB/future-supported v2 depth.')
source=replace(source,'HERE,ROOT,DATA,RUN,DS1,DS2,FEED,OLD,S0P,NE1,SEGMENTS,ARMS,',
    'HERE,ROOT,DATA,RUN,DS1,DS2,DS6,FEED,OLD,S0P,NE1,SEGMENTS,ARMS,')
source=replace(source,'from measurement import measure_frame,history_measurement',
    'from measurement import measure_restored\nfrom restored_source import RestoredDepth\nimport importlib.util\n_spec=importlib.util.spec_from_file_location("ds7_native_controller",HERE/"controller.py")\n_native=importlib.util.module_from_spec(_spec)\n_spec.loader.exec_module(_native)\nDepthNativeBridge,DepthNativeManager=_native.DepthNativeBridge,_native.DepthNativeManager')
start=source.index('CODE = [HERE/name')
end=source.index('\n\n\ndef emit',start)
source=source[:start]+"""CODE = [HERE/n for n in ('CONFIG.json','PLAN.md','runner.py','build_runner.py','common.py',
 'controller.py','controller_tests.py','measurement.py','association.py','restored_source.py','tests.py',
 'UNIT_CHECKS.json','CONTROLLER_CHECKS.json','REAL_INPUT_CHECKS.json','launch.py','evaluate.py',
 'event_audit.py','build_evaluation.py','GENERATION.json','score_checks.py','SCORE_CHECKS.json',
 'ENVIRONMENT.json','OLD_READONLY_LOCK.json','CODE_REVIEW.json')]
CODE += [DS1/n for n in ('CONFIG.json','depth_measurement.py','depth_state.py','depth_score.py','postseal.py')]
CODE += [DS6/'runner.py',DS6/'evaluate.py',DS6/'event_audit.py',FEED/'prepare.py',
 OLD/'merge_split_manager.py',OLD/'source_scan_v4.py',S0P/'manager_p.py',NE1/'ne_controller.py',
 ROOT/'online/closed_loop_2888/z4q_source/bridge.py',CONFIG_PATH,EVENT_CONFIG]
"""+source[end:]
source=replace(source,"    for name,(start,stop) in SEGMENTS.items():\n        base=input_dir(name)",
"""    restored_sources={str(p):artifact(p) for p in RestoredDepth.paths()}
    for name,(start,stop) in SEGMENTS.items():
        base=input_dir(name)""")
source=replace(source,"sensor_fields=['depth_mm','source_index']", "sensor_fields=['depth_mm','source_index','v2_h5_current_depth_mm','filled_mask','invalidated_reason','original_depth_mm'],\n            restored_sources=restored_sources,\n            restored_scope='NO_ANNOTATION_V2_OFFLINE_RGB_FUTURE_SUPPORTED'")
source=replace(source,"branches={arm:NativeFirstGroupBridgeP(config) for arm in EVENT_ARMS}",
"branches={arm:(NativeFirstGroupBridgeP(config) if arm=='D2_CORE_FROZEN' else DepthNativeBridge(config)) for arm in EVENT_ARMS}")
source=replace(source,"managers={arm:MergeSplitManagerP(arm,branches[arm],suspects,event_config,assignments)\n              for arm in EVENT_ARMS}",
"managers={arm:(MergeSplitManagerP if arm=='D2_CORE_FROZEN' else DepthNativeManager)(arm,branches[arm],suspects,event_config,assignments)\n              for arm in EVENT_ARMS}")
source=replace(source,"    began=time.perf_counter()", "    restored_source=RestoredDepth()\n    began=time.perf_counter()")
source=replace(source,"            f6,quality=measure_frame(depth,masks,occupancy,name,frame,row['global_frame'])",
"            restored,provenance,restored_meta=restored_source(row['global_frame'])\n            restored_full,restored_measured=measure_restored(restored,provenance,masks,occupancy,name,frame)")
source=replace(source,"timing=timing[row['global_frame']],full=full,objects=measured,f6=f6,quality=quality)",
"timing=timing[row['global_frame']],full=full,objects=measured,restored_full=restored_full,restored=restored_measured,restored_source=restored_meta)")
source=replace(source,"                state_measured=({n:history_measurement(m) for n,m in f6.items()}\n                                if arm in ('D4_F6_SCALAR','D5_MULTIFRAGMENT') else measured)",
"                state_measured=restored_measured if arm=='P2_RESTORED_DEPTH' else measured")
source=replace(source,"                    if arm=='D0_GEOMETRY':\n                        choice,detail=geometry_choice(episode)\n                    elif arm=='D2_CORE_FROZEN':",
"                    if arm=='P0_NATIVE_PRESERVE':\n                        choice,detail='UNRESOLVED',dict(reason='NO_DEPTH_ABLATION_NATIVE_CONTINUITY',used_edges=0)\n                    elif arm=='D2_CORE_FROZEN':")
source=replace(source,"                        choice,detail=choose(episode,episode['depth_frozen'],f6,full,\n                                             multi=(arm=='D5_MULTIFRAGMENT'))",
"                        choice,detail=choose(episode,episode['depth_frozen'],state_measured,\n                            restored_full if arm=='P2_RESTORED_DEPTH' else full)")
start=source.index("                    if arm=='D5_MULTIFRAGMENT':")
end=source.index("                    episode['numeric']=",start)
source=source[:start]+source[end:]
source=replace(source,"if first_slice is None and arm=='D2_CORE_FROZEN'", "if first_slice is None and arm=='P2_RESTORED_DEPTH'")
source=replace(source,"measured={str(n):measured[n] for n in episode['post_roles']}", "measured={str(n):state_measured[n] for n in episode['post_roles']}")
source=replace(source,"    peak=None\n", "    restored_source.close()\n    peak=None\n")
source=replace(source,"                    episode['restore']=restore",
"""                    restore['mapping_relative_to_native']={n:k for n,k in (mapping or {}).items() if n!=k}
                    restore['published_previous_mapping']={n:previous.get(n) for n in episode['post_roles']}
                    restore['baseline_preview_mapping']={n:view['mapping'][n] for n in episode['post_roles']}
                    restore['changed_relative_to_previous']={n:k for n,k in transaction['mapping'].items()
                        if n in previous and previous[n]!=k}
                    episode['restore']=restore""")
(HERE/'runner.py').write_text(source,encoding='utf-8',newline='\n')
metadata=dict(template=artifact(DS6/'runner.py'),generated_sha256=sha(HERE/'runner.py'),
    method='explicit exact-block substitutions; compiled full flow frozen before prediction')
(HERE/'GENERATION.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Generated',sha(HERE/'runner.py'))

