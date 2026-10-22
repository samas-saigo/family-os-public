"""New E2 fictional lifecycle cases. No real source, DB, model or frozen corpus."""
import ast
from dataclasses import fields, replace
from pathlib import Path
from enum import Enum

import pytest

from family_os import _synthetic_security_lifecycle as l
from family_os import _synthetic_security_preflight as e


# Newly authored story identities: Heron School response / Juniper Clinic notice.
# Mapping into E1's existing enum space does not reuse its scenario corpus.
class Scenario(Enum):
    HERON_SCHOOL = "new-fictional-heron-school-response"
    JUNIPER_CLINIC = "new-fictional-juniper-clinic-notice"


HERON = e.Binding()
JUNIPER = replace(HERON, source=e.Source.PINE, provider=e.Provider.TWO, object=e.Object.OTHER)


def checks(**changes):
    return l.Checks(**({f.name: e.Condition.VERIFIED for f in fields(l.Checks)} | changes))


def session(grants=None, reviewers=None):
    if grants is None:
        grants = tuple(e.Rights(e.Household.HOME, source, actor, e.Permission.ALLOWED,
                               tuple(e.Action) if actor is owner else (), 1)
                       for source, owner in [(e.Source.OAK, e.Principal.ASTER),
                                             (e.Source.PINE, e.Principal.ROBIN)]
                       for actor in e.Principal)
    if reviewers is None:
        reviewers = tuple(l.ReviewerRights(e.Household.HOME, source, actor, e.Permission.ALLOWED)
                          for source in e.Source for actor in e.Principal)
    s = l.Session((l.Item(HERON), l.Item(JUNIPER)), grants,
                  reviewers=reviewers, synthetic_only=True)
    for b in (HERON, JUNIPER):
        s.configure_checks(b, checks())
    return s


def eligible(s, b=HERON, original=None, approval=e.Approval.EXPLICIT):
    result = s.propose(b.principal, b, original)
    safety = e.Safety.CLEAR if b.action is e.Action.RESTORE else e.Safety.HIGH_RISK
    result = s.attest(b.principal, b, result.revision, safety, b)
    result = s.approve(b.principal, b, result.revision, approval, b)
    if result.state in (l.State.STOPPED, l.State.RESTORE_BLOCKED):
        return result
    return s.evaluate(b.principal, b, result.revision)


def reserved(s, b=HERON, original=None):
    result = eligible(s, b, original)
    assert result.state is l.State.ELIGIBLE
    return s.reserve(b.principal, b, result.revision)


def quarantine(s, fault=l.Fault.SUCCESS):
    r = reserved(s)
    return s.dispatch(HERON.principal, HERON, r.revision, fault)


def restore_binding(s, actor=e.Principal.ASTER):
    item = s.inspect(actor, HERON)
    grant = next(g for g in s._grants if g.source is e.Source.OAK and g.principal is actor)
    return replace(HERON, principal=actor, action=e.Action.RESTORE,
                   generation=item.binding.generation, provider_version=item.binding.provider_version,
                   folder=item.binding.folder, labels=item.binding.labels,
                   target=e.Folder.INBOX, delta=e.Delta.UNDO_OWN_MOVE, request=e.Request.SECOND,
                   source_revision=grant.source_revision, consent_revision=grant.consent_revision)


def grant_change(s, source=e.Source.OAK, recipient=e.Principal.ASTER, read=None, operations=None):
    old = next(g for g in s._grants if g.source is source and g.principal is recipient)
    ops = old.operations if operations is None else operations
    value = replace(old, read=old.read if read is None else read, operations=ops,
                    source_revision=old.source_revision + 1,
                    consent_revision=old.consent_revision + (ops != old.operations))
    actor = e.Principal.ASTER if source is e.Source.OAK else e.Principal.ROBIN
    return s.submit_change(actor, value, old.source_revision)


def terms(**changes):
    return l.SharingTerms(**(dict(household=e.Household.HOME, source=e.Source.OAK,
                                  recipients=tuple(e.Principal), expected_revisions=(1, 1),
                                  fields=l.Scope.MINIMIZED_SECURITY, purpose=l.Purpose.SECURITY_REVIEW,
                                  operations=l.Scope.MINIMIZED_SECURITY, retention=l.Retention.REVIEWED,
                                  revocation=l.Revocation.REVOCABLE) | changes))


def test_complete_single_episode_is_separately_authorized_and_reversible():
    s = session(); original_history = s.history(HERON.principal, HERON)
    result = quarantine(s)
    assert result.state is l.State.QUARANTINED
    assert original_history == ()
    snapshot = s.inspect(HERON.principal, HERON)
    assert snapshot.binding.folder is e.Folder.VAULT and snapshot.mutations == 1
    restore = restore_binding(s)
    r = reserved(s, restore, HERON)
    r = s.dispatch(restore.principal, restore, r.revision, l.Fault.SUCCESS)
    assert r.state is l.State.RESTORED
    assert s.inspect(restore.principal, restore).binding.folder is e.Folder.INBOX
    assert s.inspect(restore.principal, restore).mutations == 2
    states = [ev.state for ev in s.history(HERON.principal, HERON)]
    for required in (l.State.PROPOSED, l.State.ELIGIBLE, l.State.RESERVED,
                     l.State.DISPATCHING, l.State.QUARANTINED, l.State.RESTORE_REQUESTED,
                     l.State.RESTORED):
        assert required in states


