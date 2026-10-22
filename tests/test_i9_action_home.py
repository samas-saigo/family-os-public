"""I9 real SQL projection: current grants first, independent personal state, no domain writes."""
from dataclasses import replace
from datetime import date
import pytest
from sqlalchemy import select, insert, update
from test_household_tasks import (setup, key, cmd, accept, edit, revoke, rows,
    HOME, FINGERPRINT, t, pending, right, plan, event, task, grant, source, member)


def home(setup, who='t1-ada'):
    return setup[0].action_home(setup[1][who])


def ids(section): return [c.item.id for c in section.items]


def personal(setup, operation, resource='t1-school', who='t1-ada', request=None):
    service, bearers, *_ = setup
    if operation in (t.Operation.NOT_APPLICABLE, t.Operation.RESUME):
        current = next(r for r in service.pending(bearers[who]).items if r.id == resource)
        _, command, _ = service.prepare_personal(bearers[who], resource, operation, current.revision,
            reason=t.PersonalReason.PERSONAL_JUDGMENT if operation is t.Operation.NOT_APPLICABLE else None)
    else:
        command = cmd(setup, operation, id=resource, who=who, request=request or operation.value)
    assert service.apply(bearers[who], command, confirm=True).outcome is t.Outcome.COMMITTED


def test_active_viewed_is_still_undecided_and_private(setup):
    before = home(setup)
    assert before.decisions.total == 3  # school, mixed and a safe but unresolved question
    assert home(setup, 't1-bo').decisions.total == 4  # independently authorized private source
    personal(setup, t.Operation.REVIEW)
    after = home(setup)
    assert after.decisions.total == before.decisions.total
    assert next(c.reason for c in after.decisions.items if c.item.id == 't1-school') == 'viewed-undecided'
    assert next(c.reason for c in home(setup, 't1-bo').decisions.items if c.item.id == 't1-school') == 'undecided'
    assert all(c.item.safety == 'clear' for c in after.decisions.items)
    assert not {'t1-risk', 't1-unknown', 't1-info', 't1-promotion'} & set(ids(after.decisions))


@pytest.mark.parametrize('operation', [t.Operation.DEFER, t.Operation.NEEDS_INFORMATION])
def test_followup_own_state_and_reason(setup, operation):
    personal(setup, operation)
    h = home(setup)
    assert h.decisions.total == 2 and h.followup.total == 1
    assert h.followup.items[0].reason == ('deferred' if operation is t.Operation.DEFER else 'needs-information')
    assert home(setup, 't1-bo').followup.total == 0


def test_not_applicable_resume_and_exact_evidence_change_revert(setup, engine):
    personal(setup, t.Operation.NOT_APPLICABLE)
    assert home(setup).decisions.total == 2
    assert any(r.id == 't1-school' for r in setup[0].pending(setup[1]['t1-ada']).items)
    personal(setup, t.Operation.RESUME)
    assert home(setup).decisions.items[0].item.reviewed
    for generation, fp in [(2, 'a'*64), (3, FINGERPRINT)]:
        with engine.begin() as c:
            c.execute(update(pending).where(pending.c.id == 't1-school').values(
                generation=generation, evidence_fingerprint=fp, revision=pending.c.revision+1))
        assert home(setup).decisions.items[0].item.reviewed is False


def test_accept_assignment_completed_and_no_duplicate(setup):
    tid = accept(setup)
    assert home(setup).decisions.total == 2
    assert ids(home(setup).mine) == ids(home(setup, 't1-bo').mine) == [tid]
    assert home(setup).collaboration.total == 0
    command = edit(setup, tid, assignee='t1-bo', status=t.Status.PENDING)
    assert setup[0].apply(setup[1]['t1-ada'], command, confirm=True).outcome is t.Outcome.COMMITTED
    assert ids(home(setup).collaboration) == [tid] and home(setup).mine.total == 0
    assert ids(home(setup, 't1-bo').mine) == [tid]
    command = edit(setup, tid, request='complete', assignee='t1-bo', status=t.Status.COMPLETED)
    assert setup[0].apply(setup[1]['t1-ada'], command, confirm=True).outcome is t.Outcome.COMMITTED
    assert home(setup).collaboration.total == home(setup, 't1-bo').mine.total == 0


