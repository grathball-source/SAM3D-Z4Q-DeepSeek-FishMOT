"""Adaptive geometry with retained/inferred cohorts kept separate."""
import numpy as np
from common import HERE,read
from depth_measurement import statistics,usable
from adaptive_core import adaptive_core
CFG=read(HERE/'CONFIG.json')

def measure_raw(depth,masks,occupancy,segment,frame):
    result={}
    for native,region in masks.items():
        roi,geometry=adaptive_core(region,occupancy)
        core=statistics(depth,roi)
        result[native]=dict(native=native,source='RAW_SENSOR_ADAPTIVE',
            fact_id=f'{segment}/F{frame}/n:{native}/adaptive/raw',
            whole=statistics(depth,region),core=core,core_usable=bool(usable(core)),
            roi_geometry=geometry,physical_surface_identity='UNKNOWN')
    return statistics(depth,np.ones(depth.shape,bool)),result

def measure_restored(depth,provenance,masks,occupancy,segment,frame):
    assert depth.shape==provenance.shape==(360,640)
    assert np.all(np.isin(provenance,[0,1,2,3]))
    result={}
    for native,region in masks.items():
        core,geometry=adaptive_core(region,occupancy)
        cohorts={}
        for name,codes in (('retained',[1]),('inferred',[2,3])):
            fact=statistics(depth,core&np.isin(provenance,codes))
            fact['area']=int(core.sum())
            fact['valid_fraction']=fact['n']/max(1,fact['area'])
            cohorts[name]=fact
        measured=cohorts['retained'];inferred=cohorts['inferred']
        selected='retained' if usable(measured) else 'inferred' if usable(inferred) else 'NONE'
        selected_core=dict(cohorts[selected] if selected!='NONE' else measured)
        actual_mad=selected_core['mad']
        if selected=='inferred':
            selected_core['mad']=max(actual_mad,CFG['inferred_scale_floor_mm']/1.4826)
        delta=(measured['median']-inferred['median']
               if measured['median'] is not None and inferred['median'] is not None else None)
        result[native]=dict(native=native,source='RESTORED_V2_'+selected.upper(),
            fact_id=f'{segment}/F{frame}/n:{native}/adaptive/v2/{selected}',
            whole=statistics(depth,region),core=selected_core,core_usable=selected!='NONE',
            cohort=selected,cohorts=cohorts,retained_minus_inferred_mm=delta,
            actual_selected_mad_mm=actual_mad,
            core_mad_semantics='EFFECTIVE_NOISE_ADAPTER' if selected=='inferred' else 'ACTUAL_MEDIAN_ABSOLUTE_DEVIATION',
            roi_geometry=geometry,
            uncertainty_floor_mm=CFG['inferred_scale_floor_mm'] if selected=='inferred' else 15.,
            uncertainty_qualification='ASSUMED_NOT_CALIBRATED',
            provenance_counts={str(k):int((core&(provenance==k)).sum()) for k in (0,1,2,3)},
            physical_surface_identity='UNKNOWN')
    return statistics(depth,np.ones(depth.shape,bool)),result
