"""Mandatory source and budget gate for the actual sender plan."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

from contract import assert_packet_segments, source_item, dumps
from preflight import AO1, DEV_OBS, VAL, read, stream, put
from prepare import DEV_DEPTH, M2, condition, digest

PEAK_INPUT_USD_PER_M=0.30
PEAK_OUTPUT_USD_PER_M=1.20
IMAGE_TOKEN_UPPER=1024
OUTPUT_TOKEN_UPPER=65536
TEXT_TOKEN_FACTOR=0.60  # twice DeepSeek's published English-character heuristic


def no_depth(packet):
    v=json.loads(dumps(packet))
    for section in ('PRE_HISTORY','POST_HISTORY_TO_Q'):
        for s in v[section].values():
            for o in s['observations']:o.pop('depth',None)
    t=v.get('INTERACTION_TABLE')
    if t and t['columns'][-2:]==['depth_median_pipeline_mm','depth_valid_fraction']:
        t['columns']=t['columns'][:-2]
        t['rows']=[x[:-2] for x in t['rows']]
    v['condition']='H-2D'
    return v


def verify(run):
    rejection=read(run/'public/OLD_PACKET_REJECTION.json')
    assert rejection['status']=='OLD_REAL_PACKETS_REJECTED'
    depth_audit=read(run/'public/DEPTH_INPUT_AUDIT.json')
    assert depth_audit['status']=='ALL_NEW_DEPTH_FRAMES_RAW_HDF5_MASK_PARITY'
    plan=read(run/'sender/PLAN.json');requests=plan['requests'];episodes=read(run/'public/EPISODE_FACTS.json')
    assert len(requests)==25 and len(episodes)==5 and plan['model']=='deepseek-flash'
    cases={c['case_alias']:c for c in read(AO1/'public/SOURCE_MANIFEST.json')['cases']}
    checks=[]
    for packet in episodes:
        name=packet['request_id'].split('-')[-1];c=cases[name];q=c['query_frame'];trigger=c['trigger_frame']
        lo=min(x['frame'] for x in packet['INTERACTION_OBSERVATIONS'])
        op=DEV_OBS if c['split']=='development' else VAL/'observations_validation.jsonl.gz'
        dp=DEV_DEPTH if c['split']=='development' else VAL/'features_validation.jsonl.gz'
        rows=stream(op,lo,q);depth=stream(dp,lo,q)
        roles=c['V1']['roles'];native={r:int(max((x for x in roles if x['role']==r),key=lambda x:x['frame'])['native_mask_key'].split(':')[1]) for r in 'ABXY'}
        assert_packet_segments(packet,rows,native)
        named=set()
        for part,role_set in (('PRE_HISTORY','AB'),('POST_HISTORY_TO_Q','XY')):
            for r in role_set:
                segment=packet[part][r]
                assert segment['status']=='CLEAN_SOURCE_FRAGMENT'
                for x in segment['observations']:
                    f=x['source_frame'];named.add((f,native[r]))
                    assert x['source_mask_rle_sha256'] and x['source_time_seconds']==rows[f]['time']
                    assert x['depth'].get('source_frame',f)==f
                    if x['depth'].get('epistemic_type')=='MEASUREMENT':
                        assert x['depth']['synchronized'] and x['depth']['raw_array_sha256']==depth[f]['raw_array_sha256']
                vel=segment['velocity']
                if vel.get('epistemic_type')=='ESTIMATE':
                    source={x['fact_id'] for x in segment['observations']}
                    assert len(vel['source_fact_ids'])>=3 and set(vel['source_fact_ids'])<=source
        factids={x['fact_id'] for part in ('PRE_HISTORY','POST_HISTORY_TO_Q') for s in packet[part].values() for x in s['observations']}
        eventids=set();covered=set(named)
        for row in packet['INTERACTION_OBSERVATIONS']:
            f=row['frame'];assert lo<=f<=q and row['time_seconds']==rows[f]['time']
            for o in row['anonymous_observations']:
                eventids.add(o['fact_id'])
                src=o['source_fact_ids'][0];sn=int(src.split('-N')[1]);sf=int(src.split('-N')[0].split('F')[1])
                assert sf==f and source_item(rows,f,sn) is not None
                assert o['source_mask_rle_sha256'] and (f,sn) not in covered
                covered.add((f,sn))
        expected={(f,o['id']) for f in range(lo,q+1) for o in rows[f]['observations']}
        assert covered==expected,(name,len(covered),len(expected))
        images=packet['IMAGE_INDEX']
        for im in images:
            f=im['frame'];assert f<=q and im['time_seconds']==rows[f]['time']
            assert digest(run/'sender/media'/im['media_file'])==im['sha256']
            roi=im['roi_full_mask_xyxy'];assert [im['width'],im['height']]==[roi[2]-roi[0],roi[3]-roi[1]]
            for binding in im['role_tokens']:
                role=binding['role'];src=source_item(rows,f,native[role]);assert src and src['box']==binding['bbox_full_px']
                assert binding['bbox_image_px']==[round(src['box'][0]-roi[0]),round(src['box'][1]-roi[1]),
                                                   round(src['box'][2]-roi[0]),round(src['box'][3]-roi[1])]
        for role in 'AB':
            anchor=packet['PRE_HISTORY'][role]['anchor_frame']
            assert any(im['frame']==anchor and any(b['role']==role for b in im['role_tokens']) for im in images)
        assert all(any(b['role']==r for b in im['role_tokens']) for r in 'XY' for im in images if im['frame']==q)
        assert packet['trigger']['frame']==trigger and packet['q_frame']==q
        checks.append(dict(case=name,status='PASS',source_observations=len(covered),event_observations=len(eventids),
                           pre_frames={r:len(packet['PRE_HISTORY'][r]['observations']) for r in 'AB'},
                           post_frames={r:len(packet['POST_HISTORY_TO_Q'][r]['observations']) for r in 'XY'},
                           image_count=len(images),prediction_contact=packet['trigger']['pair_contact_predicted']))
        variant={r['arm']:json.loads(r['text']) for r in requests if r['case']==name}
        assert variant['H-D']==variant['H-D-REPEAT']
        assert no_depth(variant['H-D'])==variant['H-2D']
        perm=json.loads(dumps(variant['H-D-PERMUTE']))
        for h in perm['hypotheses']:h['id']='H2' if h['id']=='H1' else 'H1'
        perm['hypotheses'].reverse()
        assert perm==variant['H-D']
        assert not variant['E']['INTERACTION_OBSERVATIONS'] and 'trigger' not in variant['E']
        for arm in ('H-2D','H-D','H-D-REPEAT','H-D-PERMUTE'):
            v=variant[arm];table=v['INTERACTION_TABLE']
            assert len(table['rows'])==len(eventids)
            assert {x[0] for x in table['rows']}==eventids
            assert all(x[1]<=q for x in table['rows'])
    assert [r['attempt_id'] for r in requests]==read(run/'public/REQUEST_MANIFEST.json')['schedule']
    depth_frames={(x['split'],x['frame']) for x in depth_audit['frames']}
    required={(cases[p['request_id'].split('-')[-1]]['split'],row['frame'])
              for p in episodes for row in p['INTERACTION_OBSERVATIONS']}
    required.update((cases[p['request_id'].split('-')[-1]]['split'],o['source_frame'])
                    for p in episodes for part in ('PRE_HISTORY','POST_HISTORY_TO_Q')
                    for segment in p[part].values() for o in segment['observations'])
    assert required==depth_frames
    budget=[]
    for request in requests:
        chars=len(request['text'])
        estimate=math.ceil(chars*TEXT_TOKEN_FACTOR)+len(request['images'])*IMAGE_TOKEN_UPPER+1024
        reserve=(estimate*PEAK_INPUT_USD_PER_M+OUTPUT_TOKEN_UPPER*PEAK_OUTPUT_USD_PER_M)/1e6
        budget.append(dict(attempt_id=request['attempt_id'],text_characters=chars,text_bytes=len(request['text'].encode()),
                           images=len(request['images']),input_token_reserve=estimate,
                           output_token_reserve=OUTPUT_TOKEN_UPPER,reserve_usd=round(reserve,8)))
    smoke_reserve=(1024+IMAGE_TOKEN_UPPER)*PEAK_INPUT_USD_PER_M/1e6+OUTPUT_TOKEN_UPPER*PEAK_OUTPUT_USD_PER_M/1e6
    total=sum(x['reserve_usd'] for x in budget)+smoke_reserve
    assert total<=plan['cap_usd'],total
    summary=dict(status='PASS',old_packet_rejection_sha256=digest(run/'public/OLD_PACKET_REJECTION.json'),
                 depth_audit_sha256=digest(run/'public/DEPTH_INPUT_AUDIT.json'),
                 plan_sha256=digest(run/'sender/PLAN.json'),contract_code_sha256=digest(Path(__file__).with_name('contract.py')),
                 cases=checks,request_count=25,model=plan['model'],max_tokens=plan['max_tokens'],
                 pricing_source='official DeepSeek V4.1 Flash peak cache-miss 2026-09-26 USD0.30/M input, USD1.20/M output',
                 budget_method='0.60 token per input character (2x published English heuristic), 1024 per image upper, 1024 request overhead, full 65536 output each',
                 request_budget=budget,smoke_reserve_usd=round(smoke_reserve,8),total_reserve_usd=round(total,8),cap_usd=plan['cap_usd'])
    put(run/'public/PREFLIGHT.json',summary)
    put(run/'sender/SENDER_GATE.json',dict(status='PASS',plan_sha256=summary['plan_sha256'],
        old_packet_rejected=True,depth_parity_pass=True,
        old_packet_rejection_sha256=summary['old_packet_rejection_sha256'],
        depth_audit_sha256=summary['depth_audit_sha256'],
        request_budget=budget,smoke_reserve_usd=summary['smoke_reserve_usd'],
        total_reserve_usd=summary['total_reserve_usd'],cap_usd=plan['cap_usd'],request_count=25))
    print(json.dumps(dict(status='PASS',cases=5,requests=25,reserve_usd=round(total,6))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    verify(p.parse_args().run)
