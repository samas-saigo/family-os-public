"""Opt-in, pure in-memory Phase 2V research. No household or execution authority."""
import argparse
from dataclasses import dataclass, field
import json
from collections.abc import Mapping

from . import calendar_action_evidence as evidence

CONTRACT_VERSION = 'synthetic-review-v1'
SCENARIO_VERSION = 'synthetic-review-sequences-v1'
IDS = tuple(f'synthetic-event-{i:02d}' for i in range(1, 17))
DISPOSITIONS = ('human_confirmed', 'human_rejected', 'needs_more_information', 'deferred')
RESOLVED = DISPOSITIONS[:2]
MAX_VISITS = 128
MAX_REVISIONS = 128
# Alternate stamps are explicitly synthetic invalidation probes, not new analyzers.
CURRENT_STAMP = (evidence.EFFECTIVE_VERSION, evidence.RULE_FINGERPRINT, CONTRACT_VERSION)
RULE_PROBE_STAMP = (evidence.EFFECTIVE_VERSION,
                    evidence.digest({'synthetic_rule_change_probe': 1}), CONTRACT_VERSION)
ANALYZER_PROBE_STAMP = ('synthetic-analyzer-change-probe-v1', evidence.RULE_FINGERPRINT,
                        CONTRACT_VERSION)
SCHEMA_PROBE_STAMP = (evidence.EFFECTIVE_VERSION, evidence.RULE_FINGERPRINT,
                      'synthetic-review-schema-change-probe-v1')
STAMPS = (CURRENT_STAMP, RULE_PROBE_STAMP, ANALYZER_PROBE_STAMP, SCHEMA_PROBE_STAMP)
INVALID_INPUT = {'provider': 'google_calendar', 'record_type': 'calendar_event', 'subject': 42}
POLICY_FINGERPRINT = evidence.digest(dict(version=CONTRACT_VERSION,
    dispositions=DISPOSITIONS, resolved=RESOLVED, stamps=STAMPS,
    policy='explicit-save; concrete-supported-only-resolution; exact-epoch-repeat; visible-all',
    history='append-only full synthetic snapshot; expected-revision and display-visit checks',
    bounds=dict(visits=MAX_VISITS, revisions=MAX_REVISIONS, snapshot=1000)))


class SyntheticReviewError(ValueError):
    def __init__(self):
        super().__init__('Synthetic review rejected; no decision saved')


def _plain(value):
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


@dataclass(frozen=True)
class SyntheticRecord:
    event_id: str
    snapshot: int
    projection: object = field(repr=False)
    stamp: tuple = CURRENT_STAMP
    invalid: bool = False
    proposal: object = field(init=False, repr=False)
    fingerprint: str = field(init=False)

    def __post_init__(self):
        try:
            if type(self.event_id) is not str or self.event_id not in IDS or not _integer(self.snapshot, 1, 1000):
                raise ValueError()
            if type(self.stamp) is not tuple or self.stamp not in STAMPS or type(self.invalid) is not bool:
                raise ValueError()
            if self.invalid:
                if self.projection is not None:
                    raise ValueError()
                projection, proposal = INVALID_INPUT, None
            else:
                if type(self.projection) is not evidence.CalendarProjection:
                    raise ValueError()
                projection = _plain(self.projection.fields)
                # Revalidate the immutable projection before accepting any observation.
                checked = evidence.CalendarProjection(projection)
                proposal = evidence.validate_proposal(checked, evidence.interpret(checked))
            identity = dict(event_id=self.event_id, snapshot=self.snapshot, input=projection,
                            stamp=self.stamp, invalid=self.invalid,
                            proposal=None if proposal is None else dict(
                                action=proposal.action_label, rule=proposal.rule_id,
                                condition=proposal.condition, scope=proposal.scope,
                                reason=proposal.reason, refs=proposal.evidence_refs,
                                confidence=proposal.confidence, review=proposal.review_recommended))
            object.__setattr__(self, 'proposal', proposal)
            object.__setattr__(self, 'fingerprint', evidence.digest(identity))
        except Exception:
            raise SyntheticReviewError() from None

    def validate(self):
        checked = SyntheticRecord(self.event_id, self.snapshot, self.projection, self.stamp, self.invalid)
        if self != checked:
            raise SyntheticReviewError()
        return self


