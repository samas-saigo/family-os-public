"""Fixed synthetic fixtures; HTTP is mocked, never live Ollama or model downloads."""
from copy import deepcopy
import json
import socket
import subprocess
import time

import pytest

from experiments import local_thinking_benchmark as b

DIGEST = 'a' * 64
LABEL = {'relevance_label': 'uncertain', 'domain_path': None, 'action_label': 'uncertain'}


class API:
    def __init__(self, model=b.MODELS[1]):
        self.model = model
        self.calls = []
        self.digest = DIGEST
        self.capabilities = ['completion', 'thinking']
        self.mutate = lambda value, count: value
        self.quant = 'Q4_K_M'

    def request(self, method, path, body=None, *, deadline):
        assert deadline > 0
        self.calls.append((method, path, deepcopy(body)))
        if path == '/api/tags':
            return {'models': [{'name': self.model, 'digest': self.digest}]}
        if path == '/api/version':
            return {'version': '0.40.6'}
        if path == '/api/show':
            return {'capabilities': self.capabilities, 'details': {
                'format': 'gguf', 'family': 'qwen3', 'parameter_size': '4.0B' if self.model == b.MODELS[0] else '8.2B',
                'quantization_level': self.quant}}
        if path == '/api/ps':
            return {'models': [{'name': self.model, 'digest': self.digest, 'size': 100, 'size_vram': 100}]}
        assert path == '/api/generate'
        value = {'model': self.model, 'done': True, 'done_reason': 'stop',
                 'response': json.dumps(LABEL), 'eval_count': 20, 'eval_duration': 1000000000,
                 'prompt_eval_count': 400, 'total_duration': 1200000000}
        if body.get('think') is True:
            value['thinking'] = 'Synthetic reasoning only.'
        return self.mutate(value, len([v for v in self.calls if v[1] == path]))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **kw: pytest.fail('live network'))
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **kw: pytest.fail('subprocess'))


def run(api=None, **kw):
    api = api or API()
    return b.run(model=api.model, thinking='off', expected_digest=DIGEST, api=api, **kw)


def test_original37_exact_identity_safe_gates_and_old_denominators():
    api = API()
    result = run(api, full=True)
    assert result['completed'] and result['identity_verified']
    item = result['runs'][0]
    assert item['diagnostics']['status_counts'] == {'valid': 34, 'projection_rejected': 3}
    assert item['legacy_metrics']['model']['action_required_truth_count'] == 6
    assert item['legacy_metrics']['model']['action_decisive_count'] == 14
    assert item['legacy_metrics']['model']['action_required_miss_count'] == 6
    assert item['diagnostics']['required_to_uncertain'] == 6
    assert item['diagnostics']['required_to_not_required'] == 0
    assert result['manifest']['historical_weights_verified'] is False
    assert result['residency_after']['gpu_fraction'] == 1
    calls = [v[2] for v in api.calls if v[1] == '/api/generate']
    assert len(calls) == 34
    for request in calls:
        assert request['think'] is False
        assert set(request) == {'model', 'prompt', 'format', 'stream', 'options', 'keep_alive', 'think'}
        assert request['options'] == {'temperature': 0, 'seed': 0, 'num_ctx': 4096, 'num_predict': 256}
        assert 'context' not in request and 'messages' not in request
        assert not any(k in request['prompt'] for k in ('fake_response', 'expected', 'source_record_id'))


@pytest.mark.parametrize('mode', b.MODES)
def test_legacy_omission_is_distinct_from_explicit_controls(mode):
    api = API(b.MODELS[0])
    result = b.run(model=api.model, thinking=mode, expected_digest=DIGEST, api=api)
    assert result['completed']
    assert len(result['runs'][0]['cases']) == 5
    for _, path, request in api.calls:
        if path == '/api/generate':
            if mode == 'legacy-omitted':
                assert 'think' not in request
            else:
                assert request['think'] is (mode == 'on')
            assert 'think' not in request['options']
    assert result['manifest']['thinking'] == mode
    assert result['manifest']['selected'] == 5
    # A smoke run never pretends its five cases have the full 6/14 denominator.
    assert result['runs'][0]['legacy_metrics']['model']['action_decisive_count'] <= 5


