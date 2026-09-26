"""Small contract regressions; no API calls and no GT file access."""
import json
import unittest
from pathlib import Path

import numpy as np

import postscore
import sender


def request():
    src = [dict(token=f'f006:o{i:02d}', center_norm=[.1*i,.2], bbox_norm=[0,0,.2,.2]) for i in (1,2)]
    dst = [dict(token=f'f007:o{i:02d}', center_norm=[.1*i,.2], bbox_norm=[0,0,.2,.2]) for i in (1,2)]
    core = dict(request_id='M3L-P01', source=dict(image_id='G006', observations=src),
                target=dict(image_id='G007', observations=dst))
    return dict(core_text=json.dumps(core))


def output(targets=('f007:o01','f007:o02'), statuses=('MATCH','MATCH')):
    rows=[]
    for i,(target,status) in enumerate(zip(targets,statuses),1):
        source=f'f006:o{i:02d}'
        evidence=([dict(image_id='G006', observation_token=source, observation='source shape'),
                   dict(image_id='G007', observation_token=target, observation='target shape')]
                  if status=='MATCH' else [])
        rows.append(dict(source_token=source,status=status,
                         target_token=target if status=='MATCH' else None,evidence=evidence,limitation=''))
    return dict(request_id='M3L-P01', matches=rows)


