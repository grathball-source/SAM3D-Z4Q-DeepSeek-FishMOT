"""DS11 after four seals: actual-bank RGB identity references and CLEAR switches."""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from types import SimpleNamespace

from scipy.optimize import linear_sum_assignment
from common import HERE, RUN, DS1, DATA, SEGMENTS, ARMS, input_dir, read, rows, sha, write_new


def legacy_audit_helpers(score):
    """Reuse frozen matching/CLEAR bodies with isolated scoring globals."""
    path = DS1/'postseal.py'
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('match_sources', 'clear_step')]
    scope = dict(score=score, np=score.np, linear_sum_assignment=linear_sum_assignment)
    exec(compile(tree, str(path), 'exec'), scope)
    return SimpleNamespace(match_sources=scope['match_sources'], clear_step=scope['clear_step'])


def expected_mapping(anchors, posts):
    if len(anchors) != 2 or len(posts) != 2:
        return {}
    if any(x['status'] != 'UNIQUE_IOU_MATCH' for x in list(anchors.values())+list(posts.values())):
        return {}
    target = {x['gt_id']: public for public, x in anchors.items()}
    if len(target) != 2 or set(target) != {x['gt_id'] for x in posts.values()}:
        return {}
    return {source: target[item['gt_id']] for source, item in posts.items()}


def mapping_outcome(restore, actual, expected):
    selected = {int(n): int(p) for n, p in (restore['mapping'] or {}).items()}
    physical = ('NOT_STAGED' if restore['status'].startswith('LOCAL_FALLBACK') else
                'UNSCORABLE_OR_NO_BIJECTION' if not expected else
                'CORRECT' if selected == expected else 'WRONG')
    first = ('UNSCORABLE_OR_NO_BIJECTION' if not expected else
             'CORRECT' if actual == expected else 'WRONG')
    return selected, physical, first


def identity_relation(first,second):
    if first.get('status')!='UNIQUE_IOU_MATCH' or second.get('status')!='UNIQUE_IOU_MATCH':return 'UNKNOWN'
    return 'SAME' if first['gt_id']==second['gt_id'] else 'DIFFERENT'


def birth_outcome(query,current_match,anchor_match):
    """Reference relation is independent of whether an action was staged."""
    relation=identity_relation(anchor_match,current_match)
    committed=query['status']=='COMMIT'
    physical=('NOT_STAGED' if not committed else 'UNSCORABLE' if relation=='UNKNOWN' else
              'CORRECT' if relation=='SAME' else 'WRONG')
    linked=query['selected_target'] is not None and query['actual_first_public_id']==query['selected_target']
    first=('NOT_RECONNECTED' if not linked else 'UNSCORABLE' if relation=='UNKNOWN' else
           'CORRECT' if relation=='SAME' else 'WRONG')
    return physical,first,relation


