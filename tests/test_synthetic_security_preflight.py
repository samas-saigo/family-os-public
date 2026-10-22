"""New fictional E1 probes, no provider, model, frozen corpus or household input."""
import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from family_os import _synthetic_security_preflight as e


def ready(binding=None, **changes):
    b = binding or e.Binding()
    rights = e.Rights(b.household, b.source, b.principal, e.Permission.ALLOWED,
                     (b.action,), b.consent_revision, b.source_revision)
    conditions = {f.name: e.Condition.VERIFIED for f in fields(e.Context)
                  if f.type is e.Condition}
    defaults = dict(approval=e.Approval.EXPLICIT, safety=e.Safety.HIGH_RISK, emergency_stop=False)
    return e.Context(b, rights, b, b, **(defaults | conditions | changes))


def test_explicit_preflight_is_only_synthetic_and_immutable():
    b = e.Binding(); c = ready(b)
    assert e.preflight(b, c) is e.Verdict.ELIGIBLE
    assert c == ready(b)
    with pytest.raises(FrozenInstanceError):
        b.generation = 2


@pytest.mark.parametrize('action,name', [
    (action, f.name) for action in e.Action for f in fields(e.Context)
    if f.type is e.Condition and (f.name != 'history_complete' or action is e.Action.RESTORE)
])
@pytest.mark.parametrize('condition', [v for v in e.Condition if v is not e.Condition.VERIFIED])
def test_every_unknown_stale_conflicted_or_unsupported_gate_blocks(action, name, condition):
    b, c = (e.Binding(), ready()) if action is e.Action.QUARANTINE else restoration()
    assert e.preflight(b, replace(c, **{name: condition})) is e.Verdict.BLOCKED


@pytest.mark.parametrize('permission', [v for v in e.Permission if v is not e.Permission.ALLOWED])
def test_access_failure_withholds_even_binding_and_decision(permission):
    c = ready(); c = replace(c, rights=replace(c.rights, read=permission))
    assert e.preflight(e.Binding(), c) is e.Verdict.WITHHELD
    assert e.preflight(replace(e.Binding(), object=e.Object.OTHER), c) is e.Verdict.WITHHELD


@pytest.mark.parametrize('name,value', [
    ('household', e.Household.OTHER), ('source', e.Source.PINE),
    ('provider', e.Provider.TWO), ('object', e.Object.OTHER),
    ('principal', e.Principal.ROBIN), ('action', e.Action.RESTORE),
    ('generation', 2), ('provider_version', 2), ('folder', e.Folder.ARCHIVE),
    ('labels', e.Labels.USER_EDIT), ('target', e.Folder.PURGING), ('delta', e.Delta.UNDO_OWN_MOVE),
    ('source_revision', 2), ('consent_revision', 2), ('policy', e.Policy.V2), ('request', e.Request.SECOND),
])
def test_every_exact_binding_component_and_approval_must_match(name, value):
    b = e.Binding(); changed = replace(b, **{name: value})
    assert e.preflight(b, ready(changed)) in (e.Verdict.WITHHELD, e.Verdict.BLOCKED)
    assert e.preflight(b, replace(ready(), approval_binding=changed)) is e.Verdict.BLOCKED
    assert e.preflight(b, replace(ready(), assessment_binding=changed)) is e.Verdict.BLOCKED


@pytest.mark.parametrize('approval', [e.Approval.PENDING, e.Approval.STANDING_PROPOSED])
def test_standing_alternative_never_approves_even_high_risk(approval):
    assert e.preflight(e.Binding(), ready(approval=approval)) is e.Verdict.AWAITING


def test_two_peer_security_readers_have_different_exact_mailbox_write_rights():
    oak = e.Binding(); pine = replace(oak, source=e.Source.PINE, provider=e.Provider.TWO)
    for principal in e.Principal:
        b = replace(pine, principal=principal); c = ready(b)
        assert e.security_count((replace(oak, principal=principal), b),
                                (ready(replace(oak, principal=principal)).rights, c.rights), principal) == 2
        if principal is e.Principal.ASTER:
            c = replace(c, rights=replace(c.rights, operations=()))
        expected = e.Verdict.BLOCKED if principal is e.Principal.ASTER else e.Verdict.ELIGIBLE
        assert e.preflight(b, c) is expected
    assert e.preflight(pine, ready(oak)) is e.Verdict.WITHHELD


