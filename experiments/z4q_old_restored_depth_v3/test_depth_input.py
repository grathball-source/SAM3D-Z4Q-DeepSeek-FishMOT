"""Small real-input check: only depth statistics may change."""
import copy

from run import DATA, HERE, SOURCE_MANIFEST, px, prepare_depth, read


def main():
    manifest = read(SOURCE_MANIFEST)
    selected = {0, 159, 199, 351, 468, 555}
    results = []
    for name in px.SEGMENTS:
        item = manifest['segments']['SOURCE_OLD'][name]
        for row, profiles, assignment, observations in px.feed(item):
            frame = row['global_frame']
            if frame not in selected:
                continue
            original_obs, original_profiles = copy.deepcopy(observations), copy.deepcopy(profiles)
            record = {'restored': {str(frame): px.descriptor(
                DATA / 'depth_restored_rgb_640x360' / f'{frame:06d}.npz')}}
            audit = prepare_depth(row, profiles, assignment, observations, item, record)
            for before, after in zip(original_obs, observations, strict=True):
                before.pop('depth'); after.pop('depth')
                assert before == after
            for native in profiles:
                original_profiles[native].pop('whole'); original_profiles[native].pop('core')
                profiles[native].pop('whole'); profiles[native].pop('core')
                assert original_profiles[native] == profiles[native]
            wrong = copy.deepcopy(record)
            wrong['restored'][str(frame)]['sha256'] = '0' * 64
            try:
                prepare_depth(row, profiles, assignment, observations, item, wrong)
            except AssertionError:
                pass
            else:
                raise AssertionError('tampered restored depth accepted')
            results.append(dict(frame=frame, changed_native_count=audit['changed_native_count'],
                                annotation_assisted_prediction_pixels=audit['provenance_in_prediction_union']['4']))
    assert {r['frame'] for r in results} == selected
    px.save(HERE / 'public/TEST_REPORT.json', dict(passed=True, cases=results,
        raw_depth_statistics_reconstructed=True, non_depth_fields_unchanged=True,
        tampered_restored_depth_rejected=True))
    print(results, flush=True)


if __name__ == '__main__':
    main()
