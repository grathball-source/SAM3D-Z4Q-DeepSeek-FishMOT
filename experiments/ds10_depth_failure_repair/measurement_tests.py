"""Direct measurement safety tests, with no annotation reference."""
from common import *
import numpy as np
from measurement import measure_raw,measure_restored
def main():
    shape=(360,640);mask=np.zeros(shape,bool);mask[100:115,200:240]=1
    occ=mask.astype('u2');masks={1:mask};depth=np.full(shape,900.,dtype='f4')
    _,raw=measure_raw(depth,masks,occ,'test',1)
    assert raw[1]['core_usable'] and raw[1]['core']['median']==900
    prov=np.ones(shape,'u1');_,rest=measure_restored(depth,prov,masks,occ,'test',1)
    assert rest[1]['core']==raw[1]['core'] and rest[1]['cohort']=='retained'
    prov[:]=2;_,rest=measure_restored(depth,prov,masks,occ,'test',1)
    assert rest[1]['cohort']=='inferred' and rest[1]['actual_selected_mad_mm']==0
    assert rest[1]['core']['mad']==60/1.4826 and rest[1]['cohorts']['inferred']['mad']==0
    prov[:]=0;_,rest=measure_restored(depth,prov,masks,occ,'test',1)
    assert not rest[1]['core_usable'] and rest[1]['cohort']=='NONE'
    bad=np.full(shape,np.nan);_,raw=measure_raw(bad,masks,occ,'test',1)
    assert not raw[1]['core_usable'] and raw[1]['core']['median'] is None
    write_new(HERE/'MEASUREMENT_CHECKS.json',dict(status='PASS',checks=5,
        cases=['actual raw median','retained exact','inferred actual MAD vs noise proxy','no provenance UNKNOWN','NaN UNKNOWN']))
    print('5 measurement checks PASS')
if __name__=='__main__':main()
