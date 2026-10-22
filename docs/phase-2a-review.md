# Phase 2A review: Gmail read-only (Issue #2)

## Scope and decisions

This PR implements only [Issue #2](https://github.com/samas-saigo/family-os/issues/2).
The issue had no comments when read. README, AGENTS.md, architecture, data-model,
dedupe, security, and roadmap documents were read before implementation. Issue #2
explicitly authorizes the Gmail adapter beyond AGENTS.md's older Phase 1 scope;
architecture documents are preserved. The attached unfinished patch was reviewed
and applied on current main (`c1e50fa`), then completed and validated.

- Gmail/auth types stay in the connector boundary. The existing `Connector`,
  `RawRecord`, and `NormalizedRecord` contracts suffice: this adapter never fetches
  bodies, so no transient-body domain extension or migration is needed.
- Fixed GET endpoints use Google's authorized requests session; no discovery SDK,
  write API, attachment endpoint, web framework, scheduler, or background service.
- Initial query is connector configuration (CLI `--query`), defaulting to
  `newer_than:365d -in:spam -in:trash`. History is mailbox-wide after that baseline;
  the initial query is not a permanent relevance/retention filter.
- Account identity must be registered explicitly before OAuth. Profile matching
  happens before saving credentials and before every fetched page. Accounts are
  distinct from people; second-person accounts, spouses, shared and unknown owners
  use the existing registry model.
- Application-level household duplicate guard checks the final registry state.
  Household upsert serializes registry writers on SQLite/PostgreSQL; account reads
  and the ingestion transaction recheck the guard/configuration. Gmail/Googlemail
  dots/plus aliases normalize together; Workspace aliases are not inferred.
  No duplicate override is offered. Direct DB writes can bypass registration;
  this is a local tool, not a database-enforced hosted authorization model.

## Persisted and excluded data

Persisted raw snapshots allowlist message/thread/history IDs, internal timestamp,
label IDs, size estimate, selected safe headers (From, To, Cc, Bcc, Subject, Date,
Message-ID, In-Reply-To, References), and attachment filename/MIME type/size/ID.
Normalized records retain identity, timestamp, sender/recipients/subject, minimized
metadata, and raw snapshot linkage. Earlier metadata versions remain attributable
to their source account. Account + provider object ID idempotency does not merge
canonical entities or collapse different accounts.

Excluded: bodies/plain text/HTML, Gmail snippets, attachment bytes, arbitrary
headers/provider fields, and credentials. Message HTTP projections exclude snippet
and body.data at every requested MIME level; history projections request only
changed message IDs and cursor fields. A second allowlist excludes unexpected
fields from fake/full responses before domain/storage. `content_hash` is null,
never a subject/snippet hash. The raw payload hash fingerprints minimized metadata
for versioning, not message body content. Subjects/addresses/filenames can themselves
be private; metadata storage still needs encrypted media and controlled backups.

## OAuth/token storage and errors

Only `gmail.readonly` is requested and additional/missing granted scopes are
rejected. User-triggered Desktop OAuth uses an external client JSON and loopback
callback. Tokens and necessary OAuth credential configuration reside in an OS
keyring entry keyed by household/account; refreshes save back there. Windows,
macOS, Secret Service/libsecret/KWallet backends are allowlisted; plaintext/null/
chainer backends fail closed with no fallback. Keyring/Google exceptions and
response bodies are not printed. Private synchronous I/O temporarily suppresses
process logging (including OAuth redirect/token diagnostics) and restores its
previous state. The CLI intentionally displays the authenticated mailbox identity
before ingestion; remaining output is aggregate counts and safe categories.

## Cursor semantics and recovery

Versioned JSON binds household, account, normalized mailbox, and initial query.
The initial cursor saves a pre-list profile history baseline and list page token.
The final list page transitions to history and immediately drains changes since
that baseline. History pagination retains its original start ID until the last
page commits the returned tip. Page records/raw snapshots/cursor commit together
under the existing optimistic version guard. Fetch/normalization/database failures
leave the failed page untouched; previous successful pages remain durable.

Expired/invalid history (HTTP 400/404), rejected list page tokens, malformed/bound
cursor state, changed queries, backward tips, or repeated tokens raise controlled
`ResyncRequiredError`. Nothing silently skips to now. [Setup/recovery](gmail.md)
documents an explicit cursor-only reset with version increment after stopping
writers and making a protected backup; re-listing retains all existing records.

## Limitations

- No real mailbox, OAuth flow, or native keyring was exercised. Provider field
  syntax and projection semantics are checked synthetically; the live opt-in smoke
  procedure is documented in gmail.md and intentionally remains unperformed.
- MIME projection supports 16 nested child levels. A deeper-part sentinel rejects
  the page instead of silently dropping attachment metadata.
- Message-fetch 404 preserves prior provenance. TRASH labels can be retained when
  messages remain readable. Deletion tombstones/canonical lifecycle are deferred.
- Initial search pagination depends on Gmail's changing result set; history catch-up
  closes the change race but cannot reconstruct expired history or deleted content.
  Controlled bounded resync does not guarantee complete historical reconstruction.
- No account revocation command, database encryption, hosted authorization, or
  threaded scheduler. Logging suppression assumes this synchronous local process.
- No classification, structured extraction, UI, canonical dedupe, provider writes,
  calendar/tasks, Finance behavior, or other provider adapters.

## Acceptance evidence

`tests/test_gmail.py` covers the connector/domain contract, same-person multiple
mailboxes, spouses/shared/unknown owners, profile mismatch, duplicate aliases and
registration rollback, disabled-account retention, initial replay/pagination and
baseline transition, new/repeated history, label/subject/attachment metadata
updates with retained raw versions, resumed history pagination, invalid history
and cursor/query binding, atomic rate-limit/transient/provider failures, body/
snippet/attachment exclusion, attachment metadata, safe errors/logging, HTTP read
endpoints/projections, and MIME depth failure. `tests/test_gmail_auth.py` covers
fake OAuth/read-only scopes, missing registration versus authentication errors,
wrong mailbox, external client config, account-scoped
keyring/load/refresh, unsafe-backend rejection, log suppression, and CLI identity
before aggregate output. Existing migrations, ingestion, registry, fixture, CLI,
and PostgreSQL DDL tests remain in the full suite. Persistence-boundary tests
reject top-level/nested snippets in raw and normalized metadata, including mixed
case keys, without changing records or cursors.

Validation: Python 3.12.14; full SQLite and real PostgreSQL 16 suites each pass
**98 tests**. `pip check` reports no broken requirements; `git diff --check` passes.
CI runs the same suites on Python 3.12 with a PostgreSQL 16 service. CI status must
be checked on the PR before merge. No live OAuth or mailbox access was initiated.

## Ownership-attribution review fix

The latest ChatGPT review identified explicit-owner reassignment during registry
reload as a blocker. The general source-account registry now permits unknown ->
person/household resolution and idempotent reloads, while rejecting person ->
other person, person -> household, household -> person, and explicit -> unknown.
Enable/disable remains independent. Rejected registry reloads roll back all
changes; existing raw/normalized history and sync cursors remain untouched.
Ten synthetic transition cases in `tests/test_registry.py` verify the owner fields,
`person_owner_id`, transactional rollback, enabled toggles, and historical retention
on both database backends. No provider-specific behavior or migrations were added.

## Exact questions for ChatGPT review

1. Does the diff against main satisfy every Issue #2 acceptance criterion while
   staying out of classification, canonical lifecycle/dedupe, UI, and Gmail writes?
2. Can any mailbox mismatch, duplicate alias registration, owner configuration
   change, or concurrent sync attach Gmail records to the wrong source account?
   Are the application-level duplicate guard and Workspace alias limits acceptable?
3. Do pre-list history capture, list-to-history catch-up, resumed history start IDs,
   final tip advancement, and transactional failures avoid silently skipping changes?
   Is the explicit bounded resync procedure sufficiently controlled?
4. Can body/snippet/attachment bytes or OAuth/private provider errors reach raw
   payloads, normalized metadata, repr, logs, or CLI output through these boundaries?
   Is the MIME sentinel/projection and null body hash policy correct?
5. Are the OS backend allowlist, account-scoped keyring entries, refresh persistence,
   scope validation, external client-file rule, and synchronous logging suppression
   adequate for this local phase? Which native-platform checks remain necessary?
6. Are mailbox-wide incremental changes after a bounded initial search, retained
   disappearance provenance, and the documented historical reconstruction limits
   acceptable Phase 2A behavior, or does the issue require a narrower policy?

Do not merge until this review and both CI database jobs pass.