@pytest.mark.parametrize('capabilities', [[], ['completion']])
@pytest.mark.parametrize('mode', ['on', 'off'])
def test_missing_thinking_capability_is_incompatible_before_inference(capabilities, mode):
    api = API(b.MODELS[0])
    api.capabilities = capabilities
    with pytest.raises(b.Incompatible):
        b.run(model=api.model, thinking=mode, expected_digest=DIGEST, api=api)
    assert not any(path == '/api/generate' for _, path, _ in api.calls)


@pytest.mark.parametrize('mode,trace', [('off', 'thinking'), ('off', ' '), ('on', '')])
def test_requested_thinking_needs_observed_compatible_response(mode, trace):
    api = API()
    api.mutate = lambda v, n: dict(v, thinking=trace)
    result = b.run(model=api.model, thinking=mode, expected_digest=DIGEST, api=api)
    assert not result['completed'] and 'not_observed' in result['abort_reason']
    assert result['runs'][0]['cases'][0]['status'] == 'incompatible'
    assert len([v for v in api.calls if v[1] == '/api/generate']) == 1


@pytest.mark.parametrize('model,mode', [('other', 'off'), (b.MODELS[1], 'legacy-omitted'),
                                       (b.MODELS[0], True), (b.MODELS[0], None)])
def test_config_allowlist(model, mode):
    with pytest.raises(b.ExperimentError):
        b.run(model=model, thinking=mode, expected_digest=DIGEST, api=API())


@pytest.mark.parametrize('kw', [{'expected_digest': 'bad'}, {'expected_digest': 'b' * 64},
                              {'repeats': True}, {'repeats': 4}, {'full': 1}])
def test_digest_and_budget_configuration_rejected(kw):
    with pytest.raises(b.ExperimentError):
        b.run(**(dict(model=b.MODELS[1], thinking='off', expected_digest=DIGEST, api=API()) | kw))


def test_8b_quantization_is_not_silently_substituted():
    api = API()
    api.quant = 'Q8_0'
    with pytest.raises(b.Incompatible):
        run(api)


@pytest.mark.parametrize('change', [
    {'response': '<think>x</think>' + json.dumps(LABEL)},
    {'response': 'not JSON'}, {'response': ''}, {'thinking': None},
    {'response': json.dumps(dict(LABEL, extra='x'))}, {'extra': True},
    {'response': '{"action_label":"required","action_label":"uncertain"}'},
    {'eval_count': 257}, {'prompt_eval_count': 3841}, {'done_reason': 'other'},
    {'model': 'wrong'}, {'done': False}, {'eval_duration': True},
])
def test_invalid_output_never_repaired_or_called_valid(change):
    api = API()
    api.mutate = lambda v, n: dict(v, **change)
    result = run(api)
    rows = result['runs'][0]['cases']
    assert all(r['status'] in {'invalid_output', 'protocol_failure'} and r['predicted'] is None for r in rows)
    assert rows[0]['raw_envelope'].items() >= change.items()
    if rows[0]['status'] == 'protocol_failure':
        assert not result['completed'] and len(rows) == 1
        assert 'legacy_metrics' not in result['runs'][0]
    else:
        assert result['runs'][0]['diagnostics']['valid_only_action_accuracy'] is None


def test_thinking_truncation_is_reported_without_raising_256_budget():
    api = API()
    api.mutate = lambda v, n: dict(v, done_reason='length', thinking='', response='')
    result = b.run(model=api.model, thinking='on', expected_digest=DIGEST, api=api)
    assert result['runs'][0]['diagnostics']['status_counts'] == {'budget_truncated': 5}
    assert all(v[2]['options']['num_predict'] == 256 for v in api.calls if v[1] == '/api/generate')


def test_raw_trace_is_separate_final_answer_and_split_tokens_are_unknown():
    api = API()
    result = b.run(model=api.model, thinking='on', expected_digest=DIGEST, api=api)
    row = result['runs'][0]['cases'][0]
    assert row['status'] == 'valid'
    assert row['raw_envelope']['thinking'] == 'Synthetic reasoning only.'
    assert row['raw_envelope']['response'] == json.dumps(LABEL)
    assert row['reasoning_token_count'] is None and row['final_token_count'] is None
    assert row['tokens_per_second'] == 20


