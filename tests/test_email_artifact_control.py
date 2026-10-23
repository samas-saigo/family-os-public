"""New frozen fixtures only; real inherited transport with in-process HTTP mocks."""
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
from types import SimpleNamespace

import pytest
from experiments import email_artifact_control as d

CONFIG, BASELINE, CORPORA = d.setup()
BY_INPUT = {d.wording.canonical(c['input']):c for cs in CORPORA.values() for c in cs}
EXECUTION = dict(commit='a'*40,tree='b'*40,kind='offline_mock')


class MockTransport(d.Transport):
    """Explicit offline override; production request now always checks live authority."""
    def request(self,method,path,value=None):
        return d.clone(d.compat.old.Transport.request,parent=d.reply_boundary(self.model['tag']))(self,method,path,value)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*a,**k): pytest.fail('Real network or old selector forbidden')
    monkeypatch.setattr(socket,'create_connection',deny)
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.setattr(d.wording,'load',deny)
    monkeypatch.setattr(d.prior,'setup',deny)
    monkeypatch.setattr(d.parent,'setup',deny)


def envelope(tag, value):
    return dict(model=tag,done=True,done_reason='stop',message=dict(role='assistant',content=json.dumps(value)),
                prompt_eval_count=800,eval_count=80,load_duration=1000,total_duration=10000)


class HTTP:
    def __init__(self,monkeypatch,responder=None):
        self.calls=[]; self.responder=responder
        monkeypatch.setattr(d.parent.http.client,'HTTPConnection',self.connect)

    def connect(self,host,port,timeout):
        assert (host,port)==('127.0.0.1',11434) and 0<timeout<=5
        outer=self
        class Wire:
            def settimeout(self,v): assert 0<v<=60
            def close(self): pass
        class Response:
            status=200
            def __init__(self,v): self.raw=io.BytesIO(json.dumps(v).encode())
            def getheaders(self): return [('Content-Type','application/json')]
            def getheader(self,k,default=None): return 'application/json' if k=='Content-Type' else default
            def read1(self,n): return self.raw.read(n)
            def close(self): self.raw.close()
        class Connection:
            sock=Wire()
            def connect(self): pass
            def request(self,method,path,body,headers):
                data=json.loads(body) if body else None
                outer.calls.append((method,path,data))
                if path=='/api/chat':
                    case=BY_INPUT[data['messages'][1]['content']]
                    value=envelope(data['model'],d.signature_wire(case['gold']))
                elif path=='/api/show':
                    m=next(m for m in CONFIG['models'].values() if m['tag']==data['model'])
                    value=dict(details=dict(format='gguf',family=m['family'],quantization_level='Q4_K_M',parameter_size='4.2B' if m['family']=='qwen35' else '8.2B'),
                               model_info={'general.architecture':m['family']},capabilities=['completion','thinking'])
                else:
                    value={'/api/version':dict(version='0.40.6'),'/api/tags':dict(models=[dict(name=m['tag'],model=m['tag'],digest=m['digest']) for m in CONFIG['models'].values()]),'/api/ps':dict(models=[])}[path]
                self.value=outer.responder(method,path,data,deepcopy(value)) if outer.responder else value
            def getresponse(self): return Response(self.value)
            def close(self): self.sock.close()
        return Connection()


def run(mode='full',arm='A'):
    return d.run(mode,arm,client_factory=MockTransport,execution=EXECUTION)


