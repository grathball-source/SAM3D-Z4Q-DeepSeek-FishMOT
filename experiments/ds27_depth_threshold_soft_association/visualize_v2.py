"""Add 16 pixels above raster titles; preserve v1 science, code and outputs."""
from common import *
import inspect
import visualize as v1

original_code=artifact(HERE/'visualize.py')
previous=artifact(HERE/'PRIVATE_VISUALS.json')
for name in ('_render','_render_diagnostic'):
    source=inspect.getsource(getattr(v1,name))
    before='header_h=max(map(len,headers))*19+14'
    assert source.count(before)==1
    exec(compile(source.replace(before,'header_h=max(map(len,headers))*19+30'),
        str(Path(__file__).resolve()),'exec'),v1.__dict__)

destination=HERE/'PRIVATE_VISUALS_V2.json'
def write_output(path,value):
    assert Path(path).name=='PRIVATE_VISUALS.json'
    value.update(layout_revision=2,header_gap_added_px=16,
        original_producer=original_code,previous_attempt=previous,
        selection_measurement_and_scientific_thresholds_unchanged=True)
    write_new(destination,value)

v1.write_new=write_output
v1.HERE=HERE/'private/v2'
v1.HERE.mkdir(exist_ok=True)
v1.__file__=str(Path(__file__).resolve())
v1.main()
