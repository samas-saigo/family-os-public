"""New Stage B corpus/labels and aggregate evaluation, never policy input labels."""
from dataclasses import dataclass
from enum import Enum

from . import _synthetic_phishing_policy as p

CORPUS_VERSION = "synthetic-phishing-corpus-v1"
MAX_SAMPLES = 64


class Truth(Enum):
    MALICIOUS = "synthetic-malicious"
    LEGITIMATE = "synthetic-legitimate"
    UNKNOWN = "synthetic-truth-unknown"


class Specimen(Enum):
    SCHOOL_SPOOF = "invented-school-dues-impersonation"
    BANK_SPOOF = "invented-bank-identity-impersonation"
    HEALTH_SPOOF = "invented-clinic-payment-impersonation"
    AUTHENTICATED_ATTACK = "authenticated-invented-payment-lure"
    COMPROMISED_SCHOOL = "compromised-invented-school-mailbox"
    COMPROMISED_CLINIC = "compromised-invented-clinic-mailbox"
    URGENCY_ATTACK = "invented-urgent-transfer-claim"
    IDENTITY_ATTACK = "invented-identity-check-claim"
    PROMOTIONAL_ATTACK = "invented-reward-credential-lure"
    MIXED_ATTACK = "invented-service-update-and-malicious-offer"
    INJECTION_ATTACK = "invented-policy-override-instruction"
    RELEASED_ATTACK = "previously-released-invented-malicious-notice"
    MISSED_ATTACK = "invented-attack-with-false-clear-evidence"
    MISSING_ATTACK = "invented-attack-with-missing-evidence"
    SCHOOL_LEGIT = "invented-school-permission-notice"
    BANK_LEGIT = "invented-bank-service-notice"
    HEALTH_LEGIT = "invented-clinic-appointment-notice"
    PROMO_LEGIT = "invented-benign-stationery-promotion"
    MIXED_LEGIT = "invented-service-notice-and-benign-stationery-ad"
    URGENT_LEGIT = "invented-legitimate-urgent-school-notice"
    FALSE_RISK_LEGIT = "invented-legitimate-clinic-falsely-flagged"
    AUTH_FAIL_LEGIT = "invented-legitimate-bank-with-auth-failure"
    CONFLICT_LEGIT = "invented-school-with-conflicting-evidence"
    STALE_LEGIT = "invented-clinic-with-stale-evidence"
    UNAVAILABLE_LEGIT = "invented-important-notice-during-outage"
    FAMILIAR_UNKNOWN = "familiar-invented-sender-without-validation"
    AUTH_UNKNOWN = "authenticated-invented-sender-without-validation"
    RELEASE_UNKNOWN = "released-invented-sender-without-validation"
    INJECTION_UNKNOWN = "invented-instruction-with-unknown-truth"


@dataclass(frozen=True)
class Sample:
    specimen: Specimen
    evidence: p.Evidence
    truth: Truth
    important: bool = False

    def __post_init__(self):
        p._enum(self.specimen, Specimen)
        if type(self.evidence) is not p.Evidence:
            raise p.PolicyError()
        p._enum(self.truth, Truth)
        p._bool(self.important)
        if self.important and self.truth is not Truth.LEGITIMATE:
            raise p.PolicyError()


