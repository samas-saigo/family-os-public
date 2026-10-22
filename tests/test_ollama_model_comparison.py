"""Phase 2P compatibility contracts; all actual HTTP connections are mocked."""
import json
import time

import pytest

from family_os import ollama_synthetic_benchmark as bench
from test_ollama_synthetic_benchmark import api, envelope, POLICY, LABELS, DIGEST
from test_ollama_flat_domain import FLAT
from test_synthetic_reasoning import source

CANDIDATE_DIGEST='b'*64


@pytest.fixture
def models_api(api,monkeypatch):
    original=bench.http.client.HTTPConnection
    class Connection(original):
        def request(self,method,path,body=None,headers=None):
            super().request(method,path,body,headers)
            self.payload=json.loads(body) if body else None
        def getresponse(self):
            response=super().getresponse()
            if self.path=='/api/tags':
                response.value['models'].append({'name':bench.CANDIDATE_MODEL,'digest':CANDIDATE_DIGEST})
            elif self.path=='/api/generate':
                response.value['model']=self.payload['model']
                response.value['response']=json.dumps(FLAT if 'domain_path' in self.payload['format']['properties'] else LABELS)
                if self.payload['model']==bench.CANDIDATE_MODEL:
                    response.value['thinking']=''
            elif self.path=='/api/ps':
                response.value['models'].append({'name':bench.CANDIDATE_MODEL,'digest':CANDIDATE_DIGEST,
                    'size':3100000000,'size_vram':3100000000})
            return response
    monkeypatch.setattr(bench.http.client,'HTTPConnection',Connection)
    return api


def candidate(**kwargs):
    return bench.benchmark(variant='flat-domain',model=bench.CANDIDATE_MODEL,**kwargs)


def payload(model=bench.CANDIDATE_MODEL):
    return bench.request_payload(bench.project_metadata(source()),POLICY,'flat-domain',model)


def test_baseline_wire_bytes_and_manifest_unchanged_with_explicit_default_model(models_api):
    for variant in bench.VARIANTS:
        default=bench.benchmark(variant=variant)
        requests=[p for _,path,p in models_api if path=='/api/generate']
        models_api.clear()
        explicit=bench.benchmark(variant=variant,model=bench.MODEL)
        assert [json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False) for _,path,p in models_api if path=='/api/generate']==[
            json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False) for p in requests]
        for key in ('manifest','definition','metrics','counts','incremental_domain_coverage','failure_reasons'):
            assert default[key]==explicit[key]
        assert default['manifest']['benchmark_engine']==('ollama-synthetic-e3' if variant=='baseline' else 'ollama-flat-domain-e1')
        assert not {'thinking_setting','thinking_location','comparison_contract'}.intersection(default['manifest'])
        assert all(set(p)=={'model','prompt','format','stream','options','keep_alive'} for p in requests)
        models_api.clear()
    assert bench.digest(bench.system_prompt(POLICY))=='e9737d5378407743ed0db491b50edfdc05fbb2672726121b740170a368b01368'
    assert bench.digest(bench.schema(POLICY))=='b5f455d48da871a72f1cf794d851e3e3e770aed3cfa6773c018e895bc5cfb813'


def test_candidate_changes_only_model_and_top_level_think():
    old=payload(bench.MODEL)
    new=payload()
    assert new==old|{'model':bench.CANDIDATE_MODEL,'think':False}
    assert new['think'] is False and 'think' not in new['options']
    assert new['options']==bench.OPTIONS and new['format']==bench.schema(POLICY,'flat-domain')


def test_candidate_smoke_full_and_repeats_keep_fixed_corpus_and_metrics(models_api):
    smoke=candidate()
    full=candidate(full=True)
    repeats=candidate(repeat_check=True)
    assert smoke['completed'] and smoke['counts']['sent']==smoke['counts']['valid']==5
    assert full['completed'] and full['counts']['selected']==37
    assert full['counts']['sent']==full['counts']['valid']==34 and full['counts']['projection_failed']==3
    assert full['counts']['infrastructure_failed']==0 and full['metrics']['ollama']['classifier_review_rate']==1
    assert repeats['repeat_check']['sent']==repeats['repeat_check']['valid']==4
    assert repeats['metrics']['ollama']['eligible_count']==5
    assert full['manifest']['model_digest']==CANDIDATE_DIGEST
    assert full['performance']['residency_observation']['observed_vram_fraction']==1
    assert full['performance']['generated_tokens_per_second']==pytest.approx(40/.6)
    for _,path,p in models_api:
        if path=='/api/generate':
            assert p['model']==bench.CANDIDATE_MODEL and p['think'] is False and 'think' not in p['options']
            assert len(p['prompt'].encode())<=3072 and set(p['format']['properties'])==bench.FLAT_KEYS
    text=json.dumps(full)
    assert all(term not in text for term in ('PRIVATE','UNTRUSTED_METADATA_JSON','subject','sender'))


