"""G1 read-service seam over trusted fictional state, not authentication or an API."""
from dataclasses import dataclass
from enum import Enum


CONTRACT_VERSION = "synthetic-household-read-contract-v2"
MAX_VISIBLE_ITEMS = 16
MAX_PAGE = 8
MAX_REVISION = 1000


class Household(Enum):
    CEDAR = "fictional-cedar-household"
    RIDGE = "fictional-ridge-household"


class Principal(Enum):
    MARA = "fictional-mara"
    LEON = "fictional-leon"


class Source(Enum):
    MARA_MAIL = "fictional-mara-mailbox"
    LEON_MAIL = "fictional-leon-mailbox"
    RIDGE_MAIL = "fictional-ridge-mailbox"


class Provider(Enum):
    ONE = "fictional-provider-one"
    TWO = "fictional-provider-two"


class Object(Enum):
    ONE = "fictional-object-one"
    TWO = "fictional-object-two"
    THREE = "fictional-object-three"
    FOUR = "fictional-object-four"
    FIVE = "fictional-object-five"


class Task(Enum):
    BOOKING = "fictional-shared-booking-step"
    SCHOOL = "fictional-school-step"


class Permission(Enum):
    ALLOWED = "declared-current-allowed"
    REVOKED = "revoked"
    UNKNOWN = "unknown"
    STALE = "stale"


class ReadScope(Enum):
    OBSERVATIONS = "minimized-observation-read"
    SECURITY = "minimized-security-read"


class Topic(Enum):
    SCHOOL = "fictional-school"
    HEALTH = "fictional-health"
    BOOKING = "fictional-booking"
    PROMOTION = "fictional-promotion"


class Safety(Enum):
    CLEAR = "declared-current-clear"
    SUSPICIOUS = "suspicious"
    HIGH_RISK = "high-risk"
    INDETERMINATE = "indeterminate"
    STALE = "stale-not-clear"


class Step(Enum):
    CHECK_BOOKING = "review-fictional-equipment-booking"
    CHECK_SCHOOL = "review-fictional-school-arrangement"


class Assignment(Enum):
    MARA = "fictional-mara"
    LEON = "fictional-leon"
    JOINT = "joint-peer-management"


class TaskStatus(Enum):
    OPEN = "synthetic-open"
    COMPLETE = "synthetic-complete"


class ContractError(ValueError):
    def __init__(self):
        super().__init__("Synthetic read contract rejected")


class AccessUnavailable(ValueError):
    def __init__(self):
        super().__init__("Read access unavailable")


def _typed(value, kind):
    if type(value) is not kind:
        raise ContractError()


def _revision(value):
    if type(value) is not int or not 1 <= value <= MAX_REVISION:
        raise ContractError()


def _tuple(values, kind, maximum=None):
    if (type(values) is not tuple or maximum is not None and len(values) > maximum
            or any(type(v) is not kind for v in values)):
        raise ContractError()


@dataclass(frozen=True)
class SourceKey:
    household: Household
    source: Source
    provider: Provider
    object: Object

    def __post_init__(self):
        for v, k in ((self.household, Household), (self.source, Source),
                     (self.provider, Provider), (self.object, Object)):
            _typed(v, k)


@dataclass(frozen=True)
class Observation:
    key: SourceKey
    generation: int
    topic: Topic
    safety: Safety

    def __post_init__(self):
        _typed(self.key, SourceKey); _revision(self.generation)
        _typed(self.topic, Topic); _typed(self.safety, Safety)


@dataclass(frozen=True)
class TaskFields:
    task: Task
    step: Step
    assignment: Assignment
    status: TaskStatus
    revision: int

    def __post_init__(self):
        for v, k in ((self.task, Task), (self.step, Step), (self.assignment, Assignment),
                     (self.status, TaskStatus)):
            _typed(v, k)
        _revision(self.revision)


@dataclass(frozen=True)
class PublishedTask:
    household: Household
    fields: TaskFields
    publication: Permission
    # Protected evidence is never projected or used to enrich approved fields.
    provenance: tuple = ()

    def __post_init__(self):
        _typed(self.household, Household); _typed(self.fields, TaskFields)
        _typed(self.publication, Permission); _tuple(self.provenance, SourceKey)


