"""Reject actual sealed EHR-1 lineage before preparing any EHR-1R request."""
import argparse
import gzip
import json
from pathlib import Path

from contract import old_packet_regression

OLD_CODE = Path('/home/xiongxiong/ehr1_event_history_20260926/run_v6')
AO1 = Path('/home/xiongxiong/ao1_input_fidelity_20260924/range_corrected_run')
DEV_OBS = Path('/home/xiongxiong/dmot-experiments/sam3_depth_failure_repair_20260917/diagnosis/observations_development.jsonl.gz')
VAL = Path('/home/xiongxiong/deepseek_z4q_closedloop_20260923_side/inputs')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def stream(path, lo, hi):
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        return {r['frame']: r for line in source if lo <= (r := json.loads(line))['frame'] <= hi}


def put(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main(out):
    cases = {c['case_alias']: c for c in read(AO1/'public/SOURCE_MANIFEST.json')['cases']}
    packets = read(OLD_CODE/'public/EPISODE_FACTS.json')
    rows = {}
    for packet in packets:
        case = packet['request_id'].split('-')[-1]
        c = cases[case]
        lo = min(o['source_frame'] for r in 'AB' for o in packet['PRE_HISTORY'][r]['observations'])
        hi = max(o['source_frame'] for r in 'AB' for o in packet['PRE_HISTORY'][r]['observations'])
        path = DEV_OBS if c['split'] == 'development' else VAL/'observations_validation.jsonl.gz'
        rows[case] = stream(path, lo, hi)
    results = old_packet_regression(packets, cases, rows)
    put(out, dict(status='OLD_REAL_PACKETS_REJECTED', checked_without_gt=True,
                  source='original predicted observations, re-read independently of packet risk fields',
                  cases=results))
    print('OLD_REAL_PACKETS_REJECTED', [(c, len(results[c]['A']), len(results[c]['B'])) for c in results])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    main(p.parse_args().out)
