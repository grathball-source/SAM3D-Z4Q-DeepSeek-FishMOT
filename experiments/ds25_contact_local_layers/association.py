"""Conditional local support paths; anonymous layers never write identity state."""
import math
import cv2
import numpy as np
from common import HERE, read, digest

CFG = read(HERE/'CONFIG.json')


def t4_cdf(value):
    u = value/math.hypot(value, 2.)
    return max(0., min(1., .5+.75*u-.25*u**3))


def _summary(packet):
    fact = packet['fact']
    return dict(frame=fact['frame'], time=fact['time'], fact_id=fact['fact_id'],
        measurement_sha256=digest(fact), status=fact['status'], reason=fact['reason'],
        contact_seed=bool(packet.get('contact_seed', False)),
        layer_count=len(fact['layers']),
        qualified_layers=[{key:layer[key] for key in
            ('support_id', 'z_mm', 'sigma_mm', 'independent_n')}
            for layer in fact['layers'] if layer['qualified']])


def _layers(packet):
    fact = packet['fact']
    if fact['status'] != 'AVAILABLE_TWO_LAYERS':
        return None
    layers = sorted((x for x in fact['layers'] if x['qualified']), key=lambda x:x['support_id'])
    if len(layers) != 2 or layers[0]['support_id'] == layers[1]['support_id']:
        return None
    for layer in layers:
        sid = layer['support_id']
        mask = np.asarray(packet['maps']['support_masks'][sid], dtype=bool)
        positions = np.asarray(packet['maps']['selected_positions'][sid])
        assert mask.ndim == 2 and positions.ndim == 1
        assert np.issubdtype(positions.dtype, np.integer)
        assert len(positions) == layer['independent_n'] and len(positions) > 0
        assert np.all(positions >= 0) and np.all(positions < mask.size)
        assert np.all(np.diff(positions) > 0), 'Canonical selected positions must be sorted and unique'
        assert mask.ravel()[positions].all(), 'Selected sources must lie in their observed support'
        if not (math.isfinite(layer['z_mm']) and math.isfinite(layer['sigma_mm']) and layer['sigma_mm'] > 0):
            return None
    assert not np.intersect1d(*(packet['maps']['selected_positions'][x['support_id']]
        for x in layers)).size, 'Two layers cannot reuse the same canonical pixel source'
    return layers


def _ownership(packet, layers, low, high):
    roles = packet.get('roles')
    if roles is None or set(roles) != {'A', 'B'}:
        return None, []
    counts = []
    candidates = {}
    for layer in layers:
        sid = layer['support_id']; positions = packet['maps']['selected_positions'][sid]
        support = packet['maps']['support_masks'][sid]
        role_counts = {}
        for role in ('A', 'B'):
            mask = np.asarray(roles[role], dtype=bool)
            assert mask.shape == support.shape, 'Role mask is from a different spatial frame'
            role_counts[role] = int(mask.ravel()[positions].sum())
        fractions = {role:n/len(positions) for role,n in role_counts.items()}
        candidates[sid] = [role for role,other in (('A', 'B'), ('B', 'A'))
            if fractions[role] >= high and fractions[other] <= low]
        counts.append(dict(support_id=sid, independent_n=len(positions),
            role_counts=role_counts, role_fractions=fractions,
            admissible_roles=candidates[sid], membership='GEOMETRIC_NOT_CERTIFIED_PHYSICAL_IDENTITY'))
    possibilities = [{layers[0]['support_id']:a, layers[1]['support_id']:b}
        for a in candidates[layers[0]['support_id']]
        for b in candidates[layers[1]['support_id']] if a != b]
    return (possibilities[0] if len(possibilities) == 1 else None), counts


