"""New Stage A enum-only specimens, never real/frozen fixture or database inputs."""
import ast
from dataclasses import FrozenInstanceError, fields, replace
from itertools import product
from pathlib import Path

import pytest

from family_os import _synthetic_routing as r


def case(business=None, safety=r.Safety.SAFE_TO_ROUTE):
    snapshot = r.Snapshot(business=business or r.Business())
    return r.Case(snapshot, assessment=r.Assessment(snapshot, r.Policy.V1, safety))


ACCESS = r.Access()
ACTION = r.Business(action=r.ActionEvidence.SUPPORTED, importance=r.Importance.IMPORTANT)
BUSINESSES = tuple(r.Business(*values) for values in product(
    (False, True), r.ActionEvidence, r.Importance, (False, True), r.Expiry))

# Newly invented English walkthrough names, with authored enum evidence only.
# No titles, body strings, dates or classifier predictions are parsed as signals.
SPECIMENS = (
    ("Lantern shop's optional ribbon discount", r.Business(promotion=True),
     r.Safety.SAFE_TO_ROUTE, r.Destination.PROMOTIONS),
    ("Ribbon discount ends today", r.Business(promotion=True, expiry=r.Expiry.UPCOMING),
     r.Safety.SAFE_TO_ROUTE, r.Destination.PROMOTIONS),
    ("Ribbon discount ended yesterday", r.Business(promotion=True, expiry=r.Expiry.EXPIRED),
     r.Safety.SAFE_TO_ROUTE, r.Destination.PROMOTIONS),
    ("Discount with independently flagged credential lure", r.Business(promotion=True),
     r.Safety.SUSPICIOUS, r.Destination.SECURITY_HOLD),
    ("Art club notice with unclear preparation instruction",
     r.Business(importance=r.Importance.IMPORTANT), r.Safety.SAFE_TO_ROUTE,
     r.Destination.PENDING),
    ("Library equipment pickup requires a confirmed time choice", ACTION,
     r.Safety.SAFE_TO_ROUTE, r.Destination.PENDING),
    ("Pickup instruction while synthetic detector is unavailable", ACTION,
     r.Safety.UNAVAILABLE, r.Destination.UNASSESSED),
    ("Discount plus separately supported pickup step",
     replace(ACTION, promotion=True), r.Safety.SAFE_TO_ROUTE, r.Destination.PENDING),
    ("Pickup step with high-risk synthetic evidence", ACTION,
     r.Safety.HIGH_RISK, r.Destination.SECURITY_HOLD),
    ("Quiet workshop information with no step", r.Business(
     informational=True, importance=r.Importance.NOT_IMPORTANT),
     r.Safety.SAFE_TO_ROUTE, r.Destination.INFORMATION),
    ("Unknown importance remains unresolved", r.Business(),
     r.Safety.SAFE_TO_ROUTE, r.Destination.PENDING),
    ("Contradictory pickup instructions plus optional discount",
     r.Business(promotion=True, action=r.ActionEvidence.CONFLICTING),
     r.Safety.SAFE_TO_ROUTE, r.Destination.PENDING),
)


@pytest.mark.parametrize("name,business,safety,destination", SPECIMENS,
                         ids=[specimen[0] for specimen in SPECIMENS])
def test_new_authored_walkthroughs(name, business, safety, destination):
    result = r.route(case(business, safety), ACCESS)
    assert result.destination is destination
    assert result.business == business and result.safety is safety
    assert result.authority is r.Authority.NONE
    assert not result.offer_visible
    assert not result.proactive_alert and not result.creates_task and not result.provider_write


@pytest.mark.parametrize("safety", tuple(r.Safety))
@pytest.mark.parametrize("business", BUSINESSES)
def test_exhaustive_safety_business_overlap_and_quietness(business, safety):
    input_case = case(business, safety)
    for intent in r.Intent:
        first = r.route(input_case, ACCESS, intent)
        assert first == r.route(input_case, ACCESS, intent)
        assert first.business == business and first.safety is safety
        assert first.authority is r.Authority.NONE
        assert not first.proactive_alert and not first.creates_task and not first.provider_write
        if safety in (r.Safety.SUSPICIOUS, r.Safety.HIGH_RISK):
            assert first.destination is r.Destination.SECURITY_HOLD
            assert not first.offer_visible
        elif safety is not r.Safety.SAFE_TO_ROUTE:
            assert first.destination is r.Destination.UNASSESSED
            assert not first.offer_visible
        elif business.action is not r.ActionEvidence.NONE:
            assert first.destination is r.Destination.PENDING
            assert not first.offer_visible
        elif business.importance is r.Importance.IMPORTANT:
            assert first.destination is r.Destination.PENDING
            assert not first.offer_visible
        elif business.promotion:
            assert first.destination is r.Destination.PROMOTIONS
            assert first.offer_visible == (intent is r.Intent.OFFER_QUERY)
        elif business.importance is not r.Importance.NOT_IMPORTANT:
            assert first.destination is r.Destination.PENDING
        elif business.informational:
            assert first.destination is r.Destination.INFORMATION
        else:
            assert first.destination is r.Destination.ABSTAIN


