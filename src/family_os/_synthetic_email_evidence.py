"""Isolated synthetic email evidence; preregistered grammar, never action authority."""
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from hashlib import sha256
import json
import re
from types import MappingProxyType
import unicodedata
from urllib.parse import unquote


RULES = (('invoice-paid',
  'Invoice paid',
  'explicit_completion',
  (('invoice_payment', 'reported_completed'),),
  None,
  None),
 ('invoice-unpaid',
  'Invoice unpaid',
  'explicit_outstanding',
  (('invoice_payment', 'reported_outstanding'),),
  None,
  None),
 ('payment-required',
  'Payment required',
  'explicit_outstanding',
  (('invoice_payment', 'reported_outstanding'),),
  None,
  None),
 ('autopay-success',
  'Autopay successful',
  'explicit_completion',
  (('invoice_payment', 'reported_completed'),),
  None,
  None),
 ('autopay-failed', 'Autopay failed', 'informational', (('invoice_payment', 'reported_failed'),), None, None),
 ('autopay-remedy',
  'Autopay failed; contact billing to arrange payment',
  'explicit_outstanding',
  (('invoice_payment', 'reported_failed'), ('contact_biller', 'reported_outstanding')),
  None,
  None),
 ('bill-ready', 'Bill available', 'informational', (), None, None),
 ('payment-due-date',
  'Invoice payment due on DATE',
  'explicit_outstanding',
  (('invoice_payment', 'reported_outstanding'),),
  'due_date',
  'invoice_payment'),
 ('payment-available-date', 'Invoice payment available on DATE', 'informational', (), 'available_date', None),
 ('renewal-due',
  'Membership renewal due on DATE',
  'explicit_outstanding',
  (('renew_membership', 'reported_outstanding'),),
  'due_date',
  'renew_membership'),
 ('renewal-complete',
  'Membership renewed on DATE',
  'explicit_completion',
  (('renew_membership', 'reported_completed'),),
  'reported_completion_date',
  'renew_membership'),
 ('visit-confirmed', 'Visit confirmed for DATE', 'informational', (), 'event_date', None),
 ('visit-cancelled',
  'Visit cancelled for DATE',
  'informational',
  (('attend_visit', 'reported_cancelled'),),
  'event_date',
  None),
 ('cancel-refund',
  'Visit cancelled; request refund',
  'explicit_outstanding',
  (('attend_visit', 'reported_cancelled'), ('request_refund', 'reported_outstanding')),
  None,
  None),
 ('cancel-refund-date',
  'Visit cancelled; request refund by DATE',
  'explicit_outstanding',
  (('attend_visit', 'reported_cancelled'), ('request_refund', 'reported_outstanding')),
  'due_date',
  'request_refund'),
 ('cancel-reschedule',
  'Visit cancelled; reschedule visit by DATE',
  'explicit_outstanding',
  (('attend_visit', 'reported_cancelled'), ('reschedule_visit', 'reported_outstanding')),
  'due_date',
  'reschedule_visit'),
 ('form-complete',
  'Service form completed',
  'explicit_completion',
  (('return_form', 'reported_completed'),),
  None,
  None),
 ('form-failed', 'Service form failed', 'informational', (('return_form', 'reported_failed'),), None, None),
 ('payment-and-form',
  'Payment completed; return the service form',
  'explicit_outstanding',
  (('invoice_payment', 'reported_completed'), ('return_form', 'reported_outstanding')),
  None,
  None),
 ('offer-expiry', 'Offer available; offer expires on DATE', 'promotional', (), 'offer_expiry', None))
