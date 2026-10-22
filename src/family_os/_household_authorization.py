"""G2a internal SQL authorization; trusted fictional harness only, no entrypoint/auth."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from uuid import uuid4

from sqlalchemy import select, insert, update, create_engine
from sqlalchemy.exc import SQLAlchemyError
from family_os.schema import (household, person, source_account, household_membership as member,
    source_read_grant as source_grant, publication_scope, publication_read_grant as publication_grant,
    authorization_audit as audit)


CONTRACT_VERSION = "g2a-authorization-v1"

class State(Enum):
    ALLOWED = 'allowed'
    REVOKED = 'revoked'


class Kind(Enum):
    MEMBERSHIP = 'membership'
    SOURCE = 'source'
    PUBLICATION = 'publication'


class Outcome(Enum):
    SUBMITTED = 'SUBMITTED-not-committed'
    COMMITTED = 'COMMITTED'
    REPLAY = 'COMMITTED-replay-no-write'
    CANCELED = 'CANCELED-no-write'
    STALE = 'NOT_APPLIED-stale-revision'
    CONFLICT = 'NOT_APPLIED-conflict'
    REJECTED = 'NOT_APPLIED-rejected'
    UNAVAILABLE = 'NOT_APPLIED-access-unavailable'
    UNKNOWN = 'UNKNOWN-reconciliation-required'


class Publication(Enum):
    BOOKING = 'fictional-booking'
    SCHOOL = 'fictional-school'


class Object(Enum):
    BOOKING = 'invented-copper-booking'
    SCHOOL = 'invented-willow-school'


class Topic(Enum):
    BOOKING = 'fictional-booking'
    SCHOOL = 'fictional-school'


class Safety(Enum):
    CLEAR = 'declared-clear'
    HIGH_RISK = 'declared-high-risk'
    UNKNOWN = 'unknown-not-clear'


class Step(Enum):
    BOOKING = 'inspect-fictional-booking'
    SCHOOL = 'inspect-fictional-school'


class Failure(ValueError):
    def __init__(self):
        super().__init__('Internal authorization unavailable')


def _id(value):
    if type(value) is not str or re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value) is None:
        raise Failure()


def _revision(value, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value <= 1000000:
        raise Failure()


@dataclass(frozen=True)
class Change:
    household_id: str
    kind: Kind
    recipient_id: str
    resource: str | None
    state: State
    expected_revision: int
    request_id: str
    observations: bool = False
    security: bool = False

    def __post_init__(self):
        for value in (self.household_id, self.recipient_id, self.request_id):
            _id(value)
        if type(self.kind) is not Kind or type(self.state) is not State:
            raise Failure()
        _revision(self.expected_revision, zero=True)
        if type(self.observations) is not bool or type(self.security) is not bool:
            raise Failure()
        if self.kind is Kind.MEMBERSHIP:
            if self.resource is not None:
                raise Failure()
        elif self.kind is Kind.SOURCE:
            _id(self.resource)
        elif self.resource not in {p.value for p in Publication}:
            raise Failure()
        if self.kind is not Kind.SOURCE and (self.observations or self.security):
            raise Failure()

    @property
    def scope_key(self):
        return 'membership' if self.resource is None else self.resource

    @property
    def fingerprint(self):
        values = [self.household_id, self.kind.value, self.recipient_id, self.resource,
                  self.state.value, self.expected_revision, self.request_id, self.observations, self.security]
        return sha256(json.dumps(values, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True, eq=False)
class _Context:
    household_id: str
    actor_id: str
    membership_revision: int
    manage_membership: bool
    sources: tuple
    publications: tuple


@dataclass(frozen=True)
class Submission:
    context: _Context
    change: Change
    recipient_revision: int = 0
    outcome: Outcome = Outcome.SUBMITTED

    @property
    def fingerprint(self):
        return sha256(f'{self.change.fingerprint}:{self.recipient_revision}'.encode()).hexdigest()


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    revision: int | None = None


@dataclass(frozen=True)
class FixtureObservation:
    source_id: str
    object: Object
    generation: int
    topic: Topic
    safety: Safety

    def __post_init__(self):
        _id(self.source_id); _revision(self.generation)
        if type(self.object) is not Object or type(self.topic) is not Topic or type(self.safety) is not Safety:
            raise Failure()


@dataclass(frozen=True)
class FixturePublication:
    key: Publication
    step: Step

    def __post_init__(self):
        if type(self.key) is not Publication or type(self.step) is not Step:
            raise Failure()


@dataclass(frozen=True)
class FixtureRepository:
    observations: tuple = ()
    publications: tuple = ()

    def __post_init__(self):
        for values, kind in ((self.observations, FixtureObservation), (self.publications, FixturePublication)):
            if type(values) is not tuple or any(type(v) is not kind for v in values):
                raise Failure()


@dataclass(frozen=True)
class PreparedRead:
    context: _Context
    limit: int
    offset: int
    topic: Topic | None


@dataclass(frozen=True)
class Projection:
    observations: tuple
    source_count: int
    publications: tuple
    publication_count: int
    security: tuple
    security_count: int


class AuthorizationService:
    """Explicit engine + fictional repository, never DATABASE_URL/provider discovery."""

    def __init__(self, engine, repository, *, synthetic_only=False):
        if synthetic_only is not True or type(repository) is not FixtureRepository:
            raise Failure()
        if engine.dialect.name not in ('sqlite', 'postgresql'):
            raise Failure()
        self._engine = engine
        self._repository = repository
        self._contexts = ()

    @contextmanager
    def _transaction(self, household_id, *, engine=None, progress=None):
        with authorization_transaction(self._engine if engine is None else engine, household_id, progress=progress) as c:
            yield c

    def _handle(self, context):
        if type(context) is not _Context or not any(context is v for v in self._contexts):
            raise Failure()

    def _actor(self, c, context):
        self._handle(context)
        current = c.execute(select(member).where(member.c.household_id == context.household_id,
                                                 member.c.person_id == context.actor_id)).mappings().one_or_none()
        if current is None or current['state'] != 'allowed' or current['revision'] != context.membership_revision:
            raise Failure()

    def harness_context(self, household_id, actor_id, *, manage_membership=False, sources=(), publications=()):
        """Trusted test provisioning, not a public authentication/permission API."""
        _id(household_id); _id(actor_id)
        if type(manage_membership) is not bool or type(sources) is not tuple or len(sources) > 8:
            raise Failure()
        for s in sources:
            _id(s)
        if type(publications) is not tuple or len(publications) > 2 or any(type(p) is not Publication for p in publications):
            raise Failure()
        with self._transaction(household_id) as c:
            row = c.execute(select(member).where(member.c.household_id == household_id,
                                                member.c.person_id == actor_id)).mappings().one_or_none()
            if row is None or row['state'] != 'allowed':
                raise Failure()
            context = _Context(household_id, actor_id, row['revision'], manage_membership, sources, publications)
        if len(self._contexts) >= 32:
            raise Failure()
        self._contexts += (context,)
        return context

    def _capability(self, context, kind, resource):
        return (context.manage_membership if kind is Kind.MEMBERSHIP else
                resource in context.sources if kind is Kind.SOURCE else
                resource in {p.value for p in context.publications})

    def submit(self, context, change):
        self._handle(context)
        if type(change) is not Change or change.household_id != context.household_id:
            raise Failure()
        with self._transaction(context.household_id) as c:
            self._actor(c, context)
            if not self._capability(context, change.kind, change.resource):
                raise Failure()
            recipient_revision = c.execute(select(member.c.revision).where(
                member.c.household_id == context.household_id, member.c.person_id == change.recipient_id)).scalar_one_or_none() or 0
        return Submission(context, change, recipient_revision)  # No grant/audit mutation; not a permission lease.

    def commit(self, context, submission, *, confirm=False):
        progress = {'commit_started': False}
        mutation_attempted = False
        try:
            self._handle(context)
            if type(submission) is not Submission or submission.context is not context or type(submission.change) is not Change:
                return Result(Outcome.REJECTED)
            change = submission.change
            if change.household_id != context.household_id or not self._capability(context, change.kind, change.resource):
                return Result(Outcome.UNAVAILABLE)
            if confirm is False:
                return Result(Outcome.CANCELED)
            if confirm is not True:
                return Result(Outcome.REJECTED)
            with self._transaction(context.household_id, progress=progress) as c:
                self._actor(c, context)
                prior_request = c.execute(select(audit).where(audit.c.household_id == context.household_id,
                    audit.c.actor_id == context.actor_id, audit.c.request_id == change.request_id)).mappings().one_or_none()
                if prior_request:
                    return Result(Outcome.REPLAY, prior_request['revision']) if prior_request['intent_hash'] == submission.fingerprint else Result(Outcome.CONFLICT)
                recipient = c.execute(select(person.c.id).where(person.c.household_id == context.household_id,
                                                               person.c.id == change.recipient_id)).scalar_one_or_none()
                if recipient is None:
                    return Result(Outcome.REJECTED)
                if change.kind is Kind.SOURCE:
                    if c.execute(select(source_account.c.id).where(source_account.c.household_id == context.household_id,
                            source_account.c.id == change.resource, source_account.c.provider == 'fixture')).scalar_one_or_none() is None:
                        return Result(Outcome.REJECTED)
                elif change.kind is Kind.PUBLICATION:
                    if c.execute(select(publication_scope.c.publication_key).where(publication_scope.c.household_id == context.household_id,
                            publication_scope.c.publication_key == change.resource)).scalar_one_or_none() is None:
                        return Result(Outcome.REJECTED)
                table = {Kind.MEMBERSHIP: member, Kind.SOURCE: source_grant, Kind.PUBLICATION: publication_grant}[change.kind]
                predicates = [table.c.household_id == context.household_id, table.c.person_id == change.recipient_id]
                if change.kind is Kind.SOURCE:
                    predicates.append(table.c.source_account_id == change.resource)
                elif change.kind is Kind.PUBLICATION:
                    predicates.append(table.c.publication_key == change.resource)
                old = c.execute(select(table).where(*predicates)).mappings().one_or_none()
                old_revision = old['revision'] if old else 0
                if old_revision != change.expected_revision:
                    return Result(Outcome.STALE)
                _revision(old_revision + 1)
                recipient_member = c.execute(select(member).where(member.c.household_id == context.household_id,
                    member.c.person_id == change.recipient_id)).mappings().one_or_none()
                if (recipient_member['revision'] if recipient_member else 0) != submission.recipient_revision:
                    return Result(Outcome.STALE)
                if change.kind is not Kind.MEMBERSHIP and (recipient_member is None or recipient_member['state'] != 'allowed'):
                    return Result(Outcome.REJECTED)
                values = dict(state=change.state.value, revision=old_revision + 1)
                membership_revision = old_revision + 1 if change.kind is Kind.MEMBERSHIP else recipient_member['revision']
                if change.kind is not Kind.MEMBERSHIP:
                    values['membership_revision'] = membership_revision
                if change.kind is Kind.SOURCE:
                    values.update(observations=change.observations, security=change.security)
                mutation_attempted = True
                if old is None:
                    values.update(household_id=context.household_id, person_id=change.recipient_id)
                    if change.kind is Kind.SOURCE:
                        values['source_account_id'] = change.resource
                    elif change.kind is Kind.PUBLICATION:
                        values['publication_key'] = change.resource
                    c.execute(insert(table).values(**values))
                elif c.execute(update(table).where(*predicates, table.c.revision == old_revision).values(**values)).rowcount != 1:
                    raise Failure()
                c.execute(insert(audit).values(id=str(uuid4()), household_id=context.household_id,
                    actor_id=context.actor_id, recipient_id=change.recipient_id, kind=change.kind.value,
                    scope_key=change.scope_key, source_account_id=change.resource if change.kind is Kind.SOURCE else None,
                    publication_key=change.resource if change.kind is Kind.PUBLICATION else None,
                    request_id=change.request_id, intent_hash=submission.fingerprint,
                    old_state=old['state'] if old else None, new_state=change.state.value,
                    old_observations=old.get('observations', False) if old else False,
                    old_security=old.get('security', False) if old else False,
                    new_observations=change.observations, new_security=change.security,
                    old_revision=old_revision, revision=old_revision + 1,
                    old_membership_revision=old.get('membership_revision', old_revision) if old else 0,
                    new_membership_revision=membership_revision, outcome='committed', created_at=datetime.now(timezone.utc)))
                return Result(Outcome.COMMITTED, old_revision + 1)
        except Failure:
            if mutation_attempted or progress['commit_started']:
                return self.reconcile_change(context, submission)
            return Result(Outcome.UNAVAILABLE)
        except Exception:
            # Driver/SQLAlchemy and ordinary exceptions cannot establish non-application.
            return self.reconcile_change(context, submission)

    def reconcile_change(self, context, submission):
        """Read-only exact-request proof on a new physical connection to the same primary.

        A household lock orders this proof after the original transaction resolves.
        Ledger absence proves non-application only within this atomic audited protocol.
        No effect retry, new key, current-state inference or authority bypass occurs.
        """
        fresh = None
        try:
            self._handle(context)
            if (type(submission) is not Submission or submission.context is not context
                    or type(submission.change) is not Change):
                return Result(Outcome.UNKNOWN)
            change = submission.change
            if (change.household_id != context.household_id
                    or not self._capability(context, change.kind, change.resource)):
                return Result(Outcome.UNKNOWN)
            # Recreate the trusted pool/creator (including connection configuration),
            # never reuse the failed connection or select a replica/new database URL.
            fresh = create_engine(self._engine.url, pool=self._engine.pool.recreate())
            fresh = fresh.execution_options(**self._engine.get_execution_options())
            with self._transaction(context.household_id, engine=fresh) as c:
                self._actor(c, context)
                record = c.execute(select(audit).where(audit.c.household_id == context.household_id,
                    audit.c.actor_id == context.actor_id, audit.c.request_id == change.request_id)).mappings().one_or_none()
                if record is None:
                    return Result(Outcome.CONFLICT)  # Verified absence under original lock order.
                if record['intent_hash'] != submission.fingerprint:
                    return Result(Outcome.CONFLICT)  # Unique key belongs to another exact intent.
                expected = dict(recipient_id=change.recipient_id, kind=change.kind.value,
                    scope_key=change.scope_key, old_revision=change.expected_revision,
                    revision=change.expected_revision + 1, new_state=change.state.value,
                    new_observations=change.observations, new_security=change.security,
                    new_membership_revision=(change.expected_revision + 1 if change.kind is Kind.MEMBERSHIP
                                             else submission.recipient_revision), outcome='committed',
                    source_account_id=change.resource if change.kind is Kind.SOURCE else None,
                    publication_key=change.resource if change.kind is Kind.PUBLICATION else None)
                if any(record[key] != value for key, value in expected.items()):
                    return Result(Outcome.UNKNOWN)
                return Result(Outcome.COMMITTED, record['revision'])  # Historical proof, not current permission.
        except Exception:
            return Result(Outcome.UNKNOWN)  # No raw driver details, secrets or private error text.
        finally:
            if fresh is not None:
                try:
                    fresh.dispose()
                except Exception:
                    pass  # Cleanup cannot replace an established outcome or leak its error.

    def prepare_read(self, context, *, limit=20, offset=0, topic=None):
        self._handle(context)
        if type(limit) is not int or not 1 <= limit <= 20 or type(offset) is not int or not 0 <= offset <= 128:
            raise Failure()
        if topic is not None and type(topic) is not Topic:
            raise Failure()
        with self._transaction(context.household_id) as c:
            self._actor(c, context)
        return PreparedRead(context, limit, offset, topic)  # No projected data or rights lease.

    def consume_read(self, context, prepared):
        self._handle(context)
        if type(prepared) is not PreparedRead or prepared.context is not context:
            raise Failure()
        return self.read(context, limit=prepared.limit, offset=prepared.offset, topic=prepared.topic)

    def read(self, context, *, limit=20, offset=0, topic=None):
        self._handle(context)
        if type(limit) is not int or not 1 <= limit <= 20 or type(offset) is not int or not 0 <= offset <= 128:
            raise Failure()
        if topic is not None and type(topic) is not Topic:
            raise Failure()
        try:
            with self._transaction(context.household_id) as c:
                self._actor(c, context)
                return authorized_projection(c, self._repository, context.household_id, context.actor_id,
                                             context.membership_revision, limit=limit, offset=offset, topic=topic)
        except SQLAlchemyError:
            raise Failure() from None

    def history(self, context, kind, resource=None, *, limit=100):
        self._handle(context)
        if type(kind) is not Kind or type(limit) is not int or not 1 <= limit <= 100:
            raise Failure()
        with self._transaction(context.household_id) as c:
            self._actor(c, context)
            if not self._capability(context, kind, resource):
                raise Failure()
            key = 'membership' if resource is None else resource
            return tuple(dict(r) for r in c.execute(select(audit).where(audit.c.household_id == context.household_id,
                audit.c.kind == kind.value, audit.c.scope_key == key).order_by(audit.c.revision, audit.c.id).limit(limit)).mappings())


@contextmanager
def authorization_transaction(engine, household_id, *, progress=None):
    """Shared ordering: writer/household -> session/identity/member -> grants -> audit.

    All callers are internal; a household ID alone never establishes authorization.
    """
    with engine.begin() as c:
        if c.get_execution_options().get('isolation_level') == 'AUTOCOMMIT':
            raise Failure()
        if c.dialect.name == 'postgresql' and (c.get_isolation_level() != 'READ COMMITTED'
                or c.connection.driver_connection.autocommit):
            raise Failure()
        if c.dialect.name == 'sqlite':
            c.exec_driver_sql('BEGIN IMMEDIATE')
        q = select(household.c.id).where(household.c.id == household_id)
        if c.dialect.name == 'postgresql':
            q = q.with_for_update()
        if c.execute(q).scalar_one_or_none() is None:
            raise Failure()
        yield c
        if progress is not None:
            progress['commit_started'] = True


def effective_source_rights(c, household_id, person_id, membership_revision):
    """Current G2a fixture rights; caller already validated session/member under lock."""
    rights = c.execute(select(source_grant.c.source_account_id, source_grant.c.observations, source_grant.c.security)
        .join(source_account, (source_account.c.household_id == source_grant.c.household_id) &
              (source_account.c.id == source_grant.c.source_account_id))
        .where(source_grant.c.household_id == household_id, source_grant.c.person_id == person_id,
               source_grant.c.state == 'allowed', source_grant.c.membership_revision == membership_revision,
               source_account.c.provider == 'fixture', source_account.c.enabled == True)).mappings().all()
    return {r['source_account_id']: r for r in rights}


def authorized_projection(c, repository, household_id, person_id, membership_revision,
                          *, limit=20, offset=0, topic=None):
    """Existing G2a policy, shared after same-transaction current identity/member check.

    Not a client entrypoint; caller must hold authorization_transaction throughout.
    """
    permitted = effective_source_rights(c, household_id, person_id, membership_revision)
    lanes = {}
    for lane in ('observations', 'security'):
        unique = {}
        for record in repository.observations:
            if record.source_id not in permitted or not permitted[record.source_id][lane]:
                continue
            key = (household_id, record.source_id, record.object.value)
            fields = (record.generation, record.topic) if lane == 'observations' else (record.generation, record.topic, record.safety)
            if key in unique and unique[key] != fields:
                raise Failure()
            unique[key] = fields
        if len(unique) > 128:
            raise Failure()
        values = tuple((key, unique[key]) for key in sorted(unique)
            if (topic is None or unique[key][1] is topic) and
               (lane != 'security' or unique[key][2] is not Safety.CLEAR))
        lanes[lane] = values
    keys = set(c.execute(select(publication_grant.c.publication_key)
        .join(publication_scope, (publication_scope.c.household_id == publication_grant.c.household_id) &
              (publication_scope.c.publication_key == publication_grant.c.publication_key))
        .where(publication_grant.c.household_id == household_id,
               publication_grant.c.person_id == person_id, publication_grant.c.state == 'allowed',
               publication_grant.c.membership_revision == membership_revision,
               publication_scope.c.approved == True)).scalars())
    fields = {}
    for p in repository.publications:
        if p.key.value not in keys:
            continue
        if p.key in fields and fields[p.key] != p.step:
            raise Failure()
        fields[p.key] = p.step
    publications = tuple((key, fields[key]) for key in sorted(fields, key=lambda p: p.value))
    return Projection(lanes['observations'][offset:offset + limit], len(lanes['observations']),
        publications[offset:offset + limit], len(publications),
        lanes['security'][offset:offset + limit], len(lanes['security']))
