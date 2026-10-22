"""New Stage C synthetic interaction probes; no fixture, household or model input."""
import ast
from dataclasses import replace
import io
from pathlib import Path
import subprocess
import sys

import pytest

from family_os import _synthetic_phishing_demo as d
from family_os import _synthetic_routing as a
from family_os import _synthetic_phishing_policy as p


@pytest.fixture
def session():
    return d.Session(a, p)


def save(session, card, operation, conditions=None):
    command = session.prepare(card, operation, conditions)
    return session.commit(command, operation.value)


def gates(session, card, **changes):
    state = session.state(card)
    return replace(p.Conditions(session.binding(state.case.snapshot, state.case.policy),
                   approval=p.Approval.EXPLICIT_SIMULATION, observed=p.Observed.VERIFIED), **changes)


def interact(session, script):
    output = io.StringIO()
    terminal = d.Terminal(session, io.StringIO(script), output)
    try:
        terminal.run()
    except (d._Exit, d._InputLimit):
        pass
    return output.getvalue()


@pytest.mark.parametrize('args', ([], ['--synthetic'], ['--synthetic-only','extra'],
                                 ['--synthetic-only=true'], ['--help','--synthetic-only']))
def test_exact_opt_in_precedes_initialization(args, monkeypatch):
    def forbidden(*args):
        raise AssertionError('initialized without opt-in')
    monkeypatch.setattr(d, 'Session', forbidden)
    out = io.StringIO()
    assert d.main(args, stream=io.StringIO(), output=out) == 2
    assert 'no scenarios initialized' in out.getvalue()


def test_fresh_process_wrong_flag_and_help_do_not_import_contracts():
    script = """
import sys,io
from family_os import _synthetic_phishing_demo as d
assert d.main([],output=io.StringIO())==2
assert d.main(['--help'],output=io.StringIO())==0
assert 'family_os._synthetic_routing' not in sys.modules
assert 'family_os._synthetic_phishing_policy' not in sys.modules
"""
    subprocess.run([sys.executable, '-c', script], check=True, capture_output=True)


@pytest.mark.parametrize('view', tuple(d.View))
def test_view_inspection_has_no_saves_or_authority(session, view):
    before = session.states.copy()
    for card in session.cards(view):
        projection = session.projection(card, view is d.View.OFFERS)
        assert not projection.creates_task and not projection.provider_write and not projection.proactive_alert
    assert session.states == before and session.events == ()
    assert d.Card.PRIVATE not in session.cards(view)


def test_five_views_important_holds_mixed_evidence_and_offers(session):
    assert session.cards(d.View.TODO) == ()
    assert session.cards(d.View.PENDING) == (d.Card.LIBRARY, d.Card.BANK, d.Card.MIXED, d.Card.CONFLICT)
    assert session.cards(d.View.SECURITY) == (d.Card.SCHOOL, d.Card.CLINIC, d.Card.BANK, d.Card.LURE)
    assert session.cards(d.View.INFORMATION) == (d.Card.INFORMATION,)
    assert session.cards(d.View.OFFERS) == (d.Card.OFFER,)
    assert not session.projection(d.Card.OFFER).offer_visible
    assert session.projection(d.Card.OFFER, True).offer_visible
    assert not session.projection(d.Card.LURE, True).offer_visible
    assert d.Card.MIXED not in session.cards(d.View.OFFERS)


def test_offer_change_revert_keeps_pending_pages_quiet_and_security_inspection_available(session):
    pending = session.cards(d.View.PENDING)
    text = interact(session, 'offers\n1\nchange\nconfirm-change\nback\nback\n'
                    'pending\nall\nprevious\nnext\nback\nquit\n')
    assert session.cards(d.View.PENDING) == pending
    assert 'authorized backlog=4; outside this page=2' in text
    pending_output = text.split('Pending Confirmation:', 1)[1]
    assert d.Card.OFFER.value not in pending_output
    assert d.Card.OFFER not in session.cards(d.View.OFFERS)
    assert d.Card.OFFER in session.cards(d.View.SECURITY)
    assert session.projection(d.Card.OFFER).destination is a.Destination.UNASSESSED
    assert not session.projection(d.Card.OFFER, True).offer_visible
    # Three security pages retain the ordinary promotion without a household question.
    text = interact(session, 'security\nnext\n2\nhistory\nrevert\n'
                    'confirm-revert\nback\nback\npending\nall\nback\noffers\nquit\n')
    assert d.Card.OFFER.value in text and 'annotation=CHANGE' in text
    assert session.cards(d.View.PENDING) == pending
    assert session.cards(d.View.OFFERS) == (d.Card.OFFER,)
    assert d.Card.OFFER not in session.cards(d.View.SECURITY)
    assert len(session.history(d.Card.OFFER)) == 2
    assert session.state(d.Card.OFFER).case.history == ()
    assert session.cards(d.View.TODO) == ()


