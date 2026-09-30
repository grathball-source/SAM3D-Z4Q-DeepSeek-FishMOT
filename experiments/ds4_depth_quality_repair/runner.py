"""One frozen full measurement run; no new reference or model access."""
import gzip
import json
import platform
import socket
import subprocess
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from bootstrap import (HERE,ROOT,DS3,OLD,DATA,SEGMENTS,ARMS,CONFIG,legacy,baseline,
    source_depth,main_region,extract_frame,artifact,verify,digest,records,write_new,
    dump_line,encoded,decode,np,cv2)
from selector import measure as separated_measure


def methods(depth,clean,suspect,region,other):
    main,geometry=main_region(region)
    pad=baseline.CFG['annulus_outer_px']+baseline.CFG['neighbor_margin_px']
    yy,xx=np.nonzero(region)
    x0,x1=max(0,int(xx.min())-pad),min(depth.shape[1],int(xx.max())+pad+1)
    y0,y1=max(0,int(yy.min())-pad),min(depth.shape[0],int(yy.max())+pad+1)
    has_suspect=bool(suspect[y0:y1,x0:x1].any())
    has_minor=bool(geometry['minor_area'])
    outputs={}; pixels={}; cache={}
    for arm,(quality,restrict,floor) in ARMS.items():
        # ponytail: immutable equivalent contexts share calculation within one
        # object; add batch acceleration only if measured runtime warrants it.
        key=(quality and has_suspect,restrict and has_minor,floor)
        shared=key in cache
        if key not in cache:
            d=clean if key[0] else depth
            excluded=other | (region & ~main) if key[1] else other
            cache[key]=(baseline.measure(d,region,excluded) if floor==15. else
                        separated_measure(d,region,excluded,floor))
        facts,regions=cache[key]
        outputs[arm]=dict(selector=facts,
            source_admission=quality,source_suspect_within_roi=int(suspect[y0:y1,x0:x1].sum()),
            source_suspect_within_mask=int((suspect&region).sum()),
            main_restriction=restrict,main_geometry=geometry,background_floor_mm=floor,
            calculation_shared_with_earlier_context=shared)
        pixels[arm]=regions
    return outputs,pixels


def freeze():
    assert not (HERE/'FREEZE.json').exists(),'refuse overwrite'
    assert json.loads((HERE/'CHECKS.json').read_text())['passed']
    assert json.loads((HERE/'SCORE_CHECKS.json').read_text())['passed']
    assert json.loads((HERE/'READONLY_ACCEPTANCE.json').read_text())['status']=='READONLY_ACCEPTANCE_PASS_READY_TO_FREEZE'
    oldseal=json.loads((DS3/'MEASUREMENTS_SEALED.json').read_text())
    for item in oldseal['artifacts']: verify(item)
    oldfreeze=json.loads((DS3/'FREEZE.json').read_text())
    for item in oldfreeze['code']+oldfreeze['locked_sources']: verify(item)
    sources=json.loads((DS3/'SOURCE_INVENTORY.json').read_text())
    native=[]
    for name,(start,stop) in SEGMENTS.items():
        assert [r['frame'] for r in sources[name]]==list(range(start,stop+1))
        for row in sources[name]:
            for kind in ('prediction','depth'):
                verify(dict(path=row[kind+'_path'],bytes=row[kind+'_bytes'],sha256=row[kind+'_sha256']))
            native.append(dict(frame=row['frame'],**artifact(DATA/'depth_native_mm'/f'{row["frame"]:06d}.npy')))
    write_new(HERE/'SOURCE_INVENTORY.json',dict(original=sources,native=native,
        calibration=artifact(DATA/'calibration.json'),dataset_readme=artifact(DATA/'README.md')))
    oldlock=[dict(path=str(p.relative_to(ROOT)),sha256=digest(p))
        for folder in ('ds1_depth_only','ds2_depth_transfer_validation','ds3_depth_foreground_filter')
        for p in sorted((ROOT/'experiments'/folder).rglob('*')) if p.is_file()
        and 'private' not in p.parts and '__pycache__' not in p.parts and p.suffix!='.pyc']
    write_new(HERE/'OLD_READONLY_LOCK.json',oldlock)
    code=list(HERE.glob('*.py'))+[HERE/p for p in ('CONFIG.json','PLAN.md','CHECKS.json','SCORE_CHECKS.json')]
    locked=[artifact(DS3/'MEASUREMENTS_SEALED.json'),artifact(DS3/'FREEZE.json'),
            artifact(DS3/'OCCUPANCY_AUDIT.jsonl.gz')]
    for name in SEGMENTS:
        locked.extend([artifact(DS3/f'{name}_measurements.jsonl.gz'),
            artifact(DS3/'private'/f'{name}_pixels.jsonl.gz'),
            artifact(OLD/'private'/name/'profiles.jsonl.gz')])
    locked += [artifact(HERE/p) for p in ('SOURCE_AUDIT.json','COMPONENT_AUDIT.json','EVALUATION_REVIEW.md','READONLY_ACCEPTANCE.json')]
    write_new(HERE/'FREEZE.json',dict(status='FROZEN_BEFORE_NEW_MEASUREMENTS_OR_REFERENCE_SCORING',
        base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        arms={k:list(v) for k,v in ARMS.items()},config=CONFIG,
        inherited_settings=baseline.CFG,code=[artifact(p) for p in sorted(code)],locked=locked,
        legacy_code=oldfreeze['code'],source_inventory=artifact(HERE/'SOURCE_INVENTORY.json'),
        old_readonly=artifact(HERE/'OLD_READONLY_LOCK.json'),
        clock_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        runtime=dict(python=platform.python_version(),numpy=np.__version__,opencv=cv2.__version__,
                     opencv_threads=cv2.getNumThreads(),native_math_threads_requested=1,device='LOCAL_CPU'),
        inference_http=0,cost_usd=0))
    return sources


