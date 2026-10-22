"""New fictional Elm household; no provider/model data, real disposable SQL."""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from threading import Barrier, Event, current_thread
from time import time
import json

from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import jwt
import pytest
from sqlalchemy import insert, select, update, inspect, event as sql_event
from sqlalchemy.exc import IntegrityError

from family_os import _household_tasks as t, _household_authorization as a
from family_os import _household_sessions as s, _verified_identity as v
from family_os.registry import register
from family_os.schema import (household_membership as member, external_identity_binding as identity,
    source_read_grant as source, household_pending_item as pending, pending_member_right as right,
    pending_task_publication as plan, household_task as task, task_member_grant as grant,
    task_domain_event as event, household_session as sessions, session_audit, person)

ROOT=Path(__file__).parents[1];HOME='t1-elm';ISSUER='https://t1-elm.example.invalid'
FINGERPRINT=sha256(b'new-fiction-school-evidence-v1').hexdigest()
BINDING=t.Binding(1,FINGERPRINT,'fictional-policy-v1')
RECIPIENTS=(t.Recipient('t1-ada',1),t.Recipient('t1-bo',1))


@pytest.fixture(scope='module')
def key(): return rsa.generate_private_key(public_exponent=65537,key_size=2048)


@pytest.fixture
def setup(engine,key):
    register(engine,{'household':{'id':HOME,'name':'Fictional T1 Elm'},
        'people':[{'id':p,'display_name':'Fictional '+p} for p in ('t1-ada','t1-bo')],
        'source_accounts':[{'id':src,'provider':'fixture','owner_type':'person','owner_id':owner}
            for src,owner in [('t1-school-source','t1-bo'),('t1-private-source','t1-bo'),('t1-home-source','t1-ada')]]})
    register(engine,{'household':{'id':'t1-fern','name':'Fictional T1 Fern'},
        'people':[{'id':'t1-cy','display_name':'Fictional Cy'}],
        'source_accounts':[{'id':'t1-foreign-source','provider':'fixture','owner_type':'person','owner_id':'t1-cy'}]})
    with engine.begin() as c:
        c.execute(insert(member),[dict(household_id=h,person_id=p,state='allowed',revision=1)
            for h,p in [(HOME,'t1-ada'),(HOME,'t1-bo'),('t1-fern','t1-cy')]])
        c.execute(insert(identity),[dict(issuer=ISSUER,subject=p,household_id=h,person_id=p,state='allowed',revision=1)
            for h,p in [(HOME,'t1-ada'),(HOME,'t1-bo'),('t1-fern','t1-cy')]])
        c.execute(insert(source),[dict(household_id=HOME,source_account_id=src,person_id=p,state='allowed',
            observations=True,security=True,revision=1,membership_revision=1)
            for src in ('t1-school-source','t1-home-source') for p in ('t1-ada','t1-bo')])
        c.execute(insert(source).values(household_id=HOME,source_account_id='t1-private-source',person_id='t1-bo',
            state='allowed',observations=True,security=True,revision=1,membership_revision=1))
        rows=[('t1-school','t1-school-source','action',True,'clear'),
            ('t1-question','t1-home-source','question',False,'clear'),
            ('t1-promotion','t1-school-source','promotion',False,'clear'),
            ('t1-info','t1-school-source','information',False,'clear'),
            ('t1-risk','t1-school-source','action',True,'high-risk'),
            ('t1-unknown','t1-school-source','action',True,'unknown'),
            ('t1-mixed','t1-school-source','mixed-service',True,'clear'),
            ('t1-private','t1-private-source','action',True,'clear')]
        c.execute(insert(pending),[dict(household_id=HOME,id=id,source_account_id=src,kind=kind,step='school-session',supported=support,
            safety=safety,supported_date=date(2033,4,8) if id=='t1-school' else None,generation=1,
            evidence_fingerprint=FINGERPRINT,definition_version='fictional-policy-v1',resolution='unresolved',revision=1)
            for id,src,kind,support,safety in rows])
        # Independently provisioned capabilities/plans, not granted by login/ownership.
        c.execute(insert(right),[dict(household_id=HOME,pending_id=id,person_id=p,state='allowed',can_read=True,
            can_review=True,can_publish=True,revision=1,membership_revision=1,reviewed=False,disposition='active')
            for id,*_ in rows for p in ('t1-ada','t1-bo')])
        c.execute(insert(plan),[dict(household_id=HOME,pending_id=id,person_id=p,state='allowed',can_read=True,
            can_edit=True,can_history=True,revision=1,membership_revision=1) for id,*_ in rows for p in ('t1-ada','t1-bo')])
    verifier=v.OfflineIdentityVerifier(issuer=ISSUER,audience='t1-fictional-client',public_keys={
        't1-key':key.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo)})
    clock=[int(time())]
    service=s.SessionService(engine,verifier,a.FixtureRepository(),synthetic_only=True,clock=lambda:clock[0])
    bearers={}
    for p,hh in [('t1-ada',HOME),('t1-bo',HOME),('t1-cy','t1-fern')]:
        challenge=verifier.challenge();now=int(time())
        token=jwt.encode(dict(iss=ISSUER,sub=p,aud='t1-fictional-client',iat=now-1,nbf=now-1,exp=now+120,nonce=challenge.nonce),
            key,algorithm='RS256',headers={'kid':'t1-key'})
        result=service.establish(verifier.verify(token,challenge),hh,request_id='session-'+p)
        assert result.outcome is s.Outcome.COMMITTED
        bearers[p]=result.bearer
    return t.TaskService(service,HOME,synthetic_only=True),bearers,service,clock


