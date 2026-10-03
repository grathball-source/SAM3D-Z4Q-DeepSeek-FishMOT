"""Descriptive all-action tables; no thresholds fitted or new tracking scores."""
from pathlib import Path
from collections import Counter
import json, statistics, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'experiments/ds20_pending_confirmation_isolation'))
from common import read, artifact, write_new, rows, verify_item

GRADES = ('CORRECT','WRONG','UNSCORABLE')
PARTS = ('whole','birth_core','core')

def describe(values):
    values = [float(v) for v in values if v is not None]
    return dict(n=len(values), minimum=min(values) if values else None,
                median=statistics.median(values) if values else None, maximum=max(values) if values else None)

def main():
    proof = read(HERE/'INDEPENDENT_CHECK.json'); assert proof['status']=='PASS'
    data = read(HERE/'ACTIONS.json'); actions=data['actions']
    screens=[]; distributions=[]; births=[]
    for part in PARTS:
        for scope in ('current_eligible','anchor_eligible','both_eligible'):
            for grade in GRADES:
                group=[a for a in actions if a['physical']==grade]
                kept=sum(a['roi_features'][part][scope] is True for a in group)
                missing=sum(a['roi_features'][part][scope] is None for a in group)
                screens.append(dict(roi=part, scope=scope, physical=grade, total=len(group),
                    eligible=kept, measurement_screened=len(group)-kept-missing, unbound=missing,
                    identity_discrimination='UNKNOWN', actual_veto=False))
    for grade in GRADES:
        group=[a for a in actions if a['physical']==grade]
        metrics={k:describe(a['original_action'].get(k) for a in group) for k in (
            'residual_mm','tolerance_mm','cost','assignment_margin','age','confirmations','confirmation_span_s')}
        metrics['normalized_whole_residual']=describe(
            a['original_action']['residual_mm']/a['original_action']['tolerance_mm'] for a in group
            if a['origin_rule']=='D1_DELAYED')
        metrics['endpoint_time_gap_s']=describe(a['endpoint_time_gap_s'] for a in group)
        distributions.append(dict(physical=grade, actions=len(group), values=metrics))
    for a in actions:
        if a['origin_rule']=='BIRTH_REFINE':
            e=a['original_action']
            births.append(dict(action_id=a['action_id'],segment=a['segment'],global_frame=a['global_frame'],
                physical=a['physical'], core=e['core'], whole=e['whole'],
                survivor_witnesses=e['survivor_witnesses'],partners=e['partners'],
                assignment_margin=e['assignment_margin'], all_current_and_exact_anchor_facts_prelabel_sealed=True))
    source=ROOT/'experiments/ds20_pending_confirmation_isolation/run/POSTSCORE_SUMMARY.json'
    old=read(source)
    scores={unit:{arm:item['metrics'][arm] for arm in ('SAM3_NATIVE','Z4Q_FROZEN','MIXED_ISOLATED')}
            for unit,item in old['units'].items()}
    result=dict(status='COMPLETE_DESCRIPTIVE_AUDIT_NO_NEW_PERFORMANCE_RESULT',
        actions=len(actions), physical_counts=data['physical_counts'],
        literal_bank_counts=data['actual_reference_physical_counts'],
        measurement_screens=screens, original_feature_distributions=distributions,
        all_original_birth_actions=births, historical_scores=scores, historical_score_source=artifact(source),
        new_metrics=None, new_predictions=0,new_scoring=0,new_model_http=0,cost_usd=0,
        quality_screen_is_not_actual_edge_veto=True, unscorable_is_not_safe=True,
        no_threshold_fitting=True, no_case_reselection=True, independent_validation=False,
        sources=[artifact(HERE/name) for name in ('ACTIONS.json','AUDIT_SUMMARY.json','FEATURES_SEALED.json',
                                                'PRIVATE_VISUALS.json','INDEPENDENT_CHECK.json')])
    write_new(HERE/'DIAGNOSTIC_RESULTS.json',result)
    lines=['# DS21 complete original Z4Q action audit','',
        'This is a retrospective diagnostic of sealed actions. No new tracking predictions, metrics, veto or model calls.', '',
        f"All {len(actions)} original durable actions: strict grades {data['physical_counts']}; literal bank grades {data['actual_reference_physical_counts']}.", '',
        '## Fixed additional measurement screens', '',
        'Counts below describe measurement eligibility only. Screened correct actions are losses of available original recovery opportunities; screened unknown actions are not safety successes.', '',
        '| ROI | Scope | Original physical grade | Total | Eligible | Screened | Unbound |',
        '|---|---|---|---:|---:|---:|---:|']
    for r in screens:
        lines.append(f"|{r['roi']}|{r['scope']}|{r['physical']}|{r['total']}|{r['eligible']}|{r['measurement_screened']}|{r['unbound']}|")
    lines+=['','## Every original Birth action','',
        '| Segment | Original frame | Physical grade | Core residual mm | Whole residual mm | Survivor witnesses | Assignment margin |',
        '|---|---:|---|---:|---:|---:|---:|']
    for r in births:
        lines.append(f"|{r['segment']}|{r['global_frame']}|{r['physical']}|{r['core']['residual_mm']:.6f}|{r['whole']['residual_mm']:.6f}|{r['survivor_witnesses']}|{r['assignment_margin']:.6f}|")
    lines+=['','## Historical performance only','',
        '| Unit | SAM3 IDF1 | Original Z4Q IDF1 | Archived DS20 IDF1 | DS21 new IDF1 |',
        '|---|---:|---:|---:|---|']
    for unit,s in scores.items():
        lines.append(f"|{unit}|{s['SAM3_NATIVE']['IDF1']:.6f}|{s['Z4Q_FROZEN']['IDF1']:.6f}|{s['MIXED_ISOLATED']['IDF1']:.6f}|NOT_RUN|")
    lines+=['','Full six-field historical scores, all action features and distributions are in DIAGNOSTIC_RESULTS.json.', '',
        '## Limits','',
        'D1 rejected matrix edges do not export exact old anchors. No public integer or age is used to reconstruct alternative histories. Current observations, actual accepted anchors and explicit Birth view anchors are bound to frozen facts; qualified identity continuity remains UNKNOWN.', '',
        'Single layers, independent-source eligibility and depth agreement do not certify physical identity. Local depth-layer ownership and continuous occlusion order are not measured by this audit. L3/LW reference is weak prediction-derived; every source cohort is exposed. No new accuracy, physical depth calibration, independent generalization or tracking gain is claimed.', '',
        'PRIVATE_VISUALS.json inventories actual old-anchor/before/commit/after pixel figures and exact source bindings. Pictures stay private; the last column is postseal diagnosis only.']
    with (HERE/'RESULTS.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines)+'\n')
    print('Descriptive complete tables:',len(actions),'actions;',len(births),'Birth actions; new metrics NOT_RUN')

if __name__=='__main__':main()
