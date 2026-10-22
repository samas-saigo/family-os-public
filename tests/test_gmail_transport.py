"""Synthetic network/credential exceptions only; never live HTTP or OS keyring."""
import logging
import traceback

import pytest
from google.auth.exceptions import RefreshError, TransportError, DefaultCredentialsError
from requests import exceptions as requests_errors
from sqlalchemy import event

from gmail_clock import FakeClock
from family_os.errors import GmailAPIError, GmailAuthError, GmailTransportError
from family_os.gmail import GmailHTTPClient, GmailConnector
from family_os.gmail_auth import KeyringSession
from family_os.ingestion import ingest
from family_os.schema import source_record, raw_source_record, source_sync_state
from test_gmail import message
from test_gmail_auth import ACCOUNT, Credentials, MemoryStore
from test_gmail_retries import PRIVATE, Response, gmail_engine, rows

TRANSIENTS = [requests_errors.Timeout, requests_errors.ConnectionError,
              requests_errors.RequestException, TransportError,
              requests_errors.ChunkedEncodingError, requests_errors.ContentDecodingError]


class RaisingSession:
    def __init__(self, clock, values):
        self.clock, self.values = clock, list(values)
        self.calls, self.starts = [], []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        self.starts.append(self.clock.clock())
        logging.getLogger('google.synthetic').warning(PRIVATE)
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def wrap(monkeypatch, session, authorized, credentials=None, store=None):
    if not authorized:
        return session
    import google.auth.transport.requests
    monkeypatch.setattr(google.auth.transport.requests, 'AuthorizedSession', lambda credentials: session)
    return KeyringSession(credentials or Credentials(), store or MemoryStore(), ACCOUNT)


def safe(failure, caplog):
    assert PRIVATE not in str(failure) + repr(failure) + caplog.text + ''.join(traceback.format_exception(failure))
    assert failure.__cause__ is None


@pytest.mark.parametrize('kind', TRANSIENTS)
@pytest.mark.parametrize('authorized', [False, True])
def test_transient_transport_retry_then_success(kind, authorized, monkeypatch, caplog):
    clock = FakeClock()
    session = RaisingSession(clock, [kind(PRIVATE), Response(200, {})])
    client = GmailHTTPClient(wrap(monkeypatch, session, authorized),
                            clock=clock.clock, sleep=clock.sleep, jitter=lambda: .5)
    caplog.set_level(logging.DEBUG)
    assert client.message('synthetic-message') == {}
    assert len(session.calls) == 2 and session.calls[0] == session.calls[1]
    assert clock.delays == [1.5] and session.starts == [0, 1.5]
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize('kind', TRANSIENTS[:4])
@pytest.mark.parametrize('authorized', [False, True])
def test_transport_exhaustion_is_five_attempt_safe_api_category(kind, authorized, monkeypatch, caplog):
    clock = FakeClock()
    session = RaisingSession(clock, [kind(PRIVATE) for _ in range(5)])
    client = GmailHTTPClient(wrap(monkeypatch, session, authorized),
                            clock=clock.clock, sleep=clock.sleep, jitter=lambda: 0)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(GmailAPIError, match='retryable') as failure:
        client.history('100', 'synthetic-page', 25)
    assert not isinstance(failure.value, (GmailAuthError, GmailTransportError))
    assert len(session.calls) == 5 and all(call == session.calls[0] for call in session.calls)
    assert clock.delays == [1, 2, 4, 8] and session.starts == [0, 1, 3, 7, 15]
    safe(failure.value, caplog)


@pytest.mark.parametrize('authorized', [False, True])
@pytest.mark.parametrize('retryable', [False, True])
def test_refresh_rejection_remains_auth_and_never_retried(authorized, retryable, monkeypatch, caplog):
    clock = FakeClock()
    session = RaisingSession(clock, [RefreshError(PRIVATE, retryable=retryable)])
    client = GmailHTTPClient(wrap(monkeypatch, session, authorized), clock=clock.clock, sleep=clock.sleep)
    with pytest.raises(GmailAuthError) as failure:
        client.profile()
    assert len(session.calls) == 1 and clock.delays == []
    safe(failure.value, caplog)


def test_other_explicit_google_credential_failure_stays_auth(monkeypatch, caplog):
    clock = FakeClock()
    session = RaisingSession(clock, [DefaultCredentialsError(PRIVATE)])
    client = GmailHTTPClient(wrap(monkeypatch, session, True), clock=clock.clock, sleep=clock.sleep)
    with pytest.raises(GmailAuthError) as failure:
        client.profile()
    assert len(session.calls) == 1 and clock.delays == []
    safe(failure.value, caplog)


@pytest.mark.parametrize('kind', [requests_errors.InvalidURL, requests_errors.InvalidHeader,
    requests_errors.InvalidSchema, requests_errors.MissingSchema, requests_errors.URLRequired,
    requests_errors.TooManyRedirects, requests_errors.SSLError, requests_errors.HTTPError,
    requests_errors.InvalidJSONError, requests_errors.StreamConsumedError,
    requests_errors.UnrewindableBodyError])
def test_deterministic_request_errors_do_not_retry(kind, monkeypatch, caplog):
    clock = FakeClock()
    session = RaisingSession(clock, [kind(PRIVATE)])
    client = GmailHTTPClient(wrap(monkeypatch, session, True), clock=clock.clock, sleep=clock.sleep)
    with pytest.raises(GmailAPIError) as failure:
        client.profile()
    assert len(session.calls) == 1 and clock.delays == []
    safe(failure.value, caplog)


