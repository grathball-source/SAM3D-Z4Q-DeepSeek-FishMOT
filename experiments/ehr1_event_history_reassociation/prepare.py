"""Freeze five causal event-history packets from existing predicted observations.

No scoring key, GT stream, previous model response, or future frame is opened here.
Run on the authorized source host; restricted media and sender plan stay off Git.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path

AO1 = Path('/home/xiongxiong/ao1_input_fidelity_20260924/range_corrected_run')
M2 = Path('/home/xiongxiong/m2t_motion_first_20260924/full_run')
VAL = Path('/home/xiongxiong/deepseek_z4q_closedloop_20260923_side/inputs')
DEV_OBS = Path('/home/xiongxiong/dmot-experiments/sam3_depth_failure_repair_20260917/diagnosis/observations_development.jsonl.gz')
DEV_DEPTH = Path('/home/xiongxiong/dmot-experiments/sam3_depth_birth_inherit_20260917/features_r2/features_development.jsonl.gz')
ARMS = ('E', 'H-2D', 'H-D', 'H-D-REPEAT', 'H-D-PERMUTE')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def put(path, value):
    path = Path(path)
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def stream(path, lo, hi):
    result = {}
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            if lo <= row['frame'] <= hi:
                assert row['frame'] not in result
                result[row['frame']] = row
    assert hi in result and lo in result, (path, lo, hi)
    return result


def item(row, native):
    return next((o for o in row['observations'] if o['id'] == native), None)


def measured(frame, obs, features, native, role, with_depth):
    o = item(obs[frame], native)
    if o is None:
        return None
    box = o['box']
    result = dict(fact_id=f'{role}-F{frame}', epistemic_type='ESTIMATE',
                  source_frame=frame, source_time_seconds=obs[frame]['time'],
                  source_observation=f'{role}-predicted-mask-at-F{frame}',
                  coordinate_system='fixed_full_640x360_mask_image', unit='px',
                  bbox_center_px=[round((box[0]+box[2])/2, 3), round((box[1]+box[3])/2, 3)],
                  bbox_px=box, area_px=o['area'], neighbor_count=len(o.get('neighbors', [])),
                  quality=dict(presence=o.get('presence'), predicted_mask_area_px=o['area']))
    if with_depth:
        f = features.get(frame)
        d = None if f is None else item(f, native)
        result['depth'] = dict(epistemic_type='UNKNOWN', reason='NO_ALIGNED_PROFILE') if d is None else dict(
            epistemic_type='MEASUREMENT', source='existing_raw_depth_profile_stream',
            source_frame=frame, source_time_seconds=f['time'], raw_array_sha256=f.get('raw_array_sha256'),
            sensor_available=f.get('sensor_available'), unit='pipeline_mm_unverified_absolute_calibration',
            core={k: d.get('core', {}).get(k) for k in ('median', 'mad', 'q25', 'q75', 'n', 'valid_fraction')},
            whole={k: d.get('whole', {}).get(k) for k in ('median', 'mad', 'q25', 'q75', 'n', 'valid_fraction')},
            overlap_pixels=d.get('overlap_pixels'), neighbors=d.get('neighbors'),
            synchronized=(f['frame'] == frame and f['time'] == obs[frame]['time']))
    return result


def fit(points):
    clean = [p for p in points if p is not None and p['neighbor_count'] == 0 and p['area_px'] > 0]
    if len(clean) < 3:
        return dict(epistemic_type='UNKNOWN', reason='FEWER_THAN_THREE_CLEAN_DISTINCT_TIMES', count=len(clean))
    times = [p['source_time_seconds'] for p in clean]
    if len(set(times)) < 3 or any(b-a > .2 for a, b in zip(times, times[1:])):
        return dict(epistemic_type='UNKNOWN', reason='NONCONTIGUOUS_OR_DUPLICATE_TIME', count=len(clean))
    t0 = sum(times)/len(times)
    den = sum((t-t0)**2 for t in times)
    xy = [p['bbox_center_px'] for p in clean]
    center = [sum(v[i] for v in xy)/len(xy) for i in (0, 1)]
    velocity = [sum((t-t0)*(v[i]-center[i]) for t, v in zip(times, xy))/den for i in (0, 1)]
    residual = math.sqrt(sum(sum((v[i]-center[i]-velocity[i]*(t-t0))**2 for i in (0, 1))
                             for t, v in zip(times, xy))/len(clean))
    speed = math.hypot(*velocity)
    return dict(epistemic_type='ESTIMATE', source_fact_ids=[p['fact_id'] for p in clean],
                time_interval_seconds=[times[0], times[-1]], method='ordinary_least_squares_bbox_centers',
                velocity_px_per_s=[round(v, 3) for v in velocity], speed_px_per_s=round(speed, 3),
                motion_direction_image_radians=None if speed < 2 else round(math.atan2(velocity[1], velocity[0]), 4),
                direction_reason='LOW_SPEED' if speed < 2 else None,
                residual_rms_px=round(residual, 3), samples=len(clean))


def role_segment(role, frames, native, obs, features, depth):
    vals = [measured(f, obs, features, native, role, depth) for f in frames if f in obs]
    vals = [x for x in vals if x is not None]
    recent = vals[-16:]
    return dict(role=role, hypothesis='native continuity within this bounded clean segment only',
                observations=vals, observed_count=len(vals),
                first_sample_frame=vals[0]['source_frame'] if vals else None,
                last_sample_frame=vals[-1]['source_frame'] if vals else None,
                velocity=fit(recent))


def build_case(case, m2, ledger, obs, features, card):
    alias, q, trigger = case['case_alias'], case['query_frame'], case['trigger_frame']
    assert q == m2['query_frame']
    before = {r: [x for x in case['V1']['roles'] if x['role'] == r] for r in 'ABXY'}
    native = {r: int(before[r][-1]['native_mask_key'].split(':')[1]) for r in 'ABXY'}
    pre_start = max(min(obs), trigger-30)
    # A one-second causal snapshot; an old AO1 reference is retained separately as stale evidence.
    pre = {r: role_segment(r, range(pre_start, trigger), native[r], obs, features, True) for r in 'AB'}
    for r in 'AB':
        if not pre[r]['observations']:
            older = [measured(x['frame'], obs, features, native[r], r, True) for x in before[r] if x['frame'] < trigger]
            pre[r] = dict(role=r, hypothesis='stale frozen pre-event reference only; no certified bridge to event',
                          observations=[x for x in older if x], observed_count=len([x for x in older if x]),
                          first_sample_frame=None, last_sample_frame=None,
                          velocity=fit([x for x in older if x]))
    post_start = min(x['frame'] for r in 'XY' for x in before[r])
    post = {r: role_segment(r, range(max(trigger+1, q-15, post_start), q+1), native[r], obs, features, True) for r in 'XY'}
    def clean_pair(f):
        x, y = item(obs[f], native['X']), item(obs[f], native['Y'])
        return bool(x and y and x['area'] and y['area'] and not x.get('neighbors') and not y.get('neighbors'))
    unavailable = next((f for f in range(trigger, q+1) if not clean_pair(f)), None)
    return_start = next((f for f in range((unavailable or trigger)+1, q-1)
                         if all(clean_pair(t) for t in (f, f+1, f+2))), None)
    visibility = dict(epistemic_type='ESTIMATE', rule='predicted X/Y masks both present and contact-free for 3 consecutive actual frames',
                      first_unavailable_frame=unavailable, first_clean_pair_streak=None if return_start is None else [return_start, return_start+2],
                      identity_across_gap='UNKNOWN', event_time_order_if_intervals_overlap='UNKNOWN')
    anchors = {r: dict(frame=before[r][-1]['frame'], source_observation=f'{r}-predicted-mask-at-F{before[r][-1]["frame"]}',
                       status='OLDER_REFERENCE_HYPOTHESIS' if before[r][-1]['frame'] < pre_start else 'PRE_EVENT_REFERENCE',
                       provenance='frozen_AO1_V1_role_not_GT') for r in 'AB'}
    # This conservative trigger is measurable in predictions and is not selected by GT.
    at = obs.get(trigger)
    a = None if at is None else item(at, native['A'])
    b = None if at is None else item(at, native['B'])
    contact = bool(a and b and (native['B'] in a.get('neighbors', []) or native['A'] in b.get('neighbors', [])))
    trig = dict(case=alias, original_frozen_trigger_frame=trigger, frame_time_seconds=None if at is None else at['time'],
                would_trigger=contact, trigger_type='PREDICTED_PAIR_NEIGHBOR_CONTACT' if contact else 'NONE_AT_FROZEN_TRIGGER',
                rule='both frozen pre-event predicted native masks present; either reports the other as neighbor',
                evidence=dict(A_present=bool(a), B_present=bool(b),
                              A_reports_B=None if a is None else native['B'] in a.get('neighbors', []),
                              B_reports_A=None if b is None else native['A'] in b.get('neighbors', []),
                              A_neighbor_count=None if a is None else len(a.get('neighbors', [])),
                              B_neighbor_count=None if b is None else len(b.get('neighbors', []))),
                deployment_status='PREDICTION_DRIVEN_CONTACT_PROXY' if contact else 'OFFLINE_DIAGNOSTIC_CONTROL',
                limitation='Does not assert the original Z4Q proposal gate or an online event state existed')
    g = m2['g_images']
    assert len(g) == len(ledger)
    rows = []
    for image, private in zip(g, ledger, strict=True):
        frame = private['frame']
        assert frame <= q and image['sha256'] == private['image_sha256']
        facts = []
        for x in private['observations']:
            n = int(x['native_mask_key'].split(':')[1])
            y = measured(frame, obs, features, n, x['token'], True)
            if y is not None:
                y['source_observation'] = x['token']
                y['fact_id'] = x['token']
                facts.append(y)
        rows.append(dict(image_id=image['image_id'], source_frame=frame, source_time_seconds=private['source_time'],
                         temporal_part='PRE_HISTORY' if frame < trigger else ('POST_HISTORY_TO_Q' if frame >= post_start else 'INTERACTION_OBSERVATIONS'),
                         observations=facts, no_persistent_identity=True))
    candidates = card['candidate_hypotheses']
    assert len(candidates) == 2 and all(set(c['mapping']) >= {'X', 'Y'} for c in candidates)
    candidates = [dict(id='H1' if c['choice'] == 'C1' else 'H2',
                       mapping=c['mapping'], epistemic_type='HYPOTHESIS',
                       source='frozen_AO1_blind_card_complete_mapping') for c in candidates]
    assert {x['id'] for x in candidates} == {'H1', 'H2'}
    base = dict(request_id=f'EHR1-{alias}', q_frame=q, q_time_seconds=case['query_time'],
                coordinate_system='fixed_full_640x360_image_top_left_origin_y_down',
                role_contract='A/B are frozen pre-event reference hypotheses; X/Y are post-event observed fragments. Same native handle across risk does not prove same physical fish.',
                no_gt_or_future_frames=True, anchors=anchors, trigger=trig,
                visibility_intervals=visibility,
                IMAGE_INDEX=[dict(image_id=x['image_id'], frame=y['frame'], time_seconds=y['source_time'])
                             for x, y in zip(g, ledger, strict=True)],
                PRE_HISTORY=pre, INTERACTION_OBSERVATIONS=[x for x in rows if x['temporal_part'] == 'INTERACTION_OBSERVATIONS'],
                POST_HISTORY_TO_Q=post, hypotheses=candidates,
                unknowns=['identity through contact is unresolved', 'no calibrated water-surface depth',
                          'anonymous intermediate observations are not linked across missing intervals'])
    return base, trig, g


def condition(base, arm):
    packet = json.loads(json.dumps(base))
    if arm == 'E':
        packet['INTERACTION_OBSERVATIONS'] = []
        trigger_frame = packet['trigger']['original_frozen_trigger_frame']
        packet.pop('trigger')
        packet.pop('visibility_intervals')
        for part in ('PRE_HISTORY', 'POST_HISTORY_TO_Q'):
            for x in packet[part].values():
                x['observations'] = x['observations'][-1:]
                for key in ('velocity', 'first_sample_frame', 'last_sample_frame', 'observed_count'):
                    x.pop(key, None)
        pre_image = max((x for x in packet['IMAGE_INDEX'] if x['frame'] < trigger_frame), key=lambda x: x['frame'])
        packet['IMAGE_INDEX'] = [pre_image, packet['IMAGE_INDEX'][-1]]
    if arm in ('E', 'H-2D'):
        for part in ('PRE_HISTORY', 'POST_HISTORY_TO_Q'):
            for x in packet[part].values():
                for o in x['observations']:
                    o.pop('depth', None)
        for frame in packet['INTERACTION_OBSERVATIONS']:
            for o in frame['observations']:
                o.pop('depth', None)
    for part in ('PRE_HISTORY', 'POST_HISTORY_TO_Q'):
        observations = [o for x in packet[part].values() for o in x['observations']]
        for o in observations:
            o.pop('bbox_px', None)
            if 'depth' in o:
                o['depth'].pop('raw_array_sha256', None)
                for key in ('core', 'whole'):
                    if key in o['depth']:
                        o['depth'][key].pop('q25', None)
                        o['depth'][key].pop('q75', None)
    for frame in packet['INTERACTION_OBSERVATIONS']:
        for o in frame['observations']:
            o.pop('bbox_px', None)
            if 'depth' in o:
                o['depth'].pop('raw_array_sha256', None)
                for key in ('core', 'whole'):
                    if key in o['depth']:
                        o['depth'][key].pop('q25', None)
                        o['depth'][key].pop('q75', None)
    if arm == 'H-D-PERMUTE':
        for c in packet['hypotheses']:
            c['id'] = 'H2' if c['id'] == 'H1' else 'H1'
        packet['hypotheses'].reverse()
    packet['condition'] = 'H-D' if arm in ('H-D-REPEAT', 'H-D-PERMUTE') else arm
    return packet


def history_images(images, private, trigger, post_start):
    pairs = list(zip(images, private, strict=True))
    pre = [x for x in pairs if x[1]['frame'] < trigger]
    middle = [x for x in pairs if trigger <= x[1]['frame'] < post_start]
    post = [x for x in pairs if x[1]['frame'] >= post_start]
    assert pre and middle and post
    chosen = pre[-2:] + [middle[round(i*(len(middle)-1)/7)] for i in range(8)] + [post[0], post[-1]]
    names = {x[0]['image_id'] for x in chosen}
    return [x for x in images if x['image_id'] in names]


def main(out):
    ao1 = read(AO1/'public/SOURCE_MANIFEST.json')
    m2 = read(M2/'public/SOURCE_MANIFEST.json')
    ledger = read(M2/'private/TOKEN_LEDGER.json')
    assert [x['case_alias'] for x in ao1['cases']] == [f'B{i:02}' for i in range(1, 6)]
    assert [x['case_alias'] for x in m2['cases']] == [x['case_alias'] for x in ao1['cases']]
    out.mkdir(parents=True, exist_ok=False)
    (out/'sender/media').mkdir(parents=True)
    episodes, triggers, requests = [], [], []
    for case, old in zip(ao1['cases'], m2['cases'], strict=True):
        alias = case['case_alias']
        lo = min(case['v2_window'][0], *(x['frame'] for x in case['V1']['roles']))
        hi = case['query_frame']
        split = case['split']
        op = DEV_OBS if split == 'development' else VAL/'observations_validation.jsonl.gz'
        dp = DEV_DEPTH if split == 'development' else VAL/'features_validation.jsonl.gz'
        obs, depth = stream(op, lo, hi), stream(dp, lo, hi)
        assert sha(op) == ao1['source_stream_sha256'][split+'_observations']
        assert sha(dp) == ({'validation': '91a154246748146896ac846f0bdd934bb67be874fe823124263650e88ad62f0e',
                           'development': '5047adf883c4d7514140a8350ed3141e5e56e51d49d13e61250b55d8a6b93660'}[split])
        card = read(AO1/'blind'/alias/'P1/card.json')
        base, trig, images = build_case(case, old, ledger[alias], obs, depth, card)
        post_start = min(x['frame'] for x in case['V1']['roles'] if x['role'] in 'XY')
        selected_history = history_images(images, ledger[alias], case['trigger_frame'], post_start)
        triggers.append(trig)
        episodes.append(base)
        for image in images:
            src = M2/'sender/media'/image['media_file']
            dst = out/'sender/media'/image['media_file']
            assert src.is_file() and sha(src) == image['sha256']
            if not dst.exists():
                shutil.copyfile(src, dst)
        for arm in ARMS:
            packet = condition(base, arm)
            last_pre = max((x for x in images if ledger[alias][images.index(x)]['frame'] < case['trigger_frame']),
                           key=lambda x: ledger[alias][images.index(x)]['frame'])
            selected = ([last_pre, images[-1]] if arm == 'E' else selected_history)
            keep = {x['image_id'] for x in selected}
            packet['IMAGE_INDEX'] = [x for x in packet['IMAGE_INDEX'] if x['image_id'] in keep]
            for row in packet['INTERACTION_OBSERVATIONS']:
                row['image_sent'] = row['image_id'] in keep
            requests.append(dict(attempt_id=f'{alias}-{arm}', case=alias, arm=arm,
                                 text=json.dumps(packet, separators=(',', ':'), ensure_ascii=False, allow_nan=False),
                                 images=[dict(image_id=x['image_id'], media_file=x['media_file'], sha256=x['sha256'], bytes=x['bytes']) for x in selected]))
    # B01 is tested first; all remaining requests are frozen before that call.
    assert len(requests) == 25
    schedule = [r['attempt_id'] for r in requests]
    put(out/'public/TRIGGER_AUDIT.json', triggers)
    put(out/'public/EPISODE_FACTS.json', episodes)
    put(out/'public/REQUEST_MANIFEST.json', dict(base='0b65e95ce41ef67978fad08fdd098532112b79b4',
        schedule=schedule, requests=[dict(attempt_id=r['attempt_id'], text_sha256=hashlib.sha256(r['text'].encode()).hexdigest(),
                                      image_sha256=[x['sha256'] for x in r['images']]) for r in requests]))
    put(out/'sender/PLAN.json', dict(model='deepseek-flash', max_tokens=65536, cap_usd=3,
                                     reserve_each_usd=.11, smoke_max=1, requests=requests))
    print(json.dumps(dict(cases=5, requests=25, images=len(list((out/'sender/media').iterdir())),
                          triggers=[(x['case'], x['would_trigger']) for x in triggers])))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    main(p.parse_args().out)
