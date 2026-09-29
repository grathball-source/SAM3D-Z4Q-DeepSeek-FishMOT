"""Record local restricted input dependencies without copying their contents."""
from run import DATA, HERE, SOURCE_MANIFEST, px, read


def main():
    freeze = read(HERE / 'public/FREEZE.json')
    original = read(SOURCE_MANIFEST)['segments']['SOURCE_OLD']
    predictions, raw_depth, references = {}, {}, {}
    for name in px.SEGMENTS:
        for row in original[name]['frames']:
            frame = row['original_frame']
            predictions[str(frame)] = dict(path=row['prediction_path'],
                bytes=row['prediction_bytes'], sha256=row['prediction_sha256'])
            raw_depth[str(frame)] = dict(path=row['depth_path'],
                bytes=row['depth_bytes'], sha256=row['depth_sha256'])
            references[str(frame)] = px.descriptor(DATA / 'labels_640x360' / f'{frame:06d}.json')
    assert len(predictions) == len(raw_depth) == len(references) == len(freeze['restored']) == 405
    px.save(HERE / 'public/RESTRICTED_INVENTORY.json', dict(
        status='PATH_BYTES_SHA_ONLY_NO_PIXEL_CONTENT',
        source='SOURCE_OLD', frames=405,
        saved_sam3_predictions=predictions, original_depth=raw_depth,
        restored_v3_depth=freeze['restored'], edited_reference=references,
        frozen_derived=freeze['derived'],
        original_source_manifest=freeze['source_manifest'],
        prediction_inputs_verified_in_original_source_manifest=True,
        reference_used_only_after_both_new_seals=True))
    print('restricted input inventory: 405 frames', flush=True)


if __name__ == '__main__':
    main()
