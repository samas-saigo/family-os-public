"""G2a new Copper booking / Willow school cases in disposable migrated stores only."""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import select, insert, update, inspect, event
from sqlalchemy.exc import IntegrityError

from family_os import _household_authorization as a
from family_os.registry import register
from family_os.schema import (household_membership as member, source_read_grant as source,
    publication_scope as scope, publication_read_grant as publication, authorization_audit as audit,
    person, source_account)


ROOT = Path(__file__).parents[1]
HOME = 'harbor'
OBS = a.FixtureObservation('nova-primary', a.Object.BOOKING, 1, a.Topic.BOOKING, a.Safety.HIGH_RISK)
PUB = a.FixturePublication(a.Publication.BOOKING, a.Step.BOOKING)


def seed(engine):
    register(engine, {'household': {'id': HOME, 'name': 'Fictional Harbor'},
        'people': [{'id': 'nova', 'display_name': 'Fictional Nova'}, {'id': 'eli', 'display_name': 'Fictional Eli'}],
        'source_accounts': [
            {'id': s, 'provider': 'fixture', 'owner_type': 'person', 'owner_id': 'nova'}
            for s in ('nova-primary', 'nova-secondary')] +
            [{'id': 'shared-notices', 'provider': 'fixture', 'owner_type': 'household', 'owner_id': HOME}]})
    register(engine, {'household': {'id': 'glen', 'name': 'Fictional Glen'},
        'people': [{'id': 'rue', 'display_name': 'Fictional Rue'}],
        'source_accounts': [{'id': 'rue-mail', 'provider': 'fixture', 'owner_type': 'person', 'owner_id': 'rue'}]})
    with engine.begin() as c:
        c.execute(insert(member), [dict(household_id=HOME, person_id=p, state='allowed', revision=1) for p in ('nova','eli')]
            + [dict(household_id='glen', person_id='rue', state='allowed', revision=1)])
        c.execute(insert(scope), [dict(household_id=HOME, publication_key=p.value, approved=True) for p in a.Publication])
    repo = a.FixtureRepository((OBS, replace(OBS, source_id='nova-secondary'), replace(OBS, source_id='shared-notices')),
                              (PUB,))
    s = a.AuthorizationService(engine, repo, synthetic_only=True)
    admin = s.harness_context(HOME, 'eli', manage_membership=True,
                             sources=('nova-primary','nova-secondary','shared-notices','rue-mail'), publications=tuple(a.Publication))
    for p in ('nova','eli'):
        for src in ('nova-primary','nova-secondary','shared-notices'):
            change = a.Change(HOME, a.Kind.SOURCE, p, src, a.State.ALLOWED, 0, f'initial-{p}-{src}', True, True)
            assert s.commit(admin, s.submit(admin, change), confirm=True).outcome is a.Outcome.COMMITTED
        change = a.Change(HOME, a.Kind.PUBLICATION, p, a.Publication.BOOKING.value, a.State.ALLOWED, 0, f'initial-task-{p}')
        assert s.commit(admin, s.submit(admin, change), confirm=True).outcome is a.Outcome.COMMITTED
    return s, admin, s.harness_context(HOME, 'nova')


def change(kind=a.Kind.SOURCE, resource='nova-primary', recipient='nova', state=a.State.REVOKED,
           expected=1, request='revoke-one', **flags):
    return a.Change(HOME, kind, recipient, resource, state, expected, request, **flags)


def save(s, ctx, cmd):
    return s.commit(ctx, s.submit(ctx, cmd), confirm=True)


def rows(engine, table):
    with engine.connect() as c:
        return tuple(dict(r) for r in c.execute(select(table)).mappings())


def test_shared_peers_multiple_accounts_and_one_independent_publication(engine):
    s, admin, nova = seed(engine)
    assert s.read(admin) == s.read(nova)
    assert s.read(nova).source_count == s.read(nova).security_count == 3
    assert s.read(nova).publication_count == 1
    assert save(s, admin, change()).outcome is a.Outcome.COMMITTED
    assert s.read(nova).source_count == 2
    assert s.read(nova).publications == s.read(admin).publications == ((a.Publication.BOOKING, a.Step.BOOKING),)
    assert s.read(admin).source_count == 3


