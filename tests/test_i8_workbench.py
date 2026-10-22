"""I8 strict same-origin fictional adapter; no new write coordinator or grants."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import update,select
from test_i7_reviews import i7,i5,i2,t,login,request,post,val,event_count,rows
from family_os.schema import pending_member_right as rights,source_read_grant as sources,household_pending_item as pending,task_domain_event as events

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('i8_workbench',ROOT/'prototypes/i8-workbench/serve_personal.py')
i8=importlib.util.module_from_spec(spec);sys.modules[spec.name]=i8;spec.loader.exec_module(i8)


@pytest.fixture
def lab(engine):
    owner=i2.Lab(engine,synthetic_only=True);producer=i5.initialize(owner);app=i8.Workbench(owner,38199)
    yield app,producer
    app.close();owner.close()


def preview(app,jar,pid,operation='not-applicable',reason='personal-judgment'):
    r=next(r for r in rows(app,jar)['items'] if r['id']==pid)
    return post(app,jar,'pending/review-preview',dict(id=pid,revision=r['revision'],operation=operation,**({'reason':reason} if operation=='not-applicable' else {})))


def confirm(app,jar,p):return post(app,jar,'pending/review-confirm',dict(receipt=p['receipt'],confirm=True))


@pytest.mark.parametrize('reason',[r.value for r in t.PersonalReason])
def test_new_private_state_preview_confirm_resume(lab,engine,reason):
    app,producer=lab;a,b=login(app),login(app,'devon');pid=producer.process(i5.cases()[0]).pending_id
    before={who:rows(app,jar)['total'] for who,jar in [('a',a),('b',b)]}
    p=val(preview(app,a,pid,reason=reason));assert p['schema']=='i8-personal-preview-v1'
    assert p['before']==dict(reviewed=False,disposition='active') and p['after']==dict(reviewed=True,disposition='not-applicable')
    assert event_count(engine,pid)==0
    assert val(confirm(app,a,p))['operation']=='not-applicable'
    own=rows(app,a,'not-applicable');assert own['items'][0]['can_resume'] is True
    assert rows(app,b,'not-applicable')['total']==0
    assert {who:rows(app,jar)['total'] for who,jar in [('a',a),('b',b)]}==before
    # Neither list nor shared task response carries the private reason.
    assert 'personal-judgment' not in str(own) and 'reason' not in str(own)
    resume=val(preview(app,a,pid,'resume'));assert resume['reason'] is None and resume['after']['disposition']=='active'
    assert val(confirm(app,a,resume))['outcome']==t.Outcome.COMMITTED.value
    assert val(confirm(app,a,resume))['outcome']==t.Outcome.REPLAY.value
    assert event_count(engine,pid)==2
    with engine.connect() as c:assert c.execute(select(events.c.personal_reason).where(events.c.pending_id==pid,events.c.operation=='not-applicable')).scalar_one()==reason


@pytest.mark.parametrize('reviewed', [True, False], ids=['current-viewed', 'never-viewed'])
def test_not_applicable_marks_viewed_and_resume_preserves_api_and_database(lab, engine, reviewed):
    app, producer = lab
    a, b = login(app), login(app, 'devon')
    pid = producer.process(i5.cases()[0]).pending_id
    if reviewed:
        assert val(confirm(app, a, val(preview(app, a, pid, 'review'))))['outcome'] == t.Outcome.COMMITTED.value
    assert val(confirm(app, a, val(preview(app, a, pid))))['outcome'] == t.Outcome.COMMITTED.value
    after_judgment = next(r for r in rows(app, a)['items'] if r['id'] == pid)
    assert after_judgment['reviewed'] is True and after_judgment['disposition'] == 'not-applicable'
    assert after_judgment['revision'] == 2 + int(reviewed)
    assert event_count(engine, pid) == 1 + int(reviewed)
    p = val(preview(app, a, pid, 'resume'))
    assert p['before'] == dict(reviewed=True, disposition='not-applicable')
    assert p['after'] == dict(reviewed=True, disposition='active')
    assert val(confirm(app, a, p))['outcome'] == t.Outcome.COMMITTED.value
    own = next(r for r in rows(app, a)['items'] if r['id'] == pid)
    assert own['reviewed'] is True and own['disposition'] == 'active'
    assert pid in {r['id'] for r in rows(app, a, 'viewed')['items']}
    assert pid not in {r['id'] for r in rows(app, a, 'unhandled')['items']}
    with engine.connect() as c:
        stored = c.execute(select(rights.c.reviewed, rights.c.disposition).where(
            rights.c.pending_id == pid, rights.c.person_id == 'i2-clara')).one()
        assert tuple(stored) == (True, 'active')
    peer = next(r for r in rows(app, b)['items'] if r['id'] == pid)
    assert not peer['reviewed'] and peer['disposition'] == 'active'


@pytest.mark.parametrize('changes',[{'reason':None},{'reason':''},{'reason':True},{'reason':[]},{'reason':'private free text'},{'person_id':'i2-devon'},{'household_id':'other'},{'source_grant_revision':1},{'revision':True},{'operation':'accept'},{'operation':'edit'}])
def test_strict_preview_shape_and_reason(lab,engine,changes):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    value=dict(id=pid,revision=1,operation='not-applicable',reason='personal-judgment');value.update(changes)
    assert post(app,a,'pending/review-preview',value)[0]=='400 Bad Request'
    assert event_count(engine,pid)==0


@pytest.mark.parametrize('operation',['review','defer','needs-information','resume'])
def test_reason_not_accepted_for_other_operations(lab,operation):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    assert post(app,a,'pending/review-preview',dict(id=pid,revision=1,operation=operation,reason='personal-judgment'))[0]=='400 Bad Request'


@pytest.mark.parametrize('route',['pending/accept','pending/outcome','tasks/edit-confirm','tasks/edit-outcome'])
def test_new_receipt_cannot_cross_old_operation_paths(lab,engine,route):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id;p=val(preview(app,a,pid))
    data=dict(receipt=p['receipt'],**({'confirm':True} if route.endswith(('accept','confirm')) else {}))
    assert post(app,a,route,data)[0]=='400 Bad Request' and event_count(engine,pid)==0


@pytest.mark.parametrize('operation',['accept','edit'])
def test_accept_edit_receipt_not_personal(lab,operation):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    if operation=='accept':p=val(post(app,a,'pending/preview',dict(id=pid,revision=1)))
    else:
        task=app.tasks.tasks(a[i2.COOKIE]).items[0]
        draft=val(post(app,a,'tasks/edit-options',dict(id=task.id)))
        p=val(post(app,a,'tasks/edit-preview',dict(draft=draft['draft'],action='reopen' if task.status is t.Status.COMPLETED else 'complete')))
    assert confirm(app,a,p)[0]=='400 Bad Request'


def test_two_sessions_cannot_transfer_receipts(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');pid=producer.process(i5.cases()[0]).pending_id;p=val(preview(app,a,pid))
    assert confirm(app,b,p)[0]=='400 Bad Request'
    assert post(app,b,'pending/review-outcome',dict(receipt=p['receipt']))[0]=='400 Bad Request'
    assert event_count(engine,pid)==0


def test_i7_old_state_query_and_new_state_fail_closed(lab,engine):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    old=i7.Workbench(app.lab,38199)
    try:
        assert post(old,a,'pending/review-preview',dict(id=pid,revision=1,operation='not-applicable',reason='personal-judgment'))[0]=='400 Bad Request'
        assert request(old,'/api/pending',cookies=a,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING='state=not-applicable')[0]=='400 Bad Request'
        assert confirm(app,a,val(preview(app,a,pid)))[0]=='200 OK'
        assert request(old,'/api/pending',cookies=a,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING='limit=20')[0]=='400 Bad Request'
        # The old adapter never returns an invented active/deferred projection.
    finally:old.close()


@pytest.mark.parametrize('header,value',[('HTTP_ORIGIN','https://evil.invalid'),('HTTP_SEC_FETCH_SITE','cross-site'),('HTTP_X_SAMAS_INTENT','wrong')])
def test_same_origin_boundaries(lab,engine,header,value):
    import json
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    body=json.dumps(dict(id=pid,revision=1,operation='not-applicable',reason='personal-judgment')).encode()
    assert request(app,'/api/pending/review-preview',cookies=a,body=body,**{header:value})[0]=='400 Bad Request'
    assert event_count(engine,pid)==0


def test_unknown_recovery_and_late_gate_retirement(lab,engine):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id;p=val(preview(app,a,pid))
    original=app.tasks.apply
    app.tasks.apply=lambda *args,**kw:t.Result(t.Outcome.UNKNOWN)
    assert val(confirm(app,a,p))['outcome']==t.Outcome.UNKNOWN.value
    # A false absence is never followed by a late execution: gate already consumed.
    app.tasks.apply=original
    outcome=val(post(app,a,'pending/review-outcome',dict(receipt=p['receipt'])))
    assert outcome['outcome']==t.Outcome.NOT_APPLIED.value and outcome['operation']=='not-applicable'
    assert val(confirm(app,a,p))['outcome']==t.Outcome.NOT_APPLIED.value
    assert event_count(engine,pid)==0


def test_committed_ack_loss_recovers_original_operation_once(lab,engine):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id;p=val(preview(app,a,pid))
    original=app.tasks.apply
    def lost(*args,**kw):original(*args,**kw);raise RuntimeError('Synthetic lost acknowledgment')
    app.tasks.apply=lost
    assert val(confirm(app,a,p))['outcome']==t.Outcome.UNKNOWN.value
    app.tasks.apply=original
    result=val(post(app,a,'writes/recover',{}));assert result['operation']=='not-applicable' and result['outcome']==t.Outcome.COMMITTED.value
    assert event_count(engine,pid)==1


@pytest.mark.parametrize('operation',['not-applicable','resume'])
def test_revoke_regrant_stales_unexecuted_preview(lab,engine,operation):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    if operation=='resume':confirm(app,a,val(preview(app,a,pid,'defer')))
    p=val(preview(app,a,pid,operation))
    with i2.a.authorization_transaction(app.lab.sessions._engine,i2.HOME) as c:
        c.execute(update(sources).where(sources.c.person_id=='i2-clara').values(state='revoked',revision=sources.c.revision+1))
    assert post(app,a,'pending/review-outcome',dict(receipt=p['receipt']))[0]=='200 OK'
    with i2.a.authorization_transaction(app.lab.sessions._engine,i2.HOME) as c:
        c.execute(update(sources).where(sources.c.person_id=='i2-clara').values(state='allowed',revision=sources.c.revision+1))
    # The explicit outcome above retires this request permanently, even if absent.
    assert val(confirm(app,a,p))['outcome']==t.Outcome.NOT_APPLIED.value
    p=val(preview(app,a,pid,operation))
    with i2.a.authorization_transaction(app.lab.sessions._engine,i2.HOME) as c:
        c.execute(update(sources).where(sources.c.person_id=='i2-clara').values(revision=sources.c.revision+1))
    assert val(confirm(app,a,p))['outcome']==t.Outcome.STALE.value


@pytest.mark.parametrize('change',['change','revert'])
def test_changed_and_reverted_evidence_invalidates_new_decisions(lab,engine,change):
    app,producer=lab;a=login(app);i5.experiment(producer,'process');pid=producer.process(i5.cases()[0]).pending_id
    assert val(confirm(app,a,val(preview(app,a,pid))))['outcome']==t.Outcome.COMMITTED.value
    p=val(preview(app,a,pid,'resume'));i5.experiment(producer,'change')
    if change=='revert':i5.experiment(producer,'revert')
    assert val(confirm(app,a,p))['outcome']==t.Outcome.STALE.value
    row=next(r for r in rows(app,a)['items'] if r['id']==pid)
    assert row['disposition']=='active' and row['can_resume'] is False


def test_filtered_pagination_and_hidden_private_state(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');results=i5.experiment(producer,'pages')
    for r in results:assert val(confirm(app,a,val(preview(app,a,r.pending_id))))['outcome']==t.Outcome.COMMITTED.value
    def query(jar,offset):
        return val(request(app,'/api/pending',cookies=jar,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING=f'limit=12&offset={offset}&state=not-applicable'))['pending']
    first,second=query(a,0),query(a,12)
    assert first['total']==second['total']==14 and first['has_more'] and not second['has_more']
    assert len(first['items'])==12 and len(second['items'])==2
    assert not ({r['id'] for r in first['items']} & {r['id'] for r in second['items']})
    assert query(b,0)==dict(items=[],total=0,has_more=False)
    old=i7.Workbench(app.lab,38199)
    try:
        assert request(old,'/api/pending',cookies=b,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING='limit=20')[0]=='200 OK'
    finally:old.close()


@pytest.mark.parametrize('query',['state=','state=not-applicable&state=all','state=not%2Dapplicable','state=not-applicable&person_id=i2-devon','state=resume'])
def test_bad_state_queries(lab,query):
    app,_=lab;a=login(app)
    assert request(app,'/api/pending',cookies=a,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING=query)[0]=='400 Bad Request'