def record(event_id, snapshot, fields, stamp=CURRENT_STAMP):
    """Only approved synthetic callers; not a real-data sanitizer or input endpoint."""
    try:
        projection = evidence.CalendarProjection(fields)
    except evidence.CalendarEvidenceError:
        if type(fields) is dict and fields == INVALID_INPUT and type(fields.get('subject')) is int:
            return SyntheticRecord(event_id, snapshot, None, stamp, True)
        raise SyntheticReviewError() from None
    return SyntheticRecord(event_id, snapshot, projection, stamp)


@dataclass(frozen=True)
class Encounter:
    event_id: str
    fingerprint: str
    visit: int
    epoch: int
    disposition: str
    needs_review: bool
    kind: str
    visible: bool = field(default=True, init=False)


@dataclass(frozen=True)
class DecisionRevision:
    revision: int
    fingerprint: str
    epoch: int
    visit: int
    disposition: str
    record: SyntheticRecord = field(repr=False)


class SyntheticReview:
    """Bounded single-threaded simulation; never a shared/client state store."""
    def __init__(self):
        self._current = {}
        self._receipts = {}
        self._history = {}
        self._visits = 0
        self._decisions = 0

    def history(self, event_id):
        if type(event_id) is not str or event_id not in IDS:
            raise SyntheticReviewError()
        return self._history.get(event_id, ())

    def encounter(self, item):
        if type(item) is not SyntheticRecord or self._visits >= MAX_VISITS:
            raise SyntheticReviewError()
        item.validate()
        previous = self._current.get(item.event_id)
        if previous and item.snapshot < previous[0].snapshot:
            raise SyntheticReviewError()
        changed = previous is not None and item.fingerprint != previous[0].fingerprint
        epoch = 1 if previous is None else previous[1] + int(changed)
        history = self.history(item.event_id)
        latest = history[-1] if history else None
        matched = latest is not None and latest.epoch == epoch and latest.fingerprint == item.fingerprint
        disposition = latest.disposition if matched else 'pending'
        reused = previous is not None and not changed and matched and disposition in RESOLVED
        kind = 'initial' if previous is None else 'changed' if changed else 'resolved_repeat' if reused else 'unresolved_repeat'
        receipt = Encounter(item.event_id, item.fingerprint, self._visits + 1, epoch,
                            disposition, not reused, kind)
        self._current[item.event_id] = (item, epoch)
        self._receipts[item.event_id] = receipt
        self._visits += 1
        return receipt

    def decide(self, command):
        """Explicit scripted human intent only; no simulated authentication."""
        try:
            if type(command) is not dict or set(command) != {
                'event_id', 'fingerprint', 'visit', 'expected_revision', 'disposition', 'confirmation'}:
                raise ValueError()
            event_id = command['event_id']
            if type(event_id) is not str or event_id not in IDS or event_id not in self._receipts:
                raise ValueError()
            receipt = self._receipts[event_id]
            history = self.history(event_id)
            if type(command['fingerprint']) is not str or command['fingerprint'] != receipt.fingerprint:
                raise ValueError()
            if not _integer(command['visit'], 1, MAX_VISITS) or command['visit'] != receipt.visit:
                raise ValueError()
            if not _integer(command['expected_revision'], 0, MAX_REVISIONS) or command['expected_revision'] != len(history):
                raise ValueError()
            disposition = command['disposition']
            if type(disposition) is not str or disposition not in DISPOSITIONS or type(command['confirmation']) is not str or command['confirmation'] != 'save':
                raise ValueError()
            if self._decisions >= MAX_REVISIONS:
                raise ValueError()
            item, epoch = self._current[event_id]
            item.validate()
            if disposition in RESOLVED and (item.invalid or item.proposal.action_label == 'uncertain'
                    or item.proposal.reason != 'supported_proposal' or not item.proposal.evidence_refs
                    or item.proposal.scope == 'unresolved'):
                raise ValueError()
            revision = DecisionRevision(len(history) + 1, receipt.fingerprint, epoch,
                                        receipt.visit, disposition, item)
        except Exception:
            raise SyntheticReviewError() from None
        self._history[event_id] = history + (revision,)
        self._decisions += 1
        return revision


@dataclass(frozen=True)
class VisitSpec:
    event_id: str
    snapshot: int
    title: str = field(repr=False)
    expected_prompt: bool
    status: object = None
    stamp: tuple = CURRENT_STAMP
    decision: object = None
    correction: object = None
    invalid: bool = False

    def item(self):
        fields = dict(INVALID_INPUT) if self.invalid else dict(
            provider='google_calendar', record_type='calendar_event', subject=self.title,
            raw_metadata={} if self.status is None else {'status': self.status})
        return record(self.event_id, self.snapshot, fields, self.stamp)


