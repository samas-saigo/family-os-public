"""Stage A only: pure enum-only routing probes, never production authority or I/O."""
from dataclasses import dataclass, replace
from enum import Enum


CONTRACT_VERSION = "synthetic-routing-v2"
MAX_GENERATION = 1000
MAX_DECISIONS = 32


class Household(Enum):
    A = "synthetic-household-A"
    B = "synthetic-household-B"


class Source(Enum):
    A = "synthetic-source-A"
    B = "synthetic-source-B"


class Item(Enum):
    A = "synthetic-item-A"
    B = "synthetic-item-B"


class Evidence(Enum):
    ORIGINAL = "original-synthetic-evidence"
    CHANGED = "changed-synthetic-evidence"


class Policy(Enum):
    V1 = "synthetic-policy-v1"
    V2 = "synthetic-policy-v2"


class Permission(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"
    REVOKED = "revoked"


class Safety(Enum):
    SAFE_TO_ROUTE = "adequate-evidence-no-detected-risk-not-a-guarantee"
    SUSPICIOUS = "suspicious"
    HIGH_RISK = "synthetic-high-risk"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    STALE = "stale"


class ActionEvidence(Enum):
    NONE = "none"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"


class Importance(Enum):
    """Independent non-promotional service importance, never advertising urgency."""
    IMPORTANT = "important"
    NOT_IMPORTANT = "not-important"
    UNKNOWN = "unknown"


class Expiry(Enum):
    NONE = "none"
    UPCOMING = "upcoming"
    EXPIRED = "expired"


class Intent(Enum):
    INSPECT = "inspect"
    OFFER_QUERY = "explicit-offer-query"


class Authority(Enum):
    NONE = "none"
    REVIEW_CONFIRMED = "review-confirmed-not-task-acceptance"
    SIMULATED_ACCEPTANCE = "synthetic-non-authoritative-acceptance"


class Confirmation(Enum):
    UNCONFIRMED = "unconfirmed"
    EXPLICIT = "explicit-synthetic-confirmation"


class Destination(Enum):
    SECURITY_HOLD = "synthetic-view-hold-not-provider-quarantine"
    UNASSESSED = "unassessed-abstention"
    PENDING = "pending-confirmation"
    PROMOTIONS = "quiet-promotions"
    INFORMATION = "quiet-information"
    ABSTAIN = "unresolved-abstention"
    SIMULATED_ACCEPTED = "simulated-accepted-not-a-task"


class RoutingError(ValueError):
    def __init__(self):
        super().__init__("Synthetic routing contract rejected")


def _enum(value, kind):
    if type(value) is not kind:
        raise RoutingError()


def _bool(value):
    if type(value) is not bool:
        raise RoutingError()


@dataclass(frozen=True)
class Business:
    promotion: bool = False
    action: ActionEvidence = ActionEvidence.NONE
    importance: Importance = Importance.UNKNOWN
    informational: bool = False
    expiry: Expiry = Expiry.NONE

    def __post_init__(self):
        _bool(self.promotion)
        _bool(self.informational)
        _enum(self.action, ActionEvidence)
        _enum(self.importance, Importance)
        _enum(self.expiry, Expiry)


@dataclass(frozen=True)
class Snapshot:
    household: Household = Household.A
    source: Source = Source.A
    item: Item = Item.A
    generation: int = 1
    evidence: Evidence = Evidence.ORIGINAL
    business: Business = Business()

    def __post_init__(self):
        for value, kind in ((self.household, Household), (self.source, Source),
                            (self.item, Item), (self.evidence, Evidence)):
            _enum(value, kind)
        if (type(self.generation) is not int or not 1 <= self.generation <= MAX_GENERATION
                or type(self.business) is not Business):
            raise RoutingError()


@dataclass(frozen=True)
class Access:
    """Declared test grant, not authentication or a production permission check."""
    household: Household = Household.A
    source: Source = Source.A
    permission: Permission = Permission.ALLOWED

    def __post_init__(self):
        _enum(self.household, Household)
        _enum(self.source, Source)
        _enum(self.permission, Permission)


@dataclass(frozen=True)
class Assessment:
    snapshot: Snapshot
    policy: Policy
    safety: Safety

    def __post_init__(self):
        if type(self.snapshot) is not Snapshot:
            raise RoutingError()
        _enum(self.policy, Policy)
        _enum(self.safety, Safety)


@dataclass(frozen=True)
class Decision:
    """Fixture/history annotation only: no receipt, task, approval or execution right."""
    assessment: Assessment
    authority: Authority

    def __post_init__(self):
        if type(self.assessment) is not Assessment:
            raise RoutingError()
        _enum(self.authority, Authority)
        if (self.authority is Authority.NONE
                or self.assessment.safety is not Safety.SAFE_TO_ROUTE
                or self.assessment.snapshot.business.action is not ActionEvidence.SUPPORTED):
            raise RoutingError()


@dataclass(frozen=True)
class Case:
    snapshot: Snapshot
    policy: Policy = Policy.V1
    assessment: Assessment | None = None
    history: tuple[Decision, ...] = ()

    def __post_init__(self):
        if type(self.snapshot) is not Snapshot:
            raise RoutingError()
        _enum(self.policy, Policy)
        if self.assessment is not None and type(self.assessment) is not Assessment:
            raise RoutingError()
        if (type(self.history) is not tuple or len(self.history) > MAX_DECISIONS
                or any(type(d) is not Decision for d in self.history)):
            raise RoutingError()


@dataclass(frozen=True)
class Projection:
    snapshot: Snapshot
    safety: Safety
    business: Business
    authority: Authority
    destination: Destination
    offer_visible: bool
    historical_acceptance: bool
    acceptance_requires_revalidation: bool

    # There is no notification, task or executor in this contract. These invariants
    # cannot be switched on through constructor arguments or fixture evidence.
    @property
    def proactive_alert(self):
        return False

    @property
    def creates_task(self):
        return False

    @property
    def provider_write(self):
        return False


def _allowed(case, access):
    if type(case) is not Case or type(access) is not Access:
        raise RoutingError()
    return (access.permission is Permission.ALLOWED
            and access.household is case.snapshot.household
            and access.source is case.snapshot.source)


def route(case: Case, access: Access, intent: Intent = Intent.INSPECT) -> Projection | None:
    """None for all withheld items: no per-item reason, identity, counter or placeholder."""
    if not _allowed(case, access):
        return None
    _enum(intent, Intent)
    assessment = case.assessment
    safety = Safety.UNKNOWN if assessment is None else assessment.safety
    if assessment is not None and (assessment.snapshot != case.snapshot
                                   or assessment.policy is not case.policy):
        safety = Safety.STALE
    # Identity + monotonic generation + exact fields + assessment/policy all bind.
    # A revert uses a new generation and never makes an old decision current again.
    current = tuple(d for d in case.history if d.assessment == assessment
                    and d.assessment.snapshot == case.snapshot
                    and d.assessment.policy is case.policy)
    # Review agreement neither grants nor withdraws separate acceptance. Acceptance
    # persists only within this exact assessment; new episodes still require review.
    authority = (Authority.SIMULATED_ACCEPTANCE
                 if any(d.authority is Authority.SIMULATED_ACCEPTANCE for d in current)
                 else Authority.REVIEW_CONFIRMED if current else Authority.NONE)
    historical = any(d.authority is Authority.SIMULATED_ACCEPTANCE for d in case.history
                     if (d.assessment.snapshot.household, d.assessment.snapshot.source,
                         d.assessment.snapshot.item) ==
                        (case.snapshot.household, case.snapshot.source, case.snapshot.item))
    if safety is not Safety.SAFE_TO_ROUTE:
        authority = Authority.NONE
    business = case.snapshot.business
    if safety in (Safety.SUSPICIOUS, Safety.HIGH_RISK):
        destination = Destination.SECURITY_HOLD
    elif safety is not Safety.SAFE_TO_ROUTE:
        destination = Destination.UNASSESSED
    elif business.action is ActionEvidence.SUPPORTED:
        destination = (Destination.SIMULATED_ACCEPTED
                       if authority is Authority.SIMULATED_ACCEPTANCE else Destination.PENDING)
    elif business.action in (ActionEvidence.CONFLICTING, ActionEvidence.UNSUPPORTED):
        destination = Destination.PENDING
    elif business.importance is Importance.IMPORTANT:
        # Independently supported service importance survives an overlapping ad,
        # without inventing an action or honoring promotional deadline claims.
        destination = Destination.PENDING
    elif business.promotion:
        destination = Destination.PROMOTIONS
    elif business.importance in (Importance.IMPORTANT, Importance.UNKNOWN):
        destination = Destination.PENDING
    elif business.informational:
        destination = Destination.INFORMATION
    else:
        destination = Destination.ABSTAIN
    return Projection(case.snapshot, safety, business, authority, destination,
                      intent is Intent.OFFER_QUERY and destination is Destination.PROMOTIONS,
                      historical, historical and authority is not Authority.SIMULATED_ACCEPTANCE)


def decide(case: Case, access: Access, authority: Authority,
           confirmation: Confirmation) -> Case:
    """Return a new bounded tuple of simulated annotations only on explicit confirmation."""
    projection = route(case, access)
    if projection is None:
        raise RoutingError()
    _enum(authority, Authority)
    _enum(confirmation, Confirmation)
    if (confirmation is not Confirmation.EXPLICIT or authority is Authority.NONE
            or projection.safety is not Safety.SAFE_TO_ROUTE
            or projection.business.action is not ActionEvidence.SUPPORTED
            or len(case.history) >= MAX_DECISIONS):
        raise RoutingError()
    decision = Decision(case.assessment, authority)
    return replace(case, history=case.history + (decision,))


def advance(case: Case, evidence: Evidence, business: Business) -> Case:
    """A change or revert invalidates assessment, retaining immutable synthetic history."""
    if type(case) is not Case:
        raise RoutingError()
    snapshot = replace(case.snapshot, generation=case.snapshot.generation + 1,
                       evidence=evidence, business=business)
    return replace(case, snapshot=snapshot, assessment=None)


def reassess(case: Case, safety: Safety, policy: Policy) -> Case:
    """New synthetic assessment episode, even for restored policy/evidence values.

    Generation is an observation/assessment episode, not a production raw-record ID.
    Never restore an earlier episode number to represent a policy or safety revert.
    """
    if type(case) is not Case:
        raise RoutingError()
    current = advance(case, case.snapshot.evidence, case.snapshot.business)
    assessment = Assessment(current.snapshot, policy, safety)
    return replace(current, policy=policy, assessment=assessment)
