"""Issue #61: newly authored enum-only synthetic cases; no frozen fixture reads."""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import importlib
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, inspect, select, text, update
from sqlalchemy.engine import make_url

from family_os import _synthetic_review_core as review


@pytest.fixture
def review_store():
    # Deliberately do not use the production-migration `engine` fixture.
    test_url = os.environ.get('TEST_DATABASE_URL')
    if not test_url:
        with review.disposable_store(synthetic_only=True) as store:
            yield store
        return
    parsed = make_url(test_url)
    assert parsed.get_backend_name() == 'postgresql'
    schema = 'sr61_test_' + uuid4().hex
    admin = create_engine(parsed, hide_parameters=True)
    engine = None
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(parsed.update_query_dict({'options': f'-csearch_path={schema}'}),
                               hide_parameters=True)
        with review.disposable_store(synthetic_only=True, postgres_test_engine=engine) as store:
            yield store
        with engine.connect() as connection:
            assert inspect(connection).get_table_names(schema=schema) == []
    finally:
        if engine is not None:
            engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def core(review_store):
    return review.ReviewCore(review_store, synthetic_only=True)


def observation(**kwargs):
    return review.Observation(review.ACCOUNTS[0], review.EVENTS[0], 'refund', 1, **kwargs)


def command(receipt, *, disposition='human_confirmed', request='one'):
    return dict(account=receipt.account, event_id=receipt.event_id, step=receipt.step,
        receipt_token=receipt.token, expected_revision=receipt.revision, epoch=receipt.epoch,
        fingerprint=receipt.fingerprint, proposal_fingerprint=receipt.proposal_fingerprint,
        disposition=disposition, confirmation='save', request_id='synthetic-request-' + request)


def history(core, obs=None):
    obs = obs or observation()
    return core.history(obs.account, obs.event_id, obs.step)


def state(core, obs=None):
    obs = obs or observation()
    return core.state(obs.account, obs.event_id, obs.step)


def counters(core):
    with core._store._engine.connect() as connection:
        return tuple(connection.execute(select(review._control.c.encounters,
                                              review._control.c.decisions)).one())


@pytest.mark.parametrize('specimen', tuple(review.SPECIMENS))
def test_encounter_is_visible_and_never_implicitly_saves(core, specimen):
    obs = observation(specimen=specimen)
    first = core.encounter(obs)
    assert first.visible and first.needs_review and first.disposition == 'pending'
    assert first.authority == 'none' and history(core) == ()
    assert state(core) == first
    assert counters(core) == (1, 0)
    repeat = core.encounter(obs)
    assert repeat.visible and repeat.needs_review and repeat.epoch == 1
    assert repeat.token != first.token
    assert history(core) == ()


@pytest.mark.parametrize('specimen', ('outstanding', 'completed'))
@pytest.mark.parametrize('disposition', review.DISPOSITIONS)
def test_explicit_dispositions_and_scoped_not_required(core, specimen, disposition):
    obs = observation(specimen=specimen)
    shown = core.encounter(obs)
    result = core.save(command(shown, disposition=disposition))
    assert result.decision.observation == obs
    assert result.decision.revision == 1 and not result.replayed
    assert result.authority == result.decision.authority == 'none'
    again = core.encounter(obs)
    assert again.visible and again.disposition == disposition
    assert again.needs_review == (disposition not in review.RESOLVED)
    assert again.kind == ('already_reviewed' if disposition in review.RESOLVED else 'unresolved_repeat')


@pytest.mark.parametrize('specimen', ('ambiguous', 'invalid', 'unsupported', 'conflicting'))
@pytest.mark.parametrize('disposition', review.RESOLVED)
def test_nonconcrete_resolution_rejected_without_writes(core, specimen, disposition):
    shown = core.encounter(observation(specimen=specimen))
    with pytest.raises(review.ReviewCoreError):
        core.save(command(shown, disposition=disposition))
    assert history(core) == () and state(core) == shown
    assert counters(core) == (1, 0)


@pytest.mark.parametrize('condition,status', [('unmet','confirmed'), ('unknown','confirmed'),
                                               ('met','tentative'), ('met','unknown')])
