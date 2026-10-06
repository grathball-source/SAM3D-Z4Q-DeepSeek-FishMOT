"""Exact source/runtime/access and all-segment prediction seals before reference reads."""
from common import *

def verify_frozen_inputs(frozen):
    name=frozen['segment'];assert name in SEGMENTS and tuple(frozen['arms'])==ARMS
    assert frozen['status']=='FROZEN_BEFORE_PREDICTION' and frozen['no_GT_before_seal']
    assert frozen['future_limit_frames']==CFG['lag_frames']==30 and not frozen['RGB_for_association']
    for path,expected in frozen['code'].items():assert sha(path)==expected,path
    for key in ('source_manifest','runtime','original_prediction','original_transactions','original_seal'):verify_item(frozen[key])
    runtime=read(frozen['runtime']['path']);verify_item(runtime['environment'])
    for pin in read(runtime['environment']['path'])['runtime_binaries']:verify_item(pin)
    source=read(frozen['source_manifest']['path'])
    assert source==frozen['source_chain'] and source['no_GT'] and source['no_restored_values']
    for pin in source['derived_inputs'].values():verify_item(pin)
    for key in ('scan','raw_sources','field_access'):verify_item(source[key])
    old.verify_cache_reference(frozen['depth_cache'])
    assert read(frozen['original_seal']['path'])['artifacts_sha256']['predictions.jsonl.gz']==frozen['original_prediction']['sha256']
    assert read(frozen['original_seal']['path'])['artifacts_sha256']['TRANSACTIONS.jsonl.gz']==frozen['original_transactions']['sha256']
    a,b=SEGMENTS[name];assert frozen['frames']==b-a+1
    return True

def verify_seal(name):
    public=RUN/name/'public';frozen=read(public/'FREEZE.json');verify_frozen_inputs(frozen)
    seal=read(public/'PREDICTIONS_SEALED.json')
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING' and tuple(seal['arms'])==ARMS
    assert seal['frames']==frozen['frames'] and 'FREEZE.json' in seal['artifacts_sha256']
    for file,expected in seal['artifacts_sha256'].items():
        p=public/file;assert p.resolve().parent==public.resolve() and sha(p)==expected,p
    return seal

def verify_all():
    seal=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert seal['status']=='ALL_PREDICTIONS_AND_ACCESS_SEALED' and seal['frames']==20098 and tuple(seal['arms'])==ARMS
    assert set(seal['seals'])==set(seal['access_seals'])==set(seal['starts'])==set(seal['ends'])==set(SEGMENTS)
    for name in SEGMENTS:
        for field in ('seals','access_seals','starts','ends'):verify_item(seal[field][name])
        verify_seal(name);assert read(seal['ends'][name]['path'])['exit_code']==0
        assert read(seal['access_seals'][name]['path'])['status']=='RAW_DEPTH_CACHE_NO_GT_RESTORED_RGB_NETWORK'
    return seal
