"""Explain sealed S0 pre-pair failures; never run association or read GT."""
from __future__ import annotations
import collections, math, sys
from pathlib import Path

def _block(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = str(args[0]).replace('\\', '/').lower()
        if any(x in name for x in ('/metrics', '/gt/', '/annotations/', 'instance_id', '/rgb/', 'depth_mm_v3')):
            raise RuntimeError('Source-only audit prohibited input: ' + name)
sys.addaudithook(_block)
from common import HERE, ROOT, RUN, SEGMENTS, artifact, read, rows, sha, verify_item, write_new
CFG = read(HERE/'CONFIG.json')
TARGETS = ('INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING', 'NO_SAME_FRAME_PRE_PAIR')

def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)

def sample_errors(item, point, key, native, public, segment, cutoff, query):
    errors = []
    def check(ok, label):
        if not ok: errors.append(label)
    check(point is not None, 'GEOMETRY_FRAME_ABSENT')
    check(all(finite(item.get(k)) for k in ('time','z_mm','mad_mm')), 'DEPTH_TIME_VALUE_NOT_FINITE')
    check(item.get('frame', cutoff+1) <= cutoff, 'AFTER_REFERENCE_CUTOFF')
    check(finite(item.get('time')) and item['time'] < query, 'NOT_BEFORE_QUERY_TIME')
    check(finite(item.get('z_mm')) and item['z_mm'] > 0, 'NONPOSITIVE_DEPTH')
    check(finite(item.get('mad_mm')) and item['mad_mm'] >= 0, 'NEGATIVE_OR_INVALID_MAD')
    check(finite(item.get('mad_mm')) and max(CFG['raw_scale_floor_mm'],1.4826*item['mad_mm']) <= CFG['max_raw_scale_mm'], 'RAW_SCALE_TOO_LARGE')
    check(list(item.get('version_key',key)) == list(key), 'DEPTH_VERSION_MISMATCH')
    check(item.get('observation_class','SOURCE_OBSERVATION') in ('SOURCE_OBSERVATION','RESTORED_POST'), 'DEPTH_CLASS_NOT_CLEAN')
    if point is not None:
        check(point.get('observation_class','SOURCE_OBSERVATION') in ('SOURCE_OBSERVATION','RESTORED_POST'), 'GEOMETRY_CLASS_NOT_CLEAN')
        check(not point.get('neighbors'), 'GEOMETRY_HAS_NEIGHBORS')
        check(point.get('area',0) >= 64, 'GEOMETRY_AREA_TOO_SMALL')
        check(point.get('source') == native, 'GEOMETRY_NATIVE_MISMATCH')
        check(point.get('public_id') == public, 'GEOMETRY_PUBLIC_MISMATCH')
        check(point.get('source_generation') == key[2], 'GEOMETRY_GENERATION_MISMATCH')
        check(point.get('public_epoch') == key[4], 'GEOMETRY_EPOCH_MISMATCH')
        check(point.get('time') == item.get('time'), 'GEOMETRY_DEPTH_TIME_MISMATCH')
    check(item.get('source_native') == native, 'DEPTH_NATIVE_MISMATCH')
    check(bool(item.get('core_usable')), 'CORE_NOT_USABLE')
    check(all(finite(item.get(k)) for k in ('n','valid_fraction')), 'QUALITY_NOT_FINITE')
    check(finite(item.get('n')) and item['n'] >= CFG['min_points'], 'INSUFFICIENT_POINTS')
    check(finite(item.get('valid_fraction')) and CFG['min_fraction'] <= item['valid_fraction'] <= 1, 'VALID_FRACTION_OUT_OF_RANGE')
    fact=item.get('fact_id')
    check(isinstance(fact,str) and fact.startswith(f'{segment}/F{item.get("frame")}/n:{native}/'), 'FACT_SOURCE_FRAME_MISMATCH')
    return errors

def compact_sample(s):
    fields=('frame','time','z_mm','mad_mm','fact_id','source_native','version_key','observation_class','n','valid_fraction','core_usable')
    out={k:s.get(k) for k in fields}
    b=s.get('association_measurement_binding') or {}
    out['binding']={k:b.get(k) for k in ('frame','global_frame','native','source_version','version_key','measurement_fact_id','certificate_fact_id','certificate_sha256','frame_binding_sha256')}
    return out

