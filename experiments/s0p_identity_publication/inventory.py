"""Publish path/size/hash only for restricted local dependencies."""
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'experiments/ms1_s0_development_8400'
sys.path.insert(0,str(OLD))
sys.path.insert(0,str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import sha  # noqa: E402
from replay_p import OBS,PROFILES,ASSIGN,ARCHIVED,SCAN,OUT,write_new  # noqa: E402
from score import GT  # noqa: E402
from postseal_event import MATCHES  # noqa: E402


def main():
    paths=dict(observations=OBS,depth_profiles=PROFILES,assignment_masks=ASSIGN,
               archived_baseline=ARCHIVED,prediction_only_trigger_scan=SCAN,
               exposed_development_gt=GT,exposed_native_gt_matches=MATCHES,
               s0p_private_reference_snapshots=HERE/'run_8400_v2/private_source/Q_REFERENCE_SNAPSHOTS.json')
    records={name:dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha(path))
             for name,path in paths.items()}
    write_new(OUT/'RESTRICTED_INVENTORY.json',dict(status='PATH_SIZE_SHA_ONLY_NO_CONTENT',
        records=records,reproduction_dependencies=[
            'Same-SHA OBS, depth profiles, assignment masks, V4 scan, archived baseline',
            'Python 3.12 with repository controller, NumPy, SciPy, pycocotools, TrackEval',
            'GT and native-to-GT matches are needed only after prediction sealing for scoring',
            'Old HOLD public recovery seal/predictions/metrics must remain unchanged',
            'Archived attempt1 source is retained for exact first-attempt reproduction'],
        private_pixels_or_raster_in_git=False))
    print('RESTRICTED_INVENTORY',len(records))


if __name__=='__main__':
    main()
