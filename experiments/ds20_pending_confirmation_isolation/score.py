"""DS20 independent scoring: sealed own-state publication and actual physical anchors."""
from common import *
from collections import Counter
from mixed_depth import validate_certificate, validate_bound_measurement, bind_measurement, _digest as evidence_digest, _validated_facts
import ast
import time
import zipfile
from itertools import islice

DS14 = ROOT / 'experiments/ds14_raw_multidataset'
_math = module('ds20_frozen_ds14_score_math', DS14 / 'evaluate.py')
metrics, rle = _math.metrics, _math.rle
polygon_reference, unique_matches = _math.polygon_reference, _math.unique_matches
clear_step, same = _math.clear_step, _math.same
np, coco = _math.np, _math.coco
FIELDS = _math.FIELDS
EVENT_ARMS = ARMS[2:]
STATE_ARMS = ARMS[1:]
GT_DEV = _math.GT_DEV
ARCHIVE = WORK / 'output/evaluation/sam3_trackeval_20260912_1705/inputs.zip'
CAMERA_REFS = _math.CAMERA_REFS


def row_sha(row):
    return hashlib.sha256((json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n').encode()).hexdigest()


def measurement_rows(public):
    # The external cache covers the whole source. A real engineering prefix
    # binds only its published frames; a formal segment always uses all rows.
    return islice(rows(public/'MIXED_DEPTH.jsonl.gz'),read(public/'RUN_SUMMARY.json')['frames'])


def deltas(summary):
    return {base: {arm: {k: summary[arm][k] - summary[base][k] for k in FIELDS}
                   for arm in ARMS if arm != base}
            for base in ARMS}


def authoritative_development_pin():
    tree = ast.parse((OLD / 'score.py').read_text(encoding='utf-8'))
    pin = next(ast.literal_eval(node.value) for node in tree.body
               if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                   and target.id == 'GT_SHA' for target in node.targets))
    assert len(pin) == 64 and all(c in '0123456789abcdef' for c in pin)
    return pin


def verify_all():
    """No reference raster is opened here; actual prediction/source bytes are checked."""
    manifest = read(RUN / 'ALL_PREDICTIONS_SEALED.json')
    assert manifest['status'] in ('ALL_SIX_BRANCHES_EIGHT_SEGMENTS_SEALED',
                                  'ALL_PREDICTIONS_AND_ACCESS_SEALED')
    assert manifest['frames'] == sum(stop - start + 1 for start, stop in SEGMENTS.values()) == 20098
    assert tuple(manifest['arms']) == ARMS and set(manifest['seals']) == set(SEGMENTS)
    assert set(manifest['access_seals']) == set(SEGMENTS)
    checked = {}
    old_lock = read(HERE/'OLD_READONLY_LOCK.json')['files']

    def archive_item(path):
        path = Path(path)
        relative = path.relative_to(ROOT).as_posix()
        assert relative in old_lock and sha(path) == old_lock[relative], relative
        return artifact(path)

    def verify_once(item):
        expected = {k: item[k] for k in ('path', 'bytes', 'sha256')}
        if item['path'] in checked:
            assert checked[item['path']] == expected, item['path']
        else:
            verify_item(item)
            checked[item['path']] = expected

    def source_artifacts(value):
        if isinstance(value, dict):
            if {'path', 'bytes', 'sha256'} <= value.keys():
                verify_once(value)
            else:
                for child in value.values():
                    source_artifacts(child)
        elif isinstance(value, list):
            for child in value:
                source_artifacts(child)

    parity = {}
    for name, (start, stop) in SEGMENTS.items():
        public = RUN / name / 'public'
        verify_once(manifest['seals'][name])
        verify_once(manifest['access_seals'][name])
        seal = read(public / 'PREDICTIONS_SEALED.json')
        assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        assert seal['frames'] == seal['published_frames'] == stop - start + 1
        assert seal['original_frames'] == [start, stop] and tuple(seal['arms']) == ARMS
        for filename, digest in seal['artifacts_sha256'].items():
            assert sha(public / filename) == digest, (name, filename)
        frozen = read(public / 'FREEZE.json')
        assert frozen['no_gt_before_seal'] and frozen['new_model_http'] == frozen['model_cost_usd'] == 0
        assert tuple(frozen['arms']) == ARMS
        for path, digest in frozen['code_sha256'].items():
            assert sha(path) == digest, path
        if 'config_scientific_sha256' in frozen:
            assert sha(HERE / 'CONFIG.json') == frozen['config_scientific_sha256']
        verify_once(frozen['source_manifest'])
        chain = frozen['source_chain']
        source_artifacts(chain)
        source_artifacts(read(chain['raw_sources']['path']))
        verify_cache_reference(frozen['measurement_cache'])
        with gzip.open(public/'MIXED_DEPTH.jsonl.gz','rt',encoding='utf-8') as f:
            assert json.loads(next(f))==frozen['measurement_cache'] and next(f,None) is None
        access = read(public / 'ACCESS.json')
        assert access['status'] == 'NO_GT_RGB_RESTORED_NETWORK'
        assert access['new_model_http'] == access['cost_usd'] == 0
        allowed = {'frame_id', 'aligned/raw_depth_mm', 'aligned/raw_source_index',
                   'native/original_depth_mm', 'depth_mm', 'source_index'}
        assert all(set(item['fields']) <= allowed for item in access['h5_or_array_field_reads'])
        assert all(item['key'] in ('depth_mm', 'source_index') for item in access['npz_field_reads'])
        archived_public = DS19/'run'/name/'public'
        archived_seal = read(archived_public/'PREDICTIONS_SEALED.json')
        archived_sources = {filename:archive_item(archived_public/filename) for filename in
            ('PREDICTIONS_SEALED.json','predictions.jsonl.gz','METRICS.json')}
        assert archived_seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        assert archived_seal['frames'] == stop-start+1
        assert archived_sources['predictions.jsonl.gz']['sha256'] == archived_seal['artifacts_sha256']['predictions.jsonl.gz']
        count = 0
        for new, old, assignment in zip(rows(public / 'predictions.jsonl.gz'),
                rows(DS19 / 'run' / name / 'public/predictions.jsonl.gz'),
                rows(input_dir(name) / 'assignments.jsonl.gz'), strict=True):
            count += 1
            assert (new['frame'], new['global_frame'], new['time']) == (
                old['frame'], old['global_frame'], old['time'])
            assert new['variants']['SAM3_NATIVE'] == old['variants']['SAM3_NATIVE'] == assignment['variants']['N0']
            assert set(new['variants'])==set(ARMS)
            for arm in ('Z4Q_FROZEN','ACTIVITY_RETURN','MIXED_RETURN'):
                assert new['variants'][arm]==old['variants'][arm],(name,count,arm,'DS19 exact own-state control parity')
        assert count == stop - start + 1
        parity[name] = dict(frames=count, native_every_mask_and_id_exact=True,
                            original_Z4Q_every_mapping_exact=True,
                            DS19_archive_sources=archived_sources,
                            actual_publication_contract=verify_publication_sources(public),
                            order_source_contract=verify_order_sources(public),
                            automatic_source_contract=verify_automatic_sources(public))
    return manifest, dict(status='PASS', segments=parity, verified_source_artifacts=len(checked),
        DS19_metrics_source=archive_item(DS19/'run/METRICS.json'),
        archived_controls=['SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_RETURN','MIXED_RETURN'],
        every_control_native_mask_and_public_mapping_exact=True,GT_opened=False)


def verify_publication_sources(public):
    """Resolve every sealed publication and event-local commit before reference access."""
    orders=order_records(public)
    transactions=iter(rows(public/'TRANSACTIONS.jsonl.gz'));transaction=next(transactions,None)
    births=iter(rows(public/'BIRTHS.jsonl.gz'));birth=next(births,None)
    count=commits=0
    for prediction,ledger,packet in zip(rows(public/'predictions.jsonl.gz'),
            rows(public/'PUBLISH_LEDGER.jsonl'),measurement_rows(public),strict=True):
        frame=prediction['frame'];count+=1
        assert frame==count==ledger['frame']==packet['frame']
        assert prediction['global_frame']==ledger['global_frame']==packet['global_frame']
        assert row_sha(prediction)==ledger['prediction_row_sha256']
        assert row_sha(packet)==ledger['mixed_row_sha256']
        actual={arm:{int(x['mask'][2:]):x['id'] for x in prediction['variants'][arm]} for arm in ARMS}
        frame_transactions={}
        while transaction is not None and transaction['frame']==frame:
            arm=transaction['arm'];assert arm in STATE_ARMS and arm not in frame_transactions
            frame_transactions[arm]=transaction
            published={int(n):k for n,k in transaction['actual_published_mapping'].items()}
            assert published==actual[arm]
            if arm in ISOLATED_ARMS:
                isolation=transaction['controller_trace']['ds20_pending_isolation']
                assert isolation['independent_confirmation_store']
                assert isolation['ordinary_pending_not_overwritten']
                assert isolation['original_matrix_confirmation_and_windows_unchanged']
                assert isolation['evaluated_on_private_clone']
                assert isolation['ordinary_pending_after']==isolation['ordinary_pending_after_proposal']
                for confirmation in isolation['event_confirmations_after']:
                    identity,pending=confirmation['identity'],confirmation['pending']
                    assert confirmation['key']==evidence_digest(identity)
                    assert identity['event']==transaction['active_event']
                    assert identity['source_version'][:3]==[public.parent.name,arm,identity['native']]
                    assert identity['origin_rule']=='D1_DELAYED'
                    assert identity['anchor']['frame']<frame
                    assert pending['target']==identity['public'] and pending['count']>0
                    assert pending['start_time']<=pending['time']<=prediction['time']
            record=transaction.get('return_record')
            assert record==transaction['controller_trace'].get('ds19_event_local_return')
            if record:
                assert arm in RETURN_ARMS and record['status']=='EVENT_LOCAL_RETURN_COMMITTED'
                assert record['frame']==frame and record['q']!=frame
                assert record['event']==transaction['active_event']
                assert record['decisions_before_publication'] and record['old_publications_unchanged']
                assert record['immutable_entry_reference_preserved'] and record['original_confirmation_and_windows']
                assert record['outside_checks'] and all(record['outside_checks'].values())
                selected={int(n):k for n,k in record['selected'].items()}
                assert set(selected)==set(record['restored_sources'])==set(record['native_write_set'])
                assert len(selected)==len(set(selected.values()))
                assert {int(n):k for n,k in record['published_mapping'].items()}==selected
                actions=record['original_proposal_trace_events']
                assert {e['native_id']:e['canonical_id'] for e in actions}==selected
                for action in actions:
                    source,target=action['native_id'],action['canonical_id']
                    assert action['kind']=='reconnect' and action['accepted']
                    assert action['origin_rule'] in ('D1_DELAYED','BIRTH_REFINE')
                    assert action['edge_veto']['event_return_routed']
                    assert source in actual[arm] and actual[arm][source]==target
                    assert transaction['actual_alias_targets'][str(source)]==target
                    assert record['epochs'][str(source)]==transaction['epochs'][str(source)]
                    assert action['old_anchor']['frame']<frame
                    assert action['association_evidence_sha256']==evidence_digest(action['association_evidence_bindings'])
                    assert action in transaction['controller_trace']['events']
                commits+=len(selected)
            transaction=next(transactions,None)
        assert set(frame_transactions)==set(STATE_ARMS)
        frame_births={}
        while birth is not None and birth['frame']==frame:
            arm=birth['arm'];assert arm in EVENT_ARMS and arm not in frame_births
            assert birth['prediction_row_sha256']==ledger['prediction_row_sha256']
            assert row_sha(birth)==ledger['birth_row_sha256'][arm]
            assert {int(n):k for n,k in birth['actual_mapping'].items()}==actual[arm]
            frame_births[arm]=birth;birth=next(births,None)
        assert set(frame_births)==set(EVENT_ARMS)
        frame_orders={arm:o for (arm,f),o in orders.items() if f==frame}
        assert set(frame_orders)==set(ledger['order_row_sha256'])
        for arm,order in frame_orders.items():
            assert order['prediction_row_sha256']==ledger['prediction_row_sha256']
            assert row_sha(order)==ledger['order_row_sha256'][arm]
            assert all(actual[arm][int(n)]==k for n,k in order['published_mapping'].items())
    assert transaction is None and birth is None
    assert count==read(public/'RUN_SUMMARY.json')['frames']
    return dict(status='PASS',frames=count,local_return_sources_committed=commits,
        all_sealed_prediction_ledger_order_birth_transaction_bindings=True,GT_read=False)


def verify_automatic_sources(public):
    """Actual accepted D1/Birth measurements resolve to their own saved ROI before GT."""
    actions=[];bindings=[];updates={}
    def collect(value):
        if isinstance(value,dict):
            if {'association_role','actual_scalar','binding_sha256'}<=value.keys():
                yield value
            else:
                for child in value.values():yield from collect(child)
        elif isinstance(value,(list,tuple)):
            for child in value:yield from collect(child)
    for transaction in rows(public/'TRANSACTIONS.jsonl.gz'):
        if transaction['arm'] not in EVENT_ARMS:continue
        updates[transaction['frame'],transaction['arm']]=transaction['controller_trace']['ds18_reference_binding_state']['clean_whole_updates']
        for action in transaction['controller_trace'].get('events',[]):
            if action.get('kind')!='reconnect' or not action.get('accepted'):continue
            evidence=action['association_evidence_bindings']
            assert action['association_evidence_sha256']==evidence_digest(evidence)
            assert evidence['evaluation_frame']==transaction['frame'] and evidence['origin_rule']==action['origin_rule']
            if action['origin_rule']=='D1_DELAYED':
                for aggregate in [evidence]+evidence['partner_aggregates']:
                    assert aggregate['complete'] and 1<=len(aggregate['whole_history'])<=15
                    for contribution in aggregate['whole_history']:
                        record=contribution['actual_contribution'];b=record['binding']
                        assert contribution['binding_integrity_valid']
                        assert contribution['time']==record['clean_time']==b['time']
                        assert contribution['depth_mm']==record['median']==b['actual_scalar']['median']
                        assert record['anchor']['frame']==b['frame']<transaction['frame']
                        assert record['anchor']['native_id']==b['native'] and record['anchor']['canonical_id']==aggregate['public_id']
                    ema=aggregate['ema_last_update']
                    assert ema['actual_ema_mm']==aggregate['actual_ema_mm']
            facts=list(collect(evidence));assert len(facts)>=2,(public.parent.name,transaction['frame'],'missing actual evidence')
            for b in facts:
                assert b['segment']==public.parent.name and b['frame']<=transaction['frame']
                assert b['source_version'][:3]==[public.parent.name,transaction['arm'],b['native']]
                assert b['version_key'][:2]==[public.parent.name,transaction['arm']]
            actions.append((transaction,action,evidence,facts));bindings.extend(facts)
    needed={b['frame'] for b in bindings};actual={};ema_last={};ema_archive={};ema_count=0
    actual_frames=read(public/'RUN_SUMMARY.json')['frames']
    for packet,source in zip(measurement_rows(public),islice(rows(input_dir(public.parent.name)/'observations.jsonl.gz'),actual_frames),strict=True):
        assert packet['frame']==source['frame']
        # Fully validate each serialized certificate once before immutable local reuse.
        # External JSON never receives the trusted token without full verification.
        packet['objects']={n:_validated_facts(c) for n,c in packet['objects'].items()}
        if packet['frame'] in needed:actual[packet['frame']]=packet
        for arm in EVENT_ARMS:
            for update in updates[packet['frame'],arm]:
                n,k=update['input_native'],update['public_id'];c=packet['objects'][str(n)]
                raw=next(o['depth'] for o in source['observations'] if o['id']==n)
                b=bind_measurement(c,'D1_WHOLE',raw,source_version=update['input_source_version'],version_key=update['input_identity_version'])
                assert update['input_binding_sha256']==b['binding_sha256'] and update['input_certificate_sha256']==c['certificate_sha256']
                assert update['frame']==packet['frame'] and update['time']==b['time']
                assert update['input_median_mm']==raw['median']
                previous=ema_last.get((arm,k))
                if update['previous_ema_mm'] is None:
                    assert update['previous_update_sha256'] is None
                    expected=raw['median']
                else:
                    assert previous is not None and previous['frame']<update['frame']
                    assert update['previous_update_sha256']==evidence_digest(previous)
                    assert update['previous_ema_mm']==previous['actual_ema_mm']
                    expected=.2*raw['median']+.8*previous['actual_ema_mm']
                assert update['actual_ema_mm']==expected
                full={key:value for key,value in update.items() if key!='public_id' and not key.startswith('input_')}
                full['input_median_mm']=update['input_median_mm'];full['actual_input_binding']=b
                ema_last[arm,k]=full;ema_archive[arm,k,update['frame']]=evidence_digest(full);ema_count+=1
    assert needed<=actual.keys()
    original={r['frame']:r for r in rows(input_dir(public.parent.name)/'profiles.jsonl.gz') if r['frame'] in needed}
    checked=0
    for transaction,action,evidence,facts in actions:
        current=[];old=[]
        for binding in facts:
            n,f,role=binding['native'],binding['frame'],binding['association_role']
            c=actual[f]['objects'][str(n)]
            assert validate_bound_measurement(binding,binding['actual_scalar'],role,c,native=n,frame=f)
            assert binding['measurement_valid']
            if transaction['arm'] in MIXED_ARMS:assert binding['screened_eligible']
            p=next(x for x in original[f]['observations'] if x['id']==n)
            scalar=p['core' if role=='BIRTH_CORE' else 'whole']
            assert all(scalar[k]==v for k,v in binding['actual_scalar'].items()),(public.parent.name,f,n,role)
            (current if f==transaction['frame'] else old).append(binding)
            checked+=1
        origin=action.get('origin_rule') or 'D1_DELAYED'
        assert current and old
        if origin=='BIRTH_REFINE':
            assert {'BIRTH_CORE','BIRTH_WHOLE'}<={b['association_role'] for b in current}
            assert {'BIRTH_CORE','BIRTH_WHOLE'}<={b['association_role'] for b in old}
        else:
            assert any(b['association_role']=='D1_WHOLE' for b in current)
            assert any(b['association_role']=='D1_WHOLE' for b in old)
            for aggregate in [evidence]+evidence['partner_aggregates']:
                ema=aggregate['ema_last_update']
                assert ema_archive[transaction['arm'],aggregate['public_id'],ema['frame']]==evidence_digest(ema)
    return dict(status='PASS',actual_accepted_actions=len(actions),actual_measurement_bindings=checked,
        actual_accepted_origin_counts=dict(Counter(action['origin_rule'] for _,action,_,_ in actions)),
        whole_ema_updates_recomputed=ema_count,whole_last15_and_partner_ema_recomputed=True,
        same_ROI_raw_profiles=True,GT_read=False,all_accepted_actions_have_current_and_actual_past_evidence=True)


def reference_rows(name, dev_pin):
    start, stop = SEGMENTS[name]
    if name == 'fishsa_development_8400':
        assert sha(GT_DEV) == dev_pin
        for row in rows(GT_DEV):
            yield row['global_frame_id'], [x['id'] for x in row['gt_grid']], [rle(x['rle']) for x in row['gt_grid']]
    elif name == 'fishsa_validation_2888':
        with zipfile.ZipFile(ARCHIVE) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            assert len(manifest['gt']) == 12188
            for global_frame in range(start, stop + 1):
                entry = manifest['gt'][global_frame - 1]
                raw = archive.read(entry['key'])
                assert hashlib.sha256(raw).hexdigest() == entry['sha256']
                label = json.loads(raw)
                assert (label['imageHeight'], label['imageWidth']) == (1080, 1920)
                ids, encoded = polygon_reference(label['shapes'], 1080, 1920, transform=True)
                yield global_frame, ids, encoded
    else:
        base = DATA if name.startswith('feeding_') else WORK / 'data/AnnotationNewBags_20260919' / name
        folder = 'labels_640x360' if name.startswith('feeding_') else CAMERA_REFS[name]
        size = (360, 640) if name.startswith('feeding_') else (1080, 1920)
        for global_frame in range(start, stop + 1):
            ids, encoded = polygon_reference(read(base / folder / f'{global_frame:06d}.json')['shapes'], *size)
            yield global_frame, ids, encoded


def order_records(public):
    """Exactly one immutable decision row per arm/current first split."""
    records = {}
    for row in rows(public / 'ORDER_EVIDENCE.jsonl.gz'):
        key = (row['arm'], row['frame'])
        assert key not in records and row['arm'] in EVENT_ARMS, key
        assert row['q'] == row['frame'], key
        assert row['selected_choice'] == row['restore']['selected_choice'], key
        assert row['detail'].get('evidence_max_frame', row['frame']) == row['frame'], key
        records[key] = row
    return records


def order_annotation(row):
    """Preserve input-side relations without turning them into depth ground truth."""
    if row is None:
        return dict(status='NO_FIRST_SPLIT_DECISION', physical_depth_order_truth='UNKNOWN')
    detail = row['detail']
    evidence = detail.get('order_evidence')
    return dict(status='SEALED_ORDER_ROW_BOUND_TO_ACTUAL_PUBLICATION',
        order_row_sha256=row_sha(row), selected_choice=row['selected_choice'],
        order_evidence_present=evidence is not None,
        order_evidence=evidence, arm=row['arm'],
        permutation_control=False,
        physical_depth_order_truth='UNKNOWN',
        identity_reference_verdict_is_not_depth_surface_truth=True)


def verify_order_sources(public):
    """Independently resolve every saved order fact to immutable actual raw statistics."""
    records = order_records(public)
    needed = {row['q'] for row in records.values()}
    needed.update(pair['frame'] for row in records.values()
                  for pair in (row['detail'].get('order_evidence') or {}).get('pre_pairs', []))
    measured = {}
    actual_frames=read(public/'RUN_SUMMARY.json')['frames']
    for current, original in zip(rows(public / 'DEPTH_OBSERVATIONS.jsonl.gz'),
                                 islice(rows(input_dir(public.parent.name) / 'DEPTH_OBSERVATIONS.jsonl.gz'),actual_frames), strict=True):
        assert current == original, (public.parent.name, current['frame'], 'raw measurement archive parity')
        if current['frame'] in needed:
            measured[current['frame']] = current
    assert needed <= measured.keys()
    mixed = {}
    for item in measurement_rows(public):
        if item['frame'] in needed: mixed[item['frame']] = item
        assert item['source_binding']['global_frame']==item['global_frame']
        assert all(validate_certificate(c) for c in item['objects'].values())
    events = read(public / 'EVENTS.json')
    pre_facts = post_facts = permuted = 0
    for (arm, frame), row in records.items():
        evidence = row['detail'].get('order_evidence')
        if evidence is None:
            continue  # The STATE_FIXED control uses the old absolute-depth selector.
        assert evidence['query_frame'] == frame and evidence['query_time'] == row['time']
        event = next(event for event in events[arm] if event['q'] == frame)
        assert evidence['pre_cutoff_frame'] == event['suspect_frame'] - 1
        if evidence['status'] == 'UNKNOWN':
            assert not evidence['eligible'] and row['selected_choice'] == 'H0'
        else:
            assert evidence['status'] == 'MEASURED_PAIRED_ORDER' and evidence['eligible']
        for pair in evidence['pre_pairs']:
            before = measured[pair['frame']]
            assert pair['frame'] <= evidence['pre_cutoff_frame'] < frame
            assert pair['time'] == before['time'] < row['time']
            for role, public_id in zip(('A', 'B'), event['public_ids'], strict=True):
                sample = pair[role]
                raw = before['adaptive_raw'][str(sample['native'])]
                assert sample['public'] == public_id and sample['fact_id'] == raw['fact_id']
                assert sample['z_mm'] == raw['core']['median'] and sample['mad_mm'] == raw['core']['mad']
                assert raw['core_usable'] and (arm not in MIXED_ARMS or mixed[pair['frame']]['objects'][str(sample['native'])]['core']['eligible_single']) and sample['time'] == before['time']
                assert sample['source_native'] == sample['native'] and sample['core_usable']
                assert sample['measured_n'] == sample['n'] == raw['core']['n']
                assert sample['measured_valid_fraction'] == sample['valid_fraction'] == raw['core']['valid_fraction']
                geometry = next(point for point in event['pre_geometry_history'][role]
                                if point['frame'] == pair['frame'])
                assert not geometry['neighbors'] and geometry['source'] == sample['native']
                assert geometry['public_id'] == public_id and geometry['time'] == sample['time']
                version = sample['version_key']
                assert version[2] == geometry['source_generation'] and version[3] == public_id
                assert version[4] == geometry['public_epoch']
                if arm!='DS16_ORDER':
                    c=mixed[pair['frame']]['objects'][str(sample['native'])]
                    assert validate_bound_measurement(sample['association_measurement_binding'],raw['core'],
                        'S0_ADAPTIVE_CORE',c,source_version=[public.parent.name,arm,sample['native'],version[2]],
                        version_key=version,native=sample['native'],frame=pair['frame'],before_frame=frame)
                pre_facts += 1
            assert pair['delta_B_minus_A_mm'] == pair['B']['z_mm'] - pair['A']['z_mm']
        current = measured[frame]['adaptive_raw']
        contract=row['detail']['association_measurement_contract']
        assert contract['whole']=='NOT_USED_BY_S0_ORDINAL'
        for native, binding in evidence['post_bindings'].items():
            native = int(native)
            actual, assigned = current[str(native)], current[str(binding['assigned_depth_source'])]
            assert binding['observation_source'] == binding['actual_state_source'] == native
            assert binding['actual_state_fact_id'] == actual['fact_id']
            assert binding['actual_core'] == actual['core']
            assert binding['assigned_measurement_fact_id'] == assigned['fact_id']
            assert binding['core'] == assigned['core']
            assert not binding['scoring_permutation_only']
            if arm!='DS16_ORDER':
                actual_binding=contract['current'][str(native)]['S0_ADAPTIVE_CORE']
                assert validate_bound_measurement(actual_binding,actual['core'],'S0_ADAPTIVE_CORE',
                    mixed[frame]['objects'][str(native)],native=native,frame=frame)
                assert actual_binding['identity_state']=='IDENTITY_UNASSIGNED'
            if arm != 'ORDER_PERMUTE':
                assert binding['assigned_depth_source'] == native
            elif binding['assigned_depth_source'] != native:
                permuted += 1
            post_facts += 1
    return dict(status='PASS', pre_fact_bindings=pre_facts, post_fact_bindings=post_facts,
        assigned_source_permutations=permuted, frozen_raw_statistics_exact=True,
        permutation_only_in_scoring_binding=True, physical_depth_accuracy='UNKNOWN', GT_read=False)


def physical_audit(name, matches, predictions):
    """Literal bank endpoints and fixed S0-P fragment consensus are separate outcomes."""
    public = RUN / name / 'public'
    events = read(public / 'EVENTS.json')
    orders = order_records(public)
    first_seen = {}
    for frame, prediction in predictions.items():
        for item in prediction['variants']['SAM3_NATIVE']:
            first_seen.setdefault(int(item['mask'][2:]), frame)

    def match(frame, source):
        return matches.get(frame, {}).get(int(source), dict(status='SOURCE_OR_REFERENCE_MISSING'))

    def expected_mapping(anchors, posts):
        known = {x['gt_id']: target for target, x in anchors.items() if x['status'] == 'UNIQUE_IOU_MATCH'}
        if (len(known) == len(anchors) == len(posts) == 2 and
                all(x['status'] == 'UNIQUE_IOU_MATCH' and x['gt_id'] in known for x in posts.values()) and
                len({x['gt_id'] for x in posts.values()}) == 2):
            return {source: known[x['gt_id']] for source, x in posts.items()}
        return {}

    def verdict(actual, expected):
        return 'UNSCORABLE' if not expected else 'CORRECT' if actual == expected else 'WRONG'

    def consensus(history):
        known = [match(item['frame'], item['source']) for item in history]
        ids = [x['gt_id'] for x in known if x['status'] == 'UNIQUE_IOU_MATCH']
        contiguous = all(b['frame'] == a['frame'] + 1 for a, b in zip(history, history[1:]))
        versions = {(x.get('source'), x.get('source_generation'), x.get('public_id'), x.get('public_epoch')) for x in history}
        qualified = bool(len(ids) >= 3 and len(set(ids)) == 1 and contiguous and len(versions) == 1)
        value = dict(status='UNIQUE_IOU_MATCH', gt_id=ids[0]) if qualified else dict(status='UNSCORABLE_FRAGMENT_CONSENSUS')
        return value, dict(observations=len(history), known=len(ids), continuous=contiguous,
                           same_version=len(versions) == 1, gt_ids=sorted(set(ids)), samples=known)

    automatic = {arm: [] for arm in STATE_ARMS}
    local_returns={arm:[] for arm in RETURN_ARMS}
    for transaction in rows(public / 'TRANSACTIONS.jsonl.gz'):
        arm, frame = transaction['arm'], transaction['frame']
        published = {int(x['mask'][2:]): x['id'] for x in predictions[frame]['variants'][arm]}
        record=transaction.get('return_record')
        if record:
            assert arm in RETURN_ARMS and record['status']=='EVENT_LOCAL_RETURN_COMMITTED'
            for action in record['original_proposal_trace_events']:
                source,target=action['native_id'],action['canonical_id']
                anchor=action['old_anchor']
                current,past,origin=match(frame,source),match(anchor['frame'],anchor['native_id']),match(first_seen.get(target),target)
                relations=dict(query_vs_bank=same(current,past),bank_vs_public_origin=same(past,origin),
                    query_vs_public_origin=same(current,origin))
                applied=published[source]==target
                durable=transaction['actual_alias_targets'].get(str(source))==target
                assert applied and durable
                physical='WRONG' if 'DIFFERENT' in relations.values() else 'UNSCORABLE' if 'UNKNOWN' in relations.values() else 'CORRECT'
                actual_reference_physical='CORRECT' if relations['query_vs_bank']=='SAME' else 'WRONG' if relations['query_vs_bank']=='DIFFERENT' else 'UNSCORABLE'
                prior_public_reference_status='PREEXISTING_PUBLIC_ORIGIN_MISMATCH' if relations['bank_vs_public_origin']=='DIFFERENT' else 'CONSISTENT_PUBLIC_ORIGIN' if relations['bank_vs_public_origin']=='SAME' else 'UNSCORABLE_PUBLIC_ORIGIN'
                first=record['first_publication'].get(str(source))
                local_returns[arm].append(dict(segment=name,arm=arm,event=record['event'],generation=record['generation'],
                    frame=frame,global_frame=transaction['global_frame'],q=record['q'],
                    source=source,target=target,origin_rule=action['origin_rule'],
                    physical=physical,actual_reference_physical=actual_reference_physical,
                    prior_public_reference_status=prior_public_reference_status,
                    relations=relations,query_match=current,bank_match=past,public_origin_match=origin,
                    actual_old_anchor=anchor,actual_first_public_id_after_this_commit=published[source],
                    original_first_source_publication=first,
                    return_delay_since_first_source_frames=None if first is None else frame-first['frame'],
                    applied_at_current_publication=applied,durable_alias_after_commit=durable,
                    explicit_event_transaction=True,counted_as_automatic=False,
                    selected_original_proposal=action,actual_commit_record=record))
        for action in transaction['controller_trace'].get('events', []):
            if action.get('kind') != 'reconnect' or not action.get('accepted'):
                continue
            source, target = action['native_id'], action['canonical_id']
            anchor = action.get('old_anchor')
            current = match(frame, source)
            past = match(anchor['frame'], anchor['native_id']) if anchor else dict(status='MISSING_ANCHOR')
            origin = match(first_seen.get(target), target)
            relations = dict(query_vs_bank=same(current, past), bank_vs_public_origin=same(past, origin),
                             query_vs_public_origin=same(current, origin))
            applied = published[source] == target
            candidates = [item for item in transaction['automatic_candidate_events'] if item['event'] == action]
            assert len(candidates) == 1, (arm, frame, source, target, 'automatic telemetry binding')
            candidate = candidates[0]
            assert candidate['applied_at_first_publication'] == applied
            durable = candidate['durable_alias_after_commit']
            overridden = candidate['overridden_by_explicit_transaction']
            assert durable == (transaction['actual_alias_targets'].get(str(source)) == target)
            committed = bool(applied and durable and not overridden)
            physical = ('NOT_FIRST_PUBLISHED' if not applied else 'NOT_DURABLE_AUTO_COMMIT' if not committed
                        else 'WRONG' if 'DIFFERENT' in relations.values()
                        else 'UNSCORABLE' if 'UNKNOWN' in relations.values() else 'CORRECT')
            physical_reference=('NOT_FIRST_PUBLISHED' if not applied else 'NOT_DURABLE_AUTO_COMMIT' if not committed
                else 'CORRECT' if relations['query_vs_bank']=='SAME'
                else 'WRONG' if relations['query_vs_bank']=='DIFFERENT' else 'UNSCORABLE')
            public_reference=('PREEXISTING_PUBLIC_ORIGIN_MISMATCH' if relations['bank_vs_public_origin']=='DIFFERENT'
                else 'CONSISTENT_PUBLIC_ORIGIN' if relations['bank_vs_public_origin']=='SAME' else 'UNSCORABLE_PUBLIC_ORIGIN')
            automatic[arm].append(dict(frame=frame, global_frame=transaction['global_frame'], source=source,
                target=target, origin_rule=action.get('origin_rule') or (
                    'BIRTH_REFINE' if action.get('phase') == 'birth' else 'D1_DELAYED'),
                stage_accepted=True, applied_at_first_publication=applied, actual_first_public_id=published[source],
                durable_alias_after_commit=durable, overridden_by_explicit_transaction=overridden,
                durable_automatic_commit=committed,
                physical=physical, physical_definition='CONSERVATIVE_JOINT_ACTUAL_BANK_AND_PUBLIC_ORIGIN',
                actual_reference_physical=physical_reference, prior_public_reference_status=public_reference,
                incidental_public_origin_return=(relations['query_vs_public_origin']=='SAME' and relations['query_vs_bank']=='DIFFERENT'),
                relations=relations, query_match=current, bank_match=past,
                public_origin_match=origin, actual_old_anchor=anchor, actual_controller_action=action))
    write_new(public / 'AUTOMATIC_RECONNECT_AUDIT.json', dict(segment=name, arms=automatic,
        counts={arm: dict(Counter(x['physical'] for x in values)) for arm, values in automatic.items()},
        bank_and_public_origin_kept_separate=True, UNKNOWN_not_correct=True, postseal_only=True,
        accepted_preview_is_not_durable_commit=True, explicit_transactions_not_counted_as_automatic=True))
    write_new(public/'LOCAL_RETURN_AUDIT.json',dict(segment=name,arms=local_returns,
        counts={arm:dict(Counter(row['physical'] for row in values)) for arm,values in local_returns.items()},
        actual_reference_counts={arm:dict(Counter(row['actual_reference_physical'] for row in values)) for arm,values in local_returns.items()},
        bank_and_public_origin_kept_separate=True,UNKNOWN_not_correct=True,postseal_only=True,
        old_publications_unchanged=True,no_double_count_as_automatic=True))

    results = {}
    for arm in EVENT_ARMS:
        group_rows, birth_rows = [], []
        for event in events[arm]:
            query_frame, restore = event['q'], event['restore']
            detail = dict(segment=name, arm=arm, event=event['id'], suspect=event['suspect_frame'],
                          confirm=event['confirm_frame'], q=query_frame, status=event['status'])
            if query_frame is None:
                group_rows.append(dict(detail, physical='NO_SPLIT'))
                continue
            assert event['evidence_cutoff_frame'] == query_frame
            numeric_detail = event['numeric']['detail']
            if 'evidence_max_frame' in numeric_detail:
                assert numeric_detail['evidence_max_frame'] == query_frame
            assert all(x['frame'] == query_frame for x in event['post_first_observations'].values())
            anchors = {int(target): match(anchor['frame'], anchor['native_id']) if anchor else
                       dict(status='MISSING_ANCHOR') for target, anchor in event['reference_anchors'].items()}
            posts = {int(source): match(query_frame, source) for source in event['post_first_observations']}
            actual = {int(x['mask'][2:]): x['id'] for x in predictions[query_frame]['variants'][arm]
                      if int(x['mask'][2:]) in posts}
            expected = expected_mapping(anchors, posts)
            consensus_anchors, support, endpoints = {}, {}, {}
            for role, target in zip(('A', 'B'), event['public_ids'], strict=True):
                history = event.get('pre_geometry_history', {}).get(role, [])
                assert all(x['frame'] < event['suspect_frame'] for x in history)
                value, evidence = consensus(history)
                consensus_anchors[int(target)] = value
                support[role] = evidence
                endpoints[role] = match(history[-1]['frame'], history[-1]['source']) if history else dict(status='MISSING_CLEAN_FRAGMENT')
            consensus_expected = expected_mapping(consensus_anchors, posts)
            endpoint_expected = expected_mapping(dict(zip(event['public_ids'], endpoints.values(), strict=True)), posts)
            post_consensus = {}
            for source in posts:
                known = []
                for frame in range(query_frame, min(len(predictions), query_frame + 10) + 1):
                    value = match(frame, source)
                    if value['status'] != 'UNIQUE_IOU_MATCH':
                        break
                    known.append(value['gt_id'])
                post_consensus[str(source)] = dict(gt_id=known[0] if len(known) >= 3 and len(set(known)) == 1 else None,
                                                   matched_frames=len(known), gt_ids=known)
            committed = restore['status'] == 'COMMIT'
            group_rows.append(dict(detail, physical=verdict(actual, expected) if committed else 'NOT_COMMITTED',
                choice=restore['selected_choice'], restore_status=restore['status'], expected_mapping=expected,
                actual_first_public_mapping=actual, selected_mapping=restore['mapping'], anchors=anchors, posts=posts,
                changes=restore['changes'], first_public_physical=verdict(actual, expected),
                clean_endpoint_matches=endpoints, clean_endpoint_expected_mapping=endpoint_expected,
                first_public_clean_endpoint_verdict=verdict(actual, endpoint_expected),
                pre_consensus_support=support, pre_consensus_expected_mapping=consensus_expected,
                first_public_pre_consensus_verdict=verdict(actual, consensus_expected),
                committed_pre_consensus_verdict=verdict(actual, consensus_expected) if committed else 'NOT_COMMITTED',
                post_q_through_q10_consensus=post_consensus, postseal_future_diagnostic_not_prediction_input=True,
                depth_order=order_annotation(orders.get((arm, query_frame)))))
        for row in rows(public / 'BIRTHS.jsonl.gz'):
            if row['arm'] != arm:
                continue
            for query in row['queries']:
                if query['status'] != 'COMMIT':
                    continue
                frame = row['frame']
                clean, bank, candidate = query['selected_reference_anchor'], query['selected_anchor'], query['selected_candidate']
                current = match(frame, query['source'])
                past, actual_bank = match(clean['frame'], clean['native_id']), match(bank['frame'], bank['native_id'])
                origin = match(first_seen.get(candidate['source']), candidate['source'])
                relations = dict(query_vs_clean=same(current, past), bank_vs_clean=same(actual_bank, past), origin_vs_clean=same(origin, past))
                physical = 'WRONG' if 'DIFFERENT' in relations.values() else 'UNSCORABLE' if 'UNKNOWN' in relations.values() else 'CORRECT'
                birth_rows.append(dict(segment=name, arm=arm, frame=frame, global_frame=row['global_frame'],
                    source=query['source'], target=query['selected_target'], actual_first_public_id=query['actual_first_public_id'],
                    physical=physical, relations=relations, query_match=current, clean_match=past, bank_match=actual_bank,
                    origin_match=origin, selection=query['selection'], surface_identity='UNKNOWN', physical_depth_accuracy='UNKNOWN'))
        results[arm] = dict(group_events=group_rows, birth_commits=birth_rows,
            group_physical_counts=dict(Counter(x['physical'] for x in group_rows)),
            birth_physical_counts=dict(Counter(x['physical'] for x in birth_rows)))
    results['automatic_reconnect'] = automatic
    results['local_event_return']=local_returns
    write_new(public / 'EVENT_AUDIT.json', dict(segment=name, arms=results,
        consensus_rule='At least3 unique matches, all same GT, contiguous same-version pre-fragment; UNKNOWN retained',
        bank_clean_endpoint_and_consensus_separate=True, unresolved_is_not_correct=True))
    return results


def score_segment(name, dev_pin):
    start, stop = SEGMENTS[name]
    public = RUN / name / 'public'
    gt, similarities, matches, prediction_rows = [], [], {}, {}
    pred = {arm: [] for arm in ARMS}
    previous, step = {arm: {} for arm in ARMS}, {arm: {} for arm in ARMS}
    switches, changed = {arm: [] for arm in ARMS}, {arm: [] for arm in STATE_ARMS}
    publication = {row['frame']: row for row in rows(public / 'PUBLISH_LEDGER.jsonl')}
    orders = order_records(public)
    events = read(public / 'EVENTS.json')
    assert set(orders) == {(arm, event['q']) for arm in EVENT_ARMS for event in events[arm]
                           if event['q'] is not None}
    assert set(publication) == set(range(1, stop - start + 2))
    mixed_iter=iter(measurement_rows(public))
    transactions = iter(rows(public / 'TRANSACTIONS.jsonl.gz'))
    transaction = next(transactions, None)
    births = iter(rows(public / 'BIRTHS.jsonl.gz'))
    birth = next(births, None)
    contacts = iter(rows(public / 'CONTACT_CERTIFICATES.jsonl.gz'))
    for index, (assignment, prediction, reference, contact) in enumerate(zip(
            rows(input_dir(name) / 'assignments.jsonl.gz'), rows(public / 'predictions.jsonl.gz'),
            reference_rows(name, dev_pin), contacts, strict=True), 1):
        global_frame, ids, reference_masks = reference
        assert prediction['frame'] == assignment['frame'] == contact['frame'] == index
        assert prediction['global_frame'] == global_frame == contact['global_frame'] == start + index - 1
        assert prediction['time'] == assignment['time'] == contact['time']
        assert set(prediction['variants']) == set(ARMS)
        assert prediction['variants']['SAM3_NATIVE'] == assignment['variants']['N0']
        keys = [x['mask'] for x in assignment['variants']['N0']]
        sources = [int(key[2:]) for key in keys]
        encoded = [rle(assignment['masks'][key]) for key in keys]
        if name in ('L3', 'LW'):
            label = read(WORK / 'data/AnnotationNewBags_20260919' / name / 'labels_raw' / f'{global_frame:06d}.json')
            native_ids, encoded = polygon_reference(label['shapes'], 1080, 1920)
            assert native_ids == sources
        matrix = (np.asarray(coco.iou(reference_masks, encoded, [0] * len(encoded)), float).reshape(len(ids), len(encoded))
                  if ids and encoded else np.zeros((len(ids), len(encoded))))
        gt.append(ids)
        similarities.append(matrix)
        matches[index] = unique_matches(ids, sources, matrix)
        prediction_rows[index] = prediction
        ledger = publication[index]
        assert row_sha(prediction) == ledger['prediction_row_sha256']
        assert row_sha(contact) == ledger['contact_row_sha256']
        mixed_frame=next(mixed_iter)
        assert mixed_frame['frame']==index and row_sha(mixed_frame)==ledger['mixed_row_sha256']
        frame_orders = {arm: row for (arm, frame), row in orders.items() if frame == index}
        assert set(ledger.get('order_row_sha256', {})) == set(frame_orders), (name, index, 'order ledger coverage')
        for arm, decision in frame_orders.items():
            assert decision['global_frame'] == global_frame and decision['time'] == prediction['time']
            assert decision['prediction_row_sha256'] == ledger['prediction_row_sha256']
            assert row_sha(decision) == ledger['order_row_sha256'][arm]
            actual = {int(item['mask'][2:]): item['id'] for item in prediction['variants'][arm]}
            published = {int(n): target for n, target in decision['published_mapping'].items()}
            assert all(actual[n] == target for n, target in published.items())
            event = next(event for event in events[arm] if event['q'] == index)
            assert decision['event'] == event['id'] and decision['restore'] == event['restore']
            assert decision['detail'] == event['numeric']['detail']
            assert set(published) == {int(n) for n in event['post_first_observations']}
        frame_transactions = {}
        while transaction is not None and transaction['frame'] == index:
            arm = transaction['arm']
            assert arm in STATE_ARMS and arm not in frame_transactions
            frame_transactions[arm] = transaction
            transaction = next(transactions, None)
        assert set(frame_transactions) == set(STATE_ARMS)
        for arm in ARMS:
            objects = prediction['variants'][arm]
            assert [x['mask'] for x in objects] == keys
            public_ids = [x['id'] for x in objects]
            assert len(public_ids) == len(set(public_ids)) == len(encoded)
            pred[arm].append(public_ids)
            step[arm], new_switches = clear_step(ids, keys, public_ids, matrix, previous[arm], step[arm], global_frame)
            switches[arm].extend(dict(x, segment=name) for x in new_switches)
            if arm == 'SAM3_NATIVE':
                continue
            actual = dict(zip(sources, public_ids, strict=True))
            assert {int(n): v for n, v in frame_transactions[arm]['actual_published_mapping'].items()} == actual
            if objects != prediction['variants']['SAM3_NATIVE']:
                changed[arm].append(global_frame)
            if arm in ledger['event_publish']:
                pair = ledger['event_publish'][arm]
                assert pair['q'] == index and pair['post_sample_count'] == 1
                assert all(actual[int(n)] == value for n, value in pair['first_public_pair'].items())
        frame_births = {}
        while birth is not None and birth['frame'] == index:
            arm = birth['arm']
            assert arm in EVENT_ARMS and arm not in frame_births
            frame_births[arm] = birth
            assert row_sha(birth) == ledger['birth_row_sha256'][arm]
            assert birth['prediction_row_sha256'] == ledger['prediction_row_sha256']
            assert {int(n): v for n, v in birth['actual_mapping'].items()} == {
                int(x['mask'][2:]): x['id'] for x in prediction['variants'][arm]}
            for query in birth['queries']:
                assert query['post_sample_count'] == 1 and query['query_observation']['frame'] == index
                assert query['actual_first_public_id'] == birth['actual_mapping'][str(query['source'])]
            if birth['queries']:
                first = ledger['birth_publish'][arm]
                assert first['post_sample_count'] == 1 and first['transaction_version'] == birth['transaction_version']
                assert all(first['first_public_ids'][str(q['source'])] == q['actual_first_public_id'] for q in birth['queries'])
            birth = next(births, None)
        assert set(frame_births) == set(EVENT_ARMS)
        assert all(not value['queries'] and not value['changes'] and
                   value['status'] == 'ORIGINAL_Z4Q_AUTOMATIC_ONLY' for value in frame_births.values()), (name, index)
        if index % 500 == 0:
            print(name, 'SCORE', index, flush=True)
    assert transaction is None and birth is None and len(gt) == stop - start + 1
    summary = {arm: metrics(gt, pred[arm], similarities)[0] for arm in ARMS}
    for arm in ARMS:
        assert len(switches[arm]) == summary[arm]['IDSW']
        assert summary[arm]['predictions'] == summary['SAM3_NATIVE']['predictions']
        # CLEAR prioritizes previous GT/track matches; altered identities can
        # change assignment cardinality despite identical masks. Report actual
        # FP/FN, while the mask/count and archived-control checks remain strict.
    old_metrics = read(DS15 / 'run/METRICS.json')['segments'][name]['metrics']
    assert summary['SAM3_NATIVE'] == old_metrics['SAM3_NATIVE']
    assert summary['Z4Q_FROZEN'] == old_metrics['Z4Q_FROZEN']
    for arm in ('ACTIVITY_RETURN','MIXED_RETURN'):
        assert summary[arm]==read(DS19/'run/METRICS.json')['segments'][name]['metrics'][arm]
    archive = read(DS18/'run/BASELINE_PARITY.json')['segments'].get(name, {})
    expected_archive = archive.get('expected_metrics', {})
    archive_diagnostic = dict(status=archive.get('status', 'UNKNOWN_NO_ARCHIVE'),
        expected_metrics=expected_archive, numerical_gate=False,
        differences={k: summary['Z4Q_FROZEN'][k] - expected_archive[k] for k in expected_archive})
    result = dict(segment=name, frames=len(gt), metrics=summary, deltas=deltas(summary), changed_frames=changed,
        original_z4q_archive_diagnostic=archive_diagnostic,
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3', 'LW') else 'EXPOSED_EXISTING_ANNOTATION',
        score_protocol='ExactDS14 official mask CLEAR.5 Identity.5 HOTA19alphas; original full-raster FishSA/1080camera and scaledFeeding')
    write_new(public / 'METRICS.json', result)
    write_new(public / 'SWITCHES.json', switches)
    with gzip.open(public / 'REFERENCE_MATCHES.jsonl.gz', 'xt', encoding='utf-8') as output:
        for frame, value in matches.items():
            output.write(json.dumps(dict(frame=frame, matches=value), separators=(',', ':')) + '\n')
    audit = physical_audit(name, matches, prediction_rows)
    return result, (gt, pred, similarities), audit


def main():
    assert not (RUN / 'METRICS.json').exists(), 'Never rescore or overwrite completed output'
    began = time.perf_counter()
    seal, parity = verify_all()
    write_new(RUN / 'PREDICTION_PARITY.json', parity)
    dev_pin = authoritative_development_pin()
    assert sha(GT_DEV) == dev_pin
    write_new(RUN / 'SCORING_FREEZE.json', dict(status='ALL_SEALS_VERIFIED_BEFORE_REFERENCE_SCORING',
        all_prediction_seal=artifact(RUN / 'ALL_PREDICTIONS_SEALED.json'), scorer=artifact(__file__),
        frozen_metric_math=artifact(DS14 / 'evaluate.py'), development_reference=artifact(GT_DEV),
        development_reference_authority=artifact(OLD / 'score.py'), development_reference_sha256=dev_pin,
        validation_original_archive=artifact(ARCHIVE), validation_adapter_authority=artifact(DS14 / 'finish_scoring.py'),
        aligned_package_annotation_version_not_substituted=True, camera_references=CAMERA_REFS,
        no_prediction_or_parameter_edit=True, new_model_http=0, cost_usd=0))
    results, audits = {}, {}
    pool_gt, pool_pred, pool_sims = [], {arm: [] for arm in ARMS}, []
    for name in SEGMENTS:
        result, (gt, pred, sims), audit = score_segment(name, dev_pin)
        results[name], audits[name] = result, audit
        if name.startswith('feeding_'):
            pool_gt.extend([[(name, x) for x in ids] for ids in gt])
            pool_sims.extend(sims)
            for arm in ARMS:
                pool_pred[arm].extend([[(name, x) for x in ids] for ids in pred[arm]])
    pooled = {arm: metrics(pool_gt, pool_pred[arm], pool_sims)[0] for arm in ARMS}
    old_pooled = read(DS15 / 'run/METRICS.json')['feeding_pooled']['metrics']
    assert all(pooled[arm] == old_pooled[arm] for arm in ('SAM3_NATIVE', 'Z4Q_FROZEN'))
    for arm in ('ACTIVITY_RETURN','MIXED_RETURN'):
        assert pooled[arm]==read(DS19/'run/METRICS.json')['feeding_pooled']['metrics'][arm]
    write_new(RUN / 'METRICS.json', dict(status='SCORED_AFTER_ALL_FOUR_EVENT_ARMS_AND_CONTROLS_EIGHT_SEALS', frames=20098,
        segments=results, feeding_pooled=dict(frames=1471, metrics=pooled, deltas=deltas(pooled)),
        event_audits=audits, no_cross_dataset_pooled_headline=True, physical_depth_accuracy='UNKNOWN',
        all_seal=artifact(RUN / 'ALL_PREDICTIONS_SEALED.json'), elapsed_seconds=time.perf_counter() - began,
        new_model_http=0, cost_usd=0))
    write_new(RUN / 'SCORE_PROVENANCE.json', dict(scorer=artifact(__file__), scientific_source_and_runtime_verified=True,
        scoring_freeze=artifact(RUN / 'SCORING_FREEZE.json'), prediction_parity=artifact(RUN / 'PREDICTION_PARITY.json'),
        reference_opened_after_all_seals=True, trackeval_package=artifact(Path(_math.trackeval.__file__)),
        official_metric_and_raster_math_unchanged=True, masked_or_ignored_ids=0, GT_used_for_predictions=False))
    print(json.dumps(dict(feeding=pooled, segments={name: row['deltas'] for name, row in results.items()})), flush=True)


if __name__ == '__main__':
    main()
