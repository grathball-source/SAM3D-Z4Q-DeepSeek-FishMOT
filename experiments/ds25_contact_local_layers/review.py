"""Postseal source, numeric and public-count audit; no pixels, GT or state writes."""
from common import *
from collections import Counter
from itertools import islice
import math

CFG = read(HERE/'CONFIG.json')


def close(a, b):
    assert a is not None and b is not None and math.isfinite(a) and math.isfinite(b)
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-10), (a, b)


def binding(value, n=None):
    assert len(value['sha256']) == 64 and all(c in '0123456789abcdef' for c in value['sha256'])
    if n is not None: assert value['shape'] == [n]


def stats(value, floor):
    assert value['n'] >= 0 and value['area'] >= 0
    close(value['valid_fraction'], value['n']/max(1, value['area']))
    if value['n']:
        close(value['scale_mm'], max(floor, 1.4826*value['mad']))
        assert value['minimum_mm'] <= value['median'] <= value['maximum_mm']
        assert value['mad'] >= 0
    else:
        assert value['median'] is None and value['scale_mm'] is None


def audit_measurement(fact, name):
    unsigned = dict(fact); claimed = unsigned.pop('measurement_sha256')
    assert digest(unsigned) == claimed
    assert fact['segment'] == name and fact['frame'] >= 1
    assert fact['global_frame'] == SEGMENTS[name][0]+fact['frame']-1
    assert fact['identity'] == fact['foreground_identity'] == fact['physical_fish_count'] == 'UNKNOWN'
    assert fact['no_peak_selection'] and fact['no_hole_filling'] and fact['no_history_input_or_state_write']
    assert not any(k in fact for k in ('roles', 'A', 'B'))
    parameters = fact['parameters']; area = fact['original_roi_area']; floor = parameters['scale_floor_mm']
    assert (parameters['minimum_layer_n'], parameters['minimum_layer_fraction'], floor,
        parameters['max_scale_mm'], parameters['layer_gap_mm'], parameters['irls_steps']) == (16, .2, 15., 60., 30., 5)
    assert fact['fact_id'] == f"{name}/F{fact['frame']}/contact_roi:{digest(fact['roi_binding'])}/raw"
    binding(fact['roi_binding']); binding(fact['original_masks_union_binding'])
    for value in fact['original_mask_bindings'].values(): binding(value)
    source = fact['source_binding']
    assert source['global_frame'] == fact['global_frame'] and source['time'] == fact['time']
    assert not any(source.get(k, False) for k in ('GT_read', 'RGB_read', 'restored_read'))
    for outer, inner in (('actual_depth_binding','aligned_depth'),
                         ('actual_source_index_binding','aligned_source_index'),
                         ('native_depth_binding','native_depth')):
        assert fact[outer] == source[inner]; binding(fact[outer])
    for key in ('summary', 'inclusive_summary'): stats(fact[key], floor)
    assert fact['summary']['area'] == fact['inclusive_summary']['area'] == area
    stats(fact['background']['summary'], floor)
    plane = fact['plane']
    if plane is not None:
        stats(plane['residual_summary'], floor)
        close(plane['residual_scale_mm'], plane['residual_summary']['scale_mm'])
        close(plane['contrast_threshold_mm'], max(parameters['background_contrast_floor_mm'],
            parameters['background_sigma_factor']*plane['residual_scale_mm']))
        assert plane['design_rank'] == 3 and plane['condition'] <= parameters['background_max_condition']
        assert plane['sample_n'] == fact['background']['summary']['n']
    measured = []; missing_n = 0
    for layer in fact['layers']:
        assert layer['physical_surface_identity'] == layer['fish_count'] == 'UNKNOWN'
        binding(layer['geometric_component_binding'])
        for population, n in (('population_binding', layer['independent_n']),
                              ('inclusive_population_binding', layer['inclusive_n'])):
            for value in layer[population].values(): binding(value, n)
        close(layer['support_fraction_of_original_roi'], layer['independent_n']/max(1, area))
        close(layer['inclusive_fraction_of_original_roi'], layer['inclusive_n']/max(1, area))
        if layer['kind'] == 'MISSING_DEPTH':
            assert layer['independent_n'] == 0 and not layer['qualified'] and not layer['inclusive_qualified']
            assert layer['z_mm'] is None and layer['sigma_mm'] is None
            missing_n += layer['inclusive_n']; continue
        assert layer['kind'] == 'MEASURED_DEPTH_SUPPORT'; measured.append(layer)
        for prefix, n, summary in (('', layer['independent_n'], layer['independent_summary']),
                                  ('inclusive_', layer['inclusive_n'], layer['inclusive_summary'])):
            stats(summary, floor); assert summary['n'] == n and summary['area'] == area
            substantial = n >= parameters['minimum_layer_n'] and n/max(1, area) >= parameters['minimum_layer_fraction']
            assert layer[prefix+'substantial'] == substantial
            if plane is None:
                assert not layer[prefix+'qualified'] and layer[prefix+'sigma_mm'] is None
                assert layer[prefix+'background_compatibility'] == 'UNKNOWN'; continue
            prediction = layer[prefix+'prediction_uncertainty_mm']; assert prediction['n'] == n
            residual = layer[prefix+'residual_summary']; stats(residual, floor)
            assert residual['n'] == n; contrast = residual['median']
            assert layer[prefix+'median_residual_mm'] == contrast
            compatible = ('UNKNOWN' if contrast is None else 'BACKGROUND_COMPATIBLE'
                if abs(contrast) <= plane['contrast_threshold_mm'] else 'DIFFERENT_FROM_LOCAL_ANNULUS_PROXY')
            assert layer[prefix+'background_compatibility'] == compatible
            combined = None if summary['scale_mm'] is None else math.sqrt(summary['scale_mm']**2 +
                plane['residual_scale_mm']**2 + prediction['q90']**2)
            if combined is None: assert layer[prefix+'sigma_mm'] is None
            else: close(layer[prefix+'sigma_mm'], combined)
            qualified = bool(substantial and plane['residual_scale_mm'] <= parameters['max_scale_mm'] and
                combined is not None and combined <= parameters['max_scale_mm'] and
                compatible == 'DIFFERENT_FROM_LOCAL_ANNULUS_PROXY')
            assert layer[prefix+'qualified'] == qualified
        assert layer['z_mm'] == layer['independent_summary']['median']
    assert sum(x['independent_n'] for x in measured) == fact['summary']['n']
    assert sum(x['inclusive_n'] for x in measured) == fact['inclusive_summary']['n']
    assert missing_n == fact['original_roi_missing_n']
    assert fact['inclusive_summary']['n']+missing_n == area
    qualified = [x for x in measured if x['qualified']]
    if 'inclusive_independent_partition_agreement' in fact:
        first, second = fact['independent_depth_groups'], fact['inclusive_depth_groups']
        partition = len(first) == len(second) and all(a['minimum_mm'] >= b['minimum_mm'] and
            a['maximum_mm'] <= b['maximum_mm'] for a,b in zip(first,second))
        flags = all(x['qualified'] == x['inclusive_qualified'] and x['substantial'] == x['inclusive_substantial']
            and x['background_compatibility'] == x['inclusive_background_compatibility'] for x in measured)
        assert fact['inclusive_independent_partition_agreement'] == partition
        assert fact['inclusive_independent_support_agreement'] == flags
        assert fact['qualified_support_ids'] == [x['support_id'] for x in qualified]
        unresolved = [x['support_id'] for x in measured if (x['substantial'] or x['inclusive_substantial']) and
            not x['qualified'] and (x['background_compatibility'] != 'BACKGROUND_COMPATIBLE' or
                x['sigma_mm'] is None or x['sigma_mm'] > parameters['max_scale_mm'] or
                x['inclusive_sigma_mm'] is None or x['inclusive_sigma_mm'] > parameters['max_scale_mm'])]
        assert fact['substantial_unresolved_support_ids'] == unresolved
        available = (partition and flags and not unresolved and len(qualified) == 2 and
            qualified[0]['depth_gap_group'] != qualified[1]['depth_gap_group'])
        assert (fact['status'] == 'AVAILABLE_TWO_LAYERS') == available
    else:
        assert fact['status'] == 'UNKNOWN' and not fact['qualified_support_ids']
    return len(qualified)


