"""Paired calculations use actual aligned mocked predictions, not old aggregates."""
import ast
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from family_os import paired_synthetic_diagnosis as paired
from family_os.audit import HumanLabels
from test_action_model_benchmark import output, response_patch
from test_ollama_synthetic_benchmark import api, envelope, POLICY, DIGEST
from test_ollama_flat_domain import flat_api, FLAT


@pytest.fixture
def cases():
    return paired.control.select_development(paired.dataset.load_dataset()[0],full=True)


def evaluate(cases,a,b,sa=None,sb=None):
    return paired.paired_metrics(cases,a,sa or ('valid',)*len(cases),b,sb or ('valid',)*len(cases),POLICY)


@pytest.mark.parametrize('full',[False,True])
def test_four_unchanged_prompts_aligned_fixed_cases_and_bounded_requests(flat_api,full):
    report=paired.benchmark(full=full)
    selected=paired.control.select_development(paired.dataset.load_dataset()[0],full=full)
    payloads=[p for _,path,p in flat_api if path=='/api/generate']
    assert report['completed'] and report['configuration_comparable'] and report['warning'] is None
    assert report['final_model_identity_verified'] and not report['holdout_inference'] and not report['persistence_exercised']
    assert not report['automatic_promotion'] and len(payloads)==len(selected)*4
    assert payloads==[paired.experiment.request_payload(paired.control.projection(c),POLICY,v) for v in paired.VARIANTS for c in selected]
    for variant in paired.VARIANTS:
        assert report['counts'][variant]['valid']==report['counts'][variant]['sent']==len(selected)
        assert report['counts'][variant]['not_attempted']==report['counts'][variant]['infrastructure_failed']==0
        assert report['variants'][variant]['metrics']['classifier_review_rate']==1
        assert report['performance'][variant]['generated_tokens_per_second']==pytest.approx(40/.6)
    for variant,row in report['comparisons'].items():
        assert row['paired_valid_count']==len(selected) and row['unpaired_count']==0
        assert row['required']['recovered']==row['required']['newly_missed']==0
        assert row['human_review_only_count']==len(selected)
    assert report['budgets']['run_seconds']==report['manifest']['global_run_seconds']==600
    assert paired.local.OPTIONS=={'temperature':0,'seed':0,'num_ctx':4096,'num_predict':256}
    assert {path for _,path,_ in flat_api}=={'/api/tags','/api/version','/api/generate'}


def test_recoveries_and_new_misses_are_aligned_not_inferred_from_aggregate_totals(cases):
    chosen=tuple(replace(c,expected=HumanLabels('relevant','home','utility','required')) for c in cases[:4])
    a=(output('required'),output('required'),output('uncertain'),output('not_required'))
    b=(output('uncertain'),output('not_required'),output('required','irrelevant'),output('required'))
    row=evaluate(chosen,a,b)
    assert row['required']['recovered']==row['required']['newly_missed']==2
    assert row['required']['recovery_rate']==row['required']['new_miss_rate']==1
    assert row['required']['recovered_from_uncertain']==row['required']['recovered_from_not_required']==1
    assert row['required']['newly_uncertain']==row['required']['newly_not_required']==1
    assert row['required']['recovered_but_candidate_irrelevant']==1
    assert row['required_recovery_relevance_transitions']['uncertain']['irrelevant']==1
    assert row['required_recovery_relevance_transitions']['uncertain']['uncertain']==1
    assert row['required_new_miss_relevance_transitions']['uncertain']['uncertain']==2
    # Both variants have recall 2/4, yet each changes two errors: no net-score attribution.
    assert sum(row['action_transitions']['required'].values())==2
    assert row['human_review_only_count']==4  # irrelevant never erases required observations


def test_same_marginals_can_have_completely_different_paired_transitions(cases):
    chosen=tuple(replace(c,expected=HumanLabels('relevant',None,None,'required')) for c in cases[:2])
    a=(output('required'),output('uncertain'))
    stable=evaluate(chosen,a,a)
    swapped=evaluate(chosen,a,(output('uncertain'),output('required')))
    assert stable['required']['recovered']==stable['required']['newly_missed']==0
    assert swapped['required']['recovered']==swapped['required']['newly_missed']==1


