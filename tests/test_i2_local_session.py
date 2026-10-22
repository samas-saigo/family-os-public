"""Fictional I2 browser boundary against real disposable SQLite/PostgreSQL stores."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from http.client import HTTPConnection
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest
from sqlalchemy import select, update

from family_os import _household_authorization as auth, _household_sessions as sessions
from family_os.schema import household_session, session_audit, household_membership, external_identity_binding

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('i2_local_session', ROOT/'prototypes/i2-local-session/local_session.py')
i2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = i2
SPEC.loader.exec_module(i2)


@pytest.fixture
def lab(engine):
    value = i2.Lab(engine, synthetic_only=True)
    yield value
    value.close()


@pytest.fixture
def app(lab):
    return i2.Application(lab, 38199)


def request(app, path='/api/session', *, cookies=None, method='POST', body=b'{}', **changes):
    env = dict(REMOTE_ADDR='127.0.0.1', HTTP_HOST=app.host, REQUEST_METHOD=method,
        PATH_INFO=path, QUERY_STRING='', SCRIPT_NAME='', HTTP_ORIGIN=app.origin,
        HTTP_SEC_FETCH_SITE='same-origin', HTTP_X_SAMAS_INTENT='local-session',
        CONTENT_TYPE='application/json', CONTENT_LENGTH=str(len(body)))
    if cookies:
        env['HTTP_COOKIE'] = '; '.join(f'{k}={v}' for k,v in cookies.items())
    env.update(changes)
    env['wsgi.input'] = BytesIO(body)
    captured = []
    raw = b''.join(app(env, lambda status, headers: captured.append((status, headers))))
    status, headers = captured[0]
    return status, headers, raw


def values(headers):
    return {v.split('=',1)[0]: v.split('=',1)[1].split(';',1)[0]
        for k,v in headers if k == 'Set-Cookie' and 'Max-Age=0' not in v}


def start(app):
    status, headers, body = request(app, '/api/start')
    assert status == '200 OK'
    return json.loads(body)['request_id'], values(headers)


def login(app, peer='clara'):
    ticket, jar = start(app)
    app.lab.approve(ticket, peer)
    status, headers, body = request(app, cookies=jar)
    assert status == '200 OK' and json.loads(body) == {'state':'active', 'member':'i2-'+peer}
    return values(headers)


def test_two_peer_sessions_independent_no_plaintext_or_authority_in_json(app, engine):
    clara, devon = login(app), login(app, 'devon')
    assert clara != devon
    for peer, jar in [('clara',clara),('devon',devon)]:
        status, headers, body = request(app, cookies=jar)
        assert json.loads(body) == {'state':'active', 'member':'i2-'+peer}
        assert jar[i2.COOKIE].encode() not in body
        assert dict(headers)['Cache-Control'].startswith('no-store')
    with engine.connect() as c:
        rows = c.execute(select(household_session)).mappings().all()
        ledger = c.execute(select(session_audit)).mappings().all()
    assert len(rows) == len(ledger) == 2
    assert {r['secret_hash'] for r in rows} == {sha256(j[i2.COOKIE].encode()).hexdigest() for j in (clara,devon)}
    assert all(j[i2.COOKIE] not in str(rows)+str(ledger) for j in (clara,devon))
    request(app, '/api/logout', cookies=clara)
    assert request(app, cookies=clara)[0] == '400 Bad Request'
    assert request(app, cookies=devon)[0] == '200 OK'


def test_pairing_is_terminal_only_exact_browser_one_delivery(app):
    ticket, jar = start(app)
    assert request(app, cookies=jar)[2] == json.dumps({'request_id':ticket,'state':'waiting'}, sort_keys=True).encode()
    assert request(app, cookies={i2.PAIR:i2.token_urlsafe(32)})[0] == '400 Bad Request'
    app.lab.approve(ticket, 'clara')
    for peer in ('clara','devon'):
        with pytest.raises(i2.Unavailable):
            app.lab.approve(ticket, peer)
    assert request(app, cookies=jar)[0] == '200 OK'
    assert request(app, cookies=jar)[0] == '400 Bad Request'


@pytest.mark.parametrize('change', [
    {'REMOTE_ADDR':'10.0.0.2'}, {'REMOTE_ADDR':'::1'},
    {'HTTP_HOST':'evil.example'}, {'HTTP_HOST':'localhost:38199'},
    {'HTTP_HOST':'127.0.0.1:38199.evil.example'}, {'HTTP_HOST':'127.0.0.1:38199,evil.example'},
    {'HTTP_ORIGIN':'http://evil.example'}, {'HTTP_ORIGIN':'null'}, {'HTTP_ORIGIN':None},
    {'HTTP_ORIGIN':'http://127.0.0.1:38200'}, {'HTTP_SEC_FETCH_SITE':'cross-site'},
    {'HTTP_SEC_FETCH_SITE':'same-site'}, {'HTTP_SEC_FETCH_SITE':None},
    {'HTTP_X_SAMAS_INTENT':None}, {'HTTP_X_FORWARDED_HOST':'evil.example'},
    {'HTTP_FORWARDED':'for=127.0.0.1'}, {'HTTP_AUTHORIZATION':'Bearer arbitrary'},
    {'QUERY_STRING':'member=devon'}, {'SCRIPT_NAME':'/mounted'},
    {'CONTENT_TYPE':'text/plain'}, {'CONTENT_LENGTH':'02'}, {'HTTP_TRANSFER_ENCODING':'chunked'},
    {'HTTP_CONTENT_ENCODING':'gzip'},
])
def test_csrf_rebinding_and_client_authority_rejected_before_issuance(app, change):
    assert request(app, '/api/start', **change)[0] == '400 Bad Request'
    assert app.lab.starts == 0


@pytest.mark.parametrize('path,method,body', [
    ('/api/start','GET',b''), ('/api/start','POST',b'{"member":"devon"}'),
    ('/api/start','POST',b'[]'), ('/api/start','POST',b'{} '),
    ('/api/approve','POST',b'{}'), ('/api/tasks','POST',b'{}'),
    ('/v0/workbench','GET',b''), ('/api/session','OPTIONS',b''),
    ('/../README.md','GET',b''), ('/.git/config','GET',b''),
    ('/local_session.py','GET',b''), ('/fixtures.js','GET',b''),
])
def test_only_whitelisted_resources_and_no_task_or_mutation_routes(app, path, method, body):
    status, headers, raw = request(app, path, method=method, body=body)
    assert status == '400 Bad Request' and raw == b'{"error":"local_session_unavailable"}'
    assert not any(k.lower().startswith('access-control') for k,v in headers)


@pytest.mark.parametrize('table', [household_membership, external_identity_binding, household_session])
def test_current_persistent_revocation_wins_over_cookie(app, engine, table):
    jar = login(app)
    with auth.authorization_transaction(engine, i2.HOME) as c:
        q = update(table).where(table.c.household_id == i2.HOME, table.c.person_id == 'i2-clara')
        c.execute(q.values(revision=table.c.revision+1, **({'revoked':True} if table is household_session else {'state':'revoked'})))
    assert request(app, cookies=jar)[0] == '400 Bad Request'


def test_adapter_expiration_and_monotonic_rollback(app):
    jar = login(app)
    now = app.lab.last
    app.lab.clock = lambda: now + i2.SESSION_SECONDS
    assert request(app, cookies=jar)[0] == '400 Bad Request'
    app.lab.clock = lambda: now-1
    assert request(app, '/api/start')[0] == '400 Bad Request'


@pytest.mark.parametrize('field', ['absolute_expiry','idle_expiry'])
def test_database_expiration_is_enforced(app, engine, field):
    jar = login(app)
    with engine.connect() as c:
        row = c.execute(select(household_session)).mappings().one()
    app.lab.sessions._clock = lambda: row[field]
    assert request(app, cookies=jar)[0] == '400 Bad Request'


def test_cancel_and_expired_pairing_never_establish_session(app, engine):
    ticket, jar = start(app)
    assert json.loads(request(app, '/api/cancel', cookies=jar)[2]) == {'state':'cancelled'}
    with pytest.raises(i2.Unavailable): app.lab.approve(ticket, 'clara')
    ticket, jar = start(app)
    now = app.lab.last
    app.lab.clock = lambda: now+i2.PAIR_SECONDS
    with pytest.raises(i2.Unavailable): app.lab.approve(ticket, 'clara')
    assert request(app, cookies=jar)[0] == '400 Bad Request'
    with engine.connect() as c: assert c.execute(select(household_session)).all() == []


def test_cancel_after_terminal_approval_does_not_deliver_or_retain_local_authority(app):
    ticket, jar = start(app)
    app.lab.approve(ticket, 'clara')
    assert app.lab.leases
    assert request(app, '/api/cancel', cookies=jar)[0] == '200 OK'
    assert app.lab.leases == {} and app.lab.pairs == {}
    assert request(app, cookies=jar)[0] == '400 Bad Request'


def test_concurrent_approval_issues_exactly_once(app, engine):
    ticket, jar = start(app)
    def approve(peer):
        try: app.lab.approve(ticket, peer); return 'approved'
        except i2.Unavailable: return 'denied'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(approve, i2.PEERS)) == ['approved','denied']
    with engine.connect() as c: assert len(c.execute(select(household_session)).all()) == 1


def test_unknown_issuance_consumes_attempt_no_cookie_no_retry(app, monkeypatch):
    ticket, jar = start(app)
    monkeypatch.setattr(app.lab.sessions, 'establish', lambda *a,**k: sessions.Result(sessions.Outcome.UNKNOWN))
    with pytest.raises(i2.Unavailable): app.lab.approve(ticket, 'clara')
    with pytest.raises(i2.Unavailable): app.lab.approve(ticket, 'clara')
    assert request(app, cookies=jar)[0] == '400 Bad Request'


def test_unknown_logout_is_not_success_and_disables_local_reuse(app, monkeypatch):
    jar = login(app)
    monkeypatch.setattr(app.lab.sessions, 'logout', lambda *a,**k: sessions.Result(sessions.Outcome.UNKNOWN))
    status, headers, raw = request(app, '/api/logout', cookies=jar)
    assert status == '200 OK' and json.loads(raw) == {'state':'unknown'}
    assert request(app, cookies=jar)[0] == '400 Bad Request'


def test_committed_logout_ack_loss_remains_unknown_without_replay(app, engine, monkeypatch):
    jar = login(app)
    original_logout = app.lab.sessions.logout
    original_commit = engine.dialect.do_commit
    armed = False
    def commit(connection):
        nonlocal armed
        original_commit(connection)
        if armed:
            armed = False
            raise RuntimeError('synthetic-ack-loss')
    def logout(*args, **kwargs):
        nonlocal armed
        armed = True
        return original_logout(*args, **kwargs)
    monkeypatch.setattr(engine.dialect, 'do_commit', commit)
    monkeypatch.setattr(app.lab.sessions, 'logout', logout)
    assert json.loads(request(app, '/api/logout', cookies=jar)[2]) == {'state':'unknown'}
    assert request(app, cookies=jar)[0] == '400 Bad Request'
    with engine.connect() as c:
        assert c.execute(select(household_session.c.revoked)).scalar_one()
        assert len(c.execute(select(session_audit).where(session_audit.c.event=='logout')).all()) == 1


def test_committed_issuance_ack_loss_never_delivers_or_reissues_secret(app, engine, monkeypatch):
    ticket, jar = start(app)
    original_commit = engine.dialect.do_commit
    armed = True
    def commit(connection):
        nonlocal armed
        original_commit(connection)
        if armed:
            armed = False
            raise RuntimeError('synthetic-ack-loss')
    monkeypatch.setattr(engine.dialect, 'do_commit', commit)
    with pytest.raises(i2.Unavailable): app.lab.approve(ticket, 'clara')
    with pytest.raises(i2.Unavailable): app.lab.approve(ticket, 'clara')
    assert request(app, cookies=jar)[0] == '400 Bad Request'
    with engine.connect() as c:
        assert len(c.execute(select(household_session)).all()) == 1
        assert len(c.execute(select(session_audit)).all()) == 1


def test_failure_never_leaks_driver_or_returns_old_active_body(app, monkeypatch, caplog):
    jar = login(app)
    def fail(*a,**k): raise RuntimeError('synthetic-driver-private-detail '+jar[i2.COOKIE])
    monkeypatch.setattr(app.lab.sessions, 'resolve', fail)
    status, headers, raw = request(app, cookies=jar)
    assert status == '400 Bad Request' and b'member' not in raw
    assert jar[i2.COOKIE] not in raw.decode()+caplog.text
    assert 'synthetic-driver' not in raw.decode()+caplog.text


def test_cookie_and_csp_properties_no_offline_changes(app):
    ticket, jar = start(app)
    app.lab.approve(ticket, 'clara')
    _, headers, _ = request(app, cookies=jar)
    for k,value in headers:
        if k == 'Set-Cookie':
            assert all(flag in value for flag in ('Secure','HttpOnly','SameSite=Strict','Path=/'))
            assert 'Domain=' not in value
    status, headers, raw = request(app, '/', method='GET', body=b'', HTTP_ORIGIN=None, HTTP_SEC_FETCH_SITE='none')
    assert status == '200 OK' and dict(headers)['Content-Security-Policy'] == i2.CSP
    assert "connect-src 'none'" in (ROOT/'prototypes/h0-workbench/index.html').read_text()


def test_start_bounds_cannot_allocate_forever(app):
    for _ in range(i2.MAX_STARTS): start(app)
    assert request(app, '/api/start')[0] == '400 Bad Request'
    assert len(app.lab.pairs) == i2.MAX_STARTS


def test_bad_cookie_and_member_query_cannot_impersonate_peer(app):
    jar = login(app)
    assert request(app, cookies=jar, QUERY_STRING='member=devon')[0] == '400 Bad Request'
    assert request(app, cookies={i2.COOKIE:'devon'})[0] == '400 Bad Request'
    assert request(app, cookies=jar)[2] == b'{"member": "i2-clara", "state": "active"}'
    raw = f'{i2.COOKIE}={jar[i2.COOKIE]}; {i2.COOKIE}={i2.token_urlsafe(32)}'
    assert request(app, HTTP_COOKIE=raw)[0] == '400 Bad Request'


def test_owned_temporary_store_ignores_runtime_database_and_cleans_up(monkeypatch, tmp_path):
    forbidden = tmp_path/'must-not-exist.sqlite3'
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///'+str(forbidden))
    with i2.disposable(synthetic_only=True) as lab:
        path = Path(lab.sessions._engine.url.database)
        assert path.exists() and path != forbidden
    assert not path.exists() and not forbidden.exists() and lab.stopped


@pytest.mark.parametrize('flag', [False,1,'true',None])
def test_no_initialization_without_exact_opt_in(engine, flag):
    with pytest.raises(i2.Unavailable): i2.Lab(engine, synthetic_only=flag)
    with pytest.raises(i2.Unavailable):
        with i2.disposable(synthetic_only=flag): pytest.fail('initialized')


@pytest.mark.parametrize('args', [[], ['--synthetic'], ['--synthetic-only=true']])
def test_cli_missing_or_nonexact_flag_does_not_start_or_initialize(args):
    result = subprocess.run([sys.executable, str(i2.HERE/'local_session.py'), *args], capture_output=True, timeout=10)
    assert result.returncode != 0 and b'--synthetic-only' in result.stderr


def test_implementation_is_not_a_provider_task_or_network_client():
    import ast
    tree = ast.parse((i2.HERE/'local_session.py').read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imports <= {'argparse','contextlib','dataclasses','hashlib','json','logging','pathlib',
        'queue','re','secrets','tempfile','threading','time','alembic.config',
        'alembic.runtime.environment','alembic.script','cryptography.hazmat.primitives.asymmetric',
        'cryptography.hazmat.primitives.serialization','jwt','sqlalchemy','family_os',
        'family_os.db','family_os.registry','family_os.schema','waitress'}
    code = (i2.HERE/'local_session.py').read_text()
    for forbidden in ('harness_context(', '_household_tasks', 'getenv(', 'environ[', 'http.server'):
        assert forbidden not in code
    js = (i2.HERE/'app.js').read_text()
    for forbidden in ('document.cookie','localStorage','sessionStorage','Authorization','fixtures.js','model.js'):
        assert forbidden not in js


def test_live_waitress_loopback_host_origin_parser_and_bounded_routes(lab):
    server, app, thread = i2.serve(lab)
    try:
        assert server.socket.getsockname()[0] == '127.0.0.1'
        def call(path, headers=None):
            conn = HTTPConnection('127.0.0.1', server.effective_port, timeout=5)
            try:
                conn.request('POST', path, '{}', headers=headers or {})
                r = conn.getresponse(); return r.status, r.read(), r.getheaders()
            finally: conn.close()
        good = {'Origin':app.origin,'Sec-Fetch-Site':'same-origin',
            'X-Samas-Intent':'local-session','Content-Type':'application/json'}
        assert call('/api/start',good)[0] == 200
        for bad in ({}, dict(good, Host='rebind.example'), dict(good, Origin='http://evil.example')):
            assert call('/api/start',bad)[0] == 400
        assert call('/.git/config',good)[0] == 400
        assert call('/api/tasks',good)[0] == 400
        assert call('/api/start',dict(good, Origin='null'))[0] == 400
    finally:
        i2.stop(server, lab, thread)
        assert not thread.is_alive()


def test_static_asset_startup_failure_occurs_before_listener_creation(lab, monkeypatch, tmp_path):
    import waitress
    monkeypatch.setattr(i2, 'HERE', tmp_path)
    monkeypatch.setattr(waitress, 'create_server', lambda *a,**k: pytest.fail('listener created before asset validation'))
    with pytest.raises(FileNotFoundError):
        i2.serve(lab)


def test_no_outbound_network_in_fixture_issuance_or_resolution(app, monkeypatch):
    def denied(*a,**k): pytest.fail('outbound network forbidden')
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    jar = login(app)
    assert request(app, cookies=jar)[0] == '200 OK'
    assert request(app, '/api/logout', cookies=jar)[0] == '200 OK'
