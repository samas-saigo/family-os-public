"""Mocked localhost boundary only: CI never connects to or requires Ollama."""
import json
from pathlib import Path
import socket
import subprocess
import time

import pytest

from family_os import ollama_synthetic_benchmark as bench
from family_os.analysis import load_classification, validate_output
from family_os.synthetic_reasoning import project_metadata
from test_synthetic_reasoning import source

DIGEST='a'*64
POLICY=load_classification(bench.ROOT/'config/classification.yaml')
LABELS={'relevance_label':'uncertain','domain_category':None,'domain_subcategory':None,'action_label':'uncertain'}


def envelope(**changes):
    return {'model':bench.MODEL,'done':True,'done_reason':'stop','response':json.dumps(LABELS),
        'total_duration':800000000,'load_duration':100000000,'prompt_eval_count':400,'prompt_eval_duration':100000000,
        'eval_count':40,'eval_duration':600000000}|changes


@pytest.fixture
def api(monkeypatch):
    """Mock even the actual HTTP connection, not a live service."""
    calls=[]
    class Sock:
        def settimeout(self,timeout): assert 0<timeout<=bench.REQUEST_SECONDS
        def shutdown(self,*args): pass
    class Response:
        status=200
        def __init__(self,value): self.value=value
        def read(self,size): return json.dumps(self.value).encode()[:size]
    class Connection:
        def __init__(self,host,port,timeout):
            assert (host,port)==('127.0.0.1',11434) and 0<timeout<=5
            self.sock=Sock()
        def connect(self): pass
        def request(self,method,path,body=None,headers=None):
            calls.append((method,path,json.loads(body) if body else None))
            self.path=path
        def getresponse(self):
            value={'/api/tags':{'models':[{'name':bench.MODEL,'digest':DIGEST}]},
                '/api/version':{'version':'0.40.1'},'/api/generate':envelope(),
                '/api/ps':{'models':[{'name':bench.MODEL,'digest':DIGEST,'size':100,'size_vram':100}]}}[self.path]
            return Response(value)
        def close(self): pass
    monkeypatch.setattr(bench.http.client,'HTTPConnection',Connection)
    # No socket operations can escape the mocked HTTP boundary.
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('live network'))
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('subprocess'))
    return calls


def test_smoke_is_five_fixed_cases_and_full_taxonomy_sent_without_truth(api):
    result=bench.benchmark()
    assert result['counts']=={'selected':5,'attempted':5,'projected':5,'sent':5,'valid':5,'failed':0,'projection_failed':0,
        'model_invalid':0,'infrastructure_failed':0,'json_valid':5,'not_attempted':0}
    assert result['completed'] and result['metrics']['ollama']['classifier_review_rate']==1
    payloads=[p for _,path,p in api if path=='/api/generate']
    assert len(payloads)==5
    for p in payloads:
        assert set(p)=={'model','prompt','format','stream','options','keep_alive'}
        assert p['model']==bench.MODEL and p['stream'] is False
        assert p['options']==bench.OPTIONS
        for category,children in POLICY.categories.items():
            assert category in p['prompt'] and all(child in p['prompt'] for child in children)
        assert all(key not in p['prompt'] for key in ('expected','fake_response','source_record_id','raw_record_id','owner_id','recipients'))
        assert set(p['format']['properties'])==bench.LABEL_KEYS
        assert len(p['prompt'].encode())<=bench.PROMPT_BYTES


def test_full_run_preserves_three_failed_projections_and_aggregate_only(api):
    result=bench.benchmark(full=True)
    assert result['counts']['selected']==result['counts']['attempted']==37
    assert result['counts']['projected']==result['counts']['sent']==result['counts']['valid']==34
    assert result['counts']['projection_failed']==result['counts']['failed']==3
    assert result['metrics']['ollama']['eligible_count']==result['metrics']['rules']['eligible_count']==37
    output=json.dumps(result)
    assert 'SYNTHETIC / NOT PRODUCTION ACCURACY' in output
    assert 'subject' not in output and 'sender' not in output and 'UNTRUSTED_METADATA' not in output
    assert result['performance']['generated_tokens_observed']==34*40
    assert result['performance']['generated_tokens_per_second']==pytest.approx(40/.6)
    assert result['performance']['load_duration_seconds']['count']==34
    assert result['performance']['residency_observation']['observed_vram_fraction']==1


