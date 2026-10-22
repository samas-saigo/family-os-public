"""E1 enum-only preflight probes. No real authority, execution, persistence or I/O."""
from dataclasses import dataclass
from enum import Enum


CONTRACT_VERSION = "synthetic-security-preflight-v3"
MAX_REVISION = 1000
MAX_RECORDS = 32


class Household(Enum):
    HOME = "invented-home"
    OTHER = "invented-other-home"


class Source(Enum):
    OAK = "invented-oak-mailbox"
    PINE = "invented-pine-mailbox"


class Principal(Enum):
    ASTER = "invented-aster"
    ROBIN = "invented-robin"


class Object(Enum):
    NOTICE = "invented-notice"
    OTHER = "invented-other-notice"


class Provider(Enum):
    ONE = "invented-provider-one"
    TWO = "invented-provider-two"


class Action(Enum):
    QUARANTINE = "proposed-reversible-quarantine"
    RESTORE = "proposed-own-delta-restore"


class Permission(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"
    REVOKED = "revoked"


class Condition(Enum):
    VERIFIED = "synthetically-verified"
    UNKNOWN = "unknown"
    STALE = "stale"
    CONFLICTED = "conflicted"
    UNSUPPORTED = "unsupported"
    REVOKED = "revoked"
    UNAVAILABLE = "unavailable"


class Safety(Enum):
    HIGH_RISK = "independently-evaluated-synthetic-high-risk"
    CLEAR = "no-detected-risk-not-guaranteed-safe"
    SUSPICIOUS = "suspicious"
    INDETERMINATE = "indeterminate"


class Policy(Enum):
    V1 = "invented-central-policy-v1"
    V2 = "invented-central-policy-v2"


class Folder(Enum):
    INBOX = "invented-inbox"
    ARCHIVE = "invented-archive"
    VAULT = "invented-verified-vault"
    PURGING = "invented-auto-purging-location"


class Labels(Enum):
    BASE = "invented-base-label-set"
    USER_EDIT = "invented-user-edited-label-set"


class Delta(Enum):
    MOVE_TO_VAULT = "move-to-verified-vault"
    UNDO_OWN_MOVE = "undo-only-recorded-move"


class Request(Enum):
    FIRST = "invented-request-one"
    SECOND = "invented-request-two"


class Approval(Enum):
    EXPLICIT = "explicit-per-action-synthetic-approval"
    PENDING = "awaiting-approval"
    STANDING_PROPOSED = "unapproved-standing-policy-disabled"
    REVOKED = "revoked"


class Outcome(Enum):
    VERIFIED_QUARANTINE = "verified-synthetic-quarantine"
    VERIFIED_RESTORE = "verified-synthetic-restore"
    FAILED = "failed-reconciliation-required"
    UNKNOWN = "unknown-reconciliation-required"


class Verdict(Enum):
    WITHHELD = "no-disclosure"
    BLOCKED = "blocked"
    AWAITING = "awaiting-explicit-authorization"
    RECONCILE = "reconciliation-required-no-blind-retry"
    REPLAY = "prior-verified-synthetic-result-no-new-dispatch"
    ELIGIBLE = "synthetic-preflight-only-not-write-authority"


class ContractError(ValueError):
    def __init__(self):
        super().__init__("Synthetic security preflight rejected")


def _enum(value, kind):
    if type(value) is not kind:
        raise ContractError()


def _revision(value):
    if type(value) is not int or not 1 <= value <= MAX_REVISION:
        raise ContractError()


@dataclass(frozen=True)
class Binding:
    household: Household = Household.HOME
    source: Source = Source.OAK
    provider: Provider = Provider.ONE
    object: Object = Object.NOTICE
    principal: Principal = Principal.ASTER
    action: Action = Action.QUARANTINE
    generation: int = 1
    provider_version: int = 1
    folder: Folder = Folder.INBOX
    labels: Labels = Labels.BASE
    target: Folder = Folder.VAULT
    delta: Delta = Delta.MOVE_TO_VAULT
    source_revision: int = 1
    consent_revision: int = 1
    policy: Policy = Policy.V1
    request: Request = Request.FIRST

    def __post_init__(self):
        for name, kind in (("household", Household), ("source", Source),
                           ("provider", Provider), ("object", Object),
                           ("principal", Principal), ("action", Action),
                           ("folder", Folder), ("labels", Labels), ("target", Folder), ("delta", Delta),
                           ("policy", Policy), ("request", Request)):
            _enum(getattr(self, name), kind)
        for name in ("generation", "provider_version", "source_revision", "consent_revision"):
            _revision(getattr(self, name))


@dataclass(frozen=True)
class Rights:
    household: Household
    source: Source
    principal: Principal
    read: Permission
    operations: tuple
    consent_revision: int
    source_revision: int = 1

    def __post_init__(self):
        for name, kind in (("household", Household), ("source", Source),
                           ("principal", Principal), ("read", Permission)):
            _enum(getattr(self, name), kind)
        _revision(self.consent_revision)
        _revision(self.source_revision)
        if type(self.operations) is not tuple or len(self.operations) > 2:
            raise ContractError()
        for action in self.operations:
            _enum(action, Action)
        if len(set(self.operations)) != len(self.operations):
            raise ContractError()


@dataclass(frozen=True)
class Record:
    binding: Binding
    outcome: Outcome

    def __post_init__(self):
        if type(self.binding) is not Binding:
            raise ContractError()
        _enum(self.outcome, Outcome)
        if (self.outcome is Outcome.VERIFIED_QUARANTINE
                and self.binding.action is not Action.QUARANTINE
                or self.outcome is Outcome.VERIFIED_RESTORE
                and self.binding.action is not Action.RESTORE):
            raise ContractError()


@dataclass(frozen=True)
class Context:
    current: Binding
    rights: Rights
    approval_binding: Binding
    assessment_binding: Binding
    approval: Approval = Approval.PENDING
    safety: Safety = Safety.INDETERMINATE
    independent_evidence: Condition = Condition.UNKNOWN
    risk_policy: Condition = Condition.UNKNOWN
    provider_state: Condition = Condition.UNKNOWN
    conditional_write: Condition = Condition.UNKNOWN
    stop_readiness: Condition = Condition.UNKNOWN
    reconciliation_readiness: Condition = Condition.UNKNOWN
    retention: Condition = Condition.UNKNOWN
    recovery_data: Condition = Condition.UNKNOWN
    history_complete: Condition = Condition.UNKNOWN
    no_later_user_changes: Condition = Condition.UNKNOWN
    emergency_stop: bool = True
    records: tuple = ()
    original_quarantine: Record | None = None

    def __post_init__(self):
        if (type(self.current) is not Binding or type(self.rights) is not Rights
                or type(self.approval_binding) is not Binding
                or type(self.assessment_binding) is not Binding):
            raise ContractError()
        _enum(self.approval, Approval)
        _enum(self.safety, Safety)
        for name in ("independent_evidence", "risk_policy", "provider_state",
                     "conditional_write", "stop_readiness", "reconciliation_readiness",
                     "retention", "recovery_data", "history_complete",
                     "no_later_user_changes"):
            _enum(getattr(self, name), Condition)
        if type(self.emergency_stop) is not bool:
            raise ContractError()
        if type(self.records) is not tuple:
            raise ContractError()
        if any(type(record) is not Record for record in self.records):
            raise ContractError()
        if self.original_quarantine is not None and type(self.original_quarantine) is not Record:
            raise ContractError()


def _identity(binding):
    return binding.household, binding.source, binding.provider, binding.object


def _source_visible(binding, rights):
    return (rights.read is Permission.ALLOWED
            and (binding.household, binding.source) == (rights.household, rights.source))


def _readable(binding, rights):
    return _source_visible(binding, rights) and binding.principal is rights.principal


def preflight(candidate, context):
    """Returns only a fixed verdict; never executes or grants actual authority."""
    if type(candidate) is not Binding or type(context) is not Context:
        raise ContractError()
    if not _readable(candidate, context.rights):
        return Verdict.WITHHELD
    if (candidate != context.current or context.emergency_stop
            or candidate.action not in context.rights.operations
            or candidate.consent_revision != context.rights.consent_revision
            or candidate.source_revision != context.rights.source_revision):
        return Verdict.BLOCKED
    # Apply collection bounds only after source access, as in Stage D.
    visible = []
    for record in context.records:
        if _source_visible(record.binding, context.rights):
            if len(visible) == MAX_RECORDS:
                raise ContractError()
            visible.append(record)
    previous = tuple(r for r in visible if r.binding.request is candidate.request
                     and r.binding.principal is candidate.principal)
    if previous:
        if len(previous) != 1 or previous[0].binding != candidate:
            return Verdict.BLOCKED
        if previous[0].outcome in (Outcome.UNKNOWN, Outcome.FAILED):
            return Verdict.RECONCILE
        return Verdict.REPLAY
    # A changed request key must not bypass unresolved work for this exact object.
    if any(_source_visible(r.binding, context.rights) and _identity(r.binding) == _identity(candidate)
           and r.outcome in (Outcome.UNKNOWN, Outcome.FAILED) for r in visible):
        return Verdict.RECONCILE
    if any(_identity(r.binding) == _identity(candidate)
           and r.binding.generation == candidate.generation
           and r.binding.provider_version == candidate.provider_version for r in visible):
        return Verdict.BLOCKED
    if (context.approval_binding != candidate or context.assessment_binding != candidate
            or context.approval is Approval.REVOKED):
        return Verdict.BLOCKED
    if context.approval is not Approval.EXPLICIT:
        return Verdict.AWAITING
    if any(getattr(context, name) is not Condition.VERIFIED for name in
           ("independent_evidence", "risk_policy", "provider_state", "conditional_write",
            "stop_readiness", "reconciliation_readiness",
            "retention", "recovery_data", "no_later_user_changes")):
        return Verdict.BLOCKED
    if candidate.action is Action.QUARANTINE:
        if (context.safety is not Safety.HIGH_RISK or candidate.target is not Folder.VAULT
                or candidate.folder not in (Folder.INBOX, Folder.ARCHIVE)
                or candidate.delta is not Delta.MOVE_TO_VAULT):
            return Verdict.BLOCKED
    else:
        original = context.original_quarantine
        # E1 establishes only a single declared complete quarantine episode. It
        # cannot authorize another restoration after a restore or a later episode.
        object_history = tuple(r for r in visible if _identity(r.binding) == _identity(candidate))
        if (context.safety is not Safety.CLEAR
                or context.history_complete is not Condition.VERIFIED
                or original is None or original.outcome is not Outcome.VERIFIED_QUARANTINE
                or object_history != (original,)
                or candidate.generation <= original.binding.generation
                or candidate.provider_version <= original.binding.provider_version
                or original.binding.target is not Folder.VAULT
                or original.binding.folder not in (Folder.INBOX, Folder.ARCHIVE)
                or original.binding.delta is not Delta.MOVE_TO_VAULT
                or _identity(original.binding) != _identity(candidate)
                or candidate.labels is not original.binding.labels
                or candidate.folder is not original.binding.target
                or candidate.target is not original.binding.folder
                or candidate.delta is not Delta.UNDO_OWN_MOVE):
            return Verdict.BLOCKED
    return Verdict.ELIGIBLE


def security_count(bindings, rights, principal):
    """Count unique authorized household/source/provider/object observations."""
    _enum(principal, Principal)
    if type(bindings) is not tuple or type(rights) is not tuple:
        raise ContractError()
    if len(rights) > 4 or any(type(r) is not Rights for r in rights):
        raise ContractError()
    # Each key must assert one current value. Revisions are not authority: no
    # highest-revision/ALLOWED-wins rule. Exact duplicates are harmless; any
    # distinct value permanently withholds this key for this evaluation.
    effective = {}
    for grant in rights:
        if grant.principal is not principal:
            continue
        key = (grant.household, grant.source, grant.principal)
        if key not in effective:
            effective[key] = grant
        elif effective[key] != grant:
            effective[key] = None
    visible = set()
    for binding in bindings:
        if type(binding) is not Binding:
            raise ContractError()
        grant = effective.get((binding.household, binding.source, principal))
        if grant is not None and _source_visible(binding, grant):
            identity = _identity(binding)
            if identity not in visible:
                if len(visible) == MAX_RECORDS:
                    raise ContractError()
                visible.add(identity)
    return len(visible)
