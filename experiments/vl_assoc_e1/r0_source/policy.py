"""Causal proposal compiler. No labels, event lists or model-ranked pruning."""
import copy
import hashlib
import itertools
import json
import math
import re
import statistics
from bridge import P, read


def name(domain, n):
    return domain+hashlib.sha256(('SCENE_V1|'+domain+'|'+str(n)).encode()).hexdigest()[:8]


def reference(engine, k, f, now):
    h = engine.bank.get(k)
    if not h or not h.get('anchor') or h['anchor']['frame'] >= f:
        return None
    if h['clean_count'] < 5 or h['clean_time'] is None or now-h['clean_time'] > 12:
        return None
    return h


def compare(engine, o, k, profile, f, now):
    h = reference(engine, k, f, now)
    if h is None:
        return dict(motion=None, core=None, whole=None, contradiction=False, missing='no_qualified_past_reference')
    cs = {v: engine.comparison(engine.measurement(profile, v), engine.history(k, v, f, now)) for v in ['core', 'whole']}
    # A residual beyond the original risk bound is explicit contradiction.
    contradiction = engine.quality(o) and not o.get('neighbors') and any(x is not None and x['lower_mm'] > engine.birth_config['risk_budget_mm'] for x in cs.values())
    return dict(motion=engine.motion(h, o, now), motion_units='age seconds; distance and radius image pixels; remaining ratios dimensionless', **cs, contradiction=bool(contradiction), missing=None)


def clean_observation(engine, o, k, occupied, now):
    h = engine.bank.get(k)
    if not engine.quality(o) or o.get('neighbors') or not h:
        return False
    area = statistics.median(h['areas']) if h['areas'] else o['area']
    if not .5*area <= o['area'] <= 1.8*area:
        return False
    # Same latent-merge eligibility as the existing history writer.
    return not any(p not in occupied and 0 <= now-t <= 6 for p, t in engine.partners(h, k).items())