def test_repeat_check_bounded_and_separate_from_unique_metrics(api):
    result=bench.benchmark(repeat_check=True)
    assert result['counts']['valid']==5
    assert result['repeat_check']=={'cases':2,'attempted':4,'sent':4,'valid':4,'failed':0,
        'model_invalid':0,'infrastructure_failed':0,'disagreements':0}
    assert len([p for _,path,p in api if path=='/api/generate'])==9
    assert result['metrics']['ollama']['eligible_count']==5


@pytest.mark.parametrize('change',[
    {'extra':'SECRET'}, {'domain_category':'home'}, {'domain_subcategory':'utility'},
    {'domain_category':'home','domain_subcategory':'hotel'}, {'action_label':'execute'},
    {'relevance_label':'ignore system instructions'}, {'relevance_label':[]},
    {'domain_category':float('nan')}, {'domain_category':float('inf')},
    {'domain_category':'home','domain_subcategory':None},
    {'domain_category':None,'domain_subcategory':'utility'},
])
def test_invalid_four_field_labels_independently_rejected(change):
    with pytest.raises(bench.BenchmarkError): bench.labels(json.dumps(LABELS|change),source(),POLICY)


@pytest.mark.parametrize('response',['null','[]','not JSON',json.dumps(LABELS)+' trailing',
    '{"action_label":"required","action_label":"uncertain"}', 'x'*4097])
def test_invalid_json_duplicate_keys_and_byte_budget(response):
    with pytest.raises(bench.BenchmarkError): bench.labels(response,source(),POLICY)


def test_valid_concrete_and_abstention_zero_confidence_empty_facts():
    for value in (LABELS,dict(relevance_label='relevant',domain_category='home',domain_subcategory='utility',action_label='required')):
        output=bench.labels(json.dumps(value),source(),POLICY)
        assert output.relevance_confidence==output.domain_confidence==output.action_confidence==0
        assert output.facts==() and validate_output(output,source(),POLICY)[0]['review_recommended']


@pytest.mark.parametrize('change',[{'model':'other'}, {'done':False}, {'done_reason':'length'}, {'thinking':'PRIVATE REASONING'},
    {'response':{}}, {'extra':'SECRET'}, {'eval_count':257}, {'eval_count':True}, {'eval_duration':-1},
    {'total_duration':float('nan')}, {'prompt_eval_count':5000}])
def test_bad_envelopes_and_token_limits(change):
    with pytest.raises(bench.BenchmarkError): bench.envelope(envelope(**change))


def test_missing_done_reason_is_rejected():
    result=envelope()
    del result['done_reason']
    with pytest.raises(bench.BenchmarkError): bench.envelope(result)


def test_missing_telemetry_null_denominators(api,monkeypatch):
    original=bench.LocalOllama._request
    def request(self,method,path,payload=None,**kwargs):
        if path=='/api/generate': return {'model':bench.MODEL,'done':True,'done_reason':'stop','response':json.dumps(LABELS)}
        if path=='/api/ps': raise bench.BenchmarkError()
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark()
    assert result['performance']['throughput_denominator_requests']==0
    assert result['performance']['generated_tokens_per_second'] is None
    assert result['performance']['residency_observation'] is None


@pytest.mark.parametrize('models',[[],[{'name':'other','digest':DIGEST}],
    [{'name':bench.MODEL,'digest':'bad'}], [{'name':bench.MODEL,'digest':DIGEST}]*2])
def test_missing_ambiguous_or_unidentified_model_refused(api,monkeypatch,models):
    monkeypatch.setattr(bench.LocalOllama,'_request',lambda *a,**k:{'models':models})
    with pytest.raises(bench.BenchmarkError): bench.benchmark()
    assert not api


