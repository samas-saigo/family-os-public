"""Synthetic prompt navigation; persistence and provider boundaries stay unchanged."""
import json

import pytest
from sqlalchemy import event

from family_os import review_terminal as terminal
from family_os.schema import analysis_evaluation_label
from test_analysis import rows
from test_review import TTY, OPTIONS, cohort, history, run

# Input consumed before each logical prompt (unknown deliberately skips child).
STAGES = {
    'relevance': 'l\n',
    'domain': 'l\nrelevant\n',
    'subcategory': 'l\nrelevant\nhome\n',
    'action': 'l\nrelevant\nhome\nutility\n',
    'confirmation': 'l\nrelevant\nhome\nutility\nrequired\n',
}


@pytest.mark.parametrize('stage', STAGES)
@pytest.mark.parametrize('control', ['c', 'cancel'])
def test_cancel_at_every_stage_returns_same_record_then_skip(engine, stage, control):
    cohort(engine, unanalyzed=True)
    before = history(engine)
    summary, output = run(engine, STAGES[stage] + control + '\ns\n')
    assert history(engine) == before
    assert summary['displayed'] == summary['skipped'] == 1
    assert summary['labeled'] == summary['aborted'] == summary['failed'] == 0
    assert output.count('Record 1/1') == 1
    assert output.count('[s]kip / [l]abel / [q]uit') == 2
    assert summary['providers']['gmail'] == {key: summary[key] for key in summary if key != 'providers'}


@pytest.mark.parametrize('stage', STAGES)
@pytest.mark.parametrize('control', ['b', 'back'])
def test_back_at_every_stage_returns_previous_logical_prompt(engine, stage, control):
    cohort(engine, unanalyzed=True)
    before = history(engine)
    # Cancel from the previous field, then skip; first-field Back is already menu.
    suffix = 's\n' if stage == 'relevance' else 'cancel\ns\n'
    summary, output = run(engine, STAGES[stage] + control + '\n' + suffix)
    assert history(engine) == before
    assert summary['skipped'] == summary['displayed'] == 1
    assert summary['aborted'] == summary['failed'] == summary['labeled'] == 0
    previous = {'relevance': '[s]kip / [l]abel / [q]uit', 'domain': 'Relevance:',
                'subcategory': 'Domain (', 'action': 'Subcategory:', 'confirmation': 'Action:'}[stage]
    # The previous prompt is repeated, not the record display or the next field.
    assert output.count(previous) == 2


@pytest.mark.parametrize('control', ['b', 'back'])
def test_action_back_with_unknown_domain_skips_nonexistent_child(engine, control):
    cohort(engine)
    summary, output = run(engine, f'l\nrelevant\nunknown\n{control}\nhome\nutility\nrequired\nsave\n')
    label = rows(engine, analysis_evaluation_label)[0]
    assert summary['labeled'] == 1
    assert (label['domain_category'], label['domain_subcategory']) == ('home', 'utility')
    assert output.count('Domain (') == 2 and output.count('Subcategory:') == 1


@pytest.mark.parametrize('domain,child', [('ignore', 'newsletter'), ('unknown', None)])
def test_subcategory_back_changes_domain_without_stale_child(engine, domain, child):
    cohort(engine)
    child_input = '' if child is None else child + '\n'
    # Select utility, then back from Action and again from Subcategory to Domain.
    summary, output = run(engine, 'l\nirrelevant\nhome\nutility\nb\nback\n' + domain + '\n' + child_input + 'not_required\nsave\n')
    label = rows(engine, analysis_evaluation_label)[0]
    expected = None if domain == 'unknown' else domain
    assert (label['domain_category'], label['domain_subcategory']) == (expected, child)
    assert summary['labeled'] == 1
    proposal = json.loads(output.split('Proposed human label: ')[-1].splitlines()[0])
    assert proposal['domain_subcategory'] == child


def test_changed_domain_rejects_old_subcategory_and_requires_new_choice(engine):
    cohort(engine)
    summary, output = run(engine, 'l\nrelevant\nhome\nutility\nb\nb\nignore\nutility\nnewsletter\nnot_required\nsave\n')
    label = rows(engine, analysis_evaluation_label)[0]
    assert summary['labeled'] == 1 and output.count('Invalid choice') == 1
    assert (label['domain_category'], label['domain_subcategory']) == ('ignore', 'newsletter')


def test_confirmation_back_can_change_action(engine):
    cohort(engine)
    summary, output = run(engine, STAGES['confirmation'] + 'back\nnot_required\nsave\n')
    assert summary['labeled'] == 1
    assert rows(engine, analysis_evaluation_label)[0]['action_label'] == 'not_required'
    assert output.count('Proposed human label:') == 2


