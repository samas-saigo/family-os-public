"""Fixed synthetic inputs only; forbid Holdout/full-loader and live execution."""
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

from experiments import rule_evidence_gap as g


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*a, **kw): pytest.fail('Forbidden full loader/network/model/process')
    for name in ('load_dataset', 'validate_dataset', 'validate_cases', 'manifest_for', 'report', '_read'):
        monkeypatch.setattr(g.dev.data, name, forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)


def test_entry_all_dependencies_file_allowlist(monkeypatch, capsys):
    allowed = {str(g.ROOT / 'fixtures/action-evaluation-v1' / n) for n in g.dev.NAMES}
    allowed |= {str(g.ROOT / 'config' / n) for n in g.CONFIG_SHA256}
    allowed.add(str(g.ROOT / 'fixtures/metadata-reasoning.synthetic.json'))
    seen = set()
    def guard(original):
        def checked(path, *a, **kw):
            if not isinstance(path, int):
                normalized = os.path.abspath(os.fspath(path))
                if normalized in allowed:
                    seen.add(normalized)
                else:
                    # Exercise the real writer too: only its fresh, fixed-name
                    # JSON output may be opened, exclusively for creation.
                    assert a and a[0] == 'x', 'Unexpected file access blocked'
                    relative = Path(normalized).relative_to(g.ROOT / g.LOCAL)
                    assert len(relative.parts) == 2 and relative.name == 'report.json'
                    assert len(relative.parts[0]) == 32 and set(relative.parts[0]) <= set('0123456789abcdef')
            return original(path, *a, **kw)
        return checked
    for module, name in ((builtins, 'open'), (io, 'open'), (os, 'open')):
        monkeypatch.setattr(module, name, guard(getattr(module, name)))
    assert g.main(['--synthetic-only']) == 0
    assert seen == allowed
    assert '12/14' in capsys.readouterr().out
    for name in ('holdout.json', '../holdout.json', 'private.json'):
        with pytest.raises(AssertionError):
            Path(g.ROOT / 'fixtures/action-evaluation-v1' / name).open()


def test_two_frozen_cohorts_and_original_scores():
    r = g.report()
    assert r == g.report()
    dev, old = (r['cohorts'][name] for name in ('development60', 'legacy37'))
    assert dev['summary']['status_counts'] == {'valid': 60}
    assert old['summary']['status_counts'] == {'valid': 34, 'projection_rejected': 3}
    assert (dev['summary']['decisive_count'], old['summary']['decisive_count']) == (40, 14)
    assert (dev['summary']['required_count'], old['summary']['required_count']) == (20, 6)
    assert dev['summary']['decisive_correct'] == 0 and old['summary']['decisive_correct'] == 12
    assert old['summary']['required_misses'] == 2
    assert dev['summary']['action_states'] == {'no_evidence': 58, 'weak_only': 2}
    assert old['summary']['action_states'] == {'strong_unanimous': 12, 'no_evidence': 17, 'conflict': 2, 'weak_only': 3}
    assert dev['summary']['caution_cases'] == 27 and dev['summary']['veto_cases'] == 0
    assert old['summary']['veto_cases'] == 5
    assert dev['summary']['projection_trace_changes'] == old['summary']['projection_trace_changes'] == 0
    assert not r['holdout_content_read'] and not r['cross_split_content_revalidated']
    assert all(c['scenario'] == 'unannotated' for c in old['cases'])


def test_actual_rule_states_and_no_prediction_changes():
    development, legacy, p, rules, _ = g.load()
    states = set()
    for c in development + legacy:
        row = g.trace(c, p, rules)
        if row['status'] != 'valid':
            assert c.id in g.REFUSED
            continue
        original = rules.analyze(c.input, p)
        assert row['predicted_action'] == original.action_label
        states.add(row['states']['action'])
        assert not set(row['matched_rule_ids']) & set(row['vetoed_rule_ids'])
    assert states == set(g.STATES)


