"""Source-only DS18 interface audit, with no prediction replay or reference access.

The cases are already identified engineering observations, not a GT selection
rule. Only the named current frames and their actual recorded old anchors are
remeasured. Pixels stay in the existing private datasets; this report contains
scalar measurements, bindings and original-controller facts only.
"""
from __future__ import annotations

import copy
from collections import Counter
import inspect
import sys

import guard  # Install the same no-GT/no-RGB/no-restoration/no-network guards.
from common import *

if str(DS14) not in sys.path:
    sys.path.append(str(DS14))
import source
from mixed_depth import (ROLES, bind_measurement, guard_inputs, guard_raw,
                         measure_mixed, validate_bound_measurement,
                         validate_certificate)

# frame is local, one-based; global_frame remains the original acquisition key.
CASES = {
    'fishsa_development_8400': [(3902, 7)],
    'fishsa_validation_2888': [(2188, 8)],
    'LW': [(3064, 133), (3065, 133)],
    'feeding_000000_000199': [(191, 30)],
    'feeding_001201_001906': [(264, 176)],
}
OLD_ARMS = ('Z4Q_FROZEN', 'ACTIVITY_ORDER', 'MIXED_ORDER')


def selected_rows(path, frames):
    result = {}
    for row in rows(path):
        frame = row['frame']
        if frame in frames:
            result[frame] = row
        if frame >= max(frames):
            break
    assert set(result) == set(frames), (str(path), sorted(frames - result.keys()))
    return result


def anchors(value):
    if isinstance(value, dict):
        if {'frame', 'native_id', 'mask'} <= value.keys():
            yield {key: value[key] for key in ('frame', 'native_id', 'mask', 'canonical_id') if key in value}
        else:
            for child in value.values():
                yield from anchors(child)
    elif isinstance(value, list):
        for child in value:
            yield from anchors(child)


def old_cases(name, requested):
    """Raw sealed controller facts, never postscore physical/GT verdicts."""
    path = DS17 / 'run' / name / 'public/TRANSACTIONS.jsonl.gz'
    frames = {frame for frame, _ in requested}
    native_at = dict(requested)
    cases = {frame: [] for frame in frames}
    for row in rows(path):
        frame = row['frame']
        if frame > max(frames):
            break
        if frame not in frames or row['arm'] not in OLD_ARMS:
            continue
        trace, native = row['controller_trace'], native_at[frame]
        events = [item for item in trace.get('events', []) if item.get('native_id') == native]
        birth = [item for item in trace.get('birth_checks', []) if item.get('native_id') == native]
        cases[frame].append(dict(arm=row['arm'], frame=frame, global_frame=row['global_frame'],
            native=native, actual_published_id=row['actual_published_mapping'].get(str(native)),
            signal=row.get('signal'), restore=row.get('restore'),
            reconnect_events=events, birth_checks=birth,
            reference_policy='RECORDED_RAW_CONTROLLER_ANCHORS; NO_GT_MATCH_USED'))
    assert all(len(value) == len(OLD_ARMS) for value in cases.values())
    needed = set(frames)
    anchor_roles = {}
    for q, records in cases.items():
        for anchor in anchors(records):
            assert anchor['frame'] <= q, (name, q, anchor)
            needed.add(anchor['frame'])
            key = (anchor['frame'], anchor['native_id'])
            anchor_roles.setdefault(key, []).append(dict(q=q, anchor=anchor))
    return cases, needed, anchor_roles, artifact(path)


def scalar_view(certificate, part):
    fact = certificate[part]
    return dict(statistics=fact['inclusive_summary'], roi_definition=fact['roi_definition'],
        roi_binding=fact['roi_binding'], inclusive_population_binding=fact['inclusive_population_binding'],
        independent_statistics=fact['summary'], status=fact['status'], reason=fact['reason'],
        eligible_single=fact['eligible_single'], quality_usable=fact['quality_usable'],
        source_ownership_exclusive=fact['source_ownership_exclusive'],
        potential_layers=fact['mixture_flag'], independent_potential_layers=fact['independent_mixture_flag'],
        inclusive_potential_layers=fact['inclusive_mixture_flag'], fact_id=fact['fact_id'])