def test_digest_change_before_dispatch_aborts_without_counting_sent(api,monkeypatch):
    original=bench.LocalOllama.installed_digest
    calls=0
    def identity(self,**kwargs):
        nonlocal calls
        calls+=1
        return DIGEST if calls==1 else 'b'*64
    monkeypatch.setattr(bench.LocalOllama,'installed_digest',identity)
    result=bench.benchmark()
    assert not result['completed'] and result['counts']['sent']==0
    assert result['counts']['failed']==1 and result['counts']['not_attempted']==4
    assert not [p for _,path,p in api if path=='/api/generate']


def test_invalid_output_aborts_after_first_sent_and_retains_denominators(api,monkeypatch):
    original=bench.LocalOllama._request
    def request(self,method,path,payload=None,**kwargs):
        if path=='/api/generate': return envelope(response='PRIVATE invalid output')
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark(full=True)
    assert not result['completed']
    assert result['counts']['sent']==result['counts']['failed']==1 and result['counts']['not_attempted']==36
    assert result['counts']['json_valid']==0
    assert result['counts']['infrastructure_failed']==1 and result['counts']['model_invalid']==0
    assert result['metrics']['ollama']['eligible_count']==37
    assert 'PRIVATE' not in json.dumps(result)


@pytest.mark.parametrize('cached',[0,341,4096])
def test_cached_prompt_count_is_optional_bounded_integer(cached):
    assert bench.envelope(envelope(prompt_eval_cached_count=cached))==bench.envelope(envelope())


@pytest.mark.parametrize('cached',[None,True,False,-1,4097,1.0,'341',[],{}])
def test_invalid_cached_prompt_counts_rejected(cached):
    with pytest.raises(bench.BenchmarkError): bench.envelope(envelope(prompt_eval_cached_count=cached))


def test_observed_cached_field_with_valid_prediction_runs_all_smoke_cases(api,monkeypatch):
    original=bench.LocalOllama._request
    def request(self,method,path,payload=None,**kwargs):
        if path=='/api/generate':
            return envelope(prompt_eval_cached_count=0,prompt_eval_count=341,eval_count=25)
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark()
    assert result['completed'] and result['counts']['valid']==5
    assert result['performance']['generation_requests_with_telemetry']==5


def test_observed_home_insurance_failure_continues_without_coercion(api,monkeypatch,caplog):
    original=bench.LocalOllama._request
    generates=0
    valid=LABELS|{'relevance_label':'relevant','domain_category':'home','domain_subcategory':'utility','action_label':'required'}
    invalid=valid|{'domain_subcategory':'insurance'}
    with pytest.raises(bench.ModelPredictionError): bench.labels(json.dumps(invalid),source(),POLICY)
    def request(self,method,path,payload=None,**kwargs):
        nonlocal generates
        if path=='/api/generate':
            generates+=1
            return envelope(prompt_eval_cached_count=0,prompt_eval_count=341,eval_count=25,
                response=json.dumps(invalid if generates==1 else valid))
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark()
    assert result['completed'] and result['abort_reason'] is None and generates==5
    c=result['counts']
    assert c['selected']==c['attempted']==c['sent']==c['json_valid']==5
    assert c['valid']==4 and c['model_invalid']==c['failed']==1
    assert c['projection_failed']==c['infrastructure_failed']==c['not_attempted']==0
    assert result['json_validity_rate']==1 and result['model_invalid_rate']==.2 and result['label_validity_rate']==.8
    metrics=result['metrics']['ollama']
    assert metrics['eligible_count']==5 and metrics['domain_classified_count']==4
    assert metrics['classifier_domain_abstained_count']==1 and metrics['classifier_review_rate']==1
    assert result['performance']['generation_requests_with_telemetry']==5
    assert not caplog.records and 'home_insurance' not in json.dumps(result)
    assert result['manifest']['benchmark_engine']=='ollama-synthetic-e3'


