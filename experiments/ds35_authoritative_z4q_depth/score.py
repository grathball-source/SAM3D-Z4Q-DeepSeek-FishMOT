"""Independent source→decision→actual publication audit, then unchanged official metrics."""
from common import *
import copy,time
from collections import Counter
from bridge import stream
from association import choose, DEPTH, E
from verify_inputs import verify_all

_common=sys.modules['common']
try:
    sys.modules['common']=module('ds35_archived_score_namespace',PRIOR/'common.py')
    S=module('ds35_unchanged_official_helpers',PRIOR/'score.py')
finally:sys.modules['common']=_common
ref,metrics,rle,np,coco,FIELDS=S.ref,S.metrics,S.rle,S.np,S.coco,S.FIELDS
polygon_reference,unique_matches,clear_step,same=S.polygon_reference,S.unique_matches,S.clear_step,S.same
S.RUN,S.ARMS,S.EVENT_ARMS,S.STATE_ARMS=RUN,ARMS,EVENT_ARMS,ARMS[1:]
ARCHIVED=PRIOR/'run'

def scoring_dependencies():
    return S.scoring_dependencies()+[artifact(__file__),artifact(HERE/'association.py'),artifact(HERE/'source_contract.py')]

from source_contract import verify_frame_contract

def mapping(prediction,arm):return {int(o['mask'][2:]):o['id'] for o in prediction['variants'][arm]}

def verify_decision(event,arm,records,transactions,predictions,ledgers):
    q=event.get('q')
    if q is None:return
    cutoff=event['decision_cutoff'];assert event['suspect_frame']<q<=cutoff<=min(q+30,len(predictions))
    actual=mapping(predictions[q],arm)
    assert {int(n):k for n,k in event['actual_first_mapping'].items()}==actual
    assert event['first_published_mapping']==event['actual_first_mapping']
    assert event['first_publish_at_arrival_frame']==ledgers[q]['first_publish_at_arrival_frame']>=cutoff
    assert event['future_in_q_state'] is False and event['authority_never_protected']
    decision=event['joint_decision'];pre=copy.deepcopy(event['joint_pre'])
    # Check every included historical point against its actual transaction; not just the last anchor.
    for role,public in zip(('A','B'),event['public_ids']):
        reference=pre[role];samples=reference['samples'];anchor=reference.get('anchor')
        if samples:
            assert reference['status']=='EXACT_INDEPENDENT_VERSIONED_REFERENCE'
            assert samples[-1]['frame']==anchor['frame']<event['suspect_frame']
            assert anchor['canonical_id']==public and samples[-1]['native']==anchor['native_id']
        for sample in samples:
            f,n=sample['frame'],sample['native'];tx=transactions[arm][f]
            assert sample['public']==public and sample['version']==reference['version']
            assert tx['mapping'][str(n)]==public and sample['version'][3]==tx['actual_epochs'].get(str(n),0)
            assert tx['bank_anchors'][str(public)]==dict(frame=f,native_id=n,canonical_id=public,mask='n:'+str(n))
            assert sample['observation_class']=='CLEAN_ACTUAL_BANK_ANCHOR'
            assert tx['source_row_sha256']==row_sha(records[f]['row'])
    for n,values in event['post_roles'].items():
        assert int(n) in mapping(predictions[q],'SAM3_NATIVE')
        assert values[0]['frame']==q and all(q<=s['frame']<=cutoff and s['source']==int(n) for s in values)
        assert all(s['source_generation']==event['post_generations'][n] for s in values)
        for sample in values:
            packet=records[sample['frame']];row=packet['row']
            observations=[o for o in row['observations'] if o['id']==int(n)]
            assert len(observations)==1
            actual_observation=observations[0]
            assert sample['time']==row['time'] and sample['bbox']==actual_observation['box']
            assert sample['area']==actual_observation['area'] and sample['neighbors']==actual_observation.get('neighbors',[])
            assert sample['source_generation']==packet['generations'][int(n)]
            assert sample['observation_class']=='POST_UNASSIGNED'
    if 'scores' in decision or decision.get('original_evidence_reason'):
        packets={f:copy.deepcopy(r) for f,r in records.items() if f<=cutoff}
        required={s['frame'] for v in pre.values() for s in v['samples']}|{s['frame'] for v in event['post_roles'].values() for s in v}
        for f in required:
            p=packets[f];a=p['assignment']
            p['masks']={o['id']:coco.decode(rle(a['masks'][o['mask']])).astype(bool) for o in p['row']['native']}
            p['extracts']={int(n):v for n,v in p['extracts'].items()}
        episode=copy.deepcopy(event)
        episode['post_roles']={int(n):v for n,v in episode['post_roles'].items()}
        episode['post_generations']={int(n):v for n,v in episode['post_generations'].items()}
        if episode.get('confirmed_post_roles'):
            episode['confirmed_post_roles']={int(n):v for n,v in episode['confirmed_post_roles'].items()}
        recomputed=choose(episode,pre,packets,arm=='DEPTH_OVERRIDE')
        assert digest(recomputed)==digest(decision),(event['id'],arm,'source→decision changed')
    restore=event['restore'];tx=transactions[arm][q]
    before={int(n):v for n,v in event['own_q_mapping_before_proposal'].items()}
    if restore['staged']:
        assert decision['depth_gate']['eligible'] and arm=='DEPTH_OVERRIDE'
        assert tx['state_selection']=='DEPTH_EVENT_TRANSACTION'
        assert any(before[n]!=actual[n] for n in before)
        assert {int(n):k for n,k in decision['mapping'].items()}=={int(n):actual[int(n)] for n in event['post_roles']}
        resolution=event['lag_resolution'];assert resolution['evidence_max_frame']==cutoff
        assert resolution['selected_state_sha256']==transactions[arm][cutoff]['full_state_sha256']
        for item in resolution['replay_state_sha256']:
            assert item['sha256']==transactions[arm][item['frame']]['full_state_sha256']
        assert tx['controller_trace']['ds35_depth_event']['outside_state_preserved']
        assert tx['controller_trace']['ds35_depth_event']['actual_q_only_written']
    else:
        assert actual==before and event['lag_resolution'] is None
        assert restore['own_state_before_proposal_sha256']==restore['own_state_after_resolution_sha256']
        assert restore['fallback']['complete_own_state_retained'] and not restore['fallback']['copies_external_B0']

