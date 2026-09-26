"""Independent postseal scoring of new reference semantics."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
AO1=REPO/'experiments/ao1_input_fidelity'
AO0=REPO/'experiments/ao0_association_observability'


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    p=Path(p);assert not p.exists(),p
    p.write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def verify(run):
    q=read(run/'REQUESTS_SEALED.json');s=read(run/'RESPONSES_SEALED.json')
    schedule=read(run/'REQUEST_MANIFEST.json')['schedule']
    assert len(schedule)==len(set(schedule))==25
    assert q['status']=='ALL_25_BODIES_FROZEN_BEFORE_FORMAL'
    assert s['status']=='ALL_25_RESPONSES_SEALED_BEFORE_SCORE'
    assert s['request_seal_sha256']==sha(run/'REQUESTS_SEALED.json')
    qs={x['attempt_id']:x for x in q['records']};ss={x['attempt_id']:x for x in s['records']}
    assert set(qs)==set(ss)==set(schedule)
    ledger=[json.loads(x) for x in (run/'CALL_LEDGER.jsonl').read_text().splitlines()]
    starts={x['attempt_id']:x for x in ledger if x['phase']=='START'}
    ends={x['attempt_id']:x for x in ledger if x['phase']=='END'}
    assert len(starts)==len(ends)==len(ledger)//2==26
    assert set(starts)==set(schedule)|{'S001'}
    assert q['at']<min(starts[x]['at'] for x in schedule)
    assert s['at']>=max(ends[x]['at'] for x in schedule)
    for a in schedule:
        assert ends[a]['transport_valid']
        assert sha(run/'responses'/(a+'.json'))==ss[a]['response_sha256']==ends[a]['response_sha256']
    assert read(run/'responses/S001.json')['smoke_ok'] is True
    return schedule


def fact_ids(packet):
    ids=set()
    def visit(v):
        if isinstance(v,dict):
            if isinstance(v.get('fact_id'),str):ids.add(v['fact_id'])
            ids.update(v.get('source_fact_ids',[]))
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(packet)
    ids.update(row[0] for row in packet.get('INTERACTION_TABLE',{}).get('rows',[]))
    return ids


def parse(content,packet):
    try:v=json.loads(content)
    except (ValueError,TypeError):return dict(parseable=False,raw_choice=None,usable=False,errors=['NOT_JSON'])
    if not isinstance(v,dict):return dict(parseable=False,raw_choice=None,usable=False,errors=['NOT_OBJECT'])
    choice=v.get('preferred_hypothesis')
    structural=v.get('request_id')==packet['request_id'] and choice in ('H1','H2','DEFER')
    errors=[] if structural else ['INVALID_DECISION_STRUCTURE']
    assessments=v.get('hypothesis_assessments')
    if not isinstance(assessments,list) or len(assessments)!=2 or {x.get('id') for x in assessments if isinstance(x,dict)}!={'H1','H2'}:
        errors.append('INVALID_ASSESSMENTS')
    else:
        allowed=fact_ids(packet)
        for a in assessments:
            for field in ('supporting_fact_ids','conflicting_fact_ids'):
                cited=a.get(field)
                if not isinstance(cited,list) or any(not isinstance(x,str) or x not in allowed for x in cited):
                    errors.append('INVALID_'+field.upper()+'_'+a['id'])
            if not isinstance(a.get('unresolved_assumptions'),list):errors.append('INVALID_ASSUMPTIONS_'+a['id'])
    if not isinstance(v.get('uncertainty_reason'),str):errors.append('INVALID_UNCERTAINTY_REASON')
    return dict(parseable=structural,raw_choice=choice,usable=structural and not errors,errors=errors,
                uncertainty_reason=v.get('uncertainty_reason'))


def bind(packet,split,old_key):
    endpoints={r:(packet['PRE_HISTORY'][r]['observations'][-1] if r in 'AB' else
                  packet['POST_HISTORY_TO_Q'][r]['observations'][-1]) for r in 'ABXY'}
    frames={x['source_frame'] for x in endpoints.values()}
    path=AO0/(split+'_rel_v2')/'RELATION_TIMELINE.jsonl.gz'
    with gzip.open(path,'rt',encoding='utf-8') as fh:
        relations=[v for line in fh if (v:=json.loads(line))['frame'] in frames]
    roles={}
    for role,o in endpoints.items():
        frame=o['source_frame'];native=int(o['source_fact_ids'][0].split('-N')[1])
        m=[x for x in relations if x['frame']==frame and x['native_id']==native and x['status']=='UNIQUE']
        roles[role]=dict(frame=frame,native_mask_key=f'n:{native}',source_mask_rle_sha256=o['source_mask_rle_sha256'],
                         status='UNIQUE' if len(m)==1 else 'UNSCORABLE_NONUNIQUE',
                         gt_id=m[0]['gt_id'] if len(m)==1 else None,
                         match_iou=m[0]['match_iou'] if len(m)==1 else None)
    g={r:roles[r]['gt_id'] for r in 'ABXY'}
    answer=None;why=None
    if None in g.values():why='NONUNIQUE_ENDPOINT_GT_BINDING'
    elif g['A']==g['B'] or g['X']==g['Y']:why='DUPLICATE_PHYSICAL_ROLE'
    elif {g['A'],g['B']}!={g['X'],g['Y']}:why='ACTUAL_MAPPING_OUTSIDE_TWO_CANDIDATES'
    else:
        mapping={r:('A' if g[r]==g['A'] else 'B') for r in 'XY'}
        found=[h['id'] for h in packet['hypotheses'] if all(h['mapping'][r]==mapping[r] for r in 'XY')]
        answer=found[0] if len(found)==1 else None
        if answer is None:why='CANDIDATE_MISMATCH'
    old_correct=next(x['mapping'] for x in old_key['candidate_mapping'] if x['choice']==old_key['private_score_answer'])
    new_correct=next((x['mapping'] for x in packet['hypotheses'] if x['id']==answer),None)
    return dict(case=packet['request_id'].split('-')[-1],roles=roles,score_answer=answer,
                unscorable_reason=why,old_to_new_reference=packet['old_to_new_reference'],
                old_answer_relation=('UNKNOWN' if new_correct is None else
                    'SAME_MAPPING_POSTHOC' if all(new_correct[r]==old_correct[r] for r in 'XY') else 'DIFFERENT_MAPPING_POSTHOC'),
                old_answer_not_assumed=True,relation_timeline_sha256=sha(path),old_key_sha256=sha(AO1/'SCORE_KEY.json'))


def main(run):
    schedule=verify(run)
    # GT relation timeline and old answer key are first opened after full seal verification.
    keys={x['case_alias']:x for x in read(AO1/'SCORE_KEY.json')['cases']}
    cases={x['case_alias']:x for x in read(AO1/'SOURCE_MANIFEST.json')['cases']}
    episodes={x['request_id'].split('-')[-1]:x for x in read(run/'EPISODE_FACTS.json')}
    bindings={c:bind(p,cases[c]['split'],keys[c]) for c,p in episodes.items()}
    save(run/'CASE_SCORE_BINDING.json',bindings)
    logical={x['attempt_id']:x for x in read(run/'REQUESTS_LOGICAL.json')['requests']}
    attempts=[]
    for a in schedule:
        request=logical[a];p=json.loads(request['text']);c=request['case']
        response=read(run/'responses'/(a+'.json'))
        parsed=parse(response.get('content'),p)
        raw=parsed['raw_choice'];correct=bindings[c]['score_answer']
        if not parsed['parseable']:status='UNPARSEABLE'
        elif correct is None:status='UNSCORABLE_NEW_REFERENCE'
        elif raw=='DEFER':status='DEFER'
        else:
            mapping=next(h['mapping'] for h in p['hypotheses'] if h['id']==raw)
            target=next(h['mapping'] for h in p['hypotheses'] if h['id']==correct)
            status='CORRECT' if mapping==target else 'WRONG'
        attempts.append(dict(attempt_id=a,case=c,arm=request['arm'],raw_choice=raw,
            parseable=parsed['parseable'],usable=parsed['usable'],evidence_errors=parsed['errors'],
            status=status,actual_new_reference_answer=correct,uncertainty_reason=parsed['uncertainty_reason'],
            finish_reason=response['finish_reason'],usage=response['usage'],latency_seconds=response['latency_seconds'],
            charged_upper_usd=response['charged_upper_usd'],response_sha256=sha(run/'responses'/(a+'.json'))))
    save(run/'ATTEMPT_RESULTS.json',attempts)
    numeric=read(run/'NUMERIC_REFERENCE.json');events=[]
    for c,p in episodes.items():
        arm={x['arm']:x for x in attempts if x['case']==c}
        events.append(dict(case=c,trigger=p['trigger']['scope'],score_answer=bindings[c]['score_answer'],
            N_H2D=numeric[c]['N_H2D']['choice'],N_HD=numeric[c]['N_HD']['choice'],
            N_HD_depth_mode=numeric[c]['N_HD']['depth_mode'],
            arms={a:{k:v[k] for k in ('status','raw_choice','parseable','usable','evidence_errors')} for a,v in arm.items()}))
    save(run/'EVENT_RESULTS.json',events)
    smoke=read(run/'responses/S001.json');spent=smoke['charged_upper_usd']+sum(x['charged_upper_usd'] for x in attempts)
    b01=events[0]
    stable=all(b01['arms'][a]['status']=='CORRECT' and b01['arms'][a]['usable'] for a in ('H-D','H-D-REPEAT','H-D-PERMUTE'))
    negative_safe=all(e['arms'][a]['status']!='WRONG' for e in events[1:] for a in ('H-D','H-D-REPEAT','H-D-PERMUTE'))
    gain=any(e['arms']['E']['status']!='CORRECT' and e['arms']['H-2D']['status']=='CORRECT' and e['arms']['H-D']['status']=='CORRECT' for e in events)
    tech=sum(x['parseable'] for x in attempts)>=24 and all(x['parseable'] for x in attempts if x['case']=='B01')
    summary=dict(status='SCORED_AFTER_ALL_25_SEALED',formal_requests=25,smoke_requests=1,
        parseable=sum(x['parseable'] for x in attempts),usable=sum(x['usable'] for x in attempts),
        peak_rate_upper_usd=spent,total_latency_seconds=sum(x['latency_seconds'] for x in attempts),
        technical_gate=tech,B01_HD_stable=stable,negative_HD_safe=negative_safe,
        exposed_E_to_history_change=gain,limited_exposed_signal=tech and stable and negative_safe and gain,
        unscorable_cases=[c for c,v in bindings.items() if v['score_answer'] is None],
        VLM_necessity='NOT_TESTED_NO_FULL_SAME_INFORMATION_NUMERIC_COMPARATOR',
        request_seal_sha256=sha(run/'REQUESTS_SEALED.json'),response_seal_sha256=sha(run/'RESPONSES_SEALED.json'))
    save(run/'SUMMARY.json',summary)
    print({k:summary[k] for k in ('parseable','usable','peak_rate_upper_usd','unscorable_cases','limited_exposed_signal')})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True)
    main(ap.parse_args().run)