def test_task_permission_revocation_is_independent_of_source_and_has_no_execution_rights(engine):
    s, admin, nova = seed(engine)
    assert save(s, admin, change(a.Kind.PUBLICATION, a.Publication.BOOKING.value)).outcome is a.Outcome.COMMITTED
    assert s.read(nova).publication_count == 0 and s.read(nova).source_count == 3
    assert s.read(admin).publication_count == 1
    assert not any(hasattr(s, name) for name in ('quarantine','restore','reconcile','dispatch'))
    with pytest.raises(a.Failure):
        s.submit(nova, change())
    with pytest.raises(a.Failure):
        s.history(nova, a.Kind.SOURCE, 'nova-primary')


def test_actual_actor_not_source_owner_and_history_never_resurrects(engine):
    s, admin, nova = seed(engine)
    before = s.history(admin, a.Kind.SOURCE, 'nova-primary')
    assert save(s, admin, change()).revision == 2
    history = s.history(admin, a.Kind.SOURCE, 'nova-primary')
    assert history[:len(before)] == before
    last = next(r for r in history if r['recipient_id']=='nova' and r['revision']==2)
    assert last['actor_id']=='eli' and last['recipient_id']=='nova'
    assert last['old_state']=='allowed' and last['new_state']=='revoked' and last['outcome']=='committed'
    assert len([r for r in history if r['recipient_id']=='nova' and r['new_state']=='allowed'])==1
    assert s.read(nova).source_count==2
    assert rows(engine, source)[0]['person_id'] in ('nova','eli')


@pytest.mark.parametrize('kind,resource', ((a.Kind.SOURCE,'rue-mail'), (a.Kind.MEMBERSHIP,None),
                                         (a.Kind.PUBLICATION,a.Publication.BOOKING.value)))
def test_cross_household_recipient_and_resource_fail_zero_writes(engine, kind, resource):
    s, admin, nova = seed(engine); before=rows(engine,audit)
    assert save(s,admin,change(kind,resource,recipient='rue',expected=0)).outcome is a.Outcome.REJECTED
    if kind is a.Kind.SOURCE:
        assert save(s,admin,change(resource='rue-mail',expected=0)).outcome is a.Outcome.REJECTED
    assert rows(engine,audit)==before
    with pytest.raises(a.Failure):
        s.submit(admin,replace(change(),household_id='glen'))
    with pytest.raises(a.Failure):
        s.harness_context('glen','nova')


def test_database_tenancy_uniqueness_and_state_constraints(engine):
    s, admin, nova=seed(engine)
    good=next(r for r in rows(engine,source) if r['person_id']=='nova')
    for bad in (good, good|{'source_account_id':'rue-mail'}, good|{'person_id':'rue'},
                good|{'person_id':'nova','source_account_id':'missing'}, good|{'state':'unknown'},good|{'revision':0}):
        with pytest.raises(IntegrityError):
            with engine.begin() as c:
                c.execute(insert(source).values(**bad))
    assert s.read(nova).source_count==3


def test_duplicate_request_exact_replay_changed_intent_conflict_and_no_silent_regrant(engine):
    s, admin, nova=seed(engine); cmd=change(); ticket=s.submit(admin,cmd)
    assert ticket.outcome is a.Outcome.SUBMITTED and s.read(nova).source_count==3
    assert s.commit(admin,ticket,confirm=True)==a.Result(a.Outcome.COMMITTED,2)
    before=rows(engine,audit)
    assert s.commit(admin,ticket,confirm=True)==a.Result(a.Outcome.REPLAY,2)
    assert save(s,admin,replace(cmd,state=a.State.ALLOWED)).outcome is a.Outcome.CONFLICT
    assert save(s,admin,replace(cmd,request_id='old-expansion',state=a.State.ALLOWED)).outcome is a.Outcome.STALE
    assert rows(engine,audit)==before and s.read(nova).source_count==2
    assert save(s,admin,change(state=a.State.ALLOWED,expected=2,request='fresh-regrant',observations=True)).revision==3
    assert s.read(nova).source_count==3 and s.read(nova).security_count==2


@pytest.mark.parametrize('confirm,expected', ((False,a.Outcome.CANCELED),(1,a.Outcome.REJECTED),('save',a.Outcome.REJECTED)))
def test_cancel_unconfirmed_or_invalid_confirmation_never_writes(engine,confirm,expected):
    s,admin,nova=seed(engine); before=rows(engine,audit),rows(engine,source)
    result=s.commit(admin,s.submit(admin,change()),confirm=confirm)
    assert result.outcome is expected
    assert (rows(engine,audit),rows(engine,source))==before


