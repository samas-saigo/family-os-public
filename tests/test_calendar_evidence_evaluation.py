"""Fixed synthetic cohorts and exact deterministic aggregates, without model inference."""
import ast
import builtins
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from family_os import calendar_action_evidence as core
from family_os import calendar_evidence_evaluation as runner


@pytest.fixture
def cohorts():
    return runner.load_cohorts()


def test_frozen_development_12_includes_all_four_required_unchanged(cohorts):
    dev, guards = cohorts
    assert len(dev) == 12 and len(guards) == 78
    original = json.loads((runner.ROOT / 'fixtures/action-evaluation-v1/development.json').read_text())
    selected = [c for c in original['cases'] if c['input']['provider'] == 'google_calendar']
    assert [c.input for c in dev] == [c['input'] for c in selected]
    assert [c.truth for c in dev] == [c['expected']['action'] for c in selected]
    assert sum(c.truth == 'required' for c in dev) == 4
    assert sha256((runner.ROOT / 'fixtures/action-evaluation-v1/development.json').read_bytes()).hexdigest() == 'dca27d27aab7976c94be6572d7152e24342de11c804c47163a12ce735b35ca6d'
    assert sha256((runner.ROOT / 'fixtures/calendar-evidence-guardrails-v1.json').read_bytes()).hexdigest() == '011b5437665a637d9c981d351977a5456b3a4fd4211ed042ae5672333e03b117'


def test_original_calendar_metrics_exact_while_human_review_remains_mandatory(cohorts):
    row = runner.evaluate(cohorts[0])
    assert row['selected'] == row['evaluated'] == row['valid'] == 12
    assert row['input_invalid'] == row['unsupported_output'] == row['unsupported_concrete_decisions'] == 0
    assert row['abstained'] == 4 and row['abstention_rate'] == 1/3
    assert row['required_recall'] == dict(numerator=4, denominator=4, rate=1.0)
    assert row['action_confusion_matrix'] == {
        'required': {'required': 4, 'not_required': 0, 'uncertain': 0},
        'not_required': {'required': 0, 'not_required': 4, 'uncertain': 0},
        'uncertain': {'required': 0, 'not_required': 0, 'uncertain': 4}}
    assert row['mistaken_clearance_on_required'] == row['required_to_uncertain'] == 0
    assert row['false_required_on_not_required'] == dict(count=0, denominator=4, rate=0.0)
    assert row['false_required_on_uncertain'] == dict(count=0, denominator=4, rate=0.0)
    assert row['positive_controls'] == dict(selected=4, missed=0)
    assert row['human_review_count'] == 12 and row['human_review_rate'] == 1
    assert row['indicator']['priority_count'] == 11
    assert row['indicator']['false_alerts_on_not_required'] == 4
    assert row['indicator']['false_alerts_on_uncertain'] == 3
    assert row['indicator']['action_predictions'] == row['indicator']['required_unflagged'] == 0
    assert row['indicator']['human_review_count'] == 12
    assert row['triads']['correct_triads'] == row['triads']['selected_triads'] == 3
    assert row['triads']['correct_pairs'] == row['triads']['changed_prediction_pairs'] == 9


def test_status_missing_cue_and_truth_denominators_are_not_combined(cohorts):
    row = runner.evaluate(cohorts[0])
    assert sum(c['selected'] for c in row['by_status'].values()) == 12
    assert all(row['by_status'][s]['selected'] == 3 for s in ('confirmed','cancelled','tentative','missing'))
    assert row['by_status']['confirmed']['required_recall']['denominator'] == 3
    assert row['by_status']['missing']['required_recall']['denominator'] == 1
    assert row['by_status']['cancelled']['required_recall']['rate'] is None
    assert row['by_cue']['status_condition']['selected'] == 9
    assert row['by_cue']['standalone']['selected'] == 3
    assert row['by_cue']['status_condition']['triads']['correct_triads'] == 3
    assert row['by_cue']['standalone']['triads']['complete_triad_correct_rate'] is None
    assert sum(c['selected'] for c in row['by_family'].values()) == 12


