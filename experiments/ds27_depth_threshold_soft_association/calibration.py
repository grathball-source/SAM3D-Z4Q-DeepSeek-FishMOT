"""Freeze two proposed parameter levels from old PRE measurements, without GT.

Spatial residual MAD includes real surface/background variation and is not a
repeatability or physical-accuracy measurement. No current replay adapts this
calibration, and no tracking score participates in selecting these levels.
"""
from common import *
from collections import Counter
import math
import numpy as np


def distribution(values):
    values = np.asarray([v for v in values if v is not None], dtype='f8')
    return dict(n=len(values), minimum=float(values.min()) if len(values) else None,
        q10=float(np.quantile(values, .1)) if len(values) else None,
        q25=float(np.quantile(values, .25)) if len(values) else None,
        median=float(np.median(values)) if len(values) else None,
        q75=float(np.quantile(values, .75)) if len(values) else None,
        q90=float(np.quantile(values, .9)) if len(values) else None,
        maximum=float(values.max()) if len(values) else None)


def run():
    ds26 = ROOT / 'experiments/ds26_phase_roi_observability'
    paths = {name: ds26 / 'run' / name for name in
        ('ENDPOINT_FACTS.jsonl.gz', 'PAIRINGS.jsonl.gz')}
    seal_path = ds26 / 'run/MEASUREMENTS_SEALED.json'
    seal = read(seal_path)
    assert seal['status'] == 'SEALED_BEFORE_INDEPENDENT_REVIEW'
    for name in paths:
        verify_item(seal['artifacts'][name])
    pairs = [p for p in rows(paths['PAIRINGS.jsonl.gz']) if p['phase'].startswith('PRE')]
    ids = {v['fact_id'] for p in pairs for v in p['role_facts'].values()}
    facts = {f['fact_id']: f for f in rows(paths['ENDPOINT_FACTS.jsonl.gz']) if f['fact_id'] in ids}
    assert len(pairs) == 119 and len(facts) == len(ids) == 229
    refs = []
    for p in pairs:
        assert p['frame'] <= p['causal_query_limit'] and p['GT_RGB_future'] is False
        for role, cited in p['role_facts'].items():
            fact = facts[cited['fact_id']]
            assert cited['measurement_sha256'] == digest(fact)
            proven = p['role_provenance'][role]
            assert proven['class_at_pre'] == 'CLEAN_ACTUAL_BANK_ANCHOR'
            assert proven['actual_publication_matches'] is True
            assert not any(fact['source_binding'].get(k, False) for k in ('GT_read', 'RGB_read', 'restored_read'))
            refs.append(dict(context_id=p['context_id'], task_id=p['task_id'], role=role,
                frame=p['frame'], segment=p['segment'], native=p['native_roles'][role],
                actual_bank_anchor=proven['actual_bank_anchor'], public=proven['public'],
                transaction_sha256=proven['transaction_sha256'], fact_id=fact['fact_id'],
                fact_sha256=digest(fact), source_binding_sha256=digest(fact['source_binding'])))
    results = {}
    for name in [*SEGMENTS, 'ALL_PRE']:
        group = list(facts.values()) if name == 'ALL_PRE' else [f for f in facts.values() if f['segment'] == name]
        layers = [l for f in group for l in f['layers']
            if l['kind'] == 'MEASURED_DEPTH_SUPPORT' and l['substantial']]
        results[name] = dict(unique_actual_mask_facts=len(group),
            background_raw_scaled_MAD_mm=distribution(1.4826*f['plane']['residual_summary']['mad']
                for f in group if f['plane']),
            support_raw_scaled_MAD_mm=distribution(1.4826*l['independent_summary']['mad'] for l in layers),
            background_independent_N=distribution(f['background']['summary']['n'] for f in group),
            support_independent_N=distribution(l['independent_n'] for l in layers),
            background_15mm_floor_hits=sum(1.4826*f['plane']['residual_summary']['mad'] < 15
                for f in group if f['plane']),
            support_15mm_floor_hits=sum(1.4826*l['independent_summary']['mad'] < 15 for l in layers),
            original_parent_reasons=dict(Counter(f['reason'] for f in group)),
            physical_accuracy_mm='UNKNOWN', temporal_repeatability_mm='UNKNOWN')
    q25 = results['ALL_PRE']['background_raw_scaled_MAD_mm']['q25']
    proposed = 5. * math.ceil(q25 / 5.)
    assert proposed == 5. and all(p['scale_floor_mm'] in (15., proposed) for p in VARIANTS.values())
    output = dict(status='PRE_ONLY_DESCRIPTIVE_CALIBRATION_FIXED_BEFORE_DS27_REPLAY',
        facts_unit='UNIQUE_ACTUAL_FRAME_MASK_FACT; CORRELATED_WITHIN_REFERENCE_CONTEXT',
        pre_pairs=len(pairs), pre_role_references=len(refs), unique_pre_facts=len(facts),
        reference_contexts=len({p['context_id'] for p in pairs}), sources=results,
        parameter_levels=VARIANTS,
        revised_floor_basis=dict(raw_background_PRE_q25_mm=q25,
            rule='CEIL_Q25_TO_NEXT_5MM_GRID', result_mm=proposed),
        revised_contrast_basis=dict(floor_mm=2.*proposed, sigma_factor=2.,
            rule='PRESPECIFIED_LOOSER_QUALIFICATION_HYPOTHESIS; NOT_SELECTED_FROM_PASS_RATE_OR_TRACKING_SCORE'),
        frozen_constants=dict(layer_gap_mm=30., maximum_scale_mm=60., minimum_independent_N=16,
            minimum_fraction=.2, background_minimum_N=64),
        post_used_for_calibration=False, GT_used=False, RGB_used=False,
        current_or_future_replay_adaptation=False, precision_claim='UNKNOWN',
        not_mean_standard_error=True, no_division_by_sqrt_N=True,
        scope='DEVELOPMENT_ABLATION_ON_PREVIOUSLY_OBSERVED_SOURCES; NOT_BLIND_GENERALIZATION',
        limitations=['Residual MAD includes nonplanarity, projection error, background contamination and missed objects.',
            'Support MAD also includes real object longitudinal depth; neither MAD is instrument accuracy.',
            'Source deduplication prevents repeated projected pixels inflating N, but does not establish independent noise.',
            'Zero-fact sources receive the same fixed levels as an extrapolation experiment.'],
        version_and_source_references=refs,
        provenance=dict(code=artifact(Path(__file__)), seal=artifact(seal_path),
            inputs={k:artifact(v) for k,v in paths.items()}), new_model_http=0, cost_usd=0)
    write_new(HERE / 'CALIBRATION.json', output)
    print(json.dumps({k:v['background_raw_scaled_MAD_mm'] for k,v in results.items()}, ensure_ascii=False))


if __name__ == '__main__':
    run()

