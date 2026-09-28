"""Causal, mask-based merge opportunity scan on the exposed prediction stream."""
import gzip
import json
import math
from collections import Counter, deque
from pathlib import Path

from mask_geometry import mask, shifted_coverage

HERE = Path(__file__).resolve().parent
ASSIGN = HERE / 'private_source/assignments.jsonl.gz'
OBS = Path('E:/CAU/D-MOT/tools/sam3_depth_failure_repair_20260917/diagnosis_evidence/diagnosis/observations_validation.jsonl.gz')


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        yield from map(json.loads, handle)


def center(o):
    a, b, c, d = o['box']
    return ((a + c) / 2, (b + d) / 2)


def scan():
    previous = None
    histories = {}
    counts = Counter()
    suspects = []
    transitions = []
    diagnostics = []
    for row, assignment in zip(rows(OBS), rows(ASSIGN), strict=True):
        frame, now = row['frame'], row['time']
        assert assignment['frame'] == frame and assignment['global_frame_id'] == row['global_frame']
        current = {o['id']: o for o in row['observations'] if o['area'] >= 64
                   and (o.get('presence') is None or o['presence'] >= .5)}
        current_masks = {int(k.split(':')[1]): mask(v) for k, v in assignment['masks'].items() if int(k.split(':')[1]) in current}
        counts[len(current)] += 1
        if previous is not None:
            prior, prior_masks, before = previous
            if len(prior) != len(current):
                transitions.append((frame, len(prior), len(current)))
            if any(o.get('neighbors') and any(n in current for n in o['neighbors'])
                   for o in current.values()):
                counts['CONTACT_ONLY_OR_RISK_FRAME'] += 1
            # Compute the compatibility graph from the prior independent sources.
            edges = {}
            for n, o in prior.items():
                if n not in prior_masks:
                    continue
                hist = list(histories.get(n, ()))
                if len(hist) >= 3 and hist[-1][0] == before:
                    left = hist[-min(10, len(hist)):]
                    t0, x0, y0 = left[0]
                    t1, x1, y1 = left[-1]
                    velocity = ((x1-x0)/(t1-t0), (y1-y0)/(t1-t0)) if t1>t0 else (0.,0.)
                    uncertainty = 1.
                else:
                    velocity = (0.,0.)
                    uncertainty = 2.
                dt = now - before
                dx, dy = velocity[0]*dt, velocity[1]*dt
                a,b,c,d = o['box']
                tolerance = max(3., .25 * math.hypot(c-a,d-b)) + 2*uncertainty
                cx,cy = center(o)
                plausible = []
                for m, p in current.items():
                    px,py = center(p)
                    pa,pb,pc,pd = p['box']
                    if abs(cx+dx-px) > tolerance+(pc-pa)/2 or abs(cy+dy-py) > tolerance+(pd-pb)/2:
                        continue
                    overlap = shifted_coverage(prior_masks[n], current_masks[m], dx, dy, tolerance)
                    if overlap > .15:
                        plausible.append((m, round(overlap, 3)))
                edges[n] = plausible
            incoming = {}
            for n, candidates in edges.items():
                for m, coverage in candidates:
                    incoming.setdefault(m, []).append((n, coverage))
            found = False
            if any(len(sources)>2 for sources in incoming.values()):
                counts['THIRD_MEMBER_GRAPH'] += 1
            for m, sources in incoming.items():
                if len(sources) != 2:
                    continue
                a,b = sorted(n for n,_ in sources)
                if any(len(edges[n]) != 1 for n in (a,b)):
                    continue
                if len([k for k,v in edges.items() if any(j==m for j,_ in v)]) != 2:
                    continue
                prior_iou = float((prior_masks[a]&prior_masks[b]).sum() /
                                  max(1,(prior_masks[a]|prior_masks[b]).sum()))
                if prior_iou >= .25:
                    counts['DUPLICATE_OVERLAP_CANDIDATE'] += 1
                    continue
                suspects.append(dict(frame=frame, time=now, sources=[a,b], group=m,
                                     coverage={str(n):v for n,v in sources},
                                     previous_count=len(prior), current_count=len(current),
                                     prior_mask_iou=prior_iou))
                found = True
            if len(prior)>len(current) and not found:
                counts['LOST_OR_OUT_OF_SCOPE_TRANSITION'] += 1
                diagnostics.append(dict(frame=frame,kind='LOST_OR_OUT_OF_SCOPE',
                    previous_count=len(prior),current_count=len(current),
                    max_incoming=max(map(len,incoming.values()),default=0)))
        new_histories = {}
        for n,o in current.items():
            old = histories.get(n, deque(maxlen=30))
            if n not in (previous[0] if previous else {}) or o.get('neighbors'):
                old = deque(maxlen=30)
            x,y = center(o)
            old.append((now,x,y))
            new_histories[n] = old
        histories = new_histories
        previous = (current,current_masks,now)
        if frame%500==0:
            print('frame',frame,'suspects',len(suspects),flush=True)
    result = dict(counts=dict(counts), transitions=transitions, suspects=suspects,
                  diagnostics=diagnostics)
    target = HERE/'private_source/scan.json'
    target.write_text(json.dumps(result, indent=2)+'\n')
    print('TRANSITIONS',len(transitions),'SUSPECTS',len(suspects))
    print('FIRST',suspects[:25])


if __name__ == '__main__':
    scan()
