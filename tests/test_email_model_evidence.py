"""Only mocked HTTP for the fixed wording experiment. Never real model inference."""
import builtins
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import runpy
import socket
import sys

import pytest

from experiments import email_model_evidence as run
from experiments import email_wording_challenge as wording
from family_os import _synthetic_email_evidence as e

CONFIG, CASES = run.setup()
BY_INPUT = {wording.canonical(c['input']):c for c in CASES}
ABSTAIN = dict(state='abstain',steps=[],dates=[])


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def denied(*args,**kw):pytest.fail('Real socket/model access forbidden')
    monkeypatch.setattr(socket,'create_connection',denied)
    monkeypatch.setattr(socket.socket,'connect',denied)


def output(ref):
    return dict(state=ref['state'],steps=[dict(action=a,status=s) for a,s in ref['steps']],
                dates=[dict(role=r,value=v,action=a) for r,v,a in ref['dates']])


def envelope(value=ABSTAIN):
    return dict(model=CONFIG['model']['tag'],done=True,done_reason='stop',
                message=dict(role='assistant',content=json.dumps(value)),
                prompt_eval_count=500,eval_count=80,total_duration=1_000_000,eval_duration=500_000)


class MockHTTP:
    """HTTPConnection boundary mock; exercises real transport parsing and CLI."""
    def __init__(self, responder=None):
        self.calls=[];self.responses=[];self.responder=responder

    def __call__(self, host, port, timeout):
        assert (host,port)==('127.0.0.1',11434) and 0<timeout<=5
        outer=self
        class Wire:
            def settimeout(self,value):assert 0<value<=60
            def close(self):pass
        class Response:
            status=200
            def __init__(self,value):
                self.raw=io.BytesIO(json.dumps(value).encode());self.headers={'Content-Type':'application/json'}
            def getheaders(self):return list(self.headers.items())
            def getheader(self,key,default=None):return self.headers.get(key,default)
            def read1(self,n):return self.raw.read(n)
            def close(self):self.raw.close()
        class Connection:
            sock=Wire()
            def connect(self):pass
            def request(self,method,path,body,headers):
                data=json.loads(body) if body else None
                outer.calls.append((method,path,data,headers))
                self.value=outer.answer(method,path,data)
            def getresponse(self):
                response=Response(self.value);outer.responses.append(response);return response
            def close(self):self.sock.close()
        return Connection()

    def answer(self,method,path,data):
        default={
            '/api/version':{'version':'0.40.6'},
            '/api/tags':{'models':[dict(name=CONFIG['model']['tag'],model=CONFIG['model']['tag'],digest=CONFIG['model']['digest'])]},
            '/api/show':{'details':{k:CONFIG['model'][k] for k in ('family','parameter_size','quantization_level')},'model_info':{'general.architecture':'qwen35'},'capabilities':['completion','thinking']},
            '/api/ps':{'models':[]},
        }.get(path)
        if path=='/api/chat':default=envelope()
        return self.responder(method,path,data,deepcopy(default)) if self.responder else deepcopy(default)


def mocked(monkeypatch,responder=None):
    http=MockHTTP(responder);monkeypatch.setattr(run.http.client,'HTTPConnection',http);return http