def test_rollback_after_grant_update_before_audit_preserves_authority(engine):
    s,admin,nova=seed(engine); before=rows(engine,source),rows(engine,audit)
    def fail(c,cursor,statement,parameters,context,many):
        if statement.startswith('INSERT INTO authorization_audit'):
            raise RuntimeError('synthetic-private-error')
    event.listen(engine,'before_cursor_execute',fail)
    try:
        assert save(s,admin,change()).outcome is a.Outcome.CONFLICT
    finally:
        event.remove(engine,'before_cursor_execute',fail)
    assert (rows(engine,source),rows(engine,audit))==before
    assert s.read(nova).source_count==3


def test_revoked_member_and_fabricated_context_cannot_read_mutate_or_inspect_history(engine):
    s,admin,nova=seed(engine); prepared=s.prepare_read(nova)
    assert save(s,admin,change(a.Kind.MEMBERSHIP,None)).outcome is a.Outcome.COMMITTED
    for call in (lambda:s.read(nova),lambda:s.consume_read(nova,prepared),lambda:s.read(replace(admin)),
                 lambda:s.history(nova,a.Kind.SOURCE,'nova-primary')):
        with pytest.raises(a.Failure):call()
    assert s.commit(nova,a.Submission(nova,change()),confirm=True).outcome is a.Outcome.UNAVAILABLE
    assert s.read(admin).source_count==3
    assert save(s,admin,change(a.Kind.MEMBERSHIP,None,state=a.State.ALLOWED,expected=2,request='member-rejoin')).revision==3
    renewed=s.harness_context(HOME,'nova')
    assert s.read(renewed).source_count==s.read(renewed).publication_count==0
    with pytest.raises(a.Failure):s.read(nova)


def test_prepared_reads_have_no_payload_and_recheck_current_source_and_task_grants(engine):
    s,admin,nova=seed(engine); prepared=s.prepare_read(nova)
    assert not hasattr(prepared,'observations')
    save(s,admin,change())
    save(s,admin,change(a.Kind.PUBLICATION,a.Publication.BOOKING.value,request='task-revoke'))
    result=s.consume_read(nova,prepared)
    assert result.source_count==2 and result.publication_count==0
    with pytest.raises(a.Failure):s.consume_read(admin,prepared)


@pytest.mark.parametrize('same', (False,True))
def test_true_concurrent_grant_changes_serialize_and_duplicate_submissions_converge(engine,same):
    s,admin,nova=seed(engine); barrier=Barrier(2)
    cmd=change()
    other=cmd if same else change(state=a.State.ALLOWED,request='expand',observations=True,security=False)
    tickets=[s.submit(admin,c) for c in (cmd,other)]
    def work(ticket):
        barrier.wait(timeout=5)
        return s.commit(admin,ticket,confirm=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(work,t) for t in tickets]
        results=[f.result(timeout=15) for f in futures]
    assert [r.outcome for r in results].count(a.Outcome.COMMITTED)==1
    assert [r.outcome for r in results].count(a.Outcome.REPLAY if same else a.Outcome.STALE)==1
    assert len([r for r in rows(engine,audit) if r['scope_key']=='nova-primary' and r['recipient_id']=='nova' and r['revision']==2])==1


def test_revocation_committed_while_prepared_request_waits_yields_fresh_denial(engine):
    s,admin,nova=seed(engine); ready=Event(); revoked=Event()
    def reader():
        p=s.prepare_read(nova);ready.set()
        assert revoked.wait(10)
        return s.consume_read(nova,p)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future=pool.submit(reader)
        assert ready.wait(10)
        assert save(s,admin,change()).outcome is a.Outcome.COMMITTED
        revoked.set()
        assert future.result(timeout=15).source_count==2


