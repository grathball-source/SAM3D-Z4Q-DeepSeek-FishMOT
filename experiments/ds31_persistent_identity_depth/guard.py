"""Existing no-GT/no-RGB/no-future/no-network audit during prediction."""
from common import *
import runpy,sys
scope=runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds31_original_guard')
from runner import run_segment
mode,name=sys.argv[1:3]
if mode=='prefix':
    output=HERE/sys.argv[4];assert output.name.startswith('slice_') and output.parent==HERE
    run_segment(name,output,stop_at=int(sys.argv[3]))
else:
    assert mode=='run';output=RUN;run_segment(name,output)
write_new(output/name/'public/ACCESS.json',dict(status='NO_GT_RGB_RESTORED_NETWORK',blocked_tokens=list(scope['BLOCKED']),
    observed_data_paths=sorted(scope['SEEN']),npz_field_reads=[dict(path=p,key=k) for p,k in sorted(scope['NPZ'])],
    note='Runtime reads sealed current-row DS18 raw measurement facts; never reads future packet rows into decisions.',new_model_http=0,cost_usd=0))