def inspect(e, order, segment):
    query=order['time']; cutoff=e['suspect_frame']-1
    roles={}; first=None
    for role,native,public in zip(('A','B'),e['member_sources'],e['public_ids']):
        frozen=e['depth_frozen'][role]; key=frozen.get('key')
        history=frozen.get('samples',[])[-CFG['history_frames']:]
        geometry={p['frame']:p for p in e['pre_geometry_history'][role]}
        version_ok=bool(key and len(key)==5 and key[3]==public and frozen.get('public')==public and frozen.get('source')==native and history)
        failures=[]
        if not version_ok:
            first=first or dict(role=role,reason='MISSING_OR_MISMATCHED_PRE_VERSION')
        else:
            for item in history:
                errors=sample_errors(item,geometry.get(item['frame']),key,native,public,segment,min(cutoff,frozen.get('cutoff_frame',cutoff)),query)
                if errors:
                    failures.append(dict(frame=item['frame'],errors=errors,depth=compact_sample(item),geometry=geometry.get(item['frame'])))
                    first=first or dict(role=role,frame=item['frame'],reason=TARGETS[0],errors=errors)
            if not failures and any(b['frame'] != a['frame']+1 or b['time'] <= a['time'] for a,b in zip(history,history[1:])):
                first=first or dict(role=role,reason='PRE_GAP_OR_NONMONOTONIC_TIME')
        df=[s['frame'] for s in history]; gf=list(geometry)
        roles[role]=dict(native=native,public=public,key=key,version_header_matches=version_ok,
            depth_frames=df,geometry_frames=gf,depth_geometry_intersection=sorted(set(df)&set(gf)),
            missing_geometry_frames=sorted(set(df)-set(gf)),failures=failures,
            depth_source_facts=[compact_sample(s) for s in history],
            geometry_versions=sorted({(s.get('source_generation'),s.get('public_id'),s.get('public_epoch')) for s in geometry.values()},key=str),
            geometry_classes=sorted({s.get('observation_class') for s in geometry.values()},key=str))
    overlap=sorted(set(roles['A']['depth_frames'])&set(roles['B']['depth_frames']))
    if first is None and not overlap:first=dict(reason=TARGETS[1])
    reason=order['detail']['order_evidence']['reason']
    if reason in TARGETS:assert first and first['reason']==reason,(segment,e['id'],first,reason)
    return dict(segment=segment,event=e['id'],suspect_frame=e['suspect_frame'],q=e['q'],q_original=order['global_frame'],
        query_time=query,logged_reason=reason,logged_choice=order['selected_choice'],
        causal_cutoff=cutoff,roles=roles,depth_pair_frames=overlap,
        geometry_pair_frames=sorted(set(roles['A']['geometry_frames'])&set(roles['B']['geometry_frames'])),
        first_original_check_failure=first,source_record_predicates_match_logged_failure=reason in TARGETS,
        newly_qualified_or_associated=False,physical_identity='NOT_READ_OR_RESCORED')

