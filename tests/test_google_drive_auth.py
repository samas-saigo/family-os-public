"""OAuth/security boundaries use fake credentials, sessions and stores only."""
from dataclasses import replace
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from family_os.cli import main
from family_os.google_drive_auth import (OSKeyringStore, SCOPE, KeyringSession, connect_account,
    load_client, load_binding, connection_value, require_metadata_scope)
from family_os.google_drive import GoogleDriveConnector, DriveHTTPClient, binding_fingerprint
from family_os.google_drive_errors import DriveAuthError, DriveIdentityError, DrivePolicyError
from test_google_drive import ACCOUNT, PERMISSION, PRIVATE, FakeDrive, config
from family_os.registry import register


class MemoryStore:
    def __init__(self):
        self.values = {}
    def load(self, account):
        return self.values.get((account.household_id, account.id))
    def save(self, account, value):
        self.values[(account.household_id, account.id)] = value


class Credentials:
    scopes = [SCOPE]
    granted_scopes = None
    def to_json(self):
        return json.dumps({"token": PRIVATE, "refresh_token": PRIVATE, "client_secret": PRIVATE,
            "client_id": "synthetic-client", "token_uri": "https://oauth2.googleapis.com/token", "scopes": self.scopes})


def fake_oauth(monkeypatch, credentials=None, user=None):
    from google_auth_oauthlib.flow import InstalledAppFlow
    import google.auth.transport.requests
    calls = []
    class Flow:
        def run_local_server(self, **kwargs):
            calls.append(("oauth", kwargs))
            logging.getLogger("google_auth_oauthlib.flow").info(PRIVATE)
            return credentials if credentials is not None else Credentials()
    def factory(filename, scopes):
        calls.append(("factory", filename, scopes))
        return Flow()
    monkeypatch.setattr(InstalledAppFlow, "from_client_secrets_file", factory)
    class Session:
        def __init__(self, credentials):
            self.credentials = credentials
        def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            return SimpleNamespace(status_code=200, json=lambda: {"user": user if user is not None else {
                "permissionId": PERMISSION, "emailAddress": ACCOUNT.external_account, "me": True}})
        def close(self):
            calls.append(("close",))
    monkeypatch.setattr(google.auth.transport.requests, "AuthorizedSession", Session)
    return calls


def test_explicit_oauth_exact_scope_shows_identity_then_saves_secure_binding(monkeypatch, tmp_path, caplog):
    calls = fake_oauth(monkeypatch); caplog.set_level(logging.DEBUG)
    order = []
    class Store(MemoryStore):
        def save(self, account, value):
            order.append("save"); super().save(account, value)
    store = Store()
    assert connect_account(ACCOUNT, tmp_path / "client.json", store, display=lambda email: order.append(email)) == ACCOUNT.external_account
    assert calls[0][2] == [SCOPE]
    assert calls[1][1]["host"] == "127.0.0.1" and calls[1][1]["access_type"] == "offline"
    assert order == [ACCOUNT.external_account, "save"]
    value = json.loads(store.load(ACCOUNT))
    assert value["permission_id"] == PERMISSION and value["email"] == ACCOUNT.external_account
    assert value["household"] == ACCOUNT.household_id and value["account"] == ACCOUNT.id
    assert value["credentials"]["scopes"] == [SCOPE]
    assert PRIVATE not in caplog.text and calls[-1] == ("close",)


@pytest.mark.parametrize("user", [
    {"permissionId": PERMISSION, "emailAddress": "wrong@example.invalid", "me": True},
    {"permissionId": "", "emailAddress": ACCOUNT.external_account, "me": True},
    {"permissionId": PERMISSION, "emailAddress": "", "me": True},
    {"permissionId": PERMISSION, "emailAddress": ACCOUNT.external_account, "me": False}, {},
])
def test_wrong_or_missing_authenticated_identity_saves_no_token(user, monkeypatch, tmp_path):
    fake_oauth(monkeypatch, user=user); store = MemoryStore()
    with pytest.raises(DriveIdentityError):
        connect_account(ACCOUNT, tmp_path / "client.json", store, display=lambda email: None)
    assert store.values == {}


@pytest.mark.parametrize("scopes", [[], ["https://www.googleapis.com/auth/drive.readonly"],
    ["https://www.googleapis.com/auth/drive"], ["https://www.googleapis.com/auth/drive.file"],
    [SCOPE, "https://www.googleapis.com/auth/gmail.readonly"], [SCOPE, "openid"],
    [SCOPE, "https://www.googleapis.com/auth/documents.readonly"],
    [SCOPE, "https://www.googleapis.com/auth/spreadsheets.readonly"],
    [SCOPE, "https://www.googleapis.com/auth/presentations.readonly"]])
