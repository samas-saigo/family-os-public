"""Stage B tests only: new enum evidence, no model/mail/frozen corpus/database."""
import ast
from dataclasses import FrozenInstanceError, fields, replace
from itertools import combinations, permutations, product
from pathlib import Path

import pytest

from family_os import _synthetic_phishing_policy as p
from family_os import _synthetic_phishing_evaluation as e
from family_os import _synthetic_routing as a

ACCESS = p.Access()
BINDING = p.Binding()
HIGH = p.evaluate(BINDING, p.Evidence(findings=(p.Finding.IMPERSONATION,)), ACCESS)
GATES = p.Conditions(approval=p.Approval.EXPLICIT_SIMULATION, observed=p.Observed.VERIFIED)
FINDINGS = tuple(combo for n in range(len(p.Finding) + 1) for combo in combinations(p.Finding, n))


@pytest.mark.parametrize("sample", e.CASES, ids=lambda s: s.specimen.value)
def test_new_synthetic_corpus_determinism(sample):
    first = p.evaluate(sample.evidence.binding, sample.evidence, ACCESS)
    assert first == p.evaluate(sample.evidence.binding, sample.evidence, ACCESS)
    assert not first.action_authority
    assert sample.evidence.claims == tuple(sample.evidence.claims)


@pytest.mark.parametrize("findings", FINDINGS)
@pytest.mark.parametrize("state", tuple(p.EvidenceState))
@pytest.mark.parametrize("auth", tuple(p.Authentication))
def test_evidence_precedence_and_abstention(findings, state, auth):
    evidence = p.Evidence(state=state, findings=findings, authentication=auth)
    result = p.evaluate(BINDING, evidence, ACCESS)
    if state is not p.EvidenceState.CURRENT:
        assert result.outcome is p.Outcome.INDETERMINATE
    elif p.Finding.CHECKED_CLEAR in findings and len(findings) > 1:
        assert result.outcome is p.Outcome.INDETERMINATE
        assert result.reason is p.Reason.CONFLICT
    elif any(f in findings for f in (p.Finding.IMPERSONATION, p.Finding.COMPROMISED,
                                    p.Finding.MALICIOUS_DESTINATION)):
        assert result.outcome is p.Outcome.HIGH_RISK
    elif p.Finding.ANOMALY in findings or auth is p.Authentication.FAIL:
        assert result.outcome is p.Outcome.SUSPICIOUS
    elif p.Finding.CHECKED_CLEAR in findings:
        assert result.outcome is p.Outcome.SAFE_TO_ROUTE
    else:
        assert result.outcome is p.Outcome.INDETERMINATE
    for order in permutations(findings):
        assert p.evaluate(BINDING, replace(evidence, findings=order), ACCESS) == result


@pytest.mark.parametrize("auth", (p.Authentication.PASS, p.Authentication.UNKNOWN))
@pytest.mark.parametrize("familiar,released", tuple(product((False, True), repeat=2)))
def test_authenticated_familiar_or_released_never_implies_clearance(auth, familiar, released):
    evidence = p.Evidence(authentication=auth, familiar_sender=familiar, user_released=released)
    assert p.evaluate(BINDING, evidence, ACCESS).outcome is p.Outcome.INDETERMINATE
    dangerous = replace(evidence, findings=(p.Finding.COMPROMISED,))
    assert p.evaluate(BINDING, dangerous, ACCESS).outcome is p.Outcome.HIGH_RISK
    assert p.evaluate(BINDING, evidence, ACCESS).outcome is p.Outcome.INDETERMINATE


@pytest.mark.parametrize("claim", tuple(p.Claim))
def test_claims_never_become_independent_validation_or_execution(claim):
    result = p.evaluate(BINDING, p.Evidence(claims=(claim,), authentication=p.Authentication.PASS), ACCESS)
    expected = (p.Outcome.SUSPICIOUS if claim in (p.Claim.URGENT, p.Claim.IDENTITY_CHECK,
                 p.Claim.PAYMENT, p.Claim.INJECTION) else p.Outcome.INDETERMINATE)
    assert result.outcome is expected and not result.action_authority


@pytest.mark.parametrize("change", ({"source": p.Source.B}, {"item": p.Item.B},
                                   {"generation": 2}, {"policy": p.Policy.V2}))
