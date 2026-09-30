"""DS8: all prediction/source/code seals before any reference access."""
from common import *
import gzip,hashlib,importlib.util,json,sys
spec=importlib.util.spec_from_file_location('ds8_official_helpers',NE1/'score.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
mask_rles,metrics,original_score=legacy.mask_rles,legacy.metrics,legacy.original_score
np,coco=original_score.np,original_score.coco
sys.path.insert(0,str(HERE))
SEALED_FILES={'predictions.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz','DEPTH_STATES.jsonl.gz',
 'TRANSACTIONS.jsonl.gz','PUBLISH_LEDGER.jsonl','EVENTS.json','RUN_SUMMARY.json','FREEZE.json',
 'COMMON_STATE_SHADOW.json','PERFORMANCE.json'}
REQUIRED_ACCESS_TOKENS={'labels_640x360','labels_original','labels_source','sealed_test',
 '/rgb_640x360/','/rgb_original/','/color/','/rgb/','depth_restored_rgb_640x360/'}

def verify_all_seals(run=RUN):
    run=Path(run)
    manifest=read(run/'ALL_PREDICTIONS_SEALED.json')
    assert manifest['status']=='ALL_FIVE_BRANCHES_FOUR_SEGMENTS_SEALED'
    assert manifest['frames']==1471 and tuple(manifest['arms'])==ARMS
    assert set(manifest['seals'])==set(SEGMENTS)
    assert manifest['new_model_http']==manifest['model_cost_usd']==0
    for name,(start,stop) in SEGMENTS.items():
        public=run/name/'public'
        assert sha(public/'PREDICTIONS_SEALED.json')==manifest['seals'][name]
        seal=read(public/'PREDICTIONS_SEALED.json')
        assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
        assert seal['segment']==name and seal['original_frames']==[start,stop]
        assert tuple(seal['arms'])==ARMS and seal['frames']==seal['published_frames']==stop-start+1
        assert seal['new_model_http']==seal['model_cost_usd']==0
        assert SEALED_FILES<=set(seal['artifacts_sha256'])
        for n,h in seal['artifacts_sha256'].items():assert sha(public/n)==h,n
        freeze=read(public/'FREEZE.json')
        assert freeze['status']=='FROZEN_BEFORE_PREDICTION' and freeze['no_gt_before_seal'] is True
        assert freeze['segment']==name and freeze['original_frames']==[start,stop] and freeze['frames']==stop-start+1
        for p in (HERE/'evaluate.py',HERE/'event_audit.py',HERE/'score_checks.py',DS1/'postseal.py',NE1/'score.py',OLD/'score.py'):
            assert str(p.resolve()) in freeze['code_sha256'],p
        for p,h in freeze['code_sha256'].items():assert sha(p)==h,p
        assert len(freeze['native_depth_sources'])==stop-start+1
        for item in list(freeze['derived_inputs'].values())+list(freeze['restored_sources'].values())+list(freeze['current_metadata'].values())+freeze['native_depth_sources']:verify_item(item)
        assert sha(input_dir(name)/'SOURCE_MANIFEST.json')==freeze['source_manifest_sha256']
        assert sha(input_dir(name)/'scan_v4.json')==freeze['scan_sha256']
        assert sha(input_dir(name)/'sources.json')==freeze['source_list_sha256']
        originals=read(input_dir(name)/'sources.json');assert len(originals)==stop-start+1
        for src in originals:
            for prefix in ('prediction','depth'):
                verify_item(dict(path=src[prefix+'_path'],bytes=src[prefix+'_bytes'],sha256=src[prefix+'_sha256']))
    access=read(run/'ACCESS_SEALED.json')
    verify_item(access['artifact']);verify_item(access['prediction_all_seal'])
    assert Path(access['artifact']['path']).resolve()==(run/'PREDICTION_ACCESS_AUDIT.json').resolve()
    assert Path(access['prediction_all_seal']['path']).resolve()==(run/'ALL_PREDICTIONS_SEALED.json').resolve()
    audit=read(run/'PREDICTION_ACCESS_AUDIT.json')
    assert audit['status']=='NO_DIRECT_GT_RGB_V3_OR_NETWORK_DURING_PREDICTION'
    assert audit['new_model_http']==audit['cost_usd']==0
    assert REQUIRED_ACCESS_TOKENS<=set(audit['forbidden_path_tokens'])
    for p in audit['observed_data_paths']:
        assert not any(k in p.replace('\\','/').lower() for k in audit['forbidden_path_tokens'])
    assert all(x['key'] in ('depth_mm','source_index') for x in audit['npz_field_reads'])
    return manifest

def observation_facts(row,arm):
    return row['restored' if arm=='P2_RESTORED_DEPTH' else 'adaptive_raw' if arm=='P1_RAW_DEPTH' else 'objects']

def check_objects(assignment,prediction):
    assert prediction['variants']['SAM3_NATIVE']==assignment['variants']['N0']
    assert set(prediction['variants'])==set(ARMS)
    masks=[x['mask'] for x in assignment['variants']['N0']]
    for arm in ARMS:
        objs=prediction['variants'][arm]
        assert [x['mask'] for x in objs]==masks
        assert all(type(x['id']) is int for x in objs),arm
        assert len(objs)==len(set(x['id'] for x in objs))
    return masks

def check_q_binding(e,arm,predictions,publish,transactions,states):
    q=e['q'];pub=publish[q]['event_publish'][arm]
    assert e['evidence_cutoff_frame']==q
    assert all(x['frame']==q for x in e['post_first_observations'].values())
    sources={int(n) for n in e['post_first_observations']};assert len(sources)==2
    assert pub['episode']==e['id'] and pub['q']==q and pub['post_sample_count']==1
    actual={int(x['mask'][2:]):x['id'] for x in predictions[q]['variants'][arm]}
    pair={n:actual[n] for n in sources}
    assert {int(n):v for n,v in pub['first_public_pair'].items()}==pair
    tx=transactions[(q,arm)]
    assert {int(n):v for n,v in tx['actual_published_mapping'].items()}==actual
    assert tx['restore']==e['restore']
    restore=e['restore'];staged=not restore['status'].startswith('LOCAL_FALLBACK')
    if staged:
        assert {int(n):v for n,v in restore['mapping'].items()}==pair
        assert bool(restore['changes'])==(restore['status']=='COMMIT')
        for n in sources:
            live=states[(q,arm)]['live'].get(str(n))
            assert not live or all(f>=q for f in live['sample_frames'])
    if arm in ('P0_NATIVE_PRESERVE','P1_RAW_DEPTH','P2_RESTORED_DEPTH'):
        preview={int(n):v for n,v in restore['baseline_preview_mapping'].items()}
        if not staged:assert pair==preview
        if staged:
            assert {int(n):v for n,v in restore['changes'].items()}=={n:v for n,v in pair.items() if preview[n]!=v}
        detail=e['numeric']['detail']
        if 'accepted' in detail:
            assert detail['evidence_max_frame']==q
            assert bool(detail['accepted'])==(e['numeric']['choice'] in ('H1','H2'))
            for edge in detail['edges'].values():
                assert max(edge['predict']['sample_frames'],default=0)<e['suspect_frame']
    return pair

def verify_publication(run=RUN):
    run=Path(run);verify_all_seals(run);checks=[];q_checks=history_checks=group_checks=0
    for name,(start,stop) in SEGMENTS.items():
        public=run/name/'public';nframes=stop-start+1
        current=list(rows(public/'predictions.jsonl.gz'))
        old_public=DS6/'run'/name/'public';old_seal=read(old_public/'PREDICTIONS_SEALED.json')
        assert old_seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
        assert old_seal['frames']==old_seal['published_frames']==nframes
        old_all=read(DS6/'run/ALL_PREDICTIONS_SEALED.json')
        assert sha(old_public/'PREDICTIONS_SEALED.json')==old_all['seals'][name]
        for file,h in old_seal['artifacts_sha256'].items():assert sha(old_public/file)==h,file
        old=list(rows(old_public/'predictions.jsonl.gz'))
        state_rows=list(rows(public/'DEPTH_STATES.jsonl.gz'))
        states={(x['frame'],x['arm']):x for x in state_rows}
        tx_rows=list(rows(public/'TRANSACTIONS.jsonl.gz'))
        tx={(x['frame'],x['arm']):x for x in tx_rows}
        expected_keys={(f,a) for f in range(1,nframes+1) for a in ARMS[1:]}
        assert len(state_rows)==len(states)==len(tx_rows)==len(tx)==nframes*(len(ARMS)-1)
        assert set(states)==set(tx)==expected_keys
        measurements={x['frame']:x for x in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        assert set(measurements)==set(range(1,nframes+1))
        events=read(public/'EVENTS.json');assert set(events)==set(ARMS[1:])
        publisher=list(rows(public/'PUBLISH_LEDGER.jsonl'));publish={x['frame']:x for x in publisher}
        assert len(publisher)==len(publish)==nframes
        predictions={x['frame']:x for x in current};assert len(predictions)==nframes
        with gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf-8') as lines:
            for i,(line,pub,assignment,new,previous) in enumerate(zip(lines,publisher,rows(input_dir(name)/'assignments.jsonl.gz'),current,old,strict=True),1):
                assert hashlib.sha256(line.encode()).hexdigest()==pub['prediction_row_sha256']
                assert new['frame']==pub['frame']==assignment['frame']==i
                assert new['global_frame']==pub['global_frame']==assignment['global_frame_id']==start+i-1
                assert all(new[k]==previous[k] for k in ('frame','global_frame','time'))
                assert measurements[i]['frame']==i and measurements[i]['global_frame']==start+i-1 and measurements[i]['time']==new['time']
                check_objects(assignment,new)
                assert new['variants']['D2_CORE_FROZEN']==previous['variants']['D2_CORE_FROZEN']
                assert new['variants']['P0_NATIVE_PRESERVE']==new['variants']['SAM3_NATIVE'],(name,i)
                for arm in ARMS[1:]:
                    actual={int(x['mask'][2:]):x['id'] for x in new['variants'][arm]}
                    assert {int(n):v for n,v in tx[(i,arm)]['actual_published_mapping'].items()}==actual
                    last={int(x['mask'][2:]):x['id'] for x in predictions[i-1]['variants'][arm]} if i>1 else {}
                    assert {int(n):v for n,v in tx[(i,arm)]['previous_mapping'].items()}==last
        assert len(current)==nframes
        for arm in ARMS[1:]:
            for e in events[arm]:
                for role,frozen in (e['depth_frozen'] or {}).items():
                    assert frozen['cutoff_frame']==e['suspect_frame']-1
                    samples=frozen['samples']
                    assert all(x['frame']<e['suspect_frame'] for x in samples)
                    assert all(b['frame']==a['frame']+1 and b['time']>a['time'] for a,b in zip(samples,samples[1:]))
                    if samples:assert frozen['key'][0]==name and frozen['key'][1]==arm and frozen['key'][3]==frozen['public']
                    for x in samples:
                        live=states[(x['frame'],arm)]['live'].get(str(frozen['source']))
                        assert live and live['key']==frozen['key'] and x['frame'] in live['sample_frames']
                        row=measurements[x['frame']]
                        fact=observation_facts(row,arm)[str(frozen['source'])]
                        assert fact['core_usable'] and x['time']==row['time']
                        assert x['fact_id']==fact['fact_id'] and x['source']==fact['source']
                        assert x['z_mm']==fact['core']['median'] and x['mad_mm']==fact['core']['mad']
                        history_checks+=1
                for group in e['group_observations']:
                    live=states[(group['frame'],arm)]['live'].get(str(group['source']))
                    assert not live or group['frame'] not in live['sample_frames'];group_checks+=1
                if e['q'] is not None:
                    check_q_binding(e,arm,predictions,publish,tx,states);q_checks+=1
        checks.append(dict(segment=name,frames=len(current),native_exact=True,old_D2_exact=True,P0_equals_native=True,old_seal_sha256=sha(old_public/'PREDICTIONS_SEALED.json')))
    write_new(run/'VERIFICATION.json',dict(status='PASS_BEFORE_GT_SCORING',checks=checks,
        q_publication_checks=q_checks,frozen_sample_fact_checks=history_checks,group_checks=group_checks,
        zero_deleted_masks=True,all_prediction_seals_verified=True,access_seal_sha256=sha(run/'ACCESS_SEALED.json')))

def support_layers(pooled):
    def exceeds(a,b):
        return all(pooled[a][k]>pooled[b][k] for k in ('IDF1','HOTA','AssA')) and pooled[a]['IDSW']<=pooled[b]['IDSW']
    return dict(P1_raw_tracking_support=exceeds('P1_RAW_DEPTH','SAM3_NATIVE'),
        P2_offline_tracking_support=exceeds('P2_RESTORED_DEPTH','SAM3_NATIVE'),
        P2_restored_increment_vs_raw=exceeds('P2_RESTORED_DEPTH','P1_RAW_DEPTH'),
        P2_full_frozen_rule=all(exceeds('P2_RESTORED_DEPTH',other) for other in ('SAM3_NATIVE','P0_NATIVE_PRESERVE','P1_RAW_DEPTH')),
        P2_scope='EXPOSED_OFFLINE_NATIVE_V2_RGB_NEXT_FRAME_SUPPORTED',
        physical_depth_accuracy='UNKNOWN',causal_raw_depth_and_restored_claims_separate=True)
def namespaced(ids, segment_index):
    return [(segment_index, int(identity)) for identity in ids]


def score(run=RUN):
    verify_all_seals(run)
    verification = read(Path(run)/'VERIFICATION.json')
    assert verification['status'] == 'PASS_BEFORE_GT_SCORING'
    combined_truth, combined_sims = [], []
    combined = {arm: [] for arm in ARMS}
    segment_metrics, reference, changed = {}, {}, {}
    pairs = [(arm, 'SAM3_NATIVE') for arm in ARMS[1:]] + [
        ('P2_RESTORED_DEPTH', arm) for arm in ('P0_NATIVE_PRESERVE', 'P1_RAW_DEPTH', 'D2_CORE_FROZEN')]
    for index, (name, (start, stop)) in enumerate(SEGMENTS.items()):
        truth, sims = [], []
        predictions = {arm: [] for arm in ARMS}
        reference_hash = hashlib.sha256()
        changed[name] = {f'{a}_vs_{b}': 0 for a, b in pairs}
        for local, (assignment, prediction) in enumerate(zip(
                rows(input_dir(name)/'assignments.jsonl.gz'),
                rows(Path(run)/name/'public/predictions.jsonl.gz'), strict=True), 1):
            native = check_objects(assignment, prediction)
            assert assignment['frame'] == prediction['frame'] == local
            assert assignment['global_frame_id'] == prediction['global_frame'] == start+local-1
            path = DATA/'labels_640x360'/f'{start+local-1:06d}.json'
            raw = path.read_bytes()
            reference_hash.update(path.name.encode()+b'\0'+raw)
            gt_ids, gt_masks = mask_rles(json.loads(raw)['shapes'])
            masks = [original_score.rle(assignment['masks'][key]) for key in native]
            sim = (np.asarray(coco.iou(gt_masks, masks, [0]*len(masks)), float)
                   if gt_masks and masks else np.zeros((len(gt_ids), len(native))))
            truth.append(gt_ids); sims.append(sim)
            combined_truth.append(namespaced(gt_ids, index)); combined_sims.append(sim)
            for arm in ARMS:
                ids = [int(x['id']) for x in prediction['variants'][arm]]
                predictions[arm].append(ids)
                combined[arm].append(namespaced(ids, index))
            for a, b in pairs:
                changed[name][f'{a}_vs_{b}'] += prediction['variants'][a] != prediction['variants'][b]
        assert len(truth) == stop-start+1
        segment_metrics[name] = {arm: metrics(truth, predictions[arm], sims) for arm in ARMS}
        reference[name] = dict(label_dir=str(DATA/'labels_640x360'), frames=len(truth),
            ordered_file_bytes_sha256=reference_hash.hexdigest(),
            qualification='existing human-edited RGB polygons; not independently certified',
            physical_depth_gt=False, pixel_surface_gt=False)
    pooled = {arm: metrics(combined_truth, combined[arm], combined_sims) for arm in ARMS}
    for arm in ARMS:
        for key in ('IDSW', 'FP', 'FN', 'GT', 'predictions'):
            assert pooled[arm][key] == sum(x[arm][key] for x in segment_metrics.values()), (arm, key)
    delta = {f'{a}_vs_{b}': {key: pooled[a][key]-pooled[b][key]
        for key in ('IDF1', 'HOTA', 'AssA', 'DetA', 'IDSW', 'FP', 'FN')} for a, b in pairs}
    support = {other: dict(rate_improvements={key: pooled['P2_RESTORED_DEPTH'][key] > pooled[other][key]
                  for key in ('IDF1', 'HOTA', 'AssA')},
                  idsw_not_increased=pooled['P2_RESTORED_DEPTH']['IDSW'] <= pooled[other]['IDSW'])
               for other in ('P0_NATIVE_PRESERVE','P1_RAW_DEPTH','SAM3_NATIVE')}
    supported = all(all(x['rate_improvements'].values()) and x['idsw_not_increased'] for x in support.values())
    result = dict(status='SCORED_AFTER_ALL_PREDICTION_SEALS', frames=len(combined_truth),
        segment_metrics=segment_metrics, pooled_metrics=pooled, pooled_delta=delta,
        changed_frames=changed, reference=reference,
        seal_sha256={name: sha(Path(run)/name/'public/PREDICTIONS_SEALED.json') for name in SEGMENTS},
        all_seal_sha256=sha(Path(run)/'ALL_PREDICTIONS_SEALED.json'),
        no_negative_id_filtering=True, segment_identity_reset=True,
        pooled_method='direct_TrackEval_on_all_frames_with_tuple_segment_identity_namespaces',
        score_support_layers=support_layers(pooled), frozen_support_rule=support, frozen_support_rule_met=supported,
        interpretation='exposed development-set tracking result; no physical-depth or surface-ownership GT',
        new_model_http=0, model_cost_usd=0)
    assert result['frames'] == 1471
    write_new(Path(run)/'METRICS.json', result)
    write_new(Path(run)/'SCORE_PROVENANCE.json', dict(evaluate_sha256=sha(__file__),
        event_audit_sha256=sha(HERE/'event_audit.py'), legacy_helpers_sha256=sha(NE1/'score.py'), matching_helper_sha256=sha(DS1/'postseal.py'), score_template_sha256=sha(HERE.parent/'ds7_depth_native_recovery/evaluate.py'), score_adaptation='DS8_P1_adaptive_raw_P2_restored_D2_P0_original_objects',
        scored_after_all_seals=True, trackeval_path=str(original_score.DEPS),
        reference=reference, segment_seal_sha256=result['seal_sha256'],
        all_seal_sha256=result['all_seal_sha256'], verification_sha256=sha(Path(run)/'VERIFICATION.json')))
    return result


def main():
    verify_publication()
    result=score()
    import event_audit
    event_audit.audit(sys.modules[__name__])
    print(json.dumps(dict(pooled=result['pooled_metrics'],delta=result['pooled_delta'],support=result['frozen_support_rule_met'])))
if __name__=='__main__':main()
