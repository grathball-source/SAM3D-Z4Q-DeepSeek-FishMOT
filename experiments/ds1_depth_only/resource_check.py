"""Timing/memory instrumentation of the frozen replay; no new scoring or tuning."""
import json
import sys
import time
from collections import deque
from pathlib import Path

import replay
import depth_score

HERE=Path(__file__).resolve().parent
active=[]
snapshots=[]
queries=[]
updates={}
memory=[]
original_init=replay.DepthState.__init__
original_freeze=replay.DepthState.freeze
original_update=replay.DepthState.update
original_predict=depth_score.predict
original_emit=replay.emit
emit_count=0


def deep_bytes(value,seen=None):
    seen=set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    total=sys.getsizeof(value)
    if isinstance(value,dict):
        total+=sum(deep_bytes(k,seen)+deep_bytes(v,seen) for k,v in value.items())
    elif isinstance(value,(list,tuple,set,deque)):
        total+=sum(deep_bytes(x,seen) for x in value)
    elif isinstance(value,replay.DepthState):
        total+=deep_bytes(value.__dict__,seen)
    return total


def init(state,segment,arm):
    if active and active[0].segment!=segment:
        active.clear(); snapshots.clear()
    original_init(state,segment,arm)
    active.append(state)


def freeze(state,*args,**kwargs):
    result=original_freeze(state,*args,**kwargs)
    snapshots.append(result)
    return result


def update(state,native,measurement,frame,*args,**kwargs):
    began=time.perf_counter_ns()
    result=original_update(state,native,measurement,frame,*args,**kwargs)
    key=(state.segment,state.arm,frame)
    updates[key]=updates.get(key,0)+(time.perf_counter_ns()-began)/1e9
    return result


def predict(frozen,query_time):
    began=time.perf_counter_ns()
    result=original_predict(frozen,query_time)
    queries.append(dict(samples=result['samples'],status=result['status'],
                        seconds=(time.perf_counter_ns()-began)/1e9))
    return result


def emit(row,mapping):
    global emit_count
    result=original_emit(row,mapping)
    emit_count+=1
    if emit_count%3==0:
        memory.append(dict(segment=active[0].segment,frame=row['frame'],
                           retained_depth_graph_bytes=deep_bytes([active,snapshots])))
    return result


def main():
    output=HERE/'resource_check'
    replay.DepthState.__init__=init
    replay.DepthState.freeze=freeze
    replay.DepthState.update=update
    depth_score.predict=predict
    replay.emit=emit
    replay.freeze_inputs(output)
    exact=[]
    for name in replay.SEGMENTS:
        replay.run_segment(name,output)
        actual=list(replay.rows(output/name/'public/predictions.jsonl.gz'))
        formal=list(replay.rows(HERE/'run'/name/'public/predictions.jsonl.gz'))
        assert actual==formal,name
        exact.append(dict(segment=name,frames=len(actual),all_four_variants_exact=True))
    result=dict(status='RESOURCE_ONLY_EXACT_FROZEN_PREDICTIONS',prediction_equality=exact,
        depth_query_timings=queries,
        frame_depth_update_timings=[dict(segment=s,arm=a,frame=f,seconds=t) for (s,a,f),t in updates.items()],
        retained_depth_graph_by_frame=memory,
        peak_retained_depth_graph_bytes=max(x['retained_depth_graph_bytes'] for x in memory),
        memory_method='recursive sys.getsizeof shared-object graph, all3 DepthStates and retained pre snapshots; CPython bytes excluding allocator overhead/temporary NumPy fits',
        same_frozen_algorithm=True,no_new_metrics=True,new_model_http=0,model_cost_usd=0,
        instrumentation_sha256=replay.sha(HERE/'resource_check.py'))
    replay.write_new(HERE/'run/RESOURCE_DIAGNOSTICS.json',result)
    print(json.dumps(dict(status=result['status'],peak_bytes=result['peak_retained_depth_graph_bytes'],
        queries=len(queries),query_total_seconds=sum(x['seconds'] for x in queries))))


if __name__=='__main__':
    main()