def test_exact_input_freeze_gold_and_plan_quotas():
    assert d.FREEZE=='29ad25c947827c115a6e8d3ef72315186556deb7'
    assert sha256((d.ROOT/d.CONFIG).read_bytes()).hexdigest()==d.CONFIG_SHA
    for mode,cs in CORPORA.items():
        assert d.validate_cases(deepcopy(cs),mode)==cs
        raw=(d.ROOT/'fixtures/email-model-artifact-control-v1'/CONFIG['fixtures'][mode]['file']).read_bytes()
        assert sha256(raw).hexdigest()==CONFIG['fixtures'][mode]['sha256'] and b'\r' not in raw
        assert json.loads(raw)['status'].startswith('DRAFT')
    assert CONFIG['order']==['A','B'] and int(CONFIG['fixtures']['full']['sha256'][0],16)%2==0
    assert CONFIG['thresholds']==dict(clear_full_min=12,net_full_min=4,ambiguous_abstain_min=7,ambiguous_overreach_max=1,missed_outstanding_max=2,missed_date_max=2)
    for mutation in ('id','group','variant','gold','input','date','quota'):
        cs=deepcopy(CORPORA['full'])
        if mutation in ('id','group','variant'): cs[0][mutation]='private_value'
        elif mutation=='gold': cs[0]['gold']['extra']='private_value'
        elif mutation=='input': cs[0]['input']['gold']=cs[0]['gold']
        elif mutation=='date': cs[0]['gold']['dates'][0][1]='2027-02-30'
        else: cs[0]['gold']['dates']=[]
        with pytest.raises((d.Error,d.engine.EmailEvidenceError,ValueError,TypeError)): d.validate_cases(cs,'full')


@pytest.mark.parametrize('mode,n',[('smoke',2),('full',24)])
def test_actual_requests_only_model_changes_and_no_hidden_fields(monkeypatch,mode,n):
    before={m:dict(vars(m)) for m in (d.parent,d.compat,d.compat.old,d.diagnostic)}
    http=HTTP(monkeypatch)
    a=run(mode,'A'); b=run(mode,'B')
    assert a['run_status']==b['run_status']=='complete'
    assert a['model_metrics']['selected']==b['model_metrics']['selected']==n
    sent=[v for _,p,v in http.calls if p=='/api/chat']
    assert len(sent)==2*n
    for va,vb,c in zip(sent[:n],sent[n:],CORPORA[mode],strict=True):
        assert va!=vb and dict(va,model=vb['model'])==vb
        assert set(va)=={'model','messages','format','stream','think','options'}
        assert va['format']==BASELINE['output_schema'] and va['options']==BASELINE['generation']['options']
        assert va['stream'] is False and va['think'] is False
        assert va['messages']==[dict(role='system',content=BASELINE['prompt']),dict(role='user',content=d.wording.canonical(c['input']))]
        assert set(json.loads(va['messages'][1]['content']))==set(c['input'])
        assert len(d.wording.canonical(va).encode())<=16384
        assert len(BASELINE['prompt'].encode())+len(va['messages'][1]['content'].encode())+1024+512<=4096
    for m,old in before.items(): assert all(vars(m)[k] is v for k,v in old.items())
    assert all(p in ('/api/chat','/api/show','/api/version','/api/tags','/api/ps') for _,p,_ in http.calls)
    assert d.validate_report(a)==a and d.validate_report(b)==b
    assert a['cases'][0]['telemetry']['eval_duration'] is None
    assert a['cases'][0]['telemetry_validation']['eval_duration']=='absent'
    assert a['cases'][0]['telemetry']['load_duration']==1000


def test_original_parser_validator_differential_and_finite_reasons():
    projection=d.engine.EmailMetadata(CORPORA['full'][0]['input'])
    values=[dict(state='abstain',steps=[],dates=[]),{},dict(state='abstain',steps=[],dates=[],private_name='private_value'),
            dict(state='explicit_outstanding',steps=[],dates=[]),
            dict(state='informational',steps=[],dates=[dict(role='due_date',value='2027-01-15',action='invoice_payment')])]
    for v in values:
        for arm in ('A','B'):
            tag=CONFIG['models'][arm]['tag']; response=envelope(tag,v)
            new=d.response_result(response,projection,BASELINE['limits'],tag)
            old=d.compat.response_result(dict(response,model=CONFIG['models']['A']['tag']),projection,BASELINE['limits'])
            assert {k:v for k,v in new.items() if k!='structure_reason'}==old
            assert new['structure_reason'] in d.diagnostic.REASONS
            if new['status']!='valid': assert new['prediction'] is None