def item(setup,id='t1-school',who='t1-ada'):
    svc,bearers,_,_=setup
    return next(x for x in svc.pending(bearers[who]).items if x.id==id)


def cmd(setup,op=t.Operation.ACCEPT,id='t1-school',who='t1-ada',request='accept-one',**changes):
    r=item(setup,id,who)
    values=dict(operation=op,resource_id=id,expected_revision=r.revision,rights_revision=r.rights_revision,request_id=request,binding=r.binding)
    if op is t.Operation.ACCEPT: values.update(assignee='joint',recipients=RECIPIENTS)
    values.update(changes)
    return t.Command(**values)


def accept(setup,who='t1-bo',id='t1-school',**changes):
    svc,bearers,_,_=setup
    result=svc.apply(bearers[who],cmd(setup,id=id,who=who,**changes),confirm=True)
    assert result.outcome is t.Outcome.COMMITTED and result.task_id
    return result.task_id


def edit(setup,task_id,who='t1-ada',request='edit-one',**changes):
    svc,bearers,_,_=setup
    row=next(r for r in svc.tasks(bearers[who]).items if r.id==task_id)
    return t.Command(t.Operation.EDIT,task_id,row.revision,row.rights_revision,request,**changes)


def rows(engine,table):
    with engine.connect() as c: return tuple(dict(r) for r in c.execute(select(table)).mappings())


def revoke(engine,table,who='t1-ada',**filters):
    # Privileged fictional test provisioning follows the same household lock ordering.
    with a.authorization_transaction(engine,HOME) as c:
        q=update(table).where(table.c.household_id==HOME,table.c.person_id==who)
        for key,value in filters.items(): q=q.where(table.c[key]==value)
        c.execute(q.values(revision=table.c.revision+1,**({'revoked':True} if table is sessions else {'state':'revoked'})))


def test_compact_household_walkthrough_persists_after_service_recreation(setup,engine):
    svc,bearers,sessions_service,_=setup
    assert svc.tasks(bearers['t1-ada']).total==0
    review=cmd(setup,t.Operation.REVIEW,request='review-school')
    assert svc.apply(bearers['t1-ada'],review,confirm=True).outcome is t.Outcome.COMMITTED
    assert item(setup).reviewed and not item(setup,who='t1-bo').reviewed
    assert svc.tasks(bearers['t1-bo']).total==0
    tid=accept(setup)
    assert not any(r.id=='t1-school' for r in svc.pending(bearers['t1-ada']).items)
    assert svc.tasks(bearers['t1-ada'])==svc.tasks(bearers['t1-bo'])
    change=edit(setup,tid,assignee='t1-ada',status=t.Status.COMPLETED)
    assert svc.apply(bearers['t1-ada'],change,confirm=True).outcome is t.Outcome.COMMITTED
    recreated=t.TaskService(sessions_service,HOME,synthetic_only=True)
    shared=recreated.tasks(bearers['t1-bo']).items[0]
    assert shared.assignee=='t1-ada' and shared.status is t.Status.COMPLETED and shared.revision==2
    history=recreated.history(bearers['t1-bo'],tid,tasks=True)
    assert [(e.operation,e.actor_id) for e in history]==[(t.Operation.ACCEPT,'t1-bo'),(t.Operation.EDIT,'t1-ada')]
    assert [e.revision for e in history]==[1,2] and len(rows(engine,task))==1