def restoration():
    original = e.Binding()
    b = replace(original, action=e.Action.RESTORE, folder=e.Folder.VAULT,
                target=e.Folder.INBOX, delta=e.Delta.UNDO_OWN_MOVE,
                generation=2, provider_version=2, request=e.Request.SECOND)
    record = e.Record(original, e.Outcome.VERIFIED_QUARANTINE)
    return b, ready(b, safety=e.Safety.CLEAR, records=(record,),
                    original_quarantine=record)


def test_restore_requires_own_approval_and_rights_not_quarantine_consent():
    b, c = restoration()
    assert e.preflight(b, c) is e.Verdict.ELIGIBLE
    assert e.preflight(b, replace(c, rights=replace(c.rights, operations=(e.Action.QUARANTINE,)))) is e.Verdict.BLOCKED
    assert e.preflight(b, replace(c, approval=e.Approval.PENDING)) is e.Verdict.AWAITING
    assert e.preflight(b, replace(c, original_quarantine=None)) is e.Verdict.BLOCKED


@pytest.mark.parametrize('outcome', [e.Outcome.FAILED, e.Outcome.UNKNOWN])
def test_failed_unknown_records_reconcile_even_with_changed_delivery_key(outcome):
    b = e.Binding(); record = e.Record(b, outcome)
    assert e.preflight(b, ready(records=(record,))) is e.Verdict.RECONCILE
    newer = replace(b, request=e.Request.SECOND)
    assert e.preflight(newer, ready(newer, records=(record,))) is e.Verdict.RECONCILE
    restore, c = restoration()
    assert e.preflight(restore, replace(c, original_quarantine=record)) is e.Verdict.BLOCKED


def test_replay_cannot_duplicate_mutation_or_reuse_key_for_changed_intent():
    b = e.Binding(); record = e.Record(b, e.Outcome.VERIFIED_QUARANTINE)
    assert e.preflight(b, ready(records=(record,))) is e.Verdict.REPLAY
    changed = replace(b, object=e.Object.OTHER)
    assert e.preflight(changed, ready(changed, records=(record,))) is e.Verdict.BLOCKED
    new_key = replace(b, request=e.Request.SECOND)
    assert e.preflight(new_key, ready(new_key, records=(record,))) is e.Verdict.BLOCKED


def test_evidence_revert_emergency_disable_and_revocation_block_queued_proposal():
    b = e.Binding()
    assert e.preflight(b, ready(emergency_stop=True)) is e.Verdict.BLOCKED
    assert e.preflight(b, ready(approval=e.Approval.REVOKED)) is e.Verdict.BLOCKED
    for generation in (2, 3):
        assert e.preflight(b, ready(replace(b, generation=generation))) is e.Verdict.BLOCKED


def test_false_positive_important_notice_is_not_proof_of_detector_quality():
    # Separately authored ground truth: this invented school notice is legitimate.
    # A falsely supplied independent verdict can pass the synthetic gates: no efficacy claim.
    assert e.preflight(e.Binding(), ready()) is e.Verdict.ELIGIBLE
    b, c = restoration()
    assert e.preflight(b, c) is e.Verdict.ELIGIBLE
    assert e.preflight(b, replace(c, no_later_user_changes=e.Condition.CONFLICTED)) is e.Verdict.BLOCKED


@pytest.mark.parametrize('safety', [v for v in e.Safety if v is not e.Safety.HIGH_RISK])
def test_no_high_risk_from_familiarity_authentication_or_release(safety):
    assert e.preflight(e.Binding(), ready(safety=safety)) is e.Verdict.BLOCKED


@pytest.mark.parametrize('folder', [e.Folder.INBOX, e.Folder.ARCHIVE, e.Folder.PURGING])
def test_unverified_or_purging_target_cannot_be_quarantine(folder):
    b = replace(e.Binding(), target=folder)
    assert e.preflight(b, ready(b)) is e.Verdict.BLOCKED