def test_stale_or_foreign_evidence_never_transfers(change):
    old = p.Evidence(findings=(p.Finding.CHECKED_CLEAR,))
    current = replace(BINDING, **change)
    access = p.Access(source=current.source)
    assert p.evaluate(current, old, access).outcome is p.Outcome.INDETERMINATE
    assert p.evaluate(current, replace(old, findings=(p.Finding.IMPERSONATION,)), access).outcome is p.Outcome.INDETERMINATE
    # Reverted evidence at a new episode cannot inherit the old clearance.
    reverted = replace(BINDING, generation=3)
    assert p.evaluate(reverted, old, ACCESS).outcome is p.Outcome.INDETERMINATE


@pytest.mark.parametrize("permission", tuple(p.Permission))
@pytest.mark.parametrize("source", tuple(p.Source))
def test_access_before_policy_recovery_and_aggregate_projection(permission, source):
    access = p.Access(source, permission)
    allowed = permission is p.Permission.ALLOWED and source is p.Source.A
    moved = p.quarantine(HIGH, GATES, ACCESS)
    if allowed:
        assert p.evaluate(BINDING, p.Evidence(), access) is not None
    else:
        assert p.evaluate(BINDING, object(), access) is None
        assert p.quarantine(HIGH, object(), access) is None
        assert p.restore(moved, object(), access) is None
        assert e.metrics(e.CASES, access) == e.metrics((), access)
        assert e.recovery_metrics((moved,), access) == e.recovery_metrics((), access)


@pytest.mark.parametrize("outcome", tuple(p.Outcome))
@pytest.mark.parametrize("provider_state", tuple(p.ProviderState))
@pytest.mark.parametrize("retention", tuple(p.Retention))
@pytest.mark.parametrize("approval", tuple(p.Approval))
@pytest.mark.parametrize("observed", tuple(p.Observed))
def test_quarantine_simulation_gates_and_unknown_outcomes(outcome, provider_state, retention, approval, observed):
    assessment = replace(HIGH, outcome=outcome)
    conditions = p.Conditions(provider_state=provider_state, retention=retention, approval=approval, observed=observed)
    record = p.quarantine(assessment, conditions, ACCESS)
    ready = (outcome is p.Outcome.HIGH_RISK and provider_state is p.ProviderState.UNCHANGED
             and retention is p.Retention.VERIFIED and approval is p.Approval.EXPLICIT_SIMULATION)
    expected = (p.RecoveryStatus.BLOCKED if not ready else p.RecoveryStatus.QUARANTINED
                if observed is p.Observed.VERIFIED else p.RecoveryStatus.FAILED
                if observed is p.Observed.FAILED else p.RecoveryStatus.UNKNOWN)
    assert record.quarantine is expected
    assert record.assessment == assessment and not record.action_authority and not record.provider_write
    assert record.restoration is None


@pytest.mark.parametrize("provider_state", tuple(p.ProviderState))
@pytest.mark.parametrize("retention", tuple(p.Retention))
@pytest.mark.parametrize("approval", tuple(p.Approval))
@pytest.mark.parametrize("observed", tuple(p.Observed))
def test_restore_never_overwrites_later_changes_or_claims_unverified_success(provider_state, retention, approval, observed):
    moved = p.quarantine(HIGH, GATES, ACCESS)
    conditions = p.Conditions(provider_state=provider_state, retention=retention, approval=approval, observed=observed)
    record = p.restore(moved, conditions, ACCESS)
    ready = (provider_state is p.ProviderState.UNCHANGED and retention is p.Retention.VERIFIED
             and approval is p.Approval.EXPLICIT_SIMULATION)
    expected = (p.RecoveryStatus.BLOCKED if not ready else p.RecoveryStatus.RESTORED
                if observed is p.Observed.VERIFIED else p.RecoveryStatus.FAILED
                if observed is p.Observed.FAILED else p.RecoveryStatus.UNKNOWN)
    assert record.restoration is expected
    assert record.quarantine is p.RecoveryStatus.QUARANTINED
    assert moved.restoration is None and not record.action_authority and not record.provider_write


