"""Append postseal change/accounting inventories; never edit predictions or scores."""
from __future__ import annotations

import gzip
import hashlib
import importlib.metadata
import json
import platform
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / 'run'
DATA = Path('E:/CAU/D-MOT/data/AlignedFeeding_v1')
FEED = ROOT / 'experiments/feeding_first_two_s0p/private'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    with path.open('rb') as stream:
        result = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def item(path, purpose):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size,
                sha256=digest(path), purpose=purpose)


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def spans(values):
    result = []
    for value in sorted(values):
        if result and result[-1][1] == value - 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def changes():
    result = []
    for public in sorted(RUN.glob('*/public')):
        comparisons = defaultdict(lambda: defaultdict(list))
        with gzip.open(public / 'predictions.jsonl.gz', 'rt', encoding='utf-8') as stream:
            for raw in stream:
                row = json.loads(raw)
                maps = {arm: {x['mask']: x['id'] for x in objects}
                        for arm, objects in row['variants'].items()}
                for other in ('SAM3_NATIVE', 'D0_GEOMETRY', 'D1_STATIC_LEGACY'):
                    assert maps['D2_DYNAMIC'].keys() == maps[other].keys()
                    for mask, public_id in maps['D2_DYNAMIC'].items():
                        if public_id != maps[other][mask]:
                            comparisons[other][mask].append(row['global_frame'])
        for other, sources in comparisons.items():
            result.append(dict(segment=public.parent.name, comparison='D2_DYNAMIC_vs_' + other,
                sources=[dict(native_mask=mask, published_object_frames=len(frames),
                              actual_frame_spans=spans(frames))
                         for mask, frames in sorted(sources.items())],
                interpretation='actual sealed ID differences, not continuous visibility or independent event gains'))
    switches = load(RUN / 'SWITCH_LEDGER.json')['events']
    def key(x):
        return (x['segment'], x['frame'], x['gt_id'], x['from_public_id'], x['to_public_id'])
    switch_diff = {}
    for other in ('SAM3_NATIVE', 'D0_GEOMETRY', 'D1_STATIC_LEGACY'):
        old, new = {key(x): x for x in switches[other]}, {key(x): x for x in switches['D2_DYNAMIC']}
        switch_diff[other] = dict(removed=[old[k] for k in sorted(old.keys() - new.keys())],
                                 added=[new[k] for k in sorted(new.keys() - old.keys())])
    write(RUN / 'CHANGE_PERSISTENCE.json', dict(status='POSTSEAL_ACTUAL_PUBLISHED_DIFFERENCES',
        comparisons=result, clear_switch_differences=switch_diff,
        prediction_seals=load(RUN / 'METRICS.json')['seal_sha256']))


def inventory():
    files = {}
    def include(path, purpose):
        path = path.resolve()
        files.setdefault(str(path), item(path, purpose))
    for name, bounds in [('feeding_000000_000199', (0, 199)), ('feeding_000351_000555', (351, 555))]:
        for record in load(FEED / name / 'sources.json'):
            include(Path(record['prediction_path']), 'SOURCE_OLD saved SAM3 raw polygon; not republished')
            include(Path(record['depth_path']), 'original NPZ; only depth_mm read, other fields prohibited')
        for filename in ('observations.jsonl.gz', 'profiles.jsonl.gz', 'assignments.jsonl.gz',
                         'sources.json', 'SOURCE_MANIFEST.json', 'scan_v4.json', 'SCAN_MANIFEST.json'):
            include(FEED / name / filename, 'existing prepared SOURCE_OLD and prediction-only scanner dependency')
        for frame in range(bounds[0], bounds[1] + 1):
            include(DATA / 'labels_640x360' / f'{frame:06d}.json', 'postseal edited GT polygon; never opened by predictor')
    for name in ('README.md', 'calibration.json', 'manifest.jsonl'):
        include(DATA / name, 'existing input units/grid/timing provenance')
    for path in sorted((HERE / 'private_visualizations').glob('*.png')):
        include(path, 'local raw-depth/mask or numeric QA figure; excluded from Git')
    write(RUN / 'RESTRICTED_INVENTORY.json', dict(status='ACTUAL_LOCAL_FILES_NOT_PUBLISHED',
        files=list(files.values()), total_files=len(files), total_bytes=sum(x['bytes'] for x in files.values()),
        excludes='No raw RGB was read; no provider IDs, credentials, GT raster or model media was created.',
        reproduction='Restore these exact hashes at listed paths, install recorded local dependencies, use README commands in fresh output directories. Raw NPZ and source polygons remain private.'))
    versions = {}
    for package in ('numpy', 'scipy', 'opencv-python', 'pycocotools', 'matplotlib'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = 'NOT_INSTALLED_UNDER_THIS_DISTRIBUTION_NAME'
    write(RUN / 'ENVIRONMENT.json', dict(python=sys.version, interpreter=sys.executable,
        platform=platform.platform(), packages=versions,
        trackeval_source_root='E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps',
        external_inference_http=0, external_inference_cost_usd=0,
        execution='local saved-input CPU replay; no SAM3/GPU/server job'))
    write(RUN / 'MODEL_CALL_ACCOUNTING.json', dict(status='NO_MODEL_OR_DEPTH_COMPLETION_IN_THIS_EXPERIMENT',
        research_http=0, technical_smoke_http=0, model_cost_usd=0, requests_prepared=0,
        evidence='Prediction code imports no provider/request preparation; real prefix used throwing provider/infer stub, blank key, blocked socket connect; no old response was read.',
        excluded='Codex development and authorized Git operations are not tested-system inference.'))
    qa = load(RUN / 'VISUAL_QA_RECORD.json')
    write(RUN / 'VISUAL_INSPECTION.json', dict(status='ACTUALLY_OPENED_AND_INSPECTED',
        date=datetime.now(timezone.utc).isoformat(), artifacts=qa['artifacts'],
        findings=['First complete automatic MS1-F59 showed separate pre fragments, group-only depth and q415 before first publication.',
                  'Maximum candidate-independent conflict was a different mask n:62 at F415: 9 core points, fraction0.18, median12198.369 versus whole1175.375 mm; frozen core gate rejected it.',
                  'Numeric plot distinguished measured points, full-gap weak forecasts, group surface and q cutoff; proxy widths are not calibrated confidence intervals.'],
        private_pixels_not_published=True, formal_prediction_seals=qa['formal_prediction_seals']))


def manifest():
    excluded = ('private_visualizations', '__pycache__')
    paths = [p for p in HERE.rglob('*') if p.is_file() and
             not any(part in excluded for part in p.relative_to(HERE).parts) and
             p.name not in ('ARTIFACT_MANIFEST.json', 'REMOTE_VERIFICATION.json')]
    paths += [ROOT / 'README.md', ROOT / 'EXPERIMENT_INDEX.md', ROOT / 'research/HANDOFF.md']
    write(RUN / 'ARTIFACT_MANIFEST.json', dict(status='PUBLIC_DELIVERY_FILES',
        files=[dict(relative_path=str(p.relative_to(ROOT)).replace('\\', '/'),
                    bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(paths)],
        excludes='Self and later remote proof excluded to prevent recursive hashing; private QA/pixels inventoried separately.',
        base_main='2fe9e0c8eb497432ae5e4c676f09b8d67bff9474'))


if __name__ == '__main__':
    if '--manifest' in sys.argv:
        manifest()
    else:
        changes()
        inventory()
    print('POSTSEAL_ARCHIVE_COMPLETE')
