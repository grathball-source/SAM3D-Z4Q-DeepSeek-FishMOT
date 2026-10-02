"""Post-seal private raw-depth/actual-publication comparison; no RGB/GT pixels."""
from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict

from common import HERE, RUN, SEGMENTS, ARMS, artifact, input_dir, read, verify_item, write_new
from source import RawDepth, native_masks, FIELD_READS

DISPLAY_ARMS = ('Z4Q_FROZEN', 'R12_RAW', 'Z4Q_DEPTH')


def verify_seals():
    """Read every branch/segment seal before any source pixels or plot selection."""
    all_path = RUN / 'ALL_PREDICTIONS_SEALED.json'
    all_seal = read(all_path)
    assert all_seal['status'] in ('ALL_FIVE_BRANCHES_EIGHT_SEGMENTS_SEALED',
                                  'ALL_PREDICTIONS_AND_ACCESS_SEALED')
    assert tuple(all_seal['arms']) == ARMS and set(all_seal['seals']) == set(SEGMENTS)
    assert set(all_seal['access_seals']) == set(SEGMENTS)
    assert all_seal['frames'] == sum(b-a+1 for a, b in SEGMENTS.values()) == 20098
    seals = {}
    for name, (first, last) in SEGMENTS.items():
        public = RUN / name / 'public'
        verify_item(all_seal['seals'][name]); verify_item(all_seal['access_seals'][name])
        seal = read(public / 'PREDICTIONS_SEALED.json')
        assert tuple(seal['arms']) == ARMS and seal['frames'] == seal['published_frames'] == last-first+1
        assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        assert artifact(public / 'predictions.jsonl.gz')['sha256'] == seal['artifacts_sha256']['predictions.jsonl.gz']
        assert artifact(public / 'EVENTS.json')['sha256'] == seal['artifacts_sha256']['EVENTS.json']
        freeze = read(public / 'FREEZE.json')
        assert freeze['no_gt_before_seal'] and freeze['new_model_http'] == freeze['model_cost_usd'] == 0
        for path, digest in freeze['code_sha256'].items():
            assert artifact(path)['sha256'] == digest, path
        seals[name] = dict(prediction_seal=artifact(public / 'PREDICTIONS_SEALED.json'),
                           access_seal=artifact(public / 'ACCESS.json'))
    metrics = read(RUN / 'METRICS.json')
    assert metrics['status'] == 'SCORED_AFTER_ALL_FIVE_ARMS_EIGHT_SEALS'
    assert metrics['all_seal'] == artifact(all_path)
    provenance = read(RUN / 'SCORE_PROVENANCE.json')
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_predictions']
    verify_item(provenance['scoring_freeze'])
    assert read(RUN / 'SCORING_FREEZE.json')['status'] == 'ALL_SEALS_VERIFIED_BEFORE_REFERENCE_SCORING'
    return dict(all_prediction_seal=artifact(all_path), segment_seals=seals,
                metrics=artifact(RUN / 'METRICS.json'), scoring_provenance=artifact(RUN / 'SCORE_PROVENANCE.json'))


def selected_rows(path, wanted):
    """Hash actual uncompressed row bytes as well as the complete saved file."""
    selected = {}
    with gzip.open(path, 'rb') as stream:
        for line in stream:
            row = json.loads(line)
            if row['frame'] in wanted:
                body = json.dumps(row, separators=(',', ':'), allow_nan=False).encode('utf-8')
                selected[row['frame']] = (row, dict(
                    uncompressed_row_bytes_sha256=hashlib.sha256(line).hexdigest(),
                    canonical_json_body_sha256=hashlib.sha256(body).hexdigest(),
                    canonical_json_lf_sha256=hashlib.sha256(body+b'\n').hexdigest()))
    assert set(selected) == set(wanted), (str(path), sorted(set(wanted)-set(selected)))
    return selected


def mapping(row, arm):
    return {int(x['mask'][2:]): x['id'] for x in row['variants'][arm]}


