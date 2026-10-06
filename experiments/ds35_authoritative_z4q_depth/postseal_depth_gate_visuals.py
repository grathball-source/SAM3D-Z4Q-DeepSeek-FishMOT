"""Every sealed common-depth case that failed the gate; private pixels, no GT."""
from common import *
from verify_inputs import verify_all

def main():
    verify_all()
    assert read(RUN/'SCORING_FREEZE.json')['verified_before_reference_raster_read']
    visual=module('ds35_frozen_actual_source_panels',HERE/'post_visuals.py')
    destination=HERE/'private/postseal_depth_gate_cases'
    destination.mkdir(parents=True,exist_ok=False)
    cases=[]
    for name in SEGMENTS:
        for event in read(RUN/name/'public/EVENTS.json')['DEPTH_OVERRIDE']:
            d=event.get('joint_decision',{})
            if not d.get('common_weights',{}).get('depth'):continue
            case=visual.private_case(name,event,'DEPTH_OVERRIDE',destination)
            case.update(selection='ALL_COMMON_DEPTH_CASES_POSTSEAL_NOT_GROUND_TRUTH_SELECTION',
                decision_reason=d['reason'],depth_gate=d['depth_gate'])
            cases.append(case)
    assert len(cases)==read(HERE/'POSTSEAL_MEASUREMENT_REVIEW.json')['counts']['common_depth_available']
    write_new(HERE/'POSTSEAL_DEPTH_GATE_PRIVATE_VISUALS.json',dict(
        status='POSTSEAL_PRIVATE_ALL_COMMON_DEPTH_GATE_CASES',cases=cases,helper=artifact(__file__),
        source_panel_helper=artifact(HERE/'post_visuals.py'),all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),
        measurements=artifact(HERE/'POSTSEAL_MEASUREMENT_REVIEW.json'),
        predictions_parameters_and_scores_unchanged=True,no_GT_raster_read=True,
        private_pixels_not_for_git=True,new_model_http=0,cost_usd=0))
    print('All common-depth gate private panels complete',len(cases),flush=True)

if __name__=='__main__':main()