@pytest.mark.parametrize('fault', list(l.Fault))
def test_dispatch_outcomes_never_infer_success_from_uncertain_delivery(fault):
    s = session(); result = quarantine(s, fault)
    expected = {l.Fault.SUCCESS: l.State.QUARANTINED, l.Fault.FAIL: l.State.FAILED,
                l.Fault.CONFLICT: l.State.FAILED, l.Fault.TIMEOUT_BEFORE: l.State.UNKNOWN,
                l.Fault.TIMEOUT_AFTER: l.State.UNKNOWN}[fault]
    assert result.state is expected
    mutations = s.inspect(HERON.principal, HERON).mutations
    assert mutations == int(fault in (l.Fault.SUCCESS, l.Fault.TIMEOUT_AFTER))
    assert s.propose(HERON.principal, HERON) == result
    assert s.inspect(HERON.principal, HERON).mutations == mutations
    with pytest.raises(l.LifecycleError):
        s.dispatch(HERON.principal, HERON, result.revision, l.Fault.SUCCESS)
    if fault is not l.Fault.SUCCESS:
        observed = s.reconcile(HERON.principal, HERON, result.revision, e.Condition.VERIFIED)
        assert observed.state is (l.State.QUARANTINED if fault is l.Fault.TIMEOUT_AFTER else l.State.FAILED)


@pytest.mark.parametrize('fault', list(l.Fault))
def test_restore_failed_unknown_and_reconciled_results_remain_distinct(fault):
    s = session(); quarantine(s); b = restore_binding(s); r = reserved(s, b, HERON)
    result = s.dispatch(b.principal, b, r.revision, fault)
    expected = l.State.RESTORED if fault is l.Fault.SUCCESS else l.State.RESTORE_UNKNOWN if fault in (l.Fault.TIMEOUT_BEFORE, l.Fault.TIMEOUT_AFTER) else l.State.RESTORE_FAILED
    assert result.state is expected
    if fault is not l.Fault.SUCCESS:
        result = s.reconcile(b.principal, b, result.revision, e.Condition.VERIFIED)
        assert result.state is (l.State.RESTORED if fault is l.Fault.TIMEOUT_AFTER else l.State.RESTORE_FAILED)
    newer = replace(b, generation=4, provider_version=4)
    with pytest.raises(l.LifecycleError):
        s.propose(newer.principal, newer, HERON)


@pytest.mark.parametrize('approval', [e.Approval.PENDING, e.Approval.STANDING_PROPOSED, e.Approval.REVOKED])
def test_no_standing_authority_or_missing_explicit_authorization(approval):
    s = session(); r = eligible(s, approval=approval)
    assert r.state is (l.State.STOPPED if approval is e.Approval.REVOKED else l.State.AWAITING)
    assert s.inspect(HERON.principal, HERON).mutations == 0
    with pytest.raises(l.LifecycleError):
        s.dispatch(HERON.principal, HERON, r.revision, l.Fault.SUCCESS)


@pytest.mark.parametrize('name', [f.name for f in fields(l.Checks)])
@pytest.mark.parametrize('condition', [v for v in e.Condition if v is not e.Condition.VERIFIED])
def test_dispatch_rechecks_every_fresh_dependency(name, condition):
    s = session(); quarantine(s); b = restore_binding(s); r = reserved(s, b, HERON)
    s.configure_checks(b, checks(**{name: condition}))
    assert s.dispatch(b.principal, b, r.revision, l.Fault.SUCCESS).state is l.State.RESTORE_BLOCKED
    assert s.inspect(b.principal, b).mutations == 1


@pytest.mark.parametrize('stage', ['before-reserve', 'after-reserve', 'before-restore'])
@pytest.mark.parametrize('source_read', [True, False])
def test_effective_revocation_stops_pending_work(stage, source_read):
    s = session(); b = HERON
    if stage == 'before-restore':
        quarantine(s); b = restore_binding(s); r = eligible(s, b, HERON)
    else:
        r = eligible(s)
    if stage == 'after-reserve':
        r = s.reserve(b.principal, b, r.revision)
    cmd = grant_change(s, read=e.Permission.REVOKED if source_read else e.Permission.ALLOWED, operations=())
    assert cmd.status is l.GrantResult.SUBMITTED
    assert s.commit_change(cmd, confirm=True) is l.GrantResult.COMMITTED
    result = s.dispatch(b.principal, b, r.revision, l.Fault.SUCCESS) if stage == 'after-reserve' else s.reserve(b.principal, b, r.revision)
    assert result == l.Response() if source_read else result.state in (l.State.STOPPED, l.State.RESTORE_BLOCKED)
    if not source_read:
        assert s.inspect(b.principal, b).mutations == int(stage == 'before-restore')


def test_revoke_during_unknown_outcome_is_not_blind_undo():
    s = session(); r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    cmd = grant_change(s, operations=())
    assert s.commit_change(cmd, confirm=True) is l.GrantResult.COMMITTED
    assert s.reconcile(HERON.principal, HERON, r.revision, e.Condition.VERIFIED).state is l.State.QUARANTINED
    b = restore_binding(s)
    assert eligible(s, b, HERON).state is l.State.RESTORE_BLOCKED
    assert s.inspect(HERON.principal, HERON).mutations == 1


