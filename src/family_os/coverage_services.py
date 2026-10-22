"""Bounded local coverage inspection. Dry-run only; no provider or credential access."""
from collections import Counter
from sqlalchemy import select, func, cast, Integer, and_

from .analysis import AnalysisInput, AnalysisValidationError, load_classification, validate_output, utc
from .analysis_services import _definition, _check_definition, analyze_source
from .audit_services import _snapshot, _household, _current_query, _display, _bounded_text
from .metadata_classifier import MetadataRulesAnalyzer, load_rules, METADATA_FIELDS, _metadata
from .schema import source_record as sources, source_account as accounts


def _config(classification_path, rules_path):
    policy = load_classification(classification_path)
    analyzer = MetadataRulesAnalyzer(load_rules(rules_path, policy))
    definition = _definition(analyzer.name, analyzer.version, policy)
    return policy, analyzer, definition, policy.fingerprint(analyzer.name, analyzer.version)


def _selected(connection, household_id, limit):
    """Round-robin providers, then UTC month/type strata, then chronological rows.

    Window ranking spans all current sources; only LIMIT rows' metadata leave SQL.
    IDs only break chronological ties; they are not the leading sample criterion.
    """
    _household(connection, household_id)
    timestamp = sources.c.occurred_at
    if connection.dialect.name == 'postgresql':
        timestamp = func.timezone('UTC', timestamp)
    month = (cast(func.extract('year', timestamp), Integer) * 100 +
             cast(func.extract('month', timestamp), Integer)).label('month_bucket')
    fields = [sources.c.id.label('source_record_id'), sources.c.raw_record_id,
        sources.c.provider_object_id, sources.c.record_type, sources.c.occurred_at,
        sources.c.subject, sources.c.sender, sources.c.recipients, sources.c.raw_metadata,
        accounts.c.provider, accounts.c.owner_type, accounts.c.owner_id, month]
    joined = sources.join(accounts, and_(accounts.c.id == sources.c.source_account_id,
                                          accounts.c.household_id == sources.c.household_id))
    ranked = select(*fields, func.row_number().over(
        partition_by=[accounts.c.provider, month, sources.c.record_type],
        order_by=[sources.c.occurred_at.asc().nulls_last(), sources.c.id]).label('stratum_rank')
        ).select_from(joined).where(sources.c.household_id == household_id).subquery()
    providers = select(ranked, func.row_number().over(partition_by=ranked.c.provider,
        order_by=[ranked.c.stratum_rank, ranked.c.month_bucket.asc().nulls_last(),
                  ranked.c.record_type, ranked.c.source_record_id]).label('provider_rank')).subquery()
    return connection.execute(select(providers).order_by(providers.c.provider_rank, providers.c.provider)
                              .limit(limit)).mappings().all()


def _input(row):
    return AnalysisInput(*(row[key] for key in ('source_record_id', 'raw_record_id', 'provider',
        'owner_type', 'owner_id', 'record_type', 'provider_object_id', 'occurred_at', 'subject',
        'sender', 'recipients', 'raw_metadata')))


def _limit(limit):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise AnalysisValidationError()


