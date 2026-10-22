"""Offline synthetic evaluation of the exact runtime analyzer, without persistence.

These metrics describe this committed synthetic corpus, not production accuracy.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from .analysis import AnalysisInput, AnalysisValidationError, validate_output, load_classification
from .metadata_classifier import load_rules, MetadataRulesAnalyzer


@dataclass(frozen=True)
class EvaluationSummary:
    case_count: int
    domain_coverage: float
    domain_abstention_rate: float
    relevance_labeled_count: int
    relevance_accuracy: float | None
    domain_predicted_count: int
    domain_accuracy: float | None
    action_labeled_count: int
    action_accuracy: float | None
    confident_false_positives: dict
    per_domain_support: dict


def evaluate_cases(cases, analyzer, policy) -> EvaluationSummary:
    """Cases supply inputs/labels only; all predictions use MetadataRulesAnalyzer."""
    if type(cases) is not list or not 1 <= len(cases) <= 10000 or type(analyzer) is not MetadataRulesAnalyzer:
        raise AnalysisValidationError()
    relevance_total = relevance_correct = action_total = action_correct = domain_total = domain_correct = 0
    false_positives = {'relevant': 0, 'irrelevant': 0, 'action_required': 0}
    support = {domain: {'labeled': 0, 'predicted': 0} for domain in policy.categories}
    ids = set()
    for case in cases:
        if type(case) is not dict or set(case) != {'id', 'input', 'expected'} or case['id'] in ids:
            raise AnalysisValidationError()
        ids.add(case['id'])
        source, expected = case['input'], case['expected']
        if type(source) is not dict or not {'provider', 'record_type', 'subject'} <= set(source) or not set(source) <= {'provider', 'record_type', 'subject', 'sender', 'raw_metadata'}:
            raise AnalysisValidationError()
        if type(expected) is not dict or set(expected) != {'relevance', 'domain', 'action'}:
            raise AnalysisValidationError()
        if expected['relevance'] not in {'relevant', 'irrelevant', 'uncertain'} or expected['action'] not in {'required', 'not_required', 'uncertain'}:
            raise AnalysisValidationError()
        domain = expected['domain']
        if domain is not None and (type(domain) is not list or len(domain) != 2 or domain[0] not in policy.categories or domain[1] not in policy.categories[domain[0]]):
            raise AnalysisValidationError()
        input = AnalysisInput('synthetic-' + case['id'], 'raw-' + case['id'], source['provider'], 'unknown', None,
            source['record_type'], 'object-' + case['id'], datetime(2026, 10, 5, tzinfo=timezone.utc),
            source['subject'], source.get('sender'), (), source.get('raw_metadata', {}))
        output = analyzer.analyze(input, policy)
        validate_output(output, input, policy)
        if expected['relevance'] != 'uncertain':
            relevance_total += 1
            relevance_correct += output.relevance_label == expected['relevance']
        if expected['action'] != 'uncertain':
            action_total += 1
            action_correct += output.action_label == expected['action']
        if domain is not None:
            support[domain[0]]['labeled'] += 1
        if output.category is not None:
            domain_total += 1
            domain_correct += domain == [output.category, output.subcategory]
            support[output.category]['predicted'] += 1
        if output.relevance_label in {'relevant', 'irrelevant'} and output.relevance_confidence >= policy.thresholds.relevance and output.relevance_label != expected['relevance']:
            false_positives[output.relevance_label] += 1
        if output.action_label == 'required' and output.action_confidence >= policy.thresholds.action and expected['action'] != 'required':
            false_positives['action_required'] += 1
    coverage = domain_total / len(cases)
    return EvaluationSummary(len(cases), coverage, 1 - coverage, relevance_total,
        relevance_correct / relevance_total if relevance_total else None, domain_total,
        domain_correct / domain_total if domain_total else None, action_total,
        action_correct / action_total if action_total else None, false_positives, support)


def main():
    # No user corpus argument: this command evaluates the committed synthetic corpus only.
    policy = load_classification('config/classification.yaml')
    analyzer = MetadataRulesAnalyzer(load_rules('config/metadata-classifier.yaml', policy))
    cases = json.loads(Path('fixtures/metadata-classifier.synthetic.json').read_text())
    print(json.dumps({'synthetic_only': True, 'analyzer_version': analyzer.version, **asdict(evaluate_cases(cases, analyzer, policy))}, sort_keys=True))


if __name__ == '__main__':
    main()