@pytest.mark.parametrize('operation,expected',[(t.Operation.REVIEW,'active'),(t.Operation.DEFER,'deferred'),(t.Operation.NEEDS_INFORMATION,'needs-information')])
def test_annotations_never_accept_or_resolve_and_private_history(setup,engine,operation,expected):
    svc,bearers,_,_=setup; command=cmd(setup,operation,request='annotate')
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.COMMITTED
    after=item(setup)
    assert after.disposition==expected and after.reviewed==(operation is t.Operation.REVIEW)
    assert svc.pending(bearers['t1-ada']).total==5
    assert svc.tasks(bearers['t1-ada']).total==0 and rows(engine,task)==()
    assert len(svc.history(bearers['t1-ada'],'t1-school',tasks=False))==1
    assert svc.history(bearers['t1-bo'],'t1-school',tasks=False)==()
    assert item(setup,who='t1-bo').disposition=='active'


def test_review_after_acceptance_cannot_revoke_shared_task(setup):
    svc,bearers,_,_=setup
    before=cmd(setup,t.Operation.REVIEW,request='later-review');tid=accept(setup)
    assert svc.apply(bearers['t1-ada'],before,confirm=True).outcome is t.Outcome.STALE
    fresh=replace(before,expected_revision=2)
    # I8 explicitly closes fresh personal decisions on accepted Pending too.
    assert svc.apply(bearers['t1-ada'],fresh,confirm=True).outcome is t.Outcome.UNAVAILABLE
    assert svc.history(bearers['t1-ada'],'t1-school',tasks=False)==()
    assert svc.tasks(bearers['t1-bo']).items[0].id==tid
    assert svc.tasks(bearers['t1-bo']).items[0].revision==1
    assert not any(r.id=='t1-school' for r in svc.pending(bearers['t1-ada']).items)


def test_information_and_promotion_never_create_pending_attention(setup):
    svc,bearers,_,_=setup
    ids={r.id for r in svc.pending(bearers['t1-ada']).items}
    assert 't1-promotion' not in ids and 't1-info' not in ids and 't1-mixed' in ids
    for id in ('t1-promotion','t1-info'):
        command=t.Command(t.Operation.ACCEPT,id,1,1,'try-'+id,BINDING,'joint',recipients=RECIPIENTS)
        assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.UNAVAILABLE
    assert svc.tasks(bearers['t1-ada']).total==0


@pytest.mark.parametrize('id',['t1-question','t1-risk','t1-unknown'])
def test_unsupported_or_unsafe_evidence_never_accepts(setup,engine,id):
    svc,bearers,_,_=setup; before=(rows(engine,task),rows(engine,event))
    assert not item(setup,id).can_accept
    assert svc.apply(bearers['t1-ada'],cmd(setup,id=id),confirm=True).outcome is t.Outcome.UNAVAILABLE
    assert (rows(engine,task),rows(engine,event))==before


def test_mixed_independently_supported_service_can_be_explicitly_accepted(setup):
    tid=accept(setup,id='t1-mixed')
    assert setup[0].tasks(setup[1]['t1-ada']).items[0].id==tid


@pytest.mark.parametrize('confirmation',[False,None,1,'save'])
def test_cancel_and_unconfirmed_inputs_write_nothing(setup,engine,confirmation):
    svc,bearers,_,_=setup;command=cmd(setup)
    before=tuple(rows(engine,table) for table in (pending,right,task,grant,event,sessions))
    result=svc.apply(bearers['t1-ada'],command,confirm=confirmation)
    assert result.outcome is (t.Outcome.CANCELED if confirmation is False else t.Outcome.UNAVAILABLE)
    assert tuple(rows(engine,table) for table in (pending,right,task,grant,event,sessions))==before


@pytest.mark.parametrize('field,value',[('generation',2),('evidence_fingerprint',sha256(b'new').hexdigest()),('definition_version','fictional-policy-v2')])
def test_changed_binding_stale_without_partial_writes(setup,engine,field,value):
    svc,bearers,_,_=setup; command=cmd(setup)
    with a.authorization_transaction(engine,HOME) as c:
        c.execute(update(pending).where(pending.c.id=='t1-school').values(**{field:value}))
    before=tuple(rows(engine,table) for table in (pending,right,task,grant,event))
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.STALE
    assert tuple(rows(engine,table) for table in (pending,right,task,grant,event))==before


