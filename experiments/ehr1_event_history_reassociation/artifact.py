"""Inventory restricted EHR-1 files by path, bytes and hash without opening their contents."""
from __future__ import annotations

import argparse
from pathlib import Path

from prepare import put, sha


def rows(paths, category):
    return [dict(category=category, path=str(p), bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(paths) if p.is_file()]


def main(run):
    sender = run/'sender'
    private = (rows((sender/'media').glob('*'), 'private_predicted_mask_pixels') +
               rows((sender/'private').rglob('*'), 'private_provider_wire_or_file_ids') +
               rows((run/'scorer_inputs').rglob('*'), 'isolated_exposed_score_source_copy'))
    public = (rows((run/'public').glob('*'), 'public_event_evidence') +
              rows((sender/'public').rglob('*'), 'public_call_record') +
              rows([sender/'PLAN.json'], 'public_logical_plan_without_file_ids'))
    put(run/'public/ARTIFACT_MANIFEST.json', dict(status='ENGINEERING_STOP_PRESERVED',
        restricted=private, public=public,
        not_in_git=['private predicted-mask PNGs', 'provider file IDs and upload ledger',
                    'exact file-ID-bearing request bodies', 'raw API wire/reasoning', 'credentials', 'GT raster'],
        credential_file_created=False, temporary_fifo_removed=not (run/'key.pipe').exists(),
        source_media_reused_from='/home/xiongxiong/m2t_motion_first_20260924/full_run/sender/media'))
    print(dict(restricted=len(private), public=len(public)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    main(p.parse_args().run)