@pytest.mark.parametrize("permission", tuple(r.Permission))
@pytest.mark.parametrize("household", tuple(r.Household))
@pytest.mark.parametrize("source", tuple(r.Source))
@pytest.mark.parametrize("safety", tuple(r.Safety))
def test_exact_source_access_before_any_projection_or_intent_validation(
        permission, household, source, safety):
    grant = r.Access(household, source, permission)
    input_case = case(ACTION, safety)
    allowed = (permission is r.Permission.ALLOWED and household is r.Household.A
               and source is r.Source.A)
    if allowed:
        assert r.route(input_case, grant) is not None
    else:
        # No existence-bearing identity, reason, link, count, history or placeholder.
        assert r.route(input_case, grant) is None
        assert r.route(input_case, grant, "invalid synthetic intent") is None
        other = replace(input_case, snapshot=replace(input_case.snapshot, item=r.Item.B))
        assert r.route(other, grant) is None
        for authority in (r.Authority.REVIEW_CONFIRMED, r.Authority.SIMULATED_ACCEPTANCE):
            with pytest.raises(r.RoutingError, match="^Synthetic routing contract rejected$"):
                r.decide(input_case, grant, authority, r.Confirmation.EXPLICIT)
        assert input_case.history == ()


@pytest.mark.parametrize("authority", (r.Authority.REVIEW_CONFIRMED,
                                      r.Authority.SIMULATED_ACCEPTANCE))
def test_explicit_simulated_decisions_are_separate_and_immutable(authority):
    original = case(ACTION)
    decided = r.decide(original, ACCESS, authority, r.Confirmation.EXPLICIT)
    result = r.route(decided, ACCESS)
    assert original.history == () and len(decided.history) == 1
    assert result.authority is authority
    expected = (r.Destination.SIMULATED_ACCEPTED
                if authority is r.Authority.SIMULATED_ACCEPTANCE else r.Destination.PENDING)
    assert result.destination is expected
    assert not result.creates_task and not result.provider_write and not result.proactive_alert
    with pytest.raises(FrozenInstanceError):
        decided.history[0].authority = r.Authority.SIMULATED_ACCEPTANCE


def test_repeated_review_confirmation_never_becomes_acceptance():
    current = case(ACTION)
    for _ in range(3):
        current = r.decide(current, ACCESS, r.Authority.REVIEW_CONFIRMED,
                           r.Confirmation.EXPLICIT)
        projection = r.route(current, ACCESS)
        assert projection.authority is r.Authority.REVIEW_CONFIRMED
        assert projection.destination is r.Destination.PENDING
        assert not projection.historical_acceptance and not projection.creates_task
    assert len(current.history) == 3


def test_acceptance_followed_by_repeated_review_preserves_current_acceptance():
    accepted = r.decide(case(ACTION), ACCESS, r.Authority.SIMULATED_ACCEPTANCE,
                        r.Confirmation.EXPLICIT)
    current = accepted
    for _ in range(3):
        previous = current
        current = r.decide(current, ACCESS, r.Authority.REVIEW_CONFIRMED,
                           r.Confirmation.EXPLICIT)
        assert current.history[:-1] == previous.history
        assert current.history[-1].authority is r.Authority.REVIEW_CONFIRMED
        result = r.route(current, ACCESS)
        assert result.authority is r.Authority.SIMULATED_ACCEPTANCE
        assert result.destination is r.Destination.SIMULATED_ACCEPTED
        assert result.historical_acceptance and not result.acceptance_requires_revalidation
        assert not result.creates_task and not result.proactive_alert and not result.provider_write
    assert len(current.history) == 4 and len(accepted.history) == 1


