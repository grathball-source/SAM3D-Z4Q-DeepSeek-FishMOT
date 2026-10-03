"""Postseal audit of actual pending stores, event keys and first publication."""
from common import *
from collections import Counter
from itertools import groupby
from report import require_complete
from mixed_depth import _digest


def int_map(value):
    return {int(key):item for key,item in value.items()}


def row_digest(row):
    return hashlib.sha256((json.dumps(row,separators=(',',':'),allow_nan=False)+'\n').encode()).hexdigest()


def key_records(records):
    result={item['key']:item for item in records}
    assert len(result)==len(records)
    return result


def audit_segment(name,public,expected_frames=None):
    start,stop=SEGMENTS[name]
    public=Path(public);count=0
    transaction_frames=groupby(rows(public/'TRANSACTIONS.jsonl.gz'),key=lambda row:row['frame'])
    checks={arm:dict(frames=0,ordinary_pending_outside_write_set_exact=0,
        actual_confirmation_records=0,new_event_confirmations_started_at_one=0,
        continued_bound_event_confirmations=0,ordinary_accepted_published=0,
        ordinary_accepted_overridden_by_explicit_write=0,local_commits=0,
        invalidated_reasons=Counter(),between_frame_pending_changes=[],
        event_confirmation_keys_seen=set(),consumed_sources=[]) for arm in ISOLATED_ARMS}
    previous_pending={}
    for prediction,ledger,frame_transactions in zip(rows(public/'predictions.jsonl.gz'),
            rows(public/'PUBLISH_LEDGER.jsonl'),transaction_frames,strict=True):
        frame,transactions=frame_transactions;count+=1
        assert frame==prediction['frame']==ledger['frame']==count
        assert prediction['global_frame']==ledger['global_frame']==start+frame-1
        assert row_digest(prediction)==ledger['prediction_row_sha256']
        transaction_rows=list(transactions)
        transactions={row['arm']:row for row in transaction_rows}
        assert len(transactions)==len(transaction_rows)
        assert set(transactions)==set(ARMS[1:])
        for arm in ISOLATED_ARMS:
            transaction=transactions[arm];audit=transaction['controller_trace']['ds20_pending_isolation']
            actual={int(item['mask'][2:]):item['id'] for item in prediction['variants'][arm]}
            assert int_map(transaction['actual_published_mapping'])==actual
            baseline=int_map(transaction['ordinary_preview_mapping'])
            ordinary=int_map(audit['ordinary_pending_after'])
            assert ordinary==int_map(audit['ordinary_pending_after_proposal'])
            pending=int_map(transaction['actual_engine_pending'])
            record=transaction.get('return_record');restore=transaction.get('restore') or {}
            write_set=set(record['native_write_set']) if record else set()
            write_set.update(int(key) for key in restore.get('changes',{}))
            write_set.update((restore.get('fallback') or {}).get('event_native_write_set',[]))
            assert {key:value for key,value in pending.items() if key not in write_set}=={
                key:value for key,value in ordinary.items() if key not in write_set},(name,frame,arm,'actual ordinary pending outside write set')
            assert {key:value for key,value in actual.items() if key not in write_set}=={
                key:value for key,value in baseline.items() if key not in write_set},(name,frame,arm,'actual publication outside write set')
            stats=checks[arm];stats['frames']+=1;stats['ordinary_pending_outside_write_set_exact']+=1
            current_before=int_map(audit['ordinary_pending_before'])
            if arm in previous_pending and current_before!=previous_pending[arm]:
                stats['between_frame_pending_changes'].append(dict(frame=frame,
                    global_frame=prediction['global_frame'],signal=transaction['signal'],
                    previous_actual=previous_pending[arm],current_before=current_before,
                    meaning='ACTUAL_PREVIEW_ENTRY_CHANGE; NOT_ASSUMED_EVENT_PROPOSAL_POLLUTION'))
            previous_pending[arm]=pending
            after=key_records(audit['event_confirmations_after'])
            before=key_records(audit['event_confirmations_before'])
            loaded=set(audit['proposal_loaded_confirmations'])
            assert loaded<=before.keys()
            actual_store=key_records(transaction['actual_event_confirmation_store'])
            assert after==actual_store,(name,frame,arm,'actual event confirmation store')
            version=int_map(transaction['actual_source_versions'])
            identity_version=int_map(transaction['actual_identity_versions'])
            anchors=int_map(transaction['bank_anchors'])
            protected=transaction['actual_protected']
            for key,confirmation in actual_store.items():
                identity,progress=confirmation['identity'],confirmation['pending']
                native,target=identity['native'],identity['public']
                assert key==_digest(identity)
                assert identity['event']==transaction['active_event'] and identity['event'] in protected
                spec=protected[identity['event']]
                assert spec['episode']==identity['event'] and spec['generation']==identity['generation']
                assert target in spec['member_public'] and progress['target']==target
                assert identity['source_version']==version[native]
                assert identity['identity_version']==identity_version[native]
                assert identity['source_version'][:3]==[name,arm,native]
                assert identity['anchor']==anchors[target] and identity['anchor']['frame']<frame
                assert identity['origin_rule']=='D1_DELAYED' and progress['count']>0
                assert progress['start_time']<=progress['time']<=prediction['time']
                assert prediction['time']-progress['time']<=.2 and prediction['time']-progress['start_time']<=.5
                if key in loaded:
                    assert progress['count']==before[key]['pending']['count']+1
                    assert progress['start_time']==before[key]['pending']['start_time']
                    stats['continued_bound_event_confirmations']+=1
                else:
                    assert progress['count']==1 and progress['start_time']==prediction['time']
                    stats['new_event_confirmations_started_at_one']+=1
                assert native in actual and actual[native]==native
                assert all(source==native or public_id!=target for source,public_id in actual.items())
                assert str(native) not in transaction['actual_alias_targets']
                assert all(int(source)==native or public_id!=target for source,public_id in transaction['actual_alias_targets'].items())
                stats['event_confirmation_keys_seen'].add(key);stats['actual_confirmation_records']+=1
            ordinary_sources=set(audit['ordinary_accepted_sources'])
            accepted={event['native_id']:event for event in transaction['controller_trace'].get('events',[])
                if event.get('kind')=='reconnect' and event.get('accepted')}
            for native in ordinary_sources:
                candidates=[item for item in transaction['automatic_candidate_events'] if item['event']['native_id']==native]
                if native in write_set:
                    stats['ordinary_accepted_overridden_by_explicit_write']+=1
                    continue
                assert native in accepted and len(candidates)==1
                target=accepted[native]['canonical_id']
                assert actual[native]==target and transaction['actual_alias_targets'][str(native)]==target
                assert candidates[0]['applied_at_first_publication'] and candidates[0]['durable_alias_after_commit']
                stats['ordinary_accepted_published']+=1
                assert all(item['identity']['native']!=native for item in actual_store.values())
            if record:
                selected=int_map(record['selected'])
                consumed=set(audit['confirmation_consumed_by_commit'])
                assert consumed==set(record['restored_sources'])==set(selected)
                assert not consumed&ordinary_sources
                assert record['confirmation_policy']=='SEPARATE_EVENT_TARGET_VERSION_ANCHOR_STORE'
                assert all(native not in consumed for native in (item['identity']['native'] for item in actual_store.values()))
                assert all(actual[native]==target for native,target in selected.items())
                for action in record['original_proposal_trace_events']:
                    if action['origin_rule']!='D1_DELAYED':continue
                    prior=[before[key] for key in loaded if
                        before[key]['identity']['native']==action['native_id'] and
                        before[key]['identity']['public']==action['canonical_id'] and
                        before[key]['identity']['anchor']==action['old_anchor']]
                    assert len(prior)==1
                    assert action['confirmations']==prior[0]['pending']['count']+1
                stats['local_commits']+=1
                stats['consumed_sources'].append(dict(frame=frame,global_frame=prediction['global_frame'],selected=selected))
            stats['invalidated_reasons'].update(item['reason'] for item in audit['invalidated'])
    assert count==(stop-start+1 if expected_frames is None else expected_frames)
    for stats in checks.values():
        stats['event_confirmation_keys_seen']=sorted(stats['event_confirmation_keys_seen'])
        stats['invalidated_reasons']=dict(stats['invalidated_reasons'])
    return dict(status='PASS_ACTUAL_PENDING_VERSION_ANCHOR_AND_PUBLICATION_ISOLATION',frames=count,arms=checks)


