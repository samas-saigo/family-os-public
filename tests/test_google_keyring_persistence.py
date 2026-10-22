"""Changed-state persistence, synthetic credentials and GET sessions only."""
import json
import logging
from types import SimpleNamespace

import pytest

from family_os import gmail_auth, google_calendar_auth, google_drive_auth
from family_os.errors import GmailAuthError
from family_os.google_calendar_errors import CalendarAuthError, CalendarPolicyError
from family_os.google_drive_errors import DriveAuthError, DrivePolicyError
from test_gmail_auth import ACCOUNT as GMAIL_ACCOUNT, Credentials as GmailCredentials
from test_google_calendar_auth import ACCOUNT as CALENDAR_ACCOUNT, Credentials as CalendarCredentials
from test_google_drive_auth import ACCOUNT as DRIVE_ACCOUNT, Credentials as DriveCredentials, PERMISSION

CASES = [(gmail_auth, GMAIL_ACCOUNT, GmailCredentials, GmailAuthError, GmailAuthError),
         (google_calendar_auth, CALENDAR_ACCOUNT, CalendarCredentials, CalendarAuthError, CalendarPolicyError),
         (google_drive_auth, DRIVE_ACCOUNT, DriveCredentials, DriveAuthError, DrivePolicyError)]
PRIVATE = "synthetic-new-secret-token-never-log"


class Store:
    def __init__(self):
        self.writes = []
        self.fail = False
    def save(self, account, value):
        logging.getLogger("keyring").debug(value)
        if self.fail:
            raise RuntimeError(PRIVATE)
        self.writes.append((account, value))


def setup(monkeypatch, module, account, credential_type):
    import google.auth.transport.requests
    credentials = credential_type()
    state = json.loads(credentials.to_json())
    credentials.to_json = lambda: json.dumps(state)
    state["token"] = PRIVATE
    calls = []
    class Session:
        change = None
        def __init__(self, credentials):
            self.credentials = credentials
        def get(self, *args, **kwargs):
            calls.append(True)
            logging.getLogger("google.auth.transport.requests").debug(PRIVATE)
            if self.change:
                self.change()
            return SimpleNamespace(status_code=200)
        def close(self):
            pass
    monkeypatch.setattr(google.auth.transport.requests, "AuthorizedSession", Session)
    store = Store()
    args = (PERMISSION,) if module is google_drive_auth else ()
    wrapper = module.KeyringSession(credentials, store, account, *args)
    return wrapper, credentials, state, store, calls


@pytest.mark.parametrize("module,account,credentials,auth_error,scope_error", CASES)
def test_unchanged_gets_never_rewrite_keyring(module, account, credentials, auth_error, scope_error, monkeypatch, caplog):
    session, _, _, store, calls = setup(monkeypatch, module, account, credentials)
    caplog.set_level(logging.DEBUG)
    for _ in range(3):
        assert session.get("https://synthetic.invalid/metadata").status_code == 200
    assert store.writes == [] and len(calls) == 3
    assert PRIVATE not in caplog.text + repr(session)


@pytest.mark.parametrize("module,account,credentials,auth_error,scope_error", CASES)
def test_refresh_saves_once_then_unchanged_gets_do_not_save(module, account, credentials, auth_error, scope_error, monkeypatch, caplog):
    session, _, state, store, _ = setup(monkeypatch, module, account, credentials)
    caplog.set_level(logging.DEBUG)
    def refresh():
        state.update(token=PRIVATE + "-refreshed", expiry="2026-10-05T09:00:00Z")
    session.session.change = refresh
    session.get("https://synthetic.invalid/metadata")
    session.session.change = None
    session.get("https://synthetic.invalid/metadata")
    session.get("https://synthetic.invalid/metadata")
    assert len(store.writes) == 1 and store.writes[0][0] == account
    saved = json.loads(store.writes[0][1])
    if module is google_drive_auth:
        assert {k: v for k, v in saved.items() if k != "credentials"} == {
            "v": 1, "household": account.household_id, "account": account.id,
            "email": account.external_account, "permission_id": PERMISSION}
        saved = saved["credentials"]
    assert saved["token"] == PRIVATE + "-refreshed" and saved["expiry"] == "2026-10-05T09:00:00Z"
    assert PRIVATE not in caplog.text
    state["token"] = PRIVATE + "-second-refresh"
    session.get("https://synthetic.invalid/metadata")
    assert len(store.writes) == 2


@pytest.mark.parametrize("module,account,credentials,auth_error,scope_error", CASES)
@pytest.mark.parametrize("when", ["before", "after"])
@pytest.mark.parametrize("scopes", [[], ["https://www.googleapis.com/auth/drive"]])
def test_scopes_fail_closed_before_and_after_requests_without_writes(module, account, credentials, auth_error, scope_error, when, scopes, monkeypatch, caplog):
    session, credential, _, store, calls = setup(monkeypatch, module, account, credentials)
    if when == "before":
        credential.granted_scopes = scopes
    else:
        session.session.change = lambda: setattr(credential, "granted_scopes", scopes)
    with pytest.raises(scope_error) as error:
        session.get("https://synthetic.invalid/metadata")
    assert len(calls) == (0 if when == "before" else 1) and store.writes == []
    assert PRIVATE not in str(error.value) + caplog.text


@pytest.mark.parametrize("module,account,credentials,auth_error,scope_error", CASES)
def test_failed_required_save_safe_and_dirty_state_retried(module, account, credentials, auth_error, scope_error, monkeypatch, caplog):
    session, _, state, store, _ = setup(monkeypatch, module, account, credentials)
    store.fail = True
    session.session.change = lambda: state.update(token=PRIVATE + "-refresh")
    caplog.set_level(logging.DEBUG)
    with pytest.raises(auth_error) as error:
        session.get("https://synthetic.invalid/metadata")
    assert PRIVATE not in str(error.value) + caplog.text and store.writes == []
    store.fail = False; session.session.change = None
    session.get("https://synthetic.invalid/metadata")
    session.get("https://synthetic.invalid/metadata")
    assert len(store.writes) == 1 and PRIVATE + "-refresh" in store.writes[0][1]
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("module,account,credentials,auth_error,scope_error", CASES)
def test_serialization_failure_is_safe_auth_error_and_does_not_save(module, account, credentials, auth_error, scope_error, monkeypatch, caplog):
    session, credential, _, store, _ = setup(monkeypatch, module, account, credentials)
    def broken():
        raise RuntimeError(PRIVATE)
    credential.to_json = broken
    with pytest.raises(auth_error) as error:
        session.get("https://synthetic.invalid/metadata")
    assert store.writes == [] and PRIVATE not in str(error.value) + caplog.text


@pytest.mark.parametrize("module,account,credentials,auth_error,scope_error", CASES)
def test_invalid_initial_scope_fails_before_session_creation(module, account, credentials, auth_error, scope_error, monkeypatch):
    import google.auth.transport.requests
    monkeypatch.setattr(google.auth.transport.requests, "AuthorizedSession", lambda c: pytest.fail("Created session before scope validation"))
    credential = credentials(); credential.granted_scopes = []
    args = (PERMISSION,) if module is google_drive_auth else ()
    with pytest.raises(scope_error):
        module.KeyringSession(credential, Store(), account, *args)


def test_google_keyring_services_remain_distinct():
    assert len({m.OSKeyringStore.SERVICE for m, *_ in CASES}) == 3
