"""OAuth and OS-store boundaries are tested with fake credentials/clients only."""
import json
import logging
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from family_os.cli import main
from family_os.domain import SourceAccount
from family_os.google_calendar_errors import CalendarAuthError, CalendarIdentityError, CalendarPolicyError
from family_os.google_calendar import CalendarHTTPClient
from family_os.google_calendar_auth import (OSKeyringStore, SCOPES, KeyringSession,
                                 connect_account, load_client, require_readonly)
from family_os.registry import register

PRIVATE = "synthetic-access-refresh-client-secret"
ACCOUNT = SourceAccount("calendar1", "home", "google_calendar", "unknown", None, "demo@gmail.com")


class MemoryStore:
    def __init__(self):
        self.values = {}
    def load(self, account):
        return self.values.get((account.household_id, account.id))
    def save(self, account, value):
        self.values[(account.household_id, account.id)] = value


class Credentials:
    scopes = list(SCOPES)
    granted_scopes = None
    def to_json(self):
        return json.dumps({"token": PRIVATE, "refresh_token": PRIVATE, "client_secret": PRIVATE,
            "client_id": "synthetic-client", "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": self.scopes})


def fake_oauth(monkeypatch, credentials=None, email="demo@gmail.com"):
    from google_auth_oauthlib.flow import InstalledAppFlow
    import google.auth.transport.requests
    calls = []
    class Flow:
        def run_local_server(self, **kwargs):
            calls.append(kwargs)
            logging.getLogger("google_auth_oauthlib.flow").info(PRIVATE)
            return credentials if credentials is not None else Credentials()
    def factory(filename, scopes):
        calls.append((filename, scopes))
        return Flow()
    monkeypatch.setattr(InstalledAppFlow, "from_client_secrets_file", factory)
    class Session:
        def __init__(self, credentials):
            self.credentials = credentials
        def get(self, *args, **kwargs):
            class Response:
                status_code = 200
                def json(self):
                    return {"items": [{"id": email, "primary": True}], "nextSyncToken": "synthetic-sync"}
            return Response()
        def close(self):
            calls.append("closed")
    monkeypatch.setattr(google.auth.transport.requests, "AuthorizedSession", Session)
    return calls


def test_opt_in_oauth_requests_only_readonly_verifies_identity_then_saves(monkeypatch, tmp_path, caplog):
    calls = fake_oauth(monkeypatch)
    store = MemoryStore()
    caplog.set_level(logging.DEBUG)
    assert connect_account(ACCOUNT, tmp_path / "outside-repository.json", store) == "demo@gmail.com"
    assert calls[0][1] == list(SCOPES)
    assert calls[1]["host"] == "127.0.0.1" and calls[1]["port"] == 0
    assert calls[1]["access_type"] == "offline" and calls[1]["prompt"] == "consent"
    assert PRIVATE in store.load(ACCOUNT)
    assert PRIVATE not in caplog.text
    assert calls[-1] == "closed"


def test_wrong_oauth_mailbox_does_not_save_any_token(monkeypatch, tmp_path):
    fake_oauth(monkeypatch, email="other@gmail.com")
    store = MemoryStore()
    with pytest.raises(CalendarIdentityError):
        connect_account(ACCOUNT, tmp_path / "client.json", store)
    assert store.values == {}


def test_oauth_client_inside_repository_rejected_before_flow(monkeypatch):
    calls = fake_oauth(monkeypatch)
    with pytest.raises(CalendarAuthError):
        connect_account(ACCOUNT, Path(__file__).parents[1] / "fake-client.json", MemoryStore())
    assert calls == []


@pytest.mark.parametrize("scopes", [[], ["https://mail.google.com/"],
    [*SCOPES, "https://www.googleapis.com/auth/gmail.modify"]])
