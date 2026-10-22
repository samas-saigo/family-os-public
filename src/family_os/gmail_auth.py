"""Opt-in local OAuth; credentials stay in an OS keyring, outside registry/DB/Git."""
from pathlib import Path
from typing import Protocol

from .errors import GmailAuthError, GmailError, MailboxIdentityError
from .gmail import GmailConnector, GmailHTTPClient
from .gmail_privacy import private_transport
from .gmail_transport import transport_get

READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class TokenStore(Protocol):
    def load(self, account) -> str | None: ...
    def save(self, account, value: str) -> None: ...


class OSKeyringStore:
    """Fail closed on unsupported/plaintext/null backends; no file fallback."""
    SERVICE = "family-os/gmail.readonly/v1"
    SECURE_MODULES = frozenset({"keyring.backends.SecretService", "keyring.backends.libsecret",
        "keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.kwallet"})

    def __init__(self, backend=None):
        try:
            if backend is None:
                import keyring
                backend = keyring.get_keyring()
            if type(backend).__module__ not in self.SECURE_MODULES or backend.priority <= 0:
                raise GmailAuthError()
            self.backend = backend
        except Exception:
            raise GmailAuthError() from None

    @staticmethod
    def _key(account):
        # JSON avoids ambiguous concatenated household/account IDs.
        import json
        return json.dumps([account.household_id, account.id], separators=(",", ":"))

    def load(self, account):
        try:
            return self.backend.get_password(self.SERVICE, self._key(account))
        except Exception:
            raise GmailAuthError() from None

    def save(self, account, value):
        try:
            self.backend.set_password(self.SERVICE, self._key(account), value)
        except Exception:
            raise GmailAuthError() from None


def require_readonly(credentials):
    # Reject cached/consented broader scopes, even if they include readonly.
    scopes = credentials.granted_scopes if credentials.granted_scopes is not None else credentials.scopes
    if set(scopes or []) != {READONLY_SCOPE}:
        raise GmailAuthError()


class KeyringSession:
    """Authorized GET session; persist renewed tokens back to keyring, never disk."""
    def __init__(self, credentials, store, account):
        from google.auth.transport.requests import AuthorizedSession
        require_readonly(credentials)
        self.credentials, self.store, self.account = credentials, store, account
        try:
            self._saved_state = credentials.to_json()
        except GmailError:
            raise
        except Exception:
            raise GmailAuthError() from None
        self.session = AuthorizedSession(credentials)

    @private_transport
    def get(self, url, **kwargs):
        try:
            require_readonly(self.credentials)
            response = transport_get(self.session, url, **kwargs)
            require_readonly(self.credentials)
            state = self.credentials.to_json()
            if state != self._saved_state:
                self.store.save(self.account, state)
                self._saved_state = state  # Advance only after a successful secure save.
            return response
        except GmailError:
            raise
        except Exception:
            raise GmailAuthError() from None

    def close(self):
        self.session.close()


def load_client(account, store=None):
    try:
        import json
        from google.oauth2.credentials import Credentials
        store = store if store is not None else OSKeyringStore()
        value = store.load(account)
        if not value:
            raise GmailAuthError()
        info = json.loads(value)
        if set(info.get("scopes", [])) != {READONLY_SCOPE}:
            raise GmailAuthError()
        credentials = Credentials.from_authorized_user_info(info)
        return GmailHTTPClient(KeyringSession(credentials, store, account))
    except GmailError:
        raise
    except Exception:
        raise GmailAuthError() from None


@private_transport
def connect_account(account, client_file, store=None):
    """User-invoked OAuth; verify profile before storing any connection."""
    client = None
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import AuthorizedSession
        from .gmail_identity import mailbox_identity
        try:
            mailbox_identity(account.external_account)  # No silent identity registration.
        except ValueError:
            raise MailboxIdentityError() from None
        path = Path(client_file).expanduser().resolve()
        repository = Path(__file__).resolve().parents[2]
        if path.is_relative_to(repository):
            raise GmailAuthError()
        store = store if store is not None else OSKeyringStore()
        flow = InstalledAppFlow.from_client_secrets_file(str(path), scopes=[READONLY_SCOPE])
        credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True,
            timeout_seconds=180, authorization_prompt_message="Open this read-only OAuth URL: {url}",
            access_type="offline", prompt="consent")
        require_readonly(credentials)
        # Do not persist tokens until the intended account is proven.
        client = GmailHTTPClient(AuthorizedSession(credentials))
        profile = GmailConnector(client).verify_account(account)
        store.save(account, credentials.to_json())
        return profile["emailAddress"]
    except GmailError:
        raise
    except Exception:
        raise GmailAuthError() from None
    finally:
        if client is not None:
            try:
                client.session.close()
            except Exception:
                # Cleanup must not expose a transport exception or mask a safe failure.
                pass