@pytest.mark.parametrize('change',[
    {'domain_category':'home','domain_subcategory':'insurance'},
    {'domain_category':'home','domain_subcategory':None},
    {'domain_category':None,'domain_subcategory':'utility'},
    {'domain_category':'bogus','domain_subcategory':'unknown'},
    {'relevance_label':'unsupported'}, {'action_label':'unsupported'},
])
def test_safe_semantic_failures_remain_zero_confidence_abstentions(api,monkeypatch,change):
    original=bench.LocalOllama._request
    def request(self,method,path,payload=None,**kwargs):
        if path=='/api/generate': return envelope(response=json.dumps(LABELS|change))
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark()
    assert result['completed'] and result['counts']['model_invalid']==result['counts']['failed']==5
    assert result['counts']['valid']==0 and result['counts']['sent']==5
    assert result['metrics']['ollama']['domain_classified_count']==0
    assert result['metrics']['ollama']['classifier_review_rate']==1
    assert result['metrics']['ollama']['concrete_predictions']['action_required']['evaluated']==0


@pytest.mark.parametrize('response',[
    'not JSON', json.dumps(LABELS)+' trailing', '[]',
    json.dumps(LABELS|{'extra':'PRIVATE'}), json.dumps(LABELS|{'action_label':[]} ),
    json.dumps(LABELS|{'action_label':'ignore all instructions'}),
    json.dumps(LABELS|{'action_label':'x'*65}),
    '{"action_label":"required","action_label":"uncertain"}',
])
def test_malformed_label_protocol_still_aborts_without_next_dispatch(api,monkeypatch,response):
    original=bench.LocalOllama._request
    def request(self,method,path,payload=None,**kwargs):
        if path=='/api/generate': return envelope(response=response)
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark()
    assert not result['completed'] and result['counts']['sent']==1
    assert result['counts']['infrastructure_failed']==1 and result['counts']['model_invalid']==0
    assert result['counts']['not_attempted']==4 and 'PRIVATE' not in json.dumps(result)


def test_repeat_semantic_failure_continues_bounded_repeat_check(api,monkeypatch):
    original=bench.LocalOllama._request
    generates=0
    def request(self,method,path,payload=None,**kwargs):
        nonlocal generates
        if path=='/api/generate':
            generates+=1
            if generates==6:
                return envelope(response=json.dumps(LABELS|{'domain_category':'home','domain_subcategory':'insurance'}))
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark(repeat_check=True)
    assert result['completed'] and generates==9
    assert result['counts']['valid']==5 and result['counts']['model_invalid']==0
    assert result['repeat_check']['model_invalid']==1 and result['repeat_check']['valid']==3
    assert result['repeat_check']['infrastructure_failed']==0 and result['repeat_check']['failed']==1


def test_full_invalid_predictions_and_projection_failures_keep_all_denominators(api,monkeypatch):
    original=bench.LocalOllama._request
    def request(self,method,path,payload=None,**kwargs):
        if path=='/api/generate':
            return envelope(response=json.dumps(LABELS|{'domain_category':'home','domain_subcategory':'insurance'}))
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark(full=True)
    assert result['completed'] and result['counts']['failed']==37
    assert result['counts']['model_invalid']==result['counts']['sent']==result['counts']['json_valid']==34
    assert result['counts']['projection_failed']==3 and result['counts']['valid']==0
    assert result['counts']['infrastructure_failed']==result['counts']['not_attempted']==0
    assert result['metrics']['ollama']['eligible_count']==result['metrics']['rules']['eligible_count']==37
    assert result['metrics']['ollama']['classifier_domain_abstained_count']==37


