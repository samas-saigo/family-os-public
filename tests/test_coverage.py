"""Synthetic local coverage only. Never use a runtime household database."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import socket

import pytest
from sqlalchemy import update, event

from family_os import coverage_services as services
from family_os.analysis import validate_output, AnalysisValidationError, AnalysisNotFoundError
from family_os.cli import main
from family_os.schema import source_record, source_account, source_analysis, analysis_evaluation_label, raw_source_record, source_sync_state
from family_os.audit import HumanLabels
from family_os.audit_services import append_label, audit_metrics
from test_audit import create_analysis, ANALYZER, POLICY
from test_analysis import input_value, rows


@pytest.mark.parametrize('subject', [None, '', 'x'*8193, 'Project update', 'PAYMENT', 'Please renew',
    'Expiration', 'Appointment details', 'Insurance renewal due', 'Hotel reservation confirmed',
    'Utility bill payment due', 'Weekly newsletter', 'Order shipped',
    'Insurance renewal due hotel reservation confirmed', 'Maybe insurance renewal due',
    'ＩＮＳＵＲＡＮＣＥ renewal—due', 'Travel booking update', 'Monthly property statement'])
def test_runtime_and_diagnostic_semantics_are_identical(subject):
    input = input_value(subject=subject)
    diagnostic = ANALYZER.diagnose(input, POLICY)
    assert diagnostic.output == ANALYZER.analyze(input, POLICY)
    validate_output(diagnostic.output, input, POLICY)
    assert subject not in repr(diagnostic) if subject else True


@pytest.mark.parametrize('subject,state', [('Project update','no_evidence'),('PAYMENT','weak_only'),
    ('Insurance renewal due','strong_unanimous'), ('Insurance renewal due weekly newsletter','conflict')])
def test_evidence_reasons_are_not_threshold_explanations(subject,state):
    diagnostic=ANALYZER.diagnose(input_value(subject=subject),POLICY)
    assert diagnostic.states['action']==state
    if state=='weak_only': assert diagnostic.output.action_confidence==.55


def build(engine, provider='gmail', subject='Project update', month=1, account='account', record_type='message'):
    analysis=create_analysis(engine,provider,account=account)
    with engine.begin() as connection:
        connection.execute(update(source_record).where(source_record.c.id==analysis.source_record_id).values(
            subject=subject,record_type=record_type, occurred_at=datetime(2026,month,1,tzinfo=timezone.utc),
            raw_metadata={'status':'confirmed','start':{'dateTime':'2026-01-01T12:00:00Z'},
                          'location':'DO NOT DISPLAY','description':'PRIVATE BODY'}))
    # Synthetic setup updates the input before establishing its immutable analysis.
    with engine.begin() as connection:
        connection.execute(source_analysis.delete().where(source_analysis.c.id==analysis.id))
    from family_os.analysis_services import analyze_source
    return analyze_source(engine, 'home', analysis.source_record_id, ANALYZER, POLICY).analysis


def test_aggregate_per_provider_per_rule_zero_and_missing_counts(engine):
    build(engine,'gmail','Insurance renewal due',account='a')
    build(engine,'gmail','PAYMENT',account='b')
    build(engine,'google_calendar',None,account='c')
    build(engine,'google_drive','x'*8193,account='d')
    result=services.coverage_diagnostics(engine,'home',limit=100)
    assert result['inspected_count']==4
    gmail=result['providers']['gmail']
    assert gmail['any_rule_match']==2 and gmail['any_strong_rule_match']==1
    assert gmail['rule_matches']['insurance_renewal']==1
    assert gmail['rule_matches']['hotel_confirmation']==0
    assert gmail['dimensions']['action']['weak_only']==1
    assert gmail['dimensions']['domain']['no_evidence']==1
    assert gmail['missing_metadata']['mimeType']==2
    assert result['providers']['google_calendar']['subject']['missing']==1
    assert result['providers']['google_drive']['subject']['oversized']==1
    serialized=json.dumps(result)
    assert not any(secret in serialized for secret in ['Insurance renewal due','PRIVATE BODY','DO NOT DISPLAY','provider_object_id'])


def test_conflict_veto_and_context_gates(engine):
    build(engine,'gmail','Insurance renewal due hotel reservation confirmed',account='a')
    build(engine,'gmail','Maybe insurance renewal due',account='b')
    build(engine,'google_calendar','Vet appointment action required',account='c',record_type='calendar_event')
    build(engine,'gmail','Vet appointment action required',account='d')
    result=services.coverage_diagnostics(engine,'home',limit=20)['providers']
    assert result['gmail']['dimensions']['domain']['conflict']==1
    assert result['gmail']['caution_veto']==1
    assert result['gmail']['rule_matches']['vet_appointment']==0
    assert result['google_calendar']['rule_matches']['vet_appointment']==1


def test_diverse_selection_spans_all_providers_months_and_types_not_first_ids(engine,monkeypatch):
    from itertools import count
    from uuid import UUID
    sequence=count(1)
    monkeypatch.setattr('family_os.ingestion.uuid4',lambda:UUID(int=next(sequence)))
    for i in range(8): build(engine,'gmail',account=f'g{i}')
    for provider in ('outlook','google_calendar','google_drive'):
        for month in (1,7): build(engine,provider,month=month,account=f'{provider}{month}')
    build(engine,'gmail',month=7,account='late',record_type='document')
    first=services.coverage_sample(engine,'home',limit=8)
    assert first==services.coverage_sample(engine,'home',limit=8)
    assert {row['provider'] for row in first['records']}=={'gmail','outlook','google_calendar','google_drive'}
    assert all(sum(row['provider']==provider for row in first['records'])==2 for provider in ('gmail','outlook','google_calendar','google_drive'))
    assert {row['occurred_at'][5:7] for row in first['records']}=={'01','07'}
    assert len(first['records'])==8
    assert {row['source_record_id'] for row in first['records']} != {row['id'] for row in sorted(rows(engine,source_record),key=lambda row:row['id'])[:8]}


@pytest.mark.parametrize('limit',[0,-1,True,1.5,'10',1001,None])
@pytest.mark.parametrize('operation',[services.coverage_diagnostics,services.coverage_sample])
def test_invalid_limits_fail_closed(engine,limit,operation):
    with pytest.raises(AnalysisValidationError): operation(engine,'home',limit=limit)


def test_sample_small_bound_and_household_access(engine):
    with pytest.raises(AnalysisValidationError): services.coverage_sample(engine,'home',limit=101)
    with pytest.raises(AnalysisNotFoundError): services.coverage_diagnostics(engine,'missing',limit=10)


def test_read_only_display_allowlist_and_sql_privacy(engine,monkeypatch):
    build(engine)
    tables=(source_record,source_analysis,raw_source_record,analysis_evaluation_label,source_sync_state)
    before=[rows(engine,table) for table in tables]
    monkeypatch.setattr(socket,'socket',lambda *a,**k:pytest.fail('network'))
    statements=[]
    def guard(conn,cursor,statement,parameters,context,executemany):
        statements.append(statement)
        assert 'raw_source_record' not in statement and 'source_sync_state' not in statement
        assert 'source_account.metadata' not in statement and 'external_account' not in statement
        assert not statement.lstrip().lower().startswith(('insert','update','delete'))
    event.listen(engine,'before_cursor_execute',guard)
    try:
        aggregate=services.coverage_diagnostics(engine,'home',limit=20)
        sample=services.coverage_sample(engine,'home',limit=10)
    finally: event.remove(engine,'before_cursor_execute',guard)
    assert statements and aggregate['dry_run']
    assert sample['records'][0]['display_metadata']=={'status':'confirmed','start.dateTime':'2026-01-01T12:00:00Z'}
    assert not any(secret in json.dumps(sample) for secret in ('private_secret','PRIVATE BODY','DO NOT DISPLAY'))
    assert before==[rows(engine,table) for table in tables]


@pytest.mark.parametrize('changed', ['raw_record_id','analyzer_version','taxonomy_version','threshold_policy_version'])
def test_sample_never_substitutes_historical_definition_or_snapshot(engine,changed):
    analysis=build(engine)
    with engine.begin() as connection:
        if changed=='raw_record_id':
            from uuid import uuid4
            raw = next(row for row in rows(engine,raw_source_record) if row['id']==analysis.raw_record_id)
            raw = dict(raw, id=str(uuid4()), payload_hash='synthetic-new-snapshot')
            connection.execute(raw_source_record.insert().values(**raw))
            connection.execute(update(source_record).where(source_record.c.id==analysis.source_record_id).values(raw_record_id=raw['id']))
        else:
            connection.execute(update(source_analysis).where(source_analysis.c.id==analysis.id).values(**{changed:'historical'}))
    sample=services.coverage_sample(engine,'home',limit=1)['records'][0]
    assert sample['analysis_id'] is None and sample['prediction_origin']=='dry_run'
    assert audit_metrics(engine,'home')['eligible_count']==0


def test_explicit_source_analysis_then_append_label_uses_existing_contract(engine):
    build(engine,subject='Insurance renewal due')
    # Remove synthetic controlled analysis; this setup is not a production operation.
    with engine.begin() as connection: connection.execute(source_analysis.delete())
    source=rows(engine,source_record)[0]
    sample=services.coverage_sample(engine,'home',limit=1)['records'][0]
    assert sample['analysis_id'] is None and not rows(engine,source_analysis)
    result=services.analyze_metadata_source(engine,'home',source['id'])
    again=services.analyze_metadata_source(engine,'home',source['id'])
    assert again['reused'] and again['analysis_id']==result['analysis_id']
    first=append_label(engine,'home',result['analysis_id'],HumanLabels('uncertain',None,None,'uncertain'))
    second=append_label(engine,'home',result['analysis_id'],HumanLabels('relevant','household_admin','insurance','required'))
    assert (first.revision,second.revision)==(1,2)
    assert audit_metrics(engine,'home')['labeled_count']==1


@pytest.mark.parametrize('command',['metadata-coverage','metadata-coverage-sample'])
def test_cli_privacy_and_local_warning(engine,monkeypatch,capsys,command):
    build(engine,subject='PRIVATE SUBJECT')
    monkeypatch.setattr('family_os.cli.create_db',lambda _:engine)
    assert main([command,'--household','home','--limit','1'])==0
    captured=capsys.readouterr()
    result=json.loads(captured.out)
    if command=='metadata-coverage':
        assert 'PRIVATE SUBJECT' not in captured.out and not captured.err
    else:
        assert 'LOCAL SENSITIVE OUTPUT' in captured.err
        assert result['records'][0]['subject']=='PRIVATE SUBJECT'


def test_cli_explicit_source_prints_safe_ids_only(engine,monkeypatch,capsys):
    analysis=build(engine,subject='PRIVATE SUBJECT')
    monkeypatch.setattr('family_os.cli.create_db',lambda _:engine)
    assert main(['analyze-metadata','--household','home','--source',analysis.source_record_id])==0
    output=capsys.readouterr().out
    assert json.loads(output)['analysis_id']==analysis.id and 'PRIVATE SUBJECT' not in output

from test_metadata_classifier import CASES

@pytest.mark.parametrize('case', CASES, ids=lambda case:case['id'])
def test_entire_committed_evaluation_corpus_uses_identical_diagnostic_resolution(case):
    data=case['input']
    input=input_value(subject=data['subject'],provider=data['provider'],record_type=data['record_type'],
                      sender=data.get('sender'),raw_metadata=data.get('raw_metadata',{}))
    assert ANALYZER.diagnose(input,POLICY).output==ANALYZER.analyze(input,POLICY)


def test_empty_household_returns_zero_counts_without_content(engine):
    from family_os.schema import household
    with engine.begin() as connection: connection.execute(household.insert().values(id='empty',name='Synthetic'))
    assert services.coverage_diagnostics(engine,'empty',limit=10)['inspected_count']==0
    assert services.coverage_sample(engine,'empty',limit=10)['records']==[]


def test_missing_gated_metadata_remains_no_evidence_not_threshold_miss(engine):
    analysis=build(engine,'google_calendar','Vet appointment action required',record_type='calendar_event')
    with engine.begin() as connection:
        connection.execute(update(source_record).where(source_record.c.id==analysis.source_record_id).values(raw_metadata={}))
    result=services.coverage_diagnostics(engine,'home',limit=10)['providers']['google_calendar']
    assert result['rule_matches']['vet_appointment']==0
    assert result['missing_metadata']['start.dateTime']==1
    assert result['dimensions']['domain']['no_evidence']==1


def test_undated_and_multiple_accounts_counted_under_one_provider(engine):
    first=build(engine,'outlook',account='a')
    build(engine,'outlook',account='b')
    with engine.begin() as connection:
        connection.execute(update(source_record).where(source_record.c.id==first.source_record_id).values(occurred_at=None))
    result=services.coverage_diagnostics(engine,'home',limit=10)
    assert result['provider_population_counts']=={'outlook':2}
    assert result['providers']['outlook']['time_buckets']=={'202601':1,'undated':1}


def test_small_limit_discloses_unsampled_provider_population(engine):
    build(engine,'gmail',account='a')
    build(engine,'outlook',account='b')
    result=services.coverage_diagnostics(engine,'home',limit=1)
    assert result['provider_population_counts']=={'gmail':1,'outlook':1}
    assert result['inspected_count']==1 and result['current_source_count']==2


def test_cli_error_logs_never_echo_private_failure(engine,monkeypatch,capsys,caplog):
    monkeypatch.setattr('family_os.cli.create_db',lambda _:engine)
    def fail(*args,**kwargs): raise RuntimeError('PRIVATE https://private.invalid TOKEN subject')
    monkeypatch.setattr(services,'coverage_diagnostics',fail)
    assert main(['metadata-coverage','--household','home','--limit','1'])==1
    captured=capsys.readouterr()
    assert 'PRIVATE' not in captured.out+captured.err+caplog.text

@pytest.mark.parametrize('dimension,target', [('relevance','relevant'),('action','required'),('domain',['home','utility'])])
@pytest.mark.parametrize('strengths,state', [(['weak'],'weak_only'),(['weak','strong'],'strong_unanimous')])
def test_diagnostic_dimension_strengths_follow_shared_resolver(tmp_path,dimension,target,strengths,state):
    import yaml
    from family_os.metadata_classifier import load_rules, MetadataRulesAnalyzer
    path=tmp_path/'synthetic-rules.yaml'
    path.write_text(yaml.safe_dump({'ruleset_version':'synthetic-v1','rules':[
        {'id':f'rule_{i}','strength':strength,'when':{'subject_phrases_any':['explicit signal']},
         'prediction':{dimension:target}} for i,strength in enumerate(strengths)]}))
    analyzer=MetadataRulesAnalyzer(load_rules(path,POLICY))
    diagnostic=analyzer.diagnose(input_value(subject='Explicit signal'),POLICY)
    assert diagnostic.states[dimension]==state
    assert diagnostic.output==analyzer.analyze(input_value(subject='Explicit signal'),POLICY)
    score=getattr(diagnostic.output,dimension+'_confidence')
    assert score==(.55 if state=='weak_only' else .9)


def test_sample_cross_household_and_analysis_identity_unchanged(engine):
    build(engine)
    from family_os.schema import household
    with engine.begin() as connection: connection.execute(household.insert().values(id='other',name='Synthetic'))
    before=rows(engine,source_analysis)
    assert services.coverage_sample(engine,'other',limit=10)['records']==[]
    assert services.coverage_diagnostics(engine,'other',limit=10)['current_source_count']==0
    with pytest.raises(AnalysisNotFoundError): services.analyze_metadata_source(engine,'other',before[0]['source_record_id'])
    assert rows(engine,source_analysis)==before


def test_classifier_runs_after_read_snapshot_closes_and_cannot_load_credentials(engine,monkeypatch):
    build(engine)
    from family_os.metadata_classifier import MetadataRulesAnalyzer
    from family_os import gmail_auth, outlook_auth, google_calendar_auth, google_drive_auth
    import keyring
    for module in (gmail_auth,outlook_auth,google_calendar_auth,google_drive_auth):
        monkeypatch.setattr(module,'load_client',lambda *args,**kwargs:pytest.fail('provider client'))
    monkeypatch.setattr(keyring,'get_password',lambda *args,**kwargs:pytest.fail('keyring'))
    diagnose=MetadataRulesAnalyzer.diagnose
    def checked(self,input,taxonomy):
        assert engine.pool.checkedout()==0
        return diagnose(self,input,taxonomy)
    monkeypatch.setattr(MetadataRulesAnalyzer,'diagnose',checked)
    services.coverage_diagnostics(engine,'home',limit=1)
    services.coverage_sample(engine,'home',limit=1)
