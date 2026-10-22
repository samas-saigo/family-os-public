# Phase 2F review — versioned source-analysis foundation

Closes Issue #14. This is infrastructure for probabilistic source classification and
structured proposals, **not production AI**. An analysis is a versioned inference
about one exact source snapshot. It is not canonical household truth. Deterministic
analyzers exist only in synthetic tests. No SDK/model provider, HTTP inference,
content access, new OAuth scope, CLI command, worker, API or UI is added. All merged
Gmail/Outlook/Calendar/Drive scopes, privacy, cursors and behavior are unchanged.

## Executable schema and exact provenance

Alembic revision `508ac6578044` follows `a08cf2190da9`. `db/schema.sql` remains a
future canonical design reference, not executable migration authority.

`source_analysis` records household/account/stable source ID/exact raw ID/provider
object ID, analyzer name/version, taxonomy version, threshold-policy version, SHA-256
input and definition fingerprints, relevance/domain/action labels and confidences,
review recommendation and UTC creation time. There is no reasoning/prompt/response
column. Composite FKs bind source and raw to **the same household, account and
provider object**. Parent identity indexes are added without rewriting source rows.
Deletion of referenced source/raw provenance is rejected, not cascaded. Updating a
source's current raw pointer never changes its historical analyses.

The DB unique contract is `(source_record_id, raw_record_id, analyzer_name,
analyzer_version, taxonomy_version, threshold_policy_version)`. Idempotent calls
return the existing result without invoking the analyzer. Deliberate reprocessing
requires a new analyzer/config version; no UPDATE/overwrite path is exposed.
Definition consistency is household-scoped: one declared analyzer/taxonomy/threshold
version tuple must map to only one definition fingerprint, including concurrent
first use on different sources. A definition fingerprint detects changed
taxonomy/threshold contents with reused versions within a household; version identity
is also a caller responsibility for changes to analyzer implementation. Changed input projection under an existing
exact key fails closed rather than relabeling an old artifact.

`analysis_fact` stores zero or more proposals with JSON/JSONB values, confidence,
evidence refs, deterministic zero-based ordinal, review recommendation and UTC time.
Repeated names are supported; uniqueness is `(analysis_id, ordinal)`. Its composite
FK binds the analysis, household and stable source. SQL checks enforce labels,
confidence ranges and nonnegative ordinals; application validation rejects nonfinite
numbers before SQL. Analysis history and pending lookup have dedicated indexes;
the unique definition index supports exact-snapshot anti-join/idempotency queries.

Immutability is enforced by append-only application operations, uniqueness and
provenance foreign keys, not SQL UPDATE/DELETE triggers or database roles. A trusted
local administrator can alter the DB outside these operations; that is not an
analyzer/client capability. Downgrading intentionally removes derived tables,
leaving existing ingestion rows unchanged. Upgrade, downgrade to the previous
revision, full downgrade to base and upgrade again are tested on both DBs.

## Frozen input and deterministic fingerprint

`family_os.analysis.AnalysisInput` contains only persisted source/raw IDs, provider,
source owner type/ID, record type, provider object ID, occurred_at, subject, sender,
recipients and minimized normalized `raw_metadata`. It does not read raw payload,
account configuration, secure credentials or sync state. No provider network call
is made. Nested mappings/sequences are defensively copied and deeply frozen.
Source text/metadata are omitted from the object's repr.

Fingerprinting uses compact UTF-8 canonical JSON, sorted object keys, preserved
array order and SHA-256. Datetimes become UTC with six fractional digits and `Z`;
SQLite's naive persisted timestamps are interpreted as UTC. Integral JSON floats
normalize to integers, so SQLite/JSONB numeric representation does not change a
logical input fingerprint. Non-JSON values, NaN/Infinity, NUL/surrogate strings and
out-of-range integers are rejected. The projection includes snapshot ID and owner;
any changed projection changes the fingerprint. It supplements, never replaces,
raw-snapshot provenance. A fixed canonical fixture runs in both database suites.

Input is bounded to 1 MiB, nested JSON to depth 32 and each mapping/array to 10,000
entries. These bounds fail closed; oversized source input is not silently truncated.

## Analyzer and validation contract

The small neutral `Analyzer` protocol declares `name`, `version` and
`analyze(AnalysisInput, ClassificationPolicy) -> AnalysisOutput`. It depends on no
CLI, HTTP, connector or model SDK. Frozen output/fact value objects are accepted;
dict-shaped or arbitrary SDK responses are rejected. The taxonomy is deeply frozen.

Output validation occurs before persistence:

