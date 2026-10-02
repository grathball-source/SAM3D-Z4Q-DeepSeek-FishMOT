"""Private raw-depth/actual-ID figures, selected only after all predictions are scored."""
import gzip
import hashlib
import json
from collections import defaultdict

from common import HERE, RUN, SEGMENTS, ARMS, artifact, input_dir, read, rows, sha, verify_item, write_new
from source import RawDepth, native_masks, FIELD_READS


def verify_seals():
    all_path = RUN/'ALL_PREDICTIONS_SEALED.json'
    all_seal = read(all_path)
    assert all_seal['status'] in ('ALL_SIX_BRANCHES_EIGHT_SEGMENTS_SEALED', 'ALL_PREDICTIONS_AND_ACCESS_SEALED')
    assert tuple(all_seal['arms']) == ARMS and all_seal['frames'] == 20098
    assert set(all_seal['seals']) == set(all_seal['access_seals']) == set(SEGMENTS)
    checked = {}
    for name, (first, last) in SEGMENTS.items():
        public = RUN/name/'public'
        verify_item(all_seal['seals'][name]); verify_item(all_seal['access_seals'][name])
        seal = read(public/'PREDICTIONS_SEALED.json')
        assert tuple(seal['arms']) == ARMS and seal['frames'] == seal['published_frames'] == last-first+1
        assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        for filename, digest in seal['artifacts_sha256'].items():
            assert sha(public/filename) == digest, (name, filename)
        frozen = read(public/'FREEZE.json')
        assert frozen['no_gt_before_seal'] and frozen['new_model_http'] == frozen['model_cost_usd'] == 0
        for path, digest in frozen['code_sha256'].items():
            assert sha(path) == digest, path
        checked[name] = dict(prediction_seal=artifact(public/'PREDICTIONS_SEALED.json'),
                             access_seal=artifact(public/'ACCESS.json'))
    metrics = read(RUN/'METRICS.json')
    assert metrics['status'] == 'SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    assert metrics['all_seal'] == artifact(all_path)
    provenance = read(RUN/'SCORE_PROVENANCE.json')
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_predictions']
    assert provenance['masked_or_ignored_ids'] == 0
    for key in ('scorer', 'scoring_freeze', 'prediction_parity'):
        verify_item(provenance[key])
    assert read(RUN/'SCORING_FREEZE.json')['status'] == 'ALL_SEALS_VERIFIED_BEFORE_REFERENCE_SCORING'
    return dict(all_prediction_seal=artifact(all_path), segment_seals=checked,
                metrics=artifact(RUN/'METRICS.json'), scoring_provenance=artifact(RUN/'SCORE_PROVENANCE.json'))


def selected_rows(path, wanted):
    selected = {}
    with gzip.open(path, 'rb') as stream:
        for line in stream:
            row = json.loads(line)
            if row['frame'] in wanted:
                body = json.dumps(row, separators=(',', ':'), allow_nan=False).encode('utf-8')
                selected[row['frame']] = (row, dict(
                    uncompressed_row_bytes_sha256=hashlib.sha256(line).hexdigest(),
                    canonical_json_lf_sha256=hashlib.sha256(body+b'\n').hexdigest()))
    assert set(selected) == set(wanted), (str(path), sorted(set(wanted)-set(selected)))
    return selected


def mapping(row, arm):
    value = {int(item['mask'][2:]):item['id'] for item in row['variants'][arm]}
    assert len(value) == len(row['variants'][arm]) == len(set(value.values()))
    return value


