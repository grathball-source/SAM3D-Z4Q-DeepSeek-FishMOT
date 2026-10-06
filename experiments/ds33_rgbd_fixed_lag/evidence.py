"""Source-bound contour hypotheses and anonymous future observations; no identity writes."""
from common import *
import copy
import math
import numpy as np

def dice(a, b):
    return float(2 * np.count_nonzero(a & b) / max(1, int(a.sum()) + int(b.sum())))

def endpoint_depth_usable(extract, row, native):
    """Consume DS31.extract's actual DS18 core fields; absent quality is unknown."""
    if not extract: return False
    if extract.get('usable') or any(k in extract for k in ('frame', 'time', 'native')):
        assert (extract.get('frame'), extract.get('time'), extract.get('native')) == (row['frame'], row['time'], native), 'Wrong or future current depth fact'
    quality = extract.get('quality', {})
    required = ('core_eligible_single', 'core_quality_usable', 'exclusive_native_sources',
        'unverified_source_n', 'core_multilayer', 'whole_multilayer',
        'independent_source_n', 'fraction_of_original_core')
    if not extract.get('usable') or any(k not in quality for k in required): return False
    scalars = [quality['independent_source_n'], quality['fraction_of_original_core'], extract.get('z_mm'),
        extract.get('mad_mm'), extract.get('scale_mm')]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in scalars): return False
    return bool(quality['core_eligible_single'] and quality['core_quality_usable'] and
        quality['exclusive_native_sources'] and quality['unverified_source_n'] == 0 and
        not quality['core_multilayer'] and not quality['whole_multilayer'] and
        quality['independent_source_n'] >= 16 and quality['fraction_of_original_core'] >= .2 and
        extract['z_mm'] > 0 and extract['mad_mm'] >= 0 and 0 < extract['scale_mm'] <= 60.)

def depth_fact_binding(extract):
    return {key:copy.deepcopy((extract or {}).get(key)) for key in
        ('fact_id', 'certificate_fact_id', 'certificate_sha256', 'roi_binding',
         'selected_source_index_binding', 'frame', 'time', 'native')}

class ContourMemory:
    def __init__(self, namespace):
        self.namespace, self.tracks, self.prior_masks = namespace, {}, {}
        self.source_frames, self.generations = {}, {}
        self.frame = 0

    def advance(self, row, pair):
        assert row['frame'] == self.frame + 1
        self.frame = row['frame']
        self.prior_masks = {}
        for k, track in list(self.tracks.items()):
            if row['time'] - track['time'] > CFG['track_expiry_seconds']:
                self.tracks.pop(k); continue
            self.prior_masks[k] = track['mask'].copy()
            if pair is not None:
                track['mask'] = pair.warp_forward(track['mask'])
                track['reliable'] = pair.warp_forward(track['reliable'], quality=True)
            else:
                # No frame-to-frame measurement must not retain fake reliable support.
                track['reliable'] = np.zeros_like(track['reliable'])
            track['at_frame'] = row['frame']

    def observe(self, row, masks, branch, extracts=None):
        """Only the original engine's actual clean bank write establishes an anchor."""
        f = row['frame']; obs = {o['id']: o for o in row['observations']}
        assert f == self.frame and set(masks) == set(obs)
        for n in masks:
            if self.source_frames.get(n) != f - 1:
                self.generations[n] = self.generations.get(n, 0) + 1
        for k, h in branch.engine.bank.items():
            anchor = h.get('anchor')
            if not anchor or anchor['frame'] != f: continue
            n = anchor['native_id']
            if n not in masks or obs[n].get('neighbors') or branch.previous.get(n) != k or not branch.engine.quality(obs[n]): continue
            assert anchor == dict(frame=f, native_id=n, mask=obs[n]['mask'], canonical_id=k)
            pre_extract = (extracts or {}).get(n)
            pre_usable = endpoint_depth_usable(pre_extract, row, n)
            self.tracks[k] = dict(anchor=copy.deepcopy(anchor), time=row['time'],
                namespace=self.namespace, generation=self.generations[n],
                public_epoch=branch.epochs.get(n, 0), mask=masks[n].copy(),
                reliable=masks[n].copy(), at_frame=f,
                anchor_depth_extract=copy.deepcopy(pre_extract), anchor_depth_usable=pre_usable)
        self.source_frames.update({n:f for n in masks})

    def capture(self, request, checkpoint, pair):
        output = {}
        for k in request['targets']:
            anchor = checkpoint.engine.bank.get(k, {}).get('anchor')
            track = self.tracks.get(k)
            if not track or track['anchor'] != anchor or track['at_frame'] != request['frame']:
                output[k] = dict(status='UNKNOWN', reason='NO_EXACT_CURRENT_BANK_ANCHOR_CONTOUR')
                continue
            assert anchor['frame'] < request['frame'] and track['time'] < request['time'], 'Noncausal bank anchor'
            depth_mask, depth_summary = (pair.point_support(self.prior_masks[k])
                if pair is not None and k in self.prior_masks else
                (np.zeros((360,640), bool), dict(status='UNKNOWN', reasons=['NO_ACTUAL_PAIR'])))
            output[k] = dict(status='SOURCE_BOUND_CONTOUR_HYPOTHESIS',
                anchor=copy.deepcopy(anchor), namespace=self.namespace,
                generation=track['generation'], public_epoch=track['public_epoch'],
                mask=track['mask'].copy(), reliable=track['reliable'].copy(),
                depth_mask=depth_mask, depth_summary=depth_summary,
                anchor_time=track['time'], anchor_depth_usable=track['anchor_depth_usable'],
                anchor_depth_quality=copy.deepcopy((track['anchor_depth_extract'] or {}).get('quality', {})),
                anchor_depth_fact_binding=depth_fact_binding(track['anchor_depth_extract']),
                target_bank_anchor=copy.deepcopy(anchor),
                action_reference_anchors=[copy.deepcopy(e.get('action_reference_anchor'))
                    for e in request.get('candidate_edges', []) if e['public_id'] == k],
                reference_contract='EXACT_CHECKPOINT_BANK_ANCHOR_NOT_ACTION_REFERENCE_SUBSTITUTION')
        return output