def test_read_transaction_orders_before_overlapping_revocation(engine):
    s,admin,nova=seed(engine); entered=Event(); release=Event(); writer_started=Event(); lock_attempted=Event()
    def hold_read(c,cursor,statement,parameters,ctx,many):
        if entered.is_set() and (statement == 'BEGIN IMMEDIATE' or 'FOR UPDATE' in statement):
            lock_attempted.set()
        if statement.startswith('SELECT source_read_grant.source_account_id') and not entered.is_set():
            entered.set();assert release.wait(10)
    event.listen(engine,'before_cursor_execute',hold_read)
    def writer():
        writer_started.set();return save(s,admin,change())
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            read=pool.submit(s.read,nova);assert entered.wait(10)
            write=pool.submit(writer);assert writer_started.wait(10);assert lock_attempted.wait(10)
            assert not write.done()  # Reader holds writer/household ordering, not remote disclosure.
            release.set()
            assert read.result(timeout=15).source_count==3
            assert write.result(timeout=15).outcome is a.Outcome.COMMITTED
    finally:
        release.set();event.remove(engine,'before_cursor_execute',hold_read)
    assert s.read(nova).source_count==2


@pytest.mark.parametrize('safety',tuple(a.Safety))
def test_field_scope_privacy_with_hidden_population_and_safety_only_changes(engine,safety):
    s,admin,nova=seed(engine)
    save(s,admin,change(state=a.State.ALLOWED,request='observation-only',observations=True))
    save(s,admin,change(resource='nova-secondary',request='hidden-source'))
    before=s.read(nova)
    repo=a.FixtureRepository((OBS,replace(OBS,safety=safety),replace(OBS,source_id='shared-notices'))+tuple(replace(OBS,source_id='nova-secondary',generation=i+1) for i in range(200))+
                             (replace(OBS,source_id='rue-mail'),),s._repository.publications)
    other=a.AuthorizationService(engine,repo,synthetic_only=True);context=other.harness_context(HOME,'nova')
    assert other.read(context)==before


def test_authorized_generation_and_security_conflicts_fail_without_arbitrary_clearance(engine):
    s,admin,nova=seed(engine)
    for altered in (replace(OBS,generation=2),replace(OBS,safety=a.Safety.CLEAR)):
        other=a.AuthorizationService(engine,a.FixtureRepository((OBS,altered)),synthetic_only=True)
        with pytest.raises(a.Failure):other.read(other.harness_context(HOME,'nova'))
    other=a.AuthorizationService(engine,a.FixtureRepository((OBS,OBS)),synthetic_only=True)
    assert other.read(other.harness_context(HOME,'nova')).source_count==1


def test_no_provider_tables_or_clients_are_used_by_internal_read_path(engine,monkeypatch):
    s,admin,nova=seed(engine)
    def forbidden(c,cursor,sql,parameters,ctx,many):
        assert not any(name in sql for name in ('raw_source_record','source_record','source_analysis','source_sync_state'))
    event.listen(engine,'before_cursor_execute',forbidden)
    try:
        monkeypatch.setattr('socket.socket',lambda *args,**kwargs:pytest.fail('network forbidden'))
        assert s.read(nova).source_count==3
    finally:event.remove(engine,'before_cursor_execute',forbidden)
    path=ROOT/'src/family_os/_household_authorization.py';tree=ast.parse(path.read_text())
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    imports|={v.name for n in ast.walk(tree) if isinstance(n,ast.Import) for v in n.names}
    assert imports <= {'contextlib','dataclasses','datetime','enum','hashlib','json','re','uuid','sqlalchemy','sqlalchemy.exc','family_os.schema'}
    for p in (ROOT/'src').rglob('*.py'):
        if p not in (path, ROOT/'src/family_os/_household_sessions.py', ROOT/'src/family_os/_household_tasks.py', ROOT/'src/family_os/_fictional_information.py'):assert '_household_authorization' not in p.read_text()


def test_migration_roundtrip_preserves_existing_identity_and_authorization_is_derived(engine):
    s,admin,nova=seed(engine); identities=rows(engine,person),rows(engine,source_account)
    config=Config(str(ROOT/'alembic.ini'));command.check(config)
    command.downgrade(config,'913feab82c07')
    assert 'household_membership' not in inspect(engine).get_table_names()
    assert (rows(engine,person),rows(engine,source_account))==identities
    command.upgrade(config,'head');command.check(config)
    assert rows(engine,member)==() and rows(engine,audit)==()
    assert (rows(engine,person),rows(engine,source_account))==identities


