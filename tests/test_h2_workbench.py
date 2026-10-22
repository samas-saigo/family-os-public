"""Real H2 -> G3b -> durable fictional auth -> localized presentation integration."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT/'prototypes/h2-workbench'
sys.path.insert(0, str(PROTOTYPE))
import generate_preview as h2
from response_contract import PreviewError, validate_response


@pytest.fixture
def harness(engine):
    return h2.Harness(engine, synthetic_only=True)


@pytest.fixture
def response(harness):
    return asyncio.run(harness.read('iris'))


def packed(value):
    return json.dumps(value, allow_nan=False).encode()


def node_view(bundle, peer='iris', phase='initial', page=0, locale='zh-CN'):
    # No fixture JSON substitution: input is captured from real G3b responses.
    node = shutil.which('node'); assert node
    script = "const fs=require('node:fs'),p=require('./prototypes/h2-workbench/presentation.js'); const b=JSON.parse(fs.readFileSync(0,'utf8')); process.stdout.write(JSON.stringify(p.view(b,...process.argv.slice(1).map((v,i)=>i===2?Number(v):v))));"
    result = subprocess.run([node, '-e', script, peer, phase, str(page), locale],
        input=json.dumps(bundle), capture_output=True, text=True, encoding='utf-8', cwd=ROOT, timeout=30)
    assert result.returncode == 0, 'H2 presentation failed'
    return json.loads(result.stdout)


def test_actual_api_read_to_bilingual_display_with_no_fabricated_fields(harness):
    bundle = asyncio.run(harness.capture_all())
    zh = node_view(bundle); en = node_view(bundle, locale='en-US')
    assert [l['title'] for l in zh['lanes']] == ['已授权的信息', '安全审核信息', '已共享的家庭事项（演示）']
    assert zh['lanes'][0]['total'] == en['lanes'][0]['total'] == 5
    assert zh['lanes'][1]['total'] == en['lanes'][1]['total'] == 4
    assert zh['lanes'][2]['rows'] == [{'identifier': 'fictional-booking', 'label': '查看虚构预订'}]
    assert en['lanes'][2]['rows'][0]['label'] == 'Inspect fictional booking'
    assert [r['source'] for r in zh['lanes'][0]['rows']] == [r['source'] for r in en['lanes'][0]['rows']]
    forbidden = {'due', 'title', 'summary', 'accepted', 'assignee', 'email', 'sender', 'body', 'permissions', 'readers'}
    assert not forbidden.intersection(zh['lanes'][0]['rows'][0])
    assert set(zh['lanes'][2]['rows'][0]) == {'identifier', 'label'}


def test_two_separate_sessions_same_household_authorized_shared_and_private_data(harness, engine):
    from family_os.schema import household_session
    with engine.connect() as c:
        sessions = c.execute(select(household_session.c.id, household_session.c.household_id,
                                    household_session.c.person_id, household_session.c.secret_hash)).all()
    assert len(sessions) == 2 and len({r.id for r in sessions}) == len({r.secret_hash for r in sessions}) == 2
    assert {r.household_id for r in sessions} == {h2.HOME}
    assert {r.person_id for r in sessions} == {'h2-iris', 'h2-soren'}
    bundle = asyncio.run(harness.capture_all())
    iris = bundle['scenarios'][0]['peers'][0]['pages']; soren = bundle['scenarios'][0]['peers'][1]['pages']
    left = [r for page in iris for r in page['observations']['items']]
    right = [r for page in soren for r in page['observations']['items']]
    assert len(left) == 5 and len(right) == 4
    assert [r for r in left if r['source_id'] != 'h2-iris-private'] == right
    assert 'h2-iris-private' not in json.dumps(soren)
    assert 'h2-iris-private' in json.dumps(iris)
    assert iris[0]['published_steps'] == soren[0]['published_steps']


@pytest.mark.parametrize('locale', ['zh-CN', 'en-US'])
def test_revocation_fresh_api_reads_and_independent_publication(harness, locale):
    bundle = asyncio.run(harness.capture_all())
    initial = node_view(bundle, locale=locale)
    revoked = node_view(bundle, phase='source-revoked', locale=locale)
    published = node_view(bundle, phase='publication-revoked', locale=locale)
    observed = node_view(bundle, phase='observation-only', locale=locale)
    assert initial['lanes'][0]['total'] == 5 and revoked['lanes'][0]['total'] == 3
    assert revoked['lanes'][1]['total'] == 2 and revoked['lanes'][2]['total'] == 1
    assert published['lanes'][0]['total'] == 3 and published['lanes'][2]['total'] == 0
    assert observed['lanes'][0]['total'] == 3 and observed['lanes'][1]['total'] == 0
    # Source rights never derived from published steps or frontend switches.
    assert all(r['source'] != 'h2-common-a' for r in revoked['lanes'][0]['rows'])
    peer = node_view(bundle, peer='soren', phase='observation-only', locale=locale)
    assert [l['total'] for l in peer['lanes']] == [4, 4, 1]
    # Historical initial results remain historical; no claim of continuously authorized files.
    assert node_view(bundle, locale=locale) == initial


def test_backend_pagination_preserved_not_reconstructed_by_browser(harness):
    bundle = asyncio.run(harness.capture_all())
    pages = bundle['scenarios'][0]['peers'][0]['pages']
    assert [p['pagination']['offset'] for p in pages] == [0, 2, 4]
    assert [len(p['observations']['items']) for p in pages] == [2, 2, 1]
    for n, data in enumerate(pages):
        view = node_view(bundle, page=n)
        for lane in view['lanes']:
            assert lane['total'] == data[lane['lane']]['total']
            assert lane['hasMore'] == data[lane['lane']]['has_more']
            assert len(lane['rows']) == len(data[lane['lane']]['items'])
    assert not pages[-1]['observations']['has_more']


@pytest.mark.parametrize('field', ['schema', 'synthetic_only', 'pagination', 'observations', 'security', 'published_steps'])
def test_missing_top_level_fields_fail_closed(response, field):
    del response[field]
    with pytest.raises(PreviewError, match='^Fictional preview unavailable$'): validate_response(packed(response))


@pytest.mark.parametrize('field,value', [('schema', 'other'), ('synthetic_only', False), ('synthetic_only', 1),
    ('secret_hash', 'do-not-project'), ('bearer', 'secret'), ('household_id', 'other'), ('due', '2099-01-01')])
def test_wrong_schema_and_unauthorized_fields_rejected_never_stripped(response, field, value):
    response[field] = value
    with pytest.raises(PreviewError): validate_response(packed(response))


@pytest.mark.parametrize('lane,field,value', [
    ('observations', 'safety', 'declared-high-risk'), ('observations', 'raw_metadata', {}),
    ('observations', 'topic', 'new-topic'), ('observations', 'object_id', 'unknown-object'),
    ('observations', 'provider', 'gmail'), ('observations', 'generation', True),
    ('observations', 'generation', 0), ('observations', 'source_id', '<script>'),
    ('observations', 'source_id', 'x'*65), ('security', 'safety', 'safe'),
    ('published_steps', 'step', 'accept-task'), ('published_steps', 'publication_id', 'unknown'),
    ('published_steps', 'source_id', 'private-provenance'), ('published_steps', 'status', 'accepted'),
])
def test_strict_rows_unknown_enums_and_no_inferred_private_fields(response, lane, field, value):
    response[lane]['items'][0][field] = value
    with pytest.raises(PreviewError): validate_response(packed(response))


@pytest.mark.parametrize('lane', ['observations', 'security', 'published_steps'])
def test_missing_row_fields_and_ambiguous_duplicates(response, lane):
    key = next(iter(response[lane]['items'][0])); del response[lane]['items'][0][key]
    with pytest.raises(PreviewError): validate_response(packed(response))


@pytest.mark.parametrize('field,value', [('limit', 0), ('limit', 21), ('limit', True), ('offset', -1), ('offset', 129)])
def test_query_shape_bounds(response, field, value):
    response['pagination'][field] = value
    with pytest.raises(PreviewError): validate_response(packed(response))


@pytest.mark.parametrize('field,value', [('total', -1), ('total', 129), ('total', True), ('has_more', 1), ('has_more', False)])
def test_bad_totals_or_has_more(response, field, value):
    response['observations'][field] = value
    with pytest.raises(PreviewError): validate_response(packed(response))


@pytest.mark.parametrize('body', [b'', b'[]', b'{', b'{"schema":1,"schema":2}', b'{"x":NaN}', b'{"x":Infinity}', b'x'*32769])
def test_json_bounds_and_ambiguity(body):
    with pytest.raises(PreviewError): validate_response(body)


def test_duplicate_current_observation_rejected_at_shape_boundary(response):
    response['observations']['items'][1] = response['observations']['items'][0]
    with pytest.raises(PreviewError): validate_response(packed(response))


def test_actual_api_authentication_failure_has_no_partial_export(harness):
    harness._bearers['iris'] = 'x'*43
    with pytest.raises(PreviewError): asyncio.run(harness.capture_all())


def test_sessions_do_not_provision_management_capabilities(harness, monkeypatch):
    monkeypatch.setattr(harness.authorization, 'harness_context', lambda *a, **k: pytest.fail('no session-to-harness authority'))
    assert asyncio.run(harness.read('iris'))['observations']['total'] == 5


@pytest.mark.parametrize('flag', [False, 1, 'true', None])
def test_harness_exact_opt_in_before_any_setup(engine, flag):
    with pytest.raises(PreviewError): h2.Harness(engine, synthetic_only=flag)


def test_generator_real_migrations_ignore_runtime_environment_and_deterministic_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'no-real-runtime-database-is-ever-discovered')
    one, two = tmp_path/'one', tmp_path/'two'
    h2.generate(one, synthetic_only=True); h2.generate(two, synthetic_only=True)
    assert {p.name: p.read_bytes() for p in one.iterdir()} == {p.name: p.read_bytes() for p in two.iterdir()}
    assert {p.name for p in one.iterdir()} == {'index.html', 'h2-translations.js', 'i18n.js', 'snapshot.js', 'presentation.js', 'app.js', 'styles.css'}
    assert (one/'styles.css').read_bytes() == (ROOT/'prototypes/h0-workbench/styles.css').read_bytes()
    assert (one/'i18n.js').read_bytes() == (ROOT/'prototypes/h0-workbench/i18n.js').read_bytes()
    assert not any(p.suffix in ('.sqlite3', '.db', '.pem') for p in one.iterdir())
    data = json.loads((one/'snapshot.js').read_text().removeprefix('globalThis.FamilyH2Snapshot = ').removesuffix(';\n'))
    assert node_view(data)['lanes'][0]['total'] == 5
    for forbidden in ('Bearer ', 'secret_hash', 'session_id', 'intent_hash', 'BEGIN PRIVATE KEY', 'BEGIN PUBLIC KEY', 'access_token', 'id_token', 'issuer', 'nonce', 'h2-sub-'):
        assert forbidden not in (one/'snapshot.js').read_text()


def test_existing_output_or_symlink_rejected_without_overwriting(tmp_path):
    output = tmp_path/'existing'; output.mkdir(); marker = output/'keep.txt'; marker.write_text('keep')
    with pytest.raises(PreviewError): h2.generate(output, synthetic_only=True)
    assert marker.read_text() == 'keep' and list(output.iterdir()) == [marker]
    link = tmp_path/'link'; link.symlink_to(output, target_is_directory=True)
    with pytest.raises(PreviewError): h2.generate(link/'new', synthetic_only=True)
    assert not (output/'new').exists()


def test_generator_failure_before_export_writes_no_assets(tmp_path, monkeypatch):
    async def fail(self): raise PreviewError()
    monkeypatch.setattr(h2.Harness, 'capture_all', fail)
    target = tmp_path/'unpublished'
    with pytest.raises(PreviewError): h2.generate(target, synthetic_only=True)
    assert not target.exists()


@pytest.mark.parametrize('args', [[], ['--synthetic'], ['--synthetic-only=true'], ['--synthetic-only', '--database-url', 'invalid']])
def test_cli_requires_exact_opt_in_and_has_no_database_parameter(tmp_path, args):
    result = subprocess.run([sys.executable, str(PROTOTYPE/'generate_preview.py'), *args,
        '--output-directory', str(tmp_path/'never-created')], cwd=ROOT, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and not (tmp_path/'never-created').exists()


def test_only_actual_api_builds_payload_not_sql_or_h1_dataset(harness, monkeypatch):
    calls = []
    original = harness.api
    async def counted(scope, receive, send):
        calls.append(scope['path'])
        await original(scope, receive, send)
    harness.api = counted
    bundle = asyncio.run(harness.capture_all())
    assert len(calls) == 17 and set(calls) == {'/v0/workbench'}
    text = json.dumps(bundle)
    assert not any(bearer in text for bearer in harness._bearers.values())
    for filename in ('presentation.js', 'app.js'):
        code = (PROTOTYPE/filename).read_text()
        for forbidden in ('fetch(', 'XMLHttpRequest', 'WebSocket', 'localStorage', 'sessionStorage', 'indexedDB',
                          'innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function', 'document.cookie'):
            assert forbidden not in code
    code = (PROTOTYPE/'generate_preview.py').read_text()
    assert 'source_record' not in code and 'select(' not in code
    assert not any('fixtures.js' in (PROTOTYPE/f).read_text() for f in ('index.html', 'app.js', 'presentation.js'))


def test_browser_presentation_behavior_against_real_generated_responses(harness, tmp_path):
    bundle = asyncio.run(harness.capture_all())
    bundle_path = tmp_path/'approved-fiction.json'; bundle_path.write_text(json.dumps(bundle))
    result = subprocess.run([shutil.which('node'), str(ROOT/'tests/browser/h2-presentation.test.js'), str(bundle_path)],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert re.search(r'pass\s+24', result.stdout), result.stdout


def test_entry_csp_and_only_local_generated_resources():
    text = (PROTOTYPE/'index.html').read_text()
    for directive in ("default-src 'none'", "script-src 'self'", "style-src 'self'", "connect-src 'none'", "object-src 'none'", "form-action 'none'"):
        assert directive in text
    assert 'unsafe-inline' not in text and 'unsafe-eval' not in text
    assert '<html lang="zh-CN">' in text
    assert not re.search(r'<(?:form|iframe|object|embed)\b|\bon\w+=|https?://', text)
