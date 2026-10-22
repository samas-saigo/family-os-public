"""One-case diagnostic: all HTTP is mocked, including the real CLI call chain."""
import builtins
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import runpy
import socket
import sys

import pytest

from experiments import single_email_diagnostic as d

CONFIG, ORIGINAL, PROJECTION = d.setup()
ABSTAIN = dict(state='abstain', steps=[], dates=[])


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail('Real socket/Ollama access forbidden')
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(socket.socket, 'connect', deny)


def envelope():
    return dict(model=CONFIG['model']['tag'], done=True, done_reason='stop',
                message=dict(role='assistant', content=json.dumps(ABSTAIN)),
                total_duration=120000000000, load_duration=80000000000,
                prompt_eval_count=500, prompt_eval_duration=1000000000,
                eval_count=80, eval_duration=39000000000)


class HTTP:
    def __init__(self, hook=None, phase=None):
        self.calls, self.responses, self.hook, self.phase = [], [], hook, phase
        self.timeouts = []

    def __call__(self, host, port, timeout):
        assert (host, port) == ('127.0.0.1', 11434) and 0 < timeout <= 5
        outer = self
        class Wire:
            def settimeout(self, seconds):
                assert 0 < seconds <= 180
                outer.timeouts.append(seconds)
            def close(self):
                pass
        class Response:
            status = 200
            def __init__(self, value):
                self.raw = io.BytesIO(json.dumps(value).encode())
                self.headers = {'Content-Type': 'application/json'}
            def getheaders(self):
                return list(self.headers.items())
            def getheader(self, k, default=None):
                return self.headers.get(k, default)
            def read1(self, n):
                if outer.phase:
                    outer.phase('body', self)
                return self.raw.read(n)
            def close(self):
                self.raw.close()
        class Connection:
            sock = Wire()
            def connect(self):
                if outer.phase:
                    outer.phase('connect', self)
            def request(self, method, path, body, headers):
                self.path = path
                value = json.loads(body) if body else None
                outer.calls.append((method, path, value, headers))
                self.value = outer.answer(method, path, value)
            def getresponse(self):
                if outer.phase:
                    outer.phase('headers', self)
                response = Response(self.value)
                outer.responses.append(response)
                return response
            def close(self):
                self.sock.close()
        return Connection()

    def answer(self, method, path, payload):
        values = {
            '/api/version': {'version': '0.40.6'},
            '/api/tags': {'models': [dict(name=CONFIG['model']['tag'], model=CONFIG['model']['tag'], digest=CONFIG['model']['digest'])]},
            '/api/show': dict(details={k: CONFIG['model'][k] for k in ('family', 'parameter_size', 'quantization_level')}, model_info={'general.architecture': 'qwen35'}, capabilities=['completion', 'thinking']),
            '/api/ps': {'models': []},
            '/api/chat': envelope(),
        }
        v = deepcopy(values[path])
        return self.hook(method, path, payload, v) if self.hook else v


def mocked(monkeypatch, hook=None, phase=None):
    http = HTTP(hook, phase)
    monkeypatch.setattr(d.http.client, 'HTTPConnection', http)
    return http