def test_three_refused_cases_never_reach_matcher(monkeypatch):
    _, legacy, policy, rules, _ = g.load()
    def fail(*a): pytest.fail('Projection refused cases must not be traced')
    monkeypatch.setattr(g, 'checked_diagnosis', fail)
    for c in legacy:
        if c.id in g.REFUSED:
            row = g.trace(c, policy, rules)
            assert row['status'] == 'projection_rejected' and row['states'] is None
            assert row['predicted_action'] is None


def test_trace_confirms_phrase_scope_and_missing_metadata():
    dev = g.report()['cohorts']['development60']['summary']
    for name, rule in dev['by_rule'].items():
        if rule['strength'] == 'strong':
            assert rule['predicate_match_count'] == 0
            assert rule['scope_failed_predicates']['subject_phrases_any'] == rule['scope_eligible']
    assert dev['by_rule']['weak_attention']['accepted_match_count'] == 2
    vet = dev['by_rule']['vet_appointment']
    assert vet['scope_eligible'] == 12
    assert vet['scope_failed_predicates'] == {'subject_phrases_any': 12, 'subject_tokens_all': 12, 'metadata_equals': 9, 'metadata_present': 3}
    assert vet['scope_missing_metadata'] == {'start.dateTime': 3, 'status': 3}
    rows = g.report()['cohorts']['development60']['cases']
    assert all(c['states']['action'] == 'no_evidence' and not c['matched_rule_ids'] and not c['vetoed_rule_ids']
               for c in rows if c['expected_action'] == 'required')


def test_triad_changes_not_mistaken_for_accuracy():
    triads = g.report()['cohorts']['development60']['triads']
    assert len(triads['groups']) == 16
    assert triads['classification']['selected_pairs'] == 48
    assert triads['changed_pairs'] == {'matched_rule_ids': 2, 'vetoed_rule_ids': 0, 'states': 2, 'predicted_action': 0, 'predicates': 8}
    assert triads['classification']['all_three_correct'] == 0
    assert sum(group['correct_pairs'] for group in triads['groups'].values()) == 0


def test_dimensions_conserve_cohort_denominators():
    for co in g.report()['cohorts'].values():
        for dimension in co['by_dimension'].values():
            assert sum(m['selected'] for m in dimension.values()) == co['summary']['selected']
            assert sum(m['required_count'] for m in dimension.values()) == co['summary']['required_count']


@pytest.mark.parametrize('mutation', ('state', 'unknown_id', 'duplicate_id', 'strong', 'overlap', 'output', 'wrong_type'))
def test_invalid_trace_contract_fails_closed(monkeypatch, mutation):
    development, _, p, rules, _ = g.load()
    c = development[0]
    diag = rules.diagnose(c.input, p)
    if mutation == 'state': diag = replace(diag, states=dict(diag.states, action='invented'))
    if mutation == 'unknown_id': diag = replace(diag, matched_rule_ids=('invented',))
    if mutation == 'duplicate_id': diag = replace(diag, matched_rule_ids=('weak_attention', 'weak_attention'))
    if mutation == 'strong': diag = replace(diag, strong_rule_ids=('weak_attention',))
    if mutation == 'overlap': diag = replace(diag, matched_rule_ids=('weak_attention',), vetoed_rule_ids=('weak_attention',))
    if mutation == 'output': diag = replace(diag, output=object())
    if mutation == 'wrong_type': diag = object()
    monkeypatch.setattr(g.matcher.MetadataRulesAnalyzer, 'diagnose', lambda *a: diag)
    row = g.trace(c, p, rules)
    assert row['status'] in ('diagnosis_rejected', 'diagnosis_invalid')
    assert row['predicted_action'] is None and row['states'] is None
    m = g.summary([row], rules)
    assert m['decisive_correct'] == 0 and sum(m['action_states'].values()) == 0