def compile_view(bridge, view):
    e, f, now = bridge.engine, view['frame'], view['now']
    obs = {o['id']: o for o in view['observations']}
    profiles, h0 = view['profiles'], view['mapping']
    occupied = set(h0.values())
    refs = {k: h for k in e.bank if (h := reference(e, k, f, now)) is not None}
    cs = {n: {k: compare(e, o, k, profiles.get(n), f, now) for k in refs} for n, o in obs.items()}
    positive = set()
    positive_sources = {}
    original_events = view['trace']['events']
    for event in original_events:
        if event.get('kind') == 'reconnect' and event.get('accepted'):
            positive.add(event['native_id'])
            positive_sources[event['native_id']] = 'accepted_reconnect_trace'
    for edge in view['trace'].get('edges', []):
        for partner in edge.get('reserved_partners', []):
            if partner.get('basis') == 'native_continuity_plus_depth_compatibility':
                for n, k in h0.items():
                    if k == partner['id']:
                        positive.add(n)
                        positive_sources[n] = 'late_reserved_partner_support'
    # Only actual trace-backed active witnesses count as supported claims.
    for edge in view['trace'].get('birth_checks', []):
        for partner in edge.get('partners', []):
            if partner.get('state') == 'support':
                for n, k in h0.items():
                    if k == partner['id']:
                        positive.add(n)
                        positive_sources[n] = 'birth_partner_support'
    statuses, choices, reasons = {}, {}, {}
    for n, o in obs.items():
        own = cs[n].get(h0[n])
        born = e.birth.get(n)
        transient = (n not in e.alias and n not in e.retired and
                     (born is None and e.first is not None or born is not None and born[0] != e.first and 0 <= now-born[1] <= 6))
        conflict = bool(own and own['contradiction'])
        if conflict:
            status = 'CONFLICT_REVIEW'
        elif n in positive:
            status = 'SUPPORTED_CURRENT'
        elif transient:
            status = 'PENDING_RECONNECT'
        elif own is None:
            status = 'UNANCHORED'
        else:
            status = 'NATIVE_CONTINUATION'
        statuses[n] = dict(status=status, transient=bool(transient), contradiction=conflict,
                           decision_basis='current_qualified_depth_conflict' if conflict else positive_sources.get(n, 'unknown'))
        def safe_reason(s):
            return re.sub(r'(partner_|candidate_)(\d+)', lambda m: m[1]+name('I', int(m[2])), str(s))
        statuses[n]['native_decision_reasons'] = [dict(phase=x.get('phase', 'late'), rejection=safe_reason(x.get('rejection')), failures=[safe_reason(a) for a in x.get('failures', [])]) for x in view['trace'].get('birth_checks', [])+view['trace'].get('edges', []) if x.get('native_id') == n]
        choices[n] = [h0[n]]
        if status not in ['PENDING_RECONNECT', 'CONFLICT_REVIEW'] or not e.quality(o) or o.get('neighbors'):
            continue
        for k, h in refs.items():
            if k == h0[n] or k in e.alias:
                continue
            motion = cs[n][k]['motion']
            if motion is None or motion['normalized_distance'] > 2:
                continue
            if k not in occupied:
                if not 0 < now-h['last_seen'] <= 6 or h['contact_time'] is None or h['last_seen']-h['contact_time'] > 1 or not h['depth_history']:
                    continue
            elif not conflict:
                # Pending proposals may compete for an occupied identity only if
                # its occupant has an independently observable conflict.
                owner = next(a for a, b in h0.items() if b == k)
                if not cs[owner].get(k, {}).get('contradiction'):
                    continue
            choices[n].append(k)
        if len(choices[n]) > 1:
            reasons[n] = 'current_depth_contradiction' if conflict else 'unresolved_recent_birth_with_reachable_old_reference'
    affected = [n for n in obs if len(choices[n]) > 1]
    if len(affected) > 2:
        return dict(status='OUT_OF_SCOPE', affected=affected, claims=statuses, proposals=[], comparisons=cs)
    proposals = []
    for values in itertools.product(*(choices[n] for n in affected)):
        changes = {n: k for n, k in zip(affected, values) if h0[n] != k}
        if not changes:
            continue
        after = dict(h0)
        after.update(changes)
        if len(set(after.values())) != len(after):
            continue
        if any(statuses[n]['status'] == 'SUPPORTED_CURRENT' for n in changes):
            continue
        displaced = [n for n in changes if not statuses[n]['transient']]
        kind = 'RECONNECT_ONE' if len(changes) == 1 and not displaced else 'REASSIGN_PAIR'
        changed_natives = set(changes)
        involved_public = set(changes.values()) | {h0[n] for n in changes}
        if any(changed_natives & {check['native_id'], check['incumbent_native']} and
               check['public_id'] in involved_public
               for check in view['trace'].get('native_return_checks', [])):
            kind = 'RETURN_RESOLUTION'
        proposals.append(dict(changes=changes, after=after, kind=kind, displaced=displaced,
                              reasons={n: reasons[n] for n in changes}))
    status = 'PROPOSAL_OVERFLOW' if len(proposals) > 4 else 'READY' if proposals else 'NO_LEGAL_PROPOSAL'
    # Preserve complete overflow candidates locally, never choose the easiest four.
    return dict(status=status, affected=affected, claims=statuses, proposals=proposals, comparisons=cs)


def measurement(d, source, age=0):
    return dict(value=d, unit='mm for depth, pixels for counts/area', source=source, age_seconds=age,
                quality='missing' if d is None or d.get('median') is None else 'raw_measurement; valid_fraction and MAD specify quality',
                missing_reason='unavailable_or_unqualified' if d is None or d.get('median') is None else None)


