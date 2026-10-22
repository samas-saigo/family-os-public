"""Offline OIDC ID-token profile. No login, sessions, G2a handles or provider I/O."""
from dataclasses import dataclass, field
import json
from secrets import token_urlsafe
from threading import Lock
from time import time
from urllib.parse import urlsplit

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from sqlalchemy import select

from family_os.schema import external_identity_binding, household_membership, person


CONTRACT_VERSION = "g2b1-offline-identity-v1"

class IdentityError(Exception):
    def __init__(self):
        super().__init__('Identity verification unavailable')


def _text(value, maximum):
    if (type(value) is not str or not 1 <= len(value) <= maximum
            or any(ord(c) < 33 or ord(c) > 126 for c in value)):
        raise IdentityError()
    return value  # Exact, case-sensitive opaque identity; never email/name normalization.


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IdentityError()
        result[key] = value
    return result


def _json(data):
    def invalid(_):
        raise IdentityError()
    value = json.loads(data, object_pairs_hook=_pairs, parse_constant=invalid)
    if type(value) is not dict:
        raise IdentityError()
    return value


class _StrictJWS(jwt.PyJWS):
    def _load(self, token):
        # PyJWT owns compact/base64 parsing. Reject duplicate JOSE names as well.
        payload, signing_input, header, signature = super()._load(token)
        segment = signing_input.partition(b'.')[0]
        strict = _json(self._decode_base64url_segment(segment, 'header'))
        if strict != header:
            raise IdentityError()
        return payload, signing_input, strict, signature


class _StrictJWT(jwt.PyJWT):
    def __init__(self):
        super().__init__()
        self._jws = _StrictJWS(algorithms=['RS256'])

    def _decode_payload(self, decoded):
        # Documented PyJWT payload hook; signature and claim checks stay in PyJWT.
        return _json(decoded['payload'])


@dataclass(frozen=True, repr=False, eq=False)
class Challenge:
    nonce: str = field(repr=False)
    expires_at: float = field(repr=False)

    def __repr__(self):
        return '<IdentityChallenge>'


@dataclass(frozen=True, repr=False, eq=False)
class VerifiedIdentity:
    issuer: str = field(repr=False)
    subject: str = field(repr=False)
    expires_at: int = field(repr=False)

    def __repr__(self):
        return '<VerifiedIdentity>'


@dataclass(frozen=True)
class ResolvedMember:
    """Internal binding snapshot only: not a session, permission or G2a context."""
    household_id: str
    person_id: str
    membership_revision: int
    binding_revision: int