@pytest.mark.parametrize('safety', tuple(a.Safety))
@pytest.mark.parametrize('importance', tuple(a.Importance))
@pytest.mark.parametrize('action', tuple(a.ActionEvidence))
def test_promotional_pending_admission_requires_independent_household_evidence(session, safety, importance, action):
    state = session.state(d.Card.OFFER)
    business = replace(state.case.snapshot.business, importance=importance, action=action)
    case = replace(state.case, snapshot=replace(state.case.snapshot, business=business))
    case = a.reassess(case, safety, case.policy)
    session.states[d.Card.OFFER] = replace(state, case=case)
    projection = session.projection(d.Card.OFFER, True)
    household_evidence = importance is a.Importance.IMPORTANT or action is a.ActionEvidence.SUPPORTED
    pending_destination = projection.destination in (a.Destination.PENDING, a.Destination.UNASSESSED,
                                                      a.Destination.ABSTAIN)
    assert (d.Card.OFFER in session.cards(d.View.PENDING)) == (household_evidence and pending_destination)
    if safety is not a.Safety.SAFE_TO_ROUTE:
        assert d.Card.OFFER in session.cards(d.View.SECURITY)
        assert d.Card.OFFER not in session.cards(d.View.OFFERS)
        assert not projection.offer_visible
    assert not projection.creates_task and not projection.proactive_alert and not projection.provider_write


@pytest.mark.parametrize('card', (d.Card.MIXED, d.Card.LURE))
def test_changed_mixed_service_and_compromised_promotion_remain_distinct(session, card):
    if card is d.Card.LURE:
        assert session.projection(card).safety is a.Safety.HIGH_RISK
        assert card in session.cards(d.View.SECURITY)
        assert card not in session.cards(d.View.OFFERS)
        assert card not in session.cards(d.View.PENDING)
    else:
        assert card in session.cards(d.View.PENDING)
    save(session, card, d.Operation.CHANGE)
    assert (card in session.cards(d.View.PENDING)) == (card is d.Card.MIXED)
    assert card in session.cards(d.View.SECURITY)
    assert card not in session.cards(d.View.OFFERS)
    save(session, card, d.Operation.REVERT)
    assert (card in session.cards(d.View.PENDING)) == (card is d.Card.MIXED)
    assert card not in session.cards(d.View.OFFERS)
    assert session.cards(d.View.TODO) == ()


@pytest.mark.parametrize('permission', (a.Permission.DENIED, a.Permission.UNKNOWN, a.Permission.REVOKED))
def test_unknown_promotion_inspection_still_requires_current_source_access(session, permission):
    save(session, d.Card.OFFER, d.Operation.CHANGE)
    session.grants[a.Source.A] = permission
    for view in d.View:
        assert d.Card.OFFER not in session.cards(view)
    assert session.history(d.Card.OFFER) == ()
    assert session.state(d.Card.OFFER) is None


@pytest.mark.parametrize('card', tuple(d.Card))
@pytest.mark.parametrize('operation', (d.Operation.REVIEW, d.Operation.ACCEPT))
def test_concrete_decisions_use_unchanged_stage_a_gates(session, card, operation):
    before = session.states.copy()
    if card is d.Card.LIBRARY:
        save(session, card, operation)
        assert len(session.history(card)) == 1
    else:
        with pytest.raises((d.DemoError, a.RoutingError)):
            save(session, card, operation)
        assert session.states == before and session.events == ()


def test_review_and_repeated_reviews_never_accept_or_revoke_acceptance(session):
    for _ in range(2):
        save(session, d.Card.LIBRARY, d.Operation.REVIEW)
        assert session.cards(d.View.TODO) == ()
        assert d.Card.LIBRARY in session.cards(d.View.PENDING)
    save(session, d.Card.LIBRARY, d.Operation.ACCEPT)
    save(session, d.Card.LIBRARY, d.Operation.REVIEW)
    assert session.cards(d.View.TODO) == (d.Card.LIBRARY,)
    assert session.projection(d.Card.LIBRARY).authority is a.Authority.SIMULATED_ACCEPTANCE
    assert not session.projection(d.Card.LIBRARY).acceptance_requires_revalidation
    assert len(session.state(d.Card.LIBRARY).case.history) == 4


