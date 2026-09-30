"""Freeze and measure every exposed DS2 source mask; never open manual labels."""
import gzip
import json
import platform
import socket
import subprocess
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from common import (HERE, ROOT, OLD, SEGMENTS, CFG, artifact, verify, records,
                    load_depth, extract_frame, prediction_masks, encoded, dump_line,
                    write_new, np, cv2, digest)
from foreground import measure


def freeze():
    assert not (HERE/'FREEZE.json').exists(), 'refuse to overwrite frozen run'
    assert json.loads((HERE/'CHECKS.json').read_text())['passed']
    code=list(HERE.glob('*.py'))+[HERE/'CONFIG.json',HERE/'PLAN.md',HERE/'CHECKS.json']
    code += [ROOT/'experiments/ds1_depth_only/depth_measurement.py',
             ROOT/'experiments/feeding_first_two_s0p/prepare.py',
             Path('E:/CAU/D-MOT/tools/sam3_depth_birth_inherit_20260917/features.py')]
    sources={}; locked=[]
    for name,(start,stop) in SEGMENTS.items():
        directory=OLD/'private'/name
        manifest=json.loads((directory/'SOURCE_MANIFEST.json').read_text())
        for key in ('assignments','profiles'): verify(manifest['derived'][key]); locked.append(manifest['derived'][key])
        assert digest(directory/'sources.json')==manifest['sources_sha256']
        rows=json.loads((directory/'sources.json').read_text())
        assert [r['frame'] for r in rows]==list(range(start,stop+1))
        for row in rows:
            for kind in ('prediction','depth'):
                verify(dict(path=row[kind+'_path'],bytes=row[kind+'_bytes'],sha256=row[kind+'_sha256']))
        sources[name]=rows
        locked += [artifact(directory/'sources.json'),artifact(directory/'SOURCE_MANIFEST.json'),
                   artifact(OLD/'run'/name/'public/DEPTH_OBSERVATIONS.jsonl.gz')]
    write_new(HERE/'SOURCE_INVENTORY.json',sources)
    oldlock=[dict(path=str(p.relative_to(ROOT)),sha256=digest(p))
             for folder in ('ds1_depth_only','ds2_depth_transfer_validation')
             for p in sorted((ROOT/'experiments'/folder).rglob('*'))
             if p.is_file() and 'private' not in p.parts and '__pycache__' not in p.parts
             and p.suffix!='.pyc']
    write_new(HERE/'OLD_READONLY_LOCK.json',oldlock)
    write_new(HERE/'FREEZE.json',dict(status='FROZEN_BEFORE_ALL_MEASUREMENTS_AND_REFERENCES',
        base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        constants=CFG,code=[artifact(p) for p in sorted(code)],locked_sources=locked,
        source_inventory=artifact(HERE/'SOURCE_INVENTORY.json'),
        old_readonly=artifact(HERE/'OLD_READONLY_LOCK.json'),
        clock_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        runtime=dict(python=platform.python_version(),numpy=np.__version__,opencv=cv2.__version__,
                     opencv_threads=cv2.getNumThreads(),math_threads_requested=1,device='LOCAL_CPU'),
        inference_http=0,smoke=0,cost_usd=0))
    return sources


