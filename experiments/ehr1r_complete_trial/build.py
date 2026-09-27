"""Project immutable v6 evidence into EHR-1R-C requests; never select a new frame."""
import argparse
import copy
import hashlib
import json
import re
import secrets
import shutil
from pathlib import Path

ARMS = ('E', 'H-2D', 'H-D', 'H-D-REPEAT', 'H-D-PERMUTE')
SRC = re.compile(r'^SRC-F(\d+)-N(\d+)$')
EVENT = re.compile(r'^EV-F(\d+)-O\d+$')


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


def walk(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)
    elif isinstance(value, str):
        yield value


def make_nodes(episodes):
    values = {value for episode in episodes for value in walk(episode) if SRC.fullmatch(value)}
    nodes = {}
    for source in sorted(values):
        frame = SRC.fullmatch(source).group(1)
        nodes[source] = f'OBS-F{frame}-T{secrets.token_hex(4)}'
    assert len(set(nodes.values())) == len(nodes)
    return nodes


def indexes(episode):
    observations, events = {}, {}
    for section in ('PRE_HISTORY', 'POST_HISTORY_TO_Q'):
        for segment in episode[section].values():
            for obs in segment['observations']:
                key = obs['source_fact_ids'][0]
                assert key not in observations
                observations[key] = obs['fact_id']
    for frame in episode['INTERACTION_OBSERVATIONS']:
        for obs in frame['anonymous_observations']:
            key = obs['source_fact_ids'][0]
            assert key not in observations
            observations[key] = obs['fact_id']
            events[obs['fact_id']] = key
    return observations, events


def project_packet(packet, episode, nodes, token_ledger):
    """Model side gets only frame-local random observation refs; native map stays private."""
    original = copy.deepcopy(packet)
    source_to_fact, event_to_source = indexes(episode)
    event_alias = {fact: 'EV-' + nodes[source][4:] for fact, source in event_to_source.items()}
    visible_source = {source:event_alias.get(fact,fact) for source,fact in source_to_fact.items()}
    for value in walk(original):
        if SRC.fullmatch(value):
            assert value in nodes
    def replace(value):
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                if key in ('source_mask_key', 'source_mask_rle_sha256', 'source_rgb_sha256', 'old_to_new_reference'):
                    continue
                if key == 'source_fact_ids':
                    if 'source_frame' in value and 'bbox_center_px' in value:
                        continue  # leaf observation provenance is in the private bridge
                    result[key] = [visible_source.get(x,event_alias.get(x,x)) for x in child
                                   if not SRC.fullmatch(x) or x in visible_source]
                else:
                    result[key] = replace(child)
            return result
        if isinstance(value, list):
            return [replace(x) for x in value]
        if isinstance(value, str):
            return event_alias.get(value, visible_source.get(value, value))
        return value
    p = replace(original)
    p['request_id'] = p['request_id'].replace('EHR1R-', 'EHR1R-C-')
    p['role_contract'] = ('A/B are qualified pre-risk fragments; X/Y are q-local fragments. '
                          'Anonymous observations during interaction do not certify physical identity.')
    if 'entry_side' in p:
        for role in 'AB':
            p['entry_side'][role] = dict(status='NOT_ESTIMATED', reason='NO_BOUNDARY_CROSSING_ESTIMATOR')
    for im in p['IMAGE_INDEX']:
        assert im['frame'] <= p['q_frame']
        for binding in im['role_tokens']:
            role = binding['role']
            section = 'PRE_HISTORY' if role in 'AB' else 'POST_HISTORY_TO_Q'
            matches = [o for o in p[section][role]['observations'] if o['source_frame'] == im['frame']]
            assert len(matches) == 1
            binding['fact_id'] = matches[0]['fact_id']
        if im.get('anonymous_tokens'):
            matches = [row for row in token_ledger if row['frame'] == im['frame'] and row['image_sha256'] == im['sha256']]
            assert len(matches) == 1, im['image_id']
            ledger = matches[0]
            assert ledger['source_time'] == im['time_seconds']
            source_by_token = {x['token']: f'SRC-F{im["frame"]}-N{int(x["native_mask_key"].split(":")[1])}' for x in ledger['observations']}
            assert set(source_by_token) == {x['token'] for x in im['anonymous_tokens']}
            for token in im['anonymous_tokens']:
                raw = source_by_token[token['token']]
                assert raw in source_to_fact
                token['fact_id'] = event_alias.get(source_to_fact[raw], source_to_fact[raw])
    return p


