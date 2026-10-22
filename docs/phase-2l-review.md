# Phase 2L — offline synthetic metadata reasoning spike

Closes Issue #36. This is a developer-only contract/comparison prototype under the
[Phase 2K decision](phase-2k-review.md), not an AI integration or classifier upgrade.
Only synthetic fixtures are used. No real household database, provider, keyring,
OAuth, model, download, external call or network service is accessed. No default
classifier, CLI/config, production rules/thresholds, schema, human label, ingestion,
transaction, task, canonical record or review queue changes.

## Modules and strict local projection

`synthetic_reasoning` implements a pure `metadata_only_v1` projector, immutable
manifest, explicit scripted fake transport and Analyzer-compatible adapter. There
are no model/plugin/SDK hooks: construction requires the exact fake transport class.
The normal Family OS CLI and services do not import either spike module. An input
without an explicitly scripted projection hash fails; the fake never reasons about
unseen records or follows instructions in metadata.

Projection admits only provider (gmail/outlook/google_calendar/google_drive), record
type (message/calendar_event/document), optional subject <=8192 characters, optional
sender <=320, persisted UTC occurred_at, and these exact metadata paths:

- status, eventType, mimeType;
- start.dateTime/date and end.dateTime/date;
- trashed and removed.

Scalar metadata strings must be <=256 characters; flags must be actual booleans.
Missing fields are omitted. Wrong-shaped, oversized or invalid allowlisted values
reject the whole projection; no truncation into positive evidence. Unknown metadata
keys are excluded, including nested siblings, rather than copied. Public projection
construction also validates its whitelist, then deeply freezes values. Canonical
UTF-8 JSON has stable keys and UTC timestamps, with a **16,384-byte total limit**;
multibyte text can exceed it even below the character limit. Response maximum is
**4,096 bytes**. Historical occurred_at remains provenance time, not event start or
an invented current obligation. No bodies/previews/snippets or file contents fill gaps.

Source/raw/provider-object/owner/account/household IDs, recipients, arbitrary headers,
raw payloads, links, permissions, credentials, cursors and financial fields never
enter the transport. Sender is the proposed **local-only** maximum, not authorization
for a future cloud request. Content is suppressed from projection/transport/analyzer
repr and fixed public errors; no runtime logs or prompt/response captures are created.
Checked-in scripted synthetic responses are test vectors, not inference transcripts.

Explicit URL and credential-pattern strings in allowed text reject, including bounded
percent-decoding and NFKC variants. This is defense in depth, **not complete secret
recognition, anonymization or a data-loss-prevention guarantee**. Arbitrary sensitive
context can remain in approved text; only synthetic callers are authorized here.
Malicious instructions are inert text in the fake's hash lookup. No browsing, tools,
code execution, subprocess, network transport or model runtime exists. These tests
cannot establish a real LLM's resistance to injection.

## Manifest identity and output contract

`SyntheticReasoningAnalyzer.analyze(AnalysisInput, ClassificationPolicy)` returns the
existing frozen `AnalysisOutput`. The manifest contains projection schema, fake
artifact/script SHA-256, declared fake revision/runtime, prompt/output-schema digests,
fixed deterministic decoding configuration, baseline rules fingerprint, paired
routing and uncalibrated score policy. The complete script, including deliberately
wrong responses, determines fake artifact identity. No human labels are read by the
transport. The static prompt is a specification, not sent to any model.

Canonical manifest SHA-256 determines effective version `synthetic-v1-<32 hex>`;
name/version fit the existing 64-character limit. Artifact/definition changes change
identity. The adapter rejects mismatched artifacts or unsupported schemas/runtime/
score/routing/digests. This fake supports one decoding mode, not configurable real
model parameters. Implementation/projection/validation changes require bumping
`ENGINE_VERSION`; hashing does not detect arbitrary code edits. Taxonomy and threshold
versions and their existing policy fingerprint remain separate.

Strict wire parsing rejects duplicate keys, malformed/non-JSON/trailing text, extra
fields, free-form reasoning/instructions, invented evidence refs, invalid enum labels,
nonfinite/non-numeric/out-of-range scores, invalid taxonomy children, half-null domain,
nonempty/wrong-shaped facts and oversized responses. Existing `validate_output` checks
the wire proposal before scores are replaced. All three returned scores are **0.0**:
unknown uncalibrated strength, not estimated probability. Facts remain empty. Final
validation must recommend review; a concrete proposal under permissive zero thresholds
is rejected rather than accepted. Current 0.80 thresholds remain unchanged.

Scripted timeout/error or missing script fails with a fixed safe error; there is no
retry or long-running backend to time out. Projection/output failure also rejects,
never silently converts bad metadata into a supported positive. The comparison alone
records these failures as explicit failed attempts plus uncertain/null-domain results
for aggregate denominators. It does not persist these fallback values.

## Paired synthetic comparison and honest metrics

`synthetic_reasoning_comparison` reads only the fixed checked-in
`fixtures/metadata-reasoning.synthetic.json` in its developer runner; no user path,
DATABASE_URL, corpus CLI flag or production command is exposed. Its bounded pure
comparison helper validates a declared synthetic corpus, case IDs/tags/input schema
and ground-truth labels. Declaration is not a detector of real data: callers must
never pass private data. Each fixture has separate expected labels and scripted fake
response; the latter is intentionally mostly oracle-like and includes explicit errors.
There is no trained/reasoning model or quality improvement demonstrated.

