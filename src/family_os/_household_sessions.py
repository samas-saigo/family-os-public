"""G2b2 internal durable sessions over G2a rights; no public login/provider path."""
from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
import json
import re
from secrets import token_urlsafe
from time import time
from uuid import uuid4

from sqlalchemy import select, insert, update, create_engine

from family_os._household_authorization import (authorization_transaction, authorized_projection,
    FixtureRepository, Topic, Failure as AuthorizationError)
from family_os._verified_identity import OfflineIdentityVerifier, IdentityError
from family_os.schema import (external_identity_binding as binding, household_membership as member,
    household_session as session, session_audit as audit)

CONTRACT_VERSION = 'g2b2-session-read-v1'
ABSOLUTE_SECONDS = 86400
IDLE_SECONDS = 1800


class SessionError(Exception):
    def __init__(self):
        super().__init__('Session access unavailable')


class Outcome(Enum):
    COMMITTED = 'COMMITTED'
    REPLAY = 'COMMITTED-replay-no-secret'
    NOT_APPLIED = 'NOT_APPLIED'
    UNAVAILABLE = 'ACCESS_UNAVAILABLE-no-historical-outcome'
    CONFLICT = 'NOT_APPLIED-changed-intent'
    STALE = 'NOT_APPLIED-stale-revision'
    UNKNOWN = 'UNKNOWN-reconciliation-required'


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    session_id: str | None = None
    revision: int | None = None
    bearer: str | None = field(default=None, repr=False)
    intent_hash: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class SessionState:
    session_id: str
    household_id: str
    person_id: str
    revision: int
    membership_revision: int
    binding_revision: int
    absolute_expiry: int
    idle_expiry: int


def _id(value):
    if type(value) is not str or re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value) is None:
        raise SessionError()


def _digest(bearer):
    if type(bearer) is not str or re.fullmatch(r'[A-Za-z0-9_-]{43}', bearer) is None:
        raise SessionError()
    return sha256(bearer.encode('ascii')).hexdigest()


def _intent(*values):
    return sha256(json.dumps(values, separators=(',',':'), ensure_ascii=True).encode()).hexdigest()


