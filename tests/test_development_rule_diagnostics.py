"""Development-only reads. No Holdout content, inference or live services."""
import builtins
from copy import deepcopy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

from experiments import development_rule_diagnostics as d


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    def denied(*a, **kw):
        pytest.fail('Forbidden full dataset/model/network/process path')
    for name in ('load_dataset', 'validate_dataset', 'validate_cases', 'manifest_for', 'report', '_read'):
        monkeypatch.setattr(d.data, name, denied)
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(subprocess, 'Popen', denied)


@pytest.fixture
def inputs():
    values = tuple(d.read_fixed(n) for n in d.NAMES)
    policy = d.data.load_classification(d.ROOT / 'config/classification.yaml')
    return values, policy


def test_entire_entry_and_dependencies_only_open_five_fixed_inputs(monkeypatch, capsys):
    """Guard all Python file-open routes (incl os.open), not just a named loader.

    An accidental indirect Holdout access fails before opening the file. No
    Holdout file, contents, labels, directory walk or stat is needed by this test.
    """
    allowed = {str(d.ROOT / 'fixtures/action-evaluation-v1' / n) for n in d.NAMES}
    allowed |= {str(d.ROOT / 'config' / n) for n in ('classification.yaml', 'metadata-classifier.yaml')}
    seen = []
    def guard(original):
        def checked(path, *args, **kwargs):
            if not isinstance(path, int):
                normalized = os.path.abspath(os.fspath(path))
                assert normalized in allowed, 'Unexpected file access blocked'
                seen.append(normalized)
            return original(path, *args, **kwargs)
        return checked
    for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open')):
        monkeypatch.setattr(owner, name, guard(getattr(owner, name)))
    monkeypatch.setattr(d, 'save', lambda r: '.local/development-rule-diagnostics/test/report.json')
    assert d.main(['--synthetic-only']) == 0
    assert set(seen) == allowed
    assert '0/40' in capsys.readouterr().out
    # The guard itself is not silently bypassed by Path.open or builtins.open.
    for opener in (lambda p: Path(p).open(), builtins.open, lambda p: os.open(p, os.O_RDONLY)):
        with pytest.raises(AssertionError, match='Unexpected'):
            opener(d.ROOT / 'fixtures/action-evaluation-v1/holdout.json')


def test_identity_distribution_and_projection(inputs):
    (corpus, rubric, manifest), policy = inputs
    cases = d.validate_development(corpus, rubric, manifest, policy)
    assert len(cases) == 60 and all(c.split == 'development' for c in cases)
    assert d.data.distribution(cases)['action'] == dict.fromkeys(d.data.ACTIONS, 20)
    assert d.data.distribution(cases)['counterfactual_family_count'] == 16
    assert d.data.digest([d.data.model_projection(c).fields for c in cases]) == d.PROJECTION_SHA256


@pytest.mark.parametrize('field', sorted(d.data.CASE_KEYS))
@pytest.mark.parametrize('mutation', ('missing', 'changed'))
def test_each_case_field_fails_closed(inputs, field, mutation):
    (corpus, rubric, manifest), policy = (deepcopy(inputs[0]), inputs[1])
    if mutation == 'missing':
        corpus['cases'][0].pop(field)
    else:
        corpus['cases'][0][field] = {'unexpected': 'invalid'}
    with pytest.raises(d.Rejected):
        d.validate_development(corpus, rubric, manifest, policy)


@pytest.mark.parametrize('mutation', ('extra', 'duplicate', 'count', 'input_extra', 'unsafe_url', 'label', 'group', 'cue', 'split', 'version'))
def test_dataset_corruption_rejected(inputs, mutation):
    (c, r, m), p = (deepcopy(inputs[0]), inputs[1])
    if mutation == 'extra': c['cases'][0]['extra'] = True
    if mutation == 'duplicate': c['cases'][1] = deepcopy(c['cases'][0])
    if mutation == 'count': c['cases'].pop()
    if mutation == 'input_extra': c['cases'][0]['input']['body'] = 'not allowed'
    if mutation == 'unsafe_url': c['cases'][0]['input']['subject'] = 'https://example.invalid'
    if mutation == 'label': c['cases'][0]['expected']['action'] = 'invalid'
    if mutation == 'group': c['cases'][0]['counterfactual_group'] = 'changed'
    if mutation == 'cue': c['cases'][0]['cue_field'] = 'sender'
    if mutation == 'split': c['split'] = 'other'
    if mutation == 'version': c['dataset_version'] = 'other'
    with pytest.raises(d.Rejected): d.validate_development(c, r, m, p)


