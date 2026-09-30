"""Non-destructive public delivery and true restricted artifact inventory."""
from common import *
import gzip

def main():
    import evaluate
    evaluate.verify_all_seals()
    lock=read(HERE/'OLD_READONLY_LOCK.json')
    for p,h in lock['files'].items():assert sha(ROOT/p)==h,p
    score=read(RUN/'SCORING_SEALED.json')
    for n,h in score['artifacts_sha256'].items():assert sha(RUN/n)==h,n
    restricted=set()
    for name,(start,stop) in SEGMENTS.items():
        freeze=read(RUN/name/'public/FREEZE.json')
        for p,h in freeze['code_sha256'].items():assert sha(p)==h,p
        for item in list(freeze['restored_sources'].values())+freeze['native_depth_sources']:
            restricted.add(Path(item['path']))
        base=input_dir(name);restricted.update(base.glob('*'))
        for src in read(base/'sources.json'):
            restricted.update(Path(src[p+'_path']) for p in ('prediction','depth'))
        restricted.update(DATA/'labels_640x360'/f'{f:06d}.json' for f in range(start,stop+1))
    for folder in ('private','slice'):
        restricted.update((HERE/folder).rglob('*'))
    items=[artifact(p) for p in sorted({p.resolve() for p in restricted if p.is_file()},key=str)]
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(files=items,count=len(items),
        bytes=sum(x['bytes'] for x in items),
        reproduction='Fresh outputs using original SOURCE_OLD masks/raw depth/scan, full_v2 H5 and projection calibration, existing dependencies; reference labels only after prediction seal.',
        boundary='Actual source/RLE/depth/private plots/GT pixels stay local; no credential reads or model calls.'))
    with (ROOT/'.gitignore').open('ab') as h:
        for folder in ('private','slice'):
            h.write((HERE.relative_to(ROOT).as_posix()+'/'+folder+'/\r\n').encode())
    m=read(RUN/'METRICS.json');v=m['pooled_metrics']['J2_RESTORED_DEPTH'];n=m['pooled_metrics']['SAM3_NATIVE']
    note=('# Latest: DS9 lawful H0 normalized joint geometry/depth trial (2026-10-01)\r\n\r\n'
        'See experiments/ds9_joint_h0_depth/RESULTS.md and PLAN.md. '
        'Six independent genuine state branches, 1471 same-source exposed frames, sealed before TrackEval and physical reference audit. '
        f"J2 IDF1/HOTA/AssA {v['IDF1']:.6f}/{v['HOTA']:.6f}/{v['AssA']:.6f}, IDSW {v['IDSW']}; "
        f"native {n['IDF1']:.6f}/{n['HOTA']:.6f}/{n['AssA']:.6f}, IDSW {n['IDSW']}. "
        f"Frozen native-target rule={m['frozen_support_rule_met']}. "
        'Compare geometry/zero/permutation before claiming independent depth gain. '
        'Original strict diagnostic metadata comparison failed; scoring completed with a separately sealed 281 one-ULP inert metadata exception. '
        'V2 has upstream RGB/future cleaning: offline diagnostic only; physical depth truth and independent-video validation unestablished. '
        'No model HTTP/smoke/training/SAM3/completion service or cost. DS1–8 old tracked files remain byte-exact. '
        'Public delivery requires normal main push and actual ref/key-byte checks. One next step only in latest report.\r\n\r\n')
    for p in (ROOT/'README.md',ROOT/'research/HANDOFF.md'):p.write_bytes(note.encode()+p.read_bytes())
    write_new(HERE/'DELIVERY_VERIFICATION.json',dict(base_commit=lock['base_commit'],
        old_tracked_byte_exact=lock['count'],frames=1471,branches=6,all_seals_verified=True,
        new_model_http=0,cost_usd=0,restricted_count=len(items),strict_support=m['frozen_support_rule_met']))
    public=[]
    for p in HERE.rglob('*'):
        if not p.is_file() or any(k in ('private','slice','__pycache__') for k in p.relative_to(HERE).parts):continue
        if p.name in ('ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json'):continue
        assert p.suffix.lower() in ('.py','.md','.json','.jsonl','.gz','.txt','.svg'),p
        if p.suffix=='.gz':
            for line in rows(p):assert '"counts"' not in json.dumps(line) and 'data:image/' not in json.dumps(line),p
        public.append(artifact(p))
    write_new(HERE/'ARTIFACT_MANIFEST.json',dict(files=public,count=len(public),
        bytes=sum(x['bytes'] for x in public),self_and_remote_proof_excluded=True))
    print(json.dumps(dict(public_files=len(public),public_bytes=sum(x['bytes'] for x in public),restricted_files=len(items))))
if __name__=='__main__':main()
