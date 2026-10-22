"""Phase 2Q: fixed synthetic data/contracts only; no inference server or household DB."""
import ast
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import socket
import subprocess

import pytest

from family_os import action_evaluation as a
from family_os.audit import HumanLabels
from family_os.analysis import canonical_json


@pytest.fixture
def dataset():
    policy=a.load_classification(a.ROOT/'config/classification.yaml')
    return dict(d=a._read(a.DIRECTORY/'development.json'),h=a._read(a.DIRECTORY/'holdout.json'),
        r=a._read(a.DIRECTORY/'rubric.json'),m=a._read(a.DIRECTORY/'manifest.json'),p=policy,
        old=a._read(a.ROOT/'fixtures/metadata-reasoning.synthetic.json'))


def parse(v):
    return a.validate_cases(v['d'],v['h'],v['p'],v['old'])


def frozen(v):
    return a.validate_dataset(v['d'],v['h'],v['r'],v['m'],v['p'],v['old'])


def case(v,id):
    return next(c for c in v['d']['cases']+v['h']['cases'] if c['id']=='synthetic-action-'+id)


def test_exact_balanced_splits_and_provider_diversity(dataset):
    cases=frozen(dataset)
    dev=a.distribution(tuple(c for c in cases if c.split=='development'))
    hold=a.distribution(tuple(c for c in cases if c.split=='holdout'))
    assert dev['case_count']==60 and dev['action']==dict.fromkeys(a.ACTIONS,20)
    assert hold['case_count']==30 and hold['action']==dict.fromkeys(a.ACTIONS,10)
    assert dev['provider']=={'gmail':18,'outlook':18,'google_calendar':12,'google_drive':12}
    assert hold['provider']=={'gmail':9,'outlook':9,'google_calendar':6,'google_drive':6}
    assert a.distribution(cases)['counterfactual_family_count']==24
    assert set(a.distribution(cases)['scenario'])==a.SCENARIOS
    assert set(a.distribution(cases)['domain'])==set(dataset['p'].categories)|{'unknown'}
    assert a.distribution(cases)['truth_certainty']=={'ambiguous':30,'explicit':60}


def test_all_cases_pass_unchanged_projection_and_existing_prompt_budgets(dataset):
    # Pure payload builder only; no HTTP/model invocation and no runner alteration.
    from family_os.ollama_synthetic_benchmark import request_payload,MODEL,CANDIDATE_MODEL,PROMPT_BYTES,REQUEST_BYTES
    for c in frozen(dataset):
        projection=a.model_projection(c)
        assert projection.byte_count<=1024
        assert set(projection.fields)<={'provider','record_type','subject','sender','occurred_at','raw_metadata'}
        for model in (MODEL,CANDIDATE_MODEL):
            payload=request_payload(projection,dataset['p'],'flat-domain',model)
            assert len(payload['prompt'].encode())<=PROMPT_BYTES
            assert len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode())<=REQUEST_BYTES
        assert 'example.invalid' in c.input.sender if c.input.sender else c.input.provider not in {'gmail','outlook'}


def test_projection_cannot_include_answers_annotations_or_split(dataset):
    c=frozen(dataset)[0]
    annotated=replace(c,expected=HumanLabels('uncertain',None,None,'uncertain'),split='holdout',
                      annotations={'rationale':'ANNOTATION_SENTINEL','evidence_refs':['subject'],'fake_response':'ANSWER_SENTINEL'})
    assert a.model_projection(annotated).canonical()==a.model_projection(c).canonical()
    encoded=a.model_projection(annotated).canonical()
    assert all(s not in encoded for s in ('ANNOTATION_SENTINEL','ANSWER_SENTINEL','evidence_refs','expected','split','synthetic-action','rationale'))
    assert 'ANNOTATION_SENTINEL' not in repr(annotated) and 'ANSWER_SENTINEL' not in repr(annotated)