def summary(fact, seed=False):
    return dict(frame=fact['frame'], time=fact['time'], fact_id=fact['fact_id'],
        measurement_sha256=digest(fact), status=fact['status'], reason=fact['reason'],
        contact_seed=seed, layer_count=len(fact['layers']),
        qualified_layers=[{key:layer[key] for key in ('support_id','z_mm','sigma_mm','independent_n')}
            for layer in fact['layers'] if layer['qualified']])


def audit_association(value, facts, query, anchor):
    """Recompute public endpoint/transition count arithmetic and ordered paths."""
    if 'pre_pairs' not in value:
        if value['reason'] == 'NO_ACTUAL_GEOMETRY_CONTACT_SEED':
            frames = value['evaluated_pre_frames']; assert frames[-1] == anchor
            assert all(b == a+1 for a,b in zip(frames,frames[1:]))
            assert value['anonymous_interval_frames'] == list(range(anchor+1,query['frame']))
            assert value['source_query_cutoff'] == query['frame']
        return 0
    pre, contact, post = value['pre_pairs'], value['anonymous_contact'], value['current_pair']
    packets = pre+contact+[post]
    assert pre[-1]['frame'] == anchor and post['frame'] == query['frame'] and post['time'] == query['time']
    assert len(pre) >= CFG['minimum_pre_pairs']
    assert [x['frame'] for x in contact] == list(range(anchor+1,query['frame']))
    assert all(b['frame'] == a['frame']+1 and b['time'] > a['time'] for a,b in zip(packets,packets[1:]))
    assert value['source_query_cutoff'] == query['frame']
    seed = value['actual_contact_seed_frame']; assert anchor < seed < query['frame']
    assert [x['frame'] for x in contact if x['contact_seed']] == [seed]
    assert all(not any(k in x for k in ('roles','A','B')) for x in contact)
    assert value['mapping_is_hypothesis'] and value['no_identity_history_or_bank_write']
    assert not value['cross_frame_source_index_matching'] and not value['elapsed_depth_extrapolation']
    layers = {}
    for packet in packets:
        fact = facts[packet['fact_id']]
        assert packet == summary(fact, packet['contact_seed'])
        assert fact['frame'] <= query['frame'] and fact['time'] <= query['time']
        layers[fact['fact_id']] = {x['support_id']:x for x in fact['layers'] if x['qualified']}
    owners = {}
    for entry in value['ownership_counts']:
        fact = facts[entry['fact_id']]; assert entry['measurement_sha256'] == digest(fact)
        assert entry['frame'] == fact['frame'] and entry['frame'] in [x['frame'] for x in pre]+[query['frame']]
        nodes = layers[entry['fact_id']]; possibilities = []
        for support in entry['supports']:
            n = nodes[support['support_id']]['independent_n']; assert support['independent_n'] == n and n > 0
            for role in ('A','B'):
                count = support['role_counts'][role]; assert 0 <= count <= n
                close(support['role_fractions'][role], count/n)
            allowed = [role for role,other in (('A','B'),('B','A'))
                if support['role_fractions'][role] >= CFG['minimum_endpoint_membership_fraction'] and
                support['role_fractions'][other] <= CFG['maximum_other_role_membership_fraction']]
            assert support['admissible_roles'] == allowed
        first, second = entry['supports']; assert first['support_id'] != second['support_id']
        possibilities = [{first['support_id']:a,second['support_id']:b}
            for a in first['admissible_roles'] for b in second['admissible_roles'] if a != b]
        unique = possibilities[0] if len(possibilities) == 1 else None
        assert entry['unique_bijection'] == unique
        owners[entry['frame']] = unique
    transitions = {}
    for entry in value['spatial_transitions']:
        first, second = facts[entry['from_fact_id']], facts[entry['to_fact_id']]
        assert (entry['from_frame'],entry['to_frame']) == (first['frame'],second['frame'])
        assert second['frame'] == first['frame']+1
        assert entry['from_measurement_sha256'] == digest(first) and entry['to_measurement_sha256'] == digest(second)
        old, new = layers[first['fact_id']], layers[second['fact_id']]
        admitted = {}
        for edge in entry['geometry']:
            a,b = edge['from_support_id'],edge['to_support_id']
            na,nb = old[a]['independent_n'],new[b]['independent_n']
            assert (edge['from_independent_n'],edge['to_independent_n']) == (na,nb)
            assert 0 <= edge['forward_overlap_n'] <= na and 0 <= edge['backward_overlap_n'] <= nb
            close(edge['forward_fraction'], edge['forward_overlap_n']/na)
            close(edge['backward_fraction'], edge['backward_overlap_n']/nb)
            admitted[a,b] = (edge['forward_fraction'] >= CFG['minimum_symmetric_overlap_fraction'] and
                edge['backward_fraction'] >= CFG['minimum_symmetric_overlap_fraction'])
            assert edge['admissible'] == admitted[a,b]
        a,b = sorted(old); c,d = sorted(new)
        assert len(entry['geometry']) == 4 and len(admitted) == 4
        permutations = [mapping for mapping in ({a:c,b:d},{a:d,b:c}) if all(admitted[s,t] for s,t in mapping.items())]
        assert entry['admissible_permutations'] == permutations
        transitions[second['frame']] = permutations
    paths = None; initial = None; low = 1/(1+CFG['minimum_joint_odds']); high = 1-low
    for index, entry in enumerate(value['calculated_order']):
        packet = packets[index]; fact = facts[entry['fact_id']]
        assert entry['fact_id'] == packet['fact_id'] and entry['measurement_sha256'] == digest(fact)
        assert (entry['frame'],entry['time']) == (fact['frame'],fact['time'])
        if paths is None:
            assert owners[fact['frame']] is not None
            paths = {role:sid for sid,role in owners[fact['frame']].items()}
        else:
            options = transitions[fact['frame']]; assert len(options) == 1
            paths = {role:options[0][sid] for role,sid in paths.items()}
        assert (entry['anchored_A_support_id'],entry['anchored_B_support_id']) == (paths['A'],paths['B'])
        if index < len(pre): assert all(owners[fact['frame']][sid] == role for role,sid in paths.items())
        a,b = layers[fact['fact_id']][paths['A']],layers[fact['fact_id']][paths['B']]
        delta = b['z_mm']-a['z_mm']; scale = math.hypot(a['sigma_mm'],b['sigma_mm'])
        u = (delta/scale)/math.hypot(delta/scale,2.)
        probability = max(0.,min(1.,.5+.75*u-.25*u**3))
        close(entry['delta_B_minus_A_mm'],delta); close(entry['scale_mm'],scale)
        close(entry['probability_A_nearer'],probability)
        order = 'A_NEARER' if probability >= high else 'B_NEARER' if probability <= low else None
        assert entry['strong_order'] == order
        if index < len(value['calculated_order'])-1:
            assert order is not None and (initial is None or order == initial)
        if initial is None: initial = order
    if value['status'] in ('CONFLICT','COMPATIBLE'):
        assert len(value['calculated_order']) == len(packets) and len(transitions) == len(packets)-1
        assert all(x['strong_order'] == initial and initial is not None for x in value['calculated_order'])
        ending = {role:owners[query['frame']][sid] for role,sid in paths.items()}
        assert value['anchored_paths_post_geometric_roles'] == ending
        conflict = ending == {'A':'B','B':'A'}
        assert conflict or ending == {'A':'A','B':'B'}
        assert value['veto'] == conflict and value['status'] == ('CONFLICT' if conflict else 'COMPATIBLE')
    else: assert value['status'] == 'UNKNOWN' and not value['veto']
    return len(packets)


