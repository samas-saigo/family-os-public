"""Private Issue #61 experiment. Disposable enum-only synthetic stores, no live wiring."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
from tempfile import TemporaryDirectory
from uuid import uuid4

from sqlalchemy import (CheckConstraint, Column, ForeignKeyConstraint, Integer,
                        MetaData, Table, Text, UniqueConstraint, create_engine,
                        event, inspect, select, text, update)
from sqlalchemy.engine import Engine

CONTRACT = 'isolated-synthetic-review-v1'
ACCOUNTS = ('synthetic-account-A', 'synthetic-account-B')
EVENTS = tuple(f'synthetic-event-{n:02d}' for n in range(1, 5))
STEPS = ('refund', 'rebooking', 'preparation', 'attendance')
DISPOSITIONS = ('human_confirmed', 'human_rejected', 'needs_more_information', 'deferred')
RESOLVED = DISPOSITIONS[:2]
STAMPS = (
    ('synthetic-analyzer-v1', 'synthetic-rules-v1', 'synthetic-proposal-v1'),
    ('synthetic-analyzer-v2-probe', 'synthetic-rules-v1', 'synthetic-proposal-v1'),
    ('synthetic-analyzer-v1', 'synthetic-rules-v2-probe', 'synthetic-proposal-v1'),
    ('synthetic-analyzer-v1', 'synthetic-rules-v1', 'synthetic-proposal-v2-probe'),
)
REFS = ('specimen.step', 'specimen.status', 'specimen.condition')
# Explicit authored test proposals, not an interpreter/classifier or a corpus reader.
SPECIMENS = {
    'outstanding': ('required', 'supported'),
    'alternate_outstanding': ('required', 'supported'),
    'completed': ('not_required', 'supported'),
    'ambiguous': ('uncertain', 'missing'),
    'invalid': ('invalid', 'invalid'),
    'unsupported': ('uncertain', 'unsupported'),
    'conflicting': ('uncertain', 'conflicting'),
}
MAX_ENCOUNTERS = MAX_DECISIONS = 128
_CAPABILITY = object()


class ReviewCoreError(ValueError):
    def __init__(self):
        super().__init__('Isolated synthetic review rejected')


class StaleReviewError(ReviewCoreError):
    pass


class IdempotencyConflictError(ReviewCoreError):
    pass


class SyntheticStoreError(ReviewCoreError):
    pass


def _integer(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return sha256(_canonical(value).encode('utf-8')).hexdigest()


def _identity(account, event_id, step):
    if (type(account) is not str or account not in ACCOUNTS or type(event_id) is not str
            or event_id not in EVENTS or type(step) is not str or step not in STEPS):
        raise ReviewCoreError()
    return f'{account}:{event_id}:{step}'


@dataclass(frozen=True, repr=False)
class Observation:
    account: str
    event_id: str
    step: str
    snapshot: int
    specimen: str = 'outstanding'
    status: str = 'confirmed'
    condition: str = 'met'
    scope: str = 'step_only'
    stamp: tuple = STAMPS[0]

    def validate(self):
        _identity(self.account, self.event_id, self.step)
        if (not _integer(self.snapshot, 1, 1000) or type(self.specimen) is not str
                or self.specimen not in SPECIMENS or type(self.status) is not str
                or self.status not in ('confirmed', 'cancelled', 'tentative', 'unknown')
                or type(self.condition) is not str or self.condition not in ('met', 'unmet', 'unknown')
                or type(self.scope) is not str or self.scope not in ('step_only', 'conditional_step')
                or type(self.stamp) is not tuple or any(type(v) is not str for v in self.stamp)
                or self.stamp not in STAMPS):
            raise ReviewCoreError()
        return self

    @property
    def evidence(self):
        self.validate()
        return {'specimen': dict(step=self.step, status=self.status,
                                 condition=self.condition, token=self.specimen)}

    @property
    def proposal(self):
        self.validate()
        action, reason = SPECIMENS[self.specimen]
        if action in ('required', 'not_required') and (
                self.condition != 'met' or self.status in ('tentative', 'unknown')):
            action, reason = 'uncertain', 'unresolved_condition'
        return dict(action=action, reason=reason, refs=REFS, step=self.step,
                    condition=self.condition, scope=self.scope, stamp=self.stamp)

    @property
    def proposal_fingerprint(self):
        return _digest(self.proposal)

    @property
    def fingerprint(self):
        self.validate()
        return _digest(dict(observation=asdict(self), evidence=self.evidence, proposal=self.proposal))


@dataclass(frozen=True)
class Receipt:
    account: str
    event_id: str
    step: str
    token: str = field(repr=False)
    fingerprint: str
    proposal_fingerprint: str
    epoch: int
    revision: int
    visit: int
    disposition: str
    kind: str
    needs_review: bool
    visible: bool = field(default=True, init=False)
    authority: str = field(default='none', init=False)


@dataclass(frozen=True)
class Decision:
    revision: int
    epoch: int
    visit: int
    disposition: str
    observation: Observation = field(repr=False)
    fingerprint: str
    proposal_fingerprint: str
    authority: str = field(default='none', init=False)


@dataclass(frozen=True)
class SaveResult:
    decision: Decision
    replayed: bool
    applies_to_current: bool
    authority: str = field(default='none', init=False)


# Deliberately separate from production metadata and Alembic.
_metadata = MetaData()
_control = Table('sr61_control', _metadata,
    Column('id', Integer, primary_key=True), Column('contract', Text, nullable=False),
    Column('encounters', Integer, nullable=False), Column('decisions', Integer, nullable=False),
    CheckConstraint('id = 1 AND encounters BETWEEN 0 AND 128 AND decisions BETWEEN 0 AND 128'))
_state = Table('sr61_state', _metadata,
    Column('identity', Text, primary_key=True), Column('epoch', Integer, nullable=False),
    Column('visit', Integer, nullable=False), Column('revision', Integer, nullable=False),
    CheckConstraint('epoch >= 0 AND visit >= 0 AND revision >= 0'))
_observation = Table('sr61_observation', _metadata,
    Column('identity', Text, nullable=False), Column('visit', Integer, nullable=False),
    Column('epoch', Integer, nullable=False), Column('snapshot', Integer, nullable=False),
    Column('token', Text, nullable=False, unique=True), Column('fingerprint', Text, nullable=False),
    Column('proposal_fingerprint', Text, nullable=False), Column('payload', Text, nullable=False),
    ForeignKeyConstraint(['identity'], ['sr61_state.identity']),
    UniqueConstraint('identity', 'visit'), CheckConstraint('visit > 0 AND epoch > 0 AND snapshot BETWEEN 1 AND 1000'))
_decision = Table('sr61_decision', _metadata,
    Column('identity', Text, nullable=False), Column('revision', Integer, nullable=False),
    Column('visit', Integer, nullable=False), Column('disposition', Text, nullable=False),
    Column('request_id', Text, nullable=False, unique=True), Column('command_fingerprint', Text, nullable=False),
    ForeignKeyConstraint(['identity', 'visit'], ['sr61_observation.identity', 'sr61_observation.visit']),
    UniqueConstraint('identity', 'revision'), CheckConstraint('revision > 0'),
    CheckConstraint("disposition IN ('human_confirmed','human_rejected','needs_more_information','deferred')"))


def _immutability_guards(connection):
    if connection.dialect.name == 'postgresql':
        connection.execute(text("""CREATE FUNCTION sr61_immutable() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Immutable synthetic ledger'; END; $$"""))
    for table in (_observation, _decision):
        if connection.dialect.name == 'sqlite':
            for operation in ('UPDATE', 'DELETE'):
                connection.execute(text(f"CREATE TRIGGER {table.name}_{operation.lower()} BEFORE {operation} "
                    f"ON {table.name} BEGIN SELECT RAISE(ABORT, 'Immutable synthetic ledger'); END"))
        else:
            connection.execute(text(f'CREATE TRIGGER {table.name}_immutable BEFORE UPDATE OR DELETE '
                f'ON {table.name} FOR EACH ROW EXECUTE FUNCTION sr61_immutable()'))


