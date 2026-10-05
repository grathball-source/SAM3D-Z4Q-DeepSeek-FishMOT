"""Contact sheets of actual restricted diagnostic figures."""
from common import *
import cv2,numpy as np
figures=read(HERE/'PRIVATE_VISUALS.json')['figures'];records=[]
for offset in range(0,len(figures),6):
    batch=figures[offset:offset+6];canvas=np.full((900,1350,3),240,'u1')
    for j,f in enumerate(batch):
        verify_item(f);im=cv2.imread(f['path']);assert im is not None
        small=cv2.resize(im,(675,450),interpolation=cv2.INTER_AREA)
        y,x=(j//2)*300,(j%2)*675
        small=cv2.resize(im,(675,300),interpolation=cv2.INTER_AREA);canvas[y:y+300,x:x+675]=small
    path=HERE/'private'/f'overview_{offset//6}.png';assert not path.exists();assert cv2.imwrite(str(path),canvas)
    records.append(dict(artifact(path),source_figures=[x['sha256'] for x in batch]))
write_new(HERE/'PRIVATE_OVERVIEWS.json',dict(figures=records))
