"""Reproduce the DS26 cohort from sealed DS25 prediction evidence only.

This is the actual one-off generation algorithm, saved after its initial
execution. It reads no GT, metric, image, raw pixel, API or server artifact.
No filtering uses depth qualification, correctness or later outcomes.

Use a fresh destination, optionally retaining the original created_utc to
reproduce byte-identical files on the same checkout and absolute source paths:
    python build_cohort.py --output-dir <fresh-directory> --created-utc <UTC>
The two output files are created with exclusive mode; old artifacts are never
overwritten. Existing source logs and seals are read-only.
"""
import argparse
import collections
import datetime
import gzip
import hashlib
import json
import pathlib


HERE = pathlib.Path(__file__).resolve().parent
DS25 = HERE.parent / 'ds25_contact_local_layers'
BASE_COMMIT = 'e76a5184aafa9780a46c93f2128264291707c4d6'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(obj):
    return sha(json.dumps(obj, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode())


def artifact(path):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size,
                sha256=sha(path.read_bytes()))


def build(destination, created_utc=None):
    """Preserve every logical role/version pair and every original reference."""
    destination = pathlib.Path(destination).resolve()
    outputs = [destination / 'COHORT.json', destination / 'COHORT_REVIEW.json']
    if any(path.exists() for path in outputs):
        raise FileExistsError('Choose a fresh output directory; cohort outputs are immutable')
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    sources = []
    transactions = {}
    facts = {}
    seals = {}
    context_map = {}
    pair_map = {}
    references = []

    for directory in sorted((DS25 / 'run').iterdir()):
        if not directory.is_dir():
            continue
        public = directory / 'public'
        name = directory.name
        order_path = public / 'ORDER_CHECKS.jsonl.gz'
        transaction_path = public / 'TRANSACTIONS.jsonl.gz'
        measurement_path = public / 'MEASUREMENTS.jsonl.gz'
        seal_path = public / 'PREDICTIONS_SEALED.json'
        if not order_path.exists():
            continue
        seal = json.loads(seal_path.read_text())
        assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        seals[name] = seal
        for path in [order_path, transaction_path, measurement_path]:
            pin = artifact(path)
            assert pin['sha256'] == seal['artifacts_sha256'][path.name], (name, path.name)
            sources.append(pin)
        sources.append(artifact(seal_path))

        facts[name] = {}
        with gzip.open(measurement_path, 'rt', encoding='utf8') as stream:
            for line in stream:
                fact = json.loads(line)
                assert fact['fact_id'] not in facts[name]
                facts[name][fact['fact_id']] = fact

        with gzip.open(order_path, 'rb') as stream:
            for line_number, raw in enumerate(stream, 1):
                row = json.loads(raw)
                for check_index, check in enumerate(row['checks']):
                    for comparison_index, comparison in enumerate(check['comparisons']):
                        if not comparison.get('pre_pairs'):
                            continue
                        assert check['query_frame'] == row['frame'] == comparison['source_query_cutoff'] == comparison['current_pair']['frame']
                        assert check['target_anchor_version'] == comparison['pre_versions']['A']
                        assert comparison['pre_versions']['B'] == comparison['current_partner_claim_version']
                        assert check['anchor']['frame'] == comparison['pre_pairs'][-1]['frame']
                        seeds = [node for node in comparison['anonymous_contact'] if node['contact_seed']]
                        assert len(seeds) == 1
                        assert comparison['actual_contact_seed_frame'] == seeds[0]['frame']
                        citations = [*comparison['pre_pairs'], *comparison['anonymous_contact'], comparison['current_pair']]
                        for citation in citations:
                            assert citation['frame'] <= row['frame']
                            fact = facts[name][citation['fact_id']]
                            assert fact['frame'] == citation['frame'] and fact['time'] == citation['time']
                            assert digest(fact) == citation['measurement_sha256']

                        context_key = dict(
                            segment=name, anchor=check['anchor'],
                            target_anchor_version=check['target_anchor_version'],
                            partner_native=comparison['partner_native'],
                            partner_public=comparison['partner_public'],
                            partner_version=comparison['pre_versions']['B'],
                            pre_frames=[node['frame'] for node in comparison['pre_pairs']],
                            pre_fact_ids=[node['fact_id'] for node in comparison['pre_pairs']],
                            seed_frame=comparison['actual_contact_seed_frame'],
                            seed_fact_id=seeds[0]['fact_id'],
                            seed_binding=comparison['actual_contact_seed_binding'],
                            seed_original_mask_bindings=comparison['seed_original_mask_bindings'])
                        context_id = 'CTX_' + digest(context_key)[:16]
                        logical_key = dict(
                            context_id=context_id, segment=name, q=row['frame'],
                            current_native=check['native_id'],
                            candidate_target_public=check['public_id'],
                            exact_anchor=check['anchor'],
                            target_anchor_version=check['target_anchor_version'],
                            partner_native=comparison['partner_native'],
                            partner_public=comparison['partner_public'],
                            partner_version=comparison['pre_versions']['B'],
                            current_partner_claim_version=comparison['current_partner_claim_version'])
                        pair_id = 'PAIR_' + digest(logical_key)[:16]
                        reference_id = 'REF_' + digest(dict(
                            segment=name, line_1based=line_number,
                            check_index=check_index, comparison_index=comparison_index,
                            raw_line_sha256=sha(raw)))[:16]
                        context = context_map.setdefault(context_id, dict(
                            context_id=context_id, key=context_key,
                            logical_pair_ids=[], reference_ids=[]))
                        assert context['key'] == context_key
                        if pair_id not in context['logical_pair_ids']:
                            context['logical_pair_ids'].append(pair_id)
                        context['reference_ids'].append(reference_id)
                        pair = pair_map.setdefault(pair_id, dict(
                            pair_id=pair_id, context_id=context_id, key=logical_key,
                            segment=name, q=row['frame'], query_frame=row['frame'],
                            global_frame=row['global_frame'], time=row['time'],
                            current_native=check['native_id'], target_public=check['public_id'],
                            partner_native=comparison['partner_native'],
                            partner_public=comparison['partner_public'],
                            target_anchor=check['anchor'], pre_versions=comparison['pre_versions'],
                            current_partner_claim_version=comparison['current_partner_claim_version'],
                            pre_frames=[node['frame'] for node in comparison['pre_pairs']],
                            seed_frame=comparison['actual_contact_seed_frame'],
                            ds25_citations=dict(
                                pre_pairs=[{key: node[key] for key in ('frame', 'time', 'fact_id', 'measurement_sha256')}
                                           for node in comparison['pre_pairs']],
                                anonymous_contact=[{key: node[key] for key in ('frame', 'time', 'fact_id', 'measurement_sha256', 'contact_seed')}
                                                   for node in comparison['anonymous_contact']],
                                current_pair={key: comparison['current_pair'][key]
                                              for key in ('frame', 'time', 'fact_id', 'measurement_sha256')}),
                            reference_ids=[], origin_rules=[]))
                        assert pair['key'] == logical_key
                        assert pair['ds25_citations']['current_pair']['fact_id'] == comparison['current_pair']['fact_id']
                        pair['reference_ids'].append(reference_id)
                        if check['origin_rule'] not in pair['origin_rules']:
                            pair['origin_rules'].append(check['origin_rule'])
                        references.append(dict(
                            reference_id=reference_id, pair_id=pair_id, context_id=context_id,
                            segment=name, q=row['frame'], origin_rule=check['origin_rule'],
                            order_file=str(order_path.resolve()), line_1based=line_number,
                            raw_line_sha256=sha(raw), raw_line_hash_includes_terminal_newline=True,
                            check_index=check_index, comparison_index=comparison_index,
                            canonical_check_sha256=digest(check),
                            canonical_comparison_sha256=digest(comparison)))
                        entries.append((name, row, check, comparison, context_id, pair_id, reference_id))
        assert seal['frames'] == line_number
        needed = {pair['q'] for pair in pair_map.values() if pair['segment'] == name}
        needed.update(frame for context in context_map.values() if context['key']['segment'] == name
                      for frame in context['key']['pre_frames'])
        transactions[name] = {}
        with gzip.open(transaction_path, 'rt', encoding='utf8') as stream:
            for line in stream:
                transaction = json.loads(line)
                if transaction['arm'] == 'Z4Q_LOCAL_LAYERS' and transaction['frame'] in needed:
                    transactions[name][transaction['frame']] = transaction

    # The actual q publication is an outcome, never proof of a candidate identity.
    counts = collections.Counter()
    for pair in pair_map.values():
        transaction = transactions[pair['segment']][pair['q']]
        actual = transaction['actual_published_mapping']
        native = pair['current_native']
        partner = pair['partner_native']
        partner_public = pair['partner_public']
        public = actual[str(native)]

        def anchored(native, public):
            return transaction['bank_anchors'].get(str(public)) == dict(
                frame=pair['q'], native_id=native, mask=f'n:{native}', canonical_id=public)

        pair.update(
            actual_published_mapping_at_q={str(native): public, str(partner): actual[str(partner)]},
            current_actual_public=public, partner_actual_public=actual[str(partner)],
            actual_current_bank_anchor_at_q=transaction['bank_anchors'].get(str(public)),
            actual_partner_bank_anchor_at_q=transaction['bank_anchors'].get(str(partner_public)),
            current_source_is_actual_q_bank_anchor=anchored(native, public),
            partner_source_is_actual_q_bank_anchor=anchored(partner, partner_public),
            post_geometry_and_quality_gate_passed=True,
            post_observation_class='GEOMETRY_QUALIFIED_ACTUAL_SOURCE_MASK; CANDIDATE_IDENTITY_UNCERTIFIED',
            candidate_mapping_is_hypothesis=True,
            original_transaction_sha256=digest(transaction))
        assert actual[str(partner)] == partner_public
        for _ in pair['reference_ids']:
            counts['current_matches_candidate_public' if public == pair['target_public'] else 'current_does_not_match_candidate_public'] += 1
            counts['current_actual_q_anchor' if anchored(native, public) else 'current_not_actual_q_anchor'] += 1
            counts['partner_actual_q_anchor' if anchored(partner, partner_public) else 'partner_not_actual_q_anchor'] += 1

    pre_role_checks = []
    for context in context_map.values():
        key = context['key']
        name = key['segment']
        anchor = key['anchor']
        target_native = anchor['native_id']
        target_public = anchor['canonical_id']
        partner_native = key['partner_native']
        partner_public = key['partner_public']
        checks = []
        for frame in key['pre_frames']:
            transaction = transactions[name][frame]
            for role, native, public in [('A', target_native, target_public), ('B', partner_native, partner_public)]:
                expected = dict(frame=frame, native_id=native, mask=f'n:{native}', canonical_id=public)
                assert transaction['bank_anchors'].get(str(public)) == expected
                assert transaction['actual_published_mapping'].get(str(native)) == public
                checks.append(dict(
                    frame=frame, global_frame=transaction['global_frame'], time=transaction['time'],
                    role=role, native=native, public=public, actual_bank_anchor=expected,
                    actual_publication_matches=True, transaction_sha256=digest(transaction),
                    class_at_pre='CLEAN_ACTUAL_BANK_ANCHOR'))
        context['pre_source_checks'] = checks
        pre_role_checks.extend(checks)
        pairs = [pair_map[pair_id] for pair_id in context['logical_pair_ids']]
        context.update(
            first_pre_frame=key['pre_frames'][0], last_pre_frame=key['pre_frames'][-1],
            first_query=min(pair['q'] for pair in pairs), last_query=max(pair['q'] for pair in pairs),
            current_natives=sorted({pair['current_native'] for pair in pairs}),
            logical_pair_count=len(pairs), reference_count=len(context['reference_ids']))

    failure_path = DS25 / 'FAILURE_REVIEW.json'
    failure_review = json.loads(failure_path.read_text())
    sources.append(artifact(failure_path))
    assert len(entries) == 540 and len(context_map) == 15 and len(pair_map) == 532
    original_records = collections.Counter((
        record['segment'], record['query_frame'], record['origin_rule'], record['native_id'],
        record['public_id'], record['partner_native'], record['partner_public'],
        record['first_pre_fact'], record['last_pre_fact'], record['seed_fact'], record['current_fact'])
        for record in failure_review['sequence_reference_records'])
    this_records = collections.Counter((
        name, row['frame'], check['origin_rule'], check['native_id'], check['public_id'],
        comparison['partner_native'], comparison['partner_public'],
        comparison['pre_pairs'][0]['fact_id'], comparison['pre_pairs'][-1]['fact_id'],
        next(node['fact_id'] for node in comparison['anonymous_contact'] if node['contact_seed']),
        comparison['current_pair']['fact_id'])
        for name, row, check, comparison, *_ in entries)
    assert original_records == this_records
    fact_sequences = collections.defaultdict(set)
    for name, row, check, comparison, context_id, pair_id, reference_id in entries:
        sequence = tuple(node['fact_id'] for node in [*comparison['pre_pairs'], *comparison['anonymous_contact'], comparison['current_pair']])
        fact_sequences[(name, sequence)].add(pair_id)
    assert len(fact_sequences) == 378
    now = created_utc or datetime.datetime.now(datetime.timezone.utc).isoformat()
    selection = dict(
        source='ALL DS25 SEALED ORDER_CHECKS comparisons containing pre_pairs; no measurement status/GT/metric filters',
        reference_occurrences=540, logical_role_and_version_pairs=532,
        anchor_partner_seed_contexts=15, distinct_whole_measurement_fact_sequences=378,
        all_eight_source_segments_preserved=True,
        zero_context_segments=[name for name in seals if not any(context['key']['segment'] == name for context in context_map.values())],
        independent_biological_events=False, all_q_frames_frozen_from_DS25=True)
    cohort = dict(
        schema='DS26_FIXED_DS25_ROLE_VERSION_COHORT_V1', created_utc=now, base_commit=BASE_COMMIT,
        selection=selection,
        contexts=sorted(context_map.values(), key=lambda context: (context['key']['segment'], context['first_query'], context['context_id'])),
        logical_pairs=sorted(pair_map.values(), key=lambda pair: (pair['segment'], pair['q'], pair['current_native'], pair['target_public'], pair['partner_native'])),
        references=references, source_artifacts=sources,
        identity_boundary='Pre role cleanliness is certified only at each actual pre bank source. Post is an actual geometrically qualified observation; no pre-to-post identity is certified. Candidate target is usually not actual publication. No risk observations are relabeled.',
        new_model_http=0, cost_usd=0)
    review = dict(
        status='PASS_FIXED_COHORT_AND_SOURCE_ROLE_REVIEW', created_utc=now,
        GT_read=False, metrics_read=False, pixels_read=False, API_read=False, server_access=False,
        new_model_http=0, cost_usd=0, selection=selection, actual_reference_counts=dict(counts),
        actual_pre_role_checks=len(pre_role_checks), actual_pre_synchronous_times=len(pre_role_checks) // 2,
        all_pre_roles_match_actual_exact_bank=True,
        reference_multiset_equals_DS25_failure_review=True,
        all_measurement_citations_match_sealed_facts=True, all_source_logs_match_prediction_seals=True,
        whole_fact_sequence_role_multiplicities={str(key): value for key, value in sorted(collections.Counter(len(value) for value in fact_sequences.values()).items())},
        logical_reference_multiplicities={str(key): value for key, value in sorted(collections.Counter(len(pair['reference_ids']) for pair in pair_map.values()).items())},
        origins=dict(collections.Counter(entry[2]['origin_rule'] for entry in entries)),
        deduplication=dict(
            context_key='segment + exact bank anchor + target anchor version + partner native/public/version + unchanged complete pre frames/fact IDs + seed frame/binding/fact',
            logical_pair_key='context_id + q + current native + candidate target public + exact anchor + target version + partner native/public/pre version/current claim version; origin preserved as references, never discarded',
            measurement_cache_key='actual frame + exact actual mask/ROI source hash and raw binding; facts may be reused, semantic candidate roles may not',
            old_378_count_is_not_independent_candidate_pairs=True),
        post_role_warning='538/540 references have current actual public unequal to candidate target. 204/540 current-source and 540/540 partner references are not q-frame actual bank anchors despite geometry/quality checks. Do not require post actual bank clean, silently drop them, or promote them to old-identity clean histories.',
        cohort_digest=digest(cohort), source_artifacts=sources)
    for path, data in zip(outputs, [cohort, review]):
        with path.open('x', encoding='utf8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    return dict(status=review['status'], files=[artifact(path) for path in outputs], selection=selection, counts=dict(counts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=pathlib.Path, required=True, help='Fresh directory; existing cohort files cause failure')
    parser.add_argument('--created-utc', help='Optional original cohort created_utc for exact reconstruction')
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir, args.created_utc), indent=2))
