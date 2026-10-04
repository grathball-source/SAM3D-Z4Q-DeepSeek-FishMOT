"""Actual-source phase endpoints; old anonymous contact facts never change."""
from common import *
from collections import defaultdict, Counter
from datetime import datetime, timezone
import runpy, time
import numpy as np
from source import RawDepth, native_masks
import source
from measurement_adapter import summarize, pair_summary

def tasks(cohort, only_pair=None):
    selected = cohort['logical_pairs']
    if only_pair: selected = [p for p in selected if p['pair_id']==only_pair]
    ids = {p['context_id'] for p in selected}; result=[]
    first_by_context = {i:next(p for p in selected if p['context_id']==i) for i in ids}
    for c in cohort['contexts']:
        if c['context_id'] not in ids: continue
        key=c['key']; p=first_by_context[c['context_id']]
        for f,cite in zip(key['pre_frames'],p['ds25_citations']['pre_pairs'],strict=True):
            checks={v['role']:v for v in c['pre_source_checks'] if v['frame']==f}
            result.append(dict(task_id=f"{c['context_id']}/pre/F{f}",context_id=c['context_id'],
                segment=key['segment'],frame=f,phase='PRE_ACTUAL_CLEAN_ANCHORS',
                native_roles={'A':key['anchor']['native_id'],'B':key['partner_native']},
                role_provenance=checks,old_contact_roi_citation=cite,
                causal_query_limit=min(x['q'] for x in selected if x['context_id']==c['context_id'])))
    for p in selected:
        result.append(dict(task_id=p['pair_id']+'/q',pair_id=p['pair_id'],context_id=p['context_id'],
            segment=p['segment'],frame=p['q'],phase='POST_ACTUAL_GEOMETRY_IDENTITY_UNKNOWN',
            native_roles={'A':p['current_native'],'B':p['partner_native']},
            role_provenance=dict(actual_mapping=p['actual_published_mapping_at_q'],
                original_transaction_sha256=p['original_transaction_sha256'],pre_versions=p['pre_versions'],
                current_partner_claim_version=p['current_partner_claim_version'],
                candidate_target_public=p['target_public'],candidate_mapping_is_hypothesis=True,
                current_source_is_actual_q_bank_anchor=p['current_source_is_actual_q_bank_anchor'],
                partner_source_is_actual_q_bank_anchor=p['partner_source_is_actual_q_bank_anchor'],
                post_geometry_and_quality_gate_passed=p['post_geometry_and_quality_gate_passed']),
            old_contact_roi_citation=p['ds25_citations']['current_pair'],causal_query_limit=p['q']))
    return result,selected

def saved_frames(name,wanted):
    base=input_dir(name)
    paths={k:base/v for k,v in [('observations','observations.jsonl.gz'),('assignments','assignments.jsonl.gz'),('depth','DEPTH_OBSERVATIONS.jsonl.gz')]}
    data={k:{r['frame']:r for r in rows(p) if r['frame'] in wanted} for k,p in paths.items()}
    assert all(set(d)==wanted for d in data.values())
    for f in wanted:
        a,b,c=(data[k][f] for k in ('observations','assignments','depth'))
        assert (a['frame'],a['global_frame'],a['time'])==(b['frame'],b['global_frame_id'],b['time'])==(c['frame'],c['global_frame'],c['time'])
    return data

def old_facts(cohort,selected):
    needed={x['fact_id']:x['measurement_sha256'] for p in selected for stage in p['ds25_citations'].values() for x in (stage if isinstance(stage,list) else [stage])}
    values={}
    for name in {p['segment'] for p in selected}:
        for f in rows(DS25/'run'/name/'public/MEASUREMENTS.jsonl.gz'):
            if f['fact_id'] in needed:
                assert digest(f)==needed[f['fact_id']]
                values[f['fact_id']]=f
    assert set(values)==set(needed)
    return values