def test_separate_guardrail_cohort_counts_and_invalids_not_fabricated_abstentions(cohorts):
    row = runner.evaluate(cohorts[1])
    assert row['selected'] == row['evaluated'] == 78
    assert row['valid'] == 61 and row['input_invalid'] == 17
    assert row['abstained'] == 41 and row['abstention_rate'] == 41/61
    assert sum(sum(r.values()) for r in row['action_confusion_matrix'].values()) == 61
    assert row['required_recall'] == dict(numerator=13, denominator=13, rate=1.0)
    assert row['false_required_on_not_required'] == dict(count=0, denominator=7, rate=0.0)
    assert row['false_required_on_uncertain'] == dict(count=0, denominator=41, rate=0.0)
    assert row['positive_controls'] == dict(selected=13, missed=0)
    assert row['human_review_count'] == row['indicator']['human_review_count'] == 78
    assert row['indicator']['valid'] == 61 and row['indicator']['priority_count'] == 49
    assert row['indicator']['false_alerts_on_not_required'] == 7
    assert row['indicator']['false_alerts_on_uncertain'] == 29
    invalid = row['by_family']['invalid_projection']
    assert invalid['selected'] == invalid['input_invalid'] == invalid['human_review_count'] == 17
    assert invalid['abstained'] == invalid['valid'] == 0
    assert invalid['abstention_rate'] is None
    assert invalid['required_recall']['rate'] is None
    assert row['by_family']['instruction_attempt']['abstained'] == 5
    assert row['by_family']['status_only']['abstained'] == 7
    assert row['by_family']['keyword_only']['abstained'] == 9
    assert row['by_family']['conflict']['abstained'] == 7


def test_empty_cohort_has_null_denominators_not_guessed_accuracy():
    row = runner.evaluate(())
    assert row['selected'] == row['valid'] == row['human_review_count'] == 0
    assert row['required_recall'] == dict(numerator=0, denominator=0, rate=None)
    assert row['abstention_rate'] is None and row['human_review_rate'] is None
    assert row['indicator']['priority_rate'] is None
    assert row['triads']['pair_correct_rate'] is None


def test_required_mistaken_clearance_and_uncertainty_have_different_counts(cohorts):
    cases = tuple(replace(c, truth='required', positive_control=True) for c in cohorts[0])
    row = runner.evaluate(cases)
    assert row['required_recall'] == dict(numerator=4, denominator=12, rate=1/3)
    assert row['mistaken_clearance_on_required'] == 4 and row['required_to_uncertain'] == 4
    assert row['positive_controls']['missed'] == 8


def test_concrete_false_alerts_are_split_by_not_required_and_uncertain(cohorts):
    required = tuple(c for c in cohorts[0] if c.truth == 'required')
    cases = tuple(replace(c, truth='not_required' if i < 2 else 'uncertain', positive_control=False)
        for i, c in enumerate(required))
    row = runner.evaluate(cases)
    assert row['false_required_on_not_required'] == dict(count=2, denominator=2, rate=1)
    assert row['false_required_on_uncertain'] == dict(count=2, denominator=2, rate=1)
    assert row['required_recall']['rate'] is None


def test_unsupported_concrete_output_is_rejected_not_accepted_as_recall_gain(cohorts, monkeypatch):
    original = core.interpret
    monkeypatch.setattr(core, 'interpret', lambda p: replace(original(p), action_label='required'))
    row = runner.evaluate(tuple(c for c in cohorts[0] if c.truth == 'uncertain'))
    assert row['unsupported_output'] == row['unsupported_concrete_decisions'] == 4
    assert row['valid'] == row['abstained'] == 0
    assert row['false_required_on_uncertain']['count'] == 0  # rejected outputs are not predictions
    assert row['truth_cohorts']['uncertain']['invalid'] == 4 and row['human_review_count'] == 4


def test_partial_triad_scoring_never_invents_valid_predictions(cohorts, monkeypatch):
    original = core.interpret
    def wrong(p):
        out = original(p)
        return replace(out, action_label='uncertain') if p.fields.get('raw_metadata', {}).get('status') == 'confirmed' else out
    monkeypatch.setattr(core, 'interpret', wrong)
    row = runner.evaluate(cohorts[0])
    assert row['unsupported_output'] == 3
    assert row['triads']['selected_triads'] == 3 and row['triads']['valid_triads'] == 0
    assert row['triads']['selected_pairs'] == 9 and row['triads']['valid_pairs'] == 3
    assert row['triads']['correct_pairs'] == 3
    assert row['required_recall']['denominator'] == 4 and row['required_recall']['numerator'] == 1


