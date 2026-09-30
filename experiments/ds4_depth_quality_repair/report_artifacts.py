"""Postseal numeric SVG and private raw-depth QA; no manual pixel access."""
import argparse
import json
import os
import socket
import sys
from html import escape
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

sys.dont_write_bytecode = True
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
from bootstrap import (HERE, DATA, SEGMENTS, ARMS, CONFIG, records, artifact,
                       verify, write_new, decode, KERNEL, statistics, main_region, np, cv2)
from score_helpers import summarize

KNOWN = [('known_F704', 'feeding_000701_001060', 704, 'o013'),
         ('known_F766', 'feeding_000701_001060', 766, 'o012'),
         ('known_F1319', 'feeding_001201_001906', 1319, 'o007')]
PRIMARY = CONFIG['primary_arm']


def percent(value):
    return 'UNKNOWN' if value is None else f'{100*value:.2f}%'


def numeric_svg(metrics):
    """Every bar has an explicit fixed denominator; null is never shown as zero."""
    width, height, bar_x, bar_width = 1100, 1060, 210, 510
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="1100" height="1060" fill="white"/>',
             '<g font-family="Arial,sans-serif" fill="#17212b">']
    def text(x, y, value, size=16):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}">{escape(str(value))}</text>')
    def bar(y, values):
        position = bar_x
        for value,color in values:
            if value is None:
                continue
            assert np.isfinite(value) and 0 <= value <= 1
            span = value*bar_width
            parts.append(f'<rect x="{position:.3f}" y="{y}" width="{span:.3f}" height="24" fill="{color}"/>')
            position += span
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="24" fill="none" stroke="#b5bec6"/>')
    first = metrics['F2_DS3']
    text(30,36,'DS4: fixed-population measurement proxies',25)
    text(30,64,'Same exposed recording; silhouette consensus is not physical depth truth or tracking accuracy.',15)
    sections = [(100,'R: reference-compatible / discordant / UNKNOWN',first['r_n']),
                (405,'Q: matched-fish / nonmatched pixel yield',first['Q']['fish_denominator']),
                (710,'S: AVAILABLE / UNKNOWN coverage',first['source_objects'])]
    for top,label,denominator in sections:
        text(30,top,label,21)
        text(30,top+26,f'Fixed denominator: {denominator:,}',15)
        text(210,top+50,'0%',13); text(683,top+50,'100%',13)
        for index,arm in enumerate(ARMS):
            item = metrics[arm]; y=top+65+index*42
            text(30,y+18,arm,15)
            if top == 100:
                fixed = item['fixed_R']
                bar(y,[(fixed['compatible_yield'],'#248353'),(fixed['discordant_yield'],'#dc4a47'),(fixed['unknown_yield'],'#bcc3ca')])
                label = f'{fixed["compatible"]:,} / {fixed["discordant"]:,} / {fixed["unknown"]:,}'
                details = f'{percent(fixed["compatible_yield"])} / {percent(fixed["discordant_yield"])} / {percent(fixed["unknown_yield"])}'
            elif top == 405:
                q=item['Q']
                bar(y,[(q['fish_yield'],'#248353'),(q['nonfish_yield'],'#eaa33a')])
                label = f'Fish {percent(q["fish_yield"])}; nonmatched {percent(q["nonfish_yield"])}'
                details = f'Samples {q["selected_counts"]["fish"]:,} / {q["selected_counts"]["other_fish"]+q["selected_counts"]["background"]:,}'
            else:
                n=item['source_objects']
                accepted=item['accepted']/n if n else None
                unknown=item['unknown']/n if n else None
                bar(y,[(accepted,'#467ca8'),(unknown,'#bcc3ca')])
                label=f'{item["accepted"]:,} / {item["unknown"]:,}'
                details=f'{percent(accepted)} / {percent(unknown)}'
            text(742,y+9,label,14); text(742,y+28,details,13)
    text(30,1004,'Green: compatible or matched fish; red: discordant; orange: nonmatched; blue: available; gray: UNKNOWN.',13)
    text(30,1032,'Q excludes unmatched references; all original objects remain in S. No-sample quality remains UNKNOWN.',13)
    parts.append('</g></svg>')
    result='\n'.join(parts)+'\n'
    ElementTree.fromstring(result)
    return result