def source_audit(name, requested):
    cases, needed, anchor_roles, old_artifact = old_cases(name, requested)
    base = input_dir(name)
    manifest = read(base / 'SOURCE_MANIFEST.json')
    for item in manifest['derived_inputs'].values():
        verify_item(item)
    for key in ('scan', 'raw_sources', 'field_access'):
        verify_item(manifest[key])
    saved = {key: selected_rows(base / filename, needed) for key, filename in (
        ('observations', 'observations.jsonl.gz'), ('profiles', 'profiles.jsonl.gz'),
        ('assignments', 'assignments.jsonl.gz'), ('raw', 'DEPTH_OBSERVATIONS.jsonl.gz'))}
    sensor = source.RawDepth(name)
    frames, populations, tests = {}, Counter(), Counter()
    try:
        for frame in sorted(needed):
            row = saved['observations'][frame]
            profile_row = saved['profiles'][frame]
            assignment = saved['assignments'][frame]
            raw_row = saved['raw'][frame]
            global_frame, now = row['global_frame'], row['time']
            assert global_frame == SEGMENTS[name][0] + frame - 1
            assert profile_row['global_frame'] == assignment['global_frame_id'] == raw_row['global_frame'] == global_frame
            depth, index, native_depth, source_binding = sensor(global_frame, now)
            assert source_binding == raw_row['raw_source_binding'], (name, frame, 'raw source binding')
            masks = source.native_masks(assignment)
            packet = measure_mixed(depth, index, masks, name, frame, global_frame,
                source_binding=source_binding, native_depth=native_depth)
            # The existing Bridge.stream adds the current frame to each profile.
            profiles = {p['id']: dict(p, frame=frame) for p in profile_row['observations']}
            raw = {int(n): value for n, value in raw_row['adaptive_raw'].items()}
            # Both screen states admit the same real statistics and population.
            screened, screened_profiles = guard_inputs(row, profiles, packet['objects'], screen=True)
            kept, kept_profiles = guard_inputs(row, profiles, packet['objects'], screen=False)
            assert all(a['depth'] == b['depth'] for a, b in zip(row['observations'], kept['observations'], strict=True))
            assert all(profiles[n]['core'] == kept_profiles[n]['core'] and
                       profiles[n]['whole'] == kept_profiles[n]['whole'] for n in profiles)
            screened_raw = guard_raw(raw, packet['objects'], screen=True)
            kept_raw = guard_raw(raw, packet['objects'], screen=False)
            assert all(kept_raw[n]['core_usable'] == raw[n]['core_usable'] for n in raw)
            assert all(screened_raw[n]['core'] == raw[n]['core'] and screened_raw[n]['whole'] == raw[n]['whole'] for n in raw)
            objects = {}
            for n, cert in packet['objects'].items():
                assert validate_certificate(cert)
                for part in ('whole', 'birth_core', 'core'):
                    populations[(part, cert[part]['status'])] += 1
                bindings = kept_profiles[n]['measurement_bindings']
                role_stats = {'D1_WHOLE': next(o['depth'] for o in row['observations'] if o['id'] == n),
                              'BIRTH_WHOLE': profiles[n]['whole'], 'BIRTH_CORE': profiles[n]['core'],
                              'S0_ADAPTIVE_CORE': raw[n]['core']}
                for role, stats in role_stats.items():
                    binding = bind_measurement(cert, role, stats)
                    assert validate_bound_measurement(binding, stats, role, cert, native=n, frame=frame)
                    mutated = dict(stats, median=(stats['median'] or 0.) + 1.)
                    assert not validate_bound_measurement(binding, mutated, role, cert, native=n, frame=frame)
                    tests['actual_scalar_mutation_rejected'] += 1
                different = cert['birth_core']['roi_binding'] != cert['core']['roi_binding']
                if profiles[n]['core']['median'] != raw[n]['core']['median'] or profiles[n]['core']['n'] != raw[n]['core']['n']:
                    try:
                        bind_measurement(cert, 'BIRTH_CORE', raw[n]['core'])
                    except AssertionError:
                        tests['adaptive_scalar_cannot_certify_fixed_core'] += 1
                    else:
                        raise AssertionError('Cross-ROI scalar was accepted')
                assert not validate_bound_measurement(bindings['BIRTH_CORE'], profiles[n]['core'],
                    'BIRTH_CORE', cert, native=n + 100000, frame=frame)
                tests['wrong_native_binding_rejected'] += 1
                objects[str(n)] = dict(native=n, mask_binding=cert['mask_binding'],
                    certificate_fact_id=cert['fact_id'], certificate_sha256=cert['certificate_sha256'],
                    fixed_vs_adaptive_roi_differs=different,
                    whole=scalar_view(cert, 'whole'), fixed_birth_core=scalar_view(cert, 'birth_core'),
                    adaptive_s0_core=scalar_view(cert, 'core'),
                    measurement_only_identity_status='UNKNOWN; NOT_MANUALLY_QUALIFIED',
                    used_by_old_anchor=anchor_roles.get((frame, n), []),
                    fixed_birth_binding=bindings['BIRTH_CORE'],
                    actual_screened_whole_available=next(o['depth']['median'] is not None for o in screened['observations'] if o['id'] == n),
                    actual_screened_fixed_core_available=screened_profiles[n]['core']['median'] is not None,
                    actual_screened_adaptive_core_usable=screened_raw[n]['core_usable'])
            frames[str(frame)] = dict(frame=frame, global_frame=global_frame, time=now,
                is_requested_current_frame=frame in cases, actual_raw_source_binding=source_binding,
                saved_native_mask_count=len(masks), all_original_statistics_match_actual_same_ROI=True,
                objects=objects, old_controller_facts=cases.get(frame, []))
    finally:
        sensor.close()
    return dict(source_manifest=artifact(base / 'SOURCE_MANIFEST.json'),
        immutable_derived_inputs=manifest['derived_inputs'], raw_sources_manifest=manifest['raw_sources'],
        raw_controller_trace=old_artifact, requested_cases=[dict(frame=f, native=n) for f, n in requested],
        measured_frames=sorted(needed), frame_results=frames,
        population_status_counts=[dict(representation=p, status=s, count=c) for (p, s), c in sorted(populations.items())],
        mutation_checks=dict(tests), source_read_contract='ACTUAL_CURRENT_AND_RECORDED_OLD_ANCHORS_ONLY_NO_GT_NO_RGB_NO_RESTORED_VALUES')


