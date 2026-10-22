"""Synthetic-only acceptance for local exact-snapshot classifier evaluation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import socket
from threading import Barrier

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import select, insert, update, delete, inspect, event
from sqlalchemy.exc import IntegrityError

from family_os import audit_services as services
from family_os.audit import HumanLabels, CandidateThresholds, validate_labels, simulate_thresholds
from family_os.analysis import AnalysisOutput, AnalysisValidationError, AnalysisNotFoundError, AnalysisDefinitionConflictError, Thresholds
from family_os.analysis_services import analyze_source
from family_os.metadata_classifier import MetadataRulesAnalyzer, load_rules
from family_os.cli import main
from family_os.storage import insert_for
from family_os.schema import source_sync_state, household as households, analysis_evaluation_label as labels, source_account, source_record, source_analysis, analysis_fact, raw_source_record
from family_os.ingestion import ingest
from test_analysis import seed, rows, POLICY, ROOT, TIME, SyntheticConnector, SyntheticAnalyzer, run

RULES = ROOT / 'config/metadata-classifier.yaml'
ANALYZER = MetadataRulesAnalyzer(load_rules(RULES, POLICY))


class ControlledAnalyzer:
    """Synthetic deliberately wrong predictions under the current declared definition."""
    name = ANALYZER.name
    version = ANALYZER.version
    def __init__(self, output): self.output = output
    def analyze(self, input, taxonomy): return self.output


def create_analysis(engine, provider='gmail', output=None, *, household='home', account='account', analyzer=None, policy=POLICY):
    # Synthetic DB setup avoids OAuth/mailbox registration while retaining FKs.
    with engine.begin() as connection:
        connection.execute(insert_for(connection, households).values(id=household,name='Synthetic').on_conflict_do_nothing())
        connection.execute(source_account.insert().values(id=account,household_id=household,provider='fixture',
            owner_type='unknown',owner_id=None,person_owner_id=None,external_account=None,enabled=True,metadata={}))
        connection.execute(source_sync_state.insert().values(source_account_id=account,cursor=None,version=0,updated_at=TIME))
    ingest(engine,household,account,SyntheticConnector())
    source = next(r for r in rows(engine,source_record) if r['source_account_id']==account)
    with engine.begin() as connection:
        connection.execute(update(source_account).where(source_account.c.id == account).values(provider=provider))
    output = output or AnalysisOutput('relevant', .9, 'home', 'lease', .9, 'not_required', .9)
    result = analyze_source(engine, household, source['id'], analyzer or ControlledAnalyzer(output), policy)
    return result.analysis


def label(engine, analysis, human=None, **options):
    return services.append_label(engine, analysis.household_id, analysis.id,
        human or HumanLabels('relevant', 'home', 'lease', 'not_required'), **options)


@pytest.fixture
def corpus(engine):
    predictions = [
        ('gmail', AnalysisOutput('relevant', .9, 'home','lease', .9, 'not_required', .9)),
        ('outlook', AnalysisOutput('relevant', .9, 'travel','hotel', .9, 'required', .9)),
        ('google_calendar', AnalysisOutput('uncertain', 0, None,None, 0, 'uncertain', .55)),
        ('google_drive', AnalysisOutput('irrelevant', .9, 'ignore','marketing', .9, 'not_required', .9)),
        ('gmail', AnalysisOutput('relevant', .85, 'home','utility', .85, 'required', .85)),
        ('google_drive', AnalysisOutput('uncertain', 0, None,None, 0, 'uncertain', 0)),
    ]
    analyses = [create_analysis(engine, provider, output, account=f'account-{i}') for i,(provider,output) in enumerate(predictions)]
    humans = [HumanLabels('relevant','home','lease','not_required'),
        HumanLabels('irrelevant','ignore','marketing','not_required'),
        HumanLabels('relevant','pet','vet_visit','required'),
        HumanLabels('uncertain',None,None,'uncertain'),
        HumanLabels('irrelevant','ignore','marketing','not_required')]
    for analysis, human in zip(analyses, humans): label(engine, analysis, human)
    label(engine, analyses[1], HumanLabels('relevant','travel','hotel','not_required'))
    return analyses


def test_revision_append_preserves_analysis_fact_history_and_safe_result(engine):
    analysis=create_analysis(engine)
    before=rows(engine,source_analysis),rows(engine,analysis_fact)
    first=label(engine,analysis)
    second=label(engine,analysis,HumanLabels('uncertain',None,None,'uncertain'))
    assert (first.revision,second.revision)==(1,2)
    assert first.id != second.id
    assert set(asdict(second))=={'id','analysis_id','source_record_id','revision'}
    assert (rows(engine,source_analysis),rows(engine,analysis_fact))==before
    assert [r['revision'] for r in sorted(rows(engine,labels),key=lambda r:r['revision'])]==[1,2]
    assert not {'canonical_entity','review_queue','task','action'} & set(inspect(engine).get_table_names())


@pytest.mark.parametrize('change', [dict(relevance_label='yes'),dict(action_label='maybe'),dict(domain_category='unknown'),
    dict(domain_subcategory=None),dict(domain_category=None),dict(domain_subcategory='hotel'),dict(domain_category=[]),dict(relevance_label=None)])
def test_invalid_labels_fail_atomically(engine,change):
    analysis=create_analysis(engine)
    with pytest.raises(AnalysisValidationError): label(engine,analysis,replace(HumanLabels('relevant','home','lease','not_required'),**change))
    assert not rows(engine,labels)


def test_no_narrative_payload_or_reviewer_identity(engine):
    analysis=create_analysis(engine)
    with pytest.raises(AnalysisValidationError): services.append_label(engine,'home',analysis.id,{'relevance_label':'relevant','notes':'private'})
    assert not {'notes','reasoning','reviewer','user_id'} & {c.name for c in labels.columns}
    assert not rows(engine,labels)


@pytest.mark.parametrize('operation',['list','metrics','simulate','label'])
def test_household_lookup_and_cross_household_rejected(engine,operation):
    analysis=create_analysis(engine)
    seed(engine,'other','other-account')
    with pytest.raises(AnalysisNotFoundError):
        if operation=='label': services.append_label(engine,'other',analysis.id,HumanLabels('uncertain',None,None,'uncertain'))
        elif operation=='list': services.audit_list(engine,'missing',limit=1)
        elif operation=='metrics': services.audit_metrics(engine,'missing')
        else: services.audit_simulate(engine,'missing',CandidateThresholds(.8,.8,.8))
    assert services.audit_metrics(engine,'other')['eligible_count']==0


@pytest.mark.parametrize('column,value',[('household_id','other'),('source_record_id','other'),('analysis_id','other'),
    ('revision',0),('revision',-1),('relevance_label','invalid'),('action_label','invalid'),
    ('domain_category',None),('domain_subcategory',None)])
def test_database_scope_revision_and_label_constraints(engine,column,value):
    analysis=create_analysis(engine); label(engine,analysis)
    bad=rows(engine,labels)[0] | {'id':'bad','revision':2,column:value}
    with pytest.raises((IntegrityError,ValueError)),engine.begin() as connection:
        connection.execute(insert(labels).values(**bad))
    assert len(rows(engine,labels))==1


def test_unique_revision_and_no_provenance_cascade(engine):
    analysis=create_analysis(engine); label(engine,analysis)
    row=rows(engine,labels)[0]
    with pytest.raises(IntegrityError),engine.begin() as connection: connection.execute(insert(labels).values(**(row|{'id':'other'})))
    with pytest.raises(IntegrityError),engine.begin() as connection: connection.execute(delete(source_analysis).where(source_analysis.c.id==analysis.id))
    assert len(rows(engine,labels))==len(rows(engine,source_analysis))==1


def test_concurrent_labeling_distinct_monotonic_revisions_without_lost_labels(engine):
    analysis=create_analysis(engine)
    barrier=Barrier(2)
    def before_lock(connection,cursor,statement,parameters,context,executemany):
        if statement == 'BEGIN IMMEDIATE' or ('FROM source_analysis' in statement and 'FOR UPDATE' in statement):
            barrier.wait(timeout=10)
    values=[HumanLabels('relevant','home','lease','required'),HumanLabels('irrelevant','ignore','marketing','not_required')]
    def append(human):
        return label(engine,analysis,human)
    event.listen(engine,'before_cursor_execute',before_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(append,values))
    finally:
        event.remove(engine,'before_cursor_execute',before_lock)
    assert sorted(r.revision for r in results)==[1,2]
    stored=rows(engine,labels)
    assert {r['relevance_label'] for r in stored}=={'relevant','irrelevant'}
    assert len({r['id'] for r in stored})==2


@pytest.mark.parametrize('strategy,expected',[('unlabeled',1),('needs_review',2),('accepted',4),('balanced',6)])
def test_sampling_strategies_bounded_and_repeatable(engine,corpus,strategy,expected):
    first=services.audit_list(engine,'home',limit=100,strategy=strategy)
    assert len(first.records)==expected and first.eligible_count==first.current_source_count==6 and first.missing_count==0
    assert first==services.audit_list(engine,'home',limit=100,strategy=strategy)
    limited=services.audit_list(engine,'home',limit=1,strategy=strategy)
    assert limited.records==first.records[:1]
    if strategy!='balanced': assert [r.source_record_id for r in first.records]==sorted(r.source_record_id for r in first.records)


@pytest.mark.parametrize('limit',[0,-1,True,1.0,None,1001])
def test_bounded_positive_limit(engine,limit):
    with pytest.raises(AnalysisValidationError): services.audit_list(engine,'home',limit=limit)


def test_balanced_round_robin_joint_strata_not_random(engine):
    analyses=[create_analysis(engine,'gmail',account=f'a{i}') for i in range(4)]
    other=create_analysis(engine,'outlook',account='b')
    sample=services.audit_list(engine,'home',strategy='balanced',limit=2)
    assert {r.provider for r in sample.records}=={'gmail','outlook'}
    assert services.audit_list(engine,'home',strategy='balanced',limit=100).records[0].source_record_id==min(a.source_record_id for a in analyses)


@pytest.mark.parametrize('kind',['raw','analyzer','taxonomy','threshold','rules'])
def test_current_definition_snapshot_missing_never_substitutes(engine,tmp_path,kind):
    analysis=create_analysis(engine)
    label(engine,analysis)
    options={}
    if kind=='raw':
        with engine.begin() as connection: connection.execute(update(source_account).where(source_account.c.id=='account').values(provider='fixture'))
        ingest(engine,'home','account',SyntheticConnector('Snapshot B'))
        with engine.begin() as connection: connection.execute(update(source_account).where(source_account.c.id=='account').values(provider='gmail'))
    elif kind=='rules':
        path=tmp_path/'rules.yaml';path.write_text(RULES.read_text().replace('metadata-v1','metadata-v2'))
        options['rules_path']=path
    else:
        with engine.begin() as connection:
            connection.execute(update(source_analysis).where(source_analysis.c.id==analysis.id).values(**{
                {'analyzer':'analyzer_version','taxonomy':'taxonomy_version','threshold':'threshold_policy_version'}[kind]:'old-version'}))
    sample=services.audit_list(engine,'home',limit=10,strategy='balanced',**options)
    assert sample.missing_count==1 and sample.eligible_count==0 and not sample.records
    metrics=services.audit_metrics(engine,'home',**options)
    assert metrics['eligible_count']==metrics['labeled_count']==0 and metrics['missing_count']==1
    assert metrics['relevance_accuracy'] is metrics['domain_selective_accuracy'] is metrics['action_accuracy'] is None
    assert services.audit_simulate(engine,'home',CandidateThresholds(0,0,0),**options)['eligible_count']==0


def test_changed_policy_content_without_version_bump_fails_closed(engine,tmp_path):
    create_analysis(engine)
    path=tmp_path/'classification.yaml';path.write_text((ROOT/'config/classification.yaml').read_text().replace('relevance: 0.80','relevance: 0.85'))
    for operation in (lambda:services.audit_list(engine,'home',limit=1,classification_path=path),
                      lambda:services.audit_metrics(engine,'home',classification_path=path)):
        with pytest.raises(AnalysisDefinitionConflictError): operation()


def test_display_allowlist_excludes_payload_account_secrets_and_arbitrary_metadata(engine,monkeypatch,caplog):
    analysis=create_analysis(engine)
    private='synthetic-secret-sentinel'
    with engine.begin() as connection:
        connection.execute(update(source_account).values(metadata={'client_secret':private}))
        connection.execute(update(raw_source_record).values(payload={'body':private,'token':private}))
        connection.execute(update(source_record).values(raw_metadata={'status':'confirmed','eventType':'default',
            'start':{'dateTime':'2026-11-01T12:30:00Z','date':'2026-11-01','secret':private},
            'end':{'dateTime':'2026-11-01T13:30:00Z','date':'2026-11-01'},
            'mimeType':'application/pdf','trashed':False,'removed':True,'access_token':private,'arbitrary':private}))
    def forbidden(*args,**kwargs): pytest.fail('Unexpected external or raw-payload access')
    monkeypatch.setattr(socket,'socket',forbidden)
    monkeypatch.setattr(MetadataRulesAnalyzer,'analyze',forbidden)
    from family_os import gmail_auth,google_calendar_auth,google_drive_auth,outlook_auth
    for module in (gmail_auth,google_calendar_auth,google_drive_auth,outlook_auth):
        monkeypatch.setattr(module,'load_client',forbidden)
    import keyring
    monkeypatch.setattr(keyring,'get_password',forbidden)
    queries=[]
    def sql(connection,cursor,statement,parameters,context,executemany):
        queries.append(statement)
        assert 'raw_source_record' not in statement
        assert 'source_account.metadata' not in statement
    event.listen(engine,'before_cursor_execute',sql)
    try:
        sample=services.audit_list(engine,'home',limit=1,strategy='balanced')
        display_query_count=len(queries)
        metrics=services.audit_metrics(engine,'home')
        services.audit_simulate(engine,'home',CandidateThresholds(.8,.8,.8))
        label(engine,analysis)
    finally: event.remove(engine,'before_cursor_execute',sql)
    display=sample.records[0].display_metadata
    assert set(display)==set(services.DISPLAY_FIELDS)
    assert private not in json.dumps(asdict(sample)) + json.dumps(metrics) + caplog.text
    assert 'Synthetic lease' not in repr(sample)
    assert not any(any(field in q for field in ('source_record.raw_metadata','source_record.subject','source_record.sender')) for q in queries[display_query_count:])


def test_display_invalid_and_oversized_values_are_not_serialized(engine):
    create_analysis(engine)
    with engine.begin() as connection:
        connection.execute(update(source_record).values(subject='x'*8193,sender='x'*321,
            raw_metadata={'status':{'secret':'hidden'},'mimeType':'x'*257,'trashed':1,'removed':'yes','start':{'date':None}}))
    record=services.audit_list(engine,'home',limit=1,strategy='balanced').records[0]
    assert record.subject is record.sender is None and record.display_metadata=={}


def test_metrics_exact_latest_revision_unknowns_and_provider_domain_breakdown(engine,corpus):
    metrics=services.audit_metrics(engine,'home')
    assert (metrics['eligible_count'],metrics['labeled_count'],metrics['unlabeled_count'])==(6,5,1)
    assert metrics['label_coverage']==5/6 and metrics['classifier_review_rate']==2/6
    assert metrics['classifier_domain_abstention_rate']==2/6 and metrics['domain_coverage']==4/6
    assert metrics['relevance_accuracy']==2/4 and metrics['action_accuracy']==1/4
    assert metrics['domain_selective_accuracy']==2/3
    assert metrics['human_uncertain_relevance']==metrics['human_uncertain_action']==metrics['human_unknown_domain']==1
    assert metrics['concrete_predictions']['relevant']==dict(evaluated=3,correct=2,false_positive=1,human_uncertain=0,precision=2/3)
    assert metrics['concrete_predictions']['action_required']['false_positive']==2
    assert metrics['concrete_predictions']['action_required']['precision']==0
    assert metrics['concrete_predictions']['irrelevant']['precision'] is None
    assert metrics['concrete_predictions']['irrelevant']['human_uncertain']==1
    assert metrics['per_domain']['home']==dict(labeled=1,predicted=2,correct=1)
    assert metrics['per_domain']['travel']==dict(labeled=1,predicted=1,correct=1)
    assert metrics['per_domain']['pet']==dict(labeled=1,predicted=0,correct=0)
    assert metrics['providers']['gmail']['eligible_count']==metrics['providers']['gmail']['labeled_count']==2
    assert metrics['providers']['google_drive']['labeled_count']==1
    assert metrics['providers']['google_calendar']['domain_selective_accuracy'] is None


def test_latest_revision_not_latest_timestamp(engine,monkeypatch):
    analysis=create_analysis(engine)
    class Clock:
        current=TIME+timedelta(days=100)
        @classmethod
        def now(cls,tz): return cls.current
    monkeypatch.setattr(services,'datetime',Clock)
    label(engine,analysis,HumanLabels('irrelevant','ignore','marketing','required'))
    Clock.current=TIME
    label(engine,analysis)
    assert services.audit_metrics(engine,'home')['relevance_accuracy']==1
    assert services.audit_list(engine,'home',limit=1,strategy='accepted').records[0].latest_human_revision==2


def test_zero_denominators_and_unlabeled_not_human_uncertain(engine):
    seed(engine)
    empty=services.audit_metrics(engine,'home')
    assert empty['missing_count']==1 and empty['eligible_count']==0
    for key in ('label_coverage','classifier_review_rate','classifier_domain_abstention_rate','domain_coverage','relevance_accuracy','domain_selective_accuracy','action_accuracy'):
        assert empty[key] is None
    analysis=create_analysis(engine,account='second')
    unlabeled=services.audit_metrics(engine,'home')
    assert unlabeled['unlabeled_count']==1 and unlabeled['human_uncertain_relevance']==0 and unlabeled['relevance_accuracy'] is None
    label(engine,analysis,HumanLabels('uncertain',None,None,'uncertain'))
    unknown=services.audit_metrics(engine,'home')
    assert unknown['labeled_count']==1 and unknown['unlabeled_count']==0 and unknown['human_uncertain_relevance']==1
    assert unknown['relevance_accuracy'] is unknown['action_accuracy'] is unknown['domain_selective_accuracy'] is None


def test_threshold_simulation_exact_pure_counts_and_no_history_config_mutation(engine,corpus):
    before=rows(engine,source_analysis),rows(engine,labels),rows(engine,analysis_fact),(ROOT/'config/classification.yaml').read_bytes()
    normal=services.audit_simulate(engine,'home',CandidateThresholds(.8,.8,.8))
    stricter=services.audit_simulate(engine,'home',CandidateThresholds(.9,.9,.9))
    assert (normal['accepted_count'],normal['review_count'],normal['observed_joint_precision'],normal['observed_labeled_coverage'])==(4,2,1/3,3/4)
    assert (stricter['accepted_count'],stricter['review_count'],stricter['observed_joint_precision'],stricter['observed_labeled_coverage'])==(3,3,1/2,2/4)
    assert stricter['accepted_delta']==-1 and stricter['review_delta']==1
    zero=services.audit_simulate(engine,'home',CandidateThresholds(.95,.95,.95))
    assert zero['accepted_count']==0 and zero['observed_joint_precision'] is None
    assert services.audit_simulate(engine,'home',CandidateThresholds(0,0,0))['accepted_count']==4
    assert before==(rows(engine,source_analysis),rows(engine,labels),rows(engine,analysis_fact),(ROOT/'config/classification.yaml').read_bytes())


@pytest.mark.parametrize('value',[-1,2,float('nan'),float('inf'),True,'0.8',None])
def test_invalid_thresholds_rejected(value):
    with pytest.raises(AnalysisValidationError): CandidateThresholds(value,.8,.8)


def test_cli_list_label_metrics_simulate_and_safe_outputs(engine,capsys,caplog):
    analysis=create_analysis(engine)
    base=['--household','home']
    assert main(['metadata-audit-list',*base,'--limit','1','--strategy','accepted'])==0
    display=json.loads(capsys.readouterr().out)
    assert display['records'][0]['subject']=='Synthetic lease'
    assert main(['metadata-audit-label',*base,'--analysis',analysis.id,'--relevance','relevant','--domain-category','home','--domain-subcategory','lease','--action','not_required'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['revision']==1 and set(result)=={'id','analysis_id','source_record_id','revision'}
    assert main(['metadata-audit-metrics',*base])==0
    metrics=json.loads(capsys.readouterr().out);assert metrics['relevance_accuracy']==1
    assert 'Synthetic lease' not in json.dumps(metrics)
    assert main(['metadata-audit-simulate',*base,'--relevance-threshold','.95','--domain-threshold','.95','--action-threshold','.95'])==0
    assert json.loads(capsys.readouterr().out)['accepted_count']==0
    assert main(['metadata-audit-label',*base,'--analysis','private-synthetic-unknown','--relevance','uncertain','--action','uncertain'])==1
    assert 'private-synthetic-unknown' not in caplog.text


def test_migration_roundtrip_preserves_all_analysis_source_and_fact_history(engine):
    source=seed(engine)[0]; run(engine,source)
    analysis=rows(engine,source_analysis)[0]
    services.append_label(engine,'home',analysis['id'],HumanLabels('uncertain',None,None,'uncertain'))
    parents=(source_analysis,analysis_fact,source_record,raw_source_record,source_account)
    before=[rows(engine,table) for table in parents]
    config=Config(str(ROOT/'alembic.ini'));command.check(config)
    command.downgrade(config,'7c19ad382ea1')
    assert 'analysis_evaluation_label' not in inspect(engine).get_table_names()
    assert [rows(engine,table) for table in parents]==before
    command.upgrade(config,'head');command.check(config)
    assert [rows(engine,table) for table in parents]==before
    assert not rows(engine,labels)


def test_historical_label_does_not_transfer_to_new_current_snapshot(engine):
    old=create_analysis(engine,provider='fixture')
    label(engine,old)
    ingest(engine,'home','account',SyntheticConnector('Project update'))
    missing=services.audit_metrics(engine,'home')
    assert missing['eligible_count']==0 and missing['missing_count']==1
    source=rows(engine,source_record)[0]
    current=analyze_source(engine,'home',source['id'],ANALYZER,POLICY).analysis
    sample=services.audit_list(engine,'home',limit=10,strategy='unlabeled')
    assert len(sample.records)==1 and sample.records[0].analysis_id==current.id
    assert sample.records[0].raw_record_id != old.raw_record_id
    assert sample.records[0].latest_human_revision is None
    assert services.audit_metrics(engine,'home')['labeled_count']==0
    assert len(rows(engine,labels))==1 and len(rows(engine,source_analysis))==2


def test_old_and_current_definitions_coexist_without_mixed_labels(engine):
    old_analyzer=ControlledAnalyzer(AnalysisOutput('relevant',.9,'home','lease',.9,'not_required',.9))
    old_analyzer.version='old-rules-v1'
    old=create_analysis(engine,analyzer=old_analyzer)
    label(engine,old)
    source=rows(engine,source_record)[0]
    new=analyze_source(engine,'home',source['id'],ANALYZER,POLICY).analysis
    sample=services.audit_list(engine,'home',limit=10,strategy='balanced')
    assert [r.analysis_id for r in sample.records]==[new.id]
    assert sample.records[0].latest_human_revision is None
    assert services.audit_metrics(engine,'home')['labeled_count']==0


def test_snapshot_counts_and_rows_are_consistent_during_concurrent_ingestion(engine):
    old=create_analysis(engine,provider='fixture')
    updated=False
    def change_after_count(connection,cursor,statement,parameters,context,executemany):
        nonlocal updated
        if statement.startswith('SELECT count(') and not updated:
            updated=True
            ingest(engine,'home','account',SyntheticConnector('New snapshot'))
    # SQLite's rollback journal intentionally blocks a concurrent writer under
    # a read snapshot. WAL permits this race without weakening snapshot isolation.
    if engine.dialect.name=='sqlite':
        with engine.connect() as connection: connection.exec_driver_sql('PRAGMA journal_mode=WAL')
    event.listen(engine,'after_cursor_execute',change_after_count)
    try:
        sample=services.audit_list(engine,'home',limit=1,strategy='accepted')
    finally: event.remove(engine,'after_cursor_execute',change_after_count)
    assert updated and sample.eligible_count==1 and sample.records[0].analysis_id==old.id
    assert services.audit_metrics(engine,'home')['missing_count']==1


def test_audit_cli_is_presentation_adapter(engine,monkeypatch,capsys):
    calls=[]
    def metrics(engine,household,**options):
        calls.append((household,options));return {'eligible_count':0}
    monkeypatch.setattr(services,'audit_metrics',metrics)
    assert main(['metadata-audit-metrics','--household','home'])==0
    assert json.loads(capsys.readouterr().out)=={'eligible_count':0}
    assert calls==[('home',dict(classification_path='config/classification.yaml',rules_path='config/metadata-classifier.yaml'))]


def test_empty_threshold_simulation_returns_null_denominators():
    result=simulate_thresholds(iter(()),CandidateThresholds(.8,.8,.8))
    assert result['eligible_count']==result['accepted_count']==result['review_count']==0
    assert result['observed_joint_precision'] is result['observed_labeled_coverage'] is None


def test_database_fractional_revision_fails_on_sqlite_integer_affinity(engine):
    analysis=create_analysis(engine);label(engine,analysis)
    row=rows(engine,labels)[0]|{'id':'fraction','revision':1.5}
    if engine.dialect.name=='sqlite':
        with pytest.raises(IntegrityError),engine.begin() as connection: connection.execute(insert(labels).values(**row))
    else:
        assert str(labels.c.revision.type)=='INTEGER'  # PostgreSQL stores an integer natively.


def test_invalid_sampling_strategy_fails_closed(engine):
    with pytest.raises(AnalysisValidationError): services.audit_list(engine,'home',limit=1,strategy='random')


def test_metrics_reads_no_source_content_columns(engine):
    create_analysis(engine)
    def forbid_content(connection,cursor,statement,parameters,context,executemany):
        assert not any(key in statement for key in ('source_record.subject','source_record.sender','raw_metadata','payload','source_account.metadata'))
    event.listen(engine,'before_cursor_execute',forbid_content)
    try:
        services.audit_metrics(engine,'home')
        services.audit_simulate(engine,'home',CandidateThresholds(.8,.8,.8))
    finally: event.remove(engine,'before_cursor_execute',forbid_content)
