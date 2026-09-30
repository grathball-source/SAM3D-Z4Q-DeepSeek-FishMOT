"""Postscore failure tracing only; no new filter run, threshold or candidate."""
from common import HERE, SEGMENTS, records, write_new


def audit():
    rows=list(records(HERE/'OCCUPANCY_AUDIT.jsonl.gz'))
    measured={(r['segment'],r['frame'],token):obj for name in SEGMENTS
              for r in records(HERE/f'{name}_measurements.jsonl.gz') for token,obj in r['objects'].items()}
    cases=[]
    for frame,token,reason in [(704,'o013','MAXIMUM_PAIRED_PURITY_DECREASE'),
                              (766,'o012','MAXIMUM_POSITIVE_RAW_MEDIAN_DELTA')]:
        row=next(r for r in rows if r['frame']==frame and r['token']==token)
        cases.append(dict(selection='POSTHOC_FAILURE_DIAGNOSIS_NOT_TUNING',reason=reason,
                          score=row,measurement=measured[(row['segment'],frame,token)]))
    far=[dict(frame=r['frame'],segment=r['segment'],token=r['token'],
              reference_status=r['reference_status'],occupancy=r['foreground'],
              median_mm=measured[(r['segment'],r['frame'],r['token'])]['foreground']['selected']['median'],
              contrast_mm=r['signed_contrast_mm']) for r in rows if r['filter_status']=='AVAILABLE'
              and measured[(r['segment'],r['frame'],r['token'])]['foreground']['selected_sign']=='FARTHER']
    write_new(HERE/'FAILURE_CASE_AUDIT.json',dict(postscore_only=True,changes_to_frozen_rule=0,new_requests=0,
        cases=cases,all_farther_selections=far,
        zero_matched_fish_accepted=[dict(frame=r['frame'],segment=r['segment'],token=r['token'],
            samples=r['foreground']['n']) for r in rows if r['reference_status']=='SCORABLE'
            and r['filter_status']=='AVAILABLE' and r['foreground']['fish']==0],
        conclusions=['Significant coherent contrast does not certify fish depth.',
          'F704 selected20 pixels all outside manual fish despite20 samples and74% dominance.',
          'F766 selected57 raw positive samples at12254.619mm, core1141.787mm; occupancy purity96.49% misses this conflict.',
          'The two-sided rule permits a dense distant component; dispersion, n and valid_fraction cannot reject it.',
          'No physical per-pixel foreground truth or device-range calibration is available here; do not assert repaired depth.']))


if __name__=='__main__': audit()
