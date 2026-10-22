"""Fixed development-only manual runner: actual HTTP boundary is always mocked."""
import ast
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from family_os import action_model_benchmark as runner
from family_os.analysis import AnalysisOutput, validate_output
from family_os.audit import HumanLabels
from test_ollama_synthetic_benchmark import api, envelope, POLICY, DIGEST
from test_ollama_model_comparison import models_api, CANDIDATE_DIGEST
from test_ollama_flat_domain import FLAT


@pytest.fixture
def cases():
    return runner.select_development(runner.dataset.load_dataset()[0],full=True)


def output(action='uncertain',relevance='uncertain',domain=None):
    return AnalysisOutput(relevance,0,*(domain or (None,None)),0,action,0,())


def response_patch(monkeypatch,fn):
    original=runner.local.LocalOllama._request
    count=0
    def request(self,method,path,value=None,**kwargs):
        nonlocal count
        if path=='/api/generate':
            count+=1
            return fn(count,value)
        return original(self,method,path,value,**kwargs)
    monkeypatch.setattr(runner.local.LocalOllama,'_request',request)


@pytest.mark.parametrize('model',runner.local.MODELS)
@pytest.mark.parametrize('full',[False,True])
def test_fixed_development_smoke_full_and_shared_wire_contract(models_api,model,full,cases):
    report=runner.benchmark(model=model,full=full)
    chosen=runner.select_development(runner.dataset.load_dataset()[0],full=full)
    payloads=[p for _,path,p in models_api if path=='/api/generate']
    assert len(payloads)==(60 if full else 5)==report['counts']['valid']==report['counts']['sent']
    assert report['completed'] and report['final_model_identity_verified'] and not report['holdout_inference']
    assert report['counts']['not_attempted']==report['counts']['model_invalid']==report['counts']['infrastructure_failed']==0
    assert payloads==[runner.local.request_payload(runner.projection(c),POLICY,'flat-domain',model) for c in chosen]
    assert all(p['options']==runner.local.OPTIONS and p['format']==runner.local.schema(POLICY,'flat-domain') for p in payloads)
    assert report['manifest']['model_digest']==(DIGEST if model==runner.local.MODEL else CANDIDATE_DIGEST)
    assert report['manifest']['split']=='development' and report['manifest']['development_case_count']==60
    assert report['manifest']['development_projection_digest']==runner.DEVELOPMENT_PROJECTION_SHA256
    assert report['metrics']['model']['classifier_review_rate']==1
    assert report['metrics']['rules']['required_recall']==0
    assert report['performance']['generated_tokens_per_second']==pytest.approx(40/.6)
    assert {path for _,path,_ in models_api}=={'/api/tags','/api/version','/api/generate','/api/ps'}
    assert all('think' not in p['options'] for p in payloads)
    assert all((p.get('think') is False) if model==runner.local.CANDIDATE_MODEL else 'think' not in p for p in payloads)
    if full:
        assert report['distributions']['action']==dict(required=20,not_required=20,uncertain=20)
        assert report['metrics']['model']['triads']['selected_triads']==16
        assert report['metrics']['model']['triads']['selected_pairs']==48
    else:
        assert {c.input.provider for c in chosen}=={'gmail','outlook','google_calendar','google_drive'}
        assert [c.id for c in chosen]==list(runner.SMOKE_IDS)
        assert sorted(c.expected.action_label for c in chosen)==['not_required','required','required','uncertain','uncertain']


def test_holdout_never_projected_or_dispatched(models_api,monkeypatch):
    original=runner.dataset.model_projection
    observed=[]
    def project(case):
        assert case.split=='development'
        observed.append(case.id)
        return original(case)
    monkeypatch.setattr(runner.dataset,'model_projection',project)
    report=runner.benchmark(full=True)
    assert report['counts']['sent']==60 and len(set(observed))==60
    assert all('holdout' not in p['prompt'] for _,path,p in models_api if path=='/api/generate')