@pytest.mark.parametrize("safety", tuple(r.Safety))
@pytest.mark.parametrize("policy", tuple(r.Policy))
def test_review_after_acceptance_does_not_transfer_to_changed_assessment(safety, policy):
    accepted = r.decide(case(ACTION), ACCESS, r.Authority.SIMULATED_ACCEPTANCE,
                        r.Confirmation.EXPLICIT)
    reviewed = r.decide(accepted, ACCESS, r.Authority.REVIEW_CONFIRMED, r.Confirmation.EXPLICIT)
    changed = r.reassess(reviewed, safety, policy)
    result = r.route(changed, ACCESS)
    assert result.authority is r.Authority.NONE and result.acceptance_requires_revalidation
    assert changed.history == reviewed.history
    if safety is r.Safety.SAFE_TO_ROUTE:
        new_review = r.decide(changed, ACCESS, r.Authority.REVIEW_CONFIRMED,
                              r.Confirmation.EXPLICIT)
        assert r.route(new_review, ACCESS).destination is r.Destination.PENDING
        assert r.route(new_review, ACCESS).acceptance_requires_revalidation
    else:
        with pytest.raises(r.RoutingError):
            r.decide(changed, ACCESS, r.Authority.REVIEW_CONFIRMED, r.Confirmation.EXPLICIT)


def test_review_after_acceptance_and_evidence_revert_needs_new_acceptance():
    accepted = r.decide(case(ACTION), ACCESS, r.Authority.SIMULATED_ACCEPTANCE,
                        r.Confirmation.EXPLICIT)
    reviewed = r.decide(accepted, ACCESS, r.Authority.REVIEW_CONFIRMED, r.Confirmation.EXPLICIT)
    changed = r.advance(reviewed, r.Evidence.CHANGED, ACTION)
    reverted = r.advance(changed, r.Evidence.ORIGINAL, ACTION)
    fresh = replace(reverted, assessment=r.Assessment(reverted.snapshot, r.Policy.V1,
                                                     r.Safety.SAFE_TO_ROUTE))
    confirmed = r.decide(fresh, ACCESS, r.Authority.REVIEW_CONFIRMED, r.Confirmation.EXPLICIT)
    result = r.route(confirmed, ACCESS)
    assert result.authority is r.Authority.REVIEW_CONFIRMED
    assert result.destination is r.Destination.PENDING and result.acceptance_requires_revalidation
    assert confirmed.history[:2] == reviewed.history
    assert r.route(reviewed, ACCESS).destination is r.Destination.SIMULATED_ACCEPTED


@pytest.mark.parametrize("safety", tuple(r.Safety))
@pytest.mark.parametrize("expiry", tuple(r.Expiry))
@pytest.mark.parametrize("intent", tuple(r.Intent))
def test_important_service_without_action_is_not_hidden_by_ad(safety, expiry, intent):
    business = r.Business(promotion=True, action=r.ActionEvidence.NONE,
                          importance=r.Importance.IMPORTANT, informational=True, expiry=expiry)
    current = case(business, safety)
    result = r.route(current, ACCESS, intent)
    expected = (r.Destination.PENDING if safety is r.Safety.SAFE_TO_ROUTE
                else r.Destination.SECURITY_HOLD
                if safety in (r.Safety.SUSPICIOUS, r.Safety.HIGH_RISK)
                else r.Destination.UNASSESSED)
    assert result.destination is expected and not result.offer_visible
    assert not result.proactive_alert and not result.creates_task and not result.provider_write
    for authority in (r.Authority.REVIEW_CONFIRMED, r.Authority.SIMULATED_ACCEPTANCE):
        with pytest.raises(r.RoutingError):
            r.decide(current, ACCESS, authority, r.Confirmation.EXPLICIT)


@pytest.mark.parametrize("importance", (r.Importance.UNKNOWN, r.Importance.NOT_IMPORTANT))
@pytest.mark.parametrize("expiry", tuple(r.Expiry))
def test_advertising_without_independent_service_importance_stays_quiet(importance, expiry):
    current = case(r.Business(promotion=True, importance=importance, expiry=expiry))
    assert r.route(current, ACCESS).destination is r.Destination.PROMOTIONS
    assert not r.route(current, ACCESS).offer_visible
    assert r.route(current, ACCESS, r.Intent.OFFER_QUERY).offer_visible
    assert not r.route(current, ACCESS).creates_task