def test_revocation_security_scope_membership_and_independent_tasks(setup, engine):
    tid = accept(setup)
    revoke(engine, source, source_account_id='t1-school-source')
    assert ids(home(setup).mine) == [tid]  # publication is independent
    assert ids(home(setup).decisions) == ['t1-question']
    assert home(setup, 't1-bo').decisions.total == 3
    with engine.begin() as c:
        c.execute(update(source).where(source.c.person_id == 't1-ada').values(security=False))
    assert home(setup).decisions.total == 0
    revoke(engine, grant, task_id=tid)
    assert home(setup).mine.total == 0
    assert home(setup, 't1-bo').mine.total == 1
    revoke(engine, member)
    with pytest.raises(t.TaskError): home(setup)


def test_observation_only_private_safety_cannot_affect_home(setup, engine):
    with engine.begin() as c:
        c.execute(update(source).where(source.c.person_id == 't1-ada').values(security=False))
    before = home(setup)
    with engine.begin() as c:
        c.execute(update(pending).where(pending.c.id == 't1-school').values(safety='high-risk'))
    assert home(setup) == before


def test_read_only_and_invalid_bearer(setup, engine):
    tables = (pending, right, plan, task, grant, event)
    before = [rows(engine, table) for table in tables]
    for _ in range(3): home(setup)
    assert before == [rows(engine, table) for table in tables]
    for bearer in ('', 'random', setup[1]['t1-cy']):
        with pytest.raises(t.TaskError): setup[0].action_home(bearer)


def test_full_counts_over_twenty_date_order_and_stable_ties(setup, engine):
    # New fictional SQL records; no frozen evaluation fixtures. Domain ACCEPT
    # creates tasks; no direct task insertion, browser aggregation or page scraping.
    with engine.begin() as c:
        for n in range(27):
            pid = f'i9-pending-{n:02d}'
            c.execute(insert(pending).values(household_id=HOME, id=pid,
                source_account_id='t1-school-source', kind='action', step='school-session', supported=True,
                safety='clear', supported_date=date(2030, 1, 1) if n >= 24 else None,
                generation=1, evidence_fingerprint=FINGERPRINT, definition_version='fictional-policy-v1',
                resolution='unresolved', revision=1))
            for person in ('t1-ada', 't1-bo'):
                c.execute(insert(right).values(household_id=HOME, pending_id=pid, person_id=person,
                    state='allowed', can_read=True, can_review=True, can_publish=True, revision=1,
                    membership_revision=1, reviewed=False, disposition='active'))
                c.execute(insert(plan).values(household_id=HOME, pending_id=pid, person_id=person,
                    state='allowed', can_read=True, can_edit=True, can_history=True, revision=1, membership_revision=1))
    # First page's ID order would miss the earliest dates entirely.
    service, bearers, *_ = setup
    command = service.prepare_review(bearers['t1-ada'], 'i9-pending-24', t.Operation.REVIEW, 1)
    service.apply(bearers['t1-ada'], command, confirm=True)
    h = home(setup)
    assert h.decisions.total == 30
    assert ids(h.decisions) == ['i9-pending-25', 'i9-pending-26', 'i9-pending-24']
    for n in range(27):
        pid=f'i9-pending-{n:02d}'
        row=next(r for r in service.pending(bearers['t1-ada'], offset=20 if n>=20 else 0).items if r.id==pid)
        command=service.prepare_review(bearers['t1-ada'],pid,t.Operation.DEFER,row.revision)
        assert service.apply(bearers['t1-ada'],command,confirm=True).outcome is t.Outcome.COMMITTED
    assert home(setup).followup.total==27
    assert ids(home(setup).followup)==['i9-pending-25','i9-pending-26','i9-pending-24']
    for n in range(27):
        pid=f'i9-pending-{n:02d}'
        preview=service.prepare_acceptance(bearers['t1-ada'], pid)
        # API prepare returns the full trusted accept command as its second member.
        command=preview[1]
        result=service.apply(bearers['t1-ada'], command, confirm=True)
        assert result.outcome is t.Outcome.COMMITTED
    h=home(setup)
    assert h.mine.total == 27 and h.decisions.total == 3
    assert [c.item.approved_date for c in h.mine.items] == [date(2030,1,1)]*3
    assert ids(h.mine) == sorted(ids(h.mine))


