"""Phase 2S: all model requests use mocked HTTP; no live inference or household data."""
import ast
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from family_os import qwen3_prompt_experiment as experiment
from family_os.audit import HumanLabels
from test_action_model_benchmark import output, response_patch
from test_ollama_synthetic_benchmark import api, envelope, POLICY, DIGEST
from test_ollama_flat_domain import flat_api, FLAT

PROMPT_PINS={
    'baseline':'ce795381831bceed14df9ca29a30135d0b1293d1060e6a510208925bf5fac14e',
    'relevance-clarified':'ffa86c21d6993fe79afad31a9dec569ea5e405996c2cd6f3eb30a7402061d2e7',
    'action-evidence':'17b9ebaba795938a405652993950ea983c45938b1fbebd53aea1b717a2a6f0d8',
    'calendar-status':'9a6f3a95e18cc90f0587f41a79070db986e287141697b4f129b94cef2d20873c',
}


@pytest.fixture
def cases():
    return experiment.control.select_development(experiment.dataset.load_dataset()[0],full=True)


@pytest.mark.parametrize('variant',experiment.VARIANTS)
@pytest.mark.parametrize('full',[False,True])
def test_independent_fixed_smoke_full_unchanged_wire_configuration(flat_api,variant,full):
    report=experiment.benchmark(variant=variant,full=full)
    chosen=experiment.control.select_development(experiment.dataset.load_dataset()[0],full=full)
    payloads=[p for _,path,p in flat_api if path=='/api/generate']
    assert report['completed'] and report['final_model_identity_verified'] and not report['holdout_inference']
    assert len(payloads)==report['counts']['valid']==report['counts']['sent']==(60 if full else 5)
    for c,p in zip(chosen,payloads):
        old=experiment.local.request_payload(experiment.control.projection(c),POLICY,'flat-domain')
        assert p==old|{'prompt':old['prompt'].replace('\nUNTRUSTED_METADATA_JSON:\n',experiment.EDITS[variant]+'\nUNTRUSTED_METADATA_JSON:\n',1)}
        assert p['options']=={'temperature':0,'seed':0,'num_ctx':4096,'num_predict':256}
        assert p['model']=='qwen3:4b-instruct' and p['keep_alive']=='1m' and p['stream'] is False
        assert p['format']==experiment.local.schema(POLICY,'flat-domain') and 'think' not in p
        assert len(p['prompt'].encode())<=3072
    assert report['manifest']['experiment_variant']==variant and report['manifest']['prompt_digest']==PROMPT_PINS[variant]
    assert report['manifest']['experiment_plan_version']=='qwen3-prompt-plan-v1'
    assert report['metrics']['model']['classifier_review_rate']==1
    assert report['diagnostics']['required_to_not_required_count']==0
    assert report['diagnostics']['required_to_uncertain_count']==(20 if full else 2)
    assert report['performance']['generated_tokens_per_second']==pytest.approx(40/.6)
    assert sum(row['selected_count'] for row in report['diagnostics']['calendar_status'].values())==(12 if full else 2)
    if full:
        assert report['diagnostics']['triads']['selected_triads']==16
        assert report['diagnostics']['triads']['selected_pairs']==48
        assert report['metrics']['model']['action_cohorts']['required']['selected']==20