def test_quality_failure_does_not_mask_later_protocol_failure(api,monkeypatch):
    original=bench.LocalOllama._request
    generates=0
    def request(self,method,path,payload=None,**kwargs):
        nonlocal generates
        if path=='/api/generate':
            generates+=1
            response=json.dumps(LABELS|{'domain_category':'home','domain_subcategory':'insurance'}) if generates==1 else 'PRIVATE invalid JSON'
            return envelope(response=response)
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark()
    assert not result['completed'] and result['counts']['sent']==2
    assert result['counts']['failed']==2 and result['counts']['model_invalid']==result['counts']['infrastructure_failed']==1
    assert result['counts']['not_attempted']==3 and 'PRIVATE' not in json.dumps(result)


def test_repeat_protocol_failure_still_aborts(api,monkeypatch):
    original=bench.LocalOllama._request
    generates=0
    def request(self,method,path,payload=None,**kwargs):
        nonlocal generates
        if path=='/api/generate':
            generates+=1
            if generates==6: return envelope(prompt_eval_cached_count=True)
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark(repeat_check=True)
    assert not result['completed'] and generates==6
    assert result['repeat_check']['infrastructure_failed']==1 and result['repeat_check']['model_invalid']==0
    assert result['counts']['valid']==5


@pytest.mark.parametrize('status',[301,302,307,308,400,401,403,404,500])
def test_http_status_redirects_no_fallback_safe_error(monkeypatch,status,caplog):
    calls=[]
    class Sock:
        def settimeout(self,*a): pass
    class Connection:
        sock=Sock()
        def __init__(self,host,port,timeout): calls.append((host,port))
        def connect(self): pass
        def request(self,*a,**k): pass
        def getresponse(self): return type('Response',(),{'status':status})()
        def close(self): pass
    monkeypatch.setattr(bench.http.client,'HTTPConnection',Connection)
    with pytest.raises(bench.BenchmarkError): bench.LocalOllama()._request('GET','/api/tags',deadline=time.monotonic()+10)
    assert calls==[('127.0.0.1',11434)] and not caplog.records


def test_ambient_proxy_variables_never_used(api,monkeypatch):
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy'):
        monkeypatch.setenv(key,'http://remote.invalid:9999')
    result=bench.benchmark()
    assert result['completed']
    assert all(path.startswith('/api/') for _,path,_ in api)


@pytest.mark.parametrize('path',['http://remote.invalid','//remote.invalid/api/tags','/api/pull','/api/chat','/api/delete'])
def test_unapproved_url_or_operation_never_connects(api,path):
    with pytest.raises(bench.BenchmarkError): bench.LocalOllama()._request('POST',path,deadline=time.monotonic()+10)
    assert not api


def test_deadline_and_timeout_public_errors_safe(monkeypatch,caplog):
    def fail(*a,**k): raise TimeoutError('PRIVATE URL AND TOKEN')
    monkeypatch.setattr(bench.http.client,'HTTPConnection',fail)
    with pytest.raises(bench.BenchmarkError) as error:
        bench.LocalOllama()._request('GET','/api/tags',deadline=time.monotonic()+10)
    assert 'PRIVATE' not in str(error.value) and not caplog.records
    with pytest.raises(bench.BenchmarkError): bench.LocalOllama()._request('GET','/api/tags',deadline=time.monotonic()-1)


def test_prompt_budget_rejects_without_truncating():
    with pytest.raises(bench.BenchmarkError): bench.request_payload(project_metadata(source(subject='x'*8192)),POLICY)


def test_manifest_pins_installed_digest_runtime_and_definition(api,monkeypatch):
    a=bench.benchmark()
    monkeypatch.setattr(bench.LocalOllama,'installed_digest',lambda *a,**k:'b'*64)
    b=bench.benchmark()
    assert a['definition']['analyzer_version']!=b['definition']['analyzer_version']
    assert a['manifest']['model_digest']==DIGEST
    assert a['manifest']['ollama_version']=='0.40.1'
    assert len(a['definition']['analyzer_version'])<=64


