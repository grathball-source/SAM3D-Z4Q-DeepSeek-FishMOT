"""Postscore delta audit against the sealed OLD raw-depth replay."""
from collections import Counter

from run import HERE, px, read


def key(event):
    return (event['segment'], event['frame'], event['gt_id'], event['native_id'],
            event['from_public_id'], event['to_public_id'])


def main():
    old = px.HERE / 'public/SOURCE_OLD'
    differences, annotated_frames = [], []
    observed = changed = 0
    for name in px.SEGMENTS:
        previous = px.rows(old / name / 'PREDICTIONS.jsonl.gz')
        current = px.rows(HERE / 'public' / name / 'PREDICTIONS.jsonl.gz')
        actions = map(__import__('json').loads,
                      (HERE / 'public' / name / 'ACTIONS.jsonl').read_text(encoding='utf-8').splitlines())
        for original, new, action in zip(previous, current, actions, strict=True):
            frame = new['original_frame']
            assert original['original_frame'] == action['original_frame'] == frame
            assert original['masks'] == new['masks']
            raw_map = {x['native_id']: x['public_id'] for x in original['public']}
            frozen = {int(k): int(v) for k, v in new['variants']['Z4Q_FROZEN_V3'].items()}
            pairwise = {int(k): int(v) for k, v in new['variants']['Z4Q_PAIRWISE_V3'].items()}
            assert frozen == pairwise
            edits = {str(n): dict(raw_depth=raw_map[n], v3=frozen[n]) for n in raw_map if frozen[n] != raw_map[n]}
            if edits:
                differences.append(dict(segment=name, frame=frame, changed_public_edges=edits,
                    v3_frozen_accepted=[e for e in action['frozen_events'] if e.get('kind') == 'reconnect' and e.get('accepted')],
                    v3_pairwise_accepted=[e for e in action['pairwise_events'] if e.get('kind') == 'reconnect' and e.get('accepted')]))
            depth = action['depth_audit']
            observed += len(depth['depth_by_native'])
            changed += depth['changed_native_count']
            if depth['provenance_in_prediction_union']['4']:
                annotated_frames.append(dict(segment=name, frame=frame,
                    annotated_predicted_pixels=depth['provenance_in_prediction_union']['4'],
                    changed_public_edges=edits))
    old_switches = read(px.HERE / 'public/SWITCH_LEDGER.json')['source']['SOURCE_OLD']['events']
    new_switches = read(HERE / 'public/SWITCH_LEDGER.json')['switches']['Z4Q_FROZEN_V3']
    before, after = {key(e): e for e in old_switches}, {key(e): e for e in new_switches}
    old_accepted = read(px.HERE / 'public/EDGE_AUDIT.json')['source']['SOURCE_OLD']['accepted_reconnects']
    v3_accepted = read(HERE / 'public/EDGE_AUDIT.json')['accepted_reconnects']
    result = dict(status='POSTSCORE_OLD_RAW_VS_V3_DIAGNOSTIC',
        frame_differences=differences,
        frames_with_changed_publication=len(differences),
        changed_depth_observations=changed, observed_native_instances=observed,
        provenance4_prediction_pixels=annotated_frames,
        removed_switches=[before[k] for k in sorted(before.keys() - after.keys())],
        added_switches=[after[k] for k in sorted(after.keys() - before.keys())],
        old_accepted_origin=dict(Counter(x['origin_rule'] for x in old_accepted)),
        v3_frozen_accepted_origin=dict(Counter(x['origin_rule'] for x in v3_accepted if x['arm'] == 'frozen_events')),
        v3_pairwise_accepted_origin=dict(Counter(x['origin_rule'] for x in v3_accepted if x['arm'] == 'pairwise_events')),
        v3_pairwise_equals_v3_frozen_all_405=True)
    px.save(HERE / 'public/DELTA_AUDIT.json', result)
    print(dict(changed_public_frames=len(differences), changed_depth_observations=changed,
               observed=observed, provenance4_frames=annotated_frames,
               removed_switches=len(result['removed_switches']), added_switches=len(result['added_switches'])), flush=True)


if __name__ == '__main__':
    main()
