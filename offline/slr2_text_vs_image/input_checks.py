"""Independent semantic and physical-invariance checks for SLR-2 preparation."""
from pathlib import Path
import json, math, hashlib, itertools

def canonical_option(option,track_map,observation_map):
    return dict(state=option['state'],matches=sorted([[track_map[x['track']],observation_map[x['observation']]] for x in option['matches']]),
                groups=sorted([[observation_map[g['observation']],sorted(track_map[t] for t in g['possible_members'])] for g in option['merged_groups']]),
                unresolved=sorted(track_map[t] for t in option['unresolved_tracks']))

def check_packet(p):
    assert set(p)=={'schema','query_id','focal_tracks','history','current','recent','pairwise','evidence','options','baseline_option_id'}
    prohibited={'frame','global_frame','native_id','public_id','split','pre','true_choice','correct','stable_correct','appearance_hsv_body','mask_sha256'}
    def walk(x):
        if isinstance(x,dict):
            assert not set(x)&prohibited
            if 'time_s' in x:assert x['time_s']<=0
            for k,v in x.items():
                assert not isinstance(v,str) or not (v.startswith('E:/') or v.startswith('/home/'))
                walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
        elif isinstance(x,float):assert math.isfinite(x)
    walk(p)
    ts=set(p['focal_tracks']);obs={x['observation']:x for x in p['current']};nonempty={k for k,v in obs.items() if v['area_px']>0}
    assert len(ts)==2 and all(t.startswith('T') for t in ts)
    assert len(obs)==len(p['current']) and all(o.startswith('O') for o in obs)
    assert {h['track'] for h in p['history']}==ts
    assert len(p['pairwise'])==2*len(obs)
    assert {(x['track'],x['observation']) for x in p['pairwise']}==set(itertools.product(ts,obs))
    assert all(e.startswith('E') for e in p['evidence'])
    for seq in ['history','current','recent','pairwise']:
        for x in p[seq]:assert x['evidence_id'] in p['evidence']
    for h in p['history']:
        ss=h['samples'];assert len(ss)<=3
        assert [x['time_s'] for x in ss]==sorted(x['time_s'] for x in ss)
        if ss:
            assert abs(h['age_s']+ss[-1]['time_s'])<1e-7
            if len(ss)>1:
                assert abs(h['span_s']-(ss[-1]['time_s']-ss[0]['time_s']))<1e-7
                assert h['span_s']>=.25-1e-7
            for s in ss:assert s['lineage'].startswith('L')
    rr=p['recent'];assert [x['time_s'] for x in rr]==sorted(x['time_s'] for x in rr)
    assert rr[-1]['time_s']==0 and {x['current_observation'] for x in rr[-1]['observations']}==set(obs)
    for x in rr[-1]['observations']:
        c=obs[x['current_observation']]
        assert x['lineage']==c['lineage'] and x['bbox_xyxy_px']==c['bbox_xyxy_px'] and x['area_px']==c['area_px']
        assert x['native_lineage_focal_track']==c['native_lineage_focal_track']
    for e in p['pairwise']:
        for modality in ['D','A','M']:assert e['available'][modality]==(e[modality] is not None)
    options=p['options'];assert len({o['option_id'] for o in options})==len(options)
    assert all(o['option_id'].startswith('H') for o in options)
    assert p['baseline_option_id'] in {o['option_id'] for o in options}
    assert len(options)==len(nonempty)*(len(nonempty)-1)+len(nonempty)+1
    matching=set();merge=set();wait=0
    for o in options:
        assert set(o)=={'option_id','state','matches','merged_groups','unresolved_tracks'}
        if o['state']=='MATCH':
            assert not o['merged_groups'] and not o['unresolved_tracks']
            assert {m['track'] for m in o['matches']}==ts and len(o['matches'])==2
            oo=[m['observation'] for m in o['matches']];assert len(set(oo))==2 and set(oo)<=nonempty
            matching.add(tuple(sorted((m['track'],m['observation']) for m in o['matches'])))
        elif o['state']=='POSSIBLE_MERGE':
            assert not o['matches'] and set(o['unresolved_tracks'])==ts and len(o['merged_groups'])==1
            g=o['merged_groups'][0];assert g['observation'] in nonempty and set(g['possible_members'])==ts;merge.add(g['observation'])
        else:
            assert o['state']=='UNRESOLVED' and not o['matches'] and not o['merged_groups'] and set(o['unresolved_tracks'])==ts;wait+=1
    assert len(matching)==len(nonempty)*(len(nonempty)-1) and merge==nonempty and wait==1
    return True