class _DisposableStore:
    def __init__(self, engine, capability):
        if capability is not _CAPABILITY:
            raise SyntheticStoreError()
        self._engine = engine
        self._active = True

    def __repr__(self):
        return '<disposable synthetic review store>'

    def reconnect(self):
        """Reopen only this factory-owned store, never accept a new URL/path."""
        if not self._active:
            raise SyntheticStoreError()
        self._engine.dispose()


@contextmanager
def disposable_store(*, synthetic_only=False, postgres_test_engine=None):
    """Trusted synthetic harness only. Never reads DATABASE_URL or accepts file paths."""
    if synthetic_only is not True:
        raise SyntheticStoreError()
    temporary = None
    store = None
    initialized = False
    engine = None
    try:
        if postgres_test_engine is None:
            temporary = TemporaryDirectory(prefix='family-os-synthetic-review-')
            engine = create_engine(f'sqlite:///{temporary.name}/review.sqlite3', hide_parameters=True)
            @event.listens_for(engine, 'connect')
            def foreign_keys(connection, _):
                connection.execute('PRAGMA foreign_keys=ON')
        else:
            if type(postgres_test_engine) is not Engine:
                raise SyntheticStoreError()
            engine = postgres_test_engine
            options = engine.url.query.get('options', '')
            if (engine.dialect.name != 'postgresql' or engine.echo
                    or engine.pool.echo or not engine.hide_parameters or
                    type(options) is not str or not re.fullmatch(
                        r'-csearch_path=sr61_test_[0-9a-f]{32}', options)):
                raise SyntheticStoreError()
            schema = options.split('=')[1]
            with engine.connect() as connection:
                if (connection.scalar(text('SELECT current_schema()')) != schema
                        or inspect(connection).get_table_names(schema=schema)
                        or inspect(connection).get_view_names(schema=schema)):
                    raise SyntheticStoreError()
        with engine.begin() as connection:
            _metadata.create_all(connection)
            _immutability_guards(connection)
            connection.execute(_control.insert().values(id=1, contract=CONTRACT, encounters=0, decisions=0))
            connection.execute(_state.insert(), [dict(identity=_identity(a, e, s), epoch=0, visit=0, revision=0)
                for a in ACCOUNTS for e in EVENTS for s in STEPS])
        initialized = True
        store = _DisposableStore(engine, _CAPABILITY)
    except Exception:
        if engine is not None and postgres_test_engine is None:
            engine.dispose()
        if temporary is not None:
            temporary.cleanup()
        raise SyntheticStoreError() from None
    try:
        yield store
    finally:
        store._active = False
        try:
            if initialized and engine.dialect.name == 'postgresql':
                with engine.begin() as connection:
                    _metadata.drop_all(connection)
                    connection.execute(text('DROP FUNCTION sr61_immutable()'))
            engine.dispose()
            if temporary is not None:
                temporary.cleanup()
        except Exception:
            raise SyntheticStoreError() from None