def test_frozen_configuration_inputs_and_original_results():
    assert run.FREEZE=='ffe329ce55bd7a148d0b849503299cdd818e138a'
    assert sha256((run.ROOT/run.CONFIG).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==run.CONFIG_SHA
    assert CONFIG['generation']==dict(stream=False,think=False,options=dict(temperature=0,seed=0,num_ctx=4096,num_predict=512))
    assert CONFIG['smoke']==['WC01-1','WC02-1','WC03-1','WC10-1','WC11-1','WC10-3']
    assert len(CASES)==36
    m=wording.report()['metrics']
    assert (m['clear_outcomes']['full'],m['clear_outcomes']['partial'],m['clear_outcomes']['abstain'])==(0,0,24)
    assert m['missed_outstanding_cases']==12 and m['missed_date_cases']==16


@pytest.mark.parametrize('mode,n', [('inventory',0),('smoke',6),('full',36)])
def test_real_runner_mock_http_modes_and_no_gold_on_wire(monkeypatch,mode,n):
    http=mocked(monkeypatch);r=run.run(mode)
    sent=[v for _,path,v,_ in http.calls if path=='/api/chat']
    assert len(sent)==n and r['run_status']=='complete' and r['identity_verified_at_end']
    assert r['attempted']==n and r['selected']['cases']==n
    ids=[]
    for payload in sent:
        assert set(payload)=={'model','messages','format','stream','think','options'}
        assert payload['model']==CONFIG['model']['tag'] and payload['think'] is False and payload['stream'] is False
        assert payload['options']==CONFIG['generation']['options'] and payload['format']==CONFIG['output_schema']
        assert payload['messages'][0]==dict(role='system',content=CONFIG['prompt'])
        p=json.loads(payload['messages'][1]['content'])
        assert set(p)=={'schema','synthetic_only','provider','record_type','notice_kind','subject'}
        ids.append(BY_INPUT[wording.canonical(p)]['id'])
        assert len(payload['messages'])==2 and 'context' not in payload
    assert ids==(CONFIG['smoke'] if mode=='smoke' else [c['id'] for c in CASES] if mode=='full' else [])
    text=wording.canonical(r)
    assert 'input_fingerprint' not in text and CONFIG['prompt'] not in text
    assert all(c['input']['subject'] not in text for c in CASES)
    assert r['restrictions']==dict(authority='none',sender_claim_only=True,human_review_required=True,independent_safety_and_authorization_required=True)
    if mode=='inventory':assert r['model_metrics'] is r['comparison'] is None
    else:
        assert r['comparison'] is not None
        assert r['status_counts']=={'valid':n}
        assert r['model_metrics']['selected']==n
    if mode=='full':
        assert r['corpus']==dict(selected=36,clear=24,ambiguous=12,groups=12)
        assert r['model_metrics']['clear_outcomes']['abstain']==24 and r['model_metrics']['ambiguous_abstain']==12
        assert r['model_metrics']['missed_outstanding_cases']==12 and r['model_metrics']['missed_date_cases']==16
        assert len(r['by_group'])==12


def test_metadata_residency_is_not_gpu_utilization_and_missing_telemetry_null(monkeypatch):
    def response(m,p,d,v):
        if p=='/api/ps':return {'models':[dict(name=CONFIG['model']['tag'],digest=CONFIG['model']['digest'],size=3300000000,size_vram=3000000000)]}
        if p=='/api/chat':
            for k in run.TELEMETRY:v.pop(k,None)
        return v
    mocked(monkeypatch,response);r=run.run('smoke')
    assert r['initial_residency']==dict(size=3300000000,size_vram=3000000000,context_length=None)
    assert all(x is None for x in r['cases'][0]['telemetry'].values())
    assert 'utilization' not in wording.canonical(r)


@pytest.mark.parametrize('bad', ['```json\n{}\n```','prefix {"state":"abstain","steps":[],"dates":[]}',
                                '{"state":"abstain","state":"informational","steps":[],"dates":[]}',
                                '{"state":NaN,"steps":[],"dates":[]}','{} trailing','\ufeff{}'])
def test_no_json_repairs(bad):
    with pytest.raises(run.ExperimentError):run.parse_prediction(bad,e.EmailMetadata(CASES[0]['input']))


@pytest.mark.parametrize('value', [dict(ABSTAIN,extra=True),dict(ABSTAIN,steps=[dict(action='invoice_payment',status='reported_outstanding')]),
    dict(state='explicit_outstanding',steps=[],dates=[]),dict(state='explicit_completion',steps=[],dates=[]),
    dict(state='informational',steps=[dict(action='invoice_payment',status='reported_completed')],dates=[]),
    dict(state='promotional',steps=[dict(action='return_form',status='reported_outstanding')],dates=[]),
    dict(state='informational',steps=[],dates=[dict(role='event_date',value='2030-02-30',action=None)]),
    dict(state='informational',steps=[],dates=[dict(role='event_date',value='2030-02-20',action='')]),
    dict(state='informational',steps=[],dates=[dict(role='due_date',value='2030-02-20',action='invoice_payment')]),
    dict(state='explicit_outstanding',steps=[dict(action='return_form',status='reported_outstanding')],dates=[dict(role='due_date',value='2030-02-20',action='invoice_payment')]),
    dict(state='explicit_completion',steps=[dict(action='return_form',status='reported_completed')],dates=[dict(role='reported_completion_date',value='2030-02-20',action='invoice_payment')]),
    dict(state='informational',steps=[],dates=[dict(role='offer_expiry',value='2030-02-20',action=None)])])
def test_cross_constraints_reject_invalid_structure(value):
    with pytest.raises(run.ExperimentError,match='invalid_structure'):
        run.parse_prediction(json.dumps(value),e.EmailMetadata(CASES[0]['input']))


def test_model_type_does_not_forge_rule_evidence_and_never_provides_authority():
    for c in CASES:
        got=run.parse_prediction(json.dumps(output(c['reference'])),e.EmailMetadata(c['input']))
        assert type(got) is run.ModelEvidence and not isinstance(got,e.Evidence)
        assert not hasattr(got,'rule_id') and got.signature()==c['reference']


@pytest.mark.parametrize('fault,code', [('json','invalid_json'),('structure','invalid_structure'),('empty','refused'),('length','truncated')])
def test_ordinary_model_failure_preserves_denominators_not_abstain(monkeypatch,fault,code):
    def response(m,p,d,v):
        if p=='/api/chat':
            if fault=='json':v['message']['content']='not JSON or private model text'
            if fault=='structure':v['message']['content']='{}'
            if fault=='empty':v['message']['content']=''
            if fault=='length':v['done_reason']='length'
        return v
    http=mocked(monkeypatch,response);r=run.run('full');m=r['model_metrics']
    assert r['attempted']==36 and r['status_counts']=={code:36}
    assert m['selected']==36 and m['clear']==24 and m['ambiguous']==12
    assert m['clear_outcomes']['abstain']==m['ambiguous_abstain']==0
    assert m['missed_outstanding_cases']==12 and m['missed_date_cases']==16
    assert m['status_counts']['invalid_output']==36 and len([x for x in http.calls if x[1]=='/api/chat'])==36
    assert 'private model text' not in wording.canonical(r)


@pytest.mark.parametrize('fault,code', [('thinking','thinking_leakage'),('inline','thinking_leakage'),('tool','protocol_error'),
    ('context','protocol_error'),('model','identity_unverified'),('done','protocol_error'),('tokens','resource_limit'),
    ('input_tokens','resource_limit'),('long','resource_limit'),('extra','protocol_error'),('timeout','timeout'),('wire','transport_error')])
def test_fatal_boundaries_stop_after_one_attempt_and_no_retries(monkeypatch,fault,code):
    def response(m,p,d,v):
        if p=='/api/chat':
            if fault=='thinking':v['message']['thinking']='never save this reasoning'
            if fault=='inline':v['message']['content']='<think>private</think>'+json.dumps(ABSTAIN)
            if fault=='tool':v['message']['tool_calls']=[{}]
            if fault=='context':v['context']=[1]
            if fault=='model':v['model']='different'
            if fault=='done':v['done']=False
            if fault=='tokens':v['eval_count']=513
            if fault=='input_tokens':v['prompt_eval_count']=4097
            if fault=='long':v['message']['content']='x'*8193
            if fault=='extra':v['thinking']='unexpected thinking'
            if fault=='timeout':raise TimeoutError('private network details')
            if fault=='wire':raise OSError('private driver details')
        return v
    http=mocked(monkeypatch,response);r=run.run('full')
    assert r['run_status']=='partial' and r['stop_code']==code and r['comparison'] is None
    assert r['attempted']==1 and r['status_counts']['not_attempted']==35
    assert r['cases'][0]['status']==code
    assert len([x for x in http.calls if x[1]=='/api/chat'])==1
    if fault=='model':
        assert not r['identity_verified_at_end']
        assert r['model_metrics'] is r['by_group'] is r['observed_identity'] is None
    else:
        assert r['identity_verified_at_end'] and r['observed_identity'] is not None
        assert r['model_metrics']['selected']==36 and r['model_metrics']['missed_outstanding_cases']==12
    assert all(x not in wording.canonical(r) for x in ('never save','private driver','private network','<think>'))


@pytest.mark.parametrize('at', ['initial','before_second','end','transient'])
def test_identity_failure_suppresses_attributed_metrics_even_if_restored(monkeypatch,at):
    seen=0
    def response(m,p,d,v):
        nonlocal seen
        if p=='/api/tags':
            seen+=1
            bad=(seen==1 if at=='initial' else seen==3 if at in ('before_second','transient') else seen==8)
            if bad:v['models'][0]['digest']='0'*64
        return v
    http=mocked(monkeypatch,response);r=run.run('smoke')
    assert r['run_status']=='partial' and not r['identity_verified_at_end']
    assert r['model_metrics'] is r['by_group'] is r['comparison'] is r['observed_identity'] is None
    if at=='initial':assert r['attempted']==0
    elif at in ('before_second','transient'):assert r['attempted']==1
    else:assert r['attempted']==6


@pytest.mark.parametrize('fault', ['missing_model','duplicates','details','capability','version','ps_digest'])
def test_inventory_fails_closed_without_inference(monkeypatch,fault):
    def response(m,p,d,v):
        if p=='/api/tags':
            if fault=='missing_model':v['models']=[]
            if fault=='duplicates':v['models']*=2
        if p=='/api/show':
            if fault=='details':v['details']['parameter_size']='8B'
            if fault=='capability':v['capabilities']=['completion']
        if p=='/api/version' and fault=='version':v['version']='private unexpected text'
        if p=='/api/ps' and fault=='ps_digest':v['models']=[dict(name=CONFIG['model']['tag'],digest='0'*64)]
        return v
    http=mocked(monkeypatch,response);r=run.run('inventory')
    assert r['run_status']=='partial' and r['model_metrics'] is r['comparison'] is None
    assert not any(x[1]=='/api/chat' for x in http.calls)


def test_total_deadline_leaves_unattempted_and_does_not_recheck_after_expiry(monkeypatch):
    clock=[100.0];monkeypatch.setattr(run.time,'monotonic',lambda:clock[0])
    def response(m,p,d,v):
        if p=='/api/chat':clock[0]=701.0
        return v
    http=mocked(monkeypatch,response);r=run.run('full')
    assert r['run_status']=='partial' and r['attempted']==1 and not r['identity_verified_at_end']
    assert r['model_metrics'] is None and r['status_counts']['not_attempted']==35


def test_only_frozen_projection_and_exact_request_can_be_sent(monkeypatch):
    http=mocked(monkeypatch);client=run.Transport(CONFIG,CASES,run.time.monotonic()+600)
    fields=dict(CASES[0]['input'],subject='A new synthetic title outside frozen set')
    with pytest.raises(run.ExperimentError):client.payload(e.EmailMetadata(fields))
    for method,path,data in [('POST','/api/pull',{}),('GET','http://external/',None),('GET','/api/tags?x=1',None),('POST','/api/show',{'model':'different','verbose':False})]:
        with pytest.raises(run.ExperimentError):client.request(method,path,data)
    payload=client.payload(e.EmailMetadata(CASES[0]['input']))
    for key,value in [('think',0),('model','another'),('format','json'),('options',{'num_predict':1024}),('messages',payload['messages']+[{'role':'assistant','content':'history'}])]:
        bad=deepcopy(payload);bad[key]=value
        with pytest.raises(run.ExperimentError):client.request('POST','/api/chat',bad)
    assert not http.calls


def test_file_access_only_fixed_wording_engine_scorer_config(monkeypatch,tmp_path):
    mocked(monkeypatch);accessed=[];old_open=io.open;old_builtin=builtins.open;old_os=os.open
    allowed={run.ROOT/run.CONFIG,run.ROOT/wording.FIXTURE,run.ROOT/wording.ENGINE,run.ROOT/'experiments/email_wording_challenge.py'}
    def guard(path):
        if isinstance(path,int):return
        value=Path(path).absolute();accessed.append(value)
        assert value in allowed, 'Unexpected file access; no legacy, split or Calendar inputs'
    def wrapped_io(p,*a,**k):guard(p);return old_open(p,*a,**k)
    def wrapped_builtin(p,*a,**k):guard(p);return old_builtin(p,*a,**k)
    def wrapped_os(p,*a,**k):guard(p);return old_os(p,*a,**k)
    monkeypatch.setattr(io,'open',wrapped_io);monkeypatch.setattr(builtins,'open',wrapped_builtin);monkeypatch.setattr(os,'open',wrapped_os)
    r=run.run('full');assert r['attempted']==36 and set(accessed)==allowed


@pytest.mark.parametrize('relative', [Path('fixtures/synthetic-email-evidence-v1.json'),Path('../outside'),Path('/tmp/other'),Path('fixtures/action-evaluation-v1/holdout.json')])
def test_new_pin_reader_has_no_arbitrary_file_permission(relative):
    with pytest.raises(run.ExperimentError):run.read_pin(relative,'0'*64)


def test_configuration_or_scorer_corruption_rejected_before_http(tmp_path,monkeypatch):
    http=mocked(monkeypatch)
    monkeypatch.setattr(run,'CONFIG_SHA','0'*64)
    with pytest.raises(run.ExperimentError):run.run('inventory')
    assert not http.calls


@pytest.mark.parametrize('fault', ['redirect','status','type','encoding','length','size','header','invalid_json'])
def test_http_response_boundary_faults(monkeypatch,fault):
    http=mocked(monkeypatch);original=http.__class__.__call__
    def connection(*a,**k):
        c=original(http,*a,**k);get=c.getresponse
        def response():
            r=get()
            if fault=='redirect':r.status=302;r.headers['Location']='http://external.invalid/'
            if fault=='status':r.status=500
            if fault=='type':r.headers['Content-Type']='text/html'
            if fault=='encoding':r.headers['Content-Encoding']='gzip'
            if fault=='length':r.headers['Content-Length']='999'
            if fault=='size':r.raw=io.BytesIO(b'x'*65537)
            if fault=='header':r.headers['Too-Large']='x'*8193
            if fault=='invalid_json':r.raw=io.BytesIO(b'not json')
            return r
        c.getresponse=response;return c
    monkeypatch.setattr(run.http.client,'HTTPConnection',connection)
    r=run.run('inventory');assert r['run_status']=='partial' and r['model_metrics'] is None
    assert all(x[1] in ('/api/version',) for x in http.calls)


def test_socket_deadline_checked_on_each_receive_including_headers(monkeypatch):
    clock=[0.0];monkeypatch.setattr(run.time,'monotonic',lambda:clock[0])
    class Raw:
        def settimeout(self,x):assert 0<x<=5
        def recv_into(self,b):
            clock[0]+=3;b[0]=ord('x');return 1
        def close(self):pass
    stream=run.DeadlineSocket(Raw(),5).makefile('rb')
    with pytest.raises(run.ExperimentError,match='timeout'):stream.readline()


def test_semantic_fault_injection_reuses_frozen_scorer(monkeypatch):
    def oracle(m,p,d,v):
        if p=='/api/chat':return envelope(output(BY_INPUT[d['messages'][1]['content']]['reference']))
        return v
    mocked(monkeypatch,oracle);r=run.run('full');m=r['model_metrics']
    assert m['clear_outcomes']['full']==24 and m['ambiguous_abstain']==12
    assert all(m[k]==0 for k in wording.COUNTERS)
    assert len(r['comparison']['new_full_case_ids'])==24
    assert r['comparison']['additional_correct_step_atoms']>0


@pytest.mark.parametrize('fault,key', [('step','unsupported_step_cases'),('complete','unsupported_completion_cases'),
    ('ambiguous','ambiguous_overreach'),('miss_date','missed_date_cases'),('invent','invented_date_cases'),('role','misbound_date_cases'),('scope','misbound_date_cases')])
def test_each_error_metric_can_really_increase(monkeypatch,fault,key):
    def response(m,p,d,v):
        if p!='/api/chat':return v
        case=BY_INPUT[d['messages'][1]['content']];ref=output(case['reference'])
        if case['id']=='WC01-1':
            if fault=='step':ref['steps'].append(dict(action='return_form',status='reported_outstanding'))
            if fault=='complete':ref['steps'].append(dict(action='return_form',status='reported_completed'))
            if fault=='miss_date':ref['dates']=[]
            if fault=='invent':ref['dates'][0]['value']='2031-12-21'
            if fault=='scope':ref['steps']=[dict(action='return_form',status='reported_outstanding')];ref['dates'][0]['action']='return_form'
        if case['id']=='WC12-1' and fault=='role':ref['dates'][0]['role']='available_date'
        if case['id']=='WC10-3' and fault=='ambiguous':ref=dict(state='informational',steps=[],dates=[])
        return envelope(ref)
    mocked(monkeypatch,response);r=run.run('full')
    assert r['model_metrics'][key]>=1 and r['model_metrics']['selected']==36
    if fault in ('step','complete'):assert r['comparison']['additional_unsupported_step_atoms']>=1
    if fault in ('invent','role','scope'):assert r['comparison']['additional_wrong_date_atoms']>=1


def test_actual_cli_call_chain_with_mock_http_and_unique_complete_reports(monkeypatch,tmp_path,capsys):
    mocked(monkeypatch)
    # Keep the actual publication root in an isolated synthetic checkout for this CLI test.
    original_save=run.save
    def save(value):
        with monkeypatch.context() as local:
            local.setattr(run,'ROOT',tmp_path);local.setattr(run,'LOCAL',Path('.local/email-model-evidence'))
            return original_save(value)
    monkeypatch.setattr(run,'save',save)
    assert run.main(['--synthetic-only','smoke'])==0
    first=capsys.readouterr().out;path1=tmp_path/first.strip().split('报告：')[-1];old=path1.read_bytes()
    assert run.main(['--synthetic-only','smoke'])==0
    path2=tmp_path/capsys.readouterr().out.strip().split('报告：')[-1]
    assert path1!=path2 and path1.read_bytes()==old
    one,two=json.loads(old),json.loads(path2.read_bytes())
    for r in (one,two):
        for c in r['cases']:c['latency_seconds']=None
    assert one==two and not list(tmp_path.rglob('*.tmp'))


@pytest.mark.parametrize('mode,n',[('inventory',0),('smoke',6),('full',36)])
def test_module_cli_via_runpy_uses_mock_no_real_inference(monkeypatch,tmp_path,capsys,mode,n):
    http=mocked(monkeypatch)
    # Same module file executed as __main__; actual CLI parsing + HTTP + save in isolated cwd root.
    monkeypatch.setattr(sys,'argv',['email_model_evidence','--synthetic-only',mode])
    monkeypatch.setattr(wording,'ROOT',run.ROOT)
    old_replace=run.os.replace;written=[]
    def publish(a,b):written.append(b);old_replace(a,b)
    monkeypatch.setattr(run.os,'replace',publish)
    monkeypatch.delitem(sys.modules,'experiments.email_model_evidence')
    try:
        with pytest.raises(SystemExit) as exc:runpy.run_module('experiments.email_model_evidence',run_name='__main__')
        assert exc.value.code==0 and len(written)==1
        assert sum(x[1]=='/api/chat' for x in http.calls)==n
        assert mode in capsys.readouterr().out
    finally:
        # CLI harness must not leave Mock-model reports resembling manual runs.
        for path in written:
            if path.exists():path.unlink()
            if path.parent.exists():path.parent.rmdir()


@pytest.mark.parametrize('args',[[],['smoke'],['--synthetic-only'],['--synthetic-only','full','--host','external'],['--synthetic-only','full','--model','other'],['--synthetic-only','full','--file','other']])
def test_cli_has_no_arbitrary_input_options(args):
    with pytest.raises(SystemExit):run.main(args)


@pytest.mark.parametrize('fault',['write','flush','fsync','replace'])
def test_report_failure_cleanup_and_no_success(monkeypatch,tmp_path,capsys,fault):
    mocked(monkeypatch);original_run=run.run
    prepared=original_run('smoke')
    monkeypatch.setattr(run,'run',lambda _:prepared);monkeypatch.setattr(run,'ROOT',tmp_path)
    if fault in ('write','flush'):
        original=Path.open
        class Broken:
            def __init__(self,s):self.stream=s
            def __enter__(self):return self
            def __exit__(self,*a):self.stream.close()
            def write(self,s):
                self.stream.write(s[:50])
                if fault=='write':raise OSError('private filesystem text')
            def flush(self):raise OSError('private filesystem text')
            def fileno(self):return self.stream.fileno()
        def opening(path,*a,**k):
            stream=original(path,*a,**k)
            return Broken(stream) if path.name=='report.json.tmp' else stream
        monkeypatch.setattr(Path,'open',opening)
    elif fault=='fsync':monkeypatch.setattr(os,'fsync',lambda _:(_ for _ in ()).throw(OSError('private fsync')))
    else:monkeypatch.setattr(os,'replace',lambda *a:(_ for _ in ()).throw(OSError('private replace')))
    assert run.main(['--synthetic-only','smoke'])==1
    text=capsys.readouterr().out
    assert '报告：' not in text and 'private' not in text
    assert not list(tmp_path.rglob('report.json')) and not list(tmp_path.rglob('*.tmp'))
    assert list((tmp_path/run.LOCAL).iterdir())==[]


def test_unpaired_unicode_is_ordinary_failed_output_not_ignored(monkeypatch):
    def response(m,p,d,v):
        if p=='/api/chat':v['message']['content']='\ud800'
        return v
    mocked(monkeypatch,response);r=run.run('smoke')
    assert r['attempted']==6 and r['status_counts']=={'invalid_structure':6}
    assert r['model_metrics']['ambiguous_abstain']==0


def test_failed_recheck_suppresses_model_conclusions_even_if_next_check_recovers(monkeypatch):
    count=0
    def response(m,p,d,v):
        nonlocal count
        if p=='/api/tags':
            count+=1
            if count==3:raise TimeoutError('private failure')
        return v
    mocked(monkeypatch,response);r=run.run('full')
    assert r['attempted']==1 and r['model_metrics'] is r['comparison'] is None
    assert not r['identity_verified_at_end']


def test_first_ordinary_invalid_output_not_claimed_structured_control(monkeypatch):
    def response(m,p,d,v):
        if p=='/api/chat':v['message']['content']='bad response'
        return v
    mocked(monkeypatch,response);r=run.run('smoke')
    assert r['control_observation']['structured_reply_observed'] is False
    assert r['control_observation']['first_attempt_status']=='invalid_json'


def test_existing_report_directory_never_overwritten(tmp_path,monkeypatch):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    class Fixed:hex='a'*32
    monkeypatch.setattr(run,'uuid4',lambda:Fixed())
    first=tmp_path/run.save({'finite':'first'});original=first.read_bytes()
    with pytest.raises(FileExistsError):run.save({'finite':'second'})
    assert first.read_bytes()==original and not list(tmp_path.rglob('*.tmp'))


@pytest.mark.parametrize('framing',['length','chunked','close'])
def test_http_headers_and_body_parse_use_actual_stdlib_with_mock_socket(monkeypatch,framing):
    # Includes HTTPConnection.getresponse's early connection-close path: the reader
    # must retain the socket until the body has actually been consumed.
    body=json.dumps({'version':'0.40.6'}).encode()
    header=b'HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Type: application/json\r\n'
    if framing=='length':wire=header+b'Content-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
    elif framing=='chunked':wire=header+b'Transfer-Encoding: chunked\r\n\r\n'+format(len(body),'x').encode()+b'\r\n'+body+b'\r\n0\r\n\r\n'
    else:wire=header+b'\r\n'+body
    class Raw:
        def __init__(self):self.data=io.BytesIO(wire);self.closed=False;self.sent=[]
        def settimeout(self,value):assert not self.closed and 0<value<=60
        def recv_into(self,buffer):assert not self.closed;return self.data.readinto(buffer)
        def sendall(self,data):self.sent.append(data)
        def close(self):self.closed=True
    raw=Raw()
    original=run.http.client.HTTPConnection.connect
    def connect(self):self.sock=raw
    monkeypatch.setattr(run.http.client.HTTPConnection,'connect',connect)
    client=run.Transport(CONFIG,CASES,run.time.monotonic()+600)
    assert client.request('GET','/api/version')=={'version':'0.40.6'}
    assert raw.closed and b'Host: 127.0.0.1:11434' in b''.join(raw.sent)


def test_mock_cli_failure_never_claims_complete_or_falls_back(monkeypatch,capsys,tmp_path):
    http=mocked(monkeypatch,lambda m,p,d,v:(_ for _ in ()).throw(OSError('private failure')))
    original_save=run.save
    def save(value):
        with monkeypatch.context() as m:
            m.setattr(run,'ROOT',tmp_path)
            return original_save(value)
    monkeypatch.setattr(run,'save',save)
    assert run.main(['--synthetic-only','full'])==2
    text=capsys.readouterr().out
    assert 'partial' in text and 'private failure' not in text
    r=json.loads((tmp_path/text.strip().split('报告：')[-1]).read_text(encoding='utf-8'))
    assert r['attempted']==0 and r['selected']['cases']==36 and r['model_metrics'] is None
    assert all(c['status']=='not_attempted' for c in r['cases'])
    assert all(x[1]=='/api/version' for x in http.calls)


def test_transport_itself_rejects_unpinned_config_or_synthetic_only_as_proof(monkeypatch):
    http=mocked(monkeypatch)
    config=deepcopy(CONFIG);config['prompt']='unapproved prompt'
    with pytest.raises(run.ExperimentError):run.Transport(config,CASES,run.time.monotonic()+600)
    cases=deepcopy(CASES);cases[0]['input']['subject']='New synthetic input, not pinned'
    assert cases[0]['input']['synthetic_only'] is True
    with pytest.raises(run.ExperimentError):run.Transport(CONFIG,cases,run.time.monotonic()+600)
    assert not http.calls


def test_partial_payment_completion_never_clears_other_outstanding_step(monkeypatch):
    def response(m,p,d,v):
        if p=='/api/chat':
            c=BY_INPUT[d['messages'][1]['content']];ref=output(c['reference'])
            if c['id']=='WC10-1':ref=dict(state='explicit_completion',steps=[ref['steps'][0]],dates=[])
            return envelope(ref)
        return v
    mocked(monkeypatch,response);r=run.run('full');m=r['model_metrics']
    assert m['clear_outcomes']['partial']==1 and m['missed_outstanding_cases']==1
    assert m['false_clearance_proxy_cases']==1 and m['unsupported_completion_cases']==0


def test_end_check_unavailable_keeps_failure_code_and_no_model_attribution(monkeypatch):
    seen=0
    def response(m,p,d,v):
        nonlocal seen
        if p=='/api/tags':
            seen+=1
            if seen==8:raise OSError('untrusted socket text')
        return v
    mocked(monkeypatch,response);r=run.run('smoke')
    assert r['attempted']==6 and r['run_status']=='partial' and r['stop_code']=='transport_error'
    assert r['model_metrics'] is r['comparison'] is None


def test_proxy_environment_cannot_change_fixed_numeric_destination(monkeypatch):
    for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy'):
        monkeypatch.setenv(name,'http://proxy.example.invalid:9000')
    http=mocked(monkeypatch);r=run.run('inventory')
    assert r['run_status']=='complete'
    assert all('proxy' not in str(c) for c in http.calls)


def test_same_semantic_atoms_in_different_order_keep_original_exact_scoring(monkeypatch):
    def response(m,p,d,v):
        if p=='/api/chat':
            ref=output(BY_INPUT[d['messages'][1]['content']]['reference']);ref['steps'].reverse()
            return envelope(ref)
        return v
    mocked(monkeypatch,response);r=run.run('full')
    assert r['model_metrics']['clear_outcomes']['full']==24
    assert len(r['comparison']['new_full_case_ids'])==24


def test_metrics_mark_per_case_new_errors_not_cancelled_by_other_repairs(monkeypatch):
    # Controlled scorer injection only: baseline and candidate fail different cases.
    cases=[c for c in CASES if c['id'] in ('WC01-1','WC01-2')]
    def row(c,miss):
        return dict(id=c['id'],group=c['group'],variant=c['variant'],reference=c['reference'],status='valid',
                    actual=deepcopy(ABSTAIN if miss else c['reference']),reason='unsupported')
    rules=[row(c,i==0) for i,c in enumerate(cases)]
    models=[row(c,i==1) for i,c in enumerate(cases)]
    r=run.compare(rules,models)
    assert r['additional_errors']['missed_outstanding_cases']==1
    assert r['reduced_errors']['missed_outstanding_cases']==1


@pytest.mark.parametrize('value', [
    dict(state='unknown',steps=[],dates=[]),
    dict(ABSTAIN,authority='approved'),
    dict(state='explicit_outstanding',steps=[dict(action='invoice_payment',status='reported_outstanding')]*2,dates=[]),
    dict(state='explicit_outstanding',steps=[dict(action='invoice_payment',status='reported_outstanding')]*3,dates=[]),
    dict(state='informational',steps=[],dates=[dict(role='event_date',value='2030-02-20',action=None)]*2),
    dict(state='explicit_outstanding',steps=[dict(action='invoice_payment',status='reported_outstanding')],dates=[dict(role='due_date',value='2030-02-20',action=None)]),
    dict(state='informational',steps=[],dates=[dict(role='event_date',value='2030-02-20',action='attend_visit')]),
    dict(state='informational',steps=[],dates=[dict(role='event_date',value='2014-02-20',action=None)]),
    dict(state='informational',steps=[],dates=[dict(role='event_date',value='2036-02-20',action=None)]),
    dict(state='informational',steps=[],dates=[dict(role='event_date',value='February 20',action=None)]),
    dict(state='explicit_outstanding',steps=[dict(action='invoice_payment',status='unknown')],dates=[]),
])
def test_remaining_schema_bounds_and_no_authority_or_free_text(value):
    with pytest.raises(run.ExperimentError):run.parse_prediction(json.dumps(value),e.EmailMetadata(CASES[0]['input']))


def test_promotional_input_cannot_become_service_due_date():
    c=next(c for c in CASES if c['id']=='WC11-1')
    bad=dict(state='explicit_outstanding',steps=[dict(action='invoice_payment',status='reported_outstanding')],
             dates=[dict(role='due_date',value='2030-02-20',action='invoice_payment')])
    with pytest.raises(run.ExperimentError):run.parse_prediction(json.dumps(bad),e.EmailMetadata(c['input']))


def test_failed_input_projection_is_not_sent_and_keeps_selected_denominators(monkeypatch):
    mocked(monkeypatch)
    original=run.Transport.payload
    def reject(self,p):raise run.ExperimentError('input_rejected')
    monkeypatch.setattr(run.Transport,'payload',reject)
    r=run.run('full')
    assert r['selected']['cases']==36 and r['attempted']==0 and r['stop_code']=='input_rejected'
    assert r['run_status']=='partial' and r['model_metrics']['missed_outstanding_cases']==12


def test_reasoning_inside_json_is_not_stripped_and_stops(monkeypatch):
    def response(m,p,d,v):
        if p=='/api/chat':v['message']['content']=json.dumps(dict(ABSTAIN,thinking='untrusted reasoning'))
        return v
    mocked(monkeypatch,response);r=run.run('full')
    assert r['attempted']==1 and r['stop_code']=='thinking_leakage'
    assert 'untrusted reasoning' not in wording.canonical(r)


def test_manual_interrupt_publishes_partial_not_retried_and_rechecks_identity(monkeypatch):
    def response(m,p,d,v):
        if p=='/api/chat':raise KeyboardInterrupt()
        return v
    http=mocked(monkeypatch,response);r=run.run('full')
    assert r['run_status']=='partial' and r['stop_code']=='interrupted'
    assert r['status_counts']=={'interrupted':1,'not_attempted':35} and r['attempted']==1
    assert r['identity_verified_at_end'] and r['comparison'] is None
    assert r['model_metrics']['selected']==36 and r['model_metrics']['missed_outstanding_cases']==12
    assert sum(path=='/api/chat' for _,path,*_ in http.calls)==1
    assert http.calls[-1][1]=='/api/show'


def test_absolute_deadline_float_roundoff_never_exceeds_frozen_timeout(monkeypatch):
    # Deterministic representative of native Windows3.12.0 >60 subtraction.
    monkeypatch.setattr(run.time,'monotonic',lambda:4.01)
    assert (4.01+60)-4.01>60
    mocked(monkeypatch)
    result=run.run('smoke')  # Mock Wire retains strict <=60 assertion; no tolerance.
    assert result['run_status']=='complete' and result['attempted']==6


def test_native_http_parser_stops_oversized_headers_before_materializing_them(monkeypatch):
    data=io.BytesIO(b'HTTP/1.1 200 OK\r\nOversized: '+b'x'*1_000_000+b'\r\n\r\n{}')
    class Raw:
        def settimeout(self,v):assert 0<v<=60
        def sendall(self,v):pass
        def recv_into(self,buffer):return data.readinto(buffer)
        def close(self):pass
    monkeypatch.setattr(run.http.client.HTTPConnection,'connect',lambda self:setattr(self,'sock',Raw()))
    client=run.Transport(CONFIG,CASES,run.time.monotonic()+600)
    with pytest.raises(run.ExperimentError,match='resource_limit'):client.request('GET','/api/version')
    # At most one bounded BufferedReader prefetch beyond the cap, not the full
    # malicious header or stdlib's much larger normal header-parser allowance.
    assert data.tell()<=8192*2


@pytest.mark.parametrize('bad_at',(1,2))
@pytest.mark.parametrize('identity',('missing','null','bool','number','list','object','empty','wrong','whitespace','non_object'))
def test_reply_identity_failure_permanently_removes_attribution(monkeypatch,bad_at,identity):
    seen=0
    values={'null':None,'bool':False,'number':0,'list':[],'object':{},'empty':'',
            'wrong':'wrong-model','whitespace':CONFIG['model']['tag']+' '}
    def response(method,path,data,value):
        nonlocal seen
        if path=='/api/chat':
            seen+=1
            if seen==bad_at:
                if identity=='missing':value.pop('model')
                elif identity=='non_object':return []
                else:value['model']=values[identity]
        return value  # All metadata, including the final check, remain normal.
    http=mocked(monkeypatch,response);r=run.run('full')
    assert r['run_status']=='partial' and r['stop_code']=='identity_unverified'
    assert not r['identity_verified_at_end']
    assert r['observed_identity'] is r['model_metrics'] is r['by_group'] is r['comparison'] is None
    assert r['attempted']==seen==bad_at and len(r['cases'])==36
    assert r['selected']==dict(cases=36,clear=24,ambiguous=12,groups=12)
    assert r['rule_metrics']['selected']==36
    expected=dict(identity_unverified=1,not_attempted=36-bad_at)
    if bad_at==2:expected['valid']=1
    assert r['status_counts']==expected
    assert r['cases'][bad_at-1]['status']=='identity_unverified'
    if bad_at==2:
        assert r['cases'][0]['actual']==ABSTAIN and r['cases'][0]['status']=='valid'
    # Prove a normal final metadata observation occurred without restoring trust.
    assert http.calls[-1][1]=='/api/show'
    assert sum(c[1]=='/api/tags' for c in http.calls)==bad_at+2
    assert sum(c[1]=='/api/chat' for c in http.calls)==bad_at


@pytest.mark.parametrize('other_error',('extra','done','context'))
def test_reply_identity_failure_has_priority_over_other_protocol_errors(monkeypatch,other_error):
    def response(method,path,data,value):
        if path=='/api/chat':
            value['model']='wrong-model'
            if other_error=='extra':value['unexpected']=True
            if other_error=='done':value['done']=False
            if other_error=='context':value['context']=[1]
        return value
    mocked(monkeypatch,response);r=run.run('smoke')
    assert r['stop_code']=='identity_unverified' and r['attempted']==1
    assert not r['identity_verified_at_end'] and r['model_metrics'] is r['by_group'] is r['comparison'] is r['observed_identity'] is None
    raw=response('POST','/api/chat',None,envelope())
    with pytest.raises(run.ExperimentError,match='identity_unverified'):
        run.response_result(raw,e.EmailMetadata(CASES[0]['input']),CONFIG['limits'])


@pytest.mark.parametrize('bad_at',(1,2))
def test_cli_cannot_publish_metrics_after_bad_reply_identity(monkeypatch,tmp_path,capsys,bad_at):
    seen=0
    def response(method,path,data,value):
        nonlocal seen
        if path=='/api/chat':
            seen+=1
            if seen==bad_at:value.pop('model')
        return value
    mocked(monkeypatch,response);save=run.save
    def publish(result):
        with monkeypatch.context() as local:
            local.setattr(run,'ROOT',tmp_path)
            return save(result)
    monkeypatch.setattr(run,'save',publish)
    assert run.main(['--synthetic-only','full'])==2
    text=capsys.readouterr().out
    assert 'partial' in text and '清晰完整/部分/abstain' not in text
    value=json.loads((tmp_path/text.strip().split('报告：')[-1]).read_text(encoding='utf-8'))
    assert value['attempted']==bad_at and value['selected']['cases']==36
    assert not value['identity_verified_at_end']
    assert all(value[k] is None for k in ('observed_identity','model_metrics','by_group','comparison'))


def test_done_false_after_valid_reply_remains_ordinary_protocol_failure(monkeypatch):
    seen=0
    def response(method,path,data,value):
        nonlocal seen
        if path=='/api/chat':
            seen+=1
            if seen==2:value['done']=False
        return value
    mocked(monkeypatch,response);r=run.run('full')
    assert r['attempted']==2 and r['run_status']=='partial' and r['stop_code']=='protocol_error'
    assert r['identity_verified_at_end'] and r['observed_identity'] is not None
    assert r['model_metrics']['selected']==36 and r['by_group'] is not None
    assert r['comparison'] is None and r['cases'][0]['actual']==ABSTAIN


@pytest.mark.parametrize('wire', [b'not JSON',b'{"model":"qwen3.5:4b-q4_K_M","model":"wrong"}',b'\xff'])
def test_unparseable_chat_identity_cannot_be_repaired_by_metadata(monkeypatch,wire):
    http=MockHTTP();factory=http.__call__
    def connection(*args,**kwargs):
        c=factory(*args,**kwargs);get=c.getresponse
        def response():
            r=get()
            if http.calls[-1][1]=='/api/chat':r.raw=io.BytesIO(wire)
            return r
        c.getresponse=response
        return c
    monkeypatch.setattr(run.http.client,'HTTPConnection',connection)
    r=run.run('full')
    assert r['attempted']==1 and r['stop_code']=='identity_unverified'
    assert not r['identity_verified_at_end']
    assert r['model_metrics'] is r['by_group'] is r['observed_identity'] is r['comparison'] is None
    assert r['selected']['cases']==36 and r['status_counts']['not_attempted']==35
    assert http.calls[-1][1]=='/api/show'
