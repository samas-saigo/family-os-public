"""Opt-in developer export: fresh fictional DB -> real G3b -> offline HTML assets.

Not installed as a production CLI. Never reads DATABASE_URL, an existing database,
provider records or arbitrary fixture input. All DB/key/session state is disposable.
"""
import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time

from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import jwt
from sqlalchemy import insert

from family_os import _household_authorization as a, _household_sessions as s
from family_os import _verified_identity as v, _fictional_read_api as api
from family_os.db import create_db
from family_os.registry import register
from family_os.schema import household_membership, external_identity_binding, publication_scope
from response_contract import PreviewError, validate_response

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HOME = 'h2-alder'
PEERS = ('iris', 'soren')
PHASES = ('initial', 'source-revoked', 'publication-revoked', 'observation-only')
SOURCES = ('h2-common-a', 'h2-common-b', 'h2-iris-private')
ISSUER = 'https://h2-identity.example.invalid'
LIMIT = 2


class Harness:
    """Privileged fixed-fiction setup only; test engines must be disposable and empty."""
    def __init__(self, engine, *, synthetic_only=False):
        if synthetic_only is not True:
            raise PreviewError()
        register(engine, {'household': {'id': HOME, 'name': 'Fictional H2 Alder'},
            'people': [{'id': 'h2-'+p, 'display_name': 'Fictional '+p} for p in PEERS],
            'source_accounts': [{'id': src, 'provider': 'fixture', 'owner_type': 'person',
                'owner_id': 'h2-soren' if src == 'h2-common-b' else 'h2-iris'} for src in SOURCES]})
        with engine.begin() as c:
            c.execute(insert(household_membership), [dict(household_id=HOME, person_id='h2-'+p, state='allowed', revision=1) for p in PEERS])
            c.execute(insert(external_identity_binding), [dict(issuer=ISSUER, subject='h2-sub-'+p,
                household_id=HOME, person_id='h2-'+p, state='allowed', revision=1) for p in PEERS])
            c.execute(insert(publication_scope).values(household_id=HOME, publication_key=a.Publication.BOOKING.value, approved=True))
        records = tuple(a.FixtureObservation(src, obj, 1, topic, risk)
            for src in SOURCES[:2] for obj, topic, risk in (
                (a.Object.BOOKING, a.Topic.BOOKING, a.Safety.HIGH_RISK),
                (a.Object.SCHOOL, a.Topic.SCHOOL, a.Safety.UNKNOWN)))
        self.repository = a.FixtureRepository(records + (records[0],
            a.FixtureObservation(SOURCES[2], a.Object.SCHOOL, 1, a.Topic.SCHOOL, a.Safety.CLEAR)),
            (a.FixturePublication(a.Publication.BOOKING, a.Step.BOOKING),))
        self.authorization = a.AuthorizationService(engine, self.repository, synthetic_only=True)
        # Independently declared test management authority, never obtained from login.
        self.controller = self.authorization.harness_context(HOME, 'h2-soren',
            sources=SOURCES, publications=(a.Publication.BOOKING,))
        for p in PEERS:
            for src in SOURCES if p == 'iris' else SOURCES[:2]:
                self.change(p, a.Kind.SOURCE, src, a.State.ALLOWED, 0, 'initial-'+p+'-'+src, True, True)
            self.change(p, a.Kind.PUBLICATION, a.Publication.BOOKING.value, a.State.ALLOWED, 0, 'initial-step-'+p)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        verifier = v.OfflineIdentityVerifier(issuer=ISSUER, audience='h2-fictional-client', public_keys={
            'h2-key': key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)})
        self.sessions = s.SessionService(engine, verifier, self.repository, synthetic_only=True)
        self._bearers = {}
        for p in PEERS:
            challenge = verifier.challenge(); now = int(time())
            token = jwt.encode(dict(iss=ISSUER, sub='h2-sub-'+p, aud='h2-fictional-client',
                iat=now-1, nbf=now-1, exp=now+120, nonce=challenge.nonce), key, algorithm='RS256', headers={'kid': 'h2-key'})
            proof = verifier.verify(token, challenge)
            result = self.sessions.establish(proof, HOME, request_id='h2-session-'+p)
            if result.outcome is not s.Outcome.COMMITTED or not result.bearer:
                # UNKNOWN is not retried or coerced; no partial preview is published.
                raise PreviewError()
            self._bearers[p] = result.bearer
        self.api = api.FictionalReadAPI(self.sessions, HOME, synthetic_only=True)

    def change(self, peer, kind, resource, state, revision, request, observations=False, security=False):
        command = a.Change(HOME, kind, 'h2-'+peer, resource, state, revision, request, observations, security)
        result = self.authorization.commit(self.controller, self.authorization.submit(self.controller, command), confirm=True)
        if result.outcome is not a.Outcome.COMMITTED:
            raise PreviewError()

    async def read(self, peer, *, limit=LIMIT, offset=0):
        events = []
        async def receive(): return {'type': 'http.request', 'body': b'', 'more_body': False}
        async def send(event): events.append(event)
        await self.api({'type': 'http', 'method': 'GET', 'path': '/v0/workbench',
            'raw_path': b'/v0/workbench', 'query_string': f'limit={limit}&offset={offset}'.encode(),
            'headers': [(b'authorization', b'Bearer '+self._bearers[peer].encode())]}, receive, send)
        if (len(events) != 2 or events[0].get('type') != 'http.response.start'
                or events[0].get('status') != 200 or events[1].get('type') != 'http.response.body'
                or events[1].get('more_body') is not False
                or dict(events[0]['headers']).get(b'cache-control') != b'no-store, no-cache, max-age=0'):
            raise PreviewError()
        return validate_response(events[1]['body'])

    async def capture(self, phase):
        peers = []
        for p in PEERS:
            first = await self.read(p)
            # Trusted fixed fixture <=5 items. Fresh backend requests, not client dedupe.
            total = max(first[lane]['total'] for lane in ('observations', 'security', 'published_steps'))
            if total > 6:
                raise PreviewError()
            pages = [first] + [await self.read(p, offset=offset) for offset in range(LIMIT, total, LIMIT)]
            peers.append({'peer': p, 'pages': pages})
        return {'phase': phase, 'peers': peers}

    async def capture_all(self):
        scenarios = [await self.capture('initial')]
        self.change('iris', a.Kind.SOURCE, SOURCES[0], a.State.REVOKED, 1, 'h2-revoke-source')
        scenarios.append(await self.capture('source-revoked'))
        self.change('iris', a.Kind.PUBLICATION, a.Publication.BOOKING.value, a.State.REVOKED, 1, 'h2-revoke-publication')
        scenarios.append(await self.capture('publication-revoked'))
        for src in SOURCES[1:]:
            self.change('iris', a.Kind.SOURCE, src, a.State.ALLOWED, 1, 'h2-observation-only-'+src, True, False)
        scenarios.append(await self.capture('observation-only'))
        return {'schema': 'h2-offline-preview-v1', 'synthetic_only': True, 'scenarios': scenarios}