def coverage_diagnostics(engine, household_id, *, limit=1000,
        classification_path='config/classification.yaml', rules_path='config/metadata-classifier.yaml'):
    """Aggregate sampled rule applicability, NOT accuracy or population estimates."""
    _limit(limit)
    policy, analyzer, definition, fingerprint = _config(classification_path, rules_path)
    with _snapshot(engine) as connection:
        _household(connection, household_id)
        _check_definition(connection, household_id, definition, fingerprint)
        total = connection.scalar(select(func.count()).select_from(sources).where(sources.c.household_id == household_id))
        population = dict(connection.execute(select(accounts.c.provider, func.count()).select_from(
            sources.join(accounts, and_(sources.c.source_account_id == accounts.c.id,
                                       sources.c.household_id == accounts.c.household_id)))
            .where(sources.c.household_id == household_id).group_by(accounts.c.provider)).all())
        rows = _selected(connection, household_id, limit)
    providers = {}
    for row in rows:
        input = _input(row)
        diagnostic = analyzer.diagnose(input, policy)
        values, _ = validate_output(diagnostic.output, input, policy)
        counts = providers.setdefault(input.provider, dict(inspected_count=0, subject=Counter(present=0, missing=0, oversized=0),
            record_types=Counter(), time_buckets=Counter(), any_rule_match=0, any_strong_rule_match=0,
            caution_veto=0, rule_matches={rule.id: 0 for rule in analyzer.ruleset.rules},
            missing_metadata={path: 0 for path in sorted(METADATA_FIELDS)}, sender_missing=0,
            dimensions={key: Counter({state: 0 for state in ('no_evidence', 'weak_only', 'conflict', 'strong_unanimous')})
                        for key in ('relevance', 'domain', 'action')},
            relevance=Counter(relevant=0, irrelevant=0, uncertain=0),
            domain=Counter(classified=0, abstained=0),
            action=Counter(required=0, not_required=0, uncertain=0), review_count=0))
        counts['inspected_count'] += 1
        counts['subject']['missing' if input.subject is None else 'oversized' if len(input.subject) > 8192 else 'present'] += 1
        counts['record_types'][input.record_type] += 1
        counts['time_buckets'][str(row['month_bucket']) if row['month_bucket'] is not None else 'undated'] += 1
        counts['sender_missing'] += input.sender is None
        for path in METADATA_FIELDS:
            counts['missing_metadata'][path] += _metadata(input, path) is None
        counts['any_rule_match'] += bool(diagnostic.matched_rule_ids)
        counts['any_strong_rule_match'] += bool(diagnostic.strong_rule_ids)
        counts['caution_veto'] += bool(diagnostic.vetoed_rule_ids)
        for rule_id in diagnostic.matched_rule_ids:
            counts['rule_matches'][rule_id] += 1
        for dimension, state in diagnostic.states.items():
            counts['dimensions'][dimension][state] += 1
        counts['relevance'][values['relevance_label']] += 1
        counts['domain']['classified' if values['domain_category'] else 'abstained'] += 1
        counts['action'][values['action_label']] += 1
        counts['review_count'] += values['review_recommended']
    return dict(definition=definition | {'definition_fingerprint': fingerprint,
        'rules_fingerprint': analyzer.ruleset.fingerprint}, current_source_count=total,
        inspected_count=len(rows), limit=limit, provider_population_counts=population,
        providers=providers, dry_run=True)


def coverage_sample(engine, household_id, *, limit=40,
        classification_path='config/classification.yaml', rules_path='config/metadata-classifier.yaml'):
    """Explicit local-only display. Unanalyzed predictions are dry-run, not label targets."""
    _limit(limit)
    if limit > 100:
        raise AnalysisValidationError()
    policy, analyzer, definition, fingerprint = _config(classification_path, rules_path)
    with _snapshot(engine) as connection:
        rows = _selected(connection, household_id, limit)
        query = _current_query(connection, household_id, definition, fingerprint)
        current = {row['source_record_id']: row for row in connection.execute(query.where(
            sources.c.id.in_([row['source_record_id'] for row in rows]))).mappings()}
    records = []
    for row in rows:
        input = _input(row)
        values, _ = validate_output(analyzer.analyze(input, policy), input, policy)
        existing = current.get(input.source_record_id)
        records.append(dict(source_record_id=input.source_record_id, raw_record_id=input.raw_record_id,
            analysis_id=existing['analysis_id'] if existing else None,
            latest_human_revision=existing['latest_human_revision'] if existing else None,
            prediction_origin='persisted' if existing else 'dry_run', provider=input.provider,
            record_type=input.record_type, occurred_at=utc(input.occurred_at).isoformat() if input.occurred_at else None,
            subject=_bounded_text(input.subject, 8192), sender=_bounded_text(input.sender, 320),
            display_metadata=_display(row['raw_metadata']),
            prediction={key: existing[key] if existing else value for key, value in values.items()}))
    return dict(definition=definition | {'definition_fingerprint': fingerprint}, records=records, dry_run=True)


def analyze_metadata_source(engine, household_id, source_record_id, *,
        classification_path='config/classification.yaml', rules_path='config/metadata-classifier.yaml'):
    """Explicit local operator persistence through the unchanged Phase 2F contract."""
    policy, analyzer, _, _ = _config(classification_path, rules_path)
    result = analyze_source(engine, household_id, source_record_id, analyzer, policy)
    return dict(analysis_id=result.analysis.id, source_record_id=result.analysis.source_record_id,
                raw_record_id=result.analysis.raw_record_id, reused=result.reused)
