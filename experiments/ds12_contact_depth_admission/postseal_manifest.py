"""Inventory actual public delivery bytes after all scientific output is sealed."""
from common import *
import re, subprocess

def main():
    assert read(HERE/'POSTRUN_ACCEPTANCE.json')['status']=='PASS'
    names=subprocess.check_output(['git','ls-files','--cached','--others',
        '--exclude-standard','--','experiments/ds12_contact_depth_admission'],cwd=ROOT).decode().splitlines()
    names+=['.gitignore','research/HANDOFF.md']
    names=sorted(set(names)-{'experiments/ds12_contact_depth_admission/ARTIFACT_MANIFEST.json',
        'experiments/ds12_contact_depth_admission/REMOTE_VERIFICATION.json'})
    items=[]
    forbidden={'image_url','base64','rle','counts','depth_map','rgb_pixels','gt_raster'}
    def check_numeric(v):
        if isinstance(v,dict):
            assert not (forbidden & set(v)), 'Public raster/payload key'
            for x in v.values():check_numeric(x)
        elif isinstance(v,list):
            for x in v:check_numeric(x)
    for name in names:
        p=ROOT/name
        assert not ({'private','slice','__pycache__'} & set(p.relative_to(ROOT).parts)),name
        assert p.suffix.lower() not in {'.png','.jpg','.jpeg','.npy','.npz','.pyc'},name
        assert p.stat().st_size<100_000_000,name
        data=p.read_bytes()
        assert not re.search(rb'\bsk-[A-Za-z0-9_-]{20,}|\bfile-[A-Za-z0-9]{20,}',data),name
        if p.suffix=='.svg':assert b'<image' not in data.lower(),name
        if '/public/' in name and p.name.endswith('.jsonl.gz'):
            for row in rows(p):check_numeric(row)
        items.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    write_new(HERE/'ARTIFACT_MANIFEST.json',dict(status='PUBLIC_DELIVERY_BYTE_INVENTORY',
        files=items,files_count=len(items),total_bytes=sum(x['bytes'] for x in items),
        predictions_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),
        scoring_seal=artifact(RUN/'SCORING_SEALED.json'),
        frozen_runtime_acceptance=artifact(HERE/'POSTRUN_ACCEPTANCE.json'),
        restricted_inventory=artifact(HERE/'RESTRICTED_INVENTORY.json'),
        exclusions=['This manifest itself','Append-only REMOTE_VERIFICATION.json proof commit',
            'Ignored private/slice inputs and pixels listed in RESTRICTED_INVENTORY.json'],
        reproduction='See README.md, PLAN.md, source/code freezes and EXECUTION_LOG.jsonl. Original restricted inputs and existing interpreter/dependencies required.',
        model_http=0,cost_usd=0))
    print(json.dumps(dict(files=len(items),bytes=sum(x['bytes'] for x in items),status='PASS')))

if __name__=='__main__':main()
