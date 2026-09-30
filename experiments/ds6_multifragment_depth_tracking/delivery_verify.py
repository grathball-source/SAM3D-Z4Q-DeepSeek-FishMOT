"""Verify final delivery bytes and refresh the new, unsealed public inventory."""
from pathlib import Path
import gzip
import json
from common import HERE,ROOT,RUN,read,sha,artifact,verify_item,write_new
from finalize import json_safe

def main():
    for item in read(HERE/'OLD_READONLY_LOCK.json')['artifacts']:verify_item(item)
    for sealname in ('SCORING_SEALED.json','ACCESS_SEALED.json'):
        seal=read(RUN/sealname)
        if 'artifacts_sha256' in seal:
            for name,digest in seal['artifacts_sha256'].items():assert sha(RUN/name)==digest
        else:
            verify_item(seal['artifact']);verify_item(seal['prediction_all_seal'])
    all_seal=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    for segment,digest in all_seal['seals'].items():
        path=RUN/segment/'public'
        assert sha(path/'PREDICTIONS_SEALED.json')==digest
        for name,expected in read(path/'PREDICTIONS_SEALED.json')['artifacts_sha256'].items():
            assert sha(path/name)==expected
        for p,expected in read(path/'FREEZE.json')['code_sha256'].items():
            assert sha(p)==expected
    for item in read(HERE/'ENVIRONMENT.json')['external_dependency_files']:
        verify_item(item)
    public=[]
    excluded={'ARTIFACT_MANIFEST.json','DELIVERY_VERIFICATION.json','REMOTE_VERIFICATION.json'}
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or path.name in excluded:
            continue
        if any(p in ('private','slice','__pycache__') for p in path.relative_to(HERE).parts):
            continue
        assert path.suffix not in ('.png','.jpg','.jpeg','.npz','.npy','.pyd','.mp4')
        if path.suffix=='.json':json_safe(read(path))
        if path.name.endswith('.jsonl.gz') or path.suffix=='.jsonl':
            opener=gzip.open if path.name.endswith('.gz') else open
            with opener(path,'rt',encoding='utf-8') as handle:
                for line in handle:json_safe(json.loads(line))
        public.append(artifact(path))
    # This delivery inventory is new and not an experiment seal. Its first
    # snapshot captured the active stdout log before flush. Correct only this
    # metadata now; all frozen code, predictions, score outputs remain exact.
    inventory=dict(public=public,total_files=len(public),total_bytes=sum(x['bytes'] for x in public),
        restricted_inventory=artifact(HERE/'RESTRICTED_INVENTORY.json'),
        excluded_self_or_late_proof=sorted(excluded),
        note='Final post-flush snapshot; corrects initial zero-byte FINALIZE_LOG metadata only. No experimental seal changed.',
        private_pixels_uploaded=False)
    with (HERE/'ARTIFACT_MANIFEST.json').open('w',encoding='utf-8',newline='\n') as handle:
        json.dump(inventory,handle,ensure_ascii=False,indent=2);handle.write('\n')
    for item in public:verify_item(item)
    write_new(HERE/'DELIVERY_VERIFICATION.json',dict(status='FINAL_PUBLIC_BYTES_OLD_BYTES_AND_ALL_PREDICTION_SCORE_SEALS_PASS',
        public_files=len(public),public_bytes=inventory['total_bytes'],old_files=347,
        manifest=artifact(HERE/'ARTIFACT_MANIFEST.json'),frozen_code_unchanged=True,
        response_or_model_http=0,cost_usd=0,no_private_pixels=True))
    print(json.dumps(dict(status='PASS',files=len(public),bytes=inventory['total_bytes'])))
if __name__=='__main__':main()