def _transition(first, second, first_layers, second_layers):
    margin = CFG['spatial_link_margin_px']
    kernel = np.ones((2*margin+1, 2*margin+1), 'u1')
    minimum = CFG['minimum_symmetric_overlap_fraction']
    first_maps, second_maps = first['maps'], second['maps']
    geometry = []
    admitted = {}
    for a in first_layers:
        sa = a['support_id']; ma = first_maps['support_masks'][sa]
        pa = first_maps['selected_positions'][sa]
        da = cv2.dilate(np.asarray(ma, dtype='u1'), kernel).astype(bool)
        for b in second_layers:
            sb = b['support_id']; mb = second_maps['support_masks'][sb]
            pb = second_maps['selected_positions'][sb]
            assert ma.shape == mb.shape, 'Consecutive support grids differ'
            db = cv2.dilate(np.asarray(mb, dtype='u1'), kernel).astype(bool)
            forward_n = int(db.ravel()[pa].sum()); backward_n = int(da.ravel()[pb].sum())
            forward = forward_n/len(pa); backward = backward_n/len(pb)
            admitted[sa,sb] = forward >= minimum and backward >= minimum
            geometry.append(dict(from_support_id=sa, to_support_id=sb,
                from_independent_n=len(pa), to_independent_n=len(pb),
                forward_overlap_n=forward_n, backward_overlap_n=backward_n,
                forward_fraction=forward, backward_fraction=backward,
                admissible=admitted[sa,sb]))
    a,b = [x['support_id'] for x in first_layers]
    c,d = [x['support_id'] for x in second_layers]
    permutations = [mapping for mapping in ({a:c,b:d}, {a:d,b:c})
        if all(admitted[s,t] for s,t in mapping.items())]
    detail = dict(from_frame=first['fact']['frame'], to_frame=second['fact']['frame'],
        geometry=geometry, admissible_permutations=permutations,
        from_fact_id=first['fact']['fact_id'], to_fact_id=second['fact']['fact_id'],
        from_measurement_sha256=digest(first['fact']), to_measurement_sha256=digest(second['fact']))
    return (permutations[0] if len(permutations) == 1 else None), detail


