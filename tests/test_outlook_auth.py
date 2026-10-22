"""Fake MSAL/cache/keyring and HTTP; no live sign-in or Graph access."""
from dataclasses import replace
import json
import logging
from types import SimpleNamespace

import pytest

from family_os.domain import SourceAccount
from family_os.outlook_auth import (connect_account, load_client, OutlookKeyringStore,
    MSALSession, READ_BASIC_SCOPE, DEFAULT_AUTHORITY, require_scopes, validate_authority)
from family_os.outlook_errors import (OutlookAuthError, OutlookIdentityError, OutlookPolicyError)
from family_os.registry import register
from family_os.cli import main

CLIENT_ID = "11111111-1111-4111-8111-111111111111"
PRIVATE = "synthetic-private-access-refresh-idtoken-MSAL-cache"
ACCOUNT = SourceAccount("out1", "home", "outlook", "person", "alex", "alex@outlook.com")


class MemoryStore:
    def __init__(self):
        self.values, self.saves = {}, []
    def load(self, account):
        return self.values.get((account.household_id, account.id))
    def save(self, account, value):
        self.values[(account.household_id, account.id)] = value
        self.saves.append(value)


def fake_msal(monkeypatch, username="alex@outlook.com", scope="Mail.ReadBasic openid profile offline_access"):
    import msal
    calls, apps = [], []
    class Cache:
        has_state_changed = False
        def __init__(self):
            self.accounts = []
        def serialize(self):
            self.has_state_changed = False
            return json.dumps({"accounts": self.accounts, "token": PRIVATE})
        def deserialize(self, value):
            self.accounts = json.loads(value)["accounts"]
    class App:
        def __init__(self, client_id, **kwargs):
            calls.append(("app", client_id, kwargs))
            self.cache = kwargs["token_cache"]
            self.result = {"access_token": PRIVATE, "scope": scope,
                           "id_token_claims": {"preferred_username": username, "oid": "local-id", "tid": "tenant"}}
            apps.append(self)
        def get_accounts(self):
            return self.cache.accounts
        def acquire_token_interactive(self, **kwargs):
            calls.append(("interactive", kwargs))
            logging.getLogger("msal.fake").warning(PRIVATE)
            self.cache.accounts = [{"username": username, "home_account_id": "stable-home-id",
                                    "local_account_id": "local-id", "realm": "tenant"}]
            return self.result
        def acquire_token_silent(self, scopes, account):
            calls.append(("silent", scopes, account))
            logging.getLogger("msal.fake").warning(PRIVATE)
            return self.result
    monkeypatch.setattr(msal, "SerializableTokenCache", Cache)
    monkeypatch.setattr(msal, "PublicClientApplication", App)
    return calls, apps


def connected(monkeypatch):
    calls, apps = fake_msal(monkeypatch)
    store = MemoryStore()
    connect_account(ACCOUNT, CLIENT_ID, store=store, show_identity=lambda _: None)
    return store, calls, apps


@pytest.mark.parametrize("address", [None, "", "bad", "   "])
def test_missing_registration_fails_before_interactive_or_keyring(monkeypatch, address):
    calls, _ = fake_msal(monkeypatch)
    store = MemoryStore()
    with pytest.raises(OutlookIdentityError):
        connect_account(replace(ACCOUNT, external_account=address), CLIENT_ID, store=store)
    assert calls == [] and not store.saves


@pytest.mark.parametrize("username, authority", [("alex@outlook.com", DEFAULT_AUTHORITY),
    ("alex@work.example.invalid", "https://login.microsoftonline.com/organizations"),
    ("alex@hotmail.com", "https://login.microsoftonline.com/consumers")])
def test_explicit_connect_approved_scopes_identity_before_secure_cache(monkeypatch, caplog, username, authority):
    calls, _ = fake_msal(monkeypatch, username)
    store = MemoryStore()
    target = replace(ACCOUNT, external_account=username.upper())
    shown = []
    def show(text):
        assert not store.saves
        shown.append(text)
    assert connect_account(target, CLIENT_ID, authority, store, show) == username
    assert shown == [f"Signed-in Microsoft account: {username}"]
    assert calls[0][2]["authority"] == authority
    assert "client_credential" not in calls[0][2]
    assert calls[1][1]["scopes"] == [READ_BASIC_SCOPE]
    payload = json.loads(store.load(target))
    assert payload["home_account_id"] == "stable-home-id"
    assert payload["account"] == ACCOUNT.id and payload["household"] == ACCOUNT.household_id
    assert "client_secret" not in payload
    assert PRIVATE in payload["cache"] and PRIVATE not in caplog.text


def test_wrong_signin_identity_never_saves_cache(monkeypatch):
    fake_msal(monkeypatch, "other@outlook.com")
    store, shown = MemoryStore(), []
    with pytest.raises(OutlookIdentityError):
        connect_account(ACCOUNT, CLIENT_ID, store=store, show_identity=shown.append)
    assert shown == ["Signed-in Microsoft account: other@outlook.com"]
    assert not store.values


