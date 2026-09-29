"""Summarize measured offline decision-to-first-publication and reconnect delays."""
import json
import statistics

from source import HERE, SEGMENTS, save, sha


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def distribution(values):
    ordered = sorted(values)
    assert ordered
    return dict(count=len(ordered), minimum=ordered[0], median=statistics.median(ordered),
                p95=ordered[int(.95*(len(ordered)-1))], maximum=ordered[-1])


def branch(source, segment, fixed):
    root = HERE / 'public' / source / segment
    if fixed:
        root /= 'onefix'
        action_name = 'ACTION_LEDGER.jsonl'
    else:
        action_name = 'B0_ACTION_LEDGER.jsonl'
    public = rows(root / 'PUBLISH_LEDGER.jsonl')
    actions = rows(root / action_name)
    assert len(public) == len(actions)
    elapsed = [row['first_publish_monotonic']-row['received_monotonic'] for row in public]
    assert all(value >= 0 for value in elapsed)
    accepted = []
    for row in actions:
        events = row['events'] if fixed else row['trace']['events']
        for event in events:
            if event.get('kind') == 'reconnect' and event.get('accepted'):
                accepted.append(dict(original_frame=row['original_frame'], native_id=event['native_id'],
                    public_id=event['canonical_id'], local_birth_frame=event['birth_frame'],
                    birth_to_commit_frames=row['frame']-event['birth_frame'],
                    confirmation_count=event.get('confirmations'),
                    confirmation_span_s=event.get('confirmation_span_s')))
    return dict(first_publication_seconds=distribution(elapsed), accepted_reconnects=accepted,
                action_sha256=sha(root / action_name), publication_sha256=sha(root / 'PUBLISH_LEDGER.jsonl'))


def main():
    result = {source: {segment: {'Z4Q_FROZEN': branch(source, segment, False),
                                'Z4Q_ONEFIX': branch(source, segment, True)}
                       for segment in SEGMENTS}
              for source in ('SOURCE_OLD', 'SOURCE_BASELINE')}
    save(HERE / 'public/LATENCY_SUMMARY.json', dict(status='OFFLINE_REPLAY_MEASURED',
        first_publication_definition='frame processing begins to one irreversible JSONL output write',
        native_shared_with_frozen_row=True, source=result, model_http=0))
    print(json.dumps({source: {segment: {arm: data['first_publication_seconds']['median']
        for arm, data in arms.items()} for segment, arms in segments.items()}
        for source, segments in result.items()}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