def test_revoked_source_and_hidden_duplicates_do_not_change_household_counts():
    oak = e.Binding(); pine = replace(oak, source=e.Source.PINE)
    rights = (ready(oak).rights, replace(ready(pine).rights, read=e.Permission.REVOKED))
    assert e.security_count((oak,), rights, e.Principal.ASTER) == e.security_count((oak,) + (pine,) * 100, rights, e.Principal.ASTER) == 1
    assert e.security_count((pine,) * 100, rights, e.Principal.ASTER) == 0
    hidden = e.Record(pine, e.Outcome.UNKNOWN)
    assert e.preflight(oak, ready(records=(hidden,) * 100)) is e.Verdict.ELIGIBLE
    assert e.security_count((oak, oak), rights, e.Principal.ASTER) == 1
    with pytest.raises(e.ContractError):
        e.preflight(oak, ready(records=(e.Record(oak, e.Outcome.UNKNOWN),) * 33))


@pytest.mark.parametrize('invalid', [True, 0, 1001, 1.0, 'secret', None])
@pytest.mark.parametrize('name', ['generation', 'provider_version', 'source_revision', 'consent_revision'])
def test_revision_inputs_are_bounded_and_errors_content_free(name, invalid):
    with pytest.raises(e.ContractError, match='^Synthetic security preflight rejected$'):
        replace(e.Binding(), **{name: invalid})


