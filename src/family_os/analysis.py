"""Model/provider-neutral analysis values and strict local configuration/validation.

Analysis is inference about an exact source snapshot, never canonical truth.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Protocol

import yaml


class AnalysisError(RuntimeError):
    """Public safe analysis category, without source/analyzer exception text."""


class AnalysisValidationError(AnalysisError):
    def __init__(self):
        super().__init__("Analysis input/output/config rejected; check documented schema and bounds")


class AnalysisNotFoundError(AnalysisError):
    def __init__(self):
        super().__init__("Analysis source not found in the requested household")


class StaleAnalysisInputError(AnalysisError):
    def __init__(self):
        super().__init__("Analysis input changed; nothing persisted, retry the current snapshot")


class AnalyzerExecutionError(AnalysisError):
    def __init__(self):
        super().__init__("Analyzer failed; nothing persisted")


class AnalysisPersistenceError(AnalysisError):
    def __init__(self):
        super().__init__("Analysis persistence failed; transaction rolled back")


class AnalysisDefinitionConflictError(AnalysisError):
    def __init__(self):
        super().__init__("Analysis definition changed without a version bump; use new config versions")


_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_PATH = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|0|[1-9][0-9]*")
# Defense against structured credential, cursor, content and reasoning envelopes.
# Opaque text cannot be reliably classified as a secret: future adapters need an egress policy.
_FORBIDDEN = frozenset({"token", "accesstoken", "refreshtoken", "idtoken", "authorization", "oauth",
    "credentials", "password", "clientsecret", "apikey", "cursor", "synctoken", "pagetoken", "changetoken",
    "keyring", "client", "session", "providerclient", "rawresponse", "modelresponse", "prompt", "prompttranscript",
    "reasoning", "chainofthought", "body", "bodypreview", "snippet", "contentbytes", "filecontents"})


def version(value):
    if type(value) is not str or not _VERSION.fullmatch(value):
        raise AnalysisValidationError()
    return value


def name(value):
    if type(value) is not str or not _NAME.fullmatch(value) or _sensitive(value):
        raise AnalysisValidationError()
    return value


def _sensitive(value):
    return value.casefold().replace("_", "").replace("-", "") in _FORBIDDEN


def confidence(value):
    if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
        raise AnalysisValidationError()
    return float(value)


def _json(value, depth=0):
    if depth > 32:
        raise AnalysisValidationError()
    if value is None or type(value) in (str, bool):
        if isinstance(value, str) and ("\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value)):
            raise AnalysisValidationError()
        return value
    if type(value) is int:
        if abs(value) > 2**63 - 1:
            raise AnalysisValidationError()
        return value
    if type(value) is float and math.isfinite(value):
        return int(value) if value.is_integer() and abs(value) <= 2**63 - 1 else value
    if isinstance(value, Mapping):
        if len(value) > 10000 or any(type(k) is not str or _sensitive(k) for k in value):
            raise AnalysisValidationError()
        return {_json(k, depth + 1): _json(v, depth + 1) for k, v in value.items()}
    if type(value) in (list, tuple):
        if len(value) > 10000:
            raise AnalysisValidationError()
        return [_json(item, depth + 1) for item in value]
    raise AnalysisValidationError()


def canonical_json(value):
    try:
        return json.dumps(_json(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except AnalysisError:
        raise
    except Exception:
        raise AnalysisValidationError() from None


def freeze_json(value):
    plain = _json(value)
    def freeze(item):
        if isinstance(item, dict):
            return MappingProxyType({k: freeze(v) for k, v in item.items()})
        if isinstance(item, list):
            return tuple(freeze(v) for v in item)
        return item
    return freeze(plain)


def utc(value):
    if not isinstance(value, datetime):
        raise AnalysisValidationError()
    # SQLite's persisted timestamps are naive UTC; inference never invents local time.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AnalysisInput:
    source_record_id: str
    raw_record_id: str
    provider: str
    owner_type: str
    owner_id: str | None
    record_type: str
    provider_object_id: str
    occurred_at: datetime | None
    subject: str | None = field(repr=False)
    sender: str | None = field(repr=False)
    recipients: tuple[str, ...] = field(repr=False)
    raw_metadata: Mapping = field(repr=False)

    def __post_init__(self):
        for value in (self.source_record_id, self.raw_record_id, self.provider, self.record_type, self.provider_object_id):
            if type(value) is not str or not value:
                raise AnalysisValidationError()
        if type(self.owner_type) is not str or self.owner_type not in {"person", "household", "unknown"} or self.owner_id is not None and type(self.owner_id) is not str:
            raise AnalysisValidationError()
        if any(v is not None and type(v) is not str for v in (self.subject, self.sender)):
            raise AnalysisValidationError()
        if type(self.recipients) not in (list, tuple) or any(type(v) is not str for v in self.recipients):
            raise AnalysisValidationError()
        if not isinstance(self.raw_metadata, Mapping):
            raise AnalysisValidationError()
        object.__setattr__(self, "recipients", tuple(self.recipients))
        object.__setattr__(self, "raw_metadata", freeze_json(self.raw_metadata))
        if self.occurred_at is not None:
            object.__setattr__(self, "occurred_at", utc(self.occurred_at))
        if len(canonical_json(self.projection()).encode("utf-8")) > 1024 * 1024:
            raise AnalysisValidationError()

    def projection(self):
        return {"source_record_id": self.source_record_id, "raw_record_id": self.raw_record_id,
            "provider": self.provider, "owner_type": self.owner_type, "owner_id": self.owner_id,
            "record_type": self.record_type, "provider_object_id": self.provider_object_id,
            "occurred_at": self.occurred_at.isoformat(timespec="microseconds").replace("+00:00", "Z") if self.occurred_at else None,
            "subject": self.subject, "sender": self.sender, "recipients": self.recipients, "raw_metadata": self.raw_metadata}

    @property
    def fingerprint(self):
        return sha256(canonical_json(self.projection()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Thresholds:
    relevance: float
    domain: float
    action: float
    fact: float

    def __post_init__(self):
        for key in ("relevance", "domain", "action", "fact"):
            object.__setattr__(self, key, confidence(getattr(self, key)))


@dataclass(frozen=True)
class ClassificationPolicy:
    taxonomy_version: str
    threshold_policy_version: str
    categories: Mapping[str, tuple[str, ...]]
    thresholds: Thresholds

    def __post_init__(self):
        version(self.taxonomy_version); version(self.threshold_policy_version)
        if type(self.thresholds) is not Thresholds or not isinstance(self.categories, Mapping) or not self.categories:
            raise AnalysisValidationError()
        categories = {}
        for category, children in self.categories.items():
            name(category)
            if type(children) not in (list, tuple) or not children:
                raise AnalysisValidationError()
            validated = tuple(name(child) for child in children)
            if len(validated) != len(set(validated)):
                raise AnalysisValidationError()
            categories[category] = validated
        object.__setattr__(self, "categories", MappingProxyType(categories))

    def fingerprint(self, analyzer_name, analyzer_version):
        return sha256(canonical_json({"analyzer_name": version(analyzer_name), "analyzer_version": version(analyzer_version),
            "taxonomy_version": self.taxonomy_version, "threshold_policy_version": self.threshold_policy_version,
            "categories": {k: sorted(v) for k, v in self.categories.items()},
            "thresholds": {k: getattr(self.thresholds, k) for k in ("relevance", "domain", "action", "fact")}}).encode()).hexdigest()


def load_classification(path: str | Path) -> ClassificationPolicy:
    class UniqueLoader(yaml.SafeLoader):
        pass
    def unique(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if key in result:
                raise AnalysisValidationError()
            result[key] = loader.construct_object(value_node)
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique)
    try:
        value = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=UniqueLoader)
        if type(value) is not dict or set(value) != {"taxonomy_version", "threshold_policy_version", "categories", "thresholds"}:
            raise AnalysisValidationError()
        if type(value["thresholds"]) is not dict or set(value["thresholds"]) != {"relevance", "domain", "action", "fact"}:
            raise AnalysisValidationError()
        if type(value["categories"]) is not dict or any(type(v) is not dict or set(v) != {"children"} for v in value["categories"].values()):
            raise AnalysisValidationError()
        return ClassificationPolicy(value["taxonomy_version"], value["threshold_policy_version"],
            {k: v["children"] for k, v in value["categories"].items()}, Thresholds(**value["thresholds"]))
    except AnalysisError:
        raise
    except Exception:
        raise AnalysisValidationError() from None


@dataclass(frozen=True)
class FactProposal:
    fact_name: str
    value: object = field(repr=False)
    confidence: float
    evidence_refs: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "value", freeze_json(self.value))
        if type(self.evidence_refs) in (list, tuple):
            object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True)
class AnalysisOutput:
    relevance_label: str
    relevance_confidence: float
    category: str | None
    subcategory: str | None
    domain_confidence: float
    action_label: str
    action_confidence: float
    facts: tuple[FactProposal, ...] = ()

    def __post_init__(self):
        if type(self.facts) in (list, tuple):
            object.__setattr__(self, "facts", tuple(self.facts))


class Analyzer(Protocol):
    name: str
    version: str
    def analyze(self, input: AnalysisInput, taxonomy: ClassificationPolicy) -> AnalysisOutput: ...


def resolve_evidence(input, ref):
    if type(ref) is not str or not 1 <= len(ref) <= 256:
        raise AnalysisValidationError()
    parts = ref.split(".")
    if len(parts) > 8 or parts[0] not in {"subject", "sender", "occurred_at", "recipients", "record_type", "raw_metadata"}:
        raise AnalysisValidationError()
    if any(not _PATH.fullmatch(part) or _sensitive(part) for part in parts):
        raise AnalysisValidationError()
    value = input.projection()
    for part in parts:
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        elif type(value) in (list, tuple) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise AnalysisValidationError()
    if value is None:
        raise AnalysisValidationError()
    return value


def validate_output(output, input, policy):
    try:
        if type(output) is not AnalysisOutput or type(policy) is not ClassificationPolicy:
            raise AnalysisValidationError()
        if output.relevance_label not in {"relevant", "irrelevant", "uncertain"} or output.action_label not in {"required", "not_required", "uncertain"}:
            raise AnalysisValidationError()
        abstained = output.category is None and output.subcategory is None
        if not abstained and (output.category not in policy.categories or output.subcategory not in policy.categories[output.category]):
            raise AnalysisValidationError()
        scores = [confidence(v) for v in (output.relevance_confidence, output.domain_confidence, output.action_confidence)]
        review = abstained or output.relevance_label == "uncertain" or output.action_label == "uncertain" or any(
            score < threshold for score, threshold in zip(scores, (policy.thresholds.relevance, policy.thresholds.domain, policy.thresholds.action)))
        if type(output.facts) is not tuple or len(output.facts) > 100:
            raise AnalysisValidationError()
        facts = []
        for ordinal, fact in enumerate(output.facts):
            if type(fact) is not FactProposal:
                raise AnalysisValidationError()
            name(fact.fact_name); score = confidence(fact.confidence)
            value = _json(fact.value)
            if len(canonical_json(value).encode("utf-8")) > 16384:
                raise AnalysisValidationError()
            if type(fact.evidence_refs) is not tuple or not 1 <= len(fact.evidence_refs) <= 32:
                raise AnalysisValidationError()
            if len(fact.evidence_refs) != len(set(fact.evidence_refs)):
                raise AnalysisValidationError()
            for ref in fact.evidence_refs:
                resolve_evidence(input, ref)
            facts.append(dict(fact_name=fact.fact_name, fact_value=value, confidence=score,
                evidence_refs=list(fact.evidence_refs), ordinal=ordinal, review_recommended=score < policy.thresholds.fact))
        # Fact review stays per-fact: low fact confidence alone does not flag the whole classification.
        return dict(relevance_label=output.relevance_label, relevance_confidence=scores[0], domain_category=output.category,
            domain_subcategory=output.subcategory, domain_confidence=scores[1], action_label=output.action_label,
            action_confidence=scores[2], review_recommended=review), facts
    except AnalysisError:
        raise
    except Exception:
        raise AnalysisValidationError() from None
