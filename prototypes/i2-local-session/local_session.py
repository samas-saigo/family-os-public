"""Opt-in loopback fictional session lab. Not installed as a Family OS entrypoint.

The terminal is a trusted fictional provisioning operator, NOT authentication.
No runtime DB discovery, provider repository, T1 route or production login exists.
"""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
import json
import logging
from pathlib import Path
from queue import Queue, Empty
import re
from secrets import token_urlsafe, token_hex
from tempfile import TemporaryDirectory
from threading import RLock, Thread, Timer
from time import monotonic, time

from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import jwt
from sqlalchemy import insert

from family_os import _household_authorization as a, _household_sessions as s
from family_os import _verified_identity as v
from family_os.db import create_db
from family_os.registry import register
from family_os.schema import household_membership, external_identity_binding

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HOME = 'i2-willow'
PEERS = ('clara', 'devon')
ISSUER = 'https://i2-willow.example.invalid'
COOKIE = '__Host-samas-i2'
PAIR = '__Host-samas-i2-pair'
PAIR_SECONDS = 120
SESSION_SECONDS = 600
RUN_SECONDS = 1800
MAX_STARTS = 8
CONTRACT_VERSION = 'i2-loopback-fictional-session-v1'
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}


class Unavailable(Exception):
    def __init__(self):
        super().__init__('Local synthetic session unavailable')


def digest(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9_-]{43}', value) is None:
        raise Unavailable()
    return sha256(value.encode('ascii')).hexdigest()


def cookie(name, value='', *, clear=False):
    return ('Set-Cookie', f'{name}={value}; Path=/; Secure; HttpOnly; SameSite=Strict'
            + ('; Max-Age=0' if clear else ''))


def cookie_values(env):
    raw = env.get('HTTP_COOKIE', '')
    values = {}
    if len(raw) > 256:
        raise Unavailable()
    for pair in raw.split('; ') if raw else ():
        name, sep, value = pair.partition('=')
        if not sep or name not in (COOKIE, PAIR) or name in values:
            raise Unavailable()
        digest(value)
        values[name] = value
    return values


@dataclass(repr=False)
class Pairing:
    ticket: str  # Public correlation ID, never sufficient to claim a session.
    deadline: float
    bearer: str | None = field(default=None, repr=False)
    failed: bool = False