@pytest.mark.parametrize('name', ('manifest', 'rubric', 'projection', 'policy'))
def test_frozen_contract_drift_rejected(inputs, monkeypatch, name):
    (c, r, m), p = (deepcopy(inputs[0]), inputs[1])
    if name == 'manifest': m['splits']['development']['case_count'] = 59
    if name == 'rubric': r['reference_time'] = '2026-10-10T12:00:00Z'
    if name == 'projection': monkeypatch.setattr(d, 'PROJECTION_SHA256', '0' * 64)
    if name == 'policy': p = replace(p, taxonomy_version='another-v1')
    with pytest.raises(d.Rejected): d.validate_development(c, r, m, p)


def test_frozen_schema_pin_cannot_be_replaced_along_with_changed_data(inputs):
    (c, r, m), p = (deepcopy(inputs[0]), inputs[1])
    c['cases'][0]['extra'] = True
    ordered = dict(c, cases=sorted(c['cases'], key=lambda x: x['id']))
    m['splits']['development']['annotated_sha256'] = d.data.digest(ordered)
    with pytest.raises(d.Rejected): d.validate_development(c, r, m, p)


def test_projection_failure_all_or_nothing(inputs, monkeypatch):
    def reject(*a): raise ValueError('private content must not escape')
    monkeypatch.setattr(d.data, 'model_projection', reject)
    with pytest.raises(d.Rejected) as error: d.validate_development(*inputs[0], inputs[1])
    assert 'private' not in str(error.value)


@pytest.mark.parametrize('raw', ('{"a":1,"a":2}', '{"a":NaN}', '{', 'x' * (d.data.FILE_BYTES + 1)))
def test_strict_bounded_json(raw):
    with pytest.raises(d.data.DatasetRejectedError): d.data.strict_json(raw)


@pytest.mark.parametrize('name', ('holdout.json', '../holdout.json', 'DEVELOPMENT.json', '', '/etc/passwd'))
def test_no_arbitrary_input_paths(name):
    with pytest.raises(d.Rejected): d.read_fixed(name)


def checkout(tmp_path, monkeypatch):
    root = tmp_path / 'checkout'
    target = root / 'fixtures/action-evaluation-v1'
    target.mkdir(parents=True)
    for name in d.NAMES:
        (target / name).write_text(d.data.canonical_json(d.read_fixed(name)), encoding='utf-8')
    monkeypatch.setattr(d, 'ROOT', root)
    return target


@pytest.mark.parametrize('kind', ('symlink', 'hardlink', 'directory', 'oversize'))
def test_fixed_reader_rejects_unsafe_files(tmp_path, monkeypatch, kind):
    target = checkout(tmp_path, monkeypatch)
    path = target / 'development.json'
    path.unlink()
    # Only an invented sentinel, never real Holdout content.
    sentinel = tmp_path / 'blocked.json'
    sentinel.write_text('must not be read')
    if kind == 'symlink': path.symlink_to(sentinel)
    if kind == 'hardlink': os.link(sentinel, path)
    if kind == 'directory': path.mkdir()
    if kind == 'oversize': path.write_text(' ' * (d.data.FILE_BYTES + 1))
    with pytest.raises((d.Rejected, d.data.DatasetRejectedError)): d.read_fixed('development.json')


def test_symlinked_parent_rejected(tmp_path, monkeypatch):
    target = checkout(tmp_path, monkeypatch)
    real = target.with_name('original')
    target.rename(real)
    target.symlink_to(real, target_is_directory=True)
    with pytest.raises(d.Rejected): d.read_fixed('development.json')