@pytest.mark.parametrize("permission", (r.Permission.DENIED, r.Permission.UNKNOWN,
                                       r.Permission.REVOKED))
def test_accepted_synthetic_history_never_leaks_to_unauthorized_source(permission):
    accepted = r.decide(case(ACTION), ACCESS, r.Authority.SIMULATED_ACCEPTANCE,
                        r.Confirmation.EXPLICIT)
    assert r.route(accepted, r.Access(permission=permission)) is None
    assert r.route(accepted, r.Access(source=r.Source.B)) is None
    assert len(accepted.history) == 1


@pytest.mark.parametrize("safety", tuple(r.Safety))
@pytest.mark.parametrize("action", tuple(r.ActionEvidence))
@pytest.mark.parametrize("authority", tuple(r.Authority))
@pytest.mark.parametrize("confirmation", tuple(r.Confirmation))
def test_decision_gate_is_exhaustive(safety, action, authority, confirmation):
    original = case(r.Business(promotion=True, action=action), safety)
    can_decide = (safety is r.Safety.SAFE_TO_ROUTE and action is r.ActionEvidence.SUPPORTED
                  and authority is not r.Authority.NONE and confirmation is r.Confirmation.EXPLICIT)
    if can_decide:
        assert len(r.decide(original, ACCESS, authority, confirmation).history) == 1
    else:
        with pytest.raises(r.RoutingError):
            r.decide(original, ACCESS, authority, confirmation)
    assert original.history == ()


def test_changed_and_reverted_evidence_never_revives_acceptance_or_review():
    original = case(ACTION)
    reviewed = r.decide(original, ACCESS, r.Authority.REVIEW_CONFIRMED, r.Confirmation.EXPLICIT)
    accepted = r.decide(reviewed, ACCESS, r.Authority.SIMULATED_ACCEPTANCE, r.Confirmation.EXPLICIT)
    changed = r.advance(accepted, r.Evidence.CHANGED,
                        r.Business(action=r.ActionEvidence.CONFLICTING))
    assert changed.snapshot.generation == 2 and changed.assessment is None
    assert changed.history == accepted.history
    assert r.route(changed, ACCESS).destination is r.Destination.UNASSESSED
    reverted = r.advance(changed, r.Evidence.ORIGINAL, ACTION)
    assert reverted.snapshot.generation == 3
    # Even an otherwise identical assessment needs the new exact snapshot.
    old_assessment = replace(reverted, assessment=accepted.assessment)
    assert r.route(old_assessment, ACCESS).safety is r.Safety.STALE
    fresh = replace(reverted, assessment=r.Assessment(reverted.snapshot, r.Policy.V1,
                                                     r.Safety.SAFE_TO_ROUTE))
    result = r.route(fresh, ACCESS)
    assert result.destination is r.Destination.PENDING and result.authority is r.Authority.NONE
    assert result.historical_acceptance and result.acceptance_requires_revalidation
    assert fresh.history == accepted.history
    with pytest.raises(r.RoutingError):
        r.decide(fresh, ACCESS, r.Authority.SIMULATED_ACCEPTANCE, r.Confirmation.UNCONFIRMED)
    new = r.decide(fresh, ACCESS, r.Authority.REVIEW_CONFIRMED, r.Confirmation.EXPLICIT)
    assert r.route(new, ACCESS).destination is r.Destination.PENDING
    new = r.decide(new, ACCESS, r.Authority.SIMULATED_ACCEPTANCE, r.Confirmation.EXPLICIT)
    assert r.route(new, ACCESS).destination is r.Destination.SIMULATED_ACCEPTED
    assert len(new.history) == 4 and accepted.history == reviewed.history + (accepted.history[-1],)


@pytest.mark.parametrize("change", (
    {"household": r.Household.B}, {"source": r.Source.B}, {"item": r.Item.B},
    {"generation": 2}, {"evidence": r.Evidence.CHANGED},
    {"business": replace(ACTION, promotion=True)},
))
def test_each_snapshot_component_blocks_assessment_and_decision_transfer(change):
    accepted = r.decide(case(ACTION), ACCESS, r.Authority.SIMULATED_ACCEPTANCE,
                        r.Confirmation.EXPLICIT)
    current = replace(accepted, snapshot=replace(accepted.snapshot, **change))
    grant = r.Access(current.snapshot.household, current.snapshot.source)
    result = r.route(current, grant)
    assert result.safety is r.Safety.STALE and result.authority is r.Authority.NONE
    fresh = replace(current, assessment=r.Assessment(current.snapshot, r.Policy.V1,
                                                     r.Safety.SAFE_TO_ROUTE))
    assert r.route(fresh, grant).authority is r.Authority.NONE
    assert r.route(fresh, grant).destination is r.Destination.PENDING


