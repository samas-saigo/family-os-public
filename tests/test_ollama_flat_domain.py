"""Opt-in Phase 2N: synthetic inputs and mocked HTTP only, no Ollama required."""
import json
from dataclasses import replace

import pytest

from family_os import ollama_synthetic_benchmark as bench
from family_os.analysis import AnalysisOutput, validate_output
from family_os.audit import HumanLabels
from test_ollama_synthetic_benchmark import api, envelope, POLICY, LABELS
from test_synthetic_reasoning import source

FLAT={'relevance_label':'uncertain','domain_path':None,'action_label':'uncertain'}


@pytest.fixture
def flat_api(api,monkeypatch):
    original=bench.http.client.HTTPConnection
    class Connection(original):
        def getresponse(self):
            response=super().getresponse()
            if self.path=='/api/generate':
                response.value['response']=json.dumps(FLAT)
            return response
    monkeypatch.setattr(bench.http.client,'HTTPConnection',Connection)
    return api


def test_complete_flat_enum_has_only_valid_paths_and_null():
    value=bench.schema(POLICY,'flat-domain')
    assert set(value['properties'])==bench.FLAT_KEYS
    assert value['additionalProperties'] is False and set(value['required'])==bench.FLAT_KEYS
    paths=value['properties']['domain_path']['enum']
    assert paths==sorted(category+'/'+child for category,children in POLICY.categories.items() for child in children)+[None]
    assert len(paths)==len(set(paths))
    assert 'home/insurance' not in paths and 'home/home_insurance' in paths
    assert value['properties']['relevance_label']==bench.schema(POLICY)['properties']['relevance_label']
    assert value['properties']['action_label']==bench.schema(POLICY)['properties']['action_label']


@pytest.mark.parametrize('path',list(bench.domain_paths(POLICY))+[None])
def test_each_flat_path_maps_exactly_and_passes_independent_validation(path):
    output=bench.labels(json.dumps(FLAT|{'domain_path':path}),source(),POLICY,'flat-domain')
    pair=bench.domain_paths(POLICY)[path] if path is not None else (None,None)
    assert (output.category,output.subcategory)==pair
    assert output.relevance_confidence==output.domain_confidence==output.action_confidence==0
    assert output.facts==() and validate_output(output,source(),POLICY)[0]['review_recommended']


@pytest.mark.parametrize('path',['home/insurance','unknown/utility','home/unknown','vehicle/home_insurance'])
def test_unallowlisted_bounded_paths_are_quality_failures_not_coerced(path):
    with pytest.raises(bench.ModelPredictionError) as error:
        bench.labels(json.dumps(FLAT|{'domain_path':path}),source(),POLICY,'flat-domain')
    assert error.value.reason=='invalid_domain_path'


@pytest.mark.parametrize('path',['home','home/utility/extra','/utility','home/','HOME/utility',
    'home/utility ', 'home%2Futility', 'http://remote.invalid',1,False,[],{},'x'*130])
def test_malformed_or_injected_paths_are_fail_fast_protocol_errors(path):
    with pytest.raises(bench.ProtocolError): bench.labels(json.dumps(FLAT|{'domain_path':path}),source(),POLICY,'flat-domain')


@pytest.mark.parametrize('response',[
    'not JSON', '[]', json.dumps(FLAT)+' trailing', json.dumps(LABELS),
    json.dumps(FLAT|{'domain_category':None}), json.dumps(FLAT|{'facts':[]}),
    json.dumps(FLAT|{'action_label':None}), json.dumps(FLAT|{'relevance_label':True}),
    '{"relevance_label":"uncertain","domain_path":null,"domain_path":"home/utility","action_label":"uncertain"}',
])
def test_flat_wire_tampering_and_half_null_fields_are_protocol_rejections(response):
    with pytest.raises(bench.ProtocolError): bench.labels(response,source(),POLICY,'flat-domain')