def run():
    sources=freeze(); tick=time.perf_counter(); timing=[]; totals={a:Counter() for a in ARMS}
    private=HERE/'private'; private.mkdir(exist_ok=True)
    original_open=Path.open; original_key=np.lib.npyio.NpzFile.__getitem__
    def blocked_open(path,*args,**kwargs):
        parts={part.lower() for part in path.parts}
        assert not parts.intersection({'labels_640x360','sealed_test','depth_restored','v3','rgb_640x360'}),path
        return original_open(path,*args,**kwargs)
    def blocked_key(sensor,key):
        assert key in ('depth_mm','source_index'),key
        return original_key(sensor,key)
    with patch.object(Path,'open',blocked_open),patch.object(np.lib.npyio.NpzFile,'__getitem__',blocked_key),\
         patch.object(socket.socket,'connect',side_effect=AssertionError('model/network forbidden')):
        for name,(start,stop) in SEGMENTS.items():
            with gzip.open(HERE/f'{name}_measurements.jsonl.gz','xt',encoding='utf-8') as out,\
                 gzip.open(private/f'{name}_pixels.jsonl.gz','xt',encoding='utf-8') as pixels_out:
                streams=zip(sources[name],records(DS3/f'{name}_measurements.jsonl.gz'),
                    records(DS3/'private'/f'{name}_pixels.jsonl.gz'),
                    records(OLD/'private'/name/'profiles.jsonl.gz'),strict=True)
                for source,expected,oldpixel,profiles in streams:
                    started=time.perf_counter(); frame=source['frame']
                    assert expected['frame']==oldpixel['frame']==profiles['global_frame']==frame
                    depth,clean,suspect,quality=source_depth(frame)
                    assignment=dict(masks={f'n:{r["native"]}':r['source_mask'] for r in oldpixel['objects'].values()})
                    _,measured,masks,occ=extract_frame(depth,assignment,{r['id']:r for r in profiles['observations']})
                    fresh,_=legacy.prediction_masks(json.loads(Path(source['prediction_path']).read_text())['shapes'])
                    assert set(fresh)==set(masks) and all(np.array_equal(fresh[n],masks[n]) for n in masks)
                    objects={}; pix={}
                    for token,old in oldpixel['objects'].items():
                        native=old['native']; region=masks[native]; exp=expected['objects'][token]
                        assert measured[native]['whole']==exp['whole'] and measured[native]['core']==exp['core']
                        facts,regions=methods(depth,clean,suspect,region,(occ-region.astype('u2'))>0)
                        assert facts['F2_DS3']['selector']==exp['foreground'],(frame,token,'DS3 facts')
                        for key,oldrle in old['regions'].items():
                            assert np.array_equal(regions['F2_DS3'][key],decode(oldrle)),(frame,token,key)
                        for arm,item in facts.items():
                            stat=item['selector']; selected=regions[arm]['selected']
                            x0,y0,x1,y1=stat['crop']; raw=depth[y0:y1,x0:x1]
                            assert int(selected.sum())==stat['selected']['n']
                            assert np.all(np.isfinite(raw[selected])&(raw[selected]>0))
                            assert not ARMS[arm][0] or not np.any(selected&suspect[y0:y1,x0:x1])
                            if ARMS[arm][1]:
                                main,_=main_region(region)
                                assert not np.any(selected&~main[y0:y1,x0:x1])
                            totals[arm][stat['status']]+=1; totals[arm][stat['reason']]+=1
                        objects[token]=dict(fact_id=exp['fact_id'],whole=measured[native]['whole'],
                            core=measured[native]['core'],core_usable=measured[native]['core_usable'],methods=facts)
                        pix[token]=dict(native=native,source_mask=old['source_mask'],
                            methods={a:dict(crop=facts[a]['selector']['crop'],
                                regions={k:encoded(v) for k,v in regions[a].items()}) for a in ARMS})
                    seconds=time.perf_counter()-started; timing.append(seconds)
                    dump_line(out,dict(frame=frame,segment=name,time=expected['time'],evidence_max_frame=frame,
                        source_depth_sha256=source['depth_sha256'],source_prediction_sha256=source['prediction_sha256'],
                        quality=quality,ds3_exact=True,objects=objects,seconds=seconds))
                    dump_line(pixels_out,dict(frame=frame,suspect=encoded(suspect),objects=pix))
                    if (frame-start+1)%100==0 or frame==stop:
                        print(f'{name} {frame-start+1}/{stop-start+1} exact; primary available={totals["F6_BG_NOISE"]["AVAILABLE"]}',flush=True)
    write_new(HERE/'TIMING.json',dict(total_seconds=time.perf_counter()-tick,frames=len(timing),
        median_frame_ms=1000*float(np.median(timing)),arms={a:dict(c) for a,c in totals.items()},
        inference_http=0,cost_usd=0))
    outputs=[artifact(HERE/f'{n}_measurements.jsonl.gz') for n in SEGMENTS]+\
            [artifact(private/f'{n}_pixels.jsonl.gz') for n in SEGMENTS]+\
            [artifact(HERE/'FREEZE.json'),artifact(HERE/'TIMING.json')]
    write_new(HERE/'MEASUREMENTS_SEALED.json',dict(status='SEALED_BEFORE_NEW_REFERENCE_SCORING',
        frames=len(timing),objects=sum(totals['F2_DS3'][k] for k in ('AVAILABLE','UNKNOWN')),
        method_measurements=sum(sum(v[k] for k in ('AVAILABLE','UNKNOWN')) for v in totals.values()),
        artifacts=outputs,clock_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))


if __name__=='__main__': run()
