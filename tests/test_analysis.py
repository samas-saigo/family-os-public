"""Synthetic-only Phase 2F contracts, tenancy, races and migration acceptance."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from threading import Barrier, BrokenBarrierError

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import select, insert, delete, update, inspect, event
from sqlalchemy.exc import IntegrityError

from family_os.analysis import (
    AnalysisInput, AnalysisOutput, FactProposal, Thresholds, ClassificationPolicy,
    AnalysisValidationError, AnalysisNotFoundError, StaleAnalysisInputError,
    AnalyzerExecutionError, AnalysisPersistenceError, AnalysisDefinitionConflictError,
    load_classification, canonical_json, resolve_evidence,
)
from family_os.analysis_services import analyze_source, analyze_pending, analysis_history, current_analysis
from family_os.domain import RawRecord, NormalizedRecord, ChangeBatch
from family_os.ingestion import ingest
from family_os.registry import register
from family_os.schema import source_analysis, analysis_fact, source_record, raw_source_record, source_account

ROOT = Path(__file__).parents[1]
POLICY = load_classification(ROOT / 'config/classification.yaml')
TIME = datetime(2026, 10, 5, 12, 30, 0, 123456, tzinfo=timezone.utc)


class SyntheticConnector:
    provider = 'fixture'

    def __init__(self, subject='Synthetic lease', object_id='file-1'):
        self.subject = subject
        self.object_id = object_id

    def fetch_changes(self, account, cursor):
        return ChangeBatch((RawRecord(self.object_id, {'subject': self.subject}),), self.subject)

    def normalize(self, raw):
        return NormalizedRecord(raw.provider_object_id, 'document', subject=raw.payload['subject'],
            sender='synthetic@example.invalid', recipients=('owner@example.invalid',), occurred_at=TIME,
            metadata={'start': {'dateTime': '2026-11-01T12:30:00Z'}, 'mimeType': 'application/pdf',
                      'items': [{'name': 'Synthetic item'}]})


def rows(engine, table):
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(table)).mappings()]


def seed(engine, household='home', account='account', count=1):
    register(engine, {'household': {'id': household, 'name': 'Synthetic household'}, 'people': [],
        'source_accounts': [{'id': account, 'provider': 'fixture', 'owner_type': 'unknown'}]})
    for index in range(count):
        ingest(engine, household, account, SyntheticConnector(object_id=f'file-{index + 1}'))
    return sorted((r for r in rows(engine, source_record) if r['household_id'] == household), key=lambda r: r['id'])


def good_output(**changes):
    output = AnalysisOutput('relevant', .95, 'home', 'lease', .95, 'not_required', .95,
        (FactProposal('proposed_date', '2026-11-01', .95, ('raw_metadata.start.dateTime',)),
         FactProposal('proposed_date', {'date': '2026-11-02'}, .96, ('subject', 'sender'))))
    return replace(output, **changes)


class SyntheticAnalyzer:
    name = 'synthetic'
    version = 'v1'

    def __init__(self, output=None, callback=None):
        self.output = good_output() if output is None else output
        self.callback = callback
        self.inputs = []

    def analyze(self, input, taxonomy):
        self.inputs.append(input)
        if self.callback:
            self.callback(input)
        return self.output


@pytest.fixture
def source(engine):
    return seed(engine)[0]


def run(engine, source, analyzer=None, policy=POLICY):
    return analyze_source(engine, source['household_id'], source['id'], analyzer or SyntheticAnalyzer(), policy)


def test_exact_snapshot_idempotency_provenance_repeated_facts_and_safe_result(engine, source):
    analyzer = SyntheticAnalyzer()
    first = run(engine, source, analyzer)
    before = rows(engine, source_analysis), rows(engine, analysis_fact)
    second = run(engine, source, analyzer)
    assert first.analysis == second.analysis and not first.reused and second.reused
    assert len(analyzer.inputs) == 1
    assert (rows(engine, source_analysis), rows(engine, analysis_fact)) == before
    analysis = first.analysis
    assert (analysis.household_id, analysis.source_account_id, analysis.source_record_id, analysis.raw_record_id) == (
        'home', 'account', source['id'], source['raw_record_id'])
    assert analysis.input_fingerprint == analyzer.inputs[0].fingerprint
    facts = sorted(rows(engine, analysis_fact), key=lambda r: r['ordinal'])
    assert [f['fact_name'] for f in facts] == ['proposed_date', 'proposed_date']
    assert [f['ordinal'] for f in facts] == [0, 1]
    assert all((f['analysis_id'], f['household_id'], f['source_record_id']) == (analysis.id, 'home', source['id']) for f in facts)
    assert facts[0]['evidence_refs'] == ['raw_metadata.start.dateTime']
    assert not {'subject', 'sender', 'recipients', 'raw_metadata', 'payload', 'cursor', 'client', 'credentials', 'facts'} & set(asdict(analysis))
    assert 'Synthetic lease' not in repr(first)
    assert rows(engine, source_record)[0]['content_hash'] is None
    assert not {'canonical_entity', 'entity_source_link', 'review_queue', 'task', 'action'} & set(inspect(engine).get_table_names())


def test_new_snapshots_and_definitions_preserve_immutable_history_and_current_selector(engine, source):
    old = run(engine, source).analysis
    old_rows = rows(engine, source_analysis), rows(engine, analysis_fact)
    v2 = SyntheticAnalyzer(); v2.version = 'v2'
    second = run(engine, source, v2).analysis
    new_taxonomy = replace(POLICY, taxonomy_version='taxonomy-v2')
    third = run(engine, source, policy=new_taxonomy).analysis
    new_thresholds = replace(POLICY, threshold_policy_version='threshold-v2', thresholds=Thresholds(.99, .99, .99, .99))
    fourth = run(engine, source, policy=new_thresholds).analysis
    assert len({old.id, second.id, third.id, fourth.id}) == 4
    ingest(engine, 'home', 'account', SyntheticConnector('Updated synthetic lease'))
    assert current_analysis(engine, 'home', source['id'], analyzer_name='synthetic', analyzer_version='v1', policy=POLICY) is None
    current = run(engine, source).analysis
    assert current.raw_record_id != old.raw_record_id and current.input_fingerprint != old.input_fingerprint
    assert current.source_record_id == old.source_record_id
    assert rows(engine, source_analysis)[0] == old_rows[0][0]
    assert rows(engine, analysis_fact)[:2] == old_rows[1]
    assert {a.id for a in analysis_history(engine, 'home', source['id'])} == {old.id, second.id, third.id, fourth.id, current.id}
    assert current_analysis(engine, 'home', source['id'], analyzer_name='synthetic', analyzer_version='v1', policy=POLICY) == current
    assert current_analysis(engine, 'home', source['id'], analyzer_name='synthetic', analyzer_version='v2', policy=POLICY) is None


@pytest.mark.parametrize('operation', ['one', 'history', 'current'])
def test_wrong_household_fails_without_invoking_analyzer(engine, source, operation):
    analyzer = SyntheticAnalyzer()
    with pytest.raises(AnalysisNotFoundError):
        if operation == 'one':
            analyze_source(engine, 'other', source['id'], analyzer, POLICY)
        elif operation == 'history':
            analysis_history(engine, 'other', source['id'])
        else:
            current_analysis(engine, 'other', source['id'], analyzer_name='synthetic', analyzer_version='v1', policy=POLICY)
    assert not analyzer.inputs and not rows(engine, source_analysis)


def test_inference_holds_no_connection_and_source_race_writes_nothing(engine, source):
    checked_out = []
    def checkout(*args): checked_out.append(1)
    def checkin(*args): checked_out.pop()
    event.listen(engine, 'checkout', checkout); event.listen(engine, 'checkin', checkin)
    def update_during_inference(input):
        assert not checked_out
        assert input.raw_record_id == source['raw_record_id']
        ingest(engine, 'home', 'account', SyntheticConnector('Snapshot B'))
        assert not checked_out
    try:
        analyzer = SyntheticAnalyzer(callback=update_during_inference)
        with pytest.raises(StaleAnalysisInputError, match='retry'):
            run(engine, source, analyzer)
    finally:
        event.remove(engine, 'checkout', checkout); event.remove(engine, 'checkin', checkin)
    assert rows(engine, source_record)[0]['raw_record_id'] != source['raw_record_id']
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)
    assert not run(engine, source).reused


def test_concurrent_duplicate_attempts_return_one_immutable_winner(engine, source):
    barrier = Barrier(2)
    analyzers = [SyntheticAnalyzer(callback=lambda _: barrier.wait(timeout=10)) for _ in range(2)]
    # Different valid outputs also cannot overwrite the first winner.
    analyzers[1].output = good_output(action_label='required')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda analyzer: run(engine, source, analyzer), analyzers))
    assert results[0].analysis == results[1].analysis
    assert sorted(r.reused for r in results) == [False, True]
    assert len(rows(engine, source_analysis)) == 1 and len(rows(engine, analysis_fact)) == 2


def test_fact_insert_failure_rolls_back_analysis_and_sanitizes_error(engine, source, caplog):
    def fail_facts(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO analysis_fact'):
            raise RuntimeError('private provider/token secret')
    event.listen(engine, 'before_cursor_execute', fail_facts)
    try:
        with pytest.raises(AnalysisPersistenceError) as error:
            run(engine, source)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_facts)
    assert 'private provider/token secret' not in str(error.value) + caplog.text
    assert error.value.__suppress_context__
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)


def test_analyzer_failure_is_safe_and_leaves_zero_rows(engine, source, caplog):
    def fail(input): raise RuntimeError('private source secret')
    with pytest.raises(AnalyzerExecutionError) as error:
        run(engine, source, SyntheticAnalyzer(callback=fail))
    assert 'private source secret' not in str(error.value) + caplog.text
    assert error.value.__suppress_context__
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)


@pytest.mark.parametrize('changes', [
    {'relevance_label': 'yes'}, {'action_label': 'action_required'}, {'category': 'unknown'},
    {'subcategory': 'flight'}, {'category': None}, {'subcategory': None}, {'relevance_label': True},
    {'facts': {'reasoning': 'private'}}, {'facts': (object(),)},
])
def test_malformed_output_rejected_atomically(engine, source, changes):
    with pytest.raises(AnalysisValidationError):
        run(engine, source, SyntheticAnalyzer(good_output(**changes)))
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)


@pytest.mark.parametrize('field', ['relevance_confidence', 'domain_confidence', 'action_confidence', 'fact_confidence'])
@pytest.mark.parametrize('score', [-.01, 1.01, float('nan'), float('inf'), float('-inf'), True, '0.9'])
def test_invalid_confidence_rejected_atomically(engine, source, field, score):
    changes = {field: score} if field != 'fact_confidence' else {'facts': (FactProposal('date', '2026', score, ('subject',)),)}
    with pytest.raises(AnalysisValidationError):
        run(engine, source, SyntheticAnalyzer(good_output(**changes)))
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)


@pytest.mark.parametrize('value', [object(), b'bytes', {1, 2}, float('nan'), float('inf'),
    {'nested': {'access_token': 'secret'}}, {'cursor': 'opaque'}, {'provider_client': object()},
    {'reasoning': 'private'}, {'prompt_transcript': 'private'}, {'bad\x00': 'bad'}, '\ud800',
    {'nested': {'oauth': 'secret'}}, {'file_contents': 'no'}, {'x': 2**64}])
def test_unsafe_fact_values_rejected_atomically(engine, source, value):
    with pytest.raises(AnalysisValidationError):
        fact = FactProposal('date', value, .99, ('subject',))
        run(engine, source, SyntheticAnalyzer(good_output(facts=(fact,))))
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)


@pytest.mark.parametrize('refs', [(), ('subject',) * 33, ('x' * 257,), ('raw_metadata.missing',),
    ('https://example.invalid/private',), ('raw_metadata.cursor',), ('credentials',), ('subject.text',),
    ('raw_metadata.start.dateTime.more',), ('raw_metadata.items.9.name',), ('raw_metadata.items.01.name',),
    ('raw_metadata..mimeType',), ('subject', 'subject'), (123,), ({'ref': 'subject'},),
    ('provider',), ('raw_metadata.start.' + '.'.join(['x'] * 8),)])
def test_invalid_evidence_rejected_atomically(engine, source, refs):
    with pytest.raises(AnalysisValidationError):
        run(engine, source, SyntheticAnalyzer(good_output(facts=(FactProposal('date', '2026', .95, refs),))))
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)


@pytest.mark.parametrize('fact_name', ['', 'AName', 'due-date', 'x' * 65, 'oauth', 'chain_of_thought', 'provider_client', 'white space'])
def test_fact_name_bounds(engine, source, fact_name):
    with pytest.raises(AnalysisValidationError):
        run(engine, source, SyntheticAnalyzer(good_output(facts=(FactProposal(fact_name, '2026', .99, ('subject',)),))))
    assert not rows(engine, source_analysis)


@pytest.mark.parametrize('changes', [{'relevance_label': 'uncertain'}, {'action_label': 'uncertain'},
    {'relevance_confidence': .79}, {'domain_confidence': .79}, {'action_confidence': .79}])
def test_review_recommendation_has_no_side_effects(engine, source, changes):
    before = rows(engine, source_record), rows(engine, raw_source_record), rows(engine, source_account)
    result = run(engine, source, SyntheticAnalyzer(good_output(**changes)))
    assert result.analysis.review_recommended
    assert (rows(engine, source_record), rows(engine, raw_source_record), rows(engine, source_account)) == before
    assert not {'review_queue', 'task', 'canonical_entity', 'entity_source_link'} & set(inspect(engine).get_table_names())


def test_low_fact_confidence_flags_only_that_proposal_and_boundary_is_inclusive(engine, source):
    output = good_output(relevance_confidence=.8, domain_confidence=.8, action_confidence=.8,
        facts=(FactProposal('date', '2026', .89, ('subject',)), FactProposal('date', '2027', .9, ('sender',))))
    assert not run(engine, source, SyntheticAnalyzer(output)).analysis.review_recommended
    assert [f['review_recommended'] for f in sorted(rows(engine, analysis_fact), key=lambda f: f['ordinal'])] == [True, False]


def test_confidently_irrelevant_and_zero_facts_keep_source_provenance(engine, source):
    result = run(engine, source, SyntheticAnalyzer(good_output(relevance_label='irrelevant', category='ignore', subcategory='newsletter', facts=())))
    assert not result.analysis.review_recommended and result.analysis.relevance_label == 'irrelevant'
    assert rows(engine, source_record) == [source] and len(rows(engine, raw_source_record)) == 1
    assert not rows(engine, analysis_fact)


def test_bounded_pending_order_household_and_current_snapshot(engine):
    sources = seed(engine, count=3)
    seed(engine, 'other', 'other-account', count=2)
    analyzer = SyntheticAnalyzer()
    first = analyze_pending(engine, 'home', analyzer, POLICY, limit=2)
    assert asdict(first) == {'selected': 2, 'created': 2, 'reused': 0, 'stale': 0}
    assert [i.source_record_id for i in analyzer.inputs] == [s['id'] for s in sources[:2]]
    second = analyze_pending(engine, 'home', analyzer, POLICY, limit=10)
    assert (second.selected, second.created) == (1, 1)
    empty = analyze_pending(engine, 'home', analyzer, POLICY, limit=10)
    assert empty.selected == 0 and len(analyzer.inputs) == 3
    ingest(engine, 'home', 'account', SyntheticConnector('Changed', sources[0]['provider_object_id']))
    last = analyze_pending(engine, 'home', analyzer, POLICY, limit=10)
    assert last.created == last.selected == 1 and len(rows(engine, source_analysis)) == 4
    assert all(r['household_id'] == 'home' for r in rows(engine, source_analysis))


@pytest.mark.parametrize('limit', [0, -1, True, 1.0, None])
def test_pending_limit_is_strictly_positive_integer(engine, limit):
    analyzer = SyntheticAnalyzer()
    with pytest.raises(AnalysisValidationError): analyze_pending(engine, 'home', analyzer, POLICY, limit=limit)
    assert not analyzer.inputs


def test_pending_stale_is_counted_once_without_retry_loop(engine, source):
    analyzer = SyntheticAnalyzer(callback=lambda _: ingest(engine, 'home', 'account', SyntheticConnector('B')))
    result = analyze_pending(engine, 'home', analyzer, POLICY, limit=1)
    assert asdict(result) == {'selected': 1, 'created': 0, 'reused': 0, 'stale': 1}
    assert len(analyzer.inputs) == 1 and not rows(engine, source_analysis)


def test_changed_config_without_version_bump_is_rejected_for_one_and_batch(engine, source):
    run(engine, source)
    changed = replace(POLICY, thresholds=Thresholds(.9, .9, .9, .9))
    analyzer = SyntheticAnalyzer()
    with pytest.raises(AnalysisDefinitionConflictError): run(engine, source, analyzer, changed)
    with pytest.raises(AnalysisDefinitionConflictError): analyze_pending(engine, 'home', analyzer, changed, limit=1)
    assert not analyzer.inputs and len(rows(engine, source_analysis)) == 1


def input_value(**changes):
    values = dict(source_record_id='source', raw_record_id='raw', provider='fixture', owner_type='unknown', owner_id=None,
        record_type='event', provider_object_id='object', occurred_at=TIME, subject='Synthetic', sender='s@example.invalid',
        recipients=('r@example.invalid',), raw_metadata={'mimeType': 'application/pdf', 'start': {'dateTime': '2026-11-01T12:00:00Z'}})
    return AnalysisInput(**(values | changes))


def test_fingerprint_canonical_json_utc_and_deep_immutability():
    input = input_value()
    equivalent = input_value(occurred_at=TIME.astimezone(timezone(timedelta(hours=8))), raw_metadata={
        'start': {'dateTime': '2026-11-01T12:00:00Z'}, 'mimeType': 'application/pdf'})
    naive_sqlite = input_value(occurred_at=TIME.replace(tzinfo=None))
    assert input.fingerprint == equivalent.fingerprint == naive_sqlite.fingerprint
    # A fixed canonical fixture catches dialect/time/serialization drift.
    expected = '{"occurred_at":"2026-10-05T12:30:00.123456Z","owner_id":null,"owner_type":"unknown","provider":"fixture","provider_object_id":"object","raw_metadata":{"mimeType":"application/pdf","start":{"dateTime":"2026-11-01T12:00:00Z"}},"raw_record_id":"raw","recipients":["r@example.invalid"],"record_type":"event","sender":"s@example.invalid","source_record_id":"source","subject":"Synthetic"}'
    assert canonical_json(input.projection()) == expected
    assert input.fingerprint == sha256(expected.encode()).hexdigest()
    with pytest.raises(FrozenInstanceError): input.subject = 'changed'
    with pytest.raises(TypeError): input.raw_metadata['start']['dateTime'] = 'changed'
    nested = {'items': [{'name': 'before'}]}
    frozen = input_value(raw_metadata=nested); before = frozen.fingerprint
    nested['items'][0]['name'] = 'after'
    assert frozen.fingerprint == before
    assert 'Synthetic' not in repr(input)
    assert resolve_evidence(frozen, 'raw_metadata.items.0.name') == 'before'
    assert canonical_json({'number': 1.0}) == canonical_json({'number': 1})


@pytest.mark.parametrize('change', [{'raw_record_id': 'raw2'}, {'subject': 'changed'}, {'sender': 'changed'},
    {'recipients': ('other@example.invalid',)}, {'raw_metadata': {'mimeType': 'text/plain'}},
    {'occurred_at': TIME + timedelta(seconds=1)}, {'owner_type': 'household', 'owner_id': 'home'}])
def test_fingerprint_changes_with_projection(change):
    assert input_value().fingerprint != input_value(**change).fingerprint


@pytest.mark.parametrize('metadata', [{'access_token': 'secret'}, {'sync_token': 'opaque'}, {'body': 'private'},
    {'nested': {'client_secret': 'secret'}}, {'nan': float('nan')}, {'not_json': object()}])
def test_analysis_input_rejects_prohibited_or_non_json_metadata(metadata):
    with pytest.raises(AnalysisValidationError): input_value(raw_metadata=metadata)


def test_config_preserves_all_existing_taxonomy_intent_and_versions():
    assert set(POLICY.categories) == {'household_admin', 'travel', 'home', 'vehicle', 'pet', 'purchase', 'finance_reference', 'ignore'}
    assert POLICY.categories['finance_reference'] == ('statement_notice', 'card_replacement', 'account_notice', 'tax_document_notice')
    assert POLICY.taxonomy_version and POLICY.threshold_policy_version
    with pytest.raises(TypeError): POLICY.categories['home'] = ('invented',)


@pytest.mark.parametrize('replacement', [
    ('relevance: 0.80', 'relevance: -1'), ('fact: 0.90', 'fact: .nan'),
    ('fact: 0.90', 'fact: .inf'), ('action: 0.80', 'action: true'),
    ('taxonomy_version: family-os-taxonomy-v1', 'taxonomy_version: ""'),
    ('threshold_policy_version: family-os-thresholds-v1', 'threshold_policy_version: [v1]'),
    ('  travel:', '  unknown field:'), ('      - flight\n      - hotel', '      - flight\n      - flight'),
    ('      - flight', '      - [flight]'),
    ('fact: 0.90', 'fact: 0.90\n  fact: 0.91'),
    ('fact: 0.90', 'fact: 0.90\n  arbitrary: 0.9'),
])
def test_config_strict_loading(tmp_path, replacement):
    path = tmp_path / 'classification.yaml'
    original = (ROOT / 'config/classification.yaml').read_text()
    assert replacement[0] in original
    path.write_text(original.replace(*replacement))
    with pytest.raises(AnalysisValidationError): load_classification(path)


@pytest.mark.parametrize('column', ['relevance_confidence', 'domain_confidence', 'action_confidence'])
@pytest.mark.parametrize('value', [-1, 2, float('nan'), float('inf')])
def test_database_confidence_constraints(engine, source, column, value):
    run(engine, source)
    row = rows(engine, source_analysis)[0] | {'id': 'invalid', 'analyzer_version': 'invalid', column: value}
    with pytest.raises(IntegrityError), engine.begin() as connection: connection.execute(insert(source_analysis).values(**row))
    assert len(rows(engine, source_analysis)) == 1


@pytest.mark.parametrize('column,value', [('relevance_label', 'yes'), ('action_label', 'yes'), ('raw_record_id', 'missing'),
    ('source_record_id', 'missing'), ('household_id', 'other'), ('source_account_id', 'other'), ('provider_object_id', 'wrong-object')])
def test_database_analysis_scope_and_labels(engine, source, column, value):
    run(engine, source)
    row = rows(engine, source_analysis)[0] | {'id': 'invalid', 'analyzer_version': 'invalid', column: value}
    with pytest.raises(IntegrityError), engine.begin() as connection: connection.execute(insert(source_analysis).values(**row))


def test_database_rejects_raw_snapshot_of_other_object_and_duplicate_definition(engine, source):
    run(engine, source)
    ingest(engine, 'home', 'account', SyntheticConnector(object_id='file-other'))
    other = next(r for r in rows(engine, source_record) if r['id'] != source['id'])
    row = rows(engine, source_analysis)[0]
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert(source_analysis).values(**(row | {'id': 'invalid', 'analyzer_version': 'invalid', 'raw_record_id': other['raw_record_id']})))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert(source_analysis).values(**(row | {'id': 'duplicate'})))


@pytest.mark.parametrize('column,value', [('confidence', -1), ('confidence', 2), ('confidence', float('nan')),
    ('confidence', float('inf')), ('ordinal', -1), ('analysis_id', 'missing'), ('source_record_id', 'other'), ('household_id', 'other')])
def test_database_fact_constraints(engine, source, column, value):
    run(engine, source)
    row = rows(engine, analysis_fact)[0] | {'id': 'invalid', 'ordinal': 10, column: value}
    with pytest.raises(IntegrityError), engine.begin() as connection: connection.execute(insert(analysis_fact).values(**row))


def test_database_duplicate_fact_ordinal_and_no_provenance_cascade(engine, source):
    run(engine, source)
    fact = rows(engine, analysis_fact)[0]
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert(analysis_fact).values(**(fact | {'id': 'duplicate'})))
    ingest(engine, 'home', 'account', SyntheticConnector('Snapshot B'))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(delete(raw_source_record).where(raw_source_record.c.id == source['raw_record_id']))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(delete(source_record).where(source_record.c.id == source['id']))
    assert len(rows(engine, source_analysis)) == 1 and len(rows(engine, analysis_fact)) == 2


def test_migration_round_trip_preserves_existing_source_rows(engine, source):
    run(engine, source)
    before = rows(engine, source_record), rows(engine, raw_source_record), rows(engine, source_account)
    config = Config(str(ROOT / 'alembic.ini'))
    command.check(config)
    command.downgrade(config, 'a08cf2190da9')
    assert 'source_analysis' not in inspect(engine).get_table_names()
    assert (rows(engine, source_record), rows(engine, raw_source_record), rows(engine, source_account)) == before
    command.upgrade(config, 'head')
    assert (rows(engine, source_record), rows(engine, raw_source_record), rows(engine, source_account)) == before
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)
    command.check(config)


@pytest.mark.parametrize('kind', ['too_many_facts', 'oversized_value', 'oversized_input', 'excess_depth', 'null_evidence', 'dict_response'])
def test_bounded_untrusted_input_and_output(engine, source, kind):
    analyzer = SyntheticAnalyzer()
    with pytest.raises(AnalysisValidationError):
        if kind == 'too_many_facts':
            analyzer.output = good_output(facts=(FactProposal('date', '2026', .95, ('subject',)),) * 101)
        elif kind == 'oversized_value':
            analyzer.output = good_output(facts=(FactProposal('date', 'x' * 16385, .95, ('subject',)),))
        elif kind == 'oversized_input':
            input_value(subject='x' * (1024 * 1024))
        elif kind == 'excess_depth':
            value = 'leaf'
            for _ in range(34): value = {'nested': value}
            FactProposal('date', value, .95, ('subject',))
        elif kind == 'null_evidence':
            with engine.begin() as connection:
                connection.execute(update(source_record).where(source_record.c.id == source['id']).values(sender=None))
            analyzer.output = good_output(facts=(FactProposal('date', '2026', .95, ('sender',)),))
        else:
            analyzer.output = {'relevance_label': 'relevant', 'raw_response': 'private'}
        run(engine, source, analyzer)
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)


def test_synthetic_analyzer_can_not_expose_custom_analysis_error_text(engine, source, caplog):
    from family_os.analysis import AnalysisError
    def fail(input): raise AnalysisError('private synthetic source/token')
    with pytest.raises(AnalyzerExecutionError) as error:
        run(engine, source, SyntheticAnalyzer(callback=fail))
    assert 'private synthetic source/token' not in str(error.value) + caplog.text
    assert not rows(engine, source_analysis)


def test_pending_concurrent_completed_candidate_is_reused(engine, source, monkeypatch):
    # A competing call commits after batch selection, before this analyze-one check.
    import family_os.analysis_services as services
    original = services.analyze_source
    def finish_first(*args, **kwargs):
        original(engine, 'home', source['id'], SyntheticAnalyzer(), POLICY)
        return original(*args, **kwargs)
    monkeypatch.setattr(services, 'analyze_source', finish_first)
    analyzer = SyntheticAnalyzer()
    result = services.analyze_pending(engine, 'home', analyzer, POLICY, limit=1)
    assert asdict(result) == {'selected': 1, 'created': 0, 'reused': 1, 'stale': 0}
    assert not analyzer.inputs


def test_fingerprint_is_captured_before_inference_and_input_mutation_fails_closed(engine, source, monkeypatch):
    seen = []
    original = AnalysisInput.fingerprint
    def observe(input):
        seen.append(original.fget(input))
        return original.fget(input)
    monkeypatch.setattr(AnalysisInput, 'fingerprint', property(observe))
    def unsafe_adapter(input):
        assert seen, 'Fingerprint must be captured before inference begins'
        # Simulate an adapter bypassing frozen dataclass assignment checks.
        object.__setattr__(input, 'subject', 'Injected different projection')
    with pytest.raises(StaleAnalysisInputError):
        run(engine, source, SyntheticAnalyzer(callback=unsafe_adapter))
    assert not rows(engine, source_analysis) and not rows(engine, analysis_fact)



def test_cross_source_concurrent_first_use_rejects_different_definition(engine):
    sources = seed(engine, count=2)
    policies = [POLICY, replace(POLICY, thresholds=Thresholds(.9, .9, .9, .9))]
    assert policies[0].fingerprint('synthetic', 'v1') != policies[1].fingerprint('synthetic', 'v1')
    inference_barrier = Barrier(2)
    insert_barrier = Barrier(2)
    analyzers = [SyntheticAnalyzer(callback=lambda _: inference_barrier.wait(timeout=10)) for _ in sources]

    def overlap_unserialized_inserts(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO source_analysis'):
            # Without household serialization, both PostgreSQL transactions get
            # past their definition checks before either insert commits. With
            # serialization, the winner holds the lock and this bounded barrier
            # times out; the incompatible waiter then fails before inserting.
            try:
                insert_barrier.wait(timeout=1)
            except BrokenBarrierError:
                pass
    event.listen(engine, 'before_cursor_execute', overlap_unserialized_inserts)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, engine, source, analyzer, policy)
                       for source, analyzer, policy in zip(sources, analyzers, policies)]
            successes, failures = [], []
            for future in futures:
                try:
                    successes.append(future.result(timeout=15))
                except AnalysisDefinitionConflictError as error:
                    failures.append(error)
    finally:
        event.remove(engine, 'before_cursor_execute', overlap_unserialized_inserts)
    assert len(successes) == len(failures) == 1
    assert not successes[0].reused
    assert all(len(analyzer.inputs) == 1 for analyzer in analyzers)
    analyses = rows(engine, source_analysis)
    facts = rows(engine, analysis_fact)
    assert len(analyses) == 1 and len(facts) == 2
    assert analyses[0]['id'] == successes[0].analysis.id
    assert {f['analysis_id'] for f in facts} == {analyses[0]['id']}
    assert {f['source_record_id'] for f in facts} == {analyses[0]['source_record_id']}
    assert len({a['definition_fingerprint'] for a in analyses}) == 1
    assert analyses[0]['definition_fingerprint'] in {policy.fingerprint('synthetic', 'v1') for policy in policies}


def test_cross_source_concurrent_first_use_accepts_same_definition(engine):
    sources = seed(engine, count=2)
    barrier = Barrier(2)
    analyzers = [SyntheticAnalyzer(callback=lambda _: barrier.wait(timeout=10)) for _ in sources]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, engine, source, analyzer) for source, analyzer in zip(sources, analyzers)]
        results = [future.result(timeout=15) for future in futures]
    assert all(not result.reused for result in results)
    assert all(len(analyzer.inputs) == 1 for analyzer in analyzers)
    analyses = rows(engine, source_analysis)
    assert len(analyses) == 2 and len(rows(engine, analysis_fact)) == 4
    assert {a['source_record_id'] for a in analyses} == {source['id'] for source in sources}
    assert {a['definition_fingerprint'] for a in analyses} == {POLICY.fingerprint('synthetic', 'v1')}
    assert {a['id'] for a in analyses} == {result.analysis.id for result in results}