def verify_publications(name,public=None,expected_frames=None):
    from itertools import islice
    public=public or RUN/name/'public'
    limit=expected_frames or SEGMENTS[name][1]-SEGMENTS[name][0]+1
    take=lambda values:islice(values,limit)
    events=read(public/'EVENTS.json');assert set(events)==set(EVENT_ARMS)
    needed={s['frame'] for values in events.values() for e in values for v in e['joint_pre'].values() for s in v['samples']}
    needed|={s['frame'] for values in events.values() for e in values for v in e['post_roles'].values() for s in v}
    needed|={f for values in events.values() for e in values if e.get('q') is not None for f in range(e['q'],e['decision_cutoff']+1)}
    records={};transactions={a:{} for a in ARMS[1:]};predictions={};ledgers={};origins={a:{} for a in ARMS}
    cached=DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'
    txs=rows(public/'TRANSACTIONS.jsonl.gz');archived=rows(PRIOR/'run'/name/'public/predictions.jsonl.gz')
    archived_transactions=rows(PRIOR/'run'/name/'public/TRANSACTIONS.jsonl.gz')
    source=zip(rows(public/'predictions.jsonl.gz'),take(rows(input_dir(name)/'assignments.jsonl.gz')),
        take(stream(input_dir(name)/'observations.jsonl.gz',input_dir(name)/'profiles.jsonl.gz')),
        take(rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz')),take(rows(cached)),rows(public/'FRAME_INPUTS_BINDINGS.jsonl.gz'),
        rows(public/'PUBLISH_LEDGER.jsonl'),take(archived),strict=True)
    parity=Counter();last_seen={};generations={}
    for f,(prediction,assignment,(row,profiles),measured,quality,bound,ledger,archive) in enumerate(source,1):
        assert f==prediction['frame']==row['frame']==ledger['frame']
        verify_frame_contract(name,prediction,assignment,row,measured,quality,bound,ledger,None)
        for o in row['observations']:
            n=o['id'];generations[n]=generations.get(n,0)+(last_seen.get(n)!=f-1);last_seen[n]=f
        assert ledger['prediction_row_sha256']==row_sha(prediction) and not ledger['published_history_rewritten']
        assert ledger['actual_delay_frames']==ledger['first_publish_at_arrival_frame']-f
        assert ledger['first_publish_at_arrival_frame']==min(f+30,limit)
        assert set(prediction['variants'])==set(ARMS)
        assert prediction['variants']['SAM3_NATIVE']==assignment['variants']['N0']==archive['variants']['SAM3_NATIVE']
        assert prediction['variants']['Z4Q_FROZEN']==archive['variants']['Z4Q_FROZEN']==prediction['variants']['DEPTH_OFF']
        masks={o['mask'] for o in assignment['variants']['N0']}
        for a in ARMS:
            vals=prediction['variants'][a];assert {o['mask'] for o in vals}==masks and len(vals)==len(set(o['id'] for o in vals))==len(masks)
            for o in vals:origins[a].setdefault(o['id'],dict(frame=f,native_id=int(o['mask'][2:]),canonical_id=o['id'],mask=o['mask']))
        for a in ARMS[1:]:
            tx=next(txs);assert tx['arm']==a and tx['frame']==f and tx['source_row_sha256']==row_sha(row)
            assert ledger['transaction_row_sha256'][a]==row_sha(tx)
            assert {int(n):k for n,k in tx['mapping'].items()}==mapping(prediction,a)
            if tx['state_selection']=='ORIGINAL_OWN_Z4Q' and a in EVENT_ARMS:
                # Ordinary steps preserve the exact own preview, including after earlier repairs.
                if tx['original_own_preview_state_sha256'] is not None:
                    assert tx['canonical_state_sha256']==tx['original_own_preview_state_sha256']
            for key in ('engine_state_sha256','full_state_sha256','canonical_state_sha256'):S._hash(tx[key])
            transactions[a][f]=tx
        original_archived=next(archived_transactions)
        assert original_archived['arm']=='Z4Q_FROZEN' and original_archived['frame']==f
        for ignored_arm in ('EVENT_RGB','EVENT_RGBD'):
            ignored=next(archived_transactions);assert ignored['arm']==ignored_arm and ignored['frame']==f
        for field in ('mapping','actual_actions','engine_state_sha256','full_state_sha256','actual_aliases',
                      'actual_epochs','actual_provenance','bank_anchors','controller_trace'):
            assert transactions['Z4Q_FROZEN'][f][field]==original_archived[field],(name,f,field,'actual original state mismatch')
        assert transactions['DEPTH_OFF'][f]['canonical_state_sha256']==transactions['Z4Q_FROZEN'][f]['canonical_state_sha256']
        parity['off_state_equal_frames']+=1
        if prediction['variants']['DEPTH_OVERRIDE']==prediction['variants']['Z4Q_FROZEN']:parity['override_publication_equal_frames']+=1
        predictions[f]=prediction;ledgers[f]=ledger
        if f in needed:
            records[f]=dict(row=row,assignment=assignment,extracts=bound['DS18_extracts'],measured=measured,
                generations={o['id']:generations[o['id']] for o in row['observations']})
        if f%1000==0:print('DS35 CONTRACT',name,f,flush=True)
    assert next(txs,None) is None and len(predictions)==limit
    for a,values in events.items():
        for e in values:verify_decision(e,a,records,transactions,predictions,ledgers)
    summary=read(public/'RUN_SUMMARY.json')
    assert summary['authority_never_protected'] and summary['all_fallbacks_keep_complete_own_state']
    assert summary['arms']['DEPTH_OFF']['original_state_parity_frames']==len(predictions)
    assert summary['arms']['DEPTH_OFF']['stages']==0
    return dict(frames=len(predictions),events={a:len(v) for a,v in events.items()},**dict(parity)),origins

def deltas(summary):
    return {base:{a:{k:summary[a][k]-summary[base][k] for k in FIELDS} for a in EVENT_ARMS if a!=base}
        for base in ('SAM3_NATIVE','Z4Q_FROZEN','DEPTH_OFF')}

def switch_changes(switches):
    result={};key=lambda v:(v['segment'],v['frame'],v['gt_id'])
    for base in ('SAM3_NATIVE','Z4Q_FROZEN','DEPTH_OFF'):
        for a in EVENT_ARMS:
            if a==base:continue
            old_values={key(v):v for v in switches[base]};new_values={key(v):v for v in switches[a]}
            result[base+'_TO_'+a]=dict(occurrence_added=[new_values[k] for k in sorted(new_values.keys()-old_values.keys())],
                occurrence_eliminated=[old_values[k] for k in sorted(old_values.keys()-new_values.keys())],
                same_GT_frame_occurrences=[dict(before=old_values[k],after=new_values[k]) for k in sorted(new_values.keys()&old_values.keys())],
                net_IDSW=len(switches[a])-len(switches[base]))
    return result

def score_segment(name,dev_pin,first_public):
    public=RUN/name/'public';start,stop=SEGMENTS[name]
    gt,sims,predictions=[],[],{};pred={a:[] for a in ARMS};matches={}
    previous,step,switches=({a:{} for a in ARMS},{a:{} for a in ARMS},{a:[] for a in ARMS})
    for frame,(prediction,assignment,truth) in enumerate(zip(rows(public/'predictions.jsonl.gz'),
        rows(input_dir(name)/'assignments.jsonl.gz'),ref.reference_rows(name,dev_pin),strict=True),1):
        global_frame,ids,reference=truth
        assert prediction['frame']==frame and prediction['global_frame']==global_frame==start+frame-1
        keys=[o['mask'] for o in assignment['variants']['N0']];sources=[int(key[2:]) for key in keys]
        encoded=[rle(assignment['masks'][key]) for key in keys]
        if name in ('L3','LW'):
            label=read(WORK/'data/AnnotationNewBags_20260919'/name/'labels_raw'/f'{global_frame:06d}.json')
            native_ids,encoded=polygon_reference(label['shapes'],1080,1920);assert native_ids==sources
        similarity=(np.asarray(coco.iou(reference,encoded,[0]*len(encoded)),float).reshape(len(ids),len(encoded))
            if ids and encoded else np.zeros((len(ids),len(encoded))))
        gt.append(ids);sims.append(similarity);matches[frame]=unique_matches(ids,sources,similarity);predictions[frame]=prediction
        for a in ARMS:
            public_ids=[o['id'] for o in prediction['variants'][a]];pred[a].append(public_ids)
            step[a],added=clear_step(ids,keys,public_ids,similarity,previous[a],step[a],global_frame)
            switches[a].extend(dict(value,segment=name) for value in added)
        if frame%1000==0:print('DS35 SCORE',name,frame,flush=True)
    assert len(gt)==stop-start+1
    summary={a:metrics(gt,pred[a],sims)[0] for a in ARMS}
    archived=read(ARCHIVED/name/'public/METRICS.json')['metrics']
    for a in ARMS[:2]:assert summary[a]==archived[a],(name,a,'same-source official control mismatch')
    assert summary['DEPTH_OFF']==summary['Z4Q_FROZEN']
    for a in ARMS:
        assert len(switches[a])==summary[a]['IDSW'] and summary[a]['predictions']==summary['SAM3_NATIVE']['predictions']
    result=dict(segment=name,frames=len(gt),metrics=summary,deltas=deltas(summary),
        archived_DS34=archived['EVENT_RGBD'],difference_vs_archived_DS34={k:summary['DEPTH_OVERRIDE'][k]-archived['EVENT_RGBD'][k] for k in FIELDS},
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3','LW') else 'EXPOSED_EXISTING_ANNOTATION',
        score_protocol='Unchanged DS14/DS20/DS33/DS34 mask CLEAR.5 Identity.5 HOTA19; original coordinate systems and reference versions',
        no_mask_or_ID_exclusion=True,physical_depth_accuracy='UNKNOWN')
    write_new(public/'METRICS.json',result);write_new(public/'SWITCHES.json',switches);write_new(public/'SWITCH_CHANGES.json',switch_changes(switches))
    with gzip.open(public/'REFERENCE_MATCHES.jsonl.gz','xt',encoding='utf-8',newline='\n') as out:
        for f,values in matches.items():out.write(json.dumps(dict(frame=f,matches=values),separators=(',',':'),allow_nan=False)+'\n')
    audit=S.physical_audit(name,matches,predictions,first_public)
    print(name,json.dumps(summary),flush=True);return result,(gt,pred,sims),audit

def main():
    assert not (RUN/'METRICS.json').exists(),'Do not overwrite sealed scores'
    began=time.perf_counter();seal=verify_all();parity,origins={},{}
    for name in SEGMENTS:parity[name],origins[name]=verify_publications(name)
    # No reference raster may be read above the complete prediction + logical contract gate.
    dev_pin=ref.authoritative_development_pin();assert sha(ref.GT_DEV)==dev_pin
    write_new(RUN/'SCORING_FREEZE.json',dict(status='ALL_SOURCE_DECISION_STATE_AND_PUBLICATION_BINDINGS_VERIFIED',
        all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),scoring_sources=scoring_dependencies(),
        development_reference=artifact(ref.GT_DEV),development_pin=dev_pin,
        prediction_parity=parity,verified_before_reference_raster_read=True,new_model_http=0,cost_usd=0))
    write_new(RUN/'PREDICTION_PARITY.json',dict(status='PASS',segments=parity,GT_opened=False))
    results,audits={},{};pool_gt,pool_sims=[],[];pool_pred={a:[] for a in ARMS}
    for name in SEGMENTS:
        result,(gt,pred,sims),audit=score_segment(name,dev_pin,origins[name]);results[name]=result;audits[name]=audit
        if name.startswith('feeding_'):
            pool_gt.extend([[(name,i) for i in ids] for ids in gt]);pool_sims.extend(sims)
            for a in ARMS:pool_pred[a].extend([[(name,i) for i in ids] for ids in pred[a]])
    pooled={a:metrics(pool_gt,pool_pred[a],pool_sims)[0] for a in ARMS}
    archived=read(ARCHIVED/'METRICS.json')['feeding_pooled']['metrics']
    for a in ARMS[:2]:assert pooled[a]==archived[a]
    write_new(RUN/'METRICS.json',dict(status='SCORED_AFTER_ALL_EIGHT_FORMAL_PREDICTION_AND_ACCESS_SEALS',frames=20098,arms=ARMS,
        segments=results,feeding_pooled=dict(frames=1471,metrics=pooled,deltas=deltas(pooled),archived_DS34=archived['EVENT_RGBD']),
        event_audits=audits,all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),score_seconds=time.perf_counter()-began,
        depth_increment_comparison='DEPTH_OVERRIDE_MINUS_EXACT_ORIGINAL_DEPTH_OFF',new_model_http=0,cost_usd=0))
    write_new(RUN/'SCORE_PROVENANCE.json',dict(scorer=artifact(__file__),scoring_freeze=artifact(RUN/'SCORING_FREEZE.json'),
        official_metric_math_unchanged=True,ignored_public_ids=0,GT_used_for_prediction=False,original_controls_exact=True))
if __name__=='__main__':main()
