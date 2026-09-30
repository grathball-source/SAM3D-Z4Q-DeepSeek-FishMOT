"""Append the stricter q-source-version residual audit; sealed metrics unchanged."""
import json
from pathlib import Path
import analyze

HERE=Path(__file__).resolve().parent
RUN=HERE/'run'

if __name__=='__main__':
    data={name:analyze.load_segment(name) for name in analyze.score.SEGMENTS}
    audit=json.loads((RUN/'EVENT_AUDIT.json').read_text(encoding='utf-8'))
    result=analyze.forecast_diagnostics(data,audit)
    result['q_source_version_required']=True
    result['review_note']='Initial residual audit allowed the first later clean fragment after q even if its source generation changed. This append-only audit binds the actual q version and excludes that case; no input, prediction, choice or TrackEval score changed.'
    analyze.score.write_new(RUN/'FORECAST_DIAGNOSTICS_VERSIONED.json',result)
    print(json.dumps({k:v for k,v in result.items() if k in ('static_absolute_mm','dynamic_absolute_mm','fitted_WLS_comparisons','within_proxy_scale')}))
