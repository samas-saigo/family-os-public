"""E2 disposable enum-only simulation; no provider, DB, network or real authority."""
from dataclasses import dataclass, fields, replace
from enum import Enum

from family_os import _synthetic_security_preflight as e


CONTRACT_VERSION = "synthetic-security-lifecycle-v2"
MAX_ATTEMPTS_PER_SOURCE = 8
MAX_EVENTS_PER_SOURCE = 64


class State(Enum):
    PROPOSED = "proposed"
    AWAITING = "awaiting-explicit-authorization"
    ELIGIBLE = "preflight-eligible-synthetic-only"
    RESERVED = "intent-reserved"
    DISPATCHING = "simulated-dispatch-in-progress"
    QUARANTINED = "verified-synthetic-quarantine"
    FAILED = "failed-no-retry"
    UNKNOWN = "outcome-unknown"
    RECONCILE = "reconciliation-required"
    RESTORE_REQUESTED = "restore-requested"
    RESTORE_BLOCKED = "restore-blocked"
    RESTORED = "verified-synthetic-restore"
    RESTORE_FAILED = "restore-failed-no-retry"
    RESTORE_UNKNOWN = "restore-outcome-unknown"
    STOPPED = "canceled-or-stopped-before-dispatch"


class Fault(Enum):
    SUCCESS = "synthetic-success"
    FAIL = "synthetic-failure-no-effect"
    TIMEOUT_BEFORE = "synthetic-timeout-no-effect"
    TIMEOUT_AFTER = "synthetic-timeout-after-effect"
    CONFLICT = "synthetic-conditional-conflict"


class Scope(Enum):
    MINIMIZED_SECURITY = "fixed-minimized-security-read-review"
    UNKNOWN = "unknown-scope"


class Purpose(Enum):
    SECURITY_REVIEW = "household-security-review"
    UNKNOWN = "unknown-purpose"


class Retention(Enum):
    REVIEWED = "reviewed-disposable-session-window-only-no-crash-durability"
    UNKNOWN = "unknown-retention"


class Revocation(Enum):
    REVOCABLE = "explicit-version-committed-source-revoke"
    UNKNOWN = "unknown-revocation"


class GrantResult(Enum):
    SUBMITTED = "submitted-not-committed"
    COMMITTED = "committed"
    CANCELED = "canceled-no-grant"
    NOT_APPLIED_STALE = "NOT-APPLIED-stale-revision"
    NOT_APPLIED_CONFLICT = "NOT-APPLIED-ambiguous-current-grant"
    NOT_APPLIED_INVALID = "NOT-APPLIED-incomplete-or-invalid-terms"
    NOT_APPLIED_CAPACITY = "NOT-APPLIED-capacity-limit"
    WITHHELD = "no-disclosure"


class NoticeResult(Enum):
    INSPECTABLE = "synthetic-inspection-only-not-delivery"
    WITHHELD = "no-disclosure"


class LifecycleError(ValueError):
    def __init__(self):
        super().__init__("Synthetic lifecycle rejected")


def _typed(value, kind):
    if type(value) is not kind:
        raise LifecycleError()


