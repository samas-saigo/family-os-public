"""Synthetic HTTP responses only; never OAuth, keyring access, or live mail."""
from copy import deepcopy
import json
import logging
import traceback

import pytest
from sqlalchemy import event, select
from gmail_clock import FakeClock

from family_os.errors import GmailAPIError, GmailAuthError
from family_os.gmail import GmailConnector, GmailHTTPClient, GET_ATTEMPTS, GET_MAX_DELAY, QUOTA_GET_ATTEMPTS
from family_os.gmail_auth import KeyringSession, READONLY_SCOPE
from family_os.ingestion import ingest
from family_os.registry import register
from family_os.schema import raw_source_record, source_record, source_sync_state
from test_gmail import message
from test_gmail_auth import ACCOUNT, Credentials, MemoryStore

PRIVATE = 'synthetic-private-token-mailbox-message-https://private.invalid/NEVER-LOG'


class Response:
    def __init__(self, status, value=None):
        self.status_code, self.value = status, value
        self.json_calls = 0

    def json(self):
        self.json_calls += 1
        logging.getLogger('google.synthetic').warning(PRIVATE)
        if isinstance(self.value, Exception):
            raise self.value
        return deepcopy(self.value)

    @property
    def text(self):
        raise AssertionError('Must not read provider text')

    @property
    def content(self):
        raise AssertionError('Must not read provider bytes')


def quota(reason='rateLimitExceeded'):
    return Response(403, {'error': {'message': PRIVATE,
        'errors': [{'reason': reason, 'message': PRIVATE, 'location': PRIVATE}],
        'private': PRIVATE}})


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kwargs):
        logging.getLogger('google.synthetic').warning(PRIVATE)
        self.calls.append((url, deepcopy(kwargs)))
        return self.responses.pop(0)


def client_for(responses, jitter=0.25):
    session, clock = Session(responses), FakeClock()
    return GmailHTTPClient(session, sleep=clock.sleep, clock=clock.clock,
                           jitter=lambda: jitter), session, clock.delays


@pytest.mark.parametrize('reason', ['rateLimitExceeded', 'userRateLimitExceeded'])
def test_recognized_403_retries_same_get_then_succeeds(reason, caplog):
    response = quota(reason)
    client, session, delays = client_for([response, Response(200, {'ok': True})])
    caplog.set_level(logging.DEBUG)
    assert client.message('synthetic-message') == {'ok': True}
    assert response.json_calls == 1
    assert len(session.calls) == 2 and session.calls[0] == session.calls[1]
    assert delays == [1.25]
    assert PRIVATE not in caplog.text
    logging.warning('Logging restored')
    assert 'Logging restored' in caplog.text


@pytest.mark.parametrize('status', [429, 500, 502, 503, 599])
def test_status_transients_retry_without_reading_error_body(status):
    failure = Response(status, AssertionError(PRIVATE))
    client, session, delays = client_for([failure, Response(200, {})])
    assert client.profile() == {}
    assert failure.json_calls == 0
    assert len(session.calls) == 2 and delays == [1.25]


@pytest.mark.parametrize('status, reason', [(403, 'rateLimitExceeded'),
    (403, 'userRateLimitExceeded'), (429, None), (500, None), (503, None)])
def test_exhaustion_is_finite_exponential_and_safe(status, reason, caplog):
    attempts = QUOTA_GET_ATTEMPTS if status in {403, 429} else GET_ATTEMPTS
    responses = [quota(reason) if reason else Response(status, AssertionError(PRIVATE))
                 for _ in range(attempts)]
    client, session, delays = client_for(responses, jitter=0.75)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(GmailAPIError, match='Gmail retryable') as failure:
        client.history('100', 'synthetic-page', 25)
    assert failure.value.status == status
    assert len(session.calls) == attempts == (8 if status in {403, 429} else 5)
    assert all(call == session.calls[0] for call in session.calls)
    assert delays == [1.75, 2.75, 4.75, 8.75] + ([16.75, 32, 32] if status in {403, 429} else [])
    assert all(0 < delay <= GET_MAX_DELAY for delay in delays)
    assert PRIVATE not in str(failure.value) + repr(failure.value) + caplog.text
    assert PRIVATE not in ''.join(traceback.format_exception(failure.value))
    assert failure.value.__cause__ is None


def test_backoff_delay_cap(monkeypatch):
    monkeypatch.setattr('family_os.gmail.GET_MAX_DELAY', 2.5)
    client, session, delays = client_for([Response(429)] * 4 + [Response(200, {})], jitter=0.75)
    assert client.profile() == {}
    assert len(session.calls) == 5
    assert delays == [1.75, 2.5, 2.5, 2.5]