def test_prompt_changes_only_domain_representation_and_key_count():
    expected=bench.TEMPLATE.replace('the four JSON labels','the three JSON labels').replace(
        'Domain must be a valid category/child pair below, or both null.',
        'Domain must be one exact domain_path below, or null.').replace('Complete taxonomy:','Complete domain_path choices:')
    assert bench.system_prompt(POLICY,'flat-domain')==expected+bench.canonical_json([*bench.domain_paths(POLICY),None])
    for instructions in ('Relevance: relevant, irrelevant, uncertain. Action: required, not_required, uncertain.',
        bench.TEMPLATE[bench.TEMPLATE.index('A notification/receipt'):bench.TEMPLATE.index('Complete taxonomy:')]):
        assert instructions in bench.system_prompt(POLICY,'flat-domain')
    assert bench.digest(bench.system_prompt(POLICY))=='e9737d5378407743ed0db491b50edfdc05fbb2672726121b740170a368b01368'
    assert bench.digest(bench.schema(POLICY))=='b5f455d48da871a72f1cf794d851e3e3e770aed3cfa6773c018e895bc5cfb813'


def test_baseline_default_matches_explicit_baseline_and_retains_e3_identity(api):
    default=bench.benchmark()
    explicit=bench.benchmark(variant='baseline')
    for key in ('manifest','definition','counts','metrics','baseline_definition','corpus_digest','incremental_domain_coverage'):
        assert default[key]==explicit[key]
    assert default['manifest']['benchmark_engine']=='ollama-synthetic-e3'
    assert 'wire_variant' not in default['manifest'] and 'wire_schema' not in default['manifest']


def test_flat_smoke_and_full_use_same_corpus_limits_and_zero_confidence(flat_api):
    smoke=bench.benchmark(variant='flat-domain')
    full=bench.benchmark(full=True,variant='flat-domain')
    assert smoke['completed'] and smoke['counts']['sent']==smoke['counts']['valid']==5
    assert full['completed'] and full['counts']['selected']==37 and full['counts']['sent']==full['counts']['valid']==34
    assert full['counts']['projection_failed']==3 and full['metrics']['ollama']['classifier_review_rate']==1
    assert full['manifest']['benchmark_engine']=='ollama-flat-domain-e1'
    assert full['manifest']['wire_variant']=='flat-domain' and full['manifest']['wire_schema']=='three-label-domain-path-v1'
    assert len(full['definition']['analyzer_version'])<=64
    for _,path,payload in flat_api:
        if path=='/api/generate':
            assert payload['options']==bench.OPTIONS and payload['model']==bench.MODEL and not payload['stream']
            assert set(payload['format']['properties'])==bench.FLAT_KEYS
            assert all(term not in payload['prompt'] for term in ('expected','fake_response','source_record_id','raw_record_id'))
            assert len(payload['prompt'].encode())<=3072
    text=json.dumps(full)
    assert 'UNTRUSTED_METADATA_JSON' not in text and 'subject' not in text and 'sender' not in text


def test_variant_identity_differs_but_non_domain_options_are_identical(api,flat_api):
    flat=bench.benchmark(variant='flat-domain')
    assert flat['variant']=='flat-domain'
    baseline_manifest=flat['manifest']|{'benchmark_engine':'ollama-synthetic-e3',
        'prompt_digest':bench.digest(bench.system_prompt(POLICY)),'schema_digest':bench.digest(bench.schema(POLICY))}
    del baseline_manifest['wire_variant']; del baseline_manifest['wire_schema']
    assert bench.digest(baseline_manifest)!=flat['manifest_fingerprint']
    assert flat['manifest']['options_digest']==bench.digest(bench.OPTIONS)


