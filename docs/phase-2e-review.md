# Phase 2E / Issue #12 review handoff

## Service boundary and scope

`family_os.services` exposes local callable application operations independently
of argparse, printing, or any UI:

| Operation | Options / purpose |
| --- | --- |
| `ingest_gmail` | Query, page size and max pages |
| `ingest_outlook` | Folder includes/excludes, page size and max pages |
| `ingest_google_calendar` | Calendar includes/excludes, page size and max pages |
| `ingest_google_drive` | Exact Shared Drive opt-ins, page size and max pages |
| `resync_google_calendar` | CalendarList (`calendar_id=None`) or one calendar stream |
| `resync_google_drive` | Personal (`drive_id=None`) or one Shared Drive stream |
| `migrate_google_drive_policy` | Complete previous/new exact-ID inclusion sets |

Callers supply and retain ownership of the database engine. Services perform
household/account lookup, existing provider/enabled/registered-identity validation,
secure client loading, provider policy and connector construction, existing
pre-ingestion identity verification, atomic ingestion, and provider cleanup.
Invalid or corrupt registration fails before secure loader/network access.
Registry duplicate guards and ingestion's account rechecks remain in place.

The CLI now parses input, delegates routine ingestion/recovery to these operations,
and presents existing safe output/errors. Explicit interactive connect stays in the
provider-specific auth functions and CLI presentation; no generic OAuth abstraction
is introduced. Registry, fixture ingestion and aggregate status remain as before.

These are callable application boundaries, **not authenticated HTTP/API endpoints**.
Passing household/account IDs does not authenticate or authorize a client. Future
Family OS client auth/authorization, scheduling, backend credentials/migration and
hosted deployment remain separate work. Centralized R0–R3 policy is unchanged.
No API framework, worker, UI, migration, provider writes, classification, canonical
entities/dedupe, review queue, notifications or Finance work is implemented.

## Result and failure contract

Ingestion returns frozen `IngestionOutcome(ingestion, verified_identity)` containing
only frozen provider-independent `IngestionResult` counters and an optional verified
operator-display identity. Gmail, Outlook and Calendar return their existing display
identities; Drive returns `None` and routine ingestion remains aggregate-only.
No SDK client, session, credential, OAuth/token data, cursor, provider response or
raw source metadata is returned. Recovery/state transformations return `None`.

Services do not print or depend on presentation callbacks. CLI success output still
places verified Gmail/Outlook/Calendar identity before aggregate JSON; Drive prints
only aggregate JSON. If ingestion fails after pre-verification, the original raised
exception receives only a `verified_identity` string so CLI can retain the identity
line on failed runs too. Exception type, message and recovery hints are preserved;
annotation failure cannot mask the primary error. No identity is attached before
verification or to Drive ingestion failures. Unexpected exception text is never
printed by CLI; its existing generic error remains. Future HTTP adapters must map
safe public categories and sanitize unexpected failures rather than expose traceback
or provider internals.

## Provider lifecycle and local recovery

After a secure loader returns a client, its service owns `client.session.close()`
in `finally`, covering successful ingestion, connector/policy errors, verification,
provider/auth errors, ingestion failures and unexpected internal exceptions.
Cleanup failures log only the existing fixed provider/category message, never
exception text, and do not replace primary failures or successful results. CLI owns
only its database engine cleanup; loaded-provider lifetime is not split across layers.

Calendar recovery delegates to the unchanged provider `recover_stream`. Drive
recovery/migration reads its secure binding through local `load_binding`, then calls
the unchanged `transform_state`. No client is loaded and no OAuth/network happens.
Provider-specific cursor validation, inclusion/binding fingerprints, target isolation,
version/CAS checks and historical retention remain exactly as before. No cursor
format is redesigned or migrated.

## Google keyring persistence

Gmail, Calendar and Drive `KeyringSession` keep the current secure serialized state
in memory when constructed. Every GET still validates exact scopes before and after
transport, serializes current state, and writes only when it differs from the last
successfully persisted state. Unchanged requests make zero writes; a refresh/change
makes one save, followed by no additional saves until another change. The comparison
snapshot advances only after secure save succeeds, so failed necessary saves raise
the safe provider auth error and leave changed state eligible for retry.