def test_unresolved_conditions_cannot_be_resolved(core, condition, status):
    shown = core.encounter(observation(condition=condition, status=status))
    with pytest.raises(review.ReviewCoreError):
        core.save(command(shown))
    assert shown.visible and shown.needs_review


def test_correction_append_only_and_queries_do_not_renew_receipt(core):
    shown = core.encounter(observation())
    first = core.save(command(shown))
    shown = state(core)
    assert shown.revision == 1
    second = core.save(command(shown, disposition='human_rejected', request='correction'))
    assert first.decision == history(core)[0]
    assert [d.revision for d in history(core)] == [1, 2]
    assert second.decision.disposition == 'human_rejected'
    assert state(core).token == shown.token
    with pytest.raises(FrozenInstanceError):
        first.decision.disposition = 'deferred'


@pytest.mark.parametrize('change', [dict(snapshot=2), dict(specimen='alternate_outstanding'),
    dict(status='cancelled'), dict(condition='unknown'), dict(scope='conditional_step'),
    *[dict(stamp=stamp) for stamp in review.STAMPS[1:]]])
def test_each_evidence_or_definition_change_reopens_and_revert_never_revives(core, change):
    original = observation()
    shown = core.encounter(original)
    first = core.save(command(shown)).decision
    altered = replace(original, **change)
    changed = core.encounter(altered)
    assert changed.epoch == 2 and changed.needs_review and changed.disposition == 'pending'
    # Reversion uses a nondecreasing synthetic snapshot counter.
    returned = replace(original, snapshot=altered.snapshot)
    if change == dict(snapshot=2):
        returned = replace(original, snapshot=3)
    reverted = core.encounter(returned)
    assert reverted.epoch == 3 and reverted.needs_review and reverted.visible
    assert history(core) == (first,)
    assert first.observation == original


def test_old_snapshot_and_stale_repeat_receipt_rejected(core):
    original = observation()
    stale = core.encounter(original)
    fresh = core.encounter(original)
    with pytest.raises(review.StaleReviewError):
        core.save(command(stale))
    core.encounter(replace(original, snapshot=2))
    with pytest.raises(review.StaleReviewError):
        core.encounter(original)
    with pytest.raises(review.StaleReviewError):
        core.save(command(fresh))
    assert history(core) == ()


def test_exact_retry_replay_is_historical_after_change_or_correction(core):
    shown = core.encounter(observation())
    cmd = command(shown)
    first = core.save(cmd)
    assert core.save(cmd).replayed and core.save(cmd).applies_to_current
    core.save(command(state(core), disposition='human_rejected', request='two'))
    assert not core.save(cmd).applies_to_current
    core.encounter(replace(observation(), snapshot=2))
    before = counters(core)
    replay = core.save(cmd)
    assert replay.replayed and not replay.applies_to_current
    assert replay.decision == first.decision
    assert counters(core) == before and state(core).disposition == 'pending'


@pytest.mark.parametrize('field,value', [('disposition','deferred'), ('expected_revision',1),
    ('epoch',2), ('fingerprint','0'*64), ('proposal_fingerprint','0'*64),
    ('receipt_token','0'*32), ('account',review.ACCOUNTS[1]), ('step','rebooking')])
def test_request_id_reuse_with_changed_command_conflicts(core, field, value):
    cmd = command(core.encounter(observation()))
    core.save(cmd)
    changed = dict(cmd, **{field:value})
    with pytest.raises(review.IdempotencyConflictError):
        core.save(changed)
    assert counters(core) == (1, 1)


@pytest.mark.parametrize('field,value', [('confirmation','auto_save'), ('confirmation',True),
    ('expected_revision',True), ('expected_revision',-1), ('epoch',False),
    ('request_id','private@example.invalid'), ('receipt_token','forged'),
    ('fingerprint','not-a-fingerprint'), ('proposal_fingerprint','bad'),
    ('disposition','complete'), ('disposition','approve_action'), ('account','real-account'),
    ('event_id','real-record'), ('step','all_household')])
