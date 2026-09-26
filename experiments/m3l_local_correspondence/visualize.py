"""Post-score QA panel. Never send this annotated or GT-containing image to a model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path('/home/xiongxiong/m3l_local_correspondence_20260926')


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]


def run(pair, token, arm='FIRST'):
    assert (ROOT/'sender/public/RESPONSES_SEALED.json').exists()
    frames=json.loads((ROOT/'public/SOURCE_MANIFEST.json').read_text())['frames']
    i=int(pair[1:])-1
    source,target=frames[i:i+2]
    src_obs={x['token']:x for x in source['observations']}
    dst_obs={x['token']:x for x in target['observations']}
    assert token in src_obs
    results=lines(ROOT/'public/final_score/TOKEN_MATCH_RESULTS.jsonl')
    assert arm in ('FIRST','REPEAT')
    result=next(x for x in results if x['attempt_id']==pair+'-'+arm and x['source_token']==token)
    baseline=lines(ROOT/'public/final_score/BASELINE_RESULTS.jsonl')
    b={x['mode']:x['target_token'] for x in baseline if x['pair']==pair and x['source_token']==token}
    path1=ROOT/'sender/media'/source['media_file']
    path2=ROOT/'sender/media'/target['media_file']
    for frame,path in ((source,path1),(target,path2)):
        assert hashlib.sha256(path.read_bytes()).hexdigest()==frame['image_sha256']
    a=cv2.imread(str(path1)); z=cv2.imread(str(path2))
    assert a is not None and z is not None and a.shape==z.shape
    h,w=a.shape[:2]
    canvas=np.full((h+240,w*2+100,3),255,np.uint8)
    canvas[70:70+h,20:20+w]=a
    canvas[70:70+h,80+w:80+w*2]=z
    start=src_obs[token]['center_norm']
    p=(int(20+start[0]*w),int(70+start[1]*h))
    cv2.circle(canvas,p,7,(0,0,0),2)
    edges=[('MODEL', result['raw_target'] if result['decision']=='MATCH' else None,(255,80,0)),
           ('N-C',b['N-C'],(180,0,180)),('N-I',b['N-I'],(0,140,220)),
           ('GT_POSTHOC',result['truth_target'],(0,150,0))]
    for name,dest,color in edges:
        if dest in dst_obs:
            pos=dst_obs[dest]['center_norm']
            q=(int(80+w+pos[0]*w),int(70+pos[1]*h))
            cv2.line(canvas,p,q,color,2)
            cv2.circle(canvas,q,5,color,2)
    cv2.putText(canvas,f'{pair}-{arm}: {source["image_id"]} -> {target["image_id"]}, source {token}',
                (15,30),cv2.FONT_HERSHEY_SIMPLEX,.52,(0,0,0),1,cv2.LINE_AA)
    for j,(name,dest,color) in enumerate(edges):
        cv2.putText(canvas,f'{name}: {dest or "none"}',(20,440+j*24),
                    cv2.FONT_HERSHEY_SIMPLEX,.47,color,1,cv2.LINE_AA)
    cv2.putText(canvas,f'Model status {result["decision"]}; GT {result["scoreability_reason"] or "UNIQUE"}',
                (20,545),cv2.FONT_HERSHEY_SIMPLEX,.43,(0,0,0),1,cv2.LINE_AA)
    out=ROOT/'private_visual'/f'{pair}_{arm}_{token.replace(":","_")}_POSTHOC.png'
    out.parent.mkdir(exist_ok=True)
    assert not out.exists()
    assert cv2.imwrite(str(out),canvas)
    print(json.dumps(dict(path=str(out),bytes=out.stat().st_size,
         sha256=hashlib.sha256(out.read_bytes()).hexdigest(),model=result['decision'],
         scoreability=result['scoreability_reason'], GT_only_posthoc=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('pair')
    p.add_argument('token')
    p.add_argument('--arm', default='FIRST', choices=('FIRST','REPEAT'))
    a=p.parse_args()
    run(a.pair,a.token,a.arm)