@pytest.mark.parametrize('authorized', [False, True])
@pytest.mark.parametrize('kind', [RuntimeError, ValueError])
def test_unknown_exception_fails_closed_without_retry(authorized, kind, monkeypatch, caplog):
    clock = FakeClock()
    session = RaisingSession(clock, [kind(PRIVATE)])
    client = GmailHTTPClient(wrap(monkeypatch, session, authorized), clock=clock.clock, sleep=clock.sleep)
    with pytest.raises(GmailAuthError if authorized else GmailAPIError) as failure:
        client.profile()
    assert len(session.calls) == 1 and clock.delays == []
    safe(failure.value, caplog)


@pytest.mark.parametrize('stage', ['scope_before', 'scope_after', 'serialize', 'save'])
@pytest.mark.parametrize('kind', [requests_errors.Timeout, TransportError])
def test_credential_operations_are_not_classified_as_transport(stage, kind, monkeypatch, caplog):
    clock, credentials = FakeClock(), Credentials()
    session = RaisingSession(clock, [Response(200, {})])
    class Store(MemoryStore):
        def save(self, *args):
            raise kind(PRIVATE)
    bound = wrap(monkeypatch, session, True, credentials, Store())
    original_get = session.get
    def get(*args, **kwargs):
        value = original_get(*args, **kwargs)
        if stage == 'scope_after':
            credentials.granted_scopes = ['https://mail.google.com/']
        elif stage == 'serialize':
            def broken():
                raise kind(PRIVATE)
            credentials.to_json = broken
        elif stage == 'save':
            credentials.to_json = lambda: PRIVATE
        return value
    session.get = get
    if stage == 'scope_before':
        credentials.granted_scopes = []
    with pytest.raises(GmailAuthError) as failure:
        GmailHTTPClient(bound, clock=clock.clock, sleep=clock.sleep).profile()
    assert len(session.calls) == int(stage != 'scope_before') and clock.delays == []
    safe(failure.value, caplog)


def test_refresh_on_transport_failure_is_saved_once_on_retry_success(monkeypatch, caplog):
    clock, credentials = FakeClock(), Credentials()
    session = RaisingSession(clock, [requests_errors.Timeout(PRIVATE), Response(200, {})])
    original = session.get
    def get(*args, **kwargs):
        credentials.to_json = lambda: PRIVATE
        return original(*args, **kwargs)
    session.get = get
    class Store(MemoryStore):
        writes = 0
        def save(self, account, state):
            self.writes += 1
            super().save(account, state)
    store = Store()
    bound = wrap(monkeypatch, session, True, credentials, store)
    assert GmailHTTPClient(bound, clock=clock.clock, sleep=clock.sleep, jitter=lambda: 0).profile() == {}
    assert store.writes == 1 and store.load(ACCOUNT) == PRIVATE
    assert clock.delays == [1]
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize('prior_page', [False, True])
@pytest.mark.parametrize('kind', [requests_errors.Timeout, TransportError])
def test_transport_page_failure_and_resume_keep_state_and_history(gmail_engine, prior_page, kind, monkeypatch, caplog):
    engine, clock, active = gmail_engine, FakeClock(), set()
    event.listen(engine, 'begin', active.add)
    event.listen(engine, 'commit', active.discard)
    event.listen(engine, 'rollback', active.discard)
    def sleep(delay):
        assert not active
        clock.sleep(delay)
    class RoutedSession:
        failing = True
        failures = 0
        saved = None
        pages = []
        def get(self, url, *, params, timeout):
            resource = url.removeprefix(GmailHTTPClient.BASE)
            if resource == 'profile':
                return Response(200, {'emailAddress': 'demo@gmail.com', 'historyId': '100'})
            if resource == 'messages':
                self.pages.append(params['pageToken'])
                if prior_page and params['pageToken'] is None:
                    return Response(200, {'messages': [{'id': 'm1'}], 'nextPageToken': 'p2'})
                self.saved = dict(rows(engine, source_sync_state)[0])
                return Response(200, {'messages': [{'id': 'm2'}, {'id': 'm3'}]})
            if resource == 'messages/m3' and self.failing:
                self.failures += 1
                logging.warning(PRIVATE)
                raise kind(PRIVATE)
            if resource.startswith('messages/'):
                return Response(200, message(resource.split('/')[1]))
            assert resource == 'history'
            return Response(200, {'historyId': '120'})
    session = RoutedSession()
    connector = GmailConnector(GmailHTTPClient(wrap(monkeypatch, session, True),
                              clock=clock.clock, sleep=sleep, jitter=lambda: 0))
    with pytest.raises(GmailAPIError, match='retryable') as failure:
        ingest(engine, 'home', 'gmail1', connector)
    safe(failure.value, caplog)
    assert session.failures == 5
    assert [d for d in clock.delays if d >= 1] == [1, 2, 4, 8]
    assert dict(rows(engine, source_sync_state)[0]) == session.saved
    before_source, before_raw = rows(engine, source_record), rows(engine, raw_source_record)
    assert len(before_source) == len(before_raw) == int(prior_page)
    session.failing = False
    result = ingest(engine, 'home', 'gmail1', connector)
    assert result.inserted == 2
    assert len(rows(engine, source_record)) == len(rows(engine, raw_source_record)) == 2 + int(prior_page)
    if prior_page:
        assert session.pages == [None, 'p2', 'p2']
        assert next(r for r in rows(engine, source_record) if r['provider_object_id'] == 'm1') == before_source[0]
        assert next(r for r in rows(engine, raw_source_record) if r['provider_object_id'] == 'm1') == before_raw[0]