def run(mode):
    started=time.perf_counter();cohort=read(HERE/'COHORT.json')
    assert len(cohort['logical_pairs'])==532 and len(cohort['contexts'])==15 and len(cohort['references'])==540
    if mode=='all':check_freeze(); out=RUN
    else:assert mode=='slice';out=HERE/'slice_real'
    assert not out.exists(), 'Never overwrite an earlier audit'
    first=min(cohort['references'],key=lambda r:(list(SEGMENTS).index(r['segment']),r['q']))['pair_id']
    todo,selected=tasks(cohort,first if mode=='slice' else None)
    oldfacts=old_facts(cohort,selected)
    for p in selected:
        assert [x['frame'] for x in p['ds25_citations']['anonymous_contact']]==list(range(p['target_anchor']['frame']+1,p['q']))
        assert p['pre_frames'][-1]==p['target_anchor']['frame'] and p['seed_frame']<p['q']
        for cite in [*p['ds25_citations']['pre_pairs'],*p['ds25_citations']['anonymous_contact'],p['ds25_citations']['current_pair']]:
            f=oldfacts[cite['fact_id']]; assert f['frame']==cite['frame']<=p['q'] and f['time']<=p['time']
    facts={};pairings=[];access=[];new_calls=0
    for name in SEGMENTS:
        group=[t for t in todo if t['segment']==name]
        if not group:continue
        wanted={t['frame'] for t in group}; data=saved_frames(name,wanted)
        byframe=defaultdict(list)
        for t in group:byframe[t['frame']].append(t)
        sensor=RawDepth(name)
        try:
            for f,entries in sorted(byframe.items()):
                row=data['observations'][f];expected=data['depth'][f]['raw_source_binding']
                depth,index,native,binding=sensor(row['global_frame'],row['time'])
                assert binding==expected
                masks=native_masks(data['assignments'][f]); obs={o['id']:o for o in row['observations']}
                cache={}
                for t in entries:
                    assert f<=t['causal_query_limit']
                    A,B=t['native_roles']['A'],t['native_roles']['B']; assert A!=B
                    for n in (A,B):
                        assert n in masks and int(masks[n].sum())==obs[n]['area']
                        assert not obs[n].get('neighbors'), 'Original endpoint geometry no longer matches clean gate'
                        if n not in cache:
                            fact,maps=old_measurement.measure_region(depth,index,native,masks,masks[n],name,f,
                                row['global_frame'],row['time'],source_binding=binding,expected_source_binding=expected)
                            assert fact['roi_binding']==old_measurement.array_binding(masks[n])
                            facts.setdefault(fact['fact_id'],fact);assert facts[fact['fact_id']]==fact
                            cache[n]=(fact,maps);new_calls+=1
                    firstfact,firstmaps=cache[A];secondfact,secondmaps=cache[B]
                    old=oldfacts[t['old_contact_roi_citation']['fact_id']]
                    pairings.append(dict(t,global_frame=row['global_frame'],time=row['time'],
                        source_binding_sha256=digest(binding),actual_masks={r:old_measurement.array_binding(masks[n]) for r,n in t['native_roles'].items()},
                        role_facts={r:dict(fact_id=cache[n][0]['fact_id'],measurement_sha256=digest(cache[n][0]),summary=summarize(cache[n][0])) for r,n in t['native_roles'].items()},
                        old_contact_roi_summary=summarize(old),
                        cross_role=pair_summary(firstfact,firstmaps,secondfact,secondmaps,index),
                        identity_recovery='NOT_PERFORMED',state_write=False,GT_RGB_future=False))
                access.append(dict(segment=name,frame=f,global_frame=row['global_frame'],time=row['time'],
                    source_binding_sha256=digest(binding),causal_query_limits=sorted({t['causal_query_limit'] for t in entries}),
                    actual_mask_measurements=len(cache)))
        finally:sensor.close()
        print(name,len(wanted),'frames',len(group),'paired endpoints',flush=True)
    assert len(pairings)==len(todo)
    write_rows(out/'ENDPOINT_FACTS.jsonl.gz',sorted(facts.values(),key=lambda f:(f['segment'],f['frame'],f['fact_id'])))
    write_rows(out/'OLD_UNCHANGED_FACTS.jsonl.gz',sorted(oldfacts.values(),key=lambda f:(f['segment'],f['frame'],f['fact_id'])))
    write_rows(out/'PAIRINGS.jsonl.gz',pairings)
    write_rows(out/'LOGICAL_PAIR_REFERENCES.jsonl.gz',selected)
    write_new(out/'SOURCE_ACCESS.json',dict(reads=access,field_reads=source.FIELD_READS,new_model_http=0,cost_usd=0))
    write_new(out/'SUMMARY.json',dict(mode=mode,contexts=len({t['context_id'] for t in todo}),logical_pairs=len(selected),
        paired_endpoints=len(todo),pre_pairs=sum(t['phase'].startswith('PRE') for t in todo),
        post_pairs=len(selected),unique_actual_mask_measurements=new_calls,unique_endpoint_facts=len(facts),
        unchanged_old_facts=len(oldfacts),raw_frames=len(access),elapsed_seconds=time.perf_counter()-started,
        state_commits=0,new_tracking_predictions=0,new_model_http=0,cost_usd=0))
    return out

if __name__=='__main__':
    mode=sys.argv[1];guard=runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds26_guard')
    out=run(mode)
    write_new(out/'ACCESS_GUARD.json',dict(status='NO_GT_RGB_RESTORED_NETWORK',blocked_tokens=list(guard['BLOCKED']),
        observed_data_paths=sorted(guard['SEEN']),npz_field_reads=[dict(path=p,key=k) for p,k in sorted(guard['NPZ'])],
        h5_or_array_fields=source.FIELD_READS,new_model_http=0,cost_usd=0))
    write_new(out/'MEASUREMENTS_SEALED.json',dict(status='SEALED_BEFORE_INDEPENDENT_REVIEW',
        created_utc=datetime.now(timezone.utc).isoformat(),
        artifacts={p.name:artifact(p) for p in out.iterdir() if p.is_file()},
        cohort=artifact(HERE/'COHORT.json'),runtime=artifact(HERE/'FREEZE.json') if mode=='all' else None,
        no_tracking_or_identity_state_write=True,new_model_http=0,cost_usd=0))
