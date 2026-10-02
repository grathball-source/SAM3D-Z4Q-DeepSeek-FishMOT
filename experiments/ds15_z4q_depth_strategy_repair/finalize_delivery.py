"""Append handoff and certify the completed public delivery, without pixel reads."""
from common import *


def main():
    summary=read(HERE/'SUMMARY.json');visuals=read(HERE/'PRIVATE_VISUALS.json')
    old=read(HERE/'OLD_READONLY_LOCK.json')['files']
    for path,digest in old.items():assert sha(ROOT/path)==digest,path
    for name in SEGMENTS:
        frozen=read(RUN/name/'public/FREEZE.json')
        for path,digest in frozen['code_sha256'].items():assert sha(path)==digest,path
    for case in visuals['cases']:verify_item(case['artifact'])
    write_new(HERE/'MAIN_JUDGEMENT.json',dict(status='METHOD_TARGET_NOT_MET_FROZEN_VERSION_STOP',
        frames=20098,arms=list(ARMS),engineering_input_publication_scoring='PASS',
        baseline_candidate_retention='FAIL_SHARED_PROTECTION_LOSES_ORIGINAL_BIRTH_RECOVERIES',
        depth_increment='ONE_FEEDING_LOCAL_GAIN_NOT_STABLE_ORIGINAL_AND_NATIVE_SUPERIORITY',
        original_actions_preserved=4,original_birth_actions_lost=2,
        original_six_action_physical_labels=dict(CORRECT=5,UNSCORABLE=1),
        depth_group_commits=dict(endpoint_correct=1,full_pre_consensus_unscorable=1),
        additional_depth_births=dict(UNSCORABLE=3),automatic_depth_vetoes=0,
        old_files_unchanged=len(old),private_visuals=len(visuals['cases']),
        new_model_http=0,model_cost_usd=0,training=0,SAM3_inference=0,completion_service=0,
        next_step='Separate anonymous observed-source continuity from certified identity references while preserving exact target versions; validate original candidate retention then freeze and replay the next version.',
        next_experiment_started=False,summary=artifact(HERE/'SUMMARY.json'),
        detailed_review=artifact(HERE/'DEEP_REVIEW.md')))
    handoff=ROOT/'research/HANDOFF.md';previous=handoff.read_bytes()
    prefix=('''# Latest: DS15 Z4Q/depth strategy repair (2026-10-02)

Completed five branches, eight segments,20098frames; all predictions/access sealed before original-reference scoring. Read experiments/ds15_z4q_depth_strategy_repair/DEEP_REVIEW.md, RESULTS.md, MAIN_JUDGEMENT.json, SUMMARY.json and three independent postseal audits. Original Z4Q19032 archived frames exact; native/R12 all20098 frame/event/metric parity exact;181842 mask tokens retained.1590 old files unchanged. Zero model HTTP/smoke/SAM3/training/completion/GPU/server/$0.24 private actual-ID/raw-depth figures are inventoried, not committed.

Target failed: DEPTH IDF1 dev92.002662 vsZ4Q99.333472; val76.641849 vs80.697587; Feeding81.820716 vs81.716806; L3weak72.426787 vs74.745256; LWweak60.613534 vs64.329395. Feeding small +0.103911/IDSW-2 does not meet native HOTA/AssA/IDSW superiority. Common protection loses original birth n7->0/dev3902 and n8->3/global11488 despite reopening both old hooks. It freezes source witness records while actual sources remain visible, creating artificial frame/time certificate gaps. Four original actions preserved; strict physical audit counts original six as5correct+1unknown, not6certifiedcorrect.3219 source-comparable checks/10850 total;0 depth vetoes. No rolling threshold search after negative results.

Only next step: separate anonymous real source continuity/proposal evidence from certified clean identity references. Preserve real target generation/epoch breaks, never update A/B clean from merged masks; jointly resolve and atomically publish current q. Do not force the known answers or copy whole B0 state. New version not started. Feeding only original4segments1471, notall1907; L3/LW prediction-dependent weak refs. Prior handoff remains verbatim below.

''').encode('utf-8')
    handoff.write_bytes(prefix+previous)
    assert handoff.read_bytes()[len(prefix):]==previous
    write_new(HERE/'HANDOFF_APPEND_PROOF.json',dict(path=str(handoff),old_bytes=len(previous),
        old_sha256=hashlib.sha256(previous).hexdigest(),prefix_bytes=len(prefix),old_suffix_unchanged=True,
        new=artifact(handoff)))
    write_new(HERE/'VISUAL_QA.json',dict(status='ACTUAL_PUBLISHED_MAPS_AND_READABLE_FIGURES_CHECKED',
        inspected=[artifact(HERE/'private/visuals'/p) for p in (
            'fishsa_development_8400_q3902_actual_ids.png','fishsa_validation_2888_q2188_actual_ids.png',
            'fishsa_development_8400_q4524_actual_ids.png')],numeric_plot=artifact(HERE/'RESULTS_PLOT.png'),
        findings='Original n7/ID0 versus new n7/ID7; original n8/ID3 versus new n8/ID8; old R12 1/7 swap and new H0. Same raw background and masks across columns. Plot matches five-arm metrics.',
        raw_depth_not_RGB=True,GT_raster_not_displayed=True,private_figures_not_public=True))
    public=[]
    for path in sorted(HERE.rglob('*')):
        if not path.is_file():continue
        parts=path.relative_to(HERE).parts
        if any(p in ('private','slice','__pycache__') for p in parts):continue
        if path.name=='PUBLIC_ARTIFACT_MANIFEST.json' or path.name.startswith('REMOTE_'):continue
        public.append(dict(relative_path=path.relative_to(ROOT).as_posix(),**artifact(path)))
    write_new(HERE/'PUBLIC_ARTIFACT_MANIFEST.json',dict(status='PUBLIC_DELIVERY_EXCLUDES_PRIVATE_PIXELS_AND_GT_RASTERS',
        files=public,count=len(public),total_bytes=sum(p['bytes'] for p in public),
        excluded=['private','slice','__pycache__','self','subsequent_remote_sync_proof'],
        handoff=artifact(handoff),private_inventory=artifact(HERE/'RESTRICTED_ARTIFACTS.json'),
        model_requests=0,cost_usd=0))
    print('Final public delivery:',len(public),'files; private figures',len(visuals['cases']))


if __name__=='__main__':main()
