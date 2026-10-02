"""One append-only L3 bank-activity comparison after sealed prediction/scoring."""
import hashlib
import json

from common import HERE, RUN, ARMS, artifact, input_dir, read, rows, verify_item, write_new
from source import FIELD_READS, RawDepth, native_masks
from visualize_postseal import context_crop, mapping, selected_rows


def main():
    # Reuse the completed seal audit; do not rerun prediction or change frozen code.
    target = HERE / 'PRIVATE_STATE_VISUALS.json'
    image_path = HERE / 'private/visuals/L3_D1_3025_bank_activity_six_actual_ids.png'
    assert not target.exists() and not image_path.exists()
    audit_path = HERE / 'STATE_BASELINE_DIVERGENCE_AUDIT.json'
    audit = read(audit_path)
    assert audit['verification']['all_prediction_seals_match']
    scored = read(RUN / 'METRICS.json')
    assert scored['status'] == 'SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    verify_item(scored['all_seal'])
    provenance = read(RUN / 'SCORE_PROVENANCE.json')
    assert provenance['reference_opened_after_all_seals']
    assert not provenance['GT_used_for_predictions']
    public = RUN / 'L3/public'
    for item in audit['segments']['L3']['verified_prediction_artifacts']:
        verify_item(item)
    for item in audit['segments']['L3']['verified_frozen_code']:
        verify_item(item)
    verify_item(audit['segments']['L3']['raw_observation_source'])
    points, seeds = (2872, 2890, 3025), {5, 6, 9, 47}
    prediction_path = public / 'predictions.jsonl.gz'
    assignment_path = input_dir('L3') / 'assignments.jsonl.gz'
    predictions = selected_rows(prediction_path, set(points))
    assignments = selected_rows(assignment_path, set(points))
    ledger = {r['frame']: r for r in rows(public / 'PUBLISH_LEDGER.jsonl') if r['frame'] in points}
    reader, frames = RawDepth('L3'), {}
    try:
        for frame in points:
            row, prediction_hash = predictions[frame]
            assignment, assignment_hash = assignments[frame]
            assert ledger[frame]['prediction_row_sha256'] == prediction_hash['canonical_json_lf_sha256']
            assert (assignment['frame'], assignment['global_frame_id'], assignment['time']) == (
                frame, row['global_frame'], row['time'])
            masks = native_masks(assignment)
            assert all(set(mapping(row, arm)) == set(masks) for arm in ARMS)
            depth, _, _, binding = reader(row['global_frame'], row['time'])
            frames[frame] = dict(prediction=row, masks=masks, depth=depth,
                prediction_row_hashes=prediction_hash, assignment_row_hashes=assignment_hash,
                raw_source_binding=binding)
    finally:
        reader.close()
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import patheffects
    crop, visible, context = context_crop(frames, seeds)
    x0, y0, x1, y1 = crop
    valid = np.concatenate([r['depth'][y0:y1, x0:x1].ravel() for r in frames.values()])
    valid = valid[np.isfinite(valid) & (valid > 0)]
    lo, hi = np.percentile(valid, [2, 98]) if len(valid) else (0., 1.)
    hi = max(hi, lo + 1.)
    colors = {n: plt.get_cmap('tab10')(i) for i, n in enumerate(sorted(seeds))}
    cmap = plt.get_cmap('viridis').copy()
    cmap.set_bad('#343434')
    fig, axes = plt.subplots(3, 6, figsize=(25, 12), squeeze=False)
    phases = {2872: 'PRE GROUP: target activity frozen here',
              2890: 'LATER REAL native9 RESIDUAL (posthoc diagnostic)',
              3025: 'AUTOMATIC D1 COMMIT: original n47 -> ID9 (not S0)'}
    for y, frame in enumerate(points):
        data = frames[frame]
        row = data['prediction']
        absent = sorted(seeds - set(data['masks']))
        for x, arm in enumerate(ARMS):
            ax = axes[y, x]
            depth = data['depth']
            image = ax.imshow(np.ma.masked_where(~np.isfinite(depth) | (depth <= 0), depth),
                cmap=cmap, vmin=lo, vmax=hi, interpolation='nearest')
            ids = mapping(row, arm)
            for native in sorted((seeds | context) & set(data['masks'])):
                mask = data['masks'][native]
                yy, xx = np.nonzero(mask)
                if not len(xx):
                    continue
                color = colors.get(native, '#d0d0d0')
                ax.contour(mask, levels=[.5], colors=[color],
                           linewidths=1.6 if native in seeds else .6)
                text = ax.text(float(xx.mean()), float(yy.mean()), f'n{native} / ID{ids[native]}',
                    color=color, fontsize=8 if native in seeds else 6,
                    ha='center', va='center', clip_on=True)
                text.set_path_effects([patheffects.withStroke(linewidth=2.2, foreground='#101010')])
            ax.set_xlim(x0 - .5, x1 - .5)
            ax.set_ylim(y1 - .5, y0 - .5)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(f'{arm}\nlocal {frame} / original {row["global_frame"]}\n'
                f'absent real masks: {",".join("n"+str(n) for n in absent) or "none"}', fontsize=9)
        axes[y, 0].set_ylabel(phases[frame], fontsize=8)
    fig.suptitle('L3 | whole-bank activity protection changes original automatic D1\n'
        'n9 last contact with n5: local2854; protected last_seen2872: 0.596s <= 1; '
        'original real last_seen2890: 1.193s > 1\n'
        'At local3025: clean anchor2712 and target cost0.748384 unchanged; new partner5 '
        'margin -4.926819 < 10 rejects; original commits n47 -> ID9\n'
        'DEPTH_ORDER vs original full L3: IDF1 -2.318468, HOTA -1.808950, AssA -4.579391. '
        'Weak unreviewed prediction-derived reference.', fontsize=10, y=.99)
    fig.subplots_adjust(left=.025, right=.955, bottom=.07, top=.86, wspace=.06, hspace=.22)
    fig.colorbar(image, cax=fig.add_axes([.965, .15, .008, .65]), label='Raw sensor depth (mm)')
    fig.text(.025, .025, 'Actual published IDs; raw sensor depth + native masks only. Gray: local context. '
        'No RGB/GT pixels. Selected after score, not model input; no data after3025 shown. '
        'Missing source masks remain missing.', fontsize=9)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    with image_path.open('xb') as stream:
        fig.savefig(stream, format='png', dpi=130)
    plt.close(fig)
    item = dict(segment='L3', action_type='AUTOMATIC_D1_NOT_S0', action_local_frame=3025,
        action_original_frame=3024, frames=list(points), selection='POSTSCORE_KNOWN_BANK_ACTIVITY_FAILURE',
        display_arms=list(ARMS), seed_sources=sorted(seeds), context_sources=sorted(context),
        crop_xyxy=list(crop), artifact=artifact(image_path), prediction_file=artifact(prediction_path),
        assignment_file=artifact(assignment_path), reference_status=scored['segments']['L3']['reference_status'],
        frames_provenance=[dict(frame=f, original_frame=frames[f]['prediction']['global_frame'],
            phase=phases[f], absent_seed_masks=sorted(seeds - set(frames[f]['masks'])),
            prediction_row_hashes=frames[f]['prediction_row_hashes'],
            assignment_row_hashes=frames[f]['assignment_row_hashes'],
            actual_mapping={a: {str(n): value for n, value in mapping(frames[f]['prediction'], a).items()}
                           for a in ARMS}, raw_source_binding=frames[f]['raw_source_binding']) for f in points])
    write_new(target, dict(status='POSTSEAL_POSTSCORE_PRIVATE_STATE_FAILURE_VISUAL', cases=[item],
        audit=artifact(audit_path), scored=artifact(RUN / 'METRICS.json'),
        prediction_seal=artifact(public / 'PREDICTIONS_SEALED.json'),
        source_field_reads=FIELD_READS, RGB_pixels_read=False, GT_pixels_read=False,
        restored_depth_read=False, private_images_not_for_git=True, new_model_http=0, cost_usd=0,
        script=artifact(__file__), reproduction='Run this script in a new empty output copy after all seals/score; '
        'requires DS14 raw sensor bags/assignment caches and installed numpy/matplotlib.'))
    assert read(target)['cases'][0]['artifact'] == artifact(image_path)
    print(json.dumps(dict(image=artifact(image_path), public_metadata=artifact(target)), ensure_ascii=False))


if __name__ == '__main__':
    main()
