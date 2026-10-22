# Phase 1 review handoff

## Scope and acceptance

Implements the kickoff instructions from the shared ChatGPT discussion:
provider-independent read-only ingestion infrastructure, without real Gmail,
Outlook, Calendar, Drive, or Finance connectors. No AI classification, canonical
entity merging, review UI, dashboard, or external write actions.

Implemented:
- Python package and command line tools; SQLAlchemy Core rather than an ORM/service stack.
- Alembic upgrade/downgrade migration, SQLite local development, PostgreSQL JSONB/timestamps.
- Household/person/account registry with person, shared-household, and unresolved owners.
- Connector protocol with one-page fetch and normalization; source account enumeration
  belongs to the registry, not to a provider's authentication implementation.
- Offline synthetic fixture adapter, paginated ingestion, persisted per-account cursors.
- Raw metadata snapshots separate from normalized source records.
- Idempotency by source account plus provider object ID; changed payloads retain raw history.
- Record, source-account, provider/thread identity, raw snapshot link, timestamps,
  recipients, and content checksum preserved for future provenance/extraction.
- Transactional page persistence: raw data, normalized records, and cursor commit together.
- Optimistic cursor version prevents an older concurrent fetch from advancing sync state.
- Aggregate logging and safe errors, without provider payloads, tokens, or exception text.
- Tests and SQLite/PostgreSQL GitHub Actions jobs.
- AGENTS.md with architectural invariants and feature-branch conventions.

## Issues found before implementation

1. The starter schema can associate an account with a person in another household;
   its polymorphic owner is not validated by database constraints.
2. Source records do not guarantee their account belongs to the same household.
3. Raw metadata alone does not model provider object versions or separate storage.
4. There is no synchronization cursor or migration history.
5. The starter is documentation, not a runnable application.

The implementation adds ownership/household constraints, raw snapshots, and sync
state to address these gaps. It preserves the architecture documents and starter
schema without silently rewriting them. Only Phase 1 tables are migrated;
future canonical tables remain design references until those phases are implemented.

## Design decisions

- Local SQLite minimizes setup; dialect-specific upserts stay inside storage code.
- IDs are globally unique within one database, consistent with starter primary keys.
- Adding accounts uses registry configuration; no per-person mailbox assumption.
- An account's household/provider/external identity is immutable, preventing accidental
  reuse of a saved cursor for another mailbox. Registry reload does not delete accounts
  or reset sync state. Use `enabled: false` to disable an account.
- An unchanged repeated provider object preserves normalized ID and timestamps.
  A changed object updates its normalized representation and links its new raw snapshot;
  all earlier raw versions remain available. This is ingestion dedupe, not entity dedupe.
- Source content hashes are future match signals; identical hashes never collapse
  records from different accounts. Empty content has no hash.
- Connector APIs contain no writes or authentication implementation. Future adapters
  must obtain credentials externally, request read-only scopes, bound fetch pages,
  handle rate limits, and report invalid cursors instead of silently skipping changes.
- Each successful page is durable. If a later page fails or the page limit is reached,
  resume from the last committed cursor. A failed page advances nothing.
- Batch cursor concurrency is protected; production registry/sync coordination and
  distributed scheduling are outside this single-user foundation.

## Privacy and operational limits

This is a synthetic local development foundation. The local SQLite database is
**not encrypted by this application**. Configure and verify encrypted storage,
backup/retention policy, and appropriate access controls before any real household
ingestion. No real accounts, tokens, or household messages have been ingested.

Adapters must provide a minimized metadata payload. The ingestion boundary rejects
common credential and full-body keys recursively. That check is an extra guard,
not a complete secret detector; adapters must allowlist metadata deliberately.
Full email bodies and attachment contents are not persisted by default. Normalizers
may hash content transiently. Metadata snapshots support metadata reprocessing;
future body extraction needs provider re-fetch or a separately approved encrypted
retention mechanism. Fixture normalization does not hash its subject as if it were
a full message body.

Logging omits household identifiers and exception text. The CLI exposes only aggregate
counts in `status`. These choices limit debugging detail; future adapters should
provide safe structured error codes. There is no hosted API, user authentication,
row-level security, secret manager, or production deployment in this delivery.

## Verification

- 26 tests pass locally on SQLite, including requested duplicate-ingestion,
  multi-account-person, and household-owned account cases.
- Additional coverage: raw-version history, transactional failures, wrong household,
  disabled/wrong-provider accounts, stale cursors, pagination/restart, privacy guards,
  migrations up/down/up, schema drift check, offline PostgreSQL DDL generation, and CLI.
- Real PostgreSQL runtime has not been tested locally: no PostgreSQL server or Docker
  is installed. A GitHub CI service runs the complete suite against PostgreSQL 16
  once the branch is pushed. This check must pass before merging.

## Review requested from ChatGPT

Review the diff from `main` to `phase-1-ingestion`, especially household boundaries,
idempotency, raw/normalized separation, cursors, metadata retention, migration
reversibility, and whether the implementation stays within Phase 1. Do not treat
the local test result as proof of live provider integration or production security.

Suggested next issue after review: implement one Gmail read-only adapter using
the existing connector protocol, with explicit OAuth/storage and body-retention
decisions. Do not bundle classification or dashboard work into that PR.

## GitHub handoff

The starter is committed on `main`; implementation uses `phase-1-ingestion` with
focused commits. Local commits use the agent identity `Codex <codex@openai.com>`
because no user Git identity was configured; global Git configuration is unchanged.

The collaboration repository is `https://github.com/samas-saigo/family-os`.
The starter architecture is published on `main`; Phase 1 changes are proposed
from `phase-1-ingestion`. The repository is currently public and contains code
and synthetic examples only. Household data and credentials remain excluded.
Do not merge until ChatGPT review and PostgreSQL CI pass.
