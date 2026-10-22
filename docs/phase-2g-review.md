# Phase 2G review — conservative local metadata classifier

Closes Issue #16. This is the first real runtime classifier for household relevance,
domain and action-needed, operating locally on minimized persisted metadata. Prefer
abstention and review over unsupported guesses. Classification remains versioned
inference about an exact source/raw snapshot, never canonical household truth.

Local metadata rules precede any external AI decision because current inputs lack
Gmail bodies/snippets, Outlook bodies/previews, Calendar descriptions/attachments and
Drive contents/exports. An external model would still lack that evidence while
introducing data egress. This phase adds no model SDK, neural model, network call,
provider scope, content access, canonical entity/dedupe, review queue/UI, task, action,
worker, API/auth, mobile/web client or Finance reconciliation. Finance remains its
own source of truth; `finance_reference` means notices/references only.

## Explicit domain abstention and migration

`AnalysisOutput` and persisted/query summary domain fields accept exactly:

- A valid taxonomy category and its valid subcategory, with finite `[0,1]` confidence.
- Both category and subcategory null, with finite confidence and review recommended.

A half-null pair is invalid. No fake unknown/other/uncertain domain is added.
Abstention forces overall review even if every score is above threshold. Labels,
confidence/JSON/evidence validation and per-fact review semantics otherwise remain
unchanged. No facts are extracted by this analyzer, including metadata-copy facts.

Alembic `7c19ad382ea1` follows `508ac6578044`, makes the two domain columns nullable
and adds a domain-pair/review check. No historical inference is recalculated or
relabeled. PostgreSQL uses ALTER; SQLite requires a physical table rebuild while
copying every historical value unchanged. Foreign-key enforcement is disabled only
on the dedicated SQLite Alembic connection during that parent-table rebuild, then
restored and checked. Referencing facts, provenance FKs, IDs, timestamps, indexes and
idempotency keys are preserved and tested with populated Phase 2F analysis/fact rows.

Downgrade restores the old non-null contract when no abstained rows exist. If any
abstained analysis exists, downgrade fails **before changes**, leaving its revision
and history intact. It never fabricates a category or deletes an immutable result.
Retain this revision or restore a pre-Phase-2G backup to use the old schema. Both
migration directions and the blocked-downgrade case run on SQLite/PostgreSQL 16.

The Phase 2F handoff documents that release's non-null contract; this section is the
explicit Phase 2G extension. Frozen AnalysisInput/projection/SHA-256 fingerprint,
exact raw provenance, household-first locking, stale-input zero writes, immutable
history, idempotency, pending ordering and exact-current queries remain unchanged.

## Runtime rules, signals and bounded normalization

`family_os.metadata_classifier.MetadataRulesAnalyzer` implements the existing
protocol with only `AnalysisInput` and the taxonomy as inference arguments. Loading
config is separate from inference. It neither imports provider/database clients nor
reads files, DB, environment, keyring or network during `analyze`.

`config/metadata-classifier.yaml` is separate from taxonomy/threshold configuration.
Rules have an ID, strength, `when` signals and structured `prediction`. All signal
kinds present in a rule are ANDed. Supported signals:

| Signal | Matching |
| --- | --- |
| `subject_phrases_any` | Any normalized contiguous token phrase, with word boundaries |
| `subject_tokens_all` | All normalized tokens, minimum two configured tokens |
| `sender_domains_any` | Exact parsed ASCII sender domain |
| `sender_domain_suffixes_any` | Exact domain or dot-boundary subdomain; never arbitrary suffix text |
| `providers`, `record_types` | Exact persisted identifiers, as context gates |
| `metadata_equals` | Exact canonical JSON scalar equality, distinguishing booleans from numbers |
| `metadata_present` | Non-null persisted value at a fixed allowlisted field |

Allowed metadata paths are `status`, `eventType`, `start.dateTime`, `start.date`,
`end.dateTime`, `end.date`, `mimeType`, `trashed`, `removed`. No arbitrary traversal
into account/provider payloads. Recipients/owner/IDs do not supply classifier meaning.
Every rule requires a subject phrase or at least two subject tokens; provider type,
sender domain, metadata/MIME or record type alone cannot classify anything. Sender
rules are supported and tested as gates; default rules contain no sender-specific
addresses/domains or private values. Multiple/ambiguous sender addresses fail the gate.

Text uses NFKC, casefold, then NFKC; Unicode alphanumeric characters form tokens and
punctuation separates them. Whitespace and intended punctuation/case variants match
identically, without locale-dependent processing or stemming. Exact token/phrase
boundaries avoid substring guesses. Subject/title input is at most 8,192 characters;
missing/oversized titles return uncertainty/abstention rather than truncating into a
positive match. Sender input is bounded to 320 characters. No provider object ID,
internal ID, dict insertion order, filename path or random order controls meaning.

