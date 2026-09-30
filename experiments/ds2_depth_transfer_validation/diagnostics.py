"""Postseal audit of fixed depth evidence, resources and actual sensor figures."""
import copy
import importlib.util
import json
import sys
import types
from collections import Counter
from pathlib import Path
from adapter import HERE, ROOT, DS1, zero_drift_predict
from prepare import write_new, digest

spec=importlib.util.spec_from_file_location('ds2_evaluate',HERE/'evaluate.py')
evaluation=importlib.util.module_from_spec(spec); sys.modules[spec.name]=evaluation
spec.loader.exec_module(evaluation)
sys.path.insert(0,str(DS1))
import analyze as original
from depth_state import predict
import matplotlib.pyplot as plt
import numpy as np

RUN=HERE/'run'


def load(name):
    public=RUN/name/'public'
    return dict(measurements={x['frame']:x for x in evaluation.records(public/'DEPTH_OBSERVATIONS.jsonl.gz')},
        states={(x['frame'],x['arm']):x for x in evaluation.records(public/'DEPTH_STATES.jsonl.gz')},
        predictions=list(evaluation.records(public/'predictions.jsonl.gz')),
        events=json.loads((public/'EVENTS.json').read_text()),
        assignments={x['frame']:x for x in evaluation.records(HERE/'private'/name/'assignments.jsonl.gz')},
        publish=list(map(json.loads,(public/'PUBLISH_LEDGER.jsonl').read_text().splitlines())),
        performance=json.loads((public/'PERFORMANCE.json').read_text()),
        shadow=json.loads((public/'COMMON_STATE_SHADOW.json').read_text()),
        summary=json.loads((public/'RUN_SUMMARY.json').read_text()))


def figures(name,event,segment,tag):
    q=event['q']; now=segment['measurements'][q]['time']
    first=segment['publish'][q-1]['event_publish']['D2_FROZEN']['first_public_pair']
    fig,axes=plt.subplots(3,1,figsize=(12,10),layout='constrained')
    for axis,(role,fragment) in zip(axes[:2],event['depth_frozen'].items()):
        samples=fragment['samples'][-10:]
        axis.plot([s['time']-now for s in samples],[s['z_mm'] for s in samples],'o-',label=f'{role} pre source {fragment["source"]}')
        d2=predict(fragment,now); d3=zero_drift_predict(fragment,now)
        if d2['mu_mm'] is not None:
            axis.errorbar([0],[d2['mu_mm']],yerr=[d2['scale_mm']],fmt='s',label=f'D2 {d2["status"]}; proxy scale')
            axis.errorbar([.02],[d3['mu_mm']],yerr=[d3['scale_mm']],fmt='^',label='D3 same scale; display x offset only')
        for source in event['post_first_observations']:
            m=segment['measurements'][q]['objects'][source]
            if m['core']['median'] is not None:
                axis.scatter([0],[m['core']['median']],marker='x',label=f'q source {source} → {first[source]}, usable={m["core_usable"]}')
        axis.axvline(0,color='black'); axis.set(xlabel='seconds relative to q; causal cutoff=0',ylabel='apparent camera Z mm')
        axis.legend(fontsize=8)
    group=event['group_observations']
    axes[2].plot([segment['measurements'][s['frame']]['time']-now for s in group],
        [segment['measurements'][s['frame']]['objects'][str(s['source'])]['core']['median'] for s in group],'o-',label='GROUP only')
    axes[2].axvline(0,color='black'); axes[2].legend(); axes[2].set(ylabel='GROUP Z mm',xlabel='seconds to q')
    detail=event['numeric']['detail']; bg=detail.get('background')
    sh=next(s for s in segment['shadow'] if s['frame']==q)
    fig.suptitle(f'{name} {event["id"]} F{evaluation.SEGMENTS[name][0]+q-1}\nD2={sh["d2_choice"]}, D3 shadow={sh["d3_choice"]}, first={first}\nbackground={bg}; scale is proxy, not calibrated error',fontsize=10)
    target=HERE/'figures'/f'{tag}.svg'; target.parent.mkdir(exist_ok=True)
    fig.savefig(target); plt.close(fig)
    frames=[]; sources=[]; roles=[]
    for role,fragment in event['depth_frozen'].items():
        if fragment['samples']:
            frames.append(fragment['samples'][-1]['frame']); sources.append([fragment['source']]); roles.append(f'{role} last valid PRE')
    frames.append(q); sources.append([int(n) for n in event['post_first_observations']]); roles.append('q FIRST_SPLIT, input cutoff')
    raster=types.FunctionType(original.raster_figure.__code__,dict(original.raster_figure.__globals__,score=evaluation),
                              'ds2_raster',original.raster_figure.__defaults__)
    target=HERE/'private'/f'{tag}_raw_depth_core.png'
    return raster(name,frames,sources,segment,target,f'{name}: pre and q raw depth / valid / predicted core',roles)


