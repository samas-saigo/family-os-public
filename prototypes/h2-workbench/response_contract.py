"""Strict G3b response shape validation, not authorization or domain inference."""
import json
import re

SCHEMA = 'g3b-fictional-read-v1'
TOPICS = {'fictional-booking', 'fictional-school'}
OBJECTS = {'invented-copper-booking', 'invented-willow-school'}
SAFETY = {'declared-clear', 'declared-high-risk', 'unknown-not-clear'}
STEPS = {'inspect-fictional-booking', 'inspect-fictional-school'}


class PreviewError(ValueError):
    def __init__(self):
        super().__init__('Fictional preview unavailable')


def _keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise PreviewError()


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise PreviewError()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PreviewError()
        result[key] = value
    return result


def validate_response(body):
    """Accept only actual bounded JSON bytes; unknown fields fail, never strip them."""
    try:
        if type(body) is not bytes or not 1 <= len(body) <= 32768:
            raise PreviewError()
        def invalid(_): raise PreviewError()
        data = json.loads(body, object_pairs_hook=_pairs, parse_constant=invalid)
        _keys(data, ('schema', 'synthetic_only', 'pagination', 'observations', 'security', 'published_steps'))
        if data['schema'] != SCHEMA or data['synthetic_only'] is not True:
            raise PreviewError()
        _keys(data['pagination'], ('limit', 'offset'))
        limit, offset = data['pagination']['limit'], data['pagination']['offset']
        _integer(limit, 1, 20); _integer(offset, 0, 128)
        for lane in ('observations', 'security', 'published_steps'):
            page = data[lane]
            _keys(page, ('items', 'total', 'has_more'))
            _integer(page['total'], 0, 128)
            if (type(page['items']) is not list or len(page['items']) > limit
                    or len(page['items']) != min(limit, max(0, page['total']-offset))
                    or type(page['has_more']) is not bool
                    or page['has_more'] != (offset+len(page['items']) < page['total'])):
                raise PreviewError()
            identities = set()
            for row in page['items']:
                if lane == 'published_steps':
                    _keys(row, ('publication_id', 'step'))
                    if row['publication_id'] not in TOPICS or row['step'] not in STEPS:
                        raise PreviewError()
                    identity = row['publication_id']
                else:
                    fields = {'source_id', 'provider', 'object_id', 'generation', 'topic'}
                    _keys(row, fields | ({'safety'} if lane == 'security' else set()))
                    if (type(row['source_id']) is not str or re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', row['source_id']) is None
                            or row['provider'] != 'fixture' or row['object_id'] not in OBJECTS
                            or row['topic'] not in TOPICS
                            or (lane == 'security' and row['safety'] not in SAFETY)):
                        raise PreviewError()
                    _integer(row['generation'], 1, 1000000)
                    identity = (row['source_id'], row['object_id'])
                if identity in identities:
                    raise PreviewError()
                identities.add(identity)
        return data
    except Exception:
        raise PreviewError() from None
