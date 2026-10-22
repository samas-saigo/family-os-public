"""G3a internal fictional code flow; no HTTP transport, listener or real login."""
from dataclasses import dataclass, field
import json
import math
import re
from secrets import token_urlsafe
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit, parse_qsl
from uuid import uuid4

from authlib.common.urls import url_encode, url_decode
from authlib.oauth2.client import OAuth2Client
from authlib.oidc.core import CodeIDToken
import jwt

from family_os._verified_identity import OfflineIdentityVerifier
from family_os._household_sessions import SessionService

CONTRACT_VERSION = 'g3a-fictional-code-flow-v1'
ATTEMPT_SECONDS = 300
MAX_ATTEMPTS = 16


class LoginError(Exception):
    def __init__(self):
        super().__init__('Login unavailable')


def _opaque(value, maximum=256):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,'+str(maximum)+'}', value):
        raise LoginError()
    return value


def _url(value):
    if type(value) is not str or not 1 <= len(value) <= 512 or not value.isascii():
        raise LoginError()
    u = urlsplit(value)
    if (u.scheme != 'https' or not u.hostname or not u.hostname.endswith('.example.invalid')
            or u.username or u.password or u.port is not None or u.query or u.fragment
            or '%' in value or any(ord(c) <= 32 or ord(c) >= 127 for c in value)
            or not u.path.startswith('/') or '//' in u.path):
        raise LoginError()
    return u


@dataclass(frozen=True)
class Configuration:
    issuer: str
    client_id: str
    authorization_endpoint: str
    token_endpoint: str
    redirect_uri: str


@dataclass(frozen=True, eq=False, repr=False)
class LoginAttempt:
    authorization_url: str = field(repr=False)

    def __repr__(self):
        return '<LoginAttempt>'


@dataclass(frozen=True, repr=False)
class TokenReply:
    status: int
    body: bytes

    def __repr__(self):
        return '<FictionalTokenReply>'


@dataclass(frozen=True, repr=False)
class _Pending:
    config: Configuration
    state: str
    verifier: str
    challenge: object
    household: str
    request_id: str
    created: float


@dataclass(frozen=True)
class Completion:
    request_id: str
    session: object  # Existing repr-redacted G2b2 result; UNKNOWN semantics unchanged.


def _pairs(entries):
    out = {}
    for k, v in entries:
        if k in out:
            raise LoginError()
        out[k] = v
    return out


class _Response:
    status_code = 200

    def __init__(self, reply):
        if type(reply) is not TokenReply or type(reply.status) is not int or reply.status != 200:
            raise LoginError()
        if type(reply.body) is not bytes or not 1 <= len(reply.body) <= 32768:
            raise LoginError()
        def invalid(_):
            raise LoginError()
        token = json.loads(reply.body, object_pairs_hook=_pairs, parse_constant=invalid)
        if (type(token) is not dict or not {'access_token', 'id_token', 'token_type'} <= token.keys()
                or token.keys() - {'access_token', 'id_token', 'token_type', 'expires_in', 'scope'}
                or token['token_type'] != 'Bearer' or token.get('scope', 'openid') != 'openid'):
            raise LoginError()
        for key, maximum in [('access_token', 4096), ('id_token', 16384)]:
            value = token[key]
            if (type(value) is not str or not 1 <= len(value) <= maximum
                    or any(ord(c) <= 32 or ord(c) >= 127 for c in value)):
                raise LoginError()
        if 'expires_in' in token and (type(token['expires_in']) is not int or not 1 <= token['expires_in'] <= 300):
            raise LoginError()
        self._token = token

    def json(self):
        return self._token


class _LocalSession:
    """Authlib transport seam. Only the trusted injected local function is called."""
    def __init__(self, config, exchange):
        self.config, self.exchange = config, exchange

    def post(self, uri, *, data, headers, auth):
        # Authlib also owns public-client token endpoint authentication encoding.
        uri, headers, body = auth.prepare('POST', uri, dict(headers), url_encode(data.items()))
        form = dict(url_decode(body))
        if (uri != self.config.token_endpoint or headers.get('Authorization')
                or set(form) != {'grant_type', 'client_id', 'redirect_uri', 'code', 'code_verifier'}
                or form['grant_type'] != 'authorization_code' or form['client_id'] != self.config.client_id
                or form['redirect_uri'] != self.config.redirect_uri):
            raise LoginError()
        return _Response(self.exchange(uri, form))


