"""Reproducible raw-depth/mask overview grids; preserve all original sheets."""
from common import *
import cv2,numpy as np
cv2.setNumThreads(1)
figures=read(HERE/'PRIVATE_VISUALS.json')['figures'];outputs=[]
for start in range(0,len(figures),4):
    canvas=np.full((850,1320,3),250,np.uint8);selected=figures[start:start+4]
    for cell,figure in enumerate(selected):
        verify_item(figure);pixels=cv2.imread(figure['path']);assert pixels.shape[:2]==(850,1320)
        x=(cell%2)*660;y=(cell//2)*425
        canvas[y:y+425,x:x+660]=cv2.resize(pixels,(660,425),interpolation=cv2.INTER_AREA)
    path=HERE/'private'/f'overview_{start//4+1}.png';assert not path.exists();assert cv2.imwrite(str(path),canvas)
    outputs.append(dict(artifact(path),source_sheets=[p['path'] for p in selected]))
write_new(HERE/'PRIVATE_OVERVIEWS.json',dict(figures=outputs))
print('Created',len(outputs),'private overview grids from',len(figures),'actual publication sheets',flush=True)
