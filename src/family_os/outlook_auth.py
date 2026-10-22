"""Explicit MSAL public-client sign-in; cache/binding live only in OS keyring."""
from hashlib import sha256
import json
from urllib.parse import urlsplit
from uuid import UUID

from .gmail_auth import OSKeyringStore
from .gmail_privacy import private_transport
from .errors import GmailError
from .outlook import GraphHTTPClient
from .outlook_identity import require_outlook_account, outlook_identity
from .outlook_errors import (OutlookError, OutlookAuthError, OutlookIdentityError,
                             OutlookPolicyError, OutlookAPIError)

READ_BASIC_SCOPE = "https://graph.microsoft.com/Mail.ReadBasic"
DEFAULT_AUTHORITY = "https://login.microsoftonline.com/common"
PROTOCOL_SCOPES = {"openid", "profile", "offline_access"}


def validate_authority(value):
    try:
        parsed = urlsplit(value)
        tenant = parsed.path.strip("/")
        if (parsed.scheme != "https" or parsed.netloc != "login.microsoftonline.com" or
            parsed.query or parsed.fragment or parsed.path != "/" + tenant or
            not tenant or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for char in tenant)):
            raise ValueError()
        return value
    except Exception:
        raise OutlookAuthError() from None


class OutlookKeyringStore(OSKeyringStore):
    # Reuse secure-backend policy and collision-free household/account keying,
    # preserving Gmail's implementation/service exactly.
    SERVICE = "family-os/outlook.Mail.ReadBasic/v1"

    def __init__(self, backend=None):
        try:
            super().__init__(backend)
        except GmailError:
            raise OutlookAuthError() from None

    @private_transport
    def load(self, account):
        try:
            return super().load(account)
        except GmailError:
            raise OutlookAuthError() from None

    @private_transport
    def save(self, account, value):
        try:
            super().save(account, value)
        except GmailError:
            raise OutlookAuthError() from None


def require_scopes(result):
    if not isinstance(result, dict):
        raise OutlookAuthError()
    if "access_token" not in result:
        if result.get("error") in {"access_denied", "unauthorized_client", "invalid_scope"}:
            raise OutlookPolicyError()
        raise OutlookAuthError()
    scopes = set(result.get("scope", "").casefold().split())
    mail = {"mail.readbasic", READ_BASIC_SCOPE.casefold()}
    if not scopes & mail or scopes - mail - PROTOCOL_SCOPES:
        raise OutlookPolicyError()
    if not isinstance(result["access_token"], str) or not result["access_token"]:
        raise OutlookAuthError()


def binding_fingerprint(payload):
    # Stable home ID stays in keyring. Only a non-secret binding fingerprint is
    # included in the provider cursor; authority/app changes require resync.
    return sha256(json.dumps([payload["home_account_id"], payload["client_id"],
                            payload["authority"]], separators=(",", ":")).encode()).hexdigest()


def validate_cached_account(app, payload, account):
    expected = require_outlook_account(account)
    accounts = app.get_accounts()
    matches = [item for item in accounts if item.get("home_account_id") == payload["home_account_id"]]
    if len(matches) != 1 or outlook_identity(matches[0].get("username")) != expected:
        raise OutlookIdentityError()
    if outlook_identity(payload.get("username")) != expected:
        raise OutlookIdentityError()
    return matches[0]


def validate_claims(result, cached):
    claims = result.get("id_token_claims") or {}
    # MSAL selects the bound account for silent acquisition. When new identity
    # claims are supplied, check them too rather than accepting an account switch.
    if claims.get("preferred_username") and outlook_identity(claims["preferred_username"]) != outlook_identity(cached["username"]):
        raise OutlookIdentityError()
    if claims.get("oid") and claims["oid"] != cached.get("local_account_id"):
        raise OutlookIdentityError()
    if claims.get("tid") and claims["tid"] != cached.get("realm"):
        raise OutlookIdentityError()


def make_app(client_id, authority, cache):
    import msal
    try:
        UUID(client_id)
        validate_authority(authority)
        return msal.PublicClientApplication(client_id, authority=authority, token_cache=cache,
                                           enable_pii_log=False, timeout=30)
    except Exception:
        raise OutlookAuthError() from None