Both analyzers see the same 37 frozen synthetic source/raw projections. Output is
clearly marked **SYNTHETIC - NOT REAL WORLD QUALITY**, with synthetic source/raw IDs,
full input fingerprints, tags, explicit analyzer/taxonomy/threshold/policy definitions,
manifest/fingerprint, per-provider/category metrics and projected byte budget. It
prints no subjects, sender, arbitrary metadata or raw fake responses. Tags include
recent/historical, ambiguous, missing and challenge cases across all four providers.
Per-category correctness requires category and child agreement.

The reused pure Phase 2H evaluator retains decisive-label denominators, separate
human uncertainty and classifier abstention, and null rates when denominators are
zero. Additional action-required miss count compares decisive human required with
predicted uncertain/not_required. Concrete proposal correctness/FP counts include
uncalibrated fake claims: they are **not confident accepted actions**. No stored human
revision is copied, changed or retargeted.

Actual corpus results:

| Measure | Unchanged rules | Scripted fake |
| --- | ---: | ---: |
| Cases | 37 | 37 |
| Domain classified / abstained | 14 / 23 | 17 / 20 |
| Domain selective correct / decisive classified | 14 / 14 | 17 / 17 |
| Relevance correct / decisive human labels | 15 / 18 | 18 / 18 |
| Action correct / decisive human labels | 12 / 14 | 12 / 14 |
| Action-required correct / evaluated concrete claims | 4 / 4 | 5 / 6 |
| Concrete action-required false positives | 0 | 1 |
| Missed action-required / required truth | 2 / 6 | 1 / 6 |
| Review recommended | 25 / 37 | 37 / 37 |
| Failed attempts | 0 | 3 |

The three rejected fake projections contain an embedded URL, oversized title and
wrong-shaped start metadata. Failed attempts remain in the 37-case denominators.
Projected valid input total: **6,013 bytes**, maximum **269 bytes**, device egress
**0 bytes**. Scripted fake coverage/accuracy says nothing about real household quality;
its single deliberately wrong required proposal must never become a task.

Current effective version: `synthetic-v1-7de0691d63ac0e857286b0fbf5498c3d`.
Manifest fingerprint: `7de0691d63ac0e857286b0fbf5498c3dc98be7030fb80d0787e17d737b31b60a`.
Baseline version remains `metadata-v1-e1-98b9e7219a73125b7292bd89`.
The runner also prints both full policy/definition fingerprints and provider/domain
counts so results can be reproduced without copying prompt or household content.

## Exact synthetic commands

From the repository root, using the existing Python 3.12 environment:

```sh
.venv/bin/python -m pytest -q tests/test_synthetic_reasoning.py
.venv/bin/python -m family_os.synthetic_reasoning_comparison
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
git diff --check
```

Windows PowerShell equivalents (developer synthetic tests only, no runtime DB):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_reasoning.py
.\.venv\Scripts\python.exe -m family_os.synthetic_reasoning_comparison
```

Full PostgreSQL tests require **only a disposable synthetic test database** supplied
through TEST_DATABASE_URL; never point tests at the user's runtime database.

## Persistence boundary, validation and deferred work

This spike **does not exercise adapter persistence**. No new service/DB integration
is added; comparison and new tests use in-memory synthetic values only. Protocol
compatibility is not proof of a tested persisted model integration. Existing full
SQLite/PostgreSQL suites still cover Phase 2F exact-key reuse, stale zero writes,
household definition locking, concurrent duplicates and append-only human revisions;
those services are unchanged. Future real integration must separately exercise the
adapter through analyze_source/analyze_pending with exact snapshot/version semantics.
Default audit/review remains rules-specific and cannot silently evaluate this adapter.

Python 3.12.14 validation: **85 new tests**, **1,440 passed on SQLite** and
**1,440 passed on real PostgreSQL 16**, including all existing migration/concurrency
regressions. `pip check` and `git diff --check` passed. Final GitHub CI results are
recorded in the PR description. Synthetic tests
cover every provider, exact paths/types/budgets, nested/encoded exclusions, Unicode/
URLs/credentials, historical/missing/conflicting/negated fixture cases, malformed JSON,
null pairs, wire scores, no facts, immutable manifests/version changes, safe failures,
zero-denominator metrics and no I/O/production wiring. No SDK/dependency changes.

Future hardware/license/resource approval and a synthetic local-model benchmark remain
separate work; this is not authorization to install/download a model or infer on actual
household data. Real-data model comparisons, consent/egress, cloud vendors, content,
training/calibration, canonical entities, product review queue, tasks/actions, providers,
API/auth, workers and UI remain deferred under the single-backend/R0–R3 architecture.

ChatGPT review questions:

1. Does exact projection validation reject bad allowed values without leaking unrelated
   persisted metadata, and are pattern filters honestly limited to defense in depth?
2. Is the adapter truly fake-only/unwired, with canonical immutable manifests and
   material changes producing a new effective identity?
3. Does independent parsing reject malformed/unsafe responses before score-zero mapping,
   guaranteeing empty facts and review-only uncalibrated proposals?
4. Do paired snapshot/definition references and decisive denominators expose deliberate
   fake errors/misses without suggesting intelligence, calibration or household accuracy?
5. Are no DB integration, real-model security/performance limits and future approval
   gates explicit, with unchanged production classification/provenance/labels?