def test_broader_or_missing_scopes_rejected(scopes, monkeypatch, tmp_path):
    credentials = Credentials()
    credentials.granted_scopes = scopes
    with pytest.raises(CalendarPolicyError):
        require_readonly(credentials)
    fake_oauth(monkeypatch, credentials=credentials)
    store = MemoryStore()
    with pytest.raises(CalendarPolicyError):
        connect_account(ACCOUNT, tmp_path / "client.json", store)
    assert not store.values


def test_load_connection_is_account_specific_and_never_initiates_oauth(monkeypatch):
    calls = fake_oauth(monkeypatch)
    store = MemoryStore()
    store.save(ACCOUNT, Credentials().to_json())
    client = load_client(ACCOUNT, store)
    assert isinstance(client, CalendarHTTPClient)
    assert calls == []
    with pytest.raises(CalendarAuthError):
        load_client(SourceAccount("other", "home", "google_calendar", "unknown", None, "other@gmail.com"), store)
    store.save(ACCOUNT, json.dumps({"scopes": [*SCOPES, "https://mail.google.com/"]}))
    with pytest.raises(CalendarPolicyError):
        load_client(ACCOUNT, store)


def test_refreshed_credentials_saved_to_keyring_and_debug_logs_suppressed(monkeypatch, caplog):
    import google.auth.transport.requests
    credentials = Credentials()
    class Session:
        def __init__(self, credentials):
            self.credentials = credentials
        def get(self, *args, **kwargs):
            logging.getLogger("google.auth.transport.requests").debug(PRIVATE)
            self.credentials.to_json = lambda: "synthetic-new-refreshed-credential"
            return SimpleNamespace(status_code=200)
        def close(self):
            pass
    monkeypatch.setattr(google.auth.transport.requests, "AuthorizedSession", Session)
    caplog.set_level(logging.DEBUG)
    store = MemoryStore()
    session = KeyringSession(credentials, store, ACCOUNT)
    session.get("https://www.googleapis.com/calendar/v3/users/me/calendarList")
    assert store.load(ACCOUNT) == "synthetic-new-refreshed-credential"
    assert PRIVATE not in caplog.text


def test_plaintext_null_and_chainer_keyrings_fail_closed():
    for module in ["keyrings.alt.file", "keyring.backends.fail", "keyring.backends.null", "keyring.backends.chainer"]:
        backend = type("FakeBackend", (), {"__module__": module, "priority": 1})()
        with pytest.raises(CalendarAuthError):
            OSKeyringStore(backend)


def test_os_store_key_and_backend_errors_do_not_leak(caplog):
    values = {}
    class Backend:
        __module__ = "keyring.backends.SecretService"
        priority = 1
        def get_password(self, service, key):
            return values.get((service, key))
        def set_password(self, service, key, value):
            values[(service, key)] = value
    store = OSKeyringStore(Backend())
    store.save(ACCOUNT, PRIVATE)
    assert store.load(ACCOUNT) == PRIVATE
    assert next(iter(values))[0] == OSKeyringStore.SERVICE
    assert json.loads(next(iter(values))[1]) == ["home", "calendar1"]
    def broken(*args):
        raise RuntimeError(PRIVATE)
    store.backend.get_password = broken
    with pytest.raises(CalendarAuthError) as error:
        store.load(ACCOUNT)
    assert PRIVATE not in str(error.value) + caplog.text


@pytest.mark.parametrize("address", [None, "", "   "])
def test_unregistered_mailbox_reports_identity_error_before_oauth(monkeypatch, tmp_path, address):
    calls = fake_oauth(monkeypatch)
    store = MemoryStore()
    with pytest.raises(CalendarIdentityError, match="register the intended primary calendar explicitly"):
        connect_account(replace(ACCOUNT, external_account=address), tmp_path / "client.json", store)
    assert calls == []
    assert store.values == {}