@pytest.mark.parametrize("safety", tuple(r.Safety))
def test_safety_change_overrides_current_simulated_acceptance(safety):
    accepted = r.decide(case(ACTION), ACCESS, r.Authority.SIMULATED_ACCEPTANCE,
                        r.Confirmation.EXPLICIT)
    assessed = replace(accepted, assessment=replace(accepted.assessment, safety=safety))
    result = r.route(assessed, ACCESS)
    if safety is r.Safety.SAFE_TO_ROUTE:
        assert result.authority is r.Authority.SIMULATED_ACCEPTANCE
    else:
        assert result.authority is r.Authority.NONE and result.historical_acceptance
        assert result.acceptance_requires_revalidation
        assert result.destination not in (r.Destination.SIMULATED_ACCEPTED, r.Destination.PROMOTIONS)
    assert assessed.history == accepted.history


def test_missing_assessment_policy_change_and_foreign_history_fail_closed():
    accepted = r.decide(case(ACTION), ACCESS, r.Authority.SIMULATED_ACCEPTANCE,
                        r.Confirmation.EXPLICIT)
    missing = replace(accepted, assessment=None)
    assert r.route(missing, ACCESS).safety is r.Safety.UNKNOWN
    policy_changed = replace(accepted, policy=r.Policy.V2)
    assert r.route(policy_changed, ACCESS).safety is r.Safety.STALE
    fresh = replace(policy_changed, assessment=r.Assessment(accepted.snapshot, r.Policy.V2,
                                                           r.Safety.SAFE_TO_ROUTE))
    assert r.route(fresh, ACCESS).authority is r.Authority.NONE
    foreign = replace(case(ACTION), snapshot=replace(accepted.snapshot, item=r.Item.B))
    foreign = replace(foreign, assessment=r.Assessment(foreign.snapshot, r.Policy.V1,
                                                       r.Safety.SAFE_TO_ROUTE), history=accepted.history)
    assert not r.route(foreign, ACCESS).historical_acceptance
    assert r.route(foreign, ACCESS).authority is r.Authority.NONE


@pytest.mark.parametrize("safety", tuple(r.Safety))
@pytest.mark.parametrize("policy", tuple(r.Policy))
def test_new_safety_or_policy_episode_and_revert_cannot_restore_old_acceptance(safety, policy):
    accepted = r.decide(case(ACTION), ACCESS, r.Authority.SIMULATED_ACCEPTANCE,
                        r.Confirmation.EXPLICIT)
    changed = r.reassess(accepted, safety, policy)
    assert changed.snapshot.generation == 2
    assert r.route(changed, ACCESS).authority is r.Authority.NONE
    reverted = r.reassess(changed, r.Safety.SAFE_TO_ROUTE, r.Policy.V1)
    result = r.route(reverted, ACCESS)
    assert reverted.snapshot.generation == 3
    assert reverted.history == accepted.history
    assert result.authority is r.Authority.NONE and result.destination is r.Destination.PENDING
    assert result.historical_acceptance and result.acceptance_requires_revalidation


@pytest.mark.parametrize("expiry", tuple(r.Expiry))
def test_promotion_expiry_never_alerts_or_accepts_or_clears_security(expiry):
    promo = case(r.Business(promotion=True, expiry=expiry))
    for safety in r.Safety:
        assessed = replace(promo, assessment=replace(promo.assessment, safety=safety))
        result = r.route(assessed, ACCESS, r.Intent.OFFER_QUERY)
        assert not result.proactive_alert and not result.creates_task and not result.provider_write
        assert result.offer_visible == (safety is r.Safety.SAFE_TO_ROUTE)
        with pytest.raises(r.RoutingError):
            r.decide(assessed, ACCESS, r.Authority.SIMULATED_ACCEPTANCE, r.Confirmation.EXPLICIT)


@pytest.mark.parametrize("generation", (0, -1, 1001, True, 1.5, "1"))
def test_bounded_exact_integer_generation(generation):
    with pytest.raises(r.RoutingError):
        r.Snapshot(generation=generation)