def run():
    sources=freeze(); started=time.perf_counter(); counts=Counter(); timing=[]
    original_open=Path.open; original_key=np.lib.npyio.NpzFile.__getitem__
    def guarded_open(path,*args,**kwargs):
        assert 'labels_640x360' not in str(path) and 'sealed_test' not in str(path),path
        return original_open(path,*args,**kwargs)
    def guarded_key(sensor,key):
        assert key=='depth_mm',key
        return original_key(sensor,key)
    private=HERE/'private'; private.mkdir(exist_ok=False)
    with patch.object(Path,'open',guarded_open), patch.object(np.lib.npyio.NpzFile,'__getitem__',guarded_key), \
         patch.object(socket.socket,'connect',side_effect=AssertionError('no model/network')):
        for name,(start,stop) in SEGMENTS.items():
            pixel_path=private/f'{name}_pixels.jsonl.gz'
            result_path=HERE/f'{name}_measurements.jsonl.gz'
            with gzip.open(pixel_path,'xt',encoding='utf-8') as pixels_out, \
                 gzip.open(result_path,'xt',encoding='utf-8') as out:
                inputs=zip(sources[name],records(OLD/'private'/name/'assignments.jsonl.gz'),
                           records(OLD/'private'/name/'profiles.jsonl.gz'),
                           records(OLD/'run'/name/'public/DEPTH_OBSERVATIONS.jsonl.gz'),strict=True)
                for source,assignment,profile,expected in inputs:
                    tick=time.perf_counter(); frame=source['frame']
                    assert assignment['global_frame_id']==profile['global_frame']==expected['global_frame']==frame
                    depth=load_depth(source['depth_path'])
                    _,baseline,masks,occ=extract_frame(depth,assignment,{r['id']:r for r in profile['observations']})
                    fresh,_=prediction_masks(json.loads(Path(source['prediction_path']).read_text())['shapes'])
                    assert set(fresh)==set(masks)
                    assert all(np.array_equal(fresh[n],masks[n]) for n in fresh)
                    for n,b in baseline.items():
                        assert b['whole']==expected['objects'][str(n)]['whole']
                        assert b['core']==expected['objects'][str(n)]['core']
                    base_seconds=time.perf_counter()-tick; filtering=time.perf_counter()
                    objects={}; private_objects={}
                    for index,(native,region) in enumerate(sorted(masks.items()),1):
                        token=f'o{index:03d}'; fact=f'{name}:F{frame}:{token}'
                        foreground,pixels=measure(depth,region,(occ-region.astype('u2'))>0)
                        objects[token]=dict(fact_id=fact,whole=baseline[native]['whole'],
                            core=baseline[native]['core'],core_usable=baseline[native]['core_usable'],
                            foreground=foreground)
                        private_objects[token]=dict(native=native,source_mask=assignment['masks'][f'n:{native}'],
                            crop=foreground['crop'],regions={k:encoded(v) for k,v in pixels.items()})
                        counts[foreground['status']]+=1; counts[foreground['reason']]+=1
                    filter_seconds=time.perf_counter()-filtering
                    row=dict(frame=frame,segment=name,time=assignment['time'],evidence_max_frame=frame,
                        source_depth_sha256=source['depth_sha256'],source_prediction_sha256=source['prediction_sha256'],
                        baseline_equivalence=True,source_mask_equivalence=True,objects=objects,
                        seconds=dict(baseline_and_source=base_seconds,filter=filter_seconds))
                    dump_line(out,row); dump_line(pixels_out,dict(frame=frame,objects=private_objects))
                    timing.append(row['seconds'])
                    if (frame-start+1)%100==0 or frame==stop:
                        print(f'{name} {frame-start+1}/{stop-start+1} masks={sum(v for k,v in counts.items() if k in ("AVAILABLE","UNKNOWN"))}',flush=True)
    write_new(HERE/'TIMING.json',dict(total_seconds=time.perf_counter()-started,frames=len(timing),
        baseline_source_median_ms=1000*float(np.median([t['baseline_and_source'] for t in timing])),
        filter_median_ms=1000*float(np.median([t['filter'] for t in timing])),
        counts=dict(counts),inference_http=0,cost_usd=0))
    items=[artifact(HERE/f'{name}_measurements.jsonl.gz') for name in SEGMENTS]
    items += [artifact(private/f'{name}_pixels.jsonl.gz') for name in SEGMENTS]
    items += [artifact(HERE/'TIMING.json'),artifact(HERE/'FREEZE.json')]
    write_new(HERE/'MEASUREMENTS_SEALED.json',dict(status='SEALED_AWAITING_REFERENCE_OCCUPANCY_SCORING',
        frames=len(timing),objects=counts['AVAILABLE']+counts['UNKNOWN'],artifacts=items,
        sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))


if __name__=='__main__': run()
