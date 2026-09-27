"""Independent visible-information checks; hashes are only the first gate."""
import argparse
import hashlib
import json
from pathlib import Path

from build import read, save, sha
from contract import CHOICES, example, schema, visible_facts

ARMS = ('E', 'H-2D', 'H-D', 'H-D-REPEAT', 'H-D-PERMUTE')
E_KEYS = {'request_id', 'q_frame', 'q_time_seconds', 'coordinate_system', 'role_contract',
          'PRE_HISTORY', 'POST_HISTORY_TO_Q', 'hypotheses', 'IMAGE_INDEX', 'unknowns', 'condition'}
ENDPOINT_KEYS = {'fact_id', 'source_frame', 'source_time_seconds', 'source_stream_frame',
                 'coordinate_system', 'unit', 'bbox_center_px', 'bbox_px', 'area_px',
                 'neighbor_count', 'quality'}
IMAGE_KEYS = {'image_id', 'frame', 'time_seconds', 'width', 'height', 'roi_full_mask_xyxy',
              'full_to_image', 'pixel_source', 'role_tokens', 'media_file', 'sha256', 'bytes'}


def checked_packet(request, old, old_by_id):
    case, arm = request['case'], request['arm']
    assert case in {f'B{i:02d}' for i in range(1, 6)} and arm in ARMS
    assert request['attempt_id'] == case+'-'+arm
    packet = json.loads(request['text'])
    expected_condition = arm if arm in ('E', 'H-2D') else 'H-D'
    assert packet['request_id'] == 'EHR-CF-'+case and packet['condition'] == expected_condition
    assert all(x not in request['text'] for x in ('SRC-F', 'frame_local:n:', 'native_mask_key',
                                                  'source_mask_key', 'GT2', 'GT6', '/home/'))
    full = json.loads(old_by_id[case+'-H-D']['text'])
    assert packet['q_frame'] == full['q_frame'] and packet['q_time_seconds'] == full['q_time_seconds']
    if arm == 'E':
        assert set(packet) == E_KEYS
        source_e = json.loads(old['text'])
        for section, roles in (('PRE_HISTORY', 'AB'), ('POST_HISTORY_TO_Q', 'XY')):
            assert set(packet[section]) == set(roles)
            for role in roles:
                segment = packet[section][role]
                assert set(segment) == {'role', 'observations'} and segment['role'] == role
                assert len(segment['observations']) == 1
                endpoint = segment['observations'][0]
                assert set(endpoint) == ENDPOINT_KEYS
                assert endpoint == {key: full[section][role]['observations'][-1][key] for key in ENDPOINT_KEYS}
                assert endpoint['source_frame'] <= packet['q_frame']
                assert endpoint == source_e[section][role]['observations'][0]
        assert packet['hypotheses'] == full['hypotheses']
        assert packet['role_contract'] == full['role_contract'] and packet['unknowns'] == full['unknowns']
        assert packet['coordinate_system'] == full['coordinate_system']
        assert packet['IMAGE_INDEX'] == source_e['IMAGE_INDEX']
        assert all(set(image) == IMAGE_KEYS and image['role_tokens'] and
                   not image.get('anonymous_tokens') for image in packet['IMAGE_INDEX'])
    else:
        expected = json.loads(old['text'])
        expected['request_id'] = packet['request_id']
        assert packet == expected, request['attempt_id']
    assert [x['image_id'] for x in packet['IMAGE_INDEX']] == [x['image_id'] for x in request['images']]
    assert [x['sha256'] for x in packet['IMAGE_INDEX']] == [x['sha256'] for x in request['images']]
    assert all(o['source_frame'] <= packet['q_frame']
               for section in ('PRE_HISTORY', 'POST_HISTORY_TO_Q')
               for segment in packet[section].values() for o in segment['observations'])
    facts = visible_facts(packet)
    seen_roles = set()
    table = packet.get('INTERACTION_TABLE')
    event_frames = ({row[table['columns'].index('fact_id')]: row[table['columns'].index('frame')]
                     for row in table['rows']} if table else {})
    assert all(frame <= packet['q_frame'] for frame in event_frames.values())
    for image in packet['IMAGE_INDEX']:
        assert image['frame'] <= packet['q_frame']
        x0, y0, x1, y1 = image['roi_full_mask_xyxy']
        assert image['width'] == x1-x0 and image['height'] == y1-y0
        for token in image['role_tokens']:
            role = token['role']; assert role in 'ABXY'
            section = 'PRE_HISTORY' if role in 'AB' else 'POST_HISTORY_TO_Q'
            matches = [o for o in packet[section][role]['observations']
                       if o['source_frame'] == image['frame']]
            assert len(matches) == 1 and token['fact_id'] == matches[0]['fact_id']
            assert token['fact_id'] in facts and token['bbox_full_px'] == matches[0]['bbox_px']
            seen_roles.add(role)
        for token in image.get('anonymous_tokens', []):
            assert token['fact_id'] in facts and event_frames[token['fact_id']] == image['frame']
    assert seen_roles == set('ABXY')
    if arm != 'E':
        assert len(table['rows']) == len(event_frames)
        i = table['columns'].index('fact_id')
        assert {row[i] for row in table['rows']} == set(event_frames)
    return packet