def birth_reference(query,frame,first_seen,match):
    """All pre identities are postseal diagnostics, never qualification inputs."""
    source=query['source'];post=match(frame,[source])[source]
    def anchor_match(anchor):
        if not anchor or not 1<=anchor['frame']<frame:return dict(status='INVALID_OR_MISSING_ANCHOR')
        native=int(anchor['native_id']);return dict(local_frame=anchor['frame'],native_source=native,**match(anchor['frame'],[native])[native])
    selected_candidate=query.get('selected_candidate') or {}
    reference_anchor=query.get('selected_reference_anchor',selected_candidate.get('reference_anchor'))
    selected=anchor_match(reference_anchor)
    selected_bank=anchor_match(query['selected_anchor'])
    physical,first,relation=birth_outcome(query,post,selected)
    references=[]
    for candidate in query['candidates']:
        native=candidate['source'];anchor=anchor_match(candidate.get('reference_anchor'))
        bank_anchor=anchor_match(candidate['anchor'])
        history=candidate['geometry_history'];points=[dict(frame=x['frame'],**match(x['frame'],[native])[native]) for x in history]
        histogram=Counter(x['gt_id'] for x in points if x['status']=='UNIQUE_IOU_MATCH')
        major=[gt for gt,count in histogram.items() if count>len(points)/2]
        majority=(dict(status='UNIQUE_IOU_MATCH',gt_id=major[0]) if len(major)==1 else dict(status='NO_CERTAIN_FULL_FRAGMENT_MAJORITY'))
        original_frame=first_seen.get(native)
        original=match(original_frame,[native])[native] if original_frame else dict(status='NO_ORIGINAL_APPEARANCE')
        first_point=points[0] if points else dict(status='NO_PRE_FRAGMENT')
        last_point=points[-1] if points else dict(status='NO_PRE_FRAGMENT')
        all_same=('UNKNOWN' if not points or any(x['status']!='UNIQUE_IOU_MATCH' for x in points) or anchor['status']!='UNIQUE_IOU_MATCH' else
                  'SAME' if all(x['gt_id']==anchor['gt_id'] for x in points) else 'DIFFERENT')
        references.append(dict(source=native,public=candidate['public'],eligible=candidate['eligible'],reasons=candidate['reasons'],anchor=anchor,
            reference_anchor=anchor,actual_bank_anchor=bank_anchor,reference_vs_actual_bank=identity_relation(anchor,bank_anchor),
            current_vs_actual_bank=identity_relation(post,bank_anchor),source_original_vs_actual_bank=identity_relation(original,bank_anchor),
            original_source_first_frame=original_frame,original_source_reference=original,
            pre_points=points,pre_total=len(points),pre_unique_matches=sum(histogram.values()),pre_gt_counts=dict(histogram),
            majority_denominator='ALL_PRE_POINTS_INCLUDING_UNKNOWN',majority_reference=majority,
            pre_all_vs_anchor=all_same,pre_first_vs_anchor=identity_relation(first_point,anchor),
            pre_last_vs_anchor=identity_relation(last_point,anchor),pre_majority_vs_anchor=identity_relation(majority,anchor),
            source_original_vs_anchor=identity_relation(original,anchor),source_original_vs_pre_last=identity_relation(original,last_point),
            current_vs_anchor=identity_relation(post,anchor),physical_surface_identity='UNKNOWN'))
    return dict(source=source,first_source_frame=query['first_source_frame'],status=query['status'],selected_target=query['selected_target'],
        selected_anchor=query['selected_anchor'],selected_reference_anchor=reference_anchor,post_match=post,anchor_match=selected,
        actual_bank_anchor_match=selected_bank,reference_vs_actual_bank=identity_relation(selected,selected_bank),
        current_vs_actual_bank=identity_relation(post,selected_bank),physical=physical,first_public_physical=first,
        anchor_current_relation=relation,actual_first_public_id=query['actual_first_public_id'],
        candidate_references=references,pre_identity_diagnostics_are_not_input_rules=True,
        physical_depth_reference_mm=None,physical_surface_identity='UNKNOWN')