def test_changed_then_reverted_evidence_requires_new_generation_and_intent(setup,engine):
    svc,bearers,_,_=setup; old=cmd(setup)
    for generation,fingerprint in [(2,sha256(b'changed').hexdigest()),(3,FINGERPRINT)]:
        with a.authorization_transaction(engine,HOME) as c:
            c.execute(update(pending).where(pending.c.id=='t1-school').values(generation=generation,evidence_fingerprint=fingerprint,revision=pending.c.revision+1))
    assert svc.apply(bearers['t1-ada'],old,confirm=True).outcome is t.Outcome.STALE
    tid=accept(setup)
    record=rows(engine,task)[0]
    assert record['accepted_generation']==3 and record['accepted_fingerprint']==FINGERPRINT


def test_optional_date_must_be_explicit_exact_supported_and_approved(setup,engine):
    svc,bearers,_,_=setup
    invalid=cmd(setup,approved_date=date(2033,4,9))
    assert svc.apply(bearers['t1-ada'],invalid,confirm=True).outcome is t.Outcome.UNAVAILABLE
    tid=accept(setup,approved_date=date(2033,4,8))
    assert svc.tasks(bearers['t1-ada']).items[0].approved_date==date(2033,4,8)
    accept(setup,id='t1-mixed',request='accept-no-date')
    assert next(r for r in svc.tasks(bearers['t1-ada']).items if r.id!=tid).approved_date is None


@pytest.mark.parametrize('permission',['can_review','can_publish'])
def test_source_read_and_membership_never_imply_domain_authority(setup,engine,permission):
    svc,bearers,_,_=setup
    with engine.begin() as c: c.execute(update(right).where(right.c.person_id=='t1-ada').values(**{permission:False}))
    op=t.Operation.REVIEW if permission=='can_review' else t.Operation.ACCEPT
    command=cmd(setup,op)
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.UNAVAILABLE
    assert rows(engine,event)==() and rows(engine,task)==()


@pytest.mark.parametrize('which',['source','review','publication','plan','membership','binding','session'])
def test_revocations_inside_current_authoritative_transaction(setup,engine,which):
    svc,bearers,_,_=setup;command=cmd(setup)
    table={'source':source,'review':right,'publication':right,'plan':plan,'membership':member,'binding':identity,'session':sessions}[which]
    if which=='review':
        command=cmd(setup,t.Operation.REVIEW)
    revoke(engine,table)
    result=svc.apply(bearers['t1-ada'],command,confirm=True)
    assert result.outcome is t.Outcome.UNAVAILABLE and rows(engine,task)==() and rows(engine,event)==()


def test_task_publication_and_edit_are_independent_of_source_and_private_changes(setup,engine):
    svc,bearers,_,_=setup;tid=accept(setup)
    before=svc.tasks(bearers['t1-ada']);history=svc.history(bearers['t1-ada'],tid,tasks=True)
    revoke(engine,source)
    with a.authorization_transaction(engine,HOME) as c:
        c.execute(update(pending).values(generation=2,evidence_fingerprint=sha256(b'private-changes').hexdigest(),safety='high-risk',revision=pending.c.revision+1))
    assert svc.pending(bearers['t1-ada']).total==0
    assert svc.tasks(bearers['t1-ada'])==before
    assert svc.history(bearers['t1-ada'],tid,tasks=True)==history
    change=edit(setup,tid,status=t.Status.COMPLETED)
    assert svc.apply(bearers['t1-ada'],change,confirm=True).outcome is t.Outcome.COMMITTED
    assert svc.tasks(bearers['t1-bo']).items[0].status is t.Status.COMPLETED
    serialized=json.dumps(asdict(svc.tasks(bearers['t1-ada'])),default=lambda x:x.value if hasattr(x,'value') else str(x))
    for forbidden in ('source_account_id','pending_id','fingerprint','generation','definition','t1-school-source','safety','evidence'):
        assert forbidden not in serialized


def test_task_visibility_revocation_removes_counts_search_and_history_independently(setup,engine):
    svc,bearers,_,_=setup;tid=accept(setup)
    revoke(engine,grant,task_id=tid)
    assert svc.tasks(bearers['t1-ada']).total==0 and svc.tasks(bearers['t1-ada'],step=t.Step.SCHOOL).total==0
    assert svc.tasks(bearers['t1-bo']).total==1 and svc.pending(bearers['t1-ada']).total==4
    with pytest.raises(t.TaskError): svc.history(bearers['t1-ada'],tid,tasks=True)
    assert svc.apply(bearers['t1-ada'],t.Command(t.Operation.EDIT,tid,1,1,'hidden-edit',status=t.Status.COMPLETED),confirm=True).outcome is t.Outcome.UNAVAILABLE