_CONTRACT_BASE_JSON = '{"engine":"synthetic-email-evidence-e1","guards":["validate-before-interpret","reject-controls-URLs-credentials-HTML-contact-addresses","full-title-only","question-quote-negation-conflict-abstain","service-context-required","no-authority-no-clearance","dates-explicit-ISO-2015-2035-no-clock"],"input_schema":"synthetic-email-metadata-v1","max_input_bytes":2048,"max_subject_chars":360,"normalization":"NFKC security scan; original-and-normalized Unicode-question scan; non-ASCII abstain; ASCII casefold; collapse spaces; one terminal period only; preserve semicolon and date punctuation","notice_kinds":["service","promotional","unknown"],"providers":["gmail","outlook"],"record_type":"message","version":"synthetic-email-evidence-v1"}'



class State(StrEnum):
    OUTSTANDING = 'explicit_outstanding'
    COMPLETION = 'explicit_completion'
    INFORMATION = 'informational'
    PROMOTION = 'promotional'
    ABSTAIN = 'abstain'


class Action(StrEnum):
    PAYMENT = 'invoice_payment'
    CONTACT = 'contact_biller'
    RENEW = 'renew_membership'
    ATTEND = 'attend_visit'
    REFUND = 'request_refund'
    RESCHEDULE = 'reschedule_visit'
    FORM = 'return_form'


class Status(StrEnum):
    OUTSTANDING = 'reported_outstanding'
    COMPLETED = 'reported_completed'
    FAILED = 'reported_failed'
    CANCELLED = 'reported_cancelled'


class DateRole(StrEnum):
    DUE = 'due_date'
    EVENT = 'event_date'
    AVAILABLE = 'available_date'
    OFFER = 'offer_expiry'
    COMPLETION = 'reported_completion_date'


class Reason(StrEnum):
    SUPPORTED = 'supported'
    MISSING = 'missing'
    QUESTIONED = 'questioned'
    QUOTED = 'quoted'
    UNICODE = 'unsupported_unicode'
    NEGATED = 'negated'
    CONFLICTING = 'conflicting'
    UNKNOWN_CONTEXT = 'unknown_context'
    CONTEXT_CONFLICT = 'context_conflict'
    INCOMPLETE_DATE = 'incomplete_date'
    INVALID_DATE = 'invalid_date'
    UNSUPPORTED = 'unsupported'


CONFLICTS = ('invoice paid; payment required', 'invoice unpaid; payment complete',
             'payment completed; payment failed')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


def contract_description():
    # A detached value; mutation cannot change the interpreter grammar.
    return dict(json.loads(_CONTRACT_BASE_JSON), rules=json.loads(canonical(RULES)))


RULE_FINGERPRINT = digest(dict(contract=contract_description(), conflicts=CONFLICTS,
    enums={name: tuple(v.value for v in kind) for name, kind in
           (('state', State), ('action', Action), ('status', Status), ('date_role', DateRole), ('reason', Reason))},
    output='immutable-named-step-claims-only; no-authority; independent-safety-and-human-review-v1'))
VERSION = 'synthetic-email-evidence-e1-' + RULE_FINGERPRINT[:16]


class EmailEvidenceError(ValueError):
    reason = 'contract_rejected'

    def __init__(self):
        super().__init__('Synthetic email evidence rejected; no result or authority granted')


def require(condition):
    if not condition:
        raise EmailEvidenceError()


def _safe_subject(value):
    require(type(value) is str and len(value) <= 360)
    value.encode('utf-8', errors='strict')
    require(not any(unicodedata.category(ch).startswith('C') for ch in value))
    inspected = value
    for _ in range(3):
        inspected = unicodedata.normalize('NFKC', unquote(inspected)).casefold()
        require(not any(unicodedata.category(ch).startswith('C') for ch in inspected))
    require(not re.search(r'[a-z][a-z0-9+.-]{1,31}\s*://|(?:https?|ftp|file|data|javascript|mailto|tel|ssh|smb|wss?)\s*:|www\.|bearer\s|(?:password|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]|[<>@]', inspected))


