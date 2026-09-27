"""Keep the sealed H evidence and construct E only from allowed endpoint fields."""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

from contract import CHOICES, example, schema

ARMS = ('E', 'H-2D', 'H-D', 'H-D-REPEAT', 'H-D-PERMUTE')
TOP_E = ('request_id', 'q_frame', 'q_time_seconds', 'coordinate_system', 'role_contract',
         'PRE_HISTORY', 'POST_HISTORY_TO_Q', 'hypotheses', 'IMAGE_INDEX', 'unknowns', 'condition')
ENDPOINT = ('fact_id', 'source_frame', 'source_time_seconds', 'source_stream_frame',
            'coordinate_system', 'unit', 'bbox_center_px', 'bbox_px', 'area_px',
            'neighbor_count', 'quality')
IMAGE = ('image_id', 'frame', 'time_seconds', 'width', 'height', 'roi_full_mask_xyxy',
         'full_to_image', 'pixel_source', 'role_tokens', 'media_file', 'sha256', 'bytes')


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def project_e(full, endpoint_images):
    """A new object: no full-packet copy and no blacklist/pop of history keys."""
    p = {key: copy.deepcopy(full[key]) for key in
         ('request_id', 'q_frame', 'q_time_seconds', 'coordinate_system', 'role_contract')}
    for section, roles in (('PRE_HISTORY', 'AB'), ('POST_HISTORY_TO_Q', 'XY')):
        p[section] = {}
        for role in roles:
            endpoint = full[section][role]['observations'][-1]
            p[section][role] = {'role': role,
                                'observations': [{key: copy.deepcopy(endpoint[key]) for key in ENDPOINT}]}
    p['hypotheses'] = copy.deepcopy(full['hypotheses'])
    p['IMAGE_INDEX'] = [{key: copy.deepcopy(image[key]) for key in IMAGE} for image in endpoint_images]
    p['unknowns'] = copy.deepcopy(full['unknowns'])
    p['condition'] = 'E'
    assert tuple(p) == TOP_E
    return p


def build(old_public, old_media, v6_source, run):
    old_public, old_media, v6_source, run = map(Path, (old_public, old_media, v6_source, run))
    assert run.exists() and not any(run.iterdir()), run
    old = read(old_public/'REQUESTS_LOGICAL.json')['requests']
    assert len(old) == 25
    prior = {x['attempt_id']: x for x in old}
    output = []
    for item in old:
        case, arm = item['case'], item['arm']
        assert item['attempt_id'] == case + '-' + arm
        if arm == 'E':
            full = json.loads(prior[case+'-H-D']['text'])
            earlier = json.loads(item['text'])
            allowed = {image['image_id'] for image in earlier['IMAGE_INDEX']}
            images = [x for x in full['IMAGE_INDEX'] if x['image_id'] in allowed]
            assert [x['image_id'] for x in images] == [x['image_id'] for x in earlier['IMAGE_INDEX']]
            packet = project_e(full, images)
            assert all(packet[part][role]['observations'][0] == earlier[part][role]['observations'][0]
                       for part, roles in (('PRE_HISTORY', 'AB'), ('POST_HISTORY_TO_Q', 'XY'))
                       for role in roles)
        else:
            packet = json.loads(item['text'])
        packet['request_id'] = 'EHR-CF-' + case
        request = {'attempt_id': item['attempt_id'], 'case': case, 'arm': arm,
                   'text': wire(packet), 'images': copy.deepcopy(item['images'])}
        assert [x['image_id'] for x in packet['IMAGE_INDEX']] == [x['image_id'] for x in item['images']]
        output.append(request)
    assert [x['attempt_id'] for x in output] == [f'B{i:02d}-{arm}' for i in range(1, 6) for arm in ARMS]
    media = {x['media_file']: x for request in output for x in request['images']}
    assert len(media) == 55
    for filename, info in media.items():
        source, target = old_media/filename, run/'private/media'/filename
        assert sha(source) == info['sha256'] and source.stat().st_size == info['bytes']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(target) == info['sha256']
    save(run/'public/CONTRACT.json', schema())
    save(run/'public/CONTRACT_EXAMPLES.json', {'schema_version': schema()['version'],
                                               'examples': [example(choice) for choice in CHOICES],
                                               'fixture_only': True})
    save(run/'public/REQUESTS_LOGICAL.json', {'requests': output})
    save(run/'public/REQUEST_MANIFEST.json', {
        'review_base': 'f68552be88c20cc500be8281f6f1ec04db34b4ee',
        'old_logical_sha256': sha(old_public/'REQUESTS_LOGICAL.json'),
        'old_request_manifest_sha256': sha(old_public/'REQUEST_MANIFEST.json'),
        'v6_episode_sha256': sha(v6_source/'EPISODE_FACTS.json'),
        'schedule': [x['attempt_id'] for x in output],
        'requests': [{'attempt_id': x['attempt_id'],
                      'text_sha256': hashlib.sha256(x['text'].encode('utf-8')).hexdigest(),
                      'image_sha256': [y['sha256'] for y in x['images']]} for x in output]})
    save(run/'private/SOURCE_LOCATION.json', {'old_public': str(old_public),
        'old_media': str(old_media), 'v6_source': str(v6_source)})
    print({'cases': 5, 'requests': len(output), 'images': len(media),
           'text_bytes': sum(len(x['text'].encode('utf-8')) for x in output)})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('old-public', 'old-media', 'v6-source', 'run'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    build(a.old_public, a.old_media, a.v6_source, a.run)
