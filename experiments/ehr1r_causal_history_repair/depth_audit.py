"""Recheck every new depth-bearing frame against actual raw HDF5 and masks."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from pycocotools import mask as mu

from preflight import AO1, DEV_OBS, VAL, read, put
from prepare import ASSIGN, DATA, DEV_DEPTH, digest
from contract import dumps

SENSOR_SOURCE=Path('/home/xiongxiong/dmot-experiments/sam3_depth_birth_inherit_20260917')
sys.path.insert(0,str(SENSOR_SOURCE))
from features import RawSensor, array_sha, stats, exclusive_core  # noqa: E402


def selected(path,frames):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        return {r['frame']:r for line in f if (r:=json.loads(line))['frame'] in frames}


def main(run):
    episodes=read(run/'public/EPISODE_FACTS.json')
    cases={c['case_alias']:c for c in read(AO1/'public/SOURCE_MANIFEST.json')['cases']}
    selected_frames={s:set() for s in ASSIGN}
    expected_hashes={}
    for p in episodes:
        split=cases[p['request_id'].split('-')[-1]]['split']
        for part in ('PRE_HISTORY','POST_HISTORY_TO_Q'):
            for segment in p[part].values():
                selected_frames[split].update(x['source_frame'] for x in segment['observations'])
                for x in segment['observations']:
                    src=x['source_fact_ids'][0];n=int(src.split('-N')[1])
                    expected_hashes[(split,x['source_frame'],n)]=x['source_mask_rle_sha256']
        selected_frames[split].update(row['frame'] for row in p['INTERACTION_OBSERVATIONS'])
        for row in p['INTERACTION_OBSERVATIONS']:
            for x in row['anonymous_observations']:
                n=int(x['source_fact_ids'][0].split('-N')[1])
                expected_hashes[(split,row['frame'],n)]=x['source_mask_rle_sha256']
    sources={}
    for split,frames in selected_frames.items():
        op=DEV_OBS if split=='development' else VAL/'observations_validation.jsonl.gz'
        dp=DEV_DEPTH if split=='development' else VAL/'features_validation.jsonl.gz'
        sources[split]=(selected(op,frames),selected(dp,frames),selected(ASSIGN[split],frames))
        assert all(set(x)==frames for x in sources[split]),(split,[len(x) for x in sources[split]],len(frames))
    sensor=RawSensor();summary=[]
    try:
        jobs=sorted((sources[split][0][f]['global_frame'],split,f) for split,frames in selected_frames.items() for f in frames)
        for i,(global_frame,split,f) in enumerate(jobs,1):
            obs,features,assign=sources[split]
            o,d,a=obs[f],features[f],assign[f]
            for key,encoded in a['masks'].items():
                n=int(key.split(':')[1]);expected=expected_hashes.get((split,f,n))
                if expected is not None:
                    assert hashlib.sha256(dumps(encoded).encode()).hexdigest()==expected
            assert o['time']==d['time']==a['time'] and d['evidence_max_global_frame']<=global_frame
            assert d['sensor_available']
            raw=sensor.load(global_frame)
            assert raw.shape==(360,640) and array_sha(raw)==d['raw_array_sha256']
            rgb=DATA/f'{global_frame-1:06d}.jpg'
            if i==1 or i%50==0:
                pixels=cv2.imread(str(rgb));assert pixels is not None and pixels.shape[:2]==(1080,1920)
            masks={}
            for n in a['variants']['N0']:
                encoded=a['masks'][n['mask']]
                masks[n['id']]=mu.decode(dict(size=encoded['size'],counts=encoded['counts'].encode())).astype(bool)
            occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros(raw.shape,'u2'))
            for profile in d['observations']:
                mask=masks[profile['id']]
                _,core=exclusive_core(mask,occupancy)
                assert stats(raw,mask)==profile['whole']
                assert stats(raw,core)==profile['core']
            summary.append(dict(split=split,frame=f,global_frame=global_frame,raw_array_sha256=d['raw_array_sha256'],
                                original_rgb_path=str(rgb),profiles=len(d['observations']),
                                invalid_depth_pixels=int((raw<=0).sum())))
            if i%100==0:print('depth_checked',i,'of',len(jobs),flush=True)
    finally:sensor.close()
    put(run/'public/DEPTH_INPUT_AUDIT.json',dict(status='ALL_NEW_DEPTH_FRAMES_RAW_HDF5_MASK_PARITY',
        frame_count=len(summary),profile_count=sum(x['profiles'] for x in summary),
        source='aligned/raw_depth_mm matched to assignment masks and causal feature stream',
        unit='pipeline_mm; external water-surface calibration unverified',frames=summary))
    print('DEPTH_AUDIT_PASS',len(summary),sum(x['profiles'] for x in summary))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