def state_for(bridge, view, compiled, feature_history=None):
    e, f, now = bridge.engine, view['frame'], view['now']
    O, I = lambda x: name('O', x), lambda x: name('I', x)
    h0 = view['mapping']
    affected = set(compiled['affected'])
    targets = {k for p in compiled['proposals'] for k in p['changes'].values()} | {h0[n] for n in affected}
    # Include every competing current observation in detailed comparisons.
    detailed = affected | {n for n, k in h0.items() if k in targets}
    def anchor(a):
        return None if not a else dict(observation=O(a['native_id']), identity=I(a['canonical_id']), age_frames=f-a['frame'], source='original_Z4Q_measurement_anchor')
    observations = {}
    for o in view['observations']:
        n = o['id']
        v = dict(claim=I(h0[n]), claim_status=compiled['claims'][n], area_pixels=o['area'],
                 box_pixels=o['box'], presence=o.get('presence'), neighbors=[O(a) for a in o.get('neighbors', [])],
                 source='current_native_prediction', measurement_age_frames=0,
                 identity_epoch=view.get('epochs', {}).get(n, bridge.epochs.get(n, 0)))
        if n in detailed:
            v['depth'] = {x: measurement(view['profiles'][n].get(x), 'current_raw_depth_ROI_'+x) for x in ['core', 'whole']}
            feat = (feature_history or {}).get(f, {}).get(n)
            v['appearance'] = dict(source='existing_256D_FPN_and_48bin_RGB_histogram', region='whole_native_mask; FPN best candidate IoU>=0.6',
                FPN_available=bool(feat and feat.get('appearance') is not None), RGB_histogram_available=bool(feat and feat.get('rgb_hist') is not None),
                candidate_mask_iou=None if feat is None else feat.get('appearance_iou'), identity_encoder_trained_for_fish=False)
        observations[O(n)] = v
    references = {}
    for k in targets:
        h = reference(e, k, f, now)
        if h is None:
            references[I(k)] = dict(value=None, missing_reason='no_qualified_causal_history')
            continue
        regular = {}
        for channel in ['core', 'whole']:
            x = e.history(k, channel, f, now)
            regular[channel] = None if x is None else dict(z_mm=x['z'], risk_mm=x['u'], mad_mm=x['mad'], n=x['n'], valid_fraction=x['fraction'], count=x['count'], age_seconds=now-x['time'], anchor=anchor(x['anchor']))
        q = e.recent_core.get(k)
        references[I(k)] = dict(anchor=anchor(h['anchor']), clean_count=h['clean_count'], age_seconds=now-h['clean_time'],
            regular=regular, recent_core=None if q is None else dict(z_mm=q['z'], risk_mm=q['u'], age_seconds=now-q['time'], anchor=anchor(q['anchor']), eligibility='only_native_survivor_in_original_edge_context'),
            contacts=[dict(identity=I(a), age_seconds=now-t) for a, t in e.partners(h, k).items()],
            identity_verified=False, source='Z4Q_branch_history_not_ground_truth')
    comparisons = {O(n): {I(k): v for k, v in compiled['comparisons'][n].items() if k in targets} for n in detailed}
    for n in detailed:
        current = (feature_history or {}).get(f, {}).get(n)
        for k in targets:
            if I(k) not in comparisons[O(n)]:
                continue
            h = reference(e, k, f, now)
            a = None if h is None else h['anchor']
            past = None if a is None else (feature_history or {}).get(a['frame'], {}).get(a['native_id'])
            values = dict(cosine_distance=None, histogram_L1_half=None, reference_anchor=anchor(a),
                          source='existing_features_at_original_Z4Q_clean_anchor', correlated_with_depth=True)
            if current and past:
                x, y = current.get('appearance'), past.get('appearance')
                if x is not None and y is not None:
                    values['cosine_distance'] = max(0., min(2., 1-sum(a*b for a,b in zip(x,y))))
                x, y = current.get('rgb_hist'), past.get('rgb_hist')
                if x is not None and y is not None:
                    values['histogram_L1_half'] = sum(abs(a-b) for a,b in zip(x,y))*.5
            values['missing_reason'] = 'unavailable_current_or_original_anchor_feature' if values['cosine_distance'] is None else None
            comparisons[O(n)][I(k)] = dict(comparisons[O(n)][I(k)], appearance=values)
        ranked = sorted((v['appearance']['cosine_distance'], k) for k, v in comparisons[O(n)].items() if v.get('appearance',{}).get('cosine_distance') is not None)
        for _, k in ranked:
            comparisons[O(n)][k]['appearance']['rank_among_available_references'] = 1+sum(d < comparisons[O(n)][k]['appearance']['cosine_distance'] for d, _ in ranked)
    alternatives = {}
    for index, p in enumerate(compiled['proposals'], 1):
        alternatives[f'P{index:02d}'] = dict(type=p['kind'], full_mapping={O(n): I(k) for n, k in p['after'].items()},
            changes=[dict(observation=O(n), before=I(h0[n]), after=I(k), trigger=p['reasons'][n],
                          replaced_claim_status=compiled['claims'][n], new_edge=comparisons[O(n)].get(I(k)),
                          old_edge=comparisons[O(n)].get(I(h0[n]))) for n, k in p['changes'].items()],
            displaced_nontransient=[O(n) for n in p['displaced']], occupancy='unique; all unchanged observations retained')
    native_decisions = []
    for edge in view['trace'].get('edges', []):
        history = e.bank.get(edge['canonical_id'], {})
        samples = history.get('depth_history') or []
        latest = samples[-1] if samples else None
        bank_anchor = history.get('anchor') if latest else None
        # D1 reads its latest bank depth sample; old_anchor exists only on accepted
        # events. An absent old_anchor must never be filled from another edge.
        depth_source = None if latest is None else dict(
            value_mm=latest[1], time=latest[0], anchor=anchor(bank_anchor),
            source='D1_bank_depth_history_latest')
        if depth_source is not None and edge.get('history_depth') is not None:
            assert math.isclose(depth_source['value_mm'], edge['history_depth'], abs_tol=1e-5)
        native_decisions.append(dict(observation=O(edge['native_id']), candidate_identity=I(edge['canonical_id']),
            source='original_delayed_reconnection_trace', anchor=anchor(edge.get('old_anchor')),
            depth_history_source=depth_source,
            rejection=edge.get('rejection'), cost=edge.get('cost'),
            depth_mm={key:edge.get(key) for key in ['history_depth','current_depth','residual_mm','tolerance_mm','partner_margin_mm','required_partner_margin_mm']},
            reserved_partners=[dict(identity=I(q['id']),
                observation=next((O(n) for n, k in h0.items() if k == q['id']), None),
                basis=q.get('basis'), own_history_depth_mm=q.get('own_history_depth'),
                current_depth_mm=q.get('current_depth'), candidate_residual_mm=q.get('candidate_residual_mm'))
                for q in edge.get('reserved_partners',[])],
            competitors=[dict(identity=I(q['id']), residual_mm=q.get('residual_mm')) for q in edge.get('alternatives',[])]))
    return dict(native_decision_provenance=native_decisions, snapshot_version=hashlib.sha256(str(bridge.version).encode()).hexdigest()[:12],
        observations=observations, references=references, comparisons=comparisons,
        H0=dict(full_mapping={O(n): I(k) for n, k in h0.items()}, source='native_Z4Q_preview'),
        alternatives=alternatives, DEFER='retain H0 without certifying its correctness',
        boundaries='Predictions and identity claims are not truth. No unobserved object can be created. Depth and appearance from one mask are correlated. Motion is a computed prediction, not a measurement.')