class Contract(unittest.TestCase):
    def test_match_and_unresolved(self):
        x=postscore.parse(json.dumps(output()),request())
        self.assertTrue(x['schema_valid'])
        self.assertTrue(all(r['usable'] for r in x['rows']))
        x=postscore.parse(json.dumps(output(statuses=('MATCH','UNRESOLVED'))),request())
        self.assertTrue(x['schema_valid'])
        self.assertFalse(x['rows'][1]['usable'])

    def test_missing_duplicate_source_and_json_keys(self):
        x=output(); x['matches'][1]['source_token']=x['matches'][0]['source_token']
        self.assertEqual(postscore.parse(json.dumps(x),request())['reason'],'SOURCE_MISSING_OR_DUPLICATE')
        self.assertEqual(postscore.parse('{"request_id":"M3L-P01","request_id":"M3L-P01","matches":[]}',request())['reason'],'DUPLICATE_JSON_KEY')
        self.assertEqual(postscore.parse('[]',request())['reason'],'BAD_TOP_LEVEL')

    def test_invalid_citation_and_target_conflict(self):
        x=output(); x['matches'][0]['evidence'][1]['observation_token']='f008:o01'
        parsed=postscore.parse(json.dumps(x),request())
        self.assertTrue(parsed['schema_valid'])
        self.assertFalse(parsed['rows'][0]['citation_valid'])
        x=output(); x['matches'][0]['evidence'][0]['observation']={'center_norm':[.1,.2]}
        parsed=postscore.parse(json.dumps(x),request())
        self.assertTrue(parsed['schema_valid'])
        self.assertFalse(parsed['rows'][0]['citation_valid'])
        x=postscore.parse(json.dumps(output(targets=('f007:o01','f007:o01'))),request())
        self.assertTrue(x['schema_valid'])
        self.assertEqual(x['conflict_targets'],['f007:o01'])
        self.assertFalse(any(r['usable'] for r in x['rows']))

    def test_missing_required_citation_not_silent_match(self):
        x=output(); x['matches'][0]['evidence']=x['matches'][0]['evidence'][:1]
        parsed=postscore.parse(json.dumps(x),request())
        self.assertTrue(parsed['schema_valid'])
        self.assertFalse(parsed['rows'][0]['citation_valid'])
        self.assertFalse(parsed['rows'][0]['usable'])

    def test_ambiguous_gt_never_forced(self):
        source=dict(observations=[dict(token='f006:o01',native_mask_key='n:1')])
        target=dict(observations=[dict(token='f007:o01',native_mask_key='n:2'),
                                  dict(token='f007:o02',native_mask_key='n:3')])
        a=dict(objects=[dict(native_id=1,gt_id=6,ambiguity=None)])
        b=dict(objects=[dict(native_id=2,gt_id=6,ambiguity=None),
                        dict(native_id=3,gt_id=None,ambiguity='MIXED',candidate_gt_ids=[6])])
        self.assertEqual(postscore.truth(source,target,a,b)['f006:o01']['reason'],'TARGET_NOT_UNIQUE')
        b['objects'][1]['candidate_gt_ids']=[9]
        self.assertEqual(postscore.truth(source,target,a,b)['f006:o01']['target'],'f007:o01')

    def test_baseline_uses_tokens_not_native(self):
        core=json.loads(request()['core_text'])
        src,dst=core['source']['observations'],core['target']['observations']
        one=np.zeros((4,4),bool); one[0,0]=True
        two=np.zeros((4,4),bool); two[3,3]=True
        masks_a={src[0]['token']:one,src[1]['token']:two}
        masks_b={dst[0]['token']:one,dst[1]['token']:two}
        for mode in ('N-C','N-I'):
            original=postscore.baseline(src,dst,masks_a,masks_b,mode)
            renamed=[dict(x,native_id=999-i) for i,x in enumerate(src)]
            self.assertEqual(original,postscore.baseline(renamed,dst,masks_a,masks_b,mode))

    def test_chain_stops_at_abstain(self):
        frames=[dict(frame=x) for x in (1300,1308,1315)]
        rows=[dict(attempt_id='P01-FIRST',source_token='a',decision='MATCH',raw_target='b',truth_target='b'),
              dict(attempt_id='P02-FIRST',source_token='b',decision='UNRESOLVED',raw_target=None,truth_target='c')]
        path=postscore.compose('a','FIRST',rows,frames)
        self.assertEqual(path['last_reached_frame'],1308)
        self.assertEqual(path['stop']['reason'],'UNRESOLVED')

    def test_real_pair_and_repeat_freeze(self):
        root=Path('/home/xiongxiong/m3l_local_correspondence_20260926')
        if not (root/'public/SLICE_AUDIT.json').exists():
            self.skipTest('real host slice unavailable')
        audit=postscore.read(root/'public/SLICE_AUDIT.json')
        self.assertEqual(audit['frames'],[1300,1308])
        plan=postscore.read(root/'sender/PLAN.json')
        frames=postscore.read(root/'public/SOURCE_MANIFEST.json')['frames']
        self.assertEqual(len(plan['requests']),12)
        self.assertEqual(len(plan['schedule']),24)
        uploaded={x['image_sha256']:'file-api-synthetic' for req in plan['requests'] for x in req['images']}
        for i,req in enumerate(plan['requests']):
            core=json.loads(req['core_text'])
            self.assertEqual([x['image_id'] for x in req['images']],
                             [core['source']['image_id'],core['target']['image_id']])
            self.assertEqual([x['image_id'] for x in req['images']],
                             [frames[i]['image_id'],frames[i+1]['image_id']])
            self.assertEqual({x['token'] for x in core['source']['observations']},
                             {x['token'] for x in frames[i]['observations']})
            self.assertEqual(len(req['images']),2)
            self.assertNotIn('endpoint_roles',req['core_text'])
            self.assertNotIn('native_id',req['core_text'])
            before=sender.wire(sender.body(req,uploaded))
            fake_score_key={'answer':'MUTATED'}
            fake_score_key['answer']='OTHER'
            self.assertEqual(before,sender.wire(sender.body(req,uploaded)))
        seal=root/'sender/public/REQUESTS_SEALED.json'
        if seal.exists():
            records=postscore.read(seal)['records']
            for i in range(1,13):
                a,b=[x['payload_sha256'] for x in records if x['pair']==f'P{i:02d}']
                self.assertEqual(a,b)


if __name__=='__main__':
    unittest.main()
