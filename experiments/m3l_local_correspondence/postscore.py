"""Independent post-seal local scorer; only this process may open exposed validation GT."""
from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from pycocotools import mask as mask_api
from scipy.optimize import linear_sum_assignment

ROOT = Path('/home/xiongxiong/m3l_local_correspondence_20260926')
LEDGER = Path('/home/xiongxiong/m2t_motion_first_20260924/full_run/private/TOKEN_LEDGER.json')
ASSIGN = Path('/home/data2/xiongxiong/d-mot/experiments/sam3_i3_validation_cpu16_20260915/run_validation_2888/assignments.jsonl.gz')
MATCH = Path('/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_validation.jsonl.gz')
MATCH_SHA = '5c557ab0dd833e00b4b0d3a6eeec3cdd6e0669f11da4f5e6611619fe5928cbd1'
ASSIGN_SHA = 'ea468964e4b287a3879dfb83b304dd64c83f055e9649d3155fa62c41b717a0fc'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    path = Path(path)
    assert not path.exists(), path
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def jsonl(path, rows):
    path = Path(path)
    assert not path.exists(), path
    path.write_text(''.join(json.dumps(x, ensure_ascii=False, allow_nan=False)+'\n' for x in rows), encoding='utf-8')


def parse(content, request):
    """Return raw decisions and separately visible schema, citation and conflict failures."""
    core = json.loads(request['core_text'])
    src, dst = core['source']['observations'], core['target']['observations']
    sources, targets = {x['token'] for x in src}, {x['token'] for x in dst}
    duplicates = []
    def unique(pairs):
        counts = Counter(k for k, _ in pairs)
        duplicates.extend(k for k, n in counts.items() if n > 1)
        return dict(pairs)
    try:
        data = json.loads(content, object_pairs_hook=unique)
    except (TypeError, ValueError):
        return dict(schema_valid=False, reason='INVALID_JSON', rows=[])
    if duplicates:
        return dict(schema_valid=False, reason='DUPLICATE_JSON_KEY', rows=[])
    if not isinstance(data, dict) or data.get('request_id') != core['request_id'] or not isinstance(data.get('matches'), list):
        return dict(schema_valid=False, reason='BAD_TOP_LEVEL', rows=[])
    rows = data['matches']
    if len(rows) != len(sources) or not all(isinstance(r, dict) for r in rows):
        return dict(schema_valid=False, reason='SOURCE_COUNT', rows=[])
    if not all(isinstance(r.get('source_token'), str) for r in rows):
        return dict(schema_valid=False, reason='BAD_SOURCE_TOKEN', rows=[])
    if Counter(r.get('source_token') for r in rows) != Counter(sources):
        return dict(schema_valid=False, reason='SOURCE_MISSING_OR_DUPLICATE', rows=[])
    decoded = []
    for r in rows:
        status, target = r.get('status'), r.get('target_token')
        if status not in ('MATCH', 'UNRESOLVED'):
            return dict(schema_valid=False, reason='BAD_STATUS', rows=[])
        if status == 'MATCH' and (not isinstance(target, str) or target not in targets):
            return dict(schema_valid=False, reason='BAD_TARGET_TOKEN', rows=[])
        if status == 'UNRESOLVED' and target is not None:
            return dict(schema_valid=False, reason='UNRESOLVED_WITH_TARGET', rows=[])
        evidence = r.get('evidence')
        if not isinstance(evidence, list):
            return dict(schema_valid=False, reason='EVIDENCE_NOT_LIST', rows=[])
        citations = []
        citation_format_valid = True
        for cite in evidence:
            if not isinstance(cite, dict):
                citation_format_valid = False
                continue
            if not isinstance(cite.get('observation'), str) or not cite['observation'].strip():
                citation_format_valid = False
            pair = (cite.get('image_id'), cite.get('observation_token'))
            if not all(isinstance(x, str) for x in pair):
                citation_format_valid = False
                continue
            if pair[0] == core['source']['image_id'] and pair[1] in sources:
                citations.append(pair)
            elif pair[0] == core['target']['image_id'] and pair[1] in targets:
                citations.append(pair)
            else:
                citation_format_valid = False
        expected = {(core['source']['image_id'], r['source_token']),
                    (core['target']['image_id'], target)} if status == 'MATCH' else set()
        citation_valid = citation_format_valid and (status == 'UNRESOLVED' or expected <= set(citations))
        decoded.append(dict(source_token=r['source_token'], status=status, target_token=target,
                            citation_valid=citation_valid, evidence=evidence,
                            limitation=r.get('limitation')))
    occupied = Counter(r['target_token'] for r in decoded if r['status'] == 'MATCH')
    for r in decoded:
        r['target_conflict'] = r['status'] == 'MATCH' and occupied[r['target_token']] > 1
        r['usable'] = r['status'] == 'MATCH' and r['citation_valid'] and not r['target_conflict']
    return dict(schema_valid=True, reason=None, rows=decoded,
                citation_invalid=sum(not r['citation_valid'] for r in decoded),
                conflict_targets=sorted(k for k, v in occupied.items() if v > 1))


