"""G3b: in-process ASGI conformance only; no listener or production entrypoint."""
import asyncio
from dataclasses import dataclass, field
import json
import re
from urllib.parse import parse_qsl

from family_os._household_sessions import SessionService, Topic

CONTRACT_VERSION = 'g3b-fictional-read-v1'
_HEADERS = ((b'content-type', b'application/json'),
            (b'cache-control', b'no-store, no-cache, max-age=0'),
            (b'pragma', b'no-cache'), (b'expires', b'0'),
            (b'x-content-type-options', b'nosniff'))


class ContractError(ValueError):
    def __init__(self):
        super().__init__('Request unavailable')


@dataclass(frozen=True)
class _Prepared:
    """Ephemeral request specification, never an authorized response or lease."""
    bearer: str = field(repr=False)
    limit: int = 20
    offset: int = 0
    topic: Topic | None = None


def _request(scope):
    if (scope.get('type') != 'http' or scope.get('method') != 'GET'
            or scope.get('path') != '/v0/workbench'
            or scope.get('raw_path', b'/v0/workbench') != b'/v0/workbench'
            or scope.get('root_path', '') != ''):
        raise ContractError()
    headers = scope.get('headers', ())
    if type(headers) not in (list, tuple) or not 1 <= len(headers) <= 4:
        raise ContractError()
    values = {}
    for pair in headers:
        if type(pair) not in (list, tuple) or len(pair) != 2:
            raise ContractError()
        name, value = pair
        if (type(name) is not bytes or type(value) is not bytes or len(value) > 256
                or name not in (b'authorization', b'accept', b'content-length', b'host')
                or name in values):
            raise ContractError()
        values[name] = value
    if (values.get(b'accept', b'application/json') != b'application/json'
            or values.get(b'host', b'fictional.test') != b'fictional.test'
            or values.get(b'content-length', b'0') != b'0'):
        raise ContractError()
    auth = values.get(b'authorization', b'')
    if re.fullmatch(rb'Bearer [A-Za-z0-9_-]{43}', auth) is None:
        raise ContractError()
    query = scope.get('query_string', b'')
    if type(query) is not bytes or len(query) > 128:
        raise ContractError()
    # No percent aliases, blank values, ambiguous separators or Unicode filters.
    if query and re.fullmatch(rb'[a-z0-9_=&-]+', query) is None:
        raise ContractError()
    params = parse_qsl(query.decode('ascii'), keep_blank_values=True,
                       strict_parsing=True, max_num_fields=3)
    parsed = {}
    for name, value in params:
        if name not in ('limit', 'offset', 'topic') or name in parsed or not value:
            raise ContractError()
        parsed[name] = value
    for name in ('limit', 'offset'):
        if name in parsed and re.fullmatch(r'0|[1-9][0-9]{0,2}', parsed[name]) is None:
            raise ContractError()
    limit, offset = int(parsed.get('limit', '20')), int(parsed.get('offset', '0'))
    if not 1 <= limit <= 20 or not 0 <= offset <= 128:
        raise ContractError()
    topic = Topic(parsed['topic']) if 'topic' in parsed else None
    return _Prepared(auth[7:].decode('ascii'), limit, offset, topic)


def _serialize(projection, request):
    """Explicit field mapping only, after G2b2 authorizes each independent lane."""
    def identity(key, fields):
        return {'source_id': key[1], 'provider': 'fixture', 'object_id': key[2],
                'generation': fields[0], 'topic': fields[1].value}

    def page(rows, total):
        return {'items': rows, 'total': total,
                'has_more': request.offset + len(rows) < total}

    observations = [identity(key, fields) for key, fields in projection.observations]
    security = [dict(identity(key, fields), safety=fields[2].value)
                for key, fields in projection.security]
    steps = [{'publication_id': key.value, 'step': step.value}
             for key, step in projection.publications]
    result = {'schema': CONTRACT_VERSION, 'synthetic_only': True,
              'pagination': {'limit': request.limit, 'offset': request.offset},
              'observations': page(observations, projection.source_count),
              'security': page(security, projection.security_count),
              'published_steps': page(steps, projection.publication_count)}
    body = json.dumps(result, ensure_ascii=True, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('ascii')
    if len(body) > 32768:
        raise ContractError()
    return body


class FictionalReadAPI:
    """Trusted explicit single-household configuration; never client configuration.

    No login, mutation, management, callbacks, environment/DB discovery or listeners.
    Synchronous DB work is intentional for this bounded in-process contract only.
    """
    def __init__(self, sessions, household_id, *, synthetic_only=False):
        if (synthetic_only is not True or type(sessions) is not SessionService
                or type(household_id) is not str
                or re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', household_id) is None):
            raise ContractError()
        self._sessions, self._household = sessions, household_id

    async def _dispatch(self, prepared, send):
        # Fresh read at consumption: preparation retained no rows or old rights.
        # No await between read and serialization. Commit must succeed before bytes.
        try:
            projection = self._sessions.read(prepared.bearer, self._household,
                limit=prepared.limit, offset=prepared.offset, topic=prepared.topic)
            body = _serialize(projection, prepared)
        except Exception:
            await self._error(send)
            return
        await self._send(send, 200, body)

    @staticmethod
    async def _send(send, status, body):
        await send({'type': 'http.response.start', 'status': status,
                    'headers': list(_HEADERS) + [(b'content-length', str(len(body)).encode('ascii'))]})
        await send({'type': 'http.response.body', 'body': body, 'more_body': False})

    @classmethod
    async def _error(cls, send):
        # Same response for every rejection: no identity/source/route oracle.
        await cls._send(send, 400, b'{"error":"request_unavailable"}')

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            # Lifespan/WebSocket support is intentionally absent; never starts a server.
            raise ContractError()
        try:
            prepared = _request(scope)
            event = await asyncio.wait_for(receive(), timeout=1)
            if (type(event) is not dict or event.get('type') != 'http.request'
                    or event.get('body', b'') != b''
                    or event.get('more_body', False) is not False):
                raise ContractError()
        except Exception:
            await self._error(send)
            return
        # Send failures propagate to transport. Never attempt a second partial response.
        await self._dispatch(prepared, send)
