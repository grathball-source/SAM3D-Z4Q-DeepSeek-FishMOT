"""Postseal delivery inventory only; no predictor, reference or source pixels."""
from common import *
import platform


def main():
    assert read(HERE/'FINAL_CHECKS.json')['status']=='PASS'
    restricted={}
    for name in SEGMENTS:
        for path in input_dir(name).iterdir():
            if path.is_file():restricted[str(path.resolve())]=artifact(path)
    for folder in ('private','slice'):
        for path in (HERE/folder).rglob('*'):
            if path.is_file():restricted[str(path.resolve())]=artifact(path)
    raw={}
    def collect(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                item={k:value[k] for k in ('path','bytes','sha256')}
                if item['path'] in raw:assert raw[item['path']]==item
                raw[item['path']]=item
            else:
                for child in value.values():collect(child)
        elif isinstance(value,list):
            for child in value:collect(child)
    for name in SEGMENTS:collect(read(input_dir(name)/'RAW_SOURCES.json'))
    write_new(HERE/'RESTRICTED_ARTIFACTS.json',dict(status='LOCAL_ONLY_NOT_FOR_GIT',
        derived_and_visual_artifacts=list(restricted.values()),raw_source_artifacts=list(raw.values()),
        raw_digests_verified_by_sealed_scorer=artifact(RUN/'SCORE_PROVENANCE.json'),
        dependencies=dict(python=sys.executable,version=platform.python_version(),deps=str(DEPS),
            source_base_commit=read(HERE/'OLD_READONLY_LOCK.json')['base_commit']),
        reproduction='Use the identical local raw/DS14 prepared files, original source metadata and deps; run in a fresh output checkout: execute.py freeze.py, orchestrate.py, baseline_check.py, score.py, summarize.py, visualize.py. Existing seals are exclusive and must not be overwritten.',
        restricted_reasons='Private raw depth, masks/polygons and actual-pixel comparison images; no private pixels or GT raster committed.',
        inventory_generator=artifact(__file__)))
    print('Restricted inventory:',len(restricted),'derived/visual and',len(raw),'raw-source artifacts')


if __name__=='__main__':main()
