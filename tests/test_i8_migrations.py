"""I8 safety gate: owned fictional SQL, real migration transactions, no runtime DB."""
from pathlib import Path
from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import event as sql_event, inspect
from family_os import db
from test_household_tasks import setup, key, cmd, t

ROOT = Path(__file__).resolve().parents[1]
OLD = 'f52b8c730ed4'
NEW = '063c9d841fe5'


def config():
    return Config(str(ROOT/'alembic.ini'))


def snapshot(engine):
    with engine.connect() as c:
        names = inspect(c).get_table_names()
        return {name: sorted([tuple(r) for r in c.exec_driver_sql('SELECT * FROM "'+name+'"')], key=repr) for name in names}


def legacy(setup):
    svc, bearers, _, _ = setup
    for index, operation in enumerate((t.Operation.REVIEW,t.Operation.DEFER,t.Operation.NEEDS_INFORMATION)):
        assert svc.apply(bearers['t1-ada'],cmd(setup,operation,request='legacy-'+str(index)),confirm=True).outcome is t.Outcome.COMMITTED


def test_i7_upgrade_preserves_every_old_value_and_constraints(setup,engine):
    legacy(setup)
    command.downgrade(config(),OLD)
    before=snapshot(engine)
    command.upgrade(config(),'head')
    after=snapshot(engine)
    for name, rows in before.items():
        if name=='alembic_version':continue
        if name=='task_domain_event':
            with engine.connect() as c:
                cols=[x['name'] for x in inspect(c).get_columns(name) if x['name']!='personal_reason']
                oldrows=sorted([tuple(r) for r in c.exec_driver_sql('SELECT '+','.join(cols)+' FROM task_domain_event')],key=repr)
                assert oldrows==rows
                assert all(r[0] is None for r in c.exec_driver_sql('SELECT personal_reason FROM task_domain_event'))
        else:assert after[name]==rows
    assert after['alembic_version']==[(NEW,)]
    command.check(config())
    command.downgrade(config(),OLD)
    assert snapshot(engine)==before
    command.upgrade(config(),'head')


@pytest.mark.parametrize('stage',['first-table','second-table','version'])
def test_failed_upgrade_rolls_back_both_tables_and_revision(setup,engine,monkeypatch,stage):
    legacy(setup);command.downgrade(config(),OLD)
    before=snapshot(engine)
    schema_before={n:inspect(engine).get_check_constraints(n) for n in ('pending_member_right','task_domain_event')}
    original=db.create_db
    reached=[]
    def create(url):
        candidate=original(url)
        @sql_event.listens_for(candidate,'after_cursor_execute')
        def fail(c,cursor,statement,parameters,context,many):
            text=statement.lower()
            sqlite=c.dialect.name=='sqlite'
            if sqlite and any(x in text for x in ('create table _alembic_tmp','drop table pending_member_right','drop table task_domain_event','alter table _alembic_tmp')):
                assert c.connection.driver_connection.in_transaction
            first=('rename to pending_member_right' in text if sqlite else 'add constraint valid_pending_disposition' in text)
            second=('rename to task_domain_event' in text if sqlite else 'add constraint valid_personal_reason' in text)
            version='update alembic_version set version_num' in text
            if {'first-table':first,'second-table':second,'version':version}[stage]:
                reached.append(True)
                raise RuntimeError('Synthetic migration interruption')
        return candidate
    monkeypatch.setattr(db,'create_db',create)
    with pytest.raises(RuntimeError,match='Synthetic migration interruption'):
        command.upgrade(config(),'head')
    assert reached
    assert snapshot(engine)==before
    assert {n:inspect(engine).get_check_constraints(n) for n in schema_before}==schema_before
    if engine.dialect.name=='sqlite':
        with engine.connect() as c:assert not c.exec_driver_sql('PRAGMA foreign_key_check').all()
    monkeypatch.setattr(db,'create_db',original)
    command.upgrade(config(),'head')
    command.check(config())


@pytest.mark.parametrize('only_resume',[False,True])
def test_new_event_blocks_downgrade_even_after_resume(setup,engine,only_resume):
    from test_i8_personal import prepared,apply,rows,event,item
    if only_resume:apply(setup,cmd(setup,t.Operation.DEFER))
    else:apply(setup,prepared(setup))
    apply(setup,prepared(setup,t.Operation.RESUME))
    assert item(setup).disposition=='active'
    before=snapshot(engine)
    with pytest.raises(RuntimeError,match='I8 history/state exists'):command.downgrade(config(),OLD)
    assert snapshot(engine)==before
    command.check(config())


def test_new_cache_without_event_also_blocks_downgrade(setup,engine):
    from sqlalchemy import update
    from family_os.schema import pending_member_right
    with engine.begin() as c:c.execute(update(pending_member_right).values(disposition='not-applicable'))
    before=snapshot(engine)
    with pytest.raises(RuntimeError,match='I8 history/state exists'):command.downgrade(config(),OLD)
    assert snapshot(engine)==before


def test_fresh_schema_and_retained_foreign_keys_unique_indexes(engine):
    assert 'personal_reason' in [x['name'] for x in inspect(engine).get_columns('task_domain_event')]
    command.check(config())
    tables=('pending_member_right','task_domain_event')
    def constraints():
        return {name:tuple(sorted(values,key=repr) for values in (inspect(engine).get_foreign_keys(name),inspect(engine).get_unique_constraints(name),inspect(engine).get_indexes(name))) for name in tables}
    before=constraints();command.downgrade(config(),OLD);assert constraints()==before
    command.upgrade(config(),'head');assert constraints()==before
    command.check(config())


@pytest.mark.parametrize('operation,reason',[
    ('not-applicable',None),('not-applicable','not-required'),('not-applicable','private free text'),
    ('resume','personal-judgment'),('review','personal-judgment'),('accept','personal-judgment')])
def test_real_database_rejects_invalid_reason_operation_pairs(setup,engine,operation,reason):
    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError
    from family_os.schema import task_domain_event
    from test_i8_personal import prepared,apply,rows,event
    if operation=='accept':
        # Use a valid real ACCEPT row: a malformed scope/duplicate insert would
        # otherwise reject independently of the private-reason CHECK.
        from test_household_tasks import accept
        from sqlalchemy import update
        accept(setup)
        before=rows(engine,event)
        with pytest.raises(IntegrityError):
            with engine.begin() as c:c.execute(update(task_domain_event).where(task_domain_event.c.id==before[0]['id']).values(personal_reason=reason))
        assert rows(engine,event)==before
        return
    apply(setup,prepared(setup))
    original=rows(engine,event)[0]
    values=dict(original,id='event_invalid',request_id='invalid-event',pending_revision=3,operation=operation,personal_reason=reason)
    with pytest.raises(IntegrityError):
        with engine.begin() as c:c.execute(insert(task_domain_event).values(**values))
    assert rows(engine,event)==(original,)
