"""Conservative local metadata rules. No database, providers, environment or network.

Rule scores are deterministic product strengths, not statistical probabilities.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import parseaddr
from hashlib import sha256
from pathlib import Path
import re
import unicodedata

import yaml

from .analysis import (AnalysisInput, AnalysisOutput, ClassificationPolicy,
    AnalysisValidationError, canonical_json, freeze_json, name, version)

# A rules engine/normalization change must bump this implementation identity.
ENGINE_VERSION = 'e1'
METADATA_FIELDS = frozenset({'status', 'eventType', 'start.dateTime', 'start.date',
    'end.dateTime', 'end.date', 'mimeType', 'trashed', 'removed'})
SIGNALS = frozenset({'subject_phrases_any', 'subject_tokens_all', 'sender_domains_any',
    'sender_domain_suffixes_any', 'record_types', 'providers', 'metadata_equals', 'metadata_present'})
# Global ambiguity veto for positive domain/relevance/action assertions. No
# grammar/negation understanding is claimed. Ignore rules may still match.
CAUTION = frozenset({'no', 'not', 'never', 'maybe', 'sample', 'example', 'cancelled', 'canceled', 'paid', 'completed', 'resolved', 'draft', 'test', 'training', 'hypothetical'})


def tokens(value):
    if type(value) is not str or len(value) > 8192:
        raise AnalysisValidationError()
    normalized = unicodedata.normalize('NFKC', unicodedata.normalize('NFKC', value).casefold())
    return tuple(''.join(c if c.isalnum() else ' ' for c in normalized).split())


def _array(value, validator):
    if type(value) is not list or not 1 <= len(value) <= 32:
        raise AnalysisValidationError()
    result = tuple(validator(item) for item in value)
    if len(result) != len(set(result)):
        raise AnalysisValidationError()
    return tuple(sorted(result))


def _text(value, *, single=False):
    if type(value) is not str or not 1 <= len(value) <= 128:
        raise AnalysisValidationError()
    result = tokens(value)
    if not result or single and len(result) != 1:
        raise AnalysisValidationError()
    return ' '.join(result)


def _domain(value):
    if type(value) is not str or len(value) > 253 or value != value.lower():
        raise AnalysisValidationError()
    if '.' not in value or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                               for label in value.split('.')):
        raise AnalysisValidationError()
    return value


def _field(value):
    if type(value) is not str or value not in METADATA_FIELDS:
        raise AnalysisValidationError()
    return value


@dataclass(frozen=True)
class Rule:
    id: str
    when: Mapping
    prediction: Mapping
    strength: str


@dataclass(frozen=True)
class Ruleset:
    declared_version: str
    fingerprint: str
    rules: tuple[Rule, ...]

    @property
    def effective_version(self):
        return version(f'{self.declared_version}-{ENGINE_VERSION}-{self.fingerprint[:24]}')


def load_rules(path, taxonomy: ClassificationPolicy) -> Ruleset:
    """All-or-nothing bounded declarative YAML, no regex/expressions/plugins."""
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if key in result:
                raise AnalysisValidationError()
            result[key] = loader.construct_object(value_node)
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        if type(taxonomy) is not ClassificationPolicy:
            raise AnalysisValidationError()
        with Path(path).open('rb') as file:
            raw = file.read(65537)
        if len(raw) > 65536:
            raise AnalysisValidationError()
        config = yaml.load(raw.decode('utf-8'), Loader=UniqueLoader)
        if type(config) is not dict or set(config) != {'ruleset_version', 'rules'}:
            raise AnalysisValidationError()
        declared = version(config['ruleset_version'])
        if len(declared) > 32 or type(config['rules']) is not list or not 1 <= len(config['rules']) <= 128:
            raise AnalysisValidationError()
        rules, ids = [], set()
        for item in config['rules']:
            if type(item) is not dict or set(item) != {'id', 'when', 'prediction', 'strength'}:
                raise AnalysisValidationError()
            rule_id = name(item['id'])
            if rule_id in ids or item['strength'] not in {'strong', 'weak'}:
                raise AnalysisValidationError()
            ids.add(rule_id)
            when, prediction = item['when'], item['prediction']
            if type(when) is not dict or not when or not set(when) <= SIGNALS:
                raise AnalysisValidationError()
            normalized = {}
            for key, values in when.items():
                if key == 'metadata_equals':
                    if type(values) is not dict or not 1 <= len(values) <= 8:
                        raise AnalysisValidationError()
                    normalized[key] = {}
                    for field, value in values.items():
                        _field(field)
                        if type(value) not in (str, bool, int, float) or len(canonical_json(value)) > 256:
                            raise AnalysisValidationError()
                        normalized[key][field] = value
                else:
                    validator = (_domain if key.startswith('sender_domain') else _field if key == 'metadata_present'
                        else name if key in {'providers', 'record_types'}
                        else lambda value: _text(value, single=key == 'subject_tokens_all'))
                    normalized[key] = _array(values, validator)
            # Context (provider, sender, MIME/status) is a gate, never sole evidence.
            if not {'subject_phrases_any', 'subject_tokens_all'} & set(normalized):
                raise AnalysisValidationError()
            if 'subject_tokens_all' in normalized and len(normalized['subject_tokens_all']) < 2:
                raise AnalysisValidationError()
            if type(prediction) is not dict or not prediction or not set(prediction) <= {'relevance', 'domain', 'action'}:
                raise AnalysisValidationError()
            if 'relevance' in prediction and prediction['relevance'] not in {'relevant', 'irrelevant'}:
                raise AnalysisValidationError()
            if 'action' in prediction and prediction['action'] not in {'required', 'not_required'}:
                raise AnalysisValidationError()
            if 'domain' in prediction:
                pair = prediction['domain']
                if type(pair) is not list or len(pair) != 2 or pair[0] not in taxonomy.categories or pair[1] not in taxonomy.categories[pair[0]]:
                    raise AnalysisValidationError()
            rules.append(Rule(rule_id, freeze_json(normalized), freeze_json(prediction), item['strength']))
        rules.sort(key=lambda rule: rule.id)
        definition = {'ruleset_version': declared, 'engine_version': ENGINE_VERSION,
            'rules': [dict(id=r.id, when=r.when, prediction=r.prediction, strength=r.strength) for r in rules]}
        fingerprint = sha256(canonical_json(definition).encode()).hexdigest()
        return Ruleset(declared, fingerprint, tuple(rules))
    except AnalysisValidationError:
        raise
    except Exception:
        raise AnalysisValidationError() from None


def _metadata(input, path):
    value = input.raw_metadata
    for component in path.split('.'):
        if not isinstance(value, Mapping) or component not in value:
            return None
        value = value[component]
    return value


def _sender_domain(sender):
    if type(sender) is not str or len(sender) > 320:
        return None
    # Reject ambiguous/multiple addresses rather than using a display name as evidence.
    if sender.count('@') != 1:
        return None
    address = parseaddr(sender)[1]
    if '@' not in address:
        return None
    candidate = address.rsplit('@', 1)[1].casefold()
    try:
        return _domain(candidate)
    except AnalysisValidationError:
        return None


def _matches(rule, input, words, domain):
    phrase_text = ' ' + ' '.join(words) + ' '
    for kind, values in rule.when.items():
        if kind == 'subject_phrases_any' and not any(' ' + phrase + ' ' in phrase_text for phrase in values): return False
        if kind == 'subject_tokens_all' and not set(values) <= set(words): return False
        if kind == 'providers' and input.provider not in values: return False
        if kind == 'record_types' and input.record_type not in values: return False
        if kind == 'sender_domains_any' and domain not in values: return False
        if kind == 'sender_domain_suffixes_any' and not any(domain and (domain == suffix or domain.endswith('.' + suffix)) for suffix in values): return False
        if kind == 'metadata_present' and not all(_metadata(input, field) is not None for field in values): return False
        if kind == 'metadata_equals' and not all(canonical_json(_metadata(input, field)) == canonical_json(value) for field, value in values.items()): return False
    return True


def _resolve(matches, dimension, default):
    candidates = [(rule.prediction[dimension], rule.strength) for rule in matches if dimension in rule.prediction]
    labels = {value for value, strength in candidates}
    if not candidates: return default, 0.0
    if len(labels) != 1: return default, 0.0
    if not any(strength == 'strong' for value, strength in candidates):
        # Weak evidence records a score, never a semantic product assertion.
        return default, 0.55
    return candidates[0][0], 0.90


@dataclass(frozen=True)
class MetadataRulesAnalyzer:
    ruleset: Ruleset
    name = 'metadata_rules'

    @property
    def version(self):
        return self.ruleset.effective_version

    def analyze(self, input: AnalysisInput, taxonomy: ClassificationPolicy) -> AnalysisOutput:
        return self.diagnose(input, taxonomy).output

    def diagnose(self, input: AnalysisInput, taxonomy: ClassificationPolicy):
        """Same runtime matcher/resolver; diagnostics contain no matched input text."""
        if type(input) is not AnalysisInput or type(taxonomy) is not ClassificationPolicy:
            raise AnalysisValidationError()
        if input.subject is None or len(input.subject) > 8192:
            return RuleDiagnostics(AnalysisOutput('uncertain', 0.0, None, None, 0.0, 'uncertain', 0.0),
                (), (), (), freeze_json({dimension: 'no_evidence' for dimension in ('relevance', 'domain', 'action')}))
        words = tokens(input.subject)
        sender = _sender_domain(input.sender)
        matches, vetoed = [], []
        caution = bool(set(words) & CAUTION) or _metadata(input, 'status') == 'cancelled' or _metadata(input, 'trashed') is True or _metadata(input, 'removed') is True
        for rule in self.ruleset.rules:
            if caution and (rule.prediction.get('relevance') == 'relevant' or rule.prediction.get('action') == 'required'
                            or rule.prediction.get('domain', ('ignore',))[0] != 'ignore'):
                if _matches(rule, input, words, sender):
                    vetoed.append(rule.id)
                continue
            if _matches(rule, input, words, sender):
                matches.append(rule)
        relevance, relevance_score = _resolve(matches, 'relevance', 'uncertain')
        domain, domain_score = _resolve(matches, 'domain', (None, None))
        action, action_score = _resolve(matches, 'action', 'uncertain')
        states = {}
        for dimension in ('relevance', 'domain', 'action'):
            candidates = [rule for rule in matches if dimension in rule.prediction]
            targets = {rule.prediction[dimension] for rule in candidates}
            states[dimension] = ('no_evidence' if not candidates else 'conflict' if len(targets) > 1
                else 'strong_unanimous' if any(rule.strength == 'strong' for rule in candidates) else 'weak_only')
        return RuleDiagnostics(AnalysisOutput(relevance, relevance_score, *domain, domain_score, action, action_score),
            tuple(rule.id for rule in matches), tuple(rule.id for rule in matches if rule.strength == 'strong'),
            tuple(vetoed), freeze_json(states))


@dataclass(frozen=True)
class RuleDiagnostics:
    output: AnalysisOutput
    matched_rule_ids: tuple[str, ...]
    strong_rule_ids: tuple[str, ...]
    vetoed_rule_ids: tuple[str, ...]
    states: Mapping
