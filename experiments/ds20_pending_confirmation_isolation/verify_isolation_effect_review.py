"""Verify the postseal LW explanation against its actual immutable sources."""
import gzip
import hashlib
import json

from common import HERE, RUN, artifact, read, verify_item, write_new


def main():
    review = read(HERE/'ISOLATION_EFFECT_REVIEW.json')
    for source in review['source_citations']:
        verify_item(source)
    selected = {(r['local_frame'],r['arm']):r for r in review['timeline']}
    actual = {}
    source = RUN/'LW/public/TRANSACTIONS.part003.jsonl.gz'
    with gzip.open(source,'rt',encoding='utf-8') as handle:
        for line in handle:
            row=json.loads(line)
            if row['frame']>3348:
                break
            key=(row['frame'],row['arm'])
            if key not in selected:
                continue
            recorded=selected[key]
            assert recorded['source_row_sha256']==hashlib.sha256(line.encode()).hexdigest()
            assert recorded['original_frame']==row['global_frame']
            assert recorded['actual_mapping']=={str(n):row['actual_published_mapping'].get(str(n))
                                                for n in (144,145)}
            actual[key]=row
    assert set(actual)==set(selected)
    audit=actual[3269,'ACTIVITY_ISOLATED']['controller_trace']['ds20_pending_isolation']
    assert any(e['reason']=='IDENTITY_VERSION_CHANGED' and e['identity']['native']==144
               for e in audit['invalidated'])
    assert selected[3272,'ACTIVITY_ISOLATED']['event_confirmations_after'][0]['pending']['count']==4
    for frame in (3273,3276,3278):
        checks=selected[frame,'ACTIVITY_ISOLATED']['protected_route_checks']
        assert any('CURRENT_QUALITY_OR_CONTACT_RISK' in c['reasons'] for c in checks)
    for frame in range(3338,3342):
        counter=selected[frame,'ACTIVITY_ISOLATED']['event_confirmations_after']
        assert len(counter)==1 and counter[0]['identity']['native']==145
        assert counter[0]['pending']['count']==frame-3337
    accepted=selected[3342,'ACTIVITY_ISOLATED']['accepted_private_proposals']
    assert len(accepted)==1 and accepted[0]['native_id']==145
    assert accepted[0]['canonical_id']==133 and accepted[0]['confirmations']==5
    assert selected[3342,'ACTIVITY_ISOLATED']['local_transaction_staged']
    public=RUN/'LW/public'
    scored=read(public/'LOCAL_RETURN_AUDIT.json')['arms']
    for arm,source_id,frame in (('ACTIVITY_RETURN',144,3272),('ACTIVITY_ISOLATED',145,3342)):
        assert len(scored[arm])==1
        record=scored[arm][0]
        assert (record['source'],record['frame'],record['target'],record['physical'])==(
            source_id,frame,133,'UNSCORABLE')
    switches=read(public/'SWITCHES.json')
    added=[s for s in switches['ACTIVITY_ISOLATED'] if s not in switches['ACTIVITY_RETURN']]
    removed=[s for s in switches['ACTIVITY_RETURN'] if s not in switches['ACTIVITY_ISOLATED']]
    assert added==review['actual_added_switches'] and removed==review['actual_removed_switches']
    assert len(added)==1 and not removed
    assert (added[0]['frame'],added[0]['native_id'],added[0]['from_public_id'],
            added[0]['to_public_id'])==(3427,150,150,144)
    automatic=read(public/'AUTOMATIC_RECONNECT_AUDIT.json')['arms']['ACTIVITY_ISOLATED']
    action=next(r for r in automatic if r['source']==150 and r['frame']==3428)
    assert action['target']==144 and action['durable_automatic_commit']
    assert action['physical']=='UNSCORABLE'
    assert action['actual_old_anchor']==dict(frame=3348,native_id=144,mask='n:144',canonical_id=144)
    metrics=read(public/'METRICS.json')['metrics']
    for arm,record in review['metrics'].items():
        assert record==metrics[arm]
    assert metrics['MIXED_RETURN']==metrics['MIXED_ISOLATED']
    assert review['isolated_minus_archived_activity']=={
        k:metrics['ACTIVITY_ISOLATED'][k]-metrics['ACTIVITY_RETURN'][k]
        for k in ('IDF1','HOTA','AssA','IDSW','FP','FN')}
    write_new(HERE/'ISOLATION_EFFECT_SOURCE_CHECK.json',dict(
        status='POSTSEAL_SELECTED_SOURCE_ROWS_GRADES_SWITCHES_AND_METRIC_DELTA_VERIFIED',
        review=artifact(HERE/'ISOLATION_EFFECT_REVIEW.json'),
        report=artifact(HERE/'ISOLATION_EFFECT_REVIEW.md'),
        selected_transaction_rows=len(actual),source_citations_verified=len(review['source_citations']),
        new_model_http=0,prediction_rerun=False,GT_raster_read=False,
        copied_final_score_only=False,private_pixel_output=False))
    print('PASS',len(actual),'actual selected transaction rows; both returns UNSCORABLE; IDSW +1/−0')


if __name__=='__main__':
    main()