def _v(number, snapshot, title, prompt=True, **kwargs):
    return VisitSpec(IDS[number - 1], snapshot, title, prompt, **kwargs)


# New English design sequences only. No existing fixture is read or modified.
SCENARIOS = (
    ('confirmation_correction', (
        _v(1, 1, 'Outstanding step: request refund', decision='human_confirmed'),
        _v(1, 1, 'Outstanding step: request refund', False, correction='human_rejected'),
        _v(1, 1, 'Outstanding step: request refund', False))),
    ('not_required_needs_explicit_decision', (
        _v(2, 1, 'Completed step: request refund; no further step requested'),
        _v(2, 1, 'Completed step: request refund; no further step requested', decision='human_confirmed'),
        _v(2, 1, 'Completed step: request refund; no further step requested', False))),
    ('uncertain_carryover', (
        _v(3, 1, 'Condition unknown: outstanding step request refund', decision='needs_more_information'),
        _v(3, 1, 'Condition unknown: outstanding step request refund', decision='deferred'),
        _v(3, 1, 'Condition unknown: outstanding step request refund'))),
    ('invalid_carryover', (
        _v(4, 1, '', invalid=True, decision='needs_more_information'),
        _v(4, 1, '', invalid=True, decision='deferred'),
        _v(4, 1, '', invalid=True))),
    ('defer_then_reject', (
        _v(5, 1, 'Outstanding step: request rebooking', decision='deferred'),
        _v(5, 1, 'Outstanding step: request rebooking', decision='human_rejected'),
        _v(5, 1, 'Outstanding step: request rebooking', False))),
    ('exact_evidence_change', (
        _v(6, 1, 'Outstanding step: request refund', decision='human_confirmed'),
        _v(6, 2, 'Outstanding step — request refund.', decision='human_confirmed'),
        _v(6, 2, 'Outstanding step — request refund.', False))),
    ('condition_conflict', (
        _v(7, 1, 'If status is confirmed request refund', status='confirmed', decision='human_confirmed'),
        _v(7, 2, 'If status is confirmed request refund', status='cancelled', decision='human_confirmed'),
        _v(7, 3, 'Event cancelled: outstanding step request refund', status='confirmed', decision='needs_more_information'),
        _v(7, 3, 'Event cancelled: outstanding step request refund', status='confirmed'))),
    ('refund_rebooking_scope', (
        _v(8, 1, 'Event cancelled: outstanding step request refund', status='cancelled', decision='human_confirmed'),
        _v(8, 2, 'Event cancelled: outstanding step request rebooking', status='cancelled', decision='human_rejected'),
        _v(8, 2, 'Event cancelled: outstanding step request rebooking', False, status='cancelled'))),
    ('partial_step_completion', (
        _v(9, 1, 'Completed step: request refund; no further step requested', decision='human_confirmed'),
        _v(9, 2, 'Outstanding step: request rebooking'),
        _v(9, 2, 'Outstanding step: request rebooking'))),
    ('rule_and_analyzer_invalidation', (
        _v(10, 1, 'Outstanding step: request refund', decision='human_confirmed'),
        _v(10, 1, 'Outstanding step: request refund', stamp=RULE_PROBE_STAMP, decision='human_confirmed'),
        _v(10, 1, 'Outstanding step: request refund', stamp=ANALYZER_PROBE_STAMP, decision='needs_more_information'),
        _v(10, 1, 'Outstanding step: request refund', stamp=ANALYZER_PROBE_STAMP))),
    ('distinct_events_same_words', (
        _v(11, 1, 'Outstanding step: request refund', decision='human_confirmed'),
        _v(12, 1, 'Outstanding step: request refund'),
        _v(11, 1, 'Outstanding step: request refund', False),
        _v(12, 1, 'Outstanding step: request refund'))),
    ('schema_invalidation', (
        _v(13, 1, 'Outstanding step: request refund', decision='human_confirmed'),
        _v(13, 1, 'Outstanding step: request refund', stamp=SCHEMA_PROBE_STAMP, decision='deferred'),
        _v(13, 1, 'Outstanding step: request refund', stamp=SCHEMA_PROBE_STAMP))),
)


