"""Final grading boundaries; no real GT and no new predictions."""
from common import *
import ast


def main():
    path=HERE/'score.py';data=path.read_bytes();newline='\r\n' if b'\r\n' in data else '\n'
    current=data.decode('utf-8');old=current
    block="""            physical_reference=('NOT_FIRST_PUBLISHED' if not applied else 'NOT_DURABLE_AUTO_COMMIT' if not committed
                else 'CORRECT' if relations['query_vs_bank']=='SAME'
                else 'WRONG' if relations['query_vs_bank']=='DIFFERENT' else 'UNSCORABLE')
            public_reference=('PREEXISTING_PUBLIC_ORIGIN_MISMATCH' if relations['bank_vs_public_origin']=='DIFFERENT'
                else 'CONSISTENT_PUBLIC_ORIGIN' if relations['bank_vs_public_origin']=='SAME' else 'UNSCORABLE_PUBLIC_ORIGIN')
""".replace('\n',newline)
    assert old.count(block)==1;old=old.replace(block,'')
    addition="""                physical=physical, physical_definition='CONSERVATIVE_JOINT_ACTUAL_BANK_AND_PUBLIC_ORIGIN',
                actual_reference_physical=physical_reference, prior_public_reference_status=public_reference,
                incidental_public_origin_return=(relations['query_vs_public_origin']=='SAME' and relations['query_vs_bank']=='DIFFERENT'),
                relations=relations, query_match=current, bank_match=past,
""".replace('\n',newline)
    original="                physical=physical, relations=relations, query_match=current, bank_match=past,"+newline
    assert old.count(addition)==1;old=old.replace(addition,original)
    old_sha=hashlib.sha256(old.encode('utf-8')).hexdigest()
    assert old_sha==read(HERE/'REAL_SLICE_SOURCE_SCORER.json')['actual_scoring_code_sha256']
    a,b=ast.parse(current),ast.parse(old)
    signatures={}
    for name in ('verify_automatic_sources','verify_order_sources','order_records','row_sha'):
        left=next(n for n in a.body if isinstance(n,ast.FunctionDef) and n.name==name)
        right=next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name==name)
        left,right=ast.dump(left,include_attributes=False),ast.dump(right,include_attributes=False)
        assert left==right
        signatures[name]=hashlib.sha256(left.encode()).hexdigest()
    audit=next(n for n in a.body if isinstance(n,ast.FunctionDef) and n.name=='physical_audit')
    wanted=('physical','physical_reference','public_reference');assignments={}
    for n in ast.walk(audit):
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in wanted:
            assignments.setdefault(n.targets[0].id,n)
    program=ast.fix_missing_locations(ast.Module(body=[assignments[k] for k in wanted],type_ignores=[]))
    cases=[]
    for relations,expected in [
        (dict(query_vs_bank='SAME',bank_vs_public_origin='DIFFERENT',query_vs_public_origin='DIFFERENT'),('WRONG','CORRECT','PREEXISTING_PUBLIC_ORIGIN_MISMATCH')),
        (dict(query_vs_bank='DIFFERENT',bank_vs_public_origin='DIFFERENT',query_vs_public_origin='SAME'),('WRONG','WRONG','PREEXISTING_PUBLIC_ORIGIN_MISMATCH')),
        (dict(query_vs_bank='UNKNOWN',bank_vs_public_origin='UNKNOWN',query_vs_public_origin='UNKNOWN'),('UNSCORABLE','UNSCORABLE','UNSCORABLE_PUBLIC_ORIGIN'))]:
        scope=dict(relations=relations,applied=True,committed=True)
        exec(compile(program,str(path),'exec'),scope)
        actual=tuple(scope[k] for k in wanted);assert actual==expected
        cases.append(dict(relations=relations,actual=dict(zip(wanted,actual))))
    write_new(HERE/'SCORER_CONTRACT_FINAL_CHECKS.json',dict(status='PASS',cases=cases,
        current_score_sha256=sha(path),source_verifier_AST_unchanged=signatures,
        source_proof_completion_disk_sha256=old_sha,GT_real_data_read=False,
        note='Prefix source verification was unchanged while unused GT grading fields were finalized before formal freeze. The source proof SHA is its completion disk snapshot; it is not an attestation of all unused loaded grading code. Formal scoring uses the whole current frozen module.',model_http=0,cost_usd=0))
    print('Final scorer contract PASS: actual-bank/public-origin/UNKNOWN separated; source functions unchanged')

if __name__=='__main__':main()