def test_only_typed_case_can_be_projected(dataset):
    with pytest.raises(a.DatasetRejectedError): a.model_projection(dataset['h']['cases'][0])


@pytest.mark.parametrize('name', ['development','holdout'])
def test_order_does_not_change_manifest_or_validation(dataset,name):
    key='d' if name=='development' else 'h'
    baseline=frozen(dataset)
    dataset[key]['cases'].reverse()
    assert frozen(dataset)==baseline
    assert a.manifest_for(dataset['d'],dataset['h'],dataset['r'],dataset['p'])==dataset['m']


@pytest.mark.parametrize('field,value',[
 ('synthetic_only',False),('synthetic_only',1),('dataset_version','action-evaluation-v2'),
 ('split','unknown'),('cases',[]),('extra','unexpected')])
def test_top_level_schema_rejected(dataset,field,value):
    dataset['d'][field]=value
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


@pytest.mark.parametrize('field,value',[
 ('id','synthetic-1'),('id',1),('scenario','other'),('temporal','tomorrow'),('truth_certainty','probable'),
 ('rationale',''),('rationale','x'*513),('ambiguity_notes',''),('evidence_refs',[]),
 ('evidence_refs',['subject']*2),('evidence_refs',['raw_metadata.body']),('evidence_refs',['raw_metadata.missing']),
 ('evidence_refs',['https://example.invalid']),('evidence_refs',[1]),('evidence_refs',['source_sync_state.cursor']),
 ('counterfactual_group','invalid group'),('cue_field','sender'),('extra',True)])
def test_case_schema_and_adjudication_bounds(dataset,field,value):
    dataset['d']['cases'][0][field]=value
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


@pytest.mark.parametrize('field,value',[
 ('provider','fixture'),('record_type','document'),('subject',''),('subject','x'*601),
 ('subject','https://example.invalid/private'),('subject','access_token=private'),
 ('sender','real@example.com'),('sender','Person <case@example.invalid>'),('sender',None),
 ('occurred_at','2026-02-30T00:00:00Z'),('occurred_at','2026-10-09T00:00:00'),
 ('occurred_at','2040-10-09T00:00:00Z'),('body','PRIVATE'),('raw_metadata',{'description':'PRIVATE'}),
 ('raw_metadata',{'start':{'date':'2026-10-12','private':'PRIVATE'}}),('raw_metadata',{'trashed':1})])
def test_input_types_privacy_and_strict_allowlist(dataset,field,value):
    dataset['d']['cases'][0]['input'][field]=value
    with pytest.raises(a.DatasetRejectedError) as error: parse(dataset)
    assert 'PRIVATE' not in str(error.value) and 'example.com' not in str(error.value)


@pytest.mark.parametrize('dimension,value',[
 ('action','later'),('relevance','urgent'),('domain',['home','insurance']),('domain',['home',None]),
 ('domain',[None,'utility']),('domain',['unknown','other']),('domain',[]),('action',True)])
def test_invalid_truth_contract(dataset,dimension,value):
    dataset['d']['cases'][0]['expected'][dimension]=value
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


def test_ambiguous_truth_cannot_be_overridden_by_a_concrete_label(dataset):
    c=case(dataset,'renewal-hint');c['expected']['action']='required'
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


def test_historical_request_cannot_be_asserted_as_current_outstanding(dataset):
    c=case(dataset,'old-charge');c['expected']['action']='required';c['truth_certainty']='explicit'
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


def test_duplicate_ids_and_projections_fail_closed(dataset):
    dataset['d']['cases'][1]['id']=dataset['d']['cases'][0]['id']
    with pytest.raises(a.DatasetRejectedError): parse(dataset)
    dataset['d']['cases'][1]['id']='synthetic-action-distinct'
    dataset['d']['cases'][1]['input']=deepcopy(dataset['d']['cases'][0]['input'])
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


@pytest.mark.parametrize('subject',['Insurance renewal due','INSURANCE -- renewal DUE!','Utility bill: payment due','Please renew'])
def test_old_corpus_reuse_and_obvious_paraphrases_rejected(dataset,subject):
    dataset['d']['cases'][0]['input']['subject']=subject
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


