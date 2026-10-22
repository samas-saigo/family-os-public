"""Actual T1 database/cookie-to-page integration, fictional records only."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import select,update,insert,event as sql_event
from time import time

from test_i2_local_session import request,login,start
from family_os.schema import (household_task as task,task_member_grant as grant,
    household_pending_item as pending,task_domain_event,source_read_grant,household_session,
    household_membership,external_identity_binding)

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('i3_workbench',ROOT/'prototypes/i3-workbench/serve_workbench.py')
i3=importlib.util.module_from_spec(spec);sys.modules[spec.name]=i3;spec.loader.exec_module(i3)
i2=i3.i2


@pytest.fixture
def app(engine):
    lab=i2.Lab(engine,synthetic_only=True)
    i3.seed(lab)
    yield i3.Workbench(lab,38199)
    lab.close()


def read(app,jar,query='',**changes):
    options=dict(CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING=query)
    options.update(changes)
    return request(app,'/api/tasks',cookies=jar,method='GET',body=b'',**options)


def tasks(app,jar,query=''):
    status,headers,raw=read(app,jar,query)
    assert status=='200 OK'
    return json.loads(raw)


def revoke(engine,person='i2-clara',table=grant):
    with i2.a.authorization_transaction(engine,i2.HOME) as c:
        c.execute(update(table).where(table.c.household_id==i2.HOME,table.c.person_id==person).values(
            revision=table.c.revision+1,**({'revoked':True} if table is household_session else {'state':'revoked'})))


def test_actual_t1_acceptance_shared_and_private_task_counts(app,engine):
    a,b=login(app),login(app,'devon')
    left=tasks(app,a,'limit=20')['tasks'];right=tasks(app,b,'limit=20')['tasks']
    assert left['total']==3 and right['total']==2
    assert {r['id'] for r in right['items']} < {r['id'] for r in left['items']}
    assert all(r in left['items'] for r in right['items'])
    assert {r['status'] for r in right['items']}=={'pending','completed'}
    assert sum(r['approved_date'] is None for r in left['items'])==2
    assert all(set(r)==i3.FIELDS for r in left['items'])
    with engine.connect() as c:
        assert len(c.execute(select(task)).all())==3
        assert len(c.execute(select(task_domain_event).where(task_domain_event.c.operation=='accept')).all())==3
        assert c.execute(select(pending.c.resolution).where(pending.c.id=='i3-unaccepted')).scalar_one()=='unresolved'


def test_authorized_database_pages_filters_and_empty_result(app,engine):
    jar=login(app)
    first=tasks(app,jar);second=tasks(app,jar,'offset=2')
    assert first['tasks']['total']==second['tasks']['total']==3
    assert len(first['tasks']['items'])==2 and first['tasks']['has_more']
    assert len(second['tasks']['items'])==1 and not second['tasks']['has_more']
    assert first['tasks']['items'][-1]['id']<second['tasks']['items'][0]['id']
    assert tasks(app,jar,'step=school-session')['tasks']['total']==1
    revoke(engine)
    assert tasks(app,jar)['tasks']=={'items':[],'total':0,'has_more':False}


def test_revoke_removes_next_page_and_count_but_not_peer(app,engine):
    a,b=login(app),login(app,'devon')
    assert tasks(app,a)['tasks']['total']==3
    revoke(engine)
    assert tasks(app,a,'offset=2')['tasks']=={'items':[],'total':0,'has_more':False}
    assert tasks(app,b)['tasks']['total']==2


def test_source_revocation_and_hidden_evidence_do_not_change_task_projection(app,engine):
    a,b=login(app),login(app,'devon')
    before=[tasks(app,j,'limit=20') for j in (a,b)]
    revoke(engine,table=source_read_grant)
    with i2.a.authorization_transaction(engine,i2.HOME) as c:
        c.execute(update(pending).where(pending.c.household_id==i2.HOME).values(
            safety='high-risk',generation=2,evidence_fingerprint='f'*64))
    assert [tasks(app,j,'limit=20') for j in (a,b)]==before


def test_hidden_task_changes_cannot_affect_other_members_page_count_or_errors(app,engine):
    a,b=login(app),login(app,'devon');before=tasks(app,b)
    left={r['id'] for r in tasks(app,a,'limit=20')['tasks']['items']}
    right={r['id'] for r in tasks(app,b,'limit=20')['tasks']['items']}
    private=(left-right).pop()
    with i2.a.authorization_transaction(engine,i2.HOME) as c:
        c.execute(update(task).where(task.c.id==private).values(step='school-session',status='completed',revision=2))
    assert tasks(app,b)==before


def test_foreign_household_session_even_with_local_lease_is_rejected(app,engine):
    i3.register(engine,{'household':{'id':'i3-fern','name':'Fictional I3 Fern'},
        'people':[{'id':'i3-evan','display_name':'Fictional Evan'}],'source_accounts':[]})
    with engine.begin() as c:
        c.execute(insert(household_membership).values(household_id='i3-fern',person_id='i3-evan',state='allowed',revision=1))
        c.execute(insert(external_identity_binding).values(issuer=i2.ISSUER,subject='i3-foreign',
            household_id='i3-fern',person_id='i3-evan',state='allowed',revision=1))
    challenge=app.lab.verifier.challenge();now=int(time())
    token=i3.jwt.encode(dict(iss=i2.ISSUER,sub='i3-foreign',aud='i2-fictional-client',
        iat=now-1,nbf=now-1,exp=now+60,nonce=challenge.nonce),app.lab.key,algorithm='RS256',headers={'kid':'i2-key'})
    result=app.lab.sessions.establish(app.lab.verifier.verify(token,challenge),'i3-fern',request_id='i3-foreign-session')
    assert result.outcome is i2.s.Outcome.COMMITTED
    app.lab.leases[i2.digest(result.bearer)]=app.lab.last+600
    assert read(app,{i2.COOKIE:result.bearer})[0]=='400 Bad Request'


def test_tasks_do_not_query_private_pending_source_payload_or_history(app,engine):
    jar=login(app);statements=[]
    def capture(c,cursor,statement,params,context,many): statements.append(statement.lower())
    sql_event.listen(engine,'before_cursor_execute',capture)
    try: assert tasks(app,jar)['tasks']['total']==3
    finally: sql_event.remove(engine,'before_cursor_execute',capture)
    for name in ('household_pending_item','source_account','raw_source_record','task_domain_event'):
        assert not any(name in s for s in statements)


@pytest.mark.parametrize('query',['limit=0','limit=21','limit=true','limit=01','offset=-1','offset=1000001',
    'limit=2&limit=2','step=other','member=devon','household=i2-willow','q=school',
    'offset=1.0','limit=%32','limit=','limit=2&','limit=2&offset=0&step=school-session&x=1','x='+'a'*128])
def test_bounded_canonical_query_contract(app,query):
    assert read(app,login(app),query)[0]=='400 Bad Request'


@pytest.mark.parametrize('changes',[
    {'HTTP_ORIGIN':'http://evil.example'},{'HTTP_SEC_FETCH_SITE':'cross-site'},
    {'HTTP_SEC_FETCH_SITE':'same-site'},{'HTTP_SEC_FETCH_SITE':None},
    {'HTTP_HOST':'rebind.example'},{'HTTP_X_SAMAS_INTENT':None},
    {'HTTP_ACCEPT':'*/*'},{'CONTENT_LENGTH':'2'}, {'HTTP_TRANSFER_ENCODING':'chunked'},
    {'HTTP_CONTENT_ENCODING':'gzip'},{'HTTP_X_MEMBER':'devon'},
    {'HTTP_AUTHORIZATION':'Bearer fake'},{'REQUEST_URI':'/api/%74asks'},
])
def test_read_request_rejects_cross_origin_bodies_aliases_and_identity_headers(app,changes):
    assert read(app,login(app),**changes)[0]=='400 Bad Request'


def test_get_accepts_browser_origin_omission_but_not_missing_fetch_metadata(app):
    jar=login(app)
    assert read(app,jar,HTTP_ORIGIN=None)[0]=='200 OK'
    assert read(app,jar,HTTP_ORIGIN=None,HTTP_SEC_FETCH_SITE=None)[0]=='400 Bad Request'


@pytest.mark.parametrize('path,method',[('/api/tasks','POST'),('/api/tasks','PUT'),('/api/accept','POST'),
    ('/api/edit','POST'),('/api/archive','POST'),('/api/reopen','POST'),('/api/tasks/task_fake','GET'),
    ('/api/history','GET'),('/fixtures.js','GET'),('/model.js','GET')])
def test_no_mutation_history_fixture_or_detail_endpoints(app,path,method):
    assert request(app,path,method=method,cookies=login(app))[0]=='400 Bad Request'


def test_invalid_session_and_logout_do_not_return_tasks(app):
    assert read(app,{i2.COOKIE:i2.token_urlsafe(32)})[0]=='400 Bad Request'
    jar=login(app);request(app,'/api/logout',cookies=jar)
    assert read(app,jar)[0]=='400 Bad Request'


def test_session_revoked_between_resolve_and_task_transaction_is_rechecked(app,engine,monkeypatch):
    jar=login(app);resolve=app.lab._current
    def changed(bearer):
        result=resolve(bearer);revoke(engine,table=household_session);return result
    monkeypatch.setattr(app.lab,'_current',changed)
    assert read(app,jar)[0]=='400 Bad Request'


def test_backend_error_and_response_limit_never_return_partial_or_prior_page(app,monkeypatch,caplog):
    jar=login(app);assert tasks(app,jar)['tasks']['total']==3
    monkeypatch.setattr(i3,'MAX_RESPONSE',1)
    status,_,raw=read(app,jar)
    assert status=='400 Bad Request' and b'items' not in raw
    def fail(*a,**k): raise RuntimeError('fictional-private-driver '+jar[i2.COOKIE])
    monkeypatch.setattr(app.tasks,'tasks',fail)
    status,_,raw=read(app,jar)
    assert status=='400 Bad Request' and raw==b'{"error":"local_session_unavailable"}'
    assert jar[i2.COOKIE] not in raw.decode()+caplog.text


def node_contract(raw,limit=2,offset=0):
    script="const c=require('./prototypes/i3-workbench/contract.js');const fs=require('fs');try{c.parse(fs.readFileSync(0,'utf8'),Number(process.argv[1]),Number(process.argv[2]));process.stdout.write('valid');}catch(_){process.stdout.write('invalid');}"
    return subprocess.run(['node','-e',script,str(limit),str(offset)],input=raw,capture_output=True,
        text=True,cwd=ROOT,timeout=10).stdout


def test_exact_backend_bytes_pass_browser_validator(app):
    status,_,raw=read(app,login(app))
    assert status=='200 OK' and node_contract(raw.decode())=='valid'
    assert node_contract(raw.decode().replace('"synthetic_only":true','"synthetic_only":true,"synthetic_only":true'))=='invalid'
    assert node_contract(' '*16385)=='invalid'


@pytest.mark.parametrize('change',['schema','extra','private','total','has_more','date','status','id','assignee','revision','duplicates','pagination'])
def test_browser_contract_rejects_malformed_json_without_partial_render(app,change):
    value=tasks(app,login(app));p=value['tasks'];r=p['items'][0]
    if change=='schema':value['schema']='other'
    elif change=='extra':value['session_secret']='forbidden'
    elif change=='private':r['source_id']='forbidden'
    elif change=='total':p['total']=True
    elif change=='has_more':p['has_more']=False
    elif change=='date':r['approved_date']='2035-02-30'
    elif change=='status':r['status']='executed'
    elif change=='id':r['id']='task_unknown'
    elif change=='assignee':r['assignee']='someone-else'
    elif change=='revision':r['revision']=0
    elif change=='duplicates':p['items'][1]=dict(r)
    elif change=='pagination':value['pagination']['offset']=2
    assert node_contract(json.dumps(value,sort_keys=True,separators=(',',':')))=='invalid'


def test_concurrent_pair_claim_delivers_only_one_cookie(app):
    ticket,jar=start(app);app.lab.approve(ticket,'clara')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:request(app,cookies=jar),range(2)))
    assert sorted(r[0] for r in results)==['200 OK','400 Bad Request']
    assert sum(any(k=='Set-Cookie' and v.startswith(i2.COOKIE+'=') and 'Max-Age=0' not in v for k,v in r[1]) for r in results)==1


def test_runtime_limit_and_shutdown_reject_retained_task_session(app):
    jar=login(app);app.lab.clock=lambda:app.lab.started+i2.RUN_SECONDS
    assert read(app,jar)[0]=='400 Bad Request'
    app.lab.close();assert app.lab.leases==app.lab.pairs=={}
    assert read(app,jar)[0]=='400 Bad Request'


def test_accelerated_runner_lifetime_closes_and_cleans_only_owned_temp_store(tmp_path):
    owned=tmp_path/'owned';owned.mkdir();forbidden=tmp_path/'runtime-must-not-exist.sqlite3'
    code="import sys;sys.path.insert(0,'prototypes/i3-workbench');import serve_workbench as w;w.i2.RUN_SECONDS=1;sys.argv=['serve_workbench.py','--synthetic-only'];w.main()"
    process=subprocess.Popen([sys.executable,'-u','-c',code],cwd=ROOT,stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,TMPDIR=str(owned),DATABASE_URL='sqlite:///'+str(forbidden)))
    try:
        process.wait(timeout=15)
        out,err=process.communicate()
        assert process.returncode==0 and not err
        assert list(owned.iterdir())==[] and not forbidden.exists()
    finally:
        if process.poll() is None:process.kill();process.communicate()


def test_offline_assets_unchanged_and_connection_has_no_task_model():
    html=(i3.HERE/'index.html').read_text();js=(i3.HERE/'workbench.js').read_text()
    assert 'fixtures.js' not in html and 'model.js' not in html and 'presentation.js' not in html
    assert "connect-src 'none'" in (ROOT/'prototypes/h0-workbench/index.html').read_text()
    assert 'localStorage' not in js and 'sessionStorage' not in js and 'document.cookie' not in js