def test_model_invalid_and_false_ignores_are_separate():
    api = API()
    api.mutate = lambda v, n: dict(v, response=json.dumps(dict(LABEL, action_label='not_required')))
    result = run(api, full=True)
    assert result['runs'][0]['diagnostics']['required_to_not_required'] == 6
    assert result['runs'][0]['diagnostics']['required_to_uncertain'] == 0
    assert result['runs'][0]['legacy_metrics']['model']['action_correct_count'] == 8
    api.mutate = lambda v, n: dict(v, response=json.dumps(dict(LABEL, domain_path='home/insurance')))
    result = run(api, full=True)
    assert result['runs'][0]['diagnostics']['status_counts']['invalid_output'] == 34
    assert result['runs'][0]['diagnostics']['required_to_uncertain'] == 0
    assert result['runs'][0]['diagnostics']['invalid_required_count'] == 6


def test_repeats_do_not_inflate_unique_denominators_or_reuse_context():
    result = run(full=True, repeats=3)
    assert len(result['runs']) == 3
    assert all(v['legacy_metrics']['model']['action_required_truth_count'] == 6 for v in result['runs'])
    assert all(v['diagnostics']['status_counts']['valid'] == 34 for v in result['runs'])


def test_final_identity_loss_removes_model_attributed_metrics():
    api = API()
    def change(v, n):
        if n == 5:
            api.digest = 'b' * 64
        return v
    api.mutate = change
    result = run(api)
    assert not result['completed'] and not result['identity_verified']
    assert 'legacy_metrics' not in result['runs'][0]
    assert 'diagnostics' not in result['runs'][0]


def test_api_failure_does_not_retry_or_invent_predictions():
    api = API()
    def fail(v, n):
        raise b.ExperimentError('PRIVATE_DETAIL')
    api.mutate = fail
    result = run(api)
    assert not result['completed'] and 'PRIVATE_DETAIL' not in json.dumps(result)
    assert result['runs'][0]['cases'][0]['status'] == 'api_failure'
    assert len([v for v in api.calls if v[1] == '/api/generate']) == 1


def test_save_is_local_unique_and_not_a_resume_input(tmp_path, monkeypatch):
    monkeypatch.setattr(b, 'ROOT', tmp_path)
    monkeypatch.setattr(b, 'OUTPUT', tmp_path / '.local/local-ai-benchmark')
    report = {'raw_envelope': 'SYNTHETIC_TRACE'}
    first, second = b.save(report), b.save(report)
    assert first != second
    assert json.loads((tmp_path / first).read_text()) == report


def test_cli_does_not_print_raw_case_or_reasoning(tmp_path, monkeypatch, capsys):
    result = b.run(model=b.MODELS[1], thinking='on', expected_digest=DIGEST, api=API())
    monkeypatch.setattr(b, 'run', lambda **kw: result)
    monkeypatch.setattr(b, 'save', lambda value: '.local/local-ai-benchmark/unique/report.json')
    assert b.main(['--synthetic-only', '--model', b.MODELS[1], '--thinking', 'on', '--expected-digest', DIGEST]) == 0
    text = capsys.readouterr().out
    assert 'Synthetic reasoning only.' not in text and 'UNTRUSTED_METADATA_JSON' not in text
    assert 'raw_envelope' not in text
    assert all(row['id'] not in text for row in result['runs'][0]['cases'])


@pytest.mark.parametrize('arg', ['--holdout', '--development', '--url', '--file', '--host', '--num-predict'])
def test_cli_has_no_arbitrary_data_or_budget_inputs(arg):
    with pytest.raises(SystemExit):
        b.main(['--synthetic-only', '--model', b.MODELS[1], arg, 'x'])


