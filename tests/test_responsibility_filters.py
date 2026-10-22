"""Real owned SQLite/PostgreSQL authorization, responsibility and pagination."""
import json
from pathlib import Path
import subprocess
import shutil
import pytest
from sqlalchemy import select
from test_i4b_workbench import app, i4b, i4, i2, t, mutate, shared, preview, confirm
from test_i2_local_session import login, request
from test_a1_connected_home import page, revoke
from family_os.schema import task_member_grant as grant, source_read_grant as source, household_membership as member, task_domain_event as event
from responsibility_fixtures import seed


def data(app, jar, mode='all', step=None, offset=0):
    query=f'limit=12&offset={offset}&responsibility={mode}' + (f'&step={step}' if step else '')
    response=page(app,jar,'tasks',query)
    assert response[0]=='200 OK'
    value=json.loads(response[2])
    assert value['schema']=='i4b-task-page-v2'
    assert value['query']==dict(responsibility=mode,step=step)
    assert len(response[2])<=16384
    assert set(value)=={'schema','synthetic_only','pagination','tasks','query'}
    return value['tasks']


@pytest.mark.parametrize('peer',['clara','devon'])
def test_real_sql_authorized_buckets_before_count_and_page_with_step_and_completed(app,peer,engine):
    a,b=login(app),login(app,'devon');seed(app,a[i2.COOKIE]);jar=a if peer=='clara' else b
    bearer=jar[i2.COOKIE]
    all_rows=[]
    for offset in range(0,60,12):
        result=data(app,jar,offset=offset);all_rows+=result['items']
        if not result['has_more']:break
    assert len(all_rows)==(45 if peer=='clara' else 44)
    with engine.connect() as c: events=c.execute(select(event)).all()
    partitions=[]
    for mode in ('all','mine','other','joint'):
        for step in (None,'school-session','home-visit'):
            expected=[r for r in all_rows if (not step or r['step']==step) and (mode=='all' or
                (r['assignee']=='joint' if mode=='joint' else r['assignee']!='joint' and
                 ((r['assignee']=='i2-'+peer) if mode=='mine' else (r['assignee']!='i2-'+peer))))]
            ids=[]
            for offset in range(0,60,12):
                p=data(app,jar,mode,step,offset)
                assert p['total']==len(expected)
                assert p['items']==expected[offset:offset+12]
                assert p['has_more']==(offset+len(p['items'])<len(expected))
                ids += [r['id'] for r in p['items']]
                if not p['has_more']: break
            assert ids==[r['id'] for r in expected] and len(set(ids))==len(ids)
            if mode!='all' and step is None:
                partitions.append(set(ids));assert len(ids)>12
                assert {r['status'] for r in expected}=={'pending','completed'}
    assert not (partitions[0]&partitions[1] or partitions[0]&partitions[2] or partitions[1]&partitions[2])
    assert set.union(*partitions)=={r['id'] for r in all_rows}
    with engine.connect() as c:assert c.execute(select(event)).all()==events  # Query only; no decision writes.


def test_assignments_move_buckets_without_changing_grants_then_revoke(app):
    a,b=login(app),login(app,'devon');row=shared(app,a)
    for assignee in ('i2-devon','i2-clara','joint'):
        p=preview(app,a,row.id,'assign',assignee);assert confirm(app,a,p)['outcome']==t.Outcome.COMMITTED.value
        for jar,peer in ((a,'clara'),(b,'devon')):
            assert row.id in {r['id'] for r in data(app,jar)['items']}
            category='joint' if assignee=='joint' else 'mine' if assignee=='i2-'+peer else 'other'
            for mode in ('mine','other','joint'):
                assert (row.id in {r['id'] for r in data(app,jar,mode)['items']})==(mode==category)
    revoke(app,source,'clara')
    assert row.id in {r['id'] for r in data(app,a,'joint')['items']}
    mutate(app,grant,(grant.c.task_id==row.id,grant.c.person_id=='i2-clara'),state='revoked',revision=2)
    assert row.id not in {r['id'] for r in data(app,a,'joint')['items']}
    assert row.id in {r['id'] for r in data(app,b,'joint')['items']}
    revoke(app,member,'clara')
    for mode in ('all','mine','other','joint'):
        assert page(app,a,'tasks','responsibility='+mode)[0]=='400 Bad Request'