def test_initial_membership_creation_requires_existing_actor_and_logs_enrollment(engine):
    s,admin,nova=seed(engine)
    with engine.begin() as c:
        c.execute(insert(person).values(id='sage',household_id=HOME,display_name='Fictional Sage',metadata={}))
    cmd=change(a.Kind.MEMBERSHIP,None,recipient='sage',state=a.State.ALLOWED,expected=0,request='enroll-sage')
    assert save(s,admin,cmd)==a.Result(a.Outcome.COMMITTED,1)
    sage=s.harness_context(HOME,'sage');assert s.read(sage).source_count==0
    log=next(v for v in s.history(admin,a.Kind.MEMBERSHIP) if v['recipient_id']=='sage')
    assert log['actor_id']=='eli' and log['old_state'] is None and log['old_revision']==0 and log['revision']==1


@pytest.mark.parametrize('kind,resource',((a.Kind.SOURCE,'nova-primary'),(a.Kind.PUBLICATION,a.Publication.BOOKING.value)))
def test_revoked_recipient_cannot_receive_implicit_new_grants(engine,kind,resource):
    s,admin,nova=seed(engine)
    save(s,admin,change(a.Kind.MEMBERSHIP,None))
    before=rows(engine,audit)
    assert save(s,admin,change(kind,resource,state=a.State.ALLOWED,request='cannot-pregrant')).outcome is a.Outcome.REJECTED
    assert rows(engine,audit)==before


def test_membership_renewal_requires_explicit_new_source_and_publication_grants(engine):
    s,admin,nova=seed(engine)
    save(s,admin,change(a.Kind.MEMBERSHIP,None))
    save(s,admin,change(a.Kind.MEMBERSHIP,None,state=a.State.ALLOWED,expected=2,request='rejoin'))
    renewed=s.harness_context(HOME,'nova')
    assert s.read(renewed).source_count==s.read(renewed).publication_count==0
    assert save(s,admin,change(state=a.State.ALLOWED,request='explicit-new-epoch',observations=True)).revision==2
    assert save(s,admin,change(a.Kind.PUBLICATION,a.Publication.BOOKING.value,state=a.State.ALLOWED,request='publish-new-epoch')).revision==2
    assert s.read(renewed).source_count==1 and s.read(renewed).publication_count==1


@pytest.mark.parametrize('limit,offset',((0,0),(21,0),(True,0),(1,-1),(1,129)))
def test_bounds_fail_closed_without_grant_mutation(engine,limit,offset):
    s,admin,nova=seed(engine);before=rows(engine,audit)
    with pytest.raises(a.Failure):s.read(nova,limit=limit,offset=offset)
    with pytest.raises(a.Failure):s.prepare_read(nova,limit=limit,offset=offset)
    assert rows(engine,audit)==before


def test_publication_approval_is_independent_and_fields_never_enriched_from_private_sources(engine):
    s,admin,nova=seed(engine);before=s.read(nova).publications
    for i,src in enumerate(('nova-primary','nova-secondary','shared-notices')):
        save(s,admin,change(resource=src,request=f'private-{i}'))
    assert s.read(nova).source_count==s.read(nova).security_count==0
    assert s.read(nova).publications==before
    with engine.begin() as c:
        c.execute(update(scope).where(scope.c.household_id==HOME).values(approved=False))
    assert s.read(nova).publication_count==0


def test_source_account_disabled_or_nonfixture_is_not_enabled_by_read_permission(engine):
    s,admin,nova=seed(engine)
    with engine.begin() as c:
        c.execute(update(source_account).where(source_account.c.id=='nova-primary').values(enabled=False))
        c.execute(update(source_account).where(source_account.c.id=='nova-secondary').values(provider='synthetic-nonfixture'))
    assert s.read(nova).source_count==1 and s.read(nova).publication_count==1
    assert save(s,admin,change(resource='nova-secondary')).outcome is a.Outcome.REJECTED


def test_history_and_replay_recheck_actor_membership_before_disclosure(engine):
    s,admin,nova=seed(engine);ticket=s.submit(admin,change())
    assert s.commit(admin,ticket,confirm=True).outcome is a.Outcome.COMMITTED
    other=s.harness_context(HOME,'nova',manage_membership=True)
    save(s,other,change(a.Kind.MEMBERSHIP,None,recipient='eli',request='revoke-admin'))
    assert s.commit(admin,ticket,confirm=True).outcome is a.Outcome.UNAVAILABLE
    with pytest.raises(a.Failure):s.history(admin,a.Kind.SOURCE,'nova-primary')


