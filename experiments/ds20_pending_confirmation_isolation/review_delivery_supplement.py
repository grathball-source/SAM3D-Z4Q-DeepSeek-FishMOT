"""Review late numeric diagnostics and appended ledger after the closed full audit."""
from common import *
import public_content_audit as privacy


def main():
    proof=read(HERE/'PUBLIC_CONTENT_AUDIT.json')
    assert proof['status']=='PASS_PUBLIC_CLOSED_CONTENT_PRIVACY_AND_FILE_LIMIT'
    prior={Path(item['path']).resolve():item for item in proof['files']}
    output=HERE/'PUBLIC_CONTENT_SUPPLEMENT.json'
    inflight=HERE/'logs/review_delivery_supplement.txt'
    checked=[]
    for path in HERE.rglob('*'):
        if not path.is_file() or privacy.excluded(path) or path in (output,inflight):continue
        item=artifact(path)
        old=prior.get(path.resolve())
        if old==item:continue
        assert item['bytes']<privacy.LIMIT
        assert old is None or path==HERE/'EXECUTION_LOG.jsonl',('REVIEWED_FILE_CHANGED',path)
        assert path.suffix in ('.json','.jsonl','.py','.md','.txt'),('UNREVIEWED_LATE_BINARY',path)
        text=path.read_text(encoding='utf-8')
        assert not privacy.CREDENTIAL.search(text) and not privacy.PROVIDER.search(text)
        assert not privacy.re.search(r'data:image/[^;]+;base64,[A-Za-z0-9+/]{128,}',text)
        if path.suffix=='.json':privacy.inspect(json.loads(text),path)
        elif path.suffix=='.jsonl':
            for line in text.splitlines():privacy.inspect(json.loads(line),path)
        assert artifact(path)==item
        checked.append(item)
    assert not privacy.findings,privacy.findings
    write_new(output,dict(status='PASS_LATE_NUMERIC_DIAGNOSTICS_AND_LEDGER_CONTENT',
        full_audit=artifact(HERE/'PUBLIC_CONTENT_AUDIT.json'),additional_or_appended_files=checked,
        counts=privacy.counts,private_pixels_or_GT_rasters_read=False,
        scope='Only late closed numeric/code/text artifacts and appended ledger; old public bytes match full audit. Own output/inflight log and future delivery hash receipts are typed metadata, finally covered by staged/remote byte verification.',
        model_http=0,cost_usd=0))
    print('Late content PASS',len(checked),'new or appended files')


if __name__=='__main__':main()
