"""Choose by provenance/existence, freeze selection, then derive sensor inputs."""
import gzip
import json
import re
import sys
from pathlib import Path
from adapter import HERE, ROOT, DS1, frozen
from prepare import DATA, RAW, build_frame, digest, write_new

ML = RAW.parent
BASE = HERE / 'private'


def select():
    rows = list(map(json.loads, (DATA / 'manifest.jsonl').read_text(encoding='utf-8').splitlines()))
    groups = {}
    for row in rows:
        groups.setdefault(row['segment'].lower(), []).append(row)
    report = json.loads((ML / 'full_report.json').read_text(encoding='utf-8'))
    batches = sorted(tuple(map(int, re.findall(r'\d+', item['batch']))) for item in report['batch_matches'])
    assert all(len(b) == 2 for b in batches)
    def support(frames):
        return sorted({next(b for b in batches if b[0] <= f <= b[1]) for f in frames})
    old_support = support([f for start, stop in frozen.SEGMENTS.values() for f in range(start, stop+1)])
    selected, excluded = [], []
    for name, items in sorted(groups.items(), key=lambda x: x[1][0]['frame']):
        frames = sorted(x['frame'] for x in items)
        start, stop = frames[0], frames[-1]
        batch_support = support(frames)
        reason = None
        if any(start <= b and stop >= a for a, b in frozen.SEGMENTS.values()):
            reason = 'DS1_EXPOSED_ORIGINAL_FRAMES'
        elif any(a <= d and b >= c for a,b in batch_support for c,d in old_support):
            reason = 'SHARED_PRODUCER_BATCH_OR_SUPPORT_WITH_DS1'
        elif frames != list(range(start, stop+1)):
            reason = 'INCOMPLETE_METADATA_RANGE'
        missing = [str(p) for r in items for p in (
            RAW / f"{r['frame']:06d}.json", DATA / r['depth_aligned'],
            DATA / 'labels_640x360' / f"{r['frame']:06d}.json") if not p.is_file()]
        if missing:
            reason = 'MISSING_REQUIRED_FILES'
        entry = dict(name=name, original_frames=[start,stop], frames=len(frames),
            production_batches=batch_support,
            production_support=[min(b[0] for b in batch_support),max(b[1] for b in batch_support)],
            prediction_dir=str(RAW), depth_dir=str((DATA / items[0]['depth_aligned']).parent),
            reference_dir=str(DATA / 'labels_640x360'), reference_files_exist=not missing,
            missing_files=missing, role='DEVELOPMENT_BY_CURRENT_USER_DS2_INSTRUCTION',
            exposure='NATIVE_BASELINE_EXPOSED; not used DS1 or prior association tuning found in repository',
            exhaustive_external_tuning_history='UNKNOWN')
        if reason or len(selected) >= 2:
            excluded.append(dict(entry, reason=reason or 'AFTER_EARLIEST_TWO'))
        else:
            selected.append(entry)
    assert [x['original_frames'] for x in selected] == [[701,1060],[1201,1906]]
    metadata = [DATA/'manifest.jsonl', DATA/'calibration.json', DATA/'README.md',
                ML.parent/'full_protocol.json', ML.parent/'full_complete.json', ML/'full_report.json',
                Path('E:/CAU/D-MOT/output/evaluation/sam3_feeding_20260928_v2/protocol.json')]
    value = dict(selection='FROZEN_BY_METADATA_AND_EXISTENCE_BEFORE_FEATURES_OR_GT_CONTENT',
        classification='TEMPORAL_NONOVERLAP_SAME_RECORDING',
        recording='FEEDING Orbbec Femto Bolt_CL8654103ML_20260918124300',
        frontend='UPSTREAM_LOOKAHEAD_UNKNOWN',
        producer_policy='earliest sorted batch owns a frame; 20 frames stride 15; forward propagation; native IDs stitched using past overlap',
        global_id_stitch_history='shared earlier production job; temporal nonoverlap is not independent recording',
        other_recordings='FishSA development already used; other datasets lack verified same raw aligned depth/grid and fresh development provenance; sealed test excluded without opening',
        selected=selected, excluded=excluded, ds1_production_support=old_support,
        raw_depth_contract='depth_mm only; camera Z mm, 360x640; zero/nonfinite missing; no instance_id/v3',
        reference_permission='open manual annotation work ranges and prior public baseline protocol; current user authorizes development use; no sealed-test designation found',
        metadata={str(p):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in metadata},
        new_model_http=0,model_cost_usd=0)
    write_new(HERE/'VALIDATION_COHORT.json', value)
    return value, {r['frame']:r for r in rows}


def main():
    cohort, metadata = select()
    for entry in cohort['selected']:
        name=entry['name']; start,stop=entry['original_frames']
        target=BASE/name; target.mkdir(parents=True, exist_ok=False)
        paths={k:target/f'{k}.jsonl.gz' for k in ('observations','profiles','assignments')}
        sources=[]
        with gzip.open(paths['observations'],'wt',encoding='utf-8',compresslevel=3) as a, \
             gzip.open(paths['profiles'],'wt',encoding='utf-8',compresslevel=3) as b, \
             gzip.open(paths['assignments'],'wt',encoding='utf-8',compresslevel=3) as c:
            for local,global_frame in enumerate(range(start,stop+1),1):
                obs,profile,assignment,source=build_frame(local,metadata[global_frame])
                for item,handle in ((obs,a),(profile,b),(assignment,c)):
                    handle.write(json.dumps(item,separators=(',',':'),allow_nan=False)+'\n')
                sources.append(source)
                if local%100==0: print(name,local,'/',stop-start+1,flush=True)
        write_new(target/'sources.json',sources)
        result=dict(name=name,start=start,stop=stop,frames=stop-start+1,
            prediction_source='SOURCE_OLD original 20260924 batched SAM3',
            depth_source='original depth_mm only',
            cohort_sha256=digest(HERE/'VALIDATION_COHORT.json'),
            derived={k:dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p)) for k,p in paths.items()},
            sources_sha256=digest(target/'sources.json'))
        write_new(target/'SOURCE_MANIFEST.json',result)
        sys.path.insert(0,str(frozen.OLD))
        from source_scan_v4 import scan
        scan(paths['observations'],paths['assignments'],target/'scan_v4.json')
        write_new(target/'SCAN_MANIFEST.json',dict(frames=stop-start+1,
            scan_sha256=digest(target/'scan_v4.json'), scanner_sha256=digest(frozen.OLD/'source_scan_v4.py')))
        write_new(HERE/'source_inventory'/f'{name}.json',dict(result, sources=sources,
            scan_sha256=digest(target/'scan_v4.json')))


if __name__=='__main__': main()