def test_exact_granted_scope_only(scopes, monkeypatch, tmp_path):
    credentials = Credentials(); credentials.granted_scopes = scopes
    with pytest.raises(DrivePolicyError):
        require_metadata_scope(credentials)
    fake_oauth(monkeypatch, credentials=credentials); store = MemoryStore()
    with pytest.raises(DrivePolicyError):
        connect_account(ACCOUNT, tmp_path / "client.json", store, display=lambda email: None)
    assert store.values == {}


@pytest.mark.parametrize("changes", [{"provider": "gmail"}, {"enabled": False}, {"external_account": None},
    {"external_account": ""}, {"external_account": "not-an-email"}])
def test_invalid_registration_fails_before_oauth_and_store_load(changes, monkeypatch, tmp_path):
    calls = fake_oauth(monkeypatch); store = MemoryStore()
    with pytest.raises(DriveIdentityError):
        connect_account(replace(ACCOUNT, **changes), tmp_path / "client.json", store, display=lambda email: None)
    with pytest.raises(DriveIdentityError):
        load_client(replace(ACCOUNT, **changes), store)
    assert calls == [] and store.values == {}


def test_repository_client_json_rejected_before_oauth(monkeypatch):
    calls = fake_oauth(monkeypatch)
    with pytest.raises(DriveAuthError):
        connect_account(ACCOUNT, Path(__file__).parents[1] / "client.json", MemoryStore(), display=lambda email: None)
    assert calls == []


def test_load_binding_and_client_are_account_specific_and_never_interactive(monkeypatch):
    calls = fake_oauth(monkeypatch); store = MemoryStore()
    store.save(ACCOUNT, connection_value(ACCOUNT, PERMISSION, Credentials()))
    assert load_binding(ACCOUNT, store) == binding_fingerprint(PERMISSION)
    client = load_client(ACCOUNT, store)
    assert isinstance(client, DriveHTTPClient) and client.bound_permission_id == PERMISSION
    assert calls == []
    assert GoogleDriveConnector(client).verify_account(ACCOUNT)[1] == binding_fingerprint(PERMISSION)
    with pytest.raises(DriveAuthError):
        load_client(replace(ACCOUNT, id="other"), store)
    store.save(replace(ACCOUNT, id="other"), store.load(ACCOUNT))
    with pytest.raises(DriveIdentityError):
        load_client(replace(ACCOUNT, id="other"), store)


@pytest.mark.parametrize("mutate,error", [
    (lambda x: x.update(v=True), DriveIdentityError), (lambda x: x.update(account="other"), DriveIdentityError),
    (lambda x: x.update(household="other"), DriveIdentityError), (lambda x: x.update(email="other@example.invalid"), DriveIdentityError),
    (lambda x: x.update(permission_id=""), DriveAuthError), (lambda x: x.update(extra=PRIVATE), DriveAuthError),
    (lambda x: x["credentials"].update(scopes=[]), DrivePolicyError),
    (lambda x: x["credentials"].update(scopes=[SCOPE, "https://www.googleapis.com/auth/drive.readonly"]), DrivePolicyError)])
def test_corrupt_or_broad_cached_connection_fails_closed(mutate, error, monkeypatch):
    calls = fake_oauth(monkeypatch); store = MemoryStore(); value = json.loads(connection_value(ACCOUNT, PERMISSION, Credentials()))
    mutate(value); store.save(ACCOUNT, json.dumps(value))
    with pytest.raises(error) as failure:
        load_client(ACCOUNT, store)
    assert PRIVATE not in str(failure.value) and calls == []


def test_refresh_save_preserves_stable_binding_and_account_key(monkeypatch, caplog):
    import google.auth.transport.requests
    credentials = Credentials()
    class Session:
        def __init__(self, credentials):
            self.credentials = credentials
        def get(self, *args, **kwargs):
            logging.getLogger("google.auth.transport.requests").debug(PRIVATE)
            self.credentials.to_json = lambda: json.dumps({"token": "refreshed-synthetic", "scopes": [SCOPE]})
            return SimpleNamespace(status_code=200)
        def close(self):
            pass
    monkeypatch.setattr(google.auth.transport.requests, "AuthorizedSession", Session)
    caplog.set_level(logging.DEBUG); store = MemoryStore()
    KeyringSession(credentials, store, ACCOUNT, PERMISSION).get("https://www.googleapis.com/drive/v3/about")
    value = json.loads(store.load(ACCOUNT))
    assert value["permission_id"] == PERMISSION and value["credentials"]["token"] == "refreshed-synthetic"
    assert set(store.values) == {(ACCOUNT.household_id, ACCOUNT.id)} and PRIVATE not in caplog.text