# Ground truth is authored independently of the evaluator: inaccurate or incomplete
# supplied findings deliberately disagree with truth in false-positive/negative probes.
# No actual URL, header, instruction text or attachment is represented or inspected.
CASES = (
    Sample(Specimen.SCHOOL_SPOOF, p.Evidence(claims=(p.Claim.SCHOOL, p.Claim.PAYMENT),
           findings=(p.Finding.IMPERSONATION,)), Truth.MALICIOUS),
    Sample(Specimen.BANK_SPOOF, p.Evidence(claims=(p.Claim.BANK, p.Claim.IDENTITY_CHECK),
           findings=(p.Finding.IMPERSONATION,)), Truth.MALICIOUS),
    Sample(Specimen.HEALTH_SPOOF, p.Evidence(claims=(p.Claim.HEALTHCARE, p.Claim.PAYMENT),
           findings=(p.Finding.IMPERSONATION,)), Truth.MALICIOUS),
    Sample(Specimen.AUTHENTICATED_ATTACK, p.Evidence(authentication=p.Authentication.PASS,
           findings=(p.Finding.MALICIOUS_DESTINATION,)), Truth.MALICIOUS),
    Sample(Specimen.COMPROMISED_SCHOOL, p.Evidence(claims=(p.Claim.SCHOOL,), familiar_sender=True,
           authentication=p.Authentication.PASS, findings=(p.Finding.COMPROMISED,)), Truth.MALICIOUS),
    Sample(Specimen.COMPROMISED_CLINIC, p.Evidence(claims=(p.Claim.HEALTHCARE,), familiar_sender=True,
           findings=(p.Finding.COMPROMISED,)), Truth.MALICIOUS),
    Sample(Specimen.URGENCY_ATTACK, p.Evidence(claims=(p.Claim.URGENT, p.Claim.PAYMENT)), Truth.MALICIOUS),
    Sample(Specimen.IDENTITY_ATTACK, p.Evidence(claims=(p.Claim.IDENTITY_CHECK,)), Truth.MALICIOUS),
    Sample(Specimen.PROMOTIONAL_ATTACK, p.Evidence(claims=(p.Claim.PROMOTION, p.Claim.IDENTITY_CHECK),
           findings=(p.Finding.MALICIOUS_DESTINATION,)), Truth.MALICIOUS),
    Sample(Specimen.MIXED_ATTACK, p.Evidence(claims=(p.Claim.PROMOTION, p.Claim.BANK, p.Claim.PAYMENT),
           findings=(p.Finding.MALICIOUS_DESTINATION,)), Truth.MALICIOUS),
    Sample(Specimen.INJECTION_ATTACK, p.Evidence(claims=(p.Claim.INJECTION,)), Truth.MALICIOUS),
    Sample(Specimen.RELEASED_ATTACK, p.Evidence(user_released=True, familiar_sender=True,
           findings=(p.Finding.COMPROMISED,)), Truth.MALICIOUS),
    Sample(Specimen.MISSED_ATTACK, p.Evidence(authentication=p.Authentication.PASS,
           findings=(p.Finding.CHECKED_CLEAR,)), Truth.MALICIOUS),
    Sample(Specimen.MISSING_ATTACK, p.Evidence(state=p.EvidenceState.MISSING), Truth.MALICIOUS),
    Sample(Specimen.SCHOOL_LEGIT, p.Evidence(claims=(p.Claim.SCHOOL,),
           findings=(p.Finding.CHECKED_CLEAR,)), Truth.LEGITIMATE, True),
    Sample(Specimen.BANK_LEGIT, p.Evidence(claims=(p.Claim.BANK,),
           findings=(p.Finding.CHECKED_CLEAR,)), Truth.LEGITIMATE, True),
    Sample(Specimen.HEALTH_LEGIT, p.Evidence(claims=(p.Claim.HEALTHCARE,),
           findings=(p.Finding.CHECKED_CLEAR,)), Truth.LEGITIMATE, True),
    Sample(Specimen.PROMO_LEGIT, p.Evidence(claims=(p.Claim.PROMOTION,),
           findings=(p.Finding.CHECKED_CLEAR,)), Truth.LEGITIMATE),
    Sample(Specimen.MIXED_LEGIT, p.Evidence(claims=(p.Claim.SCHOOL, p.Claim.PROMOTION),
           findings=(p.Finding.CHECKED_CLEAR,)), Truth.LEGITIMATE, True),
    Sample(Specimen.URGENT_LEGIT, p.Evidence(claims=(p.Claim.SCHOOL, p.Claim.URGENT)), Truth.LEGITIMATE, True),
    Sample(Specimen.FALSE_RISK_LEGIT, p.Evidence(claims=(p.Claim.HEALTHCARE,),
           findings=(p.Finding.IMPERSONATION,)), Truth.LEGITIMATE, True),
    Sample(Specimen.AUTH_FAIL_LEGIT, p.Evidence(claims=(p.Claim.BANK,),
           authentication=p.Authentication.FAIL), Truth.LEGITIMATE, True),
    Sample(Specimen.CONFLICT_LEGIT, p.Evidence(findings=(p.Finding.CHECKED_CLEAR, p.Finding.ANOMALY)),
           Truth.LEGITIMATE, True),
    Sample(Specimen.STALE_LEGIT, p.Evidence(state=p.EvidenceState.STALE,
           findings=(p.Finding.CHECKED_CLEAR,)), Truth.LEGITIMATE, True),
    Sample(Specimen.UNAVAILABLE_LEGIT, p.Evidence(state=p.EvidenceState.UNAVAILABLE), Truth.LEGITIMATE, True),
    Sample(Specimen.FAMILIAR_UNKNOWN, p.Evidence(familiar_sender=True), Truth.UNKNOWN),
    Sample(Specimen.AUTH_UNKNOWN, p.Evidence(authentication=p.Authentication.PASS), Truth.UNKNOWN),
    Sample(Specimen.RELEASE_UNKNOWN, p.Evidence(user_released=True), Truth.UNKNOWN),
    Sample(Specimen.INJECTION_UNKNOWN, p.Evidence(claims=(p.Claim.INJECTION,)), Truth.UNKNOWN),
)


