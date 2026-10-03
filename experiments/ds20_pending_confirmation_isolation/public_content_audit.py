"""Postseal public-byte privacy review; no private pixels or GT are followed."""
from pathlib import Path
import ast,gzip,hashlib,json,re,subprocess
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=HERE/'run'
DS18=ROOT/'experiments/ds18_association_evidence_interface_repair'
LIMIT=100*1024*1024
OUTPUT=HERE/'PUBLIC_CONTENT_AUDIT.json'
CREDENTIAL=re.compile(r'(?i)(?:sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_-]{24,}|AIza[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)')
PROVIDER=re.compile(r'\bfile-[A-Za-z0-9]{20,}\b')
findings=[]
counts=dict(structured_files=0,json_rows=0,text_files=0,embedded_failure_records=0,
    hashed_array_bindings=0,numeric_long_arrays=0,approved_aggregate_PNG=0,chunk_headers=0,external_cache_refs=0)
chunk_refs=[];chunk_headers=[]


def sha(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def artifact(path):
    path=Path(path).resolve()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))


def excluded(path):
    return any(part=='private' or part=='__pycache__' or part.startswith('slice') for part in path.relative_to(HERE).parts)


def violation(path,kind,route):findings.append(dict(path=str(path),kind=kind,field=route))


def inspect(value,path,route='$'):
    if isinstance(value,dict):
        if {'dtype','shape','sha256'}<=value.keys():counts['hashed_array_bindings']+=1
        if 'counts' in value and isinstance(value.get('size'),list):violation(path,'RLE_CONTAINER',route)
        for key,item in value.items():
            if key.lower() in ('base64','pixel_values','rgb_pixels','depth_raster','provider_file_id','api_key','authorization','access_token','secret_key','private_key') and item not in (None,'',[],False):
                violation(path,'RESTRICTED_PAYLOAD_KEY',route+'.'+key)
            if key.lower() in ('pixels','positions','source_indices','selected_pixels','mask') and isinstance(item,list) and len(item)>16:
                violation(path,'RAW_SPATIAL_ARRAY_CANDIDATE',route+'.'+key)
            inspect(item,path,route+'.'+key)
    elif isinstance(value,list):
        if len(value)>=64 and all(isinstance(item,(int,float)) and not isinstance(item,bool) for item in value):counts['numeric_long_arrays']+=1
        if len(value)>64 and all(isinstance(item,list) and len(item)>64 and all(isinstance(x,(int,float)) for x in item) for item in value):
            violation(path,'DENSE_RASTER_CANDIDATE',route)
        for i,item in enumerate(value):inspect(item,path,route+f'[{i}]')
    elif isinstance(value,str):
        if any(token in value for token in ('sk-','Bearer ','AIza','PRIVATE KEY')) and CREDENTIAL.search(value):violation(path,'CREDENTIAL_PATTERN',route)
        if 'file-' in value and PROVIDER.search(value):violation(path,'PROVIDER_FILE_ID_PATTERN',route)
        if value.startswith('data:image/') and len(value)>128:violation(path,'INLINE_RASTER',route)


def inspect_header(row,path):
    kind=row.get('kind') if isinstance(row,dict) else None
    if kind=='CHUNKED_JSONL_REFERENCE':
        counts['chunk_headers']+=1
        chunk_headers.append((path,row))
        assert row['rows']>=0 and len({item['name'] for item in row['parts']})==len(row['parts'])
        for item in row['parts']:
            part=(path.parent/item['name']).resolve()
            assert part.parent==path.parent.resolve() and not excluded(part)
            chunk_refs.append((part,item))
    elif kind=='SEALED_EXTERNAL_JSONL_REFERENCE':
        counts['external_cache_refs']+=1
        name=row['segment'];base=(DS18/'run'/name/'public').resolve()
        expected=dict(source='MIXED_DEPTH.jsonl.gz',source_seal='PREDICTIONS_SEALED.json',
            source_freeze='FREEZE.json',source_ledger='PUBLISH_LEDGER.jsonl')
        for key,filename in expected.items():
            item=row[key];source=Path(item['path']).resolve()
            assert source==base/filename and artifact(source)=={field:item[field] for field in ('path','bytes','sha256')}
        seal=read(base/'PREDICTIONS_SEALED.json')
        assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING' and seal['frames']==row['frames']
        assert all(row[key]['sha256']==seal['artifacts_sha256'][filename] for key,filename in expected.items() if key!='source_seal')
        with gzip.open(base/'MIXED_DEPTH.jsonl.gz','rt',encoding='utf-8') as handle:
            header=json.loads(next(handle));assert next(handle,None) is None
        assert header['kind']=='CHUNKED_JSONL_REFERENCE' and header['rows']==row['frames']
        assert len(header['parts'])==len(row['parts'])
        for old,item in zip(header['parts'],row['parts'],strict=True):
            part=Path(item['path']).resolve()
            assert part.parent==base and part.name==old['name']
            actual=artifact(part)
            assert actual=={field:item[field] for field in ('path','bytes','sha256')}
            assert actual['sha256']==old['sha256']==seal['artifacts_sha256'][part.name] and actual['bytes']==old['bytes']


