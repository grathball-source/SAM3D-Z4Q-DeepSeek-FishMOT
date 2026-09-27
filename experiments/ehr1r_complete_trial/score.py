"""Postseal physical-mapping scorer. GT paths are opened only after verify_chain."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from build import read, save, sha
from sender import body, wire

ROOT=Path(__file__).resolve().parents[2]
AO0=ROOT/'experiments/ao0_association_observability'
AO1=ROOT/'experiments/ao1_input_fidelity'
OLD=ROOT/'experiments/ehr1r_causal_history_repair/corrected_unsent'
ARMS=('E','H-2D','H-D','H-D-REPEAT','H-D-PERMUTE')


def canonical(mapping):
    assert isinstance(mapping,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in mapping.items())
    return tuple(sorted(mapping.items()))


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def verify_chain(run):
    """No GT, old key, or model-content interpretation above this boundary."""
    run=Path(run);public=run/'public';private=run/'send'
    lock=read(public/'CODE_AND_INPUT_LOCK.json')
    for filename,digest in lock['code_sha256'].items():
        assert sha(Path(__file__).parent/filename)==digest,filename
    for filename,digest in lock['input_sha256'].items():
        assert sha(public/filename)==digest,filename
    audit=read(public/'SOURCE_TO_BODY_AUDIT.json')
    assert audit['status']=='SOURCE_TO_LOGICAL_PASS' and audit['requests']==25
    manifest=read(public/'REQUEST_MANIFEST.json');logical=read(public/'REQUESTS_LOGICAL.json')['requests']
    schedule=manifest['schedule']
    assert len(schedule)==25 and len(set(schedule))==25
    assert schedule==[x['attempt_id'] for x in logical]==[x['attempt_id'] for x in manifest['requests']]
    assert set(x['case'] for x in logical)=={'B01','B02','B03','B04','B05'}
    for request,record in zip(logical,manifest['requests'],strict=True):
        assert request['attempt_id']==record['attempt_id']
        assert hashlib.sha256(request['text'].encode()).hexdigest()==record['text_sha256']
        assert [x['sha256'] for x in request['images']]==record['image_sha256']
        assert request['attempt_id']==request['case']+'-'+request['arm']
        p=json.loads(request['text'])
        assert p['request_id']=='EHR1R-C-'+request['case']
        assert [x['image_id'] for x in p['IMAGE_INDEX']]==[x['image_id'] for x in request['images']]
    assert sha(OLD/'EPISODE_FACTS.json')==manifest['source_sha256']['EPISODE_FACTS.json']
    assert sha(OLD/'REQUEST_MANIFEST.json')==manifest['source_sha256']['REQUEST_MANIFEST.json']
    assert sha(OLD/'DEPTH_INPUT_AUDIT.json')==manifest['source_sha256']['DEPTH_INPUT_AUDIT.json']
    request_seal=read(public/'REQUESTS_SEALED.json')
    assert request_seal['status']=='ALL_25_BODIES_FROZEN_BEFORE_FORMAL'
    assert request_seal['logical_sha256']==sha(public/'REQUESTS_LOGICAL.json')
    assert request_seal['manifest_sha256']==sha(public/'REQUEST_MANIFEST.json')
    assert request_seal['lock_sha256']==sha(public/'CODE_AND_INPUT_LOCK.json')
    assert request_seal['body_gate_sha256']==sha(public/'BODY_GATE.json')
    records={x['attempt_id']:x for x in request_seal['records']}
    assert set(records)==set(schedule) and len(request_seal['records'])==25
    uploads=lines(private/'UPLOAD_LEDGER.jsonl')
    uploaded={x['sha256']:x['file_id'] for x in uploads if x['phase']=='END'}
    assert {x['sha256'] for request in logical for x in request['images']}<=set(uploaded)
    gate=read(public/'BODY_GATE.json');assert gate['bodies']['status']=='BODY_GATE_PASS'
    gate_records={x['attempt_id']:x for x in gate['bodies']['records']}
    for request in logical:
        attempt=request['attempt_id'];path=private/'bodies'/(attempt+'.json')
        payload=path.read_bytes()
        assert payload==wire(body(request,uploaded)),attempt
        assert hashlib.sha256(payload).hexdigest()==records[attempt]['payload_sha256']==gate_records[attempt]['payload_sha256']
    events=lines(public/'CALL_LEDGER.jsonl')
    starts={};ends={}
    for event in events:
        a=event['attempt_id']
        assert a in schedule or a=='S001'
        if event['phase']=='START':
            assert a not in starts;starts[a]=event
        elif event['phase']=='END':
            assert a in starts and a not in ends;ends[a]=event
        else:raise AssertionError(event['phase'])
    assert len(starts)<=26
    if 'S001' in starts:
        assert 'S001' in ends and ends['S001']['transport_valid']
        smoke=public/'responses/S001.json'
        assert sha(smoke)==ends['S001']['response_sha256']
        assert read(smoke)['smoke_ok'] is True
    formal_starts={a for a in starts if a in schedule}
    assert all(request_seal['at']<starts[a]['at'] for a in formal_starts)
    for a in formal_starts:
        assert starts[a]['payload_sha256']==records[a]['payload_sha256']
        if a in ends:assert starts[a]['at']<=ends[a]['at']
        if a in ends and ends[a]['transport_valid']:
            response=public/'responses'/(a+'.json')
            assert response.exists() and sha(response)==ends[a]['response_sha256']
            assert read(response)['attempt_id']==a
        elif a in ends:
            assert not (public/'responses'/(a+'.json')).exists()
    for a in schedule:
        if a not in starts:assert not (public/'responses'/(a+'.json')).exists()
    seal_path=public/'RESPONSES_SEALED.json'
    full=seal_path.exists()
    if full:
        seal=read(seal_path)
        assert seal['status']=='ALL_25_RESPONSES_SEALED_BEFORE_SCORE'
        assert seal['request_seal_sha256']==sha(public/'REQUESTS_SEALED.json')
        assert set(ends)>=set(schedule) and all(ends[a]['transport_valid'] for a in schedule)
        assert seal['at']>=max(ends[a]['at'] for a in schedule)
        assert {x['attempt_id']:x['response_sha256'] for x in seal['records']}=={
            a:sha(public/'responses'/(a+'.json')) for a in schedule}
    else:
        partial=read(public/'PARTIAL_RESPONSES_SEALED.json')
        assert partial['status']=='PARTIAL_STOP'
        assert partial['request_seal_sha256']==sha(public/'REQUESTS_SEALED.json')
        assert partial['ledger_sha256']==sha(public/'CALL_LEDGER.jsonl')
    return dict(schedule=schedule,logical={x['attempt_id']:x for x in logical},
                starts=starts,ends=ends,full=full,seal_sha256=sha(seal_path if full else public/'PARTIAL_RESPONSES_SEALED.json'))


def fact_ids(packet):
    ids=set()
    def visit(value):
        if isinstance(value,dict):
            for key in ('fact_id',):
                if isinstance(value.get(key),str):ids.add(value[key])
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(packet)
    table=packet.get('INTERACTION_TABLE')
    if table:
        for row in table['rows']:
            ids.add(row[table['columns'].index('fact_id')])
    return ids


def parse_response(content,packet):
    try:obj=json.loads(content)
    except (ValueError,TypeError):return dict(parseable=False,usable=False,raw_choice=None,errors=['NOT_JSON'],cited=[])
    if not isinstance(obj,dict):return dict(parseable=False,usable=False,raw_choice=None,errors=['NOT_OBJECT'],cited=[])
    choice=obj.get('preferred_hypothesis');assess=obj.get('hypothesis_assessments')
    structural=(obj.get('request_id')==packet['request_id'] and choice in ('H1','H2','DEFER')
                and isinstance(assess,list) and len(assess)==2
                and all(isinstance(x,dict) for x in assess) and {x.get('id') for x in assess}=={'H1','H2'})
    errors=[];cited=[]
    if not structural:errors.append('INVALID_STRUCTURE')
    else:
        allowed=fact_ids(packet)
        for entry in assess:
            if not isinstance(entry.get('unresolved_assumptions'),list):errors.append('INVALID_ASSUMPTIONS')
            for key in ('supporting_fact_ids','conflicting_fact_ids'):
                facts=entry.get(key)
                if not isinstance(facts,list) or any(not isinstance(x,str) or x not in allowed for x in facts):
                    errors.append('INVALID_'+key.upper())
                else:cited.extend(facts)
        if choice in ('H1','H2') and not next(x for x in assess if x['id']==choice).get('supporting_fact_ids'):
            errors.append('NO_CHOSEN_SUPPORT')
        if choice=='DEFER' and not obj.get('uncertainty_reason'):
            errors.append('NO_DEFER_REASON')
    return dict(parseable=structural,usable=structural and not errors,raw_choice=choice,
                errors=sorted(set(errors)),cited=cited,uncertainty_reason=obj.get('uncertainty_reason'))


def bind(case,episode,case_source,old_key):
    endpoints={role:(episode['PRE_HISTORY' if role in 'AB' else 'POST_HISTORY_TO_Q'][role]['observations'][-1]) for role in 'ABXY'}
    path=AO0/(case_source['split']+'_rel_v2')/'RELATION_TIMELINE.jsonl.gz'
    frames={x['source_frame'] for x in endpoints.values()};relations={}
    with gzip.open(path,'rt',encoding='utf-8') as fh:
        for line in fh:
            row=json.loads(line)
            if row['frame'] in frames:relations.setdefault((row['frame'],row['native_id']),[]).append(row)
    roles={}
    for role,o in endpoints.items():
        frame=o['source_frame'];native_id=int(o['source_fact_ids'][0].split('-N')[1])
        matches=[x for x in relations.get((frame,native_id),[]) if x['status']=='UNIQUE']
        roles[role]=dict(frame=frame,source_mask_rle_sha256=o['source_mask_rle_sha256'],
            status='UNIQUE' if len(matches)==1 else 'NONUNIQUE',
            gt_id=matches[0]['gt_id'] if len(matches)==1 else None,
            match_iou=matches[0]['match_iou'] if len(matches)==1 else None)
    g={r:roles[r]['gt_id'] for r in 'ABXY'};why=None;physical=None
    if None in g.values():why='NONUNIQUE_ENDPOINT_GT_BINDING'
    elif g['A']==g['B'] or g['X']==g['Y']:why='DUPLICATE_PHYSICAL_ROLE'
    elif {g['A'],g['B']}!={g['X'],g['Y']}:why='ACTUAL_MAPPING_OUTSIDE_TWO_CANDIDATES'
    else:
        xy={r:'A' if g[r]==g['A'] else 'B' for r in 'XY'}
        choices=episode['hypotheses']
        candidate=[x['mapping'] for x in choices if all(x['mapping'][r]==xy[r] for r in 'XY')]
        if len(candidate)!=1:why='CANDIDATE_MISMATCH'
        else:physical=canonical(candidate[0])
    old_mapping=next(x['mapping'] for x in old_key['candidate_mapping'] if x['choice']==old_key['private_score_answer'])
    return dict(case=case,roles=roles,correct_physical_mapping=dict(physical) if physical else None,
        reference_scoreable=physical is not None,unscorable_reason=why,
        old_to_new_reference=episode['old_to_new_reference'],
        old_answer_relation='UNKNOWN' if physical is None else
            'SAME_MAPPING_POSTHOC' if all(dict(physical)[r]==old_mapping[r] for r in 'XY') else 'DIFFERENT_MAPPING_POSTHOC',
        old_answer_not_assumed=True,relation_timeline_sha256=sha(path),old_key_sha256=sha(AO1/'SCORE_KEY.json'))


def classify(response,packet,binding):
    if response is None:return dict(status='UNSENT',transport_valid=False,finish_reason=None,
                                     parseable=False,usable=False,raw_choice=None,physical_choice=None,evidence_errors=[])
    if response.get('transport_valid') is not True:
        return dict(status='HTTP_UNKNOWN',transport_valid=False,finish_reason=None,
                    parseable=False,usable=False,raw_choice=None,physical_choice=None,evidence_errors=[])
    parsed=parse_response(response.get('content'),packet)
    raw=parsed['raw_choice'];mapping=None
    if raw in ('H1','H2'):
        match=[x for x in packet['hypotheses'] if x['id']==raw]
        if len(match)==1:mapping=dict(canonical(match[0]['mapping']))
    if response.get('finish_reason')!='stop':status='TRUNCATED'
    elif not parsed['parseable']:status='UNPARSEABLE'
    elif not parsed['usable']:status='INVALID_EVIDENCE'
    elif not binding['reference_scoreable']:status='UNSCORABLE_NEW_REFERENCE'
    elif raw=='DEFER':status='DEFER'
    else:status='CORRECT' if canonical(mapping)==canonical(binding['correct_physical_mapping']) else 'WRONG'
    return dict(status=status,transport_valid=True,finish_reason=response.get('finish_reason'),
        parseable=parsed['parseable'],usable=parsed['usable'],raw_choice=raw,physical_choice=mapping,
        evidence_errors=parsed['errors'],cited_fact_ids=parsed['cited'],
        uncertainty_reason=parsed.get('uncertainty_reason'))


def summary(attempts,bindings,full):
    by_case={case:{x['arm']:x for x in attempts if x['case']==case} for case in sorted(bindings)}
    valid=lambda x:x['transport_valid'] and x['finish_reason']=='stop' and x['parseable'] and x['usable'] and bindings[x['case']]['reference_scoreable']
    negatives=[x for case in ('B02','B03','B04','B05') for arm in ('H-D','H-D-REPEAT','H-D-PERMUTE') for x in [by_case[case][arm]]]
    negative_safe=all(valid(x) and x['status'] in ('CORRECT','DEFER') for x in negatives)
    positives=[by_case['B01'][arm] for arm in ('H-D','H-D-REPEAT','H-D-PERMUTE')]
    b01_stable=all(valid(x) and x['status']=='CORRECT' for x in positives)
    gain=any(valid(e) and valid(h2) and valid(hd) and e['status'] in ('WRONG','DEFER')
             and h2['status']=='CORRECT' and hd['status']=='CORRECT'
             for case in by_case for e,h2,hd in [(by_case[case]['E'],by_case[case]['H-2D'],by_case[case]['H-D'])])
    technical=full and sum(x['parseable'] for x in attempts)>=24 and all(x['parseable'] for x in by_case['B01'].values())
    return dict(full_response_seal=full,formal_requests_started=sum(x['status']!='UNSENT' for x in attempts),
        returned=sum(x['transport_valid'] for x in attempts),parseable=sum(x['parseable'] for x in attempts),
        usable=sum(x['usable'] for x in attempts),technical_gate=technical,
        B01_HD_physical_stable=b01_stable,negative_HD_safe=negative_safe,
        exposed_E_to_history_gain=gain,limited_exposed_signal=technical and b01_stable and negative_safe and gain,
        unscorable_cases=[c for c,b in bindings.items() if not b['reference_scoreable']],
        VLM_necessity='NOT_TESTED_NO_FULL_SAME_INFORMATION_NUMERIC_COMPARATOR')


def main(run):
    chain=verify_chain(run)  # Only now may GT and the old answer key be opened.
    source={x['case_alias']:x for x in read(AO1/'SOURCE_MANIFEST.json')['cases']}
    old_key={x['case_alias']:x for x in read(AO1/'SCORE_KEY.json')['cases']}
    episodes={x['request_id'].split('-')[-1]:x for x in read(OLD/'EPISODE_FACTS.json')}
    bindings={case:bind(case,episode,source[case],old_key[case]) for case,episode in episodes.items()}
    attempts=[]
    for attempt in chain['schedule']:
        request=chain['logical'][attempt];packet=json.loads(request['text'])
        if attempt in chain['starts'] and attempt not in chain['ends']:response={'transport_valid':False}
        elif attempt in chain['starts'] and chain['ends'][attempt]['transport_valid']:
            response=read(Path(run)/'public/responses'/(attempt+'.json'))
        elif attempt in chain['starts']:response={'transport_valid':False}
        else:response=None
        scored=classify(response,packet,bindings[request['case']])
        attempts.append(dict(attempt_id=attempt,case=request['case'],arm=request['arm'],
            reference_scoreable=bindings[request['case']]['reference_scoreable'],**scored,
            response_sha256=sha(Path(run)/'public/responses'/(attempt+'.json')) if response and response.get('transport_valid') else None,
            usage=response.get('usage') if response else None,charged_upper_usd=response.get('charged_upper_usd') if response else None))
    events=[dict(case=case,trigger_scope=episodes[case]['trigger']['scope'],
        correct_physical_mapping=bindings[case]['correct_physical_mapping'],
        arms={x['arm']:{k:x[k] for k in ('status','raw_choice','physical_choice','parseable','usable','evidence_errors')}
              for x in attempts if x['case']==case}) for case in sorted(bindings)]
    public=Path(run)/'public'
    save(public/'REFERENCE_BINDING.json',bindings)
    save(public/'ATTEMPT_RESULTS.json',attempts)
    save(public/'EVENT_RESULTS.json',events)
    result=summary(attempts,bindings,chain['full'])
    result['response_seal_sha256']=chain['seal_sha256']
    smoke=read(public/'responses/S001.json') if (public/'responses/S001.json').exists() else None
    unknown_reserve=sum(v.get('reserve_peak_usd',0) for a,v in chain['starts'].items() if a not in chain['ends'])
    result['returned_peak_rate_usd']=sum(x['charged_upper_usd'] or 0 for x in attempts)+(smoke['charged_upper_usd'] if smoke else 0)
    result['unknown_reserved_usd']=unknown_reserve
    result['charged_peak_upper_usd']=result['returned_peak_rate_usd']+unknown_reserve
    save(public/'SUMMARY.json',result)
    print({k:result[k] for k in ('returned','parseable','usable','limited_exposed_signal','charged_peak_upper_usd')})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True)
    main(parser.parse_args().run)