Rules-config validation is all-or-nothing: duplicate YAML keys, unknown fields,
invalid versions/IDs, duplicate rule IDs or normalized signals, invalid signal arrays,
empty signals/predictions, nonfinite or nonscalar metadata equality, unsupported
paths/signal kinds, bad taxonomy pairs and excessive sizes fail closed. Config is
limited to 64 KiB / 128 rules; arrays 1–32 entries, phrases 1–128 characters and
metadata-equality maps 1–8 allowlisted fields. There is no configured regex, eval,
exec, expression language or plugin loading.

## Effective analyzer identity

Analyzer name: `metadata_rules`. Declared ruleset: `metadata-v1`.

Effective version: `metadata-v1-e1-98b9e7219a73125b7292bd89`.

Canonical config includes normalized/sorted rules, signals, predictions, strengths,
declared version and engine version. Its SHA-256 fingerprint supplies a stable
24-hex-character suffix (96 bits). Formatting, key order, equivalent normalized
phrases and rule order do not change behavior/identity. Changing rule content changes
the effective analyzer version automatically, even without a manual declared bump,
so existing immutable analyses cannot be silently reused for edited rules. Intentional
rule changes should also bump `ruleset_version`. Engine/normalization/conflict/veto
changes must bump `ENGINE_VERSION`; rule hashing does not detect arbitrary code edits.
Declared ruleset versions are bounded to 32 characters; effective versions stay within
the Phase 2F 64-character limit. Taxonomy/threshold versions keep their Phase 2F contract.

## Predictions, scores and conflict policy

Scores are deterministic **product rule strengths**, not statistical probabilities:

| Evidence | Prediction / score |
| --- | --- |
| No matching evidence, or competing labels/pairs | uncertain or domain abstained / 0.00 |
| Only weak rules supporting one label/pair | uncertain or domain abstained / 0.55 |
| At least one strong rule and unanimous matching target | supported label/pair / 0.90 |

Scores never accumulate across duplicate/corroborating rules. All competing targets
are considered, including weak disagreement. Different domains or different children
of the same category abstain rather than taking the first/last/highest-order rule.
Each dimension resolves independently. Phase 2F thresholds (default classification
0.80) set review signals only; stricter thresholds can flag otherwise supported labels.
Uncertain labels and abstained domain always recommend review. No review routing or
threshold calibration workflow is implemented.

Default strong signals include explicit insurance renewal/expiry wording, confirmed
hotel reservations, utility bills, vehicle registration renewal due, shipped orders,
available bank statements, residential-lease PDF titles and supported promotion,
newsletter, social-notification and market-price-alert wording. Home-utility action
requires explicit payment-due/action-required words plus the literal utility/bill tokens. Calendar
vet action requires vet/veterinary appointment wording **and action/required tokens**,
Calendar provider/event type, confirmed status and a persisted start datetime. Generic
meetings or confirmed appointments alone do not imply relevance/action. A Drive PDF
MIME alone does not imply bill/policy/relevance. Weak renew/payment/expiration/appointment
language remains uncertain. Informational confirmation/shipment/statement and explicit
ignore signals may support `not_required`; silence never implies it.

Known negation/conditional/completion tokens (`no`, `not`, `never`, `maybe`, `sample`,
`example`, `cancelled`, `canceled`, `paid`, `completed`, `resolved`, `draft`, `test`,
`training`, `hypothetical`), cancelled Calendar status and trashed/removed metadata veto
positive relevance/domain/action-required rules. Ignore rules can still match. This
is a conservative lexical veto, **not general language or negation understanding**.
Sender context cannot override strong contradictory subject rules. Household relevance
is a rule inference, not proof of personal versus work ownership or canonical truth.

## Application service and aggregate-only CLI

From the repository root after migration/ingestion:

```sh
family-os analyze-metadata --household HOUSEHOLD --limit 100
python -m family_os.metadata_evaluation
```

The CLI only parses/selects local config files, invokes
`analysis_services.analyze_metadata`, and prints `selected/created/reused/stale`
aggregate counters. The service validates taxonomy and rules, constructs the analyzer
and calls bounded Phase 2F `analyze_pending`. Optional `--classification-config` /
`--rules-config` override validated local config paths. No source text, recipients,
sender, metadata, matched text/rules, facts, credentials or cursors are printed.
Errors remain safe generic CLI output. No background operation is introduced.

