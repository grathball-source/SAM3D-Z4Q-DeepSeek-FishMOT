"""Postscore diagnostic: zero all v3 annotation-fill pixels and replay state."""
import copy
import gzip
import json

import numpy as np

from run import DATA, HERE, SOURCE_MANIFEST, px, prepare_depth, read, stats, exclusive_core, coco


def main():
    freeze = read(HERE / 'public/FREEZE.json')
    manifest = read(SOURCE_MANIFEST)
    changed_inputs, changed_public, checked = [], [], 0
    for name in px.SEGMENTS:
        item = manifest['segments']['SOURCE_OLD'][name]
        frozen, pairwise = px.Bridge(px.read(px.CONFIG)), px.new_bridge()
        with gzip.open(HERE / 'public' / name / 'PREDICTIONS.jsonl.gz', 'rt', encoding='utf-8') as official:
            for row, profiles, assignment, observations in px.feed(item):
                frame = row['global_frame']
                prepare_depth(row, profiles, assignment, observations, item, freeze)
                path = DATA / 'depth_restored_rgb_640x360' / f'{frame:06d}.npz'
                with np.load(path) as source:
                    only_annotation = source['provenance'] == 4
                    depth = source['depth_mm'].copy() if np.any(only_annotation) else None
                changed = []
                if depth is not None:
                    depth[only_annotation] = 0
                    masks = {o['id']: coco.decode(dict(size=assignment['masks'][o['mask']]['size'],
                        counts=assignment['masks'][o['mask']]['counts'].encode('ascii'))).astype(bool)
                        for o in observations}
                    occupancy = np.zeros((360, 640), np.uint16)
                    for mask in masks.values():
                        occupancy += mask
                    for observation in observations:
                        n = observation['id']
                        _, core = exclusive_core(masks[n], occupancy)
                        whole, core_stat = stats(depth, masks[n]), stats(depth, core)
                        replacement = {k: whole[k] for k in ('n', 'valid_fraction', 'median', 'mad')}
                        if replacement != observation['depth'] or core_stat != profiles[n]['core']:
                            changed.append(n)
                        observation['depth'] = replacement
                        profiles[n]['whole'], profiles[n]['core'] = whole, core_stat
                    if changed:
                        changed_inputs.append(dict(frame=frame, native_ids=changed,
                            provenance4_pixels=int(only_annotation.sum())))
                frozen_map, _, _, _, _ = px.decision(
                    frozen, row, copy.deepcopy(profiles), assignment, copy.deepcopy(observations))
                pair_map, _, _, _, _ = px.decision(pairwise, row, profiles, assignment, observations)
                sent = json.loads(next(official))
                assert sent['original_frame'] == frame
                official_frozen = {int(k): int(v) for k, v in sent['variants']['Z4Q_FROZEN_V3'].items()}
                official_pair = {int(k): int(v) for k, v in sent['variants']['Z4Q_PAIRWISE_V3'].items()}
                if frozen_map != official_frozen or pair_map != official_pair:
                    changed_public.append(dict(frame=frame,
                        frozen={str(n): [official_frozen[n], frozen_map[n]] for n in frozen_map
                                if frozen_map[n] != official_frozen[n]},
                        pairwise={str(n): [official_pair[n], pair_map[n]] for n in pair_map
                                  if pair_map[n] != official_pair[n]}))
                checked += 1
            assert next(official, None) is None
    assert checked == 405
    px.save(HERE / 'public/PROVENANCE4_SENSITIVITY.json', dict(
        status='POSTSCORE_FIXED_ALL_FRAMES_LABEL_PIXEL_ABLATION',
        annotation_fill_zeroed_where_provenance4=True,
        frames=checked, changed_depth_inputs=changed_inputs,
        changed_publications=changed_public,
        official_prediction_seals={name: px.sha(HERE / 'public' / name / 'SEAL.json') for name in px.SEGMENTS}))
    print(dict(frames=checked, changed_depth_input_frames=len(changed_inputs),
               changed_publication_frames=len(changed_public)), flush=True)


if __name__ == '__main__':
    main()