@pytest.mark.parametrize("module", ["keyrings.alt.file", "keyring.backends.null", "keyring.backends.fail", "keyring.backends.chainer"])
def test_insecure_keyrings_rejected(module):
    backend = type("FakeBackend", (), {"__module__": module, "priority": 1})()
    with pytest.raises(DriveAuthError):
        OSKeyringStore(backend)


def test_native_store_isolated_from_gmail_and_calendar_and_failures_safe():
    from family_os.gmail_auth import OSKeyringStore as GmailStore
    from family_os.google_calendar_auth import OSKeyringStore as CalendarStore
    values = {}
    class Backend:
        __module__ = "keyring.backends.SecretService"
        priority = 1
        def get_password(self, service, key):
            return values.get((service, key))
        def set_password(self, service, key, value):
            values[(service, key)] = value
    backend = Backend(); drive, gmail, calendar = OSKeyringStore(backend), GmailStore(backend), CalendarStore(backend)
    gmail.save(ACCOUNT, "gmail-synthetic"); calendar.save(ACCOUNT, "calendar-synthetic")
    assert drive.load(ACCOUNT) is None
    drive.save(ACCOUNT, "drive-synthetic")
    assert gmail.load(ACCOUNT) == "gmail-synthetic" and calendar.load(ACCOUNT) == "calendar-synthetic"
    assert json.loads(OSKeyringStore._key(ACCOUNT)) == [ACCOUNT.household_id, ACCOUNT.id]
    def broken(*args):
        raise RuntimeError(PRIVATE)
    backend.get_password = broken
    backend.set_password = broken
    for operation in (lambda: drive.load(ACCOUNT), lambda: drive.save(ACCOUNT, PRIVATE)):
        with pytest.raises(DriveAuthError) as failure:
            operation()
        assert PRIVATE not in str(failure.value)


def test_cli_missing_registration_before_oauth(engine, monkeypatch, tmp_path):
    calls = fake_oauth(monkeypatch)
    assert main(["google-drive-connect", "--household", "missing", "--account", "missing", "--client-file", str(tmp_path / "client.json")]) == 1
    assert calls == []


def test_cli_ingestion_aggregate_only_and_local_recovery_policy(engine, monkeypatch, capsys):
    import family_os.google_drive_auth
    register(engine, config()); fake = FakeDrive(); closed = []
    fake.session = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(family_os.google_drive_auth, "load_client", lambda account: fake)
    monkeypatch.setattr(family_os.google_drive_auth, "load_binding", lambda account: binding_fingerprint(PERMISSION))
    assert main(["ingest-google-drive", "--household", "home", "--account", "drive"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["inserted"] == 1 and closed == [True]
    assert all(value not in output for value in (PRIVATE, ACCOUNT.external_account, "Synthetic file", PERMISSION))
    before = list(fake.calls)
    assert main(["google-drive-resync", "--household", "home", "--account", "drive", "--personal"]) == 0
    assert main(["google-drive-policy", "--household", "home", "--account", "drive", "--include-shared-drive", "A"]) == 0
    assert fake.calls == before
    assert "historical records retained" in capsys.readouterr().out


def test_cli_connect_identity_display_before_save(engine, monkeypatch, tmp_path, capsys):
    import family_os.google_drive_auth
    register(engine, config()); calls = fake_oauth(monkeypatch); store = MemoryStore()
    real_connect = connect_account
    monkeypatch.setattr(family_os.google_drive_auth, "connect_account", lambda a, p, display: real_connect(a, p, store, display=display))
    assert main(["google-drive-connect", "--household", "home", "--account", "drive", "--client-file", str(tmp_path / "client.json")]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [f"Authenticated Drive email: {ACCOUNT.external_account}", "Connected with drive.metadata.readonly"]
    assert json.loads(store.load(ACCOUNT))["permission_id"] == PERMISSION
    assert calls[0][2] == [SCOPE]