def test_malformed_or_authority_commands_fail_closed(core, field, value):
    shown = core.encounter(observation())
    with pytest.raises(review.ReviewCoreError, match='^Isolated synthetic review rejected$'):
        core.save(dict(command(shown), **{field:value}))
    assert counters(core) == (1, 0)


@pytest.mark.parametrize('extra', ('subject','sender','task','reviewer','permission','priority',
                                   'confidence','raw_metadata','action','household_id'))
def test_unknown_fields_and_private_text_rejected_without_logging(core, extra, caplog, capsys):
    shown = core.encounter(observation())
    with pytest.raises(review.ReviewCoreError) as error:
        core.save(dict(command(shown), **{extra:'synthetic-sensitive-sentinel'}))
    assert 'sentinel' not in str(error.value)
    assert 'sentinel' not in caplog.text
    assert capsys.readouterr().out == ''
    assert history(core) == ()


@pytest.mark.parametrize('field,value', [('account','unknown'), ('event_id','unknown'),
    ('step','complete_all'), ('snapshot',True), ('snapshot',0), ('snapshot',1001),
    ('specimen','private text'), ('status','bad'), ('condition','bad'), ('scope','global'),
    ('stamp',('unapproved','rules','schema')), ('stamp',list(review.STAMPS[0]))])
def test_forged_observation_or_stamp_rejected(core, field, value):
    with pytest.raises(review.ReviewCoreError):
        core.encounter(replace(observation(), **{field:value}))
    assert counters(core) == (0, 0)


def test_account_event_and_named_step_isolation_cancel_refund_rebooking(core):
    refund = observation(status='cancelled', specimen='completed')
    core.save(command(core.encounter(refund)))
    other_step = replace(refund, step='rebooking', specimen='ambiguous')
    other_account = replace(refund, account=review.ACCOUNTS[1])
    other_event = replace(refund, event_id=review.EVENTS[1])
    for other in (other_step, other_account, other_event):
        receipt = core.encounter(other)
        assert receipt.disposition == 'pending' and receipt.needs_review and history(core, other) == ()
    assert not state(core, refund).needs_review
    assert state(core, other_step).needs_review


def _concurrent(call_a, call_b):
    barrier = Barrier(2)
    def run(call):
        barrier.wait(timeout=10)
        try:
            return call()
        except review.ReviewCoreError as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(run, call_a)
        b = pool.submit(run, call_b)
        return a.result(timeout=20), b.result(timeout=20)


def test_concurrent_new_saves_one_wins_other_is_stale(core, review_store):
    client = review.ReviewCore(review_store, synthetic_only=True)
    shown = core.encounter(observation())
    results = _concurrent(lambda: core.save(command(shown, request='a')),
                          lambda: client.save(command(shown, request='b', disposition='human_rejected')))
    assert sum(isinstance(r, review.SaveResult) for r in results) == 1
    assert sum(isinstance(r, review.StaleReviewError) for r in results) == 1
    assert len(history(core)) == 1 and counters(core) == (1, 1)


def test_concurrent_identical_request_converges_without_duplicate(core, review_store):
    client = review.ReviewCore(review_store, synthetic_only=True)
    cmd = command(core.encounter(observation()))
    results = _concurrent(lambda: core.save(cmd), lambda: client.save(cmd))
    assert all(isinstance(r, review.SaveResult) for r in results)
    assert sorted(r.replayed for r in results) == [False, True]
    assert results[0].decision == results[1].decision and len(history(core)) == 1


def test_concurrent_independent_first_observations_and_saves(core, review_store):
    client = review.ReviewCore(review_store, synthetic_only=True)
    a, b = observation(), replace(observation(), account=review.ACCOUNTS[1])
    receipts = _concurrent(lambda: core.encounter(a), lambda: client.encounter(b))
    assert all(isinstance(r, review.Receipt) for r in receipts)
    results = _concurrent(lambda: core.save(command(receipts[0], request='a')),
                         lambda: client.save(command(receipts[1], request='b')))
    assert all(isinstance(r, review.SaveResult) for r in results)
    assert len(history(core, a)) == len(history(core, b)) == 1
    assert counters(core) == (2, 2)