def test_relevance_false_irrelevant_and_uncertainty_transitions_separate(cases):
    chosen=tuple(replace(c,expected=HumanLabels(rel,None,None,action)) for c,rel,action in zip(cases[:4],
        ('relevant','relevant','uncertain','irrelevant'),('uncertain','uncertain','required','not_required')))
    a=(output('uncertain','irrelevant'),output('required','uncertain'),output('required','irrelevant'),output('not_required','irrelevant'))
    b=(output('required','uncertain'),output('uncertain','irrelevant'),output('required','relevant'),output('not_required','irrelevant'))
    row=evaluate(chosen,a,b)
    assert row['false_irrelevant_transitions']['yes']['no']==1
    assert row['false_irrelevant_transitions']['no']['yes']==1
    assert row['relevance_transitions']['irrelevant']['uncertain']==1
    assert row['uncertain']['newly_concrete']==row['uncertain']['recovered_uncertainty']==1
    assert row['uncertain']['newly_required']==1 and row['uncertain']['newly_not_required']==0
    assert row['by_truth_relevance']['uncertain']['false_irrelevant_transitions']['no']['no']==1


def test_domain_unknown_abstention_wrong_and_recovered_are_separate(cases):
    chosen=tuple(replace(c,expected=HumanLabels('relevant',*domain,'uncertain')) for c,domain in zip(cases[:3],
        (('home','utility'),('home','utility'),(None,None))))
    a=(output(domain=('home','utility')),output(),output(domain=('home','utility')))
    b=(output(),output(domain=('home','utility')),output(domain=('travel','hotel')))
    row=evaluate(chosen,a,b)
    assert row['domain']['known_truth_paired']==2 and row['domain']['unknown_truth_paired']==1
    assert row['domain']['recovered_correct']==row['domain']['newly_wrong']==1
    assert row['domain']['baseline_abstained']==row['domain']['candidate_abstained']==1


def test_provider_status_cue_and_truth_denominators(cases):
    baseline=tuple(output() for c in cases)
    truth=tuple(output(c.expected.action_label) for c in cases)
    row=evaluate(cases,baseline,truth)
    assert row['paired_valid_count']==60 and row['required']['recovered']==20
    assert sum(p['paired_valid_count'] for p in row['by_provider'].values())==60
    assert sum(p['selected_count'] for p in row['by_truth_action'].values())==60
    assert sum(p['selected_count'] for p in row['by_truth_relevance'].values())==60
    assert row['by_calendar_status']['confirmed']['required']['recovered']==3
    assert row['by_calendar_status']['missing']['required']['recovered']==1
    assert all(row['by_calendar_status'][s]['paired_valid_count']==3 for s in ('confirmed','cancelled','tentative','missing'))
    assert row['by_cue_family']['subject']['paired_valid_count']==39
    assert row['by_cue_family']['raw_metadata.status']['paired_valid_count']==9
    assert row['by_cue_family']['standalone']['paired_valid_count']==12


def test_triad_and_pair_correctness_vs_sensitivity_not_conflated(cases):
    truth=tuple(output(c.expected.action_label) for c in cases)
    permutation={'required':'not_required','not_required':'uncertain','uncertain':'required'}
    wrong=tuple(output(permutation[c.expected.action_label]) for c in cases)
    row=evaluate(cases,wrong,truth)['triads']
    assert row['triad_correctness_transitions']['incorrect']['correct']==16
    assert row['pair_correctness_transitions']['incorrect']['correct']==48
    assert row['pair_sensitivity_transitions']['changed']['changed']==48
    assert row['by_cue']['subject']['triad_correctness_transitions']['incorrect']['correct']==13
    assert row['by_cue']['raw_metadata.status']['triad_correctness_transitions']['incorrect']['correct']==3
    reverse=evaluate(cases,truth,wrong)['triads']
    assert reverse['triad_correctness_transitions']['correct']['incorrect']==16
    assert reverse['candidate_pair_correct_rate']==0


