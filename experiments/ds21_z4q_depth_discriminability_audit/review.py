"""Independent immutable grade/feature/publication census, no re-association."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import gzip, json, hashlib, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'experiments/ds20_pending_confirmation_isolation'))
from common import read, rows, artifact, verify_item, write_new, sha, SEGMENTS, DS18

def main():
    frozen=read(HERE/'FREEZE.json')
    for path,item in frozen['code'].items():
        assert Path(path).stat().st_size==item['bytes'] and sha(path)==item['sha256']
    source=read(HERE/'BEGIN_SOURCE_CHECK.json')
    for item in source['artifacts']:verify_item(item)
    seal=read(HERE/'FEATURES_SEALED.json')
    for item in seal['artifacts']:verify_item(item)
    data=read(HERE/'ACTIONS.json');verify_item(data['feature_seal'])
    assert datetime.fromisoformat(data['label_join_started_at_utc'])>=datetime.fromisoformat(seal['sealed_at_utc'])
    features=list(rows(HERE/'FEATURES.jsonl.gz'))
    assert len(features)==len(data['actions'])==seal['accepted_actions']
    indexed={a['action_id']:a for a in features};assert len(indexed)==len(features)
    all_labels={};counts=Counter();literal=Counter();rule=Counter();census={}
    baseline=ROOT/'experiments/ds20_pending_confirmation_isolation/run'
    for segment in SEGMENTS:
        labels=read(baseline/segment/'public/AUTOMATIC_RECONNECT_AUDIT.json')['arms']['Z4Q_FROZEN']
        mine=[a for a in data['actions'] if a['segment']==segment]
        assert len(mine)==len(labels)
        for a in mine:
            matches=[l for l in labels if (l['frame'],l['source'],l['target'],l['origin_rule'])==
                (a['frame'],a['source'],a['target'],a['origin_rule'])]
            assert len(matches)==1
            l=matches[0]
            assert a['sealed_physical_record']==l
            assert a['original_action']==l['actual_controller_action'] and a['actual_old_anchor']==l['actual_old_anchor']
            assert all(a[k]==v for k,v in indexed[a['action_id']].items())
            assert a['actual_old_anchor']['frame']<a['frame']
            assert a['actual_publication_binding']['applied_at_first_publication']
            assert a['actual_publication_binding']['durable_alias_after_commit']
            assert not a['actual_publication_binding']['overridden_by_explicit_transaction']
            counts[a['physical']]+=1;literal[a['actual_reference_physical']]+=1;rule[a['origin_rule']]+=1
        census[segment]=dict(actions=len(mine),grades=dict(Counter(a['physical'] for a in mine)))
    assert dict(counts)==data['physical_counts'] and dict(literal)==data['actual_reference_physical_counts']
    assert sum(v['frames'] for v in seal['coverage'].values())==20098
    visuals=read(HERE/'PRIVATE_VISUALS.json')
    assert visuals['action_count']==len(features) and len(visuals['figures'])<=15
    for fig in visuals['figures']:
        verify_item(fig['artifact']);assert fig['layer_ownership']=='UNKNOWN' and not fig['future_used_for_prediction']
        assert fig['actual_old_anchor']['frame']<fig['frame']
        for panel in fig['panels']:
            maps=panel['actual_mapping']
            assert all(len(set(m.values()))==len(m)==panel['all_frame_native_masks'] for m in maps.values())
    write_new(HERE/'INDEPENDENT_CHECK.json',dict(status='PASS', source_files=len(source['artifacts']),
        all_original_action_grades_and_actual_publication_bound=True,prelabel_features_exact=len(features),
        label_read_after_feature_seal=True, exposed_audit_not_blind=True,
        actual_physical_counts=dict(counts),literal_bank_counts=dict(literal),origin_rules=dict(rule),
        segments=census,visuals=len(visuals['figures']),new_predictions=0,new_scoring=0,new_model_http=0,cost_usd=0,
        files=[artifact(HERE/name) for name in ('ACTIONS.json','FEATURES_SEALED.json','PRIVATE_VISUALS.json')]))
    print('Independent original-action/feature/source/grade/actual-publication census PASS',len(features),dict(counts))

if __name__=='__main__':main()