@pytest.mark.parametrize("observed", (p.Observed.FAILED, p.Observed.UNKNOWN))
def test_unverified_quarantine_cannot_justify_a_guessed_restore(observed):
    prior = p.quarantine(HIGH, replace(GATES, observed=observed), ACCESS)
    assert p.restore(prior, GATES, ACCESS).restoration is p.RecoveryStatus.BLOCKED


@pytest.mark.parametrize("observed", tuple(p.Observed))
def test_restore_result_cannot_be_blindly_replayed(observed):
    moved = p.quarantine(HIGH, GATES, ACCESS)
    prior = p.restore(moved, replace(GATES, observed=observed), ACCESS)
    assert p.restore(prior, GATES, ACCESS).restoration is p.RecoveryStatus.BLOCKED
    assert prior.restoration is not None


@pytest.mark.parametrize("change", ({"source": p.Source.B}, {"item": p.Item.B},
                                   {"generation": 2}, {"policy": p.Policy.V2}))
def test_exact_recovery_binding(change):
    conditions = replace(GATES, binding=replace(BINDING, **change))
    assert p.quarantine(HIGH, conditions, ACCESS).quarantine is p.RecoveryStatus.BLOCKED
    moved = p.quarantine(HIGH, GATES, ACCESS)
    assert p.restore(moved, conditions, ACCESS).restoration is p.RecoveryStatus.BLOCKED


def test_false_positive_recovery_is_not_trust_and_remains_immutable():
    sample = next(s for s in e.CASES if s.specimen is e.Specimen.FALSE_RISK_LEGIT)
    assert sample.truth is e.Truth.LEGITIMATE
    result = p.evaluate(BINDING, sample.evidence, ACCESS)
    moved = p.quarantine(result, GATES, ACCESS)
    restored = p.restore(moved, GATES, ACCESS)
    assert restored.restoration is p.RecoveryStatus.RESTORED
    assert p.evaluate(BINDING, replace(sample.evidence, user_released=True), ACCESS).outcome is p.Outcome.HIGH_RISK
    with pytest.raises(FrozenInstanceError):
        restored.quarantine = p.RecoveryStatus.FAILED


def test_exact_synthetic_metrics_include_failures_and_honest_denominators():
    result = e.metrics(e.CASES)
    assert result == e.metrics(e.CASES[::-1])
    assert result["count"] == 29 and result["labeled_count"] == 25 and result["unknown_truth_count"] == 4
    assert result["malicious_count"] == 14 and result["legitimate_count"] == 11
    assert result["outcomes"] == {"safe_to_route": 6, "suspicious": 6, "high_risk": 10, "indeterminate": 7}
    assert result["false_positives"] == 3 and result["false_positive_rate"] == 3 / 11
    assert result["false_negatives"] == 1 and result["false_negative_rate"] == 1 / 14
    assert result["abstentions"] == 7 and result["coverage"] == 22 / 29
    assert result["malicious_abstentions"] == 1 and result["legitimate_abstentions"] == 3
    assert result["important_count"] == 10 and result["important_misses"] == 6
    assert result["important_miss_rate"] == 0.6
    assert result["important_held"] == 3 and result["important_abstentions"] == 3


def test_empty_and_unknown_truth_metrics_are_null_not_false_perfection():
    for samples in ((), tuple(s for s in e.CASES if s.truth is e.Truth.UNKNOWN)):
        result = e.metrics(samples)
        for key in ("false_positive_rate", "false_negative_rate", "important_miss_rate"):
            assert result[key] is None
    assert e.metrics(())["coverage"] is None
    assert e.recovery_metrics(())["restore_success_rate"] is None


def test_labels_are_separate_from_policy_and_authorized_counts_are_filtered():
    sample = e.CASES[0]
    alternate = replace(sample, truth=e.Truth.LEGITIMATE, important=True)
    assert p.evaluate(BINDING, sample.evidence, ACCESS) == p.evaluate(BINDING, alternate.evidence, ACCESS)
    foreign = replace(e.CASES[1], evidence=replace(e.CASES[1].evidence,
                      binding=replace(BINDING, source=p.Source.B)))
    assert e.metrics((sample, foreign)) == e.metrics((sample,))