class Lab:
    """One process, one explicitly provided disposable fixture DB and session service."""
    def __init__(self, engine, *, synthetic_only=False, clock=monotonic):
        if synthetic_only is not True:
            raise Unavailable()
        self.lock = RLock()
        self.clock = clock
        self.started = self.last = clock()
        self.stopped = False
        self.starts = 0
        self.pairs = {}
        self.leases = {}
        # Only newly invented people: no sources, tasks, grants, personal fields.
        register(engine, {'household': {'id': HOME, 'name': 'Fictional I2 Willow'},
            'people': [{'id': 'i2-'+p, 'display_name': 'Fictional '+p} for p in PEERS],
            'source_accounts': []})
        with engine.begin() as c:
            c.execute(insert(household_membership), [dict(household_id=HOME,
                person_id='i2-'+p, state='allowed', revision=1) for p in PEERS])
            c.execute(insert(external_identity_binding), [dict(issuer=ISSUER,
                subject='i2-sub-'+p, household_id=HOME, person_id='i2-'+p,
                state='allowed', revision=1) for p in PEERS])
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.verifier = v.OfflineIdentityVerifier(issuer=ISSUER, audience='i2-fictional-client',
            public_keys={'i2-key': self.key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)})
        self.sessions = s.SessionService(engine, self.verifier, a.FixtureRepository(), synthetic_only=True)

    def _now(self):
        now = self.clock()
        if self.stopped or not self.last <= now < self.started + RUN_SECONDS:
            raise Unavailable()
        self.last = now
        self.pairs = {k: p for k, p in self.pairs.items() if now < p.deadline}
        self.leases = {k: deadline for k, deadline in self.leases.items() if now < deadline}
        return now

    def pending(self):
        with self.lock:
            self._now()
            return tuple(p.ticket for p in self.pairs.values() if not p.failed and p.bearer is None)

    def approve(self, ticket, peer):
        """Terminal-only exact pending browser + fixed fictional identity. Never HTTP."""
        with self.lock:
            self._now()
            matches = [p for p in self.pairs.values() if p.ticket == ticket]
            if peer not in PEERS or len(matches) != 1:
                raise Unavailable()
            p = matches[0]
            if p.failed or p.bearer is not None:
                raise Unavailable()
            p.failed = True  # Consume before DB work; UNKNOWN never retries issuance.
            challenge = self.verifier.challenge()
            now = int(time())
            assertion = jwt.encode(dict(iss=ISSUER, sub='i2-sub-'+peer,
                aud='i2-fictional-client', iat=now-1, nbf=now-1, exp=now+60,
                nonce=challenge.nonce), self.key, algorithm='RS256', headers={'kid': 'i2-key'})
            result = self.sessions.establish(self.verifier.verify(assertion, challenge), HOME,
                request_id='i2-'+token_hex(16))
            if result.outcome is not s.Outcome.COMMITTED or not result.bearer:
                raise Unavailable()
            p.bearer = result.bearer
            self.leases[digest(result.bearer)] = self._now() + SESSION_SECONDS
            p.failed = False

    def _current(self, bearer):
        self._now()
        if digest(bearer) not in self.leases:
            raise Unavailable()
        return self.sessions.resolve(bearer, HOME)

    def call(self, path, values):
        with self.lock:
            now = self._now()
            if path == '/api/start':
                if values or self.starts >= MAX_STARTS:
                    raise Unavailable()
                self.starts += 1
                secret = token_urlsafe(32)
                p = Pairing(token_hex(8), now + PAIR_SECONDS)
                self.pairs[digest(secret)] = p
                return {'state': 'waiting', 'request_id': p.ticket}, [cookie(PAIR, secret)]
            if path == '/api/cancel':
                if set(values) != {PAIR}:
                    raise Unavailable()
                removed = self.pairs.pop(digest(values[PAIR]), None)
                if removed is not None and removed.bearer is not None:
                    self.leases.pop(digest(removed.bearer), None)
                return {'state': 'cancelled'}, [cookie(PAIR, clear=True)]
            if path == '/api/session' and set(values) == {PAIR}:
                p = self.pairs.get(digest(values[PAIR]))
                if p is None or p.failed:
                    raise Unavailable()
                if p.bearer is None:
                    return {'state': 'waiting', 'request_id': p.ticket}, []
                state = self._current(p.bearer)
                del self.pairs[digest(values[PAIR])]  # One delivery only, no secret recovery.
                return {'state': 'active', 'member': state.person_id}, [cookie(COOKIE, p.bearer), cookie(PAIR, clear=True)]
            if set(values) != {COOKIE}:
                raise Unavailable()
            bearer = values[COOKIE]
            state = self._current(bearer)
            if path == '/api/session':
                return {'state': 'active', 'member': state.person_id}, []
            if path == '/api/logout':
                result = self.sessions.logout(bearer, HOME, request_id='i2-'+token_hex(16),
                    expected_revision=state.revision)
                self.leases.pop(digest(bearer), None)  # Local reuse denies even on UNKNOWN.
                if result.outcome is not s.Outcome.COMMITTED:
                    return {'state': 'unknown'}, [cookie(COOKIE, clear=True)]
                return {'state': 'logged_out'}, [cookie(COOKIE, clear=True)]
            raise Unavailable()

    def close(self):
        with self.lock:
            self.stopped = True
            self.pairs.clear()
            self.leases.clear()
            self.key = None