class LoginFlow:
    """Trusted same-process fictional harness only; never wire directly to clients.

    Exact attempt identity models a browser-bound server receipt, not a browser cookie
    implementation or distributed replay protection. No durable alternate identity store.
    """
    def __init__(self, config, verifier, sessions, *, exchange, synthetic_only=False, clock=monotonic):
        try:
            if (synthetic_only is not True or type(config) is not Configuration
                    or type(verifier) is not OfflineIdentityVerifier or type(sessions) is not SessionService
                    or sessions._verifier is not verifier or not callable(exchange) or not callable(clock)):
                raise LoginError()
            issuer = _url(config.issuer)
            for endpoint in (config.authorization_endpoint, config.token_endpoint):
                if _url(endpoint).netloc != issuer.netloc:
                    raise LoginError()
            _url(config.redirect_uri); _opaque(config.client_id)
            if verifier._issuer != config.issuer or verifier._audience != config.client_id:
                raise LoginError()
            self._config, self._verifier, self._sessions = config, verifier, sessions
            self._exchange, self._clock = exchange, clock
            self._attempts, self._lock = {}, Lock()
        except Exception:
            raise LoginError() from None

    def _now(self):
        now = self._clock()
        if type(now) not in (int, float) or not math.isfinite(now) or not 0 <= now < 1e12:
            raise LoginError()
        return now

    def _client(self, state):
        return OAuth2Client(_LocalSession(self._config, self._exchange), client_id=self._config.client_id,
            token_endpoint_auth_method='none', scope='openid', state=state,
            redirect_uri=self._config.redirect_uri, code_challenge_method='S256', response_type='code')

    def begin(self, household_id):
        try:
            if type(household_id) is not str or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', household_id):
                raise LoginError()
            with self._lock:
                now = self._now()
                self._attempts = {a: p for a, p in self._attempts.items() if 0 <= now-p.created < ATTEMPT_SECONDS}
                if len(self._attempts) >= MAX_ATTEMPTS:
                    raise LoginError()
                challenge = self._verifier.challenge()
                state, verifier = token_urlsafe(32), token_urlsafe(32)
                uri, returned = self._client(state).create_authorization_url(self._config.authorization_endpoint,
                    state=state, code_verifier=verifier, nonce=challenge.nonce)
                if returned != state:
                    raise LoginError()
                receipt = LoginAttempt(uri)
                self._attempts[receipt] = _Pending(self._config, state, verifier, challenge, household_id, 'login_'+uuid4().hex, now)
                return receipt
        except Exception:
            raise LoginError() from None

    def cancel(self, attempt):
        if type(attempt) is not LoginAttempt:
            raise LoginError()
        with self._lock:
            self._attempts.pop(attempt, None)

    def complete(self, attempt, callback_url):
        try:
            # Consume before parsing/exchange/inference/DB, even on failure. Only one
            # concurrent callback obtains this pending record; no locks during DB I/O.
            with self._lock:
                if type(attempt) is not LoginAttempt:
                    raise LoginError()
                pending = self._attempts.pop(attempt, None)
                if (pending is None or pending.config != self._config
                        or not 0 <= self._now()-pending.created < ATTEMPT_SECONDS):
                    raise LoginError()
            if (type(callback_url) is not str or not 1 <= len(callback_url) <= 4096
                    or not callback_url.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in callback_url)):
                raise LoginError()
            url = urlsplit(callback_url)
            if url.fragment or callback_url.partition('?')[0] != self._config.redirect_uri:
                raise LoginError()
            params = _pairs(parse_qsl(url.query, keep_blank_values=True, strict_parsing=True, max_num_fields=8))
            if (not {'code', 'state'} <= params.keys() or params.keys()-{'code', 'state', 'iss'}
                    or params['state'] != pending.state or params.get('iss', self._config.issuer) != self._config.issuer):
                raise LoginError()
            _opaque(params['code']); _opaque(params['state'], 43)
            token = self._client(pending.state).fetch_token(self._config.token_endpoint,
                authorization_response=callback_url, grant_type='authorization_code', code_verifier=pending.verifier)
            # Only exchanged id_token enters the unchanged verifier. No client token API.
            proof = self._verifier.verify(token['id_token'], pending.challenge)
            # Decode the exact immutable token only AFTER G2b1 signature/profile verification;
            # Authlib checks optional OIDC at_hash, azp/amr and the request-bound nonce.
            claims = jwt.decode(token['id_token'], options={'verify_signature': False})
            header = jwt.get_unverified_header(token['id_token'])
            if 'at_hash' in claims:
                _opaque(claims['at_hash'], 128)  # Present-but-empty is not an absent optional hash.
            if 'c_hash' in claims:
                raise LoginError()  # Unsupported extra hash profile, never silently ignored.
            CodeIDToken(claims, header, params={'nonce': pending.challenge.nonce,
                'client_id': self._config.client_id, 'access_token': token['access_token']}).validate(leeway=0)
            result = self._sessions.establish(proof, pending.household, request_id=pending.request_id)
            return Completion(pending.request_id, result)  # G2b2 UNKNOWN/replay preserved; never retry.
        except Exception:
            raise LoginError() from None
