"""Issue #63: scripted enum-only sessions, always factory-owned temporary SQLite."""
import ast
from contextlib import contextmanager
import importlib
from io import StringIO
from pathlib import Path

import pytest
from sqlalchemy import select

from family_os import _synthetic_review_core as core_module
from family_os import _synthetic_review_demo as demo


@pytest.fixture
def session():
    # Intentionally ignore TEST_DATABASE_URL even in the PostgreSQL CI job.
    with core_module.disposable_store(synthetic_only=True) as store:
        core = core_module.ReviewCore(store, synthetic_only=True)
        output = StringIO()
        yield demo._Demo(core, core_module, StringIO(), output)


def run(session, script):
    session.stream = StringIO(script)
    try:
        session.run()
    except demo._ExitSession:
        pass
    return session.output.getvalue()


def counts(session):
    with session.core._store._engine.connect() as connection:
        return tuple(connection.execute(select(core_module._control.c.encounters,
                                              core_module._control.c.decisions)).one())


def receipt(session, index=1):
    return session.receipt(session.observations[index])


def history(session, index=1):
    obs = session.observations[index]
    return session.core.history(obs.account, obs.event_id, obs.step)


def intent(shown, *, disposition='human_confirmed', request='replay'):
    return dict(account=shown.account, event_id=shown.event_id, step=shown.step,
        receipt_token=shown.token, fingerprint=shown.fingerprint,
        proposal_fingerprint=shown.proposal_fingerprint, epoch=shown.epoch,
        expected_revision=shown.revision, disposition=disposition, confirmation='save',
        request_id='synthetic-request-' + request)


@pytest.mark.parametrize('args', [[], ['--synthetic-only=false'], ['--synthetic-only', 'true'],
    ['--synthetic-only', '--database', 'synthetic'], ['--synthetic-only', '--synthetic-only'],
    ['--synthetic-only=true'], ['--help', '--synthetic-only']])
