"""Private RGB and original-depth frames; only explicit sensor fields are read."""
from __future__ import annotations

import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from common import ROOT, WORK, DATA, module, artifact, input_dir

cv2.setNumThreads(1)
_SOURCE = None


def _source():
    """Give DS14 its own common namespace, then restore the calling experiment."""
    global _SOURCE
    if _SOURCE is None:
        base = ROOT / 'experiments/ds14_raw_multidataset'
        original = sys.modules.get('common')
        inserted = str(base) not in sys.path
        try:
            if inserted:
                sys.path.insert(0, str(base))
            sys.modules['common'] = module('ds33_sensor_ds14_common', base / 'common.py')
            _SOURCE = module('ds33_sensor_ds14_source', base / 'source.py')
        finally:
            if inserted:
                sys.path.remove(str(base))
            if original is None:
                sys.modules.pop('common', None)
            else:
                sys.modules['common'] = original
    return _SOURCE


@lru_cache(maxsize=None)
def _pin(path):
    return artifact(Path(path))


def _array(array):
    value = np.asarray(array)
    return dict(shape=list(value.shape), dtype=str(value.dtype),
                sha256=hashlib.sha256(value.tobytes(order='C')).hexdigest())


class Sensor:
    """No annotation reader, recovered depth, native-ID inference, or future lookup."""
    def __init__(self, name):
        self.name = name
        self.raw = _source().RawDepth(name)
        self.previous = None
        if name.startswith('feeding_'):
            self.base = DATA
            self.manifest = self.base / 'manifest.jsonl'
            self.calibration = self.base / 'calibration.json'
            profiles = json.loads(self.calibration.read_text(encoding='utf-8'))['recorded_profiles']
        elif name.startswith('fishsa_'):
            self.base = WORK / 'data/AlignedDataset_v1'
            self.manifest = self.base / 'manifest.jsonl'
            self.calibration = self.base / 'calibration/recorded_profiles.json'
            profiles = json.loads(self.calibration.read_text(encoding='utf-8'))
            unpaired = json.loads((self.base / 'unpaired/manifest.json').read_text(encoding='utf-8'))
            self.unpaired = {r['source_color_index'] + 1: r for r in unpaired}
        else:
            assert name in ('L3', 'LW'), name
            self.base = WORK / 'data/AnnotationNewBags_20260919' / name
            self.manifest = self.base / 'manifest.json'
            self.calibration = self.base / 'calibration.json'
            profiles = json.loads(self.calibration.read_text(encoding='utf-8'))
        self.geometry = getattr(self.raw, 'geo', None)
        if self.geometry is None:
            self.geometry = _source().Geometry(profiles, 640, 360)
            self.geometry.kc[0, 2] += (640 / self.geometry.color['width'] - 1) / 2
            self.geometry.kc[1, 2] += (360 / self.geometry.color['height'] - 1) / 2
        self.K = self.geometry.kc.copy()
        self.distortion = self.geometry.dc.copy()

    def metadata(self, global_frame):
        g = int(global_frame)
        assert g == global_frame
        row = self.raw.metadata.get(g)
        if self.name.startswith('feeding_'):
            assert row is not None
            path = self.base / row['rgb']
            rgb_time = row['rgb_timestamp_us']
        elif self.name.startswith('fishsa_'):
            if row is None:
                assert g == 1 and g in self.unpaired
                row = self.unpaired[g]
            else:
                assert row['source_color_index'] + 1 == g
            path = self.base / row['rgb']
            rgb_time = row['color_timestamp_us']
        else:
            assert row is not None
            path = Path(row['rgb_source'])
            rgb_time = row['rgb_timestamp_us']
        # Labels and instance fields in mixed manifests are deliberately not returned.
        return dict(global_frame=g, rgb_path=str(path.resolve()),
                    rgb_timestamp_us=int(rgb_time),
                    depth_timestamp_us=row.get('depth_timestamp_us'),
                    delta_us=row.get('delta_us'))

    def read(self, global_frame, time):
        g = int(global_frame)
        meta = self.metadata(g)
        assert abs(meta['rgb_timestamp_us'] / 1e6 - time) < 1e-6, (self.name, g, time)
        if self.previous is not None:
            assert g >= self.previous[0] and time >= self.previous[1]
        depth, index, native, raw_binding = self.raw(g, time)
        image = cv2.imread(meta['rgb_path'], cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(meta['rgb_path'])
        source_shape = list(image.shape)
        assert image.shape in ((360, 640, 3), (1080, 1920, 3)), (self.name, g, image.shape)
        resized = image.shape[:2] != (360, 640)
        if resized:
            image = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        assert gray.shape == depth.shape == index.shape == (360, 640)
        assert gray.dtype == np.uint8
        valid = index >= 0
        source = index[valid]
        xyz = np.full((*depth.shape, 3), np.nan, dtype=np.float32)
        xyz[valid] = (self.geometry.rc.reshape(-1, 3)[source]
                      * native.ravel()[source, None] + self.geometry.t).astype(np.float32)
        assert np.array_equal(xyz[..., 2][valid], depth[valid])
        binding = dict(raw_binding)
        binding.update(schema='DS33_SENSOR_FRAME_V1', segment=self.name,
                       global_frame=g, time=float(time), **{k: meta[k] for k in
                           ('rgb_timestamp_us', 'depth_timestamp_us', 'delta_us')},
                       rgb=_pin(meta['rgb_path']), source_manifest=_pin(str(self.manifest)),
                       recorded_calibration=_pin(str(self.calibration)),
                       RGB_read=True, GT_read=False, annotation_read=False,
                       restored_read=False, no_future_sensor_lookup=True,
                       rgb_source_shape=source_shape,
                       rgb_resize='cv2.INTER_AREA_1920x1080_to_640x360' if resized else 'ALREADY_ALIGNED_640x360',
                       rgb_gray='cv2.COLOR_BGR2GRAY',
                       pixel_center_formula='u_new=(u_original+0.5)/3-0.5; same for v',
                       K=self.K.tolist(), distortion_opencv=self.distortion.tolist(),
                       calibration_available=True,
                       xyz_coordinates='RECORDED_RGB_CAMERA_XYZ_MM_FROM_ACTUAL_NATIVE_SOURCE_INDEX',
                       array_bindings=dict(gray=_array(gray), depth_mm=_array(depth),
                                           source_index=_array(index), native_depth=_array(native), xyz_mm=_array(xyz)),
                       physical_3D_accuracy='UNKNOWN_UNDERWATER_CALIBRATION_NOT_VALIDATED',
                       depth_difference_is_motion=False)
        if self.name.startswith('fishsa_') and g == 1:
            binding['unpaired_manifest'] = _pin(str(self.base / 'unpaired/manifest.json'))
            assert not binding['sensor_available'] and not np.any(depth)
        self.previous = (g, float(time))
        return dict(gray=gray, depth_mm=depth, source_index=index,
                    native_depth=native, xyz_mm=xyz, K=self.K.copy(), distortion=self.distortion.copy(),
                    binding=binding)

    def close(self):
        self.raw.close()

