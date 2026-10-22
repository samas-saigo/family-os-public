"""T1 durable fictional domain; internal sessions, no API/UI/provider integration."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from enum import Enum
from hashlib import sha256
import json
import re
from uuid import uuid4

from sqlalchemy import select, insert, update, func, create_engine, case
from family_os._household_sessions import SessionService, SessionError
from family_os._household_authorization import authorization_transaction, effective_source_rights, Failure
from family_os.schema import (household_pending_item as pending, pending_member_right as right,
    pending_task_publication as plan, household_task as task, task_member_grant as grant,
    task_domain_event as event, household_membership as member, source_read_grant as source_grant)

CONTRACT_VERSION = 't1-fictional-household-domain-v1'
EDIT_PREVIEW_CONTRACT = 't1-fictional-edit-preview-v1'
PERSONAL_CONTRACT = 'i8-personal-v1'  # Frozen command fingerprint namespace.
PERSONAL_STATE_CONTRACT = 'i8-viewed-judgment-v2'


class TaskError(ValueError):
    def __init__(self): super().__init__('Household domain unavailable')


class Operation(Enum):
    REVIEW = 'review'
    DEFER = 'defer'
    NEEDS_INFORMATION = 'needs-information'
    NOT_APPLICABLE = 'not-applicable'
    RESUME = 'resume'
    ACCEPT = 'accept'
    EDIT = 'edit'


class PersonalReason(Enum):
    NOT_MY_RESPONSIBILITY = 'not-my-responsibility'
    NOT_PARTICIPATING = 'not-participating'
    PERSONAL_JUDGMENT = 'personal-judgment'


class Step(Enum):
    SCHOOL = 'school-session'
    HOME = 'home-visit'


class Responsibility(Enum):
    ALL = 'all'
    MINE = 'mine'
    OTHER = 'other'
    JOINT = 'joint'


class PendingState(Enum):
    ALL = 'all'
    UNHANDLED = 'unhandled'
    VIEWED = 'viewed'
    DEFERRED = 'deferred'
    NEEDS_INFORMATION = 'needs-information'
    NOT_APPLICABLE = 'not-applicable'


class Status(Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'


class Outcome(Enum):
    COMMITTED = 'COMMITTED'
    REPLAY = 'COMMITTED-replay'
    STALE = 'NOT_APPLIED-stale'
    CONFLICT = 'NOT_APPLIED-changed-intent'
    CANCELED = 'NOT_APPLIED-canceled'
    UNAVAILABLE = 'NOT_APPLIED-unavailable'
    NOT_APPLIED = 'NOT_APPLIED-verified-absence'
    UNKNOWN = 'UNKNOWN-reconciliation-required'


def _id(value):
    if type(value) is not str or re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value) is None: raise TaskError()


def _revision(value):
    if type(value) is not int or not 1 <= value <= 1000000: raise TaskError()


@dataclass(frozen=True)
class Binding:
    generation: int
    fingerprint: str
    definition: str

    def __post_init__(self):
        _revision(self.generation)
        if (type(self.fingerprint) is not str or re.fullmatch(r'[0-9a-f]{64}', self.fingerprint) is None
                or type(self.definition) is not str or re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}', self.definition) is None): raise TaskError()


@dataclass(frozen=True)
class Recipient:
    person_id: str
    plan_revision: int

    def __post_init__(self): _id(self.person_id); _revision(self.plan_revision)


@dataclass(frozen=True)
class EditRecipient:
    person_id: str
    revision: int
    membership_revision: int

    def __post_init__(self):
        _id(self.person_id); _revision(self.revision); _revision(self.membership_revision)


@dataclass(frozen=True)
class Command:
    operation: Operation
    resource_id: str
    expected_revision: int
    rights_revision: int
    request_id: str
    binding: Binding | None = None
    assignee: str | None = None
    status: Status | None = None
    approved_date: date | None = None
    recipients: tuple = ()
    edit_recipients: tuple = ()
    personal_reason: PersonalReason | None = None
    source_grant_revision: int | None = None

    def __post_init__(self):
        _id(self.resource_id); _id(self.request_id); _revision(self.expected_revision); _revision(self.rights_revision)
        if type(self.operation) is not Operation: raise TaskError()
        if self.operation in (Operation.NOT_APPLICABLE, Operation.RESUME):
            _revision(self.source_grant_revision)
            if ((self.operation is Operation.NOT_APPLICABLE and type(self.personal_reason) is not PersonalReason)
                    or (self.operation is Operation.RESUME and self.personal_reason is not None)): raise TaskError()
        elif self.personal_reason is not None or self.source_grant_revision is not None: raise TaskError()
        if self.assignee is not None: _id(self.assignee)
        if self.status is not None and type(self.status) is not Status: raise TaskError()
        if self.approved_date is not None and type(self.approved_date) is not date: raise TaskError()
        if type(self.recipients) is not tuple or any(type(r) is not Recipient for r in self.recipients): raise TaskError()
        if (type(self.edit_recipients) is not tuple or any(type(r) is not EditRecipient for r in self.edit_recipients)
                or len(self.edit_recipients)>2 or len({r.person_id for r in self.edit_recipients})!=len(self.edit_recipients)
                or (self.operation is not Operation.EDIT and self.edit_recipients)): raise TaskError()
        if self.operation is Operation.EDIT:
            if self.binding is not None or self.recipients or self.approved_date is not None or (self.assignee is None and self.status is None): raise TaskError()
        elif type(self.binding) is not Binding or self.status is not None: raise TaskError()
        elif self.operation is Operation.ACCEPT:
            if self.assignee is None or not 1 <= len(self.recipients) <= 2 or len({r.person_id for r in self.recipients}) != len(self.recipients): raise TaskError()
        elif self.assignee is not None or self.approved_date is not None or self.recipients: raise TaskError()

    @property
    def fingerprint(self):
        values = [self.operation.value, self.resource_id, self.expected_revision, self.rights_revision, self.request_id,
            None if self.binding is None else [self.binding.generation, self.binding.fingerprint, self.binding.definition],
            self.assignee, None if self.status is None else self.status.value,
            None if self.approved_date is None else self.approved_date.isoformat(),
            sorted([r.person_id, r.plan_revision] for r in self.recipients)]
        # Existing internal commands retain their exact historical intent hash.
        if self.edit_recipients:
            values.append([[r.person_id,r.revision,r.membership_revision] for r in self.edit_recipients])
        if self.operation in (Operation.NOT_APPLICABLE, Operation.RESUME):
            values.append([PERSONAL_CONTRACT, None if self.personal_reason is None else self.personal_reason.value, self.source_grant_revision])
        return sha256(json.dumps(values, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    revision: int | None = None
    task_id: str | None = None


@dataclass(frozen=True)
class PendingView:
    id: str
    revision: int
    rights_revision: int
    step: Step | None
    binding: Binding
    supported: bool
    safety: str | None
    supported_date: date | None
    reviewed: bool
    disposition: str
    can_review: bool
    can_accept: bool
    can_resume: bool = False


@dataclass(frozen=True)
class PersonalState:
    reviewed: bool
    disposition: str


@dataclass(frozen=True)
class TaskView:
    id: str
    step: Step
    assignee: str
    status: Status
    approved_date: date | None
    revision: int
    rights_revision: int
    can_edit: bool
    can_history: bool


@dataclass(frozen=True)
class Page:
    items: tuple
    total: int
    has_more: bool


@dataclass(frozen=True)
class ActionCard:
    item: TaskView | PendingView
    reason: str


@dataclass(frozen=True)
class ActionSection:
    items: tuple[ActionCard, ...]
    total: int


@dataclass(frozen=True)
class ActionHome:
    actor_id: str
    mine: ActionSection
    decisions: ActionSection
    followup: ActionSection
    collaboration: ActionSection


@dataclass(frozen=True)
class HistoryEntry:
    operation: Operation
    actor_id: str
    revision: int
    created_at: int
    step: Step | None = None
    assignee: str | None = None
    status: Status | None = None
    approved_date: date | None = None


class TaskService:
    """Fixed trusted household + existing synthetic session service, not authentication."""
    def __init__(self, sessions, household_id, *, synthetic_only=False):
        if synthetic_only is not True or type(sessions) is not SessionService: raise TaskError()
        _id(household_id)
        self._sessions, self._engine, self._household = sessions, sessions._engine, household_id

    @contextmanager
    def _transaction(self, bearer, *, engine=None, progress=None):
        with authorization_transaction(self._engine if engine is None else engine, self._household, progress=progress) as c:
            now = self._sessions._now()
            actor = self._sessions._validate(c, self._household, bearer, now)
            yield c, actor, now

    def _pending_query(self, c, actor):
        sources = effective_source_rights(c, self._household, actor['person_id'], actor['membership_revision'])
        readable = [key for key, scopes in sources.items() if scopes['observations']]
        security_sources = [key for key, scopes in sources.items() if scopes['security']]
        # Private risk assertions are not even selected for observation-only access.
        columns = [column for column in pending.c if column.name != 'safety']
        # An annotation belongs to its exact evidence, not a later/reverted version.
        own_bound_event = select(event.c.id).where(
            event.c.household_id == pending.c.household_id, event.c.pending_id == pending.c.id,
            event.c.actor_id == actor['person_id'], event.c.generation == pending.c.generation,
            event.c.evidence_fingerprint == pending.c.evidence_fingerprint,
            event.c.definition_version == pending.c.definition_version).correlate(pending)
        # Events are authoritative, including historical I8 judgments whose cache
        # predates the viewed implication. Never trust a raw/stale reviewed cache.
        reviewed = own_bound_event.where(event.c.operation.in_(('review', 'not-applicable'))).exists()
        disposition_operation = case((right.c.disposition == 'deferred', 'defer'), else_=right.c.disposition)
        disposition = own_bound_event.where(event.c.operation == disposition_operation).correlate(right).exists()
        q = select(*columns, case((pending.c.source_account_id.in_(security_sources),
            pending.c.safety), else_=None).label('safety'), right.c.revision.label('rights_revision'), right.c.can_review,
            right.c.can_publish, reviewed.label('reviewed'),
            case((disposition, right.c.disposition), else_='active').label('disposition')).join(right,
            (right.c.household_id == pending.c.household_id) & (right.c.pending_id == pending.c.id)).where(
            pending.c.household_id == self._household, pending.c.source_account_id.in_(readable),
            right.c.person_id == actor['person_id'], right.c.state == 'allowed', right.c.can_read == True,
            right.c.membership_revision == actor['membership_revision'],
            pending.c.kind.in_(('action','question','mixed-service')))
        return q, sources

    def _pending(self, c, actor, resource):
        q, sources = self._pending_query(c, actor)
        row = c.execute(q.where(pending.c.id == resource)).mappings().one_or_none()
        if row is None: raise TaskError()
        return row, sources[row['source_account_id']]

    def _task_query(self, actor):
        # Deliberately do NOT select private origin/evidence or join pending/source.
        return select(task.c.id, task.c.step, task.c.assignee_kind, task.c.assignee_id,
            task.c.status, task.c.approved_date, task.c.revision,
            grant.c.revision.label('rights_revision'), grant.c.can_edit, grant.c.can_history).join(grant,
            (grant.c.household_id == task.c.household_id) & (grant.c.task_id == task.c.id)).where(
            task.c.household_id == self._household, grant.c.person_id == actor['person_id'],
            grant.c.state == 'allowed', grant.c.can_read == True,
            grant.c.membership_revision == actor['membership_revision'])

    def _task(self, c, actor, resource):
        row = c.execute(self._task_query(actor).where(task.c.id == resource)).mappings().one_or_none()
        if row is None: raise TaskError()
        return row

    def _page(self, bearer, *, tasks, limit, offset, step, responsibility=Responsibility.ALL, pending_state=PendingState.ALL):
        try:
            if type(responsibility) is not Responsibility or (not tasks and responsibility is not Responsibility.ALL): raise TaskError()
            if type(pending_state) is not PendingState or (tasks and pending_state is not PendingState.ALL): raise TaskError()
            if type(limit) is not int or not 1 <= limit <= 20 or type(offset) is not int or not 0 <= offset <= 1000000 or (step is not None and type(step) is not Step): raise TaskError()
            with self._transaction(bearer) as (c, actor, now):
                q = self._task_query(actor) if tasks else self._pending_query(c, actor)[0].where(pending.c.resolution == 'unresolved')
                table = task if tasks else pending
                if step is not None: q = q.where(table.c.step == step.value)
                # Display predicates on the independently authorized task query, never grants.
                # The current actor comes only from SessionService in this transaction.
                if responsibility is Responsibility.JOINT:
                    q = q.where(task.c.assignee_kind == 'joint')
                elif responsibility in (Responsibility.MINE, Responsibility.OTHER):
                    q = q.where(task.c.assignee_kind == 'person')
                    q = q.where(task.c.assignee_id == actor['person_id'] if responsibility is Responsibility.MINE
                                else task.c.assignee_id != actor['person_id'])
                order = table.c.id
                if not tasks and pending_state is not PendingState.ALL:
                    # Effective own annotation is already exact-evidence-bound and access-filtered.
                    own = q.subquery()
                    q = select(own)
                    order = own.c.id
                    if pending_state in (PendingState.UNHANDLED, PendingState.VIEWED):
                        q = q.where(own.c.disposition == 'active', own.c.reviewed == (pending_state is PendingState.VIEWED))
                    else: q = q.where(own.c.disposition == pending_state.value)
                total = c.execute(select(func.count()).select_from(q.subquery())).scalar_one()
                rows = c.execute(q.order_by(order).limit(limit).offset(offset)).mappings().all()
                if tasks:
                    values = tuple(self._task_view(r) for r in rows)
                else:
                    sources = effective_source_rights(c, self._household, actor['person_id'], actor['membership_revision'])
                    values = tuple(self._pending_view(r,sources[r['source_account_id']]) for r in rows)
                self._sessions._touch(c, actor, now)
            return Page(values,total,offset+len(values)<total)
        except Exception: raise TaskError() from None

    @staticmethod
    def _pending_view(r,source):
        # One projection/candidate predicate shared by list and I6 detail reads.
        # A candidate flag never replaces prepare_acceptance/apply validation.
        return PendingView(r['id'],r['revision'],r['rights_revision'],None if r['step'] is None else Step(r['step']),
            Binding(r['generation'],r['evidence_fingerprint'],r['definition_version']),r['supported'],
            r['safety'] if source['security'] else None,r['supported_date'],r['reviewed'],r['disposition'],r['can_review'],
            bool(source['security'] and r['can_publish'] and r['supported'] and r['safety']=='clear'
                and r['kind'] in ('action','mixed-service')),
            bool(r['resolution']=='unresolved' and r['can_review'] and r['disposition'] in ('deferred','needs-information','not-applicable')))

    def pending(self, bearer, *, limit=20, offset=0, step=None, pending_state=PendingState.ALL):
        return self._page(bearer,tasks=False,limit=limit,offset=offset,step=step,pending_state=pending_state)

    def tasks(self, bearer, *, limit=20, offset=0, step=None, responsibility=Responsibility.ALL):
        return self._page(bearer,tasks=True,limit=limit,offset=offset,step=step,responsibility=responsibility)

    @staticmethod
    def _task_view(r):
        return TaskView(r['id'],Step(r['step']),'joint' if r['assignee_kind']=='joint' else r['assignee_id'],
            Status(r['status']),r['approved_date'],r['revision'],r['rights_revision'],r['can_edit'],r['can_history'])

    def action_home(self, bearer):
        """I9 read projection, not a new permission or persisted disposition.

        Current source/security rights qualify Pending review navigation. Published
        tasks deliberately remain independent of their private source. Every count
        and bounded sample uses the same household authorization transaction.
        """
        try:
            with self._transaction(bearer) as (c, actor, now):
                tasks = self._task_query(actor).where(task.c.status == 'pending').subquery()
                query, sources = self._pending_query(c, actor)
                ordinary = query.where(pending.c.resolution == 'unresolved',
                    pending.c.safety == 'clear', pending.c.source_account_id.in_(
                        [key for key, scopes in sources.items() if scopes['security']]),
                    right.c.can_review == True).subquery()

                def section(q, columns, *, is_task):
                    total = c.execute(select(func.count()).select_from(q.subquery())).scalar_one()
                    day = columns.approved_date if is_task else columns.supported_date
                    order = [day.is_(None), day]
                    if not is_task: order.append(columns.reviewed)
                    rows = c.execute(q.order_by(*order, columns.id).limit(3)).mappings().all()
                    values = []
                    for row in rows:
                        if is_task:
                            item = self._task_view(row)
                            reason = ('joint-task' if item.assignee == 'joint' else
                                      'my-task' if item.assignee == actor['person_id'] else 'other-task')
                        else:
                            item = self._pending_view(row, sources[row['source_account_id']])
                            reason = (item.disposition if item.disposition != 'active' else
                                      'viewed-undecided' if item.reviewed else 'undecided')
                        values.append(ActionCard(item, reason))
                    return ActionSection(tuple(values), total)

                mine = section(select(tasks).where((tasks.c.assignee_kind == 'joint') |
                    (tasks.c.assignee_id == actor['person_id'])), tasks.c, is_task=True)
                collaboration = section(select(tasks).where(tasks.c.assignee_kind == 'person',
                    tasks.c.assignee_id != actor['person_id']), tasks.c, is_task=True)
                decisions = section(select(ordinary).where(ordinary.c.disposition == 'active'),
                    ordinary.c, is_task=False)
                followup = section(select(ordinary).where(ordinary.c.disposition.in_(
                    ('deferred', 'needs-information'))), ordinary.c, is_task=False)
                self._sessions._touch(c, actor, now)
                return ActionHome(actor['person_id'], mine, decisions, followup, collaboration)
        except Exception:
            raise TaskError() from None

    def _access(self,c,actor,command):
        if command.operation is Operation.EDIT:
            row = self._task(c,actor,command.resource_id)
            if not row['can_edit']: raise TaskError()
            return row,None
        row, source = self._pending(c,actor,command.resource_id)
        if not row['can_publish' if command.operation is Operation.ACCEPT else 'can_review']: raise TaskError()
        if command.operation is Operation.ACCEPT and not source['security']: raise TaskError()
        return row,source

    def _result(self,c,actor,row,outcome):
        task_id = row['task_id']
        if task_id is not None:
            try: self._task(c,actor,task_id)
            except TaskError: task_id = None
        return Result(outcome,row['task_revision'] if row['operation']=='edit' else row['pending_revision'],task_id)

    def _prior(self,c,actor,command):
        prior = c.execute(select(event).where(event.c.household_id==self._household,
            event.c.actor_id==actor['person_id'],event.c.request_id==command.request_id)).mappings().one_or_none()
        if prior is None: return None
        if prior['intent_hash']!=command.fingerprint: return Result(Outcome.CONFLICT)
        expected_field='task_revision' if command.operation is Operation.EDIT else 'pending_revision'
        resource_field='task_id' if command.operation is Operation.EDIT else 'pending_id'
        if (prior['operation']!=command.operation.value or prior['outcome']!='committed'
                or prior[resource_field]!=command.resource_id or prior[expected_field]!=command.expected_revision+1):
            return Result(Outcome.UNKNOWN)
        if command.binding is not None and (prior['generation'],prior['evidence_fingerprint'],prior['definition_version']) != (
                command.binding.generation,command.binding.fingerprint,command.binding.definition): return Result(Outcome.UNKNOWN)
        return self._result(c,actor,prior,Outcome.REPLAY)

    def _assignment(self,c,assignee,recipients):
        if assignee=='joint': return 'joint',None
        if assignee not in recipients: raise TaskError()
        if c.execute(select(member.c.person_id).where(member.c.household_id==self._household,
            member.c.person_id==assignee,member.c.state=='allowed')).scalar_one_or_none() is None: raise TaskError()
        return 'person',assignee

    def _accept_plan(self,c,actor,row,command):
        if (row['resolution']!='unresolved' or not row['supported'] or row['safety']!='clear'
                or row['kind'] not in ('action','mixed-service') or row['step'] is None
                or (command.approved_date is not None and command.approved_date!=row['supported_date'])): raise TaskError()
        recipients = []
        for requested in command.recipients:
            recipient = c.execute(select(plan).join(member,(member.c.household_id==plan.c.household_id)&(member.c.person_id==plan.c.person_id)).where(
                plan.c.household_id==self._household,plan.c.pending_id==row['id'],plan.c.person_id==requested.person_id,
                plan.c.state=='allowed',plan.c.can_read==True,plan.c.revision==requested.plan_revision,
                member.c.state=='allowed',plan.c.membership_revision==member.c.revision)).mappings().one_or_none()
            if recipient is None: raise TaskError()
            recipients.append(recipient)
        ids = {r['person_id'] for r in recipients}
        if actor['person_id'] not in ids: raise TaskError()  # Narrow T1 publisher is an approved recipient too.
        kind, assignee = self._assignment(c,command.assignee,ids)
        return recipients,kind,assignee

    def prepare_acceptance(self,bearer,resource_id):
        """Internal, current immutable preview command; never grants or writes a decision."""
        try:
            _id(resource_id)
            with self._transaction(bearer) as (c,actor,now):
                row,source=self._pending(c,actor,resource_id)
                if not row['can_publish'] or not source['security']: raise TaskError()
                recipients=c.execute(select(plan.c.person_id,plan.c.revision).join(member,
                    (member.c.household_id==plan.c.household_id)&(member.c.person_id==plan.c.person_id)).where(
                    plan.c.household_id==self._household,plan.c.pending_id==resource_id,
                    plan.c.state=='allowed',plan.c.can_read==True,member.c.state=='allowed',
                    plan.c.membership_revision==member.c.revision).order_by(plan.c.person_id).limit(3)).all()
                if not 1<=len(recipients)<=2: raise TaskError()
                command=Command(Operation.ACCEPT,resource_id,row['revision'],row['rights_revision'],
                    'accept_'+uuid4().hex,Binding(row['generation'],row['evidence_fingerprint'],row['definition_version']),
                    assignee='joint' if len(recipients)==2 else actor['person_id'],approved_date=row['supported_date'],
                    recipients=tuple(Recipient(r.person_id,r.revision) for r in recipients))
                self._access(c,actor,command)
                self._accept_plan(c,actor,row,command)
                self._sessions._touch(c,actor,now)
                result=(Step(row['step']),command)
            return result
        except Exception: raise TaskError() from None

    def _source_revision(self, c, actor, row):
        # Version lookup only; _pending/_access already applies the existing G2a
        # effective rights query. No new source permission resolver.
        revision = c.execute(select(source_grant.c.revision).where(
            source_grant.c.household_id == self._household,
            source_grant.c.source_account_id == row['source_account_id'],
            source_grant.c.person_id == actor['person_id'], source_grant.c.state == 'allowed',
            source_grant.c.observations == True,
            source_grant.c.membership_revision == actor['membership_revision'])).scalar_one_or_none()
        _revision(revision)
        return revision

    @staticmethod
    def _personal_plan(row, command):
        if row['resolution'] != 'unresolved': raise TaskError()
        if command.operation is Operation.REVIEW: return dict(reviewed=True)
        if command.operation is Operation.DEFER: return dict(disposition='deferred')
        if command.operation is Operation.NEEDS_INFORMATION: return dict(disposition='needs-information')
        if command.operation is Operation.NOT_APPLICABLE: return dict(reviewed=True,disposition='not-applicable')
        if command.operation is Operation.RESUME and row['disposition'] in ('deferred','needs-information','not-applicable'):
            # row is the exact-evidence own projection, never the old raw cache.
            # Do not reset reviewed, mutate another adult or touch a Task.
            return dict(disposition='active')
        raise TaskError()

    def prepare_personal(self, bearer, resource_id, operation, expected_revision, *, reason=None):
        """One authorized snapshot/validator for I8 preview and original I7 calls."""
        try:
            _id(resource_id); _revision(expected_revision)
            if type(operation) is not Operation or operation not in (Operation.REVIEW, Operation.DEFER,
                    Operation.NEEDS_INFORMATION, Operation.NOT_APPLICABLE, Operation.RESUME): raise TaskError()
            with self._transaction(bearer) as (c,actor,now):
                row,source = self._pending(c,actor,resource_id)
                source_revision = self._source_revision(c,actor,row) if operation in (Operation.NOT_APPLICABLE,Operation.RESUME) else None
                command = Command(operation,resource_id,row['revision'],row['rights_revision'],
                    'review_'+uuid4().hex,Binding(row['generation'],row['evidence_fingerprint'],row['definition_version']),
                    personal_reason=reason,source_grant_revision=source_revision)
                self._access(c,actor,command)
                if row['revision']!=expected_revision: raise TaskError()
                annotation=self._personal_plan(row,command)
                self._sessions._touch(c,actor,now)
                result=(self._pending_view(row,source),command,PersonalState(annotation.get('reviewed',row['reviewed']),annotation.get('disposition',row['disposition'])))
            return result
        except Exception: raise TaskError() from None

    def prepare_review(self, bearer, resource_id, operation, expected_revision):
        # Preserve the old entrypoint/allowlist and command bytes.
        if type(operation) is not Operation or operation not in (Operation.REVIEW,Operation.DEFER,Operation.NEEDS_INFORMATION): raise TaskError()
        return self.prepare_personal(bearer,resource_id,operation,expected_revision)[1]

    def _edit_recipients(self,c,resource,*,bounded=False):
        q=select(grant.c.person_id,grant.c.revision,grant.c.membership_revision).join(member,
            (member.c.household_id==grant.c.household_id)&(member.c.person_id==grant.c.person_id)).where(
            grant.c.household_id==self._household,grant.c.task_id==resource,grant.c.state=='allowed',grant.c.can_read==True,
            member.c.state=='allowed',grant.c.membership_revision==member.c.revision).order_by(grant.c.person_id)
        rows=c.execute(q.limit(3) if bounded else q).all()
        return tuple(EditRecipient(*r) for r in rows)

    def _edit_plan(self,c,row,command,recipients):
        kind,assignee=(row['assignee_kind'],row['assignee_id']) if command.assignee is None else self._assignment(
            c,command.assignee,{r.person_id for r in recipients})
        return dict(step=row['step'],assignee_kind=kind,assignee_id=assignee,
            status=row['status'] if command.status is None else command.status.value,approved_date=row['approved_date'])

    def prepare_edits(self,bearer,resource_id):
        """Bounded server-held choices. Same edit validator as apply; no source access."""
        try:
            _id(resource_id)
            with self._transaction(bearer) as (c,actor,now):
                row=self._task(c,actor,resource_id)
                if not row['can_edit']: raise TaskError()
                recipients=self._edit_recipients(c,resource_id,bounded=True)
                if not 1<=len(recipients)<=2: raise TaskError()
                before=self._task_view(row)
                choices=[dict(assignee=r.person_id) for r in recipients if r.person_id!=before.assignee]
                if len(recipients)==2 and before.assignee!='joint': choices.append(dict(assignee='joint'))
                choices.append(dict(status=Status.COMPLETED if before.status is Status.PENDING else Status.PENDING))
                commands=[]
                for choice in choices:
                    command=Command(Operation.EDIT,resource_id,row['revision'],row['rights_revision'],
                        'edit_'+uuid4().hex,edit_recipients=recipients,**choice)
                    self._access(c,actor,command)
                    self._edit_plan(c,row,command,recipients)
                    commands.append(command)
                self._sessions._touch(c,actor,now)
                result=(before,tuple(commands))
            return result
        except Exception: raise TaskError() from None

    def _accept(self,c,actor,row,command,now,progress):
        recipients,kind,assignee=self._accept_plan(c,actor,row,command)
        tid='task_'+uuid4().hex
        progress['mutation']=True
        c.execute(insert(task).values(household_id=self._household,id=tid,pending_id=row['id'],step=row['step'],
            assignee_kind=kind,assignee_id=assignee,status='pending',approved_date=command.approved_date,
            revision=1,created_at=now,accepted_generation=row['generation'],accepted_fingerprint=row['evidence_fingerprint'],accepted_definition=row['definition_version']))
        for r in recipients:
            c.execute(insert(grant).values(household_id=self._household,task_id=tid,person_id=r['person_id'],state='allowed',
                can_read=r['can_read'],can_edit=r['can_edit'],can_history=r['can_history'],revision=1,membership_revision=r['membership_revision']))
        return tid,dict(step=row['step'],assignee_kind=kind,assignee_id=assignee,status='pending',approved_date=command.approved_date)

    def _apply(self,c,actor,command,now,progress):
        row,_ = self._access(c,actor,command)
        prior = self._prior(c,actor,command)
        if prior is not None: return prior
        if row['revision']!=command.expected_revision or row['rights_revision']!=command.rights_revision: return Result(Outcome.STALE)
        if row['revision']>=1000000: raise TaskError()
        values={};tid=None
        annotation=None
        if command.operation not in (Operation.ACCEPT,Operation.EDIT):
            if command.operation in (Operation.NOT_APPLICABLE,Operation.RESUME) and command.source_grant_revision!=self._source_revision(c,actor,row): return Result(Outcome.STALE)
            annotation=self._personal_plan(row,command)
            # Preserve effective viewed state, also refreshing a legacy cache;
            # DEFER/NEEDS_INFORMATION/RESUME do not independently prove viewing.
            annotation.setdefault('reviewed',row['reviewed'])
        if command.operation is not Operation.EDIT:
            if command.binding!=Binding(row['generation'],row['evidence_fingerprint'],row['definition_version']): return Result(Outcome.STALE)
            # Validate all acceptance permissions before the first write.
            if command.operation is Operation.ACCEPT:
                # All inserts/validation run in the same transaction; failure rolls back.
                tid,values=self._accept(c,actor,row,command,now,progress)
            if command.operation is not Operation.ACCEPT: progress['mutation']=True
            if c.execute(update(pending).where(pending.c.household_id==self._household,pending.c.id==row['id'],pending.c.revision==row['revision']).values(
                revision=row['revision']+1, resolution='accepted' if command.operation is Operation.ACCEPT else row['resolution'])).rowcount!=1: raise TaskError()
            if command.operation is not Operation.ACCEPT:
                if c.execute(update(right).where(right.c.household_id==self._household,right.c.pending_id==row['id'],right.c.person_id==actor['person_id'],
                        right.c.revision==row['rights_revision'],right.c.state=='allowed',right.c.membership_revision==actor['membership_revision']).values(**annotation)).rowcount!=1: raise TaskError()
            audit_values=dict(pending_id=row['id'],pending_revision=row['revision']+1,task_id=tid,task_revision=1 if tid else None,
                generation=row['generation'],evidence_fingerprint=row['evidence_fingerprint'],definition_version=row['definition_version'])
        else:
            recipients=self._edit_recipients(c,row['id'],bounded=bool(command.edit_recipients))
            if command.edit_recipients and command.edit_recipients!=recipients: return Result(Outcome.STALE)
            values=self._edit_plan(c,row,command,recipients)
            kind,assignee=values['assignee_kind'],values['assignee_id']
            progress['mutation']=True;tid=row['id']
            if c.execute(update(task).where(task.c.household_id==self._household,task.c.id==tid,task.c.revision==row['revision']).values(
                revision=row['revision']+1,assignee_kind=kind,assignee_id=assignee,status=values['status'])).rowcount!=1: raise TaskError()
            audit_values=dict(task_id=tid,task_revision=row['revision']+1)
        if command.operation is Operation.NOT_APPLICABLE: audit_values['personal_reason']=command.personal_reason.value
        c.execute(insert(event).values(id='event_'+uuid4().hex,household_id=self._household,actor_id=actor['person_id'],request_id=command.request_id,
            intent_hash=command.fingerprint,operation=command.operation.value,outcome='committed',created_at=now,**audit_values,**values))
        return Result(Outcome.COMMITTED,row['revision']+1,tid)

    def apply(self,bearer,command,*,confirm=False):
        if confirm is False: return Result(Outcome.CANCELED)
        if confirm is not True or type(command) is not Command: return Result(Outcome.UNAVAILABLE)
        progress={'mutation':False,'commit_started':False}
        try:
            with self._transaction(bearer,progress=progress) as (c,actor,now):
                result=self._apply(c,actor,command,now,progress)
                if result.outcome in (Outcome.COMMITTED,Outcome.REPLAY): self._sessions._touch(c,actor,now)
            return result
        except (TaskError,SessionError,Failure):
            return Result(Outcome.UNKNOWN if progress['mutation'] or progress['commit_started'] else Outcome.UNAVAILABLE)
        except Exception: return Result(Outcome.UNKNOWN)

    def history(self,bearer,resource_id,*,tasks,limit=100):
        try:
            _id(resource_id)
            if type(tasks) is not bool or type(limit) is not int or not 1<=limit<=100: raise TaskError()
            with self._transaction(bearer) as (c,actor,now):
                if tasks:
                    row=self._task(c,actor,resource_id)
                    if not row['can_history']: raise TaskError()
                    q=select(event.c.operation,event.c.actor_id,event.c.task_revision.label('revision'),event.c.created_at,
                        event.c.step,event.c.assignee_kind,event.c.assignee_id,event.c.status,event.c.approved_date).where(
                        event.c.household_id==self._household,event.c.task_id==resource_id).order_by(event.c.task_revision)
                else:
                    self._pending(c,actor,resource_id)
                    q=select(event.c.operation,event.c.actor_id,event.c.pending_revision.label('revision'),event.c.created_at).where(
                        event.c.household_id==self._household,event.c.pending_id==resource_id,event.c.actor_id==actor['person_id']).order_by(event.c.pending_revision)
                rows=c.execute(q.limit(limit)).mappings().all()
                values=tuple(HistoryEntry(Operation(r['operation']),r['actor_id'],r['revision'],r['created_at'],
                    None if not tasks else Step(r['step']),None if not tasks else ('joint' if r['assignee_kind']=='joint' else r['assignee_id']),
                    None if not tasks else Status(r['status']),None if not tasks else r['approved_date']) for r in rows)
                self._sessions._touch(c,actor,now)
            return values
        except Exception: raise TaskError() from None

    def verify_outcome(self,bearer,command):
        """Fresh same-primary physical connection; exact own request, never replays writes."""
        fresh=None
        try:
            if type(command) is not Command: raise TaskError()
            fresh=create_engine(self._engine.url,pool=self._engine.pool.recreate())
            fresh=fresh.execution_options(**self._engine.get_execution_options())
            with self._transaction(bearer,engine=fresh) as (c,actor,_):
                # Current operation access before even looking for historical request.
                self._access(c,actor,command)
                prior=self._prior(c,actor,command)
                result=Result(Outcome.NOT_APPLIED) if prior is None else Result(
                    Outcome.COMMITTED if prior.outcome is Outcome.REPLAY else prior.outcome,prior.revision,prior.task_id)
            return result
        except Exception: return Result(Outcome.UNKNOWN)
        finally:
            if fresh is not None:
                try: fresh.dispose()
                except Exception: pass