def test_deterministic_baseline_and_no_source_prose():
    report = d.diagnose()
    assert report == d.diagnose()
    assert report['metrics']['decisive_count'] == 40
    assert report['metrics']['required_count'] == report['metrics']['uncertain_count'] == 20
    assert report['metrics']['status_counts'] == {'valid': 60}
    assert report['metrics']['required_to_uncertain'] == 20
    assert report['metrics']['decisive_correct'] == 0
    assert report['triads']['selected_triads'] == 16
    assert report['triads']['selected_pairs'] == 48
    assert report['triads']['unchanged_prediction_triads'] == 16
    for dim in ('provider', 'scenario', 'temporal'):
        assert sum(v['selected'] for v in report['by_dimension'][dim].values()) == 60
    for c in report['cases']:
        assert not set(c) & {'subject', 'sender', 'input', 'rationale', 'evidence_refs', 'ambiguity_notes', 'raw_metadata'}
    assert not report['holdout_content_read'] and not report['cross_split_content_revalidated']


@pytest.mark.parametrize('fault,status', [('rejected','rejected'), ('exception','rule_error'), ('invalid','invalid_output')])
def test_failures_never_become_correct_or_valid_abstentions(monkeypatch, fault, status):
    cases, policy, rules, manifest = d.load_development()
    class Broken:
        name, version, ruleset = rules.name, rules.version, rules.ruleset
        def analyze(self, *a):
            if fault == 'rejected': raise d.AnalysisError('sensitive')
            if fault == 'exception': raise RuntimeError('sensitive')
            return object()
    monkeypatch.setattr(d, 'load_development', lambda: (cases, policy, Broken(), manifest))
    report = d.diagnose()
    m = report['metrics']
    assert m['status_counts'] == {status: 60}
    assert m['decisive_count'] == 40 and m['decisive_correct'] == 0
    assert m['required_misses'] == m['required_invalid_or_rejected'] == 20
    assert m['required_to_uncertain'] == m['valid_action_abstentions'] == 0
    assert report['triads']['valid_triads'] == 0
    assert report['triads']['pair_change_rate'] is None
    assert 'sensitive' not in json.dumps(report)


def test_diagnostics_specific_errors_and_triad_sensitivity():
    rows = d.diagnose()['cases']
    for r in rows:
        r['predicted_action'] = r['expected_action']
    assert d.metrics(rows)['decisive_correct'] == 40
    assert d.triads(rows)['all_three_correct'] == 16
    assert d.triads(rows)['changed_pairs'] == 48
    required = [r for r in rows if r['expected_action'] == 'required']
    required[0]['predicted_action'] = 'not_required'
    required[1]['predicted_action'] = 'uncertain'
    required[0]['predicted_relevance'] = 'irrelevant'
    required[0]['expected_relevance'] = 'relevant'
    next(r for r in rows if r['expected_action'] == 'not_required')['predicted_action'] = 'required'
    next(r for r in rows if r['expected_action'] == 'uncertain')['predicted_action'] = 'required'
    m = d.metrics(rows)
    assert m['required_to_not_required'] == m['required_to_uncertain'] == 1
    assert m['relevant_false_irrelevant'] == m['not_required_to_required'] == m['uncertain_concrete'] == 1
    assert d.metrics([])['decisive_accuracy'] is None
    assert d.triads([])['pair_change_rate'] is None


def test_output_is_local_ignored_unique_and_clipboard_friendly(tmp_path, monkeypatch, capsys):
    report = d.diagnose()
    monkeypatch.setattr(d, 'ROOT', tmp_path)
    first, second = d.save(report), d.save(report)
    assert first != second
    assert json.loads((tmp_path / first).read_text()) == report
    monkeypatch.setattr(d, 'diagnose', lambda: report)
    assert d.main(['--synthetic-only']) == 0
    out = capsys.readouterr().out
    assert 'Development' in out and '不代表真实世界准确率' in out
    assert 'synthetic-action-' not in out


def test_failure_does_not_write_or_leak(monkeypatch, capsys):
    def fail(): raise RuntimeError('secret case prose')
    monkeypatch.setattr(d, 'diagnose', fail)
    monkeypatch.setattr(d, 'save', lambda r: pytest.fail('partial output'))
    assert d.main(['--synthetic-only']) == 1
    assert 'secret' not in capsys.readouterr().out


@pytest.mark.parametrize('args', ([], ['--synthetic-only', '--final-holdout'], ['--synthetic-only', '--path', 'other.json']))
def test_cli_only_explicit_fixed_development(args):
    with pytest.raises(SystemExit): d.main(args)