def test_baseline_byte_equivalent_to_historical_phase2r_for_all_cases(flat_api,cases):
    for c in cases:
        projected=experiment.control.projection(c)
        a=experiment.request_payload(projected,POLICY)
        b=experiment.local.request_payload(projected,POLICY,'flat-domain')
        assert json.dumps(a,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()==json.dumps(b,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    historical=experiment.control.benchmark(full=True)
    flat_api.clear()
    new=experiment.benchmark(full=True)
    assert new['counts']==historical['counts'] and new['metrics']==historical['metrics']
    for key in historical['manifest']:
        if key not in {'engine_version','metrics_version'}:assert new['manifest'][key]==historical['manifest'][key]


@pytest.mark.parametrize('variant',experiment.VARIANTS)
def test_pinned_literal_hashes_and_edit_isolation(variant,cases):
    base=experiment.local.system_prompt(POLICY,'flat-domain')
    text=experiment.system_prompt(POLICY,variant)
    assert text==base+experiment.EDITS[variant]
    assert experiment.local.digest(text)==PROMPT_PINS[variant]==experiment.PROMPT_SHA256[variant]
    assert experiment.local.digest(experiment.EDITS[variant])==experiment.EDIT_SHA256[variant]
    for other in experiment.VARIANTS:
        if other not in (variant,'baseline'):assert experiment.EDITS[other] not in text
    for c in cases:
        assert c.id not in text and c.input.subject not in text
    assert all(term not in text for term in ('counterfactual_group','rationale','evidence_refs','expected','20/20','60 cases'))


@pytest.mark.parametrize('variant',experiment.VARIANTS[1:])
def test_changed_literal_fails_preflight_before_network(flat_api,monkeypatch,variant):
    monkeypatch.setitem(experiment.EDITS,variant,'PRIVATE modified prompt')
    with pytest.raises(experiment.local.BenchmarkError):experiment.benchmark(variant=variant)
    assert not flat_api


def test_oversized_prompt_no_budget_expansion_or_network(flat_api,monkeypatch):
    edit=' x'*2000
    monkeypatch.setitem(experiment.EDITS,'action-evidence',edit)
    monkeypatch.setitem(experiment.EDIT_SHA256,'action-evidence',experiment.local.digest(edit))
    monkeypatch.setitem(experiment.PROMPT_SHA256,'action-evidence',experiment.local.digest(experiment.local.system_prompt(POLICY,'flat-domain')+edit))
    with pytest.raises(experiment.local.BenchmarkError):experiment.benchmark(variant='action-evidence')
    assert not flat_api and experiment.local.PROMPT_BYTES==3072 and experiment.local.OPTIONS['num_ctx']==4096


@pytest.mark.parametrize('arg',['--holdout','--final-holdout','--all','--prompt','--input','--file','--host','--url',
    '--database','--household','--repeat-check','--reference'])
def test_cli_has_no_open_inputs_or_hidden_inference(arg,flat_api):
    with pytest.raises(SystemExit):experiment.main([arg])
    assert not flat_api


@pytest.mark.parametrize('variant',['stacked','relevance+action','flat-domain','',None,True,[]])
def test_unknown_variants_fail_before_lookup_or_network(variant,flat_api):
    with pytest.raises(experiment.local.BenchmarkError):experiment.benchmark(variant=variant)
    assert not flat_api


@pytest.mark.parametrize('model',['qwen3.5:4b-q4_K_M','qwen3:latest','remote/model','http://remote.invalid',None,False,[]])
def test_only_frozen_qwen3_model_allowed(model,flat_api):
    with pytest.raises(experiment.local.BenchmarkError):experiment.benchmark(model=model)
    assert not flat_api


def test_cli_rejects_qwen35_before_dispatch(flat_api):
    with pytest.raises(SystemExit):experiment.main(['--model','qwen3.5:4b-q4_K_M'])
    assert not flat_api


def test_holdout_never_projected_dispatched_or_scored(flat_api,monkeypatch):
    original=experiment.dataset.model_projection
    seen=[]
    def project(c):
        assert c.split=='development'
        seen.append(c.id)
        return original(c)
    monkeypatch.setattr(experiment.dataset,'model_projection',project)
    report=experiment.benchmark(full=True,variant='calendar-status')
    assert report['counts']['sent']==60 and len(set(seen))==60
    assert report['diagnostics']['selected_count']==60 and report['manifest']['split']=='development'
    assert all('holdout' not in p['prompt'] for _,path,p in flat_api if path=='/api/generate')


def test_whole_case_or_holdout_never_enters_prompt_builder(cases):
    with pytest.raises(experiment.local.BenchmarkError):experiment.request_payload(cases[0],POLICY)
    with pytest.raises(experiment.local.BenchmarkError):experiment.request_payload(cases[0].input,POLICY)
    with pytest.raises(experiment.local.BenchmarkError):experiment.control.projection(replace(cases[0],split='holdout'))
    changed=replace(cases[0],expected=HumanLabels('irrelevant',None,None,'uncertain'),annotations={'PRIVATE':'PRIVATE'})
    assert experiment.request_payload(experiment.control.projection(changed),POLICY,'action-evidence')==experiment.request_payload(experiment.control.projection(cases[0]),POLICY,'action-evidence')


def test_no_oracle_or_source_text_in_output_errors_logs(flat_api,cases,caplog):
    report=experiment.benchmark(full=True,variant='action-evidence')
    text=json.dumps(report)
    for c in cases:
        assert c.id not in text and c.input.subject not in text
        if c.input.sender:assert c.input.sender not in text
    assert not caplog.records and 'UNTRUSTED_METADATA_JSON' not in text
    for _,path,p in flat_api:
        if path=='/api/generate':
            assert all(word not in p['prompt'] for word in ('rationale','expected','evidence_refs','ambiguity_notes',
                'source_record_id','raw_record_id','truth_certainty','counterfactual_group'))


def test_diagnostics_exact_crosschecks_required_clearance_uncertainty_and_domain(cases):
    chosen=tuple(replace(c,expected=HumanLabels('relevant','home','utility',action)) for c,action in zip(cases[:5],
        ('required','required','required','not_required','uncertain')))
    predicted=(output('not_required','irrelevant'),output('uncertain'),output('required','irrelevant',('home','utility')),
               output('required','relevant',('travel','hotel')),output('required','relevant'))
    d=experiment.diagnostics(chosen,predicted,('valid',)*5,POLICY)
    assert d['required_to_not_required_count']==d['required_to_uncertain_count']==1
    assert d['required_to_not_required_rate']==d['required_to_uncertain_rate']==1/3
    assert d['required_recall']==1/3 and d['required_false_irrelevant_count']==2
    assert d['predicted_required_and_irrelevant_count']==1
    assert d['required_truth_relevance_by_action']['irrelevant']['not_required']==1
    assert d['uncertain_to_required_count']==1 and d['uncertain_to_required_rate']==1
    assert d['domain_known_valid_count']==5 and d['domain_abstained_on_known_truth']==3
    assert d['domain_wrong_on_known_truth']==1 and d['domain_undercoverage_rate']==.6
    assert sum(p['selected_count'] for p in d['providers'].values())==5


def test_calendar_status_and_cue_cohorts_exact_with_null_denominators(cases):
    predicted=tuple(output(c.expected.action_label) for c in cases)
    d=experiment.diagnostics(cases,predicted,('valid',)*60,POLICY)
    for status in ('confirmed','cancelled','tentative'):
        row=d['calendar_status'][status]
        assert row['selected_count']==3
        assert sum(sum(v.values()) for v in row['action_confusion'].values())==3
    assert d['calendar_status']['confirmed']['required_recall']==1
    assert d['calendar_status']['cancelled']['required_recall'] is None
    assert d['calendar_status']['cancelled']['required_to_not_required_rate'] is None
    assert d['cue_family']['raw_metadata.status']['selected_count']==9
    assert d['cue_family']['subject']['selected_count']==39
    assert d['cue_family']['standalone']['selected_count']==12
    assert d['triads']['correct_triads']==16 and d['triads']['correct_pairs']==48


def test_partial_invalid_results_not_fabricated_abstentions(flat_api,monkeypatch):
    def respond(i,p):
        if i==1:return envelope(response=json.dumps(FLAT|{'domain_path':'home/insurance'}))
        if i==3:raise RuntimeError('PRIVATE token subject')
        return envelope(response=json.dumps(FLAT))
    response_patch(monkeypatch,respond)
    report=experiment.benchmark(variant='action-evidence')
    assert not report['completed'] and report['metrics_scope']=='partial_observed'
    assert report['counts']['model_invalid']==report['counts']['infrastructure_failed']==1
    assert report['counts']['not_attempted']==2 and report['counts']['valid']==1
    d=report['diagnostics']
    assert d['required_miss_count']==1 and d['required_to_uncertain_count']==0
    assert d['action_cohorts']['required']['invalid']==1
    assert d['action_cohorts']['required']['not_evaluated']==1
    assert d['domain_known_valid_count']==1 and 'PRIVATE' not in json.dumps(report)


@pytest.mark.parametrize('response',['not JSON',json.dumps(FLAT)+' trailing','<think>PRIVATE</think>'+json.dumps(FLAT),
    json.dumps(FLAT|{'extra':'PRIVATE'}),'x'*4097])
def test_bad_json_thinking_truncation_fail_fast_no_retry(flat_api,monkeypatch,response):
    response_patch(monkeypatch,lambda i,p:envelope(response=response))
    report=experiment.benchmark(variant='calendar-status')
    assert not report['completed'] and report['counts']['sent']==1 and report['counts']['not_attempted']==4
    assert report['counts']['infrastructure_failed']==1 and report['counts']['model_invalid']==0
    assert report['metrics']['model']['required_recall'] is None
    assert 'PRIVATE' not in json.dumps(report)


@pytest.mark.parametrize('change',[{'done':False},{'done_reason':'length'},{'done_reason':None},{'model':'other'},
    {'thinking':'PRIVATE'},{'eval_count':257},{'prompt_eval_cached_count':True},{'extra':'PRIVATE'}])
def test_strict_envelope_security_preserved(flat_api,monkeypatch,change):
    response_patch(monkeypatch,lambda i,p:envelope(response=json.dumps(FLAT))|change)
    report=experiment.benchmark(variant='relevance-clarified')
    assert not report['completed'] and report['counts']['infrastructure_failed']==1 and report['counts']['sent']==1
    assert 'PRIVATE' not in json.dumps(report)


def test_identity_change_after_request_failure_suppresses_attribution(flat_api,monkeypatch):
    calls=0
    def digest(self,**kwargs):
        nonlocal calls
        calls+=1
        return DIGEST if calls<=2 else 'b'*64
    def fail(i,p):raise RuntimeError('PRIVATE')
    monkeypatch.setattr(experiment.local.LocalOllama,'installed_digest',digest)
    response_patch(monkeypatch,fail)
    report=experiment.benchmark(variant='action-evidence')
    assert not report['final_model_identity_verified'] and report['counts']['sent']==1
    assert all(k not in report for k in ('manifest','metrics','diagnostics','performance','definition'))


def test_predispatch_model_mismatch_never_sends(flat_api,monkeypatch):
    count=0
    def digest(self,**kwargs):
        nonlocal count
        count+=1
        return DIGEST if count==1 else 'b'*64
    monkeypatch.setattr(experiment.local.LocalOllama,'installed_digest',digest)
    report=experiment.benchmark()
    assert report['counts']['sent']==0 and not report['final_model_identity_verified']
    assert not any(path=='/api/generate' for _,path,_ in flat_api)


def test_monotonic_deadline_no_real_sleep(flat_api,monkeypatch):
    now=experiment.time.monotonic();clock=iter((now,now+601,now+602))
    monkeypatch.setattr(experiment,'time',SimpleNamespace(monotonic=lambda:next(clock)))
    report=experiment.benchmark()
    assert report['counts']['sent']==0 and not report['final_model_identity_verified']


def test_fingerprints_separate_variants_and_manual_repeated_configurations(flat_api):
    reports=[experiment.benchmark(variant=v) for v in experiment.VARIANTS]
    assert len({r['manifest_fingerprint'] for r in reports})==4
    assert len({r['definition']['analyzer_version'] for r in reports})==4
    repeat=experiment.benchmark()
    assert repeat['manifest']==reports[0]['manifest'] and repeat['manifest_fingerprint']==reports[0]['manifest_fingerprint']
    check=experiment.check_reproducibility(reports[0],repeat)
    assert check['same_configuration'] and check['aggregate_metrics_equal']
    assert not check['per_case_determinism_established']
    with pytest.raises(experiment.local.BenchmarkError):experiment.check_reproducibility(reports[0],reports[1])


def test_manual_compatible_baseline_tradeoff_table_never_selects_winner(flat_api):
    a=experiment.benchmark(full=True);b=experiment.benchmark(full=True,variant='action-evidence')
    table=experiment.compare_reports(a,b)
    assert table['selected_count']==60 and table['comparison']=='baseline-only' and table['winner'] is None
    assert table['tradeoffs']['required_recall']['delta']==0
    assert table['tradeoffs']['domain_selective_accuracy']['delta'] is None
    assert table['observed_denominators']['baseline']['relevance_decisive_count']==58


@pytest.mark.parametrize('change',['digest','runtime','selection','partial','invalid','tampered','nonbaseline','different-cohorts'])
def test_incompatible_references_do_not_invent_improvement(flat_api,change):
    a=experiment.benchmark();b=experiment.benchmark(variant='action-evidence')
    if change in ('digest','runtime','selection'):
        key={'digest':'model_digest','runtime':'ollama_version','selection':'selection_digest'}[change]
        b['manifest'][key]='changed';b['manifest_fingerprint']=experiment.local.digest(b['manifest'])
    elif change=='partial':b['completed']=False
    elif change=='invalid':b['counts']['valid']=4;b['counts']['model_invalid']=1
    elif change=='tampered':b['manifest_fingerprint']='PRIVATE'
    elif change=='nonbaseline':a=b
    else:b['metrics']['model']['action_cohorts']['required']['valid']=1
    with pytest.raises(experiment.local.BenchmarkError):experiment.compare_reports(a,b)


def test_cli_safe_aggregate_success_failure_interrupt(flat_api,monkeypatch,capsys):
    assert experiment.main(['--variant','calendar-status'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['manifest']['experiment_variant']=='calendar-status' and result['counts']['valid']==5
    def fail(**kwargs):raise RuntimeError('PRIVATE prompt')
    monkeypatch.setattr(experiment,'benchmark',fail)
    assert experiment.main([])==1 and 'PRIVATE' not in capsys.readouterr().out
    def interrupt(**kwargs):raise KeyboardInterrupt
    monkeypatch.setattr(experiment,'benchmark',interrupt)
    assert experiment.main([])==130 and 'no state persisted' in capsys.readouterr().out


def test_isolation_no_production_imports_or_wiring():
    imports=[]
    for node in ast.walk(ast.parse(Path(experiment.__file__).read_text())):
        if isinstance(node,ast.Import):imports.extend(a.name for a in node.names)
        elif isinstance(node,ast.ImportFrom):
            if node.module:imports.append(node.module)
            else:imports.extend(a.name for a in node.names)
    assert set(imports)<={'argparse','collections','json','time','action_model_benchmark','analysis','audit','metadata_classifier'}
    for path in (experiment.dataset.ROOT/'src/family_os').rglob('*.py'):
        if path.name in {'qwen3_prompt_experiment.py','paired_synthetic_diagnosis.py'}:continue
        assert 'qwen3_prompt_experiment' not in path.read_text()


@pytest.mark.parametrize('method,path',[('POST','/api/pull'),('POST','/api/chat'),('GET','/api/show'),
    ('GET','http://remote.invalid'),('POST','/api/delete')])
def test_local_transport_rejects_forbidden_operation_before_network(flat_api,method,path):
    with pytest.raises(experiment.local.BenchmarkError):
        experiment.local.LocalOllama()._request(method,path,deadline=experiment.time.monotonic()+10)
    assert not flat_api


@pytest.mark.parametrize('status',[302,307,429,500])
def test_transport_failures_stop_no_retry_redirect_or_private_leak(flat_api,monkeypatch,status):
    original=experiment.local.http.client.HTTPConnection
    class Connection(original):
        def getresponse(self):
            response=super().getresponse()
            if self.path=='/api/generate':
                response.status=status;response.value={'error':'PRIVATE URL token'}
            return response
    monkeypatch.setattr(experiment.local.http.client,'HTTPConnection',Connection)
    report=experiment.benchmark(variant='action-evidence')
    assert not report['completed'] and report['counts']['sent']==1
    assert sum(path=='/api/generate' for _,path,_ in flat_api)==1
    assert 'PRIVATE' not in json.dumps(report)


def test_fixed_readonly_files_no_runtime_database_access(flat_api,monkeypatch):
    original=Path.open
    allowed={experiment.dataset.DIRECTORY/name for name in ('development.json','holdout.json','rubric.json','manifest.json')}
    allowed|={experiment.dataset.ROOT/'fixtures/metadata-reasoning.synthetic.json',
        experiment.dataset.ROOT/'config/classification.yaml',experiment.dataset.ROOT/'config/metadata-classifier.yaml'}
    def opened(path,mode='r',*args,**kwargs):
        assert path in allowed and not any(char in mode for char in 'wax+')
        return original(path,mode,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened)
    assert experiment.benchmark(variant='calendar-status')['completed']


def test_phase2r_remains_unchanged_and_qwen35_supported(flat_api):
    # Phase 2P/2R behavior has no dependency on the experiment's edit registry.
    # Candidate exercised by existing model-comparison tests; pure request identity here.
    cases=experiment.control.select_development(experiment.dataset.load_dataset()[0],full=False)
    projected=experiment.control.projection(cases[0])
    payload=experiment.local.request_payload(projected,POLICY,'flat-domain',experiment.local.CANDIDATE_MODEL)
    assert payload['think'] is False and payload['model']==experiment.local.CANDIDATE_MODEL
    assert 'Action clarification' not in payload['prompt']
    assert 'Relevance clarification' not in payload['prompt']
    assert 'Calendar clarification' not in payload['prompt']


def test_tampered_development_projection_fails_before_http(flat_api,monkeypatch):
    all_cases,policy,manifest=experiment.dataset.load_dataset()
    first=next(c for c in all_cases if c.split=='development')
    altered=tuple(replace(c,input=replace(c.input,subject='PRIVATE tamper')) if c is first else c for c in all_cases)
    monkeypatch.setattr(experiment.dataset,'load_dataset',lambda:(altered,policy,manifest))
    with pytest.raises(experiment.local.BenchmarkError):experiment.benchmark()
    assert not flat_api


def test_zero_denominator_and_unobserved_diagnostics(cases):
    d=experiment.diagnostics((),(),(),POLICY)
    assert d['required_recall'] is None and d['required_to_not_required_rate'] is None
    assert d['domain_undercoverage_rate'] is None and d['uncertain_to_required_rate'] is None
    selected=(replace(cases[0],expected=HumanLabels('relevant','home','utility','required')),)
    d=experiment.diagnostics(selected,(None,),('model_invalid',),POLICY)
    assert d['required_miss_count']==1 and d['required_recall']==0
    assert d['required_to_not_required_rate'] is None and d['required_to_uncertain_rate'] is None
    assert d['domain_known_valid_count']==0 and d['domain_abstained_on_known_truth']==0


def test_manual_repeat_difference_is_visible_not_claimed_deterministic(flat_api,monkeypatch):
    first=experiment.benchmark(variant='action-evidence')
    response_patch(monkeypatch,lambda i,p:envelope(response=json.dumps(FLAT|{'action_label':'required'})))
    second=experiment.benchmark(variant='action-evidence')
    assert first['manifest_fingerprint']==second['manifest_fingerprint']
    check=experiment.check_reproducibility(first,second)
    assert not check['aggregate_metrics_equal'] and not check['aggregate_diagnostics_equal']
    assert not check['per_case_determinism_established']


def test_conditional_accuracy_delta_suppressed_when_coverage_denominators_differ(flat_api,monkeypatch):
    first=experiment.benchmark()
    response_patch(monkeypatch,lambda i,p:envelope(response=json.dumps(FLAT|{'domain_path':'home/utility'})))
    second=experiment.benchmark(variant='relevance-clarified')
    table=experiment.compare_reports(first,second)
    row=table['tradeoffs']['domain_selective_accuracy']
    assert row['delta'] is None and row['delta_comparable'] is False
    assert table['observed_denominators']['baseline']['domain_selective_count']==0
    assert table['observed_denominators']['candidate']['domain_selective_count']>0


def test_comparison_and_repeat_reject_malformed_references_safely(flat_api):
    good=experiment.benchmark()
    with pytest.raises(experiment.local.BenchmarkError):experiment.compare_reports({'PRIVATE':'PRIVATE'},good)
    with pytest.raises(experiment.local.BenchmarkError):experiment.check_reproducibility(good,None)


@pytest.mark.parametrize('statement',['import sqlalchemy','import keyring','from family_os import gmail_auth',
    'from family_os.analysis_services import analyze_source'])
def test_isolation_guard_rejects_both_import_forms(monkeypatch,statement):
    original=Path.read_text
    def read(path,*args,**kwargs):
        text=original(path,*args,**kwargs)
        return text+'\n'+statement if path==Path(experiment.__file__) else text
    monkeypatch.setattr(Path,'read_text',read)
    with pytest.raises(AssertionError):test_isolation_no_production_imports_or_wiring()