- Relevance: `relevant`, `irrelevant`, `uncertain`.
- Action: `required`, `not_required`, `uncertain`.
- Category and required subcategory must exist together in the taxonomy. Missing or
  invalid categories fail validation, rather than being persisted for review.
- Confidence is finite numeric `[0,1]`; booleans and numeric strings are rejected.
- At most 100 facts; names match `[a-z][a-z0-9_]{0,63}` and reject reserved sensitive
  names. Values are JSON-safe, at most 16 KiB each, and reject structured credential,
  cursor, provider-client, body/content, prompt and reasoning envelopes recursively.
- Evidence refs are validated as described below. All rows commit atomically.

Reserved-key checks are defense against structured state, not a general secret/DLP
classifier for opaque strings. Callers must never supply secrets or narrative
reasoning as fact values. Future adapters need explicit egress/result policies;
these checks do not authorize arbitrary provider payload persistence. Unexpected
analyzer/persistence failures use fixed safe errors without private exception text.

## Evidence references

Each fact requires 1–32 unique reference strings, each 1–256 characters and at most
8 dot-separated components. Allowed roots are `subject`, `sender`, `occurred_at`,
`recipients`, `record_type`, `raw_metadata`. Components are ASCII identifiers
`[A-Za-z_][A-Za-z0-9_]*` or zero-based decimal array indexes (no leading zeros).
Examples: `subject`, `sender`, `raw_metadata.start.dateTime`,
`raw_metadata.mimeType`, `recipients.0`, `raw_metadata.items.0.name`.

Every path must resolve to a non-null field/value in this exact immutable input.
URLs, empty/unresolved paths, out-of-range indexes and credential/cursor/keyring
components are rejected. Evidence is a reference, not copied free-form text. Entire
allowed fields may be referenced; no evidence values are duplicated in fact rows.

## Versioned taxonomy and review-only thresholds

`config/classification.yaml` declares `family-os-taxonomy-v1` and
`family-os-thresholds-v1`. All eight original categories and all subcategories are
preserved. `finance_reference` is notices/references only; Finance remains the
financial source of truth. The former unversioned `required_outputs` wish list is
replaced by the explicit label contract plus optional fact proposals; optional
people/assets/dates/organizations are not fabricated as required outputs.

Strict config loading rejects duplicate/unknown keys, malformed versions, invalid
names, duplicate/empty child lists and invalid thresholds. Version identifiers use
`[A-Za-z0-9][A-Za-z0-9_.-]{0,63}`. Acceptance thresholds are relevance/domain/action
0.80 and fact 0.90. A score equal to its threshold is accepted. Version the taxonomy
or threshold policy when changing it; do not rewrite historical results.

An uncertain relevance/action label or low required classification confidence flags
that analysis. Low fact confidence flags **only that fact**, not otherwise confident
classification, matching Issue #14's per-fact acceptance criterion. Neither signal
creates a review queue, task, entity, action, notification or hidden/deleted source.
Confidently irrelevant sources and their history remain fully stored/provenanced.
Actual classifiers/extraction/confidence-threshold product behavior stay unchecked
on the roadmap. The next step is implementing and evaluating a real classifier or
extractor against this foundation and the minimized input actually available.

## Callable services, stale protection and current views

`family_os.analysis_services` exposes:

- `analyze_source(engine, household_id, source_record_id, analyzer, policy)`.
- `analyze_pending(engine, household_id, analyzer, policy, limit=positive_integer)`.
- `analysis_history(engine, household_id, source_record_id)`.
- `current_analysis(..., analyzer_name=..., analyzer_version=..., policy=...)`.

The trusted local caller supplies household context; these are not authenticated
HTTP endpoints. There is no scheduler or production reference analyzer. Disabled
source accounts' already-persisted records remain analyzable; analysis does not load
credentials or initiate ingestion. Services return frozen classification/provenance
summaries, a reuse flag, or aggregate batch counts. They never return source content,
raw metadata, clients, credentials, tokens, cursors or raw analyzer responses.

Analyze-one captures the current source/raw projection, fingerprints it and checks
for an exact existing result, then releases the read connection **before inference**.
After validation, PostgreSQL briefly serializes final definition registration/checking
by locking the requested household row with `SELECT FOR UPDATE`, then re-reading and
locking the current source row. SQLite retains its single `BEGIN IMMEDIATE` writer
reservation before reading; it does not need an additional household lock.