@pytest.mark.parametrize('folder', list(e.Folder))
@pytest.mark.parametrize('labels', list(e.Labels))
def test_later_owner_moves_labels_or_reverts_never_get_overwritten(folder, labels):
    s = session(); quarantine(s)
    assert s.user_change(e.Principal.ASTER, HERON, folder, labels)
    assert s.user_change(e.Principal.ASTER, HERON, e.Folder.VAULT, e.Labels.BASE)
    b = restore_binding(s)
    assert eligible(s, b, HERON).state is l.State.RESTORE_BLOCKED
    assert s.inspect(b.principal, b).mutations == 1


def test_post_reservation_owner_change_and_policy_change_stop_dispatch():
    for change in ['owner', 'policy']:
        s = session(); r = reserved(s)
        if change == 'owner':
            s.user_change(e.Principal.ASTER, HERON, e.Folder.ARCHIVE, e.Labels.USER_EDIT)
        else:
            s.configure_policy(e.Policy.V2)
        assert s.dispatch(HERON.principal, HERON, r.revision, l.Fault.SUCCESS).state is l.State.STOPPED
        assert s.inspect(HERON.principal, HERON).mutations == 0


def test_same_object_controlled_interleaving_reserves_only_one_intent():
    grants = tuple(replace(g, operations=tuple(e.Action)) if g.source is e.Source.OAK else g for g in session()._grants)
    s = session(grants); peer = replace(HERON, principal=e.Principal.ROBIN)
    first = eligible(s); second = eligible(s, peer)
    assert s.reserve(HERON.principal, HERON, first.revision).state is l.State.RESERVED
    assert s.reserve(peer.principal, peer, second.revision).state is l.State.STOPPED
    with pytest.raises(l.LifecycleError):
        s.reserve(HERON.principal, HERON, first.revision)
    assert s.inspect(HERON.principal, HERON).mutations == 0


def test_changed_request_key_cannot_bypass_unknown_same_object_effect():
    s = session(); quarantine(s, l.Fault.TIMEOUT_AFTER)
    new = replace(HERON, request=e.Request.SECOND)
    assert eligible(s, new).state is l.State.STOPPED
    with pytest.raises(l.LifecycleError):
        s.propose(HERON.principal, replace(HERON, target=e.Folder.PURGING))
    assert s.inspect(HERON.principal, HERON).mutations == 1


@pytest.mark.parametrize('inspection', [v for v in e.Condition if v is not e.Condition.VERIFIED])
def test_unknown_inspection_and_lost_recovery_facts_cannot_claim_success(inspection):
    s = session(); r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    r = s.reconcile(HERON.principal, HERON, r.revision, inspection)
    assert r.state is l.State.RECONCILE
    s.configure_checks(HERON, checks(recovery_data=e.Condition.UNAVAILABLE))
    assert s.reconcile(HERON.principal, HERON, r.revision, e.Condition.VERIFIED).state is l.State.RECONCILE


def test_unknown_effect_then_owner_change_remains_unresolved_not_success():
    s = session(); r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    s.user_change(HERON.principal, HERON, e.Folder.ARCHIVE, e.Labels.USER_EDIT)
    assert s.reconcile(HERON.principal, HERON, r.revision, e.Condition.VERIFIED).state is l.State.RECONCILE
    assert s.inspect(HERON.principal, HERON).binding.folder is e.Folder.ARCHIVE


def test_emergency_stop_preserves_unknown_and_blocks_queued_independent_operation():
    s = session(); unknown = quarantine(s, l.Fault.TIMEOUT_AFTER)
    assert s.emergency_stop(e.Principal.ASTER, e.Household.HOME, e.Source.OAK)
    assert s.reconcile(HERON.principal, HERON, unknown.revision, e.Condition.VERIFIED).state is l.State.QUARANTINED
    b = restore_binding(s)
    assert eligible(s, b, HERON).state is l.State.RESTORE_BLOCKED
    other = replace(JUNIPER, principal=e.Principal.ROBIN)
    assert reserved(s, other).state is l.State.RESERVED


def test_two_peer_unified_authorized_counts_history_and_existence_privacy():
    s = session()
    assert s.summary(e.Principal.ASTER) == s.summary(e.Principal.ROBIN) == dict(objects=2, unresolved_attempts=0, verified_quarantine_attempts=0, verified_restore_attempts=0, failed_attempts=0)
    quarantine(s)
    assert s.history(e.Principal.ROBIN, HERON) == s.history(e.Principal.ASTER, HERON)
    denied = replace(JUNIPER, principal=e.Principal.ASTER)
    assert eligible(s, denied).state is l.State.STOPPED
    assert s.user_change(e.Principal.ASTER, JUNIPER, e.Folder.ARCHIVE, e.Labels.BASE) is False
    change = grant_change(s, recipient=e.Principal.ROBIN, read=e.Permission.REVOKED)
    assert s.commit_change(change, confirm=True) is l.GrantResult.COMMITTED
    assert s.summary(e.Principal.ROBIN) == dict(objects=1, unresolved_attempts=0, verified_quarantine_attempts=0, verified_restore_attempts=0, failed_attempts=0)
    assert s.history(e.Principal.ROBIN, HERON) == ()
    assert s.inspect(e.Principal.ROBIN, HERON) is None
    assert s.propose(e.Principal.ROBIN, replace(HERON, principal=e.Principal.ROBIN)) == l.Response()
    assert s.propose(e.Principal.ROBIN, replace(HERON, principal=e.Principal.ROBIN, object=e.Object.OTHER)) == l.Response()