def test_invalid_path_continues_with_reason_without_retry_or_coercion(flat_api,monkeypatch):
    original=bench.LocalOllama._request
    generates=0
    def request(self,method,path,payload=None,**kwargs):
        nonlocal generates
        if path=='/api/generate':
            generates+=1
            if generates==1: return envelope(response=json.dumps(FLAT|{'domain_path':'home/insurance'}))
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark(variant='flat-domain')
    assert result['completed'] and generates==5 and result['counts']['model_invalid']==1
    assert result['failure_reasons']['invalid_domain_path']==1 and sum(result['failure_reasons'].values())==1
    assert result['counts']['valid']==4 and result['counts']['json_valid']==5
    assert 'home/insurance' not in json.dumps(result)


@pytest.mark.parametrize('change,reason',[
    ({'domain_category':'home','domain_subcategory':'insurance'},'cross_taxonomy_pair'),
    ({'domain_category':'home','domain_subcategory':None},'incomplete_domain_pair'),
    ({'relevance_label':'unsupported'},'other_semantic'),
    ({'domain_category':'home','domain_subcategory':'unknown'},'other_semantic'),
])
def test_baseline_semantic_reason_counts_are_safe_aggregate_buckets(api,monkeypatch,change,reason):
    original=bench.LocalOllama._request
    def request(self,method,path,payload=None,**kwargs):
        if path=='/api/generate': return envelope(response=json.dumps(LABELS|change))
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark()
    assert result['completed'] and result['counts']['model_invalid']==5
    assert result['failure_reasons'][reason]==sum(result['failure_reasons'].values())==5


@pytest.mark.parametrize('failure',['protocol','request_identity_or_resource'])
def test_flat_fail_fast_failures_are_separate_from_quality(flat_api,monkeypatch,failure):
    original=bench.LocalOllama._request
    def request(self,method,path,payload=None,**kwargs):
        if path=='/api/generate':
            if failure=='protocol': return envelope(response=json.dumps(FLAT|{'extra':'PRIVATE'}))
            raise bench.BenchmarkError()
        return original(self,method,path,payload,**kwargs)
    monkeypatch.setattr(bench.LocalOllama,'_request',request)
    result=bench.benchmark(variant='flat-domain')
    assert not result['completed'] and result['counts']['sent']==1 and result['counts']['not_attempted']==4
    assert result['failure_reasons'][failure]==1 and result['counts']['model_invalid']==0
    assert 'PRIVATE' not in json.dumps(result)


def test_incremental_coverage_excludes_unknown_truth_and_rule_classifications():
    zero=AnalysisOutput('uncertain',0,None,None,0,'uncertain',0)
    home=replace(zero,category='home',subcategory='utility')
    wrong_child=replace(zero,category='home',subcategory='maintenance')
    decisive=HumanLabels('uncertain','home','utility','uncertain')
    unknown=HumanLabels('uncertain',None,None,'uncertain')
    cases=[(source(),h,(),None) for h in (decisive,decisive,decisive,unknown,decisive)]
    result=bench.incremental_domain_coverage(cases,[zero,zero,zero,zero,home],[home,wrong_child,zero,home,home])
    assert result==dict(rules_abstained_count=4,human_decisive_count=3,human_unknown_count=1,
        model_classified_count=3,decisive_model_classified_count=2,correct_count=1,wrong_count=1,
        decisive_model_abstained_count=1,unknown_human_model_classified_count=1,
        correct_coverage=1/3,selective_accuracy=.5)
    empty=bench.incremental_domain_coverage([],[],[])
    assert empty['correct_coverage'] is None and empty['selective_accuracy'] is None
    with pytest.raises(bench.BenchmarkError): bench.incremental_domain_coverage(cases,[],[])


def test_fixed_corpus_prompt_budget_is_not_widened():
    count=0
    for input,_,_,_ in bench._cases(bench.strict_json(bench.FIXTURE.read_text()),POLICY):
        try: projection=bench.project_metadata(input)
        except bench.AnalysisError: continue
        count+=1
        assert len(bench.request_payload(projection,POLICY,'flat-domain')['prompt'].encode())<=bench.PROMPT_BYTES==3072
    assert count==34
    with pytest.raises(bench.BenchmarkError):
        bench.request_payload(bench.project_metadata(source(subject='x'*3000)),POLICY,'flat-domain')