def stream(path, wanted):
    result = {}
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            if obj['frame'] in wanted:
                assert obj['frame'] not in result
                result[obj['frame']] = obj
    assert result.keys() == wanted, (path, wanted - result.keys())
    return result


def unique_gt(obj, objects):
    gt = obj.get('gt_id')
    if gt is None or obj.get('ambiguity'):
        return None, 'SOURCE_UNMATCHED_OR_AMBIGUOUS'
    if sum(x is not obj and not x.get('ambiguity') and x.get('gt_id') == gt for x in objects):
        return None, 'SOURCE_GT_DUPLICATE'
    return gt, None


def truth(src_private, dst_private, src_match, dst_match):
    by_native_src = {}
    by_native_dst = {}
    for obj in src_match['objects']:
        by_native_src.setdefault(int(obj['native_id']), []).append(obj)
    for obj in dst_match['objects']:
        by_native_dst.setdefault(int(obj['native_id']), []).append(obj)
    result = {}
    for obs in src_private['observations']:
        token = obs['token']
        native = int(obs['native_mask_key'].split(':')[1])
        candidates = by_native_src.get(native, [])
        if len(candidates) != 1:
            result[token] = dict(target=None, reason='SOURCE_MISSING_OR_DUPLICATE_MATCH_ROW')
            continue
        obj = candidates[0]
        gt, reason = unique_gt(obj, src_match['objects'])
        if reason:
            result[token] = dict(target=None, reason=reason)
            continue
        hits = []
        possible = []
        for target_obs in dst_private['observations']:
            matches = by_native_dst.get(int(target_obs['native_mask_key'].split(':')[1]), [])
            if len(matches) != 1:
                possible.append(target_obs['token'])
                continue
            other = matches[0]
            if other.get('ambiguity') and (not other.get('candidate_gt_ids') or str(gt) in
                    {str(x) for x in other['candidate_gt_ids']}):
                possible.append(target_obs['token'])
            elif not other.get('ambiguity') and other.get('gt_id') == gt:
                hits.append(target_obs['token'])
        if len(hits) != 1 or possible:
            result[token] = dict(target=None, reason='TARGET_NOT_UNIQUE',
                                 target_hits=hits, ambiguous_possible=possible)
        else:
            result[token] = dict(target=hits[0], reason=None, gt_id=gt)
    return result


def center(a, b):
    return math.dist(a['center_norm'], b['center_norm'])