def test_no_relevance_domain_authority_and_every_required_uncertain_remains_visible(cohorts):
    for cases in cohorts:
        row = runner.evaluate(cases)
        assert not row['relevance_filtering'] and not row['domain_authority']
        assert row['silent_suppression_count'] == 0 and row['human_review_count'] == len(cases)
        assert not hasattr(cases[0], 'relevance_label') and not hasattr(cases[0], 'domain_category')


@pytest.mark.parametrize('family,truth,cue,positive', (
    ('PRIVATE_FAMILY', 'required', 'standalone', True), ('status_only','UNKNOWN','standalone',False),
    ('status_only','uncertain','PRIVATE_CUE',False), ('status_only','uncertain','standalone',True)))
def test_untrusted_evaluation_annotations_cannot_leak_into_report(cohorts, family, truth, cue, positive):
    with pytest.raises(core.CalendarEvidenceError):
        runner.evaluate((replace(cohorts[0][0], family=family, truth=truth, cue=cue, positive_control=positive),))


def test_invalid_positive_cannot_silently_disappear(cohorts):
    source = dict(cohorts[0][0].input, account_id='PRIVATE')
    with pytest.raises(core.CalendarEvidenceError): runner.evaluate((replace(cohorts[0][0], input=source),))


def test_report_is_deterministic_aggregate_only_and_not_historical_model_reconstruction(cohorts, capsys):
    one = runner.report()
    assert one == runner.report()
    assert one['exit_decision'] == 'continue_isolated_synthetic_research_only'
    assert not one['holdout_access'] and not one['persistence'] and not one['production_wiring']
    assert one['no_ai_or_model_calls'] and not one['action_authority']
    assert 'no per-case' in one['historical_model_context']
    assert runner.main([]) == 0
    emitted = capsys.readouterr().out
    assert json.loads(emitted) == one
    for cases in cohorts:
        for c in cases:
            title = c.input.get('subject')
            if type(title) is str and title:
                assert title not in emitted
    for marker in ('synthetic-action-', 'raw_metadata', 'example.invalid', '/workspace', 'rationale', 'subject', 'prompt', 'SECRET', 'PRIVATE_SENTINEL'):
        assert marker not in emitted


@pytest.mark.parametrize('argv', (['--file','PRIVATE'], ['--holdout'], ['--household','PRIVATE'],
    ['--model','qwen3:4b-instruct'], ['--full'], ['--export','PRIVATE']))
def test_cli_has_no_arbitrary_input_export_or_model_controls(argv, capsys):
    assert runner.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.err == ''
    assert captured.out == 'Synthetic Calendar evaluation failed; no source content or partial report printed\n'


@pytest.mark.parametrize('kind', ('bad', 'interrupt'))
def test_errors_print_no_private_exception_or_partial_report(monkeypatch, capsys, kind):
    def fail():
        if kind == 'interrupt': raise KeyboardInterrupt
        raise RuntimeError('PRIVATE_TITLE https://private.invalid access_token=SECRET')
    monkeypatch.setattr(runner, 'report', fail)
    assert runner.main([]) == (130 if kind == 'interrupt' else 1)
    text = capsys.readouterr().out
    assert 'PRIVATE' not in text and 'SECRET' not in text and 'https' not in text
    assert text.count('\n') == 1


def test_quality_blocker_stops_exit_without_changing_anything(monkeypatch, capsys):
    value = runner.report()
    monkeypatch.setattr(runner, 'report', lambda: dict(value, exit_decision='stop_abstain'))
    assert runner.main([]) == 1
    assert json.loads(capsys.readouterr().out)['exit_decision'] == 'stop_abstain'