def test_projection_is_annotation_independent_and_holdout_fails_before_projection(cases,monkeypatch):
    case=cases[0]
    changed=replace(case,expected=HumanLabels('irrelevant',None,None,'uncertain'),
        annotations={'PRIVATE_LABEL_RATIONALE':'PRIVATE_LABEL_RATIONALE'})
    assert runner.projection(changed)==runner.projection(case)
    monkeypatch.setattr(runner.dataset,'model_projection',lambda c:pytest.fail('must reject before projection'))
    with pytest.raises(runner.local.BenchmarkError):runner.projection(replace(case,split='holdout'))
    with pytest.raises(runner.local.BenchmarkError):runner.projection(case.input)


@pytest.mark.parametrize('tamper',['missing','duplicate','holdout_relabel','projection','manifest'])
def test_dataset_fail_closed_before_any_http(models_api,monkeypatch,tamper):
    cases,policy,manifest=runner.dataset.load_dataset()
    if tamper=='missing':cases=cases[1:]
    elif tamper=='duplicate':cases=cases+(cases[0],)
    elif tamper=='holdout_relabel':
        dev=next(c for c in cases if c.split=='development');hold=next(c for c in cases if c.split=='holdout')
        cases=tuple(replace(hold,id=c.id,split='development') if c is dev else c for c in cases)
    elif tamper=='projection':
        c=next(c for c in cases if c.split=='development')
        cases=tuple(replace(c,input=replace(c.input,subject='PRIVATE TAMPER')) if item is c else item for item in cases)
    else:manifest=manifest|{'extra':'PRIVATE'}
    monkeypatch.setattr(runner.dataset,'load_dataset',lambda:(cases,policy,manifest))
    with pytest.raises(runner.local.BenchmarkError):runner.benchmark(full=True)
    assert not models_api


def test_requests_reports_and_logs_never_contain_annotations_ids_or_input_text(models_api,caplog,cases):
    report=runner.benchmark(full=True)
    text=json.dumps(report)
    for c in cases:
        assert c.id not in text and c.input.subject not in text
        if c.input.sender:assert c.input.sender not in text
    assert 'UNTRUSTED_METADATA' not in text and not caplog.records
    for _,path,p in models_api:
        if path=='/api/generate':
            assert all(key not in p['prompt'] for key in ('expected','rationale','evidence_refs','ambiguity_note',
                'truth_certainty','counterfactual_group','cue_field','source_record_id','raw_record_id','owner_id','split'))
            assert all(c.id not in p['prompt'] for c in cases)


@pytest.mark.parametrize('arg',['--holdout','--final-holdout','--split','--input','--file','--url','--host',
    '--variant','--repeat-check','--database','--household'])
def test_cli_has_no_holdout_or_arbitrary_input_endpoint_options(arg,models_api):
    with pytest.raises(SystemExit):runner.main([arg])
    assert not models_api


@pytest.mark.parametrize('model',['qwen3:latest','qwen3.5','remote/model','http://remote.invalid',None,False,[]])
def test_unknown_models_before_lookup_or_network(models_api,model):
    with pytest.raises(runner.local.BenchmarkError):runner.benchmark(model=model)
    assert not models_api


@pytest.mark.parametrize('full',[None,1,'yes',[],{}])
def test_full_requires_explicit_boolean(full,models_api):
    with pytest.raises(runner.local.BenchmarkError):runner.benchmark(full=full)
    assert not models_api


def test_exact_client_and_matching_model_required(models_api):
    with pytest.raises(runner.local.BenchmarkError):runner.benchmark(transport=object())
    with pytest.raises(runner.local.BenchmarkError):runner.benchmark(transport=runner.local.LocalOllama(runner.local.CANDIDATE_MODEL))
    assert not models_api


def test_configuration_and_selection_version_identity(models_api,monkeypatch):
    default=runner.benchmark();full=runner.benchmark(full=True)
    candidate=runner.benchmark(model=runner.local.CANDIDATE_MODEL)
    for key in ('prompt_digest','schema_digest','options_digest','taxonomy_digest','threshold_digest','rubric_digest',
        'development_input_digest','development_annotated_digest','rules_fingerprint'):
        assert default['manifest'][key]==candidate['manifest'][key]
    assert default['manifest']['selected_count']==5 and full['manifest']['selected_count']==60
    assert len({r['definition']['analyzer_version'] for r in (default,full,candidate)})==3
    assert len(default['definition']['analyzer_version'])<=64
    monkeypatch.setattr(runner.local.LocalOllama,'installed_digest',lambda self,**k:'c'*64)
    changed=runner.benchmark()
    assert changed['definition']!=default['definition']
    monkeypatch.setattr(runner.local.LocalOllama,'runtime_version',lambda self,**k:'0.99.1')
    assert runner.benchmark()['definition']!=changed['definition']


