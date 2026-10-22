"""G3b ASGI request/response probes; new Larch fiction, disposable SQL only."""
import asyncio
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
from threading import Event
from time import time

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import jwt
import pytest
from sqlalchemy import insert, select, update

from family_os import _fictional_read_api as api, _household_sessions as s
from family_os import _household_authorization as a, _verified_identity as v
from family_os.schema import (household, person, source_account,
    household_membership as member, external_identity_binding as binding,
    source_read_grant as grant, publication_scope as publication_scope,
    publication_read_grant as publication, household_session as sessions,
    authorization_audit, session_audit)

ROOT = Path(__file__).parents[1]
HOME = 'larch'
ISSUER = 'https://larch-id.example.invalid'


@pytest.fixture(scope='module')
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def setup(engine, key):
    clock = [int(time())]
    verifier = v.OfflineIdentityVerifier(issuer=ISSUER, audience='larch-client',
        public_keys={'larch-key': key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)})
    with engine.begin() as c:
        c.execute(insert(household), [dict(id=HOME, name='Fictional Larch'), dict(id='azalea', name='Fictional Azalea')])
        c.execute(insert(person), [dict(id=p, household_id=h, display_name='Fictional '+p, metadata={})
            for p, h in [('tess', HOME), ('vale', HOME), ('sol', 'azalea')]])
        c.execute(insert(member), [dict(household_id=h, person_id=p, state='allowed', revision=1)
            for p, h in [('tess', HOME), ('vale', HOME), ('sol', 'azalea')]])
        c.execute(insert(binding), [dict(issuer=ISSUER, subject=p, household_id=h, person_id=p, state='allowed', revision=1)
            for p, h in [('tess', HOME), ('vale', HOME), ('sol', 'azalea')]])
        c.execute(insert(source_account), [dict(id=src, household_id=h, provider='fixture', owner_type='person',
            owner_id=owner, person_owner_id=owner, external_account=None, enabled=True, metadata={'private': 'never-return-account-data'})
            for src, h, owner in [('larch-one', HOME, 'tess'), ('larch-two', HOME, 'vale'),
                                  ('larch-private', HOME, 'tess'), ('azalea-one', 'azalea', 'sol')]])
        c.execute(insert(grant), [dict(household_id=HOME, source_account_id=src, person_id=p,
            state='allowed', observations=True, security=True, revision=1, membership_revision=1)
            for src, p in [('larch-one', 'tess'), ('larch-one', 'vale'), ('larch-two', 'tess'),
                           ('larch-two', 'vale'), ('larch-private', 'tess')]])
        c.execute(insert(publication_scope).values(household_id=HOME, publication_key=a.Publication.BOOKING.value, approved=True))
        c.execute(insert(publication), [dict(household_id=HOME, publication_key=a.Publication.BOOKING.value,
            person_id=p, state='allowed', revision=1, membership_revision=1) for p in ('tess', 'vale')])
    observation = a.FixtureObservation('larch-one', a.Object.BOOKING, 1, a.Topic.BOOKING, a.Safety.HIGH_RISK)
    repository = a.FixtureRepository((observation, observation,
        replace(observation, source_id='larch-two', object=a.Object.SCHOOL, topic=a.Topic.SCHOOL),
        replace(observation, source_id='larch-private'), replace(observation, source_id='azalea-one')),
        (a.FixturePublication(a.Publication.BOOKING, a.Step.BOOKING),))
    service = s.SessionService(engine, verifier, repository, synthetic_only=True, clock=lambda: clock[0])
    def issue(p):
        challenge = verifier.challenge(); now = int(time())
        token = jwt.encode(dict(iss=ISSUER, sub=p, aud='larch-client', iat=now-1, nbf=now-1,
            exp=now+120, nonce=challenge.nonce, roles=['owner']), key, algorithm='RS256', headers={'kid': 'larch-key'})
        proof = verifier.verify(token, challenge)
        result = service.establish(proof, 'azalea' if p == 'sol' else HOME, request_id='start-'+p)
        assert result.outcome is s.Outcome.COMMITTED
        return result.bearer, token
    tess, token = issue('tess'); vale, _ = issue('vale'); sol, _ = issue('sol')
    return api.FictionalReadAPI(service, HOME, synthetic_only=True), service, tess, vale, sol, token, clock


