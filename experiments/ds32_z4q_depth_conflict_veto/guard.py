"""Audit actual source reads; forbid GT/RGB/restored/future/network during replay."""
from common import *
import runpy,sys
scope=runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds32_guard')
from runner import run_segment
mode,name=sys.argv[1:3]
if mode=='prefix':
    output=HERE/sys.argv[4];assert output.name.startswith('slice_') and output.parent==HERE
    run_segment(name,output,stop_at=int(sys.argv[3]),disabled=len(sys.argv)>5 and sys.argv[5]=='disabled')
else:
    assert mode in ('run','counter_allow','counter_veto')
    output=RUN if mode=='run' else HERE/mode
    selected=read(HERE/'COUNTERFACTUAL_SELECTION.json') if mode!='run' else None
    edge=tuple(selected['allow_edge']) if mode=='counter_allow' else None
    run_segment(name,output,allow_edge=edge)
write_new(output/name/'public/ACCESS.json',dict(status='NO_GT_RGB_RESTORED_NETWORK',blocked_tokens=list(scope['BLOCKED']),
    observed_data_paths=sorted(scope['SEEN']),npz_field_reads=[dict(path=p,key=k) for p,k in sorted(scope['NPZ'])],
    note='Only current sealed DS18 object facts; no future packet acquisition into decisions.',model_http=0,cost_usd=0))
