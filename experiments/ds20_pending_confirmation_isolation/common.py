"""DS20 isolated confirmations, immutable DS14 inputs and sealed DS18 measurements."""
from pathlib import Path
import os, sys, json, gzip, hashlib, importlib.util
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                  MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
WORK=Path('E:/CAU/D-MOT')
DS1=ROOT/'experiments/ds1_depth_only'
DS2=ROOT/'experiments/ds2_depth_transfer_validation'
DS6=ROOT/'experiments/ds6_multifragment_depth_tracking'
DS12=ROOT/'experiments/ds12_contact_depth_admission'
FEED=ROOT/'experiments/feeding_first_two_s0p'
OLD=ROOT/'experiments/ms1_s0_development_8400'
S0P=ROOT/'experiments/s0p_identity_publication'
NE1=ROOT/'experiments/ne1_native_first_event_association'
DATA=WORK/'data/AlignedFeeding_v1'
DEPS=WORK/'tools/jev_z4q_scene_v1_20260922/deps'
RUN=HERE/'run'
DS14=ROOT/'experiments/ds14_raw_multidataset'
DS15=ROOT/'experiments/ds15_z4q_depth_strategy_repair'
DS16=ROOT/'experiments/ds16_relative_depth_order'
DS17=ROOT/'experiments/ds17_mixed_depth_activity_repair'
DS18=ROOT/'experiments/ds18_association_evidence_interface_repair'
DS19=ROOT/'experiments/ds19_protected_event_return'
ARMS=('SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_RETURN','ACTIVITY_ISOLATED','MIXED_RETURN','MIXED_ISOLATED')
EVENT_ARMS=ARMS[2:]
RETURN_ARMS=EVENT_ARMS
MIXED_ARMS=('MIXED_RETURN','MIXED_ISOLATED')
ISOLATED_ARMS=('ACTIVITY_ISOLATED','MIXED_ISOLATED')
ARCHIVED_ARMS=('SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_RETURN','MIXED_RETURN')
SEGMENTS={'feeding_000000_000199':(0,199),'feeding_000351_000555':(351,555),
          'feeding_000701_001060':(701,1060),'feeding_001201_001906':(1201,1906),
          'fishsa_development_8400':(1,8400),'fishsa_validation_2888':(9301,12188),
          'L3':(0,3709),'LW':(0,3628)}
for p in (DS1,FEED,OLD,S0P,NE1,ROOT/'online/closed_loop_2888/z4q_source',DEPS,
          DS18,DS16,WORK/'tools/depth_restoration',WORK/'tools/sam3_depth_birth_inherit_20260917'):
    if str(p) not in sys.path:sys.path.append(str(p))
def input_dir(name):return DS14/'private'/name
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):
    opener=gzip.open if str(p).endswith('.gz') else open
    with opener(p,'rt',encoding='utf-8') as f:
        first=next(f,None)
        if first is None:return
        value=json.loads(first)
        if isinstance(value,dict) and value.get('kind')=='SEALED_EXTERNAL_JSONL_REFERENCE':
            assert next(f,None) is None
            verify_cache_reference(value)
            yield from rows(value['source']['path'])
        elif isinstance(value,dict) and value.get('kind')=='CHUNKED_JSONL_REFERENCE':
            assert next(f,None) is None
            for item in value['parts']:
                part=Path(p).parent/item['name']
                assert part.resolve().parent==Path(p).resolve().parent
                assert part.stat().st_size==item['bytes'] and sha(part)==item['sha256']
                yield from rows(part)
        else:
            yield value
            yield from (json.loads(x) for x in f)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def artifact(p):
    p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def verify_item(i):assert artifact(i['path'])=={k:i[k] for k in ('path','bytes','sha256')},i['path']
def write_new(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False,default=str);f.write('\n')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m);return m

def cache_reference(name):
    """Freeze every physical part plus the original producer/source/seal/ledger."""
    public=DS18/'run'/name/'public'
    path=public/'MIXED_DEPTH.jsonl.gz'
    with gzip.open(path,'rt',encoding='utf-8') as f:
        header=json.loads(next(f));assert next(f,None) is None
    assert header['kind']=='CHUNKED_JSONL_REFERENCE'
    start,stop=SEGMENTS[name]
    assert header['rows']==stop-start+1
    result=dict(kind='SEALED_EXTERNAL_JSONL_REFERENCE',segment=name,frames=header['rows'],
        source=artifact(path),source_seal=artifact(public/'PREDICTIONS_SEALED.json'),
        source_freeze=artifact(public/'FREEZE.json'),source_ledger=artifact(public/'PUBLISH_LEDGER.jsonl'),
        parts=[artifact(public/item['name']) for item in header['parts']],
        policy='EXACT_READONLY_DS18_FRAME_FACTS; NO_NEW_PROJECTION_OR_DEPTH_PARAMETER')
    verify_cache_reference(result)
    return result