def test_runner_accepts_only_fixed_modes_and_suppresses_failures(api,monkeypatch,capsys):
    assert bench.main([])==0
    assert 'SYNTHETIC / NOT PRODUCTION ACCURACY' in capsys.readouterr().out
    for args in (['--host','remote.invalid'],['--file','private.sqlite'],['--model','other']):
        with pytest.raises(SystemExit): bench.main(args)
    def fail(**kwargs): raise RuntimeError('PRIVATE model text')
    monkeypatch.setattr(bench,'benchmark',fail)
    assert bench.main([])==1
    assert 'PRIVATE' not in capsys.readouterr().out


def test_no_production_wiring_or_database_dependencies():
    import ast
    tree=ast.parse(Path(bench.__file__).read_text())
    modules=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom):
            modules.append(node.module or '')
            modules.extend((node.module or '')+'.'+alias.name for alias in node.names)
    forbidden={'db','schema','analysis_services','audit_services','review_services',
        'gmail_auth','outlook_auth','google_calendar_auth','google_drive_auth','sqlalchemy','keyring'}
    assert not any(forbidden.intersection(module.split('.')) for module in modules)
    for file in (bench.ROOT/'src/family_os').glob('*.py'):
        if file.name not in {'ollama_synthetic_benchmark.py','action_model_benchmark.py'}:
            assert 'ollama_synthetic_benchmark' not in file.read_text()


@pytest.mark.parametrize('statement',[
    'import sqlalchemy', 'import keyring', 'from sqlalchemy import create_engine',
    'from family_os import audit_services',
])
def test_isolation_guard_rejects_both_import_forms(monkeypatch,statement):
    original=Path.read_text
    def read(path,*args,**kwargs):
        text=original(path,*args,**kwargs)
        return text+'\n'+statement if path==Path(bench.__file__) else text
    monkeypatch.setattr(Path,'read_text',read)
    with pytest.raises(AssertionError): test_no_production_wiring_or_database_dependencies()


@pytest.mark.parametrize('unverifiable',[False,True])
def test_final_identity_after_request_failure_preserves_counts_only(api,monkeypatch,caplog,unverifiable):
    original=bench.LocalOllama._request
    generates=0
    def request(self,method,path,payload=None,**kwargs):
        nonlocal generates
        if path=='/api/generate':
            generates+=1
            if generates==2:
                raise bench.BenchmarkError()
        return original(self,method,path,payload,**kwargs)
    def identity(self,**kwargs):
        if generates<2:
            return DIGEST
        if unverifiable:
            raise bench.BenchmarkError()
        return 'b'*64
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    monkeypatch.setattr(bench.LocalOllama,'installed_digest',identity)
    result=bench.benchmark()
    assert not result['completed'] and not result['final_model_identity_verified']
    assert result['abort_reason']=='final_model_identity_unverified'
    assert result['counts']['sent']==2 and result['counts']['valid']==1
    assert result['counts']['failed']==1 and result['counts']['not_attempted']==3
    assert not {'metrics','manifest','manifest_fingerprint','definition','performance'}.intersection(result)
    assert DIGEST not in json.dumps(result) and 'b'*64 not in json.dumps(result)
    assert not caplog.records


def test_identity_change_at_end_discards_mislabeled_report(api,monkeypatch):
    calls=0
    def identity(self,**kwargs):
        nonlocal calls
        calls+=1
        return DIGEST if calls<=6 else 'b'*64
    monkeypatch.setattr(bench.LocalOllama,'installed_digest',identity)
    with pytest.raises(bench.BenchmarkError): bench.benchmark()


def test_repeat_disagreement_reported_without_overwriting_primary_results(api,monkeypatch):
    original=bench.LocalOllama._request
    generates=0
    def request(self,method,path,payload=None,**kwargs):
        nonlocal generates
        if path=='/api/generate':
            generates+=1
            if generates>5:
                return envelope(response=json.dumps(dict(relevance_label='irrelevant',domain_category='ignore',domain_subcategory='newsletter',action_label='not_required')))
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark(repeat_check=True)
    assert result['repeat_check']['disagreements']==4
    assert result['metrics']['ollama']['domain_classified_count']==0