def cases_after_score():
    """Fixed prior failures plus actual new branch errors, selected after scoring."""
    cases = {}

    def add(name, q, tag, sources=()):
        key = (name, q)
        case = cases.setdefault(key, dict(segment=name, q=q, tags=[], seed_sources=set()))
        if tag not in case['tags']: case['tags'].append(tag)
        case['seed_sources'].update(int(n) for n in sources)

    add('fishsa_development_8400', 4524, 'PRIOR_DS14_WRONG_GROUP')
    add('L3', 1421, 'PRIOR_DS14_WRONG_GROUP_WEAK_REFERENCE')
    add('fishsa_development_8400', 3902, 'POSTSCORE_LOST_ORIGINAL_BIRTH_REFINE', (7, 4))
    add('fishsa_validation_2888', 2188, 'POSTSCORE_LOST_ORIGINAL_BIRTH_REFINE_GLOBAL11488', (8, 7, 1))
    add('L3', 669, 'POSTSEAL_NEW_DEPTH_BIRTH_GLOBAL668_UNSCORABLE_NEITHER_SUCCESS_NOR_SAFE', (19, 18))
    add('L3', 735, 'POSTSEAL_NEW_DEPTH_BIRTH_GLOBAL734_UNSCORABLE_NEITHER_SUCCESS_NOR_SAFE', (21, 20))
    add('LW', 2065, 'POSTSEAL_NEW_DEPTH_BIRTH_GLOBAL2064_UNSCORABLE_NEITHER_SUCCESS_NOR_SAFE', (88, 85))
    feeding = 'feeding_001201_001906'
    row = selected_rows(RUN / feeding / 'public/predictions.jsonl.gz', {686})[686][0]
    maps = [mapping(row, arm) for arm in DISPLAY_ARMS]
    differing = {n for n in maps[0] if len({m[n] for m in maps}) > 1}
    if differing:
        add(feeding, 686, 'FIXED_NEW_BIRTH_GLOBAL1886_PUBLICATION_DIFFERENCE', differing)
    for name in SEGMENTS:
        public = RUN / name / 'public'
        audit = read(public / 'EVENT_AUDIT.json')['arms']
        depth = audit['Z4Q_DEPTH']
        for event in depth['group_events']:
            if event.get('restore_status') == 'COMMIT' and (
                    event['physical'] == 'WRONG' or event.get('committed_pre_consensus_verdict') == 'WRONG'):
                add(name, event['q'], 'POSTSEAL_DEPTH_GROUP_WRONG_' + event['physical'],
                    event['actual_first_public_mapping'])
        for event in depth['birth_commits']:
            if event['physical'] == 'WRONG':
                add(name, event['frame'], 'POSTSEAL_DEPTH_BIRTH_WRONG', [event['source']])
        automatic = read(public / 'AUTOMATIC_RECONNECT_AUDIT.json')['arms']['Z4Q_DEPTH']
        for event in automatic:
            if event['physical'] == 'WRONG' and event['applied_at_first_publication']:
                add(name, event['frame'], 'POSTSEAL_DEPTH_AUTOMATIC_WRONG', [event['source']])
        events = read(public / 'EVENTS.json')
        for case in [c for c in cases.values() if c['segment'] == name]:
            for arm in ('R12_RAW', 'Z4Q_SHARED', 'Z4Q_DEPTH'):
                for event in events[arm]:
                    if event.get('q') == case['q']:
                        case['seed_sources'].update(event['member_sources'])
                        case['seed_sources'].add(event['group_source'])
                        case['seed_sources'].update(int(n) for n in event['post_first_observations'])
    return sorted(cases.values(), key=lambda c: (list(SEGMENTS).index(c['segment']), c['q']))


def context_crop(frames, seeds):
    """Common three-frame crop includes event roles and nearby native context."""
    import numpy as np
    bounds = {}
    for data in frames.values():
        for n, mask in data['masks'].items():
            yy, xx = np.nonzero(mask)
            box = (int(xx.min()), int(yy.min()), int(xx.max()+1), int(yy.max()+1))
            if n in bounds:
                a = bounds[n]; box = (min(a[0], box[0]), min(a[1], box[1]), max(a[2], box[2]), max(a[3], box[3]))
            bounds[n] = box
    present = set(seeds) & set(bounds)
    assert present, 'No actual native mask for event sources'
    def union(keys):
        return (min(bounds[n][0] for n in keys), min(bounds[n][1] for n in keys),
                max(bounds[n][2] for n in keys), max(bounds[n][3] for n in keys))
    x0, y0, x1, y1 = union(present)
    nearby = {n for n, b in bounds.items() if b[2] >= x0-24 and b[0] <= x1+24
              and b[3] >= y0-24 and b[1] <= y1+24}
    x0, y0, x1, y1 = union(nearby | present)
    return (max(0, x0-16), max(0, y0-16), min(640, x1+16), min(360, y1+16)), present, nearby-present


