"""Direct real-state checks for the single new native-continuity guard."""
import copy

from onefix import CertifiedNativeGuard
from source import HERE, ROOT, save, sha
from trace import CONFIG, Bridge, read, state, stream


def main():
    item = read(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')['segments']['SOURCE_OLD']['feeding_000000_000199']
    feed = list(stream(item['derived']['observations']['path'], item['derived']['profiles']['path'],
                       200, global_start=0))
    frozen = Bridge(read(CONFIG))
    checks = []
    for row, profiles in feed[:159]:
        view = frozen.preview(row['frame'], row['time'], row['observations'], profiles)
        frozen.commit_once(view)
    before = copy.deepcopy(frozen)
    guarded = copy.deepcopy(before)
    guarded.engine.__class__ = CertifiedNativeGuard
    assert state(before) == state(guarded)
    row, profiles = feed[159]  # original F159, local 160
    allow_view = before.preview(row['frame'], row['time'], row['observations'], profiles)
    veto_view = guarded.preview(row['frame'], row['time'], row['observations'], profiles)
    allow, allow_trace = before.commit_once(allow_view)
    veto, veto_trace = guarded.commit_once(veto_view)
    assert allow[26] == 16 and veto[26] == 26
    assert all(allow[n] == veto[n] for n in allow if n != 26)
    assert any(event['kind'] == 'reconnect' and event.get('accepted') and event['native_id'] == 26
               for event in allow_trace['events'])
    assert any(item['native_id'] == 26 and item['certificate']['qualified']
               for item in veto_trace['onefix_guard'])
    assert 26 in before.engine.alias and 26 not in guarded.engine.alias
    checks.append(dict(frame=159, frozen_native26=allow[26], guard_native26=veto[26],
                       other_native_mappings_equal=True, pre_state_equal=True))
    # The same rule must leave a genuinely new source's five-frame confirmation alive.
    frozen = before
    for row, profiles in feed[160:194]:
        view = frozen.preview(row['frame'], row['time'], row['observations'], profiles)
        frozen.commit_once(view)
    eligible = copy.deepcopy(frozen)
    eligible.engine.__class__ = CertifiedNativeGuard
    row, profiles = feed[194]  # original F194, local 195
    view = eligible.preview(row['frame'], row['time'], row['observations'], profiles)
    mapping, trace = eligible.commit_once(view)
    assert mapping[38] == 7, (mapping.get(38), trace['onefix_guard'],
                              [e for e in trace['events'] if e.get('native_id') == 38])
    assert any(event['kind'] == 'reconnect' and event.get('accepted') and event['native_id'] == 38
               for event in trace['events'])
    assert all(item['native_id'] != 38 for item in trace['onefix_guard'])
    checks.append(dict(frame=194, short_new_source_native38_public=mapping[38],
                       accepted_reconnect_remains=True))
    output = HERE / 'public/ONEFIX_TEST.json'
    save(output, dict(status='PASS', checks=checks, test_sha256=sha(__file__),
                      no_gt_read=True, model_http=0))
    print('PASS', checks, flush=True)


if __name__ == '__main__':
    main()