def test_candidate_versions_identify_digest_runtime_thinking_and_wire_config(models_api,monkeypatch):
    old=bench.benchmark(variant='flat-domain')
    new=candidate()
    a,b=old['manifest'],new['manifest']
    for key in ('prompt_digest','schema_digest','options_digest','taxonomy_digest','threshold_digest','rules_fingerprint',
        'projection_contract_digest','projection_schema','projection_engine','ollama_version','wire_schema'):
        assert a[key]==b[key]
    assert b['model']==bench.CANDIDATE_MODEL and b['model_digest']==CANDIDATE_DIGEST and b['ollama_version']=='0.40.1'
    assert b['thinking_setting'] is False and b['thinking_location']=='top-level'
    assert b['generation_endpoint']=='/api/generate' and b['benchmark_engine']=='ollama-qwen35-flat-domain-e1'
    assert b['comparison_contract']=='local-model-comparison-v1'
    assert old['definition']['analyzer_version']!=new['definition']['analyzer_version']
    assert len(new['definition']['analyzer_version'])<=64
    monkeypatch.setattr(bench.LocalOllama,'installed_digest',lambda self,**kwargs:'c'*64)
    changed=candidate()
    assert changed['definition']['analyzer_version']!=new['definition']['analyzer_version']


@pytest.mark.parametrize('model',['qwen3.5','qwen3.5:latest','qwen3.5:4b-q4_k_m','remote/model','http://remote.invalid',None,False,[]])
def test_unknown_models_fail_before_lookup_or_request(models_api,model):
    with pytest.raises(bench.BenchmarkError): bench.benchmark(variant='flat-domain',model=model)
    with pytest.raises(bench.BenchmarkError): bench.LocalOllama(model)
    assert not models_api


def test_candidate_requires_explicit_flat_domain_and_matching_client(models_api):
    with pytest.raises(bench.BenchmarkError): bench.benchmark(model=bench.CANDIDATE_MODEL)
    with pytest.raises(bench.BenchmarkError): bench.request_payload(bench.project_metadata(source()),POLICY,model=bench.CANDIDATE_MODEL)
    with pytest.raises(bench.BenchmarkError): candidate(transport=bench.LocalOllama())
    with pytest.raises(bench.BenchmarkError): bench.benchmark(transport=bench.LocalOllama(bench.CANDIDATE_MODEL))
    assert not models_api


@pytest.mark.parametrize('thinking',[True,0,1,None,'false',[],{}])
def test_wrong_top_level_think_is_rejected_before_network(models_api,thinking):
    value=payload()|{'think':thinking}
    with pytest.raises(bench.BenchmarkError):
        bench.LocalOllama(bench.CANDIDATE_MODEL)._request('POST','/api/generate',value,deadline=time.monotonic()+10)
    assert not models_api


def test_missing_misplaced_or_baseline_think_never_dispatches(models_api):
    missing=payload(); del missing['think']
    misplaced=payload(); del misplaced['think']; misplaced['options']=bench.OPTIONS|{'think':False}
    both=payload(); both['options']=bench.OPTIONS|{'think':False}
    for value in (missing,misplaced,both):
        with pytest.raises(bench.BenchmarkError):
            bench.LocalOllama(bench.CANDIDATE_MODEL)._request('POST','/api/generate',value,deadline=time.monotonic()+10)
    with pytest.raises(bench.BenchmarkError):
        bench.LocalOllama()._request('POST','/api/generate',payload(bench.MODEL)|{'think':False},deadline=time.monotonic()+10)
    assert not models_api