@pytest.mark.parametrize('field',['can_edit','can_history'])
def test_task_read_does_not_grant_edit_or_history(setup,engine,field):
    svc,bearers,_,_=setup;tid=accept(setup)
    with engine.begin() as c: c.execute(update(grant).where(grant.c.person_id=='t1-ada').values(**{field:False}))
    assert svc.tasks(bearers['t1-ada']).total==1
    if field=='can_edit':
        assert svc.apply(bearers['t1-ada'],edit(setup,tid,status=t.Status.COMPLETED),confirm=True).outcome is t.Outcome.UNAVAILABLE
    else:
        with pytest.raises(t.TaskError): svc.history(bearers['t1-ada'],tid,tasks=True)


def test_observation_only_scope_cannot_leak_security_or_acceptance_status(setup,engine):
    svc,bearers,_,_=setup
    with engine.begin() as c: c.execute(update(source).where(source.c.person_id=='t1-ada').values(security=False))
    before=svc.pending(bearers['t1-ada'])
    assert all(r.safety is None and not r.can_accept for r in before.items)
    with engine.begin() as c: c.execute(update(pending).values(safety='unknown'))
    assert svc.pending(bearers['t1-ada'])==before
    assert svc.apply(bearers['t1-ada'],cmd(setup),confirm=True).outcome is t.Outcome.UNAVAILABLE


def test_hidden_population_does_not_influence_pending_counts_pagination_errors(setup,engine):
    svc,bearers,_,_=setup;before=svc.pending(bearers['t1-ada'],limit=1,offset=1)
    base=rows(engine,pending)[-1]
    with engine.begin() as c:
        c.execute(insert(pending),[{**base,'id':'t1-hidden-'+str(n),'source_account_id':'t1-private-source'} for n in range(140)])
    assert svc.pending(bearers['t1-ada'],limit=1,offset=1)==before
    denied=svc.apply(bearers['t1-ada'],t.Command(t.Operation.ACCEPT,'t1-private',1,1,'try-hidden',BINDING,'joint',recipients=RECIPIENTS),confirm=True)
    missing=svc.apply(bearers['t1-ada'],t.Command(t.Operation.ACCEPT,'t1-missing',1,1,'try-missing',BINDING,'joint',recipients=RECIPIENTS),confirm=True)
    assert denied==missing==t.Result(t.Outcome.UNAVAILABLE)


def test_exact_replay_and_changed_intent_do_not_duplicate_task_or_audit(setup,engine):
    svc,bearers,_,_=setup;command=cmd(setup)
    first=svc.apply(bearers['t1-ada'],command,confirm=True)
    second=svc.apply(bearers['t1-ada'],command,confirm=True)
    assert first.outcome is t.Outcome.COMMITTED and second.outcome is t.Outcome.REPLAY and second.task_id==first.task_id
    assert len(rows(engine,task))==len(rows(engine,event))==1
    assert svc.apply(bearers['t1-ada'],replace(command,assignee='t1-bo'),confirm=True).outcome is t.Outcome.CONFLICT
    assert svc.apply(bearers['t1-ada'],replace(command,request_id='fresh-after-accepted',expected_revision=2),confirm=True).outcome is t.Outcome.UNAVAILABLE
    assert len(rows(engine,task))==len(rows(engine,event))==1


@pytest.mark.parametrize('operation',[t.Operation.REVIEW,t.Operation.DEFER,t.Operation.NEEDS_INFORMATION,t.Operation.ACCEPT])
def test_exact_idempotency_for_each_pending_operation(setup,engine,operation):
    svc,bearers,_,_=setup;command=cmd(setup,operation)
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.COMMITTED
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.REPLAY
    assert len(rows(engine,event))==1


