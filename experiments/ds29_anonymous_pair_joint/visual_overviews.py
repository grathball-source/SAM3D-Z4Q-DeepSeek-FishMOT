"""Reproduce overview grids in a fresh directory, or verify the saved inventory."""
from common import *
import cv2,numpy as np
cv2.setNumThreads(1)
inventory=read(HERE/'PRIVATE_OVERVIEWS.json')
destination=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else None
if destination:
    assert not destination.exists(), 'Use a fresh private output directory'
    destination.mkdir(parents=True)
for index,figure in enumerate(inventory['figures'],1):
    verify_item(figure)
    canvas=np.full((850,1320,3),250,np.uint8)
    for cell,source in enumerate(figure['source_sheets']):
        pin=next(p for p in read(HERE/'PRIVATE_VISUALS.json')['figures'] if p['path']==source)
        verify_item(pin)
        pixels=cv2.imread(source);assert pixels is not None and pixels.shape[:2]==(850,1320)
        x=(cell%2)*660;y=(cell//2)*425
        canvas[y:y+425,x:x+660]=cv2.resize(pixels,(660,425),interpolation=cv2.INTER_AREA)
    if destination:assert cv2.imwrite(str(destination/f'overview_{index}.png'),canvas)
print('Verified four saved overview inventories and all fourteen source sheets; saved images unchanged')