@dataclass(frozen=True)
class Membership:
    household: Household
    principal: Principal
    permission: Permission
    revision: int

    def __post_init__(self):
        _typed(self.household, Household); _typed(self.principal, Principal)
        _typed(self.permission, Permission); _revision(self.revision)


@dataclass(frozen=True)
class SourceGrant:
    household: Household
    source: Source
    principal: Principal
    permission: Permission
    revision: int
    scopes: tuple = ()

    def __post_init__(self):
        for v, k in ((self.household, Household), (self.source, Source),
                     (self.principal, Principal), (self.permission, Permission)):
            _typed(v, k)
        _revision(self.revision); _tuple(self.scopes, ReadScope, 2)
        if len(set(self.scopes)) != len(self.scopes):
            raise ContractError()


@dataclass(frozen=True)
class TaskGrant:
    household: Household
    task: Task
    principal: Principal
    permission: Permission
    revision: int

    def __post_init__(self):
        for v, k in ((self.household, Household), (self.task, Task),
                     (self.principal, Principal), (self.permission, Permission)):
            _typed(v, k)
        _revision(self.revision)


@dataclass(frozen=True)
class Authorization:
    memberships: tuple = ()
    sources: tuple = ()
    tasks: tuple = ()

    def __post_init__(self):
        # Trusted assertion envelopes, not hidden observation population limits.
        _tuple(self.memberships, Membership, 16)
        _tuple(self.sources, SourceGrant, 32)
        _tuple(self.tasks, TaskGrant, 16)


@dataclass(frozen=True)
class HouseholdState:
    observations: tuple = ()
    tasks: tuple = ()

    def __post_init__(self):
        # Finite typed trusted harness input. Visible consistency/caps follow access.
        _tuple(self.observations, Observation); _tuple(self.tasks, PublishedTask)


@dataclass(frozen=True, eq=False)
class _RequestContext:
    household: Household
    principal: Principal
    membership_revision: int


@dataclass(frozen=True)
class Query:
    limit: int = MAX_PAGE
    offset: int = 0
    topic: Topic | None = None

    def __post_init__(self):
        if (type(self.limit) is not int or not 1 <= self.limit <= MAX_PAGE
                or type(self.offset) is not int or not 0 <= self.offset <= MAX_VISIBLE_ITEMS):
            raise ContractError()
        if self.topic is not None:
            _typed(self.topic, Topic)


@dataclass(frozen=True)
class PreparedQuery:
    context: _RequestContext
    query: Query


@dataclass(frozen=True)
class ObservationEntry:
    key: SourceKey
    generation: int
    topic: Topic


@dataclass(frozen=True)
class SecurityEntry:
    key: SourceKey
    generation: int
    safety: Safety


@dataclass(frozen=True)
class _SecurityFields:
    # Topic is an authorized security search dimension, not observation-only state.
    key: SourceKey
    generation: int
    topic: Topic
    safety: Safety


def _scope_fields(observation, scope):
    if scope is ReadScope.OBSERVATIONS:
        return ObservationEntry(observation.key, observation.generation, observation.topic)
    return _SecurityFields(observation.key, observation.generation, observation.topic, observation.safety)


@dataclass(frozen=True)
class Page:
    rows: tuple
    total: int
    has_more: bool


@dataclass(frozen=True)
class Projection:
    observations: Page
    tasks: Page
    security: Page


def _effective(values, key, expected):
    matching = tuple(v for v in values if key(v) == expected)
    # No numeric revision, input order or arbitrary ALLOWED entry establishes authority.
    if not matching or any(v != matching[0] for v in matching):
        return None
    return matching[0] if matching[0].permission is Permission.ALLOWED else None


def _coalesce(values, key):
    unique = {}
    for value in values:
        identity = key(value)
        if identity in unique and unique[identity] != value:
            raise ContractError()
        unique[identity] = value
    if len(unique) > MAX_VISIBLE_ITEMS:
        raise ContractError()
    return tuple(unique[k] for k in sorted(unique, key=lambda k: tuple(v.value for v in k)))


def _page(rows, query):
    end = query.offset + query.limit
    return Page(rows[query.offset:end], len(rows), end < len(rows))