@pytest.mark.parametrize("scope", ["Mail.Read", "Mail.ReadWrite", "Mail.Send", "Mail.ReadBasic.Shared",
    "Mail.Read.Shared", "Mail.ReadBasic Mail.Read", "Mail.ReadBasic User.Read", "", "openid profile"])
def test_non_basic_permissions_rejected_before_binding(monkeypatch, scope):
    fake_msal(monkeypatch, scope=scope)
    store = MemoryStore()
    with pytest.raises(OutlookPolicyError):
        connect_account(ACCOUNT, CLIENT_ID, store=store, show_identity=lambda _: None)
    assert not store.saves


@pytest.mark.parametrize("result, error", [(None, OutlookAuthError),
    ({"error": "access_denied", "error_description": PRIVATE}, OutlookPolicyError),
    ({"error": "invalid_grant", "error_description": PRIVATE}, OutlookAuthError)])
def test_auth_errors_do_not_expose_msal_text(result, error):
    with pytest.raises(error) as failure:
        require_scopes(result)
    assert PRIVATE not in str(failure.value)


def test_load_only_account_cache_and_never_interactive(monkeypatch):
    store, calls, _ = connected(monkeypatch)
    calls.clear()
    client = load_client(ACCOUNT, store)
    assert [call[0] for call in calls] == ["app"]
    username, fingerprint = client.identity()
    assert username == ACCOUNT.external_account
    assert len(fingerprint) == 64 and "stable-home-id" not in fingerprint
    with pytest.raises(OutlookAuthError):
        load_client(replace(ACCOUNT, id="other"), store)
    with pytest.raises(OutlookAuthError):
        load_client(replace(ACCOUNT, household_id="other"), store)
    client.session.close()


@pytest.mark.parametrize("change", ["home", "username", "switched-account"])
def test_loaded_connection_never_switches_cached_accounts(monkeypatch, change):
    store, calls, apps = connected(monkeypatch)
    client = load_client(ACCOUNT, store)
    app = apps[-1]
    if change == "home":
        app.cache.accounts[0]["home_account_id"] = "other-home-id"
    elif change == "username":
        app.cache.accounts[0]["username"] = "other@outlook.com"
    else:
        app.cache.accounts = [{"home_account_id": "other-home-id", "username": "other@outlook.com"}]
    calls.clear()
    with pytest.raises(OutlookIdentityError):
        client.session.get("https://graph.microsoft.com/v1.0/me/mailFolders")
    assert not calls
    assert len(store.saves) == 1
    client.session.close()


@pytest.mark.parametrize("field, value", [("preferred_username", "other@outlook.com"),
    ("oid", "other-local-id"), ("tid", "other-tenant")])
def test_silent_result_identity_claims_cannot_switch_account(monkeypatch, field, value):
    store, _, apps = connected(monkeypatch)
    client = load_client(ACCOUNT, store)
    apps[-1].result["id_token_claims"][field] = value
    with pytest.raises(OutlookIdentityError):
        client.session.get("https://graph.microsoft.com/v1.0/me/mailFolders")
    assert len(store.saves) == 1
    client.session.close()


def test_silent_only_request_and_refreshed_cache_persistence_suppresses_logs(monkeypatch, caplog):
    store, calls, apps = connected(monkeypatch)
    client = load_client(ACCOUNT, store)
    observed = []
    class HTTP:
        def get(self, url, **kwargs):
            assert len(store.saves) == 2  # Refreshed cache saved before Graph I/O.
            logging.getLogger("requests.fake").warning(PRIVATE)
            observed.append(kwargs)
            return SimpleNamespace(status_code=200)
        def close(self):
            pass
    client.session.http = HTTP()
    apps[-1].cache.has_state_changed = True
    calls.clear()
    caplog.set_level(logging.DEBUG)
    client.session.get("https://graph.microsoft.com/v1.0/me/mailFolders", headers={"Prefer": 'IdType="ImmutableId"'})
    assert calls[0][0] == "silent" and calls[0][1] == [READ_BASIC_SCOPE]
    assert calls[0][2]["home_account_id"] == "stable-home-id"
    assert observed[0]["headers"]["Authorization"] == "Bearer " + PRIVATE
    assert PRIVATE not in caplog.text
    logging.warning("Diagnostics restored")
    assert "Diagnostics restored" in caplog.text


def test_no_silent_token_requires_explicit_reconnect(monkeypatch):
    store, calls, apps = connected(monkeypatch)
    client = load_client(ACCOUNT, store)
    apps[-1].result = None
    calls.clear()
    with pytest.raises(OutlookAuthError):
        client.session.get("https://graph.microsoft.com/v1.0/me/mailFolders")
    assert [call[0] for call in calls] == ["silent"]
    client.session.close()