def test_conflicting_source_does_not_hide_independently_authorized_mailbox():
    base = session()._grants
    grants = (base[0], replace(base[0], read=e.Permission.REVOKED, source_revision=2), base[2])
    s = session(grants)
    assert s.summary(e.Principal.ASTER)['objects'] == 1
    assert s.inspect(e.Principal.ASTER, HERON) is None


@pytest.mark.parametrize('reverse', [False, True])
def test_revoke_expansion_compare_revision_no_silent_regrant(reverse):
    s = session()
    revoke = grant_change(s, recipient=e.Principal.ROBIN, read=e.Permission.REVOKED)
    expand = grant_change(s, recipient=e.Principal.ROBIN, operations=tuple(e.Action))
    first, second = (expand, revoke) if reverse else (revoke, expand)
    assert s.commit_change(first, confirm=True) is l.GrantResult.COMMITTED
    before = s._grants, s._grant_history
    assert s.commit_change(second, confirm=True) is l.GrantResult.NOT_APPLIED_STALE
    assert (s._grants, s._grant_history) == before
    if not reverse:
        assert s.inspect(e.Principal.ROBIN, HERON) is None


@pytest.mark.parametrize('field,value', [('fields', l.Scope.UNKNOWN), ('operations', l.Scope.UNKNOWN),
                                        ('purpose', l.Purpose.UNKNOWN), ('retention', l.Retention.UNKNOWN),
                                        ('revocation', l.Revocation.UNKNOWN)])
def test_sharing_incomplete_terms_fail_without_partial_grants(field, value):
    s = session(); before = s._grants, s._grant_history
    assert s.share(e.Principal.ASTER, terms(**{field: value}), confirm=True) is l.GrantResult.NOT_APPLIED_INVALID
    assert (s._grants, s._grant_history) == before


def test_complete_sharing_cancel_and_stale_recipient_are_atomic():
    s = session(); before = s._grants, s._grant_history
    assert s.share(e.Principal.ASTER, terms(), confirm=False) is l.GrantResult.CANCELED
    assert (s._grants, s._grant_history) == before
    assert s.share(e.Principal.ASTER, terms(expected_revisions=(1, 2)), confirm=True) is l.GrantResult.NOT_APPLIED_STALE
    assert (s._grants, s._grant_history) == before
    assert s.share(e.Principal.ROBIN, terms(), confirm=True) is l.GrantResult.WITHHELD
    assert s.share(e.Principal.ASTER, terms(), confirm=True) is l.GrantResult.COMMITTED
    assert s.summary(e.Principal.ASTER)['objects'] == 2
    assert next(g for g in s._grants if g.source is e.Source.OAK and g.principal is e.Principal.ROBIN).operations == ()


def test_source_notification_preparation_revocation_and_destination_are_rechecked():
    s = session(); notice = s.prepare_notice(e.Principal.ROBIN, HERON)
    assert s.inspect_notice(e.Principal.ROBIN, notice) is l.NoticeResult.INSPECTABLE
    assert s.inspect_notice(e.Principal.ASTER, notice) is l.NoticeResult.WITHHELD
    change = grant_change(s, recipient=e.Principal.ROBIN, read=e.Permission.REVOKED)
    s.commit_change(change, confirm=True)
    assert s.inspect_notice(e.Principal.ROBIN, notice) is l.NoticeResult.WITHHELD
    assert s.prepare_notice(e.Principal.ROBIN, HERON) is None


def test_single_original_episode_restore_history_and_version_cannot_be_forged():
    s = session(); quarantine(s); b = restore_binding(s)
    assert eligible(s, b, replace(HERON, generation=2)).state is l.State.RESTORE_BLOCKED
    with pytest.raises(l.LifecycleError):
        s.propose(b.principal, replace(b, generation=1), HERON)


@pytest.mark.parametrize('flag', [False, None, 1, 'synthetic-only'])
def test_exact_opt_in_precedes_initialization(flag):
    with pytest.raises(l.LifecycleError):
        l.Session(None, None, synthetic_only=flag)


def test_close_drops_all_disposable_state_and_history():
    s = session(); quarantine(s); s.close()
    assert not s._items and not s._attempts and not s._events and not s._grants and not s._receipts
    with pytest.raises(l.LifecycleError):
        s.summary(e.Principal.ASTER)


