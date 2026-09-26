"""Audit whether frozen AO1 role anchors can reach the EHR-1 bounded native segments."""
import argparse
import json
from pathlib import Path

from prepare import AO1, DEV_OBS, VAL, item, put, read, stream


def main(run):
    cases = read(AO1/'public/SOURCE_MANIFEST.json')['cases']
    report = []
    for case in cases:
        trigger, q = case['trigger_frame'], case['query_frame']
        roles = case['V1']['roles']
        lo = min(x['frame'] for x in roles)
        path = DEV_OBS if case['split'] == 'development' else VAL/'observations_validation.jsonl.gz'
        obs = stream(path, lo, q)
        record = dict(case=case['case_alias'], roles={})
        ids = {role: int(max((x for x in roles if x['role'] == role), key=lambda x: x['frame'])['native_mask_key'].split(':')[1])
               for role in 'AB'}
        contact_frames = []
        for f in range(lo, trigger+1):
            a, b = item(obs[f], ids['A']), item(obs[f], ids['B'])
            if a and b and (ids['B'] in a.get('neighbors', []) or ids['A'] in b.get('neighbors', [])):
                contact_frames.append(f)
        record['first_predicted_pair_contact_at_or_before_frozen_trigger'] = contact_frames[0] if contact_frames else None
        for role in 'AB':
            anchor = max(x['frame'] for x in roles if x['role'] == role)
            n = int(next(x['native_mask_key'] for x in roles if x['role'] == role and x['frame'] == anchor).split(':')[1])
            broken = []
            for f in range(anchor, trigger):
                o = item(obs[f], n)
                reason = ('MISSING_PREDICTED_MASK' if o is None else
                          'ZERO_AREA' if not o['area'] else
                          'CONTACT_RISK' if o.get('neighbors') else None)
                if reason:
                    broken.append(dict(frame=f, reason=reason))
            record['roles'][role] = dict(anchor=anchor, trigger=trigger,
                                          first_unreliable=broken[0] if broken else None,
                                          total_unreliable_frames=len(broken),
                                          original_anchor_connects_as_CLEAN_segment=not broken)
        report.append(record)
    episode = {x['request_id'].split('-')[-1]: x for x in read(run/'public/EPISODE_FACTS.json')}
    for r in report:
        p = episode[r['case']]
        for role in 'AB':
            seq = p['PRE_HISTORY'][role]['observations']
            r['roles'][role]['sent_PRE_HISTORY_frames'] = len(seq)
            r['roles'][role]['sent_contact_risk_frames'] = sum(x['neighbor_count'] > 0 for x in seq)
    put(run/'public/LINEAGE_AUDIT_V2.json', dict(status='POST_FREEZE_SOURCE_CONTRACT_FAILURE',
        rule='One pre-event identity hypothesis may use only an anchor-connected clean segment; same native across gaps/contact is not identity proof',
        checked_without_GT_or_model_outputs=True, cases=report))
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    main(parser.parse_args().run)
