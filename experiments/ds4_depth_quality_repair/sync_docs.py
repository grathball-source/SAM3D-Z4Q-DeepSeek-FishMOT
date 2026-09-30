"""Append current DS4 handoff while preserving historical bytes."""
import subprocess
from bootstrap import ROOT


def change(path,transform):
    original=subprocess.check_output(['git','show',f'HEAD:{path}'],cwd=ROOT)
    file=ROOT/path
    assert file.read_bytes()==original,'refuse overwrite existing local edits'
    file.write_bytes(transform(original))


def run():
    lead='''Current result,2026-09-30: [DS4 failure review and depth-quality repair](experiments/ds4_depth_quality_repair/RESULTS.md) completed all1066 exposed SOURCE_OLD frames and28382 original masks, five controlled measurement arms. **Engineering/input PASS; PROXY_GAIN_ONLY; physical depth/registration/tracking UNKNOWN.** On fixed21817 raw-silhouette references, F2→F6 compatible15766→17655, discordant202→143, UNKNOWN5849→4019. Fixed-Q fish retention35.3371%→41.2397%, but nonmatched samples+16620 and44new proxy conflicts are preserved. F766 raw12.25m samples were traced to original BAG, then the new primary selected91 original samples at1142.53mm; F704 refuses an ambiguous side branch. Mixed-depth components, wrong-fish samples and reference contamination remain real failure mechanisms.18checks, full DS3 pixel/fact reproduction, seals and independent postscore review pass. No tracker/API/training/SAM3/completion; HTTP/cost0. Private raw-depth QA was actually viewed and remains local. [Current handoff](research/HANDOFF.md): one next step is independent physical-surface and spatial-registration pixel audit, without retuning this run or automatic VLM/tracker integration.

'''.encode('utf-8')
    def readme(old):
        old=old.replace(b'Current result,2026-09-30:',b'Archived DS3 result,2026-09-30:',1)
        index=old.index(b'Archived DS3 result,2026-09-30:')
        return old[:index]+lead+old[index:]
    change('README.md',readme)
    index='''## DS4: depth source/background quality repair — PROXY_GAIN_ONLY

[Complete failure review/results](experiments/ds4_depth_quality_repair/RESULTS.md), [frozen plan](experiments/ds4_depth_quality_repair/PLAN.md), [summary](experiments/ds4_depth_quality_repair/SUMMARY.json), [independent source audit](experiments/ds4_depth_quality_repair/SOURCE_AUDIT.json), [full component audit](experiments/ds4_depth_quality_repair/COMPONENT_AUDIT.json), [postscore review](experiments/ds4_depth_quality_repair/POSTSCORE_REVIEW.md). All1066 exposed source frames,28382 unchanged masks; 5arms,18tests; old DS3 facts/pixels and Q28088/294 exact. Main F6 native-SUSPECT admission+separate background floor: fixed R21817 compatible+1889, discordant−59, UNKNOWN−1830, with44new discordances and16620extra nonmatched sample pixels. Physical depth, pixel surface ownership, registration and tracking increment UNKNOWN.0API/training/SAM3/completion/cost; no tracker change. Whole/core and prior DS1/2/3 seals unchanged. Restricted actual pixel paths/bytes/SHA remain private; all public code/logs/results require nonforce main push and actual remote proof. One next step: independent pixel surface/registration audit.

'''.encode('utf-8')
    def add_index(old):
        position=old.index(b'## DS3:')
        return old[:position]+index+old[position:]
    change('EXPERIMENT_INDEX.md',add_index)
    handoff='''# Active handoff — DS4 frozen depth-quality measurement,2026-09-30

Read experiments/ds4_depth_quality_repair/RESULTS.md, PLAN/CONFIG/FREEZE,
SOURCE_AUDIT/COMPONENT_AUDIT/EVALUATION_REVIEW, CHECKS/SCORE_CHECKS/READONLY_ACCEPTANCE,
MEASUREMENTS_SEALED/SCORING_SEALED/SUMMARY, both per-object occupancy streams,
POSTSCORE_REVIEW/POSTSCORE_DIAGNOSTICS, CASES_POSTSEAL, source/restricted/public
inventories, all logs, original and caption-repaired QA metadata/actual inspection,
and REMOTE_VERIFICATION. Base ace9a37b1c6a2a59d3d5397f335d081f1a5a8ae8.

All1066 exposed SOURCE_OLD frames701–1060/1201–1906 and28382 masks completed.
Engineering/input PASS; PROXY_GAIN_ONLY; physical depth/registration/tracking UNKNOWN.
Q28088+294unscorable exact to DS3; fixed raw-silhouette R21817.
F2→F6 compatible15766→17655, discordant202→143, UNKNOWN5849→4019.
44new discordances (39old-compatible,5old-UNKNOWN), fish yield35.3371→41.2397%,
nonmatched samples41620→58240; conditional purity98.9106→98.6966%.
F6 is frozen native>5m SUSPECT admission plus separate1mm background floor;
foregound floor15mm, contrast floor30mm and other DS3 rules unchanged.
F3 range-only/F4 main-only/F5 combination are controls, no postscore winner.
F4 actually reselects:272restored/137rejected, matched pixels net+9012;
do not substitute the earlier static164old-component veto cost for real results.

F76657 native12m points verified in original BAG, decoding and reprojection exact;
F6 selects91 raw1.1425m points. Sensor range/hardware cause UNKNOWN.
F704 primary refuses ambiguous side branch. F1821 mixes two depth modes in one
connected component, with lower MAD but shifted median; F1044 selects other fish;
F1385wrong-fish selection still proxy-compatible; F1319raw reference shares anomaly.
Low-depth strips not fully covered by RGB source contours need physical spatial
audit; byte/code reprojection equality does not prove calibrated surface alignment.
Raw-silhouette consensus and occupancy are not physical distance/surface GT.

18unit checks + bounded read-only scorer acceptance + exact every-object DS3
reproduction pass. A launcher review-field mismatch was fixed before FREEZE;
attempt log retained. All outputs sealed before new manual reference reads.
Postscore caption rerenders only fix clipped text; original figures preserved.
Eight latest QA figures actually opened. All pixels private. Old DS1/2/3 untouched.
HTTP/smoke/training/SAM3/completion/cost0, no tracker/DepthState/q/trigger changes,
no new IDF1/HOTA/AssA. Main/ref delivery follows actual REMOTE_VERIFICATION.

One next step: independently audit fish/background/anomalous surfaces and spatial
registration on sealed new-conflict/low-retention cases before background-fit or
DepthState decisions. Do not retune DS4 or automatically add VLM/tracking.

'''.encode('utf-8')
    def add_handoff(old):
        old=old.replace('# Active handoff — DS3'.encode('utf-8'),'# Historical handoff — DS3'.encode('utf-8'),1)
        return handoff+old
    change('research/HANDOFF.md',add_handoff)


if __name__=='__main__': run()
