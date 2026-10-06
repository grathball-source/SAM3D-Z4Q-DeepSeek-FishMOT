"""Unchanged DS34 per-frame raw mask/quality checks; DS35 association reads no RGB."""
from common import *
from association import DEPTH
from pycocotools import mask as coco

def rle(value):
    return dict(size=value['size'], counts=value['counts'].encode('ascii'))

_checked = {}
def _verify_source_files(value):
    if isinstance(value,dict):
        if {'path','bytes','sha256'} <= value.keys():
            pin = {k:value[k] for k in ('path','bytes','sha256')}
            if pin['path'] not in _checked: verify_item(pin); _checked[pin['path']]=pin
            else: assert _checked[pin['path']]==pin
        else:
            for child in value.values(): _verify_source_files(child)
    elif isinstance(value,list):
        for child in value: _verify_source_files(child)

def _source_array_binding(array):
    header=json.dumps([array.dtype.str,list(array.shape)],separators=(',',':')).encode()
    return dict(dtype=array.dtype.str,shape=list(array.shape),
        sha256=hashlib.sha256(header+b'\n'+array.tobytes(order='C')).hexdigest())

def verify_frame_contract(name, current, assignment, row, measured, quality, bound, ledger, rgb_pin):
    frame, global_frame, now = current['frame'], current['global_frame'], current['time']
    assert (row['frame'], row['global_frame'], row['time']) == (frame, global_frame, now)
    assert (assignment['frame'], assignment['global_frame_id'], assignment['time']) == (frame, global_frame, now)
    for packet in (measured, quality, bound):
        assert (packet['frame'], packet['global_frame'], packet['time']) == (frame, global_frame, now)
    assert measured['segment'] == quality['segment'] == name
    assert bound['source_row_sha256'] == row_sha(row)
    assert bound['assignment_row_sha256'] == row_sha(assignment)
    assert bound['measured_row_sha256'] == row_sha(measured)
    assert bound['DS18_packet_sha256'] == digest(quality)
    assert ledger['frame_inputs_row_sha256'] == row_sha(bound)
    assert bound['actual_RGB_read'] is False and bound['GT'] is False
    assert bound['raw_source_binding'] == measured['raw_source_binding']
    assert quality['source_binding'] == dict(measured['raw_source_binding'], frame=frame)
    shared = {key:quality[key] for key in ('segment', 'frame', 'global_frame', 'time', 'source_binding',
        'actual_depth_binding', 'actual_source_index_binding', 'native_depth_binding')}
    assert quality['frame_binding_sha256'] == digest(shared)
    for outer, inner in (('actual_depth_binding', 'aligned_depth'),
                        ('actual_source_index_binding', 'aligned_source_index'), ('native_depth_binding', 'native_depth')):
        assert quality[outer] == measured['raw_source_binding'][inner]
    _verify_source_files(measured['raw_source_binding'])
    masks = {int(o['mask'][2:]):coco.decode(rle(assignment['masks'][o['mask']])).astype(bool)
             for o in assignment['variants']['N0']}
    assert set(masks) == {int(n) for n in quality['objects']} == {o['id'] for o in row['observations']}
    extracts = {str(n):DEPTH.extract(cert) for n, cert in quality['objects'].items()}
    assert bound['DS18_extracts'] == extracts
    raw = {int(n):v for n,v in measured['adaptive_raw'].items()}
    for native, cert in quality['objects'].items():
        assert cert['certificate_sha256'] == digest({k:v for k,v in cert.items() if k != 'certificate_sha256'})
        assert (cert['native'], cert['segment'], cert['frame'], cert['global_frame'], cert['time']) == (
            int(native), name, frame, global_frame, now)
        assert cert['frame_binding_sha256'] == quality['frame_binding_sha256']
        assert cert['mask_binding'] == _source_array_binding(masks[int(native)])
        for part in ('whole', 'core'):
            assert cert[part]['inclusive_statistics_sha256'] == digest(cert[part]['inclusive_summary'])
            assert cert[part]['source_quality_denominator'] == 'ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS'
            assert cert[part]['roi_binding'] == cert['mask_binding' if part == 'whole' else 'core_binding']
            for field in ('n', 'area', 'valid_fraction', 'median', 'mad'):
                assert cert[part]['inclusive_summary'][field] == raw[int(native)][part][field]
    return dict(row=row, source_row_sha256=row_sha(row), assignment_row_sha256=row_sha(assignment),
        masks={str(n):array_hash(mask) for n,mask in masks.items()}, extracts=extracts,
        raw_source_binding=measured['raw_source_binding'], adaptive_full=measured.get('adaptive_full'),
        encoded_masks=assignment['masks'])