def test_autocommit_and_unverified_postgres_isolation_fail_closed(engine):
    s,admin,nova=seed(engine)
    levels=['AUTOCOMMIT'] + (['REPEATABLE READ','SERIALIZABLE'] if engine.dialect.name=='postgresql' else [])
    for level in levels:
        unsupported=a.AuthorizationService(engine.execution_options(isolation_level=level),s._repository,synthetic_only=True)
        with pytest.raises(a.Failure):unsupported.harness_context(HOME,'nova')


def test_current_source_identity_excludes_generation_and_counts_duplicates_once(engine):
    s,admin,nova=seed(engine)
    same=a.AuthorizationService(engine,a.FixtureRepository((OBS,OBS)),synthetic_only=True)
    assert same.read(same.harness_context(HOME,'nova')).source_count==1
    inconsistent=a.AuthorizationService(engine,a.FixtureRepository((OBS,replace(OBS,generation=2))),synthetic_only=True)
    with pytest.raises(a.Failure):inconsistent.read(inconsistent.harness_context(HOME,'nova'))


def test_durable_permissions_visible_to_independent_service_instances(engine):
    s,admin,nova=seed(engine)
    second=a.AuthorizationService(engine,s._repository,synthetic_only=True);viewer=second.harness_context(HOME,'nova')
    assert s.read(nova)==second.read(viewer)
    save(s,admin,change())
    assert s.read(nova)==second.read(viewer) and second.read(viewer).source_count==2


def test_authorization_migration_preserves_source_raw_analysis_and_fact_history(engine):
    from datetime import datetime,timezone
    from family_os.schema import raw_source_record,source_record,source_analysis,analysis_fact
    s,admin,nova=seed(engine);now=datetime.now(timezone.utc)
    with engine.begin() as c:
        c.execute(insert(raw_source_record).values(id='g2-raw',household_id=HOME,source_account_id='nova-primary',
            provider_object_id='synthetic-migration',payload_hash='a'*64,payload={'synthetic':True},ingested_at=now))
        c.execute(insert(source_record).values(id='g2-source',household_id=HOME,source_account_id='nova-primary',
            provider_object_id='synthetic-migration',record_type='document',recipients=[],raw_metadata={},raw_record_id='g2-raw',ingested_at=now,updated_at=now))
        c.execute(insert(source_analysis).values(id='g2-analysis',household_id=HOME,source_account_id='nova-primary',
            source_record_id='g2-source',raw_record_id='g2-raw',provider_object_id='synthetic-migration',analyzer_name='g2-test',
            analyzer_version='v1',taxonomy_version='v1',threshold_policy_version='v1',input_fingerprint='a'*64,
            definition_fingerprint='b'*64,relevance_label='uncertain',relevance_confidence=0,domain_confidence=0,
            action_label='uncertain',action_confidence=0,review_recommended=True,created_at=now))
        c.execute(insert(analysis_fact).values(id='g2-fact',analysis_id='g2-analysis',household_id=HOME,source_record_id='g2-source',
            fact_name='fictional',fact_value=True,confidence=.5,evidence_refs=[],ordinal=0,review_recommended=True,created_at=now))
    tables=(raw_source_record,source_record,source_analysis,analysis_fact)
    before=tuple(rows(engine,t) for t in tables)
    config=Config(str(ROOT/'alembic.ini'));command.downgrade(config,'913feab82c07')
    assert tuple(rows(engine,t) for t in tables)==before
    command.upgrade(config,'head');command.check(config)
    assert tuple(rows(engine,t) for t in tables)==before


def test_old_pending_submission_cannot_transfer_to_rejoined_recipient_membership(engine):
    s,admin,nova=seed(engine)
    pending=s.submit(admin,change(state=a.State.ALLOWED,request='pending-expansion',observations=True))
    save(s,admin,change(a.Kind.MEMBERSHIP,None))
    save(s,admin,change(a.Kind.MEMBERSHIP,None,state=a.State.ALLOWED,expected=2,request='recipient-rejoin'))
    before=rows(engine,audit)
    assert s.commit(admin,pending,confirm=True).outcome is a.Outcome.STALE
    assert rows(engine,audit)==before
    renewed=s.harness_context(HOME,'nova')
    assert s.read(renewed).source_count==0