def test_invalid_and_unattempted_never_become_uncertain_predictions(cases):
    chosen=tuple(replace(c,expected=HumanLabels('relevant',None,None,'required')) for c in cases[:3])
    row=evaluate(chosen,(output('required'),None,output('uncertain')),(None,output('required'),None),
        ('valid','model_invalid','valid'),('infrastructure_failed','valid','not_attempted'))
    assert row['paired_valid_count']==0 and row['unpaired_count']==3 and row['paired_valid_coverage']==0
    assert row['required']['recovery_rate'] is None and row['required']['new_miss_rate'] is None
    assert sum(sum(v.values()) for v in row['action_transitions'].values())==0
    assert row['status_transitions']['model_invalid']['valid']==1
    assert row['human_review_only_count']==0
    empty=evaluate((),(),())
    assert empty['paired_valid_coverage'] is None and empty['triads']['candidate_pair_correct_rate'] is None


def test_partial_triangle_only_scores_pairs_with_all_four_valid_outputs(cases):
    truth=tuple(output(c.expected.action_label) for c in cases)
    selected=list(truth);selected[0]=None
    row=evaluate(cases,truth,tuple(selected),sb=('model_invalid',)+('valid',)*59)
    assert row['triads']['paired_valid_triads']==15 and row['triads']['paired_valid_pairs']==46


@pytest.mark.parametrize('field',['relevance_confidence','action_confidence','domain_confidence'])
def test_nonzero_uncalibrated_confidence_rejected(cases,field):
    with pytest.raises(paired.local.BenchmarkError):evaluate((cases[0],),(output(),),(replace(output(),**{field:.9}),))


def test_every_dispatch_uses_projection_not_annotations_or_holdout(flat_api,monkeypatch):
    original=paired.dataset.model_projection
    observed=[]
    def project(c):
        assert c.split=='development';observed.append(c.id)
        return original(c)
    monkeypatch.setattr(paired.dataset,'model_projection',project)
    assert paired.benchmark(full=True)['completed'] and len(set(observed))==60
    for _,path,p in flat_api:
        if path=='/api/generate':
            assert all(word not in p['prompt'] for word in ('rationale','expected','evidence_refs','source_record_id','raw_record_id',
                'counterfactual_group','truth_certainty','holdout'))


def test_report_never_contains_case_content_or_raw_error(flat_api,cases,caplog):
    report=paired.benchmark(full=True);text=json.dumps(report)
    assert 'UNTRUSTED_METADATA_JSON' not in text and not caplog.records
    for c in cases:
        assert c.id not in text and c.input.subject not in text
        if c.input.sender:assert c.input.sender not in text


@pytest.mark.parametrize('arg',['--holdout','--final-holdout','--input','--file','--host','--url','--model','--variant',
    '--household','--database','--prompt','--repeat-check'])
def test_cli_closed_to_arbitrary_or_production_inputs(arg,flat_api):
    with pytest.raises(SystemExit):paired.main([arg])
    assert not flat_api


@pytest.mark.parametrize('full',[None,1,'yes',[],{}])
def test_invalid_scope_before_network(full,flat_api):
    with pytest.raises(paired.local.BenchmarkError):paired.benchmark(full=full)
    assert not flat_api


def test_wrong_client_or_model_before_any_request(flat_api):
    with pytest.raises(paired.local.BenchmarkError):paired.benchmark(transport=object())
    with pytest.raises(paired.local.BenchmarkError):paired.benchmark(transport=paired.local.LocalOllama(paired.local.CANDIDATE_MODEL))
    assert not flat_api


def test_late_variant_bad_prompt_fails_entire_preflight_before_network(flat_api,monkeypatch):
    monkeypatch.setitem(paired.experiment.EDITS,'calendar-status','PRIVATE changed')
    with pytest.raises(paired.local.BenchmarkError):paired.benchmark()
    assert not flat_api


def test_oversized_late_prompt_cannot_expand_budget(flat_api,monkeypatch):
    edit=' x'*2000;variant='calendar-status'
    monkeypatch.setitem(paired.experiment.EDITS,variant,edit)
    monkeypatch.setitem(paired.experiment.EDIT_SHA256,variant,paired.local.digest(edit))
    monkeypatch.setitem(paired.experiment.PROMPT_SHA256,variant,paired.local.digest(paired.local.system_prompt(POLICY,'flat-domain')+edit))
    with pytest.raises(paired.local.BenchmarkError):paired.benchmark()
    assert not flat_api and paired.local.PROMPT_BYTES==3072


