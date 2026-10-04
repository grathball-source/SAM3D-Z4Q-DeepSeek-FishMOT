"""Pinned real pixel sheets and overviews; actual viewing recorded separately."""
from common import *
import cv2
import numpy as np

main=read(HERE/'PRIVATE_VISUALS.json');failed=read(HERE/'FAILURE_VISUALS.json')
figures=main['figures']+[c['figure'] for c in failed['cases']]
for pin in figures:verify_item(pin)
overviews=[]
for category,pins in (('coverage',main['figures']),('failures',[c['figure'] for c in failed['cases']])):
    for page,start in enumerate(range(0,len(pins),8),1):
        canvas=np.full((1030,2680,3),250,'u1');cells=[]
        for i,pin in enumerate(pins[start:start+8]):
            img=cv2.imread(pin['path']);assert img is not None
            scale=min(650/img.shape[1],480/img.shape[0]);w,h=round(img.shape[1]*scale),round(img.shape[0]*scale)
            cell=np.full((515,670,3),250,'u1');cell[30:30+h,10:10+w]=cv2.resize(img,(w,h))
            cv2.putText(cell,str(start+i+1)+' '+Path(pin['path']).name[:70],(8,19),cv2.FONT_HERSHEY_SIMPLEX,.32,(15,15,15),1)
            canvas[(i//4)*515:(i//4+1)*515,(i%4)*670:(i%4+1)*670]=cell;cells.append(pin)
        path=HERE/'private'/f'{category}_overview_{page}.png';assert not path.exists() and cv2.imwrite(str(path),canvas)
        overviews.append(dict(figure=artifact(path),bound_source_figures=cells))
write_new(HERE/'VISUAL_REVIEW.json',dict(status='PIXEL_BINDINGS_AND_ALL_CASE_OVERVIEWS_READY_FOR_ACTUAL_VIEWING',
    figures=len(figures),coverage_figures=len(main['figures']),all_wrong_case_figures=len(failed['cases']),
    overviews=overviews,all_displayed_raw_facts_bound=True,no_RGB_GT_raster=True,
    future_publish_timeline_postseal_only_not_input=True,private_pixels_not_published=True,new_model_http=0,cost_usd=0))
print(json.dumps(dict(figures=len(figures),overviews=[p['figure']['path'] for p in overviews])))