@pytest.mark.parametrize('fault',['reply_identity','metadata_identity','metadata_exception','interrupt_identity','timeout','truncated','thinking','exception','invalid','refused'])
def test_failures_partial_denominators_permanent_taint_privacy(monkeypatch,fault):
    version_count=0
    def answer(m,p,v,r):
        nonlocal version_count
        if p=='/api/version':
            version_count+=1
            if version_count==2:
                if fault=='metadata_identity': return dict(version='0.40.5')
                if fault=='metadata_exception': raise RuntimeError('private_value')
                if fault=='interrupt_identity': raise KeyboardInterrupt()
        if p=='/api/chat':
            if fault=='reply_identity': r['model']='private_model'
            if fault=='timeout': raise TimeoutError('private_value')
            if fault=='exception': raise RuntimeError('private_value')
            if fault=='truncated': r['done_reason']='length'
            if fault=='thinking': r['message']['thinking']='private_thinking'
            if fault=='invalid': r['message']['content']='{"private_name":"private_value"}'
            if fault=='refused': r['message']['content']=''
        return r
    http=HTTP(monkeypatch,answer); r=run()
    assert r['selected']==24 and len(r['cases'])==24
    assert r['attempted']<=24 and r['unobserved_predictions']==24
    if fault in ('reply_identity','metadata_identity','metadata_exception','interrupt_identity'):
        assert r['identity_tainted'] and not r['identity_verified_at_end']
        assert r['model_metrics'] is None and r['by_group'] is None
    else:
        assert r['model_metrics']['selected']==24 and r['model_metrics']['ambiguous_abstain']==0
        assert r['model_metrics']['missed_date_cases']==8
        if fault not in ('invalid','refused'):
            assert r['run_status']=='partial' and sum(p=='/api/chat' for _,p,_ in http.calls)==1
    assert all(row['actual'] is None for row in r['cases'])
    text=d.encoded(d.validate_report(r)).decode()
    assert 'private_' not in text and BASELINE['prompt'] not in text
    assert all(c['input']['subject'] not in text for c in CORPORA['full'])


def test_smoke_invalid_stops_immediately_and_full_is_separate(monkeypatch):
    def invalid(m,p,v,r):
        if p=='/api/chat': r['message']['content']='{}'
        return r
    http=HTTP(monkeypatch,invalid); r=run('smoke')
    assert r['run_status']=='partial' and r['attempted']==1
    assert sum(p=='/api/chat' for _,p,_ in http.calls)==1
    assert d.compare(r,r)['decision']=='not_evaluable'
    with pytest.raises(d.Error): d.prerequisites('smoke','B',[r],EXECUTION)


def test_single_request_counter_consumed_even_on_connect_failure(monkeypatch):
    client=MockTransport(CONFIG,BASELINE,CORPORA['smoke'][0],'A',d.time.monotonic()+120)
    payload=client.payload(d.engine.EmailMetadata(CORPORA['smoke'][0]['input']))
    connections=[]
    def failed(*a,**k): connections.append(1);raise OSError('private_error')
    monkeypatch.setattr(d.parent.http.client,'HTTPConnection',failed)
    with pytest.raises(d.Error): client.request('POST','/api/chat',payload)
    with pytest.raises(d.Error): client.request('POST','/api/chat',payload)
    assert len(connections)==1 and client.chat_attempts==1


@pytest.fixture
def publication_root(tmp_path,monkeypatch):
    original=d.ROOT
    paths=set(CONFIG['source_pins']) | {d.CONFIG.as_posix()}
    paths |= {'fixtures/email-model-artifact-control-v1/'+p['file'] for p in CONFIG['fixtures'].values()}
    for relative in paths:
        dst=tmp_path/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original/relative,dst)
    monkeypatch.setattr(d,'ROOT',tmp_path)
    return tmp_path


