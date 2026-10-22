"""Local confirmed evaluation workflow; no terminal, providers, OAuth or network."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
import re

from sqlalchemy import select, func, and_, exists
from sqlalchemy.exc import IntegrityError, OperationalError

from .analysis import (AnalysisError, AnalysisValidationError, AnalysisNotFoundError,
                       AnalysisPersistenceError, StaleAnalysisInputError, freeze_json, validate_output)
from .analysis_services import _prepare_analysis, _persist_analysis, _check_definition, _matching
from .audit_services import (_snapshot, _household, _current_query, _display, _bounded_text,
                             _append_label, EvaluationRevisionConflictError)
from .audit import validate_labels
from .coverage_services import _config, _input
from .schema import source_record as sources, source_account as accounts, source_analysis, analysis_evaluation_label as labels

PROVIDERS = ('gmail', 'outlook', 'google_calendar', 'google_drive')


class ReviewChangedError(AnalysisError):
    def __init__(self):
        super().__init__('Source snapshot or classifier definition changed; restart review to refresh')


@dataclass(frozen=True)
class ReviewTicket:
    household_id: str
    source_record_id: str
    raw_record_id: str
    input_fingerprint: str
    definition: object


@dataclass(frozen=True)
class ReviewItem:
    ticket: ReviewTicket = field(repr=False)
    provider: str
    record_type: str
    occurred_at: str
    subject: str | None = field(repr=False)
    sender: str | None = field(repr=False)
    display_metadata: object = field(repr=False)
    prediction: object
    prediction_origin: str
    latest_human_revision: int | None
    human_labels: object | None


@dataclass(frozen=True)
class ReviewSelection:
    definition: object
    categories: object
    since: str
    until: str
    items: tuple[ReviewItem, ...] = field(repr=False)


def _date(value):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise AnalysisValidationError()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AnalysisValidationError() from None


def select_review(engine, household_id, *, since, until=None, limit=15, provider=None,
                  include_labeled=False, classification_path='config/classification.yaml',
                  rules_path='config/metadata-classifier.yaml'):
    if type(limit) is not int or not 1 <= limit <= 50 or type(include_labeled) is not bool:
        raise AnalysisValidationError()
    if provider is not None and (type(provider) is not str or provider not in PROVIDERS):
        raise AnalysisValidationError()
    start = _date(since)
    end = _date(until) if until is not None else datetime.now(timezone.utc).date() + timedelta(days=1)
    if start >= end:
        raise AnalysisValidationError()
    start_time, end_time = (datetime.combine(value, time.min, timezone.utc) for value in (start, end))
    policy, analyzer, definition, fingerprint = _config(classification_path, rules_path)
    declared = definition | {'definition_fingerprint': fingerprint, 'rules_fingerprint': analyzer.ruleset.fingerprint}
    with _snapshot(engine) as connection:
        _household(connection, household_id)
        _check_definition(connection, household_id, definition, fingerprint)
        conditions = [sources.c.household_id == household_id, sources.c.occurred_at >= start_time,
                      sources.c.occurred_at < end_time]
        if provider is not None:
            conditions.append(accounts.c.provider == provider)
        if not include_labeled:
            labeled = select(source_analysis.c.id).join(labels, and_(labels.c.analysis_id == source_analysis.c.id,
                labels.c.household_id == household_id)).where(source_analysis.c.household_id == household_id,
                source_analysis.c.definition_fingerprint == fingerprint,
                *_matching(sources.c.id, sources.c.raw_record_id, definition))
            conditions.append(~exists(labeled))
        fields = [sources.c.id.label('source_record_id'), sources.c.raw_record_id, sources.c.provider_object_id,
                  sources.c.record_type, sources.c.occurred_at, sources.c.subject, sources.c.sender,
                  sources.c.recipients, sources.c.raw_metadata, accounts.c.provider, accounts.c.owner_type, accounts.c.owner_id]
        joined = sources.join(accounts, and_(accounts.c.id == sources.c.source_account_id,
                                             accounts.c.household_id == sources.c.household_id))
        ranked = select(*fields, func.row_number().over(partition_by=[accounts.c.provider, sources.c.record_type],
            order_by=[sources.c.occurred_at.desc(), sources.c.id]).label('type_rank')).select_from(joined).where(*conditions).subquery()
        providers = select(ranked, func.row_number().over(partition_by=ranked.c.provider,
            order_by=[ranked.c.type_rank, ranked.c.occurred_at.desc(), ranked.c.record_type, ranked.c.source_record_id]
            ).label('provider_rank')).subquery()
        rows = connection.execute(select(providers).order_by(providers.c.provider_rank,
            providers.c.occurred_at.desc(), providers.c.provider, providers.c.source_record_id).limit(limit)).mappings().all()
        current_query = _current_query(connection, household_id, definition, fingerprint).where(
            sources.c.id.in_([row['source_record_id'] for row in rows]))
        current = {row['source_record_id']: row for row in connection.execute(current_query).mappings()}
    items = []
    for row in rows:
        input = _input(row)
        existing = current.get(input.source_record_id)
        if existing:
            prediction = {key: existing[key] for key in ('relevance_label', 'relevance_confidence', 'domain_category',
                'domain_subcategory', 'domain_confidence', 'action_label', 'action_confidence', 'review_recommended')}
        else:
            prediction, _ = validate_output(analyzer.analyze(input, policy), input, policy)
        human = {key: existing['human_' + key] for key in ('relevance_label','domain_category','domain_subcategory','action_label')} if existing and existing['latest_human_revision'] else None
        items.append(ReviewItem(ReviewTicket(household_id, input.source_record_id, input.raw_record_id,
            input.fingerprint, freeze_json(declared)), input.provider, input.record_type, input.occurred_at.isoformat(),
            _bounded_text(input.subject, 8192), _bounded_text(input.sender, 320), freeze_json(_display(row['raw_metadata'])),
            freeze_json(prediction), 'persisted' if existing else 'dry_run',
            existing['latest_human_revision'] if existing else None, freeze_json(human) if human else None))
    return ReviewSelection(freeze_json(declared), policy.categories, start.isoformat(), end.isoformat(), tuple(items))


def save_review(engine, ticket, human_labels, *, confirmed=False,
                classification_path='config/classification.yaml', rules_path='config/metadata-classifier.yaml'):
    """One confirmed transaction: exact displayed snapshot -> analysis -> label.

    Shared analyze_source/append_label internals avoid the two-commit race. Inference
    happens before BEGIN. No retries; typed conflicts require a new explicit action.
    """
    if confirmed is not True or type(ticket) is not ReviewTicket:
        raise AnalysisValidationError()
    policy, analyzer, definition, fingerprint = _config(classification_path, rules_path)
    declared = definition | {'definition_fingerprint': fingerprint, 'rules_fingerprint': analyzer.ruleset.fingerprint}
    if declared != ticket.definition:
        raise ReviewChangedError()
    validate_labels(human_labels, policy)
    try:
        prepared = _prepare_analysis(engine, ticket.household_id, ticket.source_record_id, analyzer, policy,
                                     expected_fingerprint=ticket.input_fingerprint)
        if prepared.input.raw_record_id != ticket.raw_record_id:
            raise ReviewChangedError()
        # Re-read local config after inference, outside any database transaction.
        _, current_analyzer, current_definition, current_fingerprint = _config(classification_path, rules_path)
        if declared != current_definition | {'definition_fingerprint': current_fingerprint,
                                            'rules_fingerprint': current_analyzer.ruleset.fingerprint}:
            raise ReviewChangedError()
        with engine.begin() as connection:
            result = _persist_analysis(connection, ticket.household_id, prepared)
            # Final bounded config check also rolls back a newly inserted analysis
            # if the local definition changed while waiting for the DB lock.
            _, final_analyzer, final_definition, final_fingerprint = _config(classification_path, rules_path)
            if declared != final_definition | {'definition_fingerprint': final_fingerprint,
                                              'rules_fingerprint': final_analyzer.ruleset.fingerprint}:
                raise ReviewChangedError()
            return _append_label(connection, ticket.household_id, result.analysis.id, human_labels, policy)
    except (StaleAnalysisInputError, AnalysisNotFoundError):
        raise ReviewChangedError() from None
    except AnalysisError:
        raise
    except (IntegrityError, OperationalError):
        raise EvaluationRevisionConflictError() from None
    except Exception:
        raise AnalysisPersistenceError() from None