All persistence runs through `analyze_source` / `analyze_pending`: inference holds no
DB connection or lock, then final household → source → definition consistency → exact
analysis check → analysis/facts ordering preserves the Phase 2F first-use and stale
protections. Existing exact analyses skip inference; changed rule identity creates
new history. Records are never hidden/deleted, even when confidently irrelevant.

## Synthetic evaluation and limitations

`fixtures/metadata-classifier.synthetic.json` supplies 30 synthetic minimized inputs
and explicit expected labels spanning Gmail, Outlook, Calendar and Drive, all eight
taxonomy domains, clear positives/ignore cases, unsupported cases, conflicts, generic
meetings/PDFs, missing fields, vetoes and normalization variants. Fixtures do not
supply bodies/file contents or labels requiring them. Unsupported but positively
labeled travel/membership/service cases deliberately remain misses; coverage is not
forced to 100%. The harness calls the exact same config parser, analyzer, normalizer,
score calculation and output validator as runtime, with no DB/provider calls.

Current synthetic summary:

- 30 cases; domain coverage **14/30 = 46.7%**, abstention **16/30 = 53.3%**.
- Relevance accuracy on labeled non-ambiguous cases: **15/18 = 83.3%**.
- Domain accuracy among non-abstained predictions: **14/14 = 100%**.
- Action accuracy on labeled non-ambiguous cases: **12/14 = 85.7%**.
- Confident false-positive counts: relevant **0**, irrelevant **0**, action-required **0**.

Confident false positives include unsupported/uncertain expected labels when a
contradicting definite prediction crosses the corresponding Phase 2F threshold.
Per-domain support reports labeled/predicted case counts:

| Category | Labeled | Predicted |
| --- | ---: | ---: |
| household_admin | 2 | 1 |
| travel | 3 | 2 |
| home | 3 | 3 |
| vehicle | 2 | 1 |
| pet | 1 | 1 |
| purchase | 1 | 1 |
| finance_reference | 1 | 1 |
| ignore | 4 | 4 |

These are **synthetic test metrics, not production-quality claims**. Selective 14-case
accuracy does not establish recall, real-world precision or statistical calibration.
Rules are a small mostly English baseline. Titles can be misleading; they cannot
establish canonical dates, ownership, deadlines or content facts. Missing/redacted
metadata and unavailable bodies/files constrain what can be inferred. Real-data
local evaluation/review and a structured-extraction/content-boundary decision should
precede canonical dedupe; real household data is not committed or accessed here.
Structured extraction and broader threshold/review product behavior remain unchecked.

## Validation evidence

Python 3.12.14 validation:

- Full SQLite suite: **941 passed** (828 existing tests + 113 Phase 2G tests).
- Full real PostgreSQL 16 suite: **941 passed**, using disposable per-test schemas.
- Alembic upgrade/downgrade/upgrade and schema checks pass on both databases,
  including populated Phase 2F analysis/facts and non-destructive blocked downgrade.
- `pip check`: no broken requirements; `git diff --check`: clean.
- Synthetic evaluation: deterministic 30-case summary above, using the runtime engine.
- Direct weak-only relevance/action/domain regressions enforce semantic abstention
  at 0.55 and review after validation. Weak plus strong unanimous targets remain
  concrete at 0.90; weak/strong disagreements abstain at 0.0. The four default weak
  attention examples persist uncertain labels, null/null domain and review.

Existing CI runs the full suites on Python 3.12 / SQLite and PostgreSQL 16; final
CI status is recorded in the PR description. All automated provider clients,
analyzer inputs and evaluation data are synthetic. Zero external data egress.

## Exact ChatGPT review questions

1. Does explicit null/null domain abstention force review, reject half-null pairs and
   preserve existing classified analysis/fact provenance across both migration directions?
2. Is blocked downgrade with abstained rows the correct history-preserving behavior,
   including SQLite's necessary physical rebuild and restored foreign-key enforcement?
3. Do strict config parsing, normalization and content-sensitive effective versions
   prevent silent rule edits or order-dependent semantic behavior?
4. Are default strong rules narrow enough, with adequate ambiguity/conflict/veto
   handling and no automatic classification from provider type, MIME or object IDs?
5. Are action-required and informational/ignore scores conservative product strengths,
   without claiming calibrated probabilities or creating tasks/canonical/review state?
6. Does the runtime service/aggregate CLI preserve all Phase 2F idempotency, household
   serialization, stale-input, history/current and privacy contracts?
7. Does the synthetic harness evaluate the exact runtime engine, with honest coverage,
   missing-support cases and metrics that cannot be mistaken for real production quality?
8. Are zero egress, missing-content limitations, deferred extraction/model/content/API/UI
   boundaries and the next evaluation/review step explicit enough for this baseline?