@pytest.mark.parametrize('expansion', (False, True))
@pytest.mark.parametrize('error_type', ('sqlalchemy', 'runtime', 'failure'))
def test_post_commit_ack_loss_is_verified_on_fresh_connection_without_duplicate_effect(engine, monkeypatch, caplog, expansion, error_type):
    from sqlalchemy.exc import OperationalError
    s,admin,nova=seed(engine)
    cmd=change(state=a.State.ALLOWED if expansion else a.State.REVOKED,
               observations=expansion, security=False)
    ticket=s.submit(admin,cmd)
    previous_audit=rows(engine,audit)
    original=engine.dialect.do_commit
    armed=True; original_driver=[]; new_drivers=[]; updates=[]
    def capture(c,cursor,sql,parameters,ctx,many):
        if sql.startswith('UPDATE source_read_grant'):
            original_driver.append(c.connection.driver_connection); updates.append(sql)
    def connected(driver,record):new_drivers.append(driver)
    def lost(conn):
        nonlocal armed
        original(conn)  # Actual database commit succeeds before the synthetic acknowledgment loss.
        if armed:
            armed=False
            if error_type=='sqlalchemy':
                raise OperationalError('private-synthetic-driver-detail', {}, RuntimeError('private-token-shaped-text'))
            if error_type=='failure':raise a.Failure()
            raise RuntimeError('private-synthetic-runtime-detail')
    event.listen(engine,'before_cursor_execute',capture)
    event.listen(engine.pool,'connect',connected)
    monkeypatch.setattr(engine.dialect,'do_commit',lost)
    try:
        assert s.commit(admin,ticket,confirm=True)==a.Result(a.Outcome.COMMITTED,2)
        assert len(updates)==1 and new_drivers
        assert all(driver is not original_driver[0] for driver in new_drivers)
        assert s.commit(admin,ticket,confirm=True)==a.Result(a.Outcome.REPLAY,2)
        assert len(updates)==1
    finally:
        event.remove(engine,'before_cursor_execute',capture)
        event.remove(engine.pool,'connect',connected)
    assert len(rows(engine,audit))==len(previous_audit)+1
    actual=next(v for v in rows(engine,source) if v['person_id']=='nova' and v['source_account_id']=='nova-primary')
    assert actual['state']==cmd.state.value and actual['revision']==2
    assert s.read(nova).source_count==(3 if expansion else 2)
    assert 'private' not in caplog.text


@pytest.mark.parametrize('expansion', (False, True))
def test_commit_ack_loss_with_database_unavailable_preserves_unknown_then_exact_reconciliation(engine, monkeypatch, caplog, expansion):
    s,admin,nova=seed(engine)
    ticket=s.submit(admin,change(state=a.State.ALLOWED if expansion else a.State.REVOKED, observations=expansion))
    before=rows(engine,audit)
    original=engine.dialect.do_commit
    armed=True
    def lost(conn):
        nonlocal armed
        original(conn)
        if armed:
            armed=False
            raise RuntimeError('private-ack-error')
    def unavailable():raise RuntimeError('private-connect-error')
    with monkeypatch.context() as patch:
        patch.setattr(engine.dialect,'do_commit',lost)
        patch.setattr(engine.pool,'recreate',unavailable)
        result=s.commit(admin,ticket,confirm=True)
        assert result==a.Result(a.Outcome.UNKNOWN)
        assert 'private' not in str(result)
        assert s.reconcile_change(admin,ticket)==a.Result(a.Outcome.UNKNOWN)
    assert len(rows(engine,audit))==len(before)+1
    assert s.reconcile_change(admin,ticket)==a.Result(a.Outcome.COMMITTED,2)
    assert s.commit(admin,ticket,confirm=True)==a.Result(a.Outcome.REPLAY,2)
    assert len(rows(engine,audit))==len(before)+1
    assert 'private' not in caplog.text