def check_requests(root):
    root=Path(root);read=lambda n:json.loads((root/n).read_text(encoding='utf-8'))
    requests=read('REQUESTS.json');maps=read('REQUEST_MAPS.json');ix=read('PRIVATE_INDEX.json')
    assert len(requests)==144 and len(maps)==144 and len(ix)==36
    assert {r['request_id'] for r in requests}==set(maps)
    stages={x['query_id']:x['stage'] for x in ix};group={};image_count=0;checks=0
    for r in requests:
        check_packet(r['packet']);checks+=1
        assert r['query_id']==r['packet']['query_id']
        m=maps[r['request_id']];assert m['query_id']==r['query_id'] and m['arm']==r['arm'] and m['view']==r['view']
        assert {o['option_id']:canonical_option(o,m['track_native_map'],m['observation_native_map']) for o in r['packet']['options']}==m['option_map']
        assert set(m['pre_public_by_track'])==set(m['track_native_map'])
        assert set(m['current_public_by_observation'])==set(m['observation_native_map'])
        pp=set(m['pre_public_by_native'].values())-set(m['pre_public_by_track'].values())
        assert set(m['protected_nonfocal_observations'])=={o for o,pub in m['current_public_by_observation'].items() if pub in pp}
        assert m['baseline_option_id']==r['packet']['baseline_option_id']
        for rel,h in zip(r['image_paths'],r['image_sha256']):
            path=(root/rel).resolve();assert path.is_relative_to((root/'images').resolve());assert hashlib.sha256(path.read_bytes()).hexdigest()==h;image_count+=1
        assert len(r['image_paths'])==len(r['image_sha256'])==(1 if r['arm']=='V' else 0)
        group.setdefault((r['query_id'],r['arm']),{})[r['view']]=r
    paired=0;repeated=0;permuted=0
    for (qid,arm),views in group.items():
        assert set(views)==({'original','repeat','permuted'} if stages[qid]=='first_split' else {'original'})
        original=views['original'];other=group[(qid,'V' if arm=='T' else 'T')]
        assert original['packet']==other['original']['packet'];paired+=1
        if 'repeat' in views:
            r=views['repeat'];assert r['packet']==original['packet'] and r['image_paths']==original['image_paths'] and r['image_sha256']==original['image_sha256'];repeated+=1
            m1=maps[original['request_id']];m2=maps[views['permuted']['request_id']]
            a=sorted(json.dumps(x,sort_keys=True) for x in m1['option_map'].values());b=sorted(json.dumps(x,sort_keys=True) for x in m2['option_map'].values());assert a==b;permuted+=1
    # Negative tests check that causal and legal option assertions are effective.
    import copy
    base=requests[0]['packet'];bad=copy.deepcopy(base);bad['recent'][0]['time_s']=1
    try:check_packet(bad)
    except AssertionError:pass
    else:raise AssertionError('future observation accepted')
    bad=copy.deepcopy(base);m=next(o for o in bad['options'] if o['state']=='MATCH');m['matches'][1]['observation']=m['matches'][0]['observation']
    try:check_packet(bad)
    except AssertionError:pass
    else:raise AssertionError('duplicate assignment accepted')
    return dict(exit_code=0,packet_checks=checks,queries=len(ix),requests=len(requests),arm_equality_checks=paired,
                exact_repeat_checks=repeated,physical_permutation_checks=permuted,image_hash_checks=image_count,
                negative_semantic_checks=2,GT_read=False,full_candidate_option_enumeration=True)

if __name__=='__main__':
    p=Path(__file__).resolve().parent;result=check_requests(p)
    (p/'INPUT_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