def cases_after_score():
    """All order first splits, two fixed prior births, and two divergence onsets per segment."""
    cases = {}
    for name in SEGMENTS:
        public = RUN/name/'public'
        events = read(public/'EVENTS.json')['DEPTH_ORDER']
        orders = {row['frame']:row for row in rows(public/'ORDER_EVIDENCE.jsonl.gz') if row['arm']=='DEPTH_ORDER'}

        def add(q, tag, seeds=()):
            case = cases.setdefault((name, q), dict(segment=name, q=q, tags=[], seed_sources=set()))
            case['tags'].append(tag)
            case['seed_sources'].update(seeds)
            return case

        for event in events:
            q = event['q']
            if q is None:
                continue
            case = add(q, 'ALL_DEPTH_ORDER_FIRST_SPLITS', event['member_sources'])
            case['seed_sources'].update(int(n) for n in event['post_first_observations'])
            case['seed_sources'].add(event['group_source'])
            case['event'] = event['id']
            case['order'] = orders[q]
            pre_pairs = (orders[q]['detail'].get('order_evidence') or {}).get('pre_pairs', [])
            pre = event['pre_geometry_history']
            common = set(p['frame'] for p in pre.get('A', [])) & set(p['frame'] for p in pre.get('B', []))
            available = [p['frame'] for values in pre.values() for p in values]
            case['pre_frame'] = (pre_pairs[-1]['frame'] if pre_pairs else max(common) if common else
                                 max(available) if available else None)
            case['pre_policy'] = ('LATEST_MEASURED_PAIRED_ORDER' if pre_pairs else 'LATEST_COMMON_TRUSTED_GEOMETRY'
                                  if common else 'LATEST_AVAILABLE_SINGLE_ROLE_PRE_NOT_A_PAIRED_REFERENCE')
        fixed = {'fishsa_development_8400':(3902, (7, 4)), 'fishsa_validation_2888':(2188, (8, 7, 1))}
        if name in fixed:
            q, seeds = fixed[name]
            case = add(q, 'PRIOR_DS15_LOST_ORIGINAL_BIRTH', seeds)
            automatic = read(public/'AUTOMATIC_RECONNECT_AUDIT.json')['arms']['Z4Q_FROZEN']
            action = next((item for item in automatic if item['frame']==q), None)
            anchor = (action or {}).get('actual_old_anchor')
            if anchor:
                case.setdefault('pre_frame', anchor['frame'])
                case.setdefault('pre_policy', 'ORIGINAL_Z4Q_CLEAN_TARGET_BANK_REFERENCE')
                case['seed_sources'].add(anchor['native_id'])
        count, previous_difference = 0, False
        for row in rows(public/'predictions.jsonl.gz'):
            off, order = mapping(row, 'ORDER_OFF'), mapping(row, 'DEPTH_ORDER')
            differing = {n for n in off if off[n]!=order[n]}
            if differing and not previous_difference and count < 2:
                add(row['frame'], 'ACTUAL_ORDER_OFF_VS_DEPTH_ORDER_DIVERGENCE_ONSET', differing)
                count += 1
            previous_difference = bool(differing)
    return sorted(cases.values(), key=lambda case:(list(SEGMENTS).index(case['segment']), case['q']))


def context_crop(frames, seeds):
    import numpy as np
    bounds = {}
    for data in frames.values():
        for native, mask in data['masks'].items():
            yy, xx = np.nonzero(mask)
            if not len(xx):
                continue
            box = (int(xx.min()), int(yy.min()), int(xx.max()+1), int(yy.max()+1))
            if native in bounds:
                old = bounds[native]
                box = (min(old[0],box[0]), min(old[1],box[1]), max(old[2],box[2]), max(old[3],box[3]))
            bounds[native] = box
    present = seeds & set(bounds)
    assert present, 'No real mask for selected event or changed source'
    def union(keys):
        return (min(bounds[n][0] for n in keys), min(bounds[n][1] for n in keys),
                max(bounds[n][2] for n in keys), max(bounds[n][3] for n in keys))
    x0,y0,x1,y1 = union(present)
    nearby = {n for n,b in bounds.items() if b[2]>=x0-24 and b[0]<=x1+24 and b[3]>=y0-24 and b[1]<=y1+24}
    x0,y0,x1,y1 = union(nearby | present)
    return (max(0,x0-16), max(0,y0-16), min(640,x1+16), min(360,y1+16)), present, nearby-present


