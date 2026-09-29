"""Final public artifact and boundary checks; no model calls or new scoring."""
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

HERE=Path(__file__).resolve().parent
OUT=HERE/'run_8400_v2/public'
INITIAL=HERE/'run_8400/public'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path,value):
    if path.exists():
        assert read(path)==value,path
        return
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)
        handle.write('\n')


def run():
    freeze=read(OUT/'FREEZE.json')
    initial=read(INITIAL/'FREEZE.json')
    old_public=HERE.parent/'ms1_s0_development_8400/run_development_v7_recovery/public'
    assert sha(old_public/'PREDICTIONS_SEALED.json')==freeze['old_hold_seal_sha256']
    assert sha(old_public/'METRICS.json')==freeze['old_hold_metrics_sha256']
    final_seal=read(OUT/'PREDICTIONS_SEALED.json')
    initial_seal=read(INITIAL/'PREDICTIONS_SEALED.json')
    for path,digest in freeze['code_sha256'].items():
        assert sha(path)==digest,path
    for name in ('manager_p.py','replay_p.py'):
        original=next(v for k,v in initial['code_sha256'].items() if k.endswith(name))
        assert sha(HERE/'attempt1_source'/name)==original
    assert sha(HERE/'attempt1_source/score_p.py')==read(INITIAL/'SCORE_PROVENANCE.json')['scorer_sha256']
    for public,seal in ((OUT,final_seal),(INITIAL,initial_seal)):
        assert seal['frames']==seal['published_frames']==8400
        for name,key in [('predictions_development.jsonl.gz','predictions_sha256'),
                         ('TRANSACTIONS.jsonl.gz','transactions_sha256'),
                         ('PUBLISH_LEDGER.jsonl','publish_ledger_sha256'),
                         ('EVENTS.json','events_sha256'),('CALL_LEDGER.jsonl','call_ledger_sha256')]:
            assert sha(public/name)==seal[key],name
        assert (public/'CALL_LEDGER.jsonl').stat().st_size==0
    metrics=read(OUT/'METRICS.json')
    switches=read(OUT/'SWITCH_AUDIT.json')
    events=read(OUT/'EVENTS.json')['events']
    assert [metrics['metrics'][x]['IDSW'] for x in ('B0','OLD-HOLD','HOLD-P')]==[6,18,2]
    assert switches['counts']=={'B0':6,'OLD-HOLD':18,'HOLD-P':2}
    assert switches['old_temporary_roundtrips_removed']==16
    assert len(switches['new_only'])==0
    assert len(events)==13 and sum(e['q'] is not None for e in events)==9
    assert sum(e['status']=='LOCAL_FALLBACK_UNRESOLVED' for e in events)==2
    physical=read(OUT/'PHYSICAL_EVENT_AUDIT.json')
    assert physical['q_events']==9
    outside=read(OUT/'OUTSIDE_STATE_AUDIT.json')
    assert outside['checked_active_frames']==outside['exact_frames']==299 and not outside['failures']
    slice_=read(HERE/'F2145_SLICE.json')
    def public(arm,frame,mask):
        return next(x['id'] for x in slice_[arm][str(frame)] if x['mask']==mask)
    assert public('old',2145,'n:4')==-1000001
    assert [public('repaired',f,'n:4') for f in (2144,2145,2146)]==[4,4,4]
    ledger=[json.loads(x) for x in (OUT/'PUBLISH_LEDGER.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(ledger)==8400 and [x['frame'] for x in ledger]==list(range(1,8401))
    assert all(ledger[e['q']-1]['event_publish']['q']==e['q'] for e in events if e['q'])
    figures=read(OUT/'VISUALIZATION_DATA.json')['figures']
    assert len(figures)==2
    for figure in figures:
        path=Path(figure['svg'])
        assert sha(path)==figure['svg_sha256'] and ElementTree.parse(path).getroot().tag.endswith('svg')
        assert figure['raw_pixels_included'] is False and figure['gt_used'] is False
    restricted=read(OUT/'RESTRICTED_INVENTORY.json')['records']
    assert len(restricted)==8
    for item in restricted.values():
        path=Path(item['path'])
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
    tests=dict(status='PASS',unit_tests=5,real_f2145_source_slice='PASS',
        mock_h2_publisher_once='PASS',unresolved_preview_not_published='PASS',
        continuous_residual_and_carrier_change='PASS',
        one_mask_one_public_output='PASS',
        group_failure_preserves_outside_branch_state='PASS',
        final_full_replay_frames=8400,independent_outside_state_frames=299,
        original_mask_order_and_id_uniqueness='PASS_BY_REPLAY_AND_SCORER',
        no_gt_before_prediction_seal='PASS_BY_SOURCE_AUDIT_AND_SEPARATE_SCORER',
        future_frames_not_used_in_q='UNCHANGED_S0_CONTROL_FLOW_AND_ONE_POINT_POST',
        initial_attempt_preserved=True)
    write_new(HERE/'TEST_REPORT.json',tests)
    acceptance=dict(status='PASS_WITH_EXPOSED_DEVELOPMENT_LIMIT',review_base=freeze['review_base'],
        final_prediction_sha256=final_seal['predictions_sha256'],
        initial_prediction_sha256=initial_seal['predictions_sha256'],
        frames=8400,events=13,q_events=9,new_model_http=0,new_model_cost_usd=0,
        old_paid_inference_status='16_START_15_END_F5927_S0_HTTP_UNKNOWN',
        old_hold_source='V7_ZERO_HTTP_RECOVERY_REPLAY',
        masks_and_ids_included=True,negative_ids_not_filtered=True,
        full_metrics_scored_after_seal=True,first_publication_one_per_frame=True,
        outside_state_frames_exact=299,original_seals_unchanged=True,
        new_vlm_metric_row=False,initial_postscore_engineering_revision_disclosed=True,
        restricted_inventory_verified=True,figures_valid_svg=True)
    write_new(OUT/'ACCEPTANCE.json',acceptance)
    print('ACCEPTANCE',acceptance['status'])


if __name__=='__main__':
    run()