def fragment_reference(event, physical, states, measurements, match, arm, frame_count):
    """RGB identity qualification never labels anonymous depth pieces as surfaces."""
    output = []
    q = event['q']
    for role, frozen in (event['depth_frozen'] or {}).items():
        samples = frozen['samples'][-10:]
        base = dict(role=role, source=frozen['source'], public=frozen['public'],
            key=frozen['key'], pre_sample_frames=[x['frame'] for x in samples],
            surface_identity='UNKNOWN', physical_depth_reference_mm=None,
            pre_identity_reference='UNKNOWN', q_identity_reference='UNKNOWN',
            post_fragment_reference='UNKNOWN', post_sample_frames=[], exclusions=[])
        anchor = physical.get('anchor_matches', {}).get(frozen['public'])
        if not samples:
            base['exclusions'].append('NO_FROZEN_HISTORY')
        if not anchor or anchor['status'] != 'UNIQUE_IOU_MATCH':
            base['exclusions'].append('UNSCORABLE_ACTUAL_BANK_ANCHOR')
        if not samples or not anchor or anchor['status'] != 'UNIQUE_IOU_MATCH':
            output.append(base)
            continue
        gt = anchor['gt_id']
        base['anchor_gt_id'] = gt
        references = [match(x['frame'], [frozen['source']])[frozen['source']] for x in samples]
        versions = [states[(x['frame'], arm)]['live'].get(str(frozen['source'])) for x in samples]
        base['pre_matches'] = references
        if any(x['status'] != 'UNIQUE_IOU_MATCH' or x.get('gt_id') != gt for x in references):
            base['exclusions'].append('PRE_FRAGMENT_NOT_UNIQUE_SAME_REFERENCE_ID')
            output.append(base)
            continue
        if any(not x or x['key'] != frozen['key'] for x in versions):
            base['exclusions'].append('PRE_FRAGMENT_VERSION_MISMATCH')
            output.append(base)
            continue
        base['pre_identity_reference'] = 'UNIQUE_SAME_RGB_REFERENCE_ID'
        targets = [int(n) for n, x in physical.get('post_matches', {}).items()
                   if x['status'] == 'UNIQUE_IOU_MATCH' and x['gt_id'] == gt]
        if q is None or len(targets) != 1:
            base['exclusions'].append('NO_UNIQUE_Q_SOURCE_FOR_REFERENCE')
            output.append(base)
            continue
        target = targets[0]
        base.update(q_identity_reference='UNIQUE_SAME_RGB_REFERENCE_ID', q_source=target)
        observation = measurements[q]['adaptive_raw' if arm=='R11_RAW' else 'restored'][str(target)]
        base['q_qualified_piece_count'] = observation.get('qualified_piece_count')
        base['q_piece_references'] = [x['piece_id'] for x in observation.get('pieces', []) if x['qualified']]
        active = states[(q, arm)]['live'].get(str(target))
        if not active:
            base['exclusions'].append('Q_SOURCE_VERSION_NOT_BOUND')
            output.append(base)
            continue
        base['q_key'] = active['key']
        begun = False
        stop_reason = 'WINDOW_OR_SEGMENT_END'
        for frame in range(q, min(q+30, frame_count+1)):
            current = states[(frame, arm)]['live'].get(str(target))
            if current and current['key'] != active['key']:
                stop_reason = 'SOURCE_VERSION_CHANGE'
                break
            valid = bool(current and frame in current['sample_frames'])
            if not valid:
                if begun:
                    stop_reason = 'RISK_MISSING_OR_UNQUALIFIED_SAMPLE'
                    break
                continue
            reference = match(frame, [target])[target]
            if reference['status'] != 'UNIQUE_IOU_MATCH' or reference.get('gt_id') != gt:
                if begun:
                    stop_reason = 'NONUNIQUE_OR_DIFFERENT_RGB_REFERENCE_ID'
                    break
                continue
            begun = True
            base['post_sample_frames'].append(frame)
        base['post_stop_reason'] = stop_reason
        if begun:
            base['post_fragment_reference'] = 'CONTIGUOUS_SAME_Q_VERSION_SAME_RGB_REFERENCE_ID'
        else:
            base['exclusions'].append('NO_QUALIFIED_CONTIGUOUS_POST_FRAGMENT_WITHIN_30_FRAMES')
        output.append(base)
    return output