def test_confirmation_back_reaches_all_earlier_fields(engine):
    cohort(engine)
    summary, _ = run(engine, STAGES['confirmation'] + 'b\nb\nb\nb\nirrelevant\nignore\nnewsletter\nnot_required\nsave\n')
    label = rows(engine, analysis_evaluation_label)[0]
    assert summary['labeled'] == 1
    assert (label['relevance_label'], label['domain_category'], label['domain_subcategory'], label['action_label']) == (
        'irrelevant', 'ignore', 'newsletter', 'not_required')


@pytest.mark.parametrize('response', ['', 'yes', 'no', 'invalid', 'c', 'cancel'])
def test_unconfirmed_confirmation_returns_same_menu_without_write(engine, response):
    cohort(engine, unanalyzed=True)
    before = history(engine)
    summary, _ = run(engine, STAGES['confirmation'] + response + '\ns\n')
    assert history(engine) == before
    assert summary['skipped'] == 1 and summary['aborted'] == summary['failed'] == summary['labeled'] == 0


def test_cancel_and_restart_requires_all_new_choices(engine):
    cohort(engine)
    summary, output = run(engine, STAGES['confirmation'] + 'cancel\nl\nsave\nirrelevant\nunknown\nnot_required\nsave\n')
    assert summary['labeled'] == 1 and output.count('Invalid choice') == 1
    label = rows(engine, analysis_evaluation_label)[0]
    assert label['relevance_label'] == 'irrelevant' and label['action_label'] == 'not_required'
    assert label['domain_category'] is label['domain_subcategory'] is None


@pytest.mark.parametrize('stage', STAGES)
@pytest.mark.parametrize('control', ['q', 'quit'])
def test_quit_at_every_label_stage_writes_nothing(engine, stage, control):
    cohort(engine, unanalyzed=True)
    before = history(engine)
    summary, _ = run(engine, STAGES[stage] + control + '\n')
    assert history(engine) == before
    assert summary['aborted'] == summary['displayed'] == 1
    assert summary['labeled'] == summary['failed'] == summary['skipped'] == 0


def test_saved_revision_survives_navigation_and_quit_on_next_record(engine):
    cohort(engine, account='one')
    cohort(engine, account='two')
    summary, _ = run(engine, 'l\nrelevant\nunknown\nrequired\nsave\nl\nirrelevant\nignore\nb\nc\nl\nquit\n')
    assert summary['displayed'] == 2 and summary['labeled'] == summary['aborted'] == 1
    assert len(rows(engine, analysis_evaluation_label)) == 1
    assert rows(engine, analysis_evaluation_label)[0]['revision'] == 1


def test_navigation_prompts_hold_no_connection_and_write_only_after_save(engine, monkeypatch):
    cohort(engine, unanalyzed=True)
    before = history(engine)
    checked_out = set()
    event.listen(engine, 'checkout', lambda dbapi, record, proxy: checked_out.add(id(record)))
    event.listen(engine, 'checkin', lambda dbapi, record: checked_out.discard(id(record)))
    original = terminal.save_review
    calls = []
    def save(*args, **kwargs):
        assert not checked_out and history(engine) == before
        calls.append(kwargs['confirmed'])
        return original(*args, **kwargs)
    monkeypatch.setattr(terminal, 'save_review', save)
    class CheckedInput(TTY):
        def readline(self, *args):
            assert not checked_out
            assert history(engine) == before
            return super().readline(*args)
    answers = STAGES['confirmation'] + 'b\nb\nb\nunknown\nb\nc\nl\nuncertain\nunknown\nuncertain\nsave\n'
    summary = terminal.run_review(engine, 'home', input_stream=CheckedInput(answers), output_stream=TTY(), **OPTIONS)
    assert calls == [True] and summary['labeled'] == 1


def test_navigation_invalid_input_never_echoed_and_summary_remains_aggregate(engine):
    cohort(engine, subject='SYNTHETIC\x1b[2J PRIVATE SUBJECT')
    summary, output = run(engine, STAGES['subcategory'] + 'PRIVATE INVALID INPUT\nback\ncancel\ns\n')
    assert 'PRIVATE INVALID INPUT' not in output and '\x1b' not in output
    aggregate = output.split('Session summary: ')[1]
    assert 'SUBJECT' not in aggregate and 'source_record_id' not in aggregate
    assert summary['skipped'] == 1
