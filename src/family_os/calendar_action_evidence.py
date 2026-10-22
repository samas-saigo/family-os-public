"""Pure, synthetic-only Calendar proposals; no model, provider, DB or I/O.

Full-title grammar is an auditable research vocabulary, not a production classifier.
All results require human review and have no action/eligibility/execution authority.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from hashlib import sha256
import json
import re
from types import MappingProxyType
import unicodedata
from urllib.parse import unquote

ENGINE_VERSION = 'calendar-evidence-e2'
INPUT_SCHEMA = 'synthetic-calendar-metadata-v1'
INPUT_BYTES = 4096
ACTIONS = ('required', 'not_required', 'uncertain')
STEPS = ('provide access at the scheduled time', 'bring the driving licence',
         'bring the vaccination booklet', 'bring the current allergy chart',
         'request refund', 'request rebooking')
CONDITIONAL_PAIRS = (
    ('household boiler visit', STEPS[0]), ('family rental car pickup', STEPS[1]),
    ('pet vaccination visit', STEPS[2]))
INDICATOR_TOKENS = ('bring', 'provide', 'outstanding', 'refund', 'rebooking',
                    'completed', 'cancelled', 'prepare')
MONTHS = ('january', 'february', 'march', 'april', 'may', 'june', 'july',
          'august', 'september', 'october', 'november', 'december')
DATE_PATTERN = r'([0-9]{1,2}) (' + '|'.join(MONTHS) + r') (20[0-9]{2})'
RULES = (
    ('conditional-preparation-v1', 'if this EVENT is confirmed STEP do not prepare while status is tentative'),
    ('status-condition-v1', 'if status is confirmed STEP'),
    ('booked-preparation-v1', 'your pet consultation is booked bring the current allergy chart on DATE'),
    ('completed-visit-v1', 'pet consultation completed on DATE visit record only no follow up requested'),
    ('outstanding-step-v1', 'outstanding step STEP / condition met outstanding step STEP'),
    ('no-step-v1', 'completed step STEP no further step requested / cancelled step STEP no replacement step requested / do not STEP no further step requested'),
    ('unmet-step-v1', 'condition unmet step STEP not requested'),
    ('unknown-step-v1', 'condition unknown outstanding step STEP / superseded step STEP replacement step unknown'),
    ('cancelled-followup-v1', 'event cancelled outstanding step request refund / request rebooking'),
    ('abstain-v1', 'all unsupported, missing, conflicting or unresolved evidence'))
CONDITIONS = ('confirmed_condition_met', 'confirmed_condition_unmet_cancelled',
              'condition_unresolved', 'explicit_booked_instruction', 'explicit_completed_visit',
              'explicit_outstanding', 'explicit_condition_met', 'explicit_no_step',
              'explicit_condition_unmet', 'explicit_replacement_unknown',
              'explicit_cancelled_followup', 'conflicting_status', 'unsupported', 'missing')
SCOPES = ('conditional_preparation', 'explicit_preparation', 'completed_visit',
          'named_step', 'refund', 'rebooking', 'unresolved')
REASONS = ('supported_proposal', 'unresolved_condition', 'unknown_replacement',
           'conflicting_evidence', 'unsupported_evidence', 'missing_evidence')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


RULE_FINGERPRINT = digest(dict(engine=ENGINE_VERSION, schema=INPUT_SCHEMA,
    rules=RULES, steps=STEPS, conditional_pairs=CONDITIONAL_PAIRS, months=MONTHS,
    conditions=CONDITIONS, scopes=SCOPES, reasons=REASONS,
    normalization='NFKC-casefold-punctuation-separated-ascii-words-v1',
    ambiguity='abstain-before-token-matching; original-or-NFKC Unicode QUESTION+MARK/INTERROBANG-v1',
    bounds=dict(bytes=INPUT_BYTES, subject=600, metadata_text=256, timestamp=32),
    policy='full-match-only; zero-confidence; human-review-all; no-authority-v1'))
EFFECTIVE_VERSION = ENGINE_VERSION + '-' + RULE_FINGERPRINT[:16]
INDICATOR_FINGERPRINT = digest(dict(version='inspection-indicator-v1', tokens=INDICATOR_TOKENS,
    statuses=('confirmed', 'cancelled', 'tentative'), policy='priority-only-no-action; human-review-all'))


class CalendarEvidenceError(ValueError):
    def __init__(self):
        super().__init__('Synthetic Calendar evidence rejected; no action accepted')


def _text(value, limit):
    if type(value) is not str or len(value) > limit or '\x00' in value:
        raise ValueError()
    value.encode('utf-8', errors='strict')
    checked = value
    for _ in range(3):
        checked = unicodedata.normalize('NFKC', unquote(checked)).casefold()
    if re.search(r'(?:https?|ftp|file|data)\s*:|www\.|bearer\s|(?:password|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]', checked):
        raise ValueError()
    return value


def normalize(text):
    # No locale, substring, arbitrary configured regex or ID-based matching.
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


def _has_question_mark(text):
    # Inspect original characters too: e.g. Greek QUESTION MARK becomes an ordinary
    # semicolon under NFKC. Declarative semicolons must remain supported.
    for char in text + unicodedata.normalize('NFKC', text):
        name = unicodedata.name(char, '')
        if ('QUESTION' in name and 'MARK' in name) or 'INTERROBANG' in name:
            return True
    return False


@dataclass(frozen=True)
class CalendarProjection:
    fields: Mapping = field(repr=False)

    def __post_init__(self):
        try:
            source = self.fields
            if type(source) is not dict or not {'provider', 'record_type'} <= set(source) or not set(source) <= {'provider', 'record_type', 'subject', 'occurred_at', 'raw_metadata'}:
                raise ValueError()
            if source['provider'] != 'google_calendar' or source['record_type'] != 'calendar_event':
                raise ValueError()
            result = dict(source)
            if 'subject' in result:
                _text(result['subject'], 600)
            if 'occurred_at' in result:
                _text(result['occurred_at'], 32)
                if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{6})?Z', result['occurred_at']):
                    raise ValueError()
                datetime.fromisoformat(result['occurred_at'])
            metadata = result.get('raw_metadata', {})
            if type(metadata) is not dict or not set(metadata) <= {'status', 'eventType', 'start', 'end'}:
                raise ValueError()
            copied = {}
            for key in ('status', 'eventType'):
                if key in metadata:
                    copied[key] = _text(metadata[key], 256)
            for key in ('start', 'end'):
                if key in metadata:
                    child = metadata[key]
                    if type(child) is not dict or not set(child) <= {'date', 'dateTime'} or len(child) != 1:
                        raise ValueError()
                    copied[key] = dict(child)
                    for name, value in child.items():
                        _text(value, 256)
                        if name == 'date':
                            if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', value):
                                raise ValueError()
                            date.fromisoformat(value)
                        else:
                            if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})', value):
                                raise ValueError()
                            if datetime.fromisoformat(value).utcoffset() is None:
                                raise ValueError()
            if 'raw_metadata' in result:
                result['raw_metadata'] = copied
            if len(canonical(result).encode('utf-8')) > INPUT_BYTES:
                raise ValueError()
            for key in ('start', 'end'):
                if key in copied:
                    copied[key] = MappingProxyType(copied[key])
            if 'raw_metadata' in result:
                result['raw_metadata'] = MappingProxyType(copied)
            object.__setattr__(self, 'fields', MappingProxyType(result))
        except Exception:
            raise CalendarEvidenceError() from None


@dataclass(frozen=True)
class ActionProposal:
    action_label: str
    rule_id: str
    condition: str
    scope: str
    reason: str
    evidence_refs: tuple
    review_recommended: bool = field(default=True, init=False)
    confidence: float = field(default=0.0, init=False)

    def __post_init__(self):
        if any(type(value) is not str for value in (self.action_label, self.rule_id, self.condition, self.scope, self.reason)) or self.action_label not in ACTIONS or self.rule_id not in dict(RULES) or self.condition not in CONDITIONS or self.scope not in SCOPES or self.reason not in REASONS or type(self.evidence_refs) is not tuple or len(self.evidence_refs) > 2 or any(type(ref) is not str or ref not in ('subject', 'raw_metadata.status') for ref in self.evidence_refs) or len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise CalendarEvidenceError()


@dataclass(frozen=True)
class InspectionIndicator:
    priority: bool
    evidence_refs: tuple
    rule_id: str = field(default='inspection-indicator-v1', init=False)
    human_review_required: bool = field(default=True, init=False)


def _require_projection(projection):
    if type(projection) is not CalendarProjection:
        raise CalendarEvidenceError()


def indicator(projection):
    _require_projection(projection)
    fields = projection.fields
    refs = []
    if set(normalize(fields.get('subject', '')).split()) & set(INDICATOR_TOKENS):
        refs.append('subject')
    if fields.get('raw_metadata', {}).get('status') in ('confirmed', 'cancelled', 'tentative'):
        refs.append('raw_metadata.status')
    return InspectionIndicator(bool(refs), tuple(refs))


def _interpret(projection):
    _require_projection(projection)
    fields = projection.fields
    raw_text = fields.get('subject', '')
    questioned = _has_question_mark(raw_text)
    text = normalize(raw_text)
    status = fields.get('raw_metadata', {}).get('status')
    refs = ('subject',) if text else ()
    def proposal(action, rule, condition, scope='named_step', reason='supported_proposal', evidence=refs):
        return ActionProposal(action, rule, condition, scope, reason, evidence)
    def conditional(rule):
        evidence = refs + (('raw_metadata.status',) if status else ())
        if status == 'confirmed':
            return proposal('required', rule, 'confirmed_condition_met', 'conditional_preparation', evidence=evidence)
        if status == 'cancelled':
            return proposal('not_required', rule, 'confirmed_condition_unmet_cancelled', 'conditional_preparation', evidence=evidence)
        return proposal('uncertain', rule, 'condition_unresolved', 'conditional_preparation', 'unresolved_condition', evidence)
    if questioned:
        return proposal('uncertain', 'abstain-v1', 'unsupported', 'unresolved', 'unsupported_evidence')
    if any(char in unicodedata.normalize('NFKC', raw_text) for char in ('"', "'", '`', '“', '”', '‘', '’', '\n', '\r', '\t')):
        return proposal('uncertain', 'abstain-v1', 'unsupported', 'unresolved', 'unsupported_evidence')
    for event, step in CONDITIONAL_PAIRS:
        if text == f'if this {event} is confirmed {step} do not prepare while status is tentative':
            return conditional('conditional-preparation-v1')
    for step in STEPS:
        if text == f'if status is confirmed {step}':
            return conditional('status-condition-v1')
        if text in (f'outstanding step {step}', f'condition met outstanding step {step}'):
            condition = 'explicit_condition_met' if text.startswith('condition') else 'explicit_outstanding'
            return proposal('required', 'outstanding-step-v1', condition)
        if text in (f'completed step {step} no further step requested',
                    f'cancelled step {step} no replacement step requested',
                    f'do not {step} no further step requested'):
            return proposal('not_required', 'no-step-v1', 'explicit_no_step')
        if text == f'condition unmet step {step} not requested':
            return proposal('not_required', 'unmet-step-v1', 'explicit_condition_unmet')
        if text == f'condition unknown outstanding step {step}':
            return proposal('uncertain', 'unknown-step-v1', 'condition_unresolved', reason='unresolved_condition')
        if text == f'superseded step {step} replacement step unknown':
            return proposal('uncertain', 'unknown-step-v1', 'explicit_replacement_unknown', reason='unknown_replacement')
    for step in ('refund', 'rebooking'):
        if text == f'event cancelled outstanding step request {step}':
            evidence = refs + (('raw_metadata.status',) if status else ())
            if status in ('confirmed', 'tentative'):
                return proposal('uncertain', 'cancelled-followup-v1', 'conflicting_status', step, 'conflicting_evidence', evidence)
            return proposal('required', 'cancelled-followup-v1', 'explicit_cancelled_followup', step, evidence=evidence)
    for pattern, action, rule, condition, scope in (
        ('your pet consultation is booked bring the current allergy chart on ' + DATE_PATTERN,
         'required', 'booked-preparation-v1', 'explicit_booked_instruction', 'explicit_preparation'),
        ('pet consultation completed on ' + DATE_PATTERN + ' visit record only no follow up requested',
         'not_required', 'completed-visit-v1', 'explicit_completed_visit', 'completed_visit')):
        match = re.fullmatch(pattern, text)
        if match:
            try:
                date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1]))
            except ValueError:
                break
            if rule == 'booked-preparation-v1' and status in ('cancelled', 'tentative'):
                return proposal('uncertain', rule, 'conflicting_status', scope, 'conflicting_evidence', refs + ('raw_metadata.status',))
            return proposal(action, rule, condition, scope)
    conflicting = ('outstanding step' in text and ('completed step' in text or 'do not' in text))
    return proposal('uncertain', 'abstain-v1', 'unsupported' if text else 'missing',
        'unresolved', 'conflicting_evidence' if conflicting else 'unsupported_evidence' if text else 'missing_evidence')


def interpret(projection):
    """Opt-in synthetic proposal, independent of all production classifications."""
    return _interpret(projection)


def validate_proposal(projection, proposal):
    """Evidence must resolve; concrete output must replay the frozen supported grammar."""
    _require_projection(projection)
    if type(proposal) is not ActionProposal or proposal.review_recommended is not True or type(proposal.confidence) is not float or proposal.confidence != 0.0:
        raise CalendarEvidenceError()
    for ref in proposal.evidence_refs:
        value = projection.fields
        for part in ref.split('.'):
            if not isinstance(value, Mapping) or part not in value:
                raise CalendarEvidenceError()
            value = value[part]
        if type(value) is not str or not value:
            raise CalendarEvidenceError()
    if proposal != _interpret(projection):
        raise CalendarEvidenceError()
    return proposal
