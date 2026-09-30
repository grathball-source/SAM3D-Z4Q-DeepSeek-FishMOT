"""Postseal switch differences, depth-choice/fallback distinction and QA cases."""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ds2_diagnostics',HERE/'diagnostics.py')
diag=importlib.util.module_from_spec(spec); sys.modules[spec.name]=diag
spec.loader.exec_module(diag)
write_new=diag.write_new
RUN=HERE/'run'


def main():
    for name,bounds in diag.evaluation.SEGMENTS.items(): diag.evaluation.verify_seal(RUN,name,*bounds)
    data={name:diag.load(name) for name in diag.evaluation.SEGMENTS}
    depths=json.loads((RUN/'DEPTH_DIAGNOSTICS.json').read_text(encoding='utf-8'))
    audit=json.loads((RUN/'EVENT_AUDIT.json').read_text(encoding='utf-8'))
    switches=json.loads((RUN/'SWITCH_LEDGER.json').read_text(encoding='utf-8'))['events']
    def key(x): return x['segment'],x['frame'],x['gt_id'],x['from_public_id'],x['to_public_id']
    differences={}
    current={key(x):x for x in switches['D2_FROZEN']}
    for arm in ('SAM3_NATIVE','D0_GEOMETRY','D1_STATIC_LEGACY','D3_ZERO_DRIFT_MATCHED_SCALE'):
        other={key(x):x for x in switches[arm]}
        differences[arm]=dict(added=[current[k] for k in sorted(current.keys()-other.keys())],
                              removed=[other[k] for k in sorted(other.keys()-current.keys())])
    choice_changes=[x for x in depths['event_scores'] if x['selected'] in ('H1','H2') and
                    x['geometry_common_state_choice'] in ('H1','H2') and x['selected']!=x['geometry_common_state_choice']]
    public_changes=[]
    for name,s in data.items():
        for entry in s['publish']:
            pub=entry['event_publish']
            if 'D2_FROZEN' in pub and 'D1_STATIC_LEGACY' in pub and pub['D2_FROZEN']['first_public_pair']!=pub['D1_STATIC_LEGACY']['first_public_pair']:
                public_changes.append(dict(segment=name,q=entry['frame'],original_q=entry['global_frame'],
                    D2=pub['D2_FROZEN']['first_public_pair'],D1=pub['D1_STATIC_LEGACY']['first_public_pair']))
    views=[]
    for tag,items in (('earliest_depth_selection_change_NOT_STAGED',choice_changes),
                      ('earliest_dynamic_vs_static_public_change',public_changes)):
        if items:
            item=min(items,key=lambda x:x['original_q']); name=item['segment']
            e=next(e for e in data[name]['events']['D2_FROZEN'] if e['q']==item['q'])
            view=diag.figures(name,e,data[name],tag)
            views.append(dict(view,tag=tag,status=e['restore']['status'],
                              selected_choice=e['numeric']['choice']))
    forecast=json.loads((RUN/'FORECAST_DIAGNOSTICS_VERSIONED.json').read_text(encoding='utf-8'))
    role_summaries=[]
    for name,event,role in sorted({(x['segment'],x['event'],x['role']) for x in forecast['observations']}):
        selected=[x for x in forecast['observations'] if (x['segment'],x['event'],x['role'])==(name,event,role)]
        role_summaries.append(dict(segment=name,event=event,role=role,observations=len(selected),
            statuses=dict(Counter(x['status'] for x in selected)),
            last_value_abs_mm=diag.original.stats([x['static_abs_mm'] for x in selected]),
            D2_abs_mm=diag.original.stats([x['dynamic_abs_mm'] for x in selected]),
            D3_abs_mm=diag.original.stats([x['zero_drift_abs_mm'] for x in selected]),
            scale_mm=diag.original.stats([x['proxy_scale_mm'] for x in selected]),
            interpretation='POSTSEAL_AUDIT_ONLY; clustered event/role raw observation residual, not depth GT'))
    counts={}
    for arm in diag.evaluation.ARMS[1:]:
        events=[e for s in data.values() for e in s['events'][arm]]
        counts[arm]=dict(suspects=len(events),cancelled=sum(e['confirm_frame'] is None for e in events),
            confirmed=sum(e['confirm_frame'] is not None for e in events),q=sum(e['q'] is not None for e in events),
            terminal_status=dict(Counter(e['status'] for e in events)),
            q_transaction_status=dict(Counter(e['restore']['status'] for e in events if e['q'] is not None)))
    write_new(RUN/'COMPLETE_AUDIT.json',dict(status='POSTSEAL_DIAGNOSTIC_ONLY',event_counts=counts,
        switch_differences=differences,depth_selection_changes=choice_changes,
        D2_vs_D1_actual_first_public_changes=public_changes,
        forecast_per_event_role=role_summaries,extra_restricted_figures=views,
        no_staged_depth_changes_vs_D0=True,no_D2_D3_choice_or_publication_changes=True,
        audit_code_sha256=diag.digest(Path(__file__))))
    print(json.dumps(dict(counts=counts,choice_changes=[x['original_q'] for x in choice_changes],
        static_public_changes=public_changes,extra_images=[x['path'] for x in views]),ensure_ascii=False))


if __name__=='__main__': main()
