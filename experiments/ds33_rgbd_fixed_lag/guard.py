"""Prediction-only access ledger; RGB is authorized, references and networking are not."""
import os, sys
BLOCKED = ('labels_640x360', 'labels_original', 'labels_source', 'labels_recovered',
    'labels_raw', 'restoration/v3/', 'depth_restored_rgb_640x360/', 'sealed_test',
    'gt_grid', 'truth.jsonl', 'offline_matches', 'test_gt', 'full_v2',
    'reference_matches', 'event_audit', 'automatic_reconnect_audit', 'switches.json',
    'metrics.json', 'postseal_', 'gt_raster', 'annotations/')
SEEN = set()
NPZ = set()
H5 = set()


def access_guard(event, args):
    if event == 'socket.connect':
        raise RuntimeError('DS33 prohibits prediction network access')
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = str(args[0]).replace('\\', '/').lower()
    if any(token in path for token in BLOCKED):
        raise RuntimeError('Forbidden prediction access: ' + path)
    if '/data/' in path or '/private/' in path:
        SEEN.add(str(args[0]))


sys.addaudithook(access_guard)
from common import *
import numpy as np
_npz_get = np.lib.npyio.NpzFile.__getitem__


def npz_get(sensor, key):
    if key not in ('depth_mm', 'source_index'):
        raise RuntimeError('Forbidden sensor field: ' + str(key))
    NPZ.add((str(sensor.zip.filename), key))
    return _npz_get(sensor, key)


np.lib.npyio.NpzFile.__getitem__ = npz_get
import h5py
_h5_get = h5py.Group.__getitem__
H5_KEYS = {'/frame_id', '/aligned/raw_depth_mm', '/aligned/raw_source_index',
           '/native/original_depth_mm'}


def h5_get(group, key):
    assert isinstance(key, str), 'Indirect H5 references are not permitted'
    absolute = key if key.startswith('/') else group.name.rstrip('/') + '/' + key
    if absolute not in H5_KEYS:
        raise RuntimeError('Forbidden H5 sensor field: ' + absolute)
    H5.add((str(group.file.filename), absolute))
    return _h5_get(group, key)


h5py.Group.__getitem__ = h5_get


def main():
    from runner import run_segment
    mode, name = sys.argv[1:3]
    if mode == 'prefix':
        output = HERE / sys.argv[4]
        assert output.parent == HERE and output.name.startswith('slice_')
        run_segment(name, output, stop_at=int(sys.argv[3]))
    else:
        assert mode == 'run'
        output = RUN
        run_segment(name, output)
    from sensor import _source
    write_new(output / name / 'public/ACCESS.json', dict(
        status='RGB_RAW_DEPTH_FINITE_LAG_NO_GT_RESTORED_NETWORK',
        blocked_tokens=list(BLOCKED), observed_data_paths=sorted(SEEN),
        npz_field_reads=[dict(path=p, key=k) for p, k in sorted(NPZ)],
        h5_field_reads=[dict(path=p, key=k) for p, k in sorted(H5)],
        original_sensor_field_reads=_source().FIELD_READS,
        actual_RGB_pixel_reads='PER_FRAME_SENSOR_BINDING_AND_FLOW_RECORDS',
        future_limit_frames=CFG['lag_frames'],
        publication='FIXED_LAG_FIRST_PUBLICATION_ONLY; NO_PUBLISHED_HISTORY_REWRITES',
        annotation_instance_id_read=False, restored_depth_read=False,
        new_model_http=0, cost_usd=0))


if __name__ == '__main__':
    main()