def main():
    proof = verify_seals()  # No raw pixels or plot selection precede completed scoring.
    assert not (HERE/'PRIVATE_VISUALS.json').exists(), 'Never replace finished visualizations'
    cases = cases_after_score()
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import patheffects
    by_segment = defaultdict(list)
    for case in cases:
        by_segment[case['segment']].append(case)
    inventory = []
    metrics = read(RUN/'METRICS.json')['segments']
    for name, segment_cases in by_segment.items():
        public = RUN/name/'public'
        for case in segment_cases:
            case['points'] = sorted({frame for frame in (case.get('pre_frame'), case['q']-1, case['q'])
                                     if frame is not None and 1<=frame<=case['q']})
        wanted = {frame for case in segment_cases for frame in case['points']}
        prediction_path, assignment_path = public/'predictions.jsonl.gz', input_dir(name)/'assignments.jsonl.gz'
        predictions, assignments = selected_rows(prediction_path, wanted), selected_rows(assignment_path, wanted)
        ledger = {row['frame']:row for row in rows(public/'PUBLISH_LEDGER.jsonl') if row['frame'] in wanted}
        reader, frames = RawDepth(name), {}
        try:
            for frame in sorted(wanted):
                row, prediction_hash = predictions[frame]
                assignment, assignment_hash = assignments[frame]
                assert ledger[frame]['prediction_row_sha256'] == prediction_hash['canonical_json_lf_sha256']
                assert (assignment['frame'], assignment['global_frame_id'], assignment['time']) == (frame,row['global_frame'],row['time'])
                masks = native_masks(assignment)
                assert all(set(mapping(row, arm)) == set(masks) for arm in ARMS)
                depth, _, _, binding = reader(row['global_frame'], row['time'])
                frames[frame] = dict(prediction=row, prediction_row_hashes=prediction_hash,
                    assignment_row_hashes=assignment_hash, masks=masks, depth=depth, source_binding=binding)
        finally:
            reader.close()
        for case in segment_cases:
            points = case['points']; shown = {frame:frames[frame] for frame in points}
            if case.get('order'):
                order_body = (json.dumps(case['order'],separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')
                assert hashlib.sha256(order_body).hexdigest() == ledger[case['q']]['order_row_sha256']['DEPTH_ORDER']
                assert case['order']['prediction_row_sha256'] == frames[case['q']]['prediction_row_hashes']['canonical_json_lf_sha256']
            crop,seeds,context = context_crop(shown, case['seed_sources'])
            x0,y0,x1,y1 = crop
            valid = np.concatenate([data['depth'][y0:y1,x0:x1].ravel() for data in shown.values()])
            valid = valid[np.isfinite(valid) & (valid>0)]
            lo,hi = np.percentile(valid,[2,98]) if len(valid) else (0.,1.)
            if hi<=lo:
                hi=lo+1.
            colors = {n:plt.get_cmap('tab10')(i%10) for i,n in enumerate(sorted(seeds))}
            fig,axes = plt.subplots(len(points),len(ARMS),figsize=(25.,3.1*len(points)+2.),squeeze=False)
            cmap = plt.get_cmap('viridis').copy(); cmap.set_bad('#343434')
            for y,frame in enumerate(points):
                data,row = frames[frame],frames[frame]['prediction']
                phase = 'FIRST SPLIT / q' if frame==case['q'] else 'q-1 OBSERVATION' if frame==case['q']-1 else 'PRE REFERENCE'
                for x,arm in enumerate(ARMS):
                    ax = axes[y,x]
                    image = ax.imshow(np.ma.masked_where(~np.isfinite(data['depth']) | (data['depth']<=0),data['depth']),
                        cmap=cmap,vmin=lo,vmax=hi,interpolation='nearest')
                    ids = mapping(row,arm)
                    for native in sorted((seeds | context) & set(data['masks'])):
                        mask=data['masks'][native]; yy,xx=np.nonzero(mask)
                        if not len(xx):
                            continue
                        color=colors.get(native,'#d0d0d0')
                        ax.contour(mask,levels=[.5],colors=[color],linewidths=1.4 if native in seeds else .6)
                        label=ax.text(float(xx.mean()),float(yy.mean()),f'n{native} / ID{ids[native]}',
                            color=color,fontsize=8 if native in seeds else 6,ha='center',va='center',clip_on=True)
                        label.set_path_effects([patheffects.withStroke(linewidth=2.2,foreground='#101010')])
                    ax.set_xlim(x0-.5,x1-.5); ax.set_ylim(y1-.5,y0-.5)
                    ax.set_title(f'{arm}\n{phase} | local {frame} / original {row["global_frame"]}',fontsize=9)
                    ax.set_xticks([]); ax.set_yticks([])
            order=case.get('order') or {}; detail=order.get('detail') or {}; evidence=detail.get('order_evidence') or {}
            relation=(f"{evidence.get('status','UNKNOWN_NOT_AN_ORDER_EVENT')} | {evidence.get('reason','No ordinal decision at this frame')} | "
                f"paired pre n={len(evidence.get('pre_pairs',[]))}, pre nearer(A) proxy={evidence.get('p_A_nearer_at_q','UNKNOWN')} | "
                f"choice={order.get('selected_choice','N/A')}, restore={(order.get('restore') or {}).get('status','N/A')}")
            values=metrics[name]['metrics']; a,b=values['DEPTH_ORDER'],values['Z4Q_FROZEN']
            headline=(f"DEPTH_ORDER minus Z4Q_FROZEN full segment: IDF1 {a['IDF1']-b['IDF1']:+.4f}; "
                f"HOTA {a['HOTA']-b['HOTA']:+.4f}; AssA {a['AssA']-b['AssA']:+.4f}; IDSW {a['IDSW']-b['IDSW']:+d}")
            fig.suptitle(f'{name} | q={case["q"]}\n{relation}\n{headline}\n'
                'Actual published IDs, common raw depth; no RGB/GT pixels. Confidence is an uncalibrated proxy.',fontsize=10,y=.985)
            fig.subplots_adjust(left=.015,right=.955,bottom=.065,top=.83,wspace=.06,hspace=.24)
            fig.colorbar(image,cax=fig.add_axes([.965,.15,.008,.60]),label='Raw depth (mm)')
            fig.text(.015,.025,'; '.join(case['tags'])+' | Pre policy: '+case.get('pre_policy','NO_TRUSTED_PRE_SELECTED')+
                ' | Gray: nearby native context. No future frame displayed.',fontsize=8)
            path=HERE/'private/visuals'/f'{name}_q{case["q"]}_six_actual_ids.png'
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as target:
                fig.savefig(target,format='png',dpi=130)
            plt.close(fig)
            inventory.append(dict(segment=name,q=case['q'],global_q=frames[case['q']]['prediction']['global_frame'],
                tags=case['tags'],frames=points,pre_policy=case.get('pre_policy','NO_TRUSTED_PRE_SELECTED'),
                display_arms=list(ARMS),crop_xyxy=list(crop),seed_sources=sorted(seeds),context_sources=sorted(context),
                order_evidence=evidence,actual_selected_choice=order.get('selected_choice'),
                artifact=artifact(path),prediction_file=artifact(prediction_path),assignment_file=artifact(assignment_path),
                frames_provenance=[dict(frame=frame,global_frame=frames[frame]['prediction']['global_frame'],
                    prediction_row_hashes=frames[frame]['prediction_row_hashes'],assignment_row_hashes=frames[frame]['assignment_row_hashes'],
                    actual_mapping={arm:{str(n):mapping(frames[frame]['prediction'],arm)[n]
                        for n in sorted(seeds | context) if n in frames[frame]['masks']} for arm in ARMS},
                    raw_source_binding=frames[frame]['source_binding']) for frame in points]))
    write_new(HERE/'PRIVATE_VISUALS.json',dict(status='POSTSEAL_POSTSCORE_SIX_ARM_ACTUAL_PUBLICATION_VISUALS',
        selection='All DEPTH_ORDER first-split events; fixed prior original births dev3902/val2188; at most two actual ORDER_OFF/DEPTH_ORDER divergence onsets per segment',
        cases=inventory,seals_verified_before_pixels=proof,source_field_reads=FIELD_READS,
        RGB_pixels_read=False,GT_pixels_read=False,restored_depth_read=False,private_images_not_for_git=True,
        physical_depth_order_truth='UNKNOWN_NO_SURFACE_GT',confidence_not_physical_accuracy=True,
        future_frames_displayed=False,new_model_http=0,cost_usd=0,visualizer=artifact(__file__)))
    print('Private six-arm actual-ID comparison figures:',len(inventory),flush=True)


if __name__=='__main__':
    main()
