"""Read saved native v2 estimates and project them without RGB, GT or a model.

This is an offline diagnostic source: v2 used RGB and next-frame cleaning.
It cannot be made causally equivalent by masking selected provenance codes.
"""
from pathlib import Path
import json
import sys

import h5py
import numpy as np

DATA = Path('E:/CAU/D-MOT/data/AlignedFeeding_v1')
V2 = Path('E:/CAU/D-MOT/tools/depth_restoration_feeding_20260929/full_v2')
PROJECTION = Path('E:/CAU/D-MOT/tools/depth_restoration')
sys.path.insert(0, str(PROJECTION))
from geometry import Geometry
from build_aligned_dataset import rasterize, gather


class RestoredDepth:
    """Current-frame reader; ``current_source_index`` is a private pixel array.

    ``__call__`` returns depth, provenance, and JSON-safe source metadata.
    Initialization reads only one-dimensional index/time metadata and shapes.
    All native image arrays are loaded only for the requested global frame.
    """

    def __init__(self):
        self._files = []
        self._locations = {}
        self.current_frame = None
        self.current_source_index = None
        self._rows = {
            row['frame']: row for row in map(
                json.loads, (DATA/'manifest.jsonl').read_text(encoding='utf-8').splitlines())
        }
        profiles = json.loads((DATA/'calibration.json').read_text(encoding='utf-8'))['recorded_profiles']
        self.geom = Geometry(profiles, 640, 360)
        self.geom.kc[0, 2] += (640/self.geom.color['width']-1)/2
        self.geom.kc[1, 2] += (360/self.geom.color['height']-1)/2
        try:
            for number in (1, 2, 3):
                path = V2/f'depth_restored_v2_{number:02d}.h5'
                source = h5py.File(path, 'r')
                self._files.append(source)
                assert source.attrs['complete'] and source.attrs['version'] == 'v2'
                indices = source['index'][:]
                assert source['depth_mm'].shape == (len(indices), 576, 640)
                for key in ('original_depth_mm', 'filled_mask', 'invalidated_reason'):
                    assert source[key].shape == source['depth_mm'].shape
                metadata = {key: source[key][:] for key in (
                    'color_index', 'color_timestamp_us', 'depth_timestamp_us', 'delta_us')}
                for row, index in enumerate(indices):
                    frame = int(index)
                    assert frame not in self._locations and int(metadata['color_index'][row]) == frame
                    timing = {key: int(value[row]) for key, value in metadata.items()}
                    assert timing['delta_us'] == timing['color_timestamp_us']-timing['depth_timestamp_us']
                    if frame in self._rows:
                        item = self._rows[frame]
                        assert timing['color_timestamp_us'] == item['rgb_timestamp_us']
                        assert timing['depth_timestamp_us'] == item['depth_timestamp_us']
                        assert timing['delta_us'] == item['delta_us']
                    self._locations[frame] = (source, row, timing)
            assert set(self._locations) == set(range(1907))
        except Exception:
            self.close()
            raise

    def __call__(self, global_frame):
        frame = int(global_frame)
        assert frame == global_frame and frame in self._rows
        source, row, timing = self._locations[frame]
        depth = source['depth_mm'][row]
        original = source['original_depth_mm'][row]
        filled = source['filled_mask'][row] > 0
        flags = source['invalidated_reason'][row]
        assert np.isfinite(depth).all() and (depth >= 0).all()
        retained = (original > 0) & (flags == 0)
        assert np.array_equal(depth[retained], original[retained])
        assert np.all((depth > 0) == (retained | filled))
        provenance = np.zeros(depth.shape, 'u1')
        provenance[depth > 0] = 1
        provenance[filled & (original == 0)] = 2
        provenance[filled & (original > 0)] = 3
        assert np.array_equal(depth > 0, provenance > 0)
        flat = depth.ravel()
        indices = np.flatnonzero(np.isfinite(flat) & (flat > 0))
        xyz = self.geom.rc.reshape(-1, 3)[indices]*flat[indices, None]+self.geom.t
        aligned, source_index = rasterize(
            self.geom.project_xyz(xyz), xyz[:, 2], indices, 360, 640)
        aligned_provenance = gather(provenance, source_index)
        assert np.array_equal(aligned > 0, source_index >= 0)
        assert np.array_equal(aligned > 0, aligned_provenance > 0)
        self.current_frame = frame
        self.current_source_index = source_index
        meta = dict(
            global_frame=frame, index=frame,
            future_support='UPSTREAM_I_PLUS_1_OFFLINE',
            native_path=str(Path(source.filename).resolve()),
            native_row=row, native_index=frame, **timing,
            source='SAVED_NATIVE_V2_REPROJECTED_OFFLINE_RGB_FUTURE_SUPPORTED',
            fields_read=['depth_mm', 'original_depth_mm', 'filled_mask', 'invalidated_reason'],
            coordinates='recorded RGB camera-Z millimeters; 360x640',
            provenance_codes={'0': 'missing', '1': 'retained original measurement',
                              '2': 'LingBot original-zero estimate', '3': 'LingBot nonzero replacement'},
            provenance_counts={str(code): int((aligned_provenance == code).sum()) for code in range(4)},
            RGB_read_now=False, GT_read_now=False, model_called_now=False,
            upstream_RGB_used=True, upstream_next_frame_cleaning=True,
            physical_accuracy='UNKNOWN', causal_equivalence='NOT_ESTABLISHED')
        return aligned, aligned_provenance, meta

    @staticmethod
    def paths():
        return [*(V2/f'depth_restored_v2_{number:02d}.h5' for number in (1, 2, 3)),
                V2/'run_config.json', V2/'verification.json', DATA/'calibration.json',
                DATA/'manifest.jsonl', PROJECTION/'geometry.py',
                PROJECTION/'build_aligned_dataset.py']

    def close(self):
        for source in self._files:
            source.close()
        self._files.clear()
        self.current_frame = None
        self.current_source_index = None