def test_oauth_configuration_value_error_remains_safe_auth_error(monkeypatch, tmp_path, caplog):
    from google_auth_oauthlib.flow import InstalledAppFlow
    def invalid_config(*args, **kwargs):
        raise ValueError(PRIVATE)
    monkeypatch.setattr(InstalledAppFlow, "from_client_secrets_file", invalid_config)
    store = MemoryStore()
    with pytest.raises(CalendarAuthError) as failure:
        connect_account(ACCOUNT, tmp_path / "client.json", store)
    assert PRIVATE not in str(failure.value) + caplog.text
    assert store.values == {}


def test_identity_display_precedes_secure_save(monkeypatch, tmp_path):
    fake_oauth(monkeypatch)
    order = []
    class Store(MemoryStore):
        def save(self, account, value):
            order.append("save")
            super().save(account, value)
    store = Store()
    assert connect_account(ACCOUNT, tmp_path / "client.json", store,
        display=lambda identity: order.append(identity)) == ACCOUNT.external_account
    assert order == [ACCOUNT.external_account, "save"]


def test_calendar_keyring_separate_from_gmail_even_same_account_id():
    from family_os.gmail_auth import OSKeyringStore as GmailStore
    values = {}
    class Backend:
        __module__ = "keyring.backends.SecretService"
        priority = 1
        def get_password(self, service, key):
            return values.get((service, key))
        def set_password(self, service, key, value):
            values[(service, key)] = value
    calendar_store, gmail_store = OSKeyringStore(Backend()), GmailStore(Backend())
    gmail_store.save(ACCOUNT, "synthetic-gmail")
    assert calendar_store.load(ACCOUNT) is None
    calendar_store.save(ACCOUNT, "synthetic-calendar")
    assert gmail_store.load(ACCOUNT) == "synthetic-gmail"
    assert calendar_store.load(ACCOUNT) == "synthetic-calendar"


@pytest.mark.parametrize("scopes", [["https://www.googleapis.com/auth/calendar.readonly"],
    [*SCOPES, "https://www.googleapis.com/auth/calendar"],
    [*SCOPES, "https://www.googleapis.com/auth/drive.readonly"],
    [*SCOPES, "openid"], [SCOPES[0]]])
def test_only_exact_two_calendar_scopes_accepted(scopes):
    credentials = Credentials(); credentials.granted_scopes = scopes
    with pytest.raises(CalendarPolicyError):
        require_readonly(credentials)


@pytest.mark.parametrize("change", [{"provider": "gmail"}, {"enabled": False}, {"external_account": None}])
def test_invalid_registration_fails_before_oauth_or_store_load(change, monkeypatch, tmp_path):
    calls = fake_oauth(monkeypatch)
    store = MemoryStore()
    with pytest.raises(CalendarIdentityError):
        connect_account(replace(ACCOUNT, **change), tmp_path / "client.json", store)
    with pytest.raises(CalendarIdentityError):
        load_client(replace(ACCOUNT, **change), store)
    assert calls == [] and store.values == {}


def test_cli_missing_registry_fails_before_oauth(engine, monkeypatch, tmp_path):
    calls = fake_oauth(monkeypatch)
    assert main(["google-calendar-connect", "--household", "missing", "--account", "missing",
                 "--client-file", str(tmp_path / "client.json")]) == 1
    assert calls == []


def test_cli_calendar_safe_identity_counts_and_cleanup(engine, monkeypatch, capsys):
    import family_os.google_calendar_auth
    from test_google_calendar import FakeCalendar, config
    register(engine, config())
    fake = FakeCalendar(); closed = []
    fake.session = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(family_os.google_calendar_auth, "load_client", lambda account: fake)
    assert main(["ingest-google-calendar", "--household", "home", "--account", "cal"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Authenticated primary Calendar identity: demo@example.invalid"
    assert json.loads(lines[1])["inserted"] == 1
    assert all(value not in str(lines) for value in ("Synthetic meeting", "guest@example.invalid", PRIVATE))
    assert closed == [True]
    assert main(["google-calendar-resync", "--household", "home", "--account", "cal", "--calendar-list"]) == 0
    assert "historical records retained" in capsys.readouterr().out