@pytest.mark.parametrize('operation', tuple(d.Operation))
@pytest.mark.parametrize('confirmation', ('save', '', 'cancel', 'confirm-something-else'))
def test_no_shared_save_or_unconfirmed_writes(session, operation, confirmation):
    before = session.states.copy()
    command = session.prepare(d.Card.LIBRARY, operation)
    with pytest.raises(d.DemoError):
        session.commit(command, confirmation)
    assert session.states == before and session.events == ()


@pytest.mark.parametrize('tail', ('back\n', 'cancel\n', 'quit\n', '', 'save\n', 'x'*65+'\n'))
@pytest.mark.parametrize('operation', ('review', 'accept', 'defer', 'change', 'revert'))
def test_back_cancel_quit_eof_and_invalid_confirmation_save_nothing(session, tail, operation):
    before = session.states.copy()
    interact(session, f'pending\n1\n{operation}\n'+tail)
    assert session.states == before and session.events == ()


@pytest.mark.parametrize('prefix', ('quarantine\n', 'quarantine\nunchanged\n',
                                  'quarantine\nunchanged\nverified\n',
                                  'quarantine\nunchanged\nverified\nverified\n'))
@pytest.mark.parametrize('tail', ('back\n', 'cancel\n', 'quit\n', ''))
@pytest.mark.parametrize('operation', ('quarantine', 'restore'))
def test_recovery_back_cancel_eof_has_no_implicit_save(session, prefix, tail, operation):
    if operation == 'restore':
        save(session, d.Card.CLINIC, d.Operation.QUARANTINE, gates(session, d.Card.CLINIC))
    before = session.states.copy()
    events = session.events
    interact(session, 'security\n2\n'+prefix.replace('quarantine',operation)+tail)
    assert session.states == before and session.events == events


def test_recovery_back_can_change_outcome_without_saving_old_choice(session):
    text = interact(session, 'security\n2\nquarantine\nunchanged\nverified\nverified\nback\n'
                     'failed\nconfirm-quarantine\nhistory\nquit\n')
    state = session.state(d.Card.CLINIC)
    assert state.recovery.quarantine is p.RecoveryStatus.FAILED
    assert len(session.history(d.Card.CLINIC)) == 1
    assert 'annotation=QUARANTINE' in text
    assert 'quarantine=FAILED' in text


def test_interactive_review_accept_history_replay_and_change(session):
    text = interact(session, 'pending\n1\nreview\nconfirm-review\naccept\nconfirm-accept\n'
                     'review\nconfirm-review\nreplay\nconfirm-replay\nhistory\nchange\n'
                     'confirm-change\nrevert\nconfirm-revert\nhistory\nback\nback\ntodo\n1\nquit\n')
    assert len(session.history(d.Card.LIBRARY)) == 5
    assert 'replayed-current' in text
    assert 'History revision=1' in text
    assert 'EVIDENCE CHANGED' in text
    projection = session.projection(d.Card.LIBRARY)
    assert projection.authority is a.Authority.NONE
    assert projection.acceptance_requires_revalidation
    assert d.Card.LIBRARY in session.cards(d.View.TODO)
    assert d.Card.LIBRARY in session.cards(d.View.PENDING)


def test_unchanged_replay_and_stale_historical_acknowledgment(session):
    command = session.prepare(d.Card.LIBRARY, d.Operation.ACCEPT)
    session.commit(command, command.operation.value)
    old = session.events
    assert session.commit(command, command.operation.value) == 'replayed-current'
    assert session.events == old
    save(session, d.Card.LIBRARY, d.Operation.CHANGE)
    after = session.events
    assert session.commit(command, command.operation.value) == 'replayed-historical'
    assert session.events == after
    assert session.projection(d.Card.LIBRARY).authority is a.Authority.NONE
    with pytest.raises(d.DemoError):
        session.commit(replace(command, operation=d.Operation.REVIEW), d.Operation.REVIEW.value)


