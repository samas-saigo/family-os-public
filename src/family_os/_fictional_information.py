"""I5 trusted synthetic producer only; no provider, model, client or credential I/O."""
from dataclasses import dataclass
from datetime import date
from enum import Enum
from hashlib import sha256
import json
import re

from sqlalchemy import select, insert, update, create_engine
from family_os import _synthetic_routing as routing
from family_os._household_authorization import authorization_transaction, effective_source_rights
from family_os._household_tasks import TaskService, Step
from family_os.schema import (source_account, household_membership as member,
    household_pending_item as pending, pending_member_right as right,
    pending_task_publication as publication, fictional_information_revision as ledger)

CONTRACT_VERSION = 'i5-fictional-routing-v1-stagea-v2'
MAX_PLANS = 64


class InputError(ValueError):
    def __init__(self): super().__init__('Fictional information unavailable')


class Source(Enum):
    SHARED = 'i5-shared-source'
    CLARA = 'i5-clara-source'
    DEVON = 'i5-devon-source'


class Peer(Enum):
    CLARA = 'i2-clara'
    DEVON = 'i2-devon'


class DateBasis(Enum):
    NONE = 'none'
    ACTION = 'independent-action-date'
    PROMOTION = 'promotion-expiry'
    UNVERIFIED = 'unverified'


class Origin(Enum):
    FIXTURE = 'trusted-fictional-fixture'


class Outcome(Enum):
    COMMITTED = 'COMMITTED'
    REPLAY = 'COMMITTED-replay'
    REJECTED = 'NOT_APPLIED-rejected'
    CONFLICT = 'NOT_APPLIED-changed-intent'
    UNKNOWN = 'UNKNOWN-reconciliation-required'