def test_four_stages_claims_atomic_save_recover_and_cross_namespace(monkeypatch,publication_root):
    HTTP(monkeypatch)
    refs=[]
    for mode,arm in d.STAGES:
        result=d.collect(mode,arm,previous=refs,execution=EXECUTION,client_factory=MockTransport)
        assert result['workflow_exit_code']==0 and result['report_read_verified']
        path=publication_root/result['report_path']; assert path.exists() and not path.with_suffix('.json.tmp').exists()
        run_id=path.parent.name; digest=result['report_sha256']
        before=path.read_bytes(); assert d.read_report(run_id,digest)==result['report']
        assert path.read_bytes()==before
        refs.append((run_id,digest))
    repeated=d.collect('smoke','A',execution=EXECUTION,client_factory=MockTransport)
    assert repeated['workflow_exit_code']==1
    with pytest.raises(d.Error): d.read_report(refs[0][0],'0'*64)
    with pytest.raises(d.Error): d.read_report('../old-run',refs[0][1])
    bad=deepcopy(result['report']);bad['experiment']='old-private-experiment'
    with pytest.raises(d.Error): d.save(bad)
    bad=deepcopy(result['report']);bad['cases'][0]['private_key']='private_value'
    with pytest.raises(d.Error): d.save(bad)
    assert len(list((publication_root/d.LOCAL/'claims').iterdir()))==4


def test_publication_failure_retains_memory_no_retry(monkeypatch,publication_root):
    http=HTTP(monkeypatch)
    def failed(*a,**k): raise OSError('private_error')
    monkeypatch.setattr(d.prior.os,'replace',failed)
    result=d.collect('smoke','A',execution=EXECUTION,client_factory=MockTransport)
    assert result['workflow_exit_code']==1 and result['report']['run_status']=='complete'
    assert result['error_code']=='stage_or_publication_failed' and not result['report_read_verified']
    assert sum(p=='/api/chat' for _,p,_ in http.calls)==2
    assert not list((publication_root/d.LOCAL).glob('*/report.json*'))
    assert (publication_root/d.LOCAL/'claims/smoke-A').exists()


def test_cli_real_modes_block_without_any_queries(monkeypatch,capsys):
    def deny(*a,**k): pytest.fail('No transport in unfrozen CLI or recover')
    monkeypatch.setattr(d,'Transport',deny)
    assert d.main(['smoke'])==1 and 'execution_not_frozen_or_authorized' in capsys.readouterr().out
    assert d.main(['full'])==1 and 'execution_not_frozen_or_authorized' in capsys.readouterr().out
    assert d.main(['check'])==0 and 'real_execution_authorized' in capsys.readouterr().out
    assert d.main(['recover','0'*32,'a'*64])==1


def recompute(report):
    rows=report['cases'];cases=CORPORA['full']
    report['model_metrics']=d.scored(rows,cases)
    report['by_group']={g:d.scored([r for r,c in zip(rows,cases) if c['group']==g],[c for c in cases if c['group']==g]) for g in sorted({c['group'] for c in cases})}
    report['unobserved_predictions']=sum(r['status']!='valid' for r in rows)
    return report


def test_joint_threshold_boundaries_unknown_and_A_harm_not_B_constraint(monkeypatch):
    HTTP(monkeypatch); a=run(arm='A');b=run(arm='B')
    assert d.compare(a,b)['decision']=='stop_candidate'  # no net gain at ceiling
    # Lose exactly four full cases on A, without adding any B harm.
    for i in (0,6,9,12): a['cases'][i]['actual']=dict(state='abstain',steps=[],dates=[])
    recompute(a)
    r=d.compare(a,b)
    assert r['decision']=='provisional_signal' and r['paired']['W']==4 and r['paired']['L']==0
    # Five harmful conditions apply to B only; A's full metrics remain visible.
    a['cases'][2]['actual']=dict(state='explicit_completion',steps=[['return_form','reported_completed']],dates=[])
    recompute(a)
    assert a['model_metrics']['unsupported_step_cases']>0 and d.compare(a,b)['decision']=='provisional_signal'
    for key in CONFIG['harm_counters']:
        bad=deepcopy(b);bad['model_metrics'][key]=None
        assert d.compare(a,bad)['decision']=='not_evaluable'
    bad=deepcopy(b);bad['cases'][2]['actual']=dict(state='explicit_completion',steps=[['return_form','reported_completed']],dates=[]);recompute(bad)
    assert d.compare(a,bad)['decision']=='stop_candidate'
    bad=deepcopy(b);bad['cases'][0]['actual']['dates'][0][1]='2034-01-01';recompute(bad)
    assert d.compare(a,bad)['checks']['invented_date_cases'] is False
    bad=deepcopy(b);bad['execution']['kind']='reviewed_manual'
    assert d.compare(a,bad)['decision']=='not_evaluable'