@pytest.mark.parametrize("field, value, error", [("v", True, OutlookAuthError), ("v", 9, OutlookAuthError),
    ("account", "other", OutlookIdentityError),
    ("household", "other", OutlookIdentityError), ("home_account_id", "other", OutlookIdentityError),
    ("username", "other@outlook.com", OutlookIdentityError), ("client_secret", PRIVATE, OutlookAuthError)])
def test_cache_binding_and_secret_payload_rejected(monkeypatch, field, value, error):
    store, _, _ = connected(monkeypatch)
    payload = json.loads(store.load(ACCOUNT))
    payload[field] = value
    store.save(ACCOUNT, json.dumps(payload))
    with pytest.raises(error):
        load_client(ACCOUNT, store)


@pytest.mark.parametrize("authority", ["http://login.microsoftonline.com/common",
    "https://evil.invalid/common", "https://login.microsoftonline.com@evil.invalid/common",
    "https://login.microsoftonline.com/common?secret=bad", "https://login.microsoftonline.com/common/path"])
def test_authority_rejected_before_msal_network(monkeypatch, authority):
    calls, _ = fake_msal(monkeypatch)
    with pytest.raises(OutlookAuthError):
        connect_account(ACCOUNT, CLIENT_ID, authority, MemoryStore())
    assert calls == []


@pytest.mark.parametrize("module", ["keyrings.alt.file", "keyring.backends.null", "keyring.backends.chainer", "keyring.backends.fail"])
def test_unsafe_keyrings_fail_closed(module):
    backend = type("FakeBackend", (), {"__module__": module, "priority": 1})()
    with pytest.raises(OutlookAuthError):
        OutlookKeyringStore(backend)


def test_secure_keyring_service_account_scoping_and_safe_failures():
    values = {}
    class Backend:
        __module__ = "keyring.backends.SecretService"
        priority = 1
        def get_password(self, service, key):
            return values.get((service, key))
        def set_password(self, service, key, value):
            values[(service, key)] = value
    store = OutlookKeyringStore(Backend())
    store.save(ACCOUNT, PRIVATE)
    assert store.load(ACCOUNT) == PRIVATE
    assert next(iter(values))[0] == "family-os/outlook.Mail.ReadBasic/v1"
    assert json.loads(next(iter(values))[1]) == ["home", "out1"]
    assert store.load(replace(ACCOUNT, id="out2")) is None
    def broken(*args):
        raise RuntimeError(PRIVATE)
    store.backend.get_password = broken
    with pytest.raises(OutlookAuthError) as failure:
        store.load(ACCOUNT)
    assert PRIVATE not in str(failure.value)


def test_outlook_cli_identity_before_aggregate_counts(engine, monkeypatch, capsys):
    from test_outlook import FakeGraph
    import family_os.outlook_auth
    client = FakeGraph()
    client.session = SimpleNamespace(close=lambda: None)
    register(engine, {"household": {"id": "home", "name": "Synthetic"},
        "source_accounts": [{"id": "out1", "provider": "outlook", "owner_type": "unknown", "external_account": ACCOUNT.external_account}]})
    monkeypatch.setattr(family_os.outlook_auth, "load_client", lambda account: client)
    assert main(["ingest-outlook", "--household", "home", "--account", "out1", "--include-folder", "inbox"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert output[0] == "Authenticated Microsoft account: alex@outlook.com"
    assert json.loads(output[1])["inserted"] == 1
    assert PRIVATE not in str(output) and "Synthetic subject" not in str(output)


def test_failed_refresh_keyring_save_retains_dirty_cache_for_retry(monkeypatch):
    store, _, apps = connected(monkeypatch)
    client = load_client(ACCOUNT, store)
    calls = []
    client.session.http = SimpleNamespace(get=lambda *a, **kw: calls.append("http"), close=lambda: None)
    apps[-1].cache.has_state_changed = True
    saved = client.session.payload["cache"]
    store.save = lambda *args: (_ for _ in ()).throw(RuntimeError(PRIVATE))
    with pytest.raises(OutlookAuthError):
        client.session.get("https://graph.microsoft.com/v1.0/me/mailFolders")
    assert not calls
    assert apps[-1].cache.has_state_changed is True
    assert client.session.payload["cache"] == saved


def test_graph_network_failure_is_retryable_without_private_exception_text(monkeypatch):
    from family_os.outlook_errors import OutlookAPIError
    store, _, _ = connected(monkeypatch)
    client = load_client(ACCOUNT, store)
    def broken(*args, **kwargs):
        raise RuntimeError(PRIVATE)
    client.session.http = SimpleNamespace(get=broken, close=lambda: None)
    with pytest.raises(OutlookAPIError, match="retryable") as failure:
        client.session.get("https://graph.microsoft.com/v1.0/me/mailFolders")
    assert PRIVATE not in str(failure.value)