def main():
    assert not OUTPUT.exists(),'Never overwrite a completed review'
    all_seals=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert all_seals['status']=='ALL_PREDICTIONS_AND_ACCESS_SEALED' and all_seals['frames']==20098
    assert len(all_seals['seals'])==8 and len(all_seals['arms'])==6
    for name,item in all_seals['seals'].items():
        path=(RUN/name/'public/PREDICTIONS_SEALED.json').resolve()
        assert artifact(path)=={field:item[field] for field in ('path','bytes','sha256')}
        seal=read(path)
        for filename,digest in seal['artifacts_sha256'].items():assert sha(path.parent/filename)==digest,(name,filename)
    approved={}
    if (HERE/'PUBLIC_PLOTS.json').exists():
        plots=read(HERE/'PUBLIC_PLOTS.json')
        assert plots['status']=='AGGREGATE_NUMERIC_ONLY_NO_PRIVATE_PIXELS'
        assert plots['metric_source']==artifact(RUN/'METRICS.json')
        for item in plots['figures']:
            path=Path(item['path']).resolve()
            assert path in (HERE/'METRIC_COMPARISON.png',HERE/'METRIC_COMPARISON.svg')
            assert artifact(path)==item
            approved[path]=item
    inflight=HERE/'logs/public_content_audit.txt'
    files=[path for path in HERE.rglob('*') if path.is_file() and not excluded(path) and path not in (OUTPUT,inflight)]
    inventory={};file_rows={}
    for path in files:
        before=path.stat();assert before.st_size<LIMIT,('PUBLIC_FILE_GE_100MiB',path,before.st_size)
        item=artifact(path);inventory[path.resolve()]=item
        if path.suffix=='.json' or path.name.endswith(('.jsonl','.jsonl.gz')):
            counts['structured_files']+=1
            if path.suffix=='.json':inspect(read(path),path)
            else:
                opener=gzip.open if path.suffix=='.gz' else open
                file_rows[path.resolve()]=0
                with opener(path,'rt',encoding='utf-8') as handle:
                    for index,line in enumerate(handle):
                        row=json.loads(line);counts['json_rows']+=1;file_rows[path.resolve()]+=1
                        if index==0:inspect_header(row,path)
                        inspect(row,path)
        elif path.suffix in ('.py','.md','.txt','.svg'):
            counts['text_files']+=1;text=path.read_text(encoding='utf-8')
            if CREDENTIAL.search(text):violation(path,'CREDENTIAL_PATTERN','text')
            if PROVIDER.search(text):violation(path,'PROVIDER_FILE_ID_PATTERN','text')
            if re.search(r'data:image/[^;]+;base64,[A-Za-z0-9+/]{128,}',text):violation(path,'INLINE_RASTER','text')
            if path.suffix=='.svg' and re.search(r'<image\b',text):violation(path,'SVG_EMBEDDED_IMAGE','text')
            for line in text.splitlines():
                if line.startswith('AssertionError: '):
                    value=ast.literal_eval(line[len('AssertionError: '):]);inspect(value,path,'embedded_failure')
                    counts['embedded_failure_records']+=len(value) if isinstance(value,list) else 1
        elif path.suffix=='.png' and path.resolve() in approved:
            assert path.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n';counts['approved_aggregate_PNG']+=1
        else:violation(path,'UNREVIEWED_PUBLIC_BINARY','file')
        after=path.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),('FILE_CHANGED_DURING_REVIEW',path)
    for path,expected in chunk_refs:
        assert path in inventory and all(inventory[path][field]==expected[field] for field in ('bytes','sha256'))
    for path,header in chunk_headers:
        assert file_rows[path.resolve()]==1
        assert sum(file_rows[(path.parent/item['name']).resolve()] for item in header['parts'])==header['rows']
    directories=[HERE/'private',*[path for path in HERE.iterdir() if path.is_dir() and path.name.startswith('slice')]]
    sentinels=[str(path/'audit_ignore_sentinel.png') for path in directories]
    ignored=subprocess.run(['git','check-ignore','--',*sentinels],cwd=ROOT,text=True,capture_output=True)
    assert ignored.returncode==0 and len(ignored.stdout.splitlines())==len(sentinels)
    result=dict(status='PASS_PUBLIC_CLOSED_CONTENT_PRIVACY_AND_FILE_LIMIT' if not findings else 'FAIL',
        time_utc=datetime.now(timezone.utc).isoformat(),counts=counts,files=list(inventory.values()),
        public_files=len(inventory),public_bytes=sum(item['bytes'] for item in inventory.values()),
        largest=max(inventory.values(),key=lambda item:item['bytes']),findings=findings,
        actual_ignored_private_and_slice_directories=[str(path) for path in directories],
        seal_source=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),
        bounds='All current closed public files <100MiB; scalar histories, source/public mappings and frame-index arrays are permitted numeric facts, not private pixel rasters',
        exceptions='Only frozen report-generated PUBLIC_PLOTS aggregate PNG/SVG are allowed; no private pixel path or GT source is followed. External unchanged DS18 cache bytes are hash-bound to their original seal, not redundantly privacy-rescanned.',
        snapshot_notes='This new postseal delivery helper does not change frozen science. Its own in-flight execute log and this output are absent from the content snapshot; final staged/remote byte verification includes them. EXECUTION_LOG snapshot precedes the helper exit record.',
        excluded_inflight_log=str(inflight),reference_raster_or_private_pixel_read=False,new_model_http=0,cost_usd=0)
    with OUTPUT.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write('\n')
    assert not findings,('PUBLIC_CONTENT_REVIEW_FINDINGS',len(findings))
    print(result['status'],len(inventory),'files;',counts['json_rows'],'JSONL rows;',result['largest']['bytes'],'max bytes')


if __name__=='__main__':main()
