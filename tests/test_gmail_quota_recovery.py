"""Bounded extended recovery on synthetic quota errors, with virtual time only."""
import logging
import traceback

import pytest

from gmail_clock import FakeClock
from family_os.errors import GmailAPIError
from family_os.gmail import GmailHTTPClient, GET_MIN_INTERVAL
from family_os.gmail_auth import KeyringSession, READONLY_SCOPE
from test_gmail_auth import ACCOUNT, Credentials, MemoryStore
from test_gmail_pacing import TimedSession
from test_gmail_retries import PRIVATE, Response, quota


def failure(kind):
    return Response(429, ValueError(PRIVATE)) if kind == '429' else quota(kind)


def client_for(clock, session, jitter):
    return GmailHTTPClient(session, clock=clock.clock, sleep=clock.sleep, jitter=lambda: jitter)


@pytest.mark.parametrize('kind', ['rateLimitExceeded', 'userRateLimitExceeded', '429'])
@pytest.mark.parametrize('jitter', [0, .75])
def test_exact_quota_budget_exhausts_without_double_sleep_or_leaks(kind, jitter, caplog):
    clock = FakeClock(1000)
    session = TimedSession(clock, [failure(kind) for _ in range(8)])
    client = client_for(clock, session, jitter)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(GmailAPIError, match='retryable') as error:
        client.message('synthetic-message')
    expected = [1 + jitter, 2 + jitter, 4 + jitter, 8 + jitter, 16 + jitter, 32, 32]
    assert len(session.calls) == 8 and session.responses == []
    assert all(call == session.calls[0] for call in session.calls)
    assert clock.delays == expected  # No extra pacing waits after backoff.
    assert clock.clock() - 1000 == sum(expected)
    assert 95 <= sum(expected) < 100 and max(expected) == 32
    assert GET_MIN_INTERVAL == .30 and session.starts[0] == 1000
    assert all(b - a >= .30 for a, b in zip(session.starts, session.starts[1:]))
    assert PRIVATE not in str(error.value) + caplog.text + ''.join(traceback.format_exception(error.value))


@pytest.mark.parametrize('kind', ['rateLimitExceeded', 'userRateLimitExceeded', '429'])
@pytest.mark.parametrize('failed_attempts', [5, 6, 7])
def test_late_success_after_16_and_32_second_stages(kind, failed_attempts):
    clock = FakeClock()
    session = TimedSession(clock, [failure(kind) for _ in range(failed_attempts)] + [Response(200, {})])
    client = client_for(clock, session, 0)
    assert client.message('synthetic-message') == {}
    expected = [1, 2, 4, 8, 16, 32, 32][:failed_attempts]
    assert len(session.calls) == failed_attempts + 1
    assert all(call == session.calls[0] for call in session.calls)
    assert clock.delays == expected and clock.clock() == sum(expected)
    # A fresh GET has a fresh retry budget, but keeps the previous start's pacing.
    session.responses.append(Response(200, {}))
    assert client.profile() == {}
    assert clock.delays == pytest.approx(expected + [.30])


@pytest.mark.parametrize('statuses, expected_waits', [
    ([429] * 4 + [500], [1, 2, 4, 8]),
    ([429] * 6 + [503], [1, 2, 4, 8, 16, 32]),
    ([503] * 4 + [429] * 4, [1, 2, 4, 8, 16, 32, 32]),
])
def test_mixed_categories_share_finite_counter_and_do_not_extend_server_errors(statuses, expected_waits):
    clock = FakeClock()
    session = TimedSession(clock, [Response(status, ValueError(PRIVATE)) for status in statuses])
    with pytest.raises(GmailAPIError) as error:
        client_for(clock, session, 0).profile()
    assert error.value.status == statuses[-1]
    assert len(session.calls) == len(statuses) <= 8
    assert clock.delays == expected_waits
    assert session.responses == []


def test_credential_refresh_during_late_quota_retry_saved_once(monkeypatch, caplog):
    import google.auth.transport.requests
    clock, credentials = FakeClock(), Credentials()
    session = TimedSession(clock, [quota() for _ in range(7)] + [Response(200, {})])
    class AuthorizedSession:
        def __init__(self, credentials):
            self.credentials = credentials
        def get(self, *args, **kwargs):
            assert self.credentials.scopes == [READONLY_SCOPE]
            if len(session.calls) == 6:
                self.credentials.to_json = lambda: PRIVATE
            return session.get(*args, **kwargs)
        def close(self):
            pass
    class Store(MemoryStore):
        writes = 0
        def save(self, account, value):
            self.writes += 1
            super().save(account, value)
    monkeypatch.setattr(google.auth.transport.requests, 'AuthorizedSession', AuthorizedSession)
    caplog.set_level(logging.DEBUG)
    store = Store()
    assert client_for(clock, KeyringSession(credentials, store, ACCOUNT), 0).profile() == {}
    assert len(session.calls) == 8 and store.writes == 1
    assert store.load(ACCOUNT) == PRIVATE
    assert clock.delays == [1, 2, 4, 8, 16, 32, 32]
    assert PRIVATE not in caplog.text