def test_consistent_but_forged_match_trace_detected(monkeypatch):
    development, _, p, rules, _ = g.load()
    c = next(c for c in development if rules.diagnose(c.input, p).matched_rule_ids)
    diag = rules.diagnose(c.input, p)
    forged = replace(diag, matched_rule_ids=(), strong_rule_ids=(), states=dict(diag.states, action='no_evidence'))
    monkeypatch.setattr(g.matcher.MetadataRulesAnalyzer, 'diagnose', lambda *a: forged)
    assert g.trace(c, p, rules)['status'] == 'diagnosis_invalid'


def test_error_does_not_leak_content(monkeypatch, capsys):
    def fail(*a): raise RuntimeError('private source content')
    monkeypatch.setattr(g, 'report', fail)
    monkeypatch.setattr(g, 'save', lambda *a: pytest.fail('partial report'))
    assert g.main(['--synthetic-only']) == 1
    assert 'private source' not in capsys.readouterr().out


@pytest.mark.parametrize('target', ('legacy', 'rules', 'policy'))
def test_frozen_file_identity_drift_rejected(monkeypatch, target):
    original = g.read_checked
    def changed(path):
        if (target == 'legacy' and path.name.endswith('.json') or target == 'rules' and path.name == 'metadata-classifier.yaml'
                or target == 'policy' and path.name == 'classification.yaml'):
            return b'corrupt'
        return original(path)
    monkeypatch.setattr(g, 'read_checked', changed)
    with pytest.raises(g.dev.Rejected): g.load()


def test_development_frozen_identity_is_not_bypassed(monkeypatch):
    original = g.dev.read_fixed
    def changed(name):
        value = original(name)
        if name == 'development.json': value['cases'][0]['extra'] = True
        return value
    monkeypatch.setattr(g.dev, 'read_fixed', changed)
    with pytest.raises(g.dev.Rejected): g.load()


@pytest.mark.parametrize('kind', ('symlink', 'hardlink', 'oversize'))
def test_checked_reader_rejects_unsafe_input(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(g, 'ROOT', tmp_path)
    p = tmp_path / 'fixtures/metadata-reasoning.synthetic.json'
    p.parent.mkdir()
    sentinel = tmp_path / 'sentinel.json'
    sentinel.write_text('{}')
    if kind == 'symlink': p.symlink_to(sentinel)
    if kind == 'hardlink': os.link(sentinel, p)
    if kind == 'oversize': p.write_bytes(b' ' * (g.dev.data.FILE_BYTES + 1))
    with pytest.raises(g.dev.Rejected): g.read_checked(p)


def test_json_and_summary_have_no_case_prose(tmp_path, monkeypatch):
    result = g.report()
    for co in result['cohorts'].values():
        for c in co['cases']:
            assert not set(c) & {'subject', 'sender', 'rationale', 'evidence_refs', 'ambiguity_notes', 'fake_response', 'input'}
    monkeypatch.setattr(g, 'ROOT', tmp_path)
    first, second = g.save(result), g.save(result)
    assert first != second and json.loads((tmp_path / first).read_text()) == result
    text = g.short_summary(result, first)
    assert '不代表真实世界准确率' in text and '未运行 AI' in text
    assert '12/14' in text and '0/40' in text
    assert 'synthetic-action-' not in text


@pytest.mark.parametrize('args', ([], ['--synthetic-only', '--holdout'], ['--synthetic-only', '--path', 'other.json']))
def test_no_arbitrary_paths_or_split_arguments(args):
    with pytest.raises(SystemExit): g.main(args)


def test_zero_denominators_do_not_turn_into_zero_accuracy():
    _, _, _, rules, _ = g.load()
    assert g.summary([], rules)['decisive_accuracy'] is None
    assert g.triads([])['classification']['pair_change_rate'] is None


@pytest.mark.parametrize('suffix', ('fixtures/action-evaluation-v1/holdout.json', 'fixtures/other.json', 'config/household.yaml', 'fixtures/../fixtures/metadata-reasoning.synthetic.json'))
def test_low_level_reader_rejects_unapproved_paths(suffix):
    with pytest.raises(g.dev.Rejected): g.read_checked(g.ROOT / suffix)
