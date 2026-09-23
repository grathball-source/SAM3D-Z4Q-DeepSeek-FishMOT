"""Independent identity scoring helpers. This module is never imported by inference."""
from __future__ import annotations

from collections import Counter


def evaluate_transaction(transaction, gt_by_frame, fixed_public_by_gt):
    frame = transaction['frame']
    current = gt_by_frame.get(frame, {})
    edges = []
    displaced = {int(n) for n in transaction.get('displaced', [])}
    unscorable = False
    wrong = False
    for native, target in transaction['changes'].items():
        native = int(native)
        anchor = transaction['anchors'][native] if native in transaction['anchors'] else transaction['anchors'][str(native)]
        anchor_gt = gt_by_frame.get(anchor['frame'], {}).get(anchor['native_id'])
        current_gt = current.get(native)
        anchor_consistent = None if anchor_gt is None or current_gt is None else anchor_gt == current_gt
        target_correct = None if current_gt is None else fixed_public_by_gt.get(current_gt) == int(target)
        if anchor_consistent is None or target_correct is None:
            unscorable = True
        elif not anchor_consistent or not target_correct:
            wrong = True
        edges.append(dict(native=native, target=int(target), current_gt=current_gt, anchor_gt=anchor_gt,
                          anchor_consistent=anchor_consistent, target_public_correct=target_correct))
    scored_natives = {edge['native'] for edge in edges
                      if edge['anchor_consistent'] is not None and edge['target_public_correct'] is not None}
    all_displaced_scored = displaced <= scored_natives
    if not all_displaced_scored:
        unscorable = True
    verdict = 'unscorable' if unscorable else 'wrong' if wrong else 'correct'
    return dict(verdict=verdict, edges=edges,
                displaced_claims=sorted(displaced), all_displaced_claims_scored=all_displaced_scored)


def full_timeline_harm_audit(b0, branch, gt_by_frame, fixed_public_by_gt):
    harms, improvements, scorable = [], [], 0
    for frame in sorted(set(b0) | set(branch)):
        natives = set(b0.get(frame, {})) | set(branch.get(frame, {}))
        for native in sorted(natives):
            gt = gt_by_frame.get(frame, {}).get(native)
            expected = fixed_public_by_gt.get(gt) if gt is not None else None
            if expected is None:
                continue
            scorable += 1
            base_ok = b0.get(frame, {}).get(native) == expected
            branch_ok = branch.get(frame, {}).get(native) == expected
            row = dict(frame=frame, native=native, gt=gt, expected=expected,
                       B0=b0.get(frame, {}).get(native), branch=branch.get(frame, {}).get(native))
            if base_ok and not branch_ok:
                harms.append(row)
            if not base_ok and branch_ok:
                improvements.append(row)
    return dict(scorable_observations=scorable, harms=harms, improvements=improvements)