def test_exact_recovery_denominators_include_failed_unknown_and_blocked():
    moved = p.quarantine(HIGH, GATES, ACCESS)
    records = tuple(p.restore(moved, replace(GATES, observed=o), ACCESS) for o in p.Observed)
    blocked = p.restore(moved, replace(GATES, provider_state=p.ProviderState.USER_CHANGED), ACCESS)
    result = e.recovery_metrics(records + (blocked,))
    assert result["restore_attempts"] == 3 and result["restore_verified"] == 1
    assert result["restore_failed"] == result["restore_unknown"] == result["restore_blocked"] == 1
    assert result["restore_success_rate"] == 1 / 3


@pytest.mark.parametrize("source", tuple(p.Source))
@pytest.mark.parametrize("hidden_count", (1, 65, 129))
@pytest.mark.parametrize("reverse", (False, True))
def test_hidden_duplicates_and_over_limit_do_not_change_metrics(source, hidden_count, reverse):
    visible = replace(e.CASES[0], evidence=replace(e.CASES[0].evidence,
                      binding=replace(BINDING, source=source)))
    other = p.Source.B if source is p.Source.A else p.Source.A
    hidden = replace(visible, evidence=replace(visible.evidence,
                     binding=replace(BINDING, source=other)))
    access = p.Access(source)
    mixed = (visible,) + (hidden,) * hidden_count
    if reverse:
        mixed = mixed[::-1]
    assert e.metrics(mixed, access) == e.metrics((visible,), access)
    assert e.metrics((hidden,) * hidden_count, access) == e.metrics((), access)
    with pytest.raises(p.PolicyError):
        e.metrics(mixed + (visible,), access)


@pytest.mark.parametrize("source", tuple(p.Source))
@pytest.mark.parametrize("hidden_count", (1, 65, 129))
@pytest.mark.parametrize("reverse", (False, True))
def test_hidden_recovery_trials_do_not_change_validation_or_aggregates(source, hidden_count, reverse):
    visible = p.Recovery(replace(HIGH, binding=replace(BINDING, source=source)),
                         p.RecoveryStatus.QUARANTINED, p.RecoveryStatus.RESTORED)
    other = p.Source.B if source is p.Source.A else p.Source.A
    hidden = replace(visible, assessment=replace(visible.assessment,
                     binding=replace(BINDING, source=other)))
    access = p.Access(source)
    mixed = (visible,) * e.MAX_SAMPLES + (hidden,) * hidden_count
    if reverse:
        mixed = mixed[::-1]
    assert e.recovery_metrics(mixed, access) == e.recovery_metrics((visible,) * e.MAX_SAMPLES, access)
    assert e.recovery_metrics((hidden,) * hidden_count, access) == e.recovery_metrics((), access)
    with pytest.raises(p.PolicyError):
        e.recovery_metrics(mixed + (visible,), access)


@pytest.mark.parametrize("permission", (p.Permission.DENIED, p.Permission.UNKNOWN, p.Permission.REVOKED))
@pytest.mark.parametrize("source", tuple(p.Source))
def test_all_denied_ignores_duplicate_and_over_limit_collections(permission, source):
    access = p.Access(source, permission)
    foreign = replace(e.CASES[0], evidence=replace(e.CASES[0].evidence,
                      binding=replace(BINDING, source=p.Source.B)))
    assert e.metrics((e.CASES[0], foreign) * 100, access) == e.metrics((), access)
    moved = p.quarantine(HIGH, GATES, ACCESS)
    foreign_move = replace(moved, assessment=replace(HIGH, binding=replace(BINDING, source=p.Source.B)))
    assert e.recovery_metrics((moved, foreign_move) * 100, access) == e.recovery_metrics((), access)


@pytest.mark.parametrize("function", (e.metrics, e.recovery_metrics))
@pytest.mark.parametrize("permission", tuple(p.Permission))
def test_aggregate_envelope_types_still_fail_closed(function, permission):
    access = p.Access(permission=permission)
    for records in ([], (None,), (object(),)):
        with pytest.raises(p.PolicyError):
            function(records, access)
    with pytest.raises(p.PolicyError):
        function((), None)