def logical(run, old_public, v6_source, media):
    run, old_public, v6_source, media = map(Path, (run, old_public, v6_source, media))
    manifest = read(run/'public/REQUEST_MANIFEST.json')
    assert sha(old_public/'REQUESTS_LOGICAL.json') == manifest['old_logical_sha256']
    assert sha(old_public/'REQUEST_MANIFEST.json') == manifest['old_request_manifest_sha256']
    assert sha(v6_source/'EPISODE_FACTS.json') == manifest['v6_episode_sha256']
    assert read(run/'public/CONTRACT.json') == schema()
    assert read(run/'public/CONTRACT_EXAMPLES.json')['examples'] == [example(x) for x in CHOICES]
    old = read(old_public/'REQUESTS_LOGICAL.json')['requests']
    old_by_id = {x['attempt_id']: x for x in old}
    requests = read(run/'public/REQUESTS_LOGICAL.json')['requests']
    assert len(old_by_id) == len(requests) == len(manifest['requests']) == 25
    assert manifest['schedule'] == [x['attempt_id'] for x in requests] == [x['attempt_id'] for x in old]
    assert len(set(manifest['schedule'])) == 25
    for request, record in zip(requests, manifest['requests'], strict=True):
        attempt = request['attempt_id']
        assert record['attempt_id'] == attempt
        assert hashlib.sha256(request['text'].encode()).hexdigest() == record['text_sha256']
        assert [x['sha256'] for x in request['images']] == record['image_sha256']
        checked_packet(request, old_by_id[attempt], old_by_id)
        for image in request['images']:
            path = media/image['media_file']
            assert sha(path) == image['sha256'] and path.stat().st_size == image['bytes']
    for case in (f'B{i:02d}' for i in range(1, 6)):
        h = json.loads(next(x for x in requests if x['attempt_id'] == case+'-H-D')['text'])
        repeat = json.loads(next(x for x in requests if x['attempt_id'] == case+'-H-D-REPEAT')['text'])
        assert h == repeat
        h2 = json.loads(next(x for x in requests if x['attempt_id'] == case+'-H-2D')['text'])
        assert [x['sha256'] for x in h['IMAGE_INDEX']] == [x['sha256'] for x in h2['IMAGE_INDEX']]
    return {'status': 'SOURCE_TO_LOGICAL_PASS', 'cases': 5, 'requests': 25,
            'old_source_recheck_required': True,
            'logical_sha256': sha(run/'public/REQUESTS_LOGICAL.json'),
            'manifest_sha256': sha(run/'public/REQUEST_MANIFEST.json')}


def bodies(run):
    from sender import body, wire
    run = Path(run)
    requests = read(run/'public/REQUESTS_LOGICAL.json')['requests'] + read(run/'public/SMOKE_REQUESTS.json')['requests']
    uploads = [json.loads(x) for x in (run/'send/UPLOAD_LEDGER.jsonl').read_text().splitlines()]
    ids = {x['sha256']: x['file_id'] for x in uploads if x['phase'] == 'END'}
    records = []
    for request in requests:
        attempt = request['attempt_id']
        payload = (run/'send/bodies'/(attempt+'.json')).read_bytes()
        assert payload == wire(body(request, ids))
        raw = json.loads(payload)
        text = raw['messages'][1]['content'][0]['text']
        assert text == request['text']
        if request['case'] in {f'B{i:02d}' for i in range(1, 6)}:
            old_public = Path(read(run/'private/SOURCE_LOCATION.json')['old_public'])
            old = {x['attempt_id']: x for x in read(old_public/'REQUESTS_LOGICAL.json')['requests']}
            checked_packet(request, old[attempt], old)
        assert ([x['file_id'] for x in raw['messages'][1]['content'][1:]] ==
                [ids[x['sha256']] for x in request['images']])
        records.append({'attempt_id': attempt, 'payload_sha256': hashlib.sha256(payload).hexdigest(),
                        'payload_bytes': len(payload)})
    assert len(records) == 27
    return {'status': 'BODY_GATE_PASS', 'records': records}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    p.add_argument('--old-public', type=Path); p.add_argument('--v6-source', type=Path)
    p.add_argument('--media', type=Path); p.add_argument('--bodies', action='store_true')
    a = p.parse_args()
    result = bodies(a.run) if a.bodies else logical(a.run, a.old_public, a.v6_source, a.media)
    save(a.run/'public'/('BODY_GATE.json' if a.bodies else 'SOURCE_TO_BODY_AUDIT.json'), result)
    print(result['status'])