def request(state, arm):
    profile = read(P/'SCENE_PROFILE.json')
    instructions = profile['neutral'] if arm == 'B1' else profile['neutral']+' '+profile['fish_rules']+' Synthetic policy examples: '+json.dumps(profile['examples'])
    criteria = dict(H0='The complete current mapping has the strongest applicable positive support.',
                    **{k:'The complete alternative '+k+' has the strongest applicable positive support, including all new edges and displaced claims.' for k in state['alternatives']},
                    DEFER='Evidence does not sufficiently support authorizing an edit or certifying H0.')
    questions = dict(select=dict(type='choice', instructions=instructions+' Select the best supported COMPLETE interpretation among H0, the listed alternatives, and DEFER.', criteria=criteria))
    for k in state['alternatives']:
        questions[k+'_support'] = dict(type='noul', instructions=instructions+f' Is the COMPLETE edit in {k} sufficiently supported by positive applicable evidence for every changed correspondence, rather than merely possible or preferable to another weak alternative?')
        questions[k+'_displaced'] = dict(type='noul', instructions=instructions+f' In proposal {k}, does EVERY displaced nontransient claim have an independently traceable observational contradiction? Missing evidence, uniqueness and another preferred edge do not count as contradiction. Evaluate {k} directly from state.')
    return dict(model='jev-1.13.0', state=state, questions=questions)


def gate(answers, compiled):
    choice = answers['select']
    k = choice['choice']
    if not k.startswith('P'):
        return None, k
    probabilities = sorted(choice['probabilities'].values(), reverse=True)
    p = compiled['proposals'][int(k[1:])-1]
    if probabilities[0] < .85 or probabilities[0]-probabilities[1] < .20:
        return None, 'choice_risk_gate'
    if answers[k+'_support']['noul'] < .85:
        return None, 'whole_edit_support_gate'
    if p['displaced'] and answers[k+'_displaced']['noul'] < .85:
        return None, 'displaced_contradiction_gate'
    return p, 'qualifying_observation'