class Application:
    """Strict same-origin WSGI boundary; not the G3b ASGI callable or a file server."""
    def __init__(self, lab, port):
        if type(lab) is not Lab or type(port) is not int or not 1 <= port <= 65535:
            raise Unavailable()
        self.lab, self.host = lab, f'127.0.0.1:{port}'
        self.origin = 'http://' + self.host
        self.assets = {path: ((HERE/name).read_bytes(), mime) for path, (name, mime) in ASSETS.items()}

    def allows_query(self, env):
        return not env.get('QUERY_STRING')

    def read(self, env):
        # Default I2 has no data routes. Only trusted prototype subclasses extend it.
        raise Unavailable()

    def write(self, env):
        # Default I2 remains session-only; trusted opt-in subclasses must validate writes.
        raise Unavailable()

    def __call__(self, env, start_response):
        headers = [('Cache-Control', 'no-store, no-cache, max-age=0'), ('Pragma', 'no-cache'),
            ('Expires', '0'), ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer'),
            ('Content-Security-Policy', CSP), ('Cross-Origin-Resource-Policy', 'same-origin'),
            ('Cross-Origin-Opener-Policy', 'same-origin'), ('X-Frame-Options', 'DENY')]
        status, body, mime = '400 Bad Request', b'{"error":"local_session_unavailable"}', 'application/json'
        trusted_api = False
        try:
            if (env.get('REMOTE_ADDR') != '127.0.0.1' or env.get('HTTP_HOST') != self.host
                    or not self.allows_query(env) or env.get('SCRIPT_NAME', '')
                    or any(k.startswith('HTTP_X_FORWARDED') or k in ('HTTP_FORWARDED', 'HTTP_AUTHORIZATION') for k in env)):
                raise Unavailable()
            path, method = env.get('PATH_INFO'), env.get('REQUEST_METHOD')
            origin, site = env.get('HTTP_ORIGIN'), env.get('HTTP_SEC_FETCH_SITE')
            if origin is not None and origin != self.origin:
                raise Unavailable()
            if path in self.assets and method == 'GET':
                if site not in (None, 'none', 'same-origin') or env.get('CONTENT_LENGTH', '') not in ('', '0'):
                    raise Unavailable()
                body, mime = self.assets[path]
                status = '200 OK'
            elif method == 'GET':
                body = self.read(env)
                status = '200 OK'
            elif path in ('/api/start', '/api/cancel', '/api/session', '/api/logout') and method == 'POST':
                if (origin != self.origin or site != 'same-origin'
                        or env.get('HTTP_X_SAMAS_INTENT') != 'local-session'
                        or env.get('CONTENT_TYPE') != 'application/json'
                        or env.get('CONTENT_LENGTH') != '2'
                        or env.get('HTTP_TRANSFER_ENCODING') is not None
                        or env.get('HTTP_CONTENT_ENCODING') is not None
                        or env['wsgi.input'].read(2) != b'{}'):
                    raise Unavailable()
                trusted_api = True
                values = cookie_values(env)
                result, cookies = self.lab.call(path, values)
                body = json.dumps(result, ensure_ascii=True, sort_keys=True).encode('ascii')
                headers.extend(cookies)
                status = '200 OK'
            elif method == 'POST':
                body = self.write(env)
                status = '200 OK'
            else:
                raise Unavailable()
        except Exception:
            # Never expose driver/request details or serve an old authenticated body.
            status, body, mime = '400 Bad Request', b'{"error":"local_session_unavailable"}', 'application/json'
            if trusted_api:
                headers.extend([cookie(COOKIE, clear=True), cookie(PAIR, clear=True)])
        start_response(status, headers + [('Content-Type', mime), ('Content-Length', str(len(body)))])
        return [body]


