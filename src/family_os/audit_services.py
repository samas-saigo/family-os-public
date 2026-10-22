"""Local operator audit services; no provider, OAuth, keyring or raw-payload reads."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, func, and_, case
from sqlalchemy.exc import IntegrityError, OperationalError

from .analysis import (AnalysisError, AnalysisValidationError, AnalysisNotFoundError,
                       AnalysisPersistenceError, load_classification, utc)
from .analysis_services import _definition, _matching, _check_definition
from .audit import HumanLabels, validate_labels, EvaluationRecord, evaluate, simulate_thresholds
from .metadata_classifier import MetadataRulesAnalyzer, load_rules
from .schema import household, source_account, source_record, source_analysis, analysis_evaluation_label


class EvaluationRevisionConflictError(AnalysisError):
    def __init__(self):
        super().__init__('Evaluation revision could not be appended; retry explicitly')


@dataclass(frozen=True)
class LabelRevision:
    id: str
    analysis_id: str
    source_record_id: str
    revision: int


@dataclass(frozen=True)
class AuditRecord:
    analysis_id: str
    source_record_id: str
    raw_record_id: str
    provider: str
    record_type: str
    occurred_at: str | None
    subject: str | None = field(repr=False)
    sender: str | None = field(repr=False)
    display_metadata: dict = field(repr=False)
    relevance_label: str
    relevance_confidence: float
    domain_category: str | None
    domain_subcategory: str | None
    domain_confidence: float
    action_label: str
    action_confidence: float
    review_recommended: bool
    latest_human_revision: int | None


@dataclass(frozen=True)
class AuditSample:
    definition: dict
    current_source_count: int
    eligible_count: int
    missing_count: int
    strategy: str
    records: tuple[AuditRecord, ...]


@contextmanager
def _snapshot(engine):
    """One consistent local read snapshot for counts, selection and latest labels."""
    try:
        with engine.connect() as connection:
            if connection.dialect.name == 'postgresql':
                connection = connection.execution_options(isolation_level='REPEATABLE READ')
            with connection.begin():
                if connection.dialect.name == 'sqlite':
                    connection.exec_driver_sql('BEGIN')
                yield connection
    except AnalysisError:
        raise
    except Exception:
        raise AnalysisPersistenceError() from None


def _household(connection, household_id):
    if type(household_id) is not str or connection.scalar(select(household.c.id).where(household.c.id == household_id)) is None:
        raise AnalysisNotFoundError()


def _configuration(classification_path, rules_path):
    policy = load_classification(classification_path)
    analyzer = MetadataRulesAnalyzer(load_rules(rules_path, policy))
    definition = _definition(analyzer.name, analyzer.version, policy)
    return policy, definition, policy.fingerprint(analyzer.name, analyzer.version)


def _current_query(connection, household_id, definition, fingerprint, *, display=False):
    _household(connection, household_id)
    _check_definition(connection, household_id, definition, fingerprint)
    labels = analysis_evaluation_label
    latest = select(labels.c.analysis_id, func.max(labels.c.revision).label('revision')).where(
        labels.c.household_id == household_id).group_by(labels.c.analysis_id).subquery()
    joined = source_analysis.join(source_record, and_(source_record.c.household_id == household_id,
        *_matching(source_record.c.id, source_record.c.raw_record_id, definition)))
    joined = joined.join(source_account, and_(source_account.c.household_id == household_id,
        source_account.c.id == source_analysis.c.source_account_id))
    joined = joined.outerjoin(latest, latest.c.analysis_id == source_analysis.c.id).outerjoin(labels, and_(
        labels.c.analysis_id == latest.c.analysis_id, labels.c.revision == latest.c.revision,
        labels.c.household_id == household_id))
    fields = [source_analysis.c.id.label('analysis_id'), source_analysis.c.source_record_id,
        source_analysis.c.raw_record_id, source_account.c.provider,
        *[source_analysis.c[name] for name in ('relevance_label', 'relevance_confidence', 'domain_category',
            'domain_subcategory', 'domain_confidence', 'action_label', 'action_confidence', 'review_recommended')],
        latest.c.revision.label('latest_human_revision'),
        *[labels.c[name].label('human_' + name) for name in ('relevance_label', 'domain_category', 'domain_subcategory', 'action_label')]]
    if display:
        fields += [source_record.c.record_type, source_record.c.occurred_at, source_record.c.subject,
                   source_record.c.sender, source_record.c.raw_metadata]
    return select(*fields).select_from(joined).where(source_analysis.c.household_id == household_id,
                                                     source_analysis.c.definition_fingerprint == fingerprint)


def _counts(connection, household_id, query):
    total = connection.scalar(select(func.count()).select_from(source_record).where(source_record.c.household_id == household_id))
    eligible = connection.scalar(select(func.count()).select_from(query.subquery()))
    return total, eligible


DISPLAY_FIELDS = ('status', 'eventType', 'start.dateTime', 'start.date', 'end.dateTime', 'end.date', 'mimeType', 'trashed', 'removed')


def _display(metadata):
    result = {}
    if type(metadata) is not dict:
        return result
    for path in DISPLAY_FIELDS:
        value = metadata
        for part in path.split('.'):
            value = value.get(part) if type(value) is dict else None
        expected = bool if path in ('trashed', 'removed') else str
        if type(value) is expected and (expected is bool or len(value) <= 256):
            result[path] = value
    return result


def _bounded_text(value, limit):
    return value if type(value) is str and len(value) <= limit else None


def audit_list(engine, household_id, *, limit, strategy='unlabeled',
               classification_path='config/classification.yaml', rules_path='config/metadata-classifier.yaml'):
    if type(limit) is not int or not 1 <= limit <= 1000 or type(strategy) is not str or strategy not in {'unlabeled', 'needs_review', 'accepted', 'balanced'}:
        raise AnalysisValidationError()
    policy, definition, fingerprint = _configuration(classification_path, rules_path)
    with _snapshot(engine) as connection:
        query = _current_query(connection, household_id, definition, fingerprint, display=True)
        total, eligible = _counts(connection, household_id, query)
        if strategy == 'unlabeled':
            query = query.where(~source_analysis.c.id.in_(select(analysis_evaluation_label.c.analysis_id).where(
                analysis_evaluation_label.c.household_id == household_id)))
        elif strategy in {'needs_review', 'accepted'}:
            query = query.where(source_analysis.c.review_recommended == (strategy == 'needs_review'))
        if strategy == 'balanced':
            # Round-robin joint strata, then stable source IDs within each stratum.
            abstained = case((source_analysis.c.domain_category.is_(None), 1), else_=0)
            strata = [source_account.c.provider, source_analysis.c.relevance_label, abstained, source_analysis.c.action_label]
            ranked = query.add_columns(func.row_number().over(partition_by=strata,
                order_by=source_analysis.c.source_record_id).label('sample_rank')).subquery()
            query = select(ranked).order_by(ranked.c.sample_rank, ranked.c.provider, ranked.c.relevance_label,
                case((ranked.c.domain_category.is_(None), 1), else_=0), ranked.c.action_label, ranked.c.source_record_id).limit(limit)
        else:
            query = query.order_by(source_analysis.c.source_record_id).limit(limit)
        rows = connection.execute(query).mappings().all()
    records = tuple(AuditRecord(**{key: row[key] for key in AuditRecord.__dataclass_fields__ if key not in
        {'occurred_at', 'subject', 'sender', 'display_metadata'}},
        occurred_at=utc(row['occurred_at']).isoformat().replace('+00:00', 'Z') if row['occurred_at'] else None,
        subject=_bounded_text(row['subject'], 8192), sender=_bounded_text(row['sender'], 320),
        display_metadata=_display(row['raw_metadata'])) for row in rows)
    return AuditSample(definition | {'definition_fingerprint': fingerprint}, total, eligible, total-eligible, strategy, records)


def _append_label(connection, household_id, analysis_id, labels, policy):
    """Shared append-only revision allocation; caller owns a short transaction."""
    _household(connection, household_id)
    query = select(source_analysis).where(source_analysis.c.household_id == household_id,
                                            source_analysis.c.id == analysis_id)
    if connection.dialect.name == 'postgresql':
        query = query.with_for_update()
    target = connection.execute(query).mappings().one_or_none()
    if target is None:
        raise AnalysisNotFoundError()
    # Labels may refer to immutable historical snapshots. Taxonomy/policy
    # content must still be explicit and consistent with that artifact.
    if target['taxonomy_version'] != policy.taxonomy_version or target['threshold_policy_version'] != policy.threshold_policy_version:
        raise AnalysisValidationError()
    _check_definition(connection, household_id, _definition(target['analyzer_name'], target['analyzer_version'], policy),
                      policy.fingerprint(target['analyzer_name'], target['analyzer_version']))
    validate_labels(labels, policy)
    latest = connection.scalar(select(func.max(analysis_evaluation_label.c.revision)).where(
        analysis_evaluation_label.c.household_id == household_id,
        analysis_evaluation_label.c.analysis_id == analysis_id)) or 0
    revision = latest + 1
    label_id = str(uuid4())
    connection.execute(analysis_evaluation_label.insert().values(id=label_id, household_id=household_id,
        analysis_id=analysis_id, source_record_id=target['source_record_id'], revision=revision,
        relevance_label=labels.relevance_label, domain_category=labels.domain_category,
        domain_subcategory=labels.domain_subcategory, action_label=labels.action_label,
        created_at=datetime.now(timezone.utc)))
    return LabelRevision(label_id, analysis_id, target['source_record_id'], revision)


def append_label(engine, household_id, analysis_id, labels, *, classification_path='config/classification.yaml'):
    policy = load_classification(classification_path)
    try:
        with engine.begin() as connection:
            if connection.dialect.name == 'sqlite':
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            return _append_label(connection, household_id, analysis_id, labels, policy)
    except AnalysisError:
        raise
    except (IntegrityError, OperationalError):
        raise EvaluationRevisionConflictError() from None
    except Exception:
        raise AnalysisPersistenceError() from None


def _evaluation_rows(connection, query):
    for row in connection.execution_options(stream_results=True).execute(query).mappings():
        human = HumanLabels(*(row['human_' + name] for name in ('relevance_label', 'domain_category', 'domain_subcategory', 'action_label'))) if row['latest_human_revision'] is not None else None
        yield EvaluationRecord(*(row[name] for name in ('provider', 'relevance_label', 'relevance_confidence', 'domain_category',
            'domain_subcategory', 'domain_confidence', 'action_label', 'action_confidence', 'review_recommended')), human)


def audit_metrics(engine, household_id, *, classification_path='config/classification.yaml', rules_path='config/metadata-classifier.yaml'):
    policy, definition, fingerprint = _configuration(classification_path, rules_path)
    with _snapshot(engine) as connection:
        query = _current_query(connection, household_id, definition, fingerprint)
        total, eligible = _counts(connection, household_id, query)
        metrics = evaluate(_evaluation_rows(connection, query), policy.categories)
    return dict(definition=definition | {'definition_fingerprint': fingerprint}, current_source_count=total,
                missing_count=total-eligible, **metrics)


def audit_simulate(engine, household_id, thresholds, *, classification_path='config/classification.yaml', rules_path='config/metadata-classifier.yaml'):
    policy, definition, fingerprint = _configuration(classification_path, rules_path)
    with _snapshot(engine) as connection:
        query = _current_query(connection, household_id, definition, fingerprint)
        total, eligible = _counts(connection, household_id, query)
        result = simulate_thresholds(_evaluation_rows(connection, query), thresholds)
    return dict(definition=definition | {'definition_fingerprint': fingerprint}, current_source_count=total,
                missing_count=total-eligible, **result)
