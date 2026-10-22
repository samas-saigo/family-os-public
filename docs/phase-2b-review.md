# Phase 2B review handoff — Issue #4

## Scope and permissions

Implements [Issue #4](https://github.com/samas-saigo/family-os/issues/4) on top of
merged Gmail/main (`6d08652`). The full issue had no comments when read. Current
AGENTS.md, README, architecture, data-model, dedupe, security, and roadmap were
read before implementation. Architecture documents and executable migrations are
preserved. AGENTS/README now reflect merged Gmail plus this Outlook phase.

Only delegated `https://graph.microsoft.com/Mail.ReadBasic` is requested through
MSAL PublicClientApplication. MSAL manages protocol openid/profile/offline_access;
returned resource scopes are checked and broader/shared/write/send permissions
are rejected. No client secret argument or credential is accepted. No User.Read
or `/me` profile lookup is needed: identity comes from the signed-in MSAL account.
Personal Microsoft and work/school accounts are supported subject to app audience,
consent, and tenant policy. This is the signed-in own mailbox only; delegated/
shared Exchange mailbox access is deferred.

## Identity and secure cache binding

`external_account` must be explicitly registered before OAuth. Outlook identity
is the trimmed, case-folded MSAL sign-in username, without Gmail alias rewriting,
dot/plus stripping, or guessing preferred mail aliases/work UPNs. The interactive
command displays the signed-in username **before** verifying and storing any
binding. Wrong accounts save nothing. General merged ownership rules remain:
unknown may resolve once; explicit person/household ownership is immutable.

Enabled Outlook registrations in a household must have distinct normalized
`outlook_identity(external_account)` values. The application-level guard checks
final registry state under the existing household-upsert serialization, allowing
an old account to be disabled and its replacement enabled in one transaction.
Outlook account reads recheck the same household/provider-scoped invariant, so
direct database corruption blocks reads and ingestion before provider I/O. Gmail's
guard is unchanged; identical email strings across Gmail/Outlook or different
households remain allowed. No alias/UPN equivalence beyond trim/case-folding is
inferred. No new database constraint or migration is introduced.

The OS keyring payload is scoped by JSON household/account pair under a distinct
Outlook service and contains serialized MSAL cache, stable home_account_id,
username, client ID, authority, and household/account binding. It never enters
YAML, databases, logs, or plaintext cache files. The existing secure-backend
policy is reused without changing Gmail implementation/service. Plaintext/null/
chainer/failing backends have no fallback. Loading never initiates interactive
OAuth; every Graph request silently acquires for the exact bound account, checks
cached identity and any returned identity claims, and rejects switches/ambiguity.
Changed cache is securely persisted before Graph I/O; failed saves keep the cache
dirty and fail the page. OAuth/Graph library logging is suppressed only during
synchronous private I/O, reusing the merged privacy decorator.

## Folder policy and cursor design

Graph folder discovery traverses paginated visible root/child folders. Well-known
IDs identify excluded folders regardless of localized names: Junk, Deleted,
Drafts, Outbox, Sent, and identifiable sync/failure folders. Excluded/hidden
subtrees stay excluded. Inbox/Archive/custom normal folders are included by
default. Per-account CLI connector configuration accepts explicit include/exclude
IDs or supported well-known names; explicit include can opt in to Sent, and
explicit exclude wins. No folder display-name heuristics are used.

One schema-v1 JSON cursor binds household, account ID, normalized username,
SHA-256 home-ID/client-ID/authority fingerprint, folder-policy fingerprint, and
per-folder ID/display name/active flag/link kind/link plus pending queue. Actual
stable MSAL identity remains in keyring. The ingestion layer sees only its opaque
cursor string and existing plain domain records. Policy/binding changes require
controlled resync rather than silently resetting streams.

Each batch processes one folder delta page through the existing transactional
records + cursor + optimistic-version commit. Exact nextLink is retained while
paging and exact deltaLink after completion. No token is decoded/reconstructed.
Continuation routing is validated against public HTTPS Graph v1.0 `/me` and the
exact folder stream/listing path, accepting equivalent percent-encoded/OData
folder routes. Other hosts, userinfo, ports, fragments, wrong
folders/accounts/API versions, duplicate/unsafe query fields, missing/wrong token
envelopes, redirects, and repeated nextLinks fail closed. Pending queue corruption
cannot omit unfinished active streams. New included folders start initial delta;
existing links remain. Removed folders become inactive with their history and
links retained; returned folders resume their previous stream.

Invalid/lost delta (400/404/410), malformed state, or incompatible policy/binding
raise typed controlled-resync errors. An affected folder ID can be attached as a
structured recovery hint; safe error text omits IDs, raw responses, tokens, links,
and tenant details. Auth, consent/policy, and retryable API failures are distinct.
Failed pages advance nothing; earlier successful pages remain durable.
[Outlook setup/recovery](outlook.md) describes explicit stopped-writer, backed-up,
version-incrementing folder/account reset. No automatic reset to now or deletion.

## Immutable IDs and retained data

Every Graph folder/message/delta GET carries `Prefer: IdType="ImmutableId"`;
there is no path using default message IDs. Changed delta IDs are de-duplicated
per page and re-fetched with a basic-metadata `$select`. This supplies complete
current metadata and prevents a stale folder-stream event from undoing a newer
move. A move retains account + immutable-ID identity and updates parent folder
metadata/raw version without duplicating the normalized source record.

Persisted allowlist: immutable ID, internetMessageId, conversationId,
parentFolderId, received/sent/created/modified timestamps, subject, From/Sender,
To/Cc/Bcc names/addresses, categories, importance, isRead, and hasAttachments.
Normalized records retain the corresponding identity/timestamp/sender/recipient
fields, minimized metadata, and raw-version link. All versions remain attributable
to one account. Raw payload hashes fingerprint metadata, not body content.

Excluded from requests and persisted records: body, bodyPreview, uniqueBody,
MIME/$value, attachment lists/metadata/contents, internetMessageHeaders, arbitrary
extended properties/OData response fields, and OAuth/MSAL data. The shared final
forbidden-key guard additionally rejects Graph preview/body/MIME/content-byte/
header/extended-property keys recursively and case-insensitively. Gmail's allowed
minimized attachment metadata remains supported. `content_hash` stays null.

Delta @removed markers and message fetch 404 retain historical provenance without
creating tombstones or canonical lifecycle state. Metadata for vanished items may
remain stale; deletion modeling is explicitly deferred. No provider writes,
classification, extraction, UI, canonical dedupe, calendars, files, or Finance
behavior are added.

## Acceptance and validation

| Acceptance area | Synthetic evidence |
| --- | --- |
| Existing connector/domain contract; people vs accounts; personal/work and mixed Gmail/Outlook | `test_outlook.py` contract/registry/multi-person test; existing ownership/Gmail suites |
| Household/provider-scoped Outlook uniqueness | Duplicate normalization/rollback, previous registration, both replacement orders, distinct owners/identities, cross-provider/household isolation, alias limits, and corrupt DB read/sync tests |
| Missing identity, deliberate sign-in, wrong-account rejection and stable cache binding | `test_outlook_auth.py` registration, sign-in display-before-save, wrong username/home/claims/cache binding tests |
| Least privilege/public client/secure cache | Scope/authority/public-client tests; secure-backend rejection, account-scoped service, refresh persistence and safe-save-failure tests |
| Folder localization/default exclusion/custom nesting | Folder policy tests; HTTP root/child pagination; excluded streams never reach delta |
| New/removed/reappearing streams and opaque next/delta paging | New-folder state retention and pagination/restart tests |
| URL/cursor corruption and lost delta fail closed | Host/scheme/path/projection/token-envelope/binding/policy/queue tests; expired-state and repeated-nextLink tests |
| Immutable IDs, moves, replay, updated metadata/raw history | HTTP Prefer assertions; stale move/replay/current metadata test |
| Page atomicity and safe error categories | Failed message/later-folder tests; HTTP auth/policy/transient/error-response tests |
| No private data requests/storage/logging and null body hash | Projection/allowlist assertions, persisted sentinel checks, recursive raw/normalized privacy-guard tests, MSAL/HTTP log suppression |
| Opt-in smoke/CLI aggregates without live CI | Fake CLI identity-before-counts test; documented small Inbox/page run |

Python 3.12.14: the full SQLite and real PostgreSQL 16 suites pass **232 tests**,
including all **98 merged tests unchanged**. Dependency consistency (`pip check`)
and `git diff --check` pass. CI runs the same full suites on Python 3.12 with a
PostgreSQL 16 service; both jobs must pass before merge. No real Microsoft or
Gmail OAuth/mailbox access was initiated. Tests use synthetic Graph/MSAL/fake
credential stores exclusively. No new database migration is necessary.

## Limits and exact questions for ChatGPT

Live Microsoft OAuth/Graph and native OS keyrings were not exercised. Public-cloud
routing/projections are tested synthetically; the opt-in procedure is documented,
not claimed as live proof. Tenant/admin policies may block Mail.ReadBasic without
any scope escalation. Initial delta is bounded by page size/run limit, not date
lookback. Folder discovery repeats per page and can be chatty (safety caps on tree/
page counts fail closed). Each changed ID costs a basic-metadata re-fetch. Cross-
folder consistency is eventual; current re-fetch can itself race another move.
Metadata/cursor databases require operator-managed encryption/access controls.
The synchronous logging guard is unsuitable for a future multi-thread scheduler.
Policy changes conservatively resync rather than reconciling arbitrary histories.

1. Does this diff meet every Issue #4 acceptance criterion while leaving merged
   Gmail behavior intact and avoiding Shared/full mail permissions and out-of-scope features?
2. Are MSAL username matching, stable home-account selection/claims checks, keyring
   payload binding, scope checks, public-client configuration, and refresh persistence
   sufficient to prevent wrong-account ingestion? Are alias/UPN and tenant limits clear?
3. Is well-known ID resolution and visible-folder traversal correct for personal
   and organizational accounts, including localized/default-excluded and nested
   folders? Is explicit include/exclude precedence and conservative policy resync acceptable?
4. Can opaque per-folder continuation links, pending queues, new/removed streams,
   optimistic commits, or failures silently omit unfinished history? Is routing/
   token-envelope validation appropriately strict without interpreting token values?
5. Do ImmutableId headers and current-metadata re-fetches preserve one provider
   identity across moves/replays while retaining raw history? Are disappearance
   retention and eventual consistency acceptable without canonical lifecycle work?
6. Can any body/preview/MIME/attachment/extended field, OAuth token/cache, provider
   error, or continuation URL escape into records/repr/logs/CLI? Are projection,
   allowlist, shared guard, and existing Gmail metadata compatibility correct?
7. Is the opt-in smoke and controlled version-incrementing recovery procedure
   usable without a hidden OAuth attempt, scope escalation, reset-to-now, or
   historical deletion? Which native/live checks should precede household use?

Please review against Issue #4 and these questions; do not merge until both CI
jobs and ChatGPT review pass.