@pytest.mark.parametrize('action',['accept','edit','duplicate'])
def test_real_concurrent_actions_have_no_lost_updates(setup,engine,action):
    svc,bearers,_,_=setup
    if action=='edit':
        tid=accept(setup)
        left=edit(setup,tid,request='left-edit',assignee='t1-ada')
        right_command=edit(setup,tid,who='t1-bo',request='right-edit',status=t.Status.COMPLETED)
    else:
        left=cmd(setup,request='same' if action=='duplicate' else 'left-accept')
        right_command=left if action=='duplicate' else cmd(setup,who='t1-bo',request='right-accept')
    barrier=Barrier(2)
    def run(command,who):
        barrier.wait(timeout=10)
        return svc.apply(bearers[who],command,confirm=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(run,left,'t1-ada')
        two=pool.submit(run,right_command,'t1-ada' if action=='duplicate' else 't1-bo')
        results=[one.result(timeout=20),two.result(timeout=20)]
    assert {r.outcome for r in results}=={t.Outcome.COMMITTED,t.Outcome.REPLAY if action=='duplicate' else t.Outcome.STALE}
    assert len(rows(engine,task))==1 and len(rows(engine,event))==(2 if action=='edit' else 1)


@pytest.mark.parametrize('failure',['before-write','before-audit','after-commit','unavailable-proof'])
def test_failure_and_unknown_outcomes_never_guess_commit_or_retry(setup,engine,monkeypatch,failure):
    svc,bearers,_,_=setup;command=cmd(setup)
    if failure=='before-write':
        monkeypatch.setattr(svc,'_accept',lambda *a,**k: (_ for _ in ()).throw(t.TaskError()))
        assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.UNAVAILABLE
        assert rows(engine,task)==rows(engine,event)==()
        return
    original_commit=engine.dialect.do_commit
    armed=True
    if failure=='before-audit':
        def fail(c,cursor,statement,params,ctx,many):
            if statement.startswith('INSERT INTO task_domain_event'): raise RuntimeError('private synthetic driver fault')
        sql_event.listen(engine,'before_cursor_execute',fail)
        try: result=svc.apply(bearers['t1-ada'],command,confirm=True)
        finally: sql_event.remove(engine,'before_cursor_execute',fail)
        assert result.outcome is t.Outcome.UNKNOWN and rows(engine,task)==rows(engine,event)==()
        assert svc.verify_outcome(bearers['t1-ada'],command).outcome is t.Outcome.NOT_APPLIED
        return
    def lost(connection):
        nonlocal armed
        original_commit(connection)
        if armed:
            armed=False
            raise RuntimeError('synthetic lost commit acknowledgment')
    monkeypatch.setattr(engine.dialect,'do_commit',lost)
    result=svc.apply(bearers['t1-ada'],command,confirm=True)
    assert result.outcome is t.Outcome.UNKNOWN and len(rows(engine,task))==len(rows(engine,event))==1
    if failure=='unavailable-proof':
        import family_os._household_tasks as module
        with monkeypatch.context() as m:
            m.setattr(module,'create_engine',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('private unavailable')))
            assert svc.verify_outcome(bearers['t1-ada'],command).outcome is t.Outcome.UNKNOWN
    verified=svc.verify_outcome(bearers['t1-ada'],command)
    assert verified.outcome is t.Outcome.COMMITTED and verified.task_id
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.REPLAY
    assert len(rows(engine,task))==len(rows(engine,event))==1


def test_revoked_or_other_household_session_cannot_read_or_verify(setup,engine):
    svc,bearers,_,_=setup;command=cmd(setup);accept(setup)
    for token in ('x'*43,bearers['t1-cy']):
        with pytest.raises(t.TaskError): svc.tasks(token)
        with pytest.raises(t.TaskError): svc.pending(token)
        assert svc.apply(token,command,confirm=True).outcome is t.Outcome.UNAVAILABLE
        assert svc.verify_outcome(token,command).outcome is t.Outcome.UNKNOWN
    revoke(engine,sessions)
    with pytest.raises(t.TaskError): svc.tasks(bearers['t1-ada'])
    assert svc.tasks(bearers['t1-bo']).total==1


@pytest.mark.parametrize('kind',['member','binding','idle','absolute'])
def test_current_session_epochs_expiry_and_reenrollment(setup,engine,kind):
    svc,bearers,_,clock=setup;accept(setup)
    if kind in ('idle','absolute'): clock[0]+=s.IDLE_SECONDS if kind=='idle' else s.ABSOLUTE_SECONDS
    else:
        table=member if kind=='member' else identity
        revoke(engine,table)
        with a.authorization_transaction(engine,HOME) as c:
            c.execute(update(table).where(table.c.person_id=='t1-ada').values(state='allowed',revision=3))
    with pytest.raises(t.TaskError): svc.tasks(bearers['t1-ada'])


@pytest.mark.parametrize('limit,offset',[(0,0),(21,0),(True,0),(1,-1),(1,1000001),(1,False)])
def test_bounded_queries(setup,limit,offset):
    with pytest.raises(t.TaskError): setup[0].pending(setup[1]['t1-ada'],limit=limit,offset=offset)
    with pytest.raises(t.TaskError): setup[0].tasks(setup[1]['t1-ada'],limit=limit,offset=offset)


