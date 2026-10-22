"""Runtime and evaluation use the same conservative local metadata analyzer."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import socket

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import event, insert, select
from sqlalchemy.exc import IntegrityError
import yaml

from family_os.analysis import AnalysisValidationError, load_classification, validate_output, Thresholds
from family_os import analysis_services
from family_os.cli import main
from family_os.metadata_classifier import load_rules, MetadataRulesAnalyzer
from family_os.metadata_evaluation import evaluate_cases
from family_os.schema import source_analysis, analysis_fact, source_record, raw_source_record
from test_analysis import input_value, seed, run, rows, good_output, SyntheticAnalyzer, SyntheticConnector
from family_os.ingestion import ingest

ROOT = Path(__file__).parents[1]
POLICY = load_classification(ROOT / 'config/classification.yaml')
RULES_PATH = ROOT / 'config/metadata-classifier.yaml'
ANALYZER = MetadataRulesAnalyzer(load_rules(RULES_PATH, POLICY))
CASES = json.loads((ROOT / 'fixtures/metadata-classifier.synthetic.json').read_text())


def classify(subject, **changes):
    return ANALYZER.analyze(input_value(subject=subject, **changes), POLICY)


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_synthetic_guardrails_are_the_runtime_predictions(case):
    # Unsupported positive labels are evaluation misses, not fabricated coverage.
    if case['id'].startswith('unsupported-'):
        assert classify(case['input']['subject']).category is None
        return
    data = case['input']
    output = classify(data['subject'], provider=data['provider'], record_type=data['record_type'],
                      sender=data.get('sender'), raw_metadata=data.get('raw_metadata', {}))
    expected = case['expected']
    assert output.relevance_label == expected['relevance']
    assert [output.category, output.subcategory] == (expected['domain'] or [None, None])
    assert output.action_label == expected['action']
    values, facts = validate_output(output, input_value(subject=data['subject']), POLICY)
    assert not facts
    if output.category is None:
        assert values['review_recommended']


def test_unsupported_labeled_cases_remain_conservative_misses():
    for case in CASES:
        if case['id'].startswith('unsupported-'):
            output = classify(case['input']['subject'])
            assert output.category is None and output.relevance_label == 'uncertain'


@pytest.mark.parametrize('subject', ['Project update', 'PAYMENT', 'Renew soon', 'Expiration', 'Appointment details',
    'reinsurance renewal due', 'my order shippedness', 'Hotel reservation unconfirmed', 'Utility bill: not payment due',
    'Maybe vehicle registration renewal due', 'Sample insurance renewal due'])
def test_unsupported_weak_negated_or_conditional_subjects_do_not_guess(subject):
    output = classify(subject)
    assert output.category is None and output.action_label == 'uncertain'
    assert output.relevance_label == 'uncertain'
    assert max(output.relevance_confidence, output.domain_confidence, output.action_confidence) < .8


@pytest.mark.parametrize('subject', ['PAYMENT', 'Please renew', 'Expiration', 'Appointment details'])
def test_default_weak_attention_abstains_and_persists_review(engine, subject):
    seed(engine)
    ingest(engine, 'home', 'account', SyntheticConnector(subject))
    result = analysis_services.analyze_metadata(engine, 'home', limit=1)
    assert result.created == 1
    stored = rows(engine, source_analysis)[0]
    assert stored['relevance_label'] == stored['action_label'] == 'uncertain'
    assert stored['domain_category'] is stored['domain_subcategory'] is None
    assert stored['action_confidence'] == .55
    assert stored['review_recommended']


@pytest.mark.parametrize('dimension,target,default', [
    ('action', 'required', 'uncertain'),
    ('relevance', 'relevant', 'uncertain'),
    ('domain', ['household_admin', 'insurance'], (None, None)),
])
@pytest.mark.parametrize('mode', ['weak_only', 'unanimous_strong', 'conflict'])
def test_rule_resolution_abstains_on_weak_or_conflicting_evidence(tmp_path, dimension, target, default, mode):
    rule = {'id': 'weak', 'when': {'subject_phrases_any': ['Attention notice']},
            'prediction': {dimension: target}, 'strength': 'weak'}
    rules = [rule]
    if mode != 'weak_only':
        other = target
        if mode == 'conflict':
            other = {'action': 'not_required', 'relevance': 'irrelevant',
                     'domain': ['travel', 'hotel']}[dimension]
        rules.append(dict(rule, id='strong', strength='strong', prediction={dimension: other}))
    config = {'ruleset_version': 'synthetic-v1', 'rules': rules}
    path = tmp_path / 'rules.yaml'
    path.write_text(yaml.safe_dump(config))
    analyzer = MetadataRulesAnalyzer(load_rules(path, POLICY))
    input = input_value(subject='Attention notice')
    output = analyzer.analyze(input, POLICY)
    label = {'action': output.action_label, 'relevance': output.relevance_label,
             'domain': (output.category, output.subcategory)}[dimension]
    confidence = {'action': output.action_confidence, 'relevance': output.relevance_confidence,
                  'domain': output.domain_confidence}[dimension]
    expected = tuple(target) if dimension == 'domain' else target
    assert label == (expected if mode == 'unanimous_strong' else default)
    assert confidence == {'weak_only': .55, 'unanimous_strong': .90, 'conflict': .0}[mode]
    values, facts = validate_output(output, input, POLICY)
    assert not facts
    if mode != 'unanimous_strong':
        assert values['review_recommended']


@pytest.mark.parametrize('subject', ['Hotel reservation confirmed', 'HOTEL—reservation, confirmed!', 'ＨＯＴＥＬ RESERVATION CONFIRMED', 'Hotel\treservation\nconfirmed'])
def test_case_punctuation_and_unicode_normalization_are_equivalent(subject):
    assert classify(subject) == classify('hotel reservation confirmed')


def test_ids_owner_recipients_and_metadata_order_never_drive_semantic_classification():
    before = classify('Project update')
    changed = classify('Project update', provider_object_id='INSURANCE RENEWAL DUE', source_record_id='payment due',
                       raw_record_id='weekly newsletter', owner_type='household', owner_id='home', recipients=('newsletter@example.invalid',))
    assert before == changed
    assert classify('Residential lease.pdf', provider='google_drive', record_type='document', raw_metadata={'mimeType':'application/pdf','trashed':False}) == classify(
        'Residential lease.pdf', provider='google_drive', record_type='document', raw_metadata={'trashed':False,'mimeType':'application/pdf'})


def test_conflicting_domains_and_actions_abstain_independent_of_rule_order(tmp_path):
    config = yaml.safe_load(RULES_PATH.read_text())
    config['rules'].reverse()
    path = tmp_path / 'reversed.yaml'; path.write_text(yaml.safe_dump(config))
    reversed_analyzer = MetadataRulesAnalyzer(load_rules(path, POLICY))
    subject = 'Insurance renewal due and hotel reservation confirmed'
    output = classify(subject)
    assert output.category is output.subcategory is None and output.action_label == 'uncertain'
    assert output.domain_confidence == 0 and output.action_confidence == 0
    assert reversed_analyzer.version == ANALYZER.version
    assert reversed_analyzer.analyze(input_value(subject=subject), POLICY) == output


def test_analyzer_is_pure_and_bounded(engine, monkeypatch, caplog):
    def forbidden(*args, **kwargs): pytest.fail('Analyzer attempted external I/O')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(engine, 'connect', forbidden)
    monkeypatch.setattr(Path, 'open', forbidden)
    for _ in range(3):
        assert classify('Insurance renewal due').action_label == 'required'
    assert classify('Insurance renewal due' + 'x' * 8192).category is None
    assert classify(None).category is None
    assert not caplog.text


def test_rule_version_tracks_content_not_yaml_format_or_rule_order(tmp_path):
    config = yaml.safe_load(RULES_PATH.read_text())
    path = tmp_path / 'rules.yaml'; path.write_text(yaml.safe_dump(config))
    assert load_rules(path, POLICY).effective_version == ANALYZER.version
    config['rules'][0]['when']['subject_phrases_any'].append('insurance renewal deadline')
    path.write_text(yaml.safe_dump(config))
    changed = load_rules(path, POLICY)
    assert changed.declared_version == ANALYZER.ruleset.declared_version
    assert changed.effective_version != ANALYZER.version
    assert len(changed.effective_version) <= 64
    config['ruleset_version'] = 'metadata-v2'; path.write_text(yaml.safe_dump(config))
    assert load_rules(path, POLICY).effective_version != changed.effective_version


@pytest.mark.parametrize('mutation', ['unknown_root','empty_rules','long_version','invalid_version','duplicate_id','unknown_rule',
    'regex','empty_when','empty_array','bad_array','duplicate_phrase','bad_token','one_token','bad_domain','bad_suffix',
    'bad_provider','empty_metadata','unknown_metadata','nan_metadata','bad_present','empty_prediction','bad_label',
    'bad_category','wrong_subcategory','half_domain','null_domain','bad_strength','too_many_rules','too_many_phrases','too_long_phrase','context_only'])
def test_strict_config_fail_closed(tmp_path, mutation):
    config = yaml.safe_load(RULES_PATH.read_text()); rule = config['rules'][0]
    if mutation == 'unknown_root': config['secrets'] = 'private'
    elif mutation == 'empty_rules': config['rules'] = []
    elif mutation == 'long_version': config['ruleset_version'] = 'x' * 33
    elif mutation == 'invalid_version': config['ruleset_version'] = 'version with spaces'
    elif mutation == 'duplicate_id': config['rules'].append(rule.copy())
    elif mutation == 'unknown_rule': rule['executable'] = 'private'
    elif mutation == 'regex': rule['when']['regex'] = '.*'
    elif mutation == 'empty_when': rule['when'] = {}
    elif mutation == 'empty_array': rule['when']['subject_phrases_any'] = []
    elif mutation == 'bad_array': rule['when']['subject_phrases_any'] = 'phrase'
    elif mutation == 'duplicate_phrase': rule['when']['subject_phrases_any'] = ['payment due', 'PAYMENT-DUE']
    elif mutation == 'bad_token': rule['when']['subject_tokens_all'] = ['two words', 'due']
    elif mutation == 'one_token': rule['when'] = {'subject_tokens_all':['insurance']}
    elif mutation == 'bad_domain': rule['when']['sender_domains_any'] = ['https://example.invalid']
    elif mutation == 'bad_suffix': rule['when']['sender_domain_suffixes_any'] = ['.example.invalid']
    elif mutation == 'bad_provider': rule['when']['providers'] = [False]
    elif mutation == 'empty_metadata': rule['when']['metadata_equals'] = {}
    elif mutation == 'unknown_metadata': rule['when']['metadata_equals'] = {'cursor':'opaque'}
    elif mutation == 'nan_metadata': rule['when']['metadata_equals'] = {'status':float('nan')}
    elif mutation == 'bad_present': rule['when']['metadata_present'] = ['subject']
    elif mutation == 'empty_prediction': rule['prediction'] = {}
    elif mutation == 'bad_label': rule['prediction']['action'] = 'maybe'
    elif mutation == 'bad_category': rule['prediction']['domain'] = ['unknown','unknown']
    elif mutation == 'wrong_subcategory': rule['prediction']['domain'] = ['home','flight']
    elif mutation == 'half_domain': rule['prediction']['domain'] = ['home']
    elif mutation == 'null_domain': rule['prediction']['domain'] = [None,None]
    elif mutation == 'bad_strength': rule['strength'] = .9
    elif mutation == 'too_many_rules': config['rules'] = [dict(rule,id=f'rule_{i}') for i in range(129)]
    elif mutation == 'too_many_phrases': rule['when']['subject_phrases_any'] = [f'phrase {i}' for i in range(33)]
    elif mutation == 'too_long_phrase': rule['when']['subject_phrases_any'] = ['x' * 129]
    elif mutation == 'context_only': rule['when'] = {'metadata_equals':{'mimeType':'application/pdf'}}
    path = tmp_path / 'bad.yaml'; path.write_text(yaml.safe_dump(config))
    with pytest.raises(AnalysisValidationError): load_rules(path, POLICY)


@pytest.mark.parametrize('extra', ['ruleset_version: duplicate\n', '\n  - id: duplicate\n    id: duplicate\n', '#' + 'x' * 65536])
def test_duplicate_yaml_keys_and_oversized_config_rejected(tmp_path, extra):
    path = tmp_path / 'bad.yaml'; path.write_text(extra + RULES_PATH.read_text())
    with pytest.raises(AnalysisValidationError): load_rules(path, POLICY)


@pytest.mark.parametrize('signal', ['sender_domains_any', 'sender_domain_suffixes_any'])
def test_sender_domain_is_a_boundary_checked_gate_not_a_classifier(tmp_path, signal):
    config = yaml.safe_load(RULES_PATH.read_text())
    config['rules'] = [config['rules'][0]]
    config['rules'][0]['when'][signal] = ['example.invalid']
    path = tmp_path / 'sender.yaml'; path.write_text(yaml.safe_dump(config))
    analyzer = MetadataRulesAnalyzer(load_rules(path, POLICY))
    def prediction(subject, sender): return analyzer.analyze(input_value(subject=subject,sender=sender), POLICY)
    assert prediction('Project update','person@example.invalid').category is None
    assert prediction('Insurance renewal due','person@evil-example.invalid').category is None
    assert prediction('Insurance renewal due','Insurance <person@example.invalid>').category == 'household_admin'
    assert (prediction('Insurance renewal due','person@news.example.invalid').category is not None) == (signal == 'sender_domain_suffixes_any')
    assert prediction('Insurance renewal due','person@example.invalid, other@example.invalid').category is None


def test_synthetic_evaluation_reproducible_with_meaningful_abstention():
    first = evaluate_cases(CASES, ANALYZER, POLICY)
    assert first == evaluate_cases(CASES, ANALYZER, POLICY)
    assert first.case_count == 30 and first.domain_predicted_count == 14
    assert .4 < first.domain_coverage < .6 and first.domain_abstention_rate > .5
    assert first.relevance_accuracy == pytest.approx(15/18)
    assert first.action_accuracy == pytest.approx(12/14)
    assert first.domain_accuracy == 1
    assert set(first.per_domain_support) == set(POLICY.categories)
    assert all(counts['labeled'] > 0 for counts in first.per_domain_support.values())
    assert first.confident_false_positives == {'relevant':0,'irrelevant':0,'action_required':0}


def test_abstention_persists_forces_review_and_preserves_current_history(engine):
    source = seed(engine)[0]
    output = good_output(category=None,subcategory=None,domain_confidence=.99,facts=())
    result = run(engine, source, SyntheticAnalyzer(output))
    assert result.analysis.domain_category is result.analysis.domain_subcategory is None
    assert result.analysis.review_recommended
    assert run(engine, source, SyntheticAnalyzer(output)).reused
    assert analysis_services.current_analysis(engine,'home',source['id'],analyzer_name='synthetic',analyzer_version='v1',policy=POLICY) == result.analysis
    assert analysis_services.analysis_history(engine,'home',source['id']) == (result.analysis,)
    assert not rows(engine,analysis_fact)


@pytest.mark.parametrize('category,subcategory', [('home',None),(None,'lease')])
def test_half_abstention_rejected_atomically(engine, category, subcategory):
    source = seed(engine)[0]
    with pytest.raises(AnalysisValidationError): run(engine,source,SyntheticAnalyzer(good_output(category=category,subcategory=subcategory)))
    assert not rows(engine,source_analysis) and not rows(engine,analysis_fact)


def test_database_abstention_state_requires_pair_and_review(engine):
    source = seed(engine)[0]; run(engine,source)
    base = rows(engine,source_analysis)[0]
    for changes in ({'domain_category':None}, {'domain_subcategory':None}, {'domain_category':None,'domain_subcategory':None,'review_recommended':False}):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(insert(source_analysis).values(**(base | {'id':'bad','analyzer_version':'bad'} | changes)))


def test_runtime_service_uses_phase2f_atomic_pending_and_versioned_identity(engine, tmp_path):
    sources = seed(engine,count=2)
    ingest(engine,'home','account',SyntheticConnector('Insurance renewal due',sources[0]['provider_object_id']))
    first = analysis_services.analyze_metadata(engine,'home',limit=1)
    assert first.created == first.selected == 1
    second = analysis_services.analyze_metadata(engine,'home',limit=10)
    assert second.created == 1
    assert analysis_services.analyze_metadata(engine,'home',limit=10).selected == 0
    assert len(rows(engine,source_analysis)) == 2 and not rows(engine,analysis_fact)
    assert any(a['domain_category'] is None and a['review_recommended'] for a in rows(engine,source_analysis))
    config = yaml.safe_load(RULES_PATH.read_text()); config['rules'][0]['when']['subject_phrases_any'].append('insurance renewal deadline')
    path = tmp_path / 'new.yaml'; path.write_text(yaml.safe_dump(config))
    assert analysis_services.analyze_metadata(engine,'home',limit=10,rules_path=path).created == 2
    assert len({a['analyzer_version'] for a in rows(engine,source_analysis)}) == 2


def test_cli_delegates_and_prints_only_aggregate_counters(engine, monkeypatch, capsys):
    calls=[]
    def service(*args, **kwargs):
        calls.append((args[1],kwargs)); return analysis_services.PendingAnalysisResult(3,2,0,1)
    monkeypatch.setattr(analysis_services,'analyze_metadata',service)
    assert main(['analyze-metadata','--household','home','--limit','3']) == 0
    assert json.loads(capsys.readouterr().out) == {'selected':3,'created':2,'reused':0,'stale':1}
    assert calls == [('home',{'limit':3,'classification_path':'config/classification.yaml','rules_path':'config/metadata-classifier.yaml'})]


def test_cli_runtime_and_errors_do_not_print_household_content(engine, capsys, caplog, tmp_path):
    source=seed(engine)[0]
    ingest(engine,'home','account',SyntheticConnector('Private synthetic Project update'))
    assert main(['analyze-metadata','--household','home','--limit','1']) == 0
    assert json.loads(capsys.readouterr().out)['created'] == 1
    bad=tmp_path/'bad.yaml'; bad.write_text('token: private-synthetic-secret')
    assert main(['analyze-metadata','--household','home','--limit','1','--rules-config',str(bad)]) == 1
    assert 'private-synthetic-secret' not in caplog.text + capsys.readouterr().out
    assert 'Project update' not in caplog.text


def test_migration_nullable_domain_preserves_phase2f_analysis_and_facts(engine):
    config=Config(str(ROOT/'alembic.ini'))
    command.downgrade(config,'508ac6578044')
    source=seed(engine)[0]; run(engine,source)
    before=[rows(engine,table) for table in (source_analysis,analysis_fact,source_record,raw_source_record)]
    command.upgrade(config,'head')
    assert [rows(engine,table) for table in (source_analysis,analysis_fact,source_record,raw_source_record)] == before
    command.check(config)
    command.downgrade(config,'508ac6578044')
    assert [rows(engine,table) for table in (source_analysis,analysis_fact,source_record,raw_source_record)] == before
    command.upgrade(config,'head')
    assert [rows(engine,table) for table in (source_analysis,analysis_fact,source_record,raw_source_record)] == before


def test_downgrade_with_abstention_fails_without_guessing_or_removing_history(engine):
    # Test the Phase 2G downgrade itself before later derived-table migrations.
    command.downgrade(Config(str(ROOT/'alembic.ini')), '7c19ad382ea1')
    source=seed(engine)[0]
    run(engine,source,SyntheticAnalyzer(good_output(category=None,subcategory=None,facts=())))
    before=rows(engine,source_analysis)
    with pytest.raises(RuntimeError,match='Cannot downgrade'):
        command.downgrade(Config(str(ROOT/'alembic.ini')),'508ac6578044')
    assert rows(engine,source_analysis) == before
    with engine.connect() as connection:
        assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar() == '7c19ad382ea1'
    command.upgrade(Config(str(ROOT/'alembic.ini')), 'head')
    assert rows(engine,source_analysis) == before
    command.check(Config(str(ROOT/'alembic.ini')))


def test_calendar_appointment_without_explicit_action_and_generic_drive_mime_abstain():
    output = classify('Vet appointment', provider='google_calendar', record_type='calendar_event',
                      raw_metadata={'status':'confirmed','start':{'dateTime':'2026-11-01T10:00:00Z'}})
    assert output.category is None and output.relevance_label == output.action_label == 'uncertain'
    for mime in ('application/pdf','application/vnd.google-apps.document','application/vnd.google-apps.shortcut'):
        output = classify('Project report',provider='google_drive',record_type='document',raw_metadata={'mimeType':mime})
        assert output.category is None and output.relevance_label == 'uncertain'


def test_product_scores_use_existing_thresholds_without_facts_or_calibration_claims():
    input = input_value(subject='Insurance renewal due')
    output = ANALYZER.analyze(input,POLICY)
    assert output.relevance_confidence == output.domain_confidence == output.action_confidence == .9
    values, facts = validate_output(output,input,POLICY)
    assert not values['review_recommended'] and not facts
    strict = replace(POLICY,threshold_policy_version='stricter-v2',thresholds=Thresholds(.95,.95,.95,.95))
    values, facts = validate_output(output,input,strict)
    assert values['review_recommended'] and not facts


def test_same_category_different_subcategory_conflict_is_not_resolved_by_order(tmp_path):
    config=yaml.safe_load(RULES_PATH.read_text())
    original=config['rules'][0]
    config['rules']=[original,dict(original,id='other',prediction={'domain':['household_admin','bill']})]
    path=tmp_path/'conflict.yaml';path.write_text(yaml.safe_dump(config))
    analyzer=MetadataRulesAnalyzer(load_rules(path,POLICY))
    output=analyzer.analyze(input_value(subject='Insurance renewal due'),POLICY)
    assert output.category is output.subcategory is None
    assert validate_output(output,input_value(),POLICY)[0]['review_recommended']


def test_metadata_gates_distinguish_boolean_from_number_and_require_actual_values(tmp_path):
    config=yaml.safe_load(RULES_PATH.read_text()); config['rules']=[config['rules'][0]]
    config['rules'][0]['when']['metadata_equals']={'trashed':False}
    config['rules'][0]['when']['metadata_present']=['start.date']
    path=tmp_path/'metadata.yaml';path.write_text(yaml.safe_dump(config))
    analyzer=MetadataRulesAnalyzer(load_rules(path,POLICY))
    for metadata in ({'trashed':0,'start':{'date':'2026-11-01'}},{'trashed':False,'start':{'date':None}},{}):
        assert analyzer.analyze(input_value(subject='Insurance renewal due',raw_metadata=metadata),POLICY).category is None
    assert analyzer.analyze(input_value(subject='Insurance renewal due',raw_metadata={'trashed':False,'start':{'date':'2026-11-01'}}),POLICY).category == 'household_admin'