def code_contract():
    chain = [
        DS17 / 'controller.py', DS16 / 'controller.py', DS15 / 'controller.py',
        NE1 / 'ne_controller.py', S0P / 'manager_p.py', OLD / 'merge_split_manager.py',
        ROOT / 'online/closed_loop_2888/z4q_source/bridge.py',
        *[(ROOT / 'experiments/z4q_pairwise_reconnect_repair/source' / name) for name in
          ('px_return.py', 'px_z4.py', 'px_z3.py', 'px_z2.py', 'px_d1.py')],
        DS16 / 'order_association.py', DS14 / 'source.py',
        WORK / 'tools/depth_restoration/geometry.py',
        WORK / 'tools/depth_restoration/build_aligned_dataset.py',
        WORK / 'tools/sam3_depth_birth_inherit_20260917/features.py',
        DS12 / 'contact_measurement.py', DS17 / 'mixed_depth.py', HERE / 'mixed_depth.py',
    ]
    return dict(runtime_raw_source=artifact(inspect.getfile(source.RawDepth)),
        actual_reused_code=[artifact(path) for path in chain],
        required_missingness={
            'D1_DELAYED': 'Whole is the existing positive measurement; missing current/history whole rejects that automatic edge, retaining dummy and truthful source birth/first_eligible.',
            'BIRTH_REFINE': 'Fixed exclusive 7x7 core positive cost unchanged. Required target/local-survivor/motion-eligible competitor whole is three-state: measured conflict preserves original veto, unknown prevents that candidate commit, qualified retains original cost. Unknown is never a zero-cost edge.',
            'S0': 'Whole NOT_USED_BY_FROZEN_ORDINAL_METHOD. Required same-version pre/current adaptive core pair missing yields common uninformative order evidence and H0, not a candidate-specific advantage.',
        },
        ds17_root_causes=[
            'D1 superclass unconditionally records original first-seen birth. An anonymous first observation still consumes Birth-only opportunity even when its copied whole/core was blanked.',
            'Blanking current scalar is not identity stage isolation: aliases/birth/native_runs are not restored with clean reference fields.',
            'Birth whole_veto(None) supplies no negative evidence, whereas D1 requires whole and S0 uses only adaptive core.',
            'DS17 adaptive-core eligibility certified the legacy fixed-core population; these are demonstrably different real pixel sets.',
        ],
        pending_birth_requirements=[
            'Preserve real source first_seen frame/time and generation/version; no fabricated new birth or first_eligible.',
            'Identity writes forbidden while GROUP/POST_UNASSIGNED; current anonymous evidence retained.',
            'Retry only original age window and same source/identity context; pop/restore temporary Birth eligibility with try/finally and clone pending state.',
            'Record actual publication timing. A previously published native source later reconnected is a late change, not first publication.',
        ],
        frozen_binding_requirements=[
            'Exact actual code MRO, effective constants, raw/derived source manifests and source file/field/array hashes.',
            'Each whole/fixed/adaptive ROI and inclusive scalar/source population to its own producer certificate; no cross-ROI certification.',
            'Identity class, source generation/version, original first_seen and exact old bank anchor; distinguish source activity from identity reference qualification.',
            'Missing required evidence, original diagnostic cost, matrix entry/dummy and actual D1/Birth/S0 write decision.',
            'Current q and pre fact references, actual alias before/after and publisher mapping/hash; all branches sealed before any GT scoring.',
        ])