def choose_cases(rows):
    lookup={(row['segment'],row['frame'],row['token']):row for row in rows}
    cases=[dict(label=label,row=lookup[(segment,frame,token)],selection='FIXED_EXPOSED_REGRESSION')
           for label,segment,frame,token in KNOWN]
    ordered=sorted(rows,key=lambda row:(row['frame'],row['token'],row['segment']))
    newly_available=next((row for row in ordered if row['methods'][PRIMARY]['status']=='AVAILABLE'
                          and row['methods']['F2_DS3']['status']!='AVAILABLE'),None)
    newly_discordant=next((row for row in ordered if row['reference_usable']
                           and row['methods'][PRIMARY]['reference_compatible'] is False
                           and row['methods']['F2_DS3']['reference_compatible'] is not False),None)
    for label,row in [('earliest_new_primary_available',newly_available),
                      ('earliest_new_primary_discordant',newly_discordant)]:
        if row is not None:
            cases.append(dict(label=label,row=row,selection='DETERMINISTIC_EARLIEST_POSTSEAL_DIAGNOSTIC'))
    return cases,dict(earliest_new_primary_available_found=newly_available is not None,
                      earliest_new_primary_discordant_found=newly_discordant is not None)


def real_figure(case,facts,pixels):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable

    row=case['row']; frame=row['frame']; token=row['token']
    obj=pixels['objects'][token]; measured=facts['objects'][token]
    aligned_path=DATA/'depth_rgb_640x360'/f'{frame:06d}.npz'
    native_path=DATA/'depth_native_mm'/f'{frame:06d}.npy'
    assert artifact(aligned_path)['sha256']==facts['source_depth_sha256']
    assert artifact(native_path)['sha256']==facts['quality']['native_sha256']
    with np.load(aligned_path,allow_pickle=False) as sample:
        depth=sample['depth_mm']; indices=sample['source_index']
    native=np.load(native_path,allow_pickle=False)
    source=decode(obj['source_mask'])
    main,_=main_region(source)
    occupancy=sum((decode(p['source_mask']).astype('u2') for p in pixels['objects'].values()),np.zeros(source.shape,'u2'))
    core=cv2.erode((source & (occupancy==1)).astype('u1'),KERNEL).astype(bool)
    crop=obj['methods']['F2_DS3']['crop']; x0,y0,x1,y1=crop
    local=depth[y0:y1,x0:x1]; valid=np.isfinite(local)&(local>0)
    src_indices=indices[y0:y1,x0:x1]; traced=np.zeros(local.shape,'f4')
    assert np.array_equal(valid,src_indices>=0)
    traced[valid]=native.ravel()[src_indices[valid]]
    suspect=valid & (traced>CONFIG['native_suspect_above_mm'])
    assert np.array_equal(suspect,decode(pixels['suspect'])[y0:y1,x0:x1])
    values=local[valid]; vmin=float(values.min()) if values.size else 0.
    vmax=max(vmin+1.,float(values.max()) if values.size else 1.,float(traced.max()))
    norm=Normalize(vmin=vmin,vmax=vmax,clip=False)
    own=source[y0:y1,x0:x1]
    panels=[('Raw aligned camera-Z',None,None),('F0 whole raw samples',own & valid,measured['whole']),
            ('F1 exclusive raw core',core[y0:y1,x0:x1]&valid,measured['core'])]
    for arm in ARMS:
        pp=obj['methods'][arm]; selector=measured['methods'][arm]['selector']
        assert pp['crop']==crop
        selected=decode(pp['regions']['selected'])
        assert statistics(local,selected)==selector['selected']
        assert np.all(~selected | (own & valid))
        panels.append((arm,selected,selector))
    panels.append(('Original native source depth',None,None))
    fig,axes=plt.subplots(3,3,figsize=(15,12),constrained_layout=True)
    for ax,(label,selected,stat) in zip(axes.ravel(),panels,strict=True):
        shown=traced if label=='Original native source depth' else local
        ax.imshow(np.ma.masked_where(~valid,shown),cmap='viridis',norm=norm,interpolation='nearest')
        if own.any() and not own.all():
            ax.contour(own.astype('u1'),levels=[.5],colors=['white'],linewidths=.8)
        if suspect.any():
            rgba=np.zeros((*local.shape,4)); rgba[suspect]=[.94,.05,.06,.94]
            ax.imshow(rgba,interpolation='nearest')
        if selected is not None and selected.any():
            yy,xx=np.nonzero(selected)
            ax.scatter(xx,yy,marker='s',s=15,facecolors='none',edgecolors='#3bff7c',linewidths=.7)
        if label in ARMS and ARMS[label][1]:
            yy,xx=np.nonzero(own & ~main[y0:y1,x0:x1])
            if len(xx):
                ax.scatter(xx,yy,marker='x',s=12,c='#ffb549',linewidths=.65)
        title=label
        if stat is not None:
            selector=stat.get('selected',stat)
            median=selector['median']; median_text='UNKNOWN' if median is None else f'{median:.2f} mm'
            title+=f'\nn={selector["n"]}; median {median_text}'
            if 'status' in stat:
                title+=f'; {stat["status"]}'
                title+='\n'+stat['reason'].replace('_',' ').lower()
                plane=stat['plane']
                if plane is not None:
                    title+=f'\nbackground sigma {plane["residual_scale_mm"]:.2f}; contrast {plane["contrast_threshold_mm"]:.2f} mm'
        elif label=='Original native source depth':
            count=int(suspect.sum())
            title+=f'\nSUSPECT native >5000: {count} raw source points'
            if count:
                title+=f'; median {np.median(traced[suspect]):.2f} mm'
        else:
            title+=f'\nraw crop min {vmin:.2f}; max {float(values.max()) if values.size else 0.:.2f} mm'
        ax.set_title(title,fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
    ref=row.get('reference',{})
    ref_median=ref.get('median_mm',ref.get('median'))
    ref_text=('UNKNOWN' if ref_median is None else f'{ref_median:.2f} mm')
    fig.suptitle(f'{case["label"]}: F{frame}/{token} — {case["selection"]}\n'
                 f'Raw-silhouette consensus median {ref_text}; physical depth correctness UNKNOWN.\n'
                 'White: original SAM3 contour; green squares: actual selected raw samples; red: native >5000 mm SUSPECT. '
                 'Orange crosses: source fragments excluded by main-only arms. '
                 f'Original values preserved; color scale {vmin:.2f}–{vmax:.2f} mm.',fontsize=12)
    fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),ax=list(axes.ravel()),shrink=.5,label='Original depth (mm); red source-policy values shown explicitly')
    output=HERE/'private/visualizations'/f'{case["label"]}_F{frame}_{token}.png'
    assert not output.exists(),output
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=160)
    plt.close(fig)
    return dict(label=case['label'],frame=frame,token=token,selection=case['selection'],artifact=artifact(output),
                source_depth_sha256=facts['source_depth_sha256'],
                crop_depth_min_mm=vmin,crop_depth_max_mm=float(values.max()) if values.size else None,
                original_native_suspect_n=int(suspect.sum()),physical_depth_truth='UNKNOWN',manual_pixels_read=False)