@pytest.mark.parametrize('thinking',['PRIVATE reasoning',' ',None,False,0,[],{}])
def test_candidate_thinking_field_rejected_without_leaking(models_api,monkeypatch,caplog,thinking):
    original=bench.LocalOllama._request
    def request(self,method,path,value=None,**kwargs):
        if path=='/api/generate':
            return envelope(model=bench.CANDIDATE_MODEL,response=json.dumps(FLAT),thinking=thinking)
        return original(self,method,path,value,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=candidate()
    assert not result['completed'] and result['counts']['sent']==1 and result['counts']['not_attempted']==4
    assert result['failure_reasons']['protocol']==1 and result['counts']['model_invalid']==0
    assert 'PRIVATE' not in json.dumps(result) and not caplog.records


@pytest.mark.parametrize('response',['',' ', '<think>PRIVATE</think>'+json.dumps(FLAT),
    '<THINK>PRIVATE</THINK>'+json.dumps(FLAT),json.dumps(FLAT)+'</think>',
    json.dumps(FLAT|{'domain_path':'<think>PRIVATE</think>'}),
    'PRIVATE non-JSON reasoning',json.dumps(FLAT)+' trailing'])
def test_reasoning_or_missing_final_json_is_fail_fast_never_stripped(models_api,monkeypatch,response):
    original=bench.LocalOllama._request
    def request(self,method,path,value=None,**kwargs):
        if path=='/api/generate': return envelope(model=bench.CANDIDATE_MODEL,response=response)
        return original(self,method,path,value,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=candidate()
    assert not result['completed'] and result['counts']['sent']==1 and result['counts']['not_attempted']==4
    assert result['counts']['infrastructure_failed']==result['failure_reasons']['protocol']==1
    assert 'PRIVATE' not in json.dumps(result)


@pytest.mark.parametrize('thinking_present',[False,True])
def test_absent_or_explicit_empty_thinking_with_valid_json_is_accepted(thinking_present):
    value=envelope(model=bench.CANDIDATE_MODEL,response=json.dumps(FLAT))
    if thinking_present: value['thinking']=''
    assert bench.envelope(value,bench.CANDIDATE_MODEL)['eval_count']==40


@pytest.mark.parametrize('change',[{'model':bench.MODEL},{'done':False},{'done_reason':'length'},
    {'extra':'PRIVATE'},{'response':{}},{'response':'x'*4097},{'eval_count':257},{'prompt_eval_cached_count':True}])
def test_candidate_preserves_strict_envelope_identity_schema_and_limits(change):
    with pytest.raises(bench.ProtocolError):
        bench.envelope(envelope(model=bench.CANDIDATE_MODEL,response=json.dumps(FLAT))|change,bench.CANDIDATE_MODEL)


def test_candidate_taxonomy_invalid_pair_is_counted_not_repaired(models_api,monkeypatch):
    original=bench.LocalOllama._request
    def request(self,method,path,value=None,**kwargs):
        if path=='/api/generate': return envelope(model=bench.CANDIDATE_MODEL,response=json.dumps(FLAT|{'domain_path':'home/insurance'}))
        return original(self,method,path,value,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=candidate()
    assert result['completed'] and result['counts']['model_invalid']==5 and result['counts']['valid']==0
    assert result['failure_reasons']['invalid_domain_path']==5 and result['metrics']['ollama']['classifier_domain_abstained_count']==5


@pytest.mark.parametrize('status',[400,422])
def test_unsupported_thinking_and_format_status_aborts_without_fallback(models_api,monkeypatch,status):
    original=bench.http.client.HTTPConnection
    class Connection(original):
        def getresponse(self):
            response=super().getresponse()
            if self.path=='/api/generate': response.status=status
            return response
    monkeypatch.setattr(bench.http.client,'HTTPConnection',Connection)
    result=candidate()
    assert not result['completed'] and result['counts']['sent']==result['counts']['infrastructure_failed']==1
    assert result['counts']['valid']==0 and result['counts']['model_invalid']==0
    assert len([path for _,path,_ in models_api if path=='/api/generate'])==1
    assert all(path in {'/api/tags','/api/version','/api/generate','/api/ps'} for _,path,_ in models_api)


@pytest.mark.parametrize('path',['/api/show','/api/chat','/api/pull','//remote.invalid/api/generate','http://remote.invalid'])
def test_new_model_cannot_expand_http_operations_or_remote_endpoints(models_api,path):
    with pytest.raises(bench.BenchmarkError):
        bench.LocalOllama(bench.CANDIDATE_MODEL)._request('POST',path,payload(),deadline=time.monotonic()+10)
    assert not models_api


def test_selected_candidate_digest_changes_stop_before_dispatch(models_api,monkeypatch):
    calls=0
    def identity(self,**kwargs):
        nonlocal calls
        calls+=1
        return CANDIDATE_DIGEST if calls==1 else 'c'*64
    monkeypatch.setattr(bench.LocalOllama,'installed_digest',identity)
    result=candidate()
    assert not result['completed'] and result['counts']['sent']==0
    assert result['abort_reason']=='final_model_identity_unverified'
    assert not {'manifest','metrics','definition','performance'}.intersection(result)


def test_wrong_response_model_is_not_a_model_quality_failure(models_api,monkeypatch):
    original=bench.LocalOllama._request
    def request(self,method,path,value=None,**kwargs):
        if path=='/api/generate': return envelope(response=json.dumps(FLAT))
        return original(self,method,path,value,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=candidate()
    assert not result['completed'] and result['counts']['infrastructure_failed']==1
    assert result['counts']['model_invalid']==0 and result['counts']['sent']==1


def test_candidate_truth_and_fake_scripts_remain_evaluation_only(models_api,monkeypatch):
    original=bench._cases
    def cases(corpus,policy):
        return [(input,human,tags,'FAKE_PRIVATE_SECRET') for input,human,tags,fake in original(corpus,policy)]
    monkeypatch.setattr(bench,'_cases',cases)
    result=candidate()
    assert result['completed']
    for _,path,value in models_api:
        if path=='/api/generate':
            assert all(term not in value['prompt'] for term in ('fake_response','expected','FAKE_PRIVATE_SECRET','source_record_id','raw_record_id'))
    assert 'FAKE_PRIVATE_SECRET' not in json.dumps(result)


def test_cli_allowlist_and_candidate_requires_explicit_variant(models_api,capsys):
    assert bench.main(['--model',bench.CANDIDATE_MODEL])==1
    assert not models_api
    assert bench.main(['--model',bench.CANDIDATE_MODEL,'--variant','flat-domain'])==0
    assert 'SYNTHETIC / NOT PRODUCTION ACCURACY' in capsys.readouterr().out
    for tag in ('qwen3.5:latest','cloud/model'):
        with pytest.raises(SystemExit): bench.main(['--model',tag])


@pytest.mark.parametrize('models',[
    [{'name':bench.MODEL,'digest':DIGEST}],
    [{'name':bench.CANDIDATE_MODEL,'digest':'bad'}],
    [{'name':bench.CANDIDATE_MODEL,'digest':CANDIDATE_DIGEST}]*2,
])
def test_candidate_missing_or_ambiguous_artifact_never_generates(models_api,monkeypatch,models):
    original=bench.LocalOllama._request
    def request(self,method,path,value=None,**kwargs):
        if path=='/api/tags': return {'models':models}
        return original(self,method,path,value,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    with pytest.raises(bench.BenchmarkError): candidate()
    assert not [path for _,path,_ in models_api if path=='/api/generate']


def test_candidate_context_budget_and_repeat_reasoning_fail_closed(models_api,monkeypatch):
    original=bench.LocalOllama._request
    generates=0
    def request(self,method,path,value=None,**kwargs):
        nonlocal generates
        if path=='/api/generate':
            generates+=1
            if generates==6:
                return envelope(model=bench.CANDIDATE_MODEL,response=json.dumps(FLAT),thinking='PRIVATE')
        return original(self,method,path,value,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=candidate(repeat_check=True)
    assert not result['completed'] and result['counts']['valid']==5 and generates==6
    assert result['repeat_check']['infrastructure_failed']==result['repeat_failure_reasons']['protocol']==1
    assert 'PRIVATE' not in json.dumps(result)
    with pytest.raises(bench.ProtocolError):
        bench.envelope(envelope(model=bench.CANDIDATE_MODEL,response=json.dumps(FLAT),prompt_eval_count=3841),bench.CANDIDATE_MODEL)


def test_candidate_model_tampering_is_blocked_at_http_boundary(models_api):
    client=bench.LocalOllama(bench.CANDIDATE_MODEL)
    client._model='remote-or-uninstalled'
    with pytest.raises(bench.BenchmarkError): client._request('GET','/api/tags',deadline=time.monotonic()+10)
    assert not models_api
