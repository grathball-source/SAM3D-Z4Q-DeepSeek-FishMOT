"""Independent small counterexamples for proposal scoring and public-ID guards."""
import json
from evaluate import canonical,consensus,physical_consistency,proposal_metrics,public_guard


def match(pairs):return dict(state='MATCH',matches=pairs,groups=[],unresolved=[])
def wait():return dict(state='UNRESOLVED',matches=[],groups=[],unresolved=[1,2])
def good(option):return dict(valid=True,option=option)


def run_checks():
    checks=[]
    def check(name,condition):
        assert condition,name;checks.append(name)
    truth={1:10,2:20};correct=match([[1,10],[2,20]]);wrong=match([[1,20],[2,10]])
    m=proposal_metrics(wrong,truth,True)
    check('wrong_match_harms_prior_success',m['wrong_proposal'] and m['harms_stable_success'] and not m['policy_correct'])
    m=proposal_metrics(correct,truth,False)
    check('correct_match_repairs_prior_failure',m['correct_assignment'] and m['correct_repair'] and m['policy_correct'])
    m=proposal_metrics(wait(),truth,True)
    check('WAIT_preserves_success_without_claiming_repair',m['policy_correct'] and m['abstain'] and not m['correct_assignment'] and not m['correct_repair'])
    m=proposal_metrics(None,truth,False)
    check('invalid_fallback_preserves_failure',not m['policy_correct'] and m['abstain'])
    check('physical_option_name_and_pair_order_independent',canonical(correct)==canonical(match([[2,20],[1,10]])))
    co,why=consensus([good(correct),good(match([[2,20],[1,10]])),good(correct)])
    check('three_physical_matches_required',co==canonical(correct) and why is None)
    co,why=consensus([good(correct),good(correct),good(wrong)])
    check('third_view_disagreement_veto',co is None and why=='physical_decision_disagreement')
    co,why=consensus([good(correct),dict(valid=False,option=correct),good(correct)])
    check('invalid_equal_payload_does_not_establish_consensus',co is None and why=='at_least_one_invalid')
    co,why=consensus([good(wait()),good(wait()),good(wait())])
    check('consistent_WAIT_is_not_match',co is None and why=='consistent_wait')
    check('repeat_compare_ignores_explanation',physical_consistency(good(correct),good(correct))['consistent'])
    check('repeat_vs_wait_is_real_change',physical_consistency(good(correct),good(wait()))['reason']=='MATCH_vs_WAIT')
    pre={1:100,2:200,3:300}
    # Existing focal IDs can swap physical observations, without creating duplicates.
    guard=public_guard(wrong,pre,{10:100,20:200,30:300},[1,2])
    check('focal_swap_permitted_by_transaction_guard',guard['approved'] and guard['hypothetical_public_by_native']=={10:200,20:100,30:300})
    # A third fish existing at pre is protected, even if removing it avoids duplicates.
    guard=public_guard(correct,pre,{10:300,20:400},[1,2])
    check('existing_nonfocal_identity_protected',not guard['approved'] and 'preexisting_nonfocal_public_identity' in guard['veto_reasons'])
    # New current public identities, absent at pre, may inherit the focal identity.
    guard=public_guard(correct,pre,{10:400,20:500,30:300},[1,2])
    check('newborn_current_identity_can_reconnect',guard['approved'] and guard['hypothetical_public_by_native']=={10:100,20:200,30:300})
    guard=public_guard(correct,pre,{10:400,20:500,30:100},[1,2])
    check('unselected_focal_owner_duplicate_veto',not guard['approved'] and guard['duplicate_public_ids']==[100])
    guard=public_guard(correct,pre,{10:400,20:500,30:-1,40:-1},[1,2])
    check('negative_quarantine_ID_duplicates_not_identity_collision',guard['approved'])
    before={10:400,20:500,30:300};copy=dict(before)
    guard=public_guard(correct,pre,before,[1,2])
    check('guard_never_mutates_original_public_map',before==copy)
    check('guard_keeps_unselected_current_observations',guard['hypothetical_public_by_native'][30]==300 and len(guard['hypothetical_public_by_native'])==3)
    guard=public_guard(match([[1,10],[2,10]]),pre,before,[1,2])
    check('duplicate_selected_observation_rejected',not guard['approved'] and guard['veto_reasons']==['invalid_complete_assignment'])
    guard=public_guard(correct,{1:100,2:100},before,[1,2])
    check('ambiguous_pre_focal_identity_rejected',not guard['approved'] and guard['veto_reasons']==['ambiguous_or_unconfirmed_pre_public_anchors'])
    return dict(passed=len(checks),failed=0,names=checks)


if __name__=='__main__':print(json.dumps(run_checks(),indent=2))