def _hash(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def _record(value):
    if type(value) is not str or re.fullmatch(r'i5-[a-z0-9-]{1,32}',value) is None: raise InputError()


@dataclass(frozen=True)
class Information:
    source: Source
    record_id: str
    generation: int
    safety: routing.Safety
    business: routing.Business
    step: Step | None = None
    observed_date: date | None = None
    date_basis: DateBasis = DateBasis.NONE
    origin: Origin = Origin.FIXTURE
    definition: str = CONTRACT_VERSION

    def __post_init__(self):
        _record(self.record_id)
        if (type(self.source) is not Source or type(self.safety) is not routing.Safety
                or type(self.business) is not routing.Business or type(self.origin) is not Origin or type(self.date_basis) is not DateBasis
                or (self.observed_date is None)!=(self.date_basis is DateBasis.NONE)
                or type(self.generation) is not int or not 1<=self.generation<=1000
                or (self.step is not None and type(self.step) is not Step)
                or (self.observed_date is not None and (type(self.observed_date) is not date or not 2030<=self.observed_date.year<=2045))
                or type(self.definition) is not str or self.definition!=CONTRACT_VERSION): raise InputError()

    @property
    def evidence(self):
        b=self.business
        return dict(safety=self.safety.name,date_basis=self.date_basis.value,promotion=b.promotion,action=b.action.name,
            importance=b.importance.name,informational=b.informational,expiry=b.expiry.name,
            step=None if self.step is None else self.step.value,
            observed_date=None if self.observed_date is None else self.observed_date.isoformat())

    @property
    def fingerprint(self): return _hash(self.evidence)

    @property
    def intent(self):
        return _hash([self.source.value,self.record_id,self.generation,self.fingerprint,self.definition,self.origin.value])


@dataclass(frozen=True)
class Plan:
    """Independent fixture preapproval, never a classification result or client input."""
    source: Source
    record_id: str
    readers: tuple[Peer,...] = ()
    reviewers: tuple[Peer,...] = ()
    publishers: tuple[Peer,...] = ()
    recipients: tuple[Peer,...] = ()
    membership_epoch: int = 1

    def __post_init__(self):
        _record(self.record_id)
        groups=(self.readers,self.reviewers,self.publishers,self.recipients)
        if (type(self.source) is not Source or type(self.membership_epoch) is not int or self.membership_epoch!=1
                or any(type(g) is not tuple or len(g)>2 or any(type(p) is not Peer for p in g) or len(set(g))!=len(g) for g in groups)
                or not set(self.reviewers+self.publishers)<=set(self.readers)
                or not set(self.publishers)<=set(self.recipients)): raise InputError()

    @property
    def fingerprint(self):
        return _hash([self.source.value,self.record_id,self.membership_epoch,
            *[sorted(p.value for p in g) for g in (self.readers,self.reviewers,self.publishers,self.recipients)]])


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    destination: str | None = None
    effect: str | None = None
    pending_id: str | None = None


def classify(value):
    if type(value) is not Information or routing.CONTRACT_VERSION!='synthetic-routing-v2': raise InputError()
    # Stage A's Access is just a pure-routing probe. It grants NO T1 authority.
    snapshot=routing.Snapshot(generation=value.generation,business=value.business)
    case=routing.Case(snapshot,assessment=routing.Assessment(snapshot,routing.Policy.V1,value.safety))
    projection=routing.route(case,routing.Access())
    destinations={routing.Destination.PENDING:'pending',routing.Destination.SECURITY_HOLD:'security-held',
        routing.Destination.UNASSESSED:'unassessed',routing.Destination.INFORMATION:'information',
        routing.Destination.PROMOTIONS:'promotion',routing.Destination.ABSTAIN:'abstained'}
    # Simulated acceptance is deliberately NOT a T1 authority or routing result.
    if projection.destination not in destinations:raise InputError()
    return destinations[projection.destination]


def pending_identity(household,source,record_id):
    return 'i5_'+_hash([household,source.value,record_id])[:48]


class Coordinator:
    """Privileged fixture-only application boundary, never exposed to browser clients."""
    def __init__(self,tasks,plans,*,synthetic_only=False):
        if (synthetic_only is not True or type(tasks) is not TaskService or type(plans) is not tuple
                or len(plans)>MAX_PLANS or any(type(p) is not Plan for p in plans)
                or len({(p.source,p.record_id) for p in plans})!=len(plans)): raise InputError()
        self._unknown=None
        self._tasks=tasks
        self._plans={(p.source,p.record_id):p for p in plans}

    def _validated(self,value):
        if type(value) is not Information: raise InputError()
        plan=self._plans.get((value.source,value.record_id))
        if plan is None: raise InputError()
        return plan

    def _source(self,c,value):
        provider=c.execute(select(source_account.c.provider).where(source_account.c.household_id==self._tasks._household,
            source_account.c.id==value.source.value)).scalar_one_or_none()
        if provider!='fixture': raise InputError()

    def _ready(self,c,plan):
        for peer in set(plan.readers+plan.recipients):
            if c.execute(select(member.c.revision).where(member.c.household_id==self._tasks._household,
                member.c.person_id==peer.value,member.c.state=='allowed')).scalar_one_or_none()!=plan.membership_epoch: return False
        return any(effective_source_rights(c,self._tasks._household,p.value,plan.membership_epoch)
            .get(plan.source.value,{}).get('observations',False) for p in plan.readers)

    def _prior(self,c,value,plan):
        return c.execute(select(ledger).where(ledger.c.household_id==self._tasks._household,
            ledger.c.source_account_id==value.source.value,ledger.c.record_id==value.record_id,
            ledger.c.generation==value.generation)).mappings().one_or_none()

    @staticmethod
    def _receipt(row,value,plan):
        if row['intent_hash']!=value.intent or row['plan_hash']!=plan.fingerprint: return Result(Outcome.CONFLICT)
        return Result(Outcome.REPLAY,row['destination'],row['effect'],row['pending_id'])

    def _apply(self,c,value,plan,progress):
        self._source(c,value)
        prior=self._prior(c,value,plan)
        if prior is not None:return self._receipt(prior,value,plan)
        latest=c.execute(select(ledger).where(ledger.c.household_id==self._tasks._household,
            ledger.c.source_account_id==value.source.value,ledger.c.record_id==value.record_id)
            .order_by(ledger.c.generation.desc()).limit(1)).mappings().one_or_none()
        if value.generation!=(1 if latest is None else latest['generation']+1):return Result(Outcome.REJECTED)
        if latest is not None and latest['plan_hash']!=plan.fingerprint:return Result(Outcome.CONFLICT)
        destination=classify(value)
        pid=pending_identity(self._tasks._household,value.source,value.record_id)
        old=c.execute(select(pending).where(pending.c.household_id==self._tasks._household,pending.c.id==pid)).mappings().one_or_none()
        if old is not None and (old['source_account_id']!=value.source.value or latest is None or latest['pending_id']!=pid):raise InputError()
        if old is not None:
            bound=c.execute(select(ledger).where(ledger.c.household_id==self._tasks._household,
                ledger.c.source_account_id==value.source.value,ledger.c.record_id==value.record_id,
                ledger.c.pending_id==pid,ledger.c.effect.in_(('created','updated','blocked'))).order_by(ledger.c.generation.desc()).limit(1)).mappings().one_or_none()
            if bound is None or (old['generation'],old['evidence_fingerprint'],old['definition_version']) != (
                    bound['generation'],bound['evidence_fingerprint'],bound['definition_version']):raise InputError()
        effect='recorded';reference=None
        if old is not None and old['resolution']=='accepted':
            effect='accepted-history-only';reference=pid
        elif old is not None or destination=='pending':
            # Preserve independently supported business fields on an existing hold.
            # T1 separately gates acceptance on current safety/security rights.
            concrete=(value.business.action is routing.ActionEvidence.SUPPORTED and value.step is not None
                and bool(plan.publishers))
            kind=('mixed-service' if value.business.promotion else 'action') if concrete else 'question'
            if destination in ('information','promotion'):kind=destination
            fields=dict(kind=kind,step=value.step.value if concrete else None,supported=concrete,
                safety='clear' if value.safety is routing.Safety.SAFE_TO_ROUTE else 'high-risk' if value.safety in (routing.Safety.HIGH_RISK,routing.Safety.SUSPICIOUS) else 'unknown',
                supported_date=value.observed_date if concrete and value.date_basis is DateBasis.ACTION else None,generation=value.generation,
                evidence_fingerprint=value.fingerprint,definition_version=value.definition)
            ready=self._ready(c,plan)
            if not ready and old is not None:
                # Revocation blocks business processing, but cannot leave a reusable
                # old clearance. Bind the blocked generation and invalidate only;
                # never materialize its business fields or alter any grants.
                fields={k:fields[k] for k in ('generation','evidence_fingerprint','definition_version')}
                fields['safety']='unknown'
            if old is None and not ready:effect='blocked'
            else:
                progress['mutation']=True;reference=pid
                if old is None:
                    c.execute(insert(pending).values(household_id=self._tasks._household,id=pid,
                        source_account_id=value.source.value,resolution='unresolved',revision=1,**fields))
                    for peer in plan.readers:
                        c.execute(insert(right).values(household_id=self._tasks._household,pending_id=pid,person_id=peer.value,
                            state='allowed',can_read=True,can_review=peer in plan.reviewers,can_publish=peer in plan.publishers,
                            revision=1,membership_revision=plan.membership_epoch,reviewed=False,disposition='active'))
                    for peer in plan.recipients:
                        c.execute(insert(publication).values(household_id=self._tasks._household,pending_id=pid,person_id=peer.value,
                            state='allowed',can_read=True,can_edit=True,can_history=True,revision=1,membership_revision=plan.membership_epoch))
                    effect='created'
                else:
                    if old['generation']>=value.generation or old['revision']>=1000000:raise InputError()
                    changed=c.execute(update(pending).where(pending.c.household_id==self._tasks._household,
                        pending.c.id==pid,pending.c.revision==old['revision']).values(revision=old['revision']+1,**fields)).rowcount
                    if changed!=1:raise InputError()
                    effect='updated' if ready else 'blocked'
        progress['mutation']=True
        c.execute(insert(ledger).values(household_id=self._tasks._household,source_account_id=value.source.value,
            record_id=value.record_id,generation=value.generation,evidence_fingerprint=value.fingerprint,
            intent_hash=value.intent,plan_hash=plan.fingerprint,definition_version=value.definition,
            evidence_json=json.dumps(value.evidence,sort_keys=True,separators=(',',':')),origin=value.origin.value,
            destination=destination,effect=effect,pending_id=reference))
        return Result(Outcome.COMMITTED,destination,effect,reference)

    def process(self,value):
        if self._unknown is not None:return Result(Outcome.UNKNOWN)
        progress={'mutation':False,'commit_started':False}
        try:
            plan=self._validated(value)
            with authorization_transaction(self._tasks._engine,self._tasks._household,progress=progress) as c:
                result=self._apply(c,value,plan,progress)
            return result
        except InputError:
            if not progress['mutation'] and not progress['commit_started']:return Result(Outcome.REJECTED)
            self._unknown=value.intent;return Result(Outcome.UNKNOWN)
        except Exception:
            self._unknown=value.intent if type(value) is Information else None
            return Result(Outcome.UNKNOWN)

    def verify(self,value):
        """Exact read-only reconciliation on a fresh primary connection; never a replay."""
        fresh=None
        try:
            plan=self._validated(value)
            if self._unknown is not None and self._unknown!=value.intent:return Result(Outcome.UNKNOWN)
            engine=self._tasks._engine;url=engine.url
            # Only the owned file-SQLite / PostgreSQL fixture configurations are
            # supported. A recreated pool preserves the same connection creator
            # (including PG schema options), but opens independent connections.
            if url.get_backend_name() not in ('sqlite','postgresql'):return Result(Outcome.UNKNOWN)
            if url.get_backend_name()=='sqlite' and (not url.database or ':memory:' in url.database
                    or url.query.get('mode')=='memory'):return Result(Outcome.UNKNOWN)
            fresh=create_engine(url,pool=engine.pool.recreate())
            fresh=fresh.execution_options(**self._tasks._engine.get_execution_options())
            with authorization_transaction(fresh,self._tasks._household) as c:
                self._source(c,value);prior=self._prior(c,value,plan)
                if prior is None:return Result(Outcome.UNKNOWN)  # No absence/retry guarantee is invented.
                result=self._receipt(prior,value,plan)
            if result.outcome is Outcome.REPLAY:self._unknown=None
            return Result(Outcome.COMMITTED if result.outcome is Outcome.REPLAY else result.outcome,
                result.destination,result.effect,result.pending_id)
        except Exception:return Result(Outcome.UNKNOWN)
        finally:
            if fresh is not None:
                try:fresh.dispose()
                except Exception:pass