Gmail/Calendar compare their credential serialization. Drive compares the entire
connection envelope, preserving version, household, source account, normalized
registered email, stable permissionId and credentials. Serialization and keyring
exceptions are sanitized; serialized credentials are never logged, returned or
written to disk. The three native keyring services remain distinct. This is no
credential migration or new store; Outlook MSAL `has_state_changed` behavior is
unchanged. This synchronous in-memory optimization does not establish a future
thread-safe credential manager or multi-worker execution design.

## Preserved provider behavior

All provider connector/state-machine files are unchanged. Only the three Google
auth persistence paths and CLI orchestration change:

- Gmail retains exactly `gmail.readonly`, initial query/history/cursors and minimized
  headers/attachment metadata with no bodies/snippets.
- Outlook retains delegated `Mail.ReadBasic`, signed-in own-mailbox boundary,
  immutable IDs, folder policy and per-folder delta/cache behavior.
- Calendar retains its exact two readonly scopes, primary identity checks,
  CalendarList/per-calendar streams, writerWithoutPrivateAccess, recurring/cancelled
  event metadata and targeted recovery.
- Drive retains exactly `drive.metadata.readonly`, email/permission binding,
  start-token → baseline → catch-up, disjoint personal/Shared Drive observations,
  exact-ID opt-in, shortcuts/trash/removal semantics and targeted recovery/migration.

Existing privacy allowlists, null content hashes, page atomicity, opaque continuation
handling and history/provenance remain unchanged. No content/export or new scope is
introduced. Previously merged provider review/setup docs remain historical references;
this handoff records the changed-state keyring stabilization that supersedes their
older per-request persistence descriptions.

## Acceptance and validation evidence

`tests/test_services.py` exercises direct real connector/atomic ingestion with existing
fake provider clients, immutable safe outcomes, invalid household/account/provider/
identity/disabled/duplicate reads before loading, exact options and verification
ordering, cleanup on every failure stage, safe cleanup failures, original exception
preservation, local targeted recovery/history/version changes, Drive policy migration,
and CLI delegation/output/error behavior.

`tests/test_google_keyring_persistence.py` covers all three Google providers' repeated
unchanged GETs, one changed-state write followed by no redundant writes, a later
second refresh, pre/post exact-scope rejection, full Drive envelope preservation,
failed-save dirty retry, serialization safety, and distinct keyring services.
Existing Outlook cache and all provider cursor/privacy/recovery suites still run.

Python 3.12.14: **660 tests passed on SQLite and 660 on real PostgreSQL 16**.
This includes **537 merged tests unchanged plus 123 new Phase 2E tests** (95 service
and 28 Google persistence tests). `pip check` and `git diff --check` pass. Both
GitHub database CI outcomes are recorded in the PR description. Only synthetic
OAuth/provider clients and disposable databases were used; no live OAuth, mailbox,
Calendar, Drive or native keyring access was initiated. Native-platform/manual smoke
procedures remain opt-in and were not exercised.

## Exact ChatGPT review questions

1. Do the seven explicit application operations remove routine provider lifecycle,
   connector/policy/verification and recovery orchestration from CLI without creating
   a generic provider hierarchy, OAuth abstraction or backend implementation?
2. Does account lookup and provider/enabled/identity/duplicate validation always
   precede credential/network access, while retaining household ownership and atomic
   ingestion rechecks?
3. Are frozen counters plus optional verified display identity a sufficient safe
   transport-neutral result contract, with no SDK state, credentials, cursor or raw
   metadata returned? Does the failure identity annotation preserve existing CLI
   identity/error output without changing primary exception categories?
4. Is each loaded client closed on every success/failure path, with cleanup failures
   sanitized and unable to mask the primary failure or successful result?
5. Do Calendar recovery and Drive recovery/policy migration remain local, bound,
   target-specific and CAS protected, preserving history and unrelated stream state?
6. Does Google serialized-state comparison avoid unchanged writes and persist each
   refresh exactly once, including retry after failed saves, exact scope validation
   and Drive's complete binding envelope without any plaintext cache or namespace reuse?
7. Do the unchanged 537 provider tests and new service/persistence coverage demonstrate
   that scopes, privacy, cursors, Shared Drive isolation and Outlook MSAL behavior are
   preserved, with client auth/authorization and background scheduling still deferred?