@pytest.mark.parametrize("factory", (
    lambda: r.Business(promotion=1), lambda: r.Business(informational="yes"),
    lambda: r.Business(action="supported"), lambda: r.Business(importance="important"),
    lambda: r.Business(expiry="expired"), lambda: r.Snapshot(source="private mailbox"),
    lambda: r.Snapshot(item="private message ID"), lambda: r.Snapshot(evidence="private text"),
    lambda: r.Snapshot(business={}), lambda: r.Access(permission=True),
    lambda: r.Access(household="household"), lambda: r.Access(source="source"),
    lambda: r.Assessment(None, r.Policy.V1, r.Safety.SAFE_TO_ROUTE),
    lambda: r.Assessment(r.Snapshot(), "v1", r.Safety.SAFE_TO_ROUTE),
    lambda: r.Assessment(r.Snapshot(), r.Policy.V1, "safe"),
    lambda: r.Case(None), lambda: r.Case(r.Snapshot(), policy="v1"),
    lambda: r.Case(r.Snapshot(), assessment={}), lambda: r.Case(r.Snapshot(), history=[]),
    lambda: r.Case(r.Snapshot(), history=(None,)),
    lambda: r.Decision(None, r.Authority.REVIEW_CONFIRMED),
    lambda: r.Decision(case().assessment, r.Authority.NONE),
))
def test_untrusted_fields_fail_with_generic_no_content_errors(factory, caplog):
    with pytest.raises(r.RoutingError) as error:
        factory()
    assert str(error.value) == "Synthetic routing contract rejected"
    assert not caplog.records


def test_caps_no_mutation_and_no_free_form_content_fields():
    original = case(ACTION)
    history = ()
    for _ in range(r.MAX_DECISIONS):
        original = r.decide(original, ACCESS, r.Authority.REVIEW_CONFIRMED, r.Confirmation.EXPLICIT)
        assert original.history[:len(history)] == history
        history = original.history
    with pytest.raises(r.RoutingError):
        r.decide(original, ACCESS, r.Authority.SIMULATED_ACCEPTANCE, r.Confirmation.EXPLICIT)
    assert original.history == history
    with pytest.raises(r.RoutingError):
        replace(original, history=history + (history[0],))
    with pytest.raises(r.RoutingError):
        r.advance(replace(original, snapshot=replace(original.snapshot, generation=1000)),
                  r.Evidence.CHANGED, ACTION)
    with pytest.raises(TypeError):
        r.Snapshot(subject="not accepted")
    assert all(field.name not in ("subject", "sender", "raw_metadata", "payload", "url")
               for cls in (r.Snapshot, r.Business, r.Assessment, r.Decision, r.Case)
               for field in fields(cls))
    projection = r.route(original, ACCESS)
    for attribute in ("proactive_alert", "creates_task", "provider_write"):
        with pytest.raises(FrozenInstanceError):
            setattr(projection, attribute, True)
    with pytest.raises(r.RoutingError):
        r.reassess(None, r.Safety.SAFE_TO_ROUTE, r.Policy.V1)


def test_source_isolation_static_and_runtime_without_io(monkeypatch):
    root = Path(__file__).parents[1]
    path = root / "src/family_os/_synthetic_routing.py"
    tree = ast.parse(path.read_text())
    imports = [node.module if isinstance(node, ast.ImportFrom) else alias.name
               for node in ast.walk(tree) if isinstance(node, (ast.ImportFrom, ast.Import))
               for alias in (node.names if isinstance(node, ast.Import) else (None,))]
    assert set(imports) == {"dataclasses", "enum"}
    # Only the explicitly opted-in Stage C and I5 synthetic adapters may reuse this contract.
    for production in (root / "src/family_os").rglob("*.py"):
        if production in (path, root/"src/family_os/_synthetic_phishing_demo.py", root/"src/family_os/_fictional_information.py"):
            continue
        assert "_synthetic_routing" not in production.read_text()
    original = case(ACTION)

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected I/O")

    import builtins
    import socket
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert r.route(original, ACCESS).destination is r.Destination.PENDING
    changed = r.advance(original, r.Evidence.CHANGED, ACTION)
    assert r.route(changed, ACCESS).safety is r.Safety.UNKNOWN
    confirmed = r.decide(original, ACCESS, r.Authority.REVIEW_CONFIRMED, r.Confirmation.EXPLICIT)
    assert r.route(confirmed, ACCESS).destination is r.Destination.PENDING