def report():
    assert not (HERE/'VISUALIZATION_FILES.json').exists(),'refuse overwrite'
    for filename in ('MEASUREMENTS_SEALED.json','SCORING_SEALED.json'):
        seal=json.loads((HERE/filename).read_text(encoding='utf-8'))
        for item in seal['artifacts']:
            verify(item)
    freeze=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for item in freeze['code']+freeze['legacy_code']:
        verify(item)
    summary=json.loads((HERE/'SUMMARY.json').read_text(encoding='utf-8'))
    metrics=summary['groups']['POOLED']['arms']
    assert set(metrics)==set(ARMS)
    assert len({metrics[arm]['r_n'] for arm in ARMS})==1
    assert len({metrics[arm]['q_n'] for arm in ARMS})==1
    assert len({metrics[arm]['source_objects'] for arm in ARMS})==1
    svg_path=HERE/'MEASUREMENT_SUMMARY.svg'
    with svg_path.open('x',encoding='utf-8') as stream:
        stream.write(numeric_svg(metrics))
    rows=[row for name in SEGMENTS for row in records(HERE/f'{name}_occupancy.jsonl.gz')]
    cases,selection_summary=choose_cases(rows)
    required={(case['row']['segment'],case['row']['frame']) for case in cases}
    facts={}; pixels={}
    for name in SEGMENTS:
        for row in records(HERE/f'{name}_measurements.jsonl.gz'):
            if (name,row['frame']) in required:
                facts[(name,row['frame'])]=row
        for row in records(HERE/'private'/f'{name}_pixels.jsonl.gz'):
            if (name,row['frame']) in required:
                pixels[(name,row['frame'])]=row
    outputs=[real_figure(case,facts[(case['row']['segment'],case['row']['frame'])],
                         pixels[(case['row']['segment'],case['row']['frame'])]) for case in cases]
    write_new(HERE/'VISUALIZATION_FILES.json',dict(public_numeric_svg=artifact(svg_path),private_figures=outputs,
        selection=selection_summary,manual_pixels_read=False,instance_id_read=False,restored_depth_read=False,
        exposed_diagnostic_only=True,inference_http=0))
    print(json.dumps(dict(public_svg=str(svg_path),private_figures=len(outputs),selection=selection_summary),indent=2))