def test_near_duplicate_across_splits_rejected(dataset):
    # Add a known near-paraphrase into the novelty reference; changes in punctuation are not new data.
    title=dataset['d']['cases'][0]['input']['subject']
    dataset['old']['cases'].append({'input':{'subject':title.replace(';',',')}})
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


def test_counterfactuals_change_only_declared_observable_cue_and_never_cross_splits(dataset):
    cases=frozen(dataset)
    for group in {c.annotations['counterfactual_group'] for c in cases}-{None}:
        triad=[c for c in cases if c.annotations['counterfactual_group']==group]
        assert len(triad)==3 and {c.expected.action_label for c in triad}==set(a.ACTIONS)
        assert len({c.split for c in triad})==1
        sources=[json.loads(a.model_projection(c).canonical()) for c in triad]
        cue=triad[0].annotations['cue_field'].split('.')
        for s in sources:
            target=s
            for part in cue[:-1]:target=target[part]
            target[cue[-1]]='CONTROLLED_CUE'
        assert sources[0]==sources[1]==sources[2]


def test_counterfactual_uncontrolled_detail_and_split_leak_rejected(dataset):
    case(dataset,'water-1')['input']['sender']='changed@example.invalid'
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


def test_counterfactual_family_cannot_straddle_holdout(dataset):
    # Swap matching action labels, preserving both balances and counts.
    dev=case(dataset,'water-1');hold=case(dataset,'permit-1')
    dataset['d']['cases'].remove(dev);dataset['h']['cases'].remove(hold)
    dataset['d']['cases'].append(hold);dataset['h']['cases'].append(dev)
    with pytest.raises(a.DatasetRejectedError): parse(dataset)


@pytest.mark.parametrize('id,action',[
 ('old-charge','uncertain'),('old-prep','uncertain'),('past-visit','not_required'),
 ('renewal-hint','uncertain'),('draft-cover','uncertain'),('overview','uncertain'),
 ('vaccine-1','required'),('vaccine-2','not_required'),('vaccine-3','uncertain'),
 ('replacement','required'),('claim','required'),('catalog','not_required'),('check-in','uncertain')])
def test_adjudicated_tricky_examples_preserve_visible_evidence_rubric(dataset,id,action):
    c=case(dataset,id)
    assert c['expected']['action']==action
    assert c['rationale'] and c['ambiguity_notes'] and c['evidence_refs']
    if id=='replacement': assert 'cancelled' in c['input']['subject'] and 'still pending' in c['input']['subject']
    if id=='renewal-hint': assert 'approaching' in c['input']['subject'] and c['truth_certainty']=='ambiguous'
    if id=='overview': assert c['expected']['domain'] is None and c['expected']['relevance']=='uncertain'


@pytest.mark.parametrize('split', ['d','h'])
def test_changed_annotations_or_input_change_manifest_but_never_projection_labels(dataset,split):
    before=a.manifest_for(dataset['d'],dataset['h'],dataset['r'],dataset['p'])
    dataset[split]['cases'][0]['rationale']+=' ADJUDICATION_EDIT'
    after=a.manifest_for(dataset['d'],dataset['h'],dataset['r'],dataset['p'])
    assert before['corpus_sha256']!=after['corpus_sha256']
    name='development' if split=='d' else 'holdout'
    assert before['splits'][name]['input_sha256']==after['splits'][name]['input_sha256']
    with pytest.raises(a.DatasetRejectedError): frozen(dataset)
    # Rewriting the file manifest alone cannot re-freeze changed content.
    dataset['m']=after
    with pytest.raises(a.DatasetRejectedError): frozen(dataset)