def test_http_boundary_fixed_numeric_loopback_exact_operations_and_cleanup(monkeypatch):
    calls = []
    class Wire:
        def settimeout(self, seconds):
            assert 0 < seconds <= 60
        def shutdown(self, *a):
            pass
    class Response:
        status = 200
        def read(self, maximum):
            assert maximum == 65537
            return b'{"version":"0.40.6"}'
    class Connection:
        def __init__(self, host, port, timeout):
            assert (host, port) == ('127.0.0.1', 11434)
            assert 0 < timeout <= 5
            self.sock = Wire()
        def connect(self):
            pass
        def request(self, method, path, **kw):
            calls.append((method, path))
        def getresponse(self):
            return Response()
        def close(self):
            calls.append('closed')
    monkeypatch.setattr(b.http.client, 'HTTPConnection', Connection)
    api = b.LocalAPI()
    assert api.request('GET', '/api/version', deadline=time.monotonic() + 10)['version'] == '0.40.6'
    assert calls == [('GET', '/api/version'), 'closed']
    for method, path, body in [('POST', '/api/pull', {}), ('GET', 'http://elsewhere', None),
                               ('POST', '/api/show', {'model': 'other'}),
                               ('POST', '/api/generate', {}), ('GET', '/api/tags', {})]:
        with pytest.raises(b.ExperimentError):
            api.request(method, path, body, deadline=time.monotonic() + 10)
    assert calls == [('GET', '/api/version'), 'closed']


def test_corpus_tampering_rejected_before_network(tmp_path, monkeypatch):
    copy = tmp_path / 'corpus.json'
    copy.write_bytes(b.FIXTURE.read_bytes() + b' ')
    monkeypatch.setattr(b, 'FIXTURE', copy)
    with pytest.raises(b.ExperimentError):
        run()


def test_windows_lf_identity_in_memory_does_not_rewrite_fixture(tmp_path, monkeypatch):
    copy = tmp_path / 'corpus.json'
    original = b.FIXTURE.read_bytes().replace(b'\r\n', b'\n')
    copy.write_bytes(original.replace(b'\n', b'\r\n'))
    monkeypatch.setattr(b, 'FIXTURE', copy)
    assert len(b.corpus()[1]) == 37
    assert copy.read_bytes() != original


@pytest.mark.parametrize('status', [301, 302, 401, 500, 400, 422])
def test_generate_http_errors_never_follow_redirects_or_retry(monkeypatch, status):
    policy, cases = b.corpus()
    calls = []
    class Wire:
        def settimeout(self, seconds):
            pass
        def shutdown(self, *a):
            pass
    class Connection:
        def __init__(self, *a, **kw):
            self.sock = Wire()
        def connect(self):
            pass
        def request(self, method, path, **kw):
            calls.append((method, path, json.loads(kw['body'])))
        def getresponse(self):
            return type('Response', (), {'status': status})()
        def close(self):
            calls.append('closed')
    monkeypatch.setattr(b.http.client, 'HTTPConnection', Connection)
    exception = b.Incompatible if status in {400, 422} else b.ExperimentError
    request = b.payload(cases[0][0], policy, b.MODELS[1], 'off')
    with pytest.raises(exception):
        b.LocalAPI().request('POST', '/api/generate', request, deadline=time.monotonic() + 5)
    assert len(calls) == 2 and calls[-1] == 'closed'


@pytest.mark.parametrize('raw', [b'x' * 65537, b'{"x":1,"x":2}', b'[]', b'not JSON', b'\xff'])
def test_http_size_json_and_type_bounds(monkeypatch, raw):
    class Wire:
        def settimeout(self, *a):
            pass
        def shutdown(self, *a):
            pass
    class Connection:
        sock = Wire()
        def __init__(self, *a, **kw):
            pass
        def connect(self):
            pass
        def request(self, *a, **kw):
            pass
        def getresponse(self):
            return type('Response', (), {'status': 200, 'read': lambda self, size: raw})()
        def close(self):
            pass
    monkeypatch.setattr(b.http.client, 'HTTPConnection', Connection)
    with pytest.raises(b.ExperimentError):
        b.LocalAPI().request('GET', '/api/version', deadline=time.monotonic() + 5)


@pytest.mark.parametrize('edit', [lambda p: p.update(context=[1]), lambda p: p['options'].update(think=False),
                                 lambda p: p.update(think=0), lambda p: p.update(prompt='private input'),
                                 lambda p: p['options'].update(num_predict=2048)])