def verify_cache_reference(reference):
    assert reference['kind']=='SEALED_EXTERNAL_JSONL_REFERENCE'
    name=reference['segment'];public=(DS18/'run'/name/'public').resolve()
    expected={'source':'MIXED_DEPTH.jsonl.gz','source_seal':'PREDICTIONS_SEALED.json',
              'source_freeze':'FREEZE.json','source_ledger':'PUBLISH_LEDGER.jsonl'}
    for key,filename in expected.items():
        assert Path(reference[key]['path']).resolve()==public/filename
        verify_item(reference[key])
    seal=read(reference['source_seal']['path'])
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['frames']==reference['frames']==SEGMENTS[name][1]-SEGMENTS[name][0]+1
    for key in ('source','source_freeze','source_ledger'):
        item=reference[key]
        assert seal['artifacts_sha256'][Path(item['path']).name]==item['sha256']
    with gzip.open(reference['source']['path'],'rt',encoding='utf-8') as f:
        header=json.loads(next(f));assert next(f,None) is None
    assert header['kind']=='CHUNKED_JSONL_REFERENCE' and header['rows']==reference['frames']
    assert len(header['parts'])==len(reference['parts'])
    for old,item in zip(header['parts'],reference['parts'],strict=True):
        assert Path(item['path']).resolve()==public/old['name']
        assert item['bytes']==old['bytes'] and item['sha256']==old['sha256']==seal['artifacts_sha256'][old['name']]
        verify_item(item)
    frozen=read(reference['source_freeze']['path'])
    assert frozen['source_manifest']==artifact(input_dir(name)/'SOURCE_MANIFEST.json')
    producer=(DS18/'mixed_depth.py',DS17/'mixed_depth.py',DS12/'contact_measurement.py',
        WORK/'tools/sam3_depth_birth_inherit_20260917/features.py')
    for path in producer:
        assert frozen['code_sha256'][str(path.resolve())]==sha(path),(name,path)
    return True

def validate_cache_packet(name,row,profiles,measured,assignment,packet,ledger):
    """Per-frame semantics remain mandatory even under a self-consistent new hash."""
    from mixed_depth import _validated_facts, array_binding, SCHEMA, PARAMETERS, _digest
    from source import native_masks
    frame,global_frame,now=row['frame'],row['global_frame'],row['time']
    assert (measured['segment'],measured['frame'],measured['global_frame'],measured['time'])==(name,frame,global_frame,now)
    assert (assignment['frame'],assignment['global_frame_id'],assignment['time'])==(frame,global_frame,now)
    assert (packet['segment'],packet['frame'],packet['global_frame'],packet['time'])==(name,frame,global_frame,now)
    assert (ledger['frame'],ledger['global_frame'])==(frame,global_frame)
    digest=hashlib.sha256((json.dumps(packet,separators=(',',':'),allow_nan=False)+'\n').encode()).hexdigest()
    assert digest==ledger['mixed_row_sha256']
    assert packet['schema']==SCHEMA and packet['parameters']==PARAMETERS
    assert packet['no_GT_RGB_future_or_restored_input'] and packet['no_sensor_completion']
    assert packet['source_binding']==dict(measured['raw_source_binding'],frame=frame)
    shared={key:packet[key] for key in ('segment','frame','global_frame','time','source_binding',
        'actual_depth_binding','actual_source_index_binding','native_depth_binding')}
    assert packet['frame_binding_sha256']==_digest(shared)
    for outer,inner in (('actual_depth_binding','aligned_depth'),('actual_source_index_binding','aligned_source_index'),('native_depth_binding','native_depth')):
        assert packet[outer]==measured['raw_source_binding'][inner],(name,frame,outer)
    raw={int(n):v for n,v in measured['adaptive_raw'].items()}
    mixed={int(n):_validated_facts(c) for n,c in packet['objects'].items()}
    masks=native_masks(assignment)
    assert set(mixed)==set(raw)==set(masks)==set(profiles)=={o['id'] for o in row['observations']}
    for n,c in mixed.items():
        assert profiles[n]['frame']==frame and profiles[n]['id']==n and profiles[n]['mask']==f'n:{n}'
        assert (c['native'],c['segment'],c['frame'],c['global_frame'],c['time'])==(n,name,frame,global_frame,now)
        assert c['frame_binding_sha256']==packet['frame_binding_sha256']
        assert c['mask_binding']==array_binding(masks[n])
        for part in ('whole','core'):
            for key in ('n','area','valid_fraction','median','mad'):
                assert c[part]['inclusive_summary'][key]==raw[n][part][key],(name,frame,n,part,key)
        for key in ('n','area','valid_fraction','median','mad','q25','q75'):
            assert c['birth_core']['inclusive_summary'][key]==profiles[n]['core'][key],(name,frame,n,'actual_birth_core',key)
    return mixed,digest

class ChunkedGzip:
    """Bounded public file sizes; preserves every canonical logical JSONL row."""
    def __init__(self,path,limit_bytes=70*1024*1024):
        self.path=Path(path);self.limit=limit_bytes;self.parts=[];self.handle=None;self.count=0
    def write(self,line):
        if self.handle is None:
            self.part=self.path.with_name(self.path.name.replace('.jsonl.gz',f'.part{len(self.parts)+1:03d}.jsonl.gz'))
            self.handle=gzip.open(self.part,'xt',encoding='utf-8')
        self.handle.write(line);self.count+=1
        if self.handle.buffer.fileobj.tell()>=self.limit:self._close_part()
    def _close_part(self):
        if self.handle is None:return
        self.handle.close();self.parts.append(dict(name=self.part.name,bytes=self.part.stat().st_size,sha256=sha(self.part)))
        self.handle=None
    def close(self):
        self._close_part()
        with gzip.open(self.path,'xt',encoding='utf-8') as f:
            f.write(json.dumps(dict(kind='CHUNKED_JSONL_REFERENCE',rows=self.count,parts=self.parts),separators=(',',':'))+'\n')
