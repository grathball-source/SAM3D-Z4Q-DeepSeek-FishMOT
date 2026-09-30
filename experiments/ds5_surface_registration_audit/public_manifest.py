"""Inventory new public payload; reject pixel/RLE and credential content."""
import gzip
import json
import re
from audit import HERE,artifact,write_new


def inspect(value,path):
    if isinstance(value,dict):
        assert not ('size' in value and isinstance(value.get('counts'),str)),(path,'RLE')
        for key,item in value.items():
            assert key not in ('imageData','rgb_pixels','depth_pixels','gt_raster','api_key','authorization','access_token'),(path,key)
            if key in ('source_index','source_indices','pixels','points','xy','depth_mm','native_values'):
                metadata=isinstance(item,list) and all(isinstance(x,dict) and set(x)=={'path','bytes','sha256'} for x in item)
                assert not isinstance(item,list) or metadata,(path,key,'pixel/point array')
            inspect(item,path)
    elif isinstance(value,list):
        for item in value: inspect(item,path)
    elif isinstance(value,str):
        assert not value.startswith('data:image'),path
        assert not re.search(r'\bsk-[A-Za-z0-9_-]{20,}',value),path


def run():
    files=[]
    for p in sorted(HERE.rglob('*')):
        if not p.is_file() or 'private' in p.relative_to(HERE).parts or '__pycache__' in p.parts: continue
        if p.name in ('PUBLIC_MANIFEST.json','REMOTE_VERIFICATION.json'): continue
        assert p.suffix.lower() not in ('.png','.jpg','.jpeg','.npy','.npz','.mp4'),p
        if p.name.endswith('.jsonl.gz'):
            with gzip.open(p,'rt',encoding='utf-8') as stream:
                for line in stream: inspect(json.loads(line),str(p))
        elif p.suffix=='.json':
            inspect(json.loads(p.read_text(encoding='utf-8-sig')),str(p))
        elif p.suffix=='.svg':
            s=p.read_text(encoding='utf-8')
            assert '<image ' not in s and 'data:image' not in s,p
        files.append(artifact(p))
    write_new(HERE/'PUBLIC_MANIFEST.json',dict(status='PUBLIC_PAYLOAD_CHECKED_NO_PIXELS_OR_CREDENTIALS',
        files=files,total_bytes=sum(f['bytes'] for f in files),private_pixels_uploaded=False,model_http=0))
    print(json.dumps(dict(files=len(files),bytes=sum(f['bytes'] for f in files))))


if __name__=='__main__': run()

