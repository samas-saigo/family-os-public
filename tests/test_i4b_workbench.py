"""Disposable fictional SQL only; no production database or provider access."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import select, update, event as sql_event
from sqlalchemy.exc import IntegrityError

from test_i2_local_session import request, login
from test_i4a_workbench import counts
from family_os.schema import (household_task as task, task_member_grant as grant,
    task_domain_event as event, source_read_grant as source, household_session as session,
    household_membership as member, external_identity_binding as identity,
    household_pending_item as pending)

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('i4b_workbench',ROOT/'prototypes/i4b-workbench/serve_editing.py')
i4b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=i4b;spec.loader.exec_module(i4b)
i4,i2,t=i4b.i4,i4b.i2,i4b.t


@pytest.fixture
def app(engine):
    lab=i2.Lab(engine,synthetic_only=True);i4.seed(lab)
    instance=i4b.Workbench(lab,38199)
    yield instance
    instance.close();lab.close()


def post(app,jar,path,value,**kw):
    return request(app,'/api/'+path,cookies=jar,body=json.dumps(value,separators=(',',':')).encode(),**kw)


def val(r):
    assert r[0]=='200 OK'
    return json.loads(r[2])


def shared(app,jar):
    return next(r for r in app.tasks.tasks(jar[i2.COOKIE]).items if r.assignee=='joint' and r.status is t.Status.PENDING)


def options(app,jar,id=None):
    return val(post(app,jar,'tasks/edit-options',{'id':id or shared(app,jar).id}))


def preview(app,jar,id=None,action='complete',assignee=None):
    d=options(app,jar,id)
    return val(post(app,jar,'tasks/edit-preview',dict(draft=d['draft'],action=action,**({'assignee':assignee} if assignee is not None else {}))))


def confirm(app,jar,p):return val(post(app,jar,'tasks/edit-confirm',dict(receipt=p['receipt'],confirm=True)))
def verify(app,jar,p):return val(post(app,jar,'tasks/edit-outcome',dict(receipt=p['receipt'])))


def mutate(app,table,where,**values):
    with i2.a.authorization_transaction(app.lab.sessions._engine,i2.HOME) as c:
        c.execute(update(table).where(table.c.household_id==i2.HOME,*where).values(**values))


def test_shared_sql_assignment_complete_reopen_same_task_actual_actor(app,engine):
    a,b=login(app),login(app,'devon');row=shared(app,a);before=counts(engine)
    for actor,action,assignee in [(a,'assign','i2-devon'),(b,'complete',None),(a,'reopen',None)]:
        p=preview(app,actor,row.id,action,assignee)
        assert counts(engine)[0]==before[0]
        assert confirm(app,actor,p)['outcome']==t.Outcome.COMMITTED.value
    left=next(r for r in app.tasks.tasks(a[i2.COOKIE]).items if r.id==row.id)
    right=next(r for r in app.tasks.tasks(b[i2.COOKIE]).items if r.id==row.id)
    assert left==right and left.assignee=='i2-devon' and left.status is t.Status.PENDING and left.revision==row.revision+3
    assert counts(engine)==(before[0],before[1]+3)
    with engine.connect() as c:
        actors=c.execute(select(event.c.actor_id).where(event.c.task_id==row.id,event.c.operation=='edit').order_by(event.c.task_revision)).scalars().all()
    assert actors==['i2-clara','i2-devon','i2-clara']


@pytest.mark.parametrize('scope',['editable','readonly','denied'])
def test_task_read_edit_capabilities_and_no_candidate_disclosure(app,scope):
    jar=login(app);row=shared(app,jar)
    if scope!='editable':mutate(app,grant,(grant.c.task_id==row.id,grant.c.person_id=='i2-clara'),can_edit=False,can_read=scope=='readonly',can_history=scope=='readonly',revision=2)
    r=post(app,jar,'tasks/edit-options',{'id':row.id})
    if scope=='editable':
        v=val(r);assert v['task']['can_edit'] and set(v['assignees'])=={'i2-clara','i2-devon','joint'}
    else:
        assert r[0]=='400 Bad Request'
        assert r==post(app,jar,'tasks/edit-options',{'id':'task_'+'f'*32})


def test_source_revocation_private_pending_and_security_cannot_influence_edit(app,engine):
    jar=login(app);p=preview(app,jar)
    mutate(app,source,(),state='revoked',revision=2)
    mutate(app,pending,(),safety='high-risk',generation=2,revision=10,evidence_fingerprint='c'*64)
    statements=[]
    def capture(c,cursor,statement,*args):statements.append(statement.lower())
    sql_event.listen(engine,'before_cursor_execute',capture)
    try:assert confirm(app,jar,p)['outcome']==t.Outcome.COMMITTED.value
    finally:sql_event.remove(engine,'before_cursor_execute',capture)
    assert not any(any(name in s for name in ('source_read_grant','household_pending_item','raw_source_record','source_account','pending_task_publication')) for s in statements)


def test_known_acceptance_does_not_require_old_private_source_to_edit_task(app):
    jar=login(app)
    p=val(post(app,jar,'pending/preview',{'id':'i4a-school'}))
    assert val(post(app,jar,'pending/accept',dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.COMMITTED.value
    row=next(r for r in app.tasks.tasks(jar[i2.COOKIE]).items if r.approved_date==i4.date(2036,3,14))
    mutate(app,source,(),state='revoked',revision=2)
    # Historical source results are withheld, but a known completed intent does
    # not turn its old source permission into a requirement for neutral EDIT.
    assert val(post(app,jar,'pending/outcome',dict(receipt=p['receipt'])))['outcome']==t.Outcome.UNKNOWN.value
    edit=preview(app,jar,row.id)
    assert confirm(app,jar,edit)['outcome']==t.Outcome.COMMITTED.value


@pytest.mark.parametrize('change',['task','actor-rights','recipient-rights','recipient-revoke','recipient-membership','recipient-rejoin','member','binding','session','can-edit'])
def test_exact_preview_rechecks_versions_and_current_eligibility(app,engine,change):
    jar=login(app);row=shared(app,jar);p=preview(app,jar,row.id,'assign','i2-devon');before=counts(engine)
    if change=='task':mutate(app,task,(task.c.id==row.id,),revision=2)
    elif change in ('actor-rights','recipient-rights','recipient-revoke','can-edit'):
        who='i2-clara' if change in ('actor-rights','can-edit') else 'i2-devon'
        values=dict(revision=2)
        if change=='recipient-revoke':values['state']='revoked'
        if change=='can-edit':values['can_edit']=False
        mutate(app,grant,(grant.c.task_id==row.id,grant.c.person_id==who),**values)
    elif change in ('recipient-membership','recipient-rejoin'):
        mutate(app,member,(member.c.person_id=='i2-devon',),revision=2,state='revoked' if change=='recipient-membership' else 'allowed')
    else:
        table={'member':member,'binding':identity,'session':session}[change]
        mutate(app,table,(table.c.person_id=='i2-clara',),revision=2,**({'revoked':True} if table is session else {'state':'revoked'}))
    r=post(app,jar,'tasks/edit-confirm',dict(receipt=p['receipt'],confirm=True))
    if r[0]=='200 OK':assert val(r)['outcome'] in (t.Outcome.STALE.value,t.Outcome.UNAVAILABLE.value,t.Outcome.UNKNOWN.value)
    else:assert r[0]=='400 Bad Request'
    assert counts(engine)==before


def test_changed_and_reverted_recipient_rights_never_rebase_draft(app,engine):
    jar=login(app);row=shared(app,jar);d=options(app,jar,row.id);before=counts(engine)
    mutate(app,grant,(grant.c.task_id==row.id,grant.c.person_id=='i2-devon'),state='revoked',revision=2)
    mutate(app,grant,(grant.c.task_id==row.id,grant.c.person_id=='i2-devon'),state='allowed',revision=3)
    assert post(app,jar,'tasks/edit-preview',dict(draft=d['draft'],action='assign',assignee='i2-devon'))[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('kind',['same-receipt','two-peers','two-sessions'])
def test_concurrent_confirmation_sql_cas_and_exact_replay(app,engine,kind):
    a=login(app);row=shared(app,a);pa=preview(app,a,row.id)
    b=a if kind=='same-receipt' else login(app,'devon' if kind=='two-peers' else 'clara')
    pb=pa if kind=='same-receipt' else preview(app,b,row.id)
    before=counts(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        fs=[pool.submit(confirm,app,a,pa),pool.submit(confirm,app,b,pb)];out=[f.result()['outcome'] for f in fs]
    assert sorted(out)==sorted([t.Outcome.COMMITTED.value,t.Outcome.REPLAY.value if kind=='same-receipt' else t.Outcome.STALE.value])
    assert counts(engine)==(before[0],before[1]+1)


def test_independent_adapter_locks_still_use_database_edit_cas(app,engine):
    from copy import copy
    from threading import RLock, Barrier
    jar=login(app);row=shared(app,jar);left=preview(app,jar,row.id)
    lab=copy(app.lab);lab.lock=RLock();lab.leases=dict(app.lab.leases)
    other=i4b.Workbench(lab,38199);right=preview(other,jar,row.id)
    before=counts(engine);barrier=Barrier(2)
    originals=(app.tasks.apply,other.tasks.apply)
    def run(index,*a,**k):barrier.wait(timeout=10);return originals[index](*a,**k)
    app.tasks.apply=lambda *a,**k:run(0,*a,**k)
    other.tasks.apply=lambda *a,**k:run(1,*a,**k)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            fs=[pool.submit(confirm,app,jar,left),pool.submit(confirm,other,jar,right)]
            outcomes=[f.result()['outcome'] for f in fs]
        assert sorted(outcomes)==sorted([t.Outcome.COMMITTED.value,t.Outcome.STALE.value])
        assert counts(engine)==(before[0],before[1]+1)
    finally:other.close()


def test_commit_ack_loss_fresh_verification_and_one_edit_audit(app,engine,monkeypatch):
    jar=login(app);p=preview(app,jar);before=counts(engine);original=app.tasks.apply;calls=[]
    def lost(*a,**k):calls.append(1);assert original(*a,**k).outcome is t.Outcome.COMMITTED;raise RuntimeError('synthetic acknowledgment loss')
    monkeypatch.setattr(app.tasks,'apply',lost)
    assert confirm(app,jar,p)['outcome']==t.Outcome.UNKNOWN.value
    r=verify(app,jar,p);assert r['outcome']==t.Outcome.COMMITTED.value and r['operation']=='edit'
    assert confirm(app,jar,p)['outcome']==t.Outcome.REPLAY.value
    assert len(calls)==1 and counts(engine)==(before[0],before[1]+1)


def test_pre_audit_failure_rolls_back_task_and_verifies_absence(app,engine):
    jar=login(app);row=shared(app,jar);p=preview(app,jar,row.id);before=counts(engine)
    def fail(c,cursor,statement,*args):
        if statement.lower().lstrip().startswith('insert into task_domain_event'):raise RuntimeError('synthetic fault')
    sql_event.listen(engine,'before_cursor_execute',fail)
    try:assert confirm(app,jar,p)['outcome']==t.Outcome.UNKNOWN.value
    finally:sql_event.remove(engine,'before_cursor_execute',fail)
    assert counts(engine)==before and next(r for r in app.tasks.tasks(jar[i2.COOKIE]).items if r.id==row.id)==row
    assert verify(app,jar,p)['outcome']==t.Outcome.NOT_APPLIED.value


@pytest.mark.parametrize('operation',['accept','edit'])
def test_unknown_blocks_both_kinds_of_replacement_and_recovery_is_operation_bound(app,engine,monkeypatch,operation):
    jar=login(app)
    p=preview(app,jar) if operation=='edit' else val(post(app,jar,'pending/preview',{'id':'i4a-school'}))
    monkeypatch.setattr(app.tasks,'apply',lambda *a,**k:t.Result(t.Outcome.UNKNOWN))
    monkeypatch.setattr(app.tasks,'verify_outcome',lambda *a,**k:t.Result(t.Outcome.UNKNOWN))
    route='tasks/edit-confirm' if operation=='edit' else 'pending/accept'
    assert val(post(app,jar,route,dict(receipt=p['receipt'],confirm=True)))['outcome']==t.Outcome.UNKNOWN.value
    assert post(app,jar,'pending/preview',{'id':'i3-unaccepted'})[0]=='400 Bad Request'
    assert post(app,jar,'tasks/edit-options',{'id':shared(app,jar).id})[0]=='400 Bad Request'
    recovered=val(post(app,jar,'writes/recover',{}))
    assert recovered['outcome']==t.Outcome.UNKNOWN.value and recovered['receipt'] is recovered['operation'] is None


@pytest.mark.parametrize('check',['tasks/edit-outcome','writes/recover'])
def test_verified_absence_seals_late_edit_request_and_new_explicit_confirmation_required(app,engine,check):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    assert val(post(app,jar,check,{'receipt':p['receipt']} if check.endswith('outcome') else {}))['outcome']==t.Outcome.NOT_APPLIED.value
    assert confirm(app,jar,p)['outcome']==t.Outcome.NOT_APPLIED.value
    assert counts(engine)==before
    assert confirm(app,jar,preview(app,jar))['outcome']==t.Outcome.COMMITTED.value


@pytest.mark.parametrize('first',['accept','edit'])
def test_new_cross_operation_preview_cannot_inherit_previous_success(app,first):
    jar=login(app)
    if first=='accept':
        old=val(post(app,jar,'pending/preview',{'id':'i4a-school'}));assert val(post(app,jar,'pending/accept',dict(receipt=old['receipt'],confirm=True)))['outcome']==t.Outcome.COMMITTED.value
        latest=preview(app,jar);expected='edit'
    else:
        old=preview(app,jar);assert confirm(app,jar,old)['outcome']==t.Outcome.COMMITTED.value
        latest=val(post(app,jar,'pending/preview',{'id':'i4a-school'}));expected='accept'
    recovered=val(post(app,jar,'writes/recover',{}))
    assert recovered['receipt']==latest['receipt'] and recovered['operation']==expected and recovered['outcome']==t.Outcome.NOT_APPLIED.value


@pytest.mark.parametrize('other',['peer','same-person-session'])
def test_receipt_and_draft_isolation_between_members_and_sessions(app,engine,other):
    a,b=login(app),login(app,'devon' if other=='peer' else 'clara');d=options(app,a);p=preview(app,a);before=counts(engine)
    for route,value in [('tasks/edit-preview',dict(draft=d['draft'],action='complete')),
                        ('tasks/edit-confirm',dict(receipt=p['receipt'],confirm=True)),('tasks/edit-outcome',dict(receipt=p['receipt']))]:
        assert post(app,b,route,value)[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('direction',['accept-as-edit','edit-as-accept'])
def test_operation_specific_receipt_cannot_be_used_or_verified_on_other_route(app,engine,direction):
    jar=login(app);p=val(post(app,jar,'pending/preview',{'id':'i4a-school'})) if direction=='accept-as-edit' else preview(app,jar)
    prefix='tasks/edit-' if direction=='accept-as-edit' else 'pending/'
    route=prefix+('confirm' if direction=='accept-as-edit' else 'accept')
    before=counts(engine)
    assert post(app,jar,route,dict(receipt=p['receipt'],confirm=True))[0]=='400 Bad Request'
    assert post(app,jar,prefix+'outcome',dict(receipt=p['receipt']))[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('value',[False,1,'true',None])
def test_no_write_without_exact_true(app,engine,value):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    assert post(app,jar,'tasks/edit-confirm',dict(receipt=p['receipt'],confirm=value))[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('key',['recipients','person','household','revision','rights_revision','request_id','title','date','binding','status'])
def test_browser_cannot_expand_or_replace_server_command(app,engine,key):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    assert post(app,jar,'tasks/edit-confirm',dict(receipt=p['receipt'],confirm=True,**{key:'forged'}))[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('changes',[{'HTTP_ORIGIN':None},{'HTTP_ORIGIN':'http://other.example'}, {'HTTP_HOST':'rebind.example'},
    {'HTTP_SEC_FETCH_SITE':'cross-site'},{'HTTP_X_SAMAS_INTENT':None},{'HTTP_AUTHORIZATION':'Bearer forged'},
    {'QUERY_STRING':'member=devon'},{'HTTP_TRANSFER_ENCODING':'chunked'},{'HTTP_CONTENT_ENCODING':'gzip'}])
def test_original_transport_guards_remain(app,engine,changes):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    assert post(app,jar,'tasks/edit-confirm',dict(receipt=p['receipt'],confirm=True),**changes)[0]=='400 Bad Request'
    assert counts(engine)==before


def test_old_i4a_entry_never_exposes_edit_assets_routes_or_capabilities(app):
    old=i4.Workbench(app.lab,38199);jar=login(old)
    assert post(old,jar,'tasks/edit-options',{'id':shared(app,jar).id})[0]=='400 Bad Request'
    assert '/editing.js' not in old.assets and b'data-connection="i4b"' not in old.assets['/'][0]


@pytest.mark.parametrize('mode',['i4b','i4a'])
def test_legacy_pending_recovery_is_i4a_only_and_cannot_seal_i4b_intent(app,engine,mode):
    instance=app if mode=='i4b' else i4.Workbench(app.lab,38199)
    jar=login(instance);before=counts(engine)
    p=val(post(instance,jar,'pending/preview',{'id':'i4a-school'}))
    entry=instance.receipts[i2.digest(jar[i2.COOKIE])][p['receipt']]
    response=post(instance,jar,'pending/recover',{})
    if mode=='i4b':
        assert response[0]=='400 Bad Request' and not entry.retired
        recovered=val(post(instance,jar,'writes/recover',{}))
        assert recovered['schema']=='i4b-write-result-v1' and recovered['operation']=='accept'
    else:
        recovered=val(response)
        assert recovered['schema']==i4.RESULT_SCHEMA
        assert 'operation' not in recovered
    assert entry.retired and recovered['receipt']==p['receipt']
    assert recovered['outcome']==t.Outcome.NOT_APPLIED.value
    assert counts(engine)==before


def test_other_household_session_cannot_read_prepare_or_verify_edit(app,engine):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    i4b.i3.register(engine,{'household':{'id':'i4b-cedar','name':'Fictional Cedar'},
        'people':[dict(id='i4b-evan',display_name='Fictional Evan')],'source_accounts':[]})
    from sqlalchemy import insert
    with engine.begin() as c:
        c.execute(insert(member).values(household_id='i4b-cedar',person_id='i4b-evan',state='allowed',revision=1))
        c.execute(insert(identity).values(issuer=i2.ISSUER,subject='i4b-evan-sub',household_id='i4b-cedar',person_id='i4b-evan',state='allowed',revision=1))
    now=int(i4b.i3.time());challenge=app.lab.verifier.challenge()
    assertion=i4b.i3.jwt.encode(dict(iss=i2.ISSUER,sub='i4b-evan-sub',aud='i2-fictional-client',
        iat=now-1,nbf=now-1,exp=now+60,nonce=challenge.nonce),app.lab.key,algorithm='RS256',headers={'kid':'i2-key'})
    result=app.lab.sessions.establish(app.lab.verifier.verify(assertion,challenge),'i4b-cedar',request_id='i4b-cedar-session')
    assert result.outcome is i2.s.Outcome.COMMITTED
    app.lab.leases[i2.digest(result.bearer)]=app.lab.last+600
    other={i2.COOKIE:result.bearer}
    for route,value in [('tasks/edit-options',{'id':p['task']['id']}),
                        ('tasks/edit-confirm',dict(receipt=p['receipt'],confirm=True)),
                        ('tasks/edit-outcome',dict(receipt=p['receipt'])),('writes/recover',{})]:
        assert post(app,other,route,value)[0]=='400 Bad Request'
    assert counts(engine)==before


def test_expiry_bounds_and_cleanup(app,engine):
    jar=login(app);d=options(app,jar);p=preview(app,jar);before=counts(engine);now=app.lab.last
    app.lab.clock=lambda:now+i4.PREVIEW_SECONDS+1
    assert confirm(app,jar,p)['outcome']==t.Outcome.STALE.value
    assert post(app,jar,'tasks/edit-preview',dict(draft=d['draft'],action='complete'))[0]=='400 Bad Request'
    app.lab.clock=lambda:now+i2.SESSION_SECONDS+1
    assert post(app,jar,'tasks/edit-outcome',dict(receipt=p['receipt']))[0]=='400 Bad Request'
    assert counts(engine)==before
    app.close();assert not app.receipts and not app.drafts


def test_draft_cap_is_per_session_and_candidates_are_not_household_directory(app,monkeypatch):
    jar=login(app);other=login(app,'devon');rows=app.tasks.tasks(jar[i2.COOKIE]).items
    private=next(r for r in rows if r.assignee=='i2-clara')
    p=options(app,jar,private.id)
    assert p['assignees']==['i2-clara']
    assert post(app,other,'tasks/edit-options',{'id':private.id})[0]=='400 Bad Request'
    monkeypatch.setattr(i4,'MAX_RECEIPTS',2)
    options(app,jar)
    assert post(app,jar,'tasks/edit-options',{'id':private.id})[0]=='400 Bad Request'
    assert options(app,other)['task']['can_edit']


@pytest.mark.parametrize('action,assignee',[('assign','outsider'),('assign','i2-devon'),('assign','i2-clara'),('assign',None),('complete','i2-clara'),('delete',None),('reopen',None)])
def test_unsupported_or_noop_selection_cannot_produce_writable_receipt(app,engine,action,assignee):
    jar=login(app);private=next(r for r in app.tasks.tasks(jar[i2.COOKIE]).items if r.assignee=='i2-clara')
    d=options(app,jar,private.id);before=counts(engine)
    value=dict(draft=d['draft'],action=action,**({} if assignee is None else {'assignee':assignee}))
    assert post(app,jar,'tasks/edit-preview',value)[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('assignee',[None,False,True,1,[],{}])
def test_malformed_assignment_cannot_select_a_status_only_command(app,engine,assignee):
    jar=login(app);d=options(app,jar);before=counts(engine)
    response=post(app,jar,'tasks/edit-preview',dict(draft=d['draft'],action='assign',assignee=assignee))
    assert response[0]=='400 Bad Request'
    assert not app.receipts[i2.digest(jar[i2.COOKIE])]
    assert counts(engine)==before


def test_changed_intent_fingerprint_and_privacy_errors(app,engine,caplog):
    jar=login(app);p=preview(app,jar);assert confirm(app,jar,p)['outcome']==t.Outcome.COMMITTED.value
    entry=app.receipts[i2.digest(jar[i2.COOKIE])][p['receipt']]
    entry.command=replace(entry.command,status=t.Status.PENDING)
    assert verify(app,jar,p)['outcome']==t.Outcome.CONFLICT.value
    raw=post(app,jar,'tasks/edit-options',{'id':'private-missing'})
    assert raw[0]=='400 Bad Request' and jar[i2.COOKIE] not in caplog.text+raw[2].decode()


def test_schema_and_capability_hint_reject_supported_question(app):
    jar=login(app)
    mutate(app,pending,(pending.c.id=='i4a-question',),supported=True,safety='clear',step='home-visit',kind='action')
    # Existing SQL support/type constraint already rejects this impossible state.
    with pytest.raises(IntegrityError):
        mutate(app,pending,(pending.c.id=='i4a-question',),kind='question')
    mutate(app,pending,(pending.c.id=='i4a-question',),supported=False,step=None,kind='question')
    row=next(r for r in app.tasks.pending(jar[i2.COOKIE]).items if r.id=='i4a-question')
    assert not row.can_accept


@pytest.mark.parametrize('parser',['options','preview','result','taskParse'])
def test_independent_browser_json_whitelist(app,parser):
    jar=login(app);d=options(app,jar);p=preview(app,jar)
    values={'options':d,'preview':p,'result':verify(app,jar,p)}
    if parser=='taskParse':
        values[parser]=val(request(app,'/api/tasks',cookies=jar,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING='limit=20'))
    value=values[parser]
    script="require('./prototypes/i3-workbench/contract.js');require('./prototypes/i4a-workbench/acceptance.js');const c=require('./prototypes/i4b-workbench/editing.js');try{c[process.argv[1]](require('fs').readFileSync(0,'utf8'),process.argv[1]==='taskParse'?20:process.argv[2],0);process.stdout.write('valid');}catch(_){process.stdout.write('invalid');}"
    def run(v):return subprocess.run(['node','-e',script,parser,d['task']['id']],cwd=ROOT,input=json.dumps(v,sort_keys=True,separators=(',',':')),text=True,capture_output=True,timeout=10).stdout
    assert run(value)=='valid'
    assert run(dict(value,private='forbidden'))=='invalid'
    assert run(dict(value,synthetic_only=False))=='invalid'


def test_success_result_requires_exact_operation_marker(app):
    jar=login(app);p=preview(app,jar);value=confirm(app,jar,p)
    script="require('./prototypes/i4a-workbench/acceptance.js');const c=require('./prototypes/i4b-workbench/editing.js');try{c.result(require('fs').readFileSync(0,'utf8'));process.stdout.write('valid');}catch(_){process.stdout.write('invalid');}"
    for operation in [None,'acceptance','quarantine']:
        raw=json.dumps(dict(value,operation=operation),sort_keys=True,separators=(',',':'))
        assert subprocess.run(['node','-e',script],cwd=ROOT,input=raw,text=True,capture_output=True,timeout=10).stdout=='invalid'