def main():
    assert tuple(read(HERE / 'CONFIG.json')['arms']) == ARMS
    result = dict(status='PASS_SOURCE_POPULATION_INTERFACE_AUDIT_NOT_RESEARCH_RESULT',
        arms=list(ARMS), case_selection='PREIDENTIFIED_ENGINEERING_FRAMES_AND_THEIR_RECORDED_ANCHORS; NO_GT_FILTER',
        contract=code_contract(), segments={name: source_audit(name, cases) for name, cases in CASES.items()},
        actual_new_controller_prefix_policy='REUSE_ROOT_REAL_SLICE_CHECKS; THIS_AUDIT_DOES_NOT_RUN_A_DUPLICATE_PREFIX',
        access=dict(observed_data_paths=sorted(guard.SEEN),
            npz_field_reads=[dict(path=p, key=k) for p, k in sorted(guard.NPZ)],
            h5_or_array_field_reads=source.FIELD_READS,
            GT_read=False, RGB_read=False, restored_read=False, model_http=0, cost_usd=0),
        physical_identity_truth='UNKNOWN; SOURCE_QUALITY_AND_POTENTIAL_LAYERS_ARE_NOT_GT_IDENTITY',
        no_prior_code_data_seal_or_score_changed=True)
    write_new(HERE / 'SOURCE_INTERFACE_AUDIT.json', result)
    lines = ['# DS18 来源与关联接口审计', '',
        '本审计只读取真实深度、原 SAM3 保存掩码与旧控制器原始动作；没有读取 GT、RGB、修复深度或调用模型。真实分支前缀由主执行复用，未重复长回放。', '',
        '## 调用与缺测语义', '',
        '- D1 使用 whole；Birth 使用固定 7×7 腐蚀 core，并将 whole 作为反证；S0 使用自适应 core。三种像素集合分别绑定，不能互相认证。',
        '- 旧匿名复制清空了测量，却仍记录真实首次 source birth，因此一次出生机会可能在身份仍未分配时消耗。修复须保留真实首次时间与版本，使用局部待决状态；不能捏造新出生。',
        '- Birth 缺失 required whole 必须显式 UNKNOWN 并禁止该候选提交；原有 whole 矛盾继续有效，诊断 cost 保留，dummy 不变。S0 不使用 whole，缺失 required core pair 共同无信息。', '',
        '## 真实来源切片', '', '| 来源 | 当前本地帧 | 当前全局帧 | 实测当前及旧锚点帧数 |', '|---|---|---|---|']
    for name, data in result['segments'].items():
        current = [data['frame_results'][str(frame)] for frame, _ in CASES[name]]
        lines.append(f"| {name} | {', '.join(str(x['frame']) for x in current)} | {', '.join(str(x['global_frame']) for x in current)} | {len(data['measured_frames'])} |")
    lines += ['', 'LW 的原 Birth 动作在 local3064/global3063；global3064 是 local3065。两帧均保留，未混淆索引。', '',
        '逐对象 JSON 保存 whole、固定 Birth core、自适应 S0 core 的真实统计、像素/来源摘要、独立来源统计、多层与质量拒绝、旧动作及实际锚点。原始像素留在受限数据路径。', '',
        '## 验收边界', '',
        '真实标量改动、错误 native 绑定与自适应统计认证固定 core 均进行拒绝检查。通过说明来源接口自洽，不代表物理身份正确或指标提升。',
        '最终新控制器的状态写入、首次发布及全部六臂性能仍由真实前缀、全段封存与独立评分交付；此审计不替代它们。', '']
    target = HERE / 'SOURCE_INTERFACE_AUDIT.md'
    with target.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(lines))
    print('Source-only interface audit PASS; segments', len(result['segments']), flush=True)


if __name__ == '__main__':
    main()