def test_assignment_and_publication_require_exact_independent_plan(setup,engine):
    svc,bearers,_,_=setup
    for changes in (dict(assignee='t1-cy'),dict(recipients=(t.Recipient('t1-ada',2),t.Recipient('t1-bo',1))),
                    dict(recipients=(t.Recipient('t1-bo',1),)),dict(recipients=(t.Recipient('t1-ada',1),t.Recipient('t1-cy',1)))):
        assert svc.apply(bearers['t1-ada'],cmd(setup,**changes),confirm=True).outcome is t.Outcome.UNAVAILABLE
    assert rows(engine,task)==rows(engine,grant)==rows(engine,event)==()


def test_database_tenancy_uniqueness_and_migration_roundtrip(setup,engine):
    accept(setup)
    preserved=tuple(rows(engine,table) for table in (member,identity,source,sessions,session_audit,person))
    sample=rows(engine,right)[0]
    with pytest.raises(IntegrityError):
        with engine.begin() as c: c.execute(insert(right).values(**{**sample,'person_id':'t1-cy'}))
    with pytest.raises(IntegrityError):
        with engine.begin() as c: c.execute(insert(right).values(**sample))
    cfg=Config(str(ROOT/'alembic.ini'));command.check(cfg)
    command.downgrade(cfg,'c35b79a12e04')
    assert not {'household_task','household_pending_item','task_domain_event'}.intersection(inspect(engine).get_table_names())
    assert tuple(rows(engine,table) for table in (member,identity,source,sessions,session_audit,person))==preserved
    command.upgrade(cfg,'head');command.check(cfg)
    assert rows(engine,task)==rows(engine,pending)==rows(engine,event)==()
    assert tuple(rows(engine,table) for table in (member,identity,source,sessions,session_audit,person))==preserved


def test_no_provider_tables_network_wiring_or_secret_exposure(setup,engine,monkeypatch,caplog):
    svc,bearers,_,_=setup
    def checked(c,cursor,statement,params,ctx,many):
        assert not any(name in statement for name in ('raw_source_record','source_record','source_analysis','source_sync_state'))
    sql_event.listen(engine,'before_cursor_execute',checked)
    try:
        monkeypatch.setattr('socket.socket',lambda *a,**k: pytest.fail('no network/provider'))
        tid=accept(setup)
        assert svc.tasks(bearers['t1-bo']).total==1
    finally: sql_event.remove(engine,'before_cursor_execute',checked)
    serialized=repr(svc.tasks(bearers['t1-ada']))+repr(svc.history(bearers['t1-ada'],tid,tasks=True))+caplog.text
    assert not any(token in serialized for token in bearers.values())
    assert 'secret_hash' not in serialized and not caplog.text
    path=ROOT/'src/family_os/_household_tasks.py';code=path.read_text();tree=ast.parse(code)
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{alias.name for n in ast.walk(tree) if isinstance(n,ast.Import) for alias in n.names}
    assert imports <= {'contextlib','dataclasses','datetime','enum','hashlib','json','re','uuid','sqlalchemy',
        'family_os._household_sessions','family_os._household_authorization','family_os.schema'}
    for other in (ROOT/'src').rglob('*.py'):
        if other not in (path, ROOT/'src/family_os/_fictional_information.py', ROOT/'src/family_os/_pending_explanations.py'): assert '_household_tasks' not in other.read_text()
    for flag in (False,1,'true'):
        with pytest.raises(t.TaskError): t.TaskService(setup[2],HOME,synthetic_only=flag)


@pytest.mark.parametrize('kind',['task','source'])
def test_read_and_revocation_are_database_ordered_not_permanent_leases(setup,engine,kind):
    svc,bearers,_,_=setup
    accept(setup)
    entered=Event();release=Event();writer_attempted=Event()
    def hold(c,cursor,sql,parameters,ctx,many):
        marker='SELECT household_task.id' if kind=='task' else 'SELECT source_read_grant'
        if current_thread().name.startswith('t1-reader') and sql.startswith(marker):
            entered.set();assert release.wait(15)
        if current_thread().name.startswith('t1-writer') and ('BEGIN IMMEDIATE' in sql or ('FROM household ' in sql and 'FOR UPDATE' in sql)):
            writer_attempted.set()
    sql_event.listen(engine,'before_cursor_execute',hold)
    try:
        with ThreadPoolExecutor(max_workers=1,thread_name_prefix='t1-reader') as rp, ThreadPoolExecutor(max_workers=1,thread_name_prefix='t1-writer') as wp:
            reader=rp.submit(svc.tasks if kind=='task' else svc.pending,bearers['t1-ada'])
            assert entered.wait(10)
            writer=wp.submit(revoke,engine,grant if kind=='task' else source)
            assert writer_attempted.wait(10) and not writer.done()
            release.set()
            assert reader.result(timeout=15).total==(1 if kind=='task' else 4)
            writer.result(timeout=15)
        assert (svc.tasks if kind=='task' else svc.pending)(bearers['t1-ada']).total==0
        assert svc.tasks(bearers['t1-bo']).total==1
    finally:
        release.set();sql_event.remove(engine,'before_cursor_execute',hold)