def test_no_production_wiring_imports_or_io(monkeypatch):
    root = Path(__file__).parents[1]; path = root / 'src/family_os/_synthetic_security_preflight.py'
    tree = ast.parse(path.read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imports == {'dataclasses', 'enum'}
    for other in (root / 'src/family_os').rglob('*.py'):
        if other != path and other.name != "_synthetic_security_lifecycle.py":
            assert '_synthetic_security_preflight' not in other.read_text()
    b = e.Binding(); c = ready()
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected I/O')
    import builtins
    import socket
    monkeypatch.setattr(builtins, 'open', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    assert e.preflight(b, c) is e.Verdict.ELIGIBLE


@pytest.mark.parametrize('safety', list(e.Safety))
def test_restore_release_does_not_override_current_risk(safety):
    b, c = restoration()
    expected = e.Verdict.ELIGIBLE if safety is e.Safety.CLEAR else e.Verdict.BLOCKED
    assert e.preflight(b, replace(c, safety=safety)) is expected


@pytest.mark.parametrize('name,value', [
    ('household', e.Household.OTHER), ('source', e.Source.PINE),
    ('provider', e.Provider.TWO), ('object', e.Object.OTHER),
    ('folder', e.Folder.PURGING), ('target', e.Folder.INBOX),
    ('delta', e.Delta.UNDO_OWN_MOVE), ('labels', e.Labels.USER_EDIT),
])
def test_restore_original_record_must_match_object_and_attributable_delta(name, value):
    b, c = restoration()
    original = replace(c.original_quarantine.binding, **{name: value})
    assert e.preflight(b, replace(c, original_quarantine=e.Record(
        original, e.Outcome.VERIFIED_QUARANTINE))) is e.Verdict.BLOCKED


@pytest.mark.parametrize('change', [
    {'approval': 'explicit'}, {'safety': None}, {'emergency_stop': 1},
    {'provider_state': True}, {'records': []}, {'records': (object(),)},
    {'original_quarantine': object()},
])
def test_context_rejects_untyped_or_unbounded_inputs(change):
    with pytest.raises(e.ContractError):
        replace(ready(), **change)


@pytest.mark.parametrize('operations', [[], ('quarantine',), (e.Action.QUARANTINE,) * 2,
                                        tuple(e.Action) + (e.Action.RESTORE,)])
def test_operation_scope_is_strict_bounded_and_unique(operations):
    with pytest.raises(e.ContractError):
        replace(ready().rights, operations=operations)


def test_authorized_source_history_is_not_fragmented_by_other_peer_actor():
    b = e.Binding()
    other_actor = replace(b, principal=e.Principal.ROBIN)
    assert e.security_count((other_actor,), (ready(b).rights,), e.Principal.ASTER) == 1
    assert e.security_count((b,), (ready(other_actor).rights,), e.Principal.ASTER) == 0
    prior = e.Record(other_actor, e.Outcome.UNKNOWN)
    assert e.preflight(b, ready(records=(prior,))) is e.Verdict.RECONCILE


@pytest.mark.parametrize('principal', list(e.Principal))
def test_unified_counts_use_scoped_objects_not_actors_or_action_attempts(principal):
    oak = e.Binding()
    other_actor = replace(oak, principal=e.Principal.ROBIN)
    later_attempt = replace(other_actor, generation=2, provider_version=2,
                            request=e.Request.SECOND, action=e.Action.RESTORE)
    pine = replace(oak, source=e.Source.PINE)
    other_object = replace(oak, object=e.Object.OTHER)
    other_provider = replace(oak, provider=e.Provider.TWO)
    rights = (ready(replace(oak, principal=principal)).rights,
              ready(replace(pine, principal=principal)).rights)
    observations = (oak, other_actor, later_attempt, pine, other_object, other_provider)
    assert e.security_count(observations, rights, principal) == 4
    assert e.security_count(tuple(reversed(observations)), rights, principal) == 4
    assert e.security_count((oak, other_actor) * 100, rights, principal) == 1


@pytest.mark.parametrize('permission', [v for v in e.Permission if v is not e.Permission.ALLOWED])
def test_hidden_peer_duplicates_do_not_affect_unique_visible_counts(permission):
    oak = e.Binding(); pine = replace(oak, source=e.Source.PINE)
    hidden_peer = replace(pine, principal=e.Principal.ROBIN)
    rights = (ready(oak).rights, replace(ready(pine).rights, read=permission))
    assert e.security_count((oak, replace(oak, principal=e.Principal.ROBIN)),
                            rights, e.Principal.ASTER) == 1
    assert e.security_count((oak,) + (pine, hidden_peer) * 100,
                            rights, e.Principal.ASTER) == 1
    assert e.security_count((pine, hidden_peer) * 100, rights, e.Principal.ASTER) == 0


@pytest.mark.parametrize('generation', [1, 2, 3])
@pytest.mark.parametrize('provider_version', [1, 2, 3])
def test_restore_requires_strictly_newer_synthetic_chronology(generation, provider_version):
    original_binding = replace(e.Binding(), generation=2, provider_version=2)
    original = e.Record(original_binding, e.Outcome.VERIFIED_QUARANTINE)
    b, _ = restoration()
    b = replace(b, generation=generation, provider_version=provider_version)
    c = ready(b, safety=e.Safety.CLEAR, records=(original,), original_quarantine=original)
    expected = e.Verdict.ELIGIBLE if generation > 2 and provider_version > 2 else e.Verdict.BLOCKED
    assert e.preflight(b, c) is expected


@pytest.mark.parametrize('records', ['missing', 'duplicate', 'another-quarantine', 'stale-original'])
def test_restore_requires_exact_single_original_in_declared_complete_history(records):
    b, c = restoration(); original = c.original_quarantine
    alternate = e.Record(replace(original.binding, generation=2, provider_version=2,
                                 request=e.Request.SECOND), e.Outcome.VERIFIED_QUARANTINE)
    history = {'missing': (), 'duplicate': (original, original),
               'another-quarantine': (original, alternate), 'stale-original': (alternate,)}[records]
    assert e.preflight(b, replace(c, records=history)) is e.Verdict.BLOCKED


@pytest.mark.parametrize('actor', list(e.Principal))
@pytest.mark.parametrize('delivery_key', list(e.Request))
def test_verified_restore_never_permits_a_new_restore_of_original_episode(actor, delivery_key):
    restored, c = restoration()
    prior = e.Record(replace(restored, principal=actor), e.Outcome.VERIFIED_RESTORE)
    candidate = replace(restored, generation=3, provider_version=3, request=delivery_key)
    context = ready(candidate, safety=e.Safety.CLEAR,
                    records=(c.original_quarantine, prior),
                    original_quarantine=c.original_quarantine)
    assert e.preflight(candidate, context) is e.Verdict.BLOCKED


def test_exact_restore_replay_is_historical_only_not_new_eligibility():
    b, c = restoration()
    prior = e.Record(b, e.Outcome.VERIFIED_RESTORE)
    assert e.preflight(b, replace(c, records=(c.original_quarantine, prior))) is e.Verdict.REPLAY
    assert e.preflight(b, replace(c, records=())) is e.Verdict.BLOCKED


@pytest.mark.parametrize('field,value', [('provider_version', 3), ('generation', 3),
                                        ('folder', e.Folder.ARCHIVE), ('labels', e.Labels.USER_EDIT)])
def test_restore_approval_cannot_follow_a_changed_provider_snapshot(field, value):
    b, c = restoration()
    assert e.preflight(b, replace(c, current=replace(b, **{field: value}))) is e.Verdict.BLOCKED


def test_restore_ignores_hidden_history_but_not_missing_visible_proof():
    b, c = restoration()
    hidden = e.Record(replace(b, source=e.Source.PINE), e.Outcome.VERIFIED_RESTORE)
    assert e.preflight(b, replace(c, records=c.records + (hidden,) * 100)) is e.Verdict.ELIGIBLE
    assert e.preflight(b, replace(c, records=(hidden,) * 100)) is e.Verdict.BLOCKED


@pytest.mark.parametrize('principal', list(e.Principal))
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('state,revision', [
    (e.Permission.REVOKED, 2),  # Older ALLOWED must not override newer revoke.
    (e.Permission.REVOKED, 1),  # Same-revision contradiction is not authority.
    (e.Permission.UNKNOWN, 1),
    (e.Permission.UNKNOWN, 2),
    (e.Permission.ALLOWED, 2),  # Two purported current revisions are ambiguous.
    (e.Permission.DENIED, 1),
])
def test_conflicting_effective_rights_withhold_only_affected_source(principal, reverse, state, revision):
    oak = replace(e.Binding(), principal=principal)
    pine = replace(oak, source=e.Source.PINE)
    allowed = ready(oak).rights
    conflicting = replace(allowed, read=state, source_revision=revision)
    rights = (allowed, conflicting, ready(pine).rights)
    if reverse:
        rights = tuple(reversed(rights))
    peer_binding = replace(oak, principal=e.Principal.ROBIN)
    assert e.security_count((oak, peer_binding), rights, principal) == 0
    assert e.security_count((oak, peer_binding, pine), rights, principal) == 1
    assert e.security_count((pine,) + (oak, peer_binding) * 100, rights, principal) == 1


@pytest.mark.parametrize('permission', list(e.Permission))
@pytest.mark.parametrize('principal', list(e.Principal))
def test_identical_grant_duplicates_are_consistent_not_multiple_authority(permission, principal):
    oak = replace(e.Binding(), principal=principal)
    grant = replace(ready(oak).rights, read=permission)
    expected = 1 if permission is e.Permission.ALLOWED else 0
    assert e.security_count((oak,), (grant, grant), principal) == expected
    assert e.security_count((oak,) * 100, (grant,) * 4, principal) == expected


@pytest.mark.parametrize('difference', [
    {'consent_revision': 2}, {'operations': ()}, {'source_revision': 2},
])
def test_distinct_grant_assertions_cannot_select_an_arbitrary_allowed_value(difference):
    b = e.Binding(); grant = ready(b).rights; alternate = replace(grant, **difference)
    assert e.security_count((b,), (grant, alternate, grant), b.principal) == 0
    assert e.security_count((b,), (alternate, grant, alternate), b.principal) == 0


def test_other_peer_conflicts_do_not_suppress_current_peers_authorized_household():
    oak = e.Binding(); pine = replace(oak, source=e.Source.PINE)
    other_peer = ready(replace(oak, principal=e.Principal.ROBIN)).rights
    rights = (ready(oak).rights, other_peer,
              replace(other_peer, read=e.Permission.REVOKED), ready(pine).rights)
    assert e.security_count((oak, replace(oak, principal=e.Principal.ROBIN), pine),
                            rights, e.Principal.ASTER) == 2
    assert e.security_count((oak, pine), tuple(reversed(rights)), e.Principal.ROBIN) == 0


def test_different_household_grant_key_does_not_shadow_authorized_source():
    b = e.Binding(); grant = ready(b).rights
    different_household = replace(grant, household=e.Household.OTHER, read=e.Permission.REVOKED)
    assert e.security_count((b,), (grant, different_household), b.principal) == 1
