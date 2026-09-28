"""Verify paid request/response binding and score each raw S0 choice after seal."""
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path

from postseal_event import MATCHES,PAIRS,rows,verdict

HERE=Path(__file__).resolve().parent
RUN=HERE/'run_development_v7_paid'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def compact(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()


def check_calls(public,seal):
    ledger=public/'CALL_LEDGER.jsonl'
    assert digest(ledger.read_bytes())==seal['call_ledger_sha256']
    calls=defaultdict(list)
    for line in ledger.read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        calls[row['tag']].append(row)
    for tag,entries in calls.items():
        phases=[x['phase'] for x in entries]
        assert phases in (['UNSENT'],['START','END'],['START','HTTP_UNKNOWN']), (tag,phases)
        request=json.loads((public/'requests'/f'{tag}.json').read_text(encoding='utf-8'))
        assert set(request)=={'system','user','images'}
        if phases[0]=='START':
            start=entries[0]
            assert digest(compact(request))==start['public_packet_sha256']
            body=json.loads((RUN/'private_api'/f'{tag}.body.json').read_text(encoding='utf-8'))
            assert digest(compact(body))==start['body_sha256']
            assert body['model']=='deepseek-flash'
            if phases[-1]=='END':
                record=(public/'responses'/f'{tag}.json')
                assert digest(record.read_bytes())==entries[-1]['response_sha256']
                response=json.loads(record.read_text(encoding='utf-8'))
                assert response['tag']==tag and response['raw_private_sha256']==digest(
                    (RUN/'private_api'/f'{tag}.raw.json').read_bytes())
    assert sum(x['phase']=='START' for entries in calls.values() for x in entries)==seal['http_attempts']
    return calls


def consensus(items,matches):
    known=[matches[x['frame']].get(str(x['source'])) for x in items]
    known=[x for x in known if x is not None]
    contiguous=all(b['frame']==a['frame']+1 for a,b in zip(items,items[1:]))
    versions={(x.get('source_generation'),x.get('public_epoch')) for x in items}
    return (known[0] if len(known)>=3 and len(set(known))==1 and contiguous
            and len(versions)==1 else None)


def main():
    public=RUN/'public'
    seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING' and seal['mode']=='real'
    assert (public/'METRICS.json').exists() and (public/'PHYSICAL_EVENT_AUDIT.json').exists()
    calls=check_calls(public,seal)
    usage=Counter()
    for response in (public/'responses').glob('*.json'):
        for key,value in (json.loads(response.read_text(encoding='utf-8')).get('usage') or {}).items():
            if type(value) is int:
                usage[key]+=value
    events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))['B-VLM-S0']
    fixed=json.loads((HERE/'CONFIG_V7.json').read_text(encoding='utf-8'))['fixed_model_episodes']
    selected=seal['selected_episodes']
    assert all(x in fixed for x in selected)
    matches={x['frame']:x['native_to_gt'] for x in rows(MATCHES)}
    assert len(matches)==8400
    by_id={x['id']:x for x in events}
    outcomes=[]
    for eid in fixed:
        event=by_id.get(eid)
        if event is None:
            outcomes.append(dict(episode=eid,selected=False,confirm_frame=None,q=None,
                M_status='NOT_STARTED',S_raw_choice=None,S_parse_status=None,numeric_choice=None,
                applied_choice=None,decision_source=None,stage_status='NOT_STARTED',public_id_changes=None,
                M_call_phases=[],S0_call_phases=[],raw_anchor_verdict='NO_Q',
                raw_consensus_verdict='NO_Q',applied_anchor_verdict='NO_Q',
                applied_consensus_verdict='NO_Q'))
            continue
        q=event['q']
        raw=event.get('S_raw_choice')
        restore=event.get('restore') or {}
        row=dict(episode=eid,selected=eid in selected,confirm_frame=event['confirm_frame'],
                 q=q,M_status=event.get('M_status'),S_raw_choice=raw,
                 S_parse_status=event.get('S_parse_status'),numeric_choice=(event.get('numeric') or {}).get('choice'),
                 applied_choice=restore.get('selected_choice'),decision_source=restore.get('decision_source'),
                 stage_status=restore.get('status'),public_id_changes=restore.get('changes'),
                 M_call_phases=[x['phase'] for x in calls.get(eid+'-M',[])],
                 S0_call_phases=[x['phase'] for x in calls.get(eid+'-S0',[])] )
        if q is None:
            row.update(raw_anchor_verdict='NO_Q',raw_consensus_verdict='NO_Q',
                       applied_anchor_verdict='NO_Q',applied_consensus_verdict='NO_Q')
            outcomes.append(row)
            continue
        state=json.loads((RUN/'private_source'/f'{eid}-B-VLM-S0-episode_q.json').read_text(encoding='utf-8'))
        pre={role:state['pre'][role] for role in ('A','B')}
        post=dict(zip(('X','Y'),state['post_roles']))
        anchor={role:(matches[items[-1]['frame']].get(str(items[-1]['source'])) if items else None)
                for role,items in pre.items()}
        stable={role:consensus(items,matches) for role,items in pre.items()}
        current={role:matches[q].get(str(source)) for role,source in post.items()}
        row.update(reference_anchor_available=all(x is not None for x in anchor.values()),
                   reference_consensus_available=all(x is not None for x in stable.values()),
                   q_gt_available=all(x is not None for x in current.values()),
                   raw_anchor_verdict=verdict(anchor,current,raw),
                   raw_consensus_verdict=verdict(stable,current,raw),
                   applied_anchor_verdict=verdict(anchor,current,restore.get('selected_choice')),
                   applied_consensus_verdict=verdict(stable,current,restore.get('selected_choice')),
                   candidate_anchor_verdict={choice:verdict(anchor,current,choice) for choice in PAIRS},
                   candidate_consensus_verdict={choice:verdict(stable,current,choice) for choice in PAIRS})
        outcomes.append(row)
    summary=dict(status='POSTSEAL_PAID_MODEL_AUDIT',fixed_count=len(fixed),
                 selected_count=len(selected),http_attempts=seal['http_attempts'],
                 usage_token_totals=dict(usage),peak_charge_upper_usd=seal['peak_charge_upper_usd'],
                 M_phase_counts=dict(Counter('/'.join(x['M_call_phases']) or 'NONE' for x in outcomes)),
                 S0_phase_counts=dict(Counter('/'.join(x['S0_call_phases']) or 'NONE' for x in outcomes)),
                 raw_choice_counts=dict(Counter(x['S_raw_choice'] or 'NONE' for x in outcomes)),
                 raw_anchor_verdict_counts=dict(Counter(x['raw_anchor_verdict'] for x in outcomes)),
                 raw_consensus_verdict_counts=dict(Counter(x['raw_consensus_verdict'] for x in outcomes)),
                 applied_anchor_verdict_counts=dict(Counter(x['applied_anchor_verdict'] for x in outcomes)),
                 applied_consensus_verdict_counts=dict(Counter(x['applied_consensus_verdict'] for x in outcomes)),
                 no_gt_used_before_prediction_seal=True,events=outcomes)
    output=public/'MODEL_EVENT_AUDIT.json'
    with output.open('x',encoding='utf-8') as handle:
        json.dump(summary,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='events'},ensure_ascii=False))


if __name__=='__main__':
    main()
