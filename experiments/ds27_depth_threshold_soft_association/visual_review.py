"""Small reproducible private overview producer and explicit visual review receipt."""
from common import *
import cv2, numpy as np

v1=read(HERE/'PRIVATE_VISUALS.json');v2=read(HERE/'PRIVATE_VISUALS_V2.json')
assert v1['figure_count']==v2['figure_count']==28
assert v1['source_arm_case_count']==v2['source_arm_case_count']==32
for manifest in (v1,v2):
    verify_item(manifest['producer'])
    for figure in manifest['figures']:verify_item(figure)
for a,b in zip(v1['cases'],v2['cases'],strict=True):
    for key in ('segment','arm','selection','q','check_sha256','comparison_sha256','panels'):
        assert a.get(key)==b.get(key), 'Pure layout revision changed numeric/source semantics'
qa=HERE/'private/v2/qa';qa.mkdir(exist_ok=True)
paths=[qa/f'overview_{i:02d}.png' for i in range(1,5)]
if sys.argv[1]=='make':
    for page,path in enumerate(paths):
        assert not path.exists();canvas=np.full((1030,2680,3),250,'u1')
        for i,item in enumerate(v2['figures'][page*8:page*8+8]):
            image=cv2.imread(item['path']);assert image is not None
            scale=min(650/image.shape[1],480/image.shape[0]);w,h=round(image.shape[1]*scale),round(image.shape[0]*scale)
            cell=np.full((515,670,3),250,'u1')
            cell[30:30+h,10:10+w]=cv2.resize(image,(w,h),interpolation=cv2.INTER_AREA)
            cv2.putText(cell,Path(item['path']).stem[:78],(10,20),cv2.FONT_HERSHEY_SIMPLEX,.33,(10,10,10),1,cv2.LINE_AA)
            canvas[(i//4)*515:(i//4+1)*515,(i%4)*670:(i%4+1)*670]=cell
        assert cv2.imwrite(str(path),canvas)
    print(json.dumps([artifact(p) for p in paths]))
else:
    assert sys.argv[1]=='reviewed' and all(p.exists() for p in paths)
    # Invoke only after the four actual overview images and the two named full
    # figures have been inspected. This receipt never claims model efficacy.
    details=[HERE/'private/v2/private/L3_SOFT_C1_S5_F03351.png',
        HERE/'private/v2/private/feeding_000000_000199_SOFT_C1_S5_blocked_F00158.png']
    write_new(HERE/'VISUAL_REVIEW.json',dict(status='PASS_ACTUAL_OVERVIEW_AND_TWO_FULL_SIZE_LAYOUT_REVIEW',
        producer=artifact(__file__),manifests=[artifact(HERE/'PRIVATE_VISUALS.json'),artifact(HERE/'PRIVATE_VISUALS_V2.json')],
        actual_v2_overviews_viewed=[artifact(p) for p in paths],
        all_28_v2_figures_seen_in_actual_overviews=True,individual_full_size_figures_viewed=[artifact(p) for p in details],
        not_all_28_full_size_figures_individually_viewed=True,
        v1_v2_numeric_panels_and_selected_source_contexts_exactly_equal=True,
        header_title_overlap_fixed_by_16px_spacing=True,all_weak_background_missing_supports_retained=True,
        formal_measured_cases=12,postseal_diagnostic_cases=16,no_competitive_check_numeric_only_cases=4,
        diagnostic_scope='64 endpoint facts measured after prediction seal; NOT FORMAL ASSOCIATION INPUT',
        GT_RGB_read=False,new_model_http=0,cost_usd=0))
    print('Visual review receipt written; raw pixel figures remain private')