@pytest.mark.parametrize('query',['responsibility=','responsibility=Mine','responsibility=devon','responsibility=mine&responsibility=mine',
    'responsibility=mine&person_id=i2-clara','responsibility=all&household_id=other','responsibility=%61ll',
    'responsibility=all+','responsibility=all&limit=12&offset=0&step=home-visit&extra=x',
    'responsibility=all&limit=01','responsibility=all&offset=-1','responsibility=all&limit=21',
    'responsibility=all&step=','responsibility=all&step=home-visit&step=school-session'])
def test_i4b_rejects_noncanonical_or_identity_query(app,query):
    assert page(app,login(app),'tasks',query)[0]=='400 Bad Request'


@pytest.mark.parametrize('mode',['all','mine','other','joint'])
def test_old_adapters_and_pending_never_enable_filter(app,mode):
    jar=login(app)
    for cls in (i4.i3.Workbench,i4.Workbench):
        old=cls(app.lab,38199)
        try: assert page(old,jar,'tasks','responsibility='+mode)[0]=='400 Bad Request'
        finally:
            if hasattr(old,'close'):old.close()
    assert page(app,jar,'pending','responsibility='+mode)[0]=='400 Bad Request'


@pytest.mark.parametrize('value',[None,'all','mine',True,1,{},object()])
def test_domain_enum_only_not_raw_client_claim(app,value):
    with pytest.raises(t.TaskError):app.tasks.tasks(login(app)[i2.COOKIE],responsibility=value)


def test_unfiltered_v1_compatibility_session_failure_and_private_query_exclusion(app,engine):
    jar=login(app)
    r=page(app,jar,'tasks');assert json.loads(r[2])['schema']=='i4b-task-page-v1'
    assert data(app,jar)['items']==json.loads(r[2])['tasks']['items']
    assert page(app,{},'tasks','responsibility=mine')[0]=='400 Bad Request'
    from sqlalchemy import event as listen
    statements=[]
    def capture(c,cursor,statement,*args):statements.append(statement.lower())
    listen.listen(engine,'before_cursor_execute',capture)
    try:data(app,jar,'mine')
    finally:listen.remove(engine,'before_cursor_execute',capture)
    assert not any(any(n in s for n in ('pending_member_right','household_pending_item','raw_source_record','source_account','source_read_grant')) for s in statements)


def test_strict_filter_response_binding_node():
    result=subprocess.run([shutil.which('node'),'tests/browser/responsibility-contract.test.js'],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr


def test_hidden_task_population_changes_never_affect_filtered_outputs(app,engine):
    from family_os.schema import household_task as task
    a,b=login(app),login(app,'devon')
    before={mode:data(app,b,mode) for mode in ('all','mine','other','joint')}
    private=({r['id'] for r in data(app,a)['items']}-{r['id'] for r in data(app,b)['items']}).pop()
    mutate(app,task,(task.c.id==private,),assignee_kind='person',assignee_id='i2-devon',step='school-session',status='completed',revision=2)
    assert {mode:data(app,b,mode) for mode in before}==before


@pytest.mark.parametrize('changes',[
    {'HTTP_ORIGIN':'http://other.invalid'}, {'HTTP_SEC_FETCH_SITE':'cross-site'},
    {'HTTP_X_PERSON_ID':'i2-devon'}, {'HTTP_HOST':'evil.invalid'}, {'HTTP_X_SAMAS_INTENT':'other'},
    {'REQUEST_METHOD':'POST'}, {'CONTENT_TYPE':'application/json'}, {'HTTP_ACCEPT':'*/*'},
])
def test_filter_does_not_bypass_original_transport_boundary(app,changes):
    values=dict(cookies=login(app),method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING='responsibility=mine')
    if 'REQUEST_METHOD' in changes:values['method']=changes['REQUEST_METHOD'];changes={k:v for k,v in changes.items() if k!='REQUEST_METHOD'}
    values.update(changes)
    assert request(app,'/api/tasks',**values)[0]=='400 Bad Request'