def main():
    for name,bounds in evaluation.SEGMENTS.items(): evaluation.verify_seal(RUN,name,*bounds)
    metrics=json.loads((RUN/'METRICS.json').read_text()); audit=json.loads((RUN/'EVENT_AUDIT.json').read_text())
    data={name:load(name) for name in evaluation.SEGMENTS}
    coverage={}; event_scores=[]; changed=[]; shadow_changed=[]; broad_noinfo=[]; strata=Counter()
    selected_change=selected_shadow=None
    for name,segment in data.items():
        start,_=evaluation.SEGMENTS[name]
        objects=[m for x in segment['measurements'].values() for m in x['objects'].values()]
        states=list(segment['states'].values()); p=segment['performance']
        coverage[name]=dict(observations=len(objects),core_usable=sum(x['core_usable'] for x in objects),
            core_empty=sum(x['core']['n']==0 for x in objects),
            extract_seconds=original.stats([x['extraction_seconds'] for x in segment['publish']]),
            state_update_seconds=original.stats([x['seconds'] for x in p['state_update_times']]),
            candidate_seconds=original.stats([x['seconds'] for x in p['candidate_times']]),
            receive_to_publish_seconds=original.stats([x['receive_to_publish_seconds'] for x in segment['publish']]),
            resident_max={key:max(x[key] for x in states) for key in ('resident_live_objects','resident_cache_samples','resident_current_samples','resident_latest_fragment_samples','group_count','pending_count')},
            runtime=segment['summary'],timing_scope=p['note'])
        for event in segment['events']['D2_FROZEN']:
            q=event['q']
            if q is None: continue
            detail=event['numeric']['detail']; candidates=detail.get('candidates',[])
            common=frozen_geometry(event)
            forecasts={r:predict(f,segment['measurements'][q]['time']) for r,f in event['depth_frozen'].items()}
            physical=next(x for x in audit['events'] if x['arm']=='D2_FROZEN' and x['segment']==name and x['event']==event['id'])
            edges=[dict(choice=c['choice'],**edge,missing_reasons=missing_reasons(edge,detail.get('background')),
                        scale_background_ratio=(edge['prediction']['scale_mm']/detail['background']['scale_mm']
                           if edge['prediction']['scale_mm'] is not None and detail.get('background') else None))
                   for c in candidates for edge in c['pairs']]
            sh=next(s for s in segment['shadow'] if s['frame']==q)
            posts={n:segment['measurements'][q]['objects'][n]['core_usable'] for n in event['post_first_observations']}
            legacy_event=next((e for e in segment['events']['D1_STATIC_LEGACY'] if e['q']==q),None)
            legacy=legacy_event['numeric']['detail'] if legacy_event else {}
            entry=dict(segment=name,event=event['id'],original_q=start+q-1,q=q,
                selected=event['numeric']['choice'],geometry_common_state_choice=common,
                D3_common_state_choice=sh['d3_choice'],forecasts=forecasts,
                valid_post_count=sum(posts.values()),post_usable=posts,edges=edges,
                background=detail.get('background'),candidates=candidates,
                legacy_depth_status=('EVENT_NOT_PRESENT_IN_LEGACY' if not legacy_event else
                    'DEPTH_ENABLED' if legacy.get('core_depth_used_for_both') else 'DEPTH_DISABLED_ALL_OR_NOTHING'),
                risk_frames=q-event['suspect_frame'],risk_seconds=segment['measurements'][q]['time']-segment['measurements'][event['suspect_frame']]['time'],
                pre_source_missing_count=sum(not f['samples'] for f in event['depth_frozen'].values()),
                restore=event['restore'],physical=physical['physical'],first_public_physical=physical['first_public_physical'],
                first_public_mapping=physical['first_public_mapping'])
            event_scores.append(entry)
            for role,f in forecasts.items(): strata[f['status']]+=1
            pub=segment['publish'][q-1]['event_publish']
            if 'D0_GEOMETRY' in pub and pub['D2_FROZEN']['first_public_pair']!=pub['D0_GEOMETRY']['first_public_pair']:
                changed.append(dict(segment=name,event=event['id'],original_q=start+q-1,
                    D0=pub['D0_GEOMETRY']['first_public_pair'],D2=pub['D2_FROZEN']['first_public_pair'],physical=physical['first_public_physical']))
                if selected_change is None: selected_change=(name,event)
            if sh['d2_choice']!=sh['d3_choice']:
                shadow_changed.append(dict(segment=name,event=event['id'],original_q=start+q-1,D2=sh['d2_choice'],D3=sh['d3_choice'],submitted=False))
                if selected_shadow is None: selected_shadow=(name,event)
            winner=next((c for c in candidates if c['choice']==entry['selected']),None)
            loser=next((c for c in candidates if c['choice']!=entry['selected']),None)
            if (winner and loser and all(not p['used'] for p in winner['pairs']) and
                any(p['used'] and p['cost']>0 for p in loser['pairs']) and common in ('H1','H2') and entry['selected']!=common):
                broad_noinfo.append(dict(segment=name,event=event['id'],original_q=start+q-1,
                    physical=physical['first_public_physical'],winner=winner,loser=loser,
                    interpretation='F419-type positive available edge versus common no-information zero; frozen model, not two complete tracks'))
        # Pure postseal diagnostic adapter: aliases are local views, never replay state.
        segment['events']['D2_DYNAMIC']=segment['events']['D2_FROZEN']
        segment['states'].update({(f,'D2_DYNAMIC'):v for (f,a),v in list(segment['states'].items()) if a=='D2_FROZEN'})
    forecast_audit=copy.deepcopy(audit)
    for x in forecast_audit['events']:
        if x['arm']=='D2_FROZEN': x['arm']='D2_DYNAMIC'
    fn=types.FunctionType(original.forecast_diagnostics.__code__,dict(original.forecast_diagnostics.__globals__,score=evaluation),
                          'ds2_forecast_diagnostics',original.forecast_diagnostics.__defaults__)
    forecast=fn(data,forecast_audit)
    for obs in forecast['observations']:
        event=next(e for e in data[obs['segment']]['events']['D2_FROZEN'] if e['id']==obs['event'])
        fragment=event['depth_frozen'][obs['role']]
        measured=data[obs['segment']]['measurements'][obs['frame']]
        z=measured['objects'][str(obs['target_source'])]['core']['median']
        obs['zero_drift_abs_mm']=abs(z-zero_drift_predict(fragment,measured['time'])['mu_mm'])
    forecast['independent_recordings']=1
    forecast['events_with_comparisons']=len({(x['segment'],x['event']) for x in forecast['observations']})
    forecast['event_roles_with_comparisons']=len({(x['segment'],x['event'],x['role']) for x in forecast['observations']})
    private=[]; chosen=[]
    for tag,selection in (('earliest_depth_change',selected_change),('earliest_WLS_mean_choice_change',selected_shadow)):
        if selection:
            name,event=selection; private.append(figures(name,event,data[name],tag)); chosen.append(dict(tag=tag,segment=name,event=event['id']))
        else: chosen.append(dict(tag=tag,status='NONE_EXISTS'))
    if not private:
        first=next(((name,e) for name,segment in data.items() for e in segment['events']['D2_FROZEN'] if e['q'] is not None),None)
        if first:
            name,event=first; private.append(figures(name,event,data[name],'earliest_q_quality_control'))
    write_new(RUN/'DEPTH_DIAGNOSTICS.json',dict(status='POSTSEAL_ONLY',coverage=coverage,
        forecast_status_role_counts=dict(strata),event_scores=event_scores,changed_first_publications=changed,
        common_state_shadow_choice_changes=shadow_changed,broad_available_vs_noinfo_changes=broad_noinfo,
        broad_mechanism_verdicts=dict(Counter(x['physical'] for x in broad_noinfo)),
        visualization_selection=chosen,model_http=0,model_cost_usd=0))
    write_new(RUN/'FORECAST_DIAGNOSTICS_VERSIONED.json',forecast)
    write_new(HERE/'VISUALIZATION_INVENTORY.json',dict(public_numeric=list(map(str,(HERE/'figures').glob('*.svg'))),
        restricted=private,actual_view_status='PENDING_LOCAL_VISUAL_INSPECTION',q_only=True))
    print(json.dumps(dict(changed=changed,shadow_changes=shadow_changed,broad=len(broad_noinfo),coverage={k:{'usable':v['core_usable'],'objects':v['observations']} for k,v in coverage.items()},private_figures=[x['path'] for x in private])))


def frozen_geometry(event):
    candidates=event['numeric']['detail'].get('candidates',[])
    if not candidates: return 'UNRESOLVED'
    if abs(candidates[0]['geometry']-candidates[1]['geometry'])<=1e-9:
        return 'GEOMETRY_TIE_TEMPORARY_CHOICE_NOT_EXPORTED'
    return min(candidates,key=lambda x:x['geometry'])['choice']


def missing_reasons(edge,background):
    reasons=[]
    if background is None: reasons.append('FULL_FRAME_BACKGROUND_MISSING')
    if edge['observation_scale_mm'] is None: reasons.append('POST_CORE_QUALITY_UNUSABLE')
    if edge['prediction']['mu_mm'] is None: reasons.append(edge['prediction']['status'])
    return reasons


if __name__=='__main__': main()