@pytest.mark.parametrize('update', (d.Operation.CHANGE, d.Operation.REVERT, d.Operation.DEFER))
def test_stale_command_rejected_with_no_partial_writes(session, update):
    command = session.prepare(d.Card.LIBRARY, d.Operation.ACCEPT)
    save(session, d.Card.LIBRARY, update)
    before = session.states.copy(), session.events
    with pytest.raises(d.DemoError):
        session.commit(command, command.operation.value)
    assert (session.states, session.events) == before


@pytest.mark.parametrize('safety', tuple(a.Safety))
@pytest.mark.parametrize('policy', tuple(a.Policy))
def test_safety_and_policy_episode_changes_reject_displayed_intent(session, safety, policy):
    command = session.prepare(d.Card.LIBRARY, d.Operation.ACCEPT)
    state = session.state(d.Card.LIBRARY)
    case = a.reassess(state.case, safety, policy)
    session.states[d.Card.LIBRARY] = replace(state, case=case, revision=state.revision+1)
    with pytest.raises(d.DemoError):
        session.commit(command, command.operation.value)
    assert session.events == ()


def test_change_between_display_and_intention_cannot_accept_undisplayed_state(session):
    class ChangingInput(io.StringIO):
        def readline(self, *args):
            value = super().readline(*args)
            if value == 'accept\n':
                save(session, d.Card.LIBRARY, d.Operation.REVERT)
            return value
    output = io.StringIO()
    terminal = d.Terminal(session, ChangingInput('pending\n1\naccept\nconfirm-accept\nquit\n'), output)
    with pytest.raises(d._Exit):
        terminal.run()
    assert 'Intention rejected' in output.getvalue()
    assert len(session.events) == 1
    assert session.projection(d.Card.LIBRARY).authority is a.Authority.NONE


@pytest.mark.parametrize('permission', (a.Permission.DENIED, a.Permission.UNKNOWN, a.Permission.REVOKED))
def test_access_rechecked_for_mutations_history_counts_and_replays(session, permission):
    command = session.prepare(d.Card.LIBRARY, d.Operation.ACCEPT)
    session.commit(command, command.operation.value)
    session.grants[a.Source.A] = permission
    for view in d.View:
        assert session.cards(view) == ()
    assert session.state(d.Card.LIBRARY) is None
    assert session.history(d.Card.LIBRARY) == ()
    assert session.totals() == dict(saved_annotations=0, accepted_annotations=0, recovery_annotations=0)
    with pytest.raises(d.DemoError):
        session.commit(command, command.operation.value)
    assert len(session.events) == 1  # Retained internally, not disclosed.


def test_hidden_population_cannot_affect_views_navigation_or_summary(session):
    before = {view: session.cards(view) for view in d.View}, session.totals()
    other = d.Session(a, p)
    del other.states[d.Card.PRIVATE]
    del other.originals[d.Card.PRIVATE]
    # Missing hidden slots and present denied slots must be indistinguishable.
    assert {view: other.cards(view) for view in d.View} == before[0]
    assert other.totals() == before[1]


def test_revocation_after_display_before_confirmation(session):
    class RevokingInput(io.StringIO):
        def readline(self, *args):
            value = super().readline(*args)
            if value == 'confirm-accept\n':
                session.grants[a.Source.A] = a.Permission.REVOKED
            return value
    output = io.StringIO()
    terminal = d.Terminal(session, RevokingInput('pending\n1\naccept\nconfirm-accept\nquit\n'), output)
    with pytest.raises(d._Exit):
        terminal.run()
    assert session.events == ()
    assert 'Intention rejected' in output.getvalue()


def test_overflow_and_deferred_items_remain_paginated_and_discoverable(session):
    text = interact(session, 'pending\nall\n2\ndefer\nconfirm-defer\nback\nprevious\n'
                     'next\n2\nhistory\nback\nback\nsecurity\nnext\n1\nquit\n')
    assert 'authorized backlog=4; outside this page=2' in text
    assert d.Card.CONFLICT.value in text and 'Deferred and still discoverable' in text
    assert d.Card.BANK.value in text
    assert len(session.history(d.Card.CONFLICT)) == 1
    assert session.cards(d.View.PENDING) == (d.Card.LIBRARY, d.Card.BANK, d.Card.MIXED, d.Card.CONFLICT)
    assert d.Card.PRIVATE.value not in text


