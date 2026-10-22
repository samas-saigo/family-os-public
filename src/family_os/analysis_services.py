"""Local callable analysis orchestration; no HTTP, provider clients or production AI.

Only the short final persistence transaction locks household/source rows. No database
connection is held while the caller's analyzer runs. Results expose structured classifications
and provenance, never input content, credentials or raw analyzer responses.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, exists

from .analysis import (
    Analyzer, AnalysisInput, ClassificationPolicy, AnalysisError,
    AnalysisValidationError, AnalysisNotFoundError, StaleAnalysisInputError,
    AnalyzerExecutionError, AnalysisPersistenceError, AnalysisDefinitionConflictError,
    version, utc, validate_output,
)
from .schema import household, source_record, raw_source_record, source_account, source_analysis, analysis_fact
from .storage import insert_for


@dataclass(frozen=True)
class AnalysisSummary:
    id: str
    household_id: str
    source_account_id: str
    source_record_id: str
    raw_record_id: str
    provider_object_id: str
    analyzer_name: str
    analyzer_version: str
    taxonomy_version: str
    threshold_policy_version: str
    input_fingerprint: str
    definition_fingerprint: str
    relevance_label: str
    relevance_confidence: float
    domain_category: str | None
    domain_subcategory: str | None
    domain_confidence: float
    action_label: str
    action_confidence: float
    review_recommended: bool
    created_at: datetime


@dataclass(frozen=True)
class AnalysisResult:
    analysis: AnalysisSummary
    reused: bool


@dataclass(frozen=True)
class PendingAnalysisResult:
    selected: int
    created: int
    reused: int
    stale: int


@contextmanager
def _read_connection(engine):
    try:
        with engine.connect() as connection:
            yield connection
    except AnalysisError:
        raise
    except Exception:
        raise AnalysisPersistenceError() from None


def _summary(row):
    return AnalysisSummary(**dict(row, created_at=utc(row['created_at'])))


def _source(connection, household_id, source_record_id, *, lock=False):
    query = select(source_record).where(source_record.c.household_id == household_id,
                                        source_record.c.id == source_record_id)
    if lock and connection.dialect.name == 'postgresql':
        query = query.with_for_update()
    row = connection.execute(query).mappings().one_or_none()
    if row is None:
        raise AnalysisNotFoundError()
    return row


def _input(connection, row):
    account = connection.execute(select(source_account.c.provider, source_account.c.owner_type, source_account.c.owner_id).where(
        source_account.c.household_id == row['household_id'],
        source_account.c.id == row['source_account_id'])).mappings().one_or_none()
    raw_id = connection.execute(select(raw_source_record.c.id).where(
        raw_source_record.c.household_id == row['household_id'],
        raw_source_record.c.source_account_id == row['source_account_id'],
        raw_source_record.c.provider_object_id == row['provider_object_id'],
        raw_source_record.c.id == row['raw_record_id'])).scalar_one_or_none()
    if account is None or raw_id is None:
        raise AnalysisValidationError()
    # Only normalized, already-persisted fields; not account metadata, raw payload or sync state.
    return AnalysisInput(row['id'], row['raw_record_id'], account['provider'], account['owner_type'],
        account['owner_id'], row['record_type'], row['provider_object_id'], row['occurred_at'],
        row['subject'], row['sender'], tuple(row['recipients']), row['raw_metadata'])


def _definition(analyzer_name, analyzer_version, policy):
    if type(policy) is not ClassificationPolicy:
        raise AnalysisValidationError()
    return dict(analyzer_name=version(analyzer_name), analyzer_version=version(analyzer_version),
                taxonomy_version=policy.taxonomy_version, threshold_policy_version=policy.threshold_policy_version)


def _matching(source_id, raw_id, definition):
    return (source_analysis.c.source_record_id == source_id,
            source_analysis.c.raw_record_id == raw_id,
            *(source_analysis.c[key] == value for key, value in definition.items()))


def _existing(connection, household_id, input, definition, definition_fingerprint):
    row = connection.execute(select(source_analysis).where(source_analysis.c.household_id == household_id,
        *_matching(input.source_record_id, input.raw_record_id, definition))).mappings().one_or_none()
    if row is not None:
        if row['definition_fingerprint'] != definition_fingerprint or row['input_fingerprint'] != input.fingerprint:
            raise AnalysisDefinitionConflictError()
        return AnalysisResult(_summary(row), reused=True)
    return None


def _check_definition(connection, household_id, definition, fingerprint):
    # Reusing declared versions for changed taxonomy/thresholds is never silent, including batches.
    conflict = connection.execute(select(source_analysis.c.id).where(
        source_analysis.c.household_id == household_id,
        *(source_analysis.c[key] == value for key, value in definition.items()),
        source_analysis.c.definition_fingerprint != fingerprint).limit(1)).first()
    if conflict is not None:
        raise AnalysisDefinitionConflictError()


@dataclass(frozen=True)
class PreparedAnalysis:
    """Internal inference value; no connection held. Content suppressed in repr."""
    input: AnalysisInput = field(repr=False)
    definition: dict
    definition_fingerprint: str
    values: dict | None
    facts: tuple = field(repr=False)
    previous: AnalysisResult | None


def _prepare_analysis(engine, household_id, source_record_id, analyzer, policy, *, expected_fingerprint=None):
    """Shared analyze_source preparation; optional displayed-input guard for review."""
    definition = _definition(analyzer.name, analyzer.version, policy)
    fingerprint = policy.fingerprint(definition['analyzer_name'], definition['analyzer_version'])
    with _read_connection(engine) as connection:
        row = _source(connection, household_id, source_record_id)
        input = _input(connection, row)
        input_fingerprint = input.fingerprint
        if expected_fingerprint is not None and input_fingerprint != expected_fingerprint:
            raise StaleAnalysisInputError()
        _check_definition(connection, household_id, definition, fingerprint)
        previous = _existing(connection, household_id, input, definition, fingerprint)
    if previous is not None:
        return PreparedAnalysis(input, definition, fingerprint, None, (), previous)

    try:
        output = analyzer.analyze(input, policy)
    except AnalysisValidationError:
        raise AnalysisValidationError() from None
    except Exception:
        raise AnalyzerExecutionError() from None
    if input.fingerprint != input_fingerprint:
        raise StaleAnalysisInputError()
    values, facts = validate_output(output, input, policy)

    return PreparedAnalysis(input, definition, fingerprint, values, facts, None)


def _persist_analysis(connection, household_id, prepared):
    """Shared short final persistence; caller owns transaction and may append a label.

    Lock order remains household/writer -> source -> definition -> exact analysis
    -> analysis/facts. Review then takes the analysis label-allocation lock.
    """
    input, definition = prepared.input, prepared.definition
    fingerprint = prepared.definition_fingerprint
    input_fingerprint, raw_record_id = input.fingerprint, input.raw_record_id
    source_record_id = input.source_record_id
    values, facts = prepared.values, prepared.facts
    # Consistent final lock/write order: household (or SQLite writer),
    # source, definition check, exact-analysis check, analysis, facts.
    # Serialize first-use definitions across different source records;
    # inference has already finished before acquiring either lock.
    # SQLite has no SELECT FOR UPDATE: reserve its writer before reading.
    if connection.dialect.name == 'sqlite':
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    elif connection.dialect.name == 'postgresql':
        locked_household = connection.execute(select(household.c.id).where(
            household.c.id == household_id).with_for_update()).scalar_one_or_none()
        if locked_household is None:
            raise StaleAnalysisInputError()
    try:
        current = _source(connection, household_id, source_record_id, lock=True)
    except AnalysisNotFoundError:
        raise StaleAnalysisInputError() from None
    if current['raw_record_id'] != raw_record_id or _input(connection, current).fingerprint != input_fingerprint:
        raise StaleAnalysisInputError()
    _check_definition(connection, household_id, definition, fingerprint)
    previous = _existing(connection, household_id, input, definition, fingerprint)
    if previous is not None:
        return previous
    if prepared.values is None:
        raise AnalysisPersistenceError()
    now = datetime.now(timezone.utc)
    analysis_id = str(uuid4())
    row_values = dict(id=analysis_id, household_id=household_id,
        source_account_id=current['source_account_id'], source_record_id=source_record_id,
        raw_record_id=raw_record_id, provider_object_id=input.provider_object_id,
        **definition, input_fingerprint=input_fingerprint, definition_fingerprint=fingerprint,
        **values, created_at=now)
    inserted = connection.execute(insert_for(connection, source_analysis).values(**row_values)
        .on_conflict_do_nothing(index_elements=['source_record_id', 'raw_record_id', *definition])
        .returning(source_analysis.c.id)).scalar_one_or_none()
    if inserted is None:
        previous = _existing(connection, household_id, input, definition, fingerprint)
        if previous is None:
            raise AnalysisPersistenceError()
        return previous
    if facts:
        connection.execute(analysis_fact.insert(), [dict(id=str(uuid4()), analysis_id=analysis_id,
            household_id=household_id, source_record_id=source_record_id, created_at=now, **fact)
            for fact in facts])
    return AnalysisResult(_summary(row_values), reused=False)


def analyze_source(engine, household_id: str, source_record_id: str,
                   analyzer: Analyzer, policy: ClassificationPolicy) -> AnalysisResult:
    """Analyze/reuse one exact snapshot. Stale attempts write nothing; retry explicitly."""
    prepared = _prepare_analysis(engine, household_id, source_record_id, analyzer, policy)
    if prepared.previous is not None:
        return prepared.previous
    try:
        with engine.begin() as connection:
            return _persist_analysis(connection, household_id, prepared)
    except AnalysisError:
        raise
    except Exception:
        raise AnalysisPersistenceError() from None


def analyze_pending(engine, household_id: str, analyzer: Analyzer,
                    policy: ClassificationPolicy, *, limit: int) -> PendingAnalysisResult:
    """Select at most limit current records once, in stable ID order; never retry-loop.

    Each record commits independently. Stale/deleted candidates are counted for a
    later explicit retry. Other failures abort; earlier successful commits remain.
    """
    if type(limit) is not int or limit < 1:
        raise AnalysisValidationError()
    definition = _definition(analyzer.name, analyzer.version, policy)
    fingerprint = policy.fingerprint(definition['analyzer_name'], definition['analyzer_version'])
    with _read_connection(engine) as connection:
        _check_definition(connection, household_id, definition, fingerprint)
        pending = ~exists(select(source_analysis.c.id).where(
            *_matching(source_record.c.id, source_record.c.raw_record_id, definition)))
        ids = connection.execute(select(source_record.c.id).where(
            source_record.c.household_id == household_id, pending)
            .order_by(source_record.c.id).limit(limit)).scalars().all()
    counts = [0, 0, 0]
    for source_id in ids:
        try:
            result = analyze_source(engine, household_id, source_id, analyzer, policy)
            counts[1 if result.reused else 0] += 1
        except (StaleAnalysisInputError, AnalysisNotFoundError):
            counts[2] += 1
    return PendingAnalysisResult(len(ids), *counts)


def analysis_history(engine, household_id: str, source_record_id: str) -> tuple[AnalysisSummary, ...]:
    """All immutable definitions/snapshots; chronological order is not a current selector."""
    with _read_connection(engine) as connection:
        _source(connection, household_id, source_record_id)
        rows = connection.execute(select(source_analysis).where(
            source_analysis.c.household_id == household_id,
            source_analysis.c.source_record_id == source_record_id)
            .order_by(source_analysis.c.created_at, source_analysis.c.id)).mappings().all()
    return tuple(_summary(row) for row in rows)


def current_analysis(engine, household_id: str, source_record_id: str, *, analyzer_name: str,
                     analyzer_version: str, policy: ClassificationPolicy) -> AnalysisSummary | None:
    """Current raw snapshot AND requested exact definition, never newest timestamp alone."""
    definition = _definition(analyzer_name, analyzer_version, policy)
    fingerprint = policy.fingerprint(analyzer_name, analyzer_version)
    with _read_connection(engine) as connection:
        row = _source(connection, household_id, source_record_id)
        previous = _existing(connection, household_id, _input(connection, row), definition, fingerprint)
    return previous.analysis if previous else None



def analyze_metadata(engine, household_id: str, *, limit: int,
                     classification_path='config/classification.yaml',
                     rules_path='config/metadata-classifier.yaml') -> PendingAnalysisResult:
    """Local runtime entry point; config/lifetime stay outside CLI presentation."""
    from .analysis import load_classification
    from .metadata_classifier import load_rules, MetadataRulesAnalyzer
    policy = load_classification(classification_path)
    analyzer = MetadataRulesAnalyzer(load_rules(rules_path, policy))
    return analyze_pending(engine, household_id, analyzer, policy, limit=limit)