def migrate(engine):
    """Explicit temporary connection: never env.py/DATABASE_URL/runtime discovery."""
    config = Config()
    config.set_main_option('script_location', str(ROOT/'migrations'))
    script = ScriptDirectory.from_config(config)
    with engine.connect() as c:
        with EnvironmentContext(config, script, fn=lambda rev, ctx: script._upgrade_revs('head', rev)) as context:
            context.configure(connection=c, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()


@contextmanager
def disposable(*, synthetic_only=False):
    if synthetic_only is not True:
        raise Unavailable()
    with TemporaryDirectory(prefix='samas-i2-fictional-') as directory:
        engine = create_db('sqlite:///'+(Path(directory)/'disposable.sqlite3').as_posix())
        try:
            migrate(engine)
            lab = Lab(engine, synthetic_only=True)
            try:
                yield lab
            finally:
                lab.close()
        finally:
            engine.dispose()


def serve(lab, *, application=None):
    from waitress import create_server
    if type(lab) is not Lab or lab.stopped:
        raise Unavailable()
    # A maintained HTTP parser, no directory serving, proxy trust or wildcard bind.
    # Validate/cache the complete allowlist before creating any listener/workers.
    # Placeholder origin is never served; OS-selected port is set before run().
    application = Application(lab, 1) if application is None else application
    if not isinstance(application, Application) or application.lab is not lab:
        raise Unavailable()
    server = create_server(application, host='127.0.0.1', port=0, threads=2,
        connection_limit=8, channel_timeout=5, cleanup_interval=1,
        max_request_header_size=8192, max_request_body_size=256,
        expose_tracebacks=False, ident='', clear_untrusted_proxy_headers=False)
    application.host = f'127.0.0.1:{int(server.effective_port)}'
    application.origin = 'http://' + application.host
    # Raw request/exception logging is deliberately disabled for this bounded lab.
    for name in ('waitress', 'waitress.queue'):
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
    def run():
        try:
            server.run()
        except Exception:
            lab.close()  # No traceback or request material on background failure.
    thread = Thread(target=run, daemon=True)
    thread.start()
    return server, application, thread


def stop(server, lab, thread):
    from waitress import wasyncore
    lab.close()
    server.close()
    server.task_dispatcher.shutdown(cancel_pending=True, timeout=5)
    wasyncore.close_all(map=server._map, ignore_all=True)  # Only this server's sockets.
    thread.join(timeout=5)


def interact(lab, server, app, thread, *, banner='LOCAL FICTIONAL TEST ONLY — not real login. No tasks or provider data.'):
    timer = Timer(RUN_SECONDS, lambda: (lab.close(), server.close()))
    timer.daemon = True
    timer.start()
    try:
        print(banner)
        print('Open ' + app.origin + '/ in a browser. Use another browser profile for the second adult.')
        print('Commands: pending | approve REQUEST_ID clara | approve REQUEST_ID devon | quit')
        commands = Queue(maxsize=1)
        def read_terminal():
            try:
                while True:
                    value = input('i2> ')
                    commands.put(value)
                    if value.strip() == 'quit':
                        return
            except (EOFError, KeyboardInterrupt):
                commands.put('quit')
        Thread(target=read_terminal, daemon=True).start()
        while not lab.stopped:
            try:
                line = commands.get(timeout=0.5).split()
            except Empty:
                continue
            if line == ['quit']:
                break
            try:
                if line == ['pending']:
                    print('Pending browser requests: ' + ', '.join(lab.pending()))
                elif len(line) == 3 and line[0] == 'approve':
                    lab.approve(line[1], line[2])
                    print('Fictional session approved for that browser; not production authentication.')
                else:
                    print('No change. Use pending, exact approve command, or quit.')
            except Exception:
                print('Request unavailable; no retry or outcome assumption. Start a new lab if needed.')
    finally:
        timer.cancel()
        stop(server, lab, thread)


def main():
    parser = argparse.ArgumentParser(description='Samas I2 local fictional session lab', allow_abbrev=False)
    parser.add_argument('--synthetic-only', action='store_true', required=True)
    args = parser.parse_args()
    try:
        with disposable(synthetic_only=args.synthetic_only) as lab:
            server, app, thread = serve(lab)
            interact(lab, server, app, thread)
    except (KeyboardInterrupt, EOFError):
        pass
    except Exception:
        parser.exit(1, 'Local synthetic session unavailable. No credential details are logged.\n')


if __name__ == '__main__':
    main()
