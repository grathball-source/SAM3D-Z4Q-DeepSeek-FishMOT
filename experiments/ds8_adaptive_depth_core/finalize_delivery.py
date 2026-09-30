"""Finalize DS7+DS8 without rewriting frozen experiments or publishing pixels."""
from common import *
from datetime import datetime,timezone
import importlib.util,gzip
BASE='49b06c521a7b9b9f261e6c852d6e366c17cc8fc2'
OLDTRIAL=ROOT/'experiments/ds7_depth_native_recovery'

def main():
    import evaluate
    evaluate.verify_all_seals()
    lock=read(HERE/'OLD_READONLY_LOCK.json')
    for p,h in lock['files'].items():assert sha(ROOT/p)==h,p
    for p,h in lock['ds7_frozen_code'].items():assert sha(p)==h,p
    verify_item(lock['ds7_all_seal']);verify_item(lock['ds7_scoring_seal'])
    restricted=set()
    for trial in (OLDTRIAL,HERE):
        run=trial/'run'
        seal=read(run/'SCORING_SEALED.json')
        for n,h in seal['artifacts_sha256'].items():assert sha(run/n)==h,n
        for name,(start,stop) in SEGMENTS.items():
            freeze=read(run/name/'public/FREEZE.json')
            for p,h in freeze['code_sha256'].items():assert sha(p)==h,p
            for item in list(freeze['restored_sources'].values())+freeze['native_depth_sources']:
                restricted.add(Path(item['path']))
            base=input_dir(name);restricted.update(base.glob('*'))
            for src in read(base/'sources.json'):
                restricted.update(Path(src[p+'_path']) for p in ('prediction','depth'))
            restricted.update(DATA/'labels_640x360'/f'{f:06d}.json' for f in range(start,stop+1))
        for folder in ('private','slice'):
            restricted.update((trial/folder).rglob('*'))
    private_items=[artifact(p) for p in sorted({p.resolve() for p in restricted if p.is_file()},key=str)]
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(files=private_items,count=len(private_items),
        bytes=sum(x['bytes'] for x in private_items),
        reproduction='Fresh output/checkout with listed SOURCE_OLD masks/raw/native depth, full_v2 H5/calibration/projection and existing manual RGB reference only after seal. No new SAM3 or model.',
        boundary='Paths/bytes/SHA only; actual private pixels, GT rasters, RLE inputs and credentials remain local.'))
    with (ROOT/'.gitignore').open('ab') as handle:
        for trial in (OLDTRIAL,HERE):
            for folder in ('private','slice','prefreeze_empty_attempt1'):
                handle.write((trial.relative_to(ROOT).as_posix()+'/'+folder+'/\r\n').encode())
    m=read(RUN/'METRICS.json');v=m['pooled_metrics']['P2_RESTORED_DEPTH']
    native=m['pooled_metrics']['SAM3_NATIVE']
    note=('# Latest: DS7/DS8 depth failure audit and adaptive-core trial (2026-10-01)\r\n\r\n'
        'See experiments/ds8_adaptive_depth_core/RESULTS.md / PLAN.md and experiments/ds7_depth_native_recovery/RESULTS.md. '
        'Two complete 1471-frame five-branch SOURCE_OLD replays; no model/API/SMOKE/training/SAM3/completion calls or cost. '
        'DS7 fixes lawful own-branch native publication and source-separated depth; DS8 changes only current-mask core geometry. '
        f"P2 IDF1/HOTA/AssA {v['IDF1']:.6f}/{v['HOTA']:.6f}/{v['AssA']:.6f}, IDSW {v['IDSW']}; "
        f"same-source native {native['IDF1']:.6f}/{native['HOTA']:.6f}/{native['AssA']:.6f}, IDSW {native['IDSW']}. "
        f"Frozen full depth support={m['frozen_support_rule_met']}. "
        'P0 native exact, old D2 exact, all masks preserved; sealed then independent official scoring and switch accounting. '
        'Restored native v2 has no annotation fill but upstream RGB+future cleaning: exposed offline diagnostic. '
        'No physical-mm truth or independent video validation; private artifacts inventoried by actual path/bytes/SHA. '
        'One next step is defined in latest RESULTS.md; no automatic model addition.\r\n\r\n')
    for p in (ROOT/'README.md',ROOT/'research/HANDOFF.md'):
        p.write_bytes(note.encode('utf-8')+p.read_bytes())
    write_new(HERE/'DELIVERY_VERIFICATION.json',dict(base_commit=BASE,UTC=datetime.now(timezone.utc).isoformat(),
        old_DS1_DS6_byte_exact=lock['count'],DS7_frozen_code_and_prediction_score_seals_exact=True,
        frames_per_trial=1471,branches_per_trial=5,trials=2,new_model_http=0,cost_usd=0,
        raw_and_restored_scopes_separate=True,all_seals_verified=True,strict_support=m['frozen_support_rule_met'],
        restricted_count=len(private_items),restricted_bytes=sum(x['bytes'] for x in private_items),
        private_images_actually_viewed=dict(DS7=[398,419,519,1821],DS8=[519,764,1390,1745,1805])))
    public=[]
    for trial in (OLDTRIAL,HERE):
        for p in trial.rglob('*'):
            if not p.is_file() or any(k in ('private','slice','__pycache__','prefreeze_empty_attempt1') for k in p.relative_to(trial).parts):continue
            if p.name in ('ARTIFACT_MANIFEST.json','REMOTE_VERIFICATION.json','FINAL_REMOTE_VERIFICATION.json'):continue
            assert p.suffix.lower() in ('.py','.md','.json','.jsonl','.gz','.txt','.svg'),p
            if p.suffix=='.gz':
                with gzip.open(p,'rt',encoding='utf-8') as h:
                    for line in h:
                        assert '"counts"' not in line and 'data:image/' not in line,p
            public.append(artifact(p))
    write_new(HERE/'ARTIFACT_MANIFEST.json',dict(files=public,count=len(public),
        bytes=sum(x['bytes'] for x in public),remote_proof_and_self_excluded=True))
    print(json.dumps(dict(public_files=len(public),public_bytes=sum(x['bytes'] for x in public),
        restricted_files=len(private_items),strict_support=m['frozen_support_rule_met'])))
if __name__=='__main__':main()