def baseline(src, dst, src_masks, dst_masks, mode):
    """Hungarian primary optimum; exact ties use center then target-token order."""
    n, m = len(src), len(dst)
    primary = np.empty((n, m), dtype=float)
    centers = np.empty((n, m), dtype=float)
    for i, a in enumerate(src):
        for j, b in enumerate(dst):
            centers[i, j] = center(a, b)
            if mode == 'N-C':
                primary[i, j] = centers[i, j]
            else:
                x, y = src_masks[a['token']], dst_masks[b['token']]
                intersection = np.count_nonzero(x & y)
                union = np.count_nonzero(x | y)
                primary[i, j] = 1 - intersection / union if union else 1
    ri, ci = linear_sum_assignment(primary)
    minimum = float(primary[ri, ci].sum())
    # Fixed B01 has six objects; enumerate only exact primary-optimal assignments for stable ties.
    assert max(n, m) <= 8
    best = None
    for chosen in itertools.combinations(range(n), min(n, m)):
        for targets in itertools.permutations(range(m), min(n, m)):
            pairs = list(zip(chosen, targets))
            total = sum(primary[i, j] for i, j in pairs)
            if abs(total - minimum) > 1e-12:
                continue
            key = (sum(centers[i, j] for i, j in pairs),
                   tuple((src[i]['token'], dst[j]['token']) for i, j in pairs))
            if best is None or key < best[0]:
                best = key, pairs
    assert best is not None
    return {src[i]['token']: dst[j]['token'] for i, j in best[1]}


def masks_for(frame, private, assignment, source_row):
    assert assignment['frame'] == frame and assignment['time'] == source_row['source_time'] == private['source_time']
    hashes = {x['mask_key']: x['rle_sha256'] for x in source_row['predicted_masks']}
    result = {}
    for obj in private['observations']:
        key = obj['native_mask_key']
        rle = assignment['masks'][key]
        assert hashlib.sha256(json.dumps(rle, sort_keys=True).encode()).hexdigest() == hashes[key]
        result[obj['token']] = mask_api.decode(dict(size=rle['size'], counts=rle['counts'].encode())).astype(bool)
    return result


def compose(start, arm, token_rows, frames):
    """Follow only the model's usable edges; GT annotates error but never repairs a path."""
    current = start
    path = [dict(frame=frames[0]['frame'], token=current)]
    stop = first_wrong = None
    lookup = {(x['attempt_id'], x['source_token']): x for x in token_rows}
    for i in range(len(frames)-1):
        pair = f'P{i+1:02d}'
        item = lookup.get((pair+'-'+arm, current))
        if item is None or item['decision'] != 'MATCH':
            stop = dict(pair=pair, reason=item['decision'] if item else 'MISSING_SOURCE')
            break
        if first_wrong is None and item['truth_target'] is not None and item['raw_target'] != item['truth_target']:
            first_wrong = dict(pair=pair, source=current, chosen=item['raw_target'],
                               true_target=item['truth_target'])
        current = item['raw_target']
        path.append(dict(frame=frames[i+1]['frame'], token=current))
    return dict(start_token=start, path=path, last_reached_frame=path[-1]['frame'],
                stop=stop, first_certified_wrong_step=first_wrong)