@pytest.mark.parametrize('field',['engine','metrics_version','model_digest','ollama_version','schema_digest','options_digest',
    'taxonomy_version','threshold_policy_version','development_input_digest','rules_fingerprint','selection_digest','prompt_digest'])
def test_mismatch_rejected_before_pairing(flat_api,field):
    identities=paired.benchmark()['variant_identities']
    identities['calendar-status'][field]='PRIVATE changed'
    with pytest.raises(paired.local.BenchmarkError):paired.ensure_comparable(identities)


def test_semantic_invalid_continues_but_excluded_from_pairing(flat_api,monkeypatch):
    response_patch(monkeypatch,lambda i,p:envelope(response=json.dumps(FLAT|{'domain_path':'home/insurance'} if i==6 else FLAT)))
    report=paired.benchmark()
    assert report['completed'] and report['counts']['relevance-clarified']['model_invalid']==1
    assert report['counts']['relevance-clarified']['sent']==5
    row=report['comparisons']['relevance-clarified']
    assert row['paired_valid_count']==4 and row['unpaired_count']==1
    assert row['status_transitions']['valid']['model_invalid']==1


def test_failure_mid_candidate_retains_honest_partial_pairs_and_stops_later_variants(flat_api,monkeypatch):
    def respond(i,p):
        if i==8:raise TimeoutError('PRIVATE URL token')
        return envelope(response=json.dumps(FLAT))
    response_patch(monkeypatch,respond)
    report=paired.benchmark()
    assert not report['completed'] and report['metrics_scope']=='partial_observed'
    assert report['counts']['baseline']['valid']==5
    assert report['counts']['relevance-clarified']['valid']==2
    assert report['counts']['relevance-clarified']['infrastructure_failed']==1
    assert report['counts']['action-evidence']['not_attempted']==5
    assert report['comparisons']['relevance-clarified']['paired_valid_count']==2
    assert report['comparisons']['action-evidence']['paired_valid_count']==0
    assert report['comparisons']['action-evidence']['required']['recovery_rate'] is None
    assert 'PRIVATE' not in json.dumps(report)


@pytest.mark.parametrize('response',['not JSON','{}',json.dumps(FLAT)+' trailing','<think>PRIVATE</think>'+json.dumps(FLAT),
    json.dumps(FLAT|{'extra':'PRIVATE'}),'x'*4097])
def test_protocol_failures_abort_no_retry_private_leak(flat_api,monkeypatch,response):
    response_patch(monkeypatch,lambda i,p:envelope(response=response))
    report=paired.benchmark()
    assert not report['completed'] and report['counts']['baseline']['sent']==1
    assert report['counts']['baseline']['infrastructure_failed']==1 and report['counts']['baseline']['model_invalid']==0
    assert report['counts']['calendar-status']['sent']==0
    assert 'PRIVATE' not in json.dumps(report)


@pytest.mark.parametrize('change',[{'done':False},{'done_reason':'length'},{'done_reason':None},{'model':'other'},
    {'thinking':'PRIVATE'},{'prompt_eval_cached_count':True},{'eval_count':257},{'extra':'PRIVATE'}])
def test_envelope_security_and_resource_fail_closed(flat_api,monkeypatch,change):
    response_patch(monkeypatch,lambda i,p:envelope(response=json.dumps(FLAT))|change)
    report=paired.benchmark()
    assert not report['completed'] and report['counts']['baseline']['infrastructure_failed']==1
    assert report['counts']['relevance-clarified']['sent']==0 and 'PRIVATE' not in json.dumps(report)


def test_changed_final_model_after_failure_suppresses_all_attribution(flat_api,monkeypatch):
    count=0
    def digest(self,**kwargs):
        nonlocal count
        count+=1
        return DIGEST if count<=2 else 'b'*64
    monkeypatch.setattr(paired.local.LocalOllama,'installed_digest',digest)
    def fail(i,p):raise RuntimeError('PRIVATE')
    response_patch(monkeypatch,fail)
    report=paired.benchmark()
    assert not report['configuration_comparable'] and not report['final_model_identity_verified']
    assert report['warning']=='runs_differ_or_identity_unverifiable_no_paired_attribution'
    assert all(key not in report for key in ('manifest','variants','comparisons','performance','variant_identities'))
    assert report['counts']['baseline']['sent']==1


