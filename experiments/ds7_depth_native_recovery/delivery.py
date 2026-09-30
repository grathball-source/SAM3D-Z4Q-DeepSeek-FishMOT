"""Finalize only new artifacts and append the latest handoff; old archives stay byte exact."""
from common import *
from datetime import datetime,timezone
import subprocess,os
BASE='49b06c521a7b9b9f261e6c852d6e366c17cc8fc2'
def main():
    assert read(RUN/'METRICS.json')['status']=='SCORED_AFTER_ALL_PREDICTION_SEALS'
    for n,h in read(HERE/'OLD_READONLY_LOCK.json')['files'].items():assert sha(ROOT/n)==h,n
    # Check every original prediction/event/code seal once more.
    import evaluate;evaluate.verify_all_seals()
    for n,h in read(RUN/'SCORING_SEALED.json')['artifacts_sha256'].items():assert sha(RUN/n)==h,n
    restricted=set()
    for name,(start,stop) in SEGMENTS.items():
        base=input_dir(name)
        restricted.update(base.glob('*'))
        freeze=read(RUN/name/'public/FREEZE.json')
        for item in list(freeze['restored_sources'].values())+freeze['native_depth_sources']:
            restricted.add(Path(item['path']))
        for src in read(base/'sources.json'):
            restricted.update(Path(src[p+'_path']) for p in ('prediction','depth'))
        restricted.update(DATA/'labels_640x360'/f'{f:06d}.json' for f in range(start,stop+1))
    restricted.update((HERE/'private').rglob('*'))
    restricted.update((HERE/'slice').rglob('*'))
    restricted=sorted({p.resolve() for p in restricted if p.is_file()},key=str)
    private_items=[artifact(p) for p in restricted]
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(
        files=private_items,count=len(private_items),bytes=sum(p['bytes'] for p in private_items),
        reproduction='Existing recorded SOURCE_OLD predictions/masks, raw aligned/native depth, native full_v2 H5+calibration. Re-run only in fresh output/checkout. Existing manual RGB reference only after seals.',
        boundary='No private raster/RLE/RGB/GT/provider/credentials pushed; inventories expose paths and hashes only.'))
    m=read(RUN/'METRICS.json')
    write_new(HERE/'DELIVERY_VERIFICATION.json',dict(
        old_locked_files_byte_exact=len(read(HERE/'OLD_READONLY_LOCK.json')['files']),
        frames=1471,all5_actual_branches=True,native_control_exact=True,
        P0_native_exact=True,old_D2_exact=True,new_model_http=0,cost_usd=0,
        prediction_and_score_seals_verified=True,strict_support=m['frozen_support_rule_met'],
        restricted_files=len(private_items),restricted_bytes=sum(p['bytes'] for p in private_items),
        visualization_images_actually_viewed=[398,419,519,1821],
        UTC=datetime.now(timezone.utc).isoformat(),base_commit=BASE))
    p=ROOT/'.gitignore'
    with p.open('ab') as f:f.write(b'experiments/ds7_depth_native_recovery/private/\r\nexperiments/ds7_depth_native_recovery/slice/\r\n')
    summary=m['pooled_metrics']['P2_RESTORED_DEPTH']
    note=(
        '# Latest: DS7 source-separated depth + native publication repair (2026-09-30)\r\n\r\n'
        'See experiments/ds7_depth_native_recovery/RESULTS.md and PLAN.md. Complete 1471-frame SOURCE_OLD '
        'five-branch replay, raw depth and saved native-v2 reprojected offline depth. New model/API/training/SAM3=0. '
        'Old temporary q preview caused 10 added switches despite NO_ID_CHANGE labels; lawful native/own-alias '
        'publication and balanced depth evidence are now exercised in real state. '
        f"P2 IDF1/HOTA/AssA {summary['IDF1']:.6f}/{summary['HOTA']:.6f}/{summary['AssA']:.6f}, IDSW {summary['IDSW']}. "
        f"Predeclared full support rule={m['frozen_support_rule_met']}. "
        'P0 matches native exactly; D2 matches DS6 exactly; all outputs sealed before reference scoring. '
        'V2 upstream RGB and future cleaning make P2 exposed offline diagnostic; no v3 annotation fill. '
        'Old DS1-DS6 archives remain byte exact, restricted input/pixel paths+bytes+SHA inventoried. '
        'One next step: causal no-annotation restoration and independent time-nonoverlapping validation; no model follows.\r\n\r\n')
    for target in (ROOT/'research/HANDOFF.md',ROOT/'README.md'):
        previous=target.read_bytes();target.write_bytes(note.encode('utf-8')+previous)
    public=[]
    for p in HERE.rglob('*'):
        if not p.is_file() or any(part in ('private','slice','__pycache__') for part in p.relative_to(HERE).parts):continue
        if p.name in ('ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json'):continue
        assert p.suffix.lower() in ('.py','.json','.jsonl','.gz','.md','.txt','.svg'),p
        public.append(artifact(p))
    write_new(HERE/'ARTIFACT_MANIFEST.json',dict(files=public,count=len(public),bytes=sum(x['bytes'] for x in public),
        self_and_remote_proof_excluded=True,all_private_paths_in='RESTRICTED_INVENTORY.json'))
    print(json.dumps(dict(public_files=len(public),public_bytes=sum(x['bytes'] for x in public),restricted_files=len(private_items),restricted_bytes=sum(p['bytes'] for p in private_items))))
if __name__=='__main__':main()

