"""Read-only audit of completed SLR-1 packets, never calls model or server."""
from pathlib import Path
import json, itertools, statistics, math, hashlib

OUT=Path(__file__).resolve().parent
OLD=OUT.parents[1]/'sam3_spatial_llm_stage1_20260920'/'engineering_r3'
def read(name): return json.loads((OLD/name).read_text(encoding='utf-8'))
def summary(v):
    return {'n':len(v),'min':min(v),'median':statistics.median(v),'max':max(v)} if v else {'n':0}

packets=read('PACKETS.json'); indexes={p['query_id']:p for p in read('PRIVATE_INDEX.json')}
baseline={p['query_id']:p['output'] for p in read('BASELINE_DECISIONS.json')}
results={p['query_id']:p for p in read('EVENT_RESULTS.json')}
rows=[]; allhist=[]; allcurrent=[]; alle=[]
for p in packets:
    ix=indexes[p['query_id']]; histories=[]
    for h in p['history']:
        ss=h['samples']; age=-ss[-1]['time_s'] if ss else None
        span=ss[-1]['time_s']-ss[0]['time_s'] if len(ss)>1 else None
        displacement=None; predicted=None
        if ss and h['velocity_px_s']:
            displacement=math.hypot(*h['velocity_px_s'])*age
            predicted=[a+b*age for a,b in zip(ss[-1]['center_px'],h['velocity_px_s'])]
        row={'track':h['track'],'count':len(ss),'independent':h['geometry_independent_reference'],
             'age_s':age,'span_s':span,'extrapolation_to_span_ratio':age/span if span else None,
             'predicted_displacement_px':displacement,'predicted_center':predicted,
             'predicted_off_image':predicted is not None and not (0<=predicted[0]<640 and 0<=predicted[1]<360)}
        histories.append(row); allhist.append(row)
    edges={(e['track'],e['observation']):e for e in p['pairwise']}
    candidates=[c['observation'] for c in p['current'] if c['area_px']>0]
    scores=[]
    for perm in itertools.permutations(candidates,len(p['focal_tracks'])):
        ee=[edges[(t,c)] for t,c in zip(p['focal_tracks'],perm)]
        if any(e['available_modalities']<2 or e['weighted_cost'] is None for e in ee):continue
        scores.append((sum(e['weighted_cost'] for e in ee)/len(ee),list(perm),ee))
    scores.sort(key=lambda a:a[0])
    best=scores[0] if scores else None
    gap=scores[1][0]-best[0] if len(scores)>1 else None
    fail=[]
    if best is None:fail.append('no_feasible_assignment')
    if best and best[0]>3:fail.append('absolute_cost')
    if gap is not None and gap<.15:fail.append('margin')
    allcurrent+=p['current'];alle+=p['pairwise']
    rows.append({'query_id':p['query_id'],'event':ix['event'],'frame':ix['frame'],'stage':ix['stage'],
                 'packet_chars':len(json.dumps(p,separators=(',',':'))),'current_count':len(p['current']),
                 'nonempty_current_count':len(candidates),'histories':histories,
                 'best_score':best[0] if best else None,'gap':gap,'fail_conditions':fail,
                 'best_assignment':[{'track':t,'observation':o} for t,o in zip(p['focal_tracks'],best[1])] if best else [],
                 'best_edges':best[2] if best else [],'baseline_state':baseline[p['query_id']]['state'],
                 'evaluation':results.get(p['query_id'])})

# Counterexample proves uniform risk downweighting cancels in weighted average.
cancel=[]
for e in alle:
    w=e['quality_weights']; cc=e['costs']; den=sum(w.values())
    if den:
        res=sum(cc[k]*w[k] for k in w if cc[k] is not None)/den
        scaled=sum(cc[k]*w[k]*.25 for k in w if cc[k] is not None)/(den*.25)
        cancel.append(abs(res-scaled))
stats={
 'packets':len(packets),'first_split':len(results),'history_entries':len(allhist),
 'unique_references_note':'Same per-event reference reused in both stage queries; history entry counts double event-track counts.',
 'reference_ages_s':summary([h['age_s'] for h in allhist if h['age_s'] is not None]),
 'reference_spans_s':summary([h['span_s'] for h in allhist if h['span_s'] is not None]),
 'extrapolation_ratios':summary([h['extrapolation_to_span_ratio'] for h in allhist if h['extrapolation_to_span_ratio'] is not None]),
 'predicted_displacement_px':summary([h['predicted_displacement_px'] for h in allhist if h['predicted_displacement_px'] is not None]),
 'histories_missing':sum(h['count']==0 for h in allhist),
 'histories_fallback':sum(not h['independent'] for h in allhist),
 'histories_older_1s':sum(h['age_s'] is not None and h['age_s']>1 for h in allhist),
 'histories_older_5s':sum(h['age_s'] is not None and h['age_s']>5 for h in allhist),
 'histories_predicted_off_image':sum(h['predicted_off_image'] for h in allhist),
 'candidate_count':summary([r['current_count'] for r in rows]),
 'current_descriptors':len(allcurrent),'current_empty':sum(c['area_px']==0 for c in allcurrent),
 'current_nonempty_fragmented_fraction_lt_09':sum(c['area_px']>0 and c['largest_component_fraction']<.9 for c in allcurrent),
 'current_nonempty_with_neighbors':sum(c['area_px']>0 and c['neighbor_count']>0 for c in allcurrent),
 'current_nonempty_missing_depth_core':sum(c['area_px']>0 and c['raw_depth_mm']['core']['median'] is None for c in allcurrent),
 'edge_count':len(alle),'available_modalities':{str(n):sum(e['available_modalities']==n for e in alle) for n in range(4)},
 'costs':{k:summary([e['costs'][k] for e in alle if e['costs'][k] is not None]) for k in ['appearance','motion','depth']},
 'uniform_risk_scaling_max_score_difference':max(cancel),
 'query_chars':summary([r['packet_chars'] for r in rows]),
 'input_sha256':{n:hashlib.sha256((OLD/n).read_bytes()).hexdigest() for n in ['PACKETS.json','PRIVATE_INDEX.json','BASELINE_DECISIONS.json','EVENT_RESULTS.json']},
}
for stage in ['merge_snapshot','first_split']:
    rs=[r for r in rows if r['stage']==stage]
    stats[stage]={'matches':sum(r['baseline_state']=='MATCH' for r in rs),'waits':sum(r['baseline_state']!='MATCH' for r in rs),
                  'absolute_cost_fails':sum('absolute_cost' in r['fail_conditions'] for r in rs),
                  'margin_fails':sum('margin' in r['fail_conditions'] for r in rs),
                  'no_assignment':sum('no_feasible_assignment' in r['fail_conditions'] for r in rs)}
(OUT/'AUDIT_DETAILS.json').write_text(json.dumps({'summary':stats,'rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(stats,ensure_ascii=False,indent=2))
