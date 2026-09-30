"""Inventory public payload, without source pixels or credentials."""
import gzip
import json
from pathlib import Path
from bootstrap import HERE,artifact,write_new,verify


def check(value):
    if isinstance(value,dict):
        assert not ('size' in value and isinstance(value.get('counts'),str)),'raster RLE in public data'
        for key,item in value.items():
            assert key.lower() not in {'api_key','authorization','provider_file_id','access_token','password'}
            assert key not in {'source_mask','rgb_base64','image_base64','instance_id_raster'}
            check(item)
    elif isinstance(value,list):
        for item in value: check(item)


def run():
    files=[]
    for p in sorted(HERE.iterdir()):
        if not p.is_file() or p.name in ('ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json'): continue
        assert p.suffix not in ('.png','.npz','.npy','.jpg','.pyc')
        if p.name.endswith('.jsonl.gz'):
            with gzip.open(p,'rt',encoding='utf-8') as rows:
                for row in rows: check(json.loads(row))
        elif p.suffix=='.json': check(json.loads(p.read_text(encoding='utf-8')))
        files.append(artifact(p))
    write_new(HERE/'ARTIFACT_MANIFEST.json',dict(files=len(files),bytes=sum(i['bytes'] for i in files),items=files,
        private_pixels_uploaded=False,public_payload_checked_for_raster_RLE_and_credential_fields=True,
        paths_hashes_in_restricted_inventory_allowed=True,inference_http=0,cost_usd=0,
        postscore_only_code=['finalize.py','repair_figure_captions.py','render_additional_failures.py',
                             'sync_docs.py','public_manifest.py','verify_remote.py'],
        original_freeze_and_scoring_code_unchanged=True))
    print(f'Public payload {len(files)} files; {sum(i["bytes"] for i in files)} bytes; no raster RLE/credentials')


if __name__=='__main__': run()