@dataclass(frozen=True)
class EmailMetadata:
    fields: object = field(repr=False)

    def __post_init__(self):
        try:
            v = self.fields
            require(type(v) is dict and 5 <= len(v) <= 6)
            required = {'synthetic_only', 'schema', 'provider', 'record_type', 'notice_kind'}
            require(required <= set(v) <= required | {'subject'})
            require(v['synthetic_only'] is True)
            require(type(v['schema']) is str and v['schema'] == 'synthetic-email-metadata-v1')
            require(type(v['provider']) is str and v['provider'] in ('gmail', 'outlook'))
            require(type(v['record_type']) is str and v['record_type'] == 'message')
            require(type(v['notice_kind']) is str and v['notice_kind'] in ('service', 'promotional', 'unknown'))
            if 'subject' in v:
                _safe_subject(v['subject'])
            require(len(canonical(v).encode('utf-8')) <= 2048)
            object.__setattr__(self, 'fields', MappingProxyType(dict(v)))
        except Exception:
            raise EmailEvidenceError() from None

    @property
    def fingerprint(self):
        return digest(dict(self.fields))


def _date(value):
    require(type(value) is str and bool(re.fullmatch(r'20[0-9]{2}-[0-9]{2}-[0-9]{2}', value)))
    parsed = date.fromisoformat(value)
    require(2015 <= parsed.year <= 2035)
    return value


@dataclass(frozen=True)
class StepEvidence:
    action: Action
    status: Status

    def __post_init__(self):
        require(type(self.action) is Action and type(self.status) is Status)


@dataclass(frozen=True)
class DateEvidence:
    role: DateRole
    value: str
    action: Action | None

    def __post_init__(self):
        try:
            require(type(self.role) is DateRole and (self.action is None or type(self.action) is Action))
            _date(self.value)
            require((self.action is not None) == (self.role in (DateRole.DUE, DateRole.COMPLETION)))
        except Exception:
            raise EmailEvidenceError() from None


@dataclass(frozen=True)
class Evidence:
    state: State
    steps: tuple[StepEvidence, ...]
    dates: tuple[DateEvidence, ...]
    reason: Reason
    rule_id: str
    evidence_refs: tuple[str, ...]
    input_fingerprint: str
    interpreter_version: str = field(default=VERSION, init=False)
    rule_fingerprint: str = field(default=RULE_FINGERPRINT, init=False)
    authority: str = field(default='none', init=False)
    human_review_required: bool = field(default=True, init=False)
    independent_safety_and_authorization_required: bool = field(default=True, init=False)
    sender_claim_only: bool = field(default=True, init=False)

    def __post_init__(self):
        require(type(self.state) is State and type(self.reason) is Reason)
        require(type(self.steps) is tuple and len(self.steps) <= 2 and all(type(s) is StepEvidence for s in self.steps))
        for s in self.steps: s.__post_init__()
        require(len({s.action for s in self.steps}) == len(self.steps))
        require(type(self.dates) is tuple and len(self.dates) <= 1 and all(type(d) is DateEvidence for d in self.dates))
        for d in self.dates: d.__post_init__()
        require(type(self.rule_id) is str and self.rule_id in {r[0] for r in RULES} | {'abstain-v1'})
        require(type(self.input_fingerprint) is str and bool(re.fullmatch('[0-9a-f]{64}', self.input_fingerprint)))
        require(type(self.evidence_refs) is tuple and len(self.evidence_refs) <= 2)
        require(all(type(ref) is str and ref in ('subject', 'notice_kind') for ref in self.evidence_refs))
        require(len(set(self.evidence_refs)) == len(self.evidence_refs))
        if self.state is State.ABSTAIN:
            require(not self.steps and not self.dates and self.reason is not Reason.SUPPORTED and self.rule_id == 'abstain-v1')
            return
        require(self.reason is Reason.SUPPORTED and set(self.evidence_refs) == {'subject', 'notice_kind'})
        if self.state is State.OUTSTANDING:
            require(any(s.status is Status.OUTSTANDING for s in self.steps))
        elif self.state is State.COMPLETION:
            require(bool(self.steps) and all(s.status is Status.COMPLETED for s in self.steps))
        elif self.state is State.INFORMATION:
            require(all(s.status in (Status.FAILED, Status.CANCELLED) for s in self.steps))
        elif self.state is State.PROMOTION:
            require(not self.steps)
        for d in self.dates:
            if d.role is DateRole.DUE:
                require(self.state is State.OUTSTANDING and any(s.action is d.action and s.status is Status.OUTSTANDING for s in self.steps))
            elif d.role is DateRole.COMPLETION:
                require(self.state is State.COMPLETION and any(s.action is d.action and s.status is Status.COMPLETED for s in self.steps))
            elif d.role is DateRole.OFFER:
                require(self.state is State.PROMOTION)
            else:
                require(self.state is State.INFORMATION)