def test_joint_exact_absolute_and_net_boundaries(monkeypatch):
    HTTP(monkeypatch); a=run(arm='A'); b=run(arm='B')
    empty=dict(state='abstain',steps=[],dates=[])
    for i in (0,1,3,6,9,12,13,15): a['cases'][i]['actual']=deepcopy(empty)
    for i in (0,7,12,19): b['cases'][i]['actual']=deepcopy(empty)
    for r in (a,b):
        r['cases'][2]['actual']=dict(state='informational',steps=[],dates=[])
        recompute(r)
    result=d.compare(a,b)
    assert result['decision']=='provisional_signal' and all(result['checks'].values())
    assert b['model_metrics']['clear_outcomes']['full']==12
    assert b['model_metrics']['ambiguous_abstain']==7 and b['model_metrics']['ambiguous_overreach']==1
    assert b['model_metrics']['missed_outstanding_cases']==2 and b['model_metrics']['missed_date_cases']==2
    assert result['paired']['W']-result['paired']['L']==4
    bad=deepcopy(b);bad['cases'][22]['actual']=deepcopy(empty);recompute(bad)
    assert d.compare(a,bad)['checks']['clear_full'] is False
    better_a=deepcopy(a);better_a['cases'][1]['actual']=deepcopy(CORPORA['full'][1]['gold']);recompute(better_a)
    assert d.compare(better_a,b)['checks']['net_full'] is False
    bad=deepcopy(b);bad['cases'][8]['actual']=dict(state='informational',steps=[],dates=[]);recompute(bad)
    assert not d.compare(a,bad)['checks']['ambiguous_abstain'] and not d.compare(a,bad)['checks']['ambiguous_overreach']
    bad=deepcopy(b);bad['cases'][6]['actual']=deepcopy(empty);recompute(bad)
    assert d.compare(a,bad)['checks']['missed_outstanding'] is False
    bad=deepcopy(b);bad['cases'][10]['actual']['dates']=[];recompute(bad)
    assert d.compare(a,bad)['checks']['missed_date'] is False
    for total,chat in ((600.001,1),(1,60.001)):
        bad=deepcopy(b);bad['total_elapsed_seconds']=total;bad['cases'][0]['chat_response_seconds']=chat
        assert d.compare(a,bad)['decision']=='not_evaluable'


def test_final_residency_identity_failure_latches_taint(monkeypatch):
    count=0
    def resident(m,p,v,r):
        nonlocal count
        if p=='/api/ps':
            count+=1
            if count==2: return dict(models=[dict(name=CONFIG['models']['A']['tag'],digest='0'*64)])
        return r
    HTTP(monkeypatch,resident);r=run('smoke')
    assert r['identity_tainted'] and r['model_metrics'] is None and not r['identity_verified_at_end']
    assert r['prediction_attribution']=='unattributed_diagnostic'
    d.validate_report(r)


def test_fixture_hash_failure_and_readonly_recover_no_network(monkeypatch,publication_root,capsys):
    HTTP(monkeypatch)
    r=d.collect('smoke','A',execution=EXECUTION,client_factory=MockTransport)
    run_id=Path(r['report_path']).parent.name
    def deny(*a,**k): pytest.fail('Recovery cannot construct/query a transport')
    monkeypatch.setattr(d,'Transport',deny)
    assert d.main(['recover',run_id,r['report_sha256']])==0
    assert 'report' in json.loads(capsys.readouterr().out)
    fixture=publication_root/'fixtures/email-model-artifact-control-v1'/CONFIG['fixtures']['full']['file']
    fixture.write_bytes(fixture.read_bytes()+b' ')
    with pytest.raises(d.Error): d.setup()


def test_metadata_missing_alias_and_wrong_quantization_block_before_chat(monkeypatch):
    for fault in ('alias','quantization','capability'):
        def answer(m,p,v,r):
            if p=='/api/tags' and fault=='alias':
                for item in r['models']:
                    if item['name']==CONFIG['models']['B']['tag']: item.update(name='qwen3:8b',model='qwen3:8b')
            if p=='/api/show' and fault=='quantization': r['details']['quantization_level']='Q8_0'
            if p=='/api/show' and fault=='capability': r['capabilities']=['completion']
            return r
        http=HTTP(monkeypatch,answer);r=run('smoke','B')
        assert r['attempted']==0 and r['identity_tainted']
        assert not any(p=='/api/chat' for _,p,_ in http.calls)