def _migrate_disposable(engine):
    # Never run env.py: it discovers DATABASE_URL/default runtime DB. This isolated
    # EnvironmentContext uses ONLY our newly created connection and existing revisions.
    config = Config(); config.set_main_option('script_location', str(ROOT/'migrations'))
    script = ScriptDirectory.from_config(config)
    with engine.connect() as connection:
        with EnvironmentContext(config, script, fn=lambda rev, ctx: script._upgrade_revs('head', rev)) as context:
            context.configure(connection=connection, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()


def generate(output, *, synthetic_only=False):
    if synthetic_only is not True or not isinstance(output, Path):
        raise PreviewError()
    # New directory only: no overwriting, deletion or following existing symlinks.
    output = output.absolute()
    if output.exists() or any(p.is_symlink() or p.is_junction() for p in (output, *output.parents)):
        raise PreviewError()
    with TemporaryDirectory(prefix='family-os-h2-synthetic-') as temporary:
        engine = create_db('sqlite:///'+(Path(temporary)/'disposable.sqlite3').as_posix())
        try:
            _migrate_disposable(engine)
            bundle = asyncio.run(Harness(engine, synthetic_only=True).capture_all())
        finally:
            engine.dispose()
    # All keys, assertions, bearer state and the entire database stay out of assets.
    serialized = json.dumps(bundle, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(',', ':'))
    if len(serialized) > 131072:
        raise PreviewError()
    assets = {name: (HERE/name).read_bytes() for name in ('index.html', 'h2-translations.js', 'presentation.js', 'app.js')}
    assets['styles.css'] = (ROOT/'prototypes/h0-workbench/styles.css').read_bytes()
    assets['i18n.js'] = (ROOT/'prototypes/h0-workbench/i18n.js').read_bytes()
    assets['snapshot.js'] = ('globalThis.FamilyH2Snapshot = '+serialized+';\n').encode('ascii')
    output.mkdir(parents=True, exist_ok=False)
    for name, body in assets.items():
        with (output/name).open('xb') as file:
            file.write(body)
    return output/'index.html'


def main():
    parser = argparse.ArgumentParser(description='Generate a fictional-only offline H2 preview', allow_abbrev=False)
    parser.add_argument('--synthetic-only', action='store_true', required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    try:
        generate(args.output_directory, synthetic_only=args.synthetic_only)
    except Exception:
        parser.exit(1, 'Fictional preview unavailable; use a new output directory.\n')
    print('H2 fictional preview generated. Historical snapshots only; not authentication or live authorization.')


if __name__ == '__main__':
    main()