class OfflineIdentityVerifier:
    """Trusted static public-key configuration; token cannot select issuer, URL or key.

    Nonce receipts and proof handles are single-process seam guards, not durable sessions
    or hostile-Python authentication. No discovery/JWKS fetching or key auto-refresh.
    """
    def __init__(self, *, issuer, audience, public_keys):
        try:
            _text(issuer, 512); _text(audience, 255)
            url = urlsplit(issuer)
            if (url.scheme != 'https' or not url.hostname or url.username or url.password
                    or url.query or url.fragment):
                raise IdentityError()
            if type(public_keys) is not dict or not 1 <= len(public_keys) <= 4:
                raise IdentityError()
            keys = {}
            for kid, pem in public_keys.items():
                _text(kid, 64)
                if type(pem) is not bytes or len(pem) > 4096:
                    raise IdentityError()
                key = load_pem_public_key(pem)
                if not isinstance(key, RSAPublicKey) or not 2048 <= key.key_size <= 4096:
                    raise IdentityError()
                keys[kid] = key
            self._issuer, self._audience, self._keys = issuer, audience, keys
            self._jwt = _StrictJWT()
            self._challenges = []
            self._proofs = []
            self._lock = Lock()
        except Exception:
            raise IdentityError() from None

    def challenge(self):
        """Internal trusted request initiation, not a client-chosen expected nonce."""
        with self._lock:
            now = time()
            self._challenges = [c for c in self._challenges if c.expires_at > now]
            if len(self._challenges) >= 32:
                raise IdentityError()
            c = Challenge(token_urlsafe(32), now + 300)
            self._challenges.append(c)
            return c

    def verify(self, token, challenge):
        try:
            if type(token) is not str or not 1 <= len(token) <= 16384 or not token.isascii():
                raise IdentityError()
            with self._lock:
                now = time()
                if (type(challenge) is not Challenge or not any(challenge is c for c in self._challenges)
                        or challenge.expires_at <= now):
                    raise IdentityError()
                # Unverified header is used ONLY for selection among trusted configured keys.
                header = self._jwt._jws.get_unverified_header(token)
                if (set(header) != {'alg', 'typ', 'kid'} or header['alg'] != 'RS256'
                        or header['typ'] != 'JWT' or type(header['kid']) is not str
                        or header['kid'] not in self._keys):
                    raise IdentityError()
                claims = self._jwt.decode(token, self._keys[header['kid']], algorithms=['RS256'],
                    issuer=self._issuer, audience=self._audience, leeway=0,
                    options={'require': ['iss', 'sub', 'aud', 'exp', 'iat', 'nbf', 'nonce'],
                             'strict_aud': True, 'enforce_minimum_key_length': True})
                if (claims['iss'] != self._issuer or claims['aud'] != self._audience
                        or claims.get('azp', self._audience) != self._audience
                        or claims['nonce'] != challenge.nonce):
                    raise IdentityError()
                subject = _text(claims['sub'], 255)
                if any(type(claims[k]) is not int for k in ('iat', 'nbf', 'exp')):
                    raise IdentityError()
                iat, nbf, exp = (claims[k] for k in ('iat', 'nbf', 'exp'))
                if not (now - 300 <= iat <= nbf <= now < exp <= iat + 300):
                    raise IdentityError()
                self._proofs = [p for p in self._proofs if p.expires_at > now]
                if len(self._proofs) >= 32:
                    raise IdentityError()
                proof = VerifiedIdentity(self._issuer, subject, exp)
                self._proofs.append(proof)
                self._challenges = [c for c in self._challenges if c is not challenge]
                return proof  # No token, extra claims, credentials or caller-selected Person.
        except Exception:
            raise IdentityError() from None

    def _current(self, proof):
        with self._lock:
            if (type(proof) is not VerifiedIdentity or not any(proof is p for p in self._proofs)
                    or proof.expires_at <= time()):
                raise IdentityError()


class IdentityBindingResolver:
    """Explicit offline DB seam, not a service entrypoint or authorized read adapter."""
    def __init__(self, engine, verifier, *, synthetic_only=False):
        if (synthetic_only is not True or type(verifier) is not OfflineIdentityVerifier
                or engine.dialect.name not in ('sqlite', 'postgresql')):
            raise IdentityError()
        self._engine, self._verifier = engine, verifier

    def resolve(self, proof, household_id):
        try:
            self._verifier._current(proof)
            _text(household_id, 64)
            with self._engine.connect() as c:
                # Exact identity is globally unique. No automatic linking/enrollment.
                rows = c.execute(select(external_identity_binding).where(
                    external_identity_binding.c.issuer == proof.issuer,
                    external_identity_binding.c.subject == proof.subject).limit(2)).mappings().all()
                if len(rows) != 1:
                    raise IdentityError()
                row = rows[0]
                if row['household_id'] != household_id or row['state'] != 'allowed':
                    raise IdentityError()
                membership = c.execute(select(household_membership.c.revision).join(person,
                    (person.c.household_id == household_membership.c.household_id) &
                    (person.c.id == household_membership.c.person_id)).where(
                    household_membership.c.household_id == household_id,
                    household_membership.c.person_id == row['person_id'],
                    household_membership.c.state == 'allowed')).scalar_one_or_none()
                if membership is None:
                    raise IdentityError()
                self._verifier._current(proof)  # Expiration is not a permanent identity lease.
                return ResolvedMember(household_id, row['person_id'], membership, row['revision'])
        except Exception:
            raise IdentityError() from None