@pytest.mark.parametrize("sample", e.CASES, ids=lambda s: s.specimen.value)
def test_stage_a_interoperability_only_in_tests_no_authority_or_unsafe_offer(sample):
    # There is no runtime bridge to Stage A: this explicitly synthetic adapter is test-only.
    result = p.evaluate(sample.evidence.binding, sample.evidence, ACCESS)
    mapping = {p.Outcome.SAFE_TO_ROUTE: a.Safety.SAFE_TO_ROUTE, p.Outcome.SUSPICIOUS: a.Safety.SUSPICIOUS,
               p.Outcome.HIGH_RISK: a.Safety.HIGH_RISK, p.Outcome.INDETERMINATE: a.Safety.UNKNOWN}
    business = a.Business(promotion=p.Claim.PROMOTION in sample.evidence.claims,
                          importance=a.Importance.IMPORTANT if sample.important else a.Importance.UNKNOWN)
    current = a.reassess(a.Case(a.Snapshot(business=business)), mapping[result.outcome], a.Policy.V1)
    projection = a.route(current, a.Access(), a.Intent.OFFER_QUERY)
    assert projection.authority is a.Authority.NONE
    assert not projection.creates_task and not projection.provider_write and not projection.proactive_alert
    if result.outcome is not p.Outcome.SAFE_TO_ROUTE:
        assert not projection.offer_visible
        assert projection.destination in (a.Destination.SECURITY_HOLD, a.Destination.UNASSESSED)
    elif sample.important:
        assert projection.destination is a.Destination.PENDING
    assert a.route(current, a.Access(permission=a.Permission.REVOKED)) is None


@pytest.mark.parametrize("factory", (
    lambda: p.Binding(generation=True), lambda: p.Binding(generation=0), lambda: p.Binding(generation=1001),
    lambda: p.Binding(source="private source"), lambda: p.Access(permission=True),
    lambda: p.Evidence(claims=[p.Claim.URGENT]), lambda: p.Evidence(claims=(p.Claim.URGENT,) * 2),
    lambda: p.Evidence(findings=("private URL",)), lambda: p.Evidence(authentication="pass"),
    lambda: p.Evidence(user_released=1), lambda: p.Evidence(binding=None),
    lambda: p.Assessment(None, p.Outcome.HIGH_RISK, p.Reason.CONCERN),
    lambda: p.Conditions(approval="consent"), lambda: p.Conditions(observed="success"),
    lambda: e.Sample(e.Specimen.SCHOOL_LEGIT, p.Evidence(), e.Truth.UNKNOWN, True),
    lambda: e.metrics(e.CASES + (e.CASES[0],)), lambda: e.metrics([]),
    lambda: e.metrics((), None), lambda: e.recovery_metrics((None,)),
    lambda: p.Recovery(HIGH, p.RecoveryStatus.FAILED, p.RecoveryStatus.RESTORED),
    lambda: p.Recovery(replace(HIGH, outcome=p.Outcome.SAFE_TO_ROUTE), p.RecoveryStatus.QUARANTINED),
    lambda: e.metrics(e.CASES * 3), lambda: e.recovery_metrics((p.Recovery(HIGH, p.RecoveryStatus.BLOCKED),) * 65),
))
def test_strict_bounded_fields_generic_errors_no_logging(factory, caplog):
    with pytest.raises(p.PolicyError, match="^Synthetic phishing evaluation rejected$"):
        factory()
    assert not caplog.records


def test_isolation_no_truth_in_policy_no_io_no_production_wiring(monkeypatch):
    root = Path(__file__).parents[1]
    policy = root / "src/family_os/_synthetic_phishing_policy.py"
    tree = ast.parse(policy.read_text())
    imports = [node.module if isinstance(node, ast.ImportFrom) else alias.name
               for node in ast.walk(tree) if isinstance(node, (ast.ImportFrom, ast.Import))
               for alias in (node.names if isinstance(node, ast.Import) else (None,))]
    assert set(imports) == {"dataclasses", "enum"}
    assert "Truth" not in policy.read_text() and "Specimen" not in policy.read_text()
    assert all(field.name not in ("subject", "sender", "payload", "url", "truth", "important")
               for field in fields(p.Evidence))
    for production in (root / "src/family_os").rglob("*.py"):
        if production.name.startswith("_synthetic_phishing_"):
            continue
        assert "_synthetic_phishing" not in production.read_text()
    import builtins
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected I/O")
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert e.metrics(e.CASES)["count"] == 29
    assert p.restore(p.quarantine(HIGH, GATES, ACCESS), GATES, ACCESS).restoration is p.RecoveryStatus.RESTORED
