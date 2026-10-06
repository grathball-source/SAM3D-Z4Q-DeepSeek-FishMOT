"""No network/reference/restored/RGB access in prediction; explicit source reads logged."""
import os,sys
BLOCKED=('labels_640x360','labels_original','labels_source','labels_recovered','labels_raw',
    'restoration/v3/','depth_restored_rgb_640x360/','sealed_test','gt_grid','truth.jsonl',
    'offline_matches','test_gt','reference_matches','event_audit','switches.json','metrics.json',
    'postseal_','gt_raster','annotations/','/rgb/')
SEEN=set()
def access_guard(event,args):
    if event=='socket.connect':raise RuntimeError('DS35 prediction networking forbidden')
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
    path=str(args[0]).replace('\\','/').lower()
    if any(x in path for x in BLOCKED):raise RuntimeError('Forbidden prediction access: '+path)
    if '/data/' in path or '/private/' in path:SEEN.add(str(args[0]))
sys.addaudithook(access_guard)
from common import *

def main():
    from runner import run_segment
    mode,name=sys.argv[1:3]
    if mode=='prefix':
        output=HERE/sys.argv[4];assert output.parent==HERE and output.name.startswith('slice_')
        run_segment(name,output,stop_at=int(sys.argv[3]),disabled=(len(sys.argv)>5 and sys.argv[5]=='disabled'))
    else:
        assert mode=='run';output=RUN;run_segment(name,output)
    write_new(output/name/'public/ACCESS.json',dict(status='RAW_DEPTH_CACHE_NO_GT_RESTORED_RGB_NETWORK',
        blocked_tokens=list(BLOCKED),observed_data_paths=sorted(SEEN),
        actual_sensor_pixel_reads=0,actual_depth_cache_reads='All pinned same-ROI DS18 certificates plus original measured packets',
        maximum_evidence_authority='Already acquired past/current through q+30 before first publication',
        future_limit_frames=CFG['lag_frames'],annotation_instance_id_read=False,restored_depth_read=False,
        RGB_for_association=False,new_model_http=0,cost_usd=0))
if __name__=='__main__':main()
