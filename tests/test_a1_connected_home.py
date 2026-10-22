"""Home uses the two existing independently authorized I4b reads, on owned SQL only."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from sqlalchemy import update

from test_i4b_workbench import app, i2
from test_i2_local_session import login, request
from family_os.schema import (task_member_grant as task_right, pending_member_right as pending_right,
    source_read_grant as source_right, household_membership as membership)

ROOT = Path(__file__).resolve().parents[1]


def page(app, jar, resource, query='limit=12&offset=0'):
    return request(app, '/api/' + resource, cookies=jar, method='GET', body=b'',
                   CONTENT_TYPE='', HTTP_ACCEPT='application/json', QUERY_STRING=query)


def data(app, jar, resource):
    status, _, raw = page(app, jar, resource)
    assert status == '200 OK'
    return json.loads(raw)[resource]


def revoke(app, table, peer):
    with i2.a.authorization_transaction(app.lab.sessions._engine, i2.HOME) as c:
        c.execute(update(table).where(table.c.household_id == i2.HOME,
            table.c.person_id == 'i2-' + peer).values(state='revoked', revision=table.c.revision + 1))


@pytest.mark.parametrize('peer,expected', [('clara', 3), ('devon', 2)])
def test_home_inputs_are_actual_neutral_pages_completed_in_total_and_dates_explicit(app, peer, expected):
    jar = login(app, peer)
    tasks, pending = data(app, jar, 'tasks'), data(app, jar, 'pending')
    assert tasks['total'] == expected == len(tasks['items'])
    assert sum(r['status'] == 'completed' for r in tasks['items']) == 1
    assert sum(r['approved_date'] is not None for r in tasks['items']) == 1
    assert any(r['approved_date'] is None for r in tasks['items'])
    assert any(r['can_accept'] for r in pending['items']) and any(not r['can_accept'] for r in pending['items'])
    assert ('i4a-visit' in {r['id'] for r in pending['items']}) is (peer == 'devon')
    for row in tasks['items']:
        assert set(row) == {'id','step','assignee','status','approved_date','revision','can_edit'}
    for row in pending['items']:
        assert set(row) == {'id','revision','step','supported_date','can_accept'}
        assert row['id'] not in ('i4a-offer', 'i4a-notice')


@pytest.mark.parametrize('peer', ['clara', 'devon'])
@pytest.mark.parametrize('revoked,unaffected,table', [('tasks','pending',task_right), ('pending','tasks',pending_right)])
def test_current_page_revocation_is_independent_of_other_collection_and_other_peer(app, peer, revoked, unaffected, table):
    jar, other = login(app, peer), login(app, 'devon' if peer == 'clara' else 'clara')
    before, outside = data(app, jar, unaffected), data(app, other, revoked)
    revoke(app, table, peer)
    assert data(app, jar, revoked) == {'items': [], 'total': 0, 'has_more': False}
    assert data(app, jar, unaffected) == before
    assert data(app, other, revoked) == outside


@pytest.mark.parametrize('peer', ['clara', 'devon'])
def test_source_revocation_never_revokes_independently_published_task_or_exposes_origin(app, peer):
    jar = login(app, peer)
    before = data(app, jar, 'tasks')
    revoke(app, source_right, peer)
    assert data(app, jar, 'pending') == {'items': [], 'total': 0, 'has_more': False}
    assert data(app, jar, 'tasks') == before


@pytest.mark.parametrize('peer', ['clara', 'devon'])
def test_membership_revocation_blocks_both_reads_and_current_session(app, peer):
    jar = login(app, peer)
    revoke(app, membership, peer)
    for resource in ('tasks', 'pending'):
        assert page(app, jar, resource)[0] == '400 Bad Request'
    assert request(app, cookies=jar)[0] == '400 Bad Request'


@pytest.mark.parametrize('resource', ['tasks', 'pending'])
def test_one_collection_database_failure_does_not_get_replaced_by_other_collection(app, resource, monkeypatch):
    jar = login(app)
    def fail(*args, **kwargs): raise RuntimeError('synthetic failure that must not be disclosed')
    monkeypatch.setattr(app.tasks, resource, fail)
    response = page(app, jar, resource)
    assert response[0] == '400 Bad Request'
    assert b'synthetic failure' not in response[2]
    assert page(app, jar, 'pending' if resource == 'tasks' else 'tasks')[0] == '200 OK'


@pytest.mark.parametrize('resource', ['tasks', 'pending'])
@pytest.mark.parametrize('query', ['limit=21&offset=0','limit=0&offset=0','limit=12&offset=-1',
    'limit=12&offset=0&member=devon','limit=12&offset=0&household=other','limit=12&limit=12&offset=0'])
def test_home_cannot_invent_identity_or_expand_bounded_api(resource, query, app):
    assert page(app, login(app), resource, query)[0] == '400 Bad Request'


def test_browser_opt_in_precedes_any_playwright_import_or_fixture_start():
    result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/browser/a1-home.js')],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode != 0 and 'Exact synthetic opt-in required' in result.stderr


def test_actual_refresh_unit_faults_and_i3_i4a_isolation():
    result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/browser/a1-coordination.test.js')],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    import re
    assert re.search(r'pass\s+16', result.stdout)
