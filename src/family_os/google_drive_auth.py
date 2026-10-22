"""Separate secure Drive credentials/binding; only explicit desktop connect performs OAuth."""
import json
from pathlib import Path
from typing import Protocol

from .google_drive_errors import DriveError, DriveAuthError, DrivePolicyError, DriveIdentityError
from .google_drive_identity import require_drive_account, drive_identity
from .google_drive import DriveHTTPClient, about_identity, identifier, binding_fingerprint, decode_cursor
from .gmail_privacy import private_transport

SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly"


class TokenStore(Protocol):
    def load(self, account) -> str | None: ...
    def save(self, account, value: str) -> None: ...


class OSKeyringStore:
    """Fail closed on unsupported/plaintext/null backends; no file fallback."""
    SERVICE = "family-os/google-drive.metadata.readonly/v1"
    SECURE_MODULES = frozenset({"keyring.backends.SecretService", "keyring.backends.libsecret",
        "keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.kwallet"})

    def __init__(self, backend=None):
        try:
            if backend is None:
                import keyring
                backend = keyring.get_keyring()
            if type(backend).__module__ not in self.SECURE_MODULES or backend.priority <= 0:
                raise DriveAuthError()
            self.backend = backend
        except Exception:
            raise DriveAuthError() from None

    @staticmethod
    def _key(account):
        # JSON avoids ambiguous concatenated household/account IDs.
        import json
        return json.dumps([account.household_id, account.id], separators=(",", ":"))

    def load(self, account):
        try:
            return self.backend.get_password(self.SERVICE, self._key(account))
        except Exception:
            raise DriveAuthError() from None

    def save(self, account, value):
        try:
            self.backend.set_password(self.SERVICE, self._key(account), value)
        except Exception:
            raise DriveAuthError() from None


def require_metadata_scope(credentials):
    scopes = credentials.granted_scopes if credentials.granted_scopes is not None else credentials.scopes
    if set(scopes or []) != {SCOPE}:
        raise DrivePolicyError()


def connection_value(account, permission_id, credentials):
    require_metadata_scope(credentials)
    return json.dumps({"v": 1, "household": account.household_id, "account": account.id,
        "email": require_drive_account(account), "permission_id": identifier(permission_id),
        "credentials": json.loads(credentials.to_json())}, separators=(",", ":"))


def load_connection(account, store=None):
    require_drive_account(account)
    try:
        store = store if store is not None else OSKeyringStore()
        value = store.load(account)
        if not value:
            raise DriveAuthError()
        info = decode_cursor(value)
        if not isinstance(info, dict) or set(info) != {"v", "household", "account", "email", "permission_id", "credentials"}:
            raise DriveAuthError()
        if type(info["v"]) is not int or info["v"] != 1 or info["household"] != account.household_id or info["account"] != account.id or info["email"] != require_drive_account(account):
            raise DriveIdentityError()
        identifier(info["permission_id"])
        if not isinstance(info["credentials"], dict) or set(info["credentials"].get("scopes", [])) != {SCOPE}:
            raise DrivePolicyError()
        return info, store
    except DriveError:
        raise
    except Exception:
        raise DriveAuthError() from None


def load_binding(account, store=None):
    """Local-only recovery binding lookup; no AuthorizedSession or OAuth."""
    info, _ = load_connection(account, store)
    return binding_fingerprint(info["permission_id"])


class KeyringSession:
    def __init__(self, credentials, store, account, permission_id):
        from google.auth.transport.requests import AuthorizedSession
        require_metadata_scope(credentials)
        self.credentials, self.store, self.account = credentials, store, account
        self.permission_id = identifier(permission_id)
        try:
            self._saved_state = connection_value(account, self.permission_id, credentials)
        except DriveError:
            raise
        except Exception:
            raise DriveAuthError() from None
        self.session = AuthorizedSession(credentials)

    @private_transport
    def get(self, url, **kwargs):
        try:
            require_metadata_scope(self.credentials)
            response = self.session.get(url, **kwargs)
            require_metadata_scope(self.credentials)
            state = connection_value(self.account, self.permission_id, self.credentials)
            if state != self._saved_state:
                self.store.save(self.account, state)
                self._saved_state = state  # Advance only after a successful secure save.
            return response
        except DriveError:
            raise
        except Exception:
            raise DriveAuthError() from None

    def close(self):
        self.session.close()


def load_client(account, store=None):
    info, store = load_connection(account, store)
    try:
        from google.oauth2.credentials import Credentials
        credentials = Credentials.from_authorized_user_info(info["credentials"])
        return DriveHTTPClient(KeyringSession(credentials, store, account, info["permission_id"]), info["permission_id"])
    except DriveError:
        raise
    except Exception:
        raise DriveAuthError() from None


@private_transport
def connect_account(account, client_file, store=None, *, display):
    """Presentation is supplied by the client; identity/scope enforcement stays here."""
    require_drive_account(account)
    client = None
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import AuthorizedSession
        path = Path(client_file).expanduser().resolve()
        repository = Path(__file__).resolve().parents[2]
        # Also protect checkouts when this package is installed non-editably.
        roots = (repository, Path.cwd(), *Path.cwd().parents)
        if path.is_relative_to(repository) or any((root / ".git").exists() and path.is_relative_to(root) for root in roots):
            raise DriveAuthError()
        store = store if store is not None else OSKeyringStore()
        flow = InstalledAppFlow.from_client_secrets_file(str(path), scopes=[SCOPE])
        credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True,
            timeout_seconds=180, authorization_prompt_message="Open this metadata-only OAuth URL: {url}",
            access_type="offline", prompt="consent")
        require_metadata_scope(credentials)
        client = DriveHTTPClient(AuthorizedSession(credentials))
        email, permission_id = about_identity(client.about())
        display(email)
        if drive_identity(email) != require_drive_account(account):
            raise DriveIdentityError()
        store.save(account, connection_value(account, permission_id, credentials))
        return email
    except DriveError:
        raise
    except Exception:
        raise DriveAuthError() from None
    finally:
        if client is not None:
            try:
                client.session.close()
            except Exception:
                pass