def test_exact_cohorts_confusion_false_positives_uncertainty_and_provider_metrics(cases):
    chosen=tuple(replace(c,expected=HumanLabels(rel,'home','utility',action)) for c,rel,action in zip(cases[:6],
        ['relevant']*4+['uncertain','irrelevant'],['required','required','not_required','uncertain','uncertain','not_required']))
    outputs=(output('required','relevant',('home','utility')),output('uncertain','irrelevant'),
        output('required','relevant'),output('not_required','relevant'),output('uncertain'),output('not_required','irrelevant'))
    m=runner.metrics(chosen,outputs,('valid',)*6,POLICY)
    assert m['required_recall']==.5 and m['required_miss_count']==1 and m['required_false_irrelevant_count']==1
    assert m['not_required_false_positive_count']==1 and m['not_required_false_positive_rate']==.5
    assert m['uncertain_concrete_count']==1 and m['uncertainty_preserved_rate']==.5
    assert m['action_confusion']['required']==dict(required=1,not_required=0,uncertain=1)
    assert m['action_confusion']['uncertain']==dict(required=0,not_required=1,uncertain=1)
    assert m['decisive_domain_coverage']==1/6 and m['domain_selective_accuracy']==1
    assert m['relevance_accuracy']==4/5 and m['action_accuracy']==2/4
    assert sum(p['selected_count'] for p in m['providers'].values())==6
    assert all('providers' not in p for p in m['providers'].values())


def test_invalid_unattempted_not_synthetic_abstentions_and_zero_denominators(cases):
    chosen=tuple(replace(c,expected=HumanLabels('relevant',None,None,'required')) for c in cases[:3])
    m=runner.metrics(chosen,(output('required'),None,None),('valid','model_invalid','not_attempted'),POLICY)
    assert m['required_recall']==.5 and m['required_miss_count']==1
    assert m['action_cohorts']['required']==dict(selected=3,evaluated=2,valid=1,invalid=1,not_evaluated=1)
    assert sum(m['action_confusion']['required'].values())==1 and m['action_confusion']['required']['uncertain']==0
    assert m['uncertainty_preserved_rate'] is None and m['not_required_false_positive_rate'] is None
    assert m['decisive_domain_coverage'] is None
    empty=runner.metrics((),(),(),POLICY)
    assert empty['required_recall'] is None and empty['classifier_domain_abstention_rate'] is None
    assert empty['triads']['pair_change_rate'] is None


def test_counterfactual_accuracy_and_sensitivity_are_separate(cases):
    perfect=tuple(output(c.expected.action_label) for c in cases)
    triads=runner.triad_metrics(cases,perfect)
    assert triads['selected_triads']==triads['scored_triads']==triads['correct_triads']==16
    assert triads['selected_pairs']==triads['correct_pairs']==triads['changed_prediction_pairs']==48
    swap={'required':'not_required','not_required':'uncertain','uncertain':'required'}
    wrong=runner.triad_metrics(cases,tuple(output(swap[c.expected.action_label]) for c in cases))
    assert wrong['distinct_prediction_triads']==16 and wrong['changed_prediction_pairs']==48
    assert wrong['correct_triads']==wrong['correct_pairs']==0
    partial=list(perfect);partial[0]=None
    assert runner.triad_metrics(cases,partial)['scored_pairs']<48


def test_validated_predictions_are_zero_confidence_empty_facts_review_only(cases):
    for prediction in (FLAT,FLAT|{'domain_path':'home/utility','action_label':'required','relevance_label':'relevant'}):
        result=runner.local.labels(json.dumps(prediction),cases[0].input,POLICY,'flat-domain')
        assert result.relevance_confidence==result.domain_confidence==result.action_confidence==0
        assert not result.facts and validate_output(result,cases[0].input,POLICY)[0]['review_recommended']