def _questioned(value):
    return any(('QUESTION' in unicodedata.name(c, '') and 'MARK' in unicodedata.name(c, '')) or
               'INTERROBANG' in unicodedata.name(c, '') for c in value + unicodedata.normalize('NFKC', value))


def interpret(projection):
    require(type(projection) is EmailMetadata)
    raw = projection.fields.get('subject', '')
    refs = ('subject',) if raw else ()
    def abstain(reason):
        evidence = refs + (('notice_kind',) if reason in (Reason.UNKNOWN_CONTEXT, Reason.CONTEXT_CONFLICT) else ())
        return Evidence(State.ABSTAIN, (), (), reason, 'abstain-v1', evidence, projection.fingerprint)
    if not raw.strip(): return abstain(Reason.MISSING)
    if _questioned(raw): return abstain(Reason.QUESTIONED)
    if any(c in raw for c in ('"', "'", '`', '“', '”', '‘', '’')): return abstain(Reason.QUOTED)
    if any(ord(c) > 127 for c in raw): return abstain(Reason.UNICODE)
    text = ' '.join(raw.casefold().split())
    if text.endswith('.'): text = text[:-1]
    if {'not', 'no', 'never'} & set(re.findall('[a-z]+', text)): return abstain(Reason.NEGATED)
    if text in CONFLICTS: return abstain(Reason.CONFLICTING)
    for rule_id, template, state, steps, role, action in RULES:
        pattern = re.escape(template.casefold()).replace('date', r'(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})') if 'DATE' in template else re.escape(template.casefold())
        match = re.fullmatch(pattern, text)
        if not match:
            continue
        context = projection.fields['notice_kind']
        if context == 'unknown': return abstain(Reason.UNKNOWN_CONTEXT)
        if context != ('promotional' if state == 'promotional' else 'service'):
            return abstain(Reason.CONTEXT_CONFLICT)
        dates = ()
        if role:
            try:
                value = _date(match['date'])
            except (EmailEvidenceError, ValueError):
                return abstain(Reason.INVALID_DATE)
            dates = (DateEvidence(DateRole(role), value, Action(action) if action else None),)
        return Evidence(State(state), tuple(StepEvidence(Action(a), Status(s)) for a, s in steps), dates,
                        Reason.SUPPORTED, rule_id, ('subject', 'notice_kind'), projection.fingerprint)
    if any(text.startswith(template.casefold().split('date')[0]) for _, template, _, _, _, _ in RULES if 'DATE' in template):
        return abstain(Reason.INCOMPLETE_DATE)
    return abstain(Reason.UNSUPPORTED)


def validate_result(result, projection):
    """Structural/provenance validation, never a substitute for semantic scoring."""
    require(type(projection) is EmailMetadata and type(result) is Evidence)
    result.__post_init__()
    require(result.input_fingerprint == projection.fingerprint)
    require(result.interpreter_version == VERSION and result.rule_fingerprint == RULE_FINGERPRINT)
    require(result.authority == 'none' and result.human_review_required is True and
            result.independent_safety_and_authorization_required is True and result.sender_claim_only is True)
    require(all(ref in projection.fields for ref in result.evidence_refs))
    return result
