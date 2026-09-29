"""Postscore numeric depth source audit for the F374 decision."""
import numpy as np

from run import DATA, HERE, SOURCE_MANIFEST, coco, px, read


def main():
    name = 'feeding_000351_000555'
    item = read(SOURCE_MANIFEST)['segments']['SOURCE_OLD'][name]
    assignments = {r['global_frame_id']: r for r in px.rows(item['derived']['assignments']['path'])}
    rows = []
    for frame in (361, 370, 371, 372, 373, 374, 375, 376):
        native = 67 if frame == 361 else 70
        rle = assignments[frame]['masks'][f'n:{native}']
        mask = coco.decode(dict(size=rle['size'], counts=rle['counts'].encode('ascii'))).astype(bool)
        with np.load(DATA / 'depth_restored_rgb_640x360' / f'{frame:06d}.npz') as source:
            depth, provenance = source['depth_mm'], source['provenance']
        by_class = {}
        for klass in range(1, 5):
            values = depth[mask & (provenance == klass) & (depth > 0)]
            by_class[str(klass)] = dict(n=int(values.size), median_mm=float(np.median(values)) if values.size else None)
        values = depth[mask & (depth > 0)]
        rows.append(dict(frame=frame, native_id=native, valid_n=int(values.size),
            median_mm=float(np.median(values)) if values.size else None,
            by_provenance=by_class))
    px.save(HERE / 'public/F374_DEPTH_SOURCE.json', dict(status='POSTSCORE_NUMERIC_SOURCE_AUDIT',
        rows=rows, source_assignment_sha256=item['derived']['assignments']['sha256'],
        depth_paths_in_freeze=True, no_annotation_or_rgb_pixels_serialized=True))
    print(rows, flush=True)


if __name__ == '__main__':
    main()