@pytest.mark.parametrize('change',['rubric','input','split','manifest','taxonomy'])
def test_freeze_detects_changed_holdout_rubric_and_identity(dataset,change):
    if change=='rubric':dataset['r']['annotation_policy']+=' edited'
    elif change=='input':dataset['h']['cases'][0]['input']['subject']+=' edited'
    elif change=='split':dataset['h']['split']='development'
    elif change=='manifest':dataset['m']['corpus_sha256']='0'*64
    else:dataset['p']=replace(dataset['p'],taxonomy_version='changed-taxonomy-v2')
    with pytest.raises(a.DatasetRejectedError): frozen(dataset)


@pytest.mark.parametrize('text',['{"synthetic_only":true,"synthetic_only":false}', '{"x":NaN}', '{"x":Infinity}', '{}{}', 'invalid', ' '* (a.FILE_BYTES+1)])
def test_duplicate_json_nonfinite_trailing_and_oversized_fixture_rejected(text):
    with pytest.raises(a.DatasetRejectedError):a.strict_json(text)


def test_empty_metric_denominators_remain_null(dataset):
    rules=a.MetadataRulesAnalyzer(a.load_rules(a.ROOT/'config/metadata-classifier.yaml',dataset['p']))
    result=a.evaluate_rules((),dataset['p'],rules)
    assert result['required_recall'] is None and result['required_miss_count']==0
    assert result['relevance_accuracy'] is None and result['action_accuracy'] is None
    assert result['domain_selective_accuracy'] is None


def test_default_evaluates_only_development_and_final_holdout_is_explicit(monkeypatch,capsys):
    seen=[]
    original=a.evaluate_rules
    def record(cases,policy,rules):
        seen.append({c.split for c in cases})
        return original(cases,policy,rules)
    monkeypatch.setattr(a,'evaluate_rules',record)
    assert a.main([])==0
    dev=json.loads(capsys.readouterr().out)
    assert dev['evaluated_split']=='development' and seen==[{'development'}]
    assert a.main(['--final-holdout'])==0
    final=json.loads(capsys.readouterr().out)
    assert final['evaluated_split']=='holdout' and seen[-1]=={'holdout'}
    assert dev['manifest_sha256']==final['manifest_sha256']==a.FROZEN_MANIFEST_SHA256
    assert dev['device_egress_bytes']==0 and final['persistence_exercised'] is False
    assert all(k not in canonical_json(final) for k in ('subject','sender','rationale','evidence_refs','raw_metadata','synthetic-action-'))


