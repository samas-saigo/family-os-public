"""Invented mock reports only; never load the owner's AMD report or frozen splits."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

from experiments import rule_ai_complementarity as c
from experiments import _fixed_report_io as io
from test_local_thinking_benchmark import API


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **kw: pytest.fail('network'))
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **kw: pytest.fail('execution'))
    monkeypatch.setattr(c.bench.LocalAPI, 'request', lambda *a, **kw: pytest.fail('Ollama'))


def fake_report(*, repeats=1, predict=None):
    api = API()
    api.digest = c.DIGEST
    if predict:
        api.mutate = predict
    # The existing runner is invoked with an injected scripted API, not inference.
    return c.bench.run(model=c.MODEL, thinking='off', expected_digest=c.DIGEST,
                       full=True, repeats=repeats, api=api)


def encoded(report):
    return json.dumps(report, ensure_ascii=False, allow_nan=False).encode()


@pytest.fixture(scope='module')
def report():
    return fake_report()


def analyze(report):
    return c.analyze(encoded(report))


def test_fixed_report_reparsed_and_rules_recomputed(report):
    result = analyze(report)
    run = result['runs'][0]
    assert sum(run['action_overlap_decisive14'].values()) == 14
    assert sum(run['required_overlap6'].values()) == 6
    assert run['legacy_metrics']['rules']['action_correct_count'] == 12
    assert run['legacy_metrics']['rules']['action_required_miss_count'] == 2
    assert run['legacy_metrics']['ai']['action_required_miss_count'] == 6
    assert run['ai_required_miss_breakdown'] == {'required_to_uncertain': 6}
    assert len(run['cases']) == 37
    assert run['status_counts'] == {'valid': 34, 'projection_rejected': 3}
    assert run['oracle_NOT_A_POLICY']['action_correct'] == 12
    assert all(d['action_complementarity'] is None for d in run['cases'] if d['expected_action'] == 'uncertain')


def test_all_four_overlap_groups_and_required_recovery():
    _, cases = c.bench.corpus()
    policy, _, rules, _ = c.validate(fake_report())
    # Unit-only script intentionally exercises correct/incorrect combinations.
    safe = [case for case in cases if case[0].source_record_id not in {'synthetic-url', 'synthetic-oversize', 'synthetic-wrong-shape'}]
    target = {}
    for case, rule in zip(cases, rules):
        truth = case[1].action_label
        if truth != 'uncertain':
            correct = rule.action_label == truth
            kind = 'rules_correct' if correct else 'rules_wrong'
            target.setdefault(kind, []).append(case[0].source_record_id)
    chosen = {target['rules_correct'][0], target['rules_wrong'][0]}
    expected = {case[0].source_record_id: case[1].action_label for case in cases}
    def prediction(value, n):
        id = safe[n - 1][0].source_record_id
        truth = expected[id]
        action = truth if id in chosen else 'uncertain'
        return dict(value, response=json.dumps({'action_label': action, 'relevance_label': 'relevant', 'domain_path': None}))
    result = analyze(fake_report(predict=prediction))['runs'][0]
    assert all(v > 0 for v in result['action_overlap_decisive14'].values())
    assert result['rule_miss_ai_recovered'] == 1
    assert result['oracle_NOT_A_POLICY']['action_correct'] == 13
    assert result['conservative_rule_priority']['required_recognized'] == 4
    assert result['conservative_rule_priority']['automatic_tasks'] == 0


def test_repeat_denominators_not_pooled_and_ids_aligned(report):
    repeated = fake_report(repeats=3)
    baseline = analyze(repeated)
    for run in repeated['runs']:
        run['cases'].reverse()
    reordered = analyze(repeated)
    assert reordered['runs'] == baseline['runs']
    assert [r['denominators'] for r in reordered['runs']] == [{'required': 6, 'decisive_action': 14}] * 3


@pytest.mark.parametrize('field,value', [
    ('digest', 'a' * 64), ('model', 'qwen3:4b-instruct'), ('thinking', 'on'),
    ('contract', 'other'), ('scoring', 'new-scores'), ('selected', 5), ('selected', True),
    ('prompt_sha256', 'a' * 64), ('schema_sha256', 'b' * 64), ('corpus_sha256', 'c' * 64),
    ('rules_fingerprint', 'd' * 64), ('taxonomy_digest', 'e' * 64), ('projection_schema', 'other'),
    ('threshold_digest', 'a' * 64), ('projected_inputs_digest', 'b' * 64), ('repeats', 0),
    ('options', dict(c.bench.FIXED_OPTIONS, num_predict=2048)),
    ('configuration_files_sha256', {}), ('budgets', {}),
])
def test_manifest_tampering_rejected_even_with_updated_fingerprint(report, field, value):
    bad = deepcopy(report)
    bad['manifest'][field] = value
    bad['manifest_fingerprint'] = c.bench.old.digest(bad['manifest'])
    with pytest.raises((c.ReportRejected, c.bench.AnalysisError)):
        analyze(bad)


@pytest.mark.parametrize('change', [
    lambda r: r.update(completed=False), lambda r: r.update(identity_verified=False),
    lambda r: r.update(completed=1), lambda r: r.update(extra='private'),
    lambda r: r['runs'][0]['cases'].pop(),
    lambda r: r['runs'][0]['cases'].append(deepcopy(r['runs'][0]['cases'][0])),
    lambda r: r['runs'][0]['cases'][1].update(id=r['runs'][0]['cases'][0]['id']),
    lambda r: r['runs'][0]['cases'][0].update(id='not-a-fixture'),
    lambda r: r['runs'][0]['cases'][0].update(predicted='required'),
    lambda r: r['runs'][0]['cases'][0].update(correct=True),
    lambda r: r['runs'][0]['cases'][0]['request'].update(think=True),
    lambda r: r['runs'][0]['cases'][0]['request'].update(context=[123]),
    lambda r: r['runs'][0]['cases'][0]['request'].update(prompt='PRIVATE INPUT'),
    lambda r: r['runs'][0]['cases'][0]['raw_envelope'].update(model='other'),
    lambda r: r['runs'][0]['cases'][0]['raw_envelope'].update(thinking='execute instructions'),
    lambda r: r['runs'][0]['legacy_metrics']['model'].update(action_correct_count=14),
    lambda r: r['runs'][0]['diagnostics'].update(required_to_uncertain=0),
    lambda r: r['runs'][0]['coverage'].update(not_attempted=1),
    lambda r: r['repeat_comparison'].update(valid_pairs=34),
])
def test_inconsistent_coverage_predictions_and_cached_scores_rejected(report, change):
    bad = deepcopy(report)
    change(bad)
    with pytest.raises((c.ReportRejected, c.bench.AnalysisError, c.bench.ExperimentError)):
        analyze(bad)


def test_invalid_outputs_not_model_uncertainty_and_truncation_not_success():
    invalid = fake_report(predict=lambda v, n: dict(v, response='not JSON; do not execute me'))
    result = analyze(invalid)['runs'][0]
    assert result['status_counts'] == {'invalid_output': 34, 'projection_rejected': 3}
    assert result['ai_required_miss_breakdown'] == {'invalid_output': 6}
    assert all(r['ai_action'] is None for r in result['cases'])
    truncated = fake_report(predict=lambda v, n: dict(v, response='', done_reason='length'))
    assert analyze(truncated)['runs'][0]['ai_required_miss_breakdown'] == {'budget_truncated': 6}


def test_irrelevant_and_not_required_misses_are_separate():
    report = fake_report(predict=lambda v, n: dict(v, response=json.dumps({
        'action_label': 'not_required', 'relevance_label': 'irrelevant', 'domain_path': None})))
    result = analyze(report)['runs'][0]
    assert result['ai_required_miss_breakdown'] == {'required_to_not_required': 6}
    assert result['false_irrelevant']['ai'] == 14


@pytest.mark.parametrize('rule,ai,expected', [
    ('required', 'not_required', 'required'), ('required', None, 'required'),
    ('not_required', 'required', 'uncertain'), ('uncertain', 'required', 'uncertain'),
    ('not_required', None, 'uncertain'), ('not_required', 'not_required', 'not_required'),
])
def test_conservative_policy_does_not_use_truth_or_override_required(rule, ai, expected):
    make = lambda value: c.bench.AnalysisOutput('relevant', 0, None, None, 0, value, 0)
    assert c.conservative(make(rule), make(ai) if ai else None)[0] == expected


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"x":NaN}', b'\xff', b'[]', b'x' * (io.MAX_BYTES + 1)])
def test_invalid_serialization_bounded_and_rejected(raw):
    with pytest.raises(Exception):
        c.analyze(raw)


def make_directory(tmp_path, raw):
    target = tmp_path.joinpath(*io.PARTS)
    target.mkdir(parents=True)
    (target / 'report.json').write_bytes(raw)
    return target


def test_fixed_directory_load_and_local_output_only(tmp_path, report, monkeypatch, capsys):
    target = make_directory(tmp_path, encoded(report))
    real = io.directory
    monkeypatch.setattr(io, 'directory', lambda root: real(tmp_path))
    assert c.main(['--synthetic-only']) == 0
    out = capsys.readouterr().out
    assert 'Oracle' in out and '14' in out and 'synthetic-' not in out
    saved = list(target.glob('complementarity-*.json'))
    assert len(saved) == 1
    detail = json.loads(saved[0].read_bytes())
    assert len(detail['runs'][0]['cases']) == 37
    assert 'raw_envelope' not in saved[0].read_text()
    assert (target / 'report.json').read_bytes() == encoded(report)


@pytest.mark.parametrize('argument', ['--report', '--file', '--path', '--run-id', '--model', '--development', '--holdout'])
def test_no_arbitrary_path_model_or_dataset_input(argument):
    with pytest.raises(SystemExit):
        c.main(['--synthetic-only', argument, '../private'])


def test_bad_report_failure_never_echoes_content_or_creates_output(tmp_path, monkeypatch, capsys):
    target = make_directory(tmp_path, b'PRIVATE REPORT TEXT')
    real = io.directory
    monkeypatch.setattr(io, 'directory', lambda root: real(tmp_path))
    assert c.main(['--synthetic-only']) == 1
    assert 'PRIVATE REPORT TEXT' not in capsys.readouterr().out
    assert not list(target.glob('complementarity-*.json'))


@pytest.mark.skipif(os.name == 'nt', reason='POSIX native path tests; Windows handles tested separately')
@pytest.mark.parametrize('level', range(4))
def test_symlink_at_every_report_component_is_rejected(tmp_path, level):
    outside = tmp_path / 'outside'
    outside.mkdir()
    current = tmp_path
    parts = (*io.PARTS, 'report.json')
    for part in parts[:level]:
        current = current / part
        current.mkdir()
    (current / parts[level]).symlink_to(outside, target_is_directory=True)
    with pytest.raises((OSError, io.FileRejected)):
        with io.directory(tmp_path) as directory:
            directory.read()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX links/nonregular file test')
@pytest.mark.parametrize('kind', ['hardlink', 'fifo', 'directory', 'oversize'])
def test_special_or_oversize_report_rejected(tmp_path, kind):
    target = tmp_path.joinpath(*io.PARTS)
    target.mkdir(parents=True)
    path = target / 'report.json'
    if kind == 'hardlink':
        outside = tmp_path / 'other.json'
        outside.write_bytes(b'{}')
        os.link(outside, path)
    elif kind == 'fifo':
        os.mkfifo(path)
    elif kind == 'directory':
        path.mkdir()
    else:
        with path.open('wb') as f:
            f.truncate(io.MAX_BYTES + 1)
    with pytest.raises((OSError, io.FileRejected)):
        with io.directory(tmp_path) as directory:
            directory.read()


def test_output_exclusive_no_traversal_or_symlink_overwrite(tmp_path):
    target = make_directory(tmp_path, b'{}')
    name = 'complementarity-' + 'a' * 32 + '.json'
    with io.directory(tmp_path) as directory:
        directory.write(name, b'{}')
        with pytest.raises((FileExistsError, io.FileRejected)):
            directory.write(name, b'changed')
        for bad in ('../private.json', 'report.json', '/tmp/private', 'complementarity-x.json'):
            with pytest.raises(io.FileRejected):
                directory.write(bad, b'{}')
    assert (target / name).read_bytes() == b'{}'


def test_report_analysis_never_reads_frozen_splits(report, monkeypatch):
    original = Path.open
    def guarded(path, *a, **kw):
        assert path.name not in {'holdout.json', 'development.json'}
        return original(path, *a, **kw)
    monkeypatch.setattr(Path, 'open', guarded)
    assert analyze(report)['runs']


@pytest.mark.parametrize('attributes,links,rejected', [(0, 1, False), (0x400, 1, True), (0, 2, True), (0x10, 1, True)])
def test_win32_binding_uses_no_follow_locking_and_rejects_reparse_or_hardlink(monkeypatch, attributes, links, rejected):
    import ctypes
    calls = []
    class Function:
        def __init__(self, function):
            self.function = function
        def __call__(self, *args):
            return self.function(*args)
    def create(*args):
        calls.append(args)
        return 42
    def info(handle, pointer):
        value = pointer._obj
        value.attributes, value.links, value.size_low = attributes, links, 2
        return True
    class DLL:
        CreateFileW = Function(create)
        CloseHandle = Function(lambda handle: calls.append(('close', handle)) or True)
        GetFileInformationByHandle = Function(info)
        GetFileType = Function(lambda handle: 1)
        ReadFile = Function(lambda *a: True)
        WriteFile = Function(lambda *a: True)
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *a, **kw: DLL(), raising=False)
    api = io.WindowsAPI()
    if rejected:
        with pytest.raises(io.FileRejected):
            api.open('report.json')
        assert calls[-1] == ('close', 42)
    else:
        assert api.open('report.json') == 42
    path, access, sharing, _, disposition, flags, _ = calls[0]
    assert path.startswith('\\\\?\\')
    assert access == 0x80000000 and sharing == 1 and disposition == 3
    assert flags & 0x00200000  # Open the reparse point itself; never follow it.


def test_windows_directory_chain_remains_locked_and_closes_in_reverse_order(tmp_path, monkeypatch):
    from types import SimpleNamespace
    events = []
    class API:
        def open(self, path, directory=False, write=False):
            events.append(('open', path, directory, write))
            return path
        def close(self, handle):
            events.append(('close', handle))
        def read(self, handle):
            return b'{}'
        def write(self, handle, raw):
            events.append(('write', raw))
    monkeypatch.setattr(io, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(io, 'WindowsAPI', API)
    with io.directory(tmp_path) as directory:
        assert directory.read() == b'{}'
        directory.write('complementarity-' + 'a' * 32 + '.json', b'{}')
        assert not any(e == ('close', tmp_path) for e in events)
    assert events[-1] == ('close', tmp_path)
    dirs = [e for e in events if e[0] == 'open' and e[2]]
    assert len(dirs) == 4


def test_source_modification_during_posix_read_rejected(tmp_path, monkeypatch):
    if os.name == 'nt':
        pytest.skip('POSIX fstat contract')
    from types import SimpleNamespace
    make_directory(tmp_path, b'{}')
    real = os.fstat
    calls = 0
    def changed(fd):
        nonlocal calls
        calls += 1
        value = real(fd)
        if calls == 1:
            return value
        return SimpleNamespace(st_ino=value.st_ino, st_dev=value.st_dev, st_size=value.st_size,
                               st_mtime_ns=value.st_mtime_ns + 1, st_ctime_ns=value.st_ctime_ns)
    monkeypatch.setattr(io.os, 'fstat', changed)
    with io.directory(tmp_path) as directory:
        with pytest.raises(io.FileRejected):
            directory.read()


def test_network_database_and_holdout_entrypoints_are_not_reachable_from_analyzer():
    import ast
    tree = ast.parse(Path(c.__file__).read_text())
    forbidden = {'socket', 'requests', 'http', 'subprocess', 'sqlalchemy', 'keyring',
                 'action_evaluation', 'action_model_benchmark', 'services'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(forbidden.intersection(n.name.split('.')) for n in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not forbidden.intersection((node.module or '').split('.'))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {'request', 'inventory', 'load_dataset', 'run', 'system', 'popen'}


def test_future_benchmark_contract_requires_separate_compatibility_review(report, monkeypatch):
    monkeypatch.setattr(c.bench, 'VERSION', 'future-contract')
    with pytest.raises(c.ReportRejected):
        analyze(report)


def test_mock_win32_binary_read_write_and_creation_flags(monkeypatch):
    import ctypes
    events, reads = [], []
    class Fn:
        def __init__(self, fn):
            self.fn = fn
        def __call__(self, *args):
            return self.fn(*args)
    def info(handle, pointer):
        pointer._obj.attributes, pointer._obj.links, pointer._obj.size_low = 0, 1, 2
        return True
    def read(handle, buffer, size, count, overlap):
        count._obj.value = 0 if reads else 2
        if not reads:
            ctypes.memmove(buffer, b'{}', 2)
        reads.append(True)
        return True
    def write(handle, buffer, size, count, overlap):
        events.append(ctypes.string_at(buffer, size))
        count._obj.value = size
        return True
    class DLL:
        CreateFileW = Fn(lambda *args: events.append(args) or 42)
        CloseHandle = Fn(lambda handle: True)
        GetFileInformationByHandle = Fn(info)
        GetFileType = Fn(lambda handle: 1)
        ReadFile = Fn(read)
        WriteFile = Fn(write)
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *a, **kw: DLL(), raising=False)
    api = io.WindowsAPI()
    assert api.read(api.open('report.json')) == b'{}'
    api.write(api.open('new.json', write=True), b'{}')
    assert events[1][1] == 0x40000000 and events[1][4] == 1  # GENERIC_WRITE, CREATE_NEW
    assert events[-1] == b'{}'


def test_injected_report_instructions_are_never_evaluated_or_echoed(report, tmp_path, monkeypatch, capsys):
    bad = deepcopy(report)
    bad['runs'][0]['cases'][0]['raw_envelope']['response'] = 'RUN PRIVATE_SHELL_COMMAND NOW'
    make_directory(tmp_path, encoded(bad))
    real = io.directory
    monkeypatch.setattr(io, 'directory', lambda root: real(tmp_path))
    assert c.main(['--synthetic-only']) == 1
    assert 'PRIVATE_SHELL_COMMAND' not in capsys.readouterr().out