def association_relation_audit(b0, branch, gt_by_frame, horizons=(30, 90, 150)):
    """Score identity links to causal prior observations, including fragmented GTs.

    One latest prior anchor per GT and per public ID keeps every physical individual
    and every occupied identity represented without assuming a fixed GT-to-ID map.
    """
    latest_gt, latest_public = {}, {}
    harms, improvements, unscorable = [], [], []
    scorable = 0
    scorable_by_gt = Counter()
    frames = sorted(set(b0) | set(branch))
    for frame in frames:
        gt = gt_by_frame.get(frame, {})
        current0, current1 = b0.get(frame, {}), branch.get(frame, {})
        anchors = {(a['frame'], a['native']): a for a in (*latest_gt.values(), *latest_public.values())}
        for native in sorted(set(current0) | set(current1)):
            current_gt = gt.get(native)
            for a in anchors.values():
                age = frame - a['frame']
                if not 0 < age <= max(horizons):
                    continue
                row = dict(frame=frame, native=native, anchor_frame=a['frame'],
                           anchor_native=a['native'], age_frames=age,
                           current_gt=current_gt, anchor_gt=a['gt'],
                           B0=current0.get(native), B1=current1.get(native),
                           anchor_B0=a['B0'], anchor_B1=a['B1'])
                if current_gt is None or a['gt'] is None or None in (row['B0'], row['B1'], a['B0'], a['B1']):
                    row['reason'] = 'GT_or_prediction_missing'
                    unscorable.append(row)
                    continue
                scorable += 1
                scorable_by_gt[str(current_gt)] += 1
                truth_link = current_gt == a['gt']
                base_link = row['B0'] == a['B0']
                branch_link = row['B1'] == a['B1']
                row.update(truth_link=truth_link, B0_link=base_link, B1_link=branch_link,
                           error='broken_same_GT' if truth_link else 'wrong_different_GT')
                if base_link == truth_link and branch_link != truth_link:
                    harms.append(row)
                elif base_link != truth_link and branch_link == truth_link:
                    improvements.append(row)
        # Only completed prior frames may supply anchors for the next frame.
        for native, public in current0.items():
            a = dict(frame=frame, native=native, gt=gt.get(native), B0=public,
                     B1=current1.get(native))
            if a['gt'] is not None:
                latest_gt[a['gt']] = a
            latest_public[public] = a
        for key, a in list(latest_gt.items()):
            if frame - a['frame'] >= max(horizons):
                latest_gt.pop(key)
        for key, a in list(latest_public.items()):
            if frame - a['frame'] >= max(horizons):
                latest_public.pop(key)
    return dict(scorable_pairs=scorable, unscorable_pairs=len(unscorable),
                harms=harms, improvements=improvements, unscorable=unscorable,
                scorable_by_gt=dict(scorable_by_gt),
                horizons_frames=list(horizons))


def sustained_recovery(commit_frame, target_gt, target_public, branch, gt_by_frame, horizon=120, minimum=30):
    correct = 0
    errors = []
    unscorable = 0
    requested_end = commit_frame + horizon - 1
    available_end = max(set(branch) | set(gt_by_frame), default=commit_frame - 1)
    end = min(requested_end, available_end)
    for frame in range(commit_frame, end + 1):
        current_gt = gt_by_frame.get(frame, {})
        mapping = branch.get(frame, {})
        found = False
        for native, gt in current_gt.items():
            if gt != target_gt:
                continue
            found = True
            public = mapping.get(native)
            if public is None:
                unscorable += 1
            elif public == target_public:
                correct += 1
            else:
                errors.append(dict(frame=frame, native=native, public=public))
        # Any other real individual taking the target public ID is a target-occupancy error.
        for native, public in mapping.items():
            if public == target_public and current_gt.get(native) not in (None, target_gt):
                errors.append(dict(frame=frame, native=native, public=public, reason='wrong_target_occupant'))
        if not found:
            unscorable += 1
    truncated = end < requested_end
    return dict(stable=not truncated and correct >= minimum and not errors,
                correct_observations=correct, errors=errors,
                unscorable_frames=unscorable, truncated=truncated,
                observed_end=end, requested_end=requested_end)


def followup_horizons(commit_frame, target_gt, target_public, branch, gt_by_frame):
    """Fixed windows and the remaining observed segment; right-censor short windows."""
    last = max(set(branch) | set(gt_by_frame), default=commit_frame - 1)
    result = {str(h): sustained_recovery(commit_frame, target_gt, target_public,
                                         branch, gt_by_frame, horizon=h, minimum=h)
              for h in (30, 90, 150)}
    remaining = max(0, last - commit_frame + 1)
    result["remainder"] = sustained_recovery(commit_frame, target_gt, target_public,
                                              branch, gt_by_frame, horizon=remaining,
                                              minimum=remaining) if remaining else {
                                                  "stable": False, "truncated": True,
                                                  "observed_end": last,
                                                  "requested_end": commit_frame}
    return result