class SessionService:
    """Explicit engine, fixed fictional repository and verifier; never runtime discovery.

    Clock injection is trusted test setup only, never a client-supplied timestamp.
    There are no management, reviewer, provider operation or harness-context methods.
    """
    def __init__(self, engine, verifier, repository, *, synthetic_only=False, clock=time):
        if (synthetic_only is not True or type(verifier) is not OfflineIdentityVerifier
                or type(repository) is not FixtureRepository
                or engine.dialect.name not in ('sqlite','postgresql') or not callable(clock)):
            raise SessionError()
        self._engine, self._verifier, self._repository, self._clock = engine, verifier, repository, clock

    def _now(self):
        value = self._clock()
        if type(value) not in (int,float) or not 0 < value < 4102444800:
            raise SessionError()
        return int(value)

    def _identity(self, c, household_id, issuer, subject):
        row = c.execute(select(binding).where(binding.c.issuer == issuer,
            binding.c.subject == subject).limit(2)).mappings().all()
        if len(row) != 1:
            raise SessionError()
        row = row[0]
        if (row['issuer'] != issuer or row['subject'] != subject
                or row['household_id'] != household_id or row['state'] != 'allowed'):
            raise SessionError()
        current = c.execute(select(member).where(member.c.household_id == household_id,
            member.c.person_id == row['person_id'])).mappings().one_or_none()
        if current is None or current['state'] != 'allowed':
            raise SessionError()
        return row, current

    def _validate(self, c, household_id, bearer, now):
        row = c.execute(select(session).where(session.c.household_id == household_id,
            session.c.secret_hash == _digest(bearer))).mappings().one_or_none()
        if row is None:
            raise SessionError()
        b, m = self._identity(c, household_id, row['issuer'], row['subject'])
        if (row['person_id'] != b['person_id'] or row['binding_revision'] != b['revision']
                or row['membership_revision'] != m['revision'] or row['last_active'] > now
                or row['created_at'] > now or now >= row['absolute_expiry']
                or row['revoked'] or now >= row['idle_expiry']):
            raise SessionError()
        return row

    def _touch(self, c, row, now):
        revision = row['revision'] + 1
        if revision > 1000000:
            raise SessionError()
        if c.execute(update(session).where(session.c.id == row['id'],
                session.c.revision == row['revision'], session.c.revoked == False).values(
                last_active=now, idle_expiry=min(now+IDLE_SECONDS,row['absolute_expiry']),
                revision=revision)).rowcount != 1:
            raise SessionError()
        return SessionState(row['id'],row['household_id'],row['person_id'],revision,
            row['membership_revision'],row['binding_revision'],row['absolute_expiry'],
            min(now+IDLE_SECONDS,row['absolute_expiry']))

    def _prior(self, c, household_id, actor, request, fingerprint):
        previous = c.execute(select(audit).where(audit.c.household_id == household_id,
            audit.c.actor_id == actor, audit.c.request_id == request)).mappings().one_or_none()
        if previous is None:
            return None
        if previous['intent_hash'] != fingerprint:
            return Result(Outcome.CONFLICT)
        return Result(Outcome.REPLAY,previous['session_id'])  # Never recover a plaintext secret.

    def _audit(self, c, household_id, actor, request, fingerprint, event, sid, now, previous=None):
        c.execute(insert(audit).values(id=str(uuid4()),household_id=household_id,
            actor_id=actor,person_id=actor,session_id=sid,previous_session_id=previous,request_id=request,
            intent_hash=fingerprint,event=event,outcome='committed',created_at=now))

    def _new(self, c, household_id, identity, membership, now, *, absolute=None):
        bearer=token_urlsafe(32);sid=str(uuid4())
        expiry=now+ABSOLUTE_SECONDS if absolute is None else absolute
        c.execute(insert(session).values(id=sid,household_id=household_id,person_id=identity['person_id'],
            issuer=identity['issuer'],subject=identity['subject'],secret_hash=_digest(bearer),
            binding_revision=identity['revision'],membership_revision=membership['revision'],revision=1,
            revoked=False,created_at=now,last_active=now,absolute_expiry=expiry,
            idle_expiry=min(now+IDLE_SECONDS,expiry)))
        return Result(Outcome.COMMITTED,sid,1,bearer)

    def establish(self, proof, household_id, *, request_id):
        progress={'commit_started':False,'mutation':False}; fingerprint=None
        try:
            _id(household_id);_id(request_id)
            self._verifier._current(proof)
            with authorization_transaction(self._engine,household_id,progress=progress) as c:
                self._verifier._current(proof)
                now=self._now()
                b,m=self._identity(c,household_id,proof.issuer,proof.subject)
                fingerprint=_intent('establish',household_id,b['issuer'],b['subject'],b['revision'],m['revision'])
                result=self._prior(c,household_id,b['person_id'],request_id,fingerprint)
                if result is None:
                    progress['mutation']=True
                    result=self._new(c,household_id,b,m,now)
                    self._audit(c,household_id,b['person_id'],request_id,fingerprint,'establish',result.session_id,now)
            return replace(result, intent_hash=fingerprint)  # Only expose the secret after transaction exit/commit succeeded.
        except (SessionError, IdentityError, AuthorizationError):
            return Result(Outcome.UNKNOWN if progress['mutation'] or progress['commit_started'] else Outcome.UNAVAILABLE, intent_hash=fingerprint)
        except Exception:
            return Result(Outcome.UNKNOWN, intent_hash=fingerprint)  # Never infer rollback from a driver/exit exception.

    def resolve(self, bearer, household_id):
        return self._read(bearer,household_id,projection=False)

    def read(self, bearer, household_id, *, limit=20, offset=0, topic=None):
        return self._read(bearer,household_id,projection=True,limit=limit,offset=offset,topic=topic)

    def _read(self, bearer, household_id, *, projection, limit=20, offset=0, topic=None):
        try:
            _id(household_id);_digest(bearer)
            if (type(limit) is not int or not 1<=limit<=20 or type(offset) is not int
                    or not 0<=offset<=128 or (topic is not None and type(topic) is not Topic)):
                raise SessionError()
            with authorization_transaction(self._engine,household_id) as c:
                now=self._now();row=self._validate(c,household_id,bearer,now)
                result=(authorized_projection(c,self._repository,household_id,row['person_id'],
                    row['membership_revision'],limit=limit,offset=offset,topic=topic) if projection else None)
                state=self._touch(c,row,now)
            return result if projection else state
        except Exception:
            raise SessionError() from None  # No projection or definite state outcome on commit error.

    def logout(self, bearer, household_id, *, request_id, expected_revision):
        return self._change(bearer,household_id,request_id,expected_revision,rotate=False)

    def rotate(self, bearer, household_id, *, request_id, expected_revision):
        return self._change(bearer,household_id,request_id,expected_revision,rotate=True)

    def _change(self, bearer, household_id, request, expected, *, rotate):
        progress={'commit_started':False,'mutation':False}; fingerprint=None
        try:
            _id(household_id);_id(request);_digest(bearer)
            if type(expected) is not int or not 1<=expected<1000000:
                raise SessionError()
            with authorization_transaction(self._engine,household_id,progress=progress) as c:
                now=self._now();row=self._validate(c,household_id,bearer,now)
                op='rotate' if rotate else 'logout'
                fingerprint=_intent(op,row['id'],expected)
                result=self._prior(c,household_id,row['person_id'],request,fingerprint)
                if result is None:
                    if row['revoked'] or now>=row['idle_expiry']:
                        raise SessionError()
                    if row['revision'] != expected:
                        return Result(Outcome.STALE)
                    progress['mutation']=True
                    if c.execute(update(session).where(session.c.id==row['id'],session.c.revision==expected,
                            session.c.revoked==False).values(revoked=True,revision=expected+1)).rowcount!=1:
                        raise SessionError()
                    if rotate:
                        b,m=self._identity(c,household_id,row['issuer'],row['subject'])
                        result=self._new(c,household_id,b,m,now,absolute=row['absolute_expiry'])
                    else:
                        result=Result(Outcome.COMMITTED,row['id'],expected+1)
                    self._audit(c,household_id,row['person_id'],request,fingerprint,op,result.session_id,now,
                                previous=row['id'] if rotate else None)
            return replace(result, intent_hash=fingerprint)
        except (SessionError, IdentityError, AuthorizationError):
            return Result(Outcome.UNKNOWN if progress['mutation'] or progress['commit_started'] else Outcome.UNAVAILABLE, intent_hash=fingerprint)
        except Exception:
            return Result(Outcome.UNKNOWN, intent_hash=fingerprint)

    def revoke_all(self, proof, household_id, *, request_id):
        """Fresh independently verified identity may revoke only its own member's sessions."""
        progress={'commit_started':False,'mutation':False}; fingerprint=None
        try:
            _id(household_id);_id(request_id);self._verifier._current(proof)
            with authorization_transaction(self._engine,household_id,progress=progress) as c:
                self._verifier._current(proof)
                b,m=self._identity(c,household_id,proof.issuer,proof.subject);now=self._now()
                fingerprint=_intent('revoke_all',household_id,b['person_id'],b['revision'],m['revision'])
                result=self._prior(c,household_id,b['person_id'],request_id,fingerprint)
                if result is None:
                    progress['mutation']=True
                    c.execute(update(session).where(session.c.household_id==household_id,
                        session.c.person_id==b['person_id'],session.c.revoked==False).values(
                        revoked=True,revision=session.c.revision+1))
                    self._audit(c,household_id,b['person_id'],request_id,fingerprint,'revoke_all',None,now)
                    result=Result(Outcome.COMMITTED)
            return replace(result, intent_hash=fingerprint)
        except (SessionError, IdentityError, AuthorizationError):
            return Result(Outcome.UNKNOWN if progress['mutation'] or progress['commit_started'] else Outcome.UNAVAILABLE, intent_hash=fingerprint)
        except Exception:
            return Result(Outcome.UNKNOWN, intent_hash=fingerprint)

    def history(self, bearer, household_id, *, limit=100):
        """Only the currently authorized member's own protected lifecycle ledger."""
        try:
            _id(household_id)
            if type(limit) is not int or not 1<=limit<=100:
                raise SessionError()
            with authorization_transaction(self._engine,household_id) as c:
                now=self._now();row=self._validate(c,household_id,bearer,now)
                values=tuple(dict(x) for x in c.execute(select(audit.c.id,audit.c.actor_id,
                    audit.c.person_id,audit.c.session_id,audit.c.previous_session_id,audit.c.request_id,audit.c.event,
                    audit.c.outcome,audit.c.created_at).where(audit.c.household_id==household_id,
                    audit.c.person_id==row['person_id']).order_by(audit.c.created_at,audit.c.id).limit(limit)).mappings())
                self._touch(c,row,now)
            return values
        except Exception:
            raise SessionError() from None


    def verify_outcome(self, proof, household_id, *, request_id, intent_hash):
        """Read-only exact-request proof, new physical connection to the same primary.

        Never retries a mutation or recovers/returns a bearer. Current independently
        verified self identity is required even if the ambiguous rotation revoked it.
        """
        fresh=None
        try:
            _id(household_id);_id(request_id);self._verifier._current(proof)
            if type(intent_hash) is not str or re.fullmatch(r'[0-9a-f]{64}',intent_hash) is None:
                raise SessionError()
            fresh=create_engine(self._engine.url,pool=self._engine.pool.recreate())
            fresh=fresh.execution_options(**self._engine.get_execution_options())
            with authorization_transaction(fresh,household_id) as c:
                self._verifier._current(proof)
                b,m=self._identity(c,household_id,proof.issuer,proof.subject)
                row=c.execute(select(audit).where(audit.c.household_id==household_id,
                    audit.c.actor_id==b['person_id'],audit.c.request_id==request_id)).mappings().one_or_none()
                if row is None:
                    result=Result(Outcome.NOT_APPLIED)
                elif row['intent_hash']!=intent_hash:
                    result=Result(Outcome.CONFLICT)
                elif row['outcome']!='committed' or row['person_id']!=b['person_id']:
                    result=Result(Outcome.UNKNOWN)
                else:
                    result=Result(Outcome.COMMITTED,row['session_id'])
            return result
        except Exception:
            return Result(Outcome.UNKNOWN)
        finally:
            if fresh is not None:
                try:fresh.dispose()
                except Exception:pass