@pytest.mark.parametrize('reason', ['forbidden', 'domainPolicy', 'insufficientPermissions',
    'dailyLimitExceeded', 'unknown', 'RateLimitExceeded', 'rateLimitExceeded '])
def test_permanent_or_unknown_403_not_retried(reason, caplog):
    client, session, delays = client_for([quota(reason)])
    with pytest.raises(GmailAPIError, match='request rejected') as failure:
        client.profile()
    assert failure.value.status == 403
    assert len(session.calls) == 1 and delays == []
    assert PRIVATE not in str(failure.value) + caplog.text


@pytest.mark.parametrize('value', [None, [], {}, {'error': None}, {'error': []},
    {'error': {'errors': None}}, {'error': {'errors': []}},
    {'error': {'errors': {'reason': 'rateLimitExceeded'}}},
    {'error': {'errors': [None]}}, {'error': {'errors': [{}]}},
    {'error': {'errors': [{'reason': ['rateLimitExceeded']}] }},
    {'error': {'errors': [{'reason': 'rateLimitExceeded'}, {'reason': 'forbidden'}]}},
    {'error': {'errors': [{'reason': 'rateLimitExceeded'}] * 17}},
    {'reason': 'rateLimitExceeded', 'message': PRIVATE}, ValueError(PRIVATE)])
def test_malformed_or_non_json_403_fails_closed(value, caplog):
    client, session, delays = client_for([Response(403, value)])
    with pytest.raises(GmailAPIError, match='request rejected') as failure:
        client.profile()
    assert len(session.calls) == 1 and delays == []
    assert PRIVATE not in str(failure.value) + caplog.text
    assert PRIVATE not in ''.join(traceback.format_exception(failure.value))


@pytest.mark.parametrize('status', [400, 401, 404])
def test_non_transient_status_not_retried_or_body_parsed(status):
    response = Response(status, AssertionError(PRIVATE))
    client, session, delays = client_for([response])
    with pytest.raises(GmailAPIError, match='request rejected') as failure:
        client.profile()
    assert failure.value.status == status
    assert len(session.calls) == 1 and delays == []
    assert response.json_calls == 0


@pytest.mark.parametrize('failure', [RuntimeError(PRIVATE), ValueError(PRIVATE)])
def test_transport_exception_not_retried_or_leaked(failure, caplog):
    class BrokenSession:
        calls = 0
        def get(self, *args, **kwargs):
            self.calls += 1
            logging.warning(PRIVATE)
            raise failure
    session, clock = BrokenSession(), FakeClock()
    client = GmailHTTPClient(session, sleep=clock.sleep, clock=clock.clock)
    with pytest.raises(GmailAPIError) as error:
        client.profile()
    assert session.calls == 1 and clock.delays == []
    assert PRIVATE not in str(error.value) + caplog.text
    assert PRIVATE not in ''.join(traceback.format_exception(error.value))


def test_retry_budget_restarts_per_request():
    client, session, delays = client_for([quota(), Response(200, {}), quota(), Response(200, {})])
    assert client.profile() == client.profile() == {}
    assert len(session.calls) == 4 and delays == pytest.approx([1.25, 0.30, 1.25])


@pytest.mark.parametrize('break_save', [False, True])
def test_refresh_on_transient_response_saved_once_or_safe_auth_failure(monkeypatch, caplog, break_save):
    import google.auth.transport.requests
    import family_os.gmail_auth as auth
    credentials = Credentials()
    responses = Session([quota(), Response(200, {})])
    class AuthorizedSession:
        def __init__(self, credentials):
            self.credentials = credentials
        def get(self, *args, **kwargs):
            self.credentials.to_json = lambda: PRIVATE
            return responses.get(*args, **kwargs)
        def close(self):
            pass
    class Store(MemoryStore):
        writes = 0
        def save(self, account, value):
            self.writes += 1
            if break_save:
                raise RuntimeError(PRIVATE)
            super().save(account, value)
    checks = []
    original = auth.require_readonly
    def check(credentials):
        checks.append(set(credentials.granted_scopes if credentials.granted_scopes is not None else credentials.scopes))
        original(credentials)
    monkeypatch.setattr(google.auth.transport.requests, 'AuthorizedSession', AuthorizedSession)
    monkeypatch.setattr(auth, 'require_readonly', check)
    store, clock = Store(), FakeClock()
    delays = clock.delays
    caplog.set_level(logging.DEBUG)
    client = GmailHTTPClient(KeyringSession(credentials, store, ACCOUNT),
                            sleep=clock.sleep, clock=clock.clock, jitter=lambda: 0)
    if break_save:
        with pytest.raises(GmailAuthError) as failure:
            client.profile()
        assert PRIVATE not in str(failure.value)
        assert len(responses.calls) == 1 and delays == []
    else:
        assert client.profile() == {}
        assert store.load(ACCOUNT) == PRIVATE
        assert len(responses.calls) == 2 and delays == [1]
        assert len(checks) == 5  # constructor plus before/after each GET
    assert store.writes == 1
    assert all(scopes == {READONLY_SCOPE} for scopes in checks)
    assert PRIVATE not in caplog.text