@pytest.mark.parametrize('observed', tuple(p.Observed))
def test_simulated_restore_failure_unknown_and_verified_never_grant_authority(session, observed):
    save(session, d.Card.CLINIC, d.Operation.QUARANTINE, gates(session, d.Card.CLINIC))
    save(session, d.Card.CLINIC, d.Operation.RESTORE, gates(session, d.Card.CLINIC, observed=observed))
    recovery = session.state(d.Card.CLINIC).recovery
    expected = {p.Observed.VERIFIED: p.RecoveryStatus.RESTORED, p.Observed.FAILED: p.RecoveryStatus.FAILED,
                p.Observed.UNKNOWN: p.RecoveryStatus.UNKNOWN}[observed]
    assert recovery.restoration is expected
    assert not recovery.action_authority and not recovery.provider_write
    assert session.cards(d.View.TODO) == ()
    assert session.projection(d.Card.CLINIC).safety is a.Safety.HIGH_RISK
    save(session, d.Card.CLINIC, d.Operation.RESTORE, gates(session, d.Card.CLINIC))
    assert session.state(d.Card.CLINIC).recovery.restoration is p.RecoveryStatus.BLOCKED


@pytest.mark.parametrize('provider', tuple(p.ProviderState))
@pytest.mark.parametrize('retention', tuple(p.Retention))
def test_fresh_independent_restore_gates(session, provider, retention):
    save(session, d.Card.CLINIC, d.Operation.QUARANTINE, gates(session, d.Card.CLINIC))
    save(session, d.Card.CLINIC, d.Operation.RESTORE,
         gates(session, d.Card.CLINIC, provider_state=provider, retention=retention))
    expected = p.RecoveryStatus.RESTORED if (provider is p.ProviderState.UNCHANGED
               and retention is p.Retention.VERIFIED) else p.RecoveryStatus.BLOCKED
    assert session.state(d.Card.CLINIC).recovery.restoration is expected


@pytest.mark.parametrize('update', (d.Operation.CHANGE, d.Operation.REVERT))
def test_evidence_changed_or_reverted_cannot_restore_old_move(session, update):
    save(session, d.Card.CLINIC, d.Operation.QUARANTINE, gates(session, d.Card.CLINIC))
    save(session, d.Card.CLINIC, update)
    save(session, d.Card.CLINIC, d.Operation.RESTORE, gates(session, d.Card.CLINIC))
    assert session.state(d.Card.CLINIC).recovery.restoration is p.RecoveryStatus.BLOCKED


@pytest.mark.parametrize('outcome', (p.Observed.FAILED, p.Observed.UNKNOWN))
def test_failed_unknown_quarantine_cannot_be_blindly_retried_or_restored(session, outcome):
    save(session, d.Card.CLINIC, d.Operation.QUARANTINE, gates(session, d.Card.CLINIC, observed=outcome))
    with pytest.raises(d.DemoError):
        save(session, d.Card.CLINIC, d.Operation.QUARANTINE, gates(session, d.Card.CLINIC))
    save(session, d.Card.CLINIC, d.Operation.RESTORE, gates(session, d.Card.CLINIC))
    assert session.state(d.Card.CLINIC).recovery.restoration is p.RecoveryStatus.BLOCKED


def test_capacity_is_per_card_and_replay_does_not_consume_capacity(session):
    command = None
    for _ in range(d.MAX_EVENTS):
        command = session.prepare(d.Card.LIBRARY, d.Operation.DEFER)
        session.commit(command, command.operation.value)
    assert session.commit(command, command.operation.value) == 'replayed-current'
    with pytest.raises(d.DemoError):
        save(session, d.Card.LIBRARY, d.Operation.DEFER)
    save(session, d.Card.MIXED, d.Operation.DEFER)
    assert len(session.events) == d.MAX_EVENTS+1


@pytest.mark.parametrize('script', ('', 'quit\n', 'pending\n1\naccept\n', 'offers\nback\nquit\n',
                                  'security\n2\nquarantine\nunchanged\nverified\nunknown\n'
                                  'confirm-quarantine\nquit\n'))
def test_main_disposes_state_on_every_normal_exit(script, monkeypatch):
    created = []
    factory = d.Session
    def capture(*args):
        session = factory(*args)
        created.append(session)
        return session
    monkeypatch.setattr(d, 'Session', capture)
    out = io.StringIO()
    assert d.main(['--synthetic-only'], stream=io.StringIO(script), output=out) == 0
    assert created[0].states == {} and created[0].originals == {} and created[0].events == ()
    assert 'Session totals (currently authorized only)' in out.getvalue()
    assert d.Card.PRIVATE.value not in out.getvalue()


