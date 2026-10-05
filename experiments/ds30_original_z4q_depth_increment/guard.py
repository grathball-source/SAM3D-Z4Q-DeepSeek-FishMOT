"""Reuse existing field/GT/network guards without adding research qualification."""
from common import *
import runpy,sys
# Load the original audit hook; its __main__ dispatcher is deliberately dormant.
guard_scope=runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds25_original_access_guard')
from runner import run_segment
from evidence import raw_source as source
mode,name=sys.argv[1:3]
if mode=='prefix':
    output=HERE/sys.argv[4];assert output.name.startswith('slice_') and output.parent==HERE
    run_segment(name,output,stop_at=int(sys.argv[3]),disabled=len(sys.argv)>5 and sys.argv[5]=='disabled')
else:
    assert mode=='run';output=RUN;run_segment(name,output)
write_new(output/name/'public/ACCESS.json',dict(status='NO_GT_RGB_RESTORED_NETWORK',
    blocked_tokens=list(guard_scope['BLOCKED']),observed_data_paths=sorted(guard_scope['SEEN']),
    npz_field_reads=[dict(path=p,key=k) for p,k in sorted(guard_scope['NPZ'])],
    h5_or_array_field_reads=source.FIELD_READS,new_model_http=0,cost_usd=0))