The consistent final transaction order is: household lock / SQLite writer reservation,
current source validation/lock, definition consistency check, exact-analysis existence
check, analysis insert, fact inserts. Keep this order to avoid future lock-order
inversions. Inference holds neither a connection nor the household lock. A waiting
PostgreSQL transaction checks the first transaction's committed definition after
acquiring the household lock, so the same declared versions cannot acquire different
definition fingerprints under concurrent first use. An incompatible attempt raises
`AnalysisDefinitionConflictError` and writes zero analysis/fact rows. Matching
fingerprints may still analyze different source records successfully.

The raw ID and full input fingerprint must still match. This protects both the
read-to-inference race and an ingestion update between final validation and commit.
If changed/deleted, `StaleAnalysisInputError` writes zero analysis/fact rows for the
attempt and requests an explicit retry. Concurrent duplicates serialize on this
source and return the same immutable winner; DB conflict handling additionally
resolves the exact uniqueness key safely. No long inference transaction is held.

Pending analysis collects at most the caller's limit of missing **current** snapshot
keys in stable source-ID order, once per call. No endless retry loop. Each record
commits independently; stale/deleted candidates are counted once, and other failures
abort with earlier successful commits retained. Already analyzed current keys are
skipped. New raw snapshots are pending again. Results are aggregate counters only.

History includes all snapshots/definitions in `(created_at, id)` order. That order
is for browsing, not choosing current truth. Current lookup requires the source's
current raw ID and exact requested analyzer/taxonomy/threshold definition; a newer
historical result or different analyzer version cannot substitute for it.

## Future external-model boundary and deferred work

This PR performs no external inference. A future AI vendor/local-model production
adapter is a separate architecture/security decision. Provider OAuth consent does
**not** authorize sending household metadata to an AI vendor. The future adapter
must explicitly declare which persisted fields leave Family OS and define appropriate
consent/authorization, retention and safe error boundaries. Do not persist
chain-of-thought, full prompts/transcripts or raw model responses by default.
Validated structured result, version, confidence and evidence refs form the durable
analysis artifact.

Email bodies, Outlook previews, Drive contents/export, OCR/attachments, production
models/training, prompt management, canonical entities/dedupe, review queue/UI,
tasks/actions/provider writes, API/auth/background workers, web/mobile UI and Finance
ingestion/reconciliation remain out of scope. Existing centralized R0–R3 policy and
one-backend/multi-client credential/auth boundaries are unchanged.

## Validation evidence

Python 3.12.14 local validation:

- Full SQLite suite: **828 passed** (660 unchanged merged tests + 168 new tests).
- Full real PostgreSQL 16 suite: **828 passed**, using disposable per-test schemas.
- Both suites include Alembic schema checks, upgrade/downgrade/upgrade, preservation
  of existing source rows across the Phase 2F migration, stale-source and actual
  concurrent duplicate regression tests. Two new cross-source concurrency tests cover
  conflicting fingerprints under the same versions (one winner, one typed conflict,
  no rejected facts) and matching fingerprints (both sources succeed). The conflicting
  PostgreSQL test reproduced two commits on the pre-fix code before passing with
  household serialization; both tests run in SQLite and PostgreSQL CI.
- `pip check`: no broken requirements. `git diff --check`: clean.

Commands: `.venv/bin/python -m pytest -q` and the same command with
`TEST_DATABASE_URL` set to the disposable PostgreSQL 16 database. Existing CI runs
these complete suites on Python 3.12 with SQLite and PostgreSQL 16; final CI status
is recorded in the PR description.

Synthetic analyzers and provider fixtures only; no live OAuth, mailbox, calendar,
Drive or model access.

## Exact ChatGPT review questions

1. Do the composite FKs bind each analysis/fact to the same household, account,
   stable source and exact raw snapshot without silently cascading history?
2. Does the six-part unique definition and reuse-before-inference behavior support
   immutable reprocessing only through changed analyzer/config versions?
3. Is canonical input fingerprinting deterministic across SQLite/PostgreSQL,
   including UTC timestamps, JSONB numeric representation and frozen nested values?
4. Does strict output/evidence validation reject malformed or unsafe proposals
   atomically without persisting free-form reasoning or raw model/provider responses?
5. Does household-first locking prevent conflicting first-use fingerprints across
   different sources? Do the final source locks and raw-ID/fingerprint check prevent stale
   inference, including concurrent ingestion, while keeping inference outside DB
   transactions and returning concurrent duplicates safely?
6. Are pending selection and exact-current queries snapshot/definition-aware,
   household-scoped and bounded, rather than treating newest timestamps as truth?
7. Are analysis/fact review recommendations only signals, with no canonical,
   review-queue, task, action or source-deletion side effects?
8. Is the future external-model egress boundary explicit, with no production AI,
   content/scope expansion or change to merged provider/service behavior in this PR?