async def exchange(app, bearer=None, *, query=b'', path='/v0/workbench', method='GET',
                   headers=None, body=b'', more=False, scope_changes=None):
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'method': method,
        'path': path, 'raw_path': path.encode(), 'root_path': '', 'query_string': query,
        'headers': headers if headers is not None else [(b'authorization', b'Bearer '+(bearer or '').encode())]}
    scope.update(scope_changes or {})
    sent = []
    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': more}
    async def send(event):
        sent.append(event)
    await app(scope, receive, send)
    assert len(sent) == 2 and sent[0]['type'] == 'http.response.start'
    assert sent[1]['type'] == 'http.response.body' and sent[1]['more_body'] is False
    return sent[0]['status'], json.loads(sent[1]['body']), dict(sent[0]['headers'])


def request(*args, **kwargs):
    return asyncio.run(exchange(*args, **kwargs))


def deny(result):
    assert result[0:2] == (400, {'error': 'request_unavailable'})


def revoke(engine, kind, principal='tess'):
    table = {'session': sessions, 'membership': member, 'binding': binding,
             'source': grant, 'publication': publication}[kind]
    with a.authorization_transaction(engine, HOME) as c:
        values = {'revision': table.c.revision+1}
        values['revoked' if kind == 'session' else 'state'] = True if kind == 'session' else 'revoked'
        c.execute(update(table).where(table.c.household_id == HOME, table.c.person_id == principal).values(**values))


def test_explicit_json_schema_counts_and_minimization(setup):
    app, _, tess, vale, *_ = setup
    status, view, headers = request(app, tess)
    assert status == 200 and view['schema'] == api.CONTRACT_VERSION and view['synthetic_only'] is True
    assert set(view) == {'schema', 'synthetic_only', 'pagination', 'observations', 'security', 'published_steps'}
    assert view['observations']['total'] == view['security']['total'] == 3
    assert view['published_steps'] == {'items': [{'publication_id': 'fictional-booking', 'step': 'inspect-fictional-booking'}], 'total': 1, 'has_more': False}
    assert all(set(row) == {'source_id', 'provider', 'object_id', 'generation', 'topic'} for row in view['observations']['items'])
    assert all(set(row) == {'source_id', 'provider', 'object_id', 'generation', 'topic', 'safety'} for row in view['security']['items'])
    peer = request(app, vale)[1]
    assert peer['observations']['total'] == 2
    assert 'larch-private' not in json.dumps(peer)
    assert headers[b'cache-control'] == b'no-store, no-cache, max-age=0'
    assert headers[b'pragma'] == b'no-cache' and headers[b'expires'] == b'0'
    assert b'set-cookie' not in headers and b'etag' not in headers


def test_equal_grants_equal_shared_state_and_no_actor_multipliers(setup, engine):
    app, _, tess, vale, *_ = setup
    with engine.begin() as c:
        c.execute(update(grant).where(grant.c.source_account_id == 'larch-private').values(state='revoked', revision=2))
    assert request(app, tess)[1] == request(app, vale)[1]
    assert request(app, tess)[1]['observations']['total'] == 2


@pytest.mark.parametrize('bearer', ['', 'tess', 'tess@fictional.invalid', 'x'*42, 'x'*44, '!'*43, 'x'*43])
def test_missing_malformed_or_forged_bearer(setup, bearer):
    deny(request(setup[0], bearer))


@pytest.mark.parametrize('which', ['id-token', 'wrong-household', 'hash', 'person', 'harness'])
def test_identity_substitution_is_not_session_authority(setup, engine, which):
    app, _, _, _, sol, token, _ = setup
    with engine.connect() as c:
        hashed = c.execute(select(sessions.c.secret_hash)).scalars().first()
    bearer = {'id-token': token, 'wrong-household': sol, 'hash': hashed,
              'person': 'vale', 'harness': 'harness_context'}[which]
    deny(request(app, bearer))


@pytest.mark.parametrize('kind', ['session', 'membership', 'binding'])
def test_current_revocation_denies_and_preserves_peer_session(setup, engine, kind):
    app, _, tess, vale, *_ = setup
    revoke(engine, kind)
    deny(request(app, tess))
    assert request(app, vale)[0] == 200


@pytest.mark.parametrize('expiry', ['idle', 'absolute'])
def test_expiry(setup, expiry):
    app, _, tess, *_, clock = setup
    clock[0] += s.IDLE_SECONDS if expiry == 'idle' else s.ABSOLUTE_SECONDS
    deny(request(app, tess))


def test_rotation_and_logout_have_no_routes_old_bearer_invalid(setup):
    app, service, tess, vale, *_ = setup
    revision = service.resolve(tess, HOME).revision
    rotated = service.rotate(tess, HOME, request_id='replace', expected_revision=revision)
    assert rotated.outcome is s.Outcome.COMMITTED
    deny(request(app, tess))
    assert request(app, rotated.bearer)[0] == 200
    assert request(app, vale)[0] == 200
    revision = service.resolve(rotated.bearer, HOME).revision
    assert service.logout(rotated.bearer, HOME, request_id='bye', expected_revision=revision).outcome is s.Outcome.COMMITTED
    deny(request(app, rotated.bearer))