def _revision(value, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value <= e.MAX_REVISION:
        raise LifecycleError()


def _identity(binding):
    return binding.household, binding.source, binding.provider, binding.object


def _request(binding):
    return binding.household, binding.source, binding.principal, binding.request


def _physical(binding):
    return (_identity(binding), binding.generation, binding.provider_version,
            binding.folder, binding.labels)


@dataclass(frozen=True)
class Checks:
    independent_evidence: e.Condition = e.Condition.UNKNOWN
    risk_policy: e.Condition = e.Condition.UNKNOWN
    provider_state: e.Condition = e.Condition.UNKNOWN
    conditional_write: e.Condition = e.Condition.UNKNOWN
    stop_readiness: e.Condition = e.Condition.UNKNOWN
    reconciliation_readiness: e.Condition = e.Condition.UNKNOWN
    retention: e.Condition = e.Condition.UNKNOWN
    recovery_data: e.Condition = e.Condition.UNKNOWN
    history_complete: e.Condition = e.Condition.UNKNOWN
    no_later_user_changes: e.Condition = e.Condition.UNKNOWN

    def __post_init__(self):
        for field in fields(self):
            _typed(getattr(self, field.name), e.Condition)


@dataclass(frozen=True)
class Item:
    binding: e.Binding
    revision: int = 0
    user_epoch: int = 0
    mutations: int = 0

    def __post_init__(self):
        _typed(self.binding, e.Binding)
        for value in (self.revision, self.user_epoch, self.mutations):
            _revision(value, zero=True)


@dataclass(frozen=True)
class Attempt:
    binding: e.Binding
    state: State
    revision: int
    item_revision: int
    assessment: e.Binding | None = None
    safety: e.Safety = e.Safety.INDETERMINATE
    approval_binding: e.Binding | None = None
    approval: e.Approval = e.Approval.PENDING
    original: e.Binding | None = None
    outcome: e.Outcome | None = None


@dataclass(frozen=True)
class ReviewerRights:
    """Explicit fictional source-scoped reconciliation permission, never a write grant."""
    household: e.Household
    source: e.Source
    principal: e.Principal
    permission: e.Permission

    def __post_init__(self):
        for value, kind in ((self.household, e.Household), (self.source, e.Source),
                            (self.principal, e.Principal), (self.permission, e.Permission)):
            _typed(value, kind)


@dataclass(frozen=True)
class Event:
    binding: e.Binding
    actor: e.Principal
    state: State
    revision: int


@dataclass(frozen=True)
class Receipt:
    binding: e.Binding
    before: Item
    after: Item
    applied: bool


@dataclass(frozen=True)
class Response:
    state: State | None = None
    revision: int | None = None


@dataclass(frozen=True)
class GrantChange:
    actor: e.Principal
    value: e.Rights
    expected_revision: int
    status: GrantResult = GrantResult.SUBMITTED

    def __post_init__(self):
        _typed(self.actor, e.Principal)
        _typed(self.value, e.Rights)
        _revision(self.expected_revision)
        if self.status is not GrantResult.SUBMITTED:
            raise LifecycleError()


@dataclass(frozen=True)
class SharingTerms:
    household: e.Household
    source: e.Source
    recipients: tuple
    expected_revisions: tuple
    fields: Scope
    purpose: Purpose
    operations: Scope
    retention: Retention
    revocation: Revocation

    def __post_init__(self):
        _typed(self.household, e.Household)
        _typed(self.source, e.Source)
        if (type(self.recipients) is not tuple or not 1 <= len(self.recipients) <= 2
                or type(self.expected_revisions) is not tuple
                or len(self.expected_revisions) != len(self.recipients)):
            raise LifecycleError()
        for principal in self.recipients:
            _typed(principal, e.Principal)
        if len(set(self.recipients)) != len(self.recipients):
            raise LifecycleError()
        for revision in self.expected_revisions:
            _revision(revision)
        for value, kind in ((self.fields, Scope), (self.purpose, Purpose),
                            (self.operations, Scope), (self.retention, Retention),
                            (self.revocation, Revocation)):
            _typed(value, kind)


@dataclass(frozen=True)
class PreparedNotice:
    binding: e.Binding
    principal: e.Principal
    source_revision: int

    def __post_init__(self):
        _typed(self.binding, e.Binding)
        _typed(self.principal, e.Principal)
        _revision(self.source_revision)


class Session:
    """Trusted fictional harness initialization, source-gated operator methods.

    Frozen values/tuple histories protect ordinary API use, not hostile Python.
    There is no crash durability, threading guarantee or real authentication.
    """

    def __init__(self, items, grants, *, reviewers=(), synthetic_only=False):
        if synthetic_only is not True:
            raise LifecycleError()
        if type(items) is not tuple or len(items) > 8 or any(type(i) is not Item for i in items):
            raise LifecycleError()
        if type(grants) is not tuple or len(grants) > 4 or any(type(g) is not e.Rights for g in grants):
            raise LifecycleError()
        if len({_identity(i.binding) for i in items}) != len(items):
            raise LifecycleError()
        self._items = {_identity(i.binding): i for i in items}
        self._grants = grants
        self._attempts = {}
        self._events = ()
        self._receipts = {}
        self._checks = {}
        self._grant_history = ()
        self._sharing_history = ()
        self._stops = set()
        self._policy = e.Policy.V1
        self._closed = False
        self.configure_reviewers(reviewers)

    def close(self):
        self._items.clear(); self._attempts.clear(); self._receipts.clear()
        self._checks.clear(); self._stops.clear()
        self._reviewers = (); self._grants = (); self._events = (); self._grant_history = (); self._sharing_history = ()
        self._closed = True

    def _open(self):
        if self._closed:
            raise LifecycleError()

    def _grant(self, binding, viewer):
        self._open(); _typed(binding, e.Binding); _typed(viewer, e.Principal)
        matching = tuple(g for g in self._grants if
                         (g.household, g.source, g.principal) ==
                         (binding.household, binding.source, viewer))
        if not matching or any(g != matching[0] for g in matching):
            return None
        if e.security_count((binding,), self._grants, viewer) != 1:
            return None
        return matching[0]

    def configure_reviewers(self, reviewers):
        """Trusted harness replaces current reviewer assertions; no real grant store."""
        self._open()
        if (type(reviewers) is not tuple or len(reviewers) > 4
                or any(type(r) is not ReviewerRights for r in reviewers)):
            raise LifecycleError()
        self._reviewers = reviewers

    def _reviewer(self, binding, viewer):
        matching = tuple(r for r in self._reviewers if
                         (r.household, r.source, r.principal) ==
                         (binding.household, binding.source, viewer))
        # No arbitrary ALLOWED assertion wins over ambiguous current authority.
        return bool(matching) and all(r == matching[0] for r in matching) and matching[0].permission is e.Permission.ALLOWED

    def _room(self, binding, count=1):
        if sum(ev.binding.source is binding.source and ev.binding.household is binding.household
               for ev in self._events) + count > MAX_EVENTS_PER_SOURCE:
            raise LifecycleError()

    def _change(self, attempt, state, *, actor, **changes):
        _typed(actor, e.Principal)
        self._room(attempt.binding)
        changed = replace(attempt, state=state, revision=attempt.revision + 1, **changes)
        _revision(changed.revision)
        self._attempts[_request(changed.binding)] = changed
        self._events += (Event(changed.binding, actor, state, changed.revision),)
        return Response(state, changed.revision)

    def _find(self, viewer, binding, expected=None, actor=False):
        grant = self._grant(binding, viewer)
        if grant is None:
            return None
        attempt = self._attempts.get(_request(binding))
        if (attempt is None or attempt.binding != binding
                or actor and viewer is not binding.principal):
            raise LifecycleError()
        if expected is not None:
            _revision(expected)
            if attempt.revision != expected:
                raise LifecycleError()
        return attempt

    def summary(self, viewer):
        self._open(); _typed(viewer, e.Principal)
        bindings = tuple(i.binding for i in self._items.values())
        visible_attempts = tuple(a for a in self._attempts.values() if self._grant(a.binding, viewer))
        return {"objects": e.security_count(bindings, self._grants, viewer),
                "unresolved_attempts": sum(a.state in (State.UNKNOWN, State.RESTORE_UNKNOWN, State.RECONCILE)
                               for a in visible_attempts),
                "verified_quarantine_attempts": sum(a.state is State.QUARANTINED for a in visible_attempts),
                "verified_restore_attempts": sum(a.state is State.RESTORED for a in visible_attempts),
                "failed_attempts": sum(a.state in (State.FAILED, State.RESTORE_FAILED)
                                       for a in visible_attempts)}

    def history(self, viewer, binding):
        if self._grant(binding, viewer) is None:
            return ()
        return tuple(ev for ev in self._events if _identity(ev.binding) == _identity(binding))

    def inspect(self, viewer, binding):
        if self._grant(binding, viewer) is None:
            return None
        return self._items.get(_identity(binding))

    def configure_policy(self, policy):
        """Out-of-band central fictional policy change, never a client risk override."""
        self._open(); _typed(policy, e.Policy)
        self._policy = policy

    def configure_checks(self, binding, checks):
        """Out-of-band fictional evidence/retention injection, not an operator grant."""
        self._open(); _typed(binding, e.Binding); _typed(checks, Checks)
        if _identity(binding) not in self._items:
            raise LifecycleError()
        self._checks[_identity(binding)] = checks

    def propose(self, viewer, binding, original=None):
        grant = self._grant(binding, viewer)
        if grant is None:
            return Response()
        if viewer is not binding.principal or _identity(binding) not in self._items:
            raise LifecycleError()
        if original is not None:
            _typed(original, e.Binding)
            if self._grant(original, viewer) is None:
                return Response()
        key = _request(binding)
        if key in self._attempts:
            previous = self._attempts[key]
            if previous.binding != binding or previous.original != original:
                raise LifecycleError()
            return Response(previous.state, previous.revision)
        if sum(a.binding.source is binding.source and a.binding.household is binding.household
               for a in self._attempts.values()) == MAX_ATTEMPTS_PER_SOURCE:
            raise LifecycleError()
        self._room(binding)
        item = self._items[_identity(binding)]
        state = State.RESTORE_REQUESTED if binding.action is e.Action.RESTORE else State.PROPOSED
        attempt = Attempt(binding, state, 1, item.revision, original=original)
        self._attempts[key] = attempt
        self._events += (Event(binding, viewer, state, 1),)
        return Response(state, 1)

    def attest(self, viewer, binding, expected, safety, assessment):
        attempt = self._find(viewer, binding, expected, actor=True)
        if attempt is None:
            return Response()
        _typed(safety, e.Safety); _typed(assessment, e.Binding)
        if attempt.state not in (State.PROPOSED, State.AWAITING, State.RESTORE_REQUESTED):
            raise LifecycleError()
        return self._change(attempt, actor=viewer, state=attempt.state, assessment=assessment, safety=safety)

    def approve(self, viewer, binding, expected, approval, approval_binding):
        attempt = self._find(viewer, binding, expected, actor=True)
        if attempt is None:
            return Response()
        _typed(approval, e.Approval); _typed(approval_binding, e.Binding)
        if attempt.state not in (State.PROPOSED, State.AWAITING, State.RESTORE_REQUESTED):
            raise LifecycleError()
        if binding.action not in self._grant(binding, viewer).operations:
            return self._change(attempt, actor=viewer, state=State.RESTORE_BLOCKED if binding.action is e.Action.RESTORE else State.STOPPED)
        return self._change(attempt, actor=viewer, state=attempt.state, approval=approval, approval_binding=approval_binding)

    def _context(self, attempt):
        b = attempt.binding; item = self._items[_identity(b)]
        grant = self._grant(b, b.principal)
        if grant is None:
            return None
        current = replace(b, generation=item.binding.generation,
                          provider_version=item.binding.provider_version,
                          folder=item.binding.folder, labels=item.binding.labels,
                          source_revision=grant.source_revision, consent_revision=grant.consent_revision,
                          policy=self._policy)
        checks = self._checks.get(_identity(b), Checks())
        records = tuple(e.Record(a.binding, a.outcome) for a in self._attempts.values()
                        if a.outcome is not None and a.binding.household is b.household
                        and a.binding.source is b.source)
        original = None
        if attempt.original is not None:
            prior = self._attempts.get(_request(attempt.original))
            if (prior is not None and prior.binding == attempt.original
                    and prior.state is State.QUARANTINED and prior.outcome is e.Outcome.VERIFIED_QUARANTINE):
                original = e.Record(prior.binding, prior.outcome)
            receipt = self._receipts.get(_request(attempt.original))
            if receipt is None or item.user_epoch != receipt.after.user_epoch:
                checks = replace(checks, no_later_user_changes=e.Condition.CONFLICTED)
        return e.Context(current, grant, attempt.approval_binding or b,
                         attempt.assessment or b, approval=attempt.approval,
                         safety=attempt.safety, emergency_stop=(b.household, b.source) in self._stops,
                         records=records, original_quarantine=original,
                         **{f.name: getattr(checks, f.name) for f in fields(checks)})

    def _verdict(self, attempt):
        # E2 intentionally supports one episode, and never steals a reserved intent.
        for other in self._attempts.values():
            if other.binding == attempt.binding or _identity(other.binding) != _identity(attempt.binding):
                continue
            if other.state is State.RESERVED:
                # Historical reservations cannot keep authority after effective
                # revocation/staleness. A still-current reservation cannot be stolen.
                other_context = self._context(other)
                if other_context is not None and e.preflight(other.binding, other_context) is e.Verdict.ELIGIBLE:
                    return e.Verdict.BLOCKED
            elif other.state in (State.DISPATCHING, State.UNKNOWN,
                                 State.RESTORE_UNKNOWN, State.RECONCILE):
                return e.Verdict.BLOCKED
            if attempt.binding.action is e.Action.QUARANTINE and other.outcome is not None:
                return e.Verdict.BLOCKED
        context = self._context(attempt)
        if context is None:
            return e.Verdict.WITHHELD
        if attempt.assessment is None:
            return e.Verdict.BLOCKED
        return e.preflight(attempt.binding, context)

    def evaluate(self, viewer, binding, expected):
        attempt = self._find(viewer, binding, expected, actor=True)
        if attempt is None:
            return Response()
        if attempt.state not in (State.PROPOSED, State.AWAITING, State.RESTORE_REQUESTED):
            raise LifecycleError()
        verdict = self._verdict(attempt)
        state = State.ELIGIBLE if verdict is e.Verdict.ELIGIBLE else State.AWAITING if verdict is e.Verdict.AWAITING else State.RESTORE_BLOCKED if binding.action is e.Action.RESTORE else State.STOPPED
        return self._change(attempt, actor=viewer, state=state)

    def reserve(self, viewer, binding, expected):
        attempt = self._find(viewer, binding, expected, actor=True)
        if attempt is None:
            return Response()
        if attempt.state is not State.ELIGIBLE:
            raise LifecycleError()
        item = self._items[_identity(binding)]
        if item.revision != attempt.item_revision or self._verdict(attempt) is not e.Verdict.ELIGIBLE:
            return self._change(attempt, actor=viewer, state=State.RESTORE_BLOCKED if binding.action is e.Action.RESTORE else State.STOPPED)
        self._room(binding)
        updated = replace(item, revision=item.revision + 1)
        self._items[_identity(binding)] = updated
        return self._change(attempt, actor=viewer, state=State.RESERVED, item_revision=updated.revision)

    def cancel(self, viewer, binding, expected):
        attempt = self._find(viewer, binding, expected, actor=True)
        if attempt is None:
            return Response()
        if attempt.state not in (State.PROPOSED, State.AWAITING, State.RESTORE_REQUESTED,
                                 State.ELIGIBLE, State.RESERVED):
            raise LifecycleError()
        return self._change(attempt, actor=viewer, state=State.STOPPED)

    def dispatch(self, viewer, binding, expected, fault):
        attempt = self._find(viewer, binding, expected, actor=True)
        if attempt is None:
            return Response()
        _typed(fault, Fault)
        if attempt.state is not State.RESERVED:
            raise LifecycleError()
        item = self._items[_identity(binding)]
        if item.revision != attempt.item_revision or self._verdict(attempt) is not e.Verdict.ELIGIBLE:
            return self._change(attempt, actor=viewer, state=State.RESTORE_BLOCKED if binding.action is e.Action.RESTORE else State.STOPPED)
        self._room(binding, 2)  # Reserve event capacity before any fictional effect.
        if max(item.binding.generation, item.binding.provider_version, item.revision, item.mutations) >= e.MAX_REVISION:
            raise LifecycleError()
        self._change(attempt, actor=viewer, state=State.DISPATCHING)
        attempt = self._attempts[_request(binding)]
        applied = fault in (Fault.SUCCESS, Fault.TIMEOUT_AFTER)
        after = item
        if applied:
            changed = replace(item.binding, folder=binding.target,
                              generation=item.binding.generation + 1,
                              provider_version=item.binding.provider_version + 1)
            after = replace(item, binding=changed, revision=item.revision + 1,
                            mutations=item.mutations + 1)
            self._items[_identity(binding)] = after
        self._receipts[_request(binding)] = Receipt(binding, item, after, applied)
        if fault in (Fault.TIMEOUT_BEFORE, Fault.TIMEOUT_AFTER):
            state = State.RESTORE_UNKNOWN if binding.action is e.Action.RESTORE else State.UNKNOWN
            return self._change(attempt, actor=viewer, state=state, outcome=e.Outcome.UNKNOWN)
        if fault in (Fault.FAIL, Fault.CONFLICT):
            state = State.RESTORE_FAILED if binding.action is e.Action.RESTORE else State.FAILED
            return self._change(attempt, actor=viewer, state=state, outcome=e.Outcome.FAILED)
        return self._verified(attempt, viewer)

    def _verified(self, attempt, viewer):
        receipt = self._receipts.get(_request(attempt.binding))
        item = self._items[_identity(attempt.binding)]
        if (receipt is None or receipt.binding != attempt.binding
                or _physical(item.binding) != _physical(receipt.after.binding)
                or item.user_epoch != receipt.after.user_epoch):
            return self._change(attempt, actor=viewer, state=State.RECONCILE, outcome=e.Outcome.UNKNOWN)
        if not receipt.applied:
            state = State.RESTORE_FAILED if attempt.binding.action is e.Action.RESTORE else State.FAILED
            return self._change(attempt, actor=viewer, state=state, outcome=e.Outcome.FAILED)
        restore = attempt.binding.action is e.Action.RESTORE
        return self._change(attempt, actor=viewer, state=State.RESTORED if restore else State.QUARANTINED,
                            outcome=e.Outcome.VERIFIED_RESTORE if restore else e.Outcome.VERIFIED_QUARANTINE)

    def reconcile(self, viewer, binding, expected, inspection):
        # Source visibility AND independent review authority precede attempt lookup.
        if self._grant(binding, viewer) is None or not self._reviewer(binding, viewer):
            return Response()
        attempt = self._find(viewer, binding, expected)
        if attempt is None:
            return Response()
        _typed(inspection, e.Condition)
        if attempt.state not in (State.UNKNOWN, State.RESTORE_UNKNOWN, State.FAILED,
                                 State.RESTORE_FAILED, State.RECONCILE):
            raise LifecycleError()
        self._room(binding, 2)
        self._change(attempt, actor=viewer, state=State.RECONCILE)
        attempt = self._attempts[_request(binding)]
        checks = self._checks.get(_identity(binding), Checks())
        if (inspection is not e.Condition.VERIFIED
                or checks.reconciliation_readiness is not e.Condition.VERIFIED
                or checks.recovery_data is not e.Condition.VERIFIED):
            return Response(attempt.state, attempt.revision)
        return self._verified(attempt, viewer)

    def user_change(self, viewer, binding, folder, labels):
        if (self._grant(binding, viewer) is None
                or not self._controller(viewer, binding.household, binding.source)):
            return False
        _typed(folder, e.Folder); _typed(labels, e.Labels)
        item = self._items.get(_identity(binding))
        if item is None or max(item.binding.generation, item.binding.provider_version,
                               item.revision, item.user_epoch) >= e.MAX_REVISION:
            raise LifecycleError()
        updated = replace(item.binding, folder=folder, labels=labels,
                          generation=item.binding.generation + 1,
                          provider_version=item.binding.provider_version + 1)
        self._items[_identity(binding)] = replace(item, binding=updated,
                                                revision=item.revision + 1,
                                                user_epoch=item.user_epoch + 1)
        return True

    def emergency_stop(self, actor, household, source):
        self._open(); _typed(actor, e.Principal); _typed(household, e.Household); _typed(source, e.Source)
        if not self._controller(actor, household, source):
            return False
        self._stops.add((household, source))
        return True

    def _controller(self, actor, household, source):
        # Fictional per-source control, not a hierarchical household role.
        return (household is e.Household.HOME
                and actor is (e.Principal.ASTER if source is e.Source.OAK else e.Principal.ROBIN))

    def submit_change(self, actor, value, expected):
        self._open(); _typed(actor, e.Principal); _typed(value, e.Rights); _revision(expected)
        if not self._controller(actor, value.household, value.source):
            return None
        return GrantChange(actor, value, expected)

    def commit_change(self, change, *, confirm=False):
        self._open(); _typed(change, GrantChange)
        if type(confirm) is not bool:
            raise LifecycleError()
        if not self._controller(change.actor, change.value.household, change.value.source):
            return GrantResult.WITHHELD
        if not confirm:
            return GrantResult.CANCELED
        value = change.value
        key = (value.household, value.source, value.principal)
        old = tuple(g for g in self._grants if (g.household, g.source, g.principal) == key)
        if not old or any(g != old[0] for g in old):
            return GrantResult.NOT_APPLIED_CONFLICT
        if old[0].source_revision != change.expected_revision:
            return GrantResult.NOT_APPLIED_STALE
        required_consent = old[0].consent_revision + (value.operations != old[0].operations)
        if value.source_revision != change.expected_revision + 1 or value.consent_revision != required_consent:
            return GrantResult.NOT_APPLIED_INVALID
        if sum(g.source is value.source and g.household is value.household for _, g in self._grant_history) >= MAX_EVENTS_PER_SOURCE:
            return GrantResult.NOT_APPLIED_CAPACITY
        self._grants = tuple(g for g in self._grants if (g.household, g.source, g.principal) != key) + (value,)
        self._grant_history += ((old[0], value),)
        return GrantResult.COMMITTED

    def share(self, actor, terms, *, confirm=False):
        self._open(); _typed(actor, e.Principal); _typed(terms, SharingTerms)
        if type(confirm) is not bool:
            raise LifecycleError()
        if not self._controller(actor, terms.household, terms.source):
            return GrantResult.WITHHELD
        if not confirm:
            return GrantResult.CANCELED
        if (terms.fields is not Scope.MINIMIZED_SECURITY or terms.operations is not Scope.MINIMIZED_SECURITY
                or terms.purpose is not Purpose.SECURITY_REVIEW or terms.retention is not Retention.REVIEWED
                or terms.revocation is not Revocation.REVOCABLE):
            return GrantResult.NOT_APPLIED_INVALID
        changes = []
        for recipient, expected in zip(terms.recipients, terms.expected_revisions):
            matching = tuple(g for g in self._grants if (g.household, g.source, g.principal) ==
                             (terms.household, terms.source, recipient))
            if not matching or any(g != matching[0] for g in matching):
                return GrantResult.NOT_APPLIED_CONFLICT
            old = matching[0]
            if old.source_revision != expected:
                return GrantResult.NOT_APPLIED_STALE
            if old.source_revision == e.MAX_REVISION:
                raise LifecycleError()
            changes.append((old, replace(old, read=e.Permission.ALLOWED,
                                         source_revision=old.source_revision + 1)))
        if sum(g.source is terms.source and g.household is terms.household for _, g in self._grant_history) + len(changes) > MAX_EVENTS_PER_SOURCE:
            return GrantResult.NOT_APPLIED_CAPACITY
        keys = {(new.household, new.source, new.principal) for _, new in changes}
        self._grants = tuple(g for g in self._grants if (g.household, g.source, g.principal) not in keys) + tuple(new for _, new in changes)
        self._grant_history += tuple(changes)
        self._sharing_history += ((actor, terms),)
        return GrantResult.COMMITTED

    def prepare_notice(self, viewer, binding):
        grant = self._grant(binding, viewer)
        if grant is None or _identity(binding) not in self._items:
            return None
        item = self._items[_identity(binding)]
        current = replace(binding, generation=item.binding.generation,
                          provider_version=item.binding.provider_version,
                          folder=item.binding.folder, labels=item.binding.labels)
        return PreparedNotice(current, viewer, grant.source_revision)

    def inspect_notice(self, viewer, notice):
        _typed(notice, PreparedNotice); _typed(viewer, e.Principal)
        grant = self._grant(notice.binding, viewer)
        if (viewer is not notice.principal or grant is None
                or grant.source_revision != notice.source_revision
                or _identity(notice.binding) not in self._items
                or _physical(notice.binding) != _physical(self._items[_identity(notice.binding)].binding)):
            return NoticeResult.WITHHELD
        return NoticeResult.INSPECTABLE
