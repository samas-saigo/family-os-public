# Family OS v0.1 / Slice 1 — disposable synthetic durable review core

## Contract before implementation

[Issue #61](https://github.com/samas-saigo/family-os/issues/61) implements only a
private persistence experiment, following [Phase 2W](phase-2w-product-workflow.md)
and the explicit-review boundaries of [Phase 2V](phase-2v-human-review-workflow.md).
Contract version: `isolated-synthetic-review-v1`. This is **not a production review
queue**, authenticated service or real-data rollout.
No household data, human labels, Holdout, provider API, OAuth or AI is an input.
Neither Phase 2U reasoning nor Phase 2V simulation is imported or executed.

### Isolated store and synthetic identity

`family_os._synthetic_review_core` has no import-time I/O or default database.
`disposable_store(synthetic_only=True)` creates its own temporary SQLite database;
it accepts no file path, URL or environment-based database selection. PostgreSQL
is test-harness-only: an explicitly supplied engine must target an empty, uniquely
named `sr61_test_<32 lowercase hex digits>` schema, with that exact search
path. Initialization rejects existing tables/views, production schemas, SQLite
engines supplied by callers and SQL logging. The harness must supply a dedicated
disposable PostgreSQL database. A live store capability and explicit synthetic opt-in
are both required to construct the core; closed capabilities cannot be reused.
Reopening the factory-owned connection preserves this experiment's ledger, not a
household database. Context exit disposes the SQLite directory or research tables.
The empty-schema check covers ordinary tables/views, not every PostgreSQL object
(such as functions or sequences). The trusted harness must create a fresh namespace.
Factory cleanup removes its four research tables and immutability function; the
harness removes the namespace. This is not general-purpose schema sanitization.

These gates prevent accidental live wiring; they are **not authorization or a
sandbox against hostile Python code, DB administrators or a dishonest test harness**.
There is no reviewer identity, household permission model or credential migration.
Existing SQLAlchemy/Alembic production metadata, migrations and database paths remain
untouched. Research tables and immutability guards use their own metadata only.

Identity is the tuple `(synthetic source-account, synthetic event, named step)`:
two fixed account surrogates, four fixed event surrogates, and `refund`, `rebooking`,
`preparation`, `attendance` steps. No names-as-identity, cross-provider dedupe,
canonical obligation, assignment, task or completion authority exists. Each observation
contains a positive synthetic snapshot counter (1–1,000), fixed specimen/status/
condition/scope enums and an allowlisted synthetic analyzer/rule/schema version stamp.
Specimens are newly authored fixed enum examples with **explicit test proposals**;
there is no classifier or interpreter. No arbitrary text/metadata can be stored.

Evidence refs are fixed identifiers `specimen.step`, `specimen.status`, and
`specimen.condition`; they resolve only within this enum-only synthetic observation.
Canonical JSON/SHA-256 binds exact identity, snapshot, evidence and proposal stamps.
A separate proposal fingerprint binds the supplied fixture suggestion, refs, condition
and scope. These fingerprints supplement original synthetic provenance, not replace it.

### Visible encounters and immutable history

Every explicit encounter persists an immutable observation and returns a visible
receipt with an opaque display token, epoch, current decision revision, exact evidence
and proposal fingerprints. Plain queries do not save a decision or renew a token.
An unchanged encounter still renews the token; earlier displays cannot submit new saves.
The token binds a displayed synthetic version; it is not reviewer authentication.
A different identity's legitimate token/fingerprints cannot authorize a save here.
Epochs, visits and decision revisions are per identity; revisions keep increasing
across epochs. The whole store allows at most 128 encounters and 128 decisions.
History is bounded and
ordered by revision, never timestamp. SQL guards reject updates/deletes of observation
and decision rows; only current-state/control rows are mutable. No cascading history
loss is permitted.

First encounter is pending. Only the latest explicit confirmed/rejected decision
matching the **current epoch and fingerprint** produces `already_reviewed`; the
card and history stay visible. Uncertain, invalid, unsupported, deferred and
needs-information cases remain unresolved. Any evidence, snapshot, status, condition,
scope or definition change opens a new epoch. Change then revert opens yet another;
historical agreement never revives. Older snapshot counters are rejected. Distinct
steps/accounts/events never transfer dispositions or globally clear an event.

### Explicit save, CAS and duplicate delivery

Commands have an exact field set: identity, receipt token, expected revision, epoch,
evidence/proposal fingerprints, disposition, `confirmation='save'`, and a bounded
synthetic request ID. Only `human_confirmed`, `human_rejected`,
`needs_more_information`, and `deferred` exist. Concrete resolution requires a
supported, valid, unambiguous fixture proposal for that named step. Confirming a
Not Required proposal is not completion, task closure or external approval.
Unknown fields, auto-save/close/task/permission commands and forged tokens fail closed.

A short final transaction reserves SQLite's writer with `BEGIN IMMEDIATE`, or locks
one dedicated research control row on PostgreSQL. Ordering is control lock, request
lookup, current identity/receipt/revision validation, immutable insert, state/control
update. Global serialization is deliberate for this small bounded prototype; it also
protects first use across independent source records. No human input or inference
occurs under a lock. No process-local mutex or unbounded retry exists.

The request ID is unique across the disposable store. Identical canonical command
replay returns the original immutable result without writes, even after newer evidence;
its `applies_to_current` flag is recomputed and cannot revive approval. Reusing that
ID with any different command is an idempotency conflict. A correction requires a
new request ID, fresh current receipt and expected revision, and appends a revision.
Two new saves with the same displayed revision cannot both succeed. This is request
idempotency, not semantic task/obligation identity. Failed inserts roll back all
observation/decision/state/control changes. Exceptions explicitly roll back on the
open connection before propagating; a cleanup failure cannot replace the primary
error or expose its text. Connection close remains a cleanup fallback. Successful
write transactions still commit once. Errors are typed and content-free.

## Verification, privacy and limits

Run only the opt-in synthetic test file; normal output is aggregate pytest counts:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_review_core.py
```

The PostgreSQL harness uses `TEST_DATABASE_URL` for a dedicated disposable test DB
and creates/drops a unique research schema. The new module never reads that variable
or `DATABASE_URL`. Existing full SQLite/PostgreSQL CI remains unchanged and runs the
retained regression suite too; no live model/provider inference is part of validation.
No new persistent fixture, prompt, corpus, pin, threshold or production schema changes.
Tests introduce only new English synthetic enums/cases and never read frozen fixtures.

Known limits: single synthetic operator, bounded global transaction serialization,
no UI/CLI/API/auth, no expiry-by-clock policy (staleness is receipt/version based), no
real source ingestion, quality-audit labels, tasks, canonical truth or external writes.
The process owns disposable storage; crash cleanup and adversarial-admin tamper resistance
are not production guarantees. Counts establish transaction regressions, not classifier
quality, usability or reduced human workload. Only after separate approval could a
synthetic UI follow; real-record access requires a new explicit privacy/security gate.

## Validation evidence

141 synthetic acceptance tests (123 original plus 18 review regressions) cover the
store gates, all dispositions, immutable provenance, changed/reverted evidence, receipt/revision staleness,
concurrent independent sources, duplicate delivery/corrections, resource limits,
SQL history guards, rollback and reconnection. Review regressions include cross-identity
receipt replay, explicit rollback/error propagation, and concurrent encounter/decision
capacity boundaries: at 127, exactly one of two independent writers reaches 128.
The complete suite is 2,611 tests: 2,470 retained tests plus 141 core tests.
Full local SQLite and dedicated real PostgreSQL 16 suites each passed all 2,611;
`pip check`, relative-link checks and
`git diff --check` passed. New tests read no frozen dataset or household metadata.
Existing Phase 2V isolation tests remain unchanged and pass alongside the new core.
GitHub run/job links and final head SHA are recorded in the PR after CI completion.

## ChatGPT / human review questions

1. Can any default construction, input field or store path accidentally reach live data?
2. Are original observations and decisions immutable and identity/step scoped?
3. Do changed/reverted evidence and stale receipts reject reuse without hiding cards?
4. Are concurrent first use, save/CAS, request replay and correction atomic on both DBs?
5. Can invalid/uncertain/unsupported input ever gain resolution or task/action authority?
6. Are errors/output content-free and research boundaries separate from production auth?
7. Are rollback, reconnect, limits and cleanup tested without changing production schema?
