"""Pure local evaluation values/metrics; no DB, provider, network or content access."""
from dataclasses import dataclass

from .analysis import AnalysisValidationError, ClassificationPolicy, confidence


@dataclass(frozen=True)
class HumanLabels:
    relevance_label: str
    domain_category: str | None
    domain_subcategory: str | None
    action_label: str


def validate_labels(labels, policy):
    if type(labels) is not HumanLabels or type(policy) is not ClassificationPolicy:
        raise AnalysisValidationError()
    if type(labels.relevance_label) is not str or labels.relevance_label not in {'relevant', 'irrelevant', 'uncertain'}:
        raise AnalysisValidationError()
    if type(labels.action_label) is not str or labels.action_label not in {'required', 'not_required', 'uncertain'}:
        raise AnalysisValidationError()
    category, child = labels.domain_category, labels.domain_subcategory
    if category is None and child is None:
        return labels
    if type(category) is not str or type(child) is not str or category not in policy.categories or child not in policy.categories[category]:
        raise AnalysisValidationError()
    return labels


@dataclass(frozen=True)
class EvaluationRecord:
    """No source content; latest human revision already selected by the query."""
    provider: str
    relevance_label: str
    relevance_confidence: float
    domain_category: str | None
    domain_subcategory: str | None
    domain_confidence: float
    action_label: str
    action_confidence: float
    review_recommended: bool
    human: HumanLabels | None


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


class MetricsAccumulator:
    """Streaming counters; constant space apart from providers/taxonomy categories."""
    def __init__(self, categories):
        self.categories = tuple(categories)
        self.counts = dict.fromkeys(('eligible_count', 'labeled_count', 'review_count', 'domain_classified_count',
            'human_uncertain_relevance', 'human_unknown_domain', 'human_uncertain_action',
            'relevance_decisive_count', 'relevance_correct_count', 'action_decisive_count', 'action_correct_count',
            'domain_selective_count', 'domain_correct_count'), 0)
        self.decisions = {key: {'evaluated': 0, 'correct': 0, 'false_positive': 0, 'human_uncertain': 0}
                          for key in ('relevant', 'irrelevant', 'action_required')}
        self.domains = {key: {'labeled': 0, 'predicted': 0, 'correct': 0} for key in self.categories}

    def add(self, record):
        c = self.counts
        c['eligible_count'] += 1
        c['review_count'] += int(record.review_recommended)
        c['domain_classified_count'] += int(record.domain_category is not None)
        if record.domain_category in self.domains:
            self.domains[record.domain_category]['predicted'] += 1
        human = record.human
        if human is None:
            return
        c['labeled_count'] += 1
        for dimension in ('relevance', 'action'):
            predicted = getattr(record, dimension + '_label')
            actual = getattr(human, dimension + '_label')
            if actual == 'uncertain':
                c['human_uncertain_' + dimension] += 1
            else:
                c[dimension + '_decisive_count'] += 1
                c[dimension + '_correct_count'] += int(predicted == actual)
            decision = predicted if dimension == 'relevance' else 'action_required' if predicted == 'required' else None
            if decision in self.decisions:
                d = self.decisions[decision]
                if actual == 'uncertain':
                    d['human_uncertain'] += 1
                else:
                    d['evaluated'] += 1
                    d['correct'] += int(predicted == actual)
                    d['false_positive'] += int(predicted != actual)
        if human.domain_category is None:
            c['human_unknown_domain'] += 1
        else:
            self.domains[human.domain_category]['labeled'] += 1
            if record.domain_category is not None:
                c['domain_selective_count'] += 1
                correct = (record.domain_category, record.domain_subcategory) == (human.domain_category, human.domain_subcategory)
                c['domain_correct_count'] += int(correct)
                if correct:
                    self.domains[human.domain_category]['correct'] += 1

    def result(self):
        c = self.counts
        return dict(c, unlabeled_count=c['eligible_count'] - c['labeled_count'],
            classifier_domain_abstained_count=c['eligible_count'] - c['domain_classified_count'],
            label_coverage=ratio(c['labeled_count'], c['eligible_count']),
            classifier_review_rate=ratio(c['review_count'], c['eligible_count']),
            classifier_domain_abstention_rate=ratio(c['eligible_count'] - c['domain_classified_count'], c['eligible_count']),
            domain_coverage=ratio(c['domain_classified_count'], c['eligible_count']),
            relevance_accuracy=ratio(c['relevance_correct_count'], c['relevance_decisive_count']),
            action_accuracy=ratio(c['action_correct_count'], c['action_decisive_count']),
            domain_selective_accuracy=ratio(c['domain_correct_count'], c['domain_selective_count']),
            concrete_predictions={key: dict(value, precision=ratio(value['correct'], value['evaluated']))
                                  for key, value in self.decisions.items()},
            per_domain=self.domains)


def evaluate(records, categories):
    overall = MetricsAccumulator(categories)
    providers = {}
    for record in records:
        overall.add(record)
        providers.setdefault(record.provider, MetricsAccumulator(categories)).add(record)
    return dict(overall.result(), providers={key: value.result() for key, value in sorted(providers.items())})


@dataclass(frozen=True)
class CandidateThresholds:
    relevance: float
    domain: float
    action: float

    def __post_init__(self):
        for value in (self.relevance, self.domain, self.action):
            confidence(value)


def simulate_thresholds(records, thresholds):
    """Pure counterfactual; abstention cannot be accepted even at zero thresholds.

    Observed precision uses only accepted records with decisive human labels in
    all three dimensions. Unknown labels are neither correctness nor falsehood.
    """
    if type(thresholds) is not CandidateThresholds:
        raise AnalysisValidationError()
    total = accepted = stored_accepted = decisive = accepted_labeled = accepted_correct = 0
    for record in records:
        total += 1
        stored_accepted += int(not record.review_recommended)
        selected = (record.relevance_label != 'uncertain' and record.action_label != 'uncertain'
            and record.domain_category is not None and record.relevance_confidence >= thresholds.relevance
            and record.domain_confidence >= thresholds.domain and record.action_confidence >= thresholds.action)
        accepted += int(selected)
        human = record.human
        complete = human is not None and human.relevance_label != 'uncertain' and human.action_label != 'uncertain' and human.domain_category is not None
        if complete:
            decisive += 1
            if selected:
                accepted_labeled += 1
                accepted_correct += int((record.relevance_label, record.domain_category, record.domain_subcategory, record.action_label)
                    == (human.relevance_label, human.domain_category, human.domain_subcategory, human.action_label))
    return dict(eligible_count=total, stored_accepted_count=stored_accepted, stored_review_count=total-stored_accepted,
        accepted_count=accepted, review_count=total-accepted, accepted_delta=accepted-stored_accepted,
        review_delta=stored_accepted-accepted, decisive_labeled_count=decisive, accepted_labeled_count=accepted_labeled,
        accepted_correct_count=accepted_correct, observed_joint_precision=ratio(accepted_correct, accepted_labeled),
        observed_labeled_coverage=ratio(accepted_labeled, decisive))