def review(output=RUN, segments=None, *, require_seals=True, write_report=True):
    segments = SEGMENTS if segments is None else segments
    manifest = read(output/'ALL_PREDICTIONS_SEALED.json') if require_seals else None
    if require_seals:
        assert output == RUN and segments == SEGMENTS
        assert manifest['frames'] == 20098 and manifest['arms'] == list(ARMS)
    results = {}; total = Counter()
    for name,(start,stop) in segments.items():
        public = output/name/'public'
        if require_seals:
            seal = verify_seal(name); frozen = read(public/'FREEZE.json')
            verify_item(manifest['seals'][name]); verify_item(manifest['access_seals'][name])
        else:
            assert output.parent == HERE and output.name.startswith('slice_') and not write_report
            old_public = ROOT/'experiments/ds20_pending_confirmation_isolation/run'/name/'public'
            frozen = dict(source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),
                original_prediction=artifact(old_public/'predictions.jsonl.gz'),
                original_prediction_seal=artifact(old_public/'PREDICTIONS_SEALED.json'),
                source_chain=read(input_dir(name)/'SOURCE_MANIFEST.json'))
            seal = dict(frames=stop-start+1)
        for key in ('source_manifest','original_prediction','original_prediction_seal'): verify_item(frozen[key])
        if require_seals: verify_item(frozen['runtime'])
        chain = frozen['source_chain']; assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
        for item in chain['derived_inputs'].values(): verify_item(item)
        for key in ('scan','raw_sources','field_access'): verify_item(chain[key])
        oldseal = read(frozen['original_prediction_seal']['path'])
        assert frozen['original_prediction']['sha256'] == oldseal['artifacts_sha256']['predictions.jsonl.gz']
        access = read(public/'SOURCE_ACCESS.json'); guard = read(public/'ACCESS.json')
        assert not access['GT_RGB_restored_future_network'] and access['new_model_http'] == 0
        assert guard['status'] == 'NO_GT_RGB_RESTORED_NETWORK' and guard['new_model_http'] == 0
        for entry in access['actual_reads']:
            assert 1 <= entry['frame'] <= entry['query_cutoff_frame'] <= stop-start+1
            assert entry['global_frame'] == start+entry['frame']-1
        facts = {}; measurement_reasons = Counter(); measurement_statuses = Counter()
        counts = Counter(frames=0,objects=0,changed_frames=0,candidate_checks=0,veto_checks=0,
            partner_comparisons=0,measurement_citations=0,layers=0,qualified_layers=0)
        for fact in rows(public/'MEASUREMENTS.jsonl.gz'):
            assert fact['fact_id'] not in facts; audit_measurement(fact,name)
            facts[fact['fact_id']] = fact; measurement_reasons[fact['reason']] += 1
            measurement_statuses[fact['status']] += 1
            counts['layers'] += len(fact['layers']); counts['qualified_layers'] += sum(x['qualified'] for x in fact['layers'])
        wanted = {fact['frame'] for fact in facts.values()} | {x['frame'] for x in access['actual_reads']}
        inputs = {row['frame']:row for row in rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz') if row['frame'] in wanted}
        for fact in facts.values():
            original = inputs[fact['frame']]
            assert (fact['global_frame'],fact['time']) == (original['global_frame'],original['time'])
            assert fact['source_binding'] == original['raw_source_binding']
        for entry in access['actual_reads']:
            original = inputs[entry['frame']]['raw_source_binding']
            assert entry['source_binding_sha256'] == digest(original)
            assert entry['sensor_pair_delta_us'] == original.get('delta_us')
        reasons = Counter(); partner_reasons = Counter(); statuses = Counter(); eligible = Counter(); stages = Counter()
        transactions = iter(rows(public/'TRANSACTIONS.jsonl.gz'))
        streams = (rows(public/'predictions.jsonl.gz'), rows(public/'ORDER_CHECKS.jsonl.gz'),
            rows(public/'PUBLISH_LEDGER.jsonl'), rows(public/'ANONYMOUS_RISK.jsonl.gz'),
            islice(rows(input_dir(name)/'assignments.jsonl.gz'),stop-start+1),
            islice(rows(frozen['original_prediction']['path']),stop-start+1))
        seen_veto = False
        for frame, packet in enumerate(zip(*streams, strict=True),1):
            prediction, checks, ledger, risk, assignment, archived = packet
            original, actual = next(transactions), next(transactions)
            for item in (prediction,checks,ledger,risk,original,actual):
                assert item['frame'] == frame and item['global_frame'] == start+frame-1
                assert item['time'] == prediction['time']
            assert original['arm'] == 'Z4Q_FROZEN' and actual['arm'] == 'Z4Q_LOCAL_LAYERS'
            assert ledger['prediction_row_sha256'] == row_sha(prediction)
            assert ledger['checks_row_sha256'] == row_sha(checks)
            assert ledger['transaction_row_sha256'] == {'Z4Q_FROZEN':row_sha(original),'Z4Q_LOCAL_LAYERS':row_sha(actual)}
            assert ledger['model_http'] == 0 and ledger['receive_to_first_publish_seconds'] >= 0
            assert actual['controller_trace']['relative_order_checks'] == checks['checks']
            assert risk['no_individual_depth_history_write'] and risk['no_Z4Q_bank_write']
            assert all(x['observation_class'] == 'ANONYMOUS_RISK_OBSERVATION' for x in risk['observations'].values())
            variants = prediction['variants']
            assert variants['SAM3_NATIVE'] == assignment['variants']['N0'] == archived['variants']['SAM3_NATIVE']
            assert variants['Z4Q_FROZEN'] == archived['variants']['Z4Q_FROZEN']
            for arm,tx in (('Z4Q_FROZEN',original),('Z4Q_LOCAL_LAYERS',actual)):
                published = variants[arm]
                assert len(published) == len({x['id'] for x in published}) == len(variants['SAM3_NATIVE'])
                assert [x['mask'] for x in published] == [x['mask'] for x in variants['SAM3_NATIVE']]
                assert {x['mask']:x['id'] for x in published} == {f'n:{n}':k for n,k in tx['actual_published_mapping'].items()}
            counts['frames'] += 1; counts['objects'] += len(variants['SAM3_NATIVE'])
            counts['changed_frames'] += variants['Z4Q_FROZEN'] != variants['Z4Q_LOCAL_LAYERS']
            for check in checks['checks']:
                counts['candidate_checks'] += 1; counts['veto_checks'] += bool(check['veto']); reasons[check['reason']] += 1
                assert check['query_frame'] == frame and check['origin_rule'] in ('D1_DELAYED','BIRTH_REFINE')
                for comparison in check['comparisons']:
                    counts['partner_comparisons'] += 1; partner_reasons[comparison['reason']] += 1
                    statuses[comparison['status']] += 1
                    stages['MEASURED_CHAIN' if 'pre_pairs' in comparison else
                        'NO_CONTACT_SEED_BEFORE_MEASUREMENT' if comparison['reason'] == 'NO_ACTUAL_GEOMETRY_CONTACT_SEED' else 'UPSTREAM_OR_UNAVAILABLE'] += 1
                    counts['measurement_citations'] += audit_association(comparison,facts,checks,check['anchor']['frame'])
                    if 'pre_versions' in comparison:
                        assert comparison['pre_versions']['B'] == comparison['current_partner_claim_version']
                        assert all(check['anchor']['frame'] < x['frame'] < frame for x in comparison['anonymous_risk_interval'])
                reliable = [x for x in check['comparisons'] if x['status'] in ('CONFLICT','COMPATIBLE')]
                veto = bool(reliable and all(x['status'] == 'CONFLICT' for x in reliable))
                if 'target_anchor_version' in check:
                    assert check['veto'] == veto and check['status'] == ('EXCLUDED' if veto else 'KEEP_ORIGINAL')
                    assert check['unknown_partner_count'] == sum(x['status'] == 'UNKNOWN' for x in check['comparisons'])
                else: assert not check['veto']
                edges = actual['controller_trace']['edges' if check['origin_rule'] == 'D1_DELAYED' else 'birth_checks']
                relevant = [x for x in edges if x.get('native_id') == check['native_id'] and x.get('canonical_id') == check['public_id']]
                assert len(relevant) == 1 and relevant[0]['edge_veto'] == check
                edge = relevant[0]
                if check['veto']: assert edge.get('rejection') is not None
                if edge.get('rejection') is None and edge.get('cost') is not None and edge['cost'] < 1: eligible[check['reason']] += 1
            seen_veto = seen_veto or any(x['veto'] for x in checks['checks'])
            if not seen_veto: assert original['engine_state_sha256'] == actual['engine_state_sha256']
        assert next(transactions,None) is None
        summary_record = read(public/'RUN_SUMMARY.json')
        assert counts['frames'] == summary_record['frames'] == seal['frames'] == stop-start+1
        assert counts['candidate_checks'] == summary_record['checks']
        assert counts['veto_checks'] == summary_record['veto_checks'] and counts['changed_frames'] == summary_record['changed_frames']
        assert len(facts) == summary_record['measured_objects'] and dict(measurement_reasons) == summary_record['measurement_reasons']
        total.update(counts); total['measured_objects'] += len(facts)
        results[name] = dict(**counts, measured_objects=len(facts), measurement_reasons=dict(measurement_reasons),
            measurement_statuses=dict(measurement_statuses), evidence_reasons=dict(reasons), partner_reasons=dict(partner_reasons),
            comparison_statuses=dict(statuses), comparison_stages=dict(stages), original_still_eligible_edge_reasons=dict(eligible),
            actual_measurement_citations=counts['measurement_citations'],actual_veto_checks=counts['veto_checks'],
            actual_changed_frames=counts['changed_frames'],actual_source_reads=len(access['actual_reads']), future_source_reads=0)
    assert total['frames'] == sum(stop-start+1 for start,stop in segments.values())
    report = dict(status='PASS',GT_read=False,**total,segments=results,
        measurement_selfdigests_and_fullfact_citations_checked=True,source_and_old_seals_unchanged=True,
        ledger_prediction_transaction_check_joins_checked=True,derived_sigma_qualification_order_math_checked=True,
        public_spatial_count_arithmetic_checked=True,spatial_raster_overlap_recomputed=False,
        public_count_audit_limit='Raster intersections require private masks; this audit verifies sealed producers, bindings and public count arithmetic.',
        formal_predictions_sealed=require_seals,protocol_prefix_only=not require_seals,
        future_source_reads=0,new_model_http=0,cost_usd=0)
    if write_report:
        assert require_seals
        write_new(HERE/'INPUT_REVIEW.json',report)
    print(json.dumps(dict(status='PASS',formal_predictions_sealed=require_seals,**total)),flush=True)
    return report


def audit_prefix(name, output):
    count = read(output/name/'public/RUN_SUMMARY.json')['frames']; start = SEGMENTS[name][0]
    return review(output,{name:(start,start+count-1)},require_seals=False,write_report=False)


if __name__ == '__main__': review()