def test_concurrent_encounters_only_final_receipt_can_save(core, review_store):
    client = review.ReviewCore(review_store, synthetic_only=True)
    receipts = _concurrent(lambda: core.encounter(observation()), lambda: client.encounter(observation()))
    old, new = sorted(receipts, key=lambda r:r.visit)
    with pytest.raises(review.StaleReviewError):
        core.save(command(old))
    core.save(command(new))
    assert counters(core) == (2, 1)


def test_shared_request_id_cannot_cross_source_identity(core):
    one = core.encounter(observation())
    other = core.encounter(replace(observation(), account=review.ACCOUNTS[1]))
    core.save(command(one))
    with pytest.raises(review.IdempotencyConflictError):
        core.save(command(other))
    assert history(core, replace(observation(), account=review.ACCOUNTS[1])) == ()


@pytest.mark.parametrize('failure_table', ('sr61_decision','sr61_state','sr61_control'))
def test_failed_save_rolls_back_every_write_and_can_resume(core, monkeypatch, failure_table):
    shown = core.encounter(observation())
    cmd = command(shown)
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith(('INSERT INTO '+failure_table, 'UPDATE '+failure_table)):
            raise RuntimeError('synthetic-private-db-error')
    event.listen(core._store._engine, 'before_cursor_execute', fail)
    try:
        with pytest.raises(review.SyntheticStoreError) as error:
            core.save(cmd)
        assert str(error.value) == 'Isolated synthetic review rejected'
    finally:
        event.remove(core._store._engine, 'before_cursor_execute', fail)
    assert history(core) == () and state(core) == shown and counters(core) == (1, 0)
    assert core.save(cmd).decision.revision == 1


def test_failed_encounter_rolls_back_original_receipt(core):
    shown = core.encounter(observation())
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('UPDATE sr61_control'):
            raise RuntimeError('synthetic failure')
    event.listen(core._store._engine, 'before_cursor_execute', fail)
    try:
        with pytest.raises(review.SyntheticStoreError):
            core.encounter(replace(observation(), snapshot=2))
    finally:
        event.remove(core._store._engine, 'before_cursor_execute', fail)
    assert state(core) == shown and counters(core) == (1, 0)
    assert core.save(command(shown)).decision.revision == 1


def test_reconnect_keeps_original_evidence_decisions_and_request_dedup(core, review_store):
    obs = observation()
    cmd = command(core.encounter(obs))
    original = core.save(cmd)
    review_store.reconnect()
    reopened = review.ReviewCore(review_store, synthetic_only=True)
    assert history(reopened) == (original.decision,)
    assert reopened.save(cmd).replayed
    reopened.encounter(replace(obs, snapshot=2))
    assert history(reopened)[0].observation == obs


@pytest.mark.parametrize('table', (review._observation, review._decision))
@pytest.mark.parametrize('operation', ('update','delete'))
def test_database_itself_rejects_history_mutation(core, table, operation):
    core.save(command(core.encounter(observation())))
    with pytest.raises(Exception):
        with core._store._engine.begin() as connection:
            statement = table.delete() if operation == 'delete' else table.update().values(identity='forged')
            connection.execute(statement)
    assert len(history(core)) == 1


def test_database_fk_cannot_conflate_source_observation(core):
    core.encounter(observation())
    with pytest.raises(Exception):
        with core._store._engine.begin() as connection:
            connection.execute(review._decision.insert().values(identity='forged', revision=1, visit=1,
                disposition='deferred', request_id='synthetic-request-forged', command_fingerprint='0'*64))
    assert history(core) == ()


def test_resource_bounds_are_atomic(core):
    receipt = None
    for _ in range(review.MAX_ENCOUNTERS):
        receipt = core.encounter(observation())
    with pytest.raises(review.ReviewCoreError):
        core.encounter(observation())
    assert counters(core) == (128, 0)
    for i in range(review.MAX_DECISIONS):
        core.save(command(state(core), request=str(i), disposition='deferred'))
    with pytest.raises(review.ReviewCoreError):
        core.save(command(state(core), request='overflow', disposition='deferred'))
    assert len(history(core)) == 128 and counters(core) == (128, 128)