def test_lifecycle_only_imports_e1_and_stdlib_without_production_wiring_or_io(monkeypatch):
    root = Path(__file__).parents[1]; path = root / 'src/family_os/_synthetic_security_lifecycle.py'
    tree = ast.parse(path.read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imports == {'dataclasses', 'enum', 'family_os'}
    assert any(isinstance(n, ast.ImportFrom) and n.module == 'family_os'
               and [a.name for a in n.names] == ['_synthetic_security_preflight'] for n in ast.walk(tree))
    for other in (root / 'src/family_os').rglob('*.py'):
        if other != path:
            assert '_synthetic_security_lifecycle' not in other.read_text()
    s = session()
    import builtins
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected I/O')
    monkeypatch.setattr(builtins, 'open', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    assert quarantine(s).state is l.State.QUARANTINED


def test_proposal_after_reservation_cannot_steal_first_intent():
    grants = tuple(replace(g, operations=tuple(e.Action)) if g.source is e.Source.OAK else g for g in session()._grants)
    s = session(grants); first = reserved(s)
    peer = replace(HERON, principal=e.Principal.ROBIN)
    assert eligible(s, peer).state is l.State.STOPPED
    assert s.dispatch(HERON.principal, HERON, first.revision, l.Fault.SUCCESS).state is l.State.QUARANTINED
    assert s.inspect(HERON.principal, HERON).mutations == 1


def test_new_quarantine_episode_after_owner_move_is_unsupported():
    s = session(); quarantine(s)
    s.user_change(HERON.principal, HERON, e.Folder.INBOX, e.Labels.BASE)
    item = s.inspect(HERON.principal, HERON)
    newer = replace(HERON, generation=item.binding.generation,
                    provider_version=item.binding.provider_version, request=e.Request.SECOND)
    assert eligible(s, newer).state is l.State.STOPPED
    assert item.mutations == 1


def test_other_peer_cannot_restore_already_restored_original():
    grants = tuple(replace(g, operations=tuple(e.Action)) if g.source is e.Source.OAK else g for g in session()._grants)
    s = session(grants); quarantine(s)
    b = restore_binding(s); r = reserved(s, b, HERON)
    assert s.dispatch(b.principal, b, r.revision, l.Fault.SUCCESS).state is l.State.RESTORED
    s.user_change(HERON.principal, HERON, e.Folder.VAULT, e.Labels.BASE)
    peer = replace(restore_binding(s, e.Principal.ROBIN), request=e.Request.FIRST)
    assert eligible(s, peer, HERON).state is l.State.RESTORE_BLOCKED
    assert s.inspect(peer.principal, peer).mutations == 2


@pytest.mark.parametrize('stage', ['proposed', 'eligible', 'reserved'])
def test_cancel_never_mutates_and_freezes_prior_history(stage):
    s = session()
    r = s.propose(HERON.principal, HERON) if stage == 'proposed' else eligible(s)
    if stage == 'reserved':
        r = s.reserve(HERON.principal, HERON, r.revision)
    history = s.history(HERON.principal, HERON)
    canceled = s.cancel(HERON.principal, HERON, r.revision)
    assert canceled.state is l.State.STOPPED
    assert s.history(HERON.principal, HERON)[:len(history)] == history
    assert s.inspect(HERON.principal, HERON).mutations == 0
    with pytest.raises(l.LifecycleError):
        s.dispatch(HERON.principal, HERON, canceled.revision, l.Fault.SUCCESS)


@pytest.mark.parametrize('field', ['generation', 'provider_version', 'source_revision', 'consent_revision'])
def test_stale_bound_proposal_cannot_reach_reservation(field):
    s = session(); b = replace(HERON, **{field: 2})
    assert eligible(s, b).state is l.State.STOPPED
    assert s.inspect(HERON.principal, HERON).mutations == 0


def test_emergency_stop_after_reservation_and_retention_loss_stop_dispatch():
    for gate in ['stop', 'expired', 'deletion-conflict', 'lost-delta']:
        s = session(); r = reserved(s)
        if gate == 'stop':
            s.emergency_stop(HERON.principal, HERON.household, HERON.source)
        else:
            s.configure_checks(HERON, checks(retention=e.Condition.STALE if gate == 'expired' else e.Condition.CONFLICTED,
                                            recovery_data=e.Condition.UNAVAILABLE if gate == 'lost-delta' else e.Condition.VERIFIED))
        assert s.dispatch(HERON.principal, HERON, r.revision, l.Fault.SUCCESS).state is l.State.STOPPED
        assert s.inspect(HERON.principal, HERON).mutations == 0


def test_purging_quarantine_target_is_never_recoverable_by_assumption():
    s = session(); b = replace(HERON, target=e.Folder.PURGING)
    assert eligible(s, b).state is l.State.STOPPED
    assert s.inspect(HERON.principal, HERON).mutations == 0


def test_revoked_unknown_source_is_absent_while_other_peer_can_reconcile():
    s = session(); r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    change = grant_change(s, read=e.Permission.REVOKED)
    s.commit_change(change, confirm=True)
    assert s.reconcile(HERON.principal, HERON, r.revision, e.Condition.VERIFIED) == l.Response()
    assert s.summary(HERON.principal) == dict(objects=1, unresolved_attempts=0, verified_quarantine_attempts=0, verified_restore_attempts=0, failed_attempts=0)
    assert s.history(HERON.principal, HERON) == ()
    assert s.reconcile(e.Principal.ROBIN, HERON, r.revision, e.Condition.VERIFIED).state is l.State.QUARANTINED


def test_hidden_activity_never_changes_other_members_observable_results():
    s = session(); change = grant_change(s, recipient=e.Principal.ROBIN, read=e.Permission.REVOKED)
    s.commit_change(change, confirm=True)
    before = s.summary(e.Principal.ROBIN), s.history(e.Principal.ROBIN, JUNIPER)
    quarantine(s, l.Fault.TIMEOUT_AFTER)
    s.user_change(HERON.principal, HERON, e.Folder.ARCHIVE, e.Labels.USER_EDIT)
    assert (s.summary(e.Principal.ROBIN), s.history(e.Principal.ROBIN, JUNIPER)) == before
    assert s.inspect(e.Principal.ROBIN, HERON) is None


def test_unknown_restore_with_later_owner_change_remains_unresolved():
    s = session(); quarantine(s); b = restore_binding(s); r = reserved(s, b, HERON)
    r = s.dispatch(b.principal, b, r.revision, l.Fault.TIMEOUT_AFTER)
    s.user_change(HERON.principal, HERON, e.Folder.ARCHIVE, e.Labels.USER_EDIT)
    assert s.reconcile(b.principal, b, r.revision, e.Condition.VERIFIED).state is l.State.RECONCILE
    assert s.inspect(b.principal, b).binding.folder is e.Folder.ARCHIVE


def test_sharing_records_exact_terms_and_never_adds_provider_operations():
    s = session(); selected = terms()
    assert s.share(e.Principal.ASTER, selected, confirm=True) is l.GrantResult.COMMITTED
    assert s._sharing_history == ((e.Principal.ASTER, selected),)
    assert next(g for g in s._grants if g.source is e.Source.OAK and g.principal is e.Principal.ROBIN).operations == ()


@pytest.mark.parametrize('value', [(), (e.Principal.ASTER, e.Principal.ASTER), ('private',), ([],)])
def test_recipient_terms_are_strict_bounded_and_content_free(value):
    with pytest.raises(l.LifecycleError, match='^Synthetic lifecycle rejected$'):
        terms(recipients=value, expected_revisions=tuple(1 for _ in value))


def test_capacity_failure_precedes_any_simulated_effect():
    s = session(); r = reserved(s)
    # Controlled resource-bound probe; no private data or production storage.
    event = s._events[0]
    s._events = (event,) * (l.MAX_EVENTS_PER_SOURCE - 1)
    before = s.inspect(HERON.principal, HERON), s._events
    with pytest.raises(l.LifecycleError):
        s.dispatch(HERON.principal, HERON, r.revision, l.Fault.SUCCESS)
    assert (s.inspect(HERON.principal, HERON), s._events) == before


def test_stale_notice_and_failed_revoke_do_not_claim_success():
    s = session(); notice = s.prepare_notice(e.Principal.ROBIN, HERON)
    s.user_change(HERON.principal, HERON, e.Folder.ARCHIVE, e.Labels.USER_EDIT)
    assert s.inspect_notice(e.Principal.ROBIN, notice) is l.NoticeResult.WITHHELD
    revoke = grant_change(s, recipient=e.Principal.ROBIN, read=e.Permission.REVOKED)
    assert revoke.status is l.GrantResult.SUBMITTED
    assert s.inspect(e.Principal.ROBIN, HERON) is not None
    assert s.commit_change(revoke, confirm=False) is l.GrantResult.CANCELED
    assert s.inspect(e.Principal.ROBIN, HERON) is not None


@pytest.mark.parametrize('stage', ['proposed', 'awaiting', 'eligible'])
@pytest.mark.parametrize('operation', ['reserve', 'dispatch'])
def test_intermediate_checks_and_reservation_cannot_be_bypassed(stage, operation):
    s = session()
    if stage == 'proposed':
        r = s.propose(HERON.principal, HERON)
    else:
        r = eligible(s, approval=e.Approval.PENDING if stage == 'awaiting' else e.Approval.EXPLICIT)
    before = s.inspect(HERON.principal, HERON), s.history(HERON.principal, HERON)
    if stage == 'eligible' and operation == 'reserve':
        assert s.reserve(HERON.principal, HERON, r.revision).state is l.State.RESERVED
    else:
        with pytest.raises(l.LifecycleError):
            if operation == 'dispatch':
                s.dispatch(HERON.principal, HERON, r.revision, l.Fault.SUCCESS)
            else:
                s.reserve(HERON.principal, HERON, r.revision)
        assert (s.inspect(HERON.principal, HERON), s.history(HERON.principal, HERON)) == before


def test_task_read_source_access_and_other_actors_approval_cannot_confer_mailbox_authority():
    s = session(); r = eligible(s)
    with pytest.raises(l.LifecycleError):
        s.reserve(e.Principal.ROBIN, HERON, r.revision)
    before = s.inspect(HERON.principal, HERON)
    assert s.user_change(e.Principal.ROBIN, HERON, e.Folder.ARCHIVE, e.Labels.USER_EDIT) is False
    assert s.inspect(HERON.principal, HERON) == before


def test_restore_own_scope_is_required_after_fresh_consent_change():
    s = session(); quarantine(s)
    cmd = grant_change(s, operations=(e.Action.QUARANTINE,))
    assert s.commit_change(cmd, confirm=True) is l.GrantResult.COMMITTED
    b = restore_binding(s)
    assert eligible(s, b, HERON).state is l.State.RESTORE_BLOCKED
    assert s.inspect(b.principal, b).mutations == 1


@pytest.mark.parametrize('read', [e.Permission.REVOKED, e.Permission.UNKNOWN])
def test_ambiguous_live_grant_cannot_override_deny_or_steal_operations(read):
    base = session()._grants
    grants = (base[0], replace(base[0], read=read, source_revision=2), base[2])
    s = session(grants)
    assert s.propose(HERON.principal, HERON) == l.Response()
    assert s.history(HERON.principal, HERON) == ()
    cmd = grant_change(s, operations=())
    assert s.commit_change(cmd, confirm=True) is l.GrantResult.NOT_APPLIED_CONFLICT
    assert s.summary(e.Principal.ASTER)['objects'] == 1


def test_grant_capacity_failure_is_prominent_not_applied_with_zero_partial_effects():
    s = session(); change = grant_change(s, recipient=e.Principal.ROBIN, read=e.Permission.REVOKED)
    old = next(g for g in s._grants if g.source is e.Source.OAK)
    s._grant_history = ((old, old),) * l.MAX_EVENTS_PER_SOURCE
    before = s._grants, s._grant_history
    assert s.commit_change(change, confirm=True) is l.GrantResult.NOT_APPLIED_CAPACITY
    assert (s._grants, s._grant_history) == before
    assert s.share(e.Principal.ASTER, terms(), confirm=True) is l.GrantResult.NOT_APPLIED_CAPACITY
    assert (s._grants, s._grant_history) == before


def test_important_legitimate_false_positive_is_visible_and_separately_recoverable():
    # Scenario truth is supplied only to this test; policy receives no ground-truth label.
    scenario_truth = {Scenario.HERON_SCHOOL: 'legitimate-important',
                      Scenario.JUNIPER_CLINIC: 'legitimate-important'}
    assert scenario_truth[Scenario.HERON_SCHOOL] == 'legitimate-important'
    s = session(); quarantine(s)
    assert s.summary(e.Principal.ROBIN)['verified_quarantine_attempts'] == 1
    b = restore_binding(s); r = reserved(s, b, HERON)
    assert s.dispatch(b.principal, b, r.revision, l.Fault.SUCCESS).state is l.State.RESTORED
    assert s.summary(e.Principal.ASTER) == s.summary(e.Principal.ROBIN)


@pytest.mark.parametrize('gate', ['retention', 'recovery_data'])
@pytest.mark.parametrize('condition', [e.Condition.STALE, e.Condition.UNAVAILABLE, e.Condition.CONFLICTED])
def test_recovery_expiry_and_deletion_conflicts_block_new_quarantine(gate, condition):
    s = session(); s.configure_checks(HERON, checks(**{gate: condition}))
    assert eligible(s).state is l.State.STOPPED
    assert s.inspect(HERON.principal, HERON).mutations == 0


def test_summary_distinguishes_historical_verification_from_current_physical_state():
    s = session(); r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    assert s.summary(HERON.principal)['unresolved_attempts'] == 1
    assert s.summary(HERON.principal)['verified_quarantine_attempts'] == 0
    s.reconcile(HERON.principal, HERON, r.revision, e.Condition.VERIFIED)
    b = restore_binding(s); r = reserved(s, b, HERON)
    s.dispatch(b.principal, b, r.revision, l.Fault.SUCCESS)
    assert s.inspect(b.principal, b).binding.folder is e.Folder.INBOX
    summary = s.summary(b.principal)
    assert summary['verified_quarantine_attempts'] == summary['verified_restore_attempts'] == 1
    assert summary['unresolved_attempts'] == 0


def test_revoked_reservation_cannot_execute_or_fragment_new_authorized_peer_work():
    grants = tuple(replace(g, operations=tuple(e.Action)) if g.source is e.Source.OAK else g for g in session()._grants)
    s = session(grants); old = reserved(s)
    change = grant_change(s, operations=())
    assert s.commit_change(change, confirm=True) is l.GrantResult.COMMITTED
    peer = replace(HERON, principal=e.Principal.ROBIN)
    r = reserved(s, peer)
    assert s.dispatch(peer.principal, peer, r.revision, l.Fault.SUCCESS).state is l.State.QUARANTINED
    assert s.dispatch(HERON.principal, HERON, old.revision, l.Fault.SUCCESS).state is l.State.STOPPED
    assert s.inspect(peer.principal, peer).mutations == 1


def reviewer(actor=e.Principal.ROBIN, permission=e.Permission.ALLOWED, source=e.Source.OAK):
    return l.ReviewerRights(e.Household.HOME, source, actor, permission)


@pytest.mark.parametrize('actor', tuple(e.Principal))
def test_explicit_reviewer_records_initiator_and_actual_actor(actor):
    s = session(reviewers=(reviewer(actor),))
    r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    before = s.history(actor, HERON)
    assert s.reconcile(actor, HERON, r.revision, e.Condition.VERIFIED).state is l.State.QUARANTINED
    history = s.history(actor, HERON)
    assert history[:len(before)] == before
    assert all(ev.binding.principal is HERON.principal for ev in history)
    assert all(ev.actor is HERON.principal for ev in before)
    assert all(ev.actor is actor for ev in history[len(before):])


@pytest.mark.parametrize('actor', tuple(e.Principal))
@pytest.mark.parametrize('permission', (None, e.Permission.REVOKED, e.Permission.UNKNOWN))
def test_source_read_and_write_rights_do_not_imply_reviewer_authority(actor, permission):
    s = session(reviewers=() if permission is None else (reviewer(actor, permission),))
    r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    before = s.history(actor, HERON), s.summary(actor), s.inspect(actor, HERON)
    # No target existence/revision/inspection validation is observable without review authority.
    for b, rev, inspection in ((HERON, r.revision, e.Condition.VERIFIED),
                               (replace(HERON, request=e.Request.SECOND), -1, object())):
        assert s.reconcile(actor, b, rev, inspection) == l.Response()
    assert (s.history(actor, HERON), s.summary(actor), s.inspect(actor, HERON)) == before


@pytest.mark.parametrize('revoked', tuple(e.Principal))
def test_revoked_source_overrides_explicit_reviewer_authority(revoked):
    s = session(reviewers=(reviewer(revoked),))
    r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    assert s.commit_change(grant_change(s, recipient=revoked, read=e.Permission.REVOKED), confirm=True) is l.GrantResult.COMMITTED
    events = s._events
    assert s.reconcile(revoked, HERON, -1, object()) == l.Response()
    assert s.reconcile(revoked, replace(HERON, request=e.Request.SECOND), -1, object()) == l.Response()
    assert s.history(revoked, HERON) == ()
    assert s.inspect(revoked, HERON) is None
    assert s._events == events


def test_reviewer_after_initiator_revoke_never_gains_operation_consent():
    s = session(reviewers=(reviewer(),))
    r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    s.commit_change(grant_change(s, read=e.Permission.REVOKED), confirm=True)
    assert s.reconcile(e.Principal.ROBIN, HERON, r.revision, e.Condition.VERIFIED).state is l.State.QUARANTINED
    assert s.history(e.Principal.ROBIN, HERON)[-1].actor is e.Principal.ROBIN
    assert s.inspect(e.Principal.ROBIN, HERON).mutations == 1
    for action in tuple(e.Action):
        b = replace(restore_binding(s, e.Principal.ROBIN), action=action,
                    request=e.Request.SECOND if action is e.Action.RESTORE else e.Request.FIRST)
        p = s.propose(e.Principal.ROBIN, b, HERON if action is e.Action.RESTORE else None)
        a = s.approve(e.Principal.ROBIN, b, p.revision, e.Approval.EXPLICIT, b)
        assert a.state in (l.State.STOPPED, l.State.RESTORE_BLOCKED)
    assert s.inspect(e.Principal.ROBIN, HERON).mutations == 1


@pytest.mark.parametrize('inspection', (e.Condition.UNKNOWN, e.Condition.STALE, e.Condition.CONFLICTED))
@pytest.mark.parametrize('fault', (l.Fault.FAIL, l.Fault.TIMEOUT_AFTER))
def test_reviewer_cannot_erase_failed_or_unknown_outcome_without_verified_inspection(inspection, fault):
    s = session(reviewers=(reviewer(),))
    r = quarantine(s, fault)
    assert s.reconcile(e.Principal.ROBIN, HERON, r.revision, inspection).state is l.State.RECONCILE
    assert s.summary(e.Principal.ROBIN)['unresolved_attempts'] == 1
    assert s.summary(e.Principal.ROBIN)['verified_quarantine_attempts'] == 0


@pytest.mark.parametrize('reverse', (False, True))
def test_ambiguous_reviewer_assertions_fail_closed_but_consistent_duplicates_work(reverse):
    a = reviewer()
    grants = (a, reviewer(permission=e.Permission.REVOKED))
    s = session(reviewers=tuple(reversed(grants)) if reverse else grants)
    r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    assert s.reconcile(e.Principal.ROBIN, HERON, r.revision, e.Condition.VERIFIED) == l.Response()
    s.configure_reviewers((a, a))
    assert s.reconcile(e.Principal.ROBIN, HERON, r.revision, e.Condition.VERIFIED).state is l.State.QUARANTINED


def test_reviewer_grants_are_source_scoped_and_independently_revocable():
    s = session(reviewers=(reviewer(source=e.Source.PINE),))
    r = quarantine(s, l.Fault.TIMEOUT_AFTER)
    assert s.reconcile(e.Principal.ROBIN, HERON, r.revision, e.Condition.VERIFIED) == l.Response()
    s.configure_reviewers((reviewer(),))
    s.configure_reviewers(())
    assert s.inspect(e.Principal.ROBIN, HERON) is not None
    assert s.reconcile(e.Principal.ROBIN, HERON, r.revision, e.Condition.VERIFIED) == l.Response()


@pytest.mark.parametrize('values', ([], (object(),), (reviewer(),) * 5))
def test_reviewer_harness_rejects_invalid_or_oversized_collections_atomically(values):
    s = session(reviewers=())
    with pytest.raises(l.LifecycleError):
        s.configure_reviewers(values)
    assert s._reviewers == ()