def test_generic_internal_failure_does_not_leak_errors_and_disposes_session(monkeypatch):
    session = d.Session(a, p)
    monkeypatch.setattr(d, 'Session', lambda *args: session)
    def fail(*args):
        raise RuntimeError('private URL token provider message')
    monkeypatch.setattr(d.Terminal, 'run', fail)
    out = io.StringIO()
    assert d.main(['--synthetic-only'], output=out) == 1
    assert 'private URL' not in out.getvalue()
    assert session.states == {} and session.events == ()


@pytest.mark.parametrize('bad', (None, 0, True, 33, 'request'))
def test_request_identity_is_strict_bounded_integer(session, bad):
    with pytest.raises(d.DemoError):
        replace(session.prepare(d.Card.LIBRARY, d.Operation.DEFER), request=bad)
    assert session.events == ()


def test_cross_card_and_hidden_request_replay_cannot_transfer_annotations(session):
    command = session.prepare(d.Card.LIBRARY, d.Operation.ACCEPT)
    session.commit(command, command.operation.value)
    before = session.states.copy(), session.events
    for card in (d.Card.CLINIC, d.Card.MIXED, d.Card.PRIVATE):
        with pytest.raises(d.DemoError):
            session.commit(replace(command, card=card), command.operation.value)
    assert (session.states, session.events) == before


@pytest.mark.parametrize('outcome', ('verified','failed','unknown'))
def test_interactive_restore_reports_observed_result_and_does_not_accept(session, outcome):
    text = interact(session, 'security\n2\nquarantine\nunchanged\nverified\nverified\n'
                    'confirm-quarantine\nrestore\nunchanged\nverified\n'+outcome+'\n'
                    'confirm-restore\nquit\n')
    expected = {'verified':'RESTORED','failed':'FAILED','unknown':'UNKNOWN'}[outcome]
    assert 'restore='+expected in text
    assert session.cards(d.View.TODO) == ()
    assert len(session.events) == 2


def test_revocation_terminal_hides_previous_labels_history_and_aggregate_counts(session):
    save(session, d.Card.LIBRARY, d.Operation.ACCEPT)
    text = interact(session, 'revoke\nconfirm-revoke\npending\nback\ntodo\nback\n'
                    'security\nback\noffers\nback\nquit\n')
    assert 'authorized backlog=0' in text
    for card in d.Card:
        assert card.value not in text
    assert session.totals()['saved_annotations'] == 0
    assert len(session.events) == 1


def test_interrupt_and_untrusted_input_do_not_save_or_echo(session):
    text = interact(session, 'pending\n1\naccept\nCONFIRM-ACCEPT?\n'
                    'accept\nconfirm-accept\x00\naccept\nＳＡＶＥ\nquit\n')
    assert session.events == ()
    assert 'ＳＡＶＥ' not in text and 'CONFIRM-ACCEPT?' not in text
    class Interrupted:
        def readline(self, *args):
            raise KeyboardInterrupt()
    out = io.StringIO()
    assert d.main(['--synthetic-only'], stream=Interrupted(), output=out) == 0
    assert 'saved_annotations=0' in out.getvalue()


def test_static_isolation_and_execution_without_file_network_database_or_model(monkeypatch):
    root = Path(__file__).parents[1]
    source = root / 'src/family_os/_synthetic_phishing_demo.py'
    tree = ast.parse(source.read_text())
    imports = {node.module if isinstance(node, ast.ImportFrom) else alias.name
               for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
               for alias in (node.names if isinstance(node, ast.Import) else (None,))}
    assert imports == {'dataclasses','enum','sys','family_os'}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'family_os':
            assert [x.name for x in node.names] in [['_synthetic_routing'],['_synthetic_phishing_policy']]
    for path in (root / 'src/family_os').rglob('*.py'):
        if path != source:
            assert '_synthetic_phishing_demo' not in path.read_text()
    import builtins
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('unexpected I/O')
    monkeypatch.setattr(builtins, 'open', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setenv('DATABASE_URL','never-open-a-household-database')
    assert d.main(['--synthetic-only'], stream=io.StringIO('quit\n'), output=io.StringIO()) == 0
