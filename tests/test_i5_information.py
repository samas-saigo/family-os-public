"""Owned fictional SQL; no provider, household runtime or frozen evaluation data."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import date
import importlib.util
from pathlib import Path
import sys
import json

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select,func,event as sql_event,update,insert,inspect
from family_os import _fictional_information as f
from family_os.schema import (fictional_information_revision as ledger,household_pending_item as pending,
    household_task as task,pending_member_right as rights,pending_task_publication as plans,
    task_member_grant as grants,task_domain_event as events,source_read_grant as sources,
    household_membership as members)
from test_i2_local_session import login,request
from test_i4b_workbench import i4b,i2,t,post,val,preview,confirm,mutate

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('i5_workbench',ROOT/'prototypes/i5-workbench/serve_information.py')
i5=importlib.util.module_from_spec(spec);sys.modules[spec.name]=i5;spec.loader.exec_module(i5)
r=f.routing


@pytest.fixture
def lab(engine):
    owner=i2.Lab(engine,synthetic_only=True);coordinator=i5.initialize(owner);app=i4b.Workbench(owner,38199)
    yield app,coordinator
    app.close();owner.close()


def count(engine,table):
    with engine.connect() as c:return c.scalar(select(func.count()).select_from(table))


def get(app,jar,kind='pending',query='limit=12&offset=0'):
    response=request(app,'/api/'+kind,cookies=jar,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING=query)
    return val(response)[kind]


@pytest.mark.parametrize('safety',list(r.Safety))
@pytest.mark.parametrize('business,destination',[
    (r.Business(action=r.ActionEvidence.SUPPORTED,importance=r.Importance.IMPORTANT),'pending'),
    (r.Business(action=r.ActionEvidence.CONFLICTING),'pending'),
    (r.Business(action=r.ActionEvidence.UNSUPPORTED),'pending'),
    (r.Business(promotion=True,importance=r.Importance.NOT_IMPORTANT,expiry=r.Expiry.EXPIRED),'promotion'),
    (r.Business(promotion=True,importance=r.Importance.IMPORTANT),'pending'),
    (r.Business(informational=True,importance=r.Importance.NOT_IMPORTANT),'information'),
    (r.Business(importance=r.Importance.NOT_IMPORTANT),'abstained'),
])
def test_stage_a_matrix_independent_security_priority(safety,business,destination):
    value=replace(i5.cases()[0],safety=safety,business=business)
    expected=destination if safety is r.Safety.SAFE_TO_ROUTE else 'security-held' if safety in (r.Safety.SUSPICIOUS,r.Safety.HIGH_RISK) else 'unassessed'
    assert f.classify(value)==expected


@pytest.mark.parametrize('change',[{'source':'i5-shared-source'},{'generation':True},{'generation':0},{'generation':1001},
    {'record_id':'real-mail@example.invalid'},{'record_id':'i5-'+'a'*33},{'safety':'safe'},{'business':{}},
    {'step':'school-session'},{'observed_date':'2040-01-01'},{'observed_date':date(2026,1,1)},
    {'definition':'other'},{'origin':'browser'},{'observed_date':True}])
def test_strict_projection_rejects_noncontract_fields(change):
    with pytest.raises(f.InputError):replace(i5.cases()[0],**change)


def test_real_pipeline_no_task_until_explicit_current_acceptance(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');before=count(engine,task)
    value=i5.cases()[0];result=producer.process(value)
    assert result.outcome is f.Outcome.COMMITTED and result.effect=='created'
    assert count(engine,task)==before
    rows=get(app,a)['items'];assert next(r for r in rows if r['id']==result.pending_id)['can_accept']
    assert not next(r for r in get(app,b)['items'] if r['id']==result.pending_id)['can_accept']
    assert post(app,b,'pending/preview',{'id':result.pending_id})[0]=='400 Bad Request'
    p=val(post(app,a,'pending/preview',{'id':result.pending_id}))
    assert count(engine,task)==before  # Inspection/cancel has no write.
    p=val(post(app,a,'pending/preview',{'id':result.pending_id}))
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.COMMITTED.value
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.REPLAY.value
    assert count(engine,task)==before+1
    assert result.pending_id not in {v['id'] for v in get(app,a)['items']}
    shared={v['id'] for v in get(app,a,'tasks')['items']} & {v['id'] for v in get(app,b,'tasks')['items']}
    with engine.connect() as c:tid=c.scalar(select(task.c.id).where(task.c.pending_id==result.pending_id))
    assert tid in shared
    assert confirm(app,a,preview(app,a,tid,'assign','i2-devon'))['outcome']==t.Outcome.COMMITTED.value
    assert tid in {v['id'] for v in get(app,a,'tasks')['items']} & {v['id'] for v in get(app,b,'tasks')['items']}


def test_all_startup_branches_private_visibility_and_task_independence(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');p0,t0=count(engine,pending),count(engine,task)
    results=i5.feed(producer)
    assert count(engine,pending)==p0+5 and count(engine,task)==t0
    assert [v.destination for v in results]==['pending','pending','promotion','security-held','information','pending','pending','pending']
    assert [v.pending_id is not None for v in results]==[True,True,False,False,False,True,True,True]
    for jar,own,hidden in [(a,results[5],results[6]),(b,results[6],results[5])]:
        ids={v['id'] for v in get(app,jar)['items']}
        assert own.pending_id in ids and hidden.pending_id not in ids
        assert post(app,jar,'pending/preview',{'id':hidden.pending_id})[0]=='400 Bad Request'
    for index in (1,7):
        row=next(v for v in get(app,a)['items'] if v['id']==results[index].pending_id)
        assert row['step'] is None and row['supported_date'] is None and not row['can_accept']
        assert post(app,a,'pending/preview',{'id':row['id']})[0]=='400 Bad Request'
    p=val(post(app,a,'pending/preview',{'id':results[5].pending_id}))
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.COMMITTED.value
    mutate(app,sources,(sources.c.source_account_id==f.Source.CLARA.value,),state='revoked',revision=2)
    assert results[5].pending_id not in {v['id'] for v in get(app,a)['items']}
    with engine.connect() as c:tid=c.scalar(select(task.c.id).where(task.c.pending_id==results[5].pending_id))
    assert tid in {v['id'] for v in get(app,b,'tasks')['items']}
    assert count(engine,ledger)==8


@pytest.mark.parametrize('change',['risk','unknown','conflict','missing-step','promotion','information'])
def test_evidence_updates_invalidate_old_preview_and_revert_never_restores(lab,engine,change):
    app,producer=lab;a=login(app);first=i5.cases()[0];result=producer.process(first)
    p=val(post(app,a,'pending/preview',{'id':result.pending_id}));before=count(engine,task)
    kwargs={'generation':2}
    if change=='risk':kwargs['safety']=r.Safety.HIGH_RISK
    elif change=='unknown':kwargs['safety']=r.Safety.UNAVAILABLE
    elif change=='conflict':kwargs['business']=r.Business(action=r.ActionEvidence.CONFLICTING)
    elif change=='missing-step':kwargs['step']=None
    else:kwargs['business']=r.Business(promotion=change=='promotion',informational=change=='information',importance=r.Importance.NOT_IMPORTANT)
    assert producer.process(replace(first,**kwargs)).outcome is f.Outcome.COMMITTED
    outcome=val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']
    assert outcome in (t.Outcome.STALE.value,t.Outcome.UNAVAILABLE.value,t.Outcome.UNKNOWN.value)
    assert count(engine,task)==before
    assert producer.process(replace(first,generation=3)).outcome is f.Outcome.COMMITTED
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']!=t.Outcome.COMMITTED.value
    with engine.connect() as c:
        rows=c.execute(select(ledger).where(ledger.c.record_id==first.record_id).order_by(ledger.c.generation)).mappings().all()
    assert len(rows)==3 and rows[0]['evidence_fingerprint']==rows[2]['evidence_fingerprint']


def test_accepted_history_is_never_overwritten_or_republished(lab,engine):
    app,producer=lab;a=login(app);first=i5.cases()[0];res=producer.process(first)
    p=val(post(app,a,'pending/preview',{'id':res.pending_id}));val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))
    with engine.connect() as c:before=c.execute(select(task)).all();prior=c.execute(select(events)).all()
    for n,safety in enumerate((r.Safety.HIGH_RISK,r.Safety.SAFE_TO_ROUTE),2):
        assert producer.process(replace(first,generation=n,safety=safety)).effect=='accepted-history-only'
    with engine.connect() as c:assert c.execute(select(task)).all()==before and c.execute(select(events)).all()==prior
    assert res.pending_id not in {v['id'] for v in get(app,a)['items']}
    assert val(post(app,a,'pending/outcome',dict(receipt=p['receipt'])))['outcome']==t.Outcome.COMMITTED.value


@pytest.mark.parametrize('mode',['duplicate','conflicting'])
def test_real_database_concurrent_inputs_use_one_pending_and_one_generation(lab,engine,mode):
    app,producer=lab;value=i5.cases()[0]
    other=value if mode=='duplicate' else replace(value,safety=r.Safety.HIGH_RISK)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(producer.process,(value,other)))
    assert sorted(v.outcome.value for v in results)==sorted([f.Outcome.COMMITTED.value,(f.Outcome.REPLAY if mode=='duplicate' else f.Outcome.CONFLICT).value])
    assert count(engine,ledger)==1
    assert sum(v.effect=='created' for v in results)<=2  # replay reports its historical effect, never a second insert
    with engine.connect() as c:assert c.scalar(select(func.count()).select_from(pending).where(pending.c.id==f.pending_identity(i2.HOME,value.source,value.record_id)))<2


def test_no_regrant_on_reprocessing_or_epoch_changes(lab,engine):
    app,producer=lab;a=login(app);value=i5.cases()[0];pid=producer.process(value).pending_id
    mutate(app,rights,(rights.c.pending_id==pid,rights.c.person_id=='i2-clara'),state='revoked',revision=2)
    mutate(app,plans,(plans.c.pending_id==pid,plans.c.person_id=='i2-devon'),state='revoked',revision=2)
    assert producer.process(replace(value,generation=2)).outcome is f.Outcome.COMMITTED
    assert pid not in {v['id'] for v in get(app,a)['items']}
    with engine.connect() as c:
        assert c.scalar(select(plans.c.state).where(plans.c.pending_id==pid,plans.c.person_id=='i2-devon'))=='revoked'
    changed=f.Coordinator(app.tasks,(replace(producer._plans[(value.source,value.record_id)],publishers=tuple(f.Peer)),),synthetic_only=True)
    assert changed.process(replace(value,generation=3)).outcome is f.Outcome.CONFLICT


def test_page_population_generated_by_processor_and_authorized_before_count(lab):
    app,producer=lab;a,b=login(app),login(app,'devon');before=get(app,a)['total']
    for n in range(14):
        value=replace(i5.cases()[0],record_id='i5-page-'+str(n))
        assert producer.process(value).effect=='created'
    p=get(app,a);last=get(app,a,query='limit=12&offset=12')
    assert p['total']==last['total']==before+14 and len(p['items'])==12 and p['has_more']
    assert len(last['items'])==before+2 and not last['has_more']
    assert not {v['id'] for v in p['items']} & {v['id'] for v in last['items']}
    mutate(app,sources,(sources.c.source_account_id==f.Source.SHARED.value,sources.c.person_id=='i2-devon'),state='revoked',revision=2)
    assert get(app,b)['total']==4 and get(app,a)['total']==before+14


def test_rollback_and_unknown_processing_fence_fresh_reconciliation(lab,engine,monkeypatch):
    app,producer=lab;value=i5.cases()[0];original=f.authorization_transaction
    @contextmanager
    def lost(*a,**kw):
        with original(*a,**kw) as c:yield c
        raise RuntimeError('synthetic acknowledgment loss')
    monkeypatch.setattr(f,'authorization_transaction',lost)
    assert producer.process(value).outcome is f.Outcome.UNKNOWN
    assert producer.process(replace(value,generation=2)).outcome is f.Outcome.UNKNOWN
    assert producer.verify(value).outcome is f.Outcome.UNKNOWN
    monkeypatch.setattr(f,'authorization_transaction',original)
    assert producer.verify(value).outcome is f.Outcome.COMMITTED
    assert producer.process(value).outcome is f.Outcome.REPLAY and count(engine,ledger)==1
    before=count(engine,pending)
    def fail(c,cursor,statement,*args):
        if statement.lstrip().lower().startswith('insert into fictional_information_revision'):raise RuntimeError('synthetic ledger failure')
    sql_event.listen(engine,'before_cursor_execute',fail)
    try:assert producer.process(replace(value,generation=2)).outcome is f.Outcome.UNKNOWN
    finally:sql_event.remove(engine,'before_cursor_execute',fail)
    assert count(engine,pending)==before and count(engine,ledger)==1
    assert producer.verify(replace(value,generation=2)).outcome is f.Outcome.UNKNOWN


def test_migration_downgrade_preserves_t1_and_all_existing_tables(lab,engine):
    app,producer=lab;i5.feed(producer)
    from family_os.schema import metadata
    all_tables=[table for table in metadata.sorted_tables if table is not ledger]
    # I8 adds a nullable event reason that does not exist at the old T1 target.
    # Compare every historical field; only that empty additive column is omitted.
    columns={table.name:[column for column in table.c if not (table.name=='task_domain_event' and column.name=='personal_reason')] for table in all_tables}
    with engine.connect() as c:
        assert c.exec_driver_sql('SELECT 1 FROM task_domain_event WHERE personal_reason IS NOT NULL').first() is None
        before={table.name:c.execute(select(*columns[table.name])).all() for table in all_tables}
    cfg=Config(str(ROOT/'alembic.ini'));command.check(cfg)
    command.downgrade(cfg,'e41a9b720dc3');assert 'fictional_information_revision' not in inspect(engine).get_table_names()
    with engine.connect() as c:assert {table.name:c.execute(select(*columns[table.name])).all() for table in all_tables}==before
    command.upgrade(cfg,'head');command.check(cfg);assert count(engine,ledger)==0
    # Downgraded producer provenance cannot be guessed back from a deterministic ID.
    assert producer.process(i5.cases()[0]).outcome is f.Outcome.REJECTED


@pytest.mark.parametrize('safety',list(r.Safety))
def test_only_current_safe_evidence_can_create_new_acceptable_pending(lab,safety):
    app,producer=lab;a=login(app);result=producer.process(replace(i5.cases()[0],safety=safety))
    assert result.outcome is f.Outcome.COMMITTED
    if safety is r.Safety.SAFE_TO_ROUTE:
        assert result.pending_id in {v['id'] for v in get(app,a)['items']}
    else:assert result.pending_id is None


@pytest.mark.parametrize('epoch,source_allowed',[(1,False),(2,True)])
def test_preapproval_cannot_resurrect_source_or_member(lab,engine,epoch,source_allowed):
    app,producer=lab;first=i5.cases()[0]
    if not source_allowed:mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='revoked',revision=2)
    else:mutate(app,members,(members.c.person_id=='i2-clara',),revision=epoch)
    p0=count(engine,pending)
    assert producer.process(first).effect=='blocked'
    assert count(engine,pending)==p0


def test_distinct_source_scope_and_plan_not_derived_from_membership(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');first=i5.cases()[0]
    mutate(app,sources,(sources.c.source_account_id==first.source.value,sources.c.person_id=='i2-clara'),security=False,revision=2)
    pid=producer.process(first).pending_id
    assert not next(v for v in get(app,a)['items'] if v['id']==pid)['can_accept']
    assert post(app,a,'pending/preview',{'id':pid})[0]=='400 Bad Request'
    mutate(app,rights,(rights.c.pending_id==pid,rights.c.person_id=='i2-devon'),can_review=False,can_publish=False,revision=2)
    assert not next(v for v in get(app,b)['items'] if v['id']==pid)['can_accept']
    # Current source observations alone never create accept/review permission.
    with engine.connect() as c:assert not c.scalar(select(rights.c.can_publish).where(rights.c.pending_id==pid,rights.c.person_id=='i2-devon'))


def test_restarts_exact_replay_same_plan_and_conflicting_generation(lab,engine):
    app,producer=lab;first=i5.cases()[0];result=producer.process(first);n=count(engine,pending)
    other=f.Coordinator(app.tasks,tuple(producer._plans.values()),synthetic_only=True)
    assert other.process(first).outcome is f.Outcome.REPLAY
    assert other.process(replace(first,generation=3)).outcome is f.Outcome.REJECTED
    assert other.process(replace(first,safety=r.Safety.UNKNOWN)).outcome is f.Outcome.CONFLICT
    assert other.process(replace(first,record_id='i5-unapproved')).outcome is f.Outcome.REJECTED
    assert count(engine,pending)==n and count(engine,ledger)==1


def test_provider_and_other_household_not_a_synthetic_authority(lab,engine):
    from family_os.schema import source_account
    app,producer=lab;first=i5.cases()[0];before=count(engine,ledger)
    mutate(app,source_account,(source_account.c.id==first.source.value,),provider='gmail')
    assert producer.process(first).outcome is f.Outcome.REJECTED
    assert count(engine,ledger)==before
    other=t.TaskService(app.lab.sessions,'i5-unrelated-home',synthetic_only=True)
    service=f.Coordinator(other,tuple(producer._plans.values()),synthetic_only=True)
    assert service.process(first).outcome not in (f.Outcome.COMMITTED,f.Outcome.REPLAY)
    assert count(engine,ledger)==before


def test_ledger_bounds_and_household_foreign_keys(lab,engine):
    from sqlalchemy.exc import IntegrityError
    app,producer=lab;producer.process(i5.cases()[0])
    with engine.connect() as c:row=dict(c.execute(select(ledger)).mappings().one())
    for change in ({'generation':0},{'generation':1001},{'household_id':'i5-foreign'},
                   {'record_id':'x'*36},{'origin':'browser'},{'destination':'task'},
                   {'effect':'automatically-accepted'},{'evidence_json':'x'*1025}):
        with pytest.raises(IntegrityError):
            with engine.begin() as c:c.execute(insert(ledger).values(**(dict(row,generation=2)|change)))


def test_no_grant_or_task_update_statements_on_reprocessing(lab,engine):
    app,producer=lab;value=i5.cases()[0];producer.process(value);statements=[]
    def capture(c,cursor,statement,*args):statements.append(statement.lower())
    sql_event.listen(engine,'before_cursor_execute',capture)
    try:producer.process(replace(value,generation=2))
    finally:sql_event.remove(engine,'before_cursor_execute',capture)
    assert not any(s.lstrip().startswith(('insert into '+table,'update '+table,'delete from '+table)) for table in
        ('source_read_grant','pending_member_right','pending_task_publication','household_task','task_member_grant','task_domain_event') for s in statements)
    assert not any(s.lstrip().startswith(('update fictional_information_revision','delete from fictional_information_revision')) for s in statements)


def test_task_unknown_exact_receipt_and_current_evidence(lab,engine,monkeypatch):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    p=val(post(app,a,'pending/preview',{'id':pid}));original=app.tasks.apply;verify=app.tasks.verify_outcome;n=count(engine,task)
    def lost(*a,**k):assert original(*a,**k).outcome is t.Outcome.COMMITTED;raise RuntimeError('synthetic response loss')
    monkeypatch.setattr(app.tasks,'apply',lost)
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.UNKNOWN.value
    monkeypatch.setattr(app.tasks,'verify_outcome',lambda *a,**k:t.Result(t.Outcome.UNKNOWN))
    assert post(app,a,'pending/preview',{'id':'i3-unaccepted'})[0]=='400 Bad Request'
    monkeypatch.setattr(app.tasks,'verify_outcome',verify)
    assert val(post(app,a,'pending/outcome',{'receipt':p['receipt']}))['outcome']==t.Outcome.COMMITTED.value
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.REPLAY.value
    assert count(engine,task)==n+1


def test_no_browser_producer_or_permission_routes(lab):
    app,producer=lab;a=login(app)
    for route in ('information','information/process','routing','producer','fixtures','grants'):
        assert post(app,a,route,{})[0]=='400 Bad Request'
    assert producer.process({'source':'anything'}).outcome is f.Outcome.REJECTED


def test_explicit_opt_in_and_no_provider_model_dependencies():
    import ast,subprocess
    module=ast.parse((ROOT/'src/family_os/_fictional_information.py').read_text())
    names=[]
    for node in ast.walk(module):
        if isinstance(node,ast.Import):names.extend(alias.name for alias in node.names)
        if isinstance(node,ast.ImportFrom):names.append(node.module or '')
    assert not any(any(part in name for part in ('providers','requests','urllib','keyring','ollama','socket')) for name in names)
    assert set(names)<={'dataclasses','datetime','enum','hashlib','json','re','sqlalchemy','family_os',
        'family_os._household_authorization','family_os._household_tasks','family_os.schema'}
    for node in ast.walk(module):
        if isinstance(node,ast.ImportFrom) and node.module=='family_os':assert [n.name for n in node.names]==['_synthetic_routing']
    for path in (ROOT/'src').rglob('*.py'):
        if path in (ROOT/'src/family_os/_fictional_information.py',ROOT/'src/family_os/_pending_explanations.py'):continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node,ast.Import):assert all(n.name!='family_os._fictional_information' for n in node.names)
            if isinstance(node,ast.ImportFrom):
                assert node.module!='family_os._fictional_information'
                if node.module=='family_os':assert all(n.name!='_fictional_information' for n in node.names)
    for flag in (False,1,'true'):
        with pytest.raises(f.InputError):f.Coordinator(None,(),synthetic_only=flag)
    result=subprocess.run([sys.executable,str(ROOT/'prototypes/i5-workbench/serve_information.py')],capture_output=True,text=True,timeout=15)
    assert result.returncode!=0 and '--synthetic-only' in result.stderr and 'Open ' not in result.stdout


def test_named_terminal_experiments_are_exact_and_bounded(lab):
    app,producer=lab
    for command in ('process','repeat','change','revert','repeat'):
        results=i5.experiment(producer,command)
        assert len(results)==(8 if command in ('process','repeat') else 1)
    with pytest.raises(i2.Unavailable):i5.experiment(producer,'anything')


def test_processing_and_human_acceptance_serialize_on_same_household(lab,engine):
    app,producer=lab;a=login(app);value=i5.cases()[0];pid=producer.process(value).pending_id
    _,command=app.tasks.prepare_acceptance(a[i2.COOKIE],pid);before=count(engine,task)
    with ThreadPoolExecutor(max_workers=2) as pool:
        processed=pool.submit(producer.process,replace(value,generation=2,safety=r.Safety.HIGH_RISK))
        accepted=pool.submit(app.tasks.apply,a[i2.COOKIE],command,confirm=True)
        p,result=processed.result(),accepted.result()
    assert p.outcome is f.Outcome.COMMITTED
    assert result.outcome in (t.Outcome.COMMITTED,t.Outcome.STALE)
    assert count(engine,task)==before+(result.outcome is t.Outcome.COMMITTED)
    assert p.effect==('accepted-history-only' if result.outcome is t.Outcome.COMMITTED else 'updated')


@pytest.mark.parametrize('basis',[f.DateBasis.PROMOTION,f.DateBasis.UNVERIFIED])
def test_promotional_or_unverified_date_is_never_a_household_task_date(lab,basis):
    app,producer=lab;a=login(app)
    value=replace(i5.cases()[0],date_basis=basis,business=r.Business(promotion=True,action=r.ActionEvidence.SUPPORTED,importance=r.Importance.IMPORTANT))
    pid=producer.process(value).pending_id
    row=next(v for v in get(app,a)['items'] if v['id']==pid)
    assert row['supported_date'] is None
    assert val(post(app,a,'pending/preview',{'id':pid}))['approved_date'] is None


def test_private_processing_history_cannot_change_peer_count_order_or_errors(lab):
    app,producer=lab;a=login(app);i5.feed(producer);before=get(app,a)
    private=i5.cases()[6]
    assert producer.process(replace(private,generation=2,safety=r.Safety.HIGH_RISK)).effect=='updated'
    assert get(app,a)==before


def test_inconsistent_pending_generation_is_not_silently_overwritten(lab):
    app,producer=lab;value=i5.cases()[0];pid=producer.process(value).pending_id
    mutate(app,pending,(pending.c.id==pid,),generation=9,evidence_fingerprint='d'*64,revision=9)
    assert producer.process(replace(value,generation=2)).outcome is f.Outcome.REJECTED


def test_observation_only_pending_does_not_project_private_risk_value(lab):
    app,producer=lab;a=login(app);value=i5.cases()[0]
    mutate(app,sources,(sources.c.source_account_id==value.source.value,sources.c.person_id=='i2-clara'),security=False,revision=2)
    pid=producer.process(value).pending_id;before=next(v for v in get(app,a)['items'] if v['id']==pid)
    assert not before['can_accept']
    producer.process(replace(value,generation=2,safety=r.Safety.HIGH_RISK))
    after=next(v for v in get(app,a)['items'] if v['id']==pid)
    assert dict(after,revision=before['revision'])==before
    assert 'safety' not in after


def test_all_source_revoked_blocks_business_update_and_invalidates_acceptance(lab,engine):
    app,producer=lab;first=i5.cases()[0];pid=producer.process(first).pending_id
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='revoked',revision=2)
    changed=replace(first,generation=2,safety=r.Safety.HIGH_RISK,step=t.Step.HOME,observed_date=date(2041,1,2))
    result=producer.process(changed)
    assert result.effect=='blocked'
    assert result.pending_id==pid
    with engine.connect() as c:row=c.execute(select(pending).where(pending.c.id==pid)).mappings().one()
    assert row['step']==first.step.value and row['supported_date']==first.observed_date
    assert row['safety']=='unknown' and row['generation']==2 and row['revision']==2


@pytest.mark.parametrize('safety',[r.Safety.HIGH_RISK,r.Safety.UNAVAILABLE,r.Safety.SAFE_TO_ROUTE])
def test_blocked_generation_regrant_replay_and_fresh_generation(lab,engine,safety):
    app,producer=lab;a=login(app);first=i5.cases()[0];pid=producer.process(first).pending_id
    receipt=val(post(app,a,'pending/preview',{'id':pid}))['receipt'];before=count(engine,task)
    with engine.connect() as c:
        grants_before={table.name:c.execute(select(table)).all() for table in (rights,plans,grants)}
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='revoked',revision=2)
    blocked=replace(first,generation=2,safety=safety,step=t.Step.HOME)
    assert producer.process(blocked)==f.Result(f.Outcome.COMMITTED,f.classify(blocked),'blocked',pid)
    assert pid not in {v['id'] for v in get(app,a)['items']}
    assert producer.process(blocked).outcome is f.Outcome.REPLAY
    assert producer.process(replace(blocked,step=t.Step.SCHOOL)).outcome is f.Outcome.CONFLICT
    assert producer.process(replace(first,generation=4)).outcome is f.Outcome.REJECTED
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='allowed',revision=3)
    assert producer.verify(blocked).outcome is f.Outcome.COMMITTED
    assert producer.process(blocked).effect=='blocked'  # Regrant cannot reinterpret a historical receipt.
    assert producer.process(first).outcome is f.Outcome.REPLAY  # Nor can replay of the old safe generation.
    row=next(v for v in get(app,a)['items'] if v['id']==pid)
    assert not row['can_accept'] and row['step']==first.step.value
    assert post(app,a,'pending/preview',{'id':pid})[0]=='400 Bad Request'
    assert val(post(app,a,'pending/accept',dict(receipt=receipt,confirm=True)))['outcome']!=t.Outcome.COMMITTED.value
    assert producer.process(replace(first,generation=3)).effect=='updated'
    assert next(v for v in get(app,a)['items'] if v['id']==pid)['can_accept']
    assert val(post(app,a,'pending/accept',dict(receipt=receipt,confirm=True)))['outcome']!=t.Outcome.COMMITTED.value
    assert count(engine,task)==before
    with engine.connect() as c:
        rows=c.execute(select(ledger).order_by(ledger.c.generation)).mappings().all()
        assert [(v['generation'],v['pending_id'],v['effect']) for v in rows]==[(1,pid,'created'),(2,pid,'blocked'),(3,pid,'updated')]
        assert rows[0]['evidence_fingerprint']==rows[2]['evidence_fingerprint']
        assert {table.name:c.execute(select(table)).all() for table in (rights,plans,grants)}==grants_before


@pytest.mark.parametrize('revoked',list(f.Peer))
@pytest.mark.parametrize('already_created',[False,True])
def test_one_reader_revoked_does_not_block_other_reader(lab,revoked,already_created):
    app,producer=lab;a,b=login(app),login(app,'devon');first=i5.cases()[0]
    if already_created:producer.process(first)
    # Independent preapproval can exist before that recipient has source access.
    mutate(app,sources,(sources.c.source_account_id==first.source.value,sources.c.person_id==revoked.value),state='revoked',revision=2)
    pid=producer.process(first).pending_id
    assert pid is not None
    assert producer.process(replace(first,generation=2,safety=r.Safety.HIGH_RISK)).effect=='updated'
    denied,allowed=(a,b) if revoked is f.Peer.CLARA else (b,a)
    assert pid not in {v['id'] for v in get(app,denied)['items']}
    assert pid in {v['id'] for v in get(app,allowed)['items']}
    mutate(app,sources,(sources.c.source_account_id==first.source.value,sources.c.person_id==revoked.value),state='allowed',revision=3)
    row=next(v for v in get(app,denied)['items'] if v['id']==pid)
    assert not row['can_accept']  # Existing preapproval is still subject to CURRENT safety.


def test_blocked_before_creation_and_repeated_blocked_updates_keep_links(lab,engine):
    app,producer=lab;first=i5.cases()[0]
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='revoked',revision=2)
    assert producer.process(first).pending_id is None
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='allowed',revision=3)
    pid=producer.process(replace(first,generation=2)).pending_id
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='revoked',revision=4)
    for generation in (3,4):
        value=replace(first,generation=generation)
        assert producer.process(value).effect=='blocked'
        assert producer.process(value).pending_id==pid
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='allowed',revision=5)
    assert producer.process(replace(first,generation=5)).effect=='updated'
    with engine.connect() as c:
        assert c.scalar(select(pending.c.generation).where(pending.c.id==pid))==5
        assert c.scalar(select(func.count()).select_from(ledger))==5


def test_revoked_source_accepted_task_remains_independent(lab,engine):
    app,producer=lab;a,b=login(app),login(app,'devon');first=i5.cases()[0];pid=producer.process(first).pending_id
    p=val(post(app,a,'pending/preview',{'id':pid}))
    assert val(post(app,a,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.COMMITTED.value
    with engine.connect() as c:
        original=c.execute(select(task)).all();history=c.execute(select(events)).all()
        tid=c.scalar(select(task.c.id).where(task.c.pending_id==pid))
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='revoked',revision=2)
    assert producer.process(replace(first,generation=2,safety=r.Safety.HIGH_RISK)).effect=='accepted-history-only'
    assert producer.process(replace(first,generation=3)).effect=='accepted-history-only'
    for jar in (a,b):assert tid in {v['id'] for v in get(app,jar,'tasks')['items']}
    with engine.connect() as c:assert c.execute(select(task)).all()==original and c.execute(select(events)).all()==history


@pytest.mark.parametrize('fault',['rollback','acknowledgment'])
def test_blocked_invalidation_and_ledger_are_atomic_with_unknown_verification(lab,engine,monkeypatch,fault):
    app,producer=lab;first=i5.cases()[0];pid=producer.process(first).pending_id
    mutate(app,sources,(sources.c.source_account_id==first.source.value,),state='revoked',revision=2)
    value=replace(first,generation=2,safety=r.Safety.HIGH_RISK)
    original=f.authorization_transaction
    @contextmanager
    def fail(*args,**kw):
        with original(*args,**kw) as c:
            yield c
            if fault=='rollback':raise RuntimeError('synthetic rollback')
        raise RuntimeError('synthetic acknowledgment loss')
    monkeypatch.setattr(f,'authorization_transaction',fail)
    assert producer.process(value).outcome is f.Outcome.UNKNOWN
    monkeypatch.setattr(f,'authorization_transaction',original)
    expected=f.Outcome.UNKNOWN if fault=='rollback' else f.Outcome.COMMITTED
    assert producer.verify(value).outcome is expected
    with engine.connect() as c:
        row=c.execute(select(pending).where(pending.c.id==pid)).mappings().one()
        assert row['generation']==(1 if fault=='rollback' else 2)
        assert row['safety']==('clear' if fault=='rollback' else 'unknown')
    if fault=='rollback':assert producer.process(value).outcome is f.Outcome.UNKNOWN  # Fence remains; do not resume.
    else:assert producer.process(value).outcome is f.Outcome.REPLAY


@pytest.mark.parametrize('destination',[r.Destination.SIMULATED_ACCEPTED,object()])
def test_unmapped_stage_a_destination_is_explicitly_rejected(monkeypatch,destination):
    from types import SimpleNamespace
    monkeypatch.setattr(r,'route',lambda *args:SimpleNamespace(destination=destination))
    with pytest.raises(f.InputError,match='Fictional information unavailable'):f.classify(i5.cases()[0])


def test_verify_uses_independent_connection_to_same_authoritative_database(lab,engine,monkeypatch):
    app,producer=lab;value=i5.cases()[0];producer.process(value);original=f.create_engine;opened=[]
    with engine.connect() as held:
        driver=held.connection.driver_connection
        def fresh(*args,**kw):
            e=original(*args,**kw)
            def check(c):
                opened.append(c.connection.driver_connection is not driver)
                if c.dialect.name=='sqlite':assert c.exec_driver_sql('PRAGMA foreign_keys').scalar()==1
                else:assert c.exec_driver_sql('SELECT current_schema()').scalar()==held.exec_driver_sql('SELECT current_schema()').scalar()
                c.rollback()  # The inspection must not leave an implicit transaction open.
            sql_event.listen(e,'engine_connect',check)
            return e
        monkeypatch.setattr(f,'create_engine',fresh)
        assert producer.verify(value).outcome is f.Outcome.COMMITTED
    assert opened==[True]


@pytest.mark.parametrize('url',['sqlite://','sqlite:///:memory:','sqlite:///file:demo?mode=memory&uri=true'])
def test_verify_does_not_open_in_memory_alternate_database(lab,monkeypatch,url):
    from sqlalchemy import create_engine
    app,producer=lab;engine=create_engine(url)
    monkeypatch.setattr(producer._tasks,'_engine',engine)
    monkeypatch.setattr(f,'create_engine',lambda *args,**kw:pytest.fail('Unsupported fresh database opened'))
    try:assert producer.verify(i5.cases()[0]).outcome is f.Outcome.UNKNOWN
    finally:engine.dispose()