def timeline_context(public, cases, all_events):
    wanted={}
    for c in cases:
        for role,r in c['roles'].items():
            start=min(r['depth_frames']+r['geometry_frames']+[c['suspect_frame']])-1
            wanted.setdefault(r['native'],[]).append((max(1,start),c['suspect_frame']))
    state={n:{} for n in wanted}
    for row in rows(public/'DEPTH_STATES.jsonl.gz'):
        if row['arm']!='MIXED_RETURN':continue
        frame=row['frame']
        for n,intervals in wanted.items():
            if not any(lo<=frame<=hi for lo,hi in intervals):continue
            k=str(n)
            state[n][frame]=dict(frame=frame,original_frame=row['global_frame'],source=n,
                observation_class=row['observation_classes'].get(k,'SOURCE_NOT_OBSERVED'),
                current_fragment_count=row['sample_counts'].get(k),version=row['source_versions'].get(k),
                active_event=row['active_event'],signal=row.get('signal'))
    for c in cases:
        for role,r in c['roles'].items():
            start=min(r['depth_frames']+r['geometry_frames']+[c['suspect_frame']])-1
            selected=[v for f,v in sorted(state[r['native']].items()) if start<=f<=c['suspect_frame']]
            # Keep transitions and actual endpoints, avoiding a new history selection policy.
            compact=[]; previous=None
            endpoints=set(r['depth_frames']+r['geometry_frames'])
            for v in selected:
                signature=(v['observation_class'],tuple(v['version'] or []),v['active_event'],bool(v['current_fragment_count']),v.get('signal') and v['signal'].get('kind'))
                if signature!=previous or v['frame'] in endpoints or v['frame'] in (c['suspect_frame']-1,c['suspect_frame']):compact.append(v)
                previous=signature
            r['actual_state_transitions_and_frozen_endpoints']=compact
            lifecycle=[]
            for old in all_events:
                if not old.get('end') or not start<=old['end']<c['suspect_frame']:continue
                affected=set(old['member_sources'])|{int(n) for n in old.get('post_first_observations',{})}|{old['group_source']}
                if r['native'] in affected:
                    lifecycle.append(dict(event=old['id'],end=old['end'],status=old['status'],member_sources=old['member_sources'],group_source=old['group_source'],post_sources=list(old.get('post_first_observations',{})),
                        returned_source_exemption=str(r['native']) in (old.get('returned_sources') or {})))
            r['prior_event_lifecycle_clear_candidates']=lifecycle

def main():
    all_seal=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert all_seal['status']=='ALL_PREDICTIONS_AND_ACCESS_SEALED'
    cases=[]; counts=collections.Counter(); artifacts=[]
    for segment in SEGMENTS:
        public=RUN/segment/'public';verify_item(all_seal['seals'][segment]);seal=read(public/'PREDICTIONS_SEALED.json')
        for name in ('EVENTS.json','ORDER_EVIDENCE.jsonl.gz','DEPTH_STATES.jsonl.gz','FREEZE.json'):
            path=public/name;assert sha(path)==seal['artifacts_sha256'][name];artifacts.append(artifact(path))
        events=read(public/'EVENTS.json')['MIXED_RETURN'];by_id={e['id']:e for e in events}
        local=[]
        for order in rows(public/'ORDER_EVIDENCE.jsonl.gz'):
            if order['arm']!='MIXED_RETURN':continue
            e=by_id[order['event']];assert e['q']==order['frame']==order['q']
            assert e['numeric']['detail']['order_evidence']==order['detail']['order_evidence']
            counts[order['detail']['order_evidence']['reason']]+=1
            c=inspect(e,order,segment);cases.append(c)
            if c['logged_reason'] in TARGETS:local.append(c)
        timeline_context(public,local,events)
    assert sum(counts.values())==50 and counts[TARGETS[0]]==13 and counts[TARGETS[1]]==16,counts
    error_counts=collections.Counter(err for c in cases if c['logged_reason']==TARGETS[0] for r in c['roles'].values() for f in r['failures'] for err in f['errors'])
    report=dict(status='SEALED_PRE_PAIR_SOURCE_DIAGNOSIS',GT_read=False,metrics_read=False,new_prediction=False,new_association=False,new_model_http=0,
        frozen_source=[artifact(HERE/'controller.py'),artifact(HERE/'runner.py'),artifact(ROOT/'experiments/ds16_relative_depth_order/order_association.py'),artifact(ROOT/'experiments/ds1_depth_only/depth_state.py'),artifact(ROOT/'experiments/ms1_s0_development_8400/merge_split_manager.py')],
        helper=artifact(Path(__file__)),all_prediction_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),actual_config=CFG,
        logged_reason_counts=dict(counts),invalid_field_counts=dict(error_counts),source_artifacts=artifacts,cases=cases)
    write_new(HERE/'PRE_PAIR_DIAGNOSIS.json',report)
    print('DIAGNOSIS',dict(counts),'invalid_fields',dict(error_counts))

if __name__=='__main__':main()