def _load_observation(row):
    if type(row['payload']) is not str or len(row['payload']) > 4096:
        raise SyntheticStoreError()
    payload = json.loads(row['payload'])
    if type(payload) is not dict or set(payload) != set(Observation.__dataclass_fields__):
        raise SyntheticStoreError()
    if type(payload['stamp']) is not list or len(payload['stamp']) != 3:
        raise SyntheticStoreError()
    payload['stamp'] = tuple(payload['stamp'])
    obs = Observation(**payload).validate()
    if (obs.fingerprint != row['fingerprint'] or obs.proposal_fingerprint != row['proposal_fingerprint']
            or obs.snapshot != row['snapshot'] or _identity(obs.account, obs.event_id, obs.step) != row['identity']):
        raise SyntheticStoreError()
    return obs


def _decision_value(connection, row):
    original = connection.execute(select(_observation).where(
        _observation.c.identity == row['identity'], _observation.c.visit == row['visit'])).mappings().one()
    return Decision(row['revision'], original['epoch'], row['visit'], row['disposition'],
                    _load_observation(original), original['fingerprint'], original['proposal_fingerprint'])


class ReviewCore:
    def __init__(self, store=None, *, synthetic_only=False):
        if synthetic_only is not True or type(store) is not _DisposableStore or not store._active:
            raise SyntheticStoreError()
        self._store = store

    @contextmanager
    def _transaction(self, *, write=False):
        if not self._store._active:
            raise SyntheticStoreError()
        try:
            with self._store._engine.connect() as connection:
                try:
                    # One global writer reservation protects both per-identity CAS and store limits.
                    if write and connection.dialect.name == 'sqlite':
                        connection.exec_driver_sql('BEGIN IMMEDIATE')
                    elif write:
                        connection.begin()
                    query = select(_control).where(_control.c.id == 1)
                    if write and connection.dialect.name == 'postgresql':
                        query = query.with_for_update()
                    control = connection.execute(query).mappings().one()
                    if control['contract'] != CONTRACT:
                        raise SyntheticStoreError()
                    yield connection, control
                    if write:
                        connection.commit()
                except BaseException:
                    try:
                        connection.rollback()
                    except Exception:
                        # Preserve the primary failure; connection close remains a cleanup fallback.
                        pass
                    raise
        except ReviewCoreError:
            raise
        except Exception:
            raise SyntheticStoreError() from None

    def _current(self, connection, identity):
        state = connection.execute(select(_state).where(_state.c.identity == identity)).mappings().one()
        if state['visit'] == 0:
            return state, None
        current = connection.execute(select(_observation).where(
            _observation.c.identity == identity, _observation.c.visit == state['visit'])).mappings().one()
        _load_observation(current)
        return state, current

    def _receipt(self, connection, state, current, kind=None):
        obs = _load_observation(current)
        if kind is None:
            if state['visit'] == 1:
                kind = 'initial'
            else:
                previous = connection.execute(select(_observation.c.fingerprint).where(
                    _observation.c.identity == current['identity'],
                    _observation.c.visit == state['visit'] - 1)).scalar_one()
                kind = 'changed' if previous != current['fingerprint'] else 'unresolved_repeat'
        latest = connection.execute(select(_decision).where(_decision.c.identity == current['identity'],
            _decision.c.revision == state['revision'])).mappings().one_or_none()
        disposition = 'pending'
        if latest:
            decision = _decision_value(connection, latest)
            if decision.epoch == state['epoch'] and decision.fingerprint == current['fingerprint']:
                disposition = decision.disposition
        already = disposition in RESOLVED
        return Receipt(obs.account, obs.event_id, obs.step, current['token'], current['fingerprint'],
            current['proposal_fingerprint'], state['epoch'], state['revision'], state['visit'],
            disposition, 'already_reviewed' if already else kind, not already)

    def encounter(self, observation):
        if type(observation) is not Observation:
            raise ReviewCoreError()
        observation.validate()
        identity = _identity(observation.account, observation.event_id, observation.step)
        with self._transaction(write=True) as (connection, control):
            if control['encounters'] >= MAX_ENCOUNTERS:
                raise ReviewCoreError()
            state, previous = self._current(connection, identity)
            if previous and observation.snapshot < previous['snapshot']:
                raise StaleReviewError()
            changed = previous is not None and previous['fingerprint'] != observation.fingerprint
            epoch = state['epoch'] + int(previous is None or changed)
            visit = state['visit'] + 1
            current = dict(identity=identity, visit=visit, epoch=epoch, snapshot=observation.snapshot,
                token=uuid4().hex, fingerprint=observation.fingerprint,
                proposal_fingerprint=observation.proposal_fingerprint, payload=_canonical(asdict(observation)))
            connection.execute(_observation.insert().values(**current))
            connection.execute(update(_state).where(_state.c.identity == identity).values(epoch=epoch, visit=visit))
            connection.execute(update(_control).where(_control.c.id == 1).values(encounters=control['encounters'] + 1))
            new_state = dict(state, epoch=epoch, visit=visit)
            kind = 'initial' if previous is None else 'changed' if changed else 'unresolved_repeat'
            return self._receipt(connection, new_state, current, kind)

    def state(self, account, event_id, step):
        identity = _identity(account, event_id, step)
        with self._transaction() as (connection, _):
            state, current = self._current(connection, identity)
            return None if current is None else self._receipt(connection, state, current)

    def history(self, account, event_id, step):
        identity = _identity(account, event_id, step)
        with self._transaction() as (connection, _):
            rows = connection.execute(select(_decision).where(_decision.c.identity == identity)
                                      .order_by(_decision.c.revision)).mappings().all()
            if len(rows) > MAX_DECISIONS:
                raise SyntheticStoreError()
            return tuple(_decision_value(connection, row) for row in rows)

    def save(self, command):
        if type(command) is not dict or set(command) != {
                'account', 'event_id', 'step', 'receipt_token', 'expected_revision', 'epoch',
                'fingerprint', 'proposal_fingerprint', 'disposition', 'confirmation', 'request_id'}:
            raise ReviewCoreError()
        # Isolate the validated command from caller mutation while a DB lock is awaited.
        command = dict(command)
        identity = _identity(command['account'], command['event_id'], command['step'])
        if (type(command['confirmation']) is not str or command['confirmation'] != 'save'
                or type(command['disposition']) is not str or command['disposition'] not in DISPOSITIONS
                or not _integer(command['expected_revision'], 0, MAX_DECISIONS)
                or not _integer(command['epoch'], 1, MAX_ENCOUNTERS)
                or type(command['request_id']) is not str or not re.fullmatch(
                    r'synthetic-request-[a-z0-9_-]{1,32}', command['request_id'])
                or type(command['receipt_token']) is not str or not re.fullmatch(r'[0-9a-f]{32}', command['receipt_token'])
                or any(type(command[f]) is not str or not re.fullmatch(r'[0-9a-f]{64}', command[f])
                       for f in ('fingerprint', 'proposal_fingerprint'))):
            raise ReviewCoreError()
        command_fingerprint = _digest(command)
        with self._transaction(write=True) as (connection, control):
            previous = connection.execute(select(_decision).where(
                _decision.c.request_id == command['request_id'])).mappings().one_or_none()
            state, current = self._current(connection, identity)
            if previous:
                if previous['command_fingerprint'] != command_fingerprint:
                    raise IdempotencyConflictError()
                decision = _decision_value(connection, previous)
                applies = (current is not None and decision.epoch == state['epoch']
                    and decision.fingerprint == current['fingerprint'] and decision.revision == state['revision'])
                return SaveResult(decision, True, applies)
            if (current is None or command['receipt_token'] != current['token']
                    or command['fingerprint'] != current['fingerprint']
                    or command['proposal_fingerprint'] != current['proposal_fingerprint']
                    or command['epoch'] != state['epoch'] or command['expected_revision'] != state['revision']):
                raise StaleReviewError()
            obs = _load_observation(current)
            proposal = obs.proposal
            if command['disposition'] in RESOLVED and (
                    proposal['action'] not in ('required', 'not_required') or proposal['reason'] != 'supported'):
                raise ReviewCoreError()
            if control['decisions'] >= MAX_DECISIONS:
                raise ReviewCoreError()
            revision = state['revision'] + 1
            row = dict(identity=identity, revision=revision, visit=state['visit'],
                disposition=command['disposition'], request_id=command['request_id'],
                command_fingerprint=command_fingerprint)
            connection.execute(_decision.insert().values(**row))
            # Explicit CAS in addition to writer serialization; no decision history UPDATE.
            changed = connection.execute(update(_state).where(_state.c.identity == identity,
                _state.c.revision == command['expected_revision'], _state.c.visit == state['visit'])
                .values(revision=revision))
            if changed.rowcount != 1:
                raise StaleReviewError()
            connection.execute(update(_control).where(_control.c.id == 1).values(decisions=control['decisions'] + 1))
            return SaveResult(_decision_value(connection, row), False, True)