def test_total_deadline_blocks_connect_and_nonfinite_report_values(monkeypatch):
    http=HTTP(monkeypatch)
    client=MockTransport(CONFIG,BASELINE,CORPORA['smoke'][0],'A',d.time.monotonic()-1)
    with pytest.raises(d.Error): client.request('GET','/api/version')
    assert http.calls==[]
    report=run('smoke')
    for value in (float('nan'),float('inf'),-1):
        bad=deepcopy(report);bad['total_elapsed_seconds']=value
        with pytest.raises(d.Error): d.validate_report(bad)


@pytest.mark.parametrize('counter',CONFIG['harm_counters'])
def test_each_B_harm_counter_is_an_independent_zero_requirement(monkeypatch,counter):
    HTTP(monkeypatch);a=run(arm='A');b=run(arm='B')
    for i in (0,6,9,12): a['cases'][i]['actual']=dict(state='abstain',steps=[],dates=[])
    recompute(a)
    if counter in ('unsupported_step_cases','unsupported_completion_cases'):
        b['cases'][2]['actual']=dict(state='explicit_completion',steps=[['return_form','reported_completed']],dates=[])
    elif counter=='invented_date_cases': b['cases'][0]['actual']['dates'][0][1]='2034-01-01'
    elif counter=='misbound_date_cases': b['cases'][15]['actual']['dates'][0][2]='return_form'
    else: b['cases'][0]['actual']=dict(state='informational',steps=[],dates=[])
    recompute(b);result=d.compare(a,b)
    assert result['checks'][counter] is False and result['decision']=='stop_candidate'


def test_default_real_collect_is_blocked_before_claim_or_transport(monkeypatch):
    def deny(*a,**k): pytest.fail('Real path not authorized in this PR')
    monkeypatch.setattr(d,'Transport',deny);monkeypatch.setattr(d,'claim_stage',deny)
    r=d.collect('smoke','A',execution=dict(EXECUTION,kind='reviewed_manual'))
    assert r['workflow_exit_code']==1 and r['report'] is None


@pytest.mark.parametrize('fault',['none','commit','tree','dirty','ancestry','python','platform'])
def test_future_execution_identity_gate_with_mock_git_only(monkeypatch,fault):
    monkeypatch.setattr(d.sys,'platform','linux' if fault=='platform' else 'win32')
    monkeypatch.setattr(d.sys,'version_info',(3,12,0) if fault=='python' else (3,12,10))
    execution=dict(EXECUTION,kind='reviewed_manual');calls=[]
    def git(args,**kwargs):
        calls.append(args)
        if args[1:]==['rev-parse','HEAD']: value=('0'*40 if fault=='commit' else execution['commit'])
        elif args[1:]==['rev-parse','HEAD^{tree}']: value=('0'*40 if fault=='tree' else execution['tree'])
        elif args[1]=='status': value=' M unapproved.py' if fault=='dirty' else ''
        else:
            if fault=='ancestry': raise subprocess.CalledProcessError(1,args)
            value=''
        return SimpleNamespace(stdout=value.encode())
    monkeypatch.setattr(d.subprocess,'run',git)
    if fault=='none': d.execution_gate(execution)
    else:
        with pytest.raises((d.Error,subprocess.CalledProcessError)): d.execution_gate(execution)
    assert all(x[0]=='git' for x in calls)


def test_missing_stage_prerequisite_is_zero_requests(monkeypatch,publication_root):
    http=HTTP(monkeypatch)
    for mode,arm in (('smoke','B'),('full','A'),('full','B')):
        result=d.collect(mode,arm,execution=EXECUTION,client_factory=MockTransport)
        assert result['workflow_exit_code']==1 and result['report'] is None
    assert http.calls==[] and not (publication_root/d.LOCAL/'claims').exists()
