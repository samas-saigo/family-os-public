"""I1 readiness probes, not a browser API or alternate authorization engine.

Reuse only the approved T1 fictional provisioning in disposable test stores.
Every projection comes from the unchanged TaskService and durable sessions.
"""
from dataclasses import asdict

import pytest
from sqlalchemy import event as sql_event, update

from test_household_tasks import setup, key, accept, revoke, HOME
from family_os import _household_tasks as t
from family_os.schema import (task_member_grant as grant, source_read_grant as source,
    household_membership as member, external_identity_binding as identity,
    household_session as sessions, household_pending_item as pending)


def test_i1_empty_is_an_authorized_result_not_an_authentication_fallback(setup):
    svc, bearers, _, _ = setup
    assert svc.tasks(bearers['t1-ada']) == t.Page((), 0, False)
    with pytest.raises(t.TaskError, match='^Household domain unavailable$'):
        svc.tasks('t1-ada')  # A frontend member value cannot select an identity.


def test_i1_two_sessions_share_one_authoritative_task_and_server_page(setup):
    svc, bearers, _, _ = setup
    tid = accept(setup)
    ada = svc.tasks(bearers['t1-ada'], limit=1)
    assert ada == svc.tasks(bearers['t1-bo'], limit=1)
    assert ada.total == 1 and not ada.has_more and ada.items[0].id == tid
    assert svc.tasks(bearers['t1-ada'], limit=1, offset=1) == t.Page((), 1, False)
    assert set(asdict(ada.items[0])) == {
        'id', 'step', 'assignee', 'status', 'approved_date', 'revision',
        'rights_revision', 'can_edit', 'can_history'}


def test_i1_private_origin_never_selected_and_source_revocation_preserves_task(setup, engine):
    svc, bearers, _, _ = setup
    accept(setup, id='t1-private')
    before = svc.tasks(bearers['t1-ada'])
    revoke(engine, source, who='t1-bo', source_account_id='t1-private-source')
    statements = []
    def capture(c, cursor, statement, params, context, many):
        statements.append(statement.lower())
    sql_event.listen(engine, 'before_cursor_execute', capture)
    try:
        assert svc.tasks(bearers['t1-ada']) == before
        assert svc.tasks(bearers['t1-bo']) == before
    finally:
        sql_event.remove(engine, 'before_cursor_execute', capture)
    assert not any('household_pending_item' in sql for sql in statements)
    assert not any('raw_source_record' in sql for sql in statements)


def test_i1_task_revocation_removes_server_count_page_and_history_independently(setup, engine):
    svc, bearers, _, _ = setup
    tid = accept(setup)
    revoke(engine, grant, task_id=tid)
    assert svc.tasks(bearers['t1-ada']) == t.Page((), 0, False)
    assert svc.tasks(bearers['t1-bo']).total == 1
    with pytest.raises(t.TaskError):
        svc.history(bearers['t1-ada'], tid, tasks=True)


@pytest.mark.parametrize('table', [member, identity, sessions])
def test_i1_prepared_read_parameters_do_not_lease_authorization(setup, engine, table):
    svc, bearers, _, _ = setup
    accept(setup)
    request = dict(limit=1, offset=0)
    assert svc.tasks(bearers['t1-ada'], **request).total == 1
    revoke(engine, table)
    with pytest.raises(t.TaskError):
        svc.tasks(bearers['t1-ada'], **request)
    assert svc.tasks(bearers['t1-bo'], **request).total == 1


@pytest.mark.parametrize('who', ['t1-cy', 'not-a-session'])
def test_i1_foreign_or_forged_identity_cannot_select_household(setup, who):
    svc, bearers, _, _ = setup
    accept(setup)
    with pytest.raises(t.TaskError):
        svc.tasks(bearers.get(who, who))


def test_i1_backend_failure_returns_no_fake_or_previously_authorized_page(setup, monkeypatch):
    svc, bearers, _, _ = setup
    accept(setup)
    assert svc.tasks(bearers['t1-ada']).total == 1
    def unavailable(*args, **kwargs):
        raise RuntimeError('synthetic-driver-detail-must-not-escape')
    monkeypatch.setattr(svc, '_transaction', unavailable)
    with pytest.raises(t.TaskError, match='^Household domain unavailable$') as error:
        svc.tasks(bearers['t1-ada'])
    assert 'synthetic-driver' not in str(error.value)


def test_i1_hidden_pending_changes_do_not_influence_task_search_or_counts(setup, engine):
    svc, bearers, _, _ = setup
    accept(setup)
    before = svc.tasks(bearers['t1-ada'], step=t.Step.SCHOOL)
    with engine.begin() as c:
        c.execute(update(pending).where(pending.c.household_id == HOME).values(
            safety='high-risk', generation=2))
    assert svc.tasks(bearers['t1-ada'], step=t.Step.SCHOOL) == before


@pytest.mark.parametrize('query', [{'limit': 0}, {'limit': 21}, {'offset': -1},
    {'step': 'school-session'}])
def test_i1_read_contract_rejects_unbounded_or_untyped_queries(setup, query):
    svc, bearers, _, _ = setup
    with pytest.raises(t.TaskError):
        svc.tasks(bearers['t1-ada'], **query)