def evaluate(pre_packets, contact_packets, post_packet):
    """Compare one complete mapping only through uniquely observed spatial paths."""
    pre_packets, contact_packets = list(pre_packets), list(contact_packets)
    packets = pre_packets+contact_packets+[post_packet]
    out = dict(status='UNKNOWN', veto=False,
        pre_pairs=[_summary(p) for p in pre_packets],
        anonymous_contact=[_summary(p) for p in contact_packets], current_pair=_summary(post_packet),
        ownership_counts=[], spatial_transitions=[], calculated_order=[],
        foreground_identity='UNKNOWN', physical_depth_accuracy_mm='UNKNOWN',
        mapping_is_hypothesis=True, no_identity_history_or_bank_write=True,
        cross_frame_source_index_matching=False, elapsed_depth_extrapolation=False,
        probability_calibration='UNCALIBRATED_DF4_NOISE_PROXY; SPATIAL_PATH_IS_CONDITIONAL')
    def unknown(reason):
        return dict(out, reason=reason)
    if len(pre_packets) < CFG['minimum_pre_pairs']:
        return unknown('TOO_FEW_CONTIGUOUS_PRE_PAIRS')
    if not contact_packets or not any(p.get('contact_seed', False) for p in contact_packets):
        return unknown('NO_ACTUAL_GEOMETRY_CONTACT_SEED')
    if any('roles' in p for p in contact_packets):
        return unknown('CONTACT_LAYER_HAS_FORBIDDEN_IDENTITY_ROLES')
    if any(not math.isfinite(p['fact']['time']) for p in packets):
        return unknown('SPATIAL_CHAIN_NONFINITE_TIME')
    if any(b['fact']['frame'] != a['fact']['frame']+1 or
           b['fact']['time'] <= a['fact']['time'] for a,b in zip(packets, packets[1:])):
        return unknown('SPATIAL_CHAIN_GAP_OR_NONMONOTONIC_TIME')
    layers = [_layers(p) for p in packets]
    if any(x is None for x in layers):
        return unknown('EVERY_FRAME_REQUIRES_EXACTLY_TWO_QUALIFIED_LOCAL_LAYERS')
    low = 1/(1+CFG['minimum_joint_odds']); high = 1-low
    owners = {}
    for i in list(range(len(pre_packets)))+[len(packets)-1]:
        owner, counts = _ownership(packets[i], layers[i],
            CFG['maximum_other_role_membership_fraction'], CFG['minimum_endpoint_membership_fraction'])
        out['ownership_counts'].append(dict(frame=packets[i]['fact']['frame'], supports=counts,
            unique_bijection=owner, fact_id=packets[i]['fact']['fact_id'],
            measurement_sha256=digest(packets[i]['fact'])))
        if owner is None:
            return unknown('ENDPOINT_SPATIAL_OWNERSHIP_AMBIGUOUS')
        owners[i] = owner
    paths = {role:sid for sid,role in owners[0].items()}
    initial_order = None
    for i,(packet,frame_layers) in enumerate(zip(packets,layers)):
        if i:
            permutation, detail = _transition(packets[i-1], packet, layers[i-1], frame_layers)
            out['spatial_transitions'].append(detail)
            if permutation is None:
                return unknown('SPATIAL_BIJECTION_NOT_UNIQUE')
            paths = {role:permutation[sid] for role,sid in paths.items()}
        if i < len(pre_packets) and any(owners[i][sid] != role for role,sid in paths.items()):
            return unknown('PRE_CLEAN_ENDPOINT_PATH_CHANGED')
        values = {x['support_id']:x for x in frame_layers}
        a,b = values[paths['A']],values[paths['B']]
        delta = b['z_mm']-a['z_mm']; scale = math.hypot(a['sigma_mm'],b['sigma_mm'])
        probability = t4_cdf(delta/scale)
        order = 'A_NEARER' if probability >= high else 'B_NEARER' if probability <= low else None
        out['calculated_order'].append(dict(frame=packet['fact']['frame'], time=packet['fact']['time'],
            anchored_A_support_id=paths['A'], anchored_B_support_id=paths['B'],
            delta_B_minus_A_mm=delta, scale_mm=scale, probability_A_nearer=probability,
            strong_order=order, fact_id=packet['fact']['fact_id'], measurement_sha256=digest(packet['fact'])))
        if order is None:
            return unknown('WEAK_OBSERVED_LOCAL_ORDER')
        if initial_order is not None and order != initial_order:
            return unknown('OBSERVED_LOCAL_ORDER_REVERSAL')
        initial_order = order
    ending = {role:owners[len(packets)-1][sid] for role,sid in paths.items()}
    conflict = ending == {'A':'B','B':'A'}
    assert conflict or ending == {'A':'A','B':'B'}
    return dict(out, status='CONFLICT' if conflict else 'COMPATIBLE', veto=conflict,
        reason='UNIQUE_ANONYMOUS_SPATIAL_PATHS_CONTRADICT_MAPPING' if conflict else
               'UNIQUE_ANONYMOUS_SPATIAL_PATHS_COMPATIBLE_WITH_MAPPING',
        anchored_paths_post_geometric_roles=ending,
        conditional_assumption='CONTINUOUS_UNIQUE_SPATIAL_LAYER_PATHS; NOT_GT_CERTIFIED_FISH_IDENTITIES')


