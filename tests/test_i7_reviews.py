"""I7: fictional owned SQL transactions and the unchanged shared receipt fence."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
from threading import Barrier

import pytest
from sqlalchemy import select,update,func,event as sql_event
from family_os.schema import task_domain_event as events,household_task as tasks,household_pending_item as pending,pending_member_right as rights,source_read_grant as sources,household_membership as members,external_identity_binding as bindings
from test_i6_explanations import i6
from test_i5_information import i5,f,r,count
from test_i2_local_session import login,request
from test_i4b_workbench import i4b,i2,t,post,val,mutate

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('i7_workbench',ROOT/'prototypes/i7-workbench/serve_reviews.py')
i7=importlib.util.module_from_spec(spec);sys.modules[spec.name]=i7;spec.loader.exec_module(i7)


@pytest.fixture
def lab(engine):
    owner=i2.Lab(engine,synthetic_only=True);producer=i5.initialize(owner);app=i7.Workbench(owner,38199)
    yield app,producer
    app.close();owner.close()


def page(app,jar,query=''):
    return request(app,'/api/pending',cookies=jar,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING=query)


def rows(app,jar,state='all',**kw):
    q='&'.join(k+'='+str(v) for k,v in dict(limit=20,offset=0,state=state,**kw).items())
    return val(page(app,jar,q))['pending']


def preview(app,jar,pid,op='review',revision=None):
    if revision is None:revision=next(v['revision'] for v in rows(app,jar)['items'] if v['id']==pid)
    return post(app,jar,'pending/review-preview',dict(id=pid,revision=revision,operation=op))


def save(app,jar,pid,op='review'):
    p=val(preview(app,jar,pid,op));res=post(app,jar,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True));assert res[0]=='200 OK';return val(res)


def event_count(engine,pid):
    with engine.connect() as c:return c.scalar(select(func.count()).select_from(events).where(events.c.pending_id==pid))


def own(app,jar,pid):return next(v for v in rows(app,jar)['items'] if v['id']==pid)


@pytest.mark.parametrize('operation,reviewed,disposition',[('review',True,'active'),('defer',False,'deferred'),('needs-information',False,'needs-information')])
def test_personal_current_state_actual_actor_and_no_task(lab,engine,operation,reviewed,disposition):
    app,producer=lab;a,b=login(app),login(app,'devon');pid=producer.process(i5.cases()[0]).pending_id
    before=count(engine,tasks);p=val(preview(app,a,pid,operation));assert event_count(engine,pid)==0
    res=val(post(app,a,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True)))
    assert res['outcome']==t.Outcome.COMMITTED.value and res['operation']==operation
    assert own(app,a,pid)['reviewed'] is reviewed and own(app,a,pid)['disposition']==disposition
    assert not own(app,b,pid)['reviewed'] and own(app,b,pid)['disposition']=='active'
    assert count(engine,tasks)==before
    history=app.tasks.history(a[i2.COOKIE],pid,tasks=False)
    assert [(v.operation.value,v.actor_id) for v in history]==[(operation,'i2-clara')]
    assert app.tasks.history(b[i2.COOKIE],pid,tasks=False)==()
    assert val(post(app,a,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.REPLAY.value
    assert event_count(engine,pid)==1


def test_independent_fields_and_server_filters(lab,engine):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    save(app,a,pid);save(app,a,pid,'defer');row=own(app,a,pid)
    assert row['reviewed'] and row['disposition']=='deferred'
    assert pid in {v['id'] for v in rows(app,a,'deferred')['items']}
    assert pid not in {v['id'] for v in rows(app,a,'viewed')['items']}
    save(app,a,pid,'needs-information');assert own(app,a,pid)['reviewed']
    assert pid in {v['id'] for v in rows(app,a,'needs-information')['items']}
    assert pid in {v['id'] for v in rows(app,a)['items']}


@pytest.mark.parametrize('operation',['review','defer','needs-information'])
def test_change_and_revert_do_not_revive_annotations(lab,operation):
    app,producer=lab;a=login(app);first=i5.cases()[0];pid=producer.process(first).pending_id
    save(app,a,pid,operation)
    for generation,safety in ((2,r.Safety.UNAVAILABLE),(3,first.safety)):
        producer.process(replace(first,generation=generation,safety=safety));row=own(app,a,pid)
        assert not row['reviewed'] and row['disposition']=='active'
    assert len(app.tasks.history(a[i2.COOKIE],pid,tasks=False))==1
    assert save(app,a,pid,operation)['outcome']==t.Outcome.COMMITTED.value
    assert len(app.tasks.history(a[i2.COOKIE],pid,tasks=False))==2


@pytest.mark.parametrize('scope',['source','pending','review','membership','binding'])
def test_prepare_and_confirm_recheck_current_rights(lab,engine,scope):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id;p=val(preview(app,a,pid))
    table={'source':sources,'pending':rights,'review':rights,'membership':members,'binding':bindings}[scope]
    where=(table.c.person_id=='i2-clara',)
    if scope=='source':where+=(table.c.source_account_id==f.Source.SHARED.value,)
    if scope in ('pending','review'):where+=(table.c.pending_id==pid,)
    mutate(app,table,where,**(dict(can_review=False,revision=2) if scope=='review' else dict(state='revoked',revision=2)))
    assert preview(app,a,pid,revision=1)[0]=='400 Bad Request'
    res=post(app,a,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True))
    assert res[0]=='400 Bad Request' or val(res)['outcome']!=t.Outcome.COMMITTED.value
    assert event_count(engine,pid)==0
    if scope!='review':assert pid not in {v['id'] for v in val(page(app,a))['pending']['items']} if scope in ('source','pending') else page(app,a)[0]=='400 Bad Request'


@pytest.mark.parametrize('op',['accept','edit','REVIEW','archive','',None,True])
def test_review_cannot_prepare_other_authority(lab,op):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    assert post(app,a,'pending/review-preview',dict(id=pid,revision=1,operation=op))[0]=='400 Bad Request'


@pytest.mark.parametrize('query',['state=','state=archive','state=all&state=viewed','state=%61ll','actor=i2-devon','state=all&person_id=i2-devon','state=all&limit=0','state=all&limit=21','state=all&offset=-1','state=ALL'])
def test_strict_query(lab,query):
    app,_=lab;a=login(app);assert page(app,a,query)[0]=='400 Bad Request'


def test_state_pagination_more_than_twelve_hidden_population(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');i5.experiment(producer,'pages')
    p=rows(app,a);ids=[v['id'] for v in p['items'] if v['id'].startswith('i5_')]
    assert len(ids)==14
    for pid in ids:save(app,a,pid,'defer')
    first=val(page(app,a,'limit=12&offset=0&state=deferred'))['pending']
    second=val(page(app,a,'limit=12&offset=12&state=deferred'))['pending']
    assert first['total']==second['total']==14 and first['has_more'] and not second['has_more']
    assert len(first['items'])==12 and len(second['items'])==2
    assert rows(app,b,'deferred')['total']==0
    private=producer.process(i5.cases()[5]).pending_id;save(app,a,private,'defer')
    assert rows(app,b,'deferred')['total']==0
    assert preview(app,b,private,revision=1)==preview(app,b,'i7-missing',revision=1)
    assert not any(v['id']==private for v in rows(app,b)['items'])


def test_stale_competing_peers_and_cross_operation_receipts(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');pid=producer.process(i5.cases()[0]).pending_id
    p=val(preview(app,a,pid));q=val(preview(app,b,pid,'defer'))
    assert post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True))[0]=='400 Bad Request'
    assert post(app,b,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True))[0]=='400 Bad Request'
    assert val(post(app,a,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.COMMITTED.value
    assert val(post(app,b,'pending/review-confirm',dict(receipt=q['receipt'],confirm=True)))['outcome']==t.Outcome.STALE.value
    assert event_count(engine,pid)==1


@pytest.mark.parametrize('kind',['committed','absent'])
def test_unknown_shared_fence_and_exact_recovery(lab,engine,kind):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id;p=val(preview(app,a,pid))
    apply,verify=app.tasks.apply,app.tasks.verify_outcome
    def lost(*args,**kw):
        if kind=='committed':assert apply(*args,**kw).outcome is t.Outcome.COMMITTED
        raise RuntimeError('synthetic lost acknowledgment')
    app.tasks.apply=lost;app.tasks.verify_outcome=lambda *args:t.Result(t.Outcome.UNKNOWN)
    assert val(post(app,a,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.UNKNOWN.value
    assert post(app,a,'pending/preview',dict(id=pid,revision=1))[0]=='400 Bad Request'
    assert post(app,a,'tasks/edit-options',dict(id='i3-shared'))[0]=='400 Bad Request'
    assert preview(app,a,pid,revision=1)[0]=='400 Bad Request'
    app.tasks.apply,app.tasks.verify_outcome=apply,verify
    res=val(post(app,a,'writes/recover',{}));assert res['operation']=='review'
    assert res['outcome']==(t.Outcome.COMMITTED.value if kind=='committed' else t.Outcome.NOT_APPLIED.value)
    # Recovery sealed the original gate: delayed confirmation never mutates.
    post(app,a,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True))
    assert event_count(engine,pid)==(1 if kind=='committed' else 0)


def test_personal_records_never_accept_or_reopen_task(lab,engine):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    save(app,a,pid,'defer');save(app,a,pid,'needs-information');save(app,a,pid)
    p=val(post(app,a,'pending/preview',dict(id=pid,revision=4)));assert post(app,a,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True))[0]=='400 Bad Request'
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.COMMITTED.value
    before=count(engine,tasks)
    assert preview(app,a,pid,revision=5)[0]=='400 Bad Request'
    assert pid not in {v['id'] for v in rows(app,a)['items']} and count(engine,tasks)==before


@pytest.mark.parametrize('index',[1,7])
@pytest.mark.parametrize('op',['defer','needs-information'])
def test_conflict_and_mixed_remain_unaccepted(lab,engine,index,op):
    app,producer=lab;b=login(app,'devon');pid=producer.process(i5.cases()[index]).pending_id;before=count(engine,tasks)
    save(app,b,pid,op);assert not own(app,b,pid)['can_accept'] and count(engine,tasks)==before


@pytest.mark.parametrize('old',[i4b.Workbench,i6.Workbench])
def test_old_launchers_reject_review_route_and_state_filter(engine,old):
    lab=i2.Lab(engine,synthetic_only=True);i5.initialize(lab);app=old(lab,38199)
    try:
        a=login(app);assert post(app,a,'pending/review-preview',dict(id='i4a-school',revision=1,operation='review'))[0]=='400 Bad Request'
        assert page(app,a,'state=deferred')[0]=='400 Bad Request'
        assert val(page(app,a))['schema']=='i4a-pending-page-v1'
    finally:app.close();lab.close()


def test_concurrent_exact_request_one_mutation(lab,engine):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    command=app.tasks.prepare_review(a[i2.COOKIE],pid,t.Operation.REVIEW,1);barrier=Barrier(2)
    def apply():barrier.wait();return app.tasks.apply(a[i2.COOKIE],command,confirm=True).outcome
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:apply(),range(2)))
    assert sorted(x.value for x in results)==sorted((t.Outcome.COMMITTED.value,t.Outcome.REPLAY.value))
    assert event_count(engine,pid)==1


@pytest.mark.parametrize('operation',list(i7.PERSONAL))
def test_rollback_between_annotation_and_audit_has_no_partial_effect(lab,engine,operation):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    command=app.tasks.prepare_review(a[i2.COOKIE],pid,operation,1)
    def fail(c,cursor,statement,*args):
        if statement.lstrip().startswith('INSERT INTO task_domain_event'):raise RuntimeError('synthetic pre-audit fault')
    sql_event.listen(engine,'before_cursor_execute',fail)
    try:assert app.tasks.apply(a[i2.COOKIE],command,confirm=True).outcome is t.Outcome.UNKNOWN
    finally:sql_event.remove(engine,'before_cursor_execute',fail)
    current=own(app,a,pid)
    assert current['revision']==1 and not current['reviewed'] and current['disposition']=='active'
    assert event_count(engine,pid)==0
    assert app.tasks.verify_outcome(a[i2.COOKIE],command).outcome is t.Outcome.NOT_APPLIED


@pytest.mark.parametrize('op',list(i7.PERSONAL))
def test_changed_intent_and_real_cancel(lab,engine,op):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    command=app.tasks.prepare_review(a[i2.COOKIE],pid,op,1)
    assert app.tasks.apply(a[i2.COOKIE],command).outcome is t.Outcome.CANCELED
    assert event_count(engine,pid)==0
    assert app.tasks.apply(a[i2.COOKIE],command,confirm=True).outcome is t.Outcome.COMMITTED
    other=t.Operation.DEFER if op is t.Operation.REVIEW else t.Operation.REVIEW
    assert app.tasks.apply(a[i2.COOKIE],replace(command,operation=other),confirm=True).outcome is t.Outcome.CONFLICT
    assert event_count(engine,pid)==1


@pytest.mark.parametrize('index',[2,3,4])
def test_quiet_and_security_held_never_appear_in_state_filters(lab,index):
    app,producer=lab;a=login(app);value=i5.cases()[index];result=producer.process(value)
    assert result.pending_id is None
    forged=f.pending_identity(i2.HOME,value.source,value.record_id)
    for state in app.pending_states:
        assert forged not in {v['id'] for v in rows(app,a,state)['items']}
    # I8's new enum must not silently expand the older adapter contract.
    assert page(app,a,'state=not-applicable')[0]=='400 Bad Request'
    assert preview(app,a,forged,revision=1)[0]=='400 Bad Request'


@pytest.mark.parametrize('op',['defer','needs-information'])
@pytest.mark.parametrize('safety',['high-risk','unknown'])
def test_risk_review_cannot_clear_safety_or_publish(lab,engine,op,safety):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    mutate(app,pending,(pending.c.id==pid,),safety=safety)
    before=count(engine,tasks);save(app,a,pid,op)
    assert not own(app,a,pid)['can_accept'] and count(engine,tasks)==before
    with engine.connect() as c:assert c.scalar(select(pending.c.safety).where(pending.c.id==pid))==safety
    assert post(app,a,'pending/preview',dict(id=pid,revision=2))[0]=='400 Bad Request'


@pytest.mark.parametrize('change',[{'confirm':False},{'actor':'i2-devon'},{'receipt':'x'},{'operation':'accept'}])
def test_confirm_is_strict_and_never_takes_client_authority(lab,engine,change):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id;p=val(preview(app,a,pid))
    command=dict(receipt=p['receipt'],confirm=True);command.update(change)
    assert post(app,a,'pending/review-confirm',command)[0]=='400 Bad Request'
    assert event_count(engine,pid)==0


def test_read_only_fields_and_own_state_ignore_private_safety(lab):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    mutate(app,sources,(sources.c.source_account_id==f.Source.SHARED.value,sources.c.person_id=='i2-clara'),security=False,revision=2)
    before=page(app,a)
    mutate(app,pending,(pending.c.id==pid,),safety='high-risk')
    assert page(app,a)==before
    assert set(own(app,a,pid))=={'id','revision','step','supported_date','can_accept','can_review','reviewed','disposition'}


def test_node_contracts():
    import subprocess
    subprocess.run(['node','tests/browser/i7-contract.test.js'],cwd=ROOT,check=True,capture_output=True,text=True)


@pytest.mark.parametrize('operation',['accept','edit'])
def test_existing_unknown_accept_and_edit_block_new_personal_preview(lab,operation):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    if operation=='accept':p=val(post(app,a,'pending/preview',dict(id=pid,revision=1)))
    else:
        task=app.tasks.tasks(a[i2.COOKIE]).items[0]
        options=val(post(app,a,'tasks/edit-options',dict(id=task.id)))
        p=val(post(app,a,'tasks/edit-preview',dict(draft=options['draft'],action='reopen' if task.status is t.Status.COMPLETED else 'complete')))
    app.tasks.apply=lambda *args,**kw:t.Result(t.Outcome.UNKNOWN)
    app.tasks.verify_outcome=lambda *args,**kw:t.Result(t.Outcome.UNKNOWN)
    route='pending/accept' if operation=='accept' else 'tasks/edit-confirm'
    assert val(post(app,a,route,dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.UNKNOWN.value
    assert preview(app,a,pid,revision=1)[0]=='400 Bad Request'
    recovered=val(post(app,a,'writes/recover',{}));assert recovered['operation'] is None and recovered['receipt'] is None and recovered['outcome']==t.Outcome.UNKNOWN.value
    original=val(post(app,a,'pending/outcome' if operation=='accept' else 'tasks/edit-outcome',dict(receipt=p['receipt'])))
    assert original['operation']==operation and original['outcome']==t.Outcome.UNKNOWN.value


@pytest.mark.parametrize('header,value',[('HTTP_ORIGIN','https://evil.invalid'),('HTTP_SEC_FETCH_SITE','cross-site'),('HTTP_X_SAMAS_INTENT','wrong')])
def test_new_write_routes_inherit_same_origin_csrf(lab,engine,header,value):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    body=json.dumps(dict(id=pid,revision=1,operation='review')).encode()
    res=request(app,'/api/pending/review-preview',cookies=a,body=body,**{header:value})
    assert res[0]=='400 Bad Request' and event_count(engine,pid)==0


def test_pending_dialog_stylesheet_is_opt_in(lab,engine):
    app,_=lab
    assert b'href="/reviews.css"' in app.assets['/'][0]
    css,mime=app.assets['/reviews.css']
    assert b'.i7-pending-dialog' in css and mime=='text/css; charset=utf-8'
    # Only this runner includes the layout. Existing default I6 is unaffected.
    old=i6.Workbench(app.lab,38199)
    try:
        assert '/reviews.css' not in old.assets
        assert b'href="/reviews.css"' not in old.assets['/'][0]
    finally:old.close()