def test_source_and_publication_visibility_independent(setup, engine):
    app, _, tess, *_ = setup
    revoke(engine, 'source')
    view = request(app, tess)[1]
    assert view['observations']['items'] == view['security']['items'] == []
    assert view['observations']['total'] == view['security']['total'] == 0
    assert view['published_steps']['total'] == 1
    assert 'source_id' not in json.dumps(view['published_steps'])
    revoke(engine, 'publication')
    assert request(app, tess)[1]['published_steps']['total'] == 0


@pytest.mark.parametrize('query', [b'limit=1', b'limit=1&offset=1', b'offset=128', b'topic=fictional-school'])
def test_authorized_pagination_and_fixed_topic_search(setup, query):
    app, _, _, vale, *_ = setup
    _, view, _ = request(app, vale, query=query)
    expected = 1 if b'topic' in query else 2
    assert view['observations']['total'] == expected
    assert view['published_steps']['total'] == 1
    if query == b'limit=1':
        assert view['observations']['has_more'] is True
        assert view['observations']['items'][0]['source_id'] == 'larch-one'
    if query == b'offset=128':
        assert view['observations']['items'] == [] and not view['observations']['has_more']


@pytest.mark.parametrize('query', [b'limit=0', b'limit=21', b'limit=-1', b'limit=01', b'limit=1.0', b'offset=129',
    b'offset=-1', b'offset=000', b'limit=', b'limit', b'limit=1&limit=2', b'offset=0&offset=1',
    b'topic=fictional-school&topic=fictional-school', b'person=vale', b'household=azalea', b'roles=owner',
    b'topic=private', b'topic=%66ictional-school', b'limit=1;offset=0', b'&limit=1', b'limit=1&', b'x'*129,
    b'limit=1&offset=0&topic=fictional-school&extra=x', b'\xff'])
def test_invalid_query_bounds_duplicates_and_identity_selection(setup, query):
    deny(request(setup[0], setup[2], query=query))


@pytest.mark.parametrize('headers', [[], [(b'authorization', b'Bearer '+b'x'*43)]*2,
    [(b'Authorization', b'Bearer '+b'x'*43)], [(b'authorization', b'bearer '+b'x'*43)],
    [(b'authorization', b'Bearer '+b'x'*43+b' ')], [(b'authorization', b'Bearer '+b'x'*43+b'\r\n')],
    [(b'cookie', b'session=x')], [(b'authorization', b'x'*257)], [(b'authorization', 'not-bytes')]])
def test_invalid_auth_header_shapes(setup, headers):
    deny(request(setup[0], headers=headers))


@pytest.mark.parametrize('name,value', [(b'content-length', b'1'), (b'content-length', b'00'),
    (b'transfer-encoding', b'chunked'), (b'accept', b'text/html'), (b'origin', b'https://other.invalid'),
    (b'x-person', b'vale'), (b'x-household', b'azalea'), (b'host', b'evil.invalid')])
def test_unsupported_headers(setup, name, value):
    app, _, tess, *_ = setup
    deny(request(app, headers=[(b'authorization', b'Bearer '+tess.encode()), (name, value)]))


