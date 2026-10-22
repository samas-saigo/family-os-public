"""Deterministic virtual-time Gmail tests; no live HTTP/OAuth or real sleeps."""
import logging
from types import SimpleNamespace

import pytest

from gmail_clock import FakeClock
from family_os.errors import GmailAPIError
from family_os.gmail import GmailHTTPClient, GET_MIN_INTERVAL
from family_os.gmail_auth import KeyringSession
from test_gmail_auth import ACCOUNT, Credentials, MemoryStore
from test_gmail_retries import PRIVATE, Response, quota


class TimedSession:
    def __init__(self, clock, responses=None, latency=0):
        self.clock, self.responses, self.latency = clock, responses, latency
        self.starts, self.calls = [], []

    def get(self, url, **kwargs):
        self.starts.append(self.clock.clock())
        self.calls.append((url, kwargs))
        logging.getLogger('google.synthetic').warning(PRIVATE)
        self.clock.now += self.latency
        return self.responses.pop(0) if self.responses is not None else Response(200, {})


def make_client(clock, session):
    return GmailHTTPClient(session, clock=clock.clock, sleep=clock.sleep, jitter=lambda: 0.5)


@pytest.mark.parametrize('start', [0.0, 123456789.0])
def test_first_get_starts_immediately(start):
    clock = FakeClock(start)
    session = TimedSession(clock)
    assert make_client(clock, session).profile() == {}
    assert session.starts == [start] and clock.delays == []


def test_all_supported_get_endpoints_share_one_pacer():
    clock = FakeClock()
    session = TimedSession(clock)
    client = make_client(clock, session)
    client.profile()
    client.list_messages('synthetic-query', 'synthetic-page', 25)
    client.message('synthetic-message')
    client.history('100', None, 25)
    assert session.starts == pytest.approx([0, .3, .6, .9])
    assert clock.delays == pytest.approx([.3, .3, .3])
    assert [call[0].rsplit('/', 1)[-1] for call in session.calls] == ['profile', 'messages', 'synthetic-message', 'history']
    assert all(call[1]['timeout'] == 30 for call in session.calls)


@pytest.mark.parametrize('latency, expected_delay', [(0.1, 0.2), (0.8, None)])
def test_elapsed_request_time_counts_toward_spacing(latency, expected_delay):
    clock = FakeClock()
    session = TimedSession(clock, latency=latency)
    client = make_client(clock, session)
    client.profile()
    client.profile()
    assert session.starts == pytest.approx([0, max(GET_MIN_INTERVAL, latency)])
    assert clock.delays == pytest.approx([] if expected_delay is None else [expected_delay])


def test_default_uses_monotonic_clock_and_sleep_not_wall_clock(monkeypatch):
    import family_os.gmail as gmail
    clock = FakeClock(500)
    def wall_clock():
        raise AssertionError('Wall clock must not be used')
    monkeypatch.setattr(gmail, 'time', SimpleNamespace(monotonic=clock.clock, sleep=clock.sleep, time=wall_clock))
    session = TimedSession(clock)
    client = GmailHTTPClient(session)
    client.profile()
    client.profile()
    assert session.starts == pytest.approx([500, 500.3])
    assert clock.delays == pytest.approx([.3])


def test_idle_time_is_not_banked_as_burst_credit():
    clock = FakeClock()
    session = TimedSession(clock)
    client = make_client(clock, session)
    client.profile()
    clock.now += 600
    client.profile()
    client.profile()
    assert session.starts == pytest.approx([0, 600, 600.3])
    assert clock.delays == pytest.approx([.3])


def test_oversleep_records_actual_start_not_scheduled_deadline():
    clock = FakeClock()
    session = TimedSession(clock)
    def oversleep(delay):
        clock.sleep(delay)
        clock.now += .75
    client = GmailHTTPClient(session, clock=clock.clock, sleep=oversleep)
    for _ in range(3):
        client.profile()
    assert session.starts == pytest.approx([0, 1.05, 2.10])
    assert clock.delays == pytest.approx([.3, .3])