def test_current_review_authority_required_and_other_sources_not_suppressed(setup, engine):
    with engine.begin() as c:
        c.execute(update(right).where(right.c.person_id=='t1-ada',right.c.pending_id=='t1-school').values(can_review=False))
    assert home(setup).decisions.total==2
    assert home(setup,'t1-bo').decisions.total==4


def test_hidden_populations_never_change_visible_order_totals_or_errors(setup, engine):
    before=home(setup)
    with engine.begin() as c:
        c.execute(update(pending).where(pending.c.id=='t1-private').values(
            safety='high-risk',supported_date=date(2000,1,1),generation=2,evidence_fingerprint='e'*64))
        for n in range(25):
            pid=f'i9-private-{n}'
            c.execute(insert(pending).values(household_id=HOME,id=pid,source_account_id='t1-private-source',
                kind='action',step='school-session',supported=True,safety='clear',supported_date=date(1999,1,1),
                generation=1,evidence_fingerprint=FINGERPRINT,definition_version='fictional-policy-v1',resolution='unresolved',revision=1))
            c.execute(insert(right).values(household_id=HOME,pending_id=pid,person_id='t1-ada',state='allowed',
                can_read=True,can_review=True,can_publish=True,revision=1,membership_revision=1,reviewed=False,disposition='active'))
    assert home(setup)==before


@pytest.mark.parametrize('safety',['high-risk','unknown'])
def test_safety_changes_withdraw_home_but_preserve_pending_all(setup, engine, safety):
    personal(setup,t.Operation.DEFER)
    assert home(setup).followup.total==1
    with engine.begin() as c:
        c.execute(update(pending).where(pending.c.id=='t1-school').values(safety=safety,revision=pending.c.revision+1))
    assert home(setup).followup.total==0
    assert any(r.id=='t1-school' for r in setup[0].pending(setup[1]['t1-ada']).items)


def test_home_counts_and_cards_share_authorization_order_with_revocation(setup,engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread
    from sqlalchemy import event as sql_event
    accept(setup)
    entered,release,attempted=Event(),Event(),Event()
    def hold(c,cursor,sql,parameters,ctx,many):
        if current_thread().name.startswith('i9-reader') and 'FROM household_task JOIN task_member_grant' in sql:
            entered.set();assert release.wait(15)
        if current_thread().name.startswith('i9-writer') and ('BEGIN IMMEDIATE' in sql or ('FROM household ' in sql and 'FOR UPDATE' in sql)):
            attempted.set()
    sql_event.listen(engine,'before_cursor_execute',hold)
    try:
        with ThreadPoolExecutor(max_workers=1,thread_name_prefix='i9-reader') as rp, ThreadPoolExecutor(max_workers=1,thread_name_prefix='i9-writer') as wp:
            reader=rp.submit(home,setup);assert entered.wait(10)
            writer=wp.submit(revoke,engine,grant);assert attempted.wait(10) and not writer.done()
            release.set();result=reader.result(timeout=15);writer.result(timeout=15)
        assert result.mine.total==len(result.mine.items)==1
        assert home(setup).mine.total==0 and home(setup,'t1-bo').mine.total==1
    finally:release.set();sql_event.remove(engine,'before_cursor_execute',hold)