@pytest.mark.parametrize('method', ['POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
def test_unsupported_methods(setup, method):
    deny(request(setup[0], setup[2], method=method))


@pytest.mark.parametrize('path', ['/v1/workbench', '/v0/workbench/', '/v0/manage', '/v0/login', '/v0/logout',
    '/v0/grants', '/v0/enroll', '/v0/quarantine', '/v0/restore', '/v0/tasks', '/_household_authorization', '/'])
def test_no_management_or_operation_routes(setup, path):
    deny(request(setup[0], setup[2], path=path))


@pytest.mark.parametrize('body,more', [(b'x', False), (b'{"person":"vale"}', False), (b'', True)])
def test_body_bearing_requests_reject_before_read(setup, monkeypatch, body, more):
    monkeypatch.setattr(setup[1], 'read', lambda *args, **kwargs: pytest.fail('body must reject before DB'))
    deny(request(setup[0], setup[2], body=body, more=more))


def test_request_disconnect_timeout_and_raw_path_alias(setup):
    app, _, tess, *_ = setup
    deny(request(app, tess, scope_changes={'raw_path': b'/v0/%77orkbench'}))
    deny(request(app, tess, scope_changes={'root_path': '/mounted'}))
    async def run():
        sent = []
        async def receive(): return {'type': 'http.disconnect'}
        async def send(value): sent.append(value)
        scope = {'type': 'http', 'path': '/v0/workbench', 'method': 'GET',
                 'headers': [(b'authorization', b'Bearer '+tess.encode())]}
        await app(scope, receive, send)
        assert sent[0]['status'] == 400
    asyncio.run(run())


def test_hidden_conflicting_overlimit_population_cannot_change_response(setup, engine):
    app, svc, _, vale, *_rest = setup
    before = request(app, vale, query=b'limit=1')[1]
    repo = svc._repository; first = repo.observations[0]
    altered = a.FixtureRepository(repo.observations + tuple(replace(first, source_id=src, generation=i+2)
        for src in ('larch-private', 'azalea-one') for i in range(140)), repo.publications)
    other = api.FictionalReadAPI(s.SessionService(engine, svc._verifier, altered,
        synthetic_only=True, clock=svc._clock), HOME, synthetic_only=True)
    assert request(other, vale, query=b'limit=1')[1] == before


def test_observation_only_safety_changes_no_error_but_security_conflict_rejects(setup, engine):
    app, svc, tess, *_ = setup
    with engine.begin() as c:
        c.execute(update(grant).where(grant.c.person_id == 'tess').values(security=False))
    before = request(app, tess)[1]
    repo = svc._repository; first = repo.observations[0]
    changed = a.FixtureRepository(repo.observations+(replace(first, safety=a.Safety.CLEAR),), repo.publications)
    other = api.FictionalReadAPI(s.SessionService(engine, svc._verifier, changed, synthetic_only=True, clock=svc._clock), HOME, synthetic_only=True)
    assert request(other, tess)[1] == before
    with engine.begin() as c:
        c.execute(update(grant).where(grant.c.person_id == 'tess').values(security=True))
    deny(request(other, tess))


@pytest.mark.parametrize('kind', ['session', 'membership', 'binding', 'source', 'publication'])
def test_real_committed_revocation_between_preparation_and_dispatch(setup, engine, monkeypatch, kind):
    app, svc, tess, *_ = setup
    assert request(app, tess)[0] == 200
    prepared, proceed = Event(), Event()
    original = app._dispatch
    async def paused(specification, send):
        assert not any(hasattr(specification, n) for n in ('projection', 'rows', 'rights', 'session_id'))
        assert tess not in repr(specification)
        prepared.set()
        assert proceed.wait(10)  # This test's event loop runs in a dedicated thread.
        await original(specification, send)
    monkeypatch.setattr(app, '_dispatch', paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(request, app, tess)
        assert prepared.wait(10)
        # Separate thread/connection, same authoritative engine and actual SQL commit.
        pool.submit(revoke, engine, kind).result(timeout=10)
        proceed.set()
        result = future.result(timeout=10)
    if kind in ('session', 'membership', 'binding'):
        deny(result)
    elif kind == 'source':
        assert result[1]['observations']['total'] == result[1]['security']['total'] == 0
        assert result[1]['published_steps']['total'] == 1
    else:
        assert result[1]['published_steps']['total'] == 0
        assert result[1]['observations']['total'] == 3
    monkeypatch.setattr(app, '_dispatch', original)
    assert request(app, tess)[0:2] == result[0:2]


@pytest.mark.parametrize('error', [RuntimeError, ValueError])
def test_database_or_session_failure_no_partial_projection_or_secret_leak(setup, monkeypatch, caplog, error):
    app, svc, tess, *rest = setup
    def fail(*args, **kwargs):
        raise error(tess+' private SQL password ID-token URL')
    monkeypatch.setattr(svc, 'read', fail)
    result = request(app, tess)
    deny(result)
    assert tess not in json.dumps(result[1]) and not caplog.text


def test_real_commit_failure_discards_prepared_projection(setup, engine, monkeypatch):
    app, _, tess, *_ = setup
    original = engine.dialect.do_commit
    armed = True
    def lost_ack(connection):
        nonlocal armed
        original(connection)
        if armed:
            armed = False
            raise RuntimeError('fictional lost acknowledgment')
    monkeypatch.setattr(engine.dialect, 'do_commit', lost_ack)
    deny(request(app, tess))
    assert request(app, tess)[0] == 200


def test_no_private_response_reuse_or_sensitive_headers_logs(setup, engine, caplog):
    app, _, tess, *_ = setup
    before = request(app, tess)
    revoke(engine, 'source')
    after = request(app, tess)
    assert before[1]['observations']['total'] == 3 and after[1]['observations']['total'] == 0
    serialized = json.dumps(after[1]) + repr(after[2]) + caplog.text
    for forbidden in (tess, 'never-return-account-data', 'secret_hash', 'roles', 'person_id',
                      'issuer', 'subject', 'intent_hash', 'readers', 'larch-private'):
        assert forbidden not in serialized
    with engine.connect() as c:
        assert c.execute(select(authorization_audit)).all() == []
        assert len(c.execute(select(session_audit)).all()) == 3


@pytest.mark.parametrize('flag', [False, 1, 'true', None])
def test_exact_opt_in_and_explicit_trusted_configuration(setup, flag):
    with pytest.raises(api.ContractError):
        api.FictionalReadAPI(setup[1], HOME, synthetic_only=flag)


def test_api_isolation_imports_no_network_or_harness_and_no_production_wiring(setup, monkeypatch):
    monkeypatch.setattr(a.AuthorizationService, 'harness_context', lambda *args, **kwargs: pytest.fail('no harness escalation'))
    monkeypatch.setattr('socket.create_connection', lambda *args, **kwargs: pytest.fail('no network'))
    assert request(setup[0], setup[2])[0] == 200
    path = ROOT/'src/family_os/_fictional_read_api.py'; text = path.read_text()
    tree = ast.parse(text)
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
    assert imports == {'asyncio', 'dataclasses', 'json', 're', 'urllib.parse',
                       'family_os._household_sessions'}
    for name in ('harness_context', 'authorized_projection', 'create_engine', 'getenv', 'uvicorn', 'requests', 'httpx'):
        assert name not in text
    for other in (ROOT/'src').rglob('*.py'):
        if other != path:
            assert '_fictional_read_api' not in other.read_text()
    with pytest.raises(api.ContractError):
        api.FictionalReadAPI(object(), HOME, synthetic_only=True)
    with pytest.raises(api.ContractError):
        api.FictionalReadAPI(setup[1], '../azalea', synthetic_only=True)


@pytest.mark.parametrize('kind', ['membership', 'binding'])
def test_revocation_then_reenrollment_does_not_revive_bearer(setup, engine, kind):
    app, _, tess, *_ = setup
    revoke(engine, kind)
    table = member if kind == 'membership' else binding
    with a.authorization_transaction(engine, HOME) as c:
        c.execute(update(table).where(table.c.person_id == 'tess').values(state='allowed', revision=3))
    deny(request(app, tess))


def test_supported_headers_and_duplicate_optional_header_rejection(setup):
    app, _, tess, *_ = setup
    headers = [(b'authorization', b'Bearer '+tess.encode()), (b'host', b'fictional.test'),
               (b'accept', b'application/json'), (b'content-length', b'0')]
    assert request(app, headers=headers)[0] == 200
    deny(request(app, headers=headers[:2]+[(b'host', b'fictional.test')]))


def test_receive_deadline_failure_has_safe_error_before_any_read(setup, monkeypatch):
    app, service, tess, *_ = setup
    async def timeout(awaitable, **kwargs):
        assert kwargs == {'timeout': 1}
        awaitable.close()
        raise TimeoutError('private transport information')
    monkeypatch.setattr(api.asyncio, 'wait_for', timeout)
    monkeypatch.setattr(service, 'read', lambda *args, **kwargs: pytest.fail('no read on timeout'))
    deny(request(app, tess))


def test_serialization_failure_emits_no_partial_data(setup, monkeypatch, caplog):
    def fail(*args):
        raise ValueError('private serialization details')
    monkeypatch.setattr(api, '_serialize', fail)
    deny(request(setup[0], setup[2]))
    assert not caplog.text


def test_send_failure_never_starts_second_response(setup):
    app, _, tess, *_ = setup
    async def run():
        sent = []
        async def receive(): return {'type': 'http.request'}
        async def send(event):
            sent.append(event)
            raise RuntimeError('transport closed')
        scope = {'type': 'http', 'method': 'GET', 'path': '/v0/workbench',
                 'headers': [(b'authorization', b'Bearer '+tess.encode())]}
        with pytest.raises(RuntimeError, match='^transport closed$'):
            await app(scope, receive, send)
        assert len(sent) == 1 and sent[0]['status'] == 200
    asyncio.run(run())


@pytest.mark.parametrize('protocol', ['lifespan', 'websocket'])
def test_non_http_protocols_cannot_initialize_routes(setup, protocol):
    async def run():
        async def forbidden(*args): pytest.fail('no protocol events')
        with pytest.raises(api.ContractError):
            await setup[0]({'type': protocol}, forbidden, forbidden)
    asyncio.run(run())
