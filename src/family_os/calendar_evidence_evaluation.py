"""Opt-in offline aggregate evaluation of two fixed synthetic Calendar cohorts.

No model/production imports. Only two frozen fixture reads; no holdout or exports.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

from . import calendar_action_evidence as evidence

ROOT = Path(__file__).resolve().parents[2]
FILES = {
    'fixtures/action-evaluation-v1/development.json': 'dca27d27aab7976c94be6572d7152e24342de11c804c47163a12ce735b35ca6d',
    'fixtures/calendar-evidence-guardrails-v1.json': '011b5437665a637d9c981d351977a5456b3a4fd4211ed042ae5672333e03b117'}
FILE_BYTES = 262144
METRICS_VERSION = 'calendar-evidence-metrics-v1'
FAMILIES = ('status_only', 'keyword_only', 'explicit_outstanding', 'completion_negation',
    'cancelled_followup', 'conflict', 'status_condition', 'condition', 'superseded',
    'instruction_attempt', 'invalid_date', 'booked_preparation', 'unknown_status',
    'historical', 'event_time', 'invalid_projection')


@dataclass(frozen=True)
class EvaluationCase:
    input: dict = field(repr=False)
    truth: object = field(repr=False)
    family: str
    positive_control: bool
    cue: str
    group: object = field(default=None, repr=False)


def _read(name):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError()
            value[key] = item
        return value
    try:
        if name not in FILES:
            raise ValueError()
        with (ROOT / name).open('rb') as stream:
            raw = stream.read(FILE_BYTES + 1)
        if len(raw) > FILE_BYTES or sha256(raw).hexdigest() != FILES[name]:
            raise ValueError()
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise evidence.CalendarEvidenceError() from None


def load_cohorts():
    """Pin entire development file, then select Calendar; never read holdout."""
    try:
        dev = _read('fixtures/action-evaluation-v1/development.json')
        guard = _read('fixtures/calendar-evidence-guardrails-v1.json')
        if dev['synthetic_only'] is not True or dev['dataset_version'] != 'action-evaluation-v1' or dev['split'] != 'development' or len(dev['cases']) != 60:
            raise ValueError()
        selected = tuple(EvaluationCase(c['input'], c['expected']['action'],
            'frozen_status_condition' if c['cue_field'] == 'raw_metadata.status' else 'frozen_standalone',
            c['expected']['action'] == 'required',
            'status_condition' if c['cue_field'] == 'raw_metadata.status' else 'standalone', c['counterfactual_group'])
            for c in dev['cases'] if c['input']['provider'] == 'google_calendar')
        if len(selected) != 12 or Counter(c.truth for c in selected) != Counter(dict.fromkeys(evidence.ACTIONS, 4)):
            raise ValueError()
        if set(guard) != {'synthetic_only', 'dataset_version', 'cases'} or guard['synthetic_only'] is not True or guard['dataset_version'] != 'calendar-evidence-guardrails-v1' or len(guard['cases']) != 78:
            raise ValueError()
        controls = []
        for c in guard['cases']:
            if set(c) != {'family', 'input', 'expected_action', 'positive_control'} or type(c['input']) is not dict or c['expected_action'] not in (*evidence.ACTIONS, None) or type(c['positive_control']) is not bool or c['family'] not in FAMILIES or c['positive_control'] and c['expected_action'] != 'required':
                raise ValueError()
            controls.append(EvaluationCase(c['input'], c['expected_action'], c['family'],
                c['positive_control'], 'status_condition' if c['family'] == 'status_condition' else 'standalone'))
        return selected, tuple(controls)
    except Exception:
        raise evidence.CalendarEvidenceError() from None


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _status(case):
    metadata = case.input.get('raw_metadata', {})
    if type(metadata) is not dict:
        return 'malformed'
    if 'status' not in metadata:
        return 'missing'
    value = metadata['status']
    if type(value) is not str:
        return 'malformed'
    return value if value in ('confirmed', 'cancelled', 'tentative') else 'unknown'


def _triads(rows):
    groups = {}
    for c, output, _, _ in rows:
        if c.group:
            groups.setdefault(c.group, []).append((c, output))
    selected = valid = correct = pairs = valid_pairs = changed = correct_pairs = 0
    for members in groups.values():
        if len(members) != 3:
            continue
        selected += 1
        if all(out is not None for _, out in members):
            valid += 1
            correct += int(all(out.action_label == c.truth for c, out in members))
        for (a, left), (b, right) in combinations(members, 2):
            pairs += 1
            if left is not None and right is not None:
                valid_pairs += 1
                changed += int(left.action_label != right.action_label)
                correct_pairs += int(left.action_label == a.truth and right.action_label == b.truth)
    return dict(selected_triads=selected, valid_triads=valid, correct_triads=correct,
        complete_triad_correct_rate=ratio(correct, valid), selected_pairs=pairs, valid_pairs=valid_pairs,
        changed_prediction_pairs=changed, correct_pairs=correct_pairs,
        pair_change_rate=ratio(changed, valid_pairs), pair_correct_rate=ratio(correct_pairs, valid_pairs))


def _summary(rows):
    matrix = {truth: dict.fromkeys(evidence.ACTIONS, 0) for truth in evidence.ACTIONS}
    cohorts = {truth: dict(selected=0, evaluated=0, valid=0, invalid=0) for truth in evidence.ACTIONS}
    valid = invalid = unsupported = abstained = priority = indicator_valid = 0
    positive_selected = positive_missed = priority_missed = 0
    false_alerts = dict.fromkeys(('not_required', 'uncertain'), 0)
    required_cues = Counter()
    for c, out, flag, state in rows:
        valid += int(state == 'valid')
        invalid += int(state == 'input_invalid')
        unsupported += int(state == 'unsupported_output')
        if c.truth in evidence.ACTIONS:
            cohort = cohorts[c.truth]
            cohort['selected'] += 1
            cohort['evaluated'] += 1
            cohort['valid'] += int(state == 'valid')
            cohort['invalid'] += int(state != 'valid')
        if out is not None:
            matrix[c.truth][out.action_label] += 1
            abstained += int(out.action_label == 'uncertain')
        if flag is not None:
            indicator_valid += 1
            priority += int(flag.priority)
            if c.truth in false_alerts:
                false_alerts[c.truth] += int(flag.priority)
            if c.truth == 'required' and not flag.priority:
                priority_missed += 1
        if c.positive_control:
            positive_selected += 1
            positive_missed += int(out is None or out.action_label != 'required')
        if out:
            required_cues[out.reason] += 1
    required_total = cohorts['required']['selected']
    nonrequired = cohorts['not_required']['selected']
    uncertain = cohorts['uncertain']['selected']
    correct = matrix['required']['required']
    return dict(selected=len(rows), evaluated=len(rows), valid=valid, input_invalid=invalid,
        unsupported_output=unsupported, unsupported_concrete_decisions=unsupported,
        unsupported_language_abstentions=required_cues['unsupported_evidence'],
        abstained=abstained, abstention_rate=ratio(abstained, valid),
        unknown_status_count=sum(_status(c) == 'unknown' for c, _, _, _ in rows),
        missing_status_count=sum(_status(c) == 'missing' for c, _, _, _ in rows),
        malformed_status_count=sum(_status(c) == 'malformed' for c, _, _, _ in rows),
        action_confusion_matrix=matrix, truth_cohorts=cohorts,
        required_recall=dict(numerator=correct, denominator=required_total, rate=ratio(correct, required_total)),
        required_to_uncertain=matrix['required']['uncertain'],
        mistaken_clearance_on_required=matrix['required']['not_required'],
        false_required_on_not_required=dict(count=matrix['not_required']['required'], denominator=nonrequired,
            rate=ratio(matrix['not_required']['required'], nonrequired)),
        false_required_on_uncertain=dict(count=matrix['uncertain']['required'], denominator=uncertain,
            rate=ratio(matrix['uncertain']['required'], uncertain)),
        positive_controls=dict(selected=positive_selected, missed=positive_missed),
        human_review_count=len(rows), human_review_rate=ratio(len(rows), len(rows)),
        silent_suppression_count=0, relevance_filtering=False, domain_authority=False,
        indicator=dict(valid=indicator_valid, priority_count=priority, priority_rate=ratio(priority, indicator_valid),
            false_alerts_on_not_required=false_alerts['not_required'], false_alerts_on_uncertain=false_alerts['uncertain'],
            required_unflagged=priority_missed, human_review_count=len(rows),
            human_review_rate=ratio(len(rows), len(rows)), action_predictions=0),
        triads=_triads(rows))


def evaluate(cases):
    if type(cases) is not tuple or len(cases) > 100 or any(type(c) is not EvaluationCase for c in cases):
        raise evidence.CalendarEvidenceError()
    rows = []
    for c in cases:
        if type(c.input) is not dict or c.family not in (*FAMILIES, 'frozen_status_condition', 'frozen_standalone') or c.cue not in ('status_condition', 'standalone') or c.truth not in (*evidence.ACTIONS, None) or type(c.positive_control) is not bool or c.positive_control and c.truth != 'required':
            raise evidence.CalendarEvidenceError()
        try:
            projection = evidence.CalendarProjection(c.input)
        except evidence.CalendarEvidenceError:
            if c.truth is not None:  # Frozen annotated positives may not silently become unevaluated.
                raise evidence.CalendarEvidenceError() from None
            rows.append((c, None, None, 'input_invalid'))
            continue
        if c.truth is None:
            raise evidence.CalendarEvidenceError()
        flag = evidence.indicator(projection)
        try:
            out = evidence.validate_proposal(projection, evidence.interpret(projection))
            state = 'valid'
        except evidence.CalendarEvidenceError:
            out, state = None, 'unsupported_output'
        rows.append((c, out, flag, state))
    report = _summary(rows)
    report['by_status'] = {s: _summary([row for row in rows if _status(row[0]) == s])
        for s in ('confirmed', 'cancelled', 'tentative', 'missing', 'unknown', 'malformed')}
    report['by_cue'] = {cue: _summary([row for row in rows if row[0].cue == cue])
        for cue in ('status_condition', 'standalone')}
    report['by_family'] = {family: _summary([row for row in rows if row[0].family == family])
        for family in sorted({c.family for c in cases})}
    return report


def report():
    dev, guards = load_cohorts()
    result = dict(synthetic_only=True, metrics_version=METRICS_VERSION,
        interpreter_version=evidence.EFFECTIVE_VERSION, rule_fingerprint=evidence.RULE_FINGERPRINT,
        indicator_version='inspection-indicator-v1', indicator_fingerprint=evidence.INDICATOR_FINGERPRINT,
        projection_schema=evidence.INPUT_SCHEMA, source_fingerprints=list(FILES.values()),
        development=evaluate(dev), guardrails=evaluate(guards),
        no_ai_or_model_calls=True, holdout_access=False, persistence=False,
        production_wiring=False, action_authority=False,
        historical_model_context='Reported Phase 2T aggregates only; no per-case model predictions or paired attribution')
    blocked = any(c['unsupported_concrete_decisions'] or c['mistaken_clearance_on_required'] or
        c['false_required_on_not_required']['count'] or c['false_required_on_uncertain']['count'] or
        c['positive_controls']['missed'] for c in (result['development'], result['guardrails']))
    result['exit_decision'] = 'stop_abstain' if blocked else 'continue_isolated_synthetic_research_only'
    return result


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default includes user arguments/paths. Never echo them.
        raise evidence.CalendarEvidenceError() from None


def main(argv=None):
    parser = _SafeParser(description='Offline aggregate synthetic Calendar evidence evaluation; no AI or database')
    try:
        parser.parse_args(argv)  # No dataset/file/household/model switches.
        value = report()
        print(evidence.canonical(value))
        return 0 if value['exit_decision'] != 'stop_abstain' else 1
    except KeyboardInterrupt:
        print('Synthetic Calendar evaluation interrupted; no state persisted')
        return 130
    except Exception:
        print('Synthetic Calendar evaluation failed; no source content or partial report printed')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
