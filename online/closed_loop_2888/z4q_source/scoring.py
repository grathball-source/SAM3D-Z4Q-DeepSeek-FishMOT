"""Independent identity scoring helpers. This module is never imported by inference."""
from __future__ import annotations


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


def sustained_recovery(commit_frame, target_gt, target_public, branch, gt_by_frame, horizon=120, minimum=30):
    correct = 0
    errors = []
    unscorable = 0
    end = commit_frame + horizon - 1
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
    return dict(stable=correct >= minimum and not errors, correct_observations=correct,
                errors=errors, unscorable_frames=unscorable, truncated=False)