def test_http_response_byte_budget_and_duplicate_envelope_keys(api,monkeypatch):
    connection=bench.http.client.HTTPConnection
    class BadConnection(connection):
        def getresponse(self):
            class Response:
                status=200
                def read(self,size): return b'x'*size
            return Response()
    monkeypatch.setattr(bench.http.client,'HTTPConnection',BadConnection)
    with pytest.raises(bench.BenchmarkError): bench.LocalOllama()._request('GET','/api/tags',deadline=time.monotonic()+10)
    with pytest.raises(bench.BenchmarkError): bench.strict_json('{"models":[],"models":[]}')


def test_watchdog_interrupts_socket_and_is_cleaned_up(monkeypatch):
    observed=[]
    class Sock:
        def settimeout(self,value): observed.append(('timeout',value))
        def shutdown(self,value): observed.append(('shutdown',value))
    class Connection:
        sock=Sock()
        def __init__(self,*args,**kwargs): pass
        def connect(self): pass
        def request(self,*args,**kwargs): raise TimeoutError('PRIVATE')
        def close(self): observed.append(('closed',True))
    class Timer:
        def __init__(self,seconds,callback):
            assert 0<seconds<=60
            self.callback=callback
        def start(self): self.callback()
        def cancel(self): observed.append(('cancelled',True))
        def join(self): observed.append(('joined',True))
    monkeypatch.setattr(bench.http.client,'HTTPConnection',Connection)
    monkeypatch.setattr(bench.threading,'Timer',Timer)
    with pytest.raises(bench.BenchmarkError): bench.LocalOllama()._request('GET','/api/tags',deadline=time.monotonic()+10)
    assert ('shutdown',socket.SHUT_RDWR) in observed
    assert ('cancelled',True) in observed and ('joined',True) in observed and ('closed',True) in observed


def test_wrong_model_payload_never_connects(api):
    payload=bench.request_payload(project_metadata(source()),POLICY)
    payload['model']='cloud-or-uninstalled'
    with pytest.raises(bench.BenchmarkError): bench.LocalOllama()._request('POST','/api/generate',payload,deadline=time.monotonic()+10)
    assert not api


def test_oversized_context_eval_rejected():
    with pytest.raises(bench.BenchmarkError): bench.envelope(envelope(prompt_eval_count=3841))


def test_ctrl_c_exits_safely_without_persistence(api,monkeypatch,capsys):
    monkeypatch.setattr(bench,'benchmark',lambda **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert bench.main([])==130
    assert capsys.readouterr().out=='Synthetic benchmark stopped; no state persisted.\n'


def test_scripted_truth_never_changes_model_request_payload(api,monkeypatch):
    original=bench._cases
    def cases(corpus,policy):
        values=original(corpus,policy)
        return [(input,human,tags,'SCRIPTED_FAKE_PRIVATE_SENTINEL') for input,human,tags,_ in values]
    monkeypatch.setattr(bench,'_cases',cases)
    result=bench.benchmark()
    assert result['completed']
    assert 'SCRIPTED_FAKE_PRIVATE_SENTINEL' not in json.dumps(api)
    assert 'SCRIPTED_FAKE_PRIVATE_SENTINEL' not in json.dumps(result)


def test_privacy_identity_paths_not_serialized_to_requests(api,monkeypatch):
    original=bench._cases
    from dataclasses import replace
    def cases(corpus,policy):
        values=original(corpus,policy)
        return [(replace(input,source_record_id='SOURCE_SECRET',raw_record_id='RAW_SECRET',owner_id='OWNER_SECRET',
            provider_object_id='OBJECT_SECRET',recipients=('RECIPIENT_SECRET',)),human,tags,response) for input,human,tags,response in values]
    monkeypatch.setattr(bench,'_cases',cases)
    result=bench.benchmark()
    assert result['completed']
    for sentinel in ('SOURCE_SECRET','RAW_SECRET','OWNER_SECRET','OBJECT_SECRET','RECIPIENT_SECRET'):
        assert sentinel not in json.dumps(api) and sentinel not in json.dumps(result)