def test_transport_rejects_nonfixture_or_changed_config_before_connect(monkeypatch, edit):
    policy, cases = b.corpus()
    value = b.payload(cases[0][0], policy, b.MODELS[1], 'off')
    edit(value)
    monkeypatch.setattr(b.http.client, 'HTTPConnection', lambda *a, **kw: pytest.fail('connection'))
    with pytest.raises(b.ExperimentError):
        b.LocalAPI().request('POST', '/api/generate', value, deadline=time.monotonic() + 5)


def test_deadline_failure_no_request(monkeypatch):
    monkeypatch.setattr(b.http.client, 'HTTPConnection', lambda *a, **kw: pytest.fail('connection'))
    with pytest.raises(b.ExperimentError):
        b.LocalAPI().request('GET', '/api/version', deadline=time.monotonic() - 1)


def test_empty_telemetry_is_unknown_not_fabricated_speed():
    api = API()
    api.mutate = lambda value, n: {k: v for k, v in value.items() if k not in {'eval_count', 'eval_duration'}}
    result = run(api)
    assert result['runs'][0]['cases'][0]['tokens_per_second'] is None
    assert result['runs'][0]['diagnostics']['output_token_rate']['count'] == 0


def test_experiment_imports_cannot_grow_provider_or_database_wiring():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(b.__file__).read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(v.name for v in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or '')
    assert not any({'db', 'schema', 'sqlalchemy', 'keyring', 'services', 'requests', 'subprocess',
                    'action_evaluation', 'action_model_benchmark'}.intersection(v.split('.')) for v in imports)
    assert all('local_thinking_benchmark' not in f.read_text() for f in (b.ROOT / 'src/family_os').glob('*.py'))


def test_exact_historical_flat_payload_preserved_when_omitted():
    policy, cases = b.corpus()
    projection = b.project_metadata(cases[0][0])
    assert b.payload(cases[0][0], policy, b.MODELS[0], 'legacy-omitted') == b.old.request_payload(
        projection, policy, 'flat-domain')


def test_model_change_midrun_stops_before_another_generation():
    api = API()
    def change(v, n):
        api.digest = 'b' * 64
        return v
    api.mutate = change
    result = run(api)
    assert not result['identity_verified'] and not result['completed']
    assert len([v for v in api.calls if v[1] == '/api/generate']) == 1
    assert result['runs'][0]['coverage']['not_attempted'] == 3


@pytest.mark.parametrize('mode', ['off', 'on', 'legacy-omitted'])
def test_complete_mocked_http_smoke_including_wire_serialization(monkeypatch, mode):
    backing = API(b.MODELS[0] if mode == 'legacy-omitted' else b.MODELS[1])
    class Wire:
        def settimeout(self, *a):
            pass
        def shutdown(self, *a):
            pass
    class Connection:
        def __init__(self, host, port, timeout):
            assert (host, port) == ('127.0.0.1', 11434)
            self.sock = Wire()
        def connect(self):
            pass
        def request(self, method, path, body=None, **kw):
            self.result = backing.request(method, path, json.loads(body) if body else None, deadline=1)
        def getresponse(self):
            raw = json.dumps(self.result).encode()
            return type('Response', (), {'status': 200, 'read': lambda self, size: raw[:size]})()
        def close(self):
            pass
    monkeypatch.setattr(b.http.client, 'HTTPConnection', Connection)
    result = b.run(model=backing.model, thinking=mode, expected_digest=DIGEST)
    assert result['completed'] and result['identity_verified']
    assert result['runs'][0]['coverage']['status_counts'] == {'valid': 5}


def test_historical_generation_budget_cannot_silently_drift(monkeypatch):
    monkeypatch.setattr(b.old, 'OPTIONS', dict(b.old.OPTIONS, num_predict=2048))
    with pytest.raises(b.ExperimentError, match='generation_options_changed'):
        run()


def test_required_prediction_does_not_grant_action_authority():
    api = API()
    api.mutate = lambda v, n: dict(v, response=json.dumps(dict(LABEL, action_label='required')))
    row = run(api)['runs'][0]['cases'][0]
    assert row['predicted'] == 'required'
    assert row['requires_human_confirmation'] is True
    assert row['uncertainty_retained'] is False