def test_defaults_optin_and_closed_capability_fail_before_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('database access must not occur')
    monkeypatch.setattr(review, 'create_engine', forbidden)
    for call in (lambda:review.ReviewCore(), lambda:review.ReviewCore(object(), synthetic_only=True),
                 lambda:review.disposable_store().__enter__()):
        with pytest.raises(review.SyntheticStoreError):
            call()


def test_sqlite_factory_ignores_database_env_rejects_paths_and_removes_only_own_store(tmp_path, monkeypatch):
    sentinel = tmp_path/'do-not-open.sqlite3'
    sentinel.write_bytes(b'synthetic sentinel, not a database')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{sentinel}')
    with review.disposable_store(synthetic_only=True) as store:
        core = review.ReviewCore(store, synthetic_only=True)
        owned_path = Path(store._engine.url.database)
        core.encounter(observation())
        assert owned_path != sentinel and owned_path.exists()
    assert sentinel.read_bytes() == b'synthetic sentinel, not a database'
    assert not owned_path.exists()
    with pytest.raises(review.SyntheticStoreError):
        core.state(*[review.ACCOUNTS[0],review.EVENTS[0],'refund'])
    with pytest.raises(review.SyntheticStoreError):
        store.reconnect()
    with pytest.raises(TypeError):
        review.disposable_store(synthetic_only=True, path=sentinel)


def test_external_sqlite_engine_is_rejected_without_connection():
    engine = create_engine('sqlite:///:memory:', hide_parameters=True)
    def forbidden(*args):
        raise AssertionError('external connection')
    event.listen(engine, 'connect', forbidden)
    with pytest.raises(review.SyntheticStoreError):
        with review.disposable_store(synthetic_only=True, postgres_test_engine=engine):
            pass
    engine.dispose()


def test_nonempty_store_cannot_be_reinitialized(review_store):
    if review_store._engine.dialect.name != 'postgresql':
        return
    with pytest.raises(review.SyntheticStoreError):
        with review.disposable_store(synthetic_only=True, postgres_test_engine=review_store._engine):
            pass
    assert review.ReviewCore(review_store, synthetic_only=True).state(review.ACCOUNTS[0],review.EVENTS[0],'refund') is None