@pytest.mark.parametrize('change,reason',[({'domain_path':'home/insurance'},'invalid_domain_path'),
    ({'relevance_label':'alien'},'other_semantic'),({'action_label':'execute'},'other_semantic')])
def test_semantic_invalid_is_explicit_quality_failure_and_continues(models_api,monkeypatch,change,reason):
    response_patch(monkeypatch,lambda i,p:envelope(response=json.dumps(FLAT|change if i==1 else FLAT)))
    report=runner.benchmark()
    assert report['completed'] and report['counts']['sent']==5 and report['counts']['valid']==4
    assert report['counts']['model_invalid']==report['failure_reasons'][reason]==1
    assert report['counts']['infrastructure_failed']==0 and report['counts']['json_valid']==5
    assert report['metrics']['model']['required_miss_count']==2
    assert report['metrics']['model']['action_cohorts']['required']['invalid']==1
    assert report['label_validity_rate']==.8 and report['json_validity_rate']==1


@pytest.mark.parametrize('text',['not JSON','{}',json.dumps(FLAT|{'extra':'PRIVATE'}),
    '{"action_label":"required","action_label":"uncertain"}',json.dumps(FLAT)+' trailing',
    '<think>PRIVATE</think>'+json.dumps(FLAT),'x'*4097])
def test_protocol_fail_fast_no_coerced_predictions_or_private_leak(models_api,monkeypatch,caplog,text):
    response_patch(monkeypatch,lambda i,p:envelope(response=text))
    report=runner.benchmark()
    assert not report['completed'] and report['counts']['sent']==1 and report['counts']['not_attempted']==4
    assert report['counts']['infrastructure_failed']==1 and report['counts']['model_invalid']==0
    assert report['metrics_scope']=='partial_observed' and report['metrics']['model']['required_recall'] is None
    assert report['metrics']['model']['classifier_domain_abstention_rate'] is None
    assert 'PRIVATE' not in json.dumps(report) and not caplog.records


@pytest.mark.parametrize('change',[{'done':False},{'done_reason':None},{'done_reason':'length'},{'model':'other'},
    {'extra':'PRIVATE'},{'eval_count':257},{'prompt_eval_cached_count':True},{'response':{}},{'thinking':'PRIVATE'}])
def test_envelope_security_resources_completion_are_still_fail_fast(models_api,monkeypatch,change):
    response_patch(monkeypatch,lambda i,p:envelope(**change))
    report=runner.benchmark()
    assert not report['completed'] and report['counts']['infrastructure_failed']==1
    assert report['counts']['not_attempted']==4 and report['counts']['model_invalid']==0
    assert 'PRIVATE' not in json.dumps(report)


def test_missing_done_reason_and_telemetry_absence_are_distinct(models_api,monkeypatch):
    response_patch(monkeypatch,lambda i,p:{'model':p['model'],'done':True,'response':json.dumps(FLAT)})
    assert not runner.benchmark()['completed']
    response_patch(monkeypatch,lambda i,p:{'model':p['model'],'done':True,'done_reason':'stop','response':json.dumps(FLAT)})
    report=runner.benchmark()
    assert report['completed'] and report['performance']['generated_tokens_per_second'] is None
    assert report['performance']['total_duration_seconds']['count']==0


def test_partial_infrastructure_failure_keeps_only_observed_metrics(models_api,monkeypatch):
    def fail(i,p):
        if i==3:raise RuntimeError('PRIVATE http://secret/token subject')
        return envelope(response=json.dumps(FLAT))
    response_patch(monkeypatch,fail)
    report=runner.benchmark()
    assert report['counts']['sent']==3 and report['counts']['valid']==2 and report['counts']['not_attempted']==2
    assert report['counts']['infrastructure_failed']==1 and report['final_model_identity_verified']
    assert report['metrics']['model']['scored_count']==2 and report['metrics']['rules']['selected_count']==5
    assert report['metrics']['model']['required_miss_count']==1
    assert report['performance']['request_wall_seconds']['count']==3
    assert 'PRIVATE' not in json.dumps(report)