def test_prepared_edit_after_revocation_and_changed_rights_revision_writes_nothing(setup,engine):
    svc,bearers,_,_=setup;tid=accept(setup)
    command=edit(setup,tid,status=t.Status.COMPLETED)
    before=rows(engine,task),rows(engine,event)
    with a.authorization_transaction(engine,HOME) as c:
        c.execute(update(grant).where(grant.c.person_id=='t1-ada').values(revision=2))
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.STALE
    revoke(engine,grant)
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.UNAVAILABLE
    assert (rows(engine,task),rows(engine,event))==before


def test_edit_request_replay_after_ack_loss_uses_one_history_revision(setup,engine,monkeypatch):
    svc,bearers,_,_=setup;tid=accept(setup)
    command=edit(setup,tid,status=t.Status.COMPLETED)
    original=engine.dialect.do_commit;armed=True
    def lost(connection):
        nonlocal armed
        original(connection)
        if armed:
            armed=False;raise RuntimeError('fictional acknowledgment loss')
    monkeypatch.setattr(engine.dialect,'do_commit',lost)
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.UNKNOWN
    assert svc.verify_outcome(bearers['t1-ada'],command).outcome is t.Outcome.COMMITTED
    assert svc.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.REPLAY
    assert svc.tasks(bearers['t1-bo']).items[0].revision==2
    assert len(rows(engine,event))==2


def test_known_revocation_prevents_reconciliation_from_disclosing_task_identity(setup,engine):
    svc,bearers,_,_=setup;command=cmd(setup)
    svc.apply(bearers['t1-ada'],command,confirm=True)
    revoke(engine,grant)
    # Historical acceptance remains true, but current independent visibility wins.
    assert svc.verify_outcome(bearers['t1-ada'],command)==t.Result(t.Outcome.COMMITTED,2,None)
    assert svc.apply(bearers['t1-ada'],command,confirm=True)==t.Result(t.Outcome.REPLAY,2,None)
    assert svc.tasks(bearers['t1-ada']).total==0


def test_authorized_backlog_remains_pageable_beyond_small_demo_caps(setup,engine):
    svc,bearers,_,_=setup
    prototype=next(r for r in rows(engine,pending) if r['id']=='t1-question')
    permission=next(r for r in rows(engine,right) if r['pending_id']=='t1-question' and r['person_id']=='t1-ada')
    with engine.begin() as c:
        c.execute(insert(pending),[{**prototype,'id':f't1-overflow-{n:03d}'} for n in range(150)])
        c.execute(insert(right),[{**permission,'pending_id':f't1-overflow-{n:03d}'} for n in range(150)])
    page=svc.pending(bearers['t1-ada'],offset=140)
    assert page.total==155 and len(page.items)==15 and not page.has_more


def test_private_review_and_deferral_do_not_transfer_to_changed_or_reverted_evidence(setup,engine):
    svc,bearers,_,_=setup
    for op in (t.Operation.REVIEW,t.Operation.DEFER):
        assert svc.apply(bearers['t1-ada'],cmd(setup,op,request=op.value),confirm=True).outcome is t.Outcome.COMMITTED
    assert item(setup).reviewed and item(setup).disposition=='deferred'
    for generation,fingerprint in ((2,sha256(b'new-fictional-evidence').hexdigest()),(3,FINGERPRINT)):
        with a.authorization_transaction(engine,HOME) as c:
            c.execute(update(pending).where(pending.c.id=='t1-school').values(
                generation=generation,evidence_fingerprint=fingerprint,revision=3+generation))
        current=item(setup)
        assert not current.reviewed and current.disposition=='active'
        assert svc.pending(bearers['t1-ada']).total==5
    assert len(svc.history(bearers['t1-ada'],'t1-school',tasks=False))==2
    assert len(rows(engine,event))==2