def _rate(count, denominator):
    return count / denominator if denominator else None


def _authorized(records, access, record_type):
    # Validate the caller's envelope, then filter before collection constraints.
    # Scan the finite tuple once; retain at most MAX_SAMPLES authorized values.
    if type(records) is not tuple or type(access) is not p.Access:
        raise p.PolicyError()
    visible = []
    for record in records:
        if type(record) is not record_type:
            raise p.PolicyError()
        binding = (record.evidence.binding if record_type is Sample
                   else record.assessment.binding)
        if p._allowed(binding, access):
            if len(visible) == MAX_SAMPLES:
                raise p.PolicyError()
            visible.append(record)
    return tuple(visible)


def metrics(samples: tuple[Sample, ...], access: p.Access = p.Access()):
    samples = _authorized(samples, access, Sample)
    if len({s.specimen for s in samples}) != len(samples):
        raise p.PolicyError()
    rows = []
    for sample in samples:
        # Policy never receives a truth label, importance label or specimen identifier.
        result = p.evaluate(sample.evidence.binding, sample.evidence, access)
        if result is not None:
            rows.append((sample, result.outcome))
    malicious = [o for s, o in rows if s.truth is Truth.MALICIOUS]
    legitimate = [o for s, o in rows if s.truth is Truth.LEGITIMATE]
    important = [o for s, o in rows if s.important]
    flagged = (p.Outcome.HIGH_RISK, p.Outcome.SUSPICIOUS)
    fp = sum(o in flagged for o in legitimate)
    fn = malicious.count(p.Outcome.SAFE_TO_ROUTE)
    abstentions = sum(o is p.Outcome.INDETERMINATE for _, o in rows)
    misses = sum(o is not p.Outcome.SAFE_TO_ROUTE for o in important)
    # Authorized cases only: no withheld count, existence hints or source identifiers.
    return dict(synthetic_only=True, policy_version=p.POLICY_VERSION, corpus_version=CORPUS_VERSION,
                count=len(rows), labeled_count=len(malicious) + len(legitimate),
                outcomes={o.name.lower(): sum(prediction is o for _, prediction in rows) for o in p.Outcome},
                unknown_truth_count=sum(s.truth is Truth.UNKNOWN for s, _ in rows),
                malicious_count=len(malicious), legitimate_count=len(legitimate),
                flagged_count=sum(o in flagged for _, o in rows), abstentions=abstentions,
                coverage=_rate(len(rows) - abstentions, len(rows)),
                false_positives=fp, false_positive_rate=_rate(fp, len(legitimate)),
                false_negatives=fn, false_negative_rate=_rate(fn, len(malicious)),
                malicious_abstentions=malicious.count(p.Outcome.INDETERMINATE),
                legitimate_abstentions=legitimate.count(p.Outcome.INDETERMINATE),
                important_count=len(important), important_misses=misses,
                important_miss_rate=_rate(misses, len(important)),
                important_held=sum(o in flagged for o in important),
                important_abstentions=important.count(p.Outcome.INDETERMINATE))


def recovery_metrics(records: tuple[p.Recovery, ...], access: p.Access = p.Access()):
    records = _authorized(records, access, p.Recovery)
    attempted = [r for r in records if r.restoration is not None and r.restoration is not p.RecoveryStatus.BLOCKED]
    restored = sum(r.restoration is p.RecoveryStatus.RESTORED for r in attempted)
    return dict(synthetic_only=True, count=len(records),
                quarantine_verified=sum(r.quarantine is p.RecoveryStatus.QUARANTINED for r in records),
                quarantine_blocked=sum(r.quarantine is p.RecoveryStatus.BLOCKED for r in records),
                quarantine_failed=sum(r.quarantine is p.RecoveryStatus.FAILED for r in records),
                quarantine_unknown=sum(r.quarantine is p.RecoveryStatus.UNKNOWN for r in records),
                restore_attempts=len(attempted), restore_verified=restored,
                restore_failed=sum(r.restoration is p.RecoveryStatus.FAILED for r in records),
                restore_unknown=sum(r.restoration is p.RecoveryStatus.UNKNOWN for r in records),
                restore_blocked=sum(r.restoration is p.RecoveryStatus.BLOCKED for r in records),
                restore_success_rate=_rate(restored, len(attempted)))
