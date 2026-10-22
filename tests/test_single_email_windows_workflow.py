"""Workflow/readback tests, never model inference; native PowerShell mocks on Windows."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

from experiments import collect_single_email_diagnostic as w
from experiments import single_email_diagnostic as d
from test_single_email_diagnostic import mocked


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs): pytest.fail('Real network/Ollama forbidden')
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(socket.socket, 'connect', deny)


def local_publisher(monkeypatch, tmp_path):
    original = d.save
    def save(report):
        with monkeypatch.context() as m:
            m.setattr(d, 'ROOT', tmp_path)
            return original(report)
    def read(runtime, relative):
        with monkeypatch.context() as m:
            m.setattr(d, 'ROOT', tmp_path)
            return original_read(runtime, relative)
    original_read = w.read_published
    monkeypatch.setattr(d, 'save', save)
    monkeypatch.setattr(w, 'read_published', read)


@pytest.mark.parametrize('partial', [False, True])
def test_real_mock_cli_returns_full_published_report_once(monkeypatch, tmp_path, capsys, partial):
    def response(m, p, payload, value):
        if partial and p == '/api/chat': value['message']['content'] = '{}'
        return value
    http = mocked(monkeypatch, response)
    local_publisher(monkeypatch, tmp_path)
    monkeypatch.setattr(w, 'version', lambda: (3, 12, 10))
    code = w.main(['--synthetic-only', 'single'])
    result = json.loads(capsys.readouterr().out)
    assert code == result['workflow_exit_code'] == result['diagnostic_exit_code'] == (2 if partial else 0)
    assert result['report_read_verified'] and result['report_source'] == 'published_readback'
    assert result['report'] == json.loads((tmp_path / result['report_path']).read_text(encoding='utf-8'))
    report = result['report']
    assert report['run_status'] == ('partial' if partial else 'complete')
    assert report['result']['telemetry']['load_duration'] == 80000000000
    assert report['result']['telemetry']['prompt_eval_count'] == 500
    assert report['result']['telemetry']['eval_count'] == 80
    assert report['requests'][0]['phases']['connect']['completed']
    assert report['total_elapsed_seconds'] >= 0 and report['identity_verified_at_end']
    assert sum(p == '/api/chat' for _, p, _, _ in http.calls) == 1
    assert 'subject' not in result and d.setup()[2].fields['subject'] not in json.dumps(result)


@pytest.mark.parametrize('version', [(3, 12, 0), (3, 13, 1), (3, 12, 9)])
def test_wrong_python_no_generation_or_runtime_execution(monkeypatch, capsys, version):
    def denied(): pytest.fail('Must not start diagnostic on wrong Python')
    monkeypatch.setattr(w, 'collect', denied)
    monkeypatch.setattr(w, 'version', lambda: version)
    http = mocked(monkeypatch)
    assert w.main(['--synthetic-only', 'single']) == 1
    assert json.loads(capsys.readouterr().out)['error_code'] == 'python_version_mismatch'
    assert not http.calls


@pytest.mark.parametrize('failure', ['missing', 'read_error', 'changed', 'symlink', 'invalid_json'])
def test_report_failure_retains_original_information_no_second_chat(monkeypatch, tmp_path, capsys, failure):
    http = mocked(monkeypatch)
    original_save = d.save
    def save(report):
        with monkeypatch.context() as m:
            m.setattr(d, 'ROOT', tmp_path)
            relative = original_save(report)
        path = tmp_path / relative
        if failure == 'missing': path.unlink()
        elif failure == 'changed': path.write_text('{"private":"not printable"}', encoding='utf-8')
        elif failure == 'invalid_json': path.write_text('private raw text', encoding='utf-8')
        elif failure == 'symlink':
            # Windows symlink privileges are unnecessary: inject only the
            # regular-file guard result, not filesystem permission assumptions.
            monkeypatch.setattr(d.wording, 'regular', lambda *a, **k: (_ for _ in ()).throw(ValueError('private')))
        return relative
    original_read = w.read_published
    def read(runtime, relative):
        if failure == 'read_error': raise OSError('private driver text')
        with monkeypatch.context() as m:
            m.setattr(d, 'ROOT', tmp_path)
            return original_read(runtime, relative)
    monkeypatch.setattr(d, 'save', save)
    monkeypatch.setattr(w, 'read_published', read)
    monkeypatch.setattr(w, 'version', lambda: (3, 12, 10))
    assert w.main(['--synthetic-only', 'single']) == 1
    text = capsys.readouterr().out
    value = json.loads(text)
    assert value['error_code'] == 'report_read_failed' and not value['report_read_verified']
    assert value['report_source'] == 'retained_in_memory' and value['diagnostic_exit_code'] == 0
    assert value['report']['result']['telemetry']['load_duration'] == 80000000000
    assert value['report']['requests'][0]['phases'] and value['report_path']
    assert 'not printable' not in text and 'private driver' not in text and 'private raw' not in text
    assert sum(p == '/api/chat' for _, p, _, _ in http.calls) == 1


@pytest.mark.parametrize('relative', ['../report.json', '/tmp/report.json', '.local/email-model-evidence/' + 'a'*32 + '/report.json', '.local/single-email-runtime-diagnostic/not-uuid/report.json'])
def test_no_arbitrary_report_reader(relative):
    with pytest.raises(ValueError): w.read_published(d, relative)


def test_publication_failure_retains_minimized_result_no_retry(monkeypatch, capsys):
    http = mocked(monkeypatch)
    monkeypatch.setattr(w, 'version', lambda: (3, 12, 10))
    monkeypatch.setattr(d, 'save', lambda _: (_ for _ in ()).throw(OSError('private path')))
    assert w.main(['--synthetic-only', 'single']) == 1
    text = capsys.readouterr().out
    result = json.loads(text)
    assert result['error_code'] == 'diagnostic_or_publication_failed'
    assert result['report']['requests'] and result['report']['result']['telemetry']['load_duration']
    assert result['report_path'] is None and 'private path' not in text
    assert sum(p == '/api/chat' for _, p, _, _ in http.calls) == 1


@pytest.mark.parametrize('shell_name', ['pwsh', 'powershell'])
@pytest.mark.parametrize('scenario', ['success', 'partial', 'report_error', 'clipboard_error', 'version_bad', 'fallback', 'checkout_bad', 'empty_output'])
@pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows PowerShell workflow behavior')
def test_native_powershell_behavior_mocked_no_inference(scenario, shell_name):
    shell = shutil.which(shell_name)
    assert shell, 'Windows CI must execute the behavioral harness, not skip it'
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run([shell, '-NoProfile', '-File', str(root/'tests/support/single_email_windows_mock.ps1'), '-Scenario', scenario], text=True, encoding='utf-8', capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    value = json.loads(completed.stdout.strip().splitlines()[-1])
    assert value['restored'] and value['clipboard_attempts'] == 1
    assert value['calls'] == (0 if scenario in ('version_bad', 'checkout_bad') else 1)
    if scenario == 'checkout_bad': assert value['version_probes'] == 0
    if scenario == 'version_bad': assert value['version_probes'] == 2
    assert value['failed'] == (scenario not in ('success', 'fallback'))
    if value['calls'] and scenario != 'empty_output':
        assert '80000000000' in value['printed'] and 'phases' in value['printed']
        if scenario != 'clipboard_error':
            assert '80000000000' in value['copied'] and 'phases' in value['copied']
    if scenario == 'fallback': assert value['selected'] == 'fallback-python'
    if scenario == 'success': assert value['selected'] == 'verified-python'


@pytest.mark.parametrize('shell_name', ['pwsh', 'powershell'])
@pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows approved-checkout gate')
def test_native_real_git_gate_rejects_wrong_commit_tree_and_dirty_worktree(tmp_path, shell_name):
    shell = shutil.which(shell_name)
    assert shell
    root = Path(__file__).resolve().parents[1]
    script = root/'experiments/single_email_windows.ps1'
    harness = '''param($Script,$Root)
. $Script
$ErrorActionPreference = 'Stop'
git -C $Root init --quiet
git -C $Root config user.email synthetic@example.invalid
git -C $Root config user.name Synthetic
Set-Content -LiteralPath (Join-Path $Root 'file.txt') -Value 'synthetic' -Encoding utf8
git -C $Root add file.txt
git -C $Root commit --quiet -m synthetic
$h = git -C $Root rev-parse HEAD
$t = git -C $Root rev-parse 'HEAD^{tree}'
Assert-DiagnosticCheckout $Root $h $t
$rejected = 0
foreach ($pair in @(@(('0'*40),$t), @($h,('0'*40)))) {
    try { Assert-DiagnosticCheckout $Root $pair[0] $pair[1] } catch { $rejected++ }
}
Add-Content -LiteralPath (Join-Path $Root 'file.txt') -Value 'changed'
try { Assert-DiagnosticCheckout $Root $h $t } catch { $rejected++ }
if ($rejected -ne 3) { throw 'gate_failed' }
Write-Output 'gate_passed'
'''
    # Test-only, no diagnostic or model call; script text through file avoids -c quoting.
    gate = tmp_path/'gate.ps1'
    repo = tmp_path/'repo'
    repo.mkdir()
    gate.write_text(harness, encoding='utf-8')
    result = subprocess.run([shell, '-NoProfile', '-File', str(gate), '-Script', str(script), '-Root', str(repo)], text=True, encoding='utf-8', capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'gate_passed' in result.stdout


@pytest.mark.parametrize('shell_name', ['pwsh', 'powershell'])
@pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows Python discovery and exact version probe')
def test_native_discovery_prefers_existing_verified_path_and_checks_real_version(tmp_path, shell_name):
    shell = shutil.which(shell_name)
    assert shell
    root = Path(__file__).resolve().parents[1]
    script = root/'experiments/single_email_windows.ps1'
    harness = tmp_path/'probe.ps1'
    harness.write_text(r'''param($Script,$Python,$Temporary)
. $Script
$ErrorActionPreference = 'Stop'
# Probe only the standard library version, never a repository/model module.
$valid = Test-DiagnosticPythonVersion -Python $Python
$oldTemp=$env:TEMP; $oldLocal=$env:LOCALAPPDATA
try {
    $env:TEMP=$Temporary; $env:LOCALAPPDATA=$Temporary
    $expected=Join-Path $env:TEMP 'samas-i9-56051b5dbf8443cfba3b2d55bbee16a9.venv\Scripts\python.exe'
    $null=New-Item -ItemType Directory -Force -Path (Split-Path $expected)
    $null=New-Item -ItemType File -Path $expected
    function Get-Command { param($Name,[switch]$All,$ErrorAction) return $null }
    $candidates=@(Get-DiagnosticPythonCandidates)
    if ($candidates.Count -lt 1 -or $candidates[0] -ne $expected) { throw 'wrong_priority' }
} finally { $env:TEMP=$oldTemp; $env:LOCALAPPDATA=$oldLocal }
@{ valid=$valid; preferred=$true } | ConvertTo-Json -Compress
''', encoding='utf-8')
    result = subprocess.run([shell, '-NoProfile', '-File', str(harness), '-Script', str(script), '-Python', sys.executable, '-Temporary', str(tmp_path)], text=True, encoding='utf-8', capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    value = json.loads(result.stdout.strip().splitlines()[-1])
    assert value['preferred'] and value['valid'] == (sys.version_info[:3] == (3, 12, 10))
