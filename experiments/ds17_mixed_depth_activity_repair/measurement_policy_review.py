"""Postseal source/measurement-policy review; no GT pixels or new predictions."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / 'run'
PRIVATE = ROOT / 'experiments/ds14_raw_multidataset/private'
FIELDS = ('area', 'n', 'valid_fraction', 'median', 'mad')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        yield from map(json.loads, handle)


def artifact(path):
    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=digest)


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        if isinstance(value, str):
            handle.write(value)
        else:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')


def legacy_usable(stats, core=False):
    good = (stats['median'] is not None and stats['median'] > 0 and
            stats['n'] >= 16 and stats['valid_fraction'] >= .2)
    return good and (not core or max(15., 1.4826 * stats['mad']) <= 60.)


def measure_review(name):
    public, source = RUN / name / 'public', PRIVATE / name
    seal = read(public / 'PREDICTIONS_SEALED.json')
    bindings = {}
    for filename in ('MIXED_DEPTH.jsonl.gz', 'TRANSACTIONS.jsonl.gz', 'ORDER_EVIDENCE.jsonl.gz'):
        bindings[filename] = artifact(public / filename)
        assert bindings[filename]['sha256'] == seal['artifacts_sha256'][filename]
    manifest = read(source / 'SOURCE_MANIFEST.json')
    for value in manifest['derived_inputs'].values():
        assert artifact(Path(value['path'])) == value
    count, lw_case = Counter(), None
    streams = (rows(source / 'profiles.jsonl.gz'), rows(source / 'DEPTH_OBSERVATIONS.jsonl.gz'),
               rows(public / 'MIXED_DEPTH.jsonl.gz'))
    for profiles, raw, packet in zip(*streams, strict=True):
        assert (profiles['frame'], profiles['global_frame'], profiles['time']) == (
            raw['frame'], raw['global_frame'], raw['time']) == (
            packet['frame'], packet['global_frame'], packet['time'])
        count['frames'] += 1
        frame_core_mismatch = False
        for profile in profiles['observations']:
            native = str(profile['id'])
            certificate = packet['objects'][native]
            measured = raw['adaptive_raw'][native]
            count['objects'] += 1
            for part in ('whole', 'core'):
                representation = certificate[part]
                # Frozen producer/runner checks bind this population to adaptive_raw.
                assert all(representation['inclusive_summary'][key] == measured[part][key] for key in FIELDS)
                count[part + '_adaptive_scalar_population_matches'] += 1
                different = [key for key in FIELDS if profile[part][key] != measured[part][key]]
                if different:
                    count[part + '_legacy_profile_statistics_mismatched'] += 1
                    for key in different:
                        count[part + '_legacy_profile_different_' + key] += 1
                    frame_core_mismatch |= part == 'core'
                count[part + '_status_' + representation['status']] += 1
                count[part + '_reason_' + representation['reason']] += 1
                count[part + '_mixture_flag'] += representation['mixture_flag']
                count[part + '_source_quality_fail'] += not representation['quality_usable']
                count[part + '_source_ownership_fail'] += not representation['source_ownership_exclusive']
                count[part + '_both_mix_quality_fail'] += representation['mixture_flag'] and not representation['quality_usable']
                if legacy_usable(measured[part], part == 'core'):
                    count[part + '_raw_legacy_usable'] += 1
                    if not representation['eligible_single']:
                        count[part + '_raw_legacy_usable_guarded_out'] += 1
                        count[part + '_guarded_out_reason_' + representation['reason']] += 1
            w, c = certificate['whole'], certificate['core']
            count[f'whole_core_eligible_{int(w["eligible_single"])}{int(c["eligible_single"])}'] += 1
            if legacy_usable(profile['core'], True):
                count['birth_profile_core_legacy_usable'] += 1
                count['birth_profile_core_legacy_usable_guarded_out'] += not c['eligible_single']
                if not w['eligible_single'] and c['eligible_single']:
                    count['birth_profile_core_usable_and_whole_guarded_out'] += 1
            if name == 'LW' and packet['frame'] == 3064 and profile['id'] == 133:
                lw_case = dict(frame=3064, global_frame=3063, native=133,
                    actual_legacy_birth_profile=profile,
                    adaptive_raw_measurement=measured,
                    representations={part: {key: certificate[part][key] for key in (
                        'status', 'reason', 'eligible_single', 'mixture_flag', 'quality_usable',
                        'source_ownership_exclusive', 'inclusive_summary', 'summary',
                        'scalar_population_difference', 'separated_layer_pairs')}
                        for part in ('whole', 'core')})
        count['legacy_core_statistics_mismatched_frames'] += frame_core_mismatch
    commits, checks = defaultdict(dict), defaultdict(Counter)
    lw_transactions = {}
    for record in rows(public / 'TRANSACTIONS.jsonl.gz'):
        arm, trace = record['arm'], record['controller_trace']
        for action in record.get('durable_automatic_commits', []):
            event = action['event']
            origin = event.get('origin_rule') or ('BIRTH_REFINE' if event.get('phase') == 'birth' else 'D1_DELAYED')
            key = (record['frame'], event['native_id'], event['canonical_id'], origin)
            commits[arm][key] = dict(global_frame=record['global_frame'], event=event)
        for edge in trace.get('birth_checks', []):
            if edge.get('core') is not None:
                checks[arm]['core_comparison_present'] += 1
                checks[arm]['core_present_whole_missing'] += edge.get('whole') is None
            checks[arm]['current_core_unavailable'] += 'current_core_unavailable' in edge.get('failures', [])
            checks[arm]['whole_veto_failure'] += any('whole' in f for f in edge.get('failures', []))
        if name == 'LW' and record['frame'] == 3064:
            lw_transactions[arm] = dict(actual_mapping=record['actual_published_mapping'],
                current_native133_birth_edges=[edge for edge in trace.get('birth_checks', []) if edge.get('native_id') == 133],
                durable_commits=record.get('durable_automatic_commits', []))
    ordinal = defaultdict(Counter)
    for record in rows(public / 'ORDER_EVIDENCE.jsonl.gz'):
        arm, detail = record['arm'], record['detail']
        evidence = detail['order_evidence']
        ordinal[arm]['events'] += 1
        ordinal[arm]['eligible'] += evidence['eligible']
        ordinal[arm][evidence['reason']] += 1
        ordinal[arm]['accepted'] += detail['accepted']
        if not evidence['eligible']:
            assert record['selected_choice'] == 'H0'
            assert all(c['order_log_lr'] == 0 for c in detail['candidates'].values())
            ordinal[arm]['unknown_all_candidates_exact_neutral_and_H0'] += 1
    new_births = []
    for arm in ('MIXED_ORDER', 'MIXED_OFF'):
        for key, value in commits[arm].items():
            if key[3] == 'BIRTH_REFINE' and key not in commits['ACTIVITY_ORDER']:
                new_births.append(dict(arm=arm, frame=key[0], native=key[1], target=key[2], **value))
    if lw_case:
        lw_case['actual_branch_transactions'] = lw_transactions
        lw_case['attribution'] = ('Current whole is guarded because eight shared sources, not mixture or deficient coverage. '
            'Core is admitted using adaptive ROI107 points, while actual Birth scores legacy ROI50 points. '
            'MIXED_ORDER/OFF commit133->107; ACTIVITY commits133->120. ACTIVITY lacks same133->107 edge because '
            'past own-branch aliases/banks differ. No same-state causal proof that a deleted whole veto caused the new commit.')
    return dict(counts=dict(count), ordinal=dict(ordinal), birth_checks=dict(checks),
        durable_automatic_commits={arm: dict(Counter(key[3] for key in values)) for arm, values in commits.items()},
        newly_observed_mixed_births_relative_to_activity=new_births, LW_F3064_native133=lw_case,
        sealed_log_bindings=bindings, source_manifest=artifact(source / 'SOURCE_MANIFEST.json'))


def main():
    provenance = read(RUN / 'SCORE_PROVENANCE.json')
    assert provenance['scientific_source_and_runtime_verified'] and provenance['reference_opened_after_all_seals']
    assert not provenance['GT_used_for_predictions']
    names = read(HERE / 'STRATEGY.json')['arms']  # Guard against accidentally using explanatory CONFIG arm names.
    assert names == read(RUN / 'ALL_PREDICTIONS_SEALED.json')['arms']
    segments = {p.name: measure_review(p.name) for p in sorted(RUN.iterdir()) if p.is_dir()}
    total = Counter()
    for row in segments.values():
        total.update(row['counts'])
    assert total['frames'] == 20098 and total['objects'] == 181842
    review = dict(status='POSTSCORE_READ_ONLY_MEASUREMENT_POLICY_REVIEW',
        created_utc=datetime.now(timezone.utc).isoformat(), new_model_http=0, new_predictions=0,
        new_GT_pixels_read=0, scientific_files_modified=False, score_provenance=artifact(RUN / 'SCORE_PROVENANCE.json'),
        actual_birth_core_certification='FAIL_SAME_ROI_CONTRACT; PARTIAL_SCREEN_ONLY',
        adaptive_order_core_certification='PASS_SOURCE_AND_SAME_POPULATION_BINDING; PHYSICAL_SINGLE_FISH_UNKNOWN',
        whole_population_contract='PASS_NUMERIC_POPULATION_MATCH',
        no_unknown_candidate_advantage_claim='NOT_ESTABLISHED_FOR_OPTIONAL_BIRTH_WHOLE_VETO',
        mechanisms={
            'D1_DELAYED': 'Whole unavailable rejects query before all old-target edges; dummy remains. No zero-cost old edge. Clean bank/depth/motion/area/anchor updates also stop, activity continues.',
            'BIRTH_REFINE': 'Current/target/survivor core required; missing core rejects. Whole optional: whole_veto(None)->None can remove explicit target/competitor contradiction. Missing whole adds no lower core cost but may remove an admissibility veto.',
            'S0': 'Any invalid paired pre/post raw core sets exact ordinal logLR0 for every candidate and H0 for both ORDER/OFF. Whole is not scored. Eligible weak order still uses frozen positive-sign and odds9 gates.',
            'ROI_GAP': 'guard_inputs profiles.core admission uses adaptive-core certificate but does not measure legacy fixed3px-eroded profile ROI. guard_raw uses matching adaptive-core actual scalar. This is interface ROI mismatch, not a source swap or broken old seal.',
            'COMPOSITE_GUARD': 'MIXED vs ACTIVITY changes mixture detection, native-source ownership/coverage and scalar-MAD eligibility together. Cannot assign all effect to mixture detection alone.'},
        source_locations={
            'D1_depth_gate': dict(path='experiments/z4q_pairwise_reconnect_repair/source/px_d1.py', line=58),
            'D1_clean_gate': dict(path='experiments/z4q_pairwise_reconnect_repair/source/px_d1.py', line=142),
            'Birth_optional_whole': dict(path='experiments/z4q_pairwise_reconnect_repair/source/px_z2.py', line=36, expression='if target is None:return None'),
            'Birth_current_core_required': dict(path='experiments/z4q_pairwise_reconnect_repair/source/px_z2.py', line=51),
            'Birth_cost_core_only': dict(path='experiments/z4q_pairwise_reconnect_repair/source/px_z2.py', line=113),
            'guard_profile_roi': dict(path='experiments/ds17_mixed_depth_activity_repair/mixed_depth.py', line=336),
            'runner_asserts_adaptive_not_profiles': dict(path='experiments/ds17_mixed_depth_activity_repair/runner.py', line=139),
            'S0_unknown_H0': dict(path='experiments/ds16_relative_depth_order/order_association.py', line=223)},
        totals=dict(total), segments=segments)
    write_new(HERE / 'MEASUREMENT_POLICY_REVIEW.json', review)
    t = total
    table = '\n'.join('| ' + name + ' | ' + ' | '.join(str(r['counts'].get(k, 0)) for k in (
        'objects', 'whole_status_POTENTIAL_MIXTURE', 'whole_status_UNKNOWN',
        'core_status_POTENTIAL_MIXTURE', 'core_status_UNKNOWN',
        'core_legacy_profile_statistics_mismatched')) + ' |' for name, r in segments.items())
    text = f'''# DS17测量与缺测政策复盘

本文件在全部预测封存和统一评分来源记录完成后生成；只读原始测量缓存、封存公开日志与来源摘要。没有新GT像素、预测、参数或API调用。

## 主判定

**实际Birth core的同ROI认证合同FAIL；本轮仍交付真实完整成绩，不能把工程运行通过写成所有关联测量认证通过。** 全部{t['frames']}帧、{t['objects']}对象观测中，旧profile core与adaptive证书core的area/n/fraction/median/MAD至少一项不同{t['core_legacy_profile_statistics_mismatched']}次，覆盖全部{t['legacy_core_statistics_mismatched_frames']}帧；area不同{t['core_legacy_profile_different_area']}次。whole统计全相同。两种core来自同帧、同原始深度和mask，但旧core固定3像素侵蚀，证书core采用精确L2自适应区域。相对次序的guard_raw与adaptive_raw人口一致；guard_inputs对Birth旧core只是另一ROI的筛选，不能完整认证实际被评分的core。统计相同也不构成像素集合相同的证明。

## 混合与来源质量分列

| 片段 | 观测 | whole潜在混合 | whole UNKNOWN | core潜在混合 | core UNKNOWN | 旧core统计不同 |
|---|---:|---:|---:|---:|---:|---:|
{table}

whole潜在混合{t['whole_status_POTENTIAL_MIXTURE']}，UNKNOWN{t['whole_status_UNKNOWN']}；core潜在混合{t['core_status_POTENTIAL_MIXTURE']}，UNKNOWN{t['core_status_UNKNOWN']}。这是测量筛选覆盖，不是两鱼检测准确率。whole来源ownership不合格{t['whole_source_ownership_fail']}次、独立覆盖/宽尺度质量不合格{t['whole_source_quality_fail']}次，两者可与混合重叠。mixed先判混合，故reason互斥计数与各flag非互斥计数必须区分。

原D1 whole门槛可用{t['whole_raw_legacy_usable']}次中新增拒绝{t['whole_raw_legacy_usable_guarded_out']}次；其中混合{t['whole_guarded_out_reason_SUBSTANTIAL_MEASURED_LAYERS_HAVE_NOISE_SEPARATED_MEDIANS']}，shared/unverified来源{t['whole_guarded_out_reason_ORIGINAL_SCALAR_INCLUDES_SHARED_OR_UNVERIFIED_NATIVE_SOURCES']}。原adaptive core可用{t['core_raw_legacy_usable']}次中新增拒绝{t['core_raw_legacy_usable_guarded_out']}次。whole不合格而adaptive core合格{t['whole_core_eligible_01']}次，逆向{t['whole_core_eligible_10']}次。因此Mixed相对ACTIVITY是混合、来源、覆盖和MAD筛选的组合效果，不能单独归因混合检测。

## 三条路径的缺测语义

- **D1_DELAYED**：whole缺测使query不能进入任何旧ID边，dummy保留，没有某条旧ID边零代价获利。whole缺测还阻断clean_time、运动、面积、anchor、depth_history更新；真实last_seen/contact活动仍继续。这会改变后续候选历史、回接时刻与版本，不只是当前帧删一个depth项。
- **BIRTH_REFINE**：当前、目标及局部幸存者core为必要证据，缺core拒绝。whole为可选反证；`px_z2.py:36`的`if target is None:return None`使缺whole没有explicit target/competitor veto。代价仍来自core，但可失去否决条件。原PLAN的UNKNOWN不得令候选获利预期在此没有得到一般保证，需要公开这一偏离。
- **S0相对次序**：任一pre/post paired core不合格时，全候选ordinal logLR严格0且H0；MIXED_OFF也要求同样paired eligibility。whole不进入次序因子。弱次序保留冻结公式、odds9和正支持准入，不得把H0回退算成物理正确。

## 真实LW案例与有限归因

local F3064/global3063，native133的whole共有278有效pixel，其中8个source与其他mask共享；独立270点、覆盖0.909、无分离显著层，因此拒绝原因为source ownership，而非混合或低覆盖。adaptive core107点、median783.68994/MAD10.01031被认证；Birth实际使用旧core50点、median781.48065/MAD9.18744。MIXED_ORDER和MIXED_OFF都真实提交133→107；ACTIVITY同帧133→120。ACTIVITY当时没有同133→107边，分支既有bank/alias已分化，故只能记录**whole缺失条件下确有新增Birth提交**，不能证明某条同状态whole veto被删除导致此提交。此例不是ordinal独有收益，也不凭全段指标给它物理正确标签。

本轮预测、科学配置、原seal均保持只读。优先下一步是把身份活动与测量质量接口拆开，并为实际Birth ROI提供同ROI来源证书；不在本冻结版本追加搜索或重评分。
'''
    write_new(HERE / 'MEASUREMENT_POLICY_REVIEW.md', text)
    print(json.dumps(dict(status=review['status'], totals=dict(total)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