def endpoint_only(p):
    p['INTERACTION_OBSERVATIONS'] = []
    for key in ('trigger', 'availability_intervals', 'reappearance_intervals', 'per_object_loss',
                'per_handle_clean_return', 'first_unusable_observation', 'first_physical_entry',
                'first_identity_reappearance', 'joint_clean_pair_streak', 'entry_side', 'relative_motion'):
        p.pop(key, None)
    for section in ('PRE_HISTORY', 'POST_HISTORY_TO_Q'):
        for segment in p[section].values():
            segment['observations'] = segment['observations'][-1:]
            for key in ('velocity', 'fragment_id', 'first_position_fact_id', 'last_position_fact_id'):
                segment.pop(key, None)
    p['IMAGE_INDEX'] = [x for x in p['IMAGE_INDEX'] if x['role_tokens']]
    return p


def project_request(old, episode, nodes, ledger):
    arm = old['arm']
    p = project_packet(json.loads(old['text']), episode, nodes, ledger)
    if arm == 'E':
        endpoint_only(p)
    else:
        columns = p['INTERACTION_TABLE']['columns']
        assert 'fact_id' in columns
        local_index=columns.index('local_token')
        p['INTERACTION_TABLE']['columns']=[x for x in columns if x!='local_token']
        p['INTERACTION_TABLE']['rows']=[row[:local_index]+row[local_index+1:]
            for row in p['INTERACTION_TABLE']['rows']]
        p['INTERACTION_TABLE']['full_provenance'] = 'private_lineage_and_source_audit'
    text = wire(p)
    assert 'SRC-F' not in text and 'frame_local:n:' not in text and 'native_mask_key' not in text, sorted(set(re.findall(r'SRC-F\d+-N\d+',text)))[:8]
    assert [x['image_id'] for x in p['IMAGE_INDEX']] == [x['image_id'] for x in old['images']]
    return dict(attempt_id=old['attempt_id'], case=old['case'], arm=arm, text=text,
                images=old['images'])


def build(source, media, ledger_path, out):
    source, media, out = map(Path, (source, media, out))
    assert out.exists() and not any(out.iterdir()), out
    episodes = read(source/'EPISODE_FACTS.json')
    logical_path = source/'REQUESTS_LOGICAL.json'
    if not logical_path.exists():
        logical_path = source.parent/'sender/PLAN.json'
    old = read(logical_path)['requests']
    ledger = read(ledger_path)
    nodes = make_nodes(episodes)
    save(out/'private/NODE_MAP.json', nodes)
    projected = []
    by_case = {x['request_id'].split('-')[-1]: x for x in episodes}
    for request in old:
        projected.append(project_request(request, by_case[request['case']], nodes, ledger[request['case']]))
    assert len(projected) == 25
    assert [x['attempt_id'] for x in projected] == read(source/'REQUEST_MANIFEST.json')['schedule']
    needed = {image['media_file']: image['sha256'] for req in projected for image in req['images']}
    (out/'private/media').mkdir(parents=True)
    for filename, digest in needed.items():
        src, dst = media/filename, out/'private/media'/filename
        assert sha(src) == digest
        shutil.copyfile(src, dst)
        assert sha(dst) == digest
    manifest = dict(base='e95f1a776c62028a7f0d6d5e8a48d26b7c7f4f37',
        source_sha256={x:sha(source/x) for x in ('EPISODE_FACTS.json','REQUEST_MANIFEST.json','DEPTH_INPUT_AUDIT.json')},
        logical_source_sha256=sha(logical_path),
        schedule=[x['attempt_id'] for x in projected],
        requests=[dict(attempt_id=x['attempt_id'],text_sha256=hashlib.sha256(x['text'].encode()).hexdigest(),
                       image_sha256=[y['sha256'] for y in x['images']]) for x in projected])
    save(out/'public/REQUESTS_LOGICAL.json', dict(requests=projected))
    save(out/'public/REQUEST_MANIFEST.json', manifest)
    save(out/'private/SOURCE_LOCATION.json', dict(source=str(source),logical_source=str(logical_path),
        media=str(media),token_ledger=str(ledger_path)))
    print(dict(requests=len(projected), images=len(needed), bytes=sum(len(x['text'].encode()) for x in projected)))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--media',type=Path,required=True)
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    build(args.source,args.media,args.ledger,args.out)