@pytest.mark.parametrize('abort_first',[False,True])
def test_final_changed_or_unverifiable_model_never_attributes_partial_metrics(models_api,monkeypatch,abort_first):
    calls=0
    def digest(self,**kwargs):
        nonlocal calls
        calls+=1
        return DIGEST if calls<=(2 if abort_first else 6) else 'b'*64
    monkeypatch.setattr(runner.local.LocalOllama,'installed_digest',digest)
    if abort_first:
        def fail(i,p):raise RuntimeError('PRIVATE')
        response_patch(monkeypatch,fail)
    report=runner.benchmark()
    assert not report['completed'] and not report['final_model_identity_verified']
    assert report['abort_reason']=='final_model_identity_unverified'
    assert all(key not in report for key in ('metrics','manifest','definition','performance'))
    assert report['counts']['sent']==(1 if abort_first else 5)
    assert 'PRIVATE' not in json.dumps(report)


def test_changed_identity_before_first_dispatch_no_post(models_api,monkeypatch):
    count=0
    def digest(self,**kwargs):
        nonlocal count
        count+=1
        return DIGEST if count==1 else 'b'*64
    monkeypatch.setattr(runner.local.LocalOllama,'installed_digest',digest)
    report=runner.benchmark()
    assert report['counts']['sent']==0 and report['counts']['not_attempted']==4
    assert not any(path=='/api/generate' for _,path,_ in models_api)
    assert not report['final_model_identity_verified']


def test_missing_initial_model_identity_is_safe_setup_error(models_api,monkeypatch):
    def fail(self,**kwargs):raise RuntimeError('PRIVATE digest')
    monkeypatch.setattr(runner.local.LocalOllama,'installed_digest',fail)
    assert runner.main([])==1
    assert not any(path=='/api/generate' for _,path,_ in models_api)


def test_deadline_is_bounded_without_sleeping(models_api,monkeypatch):
    now=runner.time.monotonic()
    clock=iter([now,now+runner.local.RUN_SECONDS+1,now+runner.local.RUN_SECONDS+2])
    monkeypatch.setattr(runner,'time',SimpleNamespace(monotonic=lambda:next(clock)))
    report=runner.benchmark()
    assert report['counts']['sent']==0 and not report['final_model_identity_verified']
    assert not any(path=='/api/generate' for _,path,_ in models_api)


def test_optional_residency_failure_not_replacing_safe_primary_failure(models_api,monkeypatch):
    def fail(self,*args,**kwargs):raise RuntimeError('PRIVATE residency')
    monkeypatch.setattr(runner.local.LocalOllama,'residency',fail)
    report=runner.benchmark()
    assert report['completed'] and report['performance']['residency_observation'] is None
    assert 'PRIVATE' not in json.dumps(report)


def test_cli_aggregate_success_failure_and_interrupt(models_api,monkeypatch,capsys):
    assert runner.main([])==0
    report=json.loads(capsys.readouterr().out)
    assert report['counts']['valid']==5 and report['holdout_inference'] is False
    def fail(**kwargs):raise RuntimeError('PRIVATE exception')
    monkeypatch.setattr(runner,'benchmark',fail)
    assert runner.main([])==1 and 'PRIVATE' not in capsys.readouterr().out
    def interrupt(**kwargs):raise KeyboardInterrupt
    monkeypatch.setattr(runner,'benchmark',interrupt)
    assert runner.main([])==130 and 'no state persisted' in capsys.readouterr().out


def test_isolation_both_import_forms_no_production_dependencies_or_wiring():
    imports=[]
    for node in ast.walk(ast.parse(Path(runner.__file__).read_text())):
        if isinstance(node,ast.Import):imports.extend(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom):
            if node.module:imports.append(node.module)
            imports.extend(alias.name for alias in node.names if not node.module)
    assert set(imports)<={'argparse','collections','itertools','time','action_evaluation','ollama_synthetic_benchmark',
        'analysis','audit','metadata_classifier'}
    for path in (runner.dataset.ROOT/'src/family_os').rglob('*.py'):
        if path.name in {'action_model_benchmark.py','qwen3_prompt_experiment.py'}:continue
        assert 'action_model_benchmark' not in path.read_text()


