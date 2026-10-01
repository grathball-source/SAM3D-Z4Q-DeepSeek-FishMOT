"""Verify old/sealed bytes and inventory actual public/restricted DS10 artifacts."""
from common import *

def main():
    import evaluate
    evaluate.verify_all_seals()
    lock=read(HERE/'OLD_READONLY_LOCK.json')
    for p,h in lock['files'].items():assert sha(ROOT/p)==h,p
    for n,h in read(RUN/'SCORING_SEALED.json')['artifacts_sha256'].items():assert sha(RUN/n)==h,n
    restricted=set()
    for name,(start,stop) in SEGMENTS.items():
        freeze=read(RUN/name/'public/FREEZE.json')
        for p,h in freeze['code_sha256'].items():assert sha(p)==h,p
        for item in list(freeze['restored_sources'].values())+freeze['native_depth_sources']:
            restricted.add(Path(item['path']))
        base=input_dir(name);restricted.update(base.glob('*'))
        for src in read(base/'sources.json'):
            restricted.update(Path(src[k+'_path']) for k in ('prediction','depth'))
        restricted.update(DATA/'labels_640x360'/f'{f:06d}.json' for f in range(start,stop+1))
    for folder in ('private','slice'):restricted.update((HERE/folder).rglob('*'))
    items=[artifact(p) for p in sorted({p.resolve() for p in restricted if p.is_file()},key=str)]
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(files=items,count=len(items),bytes=sum(x['bytes'] for x in items),
        reproduction='Fresh DS10 outputs using original SOURCE_OLD masks/raw/scan, native-v2 H5/calibration, existing dependencies. Reference labels only after prediction seal.',
        boundary='Real depth/ROI/private publication figures, source RLE, GT pixels remain local; public numeric graphs only. No credentials or model calls.'))
    with (ROOT/'.gitignore').open('ab') as f:
        for folder in ('private','slice'):f.write((HERE.relative_to(ROOT).as_posix()+'/'+folder+'/\r\n').encode())
    m=read(RUN/'METRICS.json');p=m['pooled_metrics'];n=p['SAM3_NATIVE'];v=p['D10_RESTORED']
    note=('# Latest: DS10 depth failure repair (2026-10-01)\r\n\r\n'
        'See experiments/ds10_depth_failure_repair/RESULTS.md, PLAN.md and diagnosis/*.md. '
        'Four independent real state branches, full same-source 1471 exposed development frames. '
        f"New v2 IDF1/HOTA/AssA {v['IDF1']:.6f}/{v['HOTA']:.6f}/{v['AssA']:.6f}, IDSW {v['IDSW']}; "
        f"native {n['IDF1']:.6f}/{n['HOTA']:.6f}/{n['AssA']:.6f}, IDSW {n['IDSW']}. "
        f"Native target rule={m['frozen_support_rule_met']}. Geometry is not an acceptance gate. "
        'Joint last-measurement depth forecast and current-object normalized null repair; no separate component attribution. '
        'All predictions/inputs/code sealed before scoring, F9 exact DS9 reproduction, predeclared inert diagnostic precision contract. '
        'V2 upstream RGB/future support: offline diagnostic only. No physical surface truth/independent-video validation. '
        'No model HTTP, training, SAM3/completion service or cost; old DS1-9 tracked bytes unchanged. '
        'One next step only in NEXT_STEP_PLAN.md, not started.\r\n\r\n')
    for path in (ROOT/'README.md',ROOT/'research/HANDOFF.md'):path.write_bytes(note.encode()+path.read_bytes())
    write_new(HERE/'DELIVERY_VERIFICATION.json',dict(base_commit=lock['base_commit'],old_byte_exact=lock['count'],
        all_seals_verified=True,frames=1471,branches=4,restricted_count=len(items),new_model_http=0,cost_usd=0,
        native_target_met=m['frozen_support_rule_met']))
    public=[]
    for path in HERE.rglob('*'):
        if not path.is_file() or any(x in ('private','slice','__pycache__') for x in path.relative_to(HERE).parts):continue
        if path.name in ('ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json'):continue
        assert path.suffix.lower() in ('.py','.md','.json','.jsonl','.gz','.txt','.svg','.png'),path
        if path.suffix.lower()=='.png':assert path.name=='BACKGROUND_DENSITY.png','only known numerical PNG public'
        if path.suffix=='.gz':
            for row in rows(path):assert '"counts"' not in json.dumps(row) and 'data:image/' not in json.dumps(row),path
        if path.suffix=='.svg':assert 'data:image/' not in path.read_text(encoding='utf-8'),path
        public.append(artifact(path))
    write_new(HERE/'ARTIFACT_MANIFEST.json',dict(files=public,count=len(public),bytes=sum(x['bytes'] for x in public),self_and_remote_proof_excluded=True))
    print(json.dumps(dict(public_files=len(public),public_bytes=sum(x['bytes'] for x in public),restricted_files=len(items))))
if __name__=='__main__':main()