@pytest.mark.parametrize('stage', ('before-update','before-audit'))
@pytest.mark.parametrize('sqlalchemy_error', (False,True))
def test_verified_failed_transaction_returns_not_applied_only_after_fresh_ledger_proof(engine,stage,sqlalchemy_error):
    from sqlalchemy.exc import OperationalError
    s,admin,nova=seed(engine);ticket=s.submit(admin,change());before=rows(engine,source),rows(engine,audit)
    def fail(c,cursor,sql,parameters,ctx,many):
        target='UPDATE source_read_grant' if stage=='before-update' else 'INSERT INTO authorization_audit'
        if sql.startswith(target):
            if sqlalchemy_error:raise OperationalError('private-synthetic-sql',{},RuntimeError('private-driver'))
            raise RuntimeError('private-synthetic-error')
    event.listen(engine,'before_cursor_execute',fail)
    try:assert s.commit(admin,ticket,confirm=True)==a.Result(a.Outcome.CONFLICT)
    finally:event.remove(engine,'before_cursor_execute',fail)
    assert (rows(engine,source),rows(engine,audit))==before
    assert s.read(nova).source_count==3


def test_failed_transaction_and_unavailable_proof_remain_unknown_not_claimed_unapplied(engine,monkeypatch):
    s,admin,nova=seed(engine);ticket=s.submit(admin,change())
    def fail(c,cursor,sql,parameters,ctx,many):
        if sql.startswith('INSERT INTO authorization_audit'):raise RuntimeError('synthetic-audit-failure')
    def unavailable():raise RuntimeError('synthetic-database-unavailable')
    event.listen(engine,'before_cursor_execute',fail)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(engine.pool,'recreate',unavailable)
            assert s.commit(admin,ticket,confirm=True)==a.Result(a.Outcome.UNKNOWN)
    finally:event.remove(engine,'before_cursor_execute',fail)
    assert s.reconcile_change(admin,ticket)==a.Result(a.Outcome.CONFLICT)


def test_reconciliation_distinguishes_exact_historical_commit_from_changed_intent(engine):
    s,admin,nova=seed(engine);ticket=s.submit(admin,change())
    assert s.commit(admin,ticket,confirm=True).outcome is a.Outcome.COMMITTED
    before=rows(engine,audit)
    assert s.reconcile_change(admin,ticket)==a.Result(a.Outcome.COMMITTED,2)
    changed=s.submit(admin,replace(ticket.change,state=a.State.ALLOWED))
    assert s.reconcile_change(admin,changed)==a.Result(a.Outcome.CONFLICT)
    assert rows(engine,audit)==before and s.read(nova).source_count==2


def test_reconciliation_requires_current_actor_and_exact_bound_submission(engine):
    s,admin,nova=seed(engine);ticket=s.submit(admin,change());save(s,admin,change())
    assert s.reconcile_change(nova,ticket)==a.Result(a.Outcome.UNKNOWN)
    assert s.reconcile_change(replace(admin),ticket)==a.Result(a.Outcome.UNKNOWN)
    other=s.harness_context(HOME,'nova',manage_membership=True)
    save(s,other,change(a.Kind.MEMBERSHIP,None,recipient='eli',request='revoke-reconciler'))
    assert s.reconcile_change(admin,ticket)==a.Result(a.Outcome.UNKNOWN)


def test_matching_hash_but_inconsistent_audit_is_not_accepted_as_commit_proof(engine):
    s,admin,nova=seed(engine);ticket=s.submit(admin,change());save(s,admin,change())
    # Privileged synthetic corruption probe, not a service operation or approved production policy.
    with engine.begin() as c:
        c.execute(update(audit).where(audit.c.request_id=='revoke-one').values(new_state='allowed'))
    assert s.reconcile_change(admin,ticket)==a.Result(a.Outcome.UNKNOWN)


@pytest.mark.parametrize('sqlalchemy_error', (False,True))
def test_commit_rejected_before_durable_write_is_verified_not_applied(engine,monkeypatch,sqlalchemy_error):
    from sqlalchemy.exc import OperationalError
    s,admin,nova=seed(engine);ticket=s.submit(admin,change());before=rows(engine,source),rows(engine,audit)
    armed=True;original=engine.dialect.do_commit
    def before_commit(conn):
        nonlocal armed
        if armed:
            armed=False
            if sqlalchemy_error:raise OperationalError('synthetic-commit-error',{},RuntimeError('private-driver'))
            raise RuntimeError('private-runtime-commit-error')
        return original(conn)
    monkeypatch.setattr(engine.dialect,'do_commit',before_commit)
    assert s.commit(admin,ticket,confirm=True)==a.Result(a.Outcome.CONFLICT)
    assert (rows(engine,source),rows(engine,audit))==before
    assert s.read(nova).source_count==3
