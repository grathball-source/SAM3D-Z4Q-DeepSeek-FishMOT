"""Reuse frozen DS8 measurements/control; change only association and controls."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'ds8_adaptive_depth_core'
assert not (HERE/'run').exists()
for name in ('common.py','controller.py','controller_tests.py','restored_source.py',
             'measurement.py','measurement_tests.py','adaptive_core.py','adaptive_tests.py','launch.py'):
    (HERE/name).write_bytes((OLD/name).read_bytes())
arms=['SAM3_NATIVE','J0_GEOMETRY','J1_RAW_DEPTH','J2_RESTORED_DEPTH','J2_DEPTH_ZERO','J2_DEPTH_PERMUTE']
common=(HERE/'common.py').read_text(encoding='utf-8')
common=common.replace('DS7 shared paths','DS9 shared paths').replace(
    "ARMS=('SAM3_NATIVE','D2_CORE_FROZEN','P0_NATIVE_PRESERVE','P1_RAW_DEPTH','P2_RESTORED_DEPTH')",'ARMS='+repr(tuple(arms)))
(HERE/'common.py').write_text(common,encoding='utf-8',newline='\n')
cfg=json.loads((OLD/'CONFIG.json').read_text(encoding='utf-8'))
cfg.pop('depth_weight');cfg.pop('minimum_depth_odds')
cfg.update(trial='DS9',arms=arms,minimum_joint_odds=9,student_df=4,
    signal_fraction=.9,geometry_background_area_px=640*360,
    geometry_residual_min=3,geometry_covariance_shrinkage=.5,
    geometry_covariance_floor_px2=16,geometry_fallback_sigma_px=4,
    geometry_fallback_bbox_fraction=.1,
    geometry_scale_note='Student-t shape = covariance/2 for df=4; past next-point residual proxy only',
    single_change='explicit lawful H0 + normalized geometry/depth association; six controlled branches',
    joint_independence='conditional geometry/depth factorization assumption; no unnormalized .25 weight',
    unique_mapping_prior='uniform over physically distinct mappings; H0 representative on duplicate',
    depth_zero='actual measurements retained, depth likelihood omitted; must equal J0 frame by frame',
    depth_permute='swap only current two post depth observations for association; state retains actual measurements')
(HERE/'CONFIG.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
runner=(OLD/'runner.py').read_text(encoding='utf-8')
def replace(old,new):
    global runner
    assert runner.count(old)==1,(old,runner.count(old))
    runner=runner.replace(old,new)
replace('"ds8_native_controller"','"ds9_native_controller"')
replace(" 'CONFIG.json','PLAN.md','README.md','runner.py','prepare_trial.py','common.py',",
        " 'CONFIG.json','PLAN.md','README.md','runner.py','prepare_trial.py','common.py',\n 'execute.py','preflight.py','check_real_slice.py',")
replace("from depth_score import dynamic_choice,geometry_choice\n",'')
replace(" 'association.py','restored_source.py','adaptive_core.py','adaptive_tests.py',",
        " 'association.py','association_tests.py','ASSOCIATION_CHECKS.json','PREFLIGHT_REVIEW.md','restored_source.py','adaptive_core.py','adaptive_tests.py',")
replace("CODE += [DS1/n", "if (HERE/'REAL_SLICE_ACCEPTANCE.json').exists():\n    CODE.append(HERE/'REAL_SLICE_ACCEPTANCE.json')\nCODE += [DS1/n")
replace("branches={arm:(NativeFirstGroupBridgeP(config) if arm=='D2_CORE_FROZEN' else DepthNativeBridge(config)) for arm in EVENT_ARMS}",
        "branches={arm:DepthNativeBridge(config) for arm in EVENT_ARMS}")
replace("managers={arm:(MergeSplitManagerP if arm=='D2_CORE_FROZEN' else DepthNativeManager)(arm,branches[arm],suspects,event_config,assignments)",
        "managers={arm:DepthNativeManager(arm,branches[arm],suspects,event_config,assignments)")
replace("    result['group_frames']", "    result['pre_geometry_history']=copy.deepcopy(e['pre'])\n    result['group_frames']")
replace("state_measured=(restored_measured if arm=='P2_RESTORED_DEPTH' else adaptive_measured if arm=='P1_RAW_DEPTH' else measured)",
        "state_measured=restored_measured if arm.startswith('J2_') else adaptive_measured")
a=runner.index("                    if arm=='P0_NATIVE_PRESERVE':")
b=runner.index("                    candidate_times.append",a)
runner=runner[:a]+"""                    mode={'J0_GEOMETRY':'GEOMETRY','J1_RAW_DEPTH':'RAW_DEPTH',
                        'J2_RESTORED_DEPTH':'RESTORED_DEPTH','J2_DEPTH_ZERO':'DEPTH_ZERO',
                        'J2_DEPTH_PERMUTE':'DEPTH_PERMUTE'}[arm]
                    choice,detail=choose(episode,episode['depth_frozen'],state_measured,
                        restored_full if arm.startswith('J2_') else adaptive_full,
                        view['mapping'],mode,name)
"""+runner[b:]
replace("if first_slice is None and arm=='P2_RESTORED_DEPTH'", "if first_slice is None and arm=='J2_RESTORED_DEPTH'")
replace("ALL_FIVE_BRANCHES_FOUR_SEGMENTS_SEALED","ALL_SIX_BRANCHES_FOUR_SEGMENTS_SEALED")
replace("error='visible_member_residual_outside_two_member_restore' if residual else 'numeric_unresolved'",
        "error=('visible_member_residual_outside_two_member_restore' if residual else\n                           'H0_KEEP_LAWFUL_MAPPING' if choice=='H0' else 'numeric_unresolved')")
(HERE/'runner.py').write_text(runner,encoding='utf-8',newline='\n')
print('Prepared six controlled DS9 branches')