@pytest.fixture
def gmail_engine(engine):
    register(engine, {'household': {'id': 'home', 'name': 'Synthetic'}, 'source_accounts': [
        {'id': 'gmail1', 'provider': 'gmail', 'owner_type': 'unknown', 'external_account': 'demo@gmail.com'}]})
    return engine


def rows(engine, table):
    with engine.connect() as connection:
        return connection.execute(select(table)).mappings().all()


@pytest.mark.parametrize('prior_page', [False, True])
@pytest.mark.parametrize('status', [403, 429, 503])
def test_http_exhaustion_preserves_entire_page_cursor_and_prior_history(gmail_engine, prior_page, status, caplog):
    engine = gmail_engine
    clock, transactions, starts = FakeClock(), set(), []
    event.listen(engine, 'begin', transactions.add)
    event.listen(engine, 'commit', transactions.discard)
    event.listen(engine, 'rollback', transactions.discard)
    def sleep(delay):
        assert not transactions  # Both pacing and backoff stay outside DB transactions.
        clock.sleep(delay)
    class RoutedSession:
        fail = True
        failures = 0
        pages = []
        committed_state = None
        def get(self, url, *, params, timeout):
            starts.append(clock.clock())
            resource = url.removeprefix(GmailHTTPClient.BASE)
            assert timeout == 30
            if resource == 'profile':
                return Response(200, {'emailAddress': 'demo@gmail.com', 'historyId': '100'})
            if resource == 'messages':
                self.pages.append(params['pageToken'])
                if prior_page and params['pageToken'] is None:
                    return Response(200, {'messages': [{'id': 'm1'}], 'nextPageToken': 'p2'})
                self.committed_state = dict(rows(engine, source_sync_state)[0])
                return Response(200, {'messages': [{'id': 'm2'}, {'id': 'm3'}]})
            if resource == 'messages/m3' and self.fail:
                self.failures += 1
                return quota() if status == 403 else Response(status, AssertionError(PRIVATE))
            if resource.startswith('messages/'):
                return Response(200, message(resource.split('/')[1]))
            assert resource == 'history'
            return Response(200, {'historyId': '120'})
    session = RoutedSession()
    connector = GmailConnector(GmailHTTPClient(session, sleep=sleep, clock=clock.clock, jitter=lambda: 0))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(GmailAPIError, match='retryable'):
        ingest(engine, 'home', 'gmail1', connector)
    assert session.failures == (8 if status in {403, 429} else 5)
    assert [delay for delay in clock.delays if delay >= 1] == [1, 2, 4, 8] + ([16, 32, 32] if status in {403, 429} else [])
    assert any(0 < delay < 1 for delay in clock.delays)
    assert dict(rows(engine, source_sync_state)[0]) == session.committed_state
    committed_sources, committed_raw = rows(engine, source_record), rows(engine, raw_source_record)
    assert len(committed_sources) == len(committed_raw) == int(prior_page)
    if prior_page:
        assert committed_sources[0]['provider_object_id'] == 'm1'
        assert json.loads(session.committed_state['cursor'])['page_token'] == 'p2'
    else:
        assert session.committed_state['cursor'] is None
    # Resume without resetting state. A previously fetched m2 was never partially stored.
    session.fail = False
    result = ingest(engine, 'home', 'gmail1', connector)
    assert (result.inserted, result.pages) == (2, 2)
    assert len(rows(engine, source_record)) == len(rows(engine, raw_source_record)) == 2 + int(prior_page)
    if prior_page:
        assert session.pages == [None, 'p2', 'p2']
        assert next(r for r in rows(engine, source_record) if r['provider_object_id'] == 'm1') == committed_sources[0]
        assert next(r for r in rows(engine, raw_source_record) if r['provider_object_id'] == 'm1') == committed_raw[0]
    assert json.loads(rows(engine, source_sync_state)[0]['cursor'])['history_id'] == '120'
    assert all(b - a >= 0.30 - 1e-10 for a, b in zip(starts, starts[1:]))
    assert PRIVATE not in caplog.text
