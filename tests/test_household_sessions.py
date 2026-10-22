"""New fictional Marlin household; real disposable transactions, no runtime data."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event, current_thread
from time import time
import ast
import json

from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import jwt
import pytest
from sqlalchemy import insert, select, update, delete, event, inspect
from sqlalchemy.exc import IntegrityError

from family_os import _household_sessions as s, _household_authorization as a, _verified_identity as v
from family_os.schema import (household,person,source_account,household_membership as member,
    external_identity_binding as binding,source_read_grant as grant,publication_scope as scope,
    publication_read_grant as publication,household_session as sessions,session_audit as audit)

ROOT=Path(__file__).parents[1]
HOME='marlin';ISSUER='https://identity.example.invalid/marlin';AUD='fictional-internal-client'


@pytest.fixture(scope='module')
def key():return rsa.generate_private_key(public_exponent=65537,key_size=2048)


class Clock:
    def __init__(self):self.now=int(time())
    def __call__(self):return self.now


@pytest.fixture
def setup(engine,key):
    clock=Clock()
    verifier=v.OfflineIdentityVerifier(issuer=ISSUER,audience=AUD,public_keys={
        'marlin-key':key.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo)})
    with engine.begin() as c:
        c.execute(insert(household),[dict(id=HOME,name='Fictional Marlin'),dict(id='finch',name='Fictional Finch')])
        c.execute(insert(person),[dict(id=p,household_id=HOME,display_name='Fictional '+p,metadata={}) for p in ('mira','owen')]+
                  [dict(id='zara',household_id='finch',display_name='Fictional Zara',metadata={})])
        c.execute(insert(member),[dict(household_id=HOME,person_id=p,state='allowed',revision=1) for p in ('mira','owen')])
        c.execute(insert(binding),[dict(issuer=ISSUER,subject=p,household_id=HOME,person_id=p,state='allowed',revision=1) for p in ('mira','owen')])
        c.execute(insert(source_account),[dict(id=src,household_id=HOME,provider='fixture',owner_type='person',owner_id=owner,
           person_owner_id=owner,external_account=None,enabled=True,metadata={}) for src,owner in [('marlin-one','mira'),('marlin-two','owen'),('marlin-private','owen')]])
        c.execute(insert(grant),[dict(household_id=HOME,source_account_id=src,person_id=p,state='allowed',observations=True,security=True,
             revision=1,membership_revision=1) for src in ('marlin-one','marlin-two') for p in ('mira','owen')])
        c.execute(insert(scope).values(household_id=HOME,publication_key=a.Publication.SCHOOL.value,approved=True))
        c.execute(insert(publication),[dict(household_id=HOME,publication_key=a.Publication.SCHOOL.value,person_id=p,state='allowed',revision=1,membership_revision=1) for p in ('mira','owen')])
    obs=a.FixtureObservation('marlin-one',a.Object.SCHOOL,1,a.Topic.SCHOOL,a.Safety.HIGH_RISK)
    repo=a.FixtureRepository((obs,obs,replace(obs,source_id='marlin-two'),replace(obs,source_id='marlin-private')),
        (a.FixturePublication(a.Publication.SCHOOL,a.Step.SCHOOL),))
    service=s.SessionService(engine,verifier,repo,synthetic_only=True,clock=clock)
    def proof(p='mira'):
        ch=verifier.challenge();now=int(time())
        token=jwt.encode(dict(iss=ISSUER,sub=p,aud=AUD,iat=now-1,nbf=now-1,exp=now+120,nonce=ch.nonce),
            key,algorithm='RS256',headers={'kid':'marlin-key'})
        return verifier.verify(token,ch)
    return service,proof,clock,repo


def establish(setup,p='mira',req='start'):
    svc,proof,_,_=setup
    result=svc.establish(proof(p),HOME,request_id=req)
    assert result.outcome is s.Outcome.COMMITTED and result.bearer
    return result


def rows(engine,table):
    with engine.connect() as c:return tuple(dict(x) for x in c.execute(select(table).order_by(table.c.id if 'id' in table.c else table.c.person_id)).mappings())


def test_equal_peer_sessions_see_one_shared_authorized_household(setup):
    svc,_,_,_=setup;mira=establish(setup);owen=establish(setup,'owen','other-start')
    left=svc.read(mira.bearer,HOME);right=svc.read(owen.bearer,HOME)
    assert left==right and left.source_count==left.security_count==2 and left.publication_count==1
    assert all('private' not in key[1] for key,_ in left.observations)
    assert not any(hasattr(svc,n) for n in ('harness_context','commit','submit','quarantine','restore','reconcile'))


def test_logout_is_individual_persistent_and_no_peer_authority(setup,engine):
    svc,_,clock,repo=setup;mira=establish(setup);owen=establish(setup,'owen','peer')
    other=s.SessionService(engine,svc._verifier,repo,synthetic_only=True,clock=clock)
    assert other.resolve(mira.bearer,HOME).person_id=='mira'
    state=svc.resolve(mira.bearer,HOME)
    assert svc.logout(mira.bearer,HOME,request_id='bye',expected_revision=state.revision).outcome is s.Outcome.COMMITTED
    with pytest.raises(s.SessionError):other.read(mira.bearer,HOME)
    assert other.read(owen.bearer,HOME).source_count==2
    assert svc.logout(mira.bearer,HOME,request_id='bye',expected_revision=state.revision).outcome is s.Outcome.UNAVAILABLE


@pytest.mark.parametrize('token',[None,'','random',b'bytes',{'person_id':'owen'},'x'*42,'x'*44,'!'*43,'é'*43])
def test_malformed_forged_or_client_identity_never_authenticates(setup,token):
    svc,_,_,_=setup
    with pytest.raises(s.SessionError,match='^Session access unavailable$'):svc.read(token,HOME)


def test_unknown_bearer_wrong_household_and_fabricated_proof_fail_closed(setup):
    svc,proof,_,_=setup;session=establish(setup)
    for token,hh in [('x'*43,HOME),(session.bearer,'finch')]:
        with pytest.raises(s.SessionError):svc.read(token,hh)
    assert svc.establish(replace(proof()),HOME,request_id='fake').outcome is s.Outcome.UNAVAILABLE
    assert svc.establish(proof(),'finch',request_id='foreign').outcome is s.Outcome.UNAVAILABLE


@pytest.mark.parametrize('kind',['membership','binding','binding-epoch','member-epoch'])
def test_current_revocation_or_epoch_change_invalidates_old_sessions(setup,engine,kind):
    svc,_,_,_=setup;session=establish(setup)
    table=member if kind.startswith('member') else binding
    with engine.begin() as c:c.execute(update(table).where(table.c.person_id=='mira').values(
        revision=2, state='revoked' if kind in ('membership','binding') else 'allowed'))
    with pytest.raises(s.SessionError):svc.read(session.bearer,HOME)
    with pytest.raises(s.SessionError):svc.history(session.bearer,HOME)


def test_reenrollment_does_not_revive_session_source_or_publication_grants(setup,engine):
    svc,proof,_,_=setup;old=establish(setup)
    with engine.begin() as c:c.execute(update(member).where(member.c.person_id=='mira').values(state='revoked',revision=2))
    with pytest.raises(s.SessionError):svc.read(old.bearer,HOME)
    with engine.begin() as c:c.execute(update(member).where(member.c.person_id=='mira').values(state='allowed',revision=3))
    with pytest.raises(s.SessionError):svc.read(old.bearer,HOME)
    new=svc.establish(proof(),HOME,request_id='rejoin');assert new.outcome is s.Outcome.COMMITTED
    view=svc.read(new.bearer,HOME)
    assert view.source_count==view.security_count==view.publication_count==0


def test_source_and_publication_revocation_are_independent(setup,engine):
    svc,_,_,_=setup;token=establish(setup).bearer
    with engine.begin() as c:c.execute(update(grant).where(grant.c.person_id=='mira').values(state='revoked',revision=2))
    view=svc.read(token,HOME);assert view.source_count==view.security_count==0 and view.publication_count==1
    assert view.publications==((a.Publication.SCHOOL,a.Step.SCHOOL),)
    with engine.begin() as c:c.execute(update(publication).where(publication.c.person_id=='mira').values(state='revoked',revision=2))
    assert svc.read(token,HOME).publication_count==0


def test_field_scope_privacy_hidden_populations_and_exact_identity(setup,engine):
    svc,_,clock,repo=setup;token=establish(setup).bearer
    with engine.begin() as c:c.execute(update(grant).where(grant.c.person_id=='mira').values(security=False))
    before=svc.read(token,HOME)
    obs=repo.observations[0]
    altered=a.FixtureRepository((obs,replace(obs,safety=a.Safety.CLEAR),repo.observations[2])+
        tuple(replace(obs,source_id='marlin-private',generation=i+1) for i in range(200)),repo.publications)
    other=s.SessionService(engine,svc._verifier,altered,synthetic_only=True,clock=clock)
    assert other.read(token,HOME)==before
    assert other.read(token,HOME,limit=1,offset=1).source_count==2
    with engine.begin() as c:c.execute(update(grant).where(grant.c.person_id=='mira').values(security=True))
    with pytest.raises(s.SessionError):other.read(token,HOME)


@pytest.mark.parametrize('seconds',[s.IDLE_SECONDS,s.ABSOLUTE_SECONDS])
def test_expiry_is_server_controlled_and_boundary_exclusive(setup,seconds):
    svc,_,clock,_=setup;token=establish(setup).bearer
    clock.now+=seconds
    with pytest.raises(s.SessionError):svc.read(token,HOME)


def test_idle_refresh_does_not_extend_absolute_and_clock_rollback_denies(setup):
    svc,_,clock,_=setup;token=establish(setup).bearer
    initial=svc.resolve(token,HOME)
    for _ in range(50):
        clock.now+=1700;state=svc.resolve(token,HOME)
        assert state.absolute_expiry==initial.absolute_expiry and state.idle_expiry<=state.absolute_expiry
    clock.now=initial.absolute_expiry
    with pytest.raises(s.SessionError):svc.resolve(token,HOME)


def test_server_clock_backward_or_invalid_denies(setup):
    svc,_,clock,_=setup;token=establish(setup).bearer
    for now in [clock.now-1,float('nan'),float('inf'),True,0]:
        clock.now=now
        with pytest.raises(s.SessionError):svc.read(token,HOME)


def test_rotation_invalidates_old_bearer_preserves_absolute_and_replay_never_returns_secret(setup,engine):
    svc,_,clock,_=setup;old=establish(setup);state=svc.resolve(old.bearer,HOME)
    clock.now+=10
    result=svc.rotate(old.bearer,HOME,request_id='rotate',expected_revision=state.revision)
    assert result.outcome is s.Outcome.COMMITTED and result.bearer!=old.bearer
    with pytest.raises(s.SessionError):svc.read(old.bearer,HOME)
    assert svc.resolve(result.bearer,HOME).absolute_expiry==state.absolute_expiry
    replay=svc.rotate(old.bearer,HOME,request_id='rotate',expected_revision=state.revision)
    assert replay.outcome is s.Outcome.UNAVAILABLE and replay.bearer is None
    assert len(rows(engine,sessions))==2 and len(rows(engine,audit))==2
    assert svc.logout(result.bearer,HOME,request_id='rotate',expected_revision=state.revision).outcome is s.Outcome.CONFLICT


def test_revoke_all_requires_independently_verified_self_identity(setup):
    svc,proof,_,_=setup;one=establish(setup);two=establish(setup,req='second');peer=establish(setup,'owen','peer')
    assert svc.revoke_all(proof(),HOME,request_id='signout-all').outcome is s.Outcome.COMMITTED
    for token in (one.bearer,two.bearer):
        with pytest.raises(s.SessionError):svc.read(token,HOME)
    assert svc.read(peer.bearer,HOME).source_count==2
    assert svc.revoke_all(proof(),HOME,request_id='signout-all').outcome is s.Outcome.REPLAY


def test_duplicate_establishment_has_one_audit_and_no_second_secret(setup,engine):
    svc,proof,_,_=setup;p=proof();first=svc.establish(p,HOME,request_id='same')
    second=svc.establish(p,HOME,request_id='same')
    assert second.outcome is s.Outcome.REPLAY and second.session_id==first.session_id and second.bearer is None
    assert len(rows(engine,sessions))==len(rows(engine,audit))==1


def test_no_plaintext_secrets_in_rows_audit_logs_errors_or_projections(setup,engine,caplog):
    svc,_,_,_=setup;issued=establish(setup)
    view=svc.read(issued.bearer,HOME);history=svc.history(issued.bearer,HOME)
    assert issued.bearer not in repr(issued)+repr(view)+repr(history)+repr(rows(engine,sessions))+repr(rows(engine,audit))+caplog.text
    assert set(rows(engine,sessions)[0])=={'id','household_id','person_id','issuer','subject','secret_hash',
       'binding_revision','membership_revision','revision','revoked','created_at','last_active','absolute_expiry','idle_expiry'}
    assert history[0]['actor_id']==history[0]['person_id']=='mira'
    peer=establish(setup,'owen','peer');assert len(svc.history(peer.bearer,HOME))==1


@pytest.mark.parametrize('mode',['rotation','duplicate','reads'])
def test_real_concurrent_session_operations_are_serialized_and_cas_protected(setup,engine,mode):
    svc,proof,_,_=setup;old=establish(setup);barrier=Barrier(2);p=proof()
    def run(i):
        barrier.wait(timeout=10)
        if mode=='rotation':return svc.rotate(old.bearer,HOME,request_id=f'rotate-{i}',expected_revision=1)
        if mode=='duplicate':return svc.establish(p,HOME,request_id='concurrent')
        return svc.resolve(old.bearer,HOME)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(run,i) for i in range(2)];values=[f.result(timeout=20) for f in futures]
    if mode=='rotation':
        assert sum(x.outcome is s.Outcome.COMMITTED for x in values)==1
        assert sum(x.outcome is s.Outcome.UNAVAILABLE for x in values)==1
        assert len(rows(engine,sessions))==2
    elif mode=='duplicate':
        assert {x.outcome for x in values}=={s.Outcome.COMMITTED,s.Outcome.REPLAY}
        assert len(rows(engine,sessions))==2
    else:
        assert {x.revision for x in values}=={2,3}
        assert rows(engine,sessions)[0]['revision']==3


@pytest.mark.parametrize('kind',['logout','membership','binding','source'])
def test_read_and_revocation_share_real_database_ordering(setup,engine,kind):
    svc,_,_,_=setup;issued=establish(setup);entered=Event();release=Event();writer_attempted=Event()
    def hold(c,cursor,sql,parameters,ctx,many):
        if current_thread().name.startswith('reader') and sql.startswith('SELECT source_read_grant'):
            entered.set();assert release.wait(15)
        if current_thread().name.startswith('writer') and ('BEGIN IMMEDIATE' in sql or ('FROM household ' in sql and 'FOR UPDATE' in sql)):
            writer_attempted.set()
    def revoke():
        if kind=='logout':return svc.logout(issued.bearer,HOME,request_id='concurrent-logout',expected_revision=2)
        with a.authorization_transaction(engine,HOME) as c:
            table={'membership':member,'binding':binding,'source':grant}[kind]
            c.execute(update(table).where(table.c.person_id=='mira').values(state='revoked',revision=2))
    event.listen(engine,'before_cursor_execute',hold)
    try:
        with ThreadPoolExecutor(max_workers=1,thread_name_prefix='reader') as rp, ThreadPoolExecutor(max_workers=1,thread_name_prefix='writer') as wp:
            read=rp.submit(svc.read,issued.bearer,HOME);assert entered.wait(10)
            write=wp.submit(revoke);assert writer_attempted.wait(10);assert not write.done()
            release.set();assert read.result(timeout=15).source_count==2
            result=write.result(timeout=15)
            if kind=='logout':assert result.outcome is s.Outcome.COMMITTED
        if kind=='source':assert svc.read(issued.bearer,HOME).source_count==0
        else:
            with pytest.raises(s.SessionError):svc.read(issued.bearer,HOME)
    finally:release.set();event.remove(engine,'before_cursor_execute',hold)


@pytest.mark.parametrize('op',['establish','rotate','logout','revoke_all'])
def test_commit_acknowledgment_loss_is_unknown_not_falsely_not_applied(setup,engine,monkeypatch,op):
    svc,proof,_,_=setup;old=establish(setup);before=rows(engine,audit)
    original=engine.dialect.do_commit;armed=True
    def lost(conn):
        nonlocal armed
        original(conn)
        if armed:armed=False;raise RuntimeError('fictional-private-ack-detail')
    monkeypatch.setattr(engine.dialect,'do_commit',lost)
    if op=='establish':result=svc.establish(proof(),HOME,request_id='ack-issue')
    elif op=='revoke_all':result=svc.revoke_all(proof(),HOME,request_id='ack-all')
    else:result=getattr(svc,op)(old.bearer,HOME,request_id='ack-change',expected_revision=1)
    assert result.outcome is s.Outcome.UNKNOWN and result.bearer is None
    assert len(rows(engine,audit))==len(before)+1


def test_failure_before_audit_rolls_back_all_session_mutation(setup,engine):
    svc,proof,_,_=setup;old=establish(setup);before=rows(engine,sessions),rows(engine,audit)
    def fail(c,cursor,sql,parameters,ctx,many):
        if sql.startswith('INSERT INTO session_audit'):raise RuntimeError('fictional-private-write-error')
    event.listen(engine,'before_cursor_execute',fail)
    try:
        assert svc.rotate(old.bearer,HOME,request_id='rollback',expected_revision=1).outcome is s.Outcome.UNKNOWN
    finally:event.remove(engine,'before_cursor_execute',fail)
    assert (rows(engine,sessions),rows(engine,audit))==before
    assert svc.read(old.bearer,HOME).source_count==2


def test_stale_cas_is_definite_not_applied_without_partial_state(setup,engine):
    svc,_,_,_=setup;old=establish(setup);svc.resolve(old.bearer,HOME)
    before=rows(engine,sessions),rows(engine,audit)
    assert svc.rotate(old.bearer,HOME,request_id='stale',expected_revision=1).outcome is s.Outcome.STALE
    assert (rows(engine,sessions),rows(engine,audit))==before


def test_isolation_no_harness_or_providers_and_exact_opt_in(setup,engine,monkeypatch):
    svc,_,clock,repo=setup
    for flag in (False,1,'true'):
        with pytest.raises(s.SessionError):s.SessionService(engine,svc._verifier,repo,synthetic_only=flag)
    monkeypatch.setattr(a.AuthorizationService,'harness_context',lambda *a,**k:pytest.fail('harness forbidden'))
    issued=establish(setup)
    assert svc.read(issued.bearer,HOME).source_count==2
    path=ROOT/'src/family_os/_household_sessions.py';tree=ast.parse(path.read_text())
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{i.name for n in ast.walk(tree) if isinstance(n,ast.Import) for i in n.names}
    assert imports <= {'dataclasses','enum','hashlib','json','re','secrets','time','uuid','sqlalchemy',
        'family_os._household_authorization','family_os._verified_identity','family_os.schema'}
    assert 'harness_context' not in path.read_text()
    for other in (ROOT/'src').rglob('*.py'):
        if other not in (path,ROOT/'src/family_os/_oidc_login.py',ROOT/'src/family_os/_fictional_read_api.py',ROOT/'src/family_os/_household_tasks.py'):assert '_household_sessions' not in other.read_text()


def test_session_migration_roundtrip_preserves_binding_membership_and_existing_grants(setup,engine):
    establish(setup);before=tuple(rows(engine,t) for t in (person,member,binding,grant,publication))
    config=Config(str(ROOT/'alembic.ini'));command.check(config)
    command.downgrade(config,'8a421d6c09be')
    assert 'household_session' not in inspect(engine).get_table_names() and 'session_audit' not in inspect(engine).get_table_names()
    assert tuple(rows(engine,t) for t in (person,member,binding,grant,publication))==before
    command.upgrade(config,'head');command.check(config)
    assert rows(engine,sessions)==rows(engine,audit)==()
    assert tuple(rows(engine,t) for t in (person,member,binding,grant,publication))==before


@pytest.mark.parametrize('op',['establish','rotate','logout','revoke_all'])
def test_unknown_commit_verification_is_read_only_exact_and_never_recovers_bearer(setup,engine,monkeypatch,op):
    svc,proof,_,_=setup;old=establish(setup);p=proof();original=engine.dialect.do_commit;armed=True
    def lost(conn):
        nonlocal armed
        original(conn)
        if armed:armed=False;raise RuntimeError('fictional-ack-loss')
    monkeypatch.setattr(engine.dialect,'do_commit',lost)
    if op=='establish':result=svc.establish(p,HOME,request_id='uncertain')
    elif op=='revoke_all':result=svc.revoke_all(p,HOME,request_id='uncertain')
    else:result=getattr(svc,op)(old.bearer,HOME,request_id='uncertain',expected_revision=1)
    assert result.outcome is s.Outcome.UNKNOWN and result.intent_hash
    before=rows(engine,sessions),rows(engine,audit)
    verified=svc.verify_outcome(p,HOME,request_id='uncertain',intent_hash=result.intent_hash)
    assert verified.outcome is s.Outcome.COMMITTED and verified.bearer is None
    assert (rows(engine,sessions),rows(engine,audit))==before
    assert svc.verify_outcome(p,HOME,request_id='uncertain',intent_hash='f'*64).outcome is s.Outcome.CONFLICT
    peer=proof('owen')
    assert svc.verify_outcome(peer,HOME,request_id='uncertain',intent_hash=result.intent_hash).outcome is s.Outcome.NOT_APPLIED
    def unavailable():raise RuntimeError('fictional-private-db-error')
    with monkeypatch.context() as patch:
        patch.setattr(engine.pool,'recreate',unavailable)
        assert svc.verify_outcome(p,HOME,request_id='uncertain',intent_hash=result.intent_hash).outcome is s.Outcome.UNKNOWN


def test_rollback_can_be_established_without_conflating_it_with_changed_intent(setup,engine):
    svc,proof,_,_=setup;old=establish(setup);p=proof();before=rows(engine,sessions),rows(engine,audit)
    def fail(c,cursor,sql,parameters,ctx,many):
        if sql.startswith('INSERT INTO session_audit'):raise RuntimeError('fictional-audit-failure')
    event.listen(engine,'before_cursor_execute',fail)
    try:result=svc.rotate(old.bearer,HOME,request_id='failed',expected_revision=1)
    finally:event.remove(engine,'before_cursor_execute',fail)
    assert result.outcome is s.Outcome.UNKNOWN
    assert svc.verify_outcome(p,HOME,request_id='failed',intent_hash=result.intent_hash).outcome is s.Outcome.NOT_APPLIED
    assert (rows(engine,sessions),rows(engine,audit))==before


def test_copy_of_opaque_bearer_is_not_device_bound_but_client_identity_cannot_override_it(setup):
    svc,_,_,_=setup;issued=establish(setup);copied=''.join(list(issued.bearer))
    assert svc.resolve(copied,HOME).person_id=='mira'
    with pytest.raises(s.SessionError):svc.resolve({'bearer':copied,'person_id':'owen'},HOME)
    with pytest.raises(s.SessionError):svc.resolve(copied,'finch')


@pytest.mark.parametrize('bad',[(0,0),(21,0),(True,0),(1,-1),(1,129)])
def test_invalid_bounded_queries_do_not_touch_session_or_audit(setup,engine,bad):
    svc,_,_,_=setup;token=establish(setup).bearer;before=rows(engine,sessions),rows(engine,audit)
    with pytest.raises(s.SessionError):svc.read(token,HOME,limit=bad[0],offset=bad[1])
    assert (rows(engine,sessions),rows(engine,audit))==before


def test_source_operation_separation_no_real_table_queries_or_network(setup,engine,monkeypatch):
    svc,_,_,_=setup;issued=establish(setup)
    def inspect_sql(c,cursor,sql,parameters,ctx,many):
        assert not any(name in sql for name in ('raw_source_record','source_record','source_analysis','source_sync_state'))
        assert issued.bearer not in str(parameters)
    event.listen(engine,'before_cursor_execute',inspect_sql)
    try:
        monkeypatch.setattr('socket.socket',lambda *a,**k:pytest.fail('network forbidden'))
        assert svc.read(issued.bearer,HOME).source_count==2
    finally:event.remove(engine,'before_cursor_execute',inspect_sql)


def test_database_session_scope_and_unique_hash_are_enforced(setup,engine):
    establish(setup);row=rows(engine,sessions)[0]
    for changes in [dict(id='different-id'),dict(id='other',secret_hash='b'*64,person_id='owen'),
                    dict(id='other',secret_hash='c'*64,household_id='finch'),
                    dict(id='other',secret_hash='c'*64,membership_revision=0),
                    dict(id='other',secret_hash='c'*64,idle_expiry=row['last_active'])]:
        bad=dict(row);bad.update(changes)
        with pytest.raises(IntegrityError):
            with engine.begin() as c:c.execute(insert(sessions).values(**bad))
    assert len(rows(engine,sessions))==1


def test_fresh_session_identity_provisioning_rejects_unbound_or_changed_proof(setup,engine):
    svc,proof,_,_=setup
    assert svc.establish(proof('not-bound'),HOME,request_id='unbound').outcome is s.Outcome.UNAVAILABLE
    assert rows(engine,sessions)==rows(engine,audit)==()
    with engine.begin() as c:c.execute(update(binding).where(binding.c.person_id=='mira').values(state='revoked',revision=2))
    assert svc.establish(proof(),HOME,request_id='revoked').outcome is s.Outcome.UNAVAILABLE
    assert rows(engine,sessions)==()


def test_revoked_bearer_denies_every_use_without_misreporting_historical_commit(setup,engine):
    svc,proof,_,_=setup;old=establish(setup)
    result=svc.rotate(old.bearer,HOME,request_id='replace',expected_revision=1)
    assert result.outcome is s.Outcome.COMMITTED
    for method in (svc.read,svc.resolve,svc.history):
        with pytest.raises(s.SessionError):method(old.bearer,HOME)
    before=rows(engine,sessions),rows(engine,audit)
    replay=svc.rotate(old.bearer,HOME,request_id='replace',expected_revision=1)
    assert replay.outcome is s.Outcome.UNAVAILABLE and replay.bearer is None
    assert (rows(engine,sessions),rows(engine,audit))==before
    verified=svc.verify_outcome(proof(),HOME,request_id='replace',intent_hash=result.intent_hash)
    assert verified.outcome is s.Outcome.COMMITTED and verified.bearer is None
