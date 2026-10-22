"""I8 own decisions on real disposable SQL; no real data or provider/model access."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from threading import Barrier
import json
import pytest
from sqlalchemy import select, update, event as sql_event
from sqlalchemy.exc import IntegrityError
from test_household_tasks import setup,key,cmd,item,accept,rows,revoke,HOME,FINGERPRINT,BINDING,t,event,right,pending,source,task,grant,member,sessions

OPS=(t.Operation.NOT_APPLICABLE,t.Operation.RESUME)


def prepared(setup,operation=t.Operation.NOT_APPLICABLE,who='t1-ada',id='t1-school',reason=t.PersonalReason.NOT_MY_RESPONSIBILITY):
    svc,bearers,_,_=setup;r=item(setup,id,who)
    return svc.prepare_personal(bearers[who],id,operation,r.revision,reason=reason if operation is t.Operation.NOT_APPLICABLE else None)[1]


def apply(setup,command,who='t1-ada'):
    return setup[0].apply(setup[1][who],command,confirm=True)


@pytest.mark.parametrize('reason',list(t.PersonalReason))
@pytest.mark.parametrize('viewed',[False,True])
def test_not_applicable_own_state_reason_and_resume(setup,engine,reason,viewed):
    svc,bearers,_,_=setup
    if viewed:assert apply(setup,cmd(setup,t.Operation.REVIEW)).outcome is t.Outcome.COMMITTED
    before=rows(engine,task),rows(engine,grant)
    totals={who:svc.pending(bearers[who]).total for who in ('t1-ada','t1-bo')}
    command=prepared(setup,reason=reason);assert apply(setup,command).outcome is t.Outcome.COMMITTED
    r=item(setup);assert r.disposition=='not-applicable' and r.reviewed is True
    peer=item(setup,who='t1-bo');assert not peer.reviewed and peer.disposition=='active'
    own=svc.pending(bearers['t1-ada'],pending_state=t.PendingState.NOT_APPLICABLE)
    assert [r.id for r in own.items]==['t1-school']
    assert svc.pending(bearers['t1-bo'],pending_state=t.PendingState.NOT_APPLICABLE).total==0
    assert {who:svc.pending(bearers[who]).total for who in totals}==totals
    events=rows(engine,event);last=events[-1];assert last['personal_reason']==reason.value and last['actor_id']=='t1-ada'
    assert not svc.history(bearers['t1-bo'],'t1-school',tasks=False)
    resume=prepared(setup,t.Operation.RESUME);assert apply(setup,resume).outcome is t.Outcome.COMMITTED
    r=item(setup);assert r.disposition=='active' and r.reviewed is True
    assert apply(setup,resume).outcome is t.Outcome.REPLAY
    assert svc.verify_outcome(bearers['t1-ada'],resume).outcome is t.Outcome.COMMITTED
    assert len(rows(engine,event))==len(events)+1
    assert rows(engine,task)==before[0] and rows(engine,grant)==before[1]
    with pytest.raises(t.TaskError):prepared(setup,t.Operation.RESUME)


@pytest.mark.parametrize('operation',[t.Operation.DEFER,t.Operation.NEEDS_INFORMATION])
@pytest.mark.parametrize('viewed',[False,True])
def test_resume_legacy_dispositions_preserves_review_and_history(setup,engine,operation,viewed):
    if viewed:apply(setup,cmd(setup,t.Operation.REVIEW,request='initial-review'))
    apply(setup,cmd(setup,operation));before=rows(engine,event)
    assert apply(setup,prepared(setup,t.Operation.RESUME)).outcome is t.Outcome.COMMITTED
    assert item(setup).reviewed==viewed and item(setup).disposition=='active'
    assert rows(engine,event)[:-1]==before


@pytest.mark.parametrize('field,value',[('generation',2),('evidence_fingerprint','f'*64),('definition_version','fictional-policy-v2')])
def test_exact_evidence_not_raw_cache_controls_resume(setup,engine,field,value):
    apply(setup,prepared(setup))
    with engine.begin() as c:c.execute(update(pending).where(pending.c.id=='t1-school').values(**{field:value},revision=pending.c.revision+1))
    assert item(setup).disposition=='active' and not item(setup).reviewed
    with pytest.raises(t.TaskError):prepared(setup,t.Operation.RESUME)
    assert next(r for r in rows(engine,right) if r['pending_id']=='t1-school' and r['person_id']=='t1-ada')['disposition']=='not-applicable'


def test_change_revert_and_historical_replay_do_not_restore_old_state(setup,engine):
    command=prepared(setup);apply(setup,command)
    for generation,fingerprint in [(2,'f'*64),(3,FINGERPRINT)]:
        with engine.begin() as c:c.execute(update(pending).where(pending.c.id=='t1-school').values(generation=generation,evidence_fingerprint=fingerprint,revision=pending.c.revision+1))
        assert apply(setup,command).outcome is t.Outcome.REPLAY
        assert item(setup).disposition=='active' and not item(setup).reviewed
        with pytest.raises(t.TaskError):prepared(setup,t.Operation.RESUME)
    assert len(rows(engine,event))==1


@pytest.mark.parametrize('committed',[False,True])
def test_source_revoke_regrant_invalidates_unexecuted_not_historical_request(setup,engine,committed):
    command=prepared(setup)
    if committed:assert apply(setup,command).outcome is t.Outcome.COMMITTED
    revoke(engine,source,source_account_id='t1-school-source')
    assert setup[0].verify_outcome(setup[1]['t1-ada'],command).outcome is t.Outcome.UNKNOWN
    with engine.begin() as c:c.execute(update(source).where(source.c.household_id==HOME,source.c.person_id=='t1-ada',source.c.source_account_id=='t1-school-source').values(state='allowed',revision=source.c.revision+1))
    assert apply(setup,command).outcome is (t.Outcome.REPLAY if committed else t.Outcome.STALE)
    assert len(rows(engine,event))==int(committed)
    if not committed:assert apply(setup,prepared(setup)).outcome is t.Outcome.COMMITTED


@pytest.mark.parametrize('target',[source,right,member,sessions])
def test_revoked_authority_blocks_new_writes_and_hidden_history(setup,engine,target):
    command=prepared(setup);revoke(engine,target)
    assert apply(setup,command).outcome is t.Outcome.UNAVAILABLE
    assert setup[0].verify_outcome(setup[1]['t1-ada'],command).outcome is t.Outcome.UNKNOWN
    assert not rows(engine,event)


@pytest.mark.parametrize('operation',OPS)
def test_new_decisions_after_acceptance_rejected_but_old_commit_replay_safe(setup,engine,operation):
    old=prepared(setup);apply(setup,old)
    tid=accept(setup);before=rows(engine,event),rows(engine,task)
    assert apply(setup,old).outcome is t.Outcome.REPLAY
    with pytest.raises(t.TaskError):setup[0].prepare_personal(setup[1]['t1-ada'],'t1-school',operation,3,reason=old.personal_reason if operation is t.Operation.NOT_APPLICABLE else None)
    forced=replace(old,operation=operation,request_id='forced-after-accept',expected_revision=3,personal_reason=old.personal_reason if operation is t.Operation.NOT_APPLICABLE else None)
    assert apply(setup,forced).outcome is t.Outcome.UNAVAILABLE
    assert (rows(engine,event),rows(engine,task))==before
    assert rows(engine,task)[0]['id']==tid


def test_not_applicable_never_blocks_independent_acceptance_or_clears_risk(setup,engine):
    for id in ['t1-risk','t1-unknown','t1-question']:
        assert apply(setup,prepared(setup,id=id)).outcome is t.Outcome.COMMITTED
        assert not item(setup,id).can_accept
    apply(setup,prepared(setup));assert item(setup).can_accept
    accept(setup);assert len(rows(engine,task))==1
    assert all(r['personal_reason'] is None for r in rows(engine,event) if r['task_id'] is not None)


def test_same_request_reason_change_is_conflict(setup,engine):
    command=prepared(setup);apply(setup,command);before=rows(engine,event)
    assert apply(setup,replace(command,personal_reason=t.PersonalReason.NOT_PARTICIPATING)).outcome is t.Outcome.CONFLICT
    assert rows(engine,event)==before


@pytest.mark.parametrize('same',[False,True])
def test_concurrent_peer_or_duplicate_requests(setup,engine,same):
    first=prepared(setup);second=first if same else prepared(setup,who='t1-bo')
    barrier=Barrier(2)
    def run(pair):
        who,command=pair;barrier.wait();return apply(setup,command,who).outcome
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,[('t1-ada',first),('t1-ada' if same else 't1-bo',second)]))
    assert sorted(r.value for r in results)==sorted(r.value for r in [t.Outcome.COMMITTED,t.Outcome.REPLAY if same else t.Outcome.STALE])
    assert len(rows(engine,event))==1


def test_rollback_and_lost_commit_acknowledgment(setup,engine,monkeypatch):
    svc,bearers,_,_=setup;command=prepared(setup);before=rows(engine,right),rows(engine,pending)
    def fail(c,cursor,sql,params,context,many):
        if sql.startswith('INSERT INTO task_domain_event'):raise RuntimeError('Synthetic interruption')
    sql_event.listen(engine,'before_cursor_execute',fail)
    try:assert apply(setup,command).outcome is t.Outcome.UNKNOWN
    finally:sql_event.remove(engine,'before_cursor_execute',fail)
    assert (rows(engine,right),rows(engine,pending))==before and not rows(engine,event)
    assert svc.verify_outcome(bearers['t1-ada'],command).outcome is t.Outcome.NOT_APPLIED
    original=svc._transaction
    @contextmanager
    def lost(*a,**kw):
        with original(*a,**kw) as values:yield values
        raise RuntimeError('Synthetic post-commit acknowledgment loss')
    monkeypatch.setattr(svc,'_transaction',lost)
    assert apply(setup,command).outcome is t.Outcome.UNKNOWN
    monkeypatch.setattr(svc,'_transaction',original)
    assert svc.verify_outcome(bearers['t1-ada'],command).outcome is t.Outcome.COMMITTED
    assert apply(setup,command).outcome is t.Outcome.REPLAY and len(rows(engine,event))==1


@pytest.mark.parametrize('reason',[None,'personal-judgment','arbitrary private notes',False])
def test_reason_requires_enum_not_text(setup,reason):
    with pytest.raises(t.TaskError):prepared(setup,reason=reason)


@pytest.mark.parametrize('field,value',[('source_grant_revision',None),('source_grant_revision',True),('source_grant_revision',0),('personal_reason',None)])
def test_new_command_required_fields(setup,field,value):
    with pytest.raises(t.TaskError):replace(prepared(setup),**{field:value})


def test_old_operations_reject_new_fields_and_i7_entrypoint_rejects_new_operations(setup):
    old=cmd(setup,t.Operation.REVIEW)
    for kw in [dict(personal_reason=t.PersonalReason.PERSONAL_JUDGMENT),dict(source_grant_revision=1)]:
        with pytest.raises(t.TaskError):replace(old,**kw)
    for op in OPS:
        with pytest.raises(t.TaskError):setup[0].prepare_review(setup[1]['t1-ada'],'t1-school',op,1)


@pytest.mark.parametrize('operation,expected',[
    (t.Operation.REVIEW,'d59166a48716826c4c6da8139f0b17b3382196525b222626a505ea80f9577330'),
    (t.Operation.DEFER,'3be2157eabed18a1a5c6e63a1505cabde1b86371cd5e929994b84770dd6cd78b'),
    (t.Operation.NEEDS_INFORMATION,'c143e10e2f34ea6b470f928bfb38315e8872f4a058c7e36b41548d9f8c401594'),
    (t.Operation.ACCEPT,'628e5950e222e06eb6ed5deaf6f17b75e8563185c398d46064cd3f25b833d8fc'),
    (t.Operation.EDIT,'9f057fec6f65a08e86dacf5fa17905178efaa897d5a1a0d03afdad45515bbea4')])
def test_exact_frozen_i7_command_fingerprint_bytes(operation,expected):
    # Constants measured from merged I7 code before adding any I8 fields.
    kw=dict(binding=t.Binding(1,'0'*64,'fixture-v1')) if operation is not t.Operation.EDIT else dict(assignee='fixture-ada')
    if operation is t.Operation.ACCEPT:kw.update(assignee='joint',recipients=(t.Recipient('fixture-ada',1),t.Recipient('fixture-bo',2)))
    assert t.Command(operation,'fixture-pending',1,2,'fixture-request',**kw).fingerprint==expected


def test_exact_i7_bound_edit_fingerprint():
    c=t.Command(t.Operation.EDIT,'fixture-pending',1,2,'fixture-request',assignee='fixture-ada',edit_recipients=(t.EditRecipient('fixture-ada',1,1),t.EditRecipient('fixture-bo',2,1)))
    assert c.fingerprint=='c988c40f250e13154fc0aeb3f0c4004b7f3384883fda5f311886f1fb67db3279'


@pytest.mark.parametrize('following',[None,t.Operation.RESUME,t.Operation.DEFER,t.Operation.NEEDS_INFORMATION])
def test_historical_not_applicable_is_viewed_proof_without_mutating_history(setup,engine,following):
    command=prepared(setup);assert apply(setup,command).outcome is t.Outcome.COMMITTED
    # Exact persisted shape from the earlier I8 writer: same event, false cache.
    with engine.begin() as c:c.execute(update(right).where(right.c.pending_id=='t1-school',right.c.person_id=='t1-ada').values(reviewed=False))
    before=rows(engine,event),rows(engine,right),rows(engine,pending)
    assert item(setup).reviewed is True
    assert not item(setup,who='t1-bo').reviewed
    assert apply(setup,command).outcome is t.Outcome.REPLAY
    assert setup[0].verify_outcome(setup[1]['t1-ada'],command).outcome is t.Outcome.COMMITTED
    assert (rows(engine,event),rows(engine,right),rows(engine,pending))==before
    if following is not None:
        follow=prepared(setup,following) if following is t.Operation.RESUME else cmd(setup,following,request='legacy-follow')
        assert apply(setup,follow).outcome is t.Outcome.COMMITTED
        assert item(setup).reviewed is True
        assert next(r for r in rows(engine,right) if r['pending_id']=='t1-school' and r['person_id']=='t1-ada')['reviewed'] is True
        assert rows(engine,event)[:-1]==before[0]
    assert all(e['operation']!='review' for e in rows(engine,event))


def test_not_applicable_preview_and_cancel_do_not_mark_viewed(setup,engine):
    svc,bearers,_,_=setup;before=rows(engine,event),rows(engine,right),rows(engine,pending)
    row,command,after=svc.prepare_personal(bearers['t1-ada'],'t1-school',t.Operation.NOT_APPLICABLE,1,reason=t.PersonalReason.PERSONAL_JUDGMENT)
    assert not row.reviewed and after.reviewed and after.disposition=='not-applicable'
    assert svc.apply(bearers['t1-ada'],command,confirm=False).outcome is t.Outcome.CANCELED
    assert not item(setup).reviewed and item(setup).disposition=='active'
    assert (rows(engine,event),rows(engine,right),rows(engine,pending))==before


@pytest.mark.parametrize('operation,expected',[
    (t.Operation.NOT_APPLICABLE,'dfcb3b42ceb00b57ad29572c5c40d40affc9c535eaf9734db916f7bf6d320670'),
    (t.Operation.RESUME,'dd77d9b0c7c1399dea2e9a3bb82dd427d74892de304fd0ccef5cbd377d95b833')])
def test_i8_semantic_change_preserves_existing_command_fingerprints(operation,expected):
    command=t.Command(operation,'fixture-pending',1,2,'fixture-request',binding=t.Binding(1,'0'*64,'fixture-v1'),
        personal_reason=t.PersonalReason.PERSONAL_JUDGMENT if operation is t.Operation.NOT_APPLICABLE else None,source_grant_revision=3)
    assert command.fingerprint==expected
