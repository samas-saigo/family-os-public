"""Opt-in local OAuth; credentials stay in an OS keyring, outside registry/DB/Git."""
from pathlib import Path
from typing import Protocol

from .google_calendar_errors import CalendarAuthError, CalendarError, CalendarIdentityError, CalendarPolicyError
from .google_calendar import GoogleCalendarConnector, CalendarHTTPClient
from .google_calendar_identity import require_calendar_account, calendar_identity
from .gmail_privacy import private_transport

SCOPES = ("https://www.googleapis.com/auth/calendar.calendarlist.readonly",
          "https://www.googleapis.com/auth/calendar.events.readonly")


class TokenStore(Protocol):
    def load(self, account) -> str | None: ...
    def save(self, account, value: str) -> None: ...


class OSKeyringStore:
    """Fail closed on unsupported/plaintext/null backends; no file fallback."""
    SERVICE = "family-os/google-calendar.readonly/v1"
    SECURE_MODULES = frozenset({"keyring.backends.SecretService", "keyring.backends.libsecret",
        "keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.kwallet"})

    def __init__(self, backend=None):
        try:
            if backend is None:
                import keyring
                backend = keyring.get_keyring()
            if type(backend).__module__ not in self.SECURE_MODULES or backend.priority <= 0:
                raise CalendarAuthError()
            self.backend = backend
        except Exception:
            raise CalendarAuthError() from None

    @staticmethod
    def _key(account):
        # JSON avoids ambiguous concatenated household/account IDs.
        import json
        return json.dumps([account.household_id, account.id], separators=(",", ":"))

    def load(self, account):
        try:
            return self.backend.get_password(self.SERVICE, self._key(account))
        except Exception:
            raise CalendarAuthError() from None

    def save(self, account, value):
        try:
            self.backend.set_password(self.SERVICE, self._key(account), value)
        except Exception:
            raise CalendarAuthError() from None


def require_readonly(credentials):
    # Reject cached/consented broader scopes, even if they include readonly.
    scopes = credentials.granted_scopes if credentials.granted_scopes is not None else credentials.scopes
    if set(scopes or []) != set(SCOPES):
        raise CalendarPolicyError()


class KeyringSession:
    """Authorized GET session; persist renewed tokens back to keyring, never disk."""
    def __init__(self, credentials, store, account):
        from google.auth.transport.requests import AuthorizedSession
        require_readonly(credentials)
        self.credentials, self.store, self.account = credentials, store, account
        try:
            self._saved_state = credentials.to_json()
        except CalendarError:
            raise
        except Exception:
            raise CalendarAuthError() from None
        self.session = AuthorizedSession(credentials)

    @private_transport
    def get(self, url, **kwargs):
        try:
            require_readonly(self.credentials)
            response = self.session.get(url, **kwargs)
            require_readonly(self.credentials)
            state = self.credentials.to_json()
            if state != self._saved_state:
                self.store.save(self.account, state)
                self._saved_state = state  # Advance only after a successful secure save.
            return response
        except CalendarError:
            raise
        except Exception:
            raise CalendarAuthError() from None

    def close(self):
        self.session.close()


def load_client(account, store=None):
    require_calendar_account(account)
    try:
        import json
        from google.oauth2.credentials import Credentials
        store = store if store is not None else OSKeyringStore()
        value = store.load(account)
        if not value:
            raise CalendarAuthError()
        info = json.loads(value)
        if set(info.get("scopes", [])) != set(SCOPES):
            raise CalendarPolicyError()
        credentials = Credentials.from_authorized_user_info(info)
        return CalendarHTTPClient(KeyringSession(credentials, store, account))
    except CalendarError:
        raise
    except Exception:
        raise CalendarAuthError() from None


@private_transport
def connect_account(account, client_file, store=None, display=None):
    """Explicit desktop OAuth; show the primary identity before secure binding."""
    require_calendar_account(account)  # Validate provider/enabled/identity before OAuth.
    client = None
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import AuthorizedSession
        path = Path(client_file).expanduser().resolve()
        repository = Path(__file__).resolve().parents[2]
        if path.is_relative_to(repository):
            raise CalendarAuthError()
        store = store if store is not None else OSKeyringStore()
        flow = InstalledAppFlow.from_client_secrets_file(str(path), scopes=list(SCOPES))
        credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True,
            timeout_seconds=180, authorization_prompt_message="Open this read-only OAuth URL: {url}",
            access_type="offline", prompt="consent")
        require_readonly(credentials)
        client = CalendarHTTPClient(AuthorizedSession(credentials))
        primary = GoogleCalendarConnector(client).primary_identity(account)
        if display is None:
            print(f"Authenticated primary Calendar identity: {primary}", flush=True)
        else:
            display(primary)
        if calendar_identity(primary) != require_calendar_account(account):
            raise CalendarIdentityError()
        store.save(account, credentials.to_json())
        return primary
    except CalendarError:
        raise
    except Exception:
        raise CalendarAuthError() from None
    finally:
        if client is not None:
            try:
                client.session.close()
            except Exception:
                pass