@pytest.mark.parametrize('method,path',[('GET','/api/pull'),('POST','/api/chat'),('POST','/api/tags'),
    ('GET','http://remote.invalid'),('GET','/api/show'),('GET','/api/generate'),('POST','/api/delete')])
def test_reused_transport_forbids_extra_operations_before_connect(models_api,method,path):
    with pytest.raises(runner.local.BenchmarkError):
        runner.local.LocalOllama()._request(method,path,deadline=runner.time.monotonic()+10)
    assert not models_api


@pytest.mark.parametrize('status',[302,307,429,500])
def test_http_failure_no_retry_or_redirect_private_body_suppressed(models_api,monkeypatch,status):
    original=runner.local.http.client.HTTPConnection
    class Connection(original):
        def getresponse(self):
            response=super().getresponse()
            if self.path=='/api/generate':
                response.status=status
                response.value={'PRIVATE':'PRIVATE subject token'}
            return response
    monkeypatch.setattr(runner.local.http.client,'HTTPConnection',Connection)
    result=runner.benchmark()
    assert not result['completed'] and result['counts']['sent']==1 and result['counts']['not_attempted']==4
    assert sum(path=='/api/generate' for _,path,_ in models_api)==1
    assert 'PRIVATE' not in json.dumps(result)


def test_timeout_safe_no_retry(models_api,monkeypatch):
    original=runner.local.http.client.HTTPConnection
    class Connection(original):
        def getresponse(self):
            if self.path=='/api/generate':raise TimeoutError('PRIVATE subject')
            return super().getresponse()
    monkeypatch.setattr(runner.local.http.client,'HTTPConnection',Connection)
    result=runner.benchmark()
    assert not result['completed'] and result['counts']['sent']==1 and result['counts']['infrastructure_failed']==1
    assert 'PRIVATE' not in json.dumps(result)


def test_fixed_readonly_files_and_no_runtime_state_access(models_api,monkeypatch):
    original_open=Path.open
    read=[]
    allowed={runner.dataset.DIRECTORY/name for name in ('development.json','holdout.json','rubric.json','manifest.json')}
    allowed|={runner.dataset.ROOT/'config/classification.yaml',runner.dataset.ROOT/'config/metadata-classifier.yaml',
              runner.dataset.ROOT/'fixtures/metadata-reasoning.synthetic.json'}
    def opened(path,mode='r',*args,**kwargs):
        assert not any(char in mode for char in 'wax+')
        assert path in allowed
        read.append(path)
        return original_open(path,mode,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened)
    result=runner.benchmark()
    assert result['completed'] and set(read)<=allowed
    assert runner.dataset.DIRECTORY/'holdout.json' in read  # integrity only; never model-dispatched


def test_model_calls_are_frozen_projections_not_whole_cases(models_api,monkeypatch):
    original=runner.local.request_payload
    seen=[]
    def payload(value,policy,variant,model):
        assert type(value) is runner.dataset.MetadataProjection
        assert not hasattr(value,'expected') and not hasattr(value,'annotations') and not hasattr(value,'input')
        seen.append(value)
        return original(value,policy,variant,model)
    monkeypatch.setattr(runner.local,'request_payload',payload)
    assert runner.benchmark()['completed'] and len(seen)>=5


def test_projection_failure_before_network_no_partial_report(models_api,monkeypatch,capsys):
    def reject(c):raise ValueError('PRIVATE projection')
    monkeypatch.setattr(runner.dataset,'model_projection',reject)
    assert runner.main([])==1 and 'PRIVATE' not in capsys.readouterr().out and not models_api


def test_label_invalid_not_counted_as_correct_uncertainty_or_valid_coverage(cases):
    chosen=(replace(cases[0],expected=HumanLabels('uncertain',None,None,'uncertain')),)
    m=runner.metrics(chosen,(None,),('model_invalid',),POLICY)
    assert m['semantic_validity']==m['observed_valid_coverage']==0
    assert m['uncertainty_preserved_count']==m['uncertain_concrete_count']==0
    assert m['uncertainty_preserved_rate'] is None and m['classifier_review_rate'] is None