class WindowEvidence:
    def __init__(self, request, targets, use_depth):
        self.request, self.targets, self.use_depth = copy.deepcopy(request), copy.deepcopy(targets), use_depth
        self.samples, self.broken = [], False
        self.previous_frame = request['frame'] - 1

    def update(self, row, masks, profiles, pair, extracts, quality):
        assert row['frame'] == self.previous_frame + 1
        assert row['frame'] <= self.request['frame'] + CFG['lag_frames']
        assert math.isfinite(row['time'])
        assert row['time'] == self.request['time'] if not self.samples else row['time'] > self.samples[-1]['time']
        obs = {o['id']: o for o in row['observations']}
        assert len(obs) == len(row['observations']) and set(obs) == set(masks)
        if row['frame'] > self.request['frame']:
            for target in self.targets.values():
                if target['status'] != 'SOURCE_BOUND_CONTOUR_HYPOTHESIS': continue
                before = target['mask']
                if pair is None:
                    target['depth_mask'] = np.zeros_like(before)
                    target['depth_summary'] = dict(status='UNKNOWN', reasons=['NO_ACTUAL_PAIR'])
                    target['reliable'] = np.zeros_like(target['reliable'])
                else:
                    target['depth_mask'], target['depth_summary'] = pair.point_support(before)
                    target['mask'] = pair.warp_forward(before)
                    target['reliable'] = pair.warp_forward(target['reliable'], quality=True)
        sources = self.request['sources']
        if any(n not in masks for n in sources): self.broken = True
        clean = not self.broken and all(n in profiles and n in obs and quality(obs[n])
            and not obs[n].get('neighbors') for n in sources)
        comparisons = {}
        for n in sources:
            current_depth = extracts.get(n) or {}
            endpoint = endpoint_depth_usable(current_depth, row, n)
            for k, target in self.targets.items():
                key = f'{n}:{k}'
                result = dict(native=n, public=k, frame=row['frame'], status='UNKNOWN',
                    source_depth_quality=copy.deepcopy(current_depth.get('quality', {})))
                if n not in masks or target['status'] != 'SOURCE_BOUND_CONTOUR_HYPOTHESIS':
                    result['reason'] = 'MISSING_CURRENT_SOURCE_OR_ANCHOR'; comparisons[key] = result; continue
                predicted, trusted = target['mask'], target['reliable']
                fraction = int(trusted.sum()) / max(1, int(predicted.sum()))
                available = int(trusted.sum()) >= CFG['flow']['min_correspondences'] and fraction >= CFG['min_reliable_contour_fraction']
                support = target['depth_mask']
                depth_available = (target['depth_summary']['status'] == 'AVAILABLE_CONDITIONAL_3D_SUPPORT'
                    and target.get('anchor_depth_usable', False) and endpoint
                    and int(support.sum()) >= CFG['flow']['min_correspondences'])
                depth_affinity = float(np.count_nonzero(support & masks[n]) / max(1, int(support.sum()))) if depth_available else None
                # SELF is evidence-based rejection only if the retained historical
                # contour has reliable visible support in another current mask.
                elsewhere = max((dice(trusted, m) for other, m in masks.items()
                    if other != n and other in profiles and quality(obs[other]) and not obs[other].get('neighbors')), default=0.)
                result.update(status='AVAILABLE_CONDITIONAL_RGB_CONTOUR' if available else 'UNKNOWN',
                    reason=None if available else 'INSUFFICIENT_CUMULATIVE_VISIBLE_CORRESPONDENCE',
                    rgb_dice=dice(predicted, masks[n]), reliable_fraction=fraction,
                    predicted_area=int(predicted.sum()), reliable_area=int(trusted.sum()),
                    predicted_mask_binding=array_hash(predicted), trusted_mask_binding=array_hash(trusted),
                    current_mask_binding=array_hash(masks[n]), depth_available=depth_available,
                    depth_affinity=depth_affinity, depth_support=copy.deepcopy(target['depth_summary']),
                    target_visible_elsewhere_dice=elsewhere, actual_reference=copy.deepcopy(target['anchor']),
                    target_bank_anchor=copy.deepcopy(target.get('target_bank_anchor', target['anchor'])),
                    anchor_depth_usable=target.get('anchor_depth_usable', False),
                    anchor_depth_quality=copy.deepcopy(target.get('anchor_depth_quality', {})),
                    anchor_depth_fact_binding=copy.deepcopy(target.get('anchor_depth_fact_binding')),
                    action_reference_anchors=copy.deepcopy(target.get('action_reference_anchors', [])),
                    actual_current_observation=dict(frame=row['frame'], time=row['time'], native=n,
                        mask=obs[n]['mask'], neighbors=list(obs[n].get('neighbors', [])), original_quality=bool(quality(obs[n]))),
                    current_depth_fact_binding=depth_fact_binding(current_depth),
                    anonymous_raw_current_observation=True, candidate_identity_not_certified_by_confirmation=True,
                    elsewhere_support_requires_reliable_prediction_and_clean_raw_observation=True,
                    propagated_contour_is_hypothesis=True, physical_identity='UNKNOWN')
                comparisons[key] = result
        self.samples.append(dict(frame=row['frame'], time=row['time'], clean=clean,
            source_generation_broken=self.broken, comparisons=comparisons))
        self.previous_frame = row['frame']

    def assess(self, options):
        count = CFG['confirmation_clean_frames']
        last = self.samples[-count:]
        result = dict(status='WAIT', scores=[], evidence_max_frame=self.previous_frame,
            sources=self.request['sources'], confirmation_frames=[s['frame'] for s in last],
            source_generation_broken=self.broken, depth_common_component_weight=0.)
        if len(last) != count or not all(s['clean'] for s in last): return result
        if any(c['status']=='UNKNOWN' for s in last for c in s['comparisons'].values()):
            result.update(status='UNKNOWN_KEEP', reason='NO_RELIABLE_COMMON_CONTOUR_EVIDENCE'); return result
        depth_common = self.use_depth and all(c['depth_available'] for s in last for c in s['comparisons'].values())
        weight = CFG['depth_weight'] if depth_common else 0.
        result['depth_common_component_weight'] = weight
        for option in options:
            terms=[]; valid=True
            for sample in last:
                for n in self.request['sources']:
                    k = option['mapping'][n]
                    if k == n and k not in self.request['targets']:
                        edges=[c for c in sample['comparisons'].values() if c['native']==n]
                        # Unknown or invisible old fish never favors a new identity.
                        if not edges or any(c['target_visible_elsewhere_dice']<CFG['min_contour_dice'] for c in edges):
                            valid=False; break
                        affinities=[(1-weight)*c['rgb_dice']+weight*(c['depth_affinity'] or 0.) for c in edges]
                        terms.append(1.-max(affinities))
                    else:
                        c=sample['comparisons'][f'{n}:{k}']
                        value=(1-weight)*c['rgb_dice']+weight*(c['depth_affinity'] or 0.)
                        if value<CFG['min_contour_dice']: valid=False; break
                        terms.append(value)
                if not valid: break
            result['scores'].append(dict(id=option['id'], available=valid,
                score=float(np.mean(terms)) if valid and terms else None))
        available=sorted((s for s in result['scores'] if s['available']),key=lambda s:(-s['score'],s['id']!='KEEP',s['id']))
        if not available:
            result.update(status='UNKNOWN_KEEP',reason='NO_SUPPORTED_IDENTITY_EXPLANATION');return result
        winner=available[0]; runner=available[1]['score'] if len(available)>1 else 0.
        margin=winner['score']-runner
        selected=winner['id'] if margin>=CFG['min_joint_margin'] else 'KEEP'
        result.update(status='DECIDED',selected_option=selected,winning_margin=margin,
            reason='SUPPORTED_JOINT_EXPLANATION' if selected!='KEEP' else 'ORIGINAL_OR_AMBIGUOUS_KEEP')
        return result

    def numeric(self):
        return dict(request=copy.deepcopy(self.request), samples=copy.deepcopy(self.samples),
            use_depth=self.use_depth, evidence_max_frame=self.previous_frame,
            future_policy='ONLY_UNPUBLISHED_FIXED_30_FRAME_WINDOW', no_assumed_public_labels_in_post=True)
