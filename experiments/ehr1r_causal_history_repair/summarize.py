"""Produce compact public indices from already-frozen packets and audits."""
import argparse
import json
from pathlib import Path


def put(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main(run):
    episodes=json.loads((run/'EPISODE_FACTS.json').read_text(encoding='utf-8'))
    timelines=[];images=[]
    for p in episodes:
        case=p['request_id'].split('-')[-1]
        timelines.append(dict(case=case,trigger=p['trigger'],old_to_new_reference=p['old_to_new_reference'],
          pre_fragments={r:p['PRE_HISTORY'][r]['fragment_id'] for r in 'AB'},
          post_fragments={r:p['POST_HISTORY_TO_Q'][r]['fragment_id'] for r in 'XY'},
          availability_intervals=p['availability_intervals'],reappearance_intervals=p['reappearance_intervals'],
          per_object_loss=p['per_object_loss'],per_handle_clean_return=p['per_handle_clean_return'],
          first_unusable_observation=p['first_unusable_observation'],first_physical_entry=p['first_physical_entry'],
          first_identity_reappearance=p['first_identity_reappearance'],joint_clean_pair_streak=p['joint_clean_pair_streak'],
          entry_side=p['entry_side'],relative_motion=p['relative_motion'],
          event_frame_count=len(p['INTERACTION_OBSERVATIONS']),
          anonymous_observation_count=sum(len(x['anonymous_observations']) for x in p['INTERACTION_OBSERVATIONS'])))
        for im in p['IMAGE_INDEX']:
            images.append({**im,'case':case,'sent_in':['E','H-2D','H-D','H-D-REPEAT','H-D-PERMUTE'] if im['role_tokens'] else
                           ['H-2D','H-D','H-D-REPEAT','H-D-PERMUTE']})
    put(run/'EVENT_TIMELINE.json',timelines)
    put(run/'IMAGE_MANIFEST.json',dict(status='IMAGE_ROI_AND_TOKEN_BINDINGS',images=images))
    preflight=json.loads((run/'PREFLIGHT.json').read_text())
    put(run/'INPUT_CONTRACT_CHECKS.json',dict(old_packets=json.loads((run/'OLD_PACKET_REJECTION.json').read_text()),
        new_cases=preflight['cases'],actual_depth_frames=json.loads((run/'DEPTH_INPUT_AUDIT.json').read_text())['frame_count'],
        request_budget_reserve_usd=preflight['total_reserve_usd']))
    print('summarized',len(timelines),'cases',len(images),'images')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