def run(root=ROOT):
    sender = root / 'sender'
    plan = read(sender / 'PLAN.json')
    request_seal = read(sender / 'public/REQUESTS_SEALED.json')
    response_seal = read(sender / 'public/RESPONSES_SEALED.json')
    assert request_seal['status'] == 'ALL_24_BODIES_FROZEN_BEFORE_FORMAL'
    assert response_seal['status'] == 'ALL_24_RESPONSES_SEALED_BEFORE_SCORE'
    assert request_seal['plan_sha256'] == sha(sender / 'PLAN.json')
    assert request_seal['code_sha256'] == sha(sender / 'sender.py')
    assert response_seal['request_seal_sha256'] == sha(sender / 'public/REQUESTS_SEALED.json')
    req_records = {x['attempt_id']: x for x in request_seal['records']}
    res_records = {x['attempt_id']: x for x in response_seal['records']}
    assert set(req_records) == set(res_records) == set(plan['schedule'])
    ledger = [json.loads(x) for x in (sender / 'public/CALL_LEDGER.jsonl').read_text().splitlines()]
    starts = [x for x in ledger if x['phase'] == 'START']
    ends = [x for x in ledger if x['phase'] == 'END']
    assert len(starts) == len(ends) == 25 and {x['attempt_id'] for x in starts} == {x['attempt_id'] for x in ends}
    responses = {}
    for attempt in plan['schedule']:
        assert sha(sender / 'private/bodies' / (attempt+'.json')) == req_records[attempt]['payload_sha256']
        path = sender / 'public/responses' / (attempt+'.json')
        assert sha(path) == res_records[attempt]['response_sha256']
        responses[attempt] = read(path)
    assert sha(MATCH) == MATCH_SHA and sha(ASSIGN) == ASSIGN_SHA
    # GT and original masks are opened only after every response hash and ledger check above.
    frames = read(root / 'public/SOURCE_MANIFEST.json')['frames']
    wanted = {x['frame'] for x in frames}
    matches, assignments = stream(MATCH, wanted), stream(ASSIGN, wanted)
    private = json.loads(LEDGER.read_text(encoding='utf-8'))['B01'][5:18]
    old_source = read(Path('/home/xiongxiong/m2t_motion_first_20260924/full_run/public/SOURCE_MANIFEST.json'))
    source_rows = {x['frame']: x for x in next(x for x in old_source['cases'] if x['case_alias']=='B01')['source_rows']}
    assert [x['frame'] for x in private] == [x['frame'] for x in frames]
    mask_map = {f['frame']: masks_for(f['frame'], p, assignments[f['frame']], source_rows[f['frame']])
                for f, p in zip(frames, private, strict=True)}
    tokens, pairs, baseline_rows = [], [], []
    decoded = {}
    truths = {}
    baselines = {}
    for i, request in enumerate(plan['requests']):
        pair = request['pair']
        src, dst = frames[i:i+2]
        assert [src['frame'], dst['frame']] == [private[i]['frame'], private[i+1]['frame']]
        true = truth(private[i], private[i+1], matches[src['frame']], matches[dst['frame']])
        truths[pair] = true
        b = {mode: baseline(src['observations'], dst['observations'], mask_map[src['frame']],
                            mask_map[dst['frame']], mode) for mode in ('N-C', 'N-I')}
        baselines[pair] = b
        for mode, mapping in b.items():
            for token in true:
                baseline_rows.append(dict(pair=pair, mode=mode, source_token=token,
                    target_token=mapping.get(token), truth=true[token]['target'],
                    scoreable=true[token]['target'] is not None,
                    correctness=('CORRECT' if mapping.get(token)==true[token]['target'] else 'WRONG')
                      if true[token]['target'] is not None else 'UNSCORABLE'))
        for arm in ('FIRST', 'REPEAT'):
            attempt = pair+'-'+arm
            parsed = parse(responses[attempt]['content'], request)
            decoded[attempt] = parsed
            pair_tokens = []
            for token, truth_row in true.items():
                row = next((x for x in parsed['rows'] if x['source_token'] == token), None)
                decision = ('FORMAT_INVALID' if not parsed['schema_valid'] else
                            'UNRESOLVED' if row['status'] == 'UNRESOLVED' else
                            'CITATION_INVALID' if not row['citation_valid'] else
                            'TARGET_CONFLICT' if row['target_conflict'] else 'MATCH')
                target = row['target_token'] if row else None
                correctness = ('UNSCORABLE' if truth_row['target'] is None else
                               'CORRECT' if decision == 'MATCH' and target == truth_row['target'] else
                               'WRONG' if decision == 'MATCH' else 'ABSTAIN_OR_INVALID')
                raw_status = row['status'] if row else 'FORMAT_INVALID'
                raw_correctness = ('UNSCORABLE' if truth_row['target'] is None else
                    'CORRECT' if raw_status == 'MATCH' and target == truth_row['target'] else
                    'WRONG' if raw_status == 'MATCH' else 'ABSTAIN_OR_INVALID')
                item = dict(attempt_id=attempt, pair=pair, arm=arm, source_token=token,
                            raw_status=raw_status, raw_target=target, raw_correctness=raw_correctness,
                            decision=decision, truth_target=truth_row['target'],
                            scoreability_reason=truth_row['reason'], correctness=correctness,
                            citation_valid=row['citation_valid'] if row else None,
                            target_conflict=row['target_conflict'] if row else None)
                tokens.append(item)
                pair_tokens.append(item)
            scoreable = [x for x in pair_tokens if x['truth_target'] is not None]
            selected = [x for x in scoreable if x['decision']=='MATCH']
            pairs.append(dict(attempt_id=attempt, pair=pair, arm=arm, source_count=len(true),
                target_count=len(dst['observations']), scoreable=len(scoreable),
                schema_valid=parsed['schema_valid'], schema_reason=parsed['reason'],
                citation_invalid=parsed.get('citation_invalid'), conflict_targets=parsed.get('conflict_targets'),
                match_selected=len(selected), correct=sum(x['correctness']=='CORRECT' for x in selected),
                wrong=sum(x['correctness']=='WRONG' for x in selected),
                unresolved=sum(x['decision']=='UNRESOLVED' for x in pair_tokens),
                latency_seconds=responses[attempt]['latency_seconds'],
                charged_upper_usd=responses[attempt]['charged_upper_usd'],
                finish_reason=responses[attempt]['finish_reason']))
    chains = []
    for arm in ('FIRST','REPEAT'):
        for role in ('A','B'):
            anchors = [x['token'] for x in private[0]['observations'] if role in x['endpoint_roles']]
            assert len(anchors)==1, (role, anchors)
            chains.append(dict(role=role, arm=arm, **compose(anchors[0], arm, tokens, frames)))
    scoreable_total = sum(x['scoreable'] for x in pairs if x['arm']=='FIRST')
    scoreable_hops = sum(x['scoreable']>0 for x in pairs if x['arm']=='FIRST')
    metrics = {}
    for arm in ('FIRST','REPEAT'):
        rows = [x for x in tokens if x['arm']==arm and x['truth_target'] is not None]
        chosen = [x for x in rows if x['decision']=='MATCH']
        metrics[arm] = dict(scoreable=len(rows), selected=len(chosen),
            correct=sum(x['correctness']=='CORRECT' for x in chosen),
            wrong=sum(x['correctness']=='WRONG' for x in chosen),
            coverage=len(chosen)/len(rows) if rows else None,
            precision=sum(x['correctness']=='CORRECT' for x in chosen)/len(chosen) if chosen else None)
    agreement_rows = []
    raw_agreement_rows = []
    for i in range(1,13):
        pair=f'P{i:02d}'
        for token,t in truths[pair].items():
            if t['target'] is None:
                continue
            a,b=[next(x for x in tokens if x['attempt_id']==pair+'-'+arm and x['source_token']==token)
                 for arm in ('FIRST','REPEAT')]
            agreement_rows.append((a['decision'],a['raw_target'])==(b['decision'],b['raw_target']))
            raw_agreement_rows.append((a['raw_status'],a['raw_target'])==(b['raw_status'],b['raw_target']))
    plausible=[]
    paired_gain=paired_harm=0
    for i in range(1,13):
        pair=f'P{i:02d}'
        for token,t in truths[pair].items():
            if t['target'] is None:
                continue
            a,b=[next(x for x in tokens if x['attempt_id']==pair+'-'+arm and x['source_token']==token)
                 for arm in ('FIRST','REPEAT')]
            numeric_wrong=all(baselines[pair][mode].get(token)!=t['target'] for mode in ('N-C','N-I'))
            numeric_right=all(baselines[pair][mode].get(token)==t['target'] for mode in ('N-C','N-I'))
            paired_gain += sum(x['correctness']=='CORRECT' for x in (a,b)) if numeric_wrong else 0
            paired_harm += sum(x['correctness']=='WRONG' for x in (a,b)) if numeric_right else 0
            if (a['correctness']==b['correctness']=='CORRECT' and
                numeric_wrong):
                plausible.append(dict(pair=pair, source_token=token, truth_target=t['target']))
    signal=(scoreable_hops>=8 and scoreable_total>=16 and
            all(metrics[x]['precision'] is not None and metrics[x]['precision']>=.95 and metrics[x]['coverage']>=.80
                for x in ('FIRST','REPEAT')) and
            sum(raw_agreement_rows)/len(raw_agreement_rows)>=.90 and
            not any(x['first_certified_wrong_step'] for x in chains))
    baseline_metrics={}
    for mode in ('N-C','N-I'):
        rows=[x for x in baseline_rows if x['mode']==mode and x['scoreable']]
        selected=[x for x in rows if x['target_token'] is not None]
        baseline_metrics[mode]=dict(scoreable=len(rows),selected=len(selected),
           correct=sum(x['correctness']=='CORRECT' for x in selected),
           wrong=sum(x['correctness']=='WRONG' for x in selected),
           coverage=len(selected)/len(rows) if rows else None,
           precision=sum(x['correctness']=='CORRECT' for x in selected)/len(selected) if selected else None)
    summary=dict(status='POST_SEAL_SCORE_COMPLETE', technical_complete=len(pairs)==24 and
                 sum(x['schema_valid'] for x in pairs)>=23,
                 parseable=sum(x['schema_valid'] for x in pairs), scoreable_hops=scoreable_hops,
                 scoreable_sources=scoreable_total, metrics=metrics,
                 baseline_metrics=baseline_metrics,
                 repeat_agreement=sum(agreement_rows)/len(agreement_rows) if agreement_rows else None,
                 raw_repeat_agreement=sum(raw_agreement_rows)/len(raw_agreement_rows) if raw_agreement_rows else None,
                 citation_invalid_attempts=[x['attempt_id'] for x in pairs if x['citation_invalid']],
                 both_numeric_wrong_vlm_both_correct=plausible,
                 distinct_increment_hops=len({x['pair'] for x in plausible}),
                 paired_gain_against_both_wrong=paired_gain,
                 paired_harm_against_both_right=paired_harm,
                 local_signal=signal, tentative_increment=signal and len({x['pair'] for x in plausible})>=2 and paired_gain>paired_harm,
                 formal_latency_seconds=sum(x['latency_seconds'] for x in pairs),
                 latency_min_seconds=min(x['latency_seconds'] for x in pairs),
                 latency_max_seconds=max(x['latency_seconds'] for x in pairs),
                 formal_charge_upper_usd=sum(x['charged_upper_usd'] for x in pairs),
                 smoke_charge_upper_usd=read(sender/'public/responses/S001.json')['charged_upper_usd'])
    summary['decision'] = ('TECHNICAL_GATE_FAIL' if not summary['technical_complete'] else
        'INCONCLUSIVE_INPUT' if scoreable_hops < 8 or scoreable_total < 16 else
        'STOP_LOCAL_VLM_ASSOCIATION' if not signal else
        'TENTATIVE_LOCAL_SIGNAL' if summary['tentative_increment'] else
        'HAS_LOCAL_CAPABILITY_NO_INCREMENT')
    dest=root/'public/final_score'
    dest.mkdir(exist_ok=False)
    write(dest/'RESPONSE_MANIFEST.json', dict(status='SEALED_AND_POSTHOC_PARSED',
         response_seal_sha256=sha(sender/'public/RESPONSES_SEALED.json'),
         records=[dict(attempt_id=x, response_sha256=res_records[x]['response_sha256'],
                       returned_model=responses[x]['returned_model'],
                       finish_reason=responses[x]['finish_reason'],
                       schema_valid=decoded[x]['schema_valid'], schema_reason=decoded[x]['reason'],
                       usage=responses[x]['usage'], latency_seconds=responses[x]['latency_seconds'],
                       charged_upper_usd=responses[x]['charged_upper_usd']) for x in plan['schedule']]))
    jsonl(dest/'TOKEN_MATCH_RESULTS.jsonl', tokens)
    write(dest/'PAIR_RESULTS.json', pairs)
    jsonl(dest/'BASELINE_RESULTS.jsonl', baseline_rows)
    write(dest/'CHAIN_COMPOSITION.json', chains)
    write(dest/'FAILURE_CASES.json', [x for x in tokens if x['correctness']=='WRONG' or
          x['decision'] in ('FORMAT_INVALID','CITATION_INVALID','TARGET_CONFLICT','UNRESOLVED')])
    write(dest/'SUMMARY.json', summary)
    print(json.dumps(summary))


if __name__=='__main__':
    run()
