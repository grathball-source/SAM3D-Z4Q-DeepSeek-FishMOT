"""Append-only DS11 restricted input/output inventory and final byte acceptance."""
from common import *

def main():
    seal=read(RUN/'SCORING_SEALED.json')
    for n,h in seal['artifacts_sha256'].items():assert sha(RUN/n)==h
    locked=read(HERE/'OLD_READONLY_LOCK.json')
    for p,h in locked['files'].items():assert sha(ROOT/p)==h,p
    for name in SEGMENTS:
        frozen=read(RUN/name/'public/FREEZE.json')
        for p,h in frozen['code_sha256'].items():assert sha(p)==h,p
    items={}
    def walk(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=set(value):
                p=Path(value['path']);parts=str(p).replace('\\','/').lower()
                if '/private/' in parts or '/data/alignedfeeding_v1/' in parts:
                    verify_item(value);items[str(p.resolve())]={k:value[k] for k in ('path','bytes','sha256')}
            for v in value.values():walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(read(HERE/'SOURCE_INVENTORY.json'))
    for start,stop in SEGMENTS.values():
        for frame in range(start,stop+1):
            p=DATA/'labels_640x360'/f'{frame:06d}.json'
            items[str(p.resolve())]=artifact(p)
    for owner in ('private','slice'):
        for p in (HERE/owner).rglob('*'):
            if p.is_file():items[str(p.resolve())]=artifact(p)
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(status='ACTUAL_RESTRICTED_BYTES_NOT_IN_GIT',
        files=list(items.values()),files_count=len(items),total_bytes=sum(x['bytes'] for x in items.values()),
        reproduction='Use original SOURCE_OLD saved prediction/depth inputs, exact shared native-v2/cache producer/source digests, existing Python/deps; run frozen local branches. Figures require original depth and masks. No API keys.',
        access='Original input/GT/raster/private slice remain local; only numeric predictions/facts/metrics/reports are public.',
        physical_scope='Exposed offline native-v2 with upstream RGB/future cleaning; not annotation-v3.',
        scoring_seal=artifact(RUN/'SCORING_SEALED.json'),old_files_byte_exact=locked['count']))
    write_new(HERE/'POSTRUN_ACCEPTANCE.json',dict(status='PASS',old_immutable_files=locked['count'],
        frozen_runtime_sources_byte_exact=True,all_prediction_scoring_seals_verified=True,
        source_inventory_sha256=sha(HERE/'SOURCE_INVENTORY.json'),restricted_inventory_sha256=sha(HERE/'RESTRICTED_INVENTORY.json'),
        new_model_http=0,smoke=0,SAM3_inference=0,training=0,completion_service=0,cost_usd=0))
    print('Private inventory',len(items),'old immutable',locked['count'])
if __name__=='__main__':main()