def test_no_production_wiring_or_import_side_effects(monkeypatch):
    root = Path(__file__).parents[1]
    module = root/'src/family_os/_synthetic_review_core.py'
    tree = ast.parse(module.read_text())
    allowed = {'contextlib','dataclasses','hashlib','json','re','tempfile','uuid','sqlalchemy'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split('.')[0] in allowed for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module.split('.')[0] in allowed
    for path in (root/'src/family_os').rglob('*.py'):
        if path not in (module, module.with_name('_synthetic_review_demo.py')):
            assert '_synthetic_review_core' not in path.read_text()
    for path in (root/'alembic').rglob('*.py'):
        assert 'sr61_' not in path.read_text()
    def forbidden(*args, **kwargs):
        raise AssertionError('import I/O')
    with monkeypatch.context() as patch:
        patch.setattr('sqlalchemy.create_engine', forbidden)
        patch.setattr('tempfile.TemporaryDirectory', forbidden)
        importlib.reload(review)
    importlib.reload(review)


@pytest.mark.parametrize('ref', review.REFS)
def test_evidence_refs_resolve_only_to_fixed_synthetic_values(ref):
    obs = observation()
    value = obs.evidence
    for part in ref.split('.'):
        value = value[part]
    assert value in ('refund', 'confirmed', 'met')
    assert 'subject' not in obs.evidence and 'sender' not in obs.evidence


@pytest.mark.parametrize('options', ['', '-csearch_path=public', '-csearch_path=test_123',
    '-csearch_path=sr61_test_'+'a'*32+',public', '-csearch_path=sr61_test_'+'a'*32+' -cfoo=bar'])
def test_unapproved_postgres_search_path_rejected_before_connect(options):
    engine = create_engine('postgresql+psycopg://synthetic:synthetic@localhost/synthetic',
        connect_args={}, hide_parameters=True)
    engine.url = engine.url.update_query_dict({'options':options})
    def forbidden(*args, **kwargs):
        raise AssertionError('connection must not be attempted')
    event.listen(engine, 'do_connect', forbidden)
    with pytest.raises(review.SyntheticStoreError):
        with review.disposable_store(synthetic_only=True, postgres_test_engine=engine):
            pass
    engine.dispose()


@pytest.mark.parametrize('optin', [False, None, 1, 'true'])
def test_optin_requires_exact_true_before_db_access(optin):
    with pytest.raises(review.SyntheticStoreError):
        with review.disposable_store(synthetic_only=optin):
            pass


def test_stale_valid_shaped_cas_fields_reject_new_save(core):
    shown = core.encounter(observation())
    for field, value in [('receipt_token','0'*32), ('fingerprint','0'*64),
                         ('proposal_fingerprint','0'*64), ('epoch',2), ('expected_revision',1)]:
        with pytest.raises(review.StaleReviewError):
            core.save(dict(command(shown), **{field:value}))
    assert history(core) == () and counters(core) == (1, 0)


def test_same_payload_new_request_is_not_a_retry_or_automatic_correction(core):
    shown = core.encounter(observation())
    core.save(command(shown))
    with pytest.raises(review.StaleReviewError):
        core.save(command(shown, request='different-request'))
    assert len(history(core)) == 1


def test_invalid_unresolved_carryover_and_new_epoch_keep_all_decisions(core):
    obs = observation(specimen='invalid')
    shown = core.encounter(obs)
    core.save(command(shown, disposition='needs_more_information'))
    repeat = core.encounter(obs)
    assert repeat.disposition == 'needs_more_information' and repeat.needs_review and repeat.visible
    core.save(command(repeat, disposition='deferred', request='two'))
    new = core.encounter(replace(obs, snapshot=2, specimen='outstanding'))
    assert new.disposition == 'pending' and new.epoch == 2
    assert [d.disposition for d in history(core)] == ['needs_more_information','deferred']
    assert all(d.observation.specimen == 'invalid' for d in history(core))


def test_factory_cleanup_does_not_touch_other_postgres_schemas(review_store):
    names = set(inspect(review_store._engine).get_table_names())
    assert names == {'sr61_control','sr61_state','sr61_observation','sr61_decision'}
    assert not names.intersection({'source_record','raw_source_record','source_analysis','review_queue','task'})


def test_input_dict_mutation_while_waiting_cannot_change_validated_command(core):
    cmd = command(core.encounter(observation()))
    def mutate(connection, cursor, statement, parameters, context, executemany):
        if 'FROM sr61_control' in statement:
            cmd['disposition'] = 'deferred'
    event.listen(core._store._engine, 'before_cursor_execute', mutate)
    try:
        saved = core.save(cmd)
    finally:
        event.remove(core._store._engine, 'before_cursor_execute', mutate)
    assert saved.decision.disposition == 'human_confirmed'


def test_request_collision_across_independent_sources_has_one_winner(core, review_store):
    client = review.ReviewCore(review_store, synthetic_only=True)
    a = core.encounter(observation())
    bobs = replace(observation(), account=review.ACCOUNTS[1])
    b = client.encounter(bobs)
    results = _concurrent(lambda:core.save(command(a)), lambda:client.save(command(b)))
    assert sum(isinstance(r,review.SaveResult) for r in results) == 1
    assert sum(isinstance(r,review.IdempotencyConflictError) for r in results) == 1
    assert len(history(core)) + len(history(core,bobs)) == 1


def test_encounter_and_save_race_never_attaches_old_decision_to_new_epoch(core, review_store):
    client = review.ReviewCore(review_store, synthetic_only=True)
    shown = core.encounter(observation())
    newer = replace(observation(), snapshot=2)
    results = _concurrent(lambda:core.save(command(shown)), lambda:client.encounter(newer))
    assert isinstance(results[1],review.Receipt)
    assert isinstance(results[0],(review.SaveResult,review.StaleReviewError))
    assert state(core).epoch == 2 and state(core).disposition == 'pending' and state(core).needs_review
    assert all(d.observation.snapshot == 1 and d.epoch == 1 for d in history(core))


@pytest.mark.parametrize('borrowed_fields', [
    ('receipt_token',), ('receipt_token', 'fingerprint', 'proposal_fingerprint')])
def test_receipt_token_replay_across_identities_changes_nothing(core, borrowed_fields):
    a = observation()
    b = replace(a, account=review.ACCOUNTS[1], event_id=review.EVENTS[1],
                snapshot=2, specimen='completed', status='cancelled')
    core.save(command(core.encounter(a), request='seed-a'))
    core.save(command(core.encounter(b), request='seed-b'))
    before_states = (state(core, a), state(core, b))
    before_history = (history(core, a), history(core, b))
    before_counts = counters(core)
    a_command = command(before_states[0], request='cross-identity')
    b_command = command(before_states[1], request='unused-b')
    for field in borrowed_fields:
        a_command[field] = b_command[field]
    # Display/version binding only: this token is not reviewer authentication.
    with pytest.raises(review.StaleReviewError):
        core.save(a_command)
    assert (history(core, a), history(core, b)) == before_history
    assert (state(core, a), state(core, b)) == before_states
    assert (state(core, a).revision, state(core, b).revision) == (1, 1)
    assert counters(core) == before_counts == (2, 2)


def test_concurrent_encounters_at_global_limit_allow_exactly_one(core, review_store):
    client = review.ReviewCore(review_store, synthetic_only=True)
    a = observation()
    b = replace(a, account=review.ACCOUNTS[1], event_id=review.EVENTS[1])
    for _ in range(review.MAX_ENCOUNTERS - 1):
        core.encounter(a)
    before_states = (state(core, a), state(core, b))
    assert counters(core) == (127, 0)
    results = _concurrent(lambda:core.encounter(a), lambda:client.encounter(b))
    assert sum(isinstance(r, review.Receipt) for r in results) == 1
    assert sum(type(r) is review.ReviewCoreError for r in results) == 1
    for i, obs in enumerate((a, b)):
        if type(results[i]) is review.ReviewCoreError:
            assert state(core, obs) == before_states[i]
    assert counters(core) == (128, 0)
    assert history(core, a) == history(core, b) == ()
    with core._store._engine.connect() as connection:
        assert len(connection.execute(select(review._observation)).all()) == 128


def test_concurrent_decisions_at_global_limit_allow_exactly_one(core, review_store):
    client = review.ReviewCore(review_store, synthetic_only=True)
    a = observation()
    b = replace(a, account=review.ACCOUNTS[1], event_id=review.EVENTS[1])
    core.encounter(a)
    core.encounter(b)
    for i in range(review.MAX_DECISIONS - 1):
        core.save(command(state(core, a), request=f'seed-{i}', disposition='deferred'))
    before_states = (state(core, a), state(core, b))
    before_history = (history(core, a), history(core, b))
    assert counters(core) == (2, 127)
    results = _concurrent(
        lambda:core.save(command(before_states[0], request='limit-a', disposition='deferred')),
        lambda:client.save(command(before_states[1], request='limit-b', disposition='deferred')))
    assert sum(isinstance(r, review.SaveResult) for r in results) == 1
    assert sum(type(r) is review.ReviewCoreError for r in results) == 1
    for i, obs in enumerate((a, b)):
        after = history(core, obs)
        assert after[:len(before_history[i])] == before_history[i]
        if type(results[i]) is review.ReviewCoreError:
            assert state(core, obs) == before_states[i] and after == before_history[i]
    assert counters(core) == (2, 128)
    assert len(history(core, a)) + len(history(core, b)) == 128


@pytest.mark.parametrize('write', (False, True))
@pytest.mark.parametrize('error_type', (review.ReviewCoreError, review.StaleReviewError,
    review.IdempotencyConflictError, RuntimeError, KeyboardInterrupt))
def test_transaction_explicitly_rolls_back_before_close_and_preserves_errors(core, monkeypatch, write, error_type):
    if error_type.__name__ in ('ReviewCoreError', 'StaleReviewError', 'IdempotencyConflictError'):
        error_type = getattr(review, error_type.__name__)
    from sqlalchemy.engine import Connection
    real_rollback = Connection.rollback
    calls = []
    def rollback(connection):
        calls.append(not connection.closed and connection.in_transaction())
        return real_rollback(connection)
    monkeypatch.setattr(Connection, 'rollback', rollback)
    primary = error_type() if issubclass(error_type, review.ReviewCoreError) else error_type('synthetic-primary')
    expected = review.SyntheticStoreError if error_type is RuntimeError else error_type
    with pytest.raises(expected) as raised:
        with core._transaction(write=write) as (connection, _):
            connection.execute(update(review._control).where(review._control.c.id == 1).values(encounters=1))
            raise primary
    assert calls == [True]
    if error_type is not RuntimeError:
        assert raised.value is primary
    else:
        assert str(raised.value) == 'Isolated synthetic review rejected'
    assert counters(core) == (0, 0) and history(core) == ()


def test_transaction_commit_failure_explicitly_rolls_back_and_can_resume(core, monkeypatch):
    from sqlalchemy.engine import Connection
    real_commit, real_rollback = Connection.commit, Connection.rollback
    events = []
    def fail_commit(connection):
        events.append('commit')
        raise RuntimeError('synthetic-private-commit-error')
    def rollback(connection):
        assert not connection.closed
        events.append('rollback')
        return real_rollback(connection)
    with monkeypatch.context() as patch:
        patch.setattr(Connection, 'commit', fail_commit)
        patch.setattr(Connection, 'rollback', rollback)
        with pytest.raises(review.SyntheticStoreError, match='^Isolated synthetic review rejected$'):
            core.encounter(observation())
    assert events == ['commit', 'rollback']
    assert counters(core) == (0, 0) and state(core) is None and history(core) == ()
    shown = core.encounter(observation())
    assert core.save(command(shown)).decision.revision == 1


@pytest.mark.parametrize('error_type', (review.StaleReviewError, RuntimeError))
def test_rollback_failure_does_not_replace_primary_or_expose_cleanup_error(core, monkeypatch, caplog, error_type):
    if error_type.__name__ == 'StaleReviewError':
        error_type = review.StaleReviewError
    from sqlalchemy.engine import Connection
    attempted = []
    def fail_rollback(connection):
        attempted.append(not connection.closed)
        raise RuntimeError('synthetic-private-rollback-error')
    primary = error_type() if error_type is review.StaleReviewError else error_type('synthetic-private-primary')
    expected = review.StaleReviewError if error_type is review.StaleReviewError else review.SyntheticStoreError
    with monkeypatch.context() as patch:
        patch.setattr(Connection, 'rollback', fail_rollback)
        with pytest.raises(expected) as raised:
            with core._transaction(write=True) as (connection, _):
                connection.execute(update(review._control).where(review._control.c.id == 1).values(encounters=1))
                raise primary
    assert attempted == [True]
    if error_type is review.StaleReviewError:
        assert raised.value is primary
    assert str(raised.value) == 'Isolated synthetic review rejected'
    assert 'synthetic-private' not in caplog.text
    assert counters(core) == (0, 0)  # Connection close remains the exceptional fallback.


def test_successful_transaction_commit_behavior_is_unchanged(core, monkeypatch):
    from sqlalchemy.engine import Connection
    real_commit, real_rollback = Connection.commit, Connection.rollback
    calls = []
    def commit(connection):
        calls.append('commit')
        return real_commit(connection)
    def rollback(connection):
        calls.append('rollback')
        return real_rollback(connection)
    monkeypatch.setattr(Connection, 'commit', commit)
    monkeypatch.setattr(Connection, 'rollback', rollback)
    core.encounter(observation())
    assert calls == ['commit']
    state(core)
    history(core)
    assert calls == ['commit']
