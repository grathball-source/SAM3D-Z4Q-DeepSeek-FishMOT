"""One-time transparent derivation of DS6 replay from the frozen DS2 control flow."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
s=(ROOT/'experiments/ds2_depth_transfer_validation/runner.py').read_text(encoding='utf-8')
def replace(old,new):
    global s
    assert old in s,old
    s=s.replace(old,new)
begin=s.index('HERE = Path')
end=s.index('EVENT_ARMS =')
s=s[:begin]+"""from common import (HERE,ROOT,DATA,RUN,DS1,DS2,FEED,OLD,S0P,NE1,SEGMENTS,ARMS,
                    input_dir,read,rows,sha,write_new,artifact)
import numpy as np
from bridge import stream
from manager_p import MergeSplitManagerP
from merge_split_manager import choice_mapping,numeric_choice
from ne_controller import NativeFirstGroupBridgeP
from depth_measurement import extract_frame
from depth_score import dynamic_choice,geometry_choice
from depth_state import DepthState
from measurement import measure_frame,history_measurement
from association import choose

""" + s[end:]
begin=s.index('CODE =')
end=s.index('\n\ndef emit')
s=s[:begin]+"""CODE = [HERE/name for name in ('CONFIG.json','PLAN.md','runner.py','common.py',
    'measurement.py','association.py','tests.py','evaluate.py','event_audit.py','score_checks.py',
    'INPUT_REVIEW.json','DESIGN_REVIEW.json','UNIT_CHECKS.json','build_runner.py')]
CODE += [DS1/name for name in ('CONFIG.json','replay.py','depth_measurement.py','depth_state.py',
    'depth_score.py','postseal.py','tests.py')]
CODE += [ROOT/'experiments/ds3_depth_foreground_filter'/n for n in ('CONFIG.json','foreground.py')]
CODE += [ROOT/'experiments/ds4_depth_quality_repair'/n for n in ('CONFIG.json','selector.py')]
CODE += [FEED/'prepare.py',OLD/'merge_split_manager.py',OLD/'source_scan_v4.py',
    S0P/'manager_p.py',NE1/'ne_controller.py',
    ROOT/'online/closed_loop_2888/z4q_source/bridge.py',CONFIG_PATH,EVENT_CONFIG]
""" + s[end:]
replace("base=INPUT_ROOT/name","base=input_dir(name)")
replace("else dynamic_choice","else dynamic_choice") if False else None
replace("full, measured, _, _ = extract_frame(depth,assignments[frame],profile_by_id)",
"""full, measured, masks, occupancy = extract_frame(depth,assignments[frame],profile_by_id)
            f6,quality=measure_frame(depth,masks,occupancy,name,frame,row['global_frame'])""")
replace("timing=timing[row['global_frame']],full=full,objects=measured)",
        "timing=timing[row['global_frame']],full=full,objects=measured,f6=f6,quality=quality)")
replace("branch,manager,state=branches[arm],managers[arm],states[arm]",
"""branch,manager,state=branches[arm],managers[arm],states[arm]
                state_measured=({n:history_measurement(m) for n,m in f6.items()}
                                if arm in ('D4_F6_SCALAR','D5_MULTIFRAGMENT') else measured)""")
replace("state.record_pending(native,measured[native],frame)","state.record_pending(native,state_measured[native],frame)")
begin=s.index("                    elif arm=='D1_STATIC_LEGACY':")
end=s.index("                    episode['numeric']",begin)
s=s[:begin]+"""                    elif arm=='D2_CORE_FROZEN':
                        choice,detail=dynamic_choice(episode,episode['depth_frozen'],measured,full)
                    else:
                        choice,detail=choose(episode,episode['depth_frozen'],f6,full,
                                             multi=(arm=='D5_MULTIFRAGMENT'))
                    candidate_times.append(dict(arm=arm,frame=frame,seconds=time.perf_counter()-candidate_start))
                    if arm=='D5_MULTIFRAGMENT':
                        scalar,scalar_detail=choose(episode,episode['depth_frozen'],f6,full,multi=False)
                        shadow.append(dict(kind='COMMON_STATE_SHADOW',event=episode['id'],frame=frame,
                            global_frame=row['global_frame'],multi_choice=choice,scalar_choice=scalar,
                            multi=detail,scalar=scalar_detail,submitted=False))
""" + s[end:]
replace("state.update(n,measured[n],frame","state.update(n,state_measured[n],frame")
replace("'D2_FROZEN'","'D2_CORE_FROZEN'")
# tracemalloc changes CPU cost strongly for per-point graph operations; explicit exclusion.
replace("    tracemalloc.start()","    # No allocation tracing in performance replay; elapsed time includes all work.")
replace("    peak=tracemalloc.get_traced_memory()[1]\n    tracemalloc.stop()","    peak=None")
replace("status='ALL_FIVE_BRANCHES_BOTH_SEGMENTS_SEALED'","status='ALL_FIVE_BRANCHES_FOUR_SEGMENTS_SEALED'")
replace("    output=HERE/'run'","    output=RUN")
replace("    freeze_inputs(output)","    freeze_inputs(output)") if False else None
replace("def main():\n    output=RUN\n    freeze_inputs(output)",
"""def main(mode='full'):
    assert mode in ('slice','full')
    output=HERE/'slice' if mode=='slice' else RUN
    freeze_inputs(output)""")
replace("        run_segment(name,output)","""        value=run_segment(name,output,slice_mode=mode=='slice')
        if mode=='slice' and value:
            write_new(output/'REAL_SLICE.json',value)
            return""")
replace("    write_new(output/'ALL_PREDICTIONS_SEALED.json'","    assert mode=='full'\n    write_new(output/'ALL_PREDICTIONS_SEALED.json'")
replace("if __name__=='__main__': main()","if __name__=='__main__': main(sys.argv[1] if len(sys.argv)>1 else 'full')")
with (HERE/'runner.py').open('x',encoding='utf-8',newline='\n') as handle:
    handle.write(s)