def test_transient_runtime_mismatch_not_silently_treated_comparable_after_restoration(flat_api,monkeypatch):
    count=0
    def runtime(self,**kwargs):
        nonlocal count
        count+=1
        return '0.99.1' if count==3 else '0.40.1'
    monkeypatch.setattr(paired.local.LocalOllama,'runtime_version',runtime)
    report=paired.benchmark()
    assert not report['configuration_comparable'] and report['warning']
    assert report['counts']['baseline']['valid']==5 and report['counts']['relevance-clarified']['sent']==0
    assert 'comparisons' not in report


def test_predispatch_model_swap_no_post_or_paired_metrics(flat_api,monkeypatch):
    count=0
    def digest(self,**kwargs):
        nonlocal count
        count+=1
        return 'b'*64 if count==2 else DIGEST
    monkeypatch.setattr(paired.local.LocalOllama,'installed_digest',digest)
    report=paired.benchmark()
    assert report['counts']['baseline']['sent']==0 and not report['configuration_comparable']
    assert not any(path=='/api/generate' for _,path,_ in flat_api) and 'comparisons' not in report


def test_one_global_monotonic_budget_no_real_sleep(flat_api,monkeypatch):
    now=paired.time.monotonic();clock=iter((now,now+601,now+602))
    monkeypatch.setattr(paired,'time',SimpleNamespace(monotonic=lambda:next(clock)))
    report=paired.benchmark()
    assert all(report['counts'][v]['sent']==0 for v in paired.VARIANTS)
    assert not report['configuration_comparable']


def test_fixed_readonly_files_no_household_database_or_account_access(flat_api,monkeypatch):
    original=Path.open
    allowed={paired.dataset.DIRECTORY/name for name in ('development.json','holdout.json','rubric.json','manifest.json')}
    allowed|={paired.dataset.ROOT/'fixtures/metadata-reasoning.synthetic.json',
              paired.dataset.ROOT/'config/classification.yaml',paired.dataset.ROOT/'config/metadata-classifier.yaml'}
    def opened(path,mode='r',*args,**kwargs):
        assert path in allowed and not any(char in mode for char in 'wax+')
        return original(path,mode,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened)
    assert paired.benchmark()['completed']


def test_cli_aggregate_only_safe_failure_and_interrupt(flat_api,monkeypatch,capsys):
    assert paired.main([])==0
    report=json.loads(capsys.readouterr().out)
    assert report['completed'] and report['comparisons']['calendar-status']['paired_valid_count']==5
    def fail(**kwargs):raise RuntimeError('PRIVATE path subject')
    monkeypatch.setattr(paired,'benchmark',fail)
    assert paired.main([])==1 and 'PRIVATE' not in capsys.readouterr().out
    def interrupt(**kwargs):raise KeyboardInterrupt
    monkeypatch.setattr(paired,'benchmark',interrupt)
    assert paired.main([])==130 and 'no state persisted' in capsys.readouterr().out


def test_ast_isolation_both_import_forms_and_no_production_wiring():
    imports=[]
    for node in ast.walk(ast.parse(Path(paired.__file__).read_text())):
        if isinstance(node,ast.Import):imports.extend(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom):
            if node.module:imports.append(node.module)
            else:imports.extend(alias.name for alias in node.names)
    assert set(imports)<={'argparse','collections','itertools','time','qwen3_prompt_experiment','analysis','audit','metadata_classifier'}
    for path in (paired.dataset.ROOT/'src/family_os').rglob('*.py'):
        if path.name=='paired_synthetic_diagnosis.py':continue
        assert 'paired_synthetic_diagnosis' not in path.read_text()


@pytest.mark.parametrize('statement',['import sqlalchemy','import keyring','from family_os import gmail_auth',
    'from family_os.analysis_services import analyze_source'])
def test_import_guards_reject_effectful_dependencies(monkeypatch,statement):
    original=Path.read_text
    def read(path,*args,**kwargs):
        text=original(path,*args,**kwargs)
        return text+'\n'+statement if path==Path(paired.__file__) else text
    monkeypatch.setattr(Path,'read_text',read)
    with pytest.raises(AssertionError):test_ast_isolation_both_import_forms_and_no_production_wiring()
