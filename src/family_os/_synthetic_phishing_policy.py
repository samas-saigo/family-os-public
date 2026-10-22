"""Stage B: enum-only synthetic policy and recovery probes. No detector or I/O."""
from dataclasses import dataclass
from enum import Enum

POLICY_VERSION = "synthetic-phishing-policy-v1"


class Source(Enum):
    A = "synthetic-mail-source-A"
    B = "synthetic-mail-source-B"


class Item(Enum):
    A = "synthetic-mail-item-A"
    B = "synthetic-mail-item-B"


class Policy(Enum):
    V1 = "synthetic-policy-v1"
    V2 = "synthetic-policy-v2-probe"


class Permission(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"
    REVOKED = "revoked"


class Claim(Enum):
    SCHOOL = "claims-school"
    BANK = "claims-bank"
    HEALTHCARE = "claims-healthcare"
    URGENT = "claims-urgency"
    IDENTITY_CHECK = "requests-identity-check"
    PAYMENT = "requests-payment"
    PROMOTION = "advertising"
    INJECTION = "untrusted-policy-instruction"


class Authentication(Enum):
    PASS = "synthetic-SPF-DKIM-DMARC-pass-not-benignity"
    FAIL = "synthetic-authentication-failure"
    UNKNOWN = "unknown"


class Finding(Enum):
    CHECKED_CLEAR = "independent-check-no-detected-risk-not-guarantee"
    IMPERSONATION = "independently-validated-impersonation"
    COMPROMISED = "independently-validated-compromised-sender"
    MALICIOUS_DESTINATION = "independently-validated-malicious-destination-no-fetch"
    ANOMALY = "independent-unresolved-anomaly"


class EvidenceState(Enum):
    CURRENT = "current"
    MISSING = "missing"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    CONFLICTING = "conflicting"


class Outcome(Enum):
    SAFE_TO_ROUTE = "safe-to-route-not-guarantee"
    SUSPICIOUS = "suspicious"
    HIGH_RISK = "synthetic-high-risk"
    INDETERMINATE = "indeterminate"


class Reason(Enum):
    INSUFFICIENT = "insufficient-current-evidence"
    CONFLICT = "conflicting-independent-findings"
    VALIDATED_RISK = "independent-risk-finding"
    CONCERN = "unresolved-concern-not-proof"
    CHECKED = "independent-clear-check-not-guarantee"


class PolicyError(ValueError):
    def __init__(self):
        super().__init__("Synthetic phishing evaluation rejected")


def _enum(value, kind):
    if type(value) is not kind:
        raise PolicyError()


def _bool(value):
    if type(value) is not bool:
        raise PolicyError()


def _tuple(value, kind):
    if (type(value) is not tuple or len(value) > len(kind)
            or any(type(v) is not kind for v in value) or len(set(value)) != len(value)):
        raise PolicyError()


@dataclass(frozen=True)
class Binding:
    source: Source = Source.A
    item: Item = Item.A
    generation: int = 1
    policy: Policy = Policy.V1

    def __post_init__(self):
        _enum(self.source, Source)
        _enum(self.item, Item)
        _enum(self.policy, Policy)
        if type(self.generation) is not int or not 1 <= self.generation <= 1000:
            raise PolicyError()


@dataclass(frozen=True)
class Access:
    source: Source = Source.A
    permission: Permission = Permission.ALLOWED

    def __post_init__(self):
        _enum(self.source, Source)
        _enum(self.permission, Permission)


@dataclass(frozen=True)
class Evidence:
    binding: Binding = Binding()
    state: EvidenceState = EvidenceState.CURRENT
    claims: tuple[Claim, ...] = ()
    authentication: Authentication = Authentication.UNKNOWN
    familiar_sender: bool = False
    user_released: bool = False
    findings: tuple[Finding, ...] = ()

    def __post_init__(self):
        if type(self.binding) is not Binding:
            raise PolicyError()
        _enum(self.state, EvidenceState)
        _tuple(self.claims, Claim)
        _enum(self.authentication, Authentication)
        _bool(self.familiar_sender)
        _bool(self.user_released)
        _tuple(self.findings, Finding)


@dataclass(frozen=True)
class Assessment:
    binding: Binding
    outcome: Outcome
    reason: Reason

    def __post_init__(self):
        if type(self.binding) is not Binding:
            raise PolicyError()
        _enum(self.outcome, Outcome)
        _enum(self.reason, Reason)

    @property
    def action_authority(self):
        return False


def _allowed(binding, access):
    if type(binding) is not Binding or type(access) is not Access:
        raise PolicyError()
    return access.permission is Permission.ALLOWED and access.source is binding.source


def evaluate(binding: Binding, evidence: Evidence, access: Access) -> Assessment | None:
    if not _allowed(binding, access):
        return None
    if type(evidence) is not Evidence:
        raise PolicyError()
    findings = set(evidence.findings)
    risk = {Finding.IMPERSONATION, Finding.COMPROMISED, Finding.MALICIOUS_DESTINATION}
    if evidence.binding != binding or evidence.state is not EvidenceState.CURRENT:
        outcome, reason = Outcome.INDETERMINATE, Reason.INSUFFICIENT
    elif Finding.CHECKED_CLEAR in findings and len(findings) > 1:
        outcome, reason = Outcome.INDETERMINATE, Reason.CONFLICT
    elif findings & risk:
        outcome, reason = Outcome.HIGH_RISK, Reason.VALIDATED_RISK
    elif Finding.ANOMALY in findings or evidence.authentication is Authentication.FAIL:
        outcome, reason = Outcome.SUSPICIOUS, Reason.CONCERN
    elif Finding.CHECKED_CLEAR in findings:
        outcome, reason = Outcome.SAFE_TO_ROUTE, Reason.CHECKED
    elif set(evidence.claims) & {Claim.URGENT, Claim.IDENTITY_CHECK, Claim.PAYMENT, Claim.INJECTION}:
        outcome, reason = Outcome.SUSPICIOUS, Reason.CONCERN
    else:
        outcome, reason = Outcome.INDETERMINATE, Reason.INSUFFICIENT
    return Assessment(binding, outcome, reason)


class ProviderState(Enum):
    UNCHANGED = "synthetic-state-unchanged"
    USER_CHANGED = "synthetic-later-user-change"
    UNKNOWN = "synthetic-state-unknown"


class Retention(Enum):
    VERIFIED = "synthetic-retention-and-recovery-records-verified"
    UNCERTAIN = "synthetic-retention-or-records-uncertain"


class Approval(Enum):
    NONE = "none"
    EXPLICIT_SIMULATION = "explicit-simulation-not-real-consent"


class Observed(Enum):
    VERIFIED = "synthetic-outcome-verified"
    FAILED = "synthetic-operation-failed"
    UNKNOWN = "synthetic-outcome-unknown"


class RecoveryStatus(Enum):
    BLOCKED = "blocked-no-simulated-dispatch"
    QUARANTINED = "simulated-verified-quarantine"
    RESTORED = "simulated-verified-restore"
    FAILED = "simulated-failure"
    UNKNOWN = "simulated-unknown-needs-reconciliation"


@dataclass(frozen=True)
class Conditions:
    binding: Binding = Binding()
    provider_state: ProviderState = ProviderState.UNCHANGED
    retention: Retention = Retention.VERIFIED
    approval: Approval = Approval.NONE
    observed: Observed = Observed.UNKNOWN

    def __post_init__(self):
        if type(self.binding) is not Binding:
            raise PolicyError()
        _enum(self.provider_state, ProviderState)
        _enum(self.retention, Retention)
        _enum(self.approval, Approval)
        _enum(self.observed, Observed)


@dataclass(frozen=True)
class Recovery:
    assessment: Assessment
    quarantine: RecoveryStatus
    restoration: RecoveryStatus | None = None

    def __post_init__(self):
        if type(self.assessment) is not Assessment:
            raise PolicyError()
        _enum(self.quarantine, RecoveryStatus)
        if self.quarantine is RecoveryStatus.RESTORED:
            raise PolicyError()
        if self.restoration is not None:
            _enum(self.restoration, RecoveryStatus)
            if self.restoration is RecoveryStatus.QUARANTINED:
                raise PolicyError()
            if (self.quarantine is not RecoveryStatus.QUARANTINED
                    and self.restoration is not RecoveryStatus.BLOCKED):
                raise PolicyError()
        if self.assessment.outcome is not Outcome.HIGH_RISK and self.quarantine is not RecoveryStatus.BLOCKED:
            raise PolicyError()

    @property
    def action_authority(self):
        return False

    @property
    def provider_write(self):
        return False


def _ready(assessment, conditions):
    if type(conditions) is not Conditions:
        raise PolicyError()
    return (conditions.binding == assessment.binding
            and conditions.provider_state is ProviderState.UNCHANGED
            and conditions.retention is Retention.VERIFIED
            and conditions.approval is Approval.EXPLICIT_SIMULATION)


def _observed(observed, success):
    return (success if observed is Observed.VERIFIED else RecoveryStatus.FAILED
            if observed is Observed.FAILED else RecoveryStatus.UNKNOWN)


def quarantine(assessment: Assessment, conditions: Conditions, access: Access) -> Recovery | None:
    if type(assessment) is not Assessment:
        raise PolicyError()
    if not _allowed(assessment.binding, access):
        return None
    status = (RecoveryStatus.BLOCKED
              if not _ready(assessment, conditions) or assessment.outcome is not Outcome.HIGH_RISK
              else _observed(conditions.observed, RecoveryStatus.QUARANTINED))
    return Recovery(assessment, status)


def restore(previous: Recovery, conditions: Conditions, access: Access) -> Recovery | None:
    if type(previous) is not Recovery:
        raise PolicyError()
    if not _allowed(previous.assessment.binding, access):
        return None
    # An unknown move cannot justify a guessed undo. Later user changes are never
    # overwritten; a new explicit recovery contract would be required outside Stage B.
    status = (RecoveryStatus.BLOCKED
              if not _ready(previous.assessment, conditions)
              or previous.quarantine is not RecoveryStatus.QUARANTINED
              or previous.restoration is not None
              else _observed(conditions.observed, RecoveryStatus.RESTORED))
    return Recovery(previous.assessment, previous.quarantine, status)