def selfcheck():
    rows=[]
    for index,(_,segment,frame,token) in enumerate(KNOWN):
        methods={arm:dict(status='UNKNOWN',selected_n=0,median_mm=None,occupancy=dict(n=0,fish=0,other_fish=0,background=0),
                         reference_compatible=None,reference_abs_error_mm=None) for arm in ARMS}
        rows.append(dict(segment=segment,frame=frame,token=token,reference_status='SCORABLE',reference_usable=True,
                         whole=dict(n=100,fish=95,other_fish=2,background=3),methods=methods))
    metrics={arm:summarize(rows,arm) for arm in ARMS}
    svg=numeric_svg(metrics)
    assert '<svg ' in svg and 'UNKNOWN' in svg and 'Fixed denominator: 3' in svg
    assert choose_cases(rows)[1]==dict(earliest_new_primary_available_found=False,earliest_new_primary_discordant_found=False)
    rows[1]['methods'][PRIMARY].update(status='AVAILABLE',selected_n=20,median_mm=1200.,
        occupancy=dict(n=20,fish=18,other_fish=1,background=1),reference_compatible=False,reference_abs_error_mm=100.)
    chosen,selection=choose_cases(rows)
    assert selection==dict(earliest_new_primary_available_found=True,earliest_new_primary_discordant_found=True)
    assert chosen[-1]['row']['frame']==766 and chosen[-2]['row']['frame']==766
    ElementTree.fromstring(numeric_svg({arm:summarize(rows,arm) for arm in ARMS}))
    print('report artifact selfcheck PASS; no data or manual reference reads')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--selfcheck',action='store_true')
    args=parser.parse_args()
    original_open=Path.open; original_key=np.lib.npyio.NpzFile.__getitem__
    def guarded_open(path,*a,**kw):
        normalized=str(path).replace('\\','/').lower()
        assert not any(s in normalized for s in ('labels_640x360','labels_source','labels_original','restoration/v3','depth_restored','sealed_test','response')),path
        return original_open(path,*a,**kw)
    def guarded_key(sensor,key):
        assert key in ('depth_mm','source_index'),key
        return original_key(sensor,key)
    with patch.object(Path,'open',guarded_open),patch.object(np.lib.npyio.NpzFile,'__getitem__',guarded_key),\
         patch.object(socket.socket,'connect',side_effect=AssertionError('no model/network')):
        selfcheck() if args.selfcheck else report()
