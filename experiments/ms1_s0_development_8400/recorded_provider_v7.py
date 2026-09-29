"""Rebuild a stopped causal replay from recorded calls, without network access."""
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

from provider_v7 import PER_SLOT_USD, write_new


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class RecordedProvider:
    def __init__(self, output, config, original):
        self.output = Path(output)
        self.original = Path(original)
        self.attempts = 0
        self.spent_upper = 0.0
        self.used = []
        ledger = self.original/'public/CALL_LEDGER.jsonl'
        self.entries = defaultdict(list)
        for line in ledger.read_text(encoding='utf-8').splitlines():
            item = json.loads(line)
            self.entries[item['tag']].append(item)
        assert len(self.entries) == config['max_inference_http'] == 16
        assert sum(x['phase'] == 'START' for group in self.entries.values() for x in group) == 16
        assert sum(x['phase'] == 'END' for group in self.entries.values() for x in group) == 15
        assert [x['phase'] for x in self.entries['MS1-F5927-S0']] == ['START']
        assert not (self.original/'private_api/MS1-F5927-S0.raw.json').exists()
        assert not (self.original/'public/responses/MS1-F5927-S0.json').exists()
        shutil.copyfile(ledger, self.output/'public/CALL_LEDGER.jsonl')

    def infer(self, episode, stage, packet, images):
        tag = episode['id']+'-'+stage
        assert tag in self.entries and tag not in self.used
        self.used.append(tag)
        group = self.entries[tag]
        phases = [x['phase'] for x in group]
        old_packet = (self.original/'public/requests'/f'{tag}.json').read_bytes()
        assert old_packet == compact(packet)+b'\n'
        assert digest(compact(packet)) == group[0]['public_packet_sha256']
        assert [(x['frame'], x['sha256']) for x in images] == [
            (x['frame'], x['sha256']) for x in packet['images']]
        write_new(self.output/'public/requests'/f'{tag}.json', packet)
        body = json.loads((self.original/'private_api'/f'{tag}.body.json').read_text(encoding='utf-8'))
        assert digest(compact(body)) == group[0]['body_sha256']
        self.attempts += 1
        if phases == ['START']:
            assert tag == 'MS1-F5927-S0'
            self.spent_upper += PER_SLOT_USD
            return None, 'PROCESS_INTERRUPTED_HTTP_UNKNOWN', None
        assert phases == ['START', 'END'], (tag, phases)
        raw = (self.original/'private_api'/f'{tag}.raw.json').read_bytes()
        response_file = self.original/'public/responses'/f'{tag}.json'
        response_bytes = response_file.read_bytes()
        response = json.loads(response_bytes)
        assert digest(response_bytes) == group[1]['response_sha256']
        assert digest(raw) == response['raw_private_sha256']
        assert response['tag'] == tag and response['parse_status'] == group[1]['parse_status']
        self.spent_upper += response['peak_charge_upper_usd']
        target = self.output/'public/responses'/f'{tag}.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as handle:
            handle.write(response_bytes)
        return response['choice'], response['parse_status'], response