def test_no_network_database_keyring_or_model_access(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('I/O access forbidden')
    monkeypatch.setattr(socket,'create_connection',forbidden)
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    # Import hooks make attempts to import a client/model/db fail immediately.
    import builtins
    original=builtins.__import__
    def imports(name,*args,**kwargs):
        if name.split('.')[0] in {'sqlalchemy','keyring','requests','httpx','http','ollama','google','msal','openai'}:
            raise AssertionError('Forbidden dependency')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',imports)
    assert a.report()['rules']['eligible_count']==60


def test_ast_and_production_isolation():
    imports=[]
    for node in ast.walk(ast.parse(Path(a.__file__).read_text())):
        if isinstance(node,ast.ImportFrom):imports.append(node.module or '')
        elif isinstance(node,ast.Import):imports.extend(alias.name for alias in node.names)
    allowed={'argparse','collections','dataclasses','datetime','hashlib','json','pathlib','re','unicodedata',
             'analysis','audit','metadata_classifier','synthetic_reasoning'}
    assert set(imports)<=allowed
    # No production entrypoint, service or existing model runner imports this dataset.
    for path in (a.ROOT/'src/family_os').rglob('*.py'):
        if path.name in {'action_evaluation.py','action_model_benchmark.py'}:continue
        assert 'action_evaluation' not in path.read_text()


def test_failed_validation_prints_no_partial_data(monkeypatch,capsys):
    def fail():raise ValueError('PRIVATE_SOURCE_SECRET')
    monkeypatch.setattr(a,'load_dataset',fail)
    assert a.main([])==1
    assert capsys.readouterr().out=='Synthetic Action evaluation failed; no partial report or source content printed\n'


def test_cohort_metrics_include_misses_false_positives_and_unknown_truth_separately(dataset):
    from family_os.analysis import AnalysisOutput
    cases=list(frozen(dataset)[:3])
    cases=[replace(c,expected=HumanLabels('relevant','home','utility',action)) for c,action in zip(cases,a.ACTIONS)]
    outputs={cases[0].id:AnalysisOutput('irrelevant',.9,'home','utility',.9,'not_required',.9),
             cases[1].id:AnalysisOutput('relevant',.9,None,None,0.,'required',.9),
             cases[2].id:AnalysisOutput('uncertain',.55,None,None,.55,'uncertain',.55)}
    class Stub:
        def analyze(self,input,policy):return outputs[input.source_record_id]
    result=a.evaluate_rules(cases,dataset['p'],Stub())
    assert result['required_miss_count']==1 and result['required_recall']==0
    assert result['not_required_false_positive_count']==1 and result['uncertain_concrete_count']==0
    assert result['required_false_irrelevant_count']==1
    assert result['action_accuracy']==0 and result['action_decisive_count']==2
    assert result['human_uncertain_action']==1
    assert result['domain_truth_count']==3 and result['decisive_domain_classified_count']==1
    assert result['decisive_domain_coverage']==pytest.approx(1/3)
    assert result['domain_selective_accuracy']==1
    assert result['concrete_predictions']['action_required']['false_positive']==1
    assert result['concrete_predictions']['irrelevant']['false_positive']==1


def test_failed_rule_output_does_not_silently_skip_or_report_fabricated_results(dataset):
    from family_os.analysis import AnalysisOutput,AnalysisValidationError
    class Broken:
        def analyze(self,input,policy):return AnalysisOutput('relevant',.9,'home','insurance',.9,'required',.9)
    with pytest.raises(AnalysisValidationError):a.evaluate_rules(frozen(dataset)[:1],dataset['p'],Broken())


@pytest.mark.parametrize('metadata',[
 {'status':'confirmed'}, {'mimeType':'application/pdf'}, {'eventType':'default'}])
def test_provider_inappropriate_metadata_is_rejected(dataset,metadata):
    dataset['d']['cases'][0]['input']['raw_metadata']=metadata
    with pytest.raises(a.DatasetRejectedError):parse(dataset)


@pytest.mark.parametrize('path,value',[
 ('status','removed'),('start',{'date':'2026-02-30'}),('end',{'dateTime':'2026-10-12'}),
 ('start',{'date':'2040-01-01'}),('start',{'dateTime':'2026-10-12T09:00:00'})])
def test_calendar_dates_and_status_are_real_bounded_values(dataset,path,value):
    case(dataset,'vaccine-1')['input']['raw_metadata'][path]=value
    with pytest.raises(a.DatasetRejectedError):parse(dataset)


def test_counterfactual_unchanged_topic_cannot_change_domain_or_relevance(dataset):
    case(dataset,'water-1')['expected']['domain']=['household_admin','bill']
    with pytest.raises(a.DatasetRejectedError):parse(dataset)


def test_label_balance_rejected_without_changing_fixture_size(dataset):
    case(dataset,'water-1')['expected']['action']='not_required'
    with pytest.raises(a.DatasetRejectedError):parse(dataset)


def test_bounded_file_reader_rejects_oversized_non_utf8_and_duplicate_json(tmp_path):
    path=tmp_path/'synthetic-fixture.json'
    for data in (b'x'*(a.FILE_BYTES+1),b'\xff',b'{"x":1,"x":2}'):
        path.write_bytes(data)
        with pytest.raises(a.DatasetRejectedError):a._read(path)


def test_golden_manifest_requires_deliberate_freeze_revision(dataset):
    assert a.digest(dataset['m'])=='f676baa523a8c7a9b187e8139be8e556244a09009ef674b7830a3729b831634f'
