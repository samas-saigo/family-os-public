"""Fictional I4a transport → unchanged T1 transactions; never a runtime database."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import select,update,insert

from test_i2_local_session import request,login
from family_os.schema import (household_task as task,task_domain_event as event,
    household_pending_item as pending,pending_member_right as right,pending_task_publication as plan,
    source_read_grant as source,household_session as session,household_membership as member,
    external_identity_binding as identity)

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('i4a_workbench',ROOT/'prototypes/i4a-workbench/serve_acceptance.py')
i4=importlib.util.module_from_spec(spec);sys.modules[spec.name]=i4;spec.loader.exec_module(i4)
i3,i2,t=i4.i3,i4.i2,i4.t


@pytest.fixture
def app(engine):
    lab=i2.Lab(engine,synthetic_only=True);i4.seed(lab)
    instance=i4.Workbench(lab,38199)
    yield instance
    instance.close();lab.close()


def post(app,jar,path,value,**changes):
    body=json.dumps(value,separators=(',',':')).encode()
    return request(app,'/api/pending/'+path,cookies=jar,body=body,**changes)


def value(result):
    assert result[0]=='200 OK'
    return json.loads(result[2])


def page(app,jar):
    return value(request(app,'/api/pending',cookies=jar,method='GET',body=b'',CONTENT_TYPE='',
        HTTP_ACCEPT='application/json',QUERY_STRING='limit=20'))['pending']


def preview(app,jar,id='i4a-school'):
    return value(post(app,jar,'preview',{'id':id}))


def accept(app,jar,p):
    return value(post(app,jar,'accept',{'receipt':p['receipt'],'confirm':True}))


def verify(app,jar,p):
    return value(post(app,jar,'outcome',{'receipt':p['receipt']}))


def counts(engine):
    with engine.connect() as c:
        return len(c.execute(select(task)).all()),len(c.execute(select(event)).all())


def change(app,table,**values):
    with i2.a.authorization_transaction(app.lab.sessions._engine,i2.HOME) as c:
        q=update(table).where(table.c.household_id==i2.HOME)
        if 'pending_id' in table.c:q=q.where(table.c.pending_id=='i4a-school')
        elif table is pending:q=q.where(table.c.id=='i4a-school')
        if table in (right,source,session,member,identity):q=q.where(table.c.person_id=='i2-clara')
        c.execute(q.values(**values))


def test_independent_pending_reads_no_promotions_notices_private_fields(app):
    a,b=login(app),login(app,'devon');left=page(app,a);right_page=page(app,b)
    assert {r['id'] for r in left['items']}=={'i3-unaccepted','i4a-school','i4a-question','i4a-risk'}
    assert {r['id'] for r in right_page['items']}=={'i4a-school','i4a-question','i4a-risk','i4a-visit'}
    assert left['total']==right_page['total']==4
    for r in left['items']+right_page['items']:
        assert set(r)=={'id','revision','step','supported_date','can_accept'}
        if r['id'] in ('i4a-question','i4a-risk'):assert not r['can_accept']
    assert post(app,a,'preview',{'id':'i4a-visit'})[0]=='400 Bad Request'


def test_preview_is_no_decision_server_binds_plan_and_accepts_once(app,engine):
    jar=login(app);before=counts(engine);p=preview(app,jar)
    assert counts(engine)==before and p['assignee']=='joint' and p['approved_date']=='2036-03-14'
    assert set(p)=={'schema','synthetic_only','receipt','id','revision','step','assignee','approved_date'}
    result=accept(app,jar,p);assert result['outcome']==t.Outcome.COMMITTED.value
    assert counts(engine)==(before[0]+1,before[1]+1)
    assert accept(app,jar,p)['outcome']==t.Outcome.REPLAY.value
    assert verify(app,jar,p)['outcome']==t.Outcome.COMMITTED.value
    assert counts(engine)==(before[0]+1,before[1]+1)
    assert 'i4a-school' not in {r['id'] for r in page(app,jar)['items']}
    assert value(post(app,jar,'recover',{}))['outcome']==t.Outcome.COMMITTED.value


def test_shared_acceptance_real_task_read_and_actual_actor(app,engine):
    a,b=login(app),login(app,'devon');before=counts(engine)
    assert accept(app,b,preview(app,b))['outcome']==t.Outcome.COMMITTED.value
    assert len(app.tasks.tasks(a[i2.COOKIE]).items)==4
    assert len(app.tasks.tasks(b[i2.COOKIE]).items)==3
    with engine.connect() as c:
        row=c.execute(select(task).where(task.c.pending_id=='i4a-school')).mappings().one()
        audit=c.execute(select(event).where(event.c.pending_id=='i4a-school')).mappings().one()
        assert audit['actor_id']=='i2-devon' and audit['request_id'].startswith('accept_')
        assert row['accepted_generation']==1 and row['approved_date']==date(2036,3,14)
    assert counts(engine)==(before[0]+1,before[1]+1)


@pytest.mark.parametrize('resource',['i4a-offer','i4a-notice','i4a-risk','i4a-question','missing'])
def test_unsafe_unknown_or_non_action_never_prepares_or_creates_task(app,engine,resource):
    jar=login(app);before=counts(engine)
    assert post(app,jar,'preview',{'id':resource})[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('value_override',[False,1,'true',None])
def test_only_exact_explicit_confirmation_can_write(app,engine,value_override):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    assert post(app,jar,'accept',{'receipt':p['receipt'],'confirm':value_override})[0]=='400 Bad Request'
    assert counts(engine)==before


def test_client_cannot_invent_assignment_recipients_evidence_or_identity(app,engine):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    for key in ('recipients','assignee','household','member','binding','request_id','rights_revision'):
        assert post(app,jar,'accept',{'receipt':p['receipt'],'confirm':True,key:'forged'})[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('target',[pending,right,plan,source,session,member,identity])
def test_current_evidence_rights_plan_session_and_membership_rechecked(app,engine,target):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    if target is pending:change(app,target,revision=2,generation=2,evidence_fingerprint='b'*64)
    elif target is session:change(app,target,revision=2,revoked=True)
    else:change(app,target,revision=2,state='revoked')
    raw=post(app,jar,'accept',{'receipt':p['receipt'],'confirm':True})
    if raw[0]=='200 OK':assert value(raw)['outcome'] in (t.Outcome.STALE.value,t.Outcome.UNAVAILABLE.value,t.Outcome.UNKNOWN.value)
    else:assert raw[0]=='400 Bad Request'
    assert counts(engine)==before


def test_evidence_revert_never_transfers_preview(app,engine):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    with engine.connect() as c:original=c.execute(select(pending.c.evidence_fingerprint).where(pending.c.id=='i4a-school')).scalar_one()
    change(app,pending,revision=2,generation=2,evidence_fingerprint='a'*64)
    change(app,pending,revision=3,generation=3,evidence_fingerprint=original)
    assert accept(app,jar,p)['outcome']==t.Outcome.STALE.value
    assert counts(engine)==before


def test_expired_preview_and_expired_local_session_do_not_write(app,engine):
    jar=login(app);p=preview(app,jar);before=counts(engine);clock=app.lab.last
    app.lab.clock=lambda:clock+i4.PREVIEW_SECONDS+1
    assert accept(app,jar,p)['outcome']==t.Outcome.STALE.value
    assert counts(engine)==before
    app.lab.clock=lambda:clock+i2.SESSION_SECONDS+1
    assert post(app,jar,'accept',{'receipt':p['receipt'],'confirm':True})[0]=='400 Bad Request'
    assert counts(engine)==before


def test_cross_peer_receipt_replay_does_not_disclose_or_mutate(app,engine):
    a,b=login(app),login(app,'devon');p=preview(app,a);before=counts(engine)
    for path,body in [('accept',{'receipt':p['receipt'],'confirm':True}),('outcome',{'receipt':p['receipt']})]:
        denied=post(app,b,path,body);missing=post(app,b,path,{**body,'receipt':'f'*32})
        assert denied==missing and denied[0]=='400 Bad Request'
    assert counts(engine)==before


def test_duplicate_concurrent_confirmations_single_task_and_audit(app,engine):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:accept(app,jar,p),range(2)))
    assert sorted(r['outcome'] for r in results)==sorted([t.Outcome.COMMITTED.value,t.Outcome.REPLAY.value])
    assert counts(engine)==(before[0]+1,before[1]+1)


def test_concurrent_peers_with_independent_previews_only_one_commits(app,engine):
    a,b=login(app),login(app,'devon');pa,pb=preview(app,a),preview(app,b);before=counts(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa=pool.submit(accept,app,a,pa);fb=pool.submit(accept,app,b,pb);results=[fa.result(),fb.result()]
    assert sorted(r['outcome'] for r in results)==sorted([t.Outcome.COMMITTED.value,t.Outcome.STALE.value])
    assert counts(engine)==(before[0]+1,before[1]+1)


def test_ack_loss_after_real_commit_unknown_then_fresh_read_verifies_no_reapply(app,engine,monkeypatch):
    jar=login(app);p=preview(app,jar);before=counts(engine);original=app.tasks.apply;calls=[]
    def lost(*args,**kwargs):
        calls.append(1);assert original(*args,**kwargs).outcome is t.Outcome.COMMITTED
        raise RuntimeError('fictional lost acknowledgment')
    monkeypatch.setattr(app.tasks,'apply',lost)
    assert accept(app,jar,p)['outcome']==t.Outcome.UNKNOWN.value
    assert verify(app,jar,p)['outcome']==t.Outcome.COMMITTED.value
    assert value(post(app,jar,'recover',{}))['receipt']==p['receipt']
    assert accept(app,jar,p)['outcome']==t.Outcome.REPLAY.value
    assert len(calls)==1 and counts(engine)==(before[0]+1,before[1]+1)


def test_unknown_reconciliation_stays_unknown_and_blocks_replacement(app,engine,monkeypatch):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    monkeypatch.setattr(app.tasks,'apply',lambda *a,**k:t.Result(t.Outcome.UNKNOWN))
    monkeypatch.setattr(app.tasks,'verify_outcome',lambda *a,**k:t.Result(t.Outcome.UNKNOWN))
    assert accept(app,jar,p)['outcome']==t.Outcome.UNKNOWN.value
    assert accept(app,jar,p)['outcome']==t.Outcome.UNKNOWN.value
    recovered=value(post(app,jar,'recover',{}))
    assert recovered['outcome']==t.Outcome.UNKNOWN.value and recovered['receipt'] is None
    assert post(app,jar,'preview',{'id':'i3-unaccepted'})[0]=='400 Bad Request'
    assert counts(engine)==before


def test_verified_absence_after_failure_permits_only_new_explicit_preview(app,engine,monkeypatch):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    def fail(*a,**k):raise RuntimeError('before mutation')
    monkeypatch.setattr(app.tasks,'apply',fail)
    assert accept(app,jar,p)['outcome']==t.Outcome.UNKNOWN.value
    assert verify(app,jar,p)['outcome']==t.Outcome.NOT_APPLIED.value
    assert counts(engine)==before
    assert preview(app,jar)['receipt']!=p['receipt']


def test_changed_intent_is_reported_without_replacing_history(app,engine):
    jar=login(app);p=preview(app,jar);entry=app.receipts[i2.digest(jar[i2.COOKIE])][p['receipt']]
    assert accept(app,jar,p)['outcome']==t.Outcome.COMMITTED.value
    before=counts(engine);entry.command=replace(entry.command,assignee='i2-clara')
    assert verify(app,jar,p)['outcome']==t.Outcome.CONFLICT.value and counts(engine)==before


def test_recover_after_revocation_withholds_receipt_and_private_outcome(app):
    jar=login(app);p=preview(app,jar);accept(app,jar,p)
    change(app,right,state='revoked',revision=2)
    result=value(post(app,jar,'recover',{}))
    assert result['outcome']==t.Outcome.UNKNOWN.value and result['receipt'] is None


@pytest.mark.parametrize('changes',[{'HTTP_ORIGIN':None},{'HTTP_ORIGIN':'http://evil.example'},
    {'HTTP_SEC_FETCH_SITE':'cross-site'},{'HTTP_HOST':'rebind.example'},{'HTTP_X_SAMAS_INTENT':None},
    {'HTTP_X_MEMBER':'devon'},{'HTTP_AUTHORIZATION':'Bearer fake'},{'QUERY_STRING':'id=i4a-school'},
    {'HTTP_TRANSFER_ENCODING':'chunked'},{'HTTP_CONTENT_ENCODING':'gzip'}, {'REQUEST_URI':'/api/pending/%61ccept'}])
def test_host_origin_csrf_alias_identity_and_body_guards(app,engine,changes):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    assert post(app,jar,'accept',{'receipt':p['receipt'],'confirm':True},**changes)[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('body',[b'{"id":"i4a-school","id":"i4a-school"}',b'[]',b'null',b'{"id":null}',b'{"id":true}',b'{"id":"'+b'a'*257+b'"}'])
def test_malformed_duplicate_and_oversized_preview_bodies(app,engine,body):
    jar=login(app);before=counts(engine)
    assert request(app,'/api/pending/preview',cookies=jar,body=body)[0]=='400 Bad Request'
    assert counts(engine)==before


def test_receipt_cap_is_bounded_and_independent_per_session(app,monkeypatch):
    a,b=login(app),login(app,'devon');monkeypatch.setattr(i4,'MAX_RECEIPTS',2)
    preview(app,a);preview(app,a)
    assert post(app,a,'preview',{'id':'i4a-school'})[0]=='400 Bad Request'
    assert preview(app,b)['id']=='i4a-school'


def test_no_secret_or_raw_binding_in_output_errors_or_logs(app,caplog,monkeypatch):
    jar=login(app);p=preview(app,jar)
    assert 'fingerprint' not in json.dumps(p) and 'recipients' not in json.dumps(p)
    def fail(*a,**k):raise RuntimeError('private '+jar[i2.COOKIE])
    monkeypatch.setattr(app.tasks,'prepare_acceptance',fail)
    response=post(app,jar,'preview',{'id':'i4a-school'})
    assert response[0]=='400 Bad Request' and jar[i2.COOKIE] not in response[2].decode()+caplog.text
    app.close();assert not app.receipts and not app.last_attempt


def test_i2_default_still_rejects_acceptance_routes(engine):
    lab=i2.Lab(engine,synthetic_only=True);instance=i2.Application(lab,38199);jar=login(instance)
    assert post(instance,jar,'preview',{'id':'i4a-school'})[0]=='400 Bad Request'
    lab.close()


def test_i3_default_remains_readonly(app):
    base=i3.Workbench(app.lab,38199);jar=login(base)
    assert post(base,jar,'preview',{'id':'i4a-school'})[0]=='400 Bad Request'
    assert b'acceptance.js' not in base.assets['/'][0]


def test_browser_contract_exact_whitelist_and_result_validation(app):
    jar=login(app);raw=request(app,'/api/pending',cookies=jar,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json',QUERY_STRING='limit=20')[2].decode()
    script="const c=require('./prototypes/i4a-workbench/acceptance.js');const fs=require('fs');try{c.parse(fs.readFileSync(0,'utf8'),20,0);process.stdout.write('valid');}catch(_){process.stdout.write('invalid');}"
    def run(v):return subprocess.run(['node','-e',script],cwd=ROOT,input=v,text=True,capture_output=True,timeout=10).stdout
    assert run(raw)=='valid'
    assert run(raw.replace('"synthetic_only":true','"synthetic_only":true,"private":"no"'))=='invalid'
    assert run(raw.replace('"synthetic_only":true','"synthetic_only":true,"synthetic_only":true'))=='invalid'


def test_private_and_unauthorized_safety_changes_do_not_affect_pending_projection(app,engine):
    jar=login(app)
    with i2.a.authorization_transaction(engine,i2.HOME) as c:
        c.execute(update(source).where(source.c.household_id==i2.HOME,source.c.person_id=='i2-clara').values(security=False,revision=2))
    before=page(app,jar)
    with i2.a.authorization_transaction(engine,i2.HOME) as c:
        c.execute(update(pending).where(pending.c.id=='i4a-risk').values(safety='clear'))
        c.execute(update(pending).where(pending.c.id=='i4a-visit').values(safety='unknown',revision=2,generation=2,evidence_fingerprint='a'*64))
    assert page(app,jar)==before
    assert post(app,jar,'preview',{'id':'i4a-school'})[0]=='400 Bad Request'


def test_cross_household_verified_session_cannot_preview_or_accept(app,engine):
    i3.register(engine,{'household':{'id':'i4a-other','name':'Fictional Other'},
        'people':[{'id':'i4a-evan','display_name':'Fictional Evan'}],'source_accounts':[]})
    with engine.begin() as c:
        c.execute(insert(member).values(household_id='i4a-other',person_id='i4a-evan',state='allowed',revision=1))
        c.execute(insert(identity).values(issuer=i2.ISSUER,subject='i4a-evan-sub',household_id='i4a-other',person_id='i4a-evan',state='allowed',revision=1))
    now=int(i3.time());challenge=app.lab.verifier.challenge()
    assertion=i3.jwt.encode(dict(iss=i2.ISSUER,sub='i4a-evan-sub',aud='i2-fictional-client',iat=now-1,nbf=now-1,exp=now+60,nonce=challenge.nonce),app.lab.key,algorithm='RS256',headers={'kid':'i2-key'})
    result=app.lab.sessions.establish(app.lab.verifier.verify(assertion,challenge),'i4a-other',request_id='i4a-other-session')
    assert result.outcome is i2.s.Outcome.COMMITTED
    app.lab.leases[i2.digest(result.bearer)]=app.lab.last+600
    jar={i2.COOKIE:result.bearer};before=counts(engine)
    assert post(app,jar,'preview',{'id':'i4a-school'})[0]=='400 Bad Request'
    assert post(app,jar,'recover',{})[0]=='400 Bad Request'
    assert counts(engine)==before


def test_two_independent_adapter_instances_rely_on_sql_cas_not_local_mutex(app,engine):
    from copy import copy
    from threading import RLock,Barrier
    jar=login(app);first=preview(app,jar)
    other_lab=copy(app.lab);other_lab.lock=RLock();other_lab.leases=dict(app.lab.leases)
    other=i4.Workbench(other_lab,38199);second=preview(other,jar);before=counts(engine);barrier=Barrier(2)
    original_left,original_right=app.tasks.apply,other.tasks.apply
    def left(*a,**k):barrier.wait(timeout=10);return original_left(*a,**k)
    def right_call(*a,**k):barrier.wait(timeout=10);return original_right(*a,**k)
    app.tasks.apply,other.tasks.apply=left,right_call
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(accept,app,jar,first);b=pool.submit(accept,other,jar,second);results=[a.result(),b.result()]
    assert sorted(r['outcome'] for r in results)==sorted([t.Outcome.COMMITTED.value,t.Outcome.STALE.value])
    assert counts(engine)==(before[0]+1,before[1]+1)
    other.close()


def test_rollback_after_task_insert_before_audit_preserves_domain(app,engine,monkeypatch):
    from sqlalchemy import event as sql_event
    jar=login(app);p=preview(app,jar);before=counts(engine)
    def fail(c,cursor,statement,params,context,many):
        if statement.lower().lstrip().startswith('insert into task_domain_event'):raise RuntimeError('fictional pre-audit fault')
    sql_event.listen(engine,'before_cursor_execute',fail)
    try:assert accept(app,jar,p)['outcome']==t.Outcome.UNKNOWN.value
    finally:sql_event.remove(engine,'before_cursor_execute',fail)
    assert counts(engine)==before
    assert verify(app,jar,p)['outcome']==t.Outcome.NOT_APPLIED.value
    assert 'i4a-school' in {r['id'] for r in page(app,jar)['items']}


@pytest.mark.parametrize('kind',['rights-version','plan-version','definition','unsupported','security-unknown','already-accepted'])
def test_exact_preview_versions_and_support_cannot_be_rebased(app,engine,kind):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    if kind=='rights-version':change(app,right,revision=2)
    elif kind=='plan-version':change(app,plan,revision=2)
    elif kind=='definition':change(app,pending,definition_version='i4a-fictional-v2')
    elif kind=='unsupported':change(app,pending,supported=False,supported_date=None)
    elif kind=='security-unknown':change(app,pending,safety='unknown')
    else:change(app,pending,resolution='accepted',revision=2)
    assert accept(app,jar,p)['outcome'] in (t.Outcome.STALE.value,t.Outcome.UNAVAILABLE.value)
    assert counts(engine)==before


def test_pending_does_not_select_raw_payload_or_account_secret_columns(app,engine):
    from sqlalchemy import event as sql_event
    jar=login(app);statements=[]
    def capture(c,cursor,statement,params,context,many):statements.append(statement.lower())
    sql_event.listen(engine,'before_cursor_execute',capture)
    try:assert page(app,jar)['total']==4
    finally:sql_event.remove(engine,'before_cursor_execute',capture)
    assert not any('raw_source_record' in s or 'source_record.' in s or 'oauth' in s or 'secret_metadata' in s for s in statements)


@pytest.mark.parametrize('path',['outcome','recover'])
def test_reconciliation_seals_delayed_unexecuted_acceptance_before_proving_absence(app,engine,path):
    jar=login(app);p=preview(app,jar);before=counts(engine)
    result=value(post(app,jar,path,{'receipt':p['receipt']} if path=='outcome' else {}))
    assert result['outcome']==t.Outcome.NOT_APPLIED.value
    assert accept(app,jar,p)['outcome']==t.Outcome.NOT_APPLIED.value
    assert counts(engine)==before
    fresh=preview(app,jar)
    assert accept(app,jar,fresh)['outcome']==t.Outcome.COMMITTED.value
    assert counts(engine)==(before[0]+1,before[1]+1)


def test_new_preview_retires_older_unconfirmed_intent_and_recovery_never_reports_prior_task_as_new(app,engine):
    jar=login(app);first=preview(app,jar);second=preview(app,jar)
    before=counts(engine)
    assert accept(app,jar,first)['outcome']==t.Outcome.NOT_APPLIED.value
    assert counts(engine)==before
    assert accept(app,jar,second)['outcome']==t.Outcome.COMMITTED.value
    latest=preview(app,jar,'i3-unaccepted')
    recovered=value(post(app,jar,'recover',{}))
    assert recovered['receipt']==latest['receipt'] and recovered['outcome']==t.Outcome.NOT_APPLIED.value
    assert accept(app,jar,latest)['outcome']==t.Outcome.NOT_APPLIED.value
    assert counts(engine)==(before[0]+1,before[1]+1)


def test_same_person_different_session_cannot_use_or_reconcile_receipt(app,engine):
    first,second=login(app),login(app);p=preview(app,first);before=counts(engine)
    assert post(app,second,'accept',{'receipt':p['receipt'],'confirm':True})[0]=='400 Bad Request'
    assert post(app,second,'outcome',{'receipt':p['receipt']})[0]=='400 Bad Request'
    assert counts(engine)==before


@pytest.mark.parametrize('kind',['type','total','row','date','revision'])
def test_server_pending_serializer_rejects_invalid_domain_contract(app,monkeypatch,kind):
    jar=login(app);valid=app.tasks.pending(jar[i2.COOKIE]);r=valid.items[0]
    bad=object() if kind=='type' else replace(valid,total=True) if kind=='total' else replace(valid,items=(object(),)) if kind=='row' else replace(valid,items=(replace(r,supported_date='private-invalid'),)) if kind=='date' else replace(valid,items=(replace(r,revision=False),))
    monkeypatch.setattr(app.tasks,'pending',lambda *a,**k:bad)
    status,_,raw=request(app,'/api/pending',cookies=jar,method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json')
    assert status=='400 Bad Request' and b'private-invalid' not in raw


@pytest.mark.parametrize('kind',['unknown-field','invalid-date','half-response','invalid-outcome','missing-receipt','null-committed','noncanonical','duplicate-key'])
def test_independent_browser_preview_and_result_validation_rejects_invalid_envelopes(app,kind):
    jar=login(app);value=preview(app,jar);method='preview'
    if kind=='unknown-field':value['private']='forbidden'
    elif kind=='invalid-date':value['approved_date']='2036-02-30'
    elif kind=='half-response':del value['assignee']
    elif kind in ('invalid-outcome','missing-receipt','null-committed'):
        method='result';value=dict(schema=i4.RESULT_SCHEMA,synthetic_only=True,outcome='COMMITTED',receipt='a'*32)
        if kind=='invalid-outcome':value['outcome']='APPLIED-maybe'
        elif kind=='missing-receipt':del value['receipt']
        else:value['receipt']=None
    raw=json.dumps(value,sort_keys=True,separators=(',',':'))
    if kind=='noncanonical':raw=' '+raw
    if kind=='duplicate-key':raw=raw.replace('"synthetic_only":true','"synthetic_only":true,"synthetic_only":true')
    script="const c=require('./prototypes/i4a-workbench/acceptance.js');const fs=require('fs');try{c[process.argv[1]](fs.readFileSync(0,'utf8'),'i4a-school');process.stdout.write('valid');}catch(_){process.stdout.write('invalid');}"
    assert subprocess.run(['node','-e',script,method],cwd=ROOT,input=raw,text=True,capture_output=True,timeout=10).stdout=='invalid'