def test_frozen_identity_and_old_boundaries_unchanged():
    assert d.FREEZE == '09916e959bda2a719a5ef962017a1f56cb3f7b72'
    assert sha256((d.ROOT / d.CONFIG).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == d.CONFIG_SHA
    assert sha256((d.ROOT / 'experiments/email_model_evidence.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest() == d.PARENT_SHA
    assert all(CONFIG[k] == ORIGINAL[k] for k in ('model', 'prompt', 'output_schema', 'generation'))
    assert ORIGINAL['limits']['request_seconds'] == 60
    assert (CONFIG['limits']['chat_seconds'], CONFIG['limits']['metadata_seconds'], CONFIG['limits']['run_seconds'], CONFIG['limits']['connect_seconds']) == (180, 5, 240, 5)


def test_real_run_one_exact_input_no_gold_history_scores_or_raw_report(monkeypatch):
    http = mocked(monkeypatch)
    r = d.run()
    assert r['run_status'] == 'complete' and r['attempted'] == r['selected'] == 1
    assert r['identity_verified_at_end'] and r['initial_residency'] is None
    chats = [v for _, p, v, _ in http.calls if p == '/api/chat']
    assert len(chats) == 1
    request = chats[0]
    assert set(request) == {'model', 'messages', 'format', 'stream', 'think', 'options'}
    assert request == dict(model=ORIGINAL['model']['tag'], messages=[dict(role='system', content=ORIGINAL['prompt']), dict(role='user', content=d.wording.canonical(dict(PROJECTION.fields)))], format=ORIGINAL['output_schema'], **ORIGINAL['generation'])
    assert [p for _, p, _, _ in http.calls] == ['/api/version', '/api/tags', '/api/show', '/api/ps', '/api/version', '/api/tags', '/api/show', '/api/chat', '/api/version', '/api/tags', '/api/show']
    wire = request['messages'][1]['content']
    assert all(key not in wire for key in ('WC01-1', 'reference', 'variant', 'group'))
    text = d.wording.canonical(r)
    assert PROJECTION.fields['subject'] not in text and ORIGINAL['prompt'] not in text
    assert all(key not in r for key in ('model_metrics', 'comparison', 'by_group', 'reference', 'score'))
    assert 'thinking' not in r['result'] and 'input_fingerprint' not in text
    assert r['result']['telemetry']['load_duration'] == 80000000000
    assert r['result']['telemetry']['eval_count'] == 80
    assert r['result']['telemetry']['thinking_count'] is None
    assert r['result']['chat_response_seconds'] is not None
    assert r['result']['prediction'] == ABSTAIN  # Structure only; not scored correct.
    for req in r['requests']:
        assert req['elapsed_seconds'] >= 0
        assert set(req['phases']) == {'connect', 'send', 'response_headers', 'response_body', 'parse_envelope'}
        assert all(p['completed'] and p['elapsed_seconds'] >= 0 for p in req['phases'].values())


@pytest.mark.parametrize('fault,code', [('timeout', 'timeout'), ('os', 'transport_error'), ('interrupt', 'interrupted')])
def test_chat_failure_no_retry_partial_null_telemetry_and_final_identity(monkeypatch, fault, code):
    def hook(m, p, v, reply):
        if p == '/api/chat':
            if fault == 'timeout':
                raise TimeoutError('never echo private service detail')
            if fault == 'interrupt':
                raise KeyboardInterrupt()
            raise OSError('never echo private service detail')
        return reply
    http = mocked(monkeypatch, hook)
    r = d.run()
    assert r['run_status'] == 'partial' and r['attempted'] == r['selected'] == 1
    assert r['result']['status'] == r['stop_code'] == code
    assert r['result']['chat_response_seconds'] is None
    assert all(v is None for v in r['result']['telemetry'].values())
    assert r['identity_verified_at_end']
    assert sum(p == '/api/chat' for _, p, _, _ in http.calls) == 1
    chat = next(q for q in r['requests'] if q['endpoint'] == '/api/chat')
    assert not chat['phases']['send']['completed'] and chat['elapsed_seconds'] >= 0
    assert 'private service detail' not in d.wording.canonical(r)


@pytest.mark.parametrize('bad', [None, '', 'wrong', 1, {}, ['qwen'], True])
def test_reply_identity_permanently_unattributed_even_final_metadata_normal(monkeypatch, bad):
    def hook(m, p, v, reply):
        if p == '/api/chat':
            reply['model'] = bad
        return reply
    http = mocked(monkeypatch, hook)
    r = d.run()
    assert not r['identity_verified_at_end'] and r['observed_identity'] is None
    assert r['prediction_attribution'] == 'unattributed_diagnostic'
    assert r['stop_code'] == r['result']['status'] == 'identity_unverified'
    assert r['run_status'] == 'partial' and r['selected'] == r['attempted'] == 1
    assert http.calls[-1][1] == '/api/show'


@pytest.mark.parametrize('at', [1, 2, 3])
def test_metadata_identity_change_and_normal_recovery_never_restore_attribution(monkeypatch, at):
    seen = 0
    def hook(m, p, v, reply):
        nonlocal seen
        if p == '/api/tags':
            seen += 1
            if seen == at:
                reply['models'][0]['digest'] = '0' * 64
        return reply
    http = mocked(monkeypatch, hook)
    r = d.run()
    assert not r['identity_verified_at_end'] and r['observed_identity'] is None
    assert r['run_status'] == 'partial' and r['selected'] == 1
    assert r['attempted'] == (1 if at == 3 else 0)
    assert sum(p == '/api/chat' for _, p, _, _ in http.calls) == r['attempted']
    if at == 3:
        assert r['result']['prediction'] == ABSTAIN
        assert r['prediction_attribution'] == 'unattributed_diagnostic'
    else:
        assert r['result']['status'] == 'not_attempted'


@pytest.mark.parametrize('fault,code', [('done', 'protocol_error'), ('json', 'invalid_json'), ('schema', 'invalid_structure'), ('thinking', 'thinking_leakage'), ('inline', 'thinking_leakage'), ('length', 'truncated'), ('tokens', 'resource_limit'), ('context', 'protocol_error'), ('tool', 'protocol_error'), ('extra', 'protocol_error'), ('large', 'resource_limit')])
def test_output_boundary_one_attempt_no_salvage(monkeypatch, fault, code):
    def hook(m, p, v, reply):
        if p == '/api/chat':
            if fault == 'done': reply['done'] = False
            if fault == 'json': reply['message']['content'] = '```json\n{}\n```'
            if fault == 'schema': reply['message']['content'] = '{}'
            if fault == 'thinking': reply['message']['thinking'] = 'never save me'
            if fault == 'inline': reply['message']['content'] = '<think>never save me</think>'
            if fault == 'length': reply['done_reason'] = 'length'
            if fault == 'tokens': reply['eval_count'] = 513
            if fault == 'context': reply['context'] = [1, 2]
            if fault == 'tool': reply['message']['tool_calls'] = [{}]
            if fault == 'extra': reply['secret'] = 'never save me'
            if fault == 'large': reply['message']['content'] = 'x' * 8193
        return reply
    http = mocked(monkeypatch, hook)
    r = d.run()
    assert r['result']['status'] == code and r['result']['prediction'] is None
    assert r['run_status'] == 'partial' and r['identity_verified_at_end']
    assert sum(p == '/api/chat' for _, p, _, _ in http.calls) == 1
    assert 'never save me' not in d.wording.canonical(r)


def test_missing_telemetry_null_and_residency_not_cold_or_utilization(monkeypatch):
    def hook(m, p, v, reply):
        if p == '/api/chat':
            for key in d.parent.TELEMETRY:
                reply.pop(key, None)
        if p == '/api/ps':
            reply['models'] = [dict(name=CONFIG['model']['tag'], digest=CONFIG['model']['digest'], size=3300000000, size_vram=3100000000, context_length=4096)]
        return reply
    mocked(monkeypatch, hook)
    r = d.run()
    assert all(v is None for v in r['result']['telemetry'].values())
    assert r['initial_residency'] == dict(size=3300000000, size_vram=3100000000, context_length=4096)
    assert 'utilization' not in d.wording.canonical(r)


class Clock:
    now = 0
    def __call__(self):
        return self.now


@pytest.mark.parametrize('stage,seconds', [('chat_headers', 179), ('chat_headers', 181), ('chat_body', 181), ('metadata_headers', 6)])
def test_absolute_budget_not_reset_per_receive_and_measured_phase(monkeypatch, stage, seconds):
    clock = Clock()
    monkeypatch.setattr(d.time, 'monotonic', clock)
    active = ''
    fired = False
    def phase(kind, obj):
        nonlocal active, fired
        if kind == 'headers': active = obj.path
        target = ('headers' if stage.endswith('headers') else 'body')
        is_chat = active == '/api/chat'
        if not fired and kind == target and (is_chat == stage.startswith('chat')):
            clock.now += seconds
            fired = True
    mocked(monkeypatch, phase=phase)
    r = d.run()
    if seconds == 179:
        assert r['run_status'] == 'complete' and r['result']['chat_response_seconds'] == 179
        assert r['result']['telemetry']['load_duration'] == 80000000000
    else:
        assert r['run_status'] == 'partial'
        assert r['stop_code'] == 'timeout'
        if stage.startswith('chat'):
            assert r['result']['chat_response_seconds'] is None
            assert all(v is None for v in r['result']['telemetry'].values())
        else:
            assert r['attempted'] == 0


def test_total_budget_final_verification_expired_no_further_connection(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(d.time, 'monotonic', clock)
    def hook(m, p, v, reply):
        if p == '/api/chat': clock.now = 241
        return reply
    http = mocked(monkeypatch, hook)
    r = d.run()
    assert r['run_status'] == 'partial' and not r['identity_verified_at_end']
    assert http.calls[-1][1] == '/api/chat'
    assert r['result']['status'] == 'resource_limit'


def test_transport_itself_accepts_only_fixed_projection_and_one_chat(monkeypatch):
    http = mocked(monkeypatch)
    t = d.Transport(CONFIG, d.time.monotonic() + 240)
    payload = t.payload(PROJECTION)
    t.request('POST', '/api/chat', payload)
    with pytest.raises(d.Error, match='resource_limit'):
        t.request('POST', '/api/chat', payload)
    for changes in (dict(subject='other'), dict(synthetic_only=False)):
        with pytest.raises((d.Error, d.engine.EmailEvidenceError)):
            t.payload(d.engine.EmailMetadata(dict(PROJECTION.fields, **changes)))
    for modified in (dict(payload, think=True), dict(payload, model='other'), dict(payload, context=[])):
        with pytest.raises(d.Error):
            d.Transport(CONFIG, d.time.monotonic() + 240).request('POST', '/api/chat', modified)
    assert len(http.calls) == 1


@pytest.mark.parametrize('method,path,value', [('POST', '/api/generate', {}), ('POST', '/api/pull', {}), ('GET', '/other', None), ('GET', '/api/chat', None), ('POST', '/api/show', {'model': 'other'}), ('GET', '/api/ps', {})])
def test_no_other_endpoint_or_request(monkeypatch, method, path, value):
    http = mocked(monkeypatch)
    with pytest.raises(d.Error):
        d.Transport(CONFIG, d.time.monotonic() + 240).request(method, path, value)
    assert not http.calls


def test_file_access_allowlist_no_forbidden_datasets_or_scoring(monkeypatch):
    allowed = {d.CONFIG.as_posix(), 'experiments/email_model_evidence.py', d.parent.CONFIG.as_posix(), 'experiments/email_wording_challenge.py', 'src/family_os/_synthetic_email_evidence.py', 'fixtures/synthetic-email-wording-challenge-v1.json'}
    original = os.open
    opened = []
    def guard(path, *args, **kwargs):
        relative = Path(path).relative_to(d.ROOT).as_posix()
        assert relative in allowed
        opened.append(relative)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(os, 'open', guard)
    def no_score(*args):
        pytest.fail('Scorer or interpreter invocation forbidden in runtime diagnostic')
    monkeypatch.setattr(d.wording, 'summarize', no_score)
    monkeypatch.setattr(d.engine, 'interpret', no_score)
    mocked(monkeypatch)
    assert d.run()['run_status'] == 'complete'
    assert set(opened) == allowed


@pytest.mark.parametrize('fault', ['config', 'parent'])
def test_corruption_before_http(monkeypatch, fault):
    original = d.read_pin
    def altered(path, expected):
        raw = original(path, expected)
        return b'{}' if fault == 'config' and path == d.CONFIG else raw
    if fault == 'config':
        # Simulated parser/input mismatch after pin: runtime checks still reject.
        monkeypatch.setattr(d, 'read_pin', altered)
    else:
        monkeypatch.setattr(d, 'PARENT_SHA', '0' * 64)
    http = mocked(monkeypatch)
    with pytest.raises((d.Error, KeyError)):
        d.run()
    assert not http.calls


def test_real_cli_twice_mock_only_distinct_reports_and_minimized_output(monkeypatch, tmp_path, capsys):
    mocked(monkeypatch)
    original_save = d.save
    def temporary_save(report):
        with monkeypatch.context() as m:
            m.setattr(d, 'ROOT', tmp_path)
            return original_save(report)
    monkeypatch.setattr(d, 'save', temporary_save)
    assert d.main(['--synthetic-only', 'single']) == 0
    first = next((tmp_path / d.LOCAL).glob('*/report.json'))
    raw = first.read_bytes()
    assert d.main(['--synthetic-only', 'single']) == 0
    paths = list((tmp_path / d.LOCAL).glob('*/report.json'))
    assert len(paths) == 2 and first.read_bytes() == raw
    assert not list((tmp_path / d.LOCAL).rglob('*.tmp'))
    out = capsys.readouterr().out
    assert out.count('报告：') == 2 and '非准确率' in out
    assert PROJECTION.fields['subject'] not in out and '准确率：' not in out


@pytest.mark.parametrize('fault', ['write', 'flush', 'fsync', 'replace'])
def test_atomic_failure_cleans_and_preserves_old_report(monkeypatch, tmp_path, fault):
    mocked(monkeypatch)
    report = d.run()
    monkeypatch.setattr(d, 'ROOT', tmp_path)
    first = tmp_path / d.save(report)
    before = first.read_bytes()
    def fail(*args, **kwargs):
        raise OSError('not for logs')
    if fault in ('write', 'flush'):
        real_open = Path.open
        class File:
            def __init__(self, f): self.f = f
            def __enter__(self): return self
            def __exit__(self, *args): self.f.close()
            def write(self, value):
                self.f.write(value[:10])
                if fault == 'write': fail()
            def flush(self): fail()
            def fileno(self): return self.f.fileno()
        def opened(p, *args, **kwargs):
            f = real_open(p, *args, **kwargs)
            return File(f) if p.name.endswith('.tmp') else f
        monkeypatch.setattr(Path, 'open', opened)
    else:
        monkeypatch.setattr(os, 'fsync' if fault == 'fsync' else 'replace', fail)
    with pytest.raises(OSError): d.save(report)
    assert first.read_bytes() == before
    assert len(list((tmp_path / d.LOCAL).iterdir())) == 1
    assert not list((tmp_path / d.LOCAL).rglob('*.tmp'))


def test_existing_run_collision_not_overwritten(monkeypatch, tmp_path):
    mocked(monkeypatch)
    report = d.run()
    monkeypatch.setattr(d, 'ROOT', tmp_path)
    monkeypatch.setattr(d, 'uuid4', lambda: type('ID', (), {'hex': '0' * 32})())
    path = tmp_path / d.save(report)
    original = path.read_bytes()
    with pytest.raises(FileExistsError): d.save(report)
    assert path.read_bytes() == original


@pytest.mark.parametrize('args', [[], ['single'], ['--synthetic-only', 'smoke'], ['--synthetic-only', 'full'], ['--synthetic-only', 'single', '--model', 'other'], ['--synthetic-only', 'single', '--input', 'file'], ['--synthetic-only', 'single', '--host', 'example.com']])
def test_cli_has_no_implicit_or_arbitrary_mode(args):
    with pytest.raises(SystemExit): d.main(args)


def test_actual_module_cli_mocked_http_partial_never_success(monkeypatch, capsys):
    mocked(monkeypatch, lambda m, p, v, r: (_ for _ in ()).throw(TimeoutError('private')) if p == '/api/chat' else r)
    monkeypatch.setattr(sys, 'argv', ['single_email_diagnostic', '--synthetic-only', 'single'])
    published = []
    # runpy executes the actual module __main__; replace only publication OS boundary.
    def replace(source, target):
        published.append(json.loads(Path(source).read_text(encoding='utf-8')))
        Path(source).unlink()
        Path(source).parent.rmdir()
    monkeypatch.setattr(os, 'replace', replace)
    monkeypatch.delitem(sys.modules, 'experiments.single_email_diagnostic', raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module('experiments.single_email_diagnostic', run_name='__main__')
    assert exc.value.code == 2 and published[0]['run_status'] == 'partial'
    out = capsys.readouterr().out
    assert 'timeout' in out and 'private' not in out


@pytest.mark.parametrize('framing', ['length', 'chunked', 'close'])
def test_actual_stdlib_http_parser_mock_socket(monkeypatch, framing):
    body = json.dumps({'version': '0.40.6'}).encode()
    header = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n'
    if framing == 'length': wire = header + b'Content-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body
    elif framing == 'chunked': wire = header + b'Transfer-Encoding: chunked\r\n\r\n' + format(len(body), 'x').encode() + b'\r\n' + body + b'\r\n0\r\n\r\n'
    else: wire = header + b'\r\n' + body
    class Raw:
        closed = False
        def __init__(self): self.data, self.sent = io.BytesIO(wire), []
        def settimeout(self, seconds): assert 0 < seconds <= 5 and not self.closed
        def sendall(self, data): self.sent.append(data)
        def recv_into(self, buffer):
            assert not self.closed
            return self.data.readinto(buffer)
        def close(self): self.closed = True
    raw = Raw()
    monkeypatch.setattr(d.http.client.HTTPConnection, 'connect', lambda self: setattr(self, 'sock', raw))
    t = d.Transport(CONFIG, d.time.monotonic() + 240)
    assert t.request('GET', '/api/version') == {'version': '0.40.6'}
    assert raw.closed and b'Host: 127.0.0.1:11434' in b''.join(raw.sent)


@pytest.mark.parametrize('fault', ['headers', 'body', 'redirect', 'encoding', 'malformed_chat'])
def test_wire_limits_and_malformed_identity(monkeypatch, fault):
    if fault == 'headers': wire = b'HTTP/1.1 200 OK\r\nHuge: ' + b'x' * 1000000 + b'\r\n\r\n{}'
    elif fault == 'body': wire = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 65537\r\n\r\n'
    elif fault == 'redirect': wire = b'HTTP/1.1 302 Found\r\nLocation: http://external.invalid\r\n\r\n'
    elif fault == 'encoding': wire = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Encoding: gzip\r\n\r\n'
    else: wire = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\nnot JSON'
    data = io.BytesIO(wire)
    class Raw:
        def settimeout(self, seconds): assert 0 < seconds <= 180
        def sendall(self, data): pass
        def recv_into(self, buffer): return data.readinto(buffer)
        def close(self): pass
    monkeypatch.setattr(d.http.client.HTTPConnection, 'connect', lambda self: setattr(self, 'sock', Raw()))
    t = d.Transport(CONFIG, d.time.monotonic() + 240)
    with pytest.raises(d.Error) as exc:
        t.request('POST', '/api/chat', t.payload(PROJECTION))
    assert exc.value.code == ('identity_unverified' if fault == 'malformed_chat' else 'resource_limit' if fault in ('headers', 'body') else 'protocol_error')
    if fault == 'headers': assert data.tell() <= 8192 * 2


def test_slow_header_trickle_uses_absolute_deadline(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(d.time, 'monotonic', clock)
    data = io.BytesIO(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}')
    class Raw:
        def settimeout(self, seconds): assert 0 < seconds <= 5
        def sendall(self, data): pass
        def recv_into(self, buffer):
            clock.now += 2
            value = data.read(1)
            buffer[:len(value)] = value
            return len(value)
        def close(self): pass
    monkeypatch.setattr(d.http.client.HTTPConnection, 'connect', lambda self: setattr(self, 'sock', Raw()))
    t = d.Transport(CONFIG, 240)
    with pytest.raises(d.Error, match='timeout'): t.request('GET', '/api/version')
    assert clock.now == 6 and t.requests[0]['elapsed_seconds'] == 6


def test_proxy_environment_has_no_effect(monkeypatch):
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
        monkeypatch.setenv(key, 'http://external.invalid:9999')
    http = mocked(monkeypatch)
    assert d.run()['run_status'] == 'complete'
    assert len(http.calls) == 11


def test_publication_failure_cli_no_success_or_private_error(monkeypatch, capsys):
    mocked(monkeypatch)
    monkeypatch.setattr(d, 'save', lambda _: (_ for _ in ()).throw(OSError('private path')))
    assert d.main(['--synthetic-only', 'single']) == 1
    out = capsys.readouterr().out
    assert '报告：' not in out and 'private path' not in out and 'diagnostic_failed' in out


@pytest.mark.parametrize('seconds', [0, -1])
def test_expired_total_deadline_never_opens_socket(monkeypatch, seconds):
    http = mocked(monkeypatch)
    t = d.Transport(CONFIG, d.time.monotonic() + seconds)
    with pytest.raises(d.Error, match='resource_limit'): t.request('POST', '/api/chat', t.payload(PROJECTION))
    assert not http.calls and t.chat_attempts == 0


def test_pin_reader_cannot_read_arbitrary_file():
    with pytest.raises(d.Error, match='input_rejected'):
        d.read_pin(Path('fixtures/holdout.json'), '0' * 64)