class ReadService:
    """Single authoritative fictional state; not a hostile-code/authentication sandbox."""

    def __init__(self, state, authorization, *, synthetic_only=False):
        if synthetic_only is not True:
            raise ContractError()
        _typed(state, HouseholdState); _typed(authorization, Authorization)
        self._state = state
        self._authorization = authorization
        self._contexts = ()

    def harness_replace_authorization(self, authorization):
        """Trusted test control, not an operator grant-edit endpoint or real CAS."""
        _typed(authorization, Authorization)
        self._authorization = authorization

    def harness_replace_state(self, state):
        """Trusted fictional snapshot replacement, never task creation or ingestion."""
        _typed(state, HouseholdState)
        self._state = state

    def _membership(self, household, principal):
        return _effective(self._authorization.memberships,
                          lambda m: (m.household, m.principal), (household, principal))

    def harness_context(self, household, principal):
        """Only the trusted synthetic harness issues contexts; no public login/identity proof."""
        _typed(household, Household); _typed(principal, Principal)
        m = self._membership(household, principal)
        if m is None:
            raise AccessUnavailable()
        for c in self._contexts:
            if (c.household, c.principal, c.membership_revision) == (household, principal, m.revision):
                return c
        if len(self._contexts) >= 16:
            raise ContractError()
        c = _RequestContext(household, principal, m.revision)
        self._contexts += (c,)
        return c

    def _authorize(self, context):
        if type(context) is not _RequestContext or not any(context is c for c in self._contexts):
            raise AccessUnavailable()
        m = self._membership(context.household, context.principal)
        if m is None or m.revision != context.membership_revision:
            raise AccessUnavailable()

    def _source(self, context, source, scope):
        g = _effective(self._authorization.sources,
                       lambda g: (g.household, g.source, g.principal),
                       (context.household, source, context.principal))
        return g is not None and scope in g.scopes

    def prepare(self, context, query):
        self._authorize(context); _typed(query, Query)
        return PreparedQuery(context, query)  # No rows, counts, links or authorization lease.

    def consume(self, context, prepared):
        self._authorize(context)
        _typed(prepared, PreparedQuery)
        if prepared.context is not context:
            raise AccessUnavailable()
        return self.project(context, prepared.query)

    def project(self, context, query=Query()):
        self._authorize(context); _typed(query, Query)
        household = context.household
        # Access is established before examining record content, duplicates or caps.
        allowed = {scope: {source for source in Source if self._source(context, source, scope)}
                   for scope in ReadScope}
        visible = {scope: _coalesce(
            (_scope_fields(o, scope) for o in self._state.observations
             if o.key.household is household and o.key.source in allowed[scope]),
            lambda o: (o.key.household, o.key.source, o.key.provider, o.key.object))
                   for scope in ReadScope}
        task_ids = {t for t in Task if _effective(self._authorization.tasks,
                    lambda g: (g.household, g.task, g.principal),
                    (household, t, context.principal)) is not None}
        published = []
        for task in Task:
            if task not in task_ids:
                continue
            assertions = tuple((t.fields, t.publication) for t in self._state.tasks
                               if t.household is household and t.fields.task is task)
            # Publication is its own declared current authority; never inspect provenance.
            if (assertions and all(a == assertions[0] for a in assertions)
                    and assertions[0][1] is Permission.ALLOWED):
                published.append(assertions[0][0])
        observations = tuple(o for o in visible[ReadScope.OBSERVATIONS]
                             if query.topic is None or o.topic is query.topic)
        security = tuple(SecurityEntry(o.key, o.generation, o.safety)
                         for o in visible[ReadScope.SECURITY] if o.safety is not Safety.CLEAR
                         and (query.topic is None or o.topic is query.topic))
        topics = {Step.CHECK_BOOKING: Topic.BOOKING, Step.CHECK_SCHOOL: Topic.SCHOOL}
        tasks = tuple(t for t in published
                      if query.topic is None or topics[t.step] is query.topic)
        return Projection(_page(observations, query), _page(tasks, query), _page(security, query))

    def observation(self, context, key):
        """Source-link-shaped lookup: absence and inaccessible existence both return None."""
        self._authorize(context); _typed(key, SourceKey)
        if key.household is not context.household or not self._source(context, key.source, ReadScope.OBSERVATIONS):
            return None
        values = _coalesce((_scope_fields(o, ReadScope.OBSERVATIONS)
                            for o in self._state.observations if o.key == key),
                           lambda o: (o.key.household, o.key.source, o.key.provider, o.key.object))
        return values[0] if values else None
