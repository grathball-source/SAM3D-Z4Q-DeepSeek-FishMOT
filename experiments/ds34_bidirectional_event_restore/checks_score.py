"""Small real source and synthetic semantic checks; no reference raster access."""
from common import *
import copy
import score


def rejected(label,action,checks):
    try:action()
    except AssertionError:checks.append(dict(name=label,status='PASS_REJECTED_AFTER_SELF_CONSISTENT_REHASH'))
    else:raise AssertionError('Accepted invalid contract: '+label)


def main():
    checks=[];name='feeding_000351_000555';base=input_dir(name)
    row=next(rows(base/'observations.jsonl.gz'));assignment=next(rows(base/'assignments.jsonl.gz'))
    measured=next(rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'));quality=next(rows(DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'))
    rgb=next(r['rgb'] for r in rows(ROOT/'experiments/ds33_rgbd_fixed_lag/RGB_INPUT_PINS.jsonl') if r['segment']==name)
    current=dict(frame=row['frame'],global_frame=row['global_frame'],time=row['time'])
    bound=dict(**current,source_row_sha256=row_sha(row),assignment_row_sha256=row_sha(assignment),
        measured_row_sha256=row_sha(measured),DS18_packet_sha256=digest(quality),
        DS18_extracts={n:score.DEPTH.extract(c) for n,c in quality['objects'].items()},
        raw_source_binding=measured['raw_source_binding'],rgb_pin=rgb,GT=False,
        actual_RGB_read='ONLY_EVENT_ENDPOINTS_SEPARATE_FLOW_LEDGER')
    ledger=dict(frame_inputs_row_sha256=row_sha(bound))
    args=[name,current,assignment,row,measured,quality,bound,ledger,rgb]
    score.verify_frame_contract(*args)
    checks.append(dict(name='REAL_MASK_RAW_DEPTH_DS18_SOURCE_TO_BODY',status='PASS',GT=False))
    for label,mutate in (
        ('WRONG_EXTRACT',lambda a:a[6].__setitem__('DS18_extracts',{})),
        ('WRONG_SERIALIZED_FRAME',lambda a:a[6].__setitem__('global_frame',a[1]['global_frame']+1)),
        ('WRONG_RGB_SOURCE',lambda a:a[6].__setitem__('rgb_pin',dict(a[8],sha256='0'*64)) )):
        bad=copy.deepcopy(args);mutate(bad);bad[7]['frame_inputs_row_sha256']=row_sha(bad[6])
        rejected(label,lambda:score.verify_frame_contract(*bad),checks)
    bad=copy.deepcopy(args);native=next(iter(bad[5]['objects']));cert=bad[5]['objects'][native]
    cert['whole']['inclusive_summary']['n']+=1
    cert['whole']['inclusive_statistics_sha256']=digest(cert['whole']['inclusive_summary'])
    cert['certificate_sha256']=digest({k:v for k,v in cert.items() if k!='certificate_sha256'})
    bad[6]['DS18_packet_sha256']=digest(bad[5]);bad[6]['DS18_extracts']={n:score.DEPTH.extract(c) for n,c in bad[5]['objects'].items()}
    bad[7]['frame_inputs_row_sha256']=row_sha(bad[6])
    rejected('REHASHED_QUALITY_DISAGREES_WITH_ORIGINAL_MEASUREMENT',lambda:score.verify_frame_contract(*bad),checks)
    known=dict(status='UNIQUE_IOU_MATCH',gt_id=1)
    assert score._verdict('UNKNOWN')=='UNSCORABLE' and score._combine([])=='UNSCORABLE'
    assert score._consensus([known,known])['status']!='UNIQUE_IOU_MATCH'
    assert score._consensus([known,known,dict(status='SOURCE_OR_REFERENCE_MISSING')])['status']!='UNIQUE_IOU_MATCH'
    assert score._consensus([known,known,dict(status='UNIQUE_IOU_MATCH',gt_id=2)])['status']!='UNIQUE_IOU_MATCH'
    assert score._consensus([known]*3)['gt_id']==1
    assert score.same(known,dict(status='NO_PRIOR_PUBLIC_ORIGIN_REFERENCE'))=='UNKNOWN'
    checks.append(dict(name='FIXED_FRAGMENT_MISSING_CONFLICT_AND_PUBLIC_ORIGIN_NOT_SAFE_PASS',status='PASS'))
    records={f:dict(row=dict(frame=f,global_frame=f,time=f*.1)) for f in range(1,6)}
    transactions={('EVENT_RGB',f):dict(full_state_sha256=digest(f)) for f in range(3,6)}
    predictions={3:dict(variants=dict(EVENT_RGB=[dict(id=7,mask='n:7'),dict(id=8,mask='n:8')]))}
    event=dict(id='synthetic',suspect_frame=2,q=3,decision_cutoff=5,public_ids=[10,20],
        bank_snapshot={'10':dict(anchor=None),'20':dict(anchor=None)},
        joint_pre={r:dict(public=k,anchor=None,status='UNKNOWN_REFERENCE',samples=[]) for r,k in zip(('A','B'),(10,20))},
        post_roles={'7':[],'8':[]},joint_decision=dict(choice='DEFER',status='DEFER',mapping=None,causal_max_frame=3),
        restore=dict(staged=False,changes={}),actual_first_mapping={'7':7,'8':8},first_published_mapping={'7':7,'8':8},
        first_publish_at_arrival_frame=5,future_in_q_state=False,post_used_as_anonymous_until_selected=True,
        lag_resolution=dict(checkpoint_frame=2,through_frame=5,evidence_max_frame=5,previous_state_sha256=digest(2),
            selected_state_sha256=digest(5),replay_state_sha256=[dict(frame=f,sha256=digest(f)) for f in range(3,6)]))
    ledgers={3:dict(first_publish_at_arrival_frame=5)}
    score.verify_event(event,'EVENT_RGB',records,transactions,predictions,ledgers,{})
    checks.append(dict(name='UNKNOWN_REFERENCE_DEFER_IS_ALLOWED_NOT_A_CORRECT_RESULT',status='PASS'))
    for label,mutate in (
        ('FUTURE_DECISION',lambda e:e['joint_decision'].__setitem__('causal_max_frame',6)),
        ('ALTERED_FIRST_PUBLIC_MAPPING',lambda e:e['first_published_mapping'].__setitem__('7',10)),
        ('ALTERED_INTERMEDIATE_FULL_STATE_HASH',lambda e:e['lag_resolution']['replay_state_sha256'][1].__setitem__('sha256',digest(400))),
        ('DEFER_CANNOT_CERTIFY_JOINT_STAGE',lambda e:e['restore'].__setitem__('staged',True))):
        bad=copy.deepcopy(event);mutate(bad)
        rejected(label,lambda:score.verify_event(bad,'EVENT_RGB',records,transactions,predictions,ledgers,{}),checks)
    g,p,sims=[[1],[1],[1]],[[11],[11],[22]],[score.np.ones((1,1))]*3
    actual=score.metrics(g,p,sims)[0];previous,step,switches={},{},[]
    for f,(gi,pi,si) in enumerate(zip(g,p,sims),1):
        step,added=score.clear_step(gi,['n:7'],pi,si,previous,step,f);switches.extend(added)
    assert actual['IDSW']==len(switches)==1 and actual['predictions']==3
    checks.append(dict(name='UNCHANGED_OFFICIAL_CLEAR_SYNTHETIC_SWITCH_COUNT',status='PASS'))
    old_switch=dict(switches[0],segment='synthetic');new_switch=dict(old_switch,from_public_id=101,to_public_id=202,public_id=202)
    values={arm:[] for arm in ARMS};values['Z4Q_FROZEN']=[old_switch];values['EVENT_RGBD']=[new_switch]
    changes=score.switch_changes(values)['Z4Q_FROZEN_TO_EVENT_RGBD']
    assert len(changes['added'])==len(changes['eliminated'])==1 and changes['net_IDSW']==0
    assert not changes['occurrence_added'] and not changes['occurrence_eliminated']
    checks.append(dict(name='NET_ZERO_PRESERVES_ADDED_AND_ELIMINATED_SWITCHES',status='PASS'))
    # A complete synthetic logical body exercises source-to-score arithmetic,
    # not merely the hash or container shape. It is never a formal flow/result.
    import checks_evidence as fixture_code
    import evidence
    episode,pre,packets=fixture_code.fixture()
    episode['confirmed_post_roles']=copy.deepcopy(episode['post_roles'])
    for role,k in zip(('A','B'),episode['public_ids']):
        pre[role].update(public=k,version=[k,1,k,0],status='EXACT_INDEPENDENT_VERSIONED_REFERENCE')
    pair_cache={}
    def provider(a,b):
        pair=fixture_code.Pair(a,b,packets);pair_cache[a,b]=pair;return pair
    decision=evidence.choose(episode,pre,packets,True,provider)
    event=dict(episode,id='synthetic_joint',decision_cutoff=14,joint_pre=pre,joint_decision=decision,
        bank_snapshot={str(k):dict(anchor=pre[r]['anchor']) for r,k in zip(('A','B'),episode['public_ids'])},
        restore=dict(staged=True,changes={}),actual_first_mapping=decision['mapping'],first_published_mapping=decision['mapping'],
        first_publish_at_arrival_frame=14,future_in_q_state=False,post_used_as_anonymous_until_selected=True,
        lag_resolution=dict(checkpoint_frame=11,through_frame=14,evidence_max_frame=14,previous_state_sha256=digest(11),
            selected_state_sha256=digest(14),replay_state_sha256=[dict(frame=f,sha256=digest(f)) for f in range(12,15)]))
    record={f:dict(row=p['row'],source_row_sha256=row_sha(p['row']),assignment_row_sha256=row_sha(p['assignment']),
        masks={str(n):array_hash(m) for n,m in p['masks'].items()},extracts={str(n):x for n,x in p['extracts'].items()},
        adaptive_full=p['measured']['adaptive_full'],source_generations={str(n):1 for n in p['masks']}) for f,p in packets.items()}
    record[11]=dict(row=dict(frame=11,time=1.1))
    transaction={('EVENT_RGBD',f):dict(mapping={str(n):n for n in (1,2)},actual_epochs={'1':0,'2':0},
        bank_anchors={str(n):dict(frame=f,native_id=n,canonical_id=n,mask=f'n:{n}') for n in (1,2)},full_state_sha256=digest(f)) for f in range(1,15)}
    decision=json.loads(json.dumps(decision));event=json.loads(json.dumps(event))
    transaction['EVENT_RGBD',12].update(controller_trace=dict(ds34_group_restore=dict(
        episode='synthetic_joint',q=12,selected=decision['mapping'],complete_member_bijection=True,
        outside_state_preserved=True,future_measurements_written=False,physical_identity='UNKNOWN_UNTIL_POSTSEAL')),
        actual_aliases={n:dict(target=k,source='DS34_EVENT_NUMERIC') for n,k in decision['mapping'].items()})
    prediction={12:dict(variants=dict(EVENT_RGBD=[dict(id=k,mask=f'n:{n}') for n,k in decision['mapping'].items()]))}
    flow_pairs={('synthetic_joint','EVENT_RGBD',a,b):dict(actual_pair=p.numeric_summary) for (a,b),p in pair_cache.items()}
    score.verify_event(event,'EVENT_RGBD',record,transaction,prediction,{12:dict(first_publish_at_arrival_frame=14)},flow_pairs)
    checks.append(dict(name='FULL_JOINT_SYNTHETIC_BODY_ARITHMETIC_REFERENCE_MAPPING_BINDING',status='PASS'))
    for label,mutate in (
        ('MODALITY_WEIGHT_TAMPER',lambda e:e['joint_decision']['common_weights'].__setitem__('depth',0.)),
        ('MOTION_AGGREGATE_TAMPER',lambda e:e['joint_decision']['scores'][0]['edges'][0].__setitem__('geometry',99.)),
        ('DEPTH_SUMMARY_TAMPER',lambda e:e['joint_decision']['scores'][0]['edges'][0].__setitem__('depth_cost',0.))):
        bad=copy.deepcopy(event);mutate(bad)
        for candidate in bad['joint_decision']['scores']:
            w=bad['joint_decision']['common_weights']
            candidate['score']=sum(e['geometry']+w['contour']*(e['contour_cost'] or 0.)+w['depth']*e['depth_cost'] for e in candidate['edges'])
        rejected(label,lambda:score.verify_event(bad,'EVENT_RGBD',record,transaction,prediction,{12:dict(first_publish_at_arrival_frame=14)},flow_pairs),checks)
    destination=HERE/(sys.argv[1] if len(sys.argv)>1 else 'SCORE_CHECKS.json')
    write_new(destination,dict(status='PASS',checks=checks,GT_opened=False,annotations_opened=False,
        new_model_http=0,cost_usd=0,code=artifact(score.__file__),scoring_dependencies=score.scoring_dependencies(),
        scope='Source/protocol and synthetic arithmetic only; not method performance.'))
    print('DS34 SCORE CHECKS PASS',len(checks),flush=True)


if __name__=='__main__':main()