def audit(score=None, run=RUN):
    if score is None:
        import evaluate as score
    # The gate occurs before the first label open, including direct CLI use.
    score.verify_all_seals(run)
    metrics = read(run/'METRICS.json')
    assert metrics['status'] == 'SCORED_AFTER_ALL_PREDICTION_SEALS'
    assert metrics['all_seal_sha256'] == sha(run/'ALL_PREDICTIONS_SEALED.json')
    helpers = legacy_audit_helpers(score)
    events_out, fragments, coverage = [], [], {}
    births_out=[];birth_row_counts=Counter()
    switches = {arm: [] for arm in ARMS}
    segment_switches = {}
    for name, (start, stop) in SEGMENTS.items():
        public = run/name/'public'
        predictions = {x['frame']: x for x in rows(public/'predictions.jsonl.gz')}
        assignments = {x['frame']: x for x in rows(input_dir(name)/'assignments.jsonl.gz')}
        states = {(x['frame'], x['arm']): x for x in rows(public/'DEPTH_STATES.jsonl.gz')}
        measurements = {x['frame']: x for x in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        events = read(public/'EVENTS.json')
        publish = {x['frame']: x for x in rows(public/'PUBLISH_LEDGER.jsonl')}
        labels = {}
        def label(local):
            if local not in labels:
                labels[local] = json.loads((DATA/'labels_640x360'/f'{start+local-1:06d}.json').read_bytes())
            return labels[local]
        def match(local, sources):
            return helpers.match_sources(assignments[local], label(local), sources)
        previous = {arm: {} for arm in ARMS}
        previous_step = {arm: {} for arm in ARMS}
        segment_switches[name] = {arm: 0 for arm in ARMS}
        reference_hash = hashlib.sha256()
        for local in range(1, stop-start+2):
            path = DATA/'labels_640x360'/f'{start+local-1:06d}.json'
            raw = path.read_bytes()
            reference_hash.update(path.name.encode()+b'\0'+raw)
            labels[local] = json.loads(raw)
            ids, reference = score.mask_rles(label(local)['shapes'])
            keys = [x['mask'] for x in assignments[local]['variants']['N0']]
            native = [score.original_score.rle(assignments[local]['masks'][key]) for key in keys]
            sim = (score.np.asarray(score.coco.iou(reference, native, [0]*len(native)), float)
                   if ids and native else score.np.zeros((len(ids), len(native))))
            for arm in ARMS:
                public_ids = [int(x['id']) for x in predictions[local]['variants'][arm]]
                previous_step[arm], new = helpers.clear_step(ids, keys, public_ids, sim,
                    previous[arm], previous_step[arm], start+local-1)
                switches[arm].extend(dict(item, segment=name, local_frame=local) for item in new)
                segment_switches[name][arm] += len(new)
        assert reference_hash.hexdigest() == metrics['reference'][name]['ordered_file_bytes_sha256']
        for arm in ARMS:
            assert segment_switches[name][arm] == metrics['segment_metrics'][name][arm]['IDSW'], (name, arm)
        facts=[obj for row in measurements.values() for obj in row['restored'].values()]
        coverage[name]=dict(source_objects=len(facts),cohort_histogram=dict(Counter(x['cohort'] for x in facts)),
            depth_usable=sum(x['core_usable'] for x in facts),physical_surface_identity='UNKNOWN')
        first_seen={}
        for local,assignment in assignments.items():
            for object in assignment['variants']['N0']:first_seen.setdefault(int(object['mask'][2:]),local)
        for birthrow in rows(public/'BIRTHS.jsonl.gz'):
            birth_row_counts[birthrow['arm']]+=1
            for query in birthrow['queries']:
                births_out.append(dict(segment=name,arm=birthrow['arm'],frame=birthrow['frame'],global_frame=start+birthrow['frame']-1,
                    **birth_reference(query,birthrow['frame'],first_seen,match)))
        for arm in ARMS[1:]:
            for event in events[arm]:
                q = event['q']
                base = dict(segment=name, arm=arm, event=event['id'], suspect=event['suspect_frame'],
                    confirm=event['confirm_frame'], q=q, original_q=start+q-1 if q is not None else None,
                    status=event['status'], reference_anchors=event['reference_anchors'])
                if q is None:
                    status = 'UNCONFIRMED' if event['confirm_frame'] is None else 'NO_SPLIT'
                    base.update(physical=status, first_public_physical=status)
                    events_out.append(base)
                    continue
                post_sources = [int(n) for n in event['post_first_observations']]
                assert len(post_sources) == 2
                anchors = {}
                for key, anchor in event['reference_anchors'].items():
                    public_id = int(key)
                    if not anchor or not 1 <= anchor['frame'] < q:
                        anchors[public_id] = dict(status='INVALID_OR_MISSING_ANCHOR')
                    else:
                        source = int(anchor['native_id'])
                        anchors[public_id] = dict(original_frame=start+anchor['frame']-1,
                            local_frame=anchor['frame'], native_source=source,
                            **match(anchor['frame'], [source])[source])
                posts = match(q, post_sources)
                expected = expected_mapping(anchors, posts)
                actual = {int(n): int(p) for n, p in publish[q]['event_publish'][arm]['first_public_pair'].items()}
                selected, outcome, first = mapping_outcome(event['restore'], actual, expected)
                pre_entry = {}
                for role, frozen in (event['depth_frozen'] or {}).items():
                    local = event['suspect_frame']-1
                    anchor = anchors.get(frozen['public'])
                    current = match(local, [frozen['source']])[frozen['source']] if local >= 1 else dict(status='NO_PRE_ENTRY_FRAME')
                    qualification = ('UNKNOWN' if not anchor or anchor['status']!='UNIQUE_IOU_MATCH' or current['status']!='UNIQUE_IOU_MATCH'
                        else 'SAME_AS_ANCHOR' if anchor['gt_id']==current['gt_id'] else 'DIFFERENT_FROM_ANCHOR')
                    pre_entry[role] = dict(frame=local if local>=1 else None, anchor_public=frozen['public'],
                        native_source=frozen['source'], match=current, identity_reference=qualification)
                base.update(physical=outcome, first_public_physical=first,
                    selected_choice=event['restore']['selected_choice'], decision_source=event['restore']['decision_source'],
                    selected_mapping=selected, first_public_mapping=actual, expected_mapping=expected,
                    residual=event['restore']['unassigned_member_residual'], anchor_matches=anchors,
                    post_matches=posts, pre_entry_reference=pre_entry,
                    depth_joint_available=bool(event['numeric']['detail']['used_edges']==4),
                    used_edges=event['numeric']['detail']['used_edges'],
                    commit_status=event['restore']['status'],
                    changes_against_lawful_preview=event['restore']['changes'],
                    baseline_preview_mapping=event['restore']['baseline_preview_mapping'],
                    selected_hypothesis=event['numeric']['choice'],
                    score_detail=event['numeric']['detail'])
                events_out.append(base)
                for fragment in fragment_reference(event, base, states, measurements, match, arm, stop-start+1):
                    fragments.append(dict(segment=name, arm=arm, event=event['id'], q=q, **fragment))
    for arm in ARMS:
        assert len(switches[arm]) == metrics['pooled_metrics'][arm]['IDSW'], arm
    statuses = ('CORRECT', 'WRONG', 'NOT_STAGED', 'UNSCORABLE_OR_NO_BIJECTION', 'NO_SPLIT', 'UNCONFIRMED')
    summary = {arm: {status: sum(x['arm']==arm and x['physical']==status for x in events_out)
        for status in statuses} for arm in ARMS[1:]}
    first_summary = {arm: {status: sum(x['arm']==arm and x['first_public_physical']==status for x in events_out)
        for status in statuses} for arm in ARMS[1:]}
    transactions_summary={arm:{status:sum(x['arm']==arm and x.get('commit_status')==status for x in events_out)
        for status in ('COMMIT','RESOLVE_NO_ID_CHANGE','LOCAL_FALLBACK_COMMITTED')} for arm in ARMS[1:]}
    correct_commit_summary={arm:sum(x['arm']==arm and x['physical']=='CORRECT' and x.get('commit_status')=='COMMIT' for x in events_out) for arm in ARMS[1:]}
    correct_nochange_summary={arm:sum(x['arm']==arm and x['physical']=='CORRECT' and x.get('commit_status')=='RESOLVE_NO_ID_CHANGE' for x in events_out) for arm in ARMS[1:]}
    interpretation = ('physical fields are legacy names for RGB-polygon identity correspondence at actual bank anchors; '
        'polygons do not certify depth surface ownership, and there is no physical depth-mm ground truth')
    write_new(run/'EVENT_AUDIT.json', dict(status='POSTSEAL_ACTUAL_BANK_ANCHOR_REFERENCE',
        summary=summary, first_public_summary=first_summary, events=events_out,
        transaction_status_summary=transactions_summary, correct_commits=correct_commit_summary,
        correct_resolutions_without_id_change=correct_nochange_summary,
        correct_count_definition='CORRECT staged mappings include both COMMIT and RESOLVE_NO_ID_CHANGE; only correct_commits count actual changes against lawful preview',
        mask_iou_min=.5, margin_min=.1, interpretation=interpretation,
        prediction_seals=metrics['seal_sha256'], unscorable_events_retained=True))
    write_new(run/'SWITCH_LEDGER.json', dict(status='POSTSEAL_CLEAR_SWITCHES', events=switches,
        segment_counts=segment_switches, metrics_sha256=sha(run/'METRICS.json'),
        count_exactly_equals_official_clear_idsw=True))
    write_new(run/'FRAGMENT_REFERENCE_AUDIT.json', dict(status='POSTSEAL_REFERENCE_QUALIFICATION_ONLY',
        interpretation=interpretation, future_post_fragments_are_audit_only=True,
        fragment_window_frames=30, roles=fragments, coverage=coverage,
        excluded_reason_counts=dict(Counter(reason for x in fragments for reason in x['exclusions'])),
        physical_depth_gt=False, pixel_surface_gt=False, surface_identity='UNKNOWN'))
    birth_summary={arm:{status:sum(x['arm']==arm and x['physical']==status for x in births_out)
        for status in ('CORRECT','WRONG','UNSCORABLE','NOT_STAGED')} for arm in ARMS[1:]}
    birth_status={arm:dict(Counter(x['status'] for x in births_out if x['arm']==arm)) for arm in ARMS[1:]}
    new_support={arm:bool(birth_summary[arm]['CORRECT']>=1 and all(metrics['frozen_support_rule'][arm]['rate_improvements'].values())
        and metrics['frozen_support_rule'][arm]['idsw_not_increased']) for arm in ARMS[2:]}
    write_new(run/'BIRTH_AUDIT.json',dict(status='POSTSEAL_FROZEN_CLEAN_ENDPOINT_BIRTH_REFERENCE',
        queries=births_out,frame_row_counts=dict(birth_row_counts),summary=birth_summary,status_summary=birth_status,
        correct_commits={arm:birth_summary[arm]['CORRECT'] for arm in ARMS[1:]},
        target_rule='SAME_BRANCH_AT_LEAST_ONE_CORRECT_NEW_BIRTH_COMMIT_AND_NATIVE_THREE_RATES_UP_IDSW_NOT_INCREASED',
        frozen_target_support=new_support,frozen_support_rule_met=any(new_support.values()),
        all_prediction_seal_sha256=metrics['all_seal_sha256'],metrics_sha256=sha(run/'METRICS.json'),
        unknown_and_noncommitted_queries_retained=True,pre_identity_references_are_posthoc_only=True,
        primary_reference='UNIQUE_RGB_MATCH_AT_ACTUAL_FROZEN_CLEAN_FRAGMENT_ENDPOINT_REFERENCE_ANCHOR',
        actual_bank_anchor_reference_is_separate=True,
        interpretation='Birth physical outcome uses the frozen clean endpoint RGB identity; actual bank anchor and earlier source identity changes are separate posthoc fields. RGB polygons do not certify depth surfaces or physical depth.',
        physical_depth_gt=False,pixel_surface_gt=False))
    filenames = ('VERIFICATION.json', 'METRICS.json', 'SCORE_PROVENANCE.json', 'EVENT_AUDIT.json',
                 'SWITCH_LEDGER.json', 'FRAGMENT_REFERENCE_AUDIT.json','BIRTH_AUDIT.json')
    write_new(run/'SCORING_SEALED.json', dict(status='ALL_SEGMENTS_AND_EVENTS_SCORED',
        all_prediction_seal_sha256=sha(run/'ALL_PREDICTIONS_SEALED.json'),
        artifacts_sha256={name: sha(run/name) for name in filenames}))
    return dict(summary=summary,birth_summary=birth_summary,birth_target_met=any(new_support.values()),switches={arm:len(x) for arm,x in switches.items()})


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False))