def test_clients_have_independent_start_state():
    clock = FakeClock()
    first, second = TimedSession(clock), TimedSession(clock)
    a, b = make_client(clock, first), make_client(clock, second)
    a.profile()
    b.profile()
    a.profile()
    assert first.starts == pytest.approx([0, .3])
    assert second.starts == [0]


def test_message_get_heavy_traffic_has_conservative_quota_headroom():
    clock = FakeClock()
    session = TimedSession(clock)
    client = make_client(clock, session)
    for _ in range(500):
        client.message('synthetic-message')
    assert GET_MIN_INTERVAL == .30
    assert all(b - a >= .30 - 1e-10 for a, b in zip(session.starts, session.starts[1:]))
    # Include both endpoints conservatively: at most 201 starts / 4020 units in 60s.
    max_window = max(sum(start <= t <= start + 60 for t in session.starts) for start in session.starts)
    assert max_window <= 201
    assert max_window * 20 <= 4020 < 6000
    assert 60 / GET_MIN_INTERVAL * 20 == pytest.approx(4000)
    assert session.starts[-1] == pytest.approx(499 * .30)


@pytest.mark.parametrize('status', [400, 401, 403, 404])
def test_permanent_failure_not_retried_but_next_get_is_paced(status):
    clock = FakeClock()
    response = quota('forbidden') if status == 403 else Response(status, ValueError(PRIVATE))
    session = TimedSession(clock, [response, Response(200, {})])
    client = make_client(clock, session)
    with pytest.raises(GmailAPIError, match='request rejected'):
        client.profile()
    assert session.starts == [0] and clock.delays == []
    assert client.profile() == {}
    assert session.starts == pytest.approx([0, .30])
    assert clock.delays == pytest.approx([.30])


@pytest.mark.parametrize('failure', [quota('rateLimitExceeded'), quota('userRateLimitExceeded'), Response(429), Response(503)])
def test_exponential_backoff_satisfies_pacing_without_second_sleep(failure):
    clock = FakeClock()
    session = TimedSession(clock, [failure, failure, Response(200, {})])
    client = make_client(clock, session)
    assert client.message('synthetic-message') == {}
    assert session.starts == [0, 1.5, 4.0]
    assert clock.delays == [1.5, 2.5]
    assert all(call == session.calls[0] for call in session.calls)
    # The next successful GET must still respect the last retry's actual start.
    client.session.responses.append(Response(200, {}))
    client.profile()
    assert clock.delays == pytest.approx([1.5, 2.5, .30])


@pytest.mark.parametrize('refresh', [False, True])
def test_paced_authorized_gets_keep_changed_state_only_keyring_saves(monkeypatch, caplog, refresh):
    import google.auth.transport.requests
    clock, credentials = FakeClock(), Credentials()
    session = TimedSession(clock)
    class AuthorizedSession:
        def __init__(self, credentials):
            self.credentials = credentials
        def get(self, *args, **kwargs):
            if refresh:
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
    client = make_client(clock, KeyringSession(credentials, store, ACCOUNT))
    client.profile()
    client.profile()
    assert session.starts == pytest.approx([0, .30])
    assert store.writes == int(refresh)
    assert PRIVATE not in caplog.text


def test_pacing_sleep_logs_and_failures_are_private(caplog):
    clock = FakeClock()
    session = TimedSession(clock)
    def broken_sleep(delay):
        logging.warning(PRIVATE)
        raise RuntimeError(PRIVATE)
    client = GmailHTTPClient(session, clock=clock.clock, sleep=broken_sleep)
    caplog.set_level(logging.DEBUG)
    client.profile()
    with pytest.raises(GmailAPIError) as failure:
        client.profile()
    assert PRIVATE not in str(failure.value) + caplog.text
    assert session.starts == [0]
    logging.warning('Diagnostics restored')
    assert 'Diagnostics restored' in caplog.text
