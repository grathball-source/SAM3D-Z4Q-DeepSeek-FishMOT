"""Do not mix retained sensor measurements with model estimates."""
import math
import cv2
import numpy as np
from common import HERE, read
from depth_measurement import statistics, usable, KERNEL
CFG=read(HERE/'CONFIG.json')
def measure_restored(depth,provenance,masks,occupancy,segment,frame):
    assert depth.shape==provenance.shape==(360,640)
    assert np.all(np.isin(provenance,[0,1,2,3]))
    result={}
    for native,region in masks.items():
        core=cv2.erode((region&(occupancy==1)).astype('u1'),KERNEL).astype(bool)
        cohorts={}
        for name,codes in (('retained',[1]),('inferred',[2,3])):
            cohort=core&np.isin(provenance,codes)
            fact=statistics(depth,cohort)
            # Eligibility denominator is the full exclusive eroded mask.
            fact['area']=int(core.sum())
            fact['valid_fraction']=fact['n']/max(1,fact['area'])
            cohorts[name]=fact
        measured=cohorts['retained'];inferred=cohorts['inferred']
        selected='retained' if usable(measured) else 'inferred' if usable(inferred) else 'NONE'
        selected_core=dict(cohorts[selected] if selected!='NONE' else measured)
        if selected=='inferred':
            selected_core['mad']=max(selected_core['mad'],CFG['inferred_scale_floor_mm']/1.4826)
        delta=(measured['median']-inferred['median']
               if measured['median'] is not None and inferred['median'] is not None else None)
        result[native]=dict(native=native,source='RESTORED_V2_'+selected.upper(),
            fact_id=f'{segment}/F{frame}/n:{native}/v2/{selected}',
            whole=statistics(depth,region),core=selected_core,core_usable=selected!='NONE',
            cohort=selected,cohorts=cohorts,retained_minus_inferred_mm=delta,
            uncertainty_floor_mm=CFG['inferred_scale_floor_mm'] if selected=='inferred' else 15.,
            uncertainty_qualification='ASSUMED_NOT_CALIBRATED',
            provenance_counts={str(k):int((core&(provenance==k)).sum()) for k in (0,1,2,3)},
            physical_surface_identity='UNKNOWN')
    return statistics(depth,np.ones(depth.shape,bool)),result
