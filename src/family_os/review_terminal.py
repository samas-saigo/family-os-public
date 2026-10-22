"""Explicit local terminal presentation over review_services; no content logging."""
from collections import Counter
import json
import sys

from .analysis import AnalysisError, canonical_json
from .audit import HumanLabels
from .review_services import select_review, save_review, ReviewChangedError
from .audit_services import EvaluationRevisionConflictError


class ReviewTerminalError(Exception):
    def __init__(self):
        super().__init__('metadata-review requires interactive stdin and stdout; run directly in a local terminal without pipes or redirection')


def require_interactive(input_stream=None, output_stream=None):
    if not (input_stream or sys.stdin).isatty() or not (output_stream or sys.stdout).isatty():
        raise ReviewTerminalError()


class _Quit(Exception):
    pass


class _Back(Exception):
    pass


class _Cancel(Exception):
    pass


def _read(input_stream, output_stream, prompt):
    output_stream.write(prompt)
    output_stream.flush()
    value = input_stream.readline(257)
    if not value:
        raise _Quit()
    if len(value) > 256:
        raise _Quit()
    value = value.strip().casefold()
    if value in ('q', 'quit'):
        raise _Quit()
    return value


def _choose(input_stream, output_stream, label, choices):
    output_stream.write(label + ': ' + ', '.join(f'{i+1}={value}' for i,value in enumerate(choices)) + '; b/back=previous prompt, c/cancel=discard draft, q/quit=exit\n')
    while True:
        value = _read(input_stream, output_stream, '> ')
        if value in ('b', 'back'):
            raise _Back()
        if value in ('c', 'cancel'):
            raise _Cancel()
        if value in choices:
            return value
        if value in tuple(str(i+1) for i in range(len(choices))):
            return choices[int(value)-1]
        output_stream.write('Invalid choice; enter a listed number/value, b/back, c/cancel or q/quit.\n')


def _label_draft(input_stream, output_stream, categories):
    """Prompt-only state machine; return labels only after explicit save.

    Earlier choices are never inferred from predictions. Re-entering a field
    requires a new choice and clears its dependent draft fields.
    """
    stage = 'relevance'
    relevance = category = subcategory = action_label = None
    while True:
        try:
            if stage == 'relevance':
                relevance = _choose(input_stream, output_stream, 'Relevance', ('relevant','irrelevant','uncertain'))
                category = subcategory = action_label = None
                stage = 'domain'
            elif stage == 'domain':
                category = _choose(input_stream, output_stream, 'Domain (unknown means both fields null)',
                                   ('unknown', *sorted(categories)))
                subcategory = action_label = None
                stage = 'action' if category == 'unknown' else 'subcategory'
            elif stage == 'subcategory':
                subcategory = _choose(input_stream, output_stream, 'Subcategory', tuple(sorted(categories[category])))
                action_label = None
                stage = 'action'
            elif stage == 'action':
                action_label = _choose(input_stream, output_stream, 'Action', ('required','not_required','uncertain'))
                stage = 'confirmation'
            else:
                human = HumanLabels(relevance, None if category == 'unknown' else category, subcategory, action_label)
                output_stream.write('Proposed human label: ' + json.dumps(dict(relevance=relevance,
                    domain_category=human.domain_category,domain_subcategory=subcategory,action=action_label),sort_keys=True) + '\n')
                confirmation = _read(input_stream, output_stream,
                    'Type save to confirm; b/back=action, c/cancel=discard draft, q/quit=exit; anything else cancels > ')
                if confirmation in ('b', 'back'):
                    raise _Back()
                return human if confirmation == 'save' else None
        except _Back:
            if stage == 'relevance':
                return None
            stage = {'domain':'relevance', 'subcategory':'domain',
                     'action':'domain' if category == 'unknown' else 'subcategory',
                     'confirmation':'action'}[stage]
        except _Cancel:
            return None


def run_review(engine, household_id, *, input_stream=None, output_stream=None, **options):
    """One bounded cohort; interaction never holds a DB transaction or connection."""
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    require_interactive(input_stream, output_stream)
    output_stream.write('SENSITIVE LOCAL OUTPUT: minimized household metadata. Do not share, upload or record.\n'
                        'Labels measure classifier quality; they are not training, tasks or provider actions.\n')
    selection = select_review(engine, household_id, **options)
    output_stream.write(f'UTC window [{selection.since}, {selection.until}); selected {len(selection.items)}.\n'
                        + f"Classifier: {selection.definition['analyzer_name']} / {selection.definition['analyzer_version']}\n")
    counts = Counter(displayed=0, skipped=0, labeled=0, aborted=0, changed_source=0, failed=0)
    providers = {}
    active = None
    finished = True
    try:
        for index, item in enumerate(selection.items, 1):
            active = providers.setdefault(item.provider, Counter({key:0 for key in counts}))
            finished = False
            counts['displayed'] += 1
            active['displayed'] += 1
            # JSON escaping prevents terminal-control characters in source text
            # from impersonating prompts. Only the existing local display allowlist.
            display = dict(provider=item.provider, record_type=item.record_type, occurred_at=item.occurred_at,
                subject=item.subject, sender=item.sender, display_metadata=item.display_metadata,
                prediction_origin=item.prediction_origin, prediction=item.prediction,
                latest_human_revision=item.latest_human_revision, human_labels=item.human_labels)
            output_stream.write(f'\nRecord {index}/{len(selection.items)}\n' + canonical_json(display) + '\n')
            while True:
                action = _read(input_stream, output_stream, '[s]kip / [l]abel / [q]uit > ')
                if action in ('s', 'skip'):
                    outcome = 'skipped'
                    break
                if action not in ('l', 'label'):
                    output_stream.write('Invalid choice; use s, l or q.\n')
                    continue
                human = _label_draft(input_stream, output_stream, selection.categories)
                if human is None:
                    output_stream.write('Not saved; draft discarded. Back at this record action menu.\n')
                    continue
                try:
                    save_review(engine, item.ticket, human, confirmed=True,
                        **{key:value for key,value in options.items() if key in ('classification_path','rules_path')})
                    # Account for the completed commit before writing its message:
                    # Ctrl+C during output must not call a saved label aborted.
                    counts['labeled'] += 1
                    active['labeled'] += 1
                    finished = True
                    output_stream.write('Saved an append-only human evaluation revision.\n')
                    break
                except ReviewChangedError:
                    outcome = 'changed_source'
                    output_stream.write('Source snapshot or definition changed; nothing saved. Restart review to refresh.\n')
                except EvaluationRevisionConflictError:
                    outcome = 'failed'
                    output_stream.write('Concurrent write conflict; nothing saved. Restart review for an explicit retry.\n')
                except AnalysisError:
                    outcome = 'failed'
                    output_stream.write('Label could not be saved; nothing saved. Check local configuration before retrying.\n')
                break
            if not finished:
                counts[outcome] += 1
                active[outcome] += 1
                finished = True
    except (_Quit, KeyboardInterrupt):
        if active is not None and not finished:
            counts['aborted'] += 1
            active['aborted'] += 1
    summary = dict(counts, providers={key:dict(value) for key,value in sorted(providers.items())})
    output_stream.write('Session summary: ' + json.dumps(summary,sort_keys=True) + '\n')
    output_stream.flush()
    return summary