@pytest.mark.parametrize('variant',['remote','BASELINE','flat_domain',None,False,[]])
def test_unapproved_variants_never_dispatch(api,variant):
    with pytest.raises(bench.BenchmarkError): bench.benchmark(variant=variant)
    assert not api


def test_cli_defaults_and_opt_in_modes_only(monkeypatch,capsys):
    calls=[]
    def run(**kwargs):
        calls.append(kwargs)
        return {'completed':True,'notice':'SYNTHETIC'}
    monkeypatch.setattr(bench,'benchmark',run)
    assert bench.main([])==0
    assert calls[-1]['variant']=='baseline'
    assert bench.main(['--variant','flat-domain','--full'])==0
    assert calls[-1]==dict(full=True,repeat_check=False,variant='flat-domain',model=bench.MODEL)
    with pytest.raises(SystemExit): bench.main(['--variant','cloud'])
    assert 'subject' not in capsys.readouterr().out


def test_flat_repeats_keep_unique_case_denominators(flat_api):
    result=bench.benchmark(variant='flat-domain',repeat_check=True)
    assert result['completed'] and result['counts']['valid']==5
    assert result['repeat_check']['valid']==result['repeat_check']['sent']==4
    assert result['metrics']['ollama']['eligible_count']==5
    assert len([path for _,path,_ in flat_api if path=='/api/generate'])==9


def test_flat_expected_labels_fake_scripts_and_identity_never_enter_requests(flat_api,monkeypatch):
    first=bench.benchmark(variant='flat-domain')
    prompts=[payload['prompt'] for _,path,payload in flat_api if path=='/api/generate']
    flat_api.clear()
    original=bench._cases
    def cases(corpus,policy):
        return [(replace(input,source_record_id='SOURCE_SECRET',raw_record_id='RAW_SECRET',
            owner_id='OWNER_SECRET',provider_object_id='OBJECT_SECRET',recipients=('RECIPIENT_SECRET',)),
            HumanLabels('uncertain',None,None,'uncertain'),tags,'FAKE_SECRET') for input,human,tags,fake in original(corpus,policy)]
    monkeypatch.setattr(bench,'_cases',cases)
    second=bench.benchmark(variant='flat-domain')
    assert [payload['prompt'] for _,path,payload in flat_api if path=='/api/generate']==prompts
    for secret in ('SOURCE_SECRET','RAW_SECRET','OWNER_SECRET','OBJECT_SECRET','RECIPIENT_SECRET','FAKE_SECRET'):
        assert secret not in json.dumps(flat_api) and secret not in json.dumps(second)
    assert first['manifest']==second['manifest']


def test_action_and_relevance_error_rates_and_false_irrelevant_are_decisive_only():
    zero=AnalysisOutput('uncertain',0,None,None,0,'uncertain',0)
    irrelevant=replace(zero,relevance_label='irrelevant',action_label='not_required')
    cases=[(source(),human,(),None) for human in (
        HumanLabels('relevant',None,None,'required'), HumanLabels('irrelevant',None,None,'not_required'),
        HumanLabels('uncertain',None,None,'uncertain'))]
    metrics=bench.metric_records(cases,[irrelevant,irrelevant,irrelevant],POLICY)
    assert metrics['relevance_decisive_count']==metrics['action_decisive_count']==2
    assert metrics['relevance_error_rate']==metrics['action_error_rate']==.5
    assert metrics['false_irrelevant_count']==1 and metrics['action_required_miss_count']==1
    empty=bench.metric_records([],[],POLICY)
    assert empty['relevance_error_rate'] is None and empty['action_error_rate'] is None