def _scenario_digest():
    return evidence.digest(dict(version=SCENARIO_VERSION, scenarios=[
        dict(name=name, visits=[dict(event_id=v.event_id, snapshot=v.snapshot,
            title=v.title, expected_prompt=v.expected_prompt, status=v.status,
            stamp=v.stamp, decision=v.decision, correction=v.correction, invalid=v.invalid)
            for v in visits]) for name, visits in SCENARIOS]))


SCENARIO_FINGERPRINT = 'bfccc2cd7512d3b16d96cbc0b3a0bdce0bbe672c3f76f0e1c0a901026adbb059'


def _command(receipt, revision, disposition):
    return dict(event_id=receipt.event_id, fingerprint=receipt.fingerprint,
                visit=receipt.visit, expected_revision=revision,
                disposition=disposition, confirmation='save')


def report():
    if _scenario_digest() != SCENARIO_FINGERPRINT:
        raise SyntheticReviewError()
    counts = dict(visits=0, initial_reviews=0, repeat_proposals=0,
                  unchanged_resolved_repeats=0, changed_evidence_rereviews=0,
                  unresolved_carryovers=0, review_prompts=0, explicit_decisions=0,
                  corrections=0, unsupported_transitions=0, wrong_reuse=0,
                  silent_suppression=0, invalid_visits=0, uncertain_visits=0)
    initial_suggestions = dict.fromkeys((*evidence.ACTIONS, 'invalid'), 0)
    for _, visits in SCENARIOS:
        state = SyntheticReview()
        for spec in visits:
            item = spec.item()
            receipt = state.encounter(item)
            counts['visits'] += 1
            counts['initial_reviews'] += receipt.kind == 'initial'
            if receipt.kind == 'initial':
                initial_suggestions['invalid' if item.invalid else item.proposal.action_label] += 1
            counts['repeat_proposals'] += receipt.kind != 'initial'
            counts['unchanged_resolved_repeats'] += receipt.kind == 'resolved_repeat'
            counts['changed_evidence_rereviews'] += receipt.kind == 'changed'
            counts['unresolved_carryovers'] += receipt.kind == 'unresolved_repeat'
            counts['review_prompts'] += receipt.needs_review
            counts['wrong_reuse'] += spec.expected_prompt and not receipt.needs_review
            counts['silent_suppression'] += not receipt.visible
            counts['invalid_visits'] += item.invalid
            counts['uncertain_visits'] += not item.invalid and item.proposal.action_label == 'uncertain'
            for disposition in (spec.decision, spec.correction):
                if disposition is not None:
                    state.decide(_command(receipt, len(state.history(item.event_id)), disposition))
                    counts['explicit_decisions'] += 1
            counts['corrections'] += spec.correction is not None
            # All attempts to bypass explicit save must be rejected atomically.
            before = state.history(item.event_id)
            try:
                state.decide(dict(_command(receipt, len(before), 'human_confirmed'), confirmation='auto'))
            except SyntheticReviewError:
                counts['unsupported_transitions'] += 1
            else:
                counts['silent_suppression'] += 1
            if state.history(item.event_id) != before:
                counts['silent_suppression'] += 1
    total = counts['visits']
    return dict(synthetic_only=True, contract_version=CONTRACT_VERSION,
                scenario_version=SCENARIO_VERSION, scenario_fingerprint=SCENARIO_FINGERPRINT,
                policy_fingerprint=POLICY_FINGERPRINT, scenario_count=len(SCENARIOS),
                counts=counts, baseline_review_prompts=total,
                initial_suggestions=initial_suggestions,
                baseline_scripted_decisions=total,
                review_prompt_rate=counts['review_prompts'] / total if total else None,
                explicit_decision_rate=counts['explicit_decisions'] / total if total else None,
                inspection_visits=total, inspection_rate=1.0 if total else None,
                exit_decision='stop_abstain' if counts['wrong_reuse'] or counts['silent_suppression']
                else 'continue_isolated_synthetic_research_only')


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SyntheticReviewError()


def main(argv=None):
    try:
        parser = _Parser(description='Aggregate-only fixed synthetic review simulation')
        parser.add_argument('--simulate', action='store_true', required=True)
        parser.parse_args(argv)
        result = report()
        print(json.dumps(result, allow_nan=False, sort_keys=True))
        return int(result['exit_decision'] == 'stop_abstain')
    except KeyboardInterrupt:
        print('Synthetic review interrupted; no state persisted')
        return 130
    except Exception:
        print('Synthetic review failed; no state persisted')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