def self_check():
    """Runnable synthetic control-flow checks, without a physical accuracy claim."""
    import copy
    shape = (24, 48)
    left = np.zeros(shape, bool); left[8:16,4:12] = True
    right = np.zeros(shape, bool); right[8:16,34:42] = True
    def packet(frame, roles=True):
        ids = [f'F{frame}/left', f'F{frame}/right']
        masks = dict(zip(ids,(left.copy(),right.copy())))
        layers = [dict(support_id=sid, qualified=True, z_mm=z, sigma_mm=15.,
            independent_n=int(mask.sum())) for sid,mask,z in zip(ids,(left,right),(700.,1000.))]
        value = dict(fact=dict(frame=frame,time=frame/30,fact_id=f'synthetic/F{frame}',
            status='AVAILABLE_TWO_LAYERS',reason='SYNTHETIC',layers=layers),
            maps=dict(support_masks=masks,
                selected_positions={sid:np.flatnonzero(mask) for sid,mask in masks.items()}))
        if roles:value['roles'] = {'A':left.copy(),'B':right.copy()}
        return value
    pre = [packet(f) for f in range(1,6)]
    contact = packet(6,False);contact['contact_seed'] = True
    post = packet(7)
    compatible = evaluate(pre,[contact],post)
    assert compatible['status'] == 'COMPATIBLE' and not compatible['veto']
    swapped = copy.deepcopy(post);swapped['roles'] = {'A':right.copy(),'B':left.copy()}
    conflict = evaluate(pre,[contact],swapped)
    assert conflict['status'] == 'CONFLICT' and conflict['veto']
    assert conflict['anchored_paths_post_geometric_roles'] == {'A':'B','B':'A'}
    assert evaluate(pre,[],post)['reason'] == 'NO_ACTUAL_GEOMETRY_CONTACT_SEED'
    unseeded = copy.deepcopy(contact);unseeded.pop('contact_seed')
    assert evaluate(pre,[unseeded],post)['status'] == 'UNKNOWN'
    wrong_gap = copy.deepcopy(contact);wrong_gap['fact']['frame'] = 8
    assert evaluate(pre,[wrong_gap],post)['reason'] == 'SPATIAL_CHAIN_GAP_OR_NONMONOTONIC_TIME'
    missing = copy.deepcopy(contact);missing['fact']['status'] = 'UNKNOWN'
    assert evaluate(pre,[missing],post)['reason'] == 'EVERY_FRAME_REQUIRES_EXACTLY_TWO_QUALIFIED_LOCAL_LAYERS'
    with_roles = copy.deepcopy(contact);with_roles['roles'] = pre[0]['roles']
    assert evaluate(pre,[with_roles],post)['reason'] == 'CONTACT_LAYER_HAS_FORBIDDEN_IDENTITY_ROLES'
    weak = copy.deepcopy(contact);weak['fact']['layers'][1]['z_mm'] = 710.
    assert evaluate(pre,[weak],post)['reason'] == 'WEAK_OBSERVED_LOCAL_ORDER'
    reverse = copy.deepcopy(contact)
    reverse['fact']['layers'][0]['z_mm'],reverse['fact']['layers'][1]['z_mm'] = 1000.,700.
    assert evaluate(pre,[reverse],post)['reason'] == 'OBSERVED_LOCAL_ORDER_REVERSAL'
    ambiguous = copy.deepcopy(contact)
    both = left|right
    all_positions = np.flatnonzero(both)
    for i,layer in enumerate(ambiguous['fact']['layers']):
        sid = layer['support_id'];positions = all_positions[i::2]
        layer['independent_n'] = len(positions)
        ambiguous['maps']['support_masks'][sid] = both.copy()
        ambiguous['maps']['selected_positions'][sid] = positions
    assert evaluate(pre,[ambiguous],post)['reason'] == 'SPATIAL_BIJECTION_NOT_UNIQUE'
    uncertain_endpoint = copy.deepcopy(post);uncertain_endpoint['roles'] = {'A':both,'B':both}
    assert evaluate(pre,[contact],uncertain_endpoint)['reason'] == 'ENDPOINT_SPATIAL_OWNERSHIP_AMBIGUOUS'
    reordered = copy.deepcopy(pre)
    for p in reordered:p['fact']['layers'].reverse()
    shuffled = evaluate(reordered,[contact],swapped)
    assert (shuffled['status'],shuffled['veto'],shuffled['anchored_paths_post_geometric_roles']) == (
        conflict['status'],conflict['veto'],conflict['anchored_paths_post_geometric_roles'])
    corruption = copy.deepcopy(contact)
    layer = corruption['fact']['layers'][0];corruption['maps']['selected_positions'][layer['support_id']][0] = 0
    try:evaluate(pre,[corruption],post)
    except AssertionError:pass
    else:raise AssertionError('Re-signed public fact cannot admit private points outside support')
    assert evaluate(pre[:4],[contact],post)['reason'] == 'TOO_FEW_CONTIGUOUS_PRE_PAIRS'
    no_overlap = copy.deepcopy(contact)
    for layer in no_overlap['fact']['layers']:
        sid = layer['support_id'];mask = no_overlap['maps']['support_masks'][sid]
        moved = np.roll(mask,10,axis=0)
        no_overlap['maps']['support_masks'][sid] = moved
        no_overlap['maps']['selected_positions'][sid] = np.flatnonzero(moved)
    assert evaluate(pre,[no_overlap],post)['reason'] == 'SPATIAL_BIJECTION_NOT_UNIQUE'
    assert all('roles' not in p for p in [contact]), 'Association mutated an anonymous packet'
    return dict(status='PASS', synthetic_only=True, GT_read=False, new_model_http=0)


if __name__ == '__main__':
    print(self_check())