def test_only_two_pinned_readonly_fixture_paths_and_no_holdout(monkeypatch):
    original = Path.open
    seen = []
    def opened(path, mode='r', *args, **kwargs):
        assert mode == 'rb' and str(path.relative_to(runner.ROOT)) in runner.FILES
        seen.append(str(path.relative_to(runner.ROOT)))
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    assert runner.report()['development']['selected'] == 12
    assert seen == list(runner.FILES)
    with pytest.raises(core.CalendarEvidenceError): runner._read('fixtures/action-evaluation-v1/holdout.json')
    with pytest.raises(core.CalendarEvidenceError): runner._read('/PRIVATE/database.sqlite3')
    assert seen == list(runner.FILES)


def test_fixture_tampering_fails_before_any_interpretation(monkeypatch):
    original = Path.open
    import io
    def opened(path, mode='r', *args, **kwargs):
        if str(path).endswith('development.json'): return io.BytesIO(b'{"PRIVATE":"SECRET"}')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    monkeypatch.setattr(core, 'interpret', lambda _: pytest.fail('must not interpret tampered input'))
    with pytest.raises(core.CalendarEvidenceError): runner.report()


def test_calls_are_offline_without_credentials_database_filesystem_exports_or_clock(cohorts, monkeypatch):
    def denied(*args, **kwargs): pytest.fail('effectful call forbidden')
    monkeypatch.setattr(socket, 'socket', denied)
    monkeypatch.setattr(builtins, 'open', denied)
    monkeypatch.setattr(Path, 'open', denied)
    monkeypatch.setattr(Path, 'write_text', denied)
    monkeypatch.setattr(Path, 'write_bytes', denied)
    # Pure evaluation on already supplied synthetic values has no filesystem calls.
    assert runner.evaluate(cohorts[0])['valid'] == 12
    assert runner.evaluate(cohorts[1])['input_invalid'] == 17


def _check_imports(text, allowed):
    tree = ast.parse(text)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.extend([node.module] if node.module else [a.name for a in node.names])
    assert set(names) <= allowed
    return tree


def test_standard_library_only_import_call_graph_and_no_production_wiring():
    core_path, runner_path = Path(core.__file__), Path(runner.__file__)
    tree = _check_imports(core_path.read_text(), {'collections.abc','dataclasses','datetime','hashlib','json','re','types','unicodedata','urllib.parse'})
    _check_imports(runner_path.read_text(), {'argparse','collections','dataclasses','hashlib','itertools','json','pathlib','calendar_action_evidence'})
    prohibited = {'open','eval','exec','__import__','print','input','read','write','request','connect','now','today','utcnow','sleep'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ''
            assert name not in prohibited
    for path in (runner.ROOT / 'src/family_os').rglob('*.py'):
        if path.name in {'calendar_action_evidence.py','calendar_evidence_evaluation.py',
                         'synthetic_review.py'}: continue
        text = path.read_text()
        assert 'calendar_action_evidence' not in text and 'calendar_evidence_evaluation' not in text


@pytest.mark.parametrize('statement', ('import sqlalchemy','import keyring','import requests','from family_os import cli',
    'from family_os.metadata_classifier import MetadataRulesAnalyzer','import ollama','from socket import socket'))
def test_import_isolation_guard_checks_both_import_forms(statement):
    with pytest.raises(AssertionError):
        _check_imports(statement, {'collections.abc','dataclasses','datetime','hashlib','json','re','types','unicodedata','urllib.parse'})


def test_fresh_import_has_no_auto_run_no_model_provider_or_database_dependencies():
    script = '''
import builtins
original = builtins.__import__
forbidden = {'sqlalchemy','keyring','requests','httpx','socket','ollama','openai','anthropic','google','family_os.cli','family_os.analysis','family_os.metadata_classifier','family_os.synthetic_reasoning','family_os.action_model_benchmark'}
def imports(name, *args, **kwargs):
    if name in forbidden or name.split('.')[0] in forbidden:
        raise RuntimeError('forbidden import')
    return original(name,*args,**kwargs)
builtins.__import__ = imports
import family_os.calendar_action_evidence
import family_os.calendar_evidence_evaluation
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, cwd=runner.ROOT)
    assert result.returncode == 0 and result.stdout == result.stderr == ''