class MSALSession:
    def __init__(self, app, cache, store, account, payload, http=None):
        import requests
        self.app, self.cache, self.store, self.account, self.payload = app, cache, store, account, payload
        self.http = http if http is not None else requests.Session()

    @private_transport
    def identity(self):
        try:
            cached = validate_cached_account(self.app, self.payload, self.account)
            return cached["username"], binding_fingerprint(self.payload)
        except OutlookError:
            raise
        except Exception:
            raise OutlookAuthError() from None

    @private_transport
    def get(self, url, **kwargs):
        try:
            cached = validate_cached_account(self.app, self.payload, self.account)
            result = self.app.acquire_token_silent([READ_BASIC_SCOPE], account=cached)
            require_scopes(result)
            validate_claims(result, cached)
            validate_cached_account(self.app, self.payload, self.account)
            if self.cache.has_state_changed:
                updated = {**self.payload, "cache": self.cache.serialize()}
                try:
                    self.store.save(self.account, json.dumps(updated))
                except Exception:
                    # serialize clears MSAL's dirty flag. Keep it dirty if secure
                    # persistence failed, so a retry cannot silently lose refreshes.
                    self.cache.has_state_changed = True
                    raise
                self.payload = updated
            headers = dict(kwargs.pop("headers", {}))
            headers["Authorization"] = "Bearer " + result["access_token"]
            try:
                return self.http.get(url, headers=headers, **kwargs)
            except Exception:
                raise OutlookAPIError() from None
        except OutlookError:
            raise
        except Exception:
            raise OutlookAuthError() from None

    def close(self):
        self.http.close()


@private_transport
def connect_account(account, client_id, authority=DEFAULT_AUTHORITY, store=None, show_identity=print):
    """Interactive sign-in only here; display identity before any keyring binding."""
    try:
        expected = require_outlook_account(account)  # Before app/keyring/OAuth work.
        import msal
        store = store if store is not None else OutlookKeyringStore()
        cache = msal.SerializableTokenCache()
        app = make_app(client_id, authority, cache)
        result = app.acquire_token_interactive(scopes=[READ_BASIC_SCOPE], login_hint=account.external_account,
                prompt="select_account", timeout=180)
        require_scopes(result)
        accounts = app.get_accounts()
        if len(accounts) != 1:
            raise OutlookIdentityError()
        cached = accounts[0]
        username = outlook_identity(cached.get("username"))
        show_identity(f"Signed-in Microsoft account: {username}")
        if username != expected or not isinstance(cached.get("home_account_id"), str) or not cached["home_account_id"]:
            raise OutlookIdentityError()
        validate_claims(result, cached)
        payload = {"v": 1, "household": account.household_id, "account": account.id,
                   "username": username, "home_account_id": cached["home_account_id"],
                   "client_id": client_id, "authority": authority, "cache": cache.serialize()}
        store.save(account, json.dumps(payload))
        return username
    except OutlookError:
        raise
    except Exception:
        raise OutlookAuthError() from None


@private_transport
def load_client(account, store=None):
    """Load only this account's keyring payload; never start interactive OAuth."""
    try:
        require_outlook_account(account)
        import msal
        store = store if store is not None else OutlookKeyringStore()
        value = store.load(account)
        if not value:
            raise OutlookAuthError()
        payload = json.loads(value)
        allowed = {"v", "household", "account", "username", "home_account_id", "client_id", "authority", "cache"}
        if set(payload) != allowed or type(payload.get("v")) is not int or payload["v"] != 1:
            raise OutlookAuthError()
        if payload["household"] != account.household_id or payload["account"] != account.id:
            raise OutlookIdentityError()
        if not isinstance(payload["home_account_id"], str) or not payload["home_account_id"]:
            raise OutlookIdentityError()
        cache = msal.SerializableTokenCache()
        cache.deserialize(payload["cache"])
        app = make_app(payload["client_id"], payload["authority"], cache)
        validate_cached_account(app, payload, account)
        return GraphHTTPClient(MSALSession(app, cache, store, account, payload))
    except OutlookError:
        raise
    except Exception:
        raise OutlookAuthError() from None