def test_optin_rejected_before_store_or_input(args, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('store or input access before opt-in')
    monkeypatch.setattr(core_module, 'disposable_store', forbidden)
    monkeypatch.setattr(demo, '_read', forbidden)
    output = StringIO()
    assert demo.main(args, stream=StringIO(), output=output) == 2
    assert output.getvalue() == 'Requires exactly --synthetic-only; no database initialized.\n'


def test_help_has_no_persistence(monkeypatch):
    monkeypatch.setattr(core_module, 'disposable_store', lambda **k:pytest.fail('unexpected store'))
    output = StringIO()
    assert demo.main(['--help'], output=output) == 0
    assert 'SYNTHETIC ONLY' in output.getvalue()


def test_import_has_no_io_or_forbidden_dependencies(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('import side effect')
    with monkeypatch.context() as patch:
        patch.setattr(core_module, 'disposable_store', forbidden)
        patch.setattr('sqlalchemy.create_engine', forbidden)
        patch.setattr('tempfile.TemporaryDirectory', forbidden)
        importlib.reload(demo)
    tree = ast.parse(Path(demo.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name in ('sys',) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module in ('dataclasses', 'uuid', 'family_os')
            if node.module == 'family_os':
                assert [a.name for a in node.names] == ['_synthetic_review_core']
    root = Path(demo.__file__).parent
    for path in root.rglob('*.py'):
        if path.name not in ('_synthetic_review_demo.py', '_synthetic_review_core.py'):
            assert '_synthetic_review_demo' not in path.read_text()
            assert '_synthetic_review_core' not in path.read_text()


def test_start_is_empty_and_load_is_explicit_and_not_repeated(session):
    text = run(session, '1\nload\nload\nquit\n')
    assert 'Empty.' in text and 'Examples already loaded' in text
    assert counts(session) == (8, 0)
    assert len(session.observations) == 8
    assert session.encounters == 8 and session.saved == 0
    assert all(receipt(session, i).disposition == 'pending' for i in range(1, 9))
    assert all(receipt(session, i).authority == 'none' for i in range(1, 9))


def test_all_list_retains_every_state_and_independent_identity(session):
    session.load()
    for index, disposition in ((1, 'human_rejected'), (2, 'human_confirmed'),
                               (3, 'deferred'), (4, 'needs_more_information')):
        session.core.save(intent(receipt(session, index), disposition=disposition, request=f'seed-{index}'))
    session.listing()
    text = session.output.getvalue()
    assert all(f'{i}. synthetic-account-' in text for i in range(1, 9))
    for value in ('human_rejected', 'human_confirmed', 'deferred', 'needs_more_information',
                  'pending', 'uncertain', 'invalid', 'already_reviewed', 'visible=True'):
        assert value in text
    assert counts(session) == (8, 4)
    # Same event has independent refund/rebooking and independent account A/B.
    assert receipt(session, 7).disposition == receipt(session, 8).disposition == 'pending'


def test_navigation_history_refresh_and_cancel_do_not_rotate_receipts(session):
    session.load()
    before = tuple(receipt(session, i) for i in range(1, 9))
    run(session, '1\nhistory\nrefresh\nreview\ncancel\nupdate\nback\nback\n2\nhistory\nback\nquit\n')
    assert tuple(receipt(session, i) for i in range(1, 9)) == before
    assert counts(session) == (8, 0)
    assert all(history(session, i) == () for i in range(1, 9))


@pytest.mark.parametrize('disposition', core_module.DISPOSITIONS)
@pytest.mark.parametrize('index', [1, 2])
def test_four_dispositions_require_separate_save_and_have_no_authority(session, disposition, index):
    text = run(session, f'load\n{index}\nreview\n{disposition}\nsave\nquit\n')
    saved = history(session, index)
    assert len(saved) == 1 and saved[0].disposition == disposition
    assert saved[0].authority == 'none' and counts(session) == (8, 1)
    assert text.index('Choose human intention') < text.index('Save review confirmation') < text.index('Review saved:')
    assert 'Future task execution is not implemented.' in text
    assert session.saved == 1


@pytest.mark.parametrize('ending', ['cancel\nquit\n', 'back\ncancel\nquit\n', '', 'quit\n', 'yes\nquit\n', 'save now\nquit\n'])
def test_unconfirmed_intention_does_not_save(session, ending):
    text = run(session, 'load\n1\nreview\nhuman_confirmed\n' + ending)
    assert counts(session) == (8, 0) and history(session) == ()
    assert 'Review saved:' not in text and session.saved == 0


@pytest.mark.parametrize('ending', ['', 'quit\n', 'cancel\nquit\n', 'save\nquit\n', '\nquit\n'])
def test_no_default_intention_and_eof_at_choice_saves_nothing(session, ending):
    text = run(session, 'load\n1\nreview\n' + ending)
    assert counts(session) == (8, 0) and 'Review saved:' not in text


def test_back_from_save_can_change_intention_without_saving_old_choice(session):
    run(session, 'load\n1\nreview\nhuman_confirmed\nback\nhuman_rejected\nsave\nquit\n')
    assert [d.disposition for d in history(session)] == ['human_rejected']
    assert counts(session) == (8, 1)


@pytest.mark.parametrize('index', [3, 4, 5, 6])
@pytest.mark.parametrize('disposition', ['human_confirmed', 'human_rejected'])
def test_uncertain_invalid_missing_conflicting_unsupported_cannot_be_resolved(session, index, disposition):
    text = run(session, f'load\n{index}\nreview\n{disposition}\nsave\nquit\n')
    assert 'Invalid or unresolved choice' in text
    assert counts(session) == (8, 0) and history(session, index) == ()
    assert receipt(session, index).needs_review


def test_correction_appends_and_duplicate_save_input_does_not_create_an_intent(session):
    run(session, 'load\n1\nreview\nhuman_confirmed\nsave\nsave\nreview\nhuman_rejected\nsave\nhistory\nquit\n')
    assert [d.revision for d in history(session)] == [1, 2]
    assert [d.disposition for d in history(session)] == ['human_confirmed', 'human_rejected']
    assert all(d.observation.snapshot == 1 and d.authority == 'none' for d in history(session))
    assert counts(session) == (8, 2) and session.saved == 2


def test_explicit_repeat_change_and_revert_preserve_history_and_reopen(session):
    session.load()
    session.core.save(intent(receipt(session)))
    original_token = receipt(session).token
    run(session, '1\nupdate\nrepeat\nback\nquit\n')
    repeated = receipt(session)
    assert repeated.token != original_token and repeated.kind == 'already_reviewed'
    assert repeated.epoch == 1 and repeated.revision == 1 and not repeated.needs_review
    run(session, '1\nupdate\nchange\nback\nquit\n')
    changed = receipt(session)
    assert changed.epoch == 2 and changed.needs_review and changed.disposition == 'pending'
    assert session.observations[1].proposal['action'] == 'uncertain'
    run(session, '1\nupdate\nrevert\nhistory\nquit\n')
    reverted = receipt(session)
    assert reverted.epoch == 3 and reverted.needs_review and reverted.disposition == 'pending'
    assert session.observations[1].snapshot == 3 and session.observations[1].proposal['action'] == 'required'
    assert len(history(session)) == 1 and history(session)[0].observation.snapshot == 1
    assert receipt(session, 7).epoch == receipt(session, 8).epoch == 1
    assert counts(session) == (11, 1)


def test_same_intent_delivery_converges_and_old_replay_cannot_resolve_changed_evidence(session):
    session.load()
    command = intent(receipt(session))
    session.commit(command)
    session.commit(command)
    assert session.saved == 1 and session.replayed == 1 and counts(session) == (8, 1)
    run(session, '1\nupdate\nchange\nback\nquit\n')
    session.commit(command)
    assert counts(session) == (9, 1) and receipt(session).disposition == 'pending'
    assert 'Historical decision only' in session.output.getvalue()


@pytest.mark.parametrize('mutation', ['encounter', 'save'])
def test_competing_client_rejects_currently_displayed_old_receipt(session, mutation):
    session.load()
    competitor = core_module.ReviewCore(session.core._store, synthetic_only=True)
    original_read = session.read
    def read(prompt):
        if prompt.startswith('Type save'):
            if mutation == 'encounter':
                competitor.encounter(session.observations[1])
            else:
                competitor.save(intent(receipt(session), disposition='deferred', request='competitor'))
        return original_read(prompt)
    session.read = read
    text = run(session, '1\nreview\nhuman_confirmed\nsave\nquit\n')
    assert 'Evidence changed; refresh and review again' in text
    assert session.saved == 0 and session.rejected == 1
    assert counts(session) == ((9, 0) if mutation == 'encounter' else (8, 1))
    assert len(history(session)) == (0 if mutation == 'encounter' else 1)
    session.read = original_read
    run(session, '1\nrefresh\nreview\nhuman_confirmed\nsave\nquit\n')
    assert session.saved == 1 and history(session)[-1].disposition == 'human_confirmed'


def test_competing_changed_snapshot_cannot_be_shown_with_cached_proposal(session):
    session.load()
    competitor = core_module.ReviewCore(session.core._store, synthetic_only=True)
    competitor.encounter(core_module.Observation(core_module.ACCOUNTS[0], core_module.EVENTS[0],
                                                'refund', 20, specimen='conflicting'))
    text = run(session, '1\nreview\nrefresh\nback\nquit\n')
    assert 'Saving is unavailable' in text and 'Suggestion only: required' not in text
    assert counts(session) == (9, 0) and history(session) == ()


@pytest.mark.parametrize('choice', ['private@example.invalid', '../../private', 'https://private.invalid',
    '9', '0', '-1', '01', 'save', '\x1b[31m', '\x00', '确认', '1; quit'])
def test_invalid_control_not_echoed_or_persisted(session, choice):
    text = run(session, choice + '\nquit\n')
    assert counts(session) == (0, 0) and session.observations == {}
    assert 'Invalid choice' in text
    if choice not in ('save', '0'):
        assert choice not in text


@pytest.mark.parametrize('script', ['x' * 65, 'load\n1\nreview\nhuman_confirmed\n' + 'x' * 65 + '\nsave\n'])
def test_oversized_input_ends_without_interpreting_tail_or_saving(script, monkeypatch):
    saved = []
    real_save = core_module.ReviewCore.save
    def save(core, command):
        saved.append(command)
        return real_save(core, command)
    monkeypatch.setattr(core_module.ReviewCore, 'save', save)
    output = StringIO()
    assert demo.main(['--synthetic-only'], stream=StringIO(script), output=output) == 0
    assert saved == [] and 'Input limit exceeded' in output.getvalue()
    assert 'x' * 65 not in output.getvalue()


def test_save_success_only_after_ack_and_no_secret_fields_displayed(session, monkeypatch):
    session.load()
    shown = receipt(session)
    real_save = session.core.save
    commands = []
    def save(command):
        assert 'Review saved:' not in session.output.getvalue()
        assert command['receipt_token'] == shown.token and command['expected_revision'] == shown.revision
        commands.append(dict(command))
        return real_save(command)
    monkeypatch.setattr(session.core, 'save', save)
    text = run(session, '1\nreview\nhuman_confirmed\nsave\nhistory\nquit\n')
    assert len(commands) == 1
    for forbidden in (shown.token, shown.fingerprint, shown.proposal_fingerprint, commands[0]['request_id']):
        assert forbidden not in text
    assert 'Review saved:' in text


@pytest.mark.parametrize('error', ['stale', 'idempotency', 'capacity'])
def test_typed_rejections_never_claim_success_or_write(session, monkeypatch, error):
    session.load()
    error_type = {'stale':core_module.StaleReviewError, 'idempotency':core_module.IdempotencyConflictError,
                  'capacity':core_module.ReviewCoreError}[error]
    monkeypatch.setattr(session.core, 'save', lambda command:(_ for _ in ()).throw(error_type()))
    text = run(session, '1\nreview\nhuman_confirmed\nsave\nquit\n')
    assert counts(session) == (8, 0) and history(session) == ()
    assert 'Review saved:' not in text and session.rejected == 1


def test_encounter_capacity_rejection_preserves_current_card_and_history(session):
    session.load()
    for _ in range(120):
        session.core.encounter(session.observations[1])
    before = receipt(session)
    text = run(session, '1\nupdate\nchange\nback\nquit\n')
    assert 'session capacity reached' in text and receipt(session) == before
    assert session.observations[1].snapshot == 1 and counts(session) == (128, 0)


@pytest.mark.parametrize('script', ['quit\n', '', 'load\n1\nreview\nhuman_confirmed\n'])
def test_runner_disposes_only_factory_sqlite_and_ignores_db_environment(script, tmp_path, monkeypatch):
    sentinel = tmp_path / 'never-open.sqlite3'
    sentinel.write_bytes(b'not a database; synthetic sentinel')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + str(sentinel))
    monkeypatch.setenv('TEST_DATABASE_URL', 'postgresql://invalid/never-connect')
    real_factory = core_module.disposable_store
    owned = []
    @contextmanager
    def factory(**kwargs):
        assert kwargs == {'synthetic_only':True}
        with real_factory(**kwargs) as store:
            assert store._engine.dialect.name == 'sqlite'
            owned.append(Path(store._engine.url.database))
            yield store
    monkeypatch.setattr(core_module, 'disposable_store', factory)
    output = StringIO()
    assert demo.main(['--synthetic-only'], stream=StringIO(script), output=output) == 0
    assert owned and all(not p.exists() for p in owned)
    assert sentinel.read_bytes() == b'not a database; synthetic sentinel'
    assert 'SYNTHETIC ONLY' in output.getvalue() and 'Disposable session ended' in output.getvalue()
    assert str(sentinel) not in output.getvalue() and 'invalid/never-connect' not in output.getvalue()


@pytest.mark.parametrize('failure', ['save', 'read', 'initialization', 'encounter'])
def test_storage_or_unexpected_failure_is_safe_and_cleans_up(monkeypatch, failure):
    owned = []
    real_factory = core_module.disposable_store
    @contextmanager
    def factory(**kwargs):
        with real_factory(**kwargs) as store:
            owned.append(Path(store._engine.url.database))
            yield store
    monkeypatch.setattr(core_module, 'disposable_store', factory)
    def fail(*a, **k):
        raise RuntimeError('synthetic-private-url-token-storage-error')
    monkeypatch.setattr(core_module.ReviewCore, {'save':'save', 'read':'state',
                                                'initialization':'__init__', 'encounter':'encounter'}[failure], fail)
    output = StringIO()
    assert demo.main(['--synthetic-only'], stream=StringIO('load\n1\nreview\nhuman_confirmed\nsave\n'), output=output) == 1
    assert owned and all(not p.exists() for p in owned)
    assert 'unavailable' in output.getvalue() and 'Review saved:' not in output.getvalue()
    assert 'synthetic-private' not in output.getvalue() and 'Traceback' not in output.getvalue()


@pytest.mark.parametrize('signal', [EOFError, KeyboardInterrupt])
def test_interrupt_at_save_confirmation_does_not_save_and_cleans_up(monkeypatch, signal):
    real_save = core_module.ReviewCore.save
    calls = []
    def save(core, command):
        calls.append(command)
        return real_save(core, command)
    monkeypatch.setattr(core_module.ReviewCore, 'save', save)
    class Interrupted(StringIO):
        def readline(self, size):
            line = super().readline(size)
            if line == 'interrupt\n':
                raise signal()
            return line
    output = StringIO()
    assert demo.main(['--synthetic-only'], stream=Interrupted('load\n1\nreview\nhuman_confirmed\ninterrupt\n'), output=output) == 0
    assert calls == [] and 'Review saved:' not in output.getvalue()
    assert 'Disposable session ended' in output.getvalue()


def test_decision_capacity_is_enforced_by_core_without_partial_history(session):
    session.load()
    for i in range(128):
        session.core.save(intent(receipt(session), disposition='deferred', request=f'capacity-{i}'))
    before = history(session)
    text = run(session, '1\nreview\nhuman_confirmed\nsave\nquit\n')
    assert 'session capacity reached' in text and 'Review saved:' not in text
    assert counts(session) == (8, 128) and history(session) == before
    assert receipt(session).revision == 128 and session.saved == 0


def test_saves_stay_scoped_to_account_event_and_named_step(session):
    session.load()
    run(session, '1\nreview\nhuman_confirmed\nsave\nback\n7\nreview\ndeferred\nsave\nback\n8\nreview\nhuman_rejected\nsave\nquit\n')
    assert receipt(session, 1).disposition == 'human_confirmed'
    assert receipt(session, 7).disposition == 'deferred'
    assert receipt(session, 8).disposition == 'human_rejected'
    assert receipt(session, 2).disposition == 'pending'
    for index in (1, 7, 8):
        assert len(history(session, index)) == 1
        assert history(session, index)[0].revision == 1
    assert counts(session) == (8, 3)


def test_keyboard_input_and_output_do_not_hold_database_transactions(session, monkeypatch):
    active = []
    transaction = session.core._transaction
    @contextmanager
    def tracked(**kwargs):
        with transaction(**kwargs) as result:
            active.append(True)
            try:
                yield result
            finally:
                active.pop()
    monkeypatch.setattr(session.core, '_transaction', tracked)
    real_read, real_say = session.read, session.say
    def read(prompt):
        assert not active
        return real_read(prompt)
    def say(text):
        assert not active
        return real_say(text)
    session.read, session.say = read, say
    run(session, 'load\n1\nhistory\nreview\nhuman_confirmed\nsave\nupdate\nchange\nquit\n')
    assert counts(session) == (9, 1) and active == []


def test_new_intentions_use_distinct_bounded_request_ids_and_displayed_revisions(session, monkeypatch):
    session.load()
    real_save = session.core.save
    commands = []
    def save(command):
        commands.append(dict(command))
        return real_save(command)
    monkeypatch.setattr(session.core, 'save', save)
    text = run(session, '1\nreview\nhuman_confirmed\nsave\nreview\ndeferred\nsave\nquit\n')
    assert [c['expected_revision'] for c in commands] == [0, 1]
    assert commands[0]['request_id'] != commands[1]['request_id']
    assert all(len(c['request_id'].removeprefix('synthetic-request-')) == 32 for c in commands)
    assert all(c['request_id'] not in text for c in commands)
    assert counts(session) == (8, 2)


def test_full_session_never_uses_network_or_production_interfaces(monkeypatch):
    import socket
    import sys
    def forbidden(*a, **k):
        raise AssertionError('network is prohibited')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    for name in ('family_os.cli', 'family_os.services', 'family_os.analysis_services',
                 'family_os.audit_services', 'family_os.review_services',
                 'family_os.synthetic_review', 'family_os.calendar_action_evidence', 'keyring'):
        monkeypatch.setitem(sys.modules, name, None)
    output = StringIO()
    assert demo.main(['--synthetic-only'], stream=StringIO('load\n1\nreview\nhuman_confirmed\nsave\nquit\n'), output=output) == 0
    assert 'saved=1' in output.getvalue()


def test_normal_quit_removes_committed_history_and_restart_is_empty(monkeypatch):
    real_factory = core_module.disposable_store
    owned = []
    observed = []
    @contextmanager
    def factory(**kwargs):
        with real_factory(**kwargs) as store:
            owned.append(Path(store._engine.url.database))
            yield store
            core = core_module.ReviewCore(store, synthetic_only=True)
            observed.append(core.history(core_module.ACCOUNTS[0], core_module.EVENTS[0], 'refund'))
    monkeypatch.setattr(core_module, 'disposable_store', factory)
    first, second = StringIO(), StringIO()
    assert demo.main(['--synthetic-only'], stream=StringIO('load\n1\nreview\nhuman_confirmed\nsave\nquit\n'), output=first) == 0
    assert len(observed[0]) == 1 and all(not p.exists() for p in owned)
    assert demo.main(['--synthetic-only'], stream=StringIO('quit\n'), output=second) == 0
    assert observed[1] == () and 'Empty.' in second.getvalue() and 'saved=0' in second.getvalue()
    assert owned[0] != owned[1] and all(not p.exists() for p in owned)


@pytest.mark.parametrize('args', [[], ['--synthetic-only=false'], ['--help']])
def test_fresh_process_gate_and_import_do_not_load_core_or_database(args):
    import subprocess
    import sys
    script = '''
import builtins, sys
from io import StringIO
original = builtins.__import__
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split('.')[0] in {'sqlalchemy', 'sqlite3', 'keyring', 'requests', 'socket'} or \
       (name == 'family_os' and '_synthetic_review_core' in fromlist):
        raise RuntimeError('forbidden import before opt-in')
    return original(name, globals, locals, fromlist, level)
builtins.__import__ = guarded
from family_os import _synthetic_review_demo as demo
assert demo.main(ARGS, stream=StringIO(), output=StringIO()) == EXPECTED
assert 'family_os._synthetic_review_core' not in sys.modules
'''.replace('ARGS', repr(args)).replace('EXPECTED', '0' if args == ['--help'] else '2')
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == result.stderr == ''


def test_interrupted_confirmation_disposes_owned_store(monkeypatch):
    real_factory = core_module.disposable_store
    paths = []
    @contextmanager
    def factory(**kwargs):
        with real_factory(**kwargs) as store:
            paths.append(Path(store._engine.url.database))
            yield store
    monkeypatch.setattr(core_module, 'disposable_store', factory)
    class Interrupted(StringIO):
        def readline(self, size):
            value = super().readline(size)
            if value == 'interrupt\n':
                raise KeyboardInterrupt()
            return value
    output = StringIO()
    assert demo.main(['--synthetic-only'], stream=Interrupted('load\n1\nreview\nhuman_confirmed\ninterrupt\n'), output=output) == 0
    assert paths and all(not p.exists() for p in paths)
    assert 'saved=0' in output.getvalue() and 'Traceback' not in output.getvalue()


def test_real_idempotency_conflict_keeps_existing_decision(session, monkeypatch):
    session.load()
    class FixedIntent:
        hex = 'a' * 32
    monkeypatch.setattr(demo, 'uuid4', lambda:FixedIntent())
    run(session, '1\nreview\nhuman_confirmed\nsave\nreview\nhuman_rejected\nsave\nquit\n')
    assert [d.disposition for d in history(session)] == ['human_confirmed']
    assert receipt(session).revision == 1 and counts(session) == (8, 1)
    assert session.saved == 1 and session.rejected == 1
    assert 'Request conflict' in session.output.getvalue()