def main():
    seals = verify_seals()
    assert not (HERE / 'PRIVATE_VISUALS.json').exists(), 'Existing figures must be preserved'
    cases = cases_after_score()
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import patheffects
    grouped = defaultdict(list)
    for case in cases: grouped[case['segment']].append(case)
    inventory = []
    for name, segment_cases in grouped.items():
        public = RUN / name / 'public'
        maximum = SEGMENTS[name][1]-SEGMENTS[name][0]+1
        wanted = {f for c in segment_cases for f in (c['q']-1, c['q'], c['q']+1) if 1 <= f <= maximum}
        prediction_path = public / 'predictions.jsonl.gz'
        assignment_path = input_dir(name) / 'assignments.jsonl.gz'
        predictions = selected_rows(prediction_path, wanted)
        assignments = selected_rows(assignment_path, wanted)
        ledger = {r['frame']: r for r in read_ledger(public / 'PUBLISH_LEDGER.jsonl') if r['frame'] in wanted}
        reader = RawDepth(name)
        frames = {}
        try:
            for frame in sorted(wanted):
                row, row_hash = predictions[frame]
                assignment, assignment_hash = assignments[frame]
                assert ledger[frame]['prediction_row_sha256'] == row_hash['canonical_json_lf_sha256']
                assert assignment['frame'] == row['frame']
                assert assignment['global_frame_id'] == row['global_frame']
                assert assignment['time'] == row['time']
                masks = native_masks(assignment)
                assert all(set(mapping(row, arm)) == set(masks) for arm in DISPLAY_ARMS)
                raw, _, _, binding = reader(row['global_frame'], row['time'])
                frames[frame] = dict(prediction=row, prediction_row_hashes=row_hash,
                    assignment_row_hashes=assignment_hash, masks=masks, depth=raw,
                    source_binding=binding)
        finally:
            reader.close()
        for case in segment_cases:
            points = [f for f in (case['q']-1, case['q'], case['q']+1) if f in frames]
            shown = {f: frames[f] for f in points}
            crop, seeds, context = context_crop(shown, case['seed_sources'])
            x0, y0, x1, y1 = crop
            valid = np.concatenate([d['depth'][y0:y1, x0:x1].ravel() for d in shown.values()])
            valid = valid[np.isfinite(valid) & (valid > 0)]
            lo, hi = np.percentile(valid, [2, 98]) if len(valid) else (0., 1.)
            if hi <= lo: hi = lo+1.
            color = {n: plt.get_cmap('tab10')(i % 10) for i, n in enumerate(sorted(seeds))}
            fig, axes = plt.subplots(len(points), len(DISPLAY_ARMS), figsize=(16, 10), squeeze=False)
            cmap = plt.get_cmap('viridis').copy(); cmap.set_bad('#343434')
            for y, frame in enumerate(points):
                data = frames[frame]; row = data['prediction']
                for x, arm in enumerate(DISPLAY_ARMS):
                    ax = axes[y, x]
                    image = ax.imshow(np.ma.masked_where(~np.isfinite(data['depth']) | (data['depth'] <= 0),
                        data['depth']), cmap=cmap, vmin=lo, vmax=hi, interpolation='nearest')
                    ids = mapping(row, arm)
                    for n in sorted((seeds | context) & set(data['masks'])):
                        mask = data['masks'][n]; yy, xx = np.nonzero(mask)
                        c = color.get(n, '#d0d0d0'); lw = 1.6 if n in seeds else .7
                        ax.contour(mask, levels=[.5], colors=[c], linewidths=lw)
                        label = ax.text(float(xx.mean()), float(yy.mean()), f'n{n} / ID{ids[n]}',
                            color=c, fontsize=9 if n in seeds else 7, weight='bold' if n in seeds else 'normal',
                            ha='center', va='center', clip_on=True)
                        label.set_path_effects([patheffects.withStroke(linewidth=2.3, foreground='#101010')])
                    ax.set_xlim(x0-.5, x1-.5); ax.set_ylim(y1-.5, y0-.5)
                    ax.set_title(f'{arm} | local {frame} / original {row["global_frame"]}', fontsize=10)
                    ax.set_xticks([]); ax.set_yticks([])
            fig.subplots_adjust(left=.025, right=.91, bottom=.06, top=.89, wspace=.08, hspace=.16)
            fig.colorbar(image, cax=fig.add_axes([.93, .15, .016, .62]), label='Original raw depth (mm)')
            fig.suptitle(f'{name} | q={case["q"]} | q-1 / q / q+1\n'
                'Actual published IDs; common raw depth and native masks; no RGB or reference pixels', fontsize=12)
            fig.text(.025, .025, '; '.join(case['tags']) + ' | Gray contours: nearby native context', fontsize=8)
            path = HERE / 'private/visuals' / f'{name}_q{case["q"]}_actual_ids.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as output: fig.savefig(output, format='png', dpi=150)
            plt.close(fig)
            qrow = frames[case['q']]['prediction']
            qmaps = {a: mapping(qrow, a) for a in DISPLAY_ARMS}
            inventory.append(dict(segment=name, q=case['q'], global_q=qrow['global_frame'], tags=case['tags'],
                frames=points, display_arms=list(DISPLAY_ARMS), crop_xyxy=list(crop), seed_sources=sorted(seeds),
                anonymous_context_sources=sorted(context), depth_display_limits_mm=[float(lo), float(hi)],
                actual_q_publications={a: {str(n): m[n] for n in sorted(seeds) if n in m} for a, m in qmaps.items()},
                differs_from_original_z4q_at_q=any(qmaps['Z4Q_DEPTH'][n] != qmaps['Z4Q_FROZEN'][n]
                    for n in seeds if n in qmaps['Z4Q_DEPTH']), artifact=artifact(path),
                prediction_file=artifact(prediction_path), assignment_file=artifact(assignment_path),
                event_audit=artifact(public / 'EVENT_AUDIT.json'), frames_provenance=[dict(frame=f,
                    global_frame=frames[f]['prediction']['global_frame'],
                    prediction_row_hashes=frames[f]['prediction_row_hashes'],
                    assignment_row_hashes=frames[f]['assignment_row_hashes'],
                    actual_mapping={a: {str(n): mapping(frames[f]['prediction'], a)[n]
                        for n in sorted(seeds | context) if n in frames[f]['masks']} for a in DISPLAY_ARMS},
                    raw_source_binding=frames[f]['source_binding']) for f in points]))
    write_new(HERE / 'PRIVATE_VISUALS.json', dict(status='POSTSEAL_POSTSCORE_ACTUAL_PUBLICATION_VISUALS',
        selection='Two fixed DS14 failures; two scored lost original BIRTH_REFINE cases; three scored unscorable additional depth births; fixed Feeding1886 if changed; all actual Z4Q_DEPTH wrong commits after scoring',
        cases=inventory, seals_verified_before_pixels=seals, source_field_reads=FIELD_READS,
        row_hash_contract='Actual uncompressed gzip row bytes, canonical JSON body, and canonical JSON plus LF are bound separately; ledger validates canonical JSON plus LF',
        RGB_pixels_read=False, GT_pixels_read=False, restored_depth_read=False, private_images_not_for_git=True,
        GT_postseal_verdict_used_for_case_selection_only=True, future_display_frames_not_prediction_input=True,
        new_model_http=0, cost_usd=0, visualizer=artifact(__file__)))
    print('Private actual ID comparison figures:', len(inventory), flush=True)


def read_ledger(path):
    import json
    with path.open('r', encoding='utf-8') as stream:
        for line in stream: yield json.loads(line)


if __name__ == '__main__':
    main()
