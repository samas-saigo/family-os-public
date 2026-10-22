"""New fictional I6 evidence/permissions; owned SQLite or isolated PG schemas only."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from sqlalchemy import select,event as sql_event,update
from family_os import _pending_explanations as e
from family_os.schema import fictional_information_revision as ledger,household_pending_item as pending,pending_member_right as rights,task_member_grant as grants,source_read_grant as sources,task_domain_event as events,household_task as task,household_membership as members,external_identity_binding as bindings
from test_i5_information import i5,f,r,get,count
from test_i2_local_session import login,request
from test_i4b_workbench import i4b,i2,t,post,val,mutate

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('i6_workbench',ROOT/'prototypes/i6-workbench/serve_explanations.py')
i6=importlib.util.module_from_spec(spec);sys.modules[spec.name]=i6;spec.loader.exec_module(i6)


@pytest.fixture
def lab(engine):
    owner=i2.Lab(engine,synthetic_only=True);producer=i5.initialize(owner);app=i6.Workbench(owner,38199)
    yield app,producer
    app.close();owner.close()


def explain(app,jar,pid,revision=1,**change):
    env=dict(method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING=f'id={pid}&revision={revision}')
    env.update(change)
    return request(app,'/api/pending/explanation',cookies=jar,**env)


def test_fictional_support_date_and_no_domain_write_on_inspection(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');pid=producer.process(i5.cases()[0]).pending_id
    with engine.connect() as c:before={table.name:c.execute(select(table)).all() for table in (pending,ledger,rights,grants,events,task)}
    for jar,capability in ((a,True),(b,False)):
        res=explain(app,jar,pid);assert res[0]=='200 OK';v=val(res)
        assert len(res[2])<=4096 and 'no-store' in dict(res[1])['Cache-Control']
        assert set(v)=={'schema','synthetic_only','id','revision','generation','definition','source_kind','step','supported_date','action','reasons','safety','can_accept'}
        assert v['action']=='supported' and v['reasons']==['structured-support'] and v['supported_date']=='2040-09-18'
        assert v['safety']=='clear' and v['can_accept'] is capability
        assert not any(token in res[2].decode() for token in ('source_account_id','fingerprint','i5-shared-source','evidence_json','sender','confidence'))
    with engine.connect() as c:assert {table.name:c.execute(select(table)).all() for table in (pending,ledger,rights,grants,events,task)}==before


@pytest.mark.parametrize('index,peer,other',[(5,'clara','devon'),(6,'devon','clara')])
def test_private_origin_does_not_follow_shared_task(lab,engine,index,peer,other):
    app,producer=lab;a,b=login(app,peer),login(app,other);pid=producer.process(i5.cases()[index]).pending_id
    assert explain(app,a,pid)[0]=='200 OK'
    assert explain(app,b,pid)==explain(app,b,'i5-missing')
    p=val(post(app,a,'pending/preview',{'id':pid,'revision':1}))
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.COMMITTED.value
    with engine.connect() as c:tid=c.scalar(select(task.c.id).where(task.c.pending_id==pid))
    assert tid in {v['id'] for v in get(app,b,'tasks')['items']}
    assert explain(app,b,pid)==explain(app,b,'i5-missing')
    assert explain(app,a,pid,2)[0]=='400 Bad Request'  # Accepted evidence is not a task projection.


@pytest.mark.parametrize('table,scope',[(sources,'source'),(rights,'pending'),(members,'member'),(bindings,'binding')])
def test_current_authority_before_ledger_inspection(lab,engine,table,scope):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    where=(table.c.person_id=='i2-clara',)
    if scope=='source':where+=(table.c.source_account_id==f.Source.SHARED.value,)
    if scope=='pending':where+=(table.c.pending_id==pid,)
    mutate(app,table,where,state='revoked',revision=2)
    statements=[]
    def capture(c,cursor,sql,*args):statements.append(sql.lower())
    sql_event.listen(engine,'before_cursor_execute',capture)
    try:res=explain(app,a,pid)
    finally:sql_event.remove(engine,'before_cursor_execute',capture)
    assert res[0]=='400 Bad Request' and res[2]==b'{"error":"local_session_unavailable"}'
    assert not any('fictional_information_revision' in sql for sql in statements)


@pytest.mark.parametrize('safety',[None,{'private':'not-for-observation-reader'},'HIGH_RISK','UNAVAILABLE'])
def test_observation_only_ignores_private_safety_values_and_validation(lab,engine,safety):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    mutate(app,sources,(sources.c.source_account_id==f.Source.SHARED.value,sources.c.person_id=='i2-clara'),security=False,revision=2)
    baseline=explain(app,a,pid);assert baseline[0]=='200 OK' and val(baseline)['safety'] is None and not val(baseline)['can_accept']
    with engine.begin() as c:
        raw=json.loads(c.scalar(select(ledger.c.evidence_json).where(ledger.c.pending_id==pid)))
        if safety is None:raw.pop('safety')
        else:raw['safety']=safety
        c.execute(update(ledger).where(ledger.c.pending_id==pid).values(evidence_json=json.dumps(raw)))
    assert explain(app,a,pid)==baseline  # Scope-excluded safety cannot change errors either.


def test_security_reader_rejects_inconsistent_authorized_risk(lab,engine):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    with engine.begin() as c:
        raw=json.loads(c.scalar(select(ledger.c.evidence_json).where(ledger.c.pending_id==pid)));raw['safety']='HIGH_RISK'
        c.execute(update(ledger).where(ledger.c.pending_id==pid).values(evidence_json=json.dumps(raw)))
    assert explain(app,a,pid)==explain(app,a,'i5-missing')


@pytest.mark.parametrize('change',['generation','fingerprint','definition','business','json','missing','record'])
def test_inconsistent_evidence_has_one_non_disclosing_failure(lab,engine,change):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    with engine.begin() as c:
        if change=='generation':c.execute(update(pending).where(pending.c.id==pid).values(generation=2))
        elif change=='fingerprint':c.execute(update(pending).where(pending.c.id==pid).values(evidence_fingerprint='0'*64))
        elif change=='definition':c.execute(update(pending).where(pending.c.id==pid).values(definition_version='other-v1'))
        elif change=='record':c.execute(update(ledger).where(ledger.c.pending_id==pid).values(record_id='i5-i6-unrelated'))
        elif change=='missing':c.execute(update(ledger).where(ledger.c.pending_id==pid).values(pending_id=None))
        else:c.execute(update(ledger).where(ledger.c.pending_id==pid).values(evidence_json='{}' if change=='business' else '{invalid'))
    assert explain(app,a,pid)==explain(app,a,'i5-missing')


def test_change_revert_old_preview_and_explanation_cannot_revive(lab):
    app,producer=lab;a=login(app);first=i5.cases()[0];pid=producer.process(first).pending_id
    p=val(post(app,a,'pending/preview',{'id':pid,'revision':1}));original=val(explain(app,a,pid))
    producer.process(replace(first,generation=2,safety=r.Safety.UNAVAILABLE))
    assert explain(app,a,pid)[0]=='400 Bad Request'
    current=val(explain(app,a,pid,2));assert current['safety']=='unknown' and not current['can_accept']
    producer.process(replace(first,generation=3))
    assert explain(app,a,pid)[0]=='400 Bad Request'
    final=val(explain(app,a,pid,3));assert final['generation']==3 and final['action']==original['action']
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']!=t.Outcome.COMMITTED.value


def test_all_source_revoke_block_regrant_never_explains_blocked_business_as_current(lab):
    app,producer=lab;a=login(app);first=i5.cases()[0];pid=producer.process(first).pending_id
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='revoked',revision=2)
    producer.process(replace(first,generation=2,safety=r.Safety.HIGH_RISK,step=t.Step.HOME))
    assert explain(app,a,pid,2)[0]=='400 Bad Request'
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='allowed',revision=3)
    v=val(explain(app,a,pid,2));assert v['action']=='unavailable' and v['safety']=='unknown'
    assert v['step']=='school-session' and not v['can_accept'] and v['reasons']==['current-evidence-unavailable']
    producer.process(replace(first,generation=3))
    assert val(explain(app,a,pid,3))['can_accept']


@pytest.mark.parametrize('index,reason',[(1,'conflicting-action-evidence'),(7,'independent-service-only')])
def test_conflicting_and_mixed_service_questions_never_gain_acceptance(lab,engine,index,reason):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[index]).pending_id;before=count(engine,task)
    for _ in range(3):
        v=val(explain(app,a,pid));assert v['reasons']==[reason] and v['step'] is None and not v['can_accept']
    assert count(engine,task)==before


@pytest.mark.parametrize('index',[2,3,4])
def test_quiet_or_security_only_new_inputs_cannot_be_explanation_backdoor(lab,index):
    app,producer=lab;a=login(app);value=i5.cases()[index];assert producer.process(value).pending_id is None
    pid=f.pending_identity(i2.HOME,value.source,value.record_id)
    assert explain(app,a,pid)==explain(app,a,'i5-missing')


@pytest.mark.parametrize('query',['','id=x','id=x&revision=0','id=x&revision=01','id=x&revision=true','id=x&revision=1000001',
    'id=x&id=x','id=x&revision=1&who=devon','id=x&revision=1&revision=1','id=%78&revision=1','id=x&revision=','id=x&revision=1#x','person_id=i2-devon&revision=1'])
def test_strict_query_contract(lab,query):
    app,_=lab;a=login(app);assert explain(app,a,'x',QUERY_STRING=query)[0]=='400 Bad Request'


@pytest.mark.parametrize('change',[{'HTTP_ORIGIN':'http://attacker.invalid'},{'HTTP_HOST':'attacker.invalid'},{'HTTP_SEC_FETCH_SITE':'cross-site'},
    {'HTTP_X_SAMAS_INTENT':''},{'HTTP_ACCEPT':'*/*'},{'CONTENT_TYPE':'application/json'},{'HTTP_X_PERSON':'i2-devon'},
    {'HTTP_CONTENT_ENCODING':'gzip'},{'HTTP_TRANSFER_ENCODING':'chunked'},{'method':'POST','body':b'{}'},
    {'HTTP_COOKIE':'samas_i2=invalid'}])
def test_same_origin_session_and_empty_read_only_requests(lab,change):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    assert explain(app,a,pid,**change)[0]=='400 Bad Request'


def test_i3_i4a_i4b_default_adapters_reject_explanation_route(lab):
    app,_=lab;a=login(app)
    for cls in (i4b.i3.Workbench,i4b.i4.Workbench,i4b.Workbench):
        original=cls(app.lab,38199)
        try:assert explain(original,a,'i5-school')[0]=='400 Bad Request'
        finally:
            if hasattr(original,'close'):original.close()


def test_missing_step_is_new_fictional_evidence_not_an_invented_task(lab):
    app,producer=lab;a=login(app);peer=tuple(f.Peer)
    plan=f.Plan(f.Source.SHARED,'i5-i6-missing',peer,peer,(f.Peer.CLARA,),peer)
    producer=f.Coordinator(app.tasks,tuple(producer._plans.values())+(plan,),synthetic_only=True)
    value=replace(i5.cases()[0],record_id=plan.record_id,step=None,observed_date=None,date_basis=f.DateBasis.NONE)
    pid=producer.process(value).pending_id;v=val(explain(app,a,pid))
    assert v['action']=='supported' and v['reasons']==['missing-action-step'] and v['step'] is None and v['supported_date'] is None and not v['can_accept']


def test_no_secret_data_dependencies_or_production_wiring():
    import ast,subprocess
    path=ROOT/'src/family_os/_pending_explanations.py';tree=ast.parse(path.read_text());names=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):names.extend(alias.name for alias in node.names)
        if isinstance(node,ast.ImportFrom):names.append(node.module)
    assert set(names)<={'dataclasses','datetime','enum','json','sqlalchemy','family_os','family_os._household_tasks','family_os.schema'}
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and node.module=='family_os':assert [a.name for a in node.names]==['_fictional_information']
    assert {node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id=='f'}<={'Origin','CONTRACT_VERSION','routing','Step','DateBasis','_hash','_record','pending_identity','Source'}
    for other in (ROOT/'src').rglob('*.py'):
        if other!=path:assert '_pending_explanations' not in other.read_text()
    result=__import__('subprocess').run([sys.executable,str(ROOT/'prototypes/i6-workbench/serve_explanations.py')],capture_output=True,text=True,timeout=15)
    assert result.returncode!=0 and '--synthetic-only' in result.stderr and 'Open ' not in result.stdout
    node=subprocess.run(['node','tests/browser/i6-contract.test.js'],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert node.returncode==0,node.stderr


@pytest.mark.parametrize('value',[False,1,'true',None])
def test_service_opt_in_is_exact(value):
    with pytest.raises(t.TaskError):e.ExplanationService(None,synthetic_only=value)


def test_fabricated_household_and_invalid_session_have_no_explanation(lab):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    other=e.ExplanationService(t.TaskService(app.lab.sessions,'i6-fictional-other-home',synthetic_only=True),synthetic_only=True)
    with pytest.raises(t.TaskError):other.read(a[i2.COOKIE],pid,1)
    assert explain(app,{i2.COOKIE:'invalid'},pid)==explain(app,{i2.COOKIE:'invalid'},'i5-missing')


def test_explanation_to_preview_rejects_silent_new_generation_rebase(lab):
    app,producer=lab;a=login(app);first=i5.cases()[0];pid=producer.process(first).pending_id
    assert val(explain(app,a,pid))['revision']==1
    producer.process(replace(first,generation=2,step=t.Step.HOME))
    before=sum(len(v) for v in app.receipts.values())
    assert post(app,a,'pending/preview',{'id':pid,'revision':1})[0]=='400 Bad Request'
    assert sum(len(v) for v in app.receipts.values())==before
    assert post(app,a,'pending/preview',{'id':pid})[0]=='400 Bad Request'
    assert val(explain(app,a,pid,2))['step']=='home-visit'
    p=val(post(app,a,'pending/preview',{'id':pid,'revision':2}))
    assert p['revision']==2 and p['step']=='home-visit'


@pytest.mark.parametrize('revision',[True,'1',0,1000001,None])
def test_i6_preview_expected_revision_is_strict(lab,revision):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    assert post(app,a,'pending/preview',{'id':pid,'revision':revision})[0]=='400 Bad Request'


@pytest.mark.parametrize('action',[r.ActionEvidence.UNSUPPORTED,r.ActionEvidence.NONE])
def test_new_fictional_insufficient_action_evidence_stays_unresolved(lab,action):
    app,producer=lab;a=login(app);peer=tuple(f.Peer)
    plan=f.Plan(f.Source.SHARED,'i5-i6-insufficient',peer,peer,(f.Peer.CLARA,),peer)
    producer=f.Coordinator(app.tasks,tuple(producer._plans.values())+(plan,),synthetic_only=True)
    value=replace(i5.cases()[0],record_id=plan.record_id,business=r.Business(action=action),step=None,observed_date=None,date_basis=f.DateBasis.NONE)
    pid=producer.process(value).pending_id;v=val(explain(app,a,pid))
    assert v['reasons']==['insufficient-action-evidence'] and v['action']==action.value and not v['can_accept']
    assert v['step'] is None and v['supported_date'] is None