def main():
    require_complete()
    segments={};sources=[];all_invalidated=Counter()
    for name in SEGMENTS:
        public=RUN/name/'public'
        segments[name]=audit_segment(name,public)
        for stats in segments[name]['arms'].values():
            all_invalidated.update(stats['invalidated_reasons'])
        sources.extend(artifact(public/filename) for filename in ('PREDICTIONS_SEALED.json','PUBLISH_LEDGER.jsonl','TRANSACTIONS.jsonl.gz'))
    result=dict(status='PASS_ACTUAL_PENDING_VERSION_ANCHOR_AND_PUBLICATION_ISOLATION',
        segments=segments,frames_per_arm=20098,isolated_arm_frames=40196,
        all_invalidated_reasons=dict(all_invalidated),sources=sources,
        checks='Actual engine stores vs ordinary preview, permitted local write sets, exact source/identity versions and anchor, unresolved target, original time windows, commit consumption and actual publisher',
        boundaries=['Full non-pending bank/alias transaction state uses unchanged frozen atomic validator plus state tests; not independently reconstructed from omitted stores',
            'Passing confirmation isolation is not a depth benefit or physical identity correctness result',
            'Between-frame pre-preview store changes are reported explicitly rather than silently called event proposal pollution'],
        source_scoring_precondition=artifact(RUN/'SCORE_PROVENANCE.json'),
        reference_raster_read_by_this_helper=False,model_http=0,cost_usd=0)
    write_new(HERE/'CONFIRMATION_AUDIT.json',result)
    lines=['# DS20 实际确认状态隔离核验','',result['status'],'',
        '全部八段、两个新分支，共40196分支帧；检查的是实际提交后engine字典、精确版本/anchor与实际首次发布，不以自报布尔字段代替实值。','',
        '| 片段/分支 | 帧 | 实际独立确认记录 | 普通接受并发布 | 局部提交 | 帧间入口变化 |',
        '|---|---:|---:|---:|---:|---:|']
    for name,value in segments.items():
        for arm,stats in value['arms'].items():
            lines.append(f'| {name}/{arm} | {stats["frames"]} | {stats["actual_confirmation_records"]} | {stats["ordinary_accepted_published"]} | {stats["local_commits"]} | {len(stats["between_frame_pending_changes"])} |')
    lines+=['','失效理由、全部实值来源和入口变化保存在CONFIRMATION_AUDIT.json。',
        '显式事务只允许事件写集内变化；组外pending与发布精确等于同分支普通preview。全部非pending bank/alias内部字段仍由冻结原子validator和状态测试核验，本日志不伪造未保存的完整快照。',
        '此PASS仅指确认隔离工程；物理正确性与完整性能在独立评分/结果报告分列。','']
    with (HERE/'CONFIRMATION_AUDIT.md').open('x',encoding='utf-8',newline='\n') as handle:handle.write('\n'.join(lines))
    print(result['status'], 'eight complete segments /40196 isolated frames')


if __name__=='__main__':main()
