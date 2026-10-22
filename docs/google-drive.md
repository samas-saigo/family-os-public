# Google Drive metadata-only (Phase 2D)

The `google_drive` connector reads metadata only, using **exactly**
`https://www.googleapis.com/auth/drive.metadata.readonly`. It never downloads or
exports contents, calls `alt=media`, or calls Docs/Sheets/Slides APIs. No Drive write
commands exist. `content_hash` remains null; provider checksums are metadata hints,
not canonical dedupe. Future content ingestion needs a separate architecture and
security decision; this phase does not choose broader or file-selected permissions.

## Setup and explicit binding

Use Python 3.12 and the pinned development requirements from the README. The
`google-drive` optional extra declares the Google OAuth/native keyring dependencies;
`requirements-dev.lock` already includes their pinned versions. Run Alembic migrations
before registration. SQLite and PostgreSQL use the existing schema without changes.

Enable the Google Drive API in a Google Cloud project, configure its OAuth consent
screen, and create a **Desktop app** OAuth client. Configure only the metadata scope
above. Download its client JSON outside this repository, including outside any Git
checkout used as the working directory. A secure native OS keyring must be available
and unlocked: supported Windows, macOS, or Linux secret-service/KWallet backend.
Plaintext, null, and chained fallback stores are rejected. Headless CI does not connect.

Copy `config/household.google-drive.example.yaml` to ignored `config/household.yaml`.
Replace the synthetic account email deliberately; register first:

```sh
family-os register config/household.yaml
family-os google-drive-connect --household demo_home --account alex_drive \
  --client-file /absolute/path/outside/repository/desktop-client.json
```

This is the only interactive sign-in command. It checks the enabled registered
`google_drive` account before OAuth, requests exactly one metadata scope, then reads
`about.get(fields=user(permissionId,emailAddress,me))`. It requires `me=true`, email,
and a stable permission ID. The CLI displays the authenticated email **before** save;
a mismatch saves nothing. Email comparison trims and case-folds only: no dot/plus or
alias rewriting. Broader, additional, or missing granted scopes are rejected.

Credentials and stable account permission ID live only in the native keyring service
`family-os/google-drive.metadata.readonly/v1`, keyed by household/account. This is
separate from Gmail and Calendar. Registry/YAML hold the explicit email, not OAuth
data or the bound permission ID. Cursor state contains only its non-secret binding
fingerprint. Owner permission IDs returned in allowlisted file metadata are separate
provenance fields, not the secure credential binding.

Existing-connection load never initiates OAuth. Each committed ingestion page
re-verifies both current email and permission ID through `about.user`; a changed
Google account fails closed. Refreshed credentials save to the same keyring entry.
The local keyring is the current implementation-stage credential boundary, not a
future client credential interface. Provider OAuth remains separate from future
Family OS authentication/authorization; no service, API, or credential migration is added.

Within a household, two enabled Drive accounts cannot share a normalized email.
Disable the old account and enable a new replacement in one registry transaction.
The same email across Gmail/Calendar/Drive is allowed. Multiple Drive accounts per
person and distinct household members are supported. Existing account ownership and
history-transition rules still apply; do not reassign an account with captured history.
To stop sync, set `enabled: false` and re-register. History is retained; remove the
local keyring entry via the native credential manager if also revoking local access.

## Coverage and stream selection

```sh
family-os ingest-google-drive --household demo_home --account alex_drive \
  --page-size 10 --max-pages 5
```

The personal/user `drive`-space corpus is always enabled: My Drive and directly shared
items available through that corpus that are not inside a Shared Drive. This is
provider coverage, not an exhaustive organization-wide filesystem inventory. There is no time-bounded initial query.
Shared Drives are **not crawled by default**. To opt in, repeat exact stable IDs:

```sh
family-os ingest-google-drive --household demo_home --account alex_drive \
  --include-shared-drive DRIVE_ID_A --include-shared-drive DRIVE_ID_B \
  --page-size 10 --max-pages 5
```

Choose these options on the first ingestion or use explicit policy migration below.
The connector paginates `drives.list` to validate configured IDs, retaining only
selected IDs for routing. Names are not policy keys. It never uses domain-admin
access. Unlisted/inaccessible configured drives fail safely rather than disappearing
silently. Each selected drive has its own `corpora=drive`, `driveId` baseline and
change stream. No automatic “all Shared Drives” option exists.

Personal/user and Shared Drive file-observation streams are intentionally disjoint.
Application logic ignores every personal baseline file with a non-empty `driveId`
and every personal file change with a Shared Drive ID in either `change.driveId`
or the returned `change.file.driveId`. This includes updates, trash and sparse
removals, whether the Drive is selected or unselected. No source/raw observation
is created and no extra file fetch/dereference is performed. Selected Shared Drive
files are persisted only through their dedicated `drive:<id>` stream.

Ordinary files directly shared with the user remain eligible for the personal
stream when they are not inside a Shared Drive. A directly shared file that actually
lives inside a Shared Drive requires that exact Drive to be explicitly selected,
even if it is visible to the user or appears in the user change log. The deprecated
`includeItemsFromAllDrives=false` request flag may remain for compatibility;
it does **not** enforce isolation. Returned-observation filtering is the boundary.

For **each** stream, ingestion commits these stages in order:

1. Capture `changes.getStartPageToken` before any baseline file listing.
2. Paginate the complete metadata baseline (`files.list`).
3. Catch up from the captured token through `changes.list(includeRemoved=true)`.
4. Adopt `newStartPageToken` only at the final change page, then use it for incremental
   sync. Intermediate `nextPageToken` values remain resumable page cursors.

Tokens are opaque strings, never URLs or reconstructed identifiers. Atomic ingestion
commits page snapshots and cursor together; a failed page retains the saved cursor.
Replays are idempotent. A persisted queue processes streams sequentially; a failed
stream blocks the queue until resolved. `max_pages` bounds committed ingestion pages,
including empty start-token and discovery pages. A minimal personal baseline requires
at least start, baseline, and catch-up pages; larger accounts require multiple runs.
Identity verification adds an `about.get` request per page. Shared Drive discovery
runs each completed sync cycle and paginates all discoverable Drive IDs, so API requests
and cost exceed a simple file-page count. Credentials are persisted after authorized
requests; keyring access is also part of the request budget. No scheduler is provided.

## Metadata and provenance

File ID is provider object identity within an account. Names need not be unique;
parents are IDs, not paths. Renames, parent changes, ownership changes, and Drive moves
update the same source object while retaining earlier raw snapshots. The same file
seen through different accounts remains separate provenance until future dedupe.

Explicit request and persistence allowlists contain:

- file ID (`file_id` in snapshots), name, MIME type, created/modified/modified-by-me/
  viewed-by-me/shared-with-me timestamps;
- trashed, explicitlyTrashed, starred, parents, driveId, ownedByMe, shared;
- originalFilename, fileExtension, fullFileExtension, size, version, provider
  md5/sha1/sha256 checksums, headRevisionId;
- shortcutDetails targetId/targetMimeType; owner permissionId/emailAddress/displayName/me;
- capabilities.canDownload and stream routing/removal markers.

Only returned fields are persisted. Google-native or restricted objects may omit
checksums, size, revision/capability or other fields. Do not widen permissions to
obtain missing metadata. `canDownload` is metadata, not authorization to download
with this token. Names and owner details can be sensitive; protect the local database.
Normalized records are `document`, with name as subject, modifiedTime (createdTime
fallback) as provenance time, no sender/recipients/content, and minimized metadata.
Folders and shortcuts retain their actual MIME types; no content is implied.

Excluded: contents/exports, descriptions, properties/appProperties, contentHints,
permissions/ACL lists, thumbnails, image/video media metadata, web/export/content/icon
links, resource keys (including shortcut targetResourceKey), labels, comments/replies,
revisions, arbitrary provider payloads, and OAuth/token data. Explicit API field
projections and a Drive-specific forbidden-key defense reinforce this boundary.

Shortcuts are independent source objects. Their target ID is metadata only: no target
fetch, identity substitution, dereferencing, or merge occurs. No paths or canonical
document entities are synthesized.

`trashed=true` describes an accessible file in trash. It is not a deleted object.
`removed=true` is a **stream observation**, potentially deletion, corpus movement,
or access loss. A sparse snapshot keeps file ID, removal and stream identity, plus
Drive ID if supplied, without erasing historical metadata or backfilling missing
fields from old snapshots. If Google returns a current file resource with removal,
only its returned fields are minimized. A differing change Drive ID is retained
separately as `change_drive_id`. Historical snapshots preserve their stream routing;
Shared Drive files receive no duplicate personal-stream observations. Legitimate
file moves still retain file identity and prior snapshots. Removal from one
stream/account does not prove real-world or canonical deletion.

## Explicit recovery and policy migration

Safe errors distinguish identity, auth/keyring, policy, inaccessible Shared Drive,
retryable transport/rate/server failure, malformed response, and stream resync.
Diagnostics exclude tokens, keys, file names, owner emails and raw provider bodies.
Invalid/expired tokens (410 or recognized invalid-page-token responses), cycles,
and malformed/wrong-account/binding/policy cursors fail closed. There is no automatic
reset to now. Cursor trails are bounded to 10,000 entries; exceeding the bound also
requires deliberate recovery. Keep cursor/database state private and trusted.

Reset only the affected personal stream, preserving the configured inclusion policy:

```sh
family-os google-drive-resync --household demo_home --account alex_drive --personal \
  --include-shared-drive DRIVE_ID_A
```

Or reset one known Shared Drive stream:

```sh
family-os google-drive-resync --household demo_home --account alex_drive \
  --shared-drive DRIVE_ID_A --include-shared-drive DRIVE_ID_A
```

Supply the **complete current** inclusion list on every ingest/reset invocation;
wrong fingerprints are rejected. Recovery is a local, keyring-bound version/CAS
transformation with no provider calls or OAuth. It preserves other streams and all
raw history; the next ingest captures a fresh start token, baseline, then catch-up.
Provider history outside Google's retained change history cannot be reconstructed
if never captured. Re-baselining current metadata does not claim continuous history.
An unknown stream cannot be reset; an uninitialized account starts with normal ingest.
A structurally corrupt cursor cannot be repaired by the validated transform: stop
and inspect a trusted backup rather than deleting history or guessing token state.

Policy changes must be deliberate. For example, starting from no Shared Drives:

```sh
family-os google-drive-policy --household demo_home --account alex_drive \
  --include-shared-drive DRIVE_ID_A
```

Then add B while retaining A:

```sh
family-os google-drive-policy --household demo_home --account alex_drive \
  --previous-shared-drive DRIVE_ID_A \
  --include-shared-drive DRIVE_ID_A --include-shared-drive DRIVE_ID_B
```

Supply the complete old and new sets. New IDs start only their own baseline;
existing streams retain tokens/history. Omit a former ID from the new set to make
it inactive without deleting history. Re-including it resumes saved state, which
may require a targeted reset if expired. Discovery validates the new policy on the
next ingestion. Policy migration needs an existing valid cursor and secure binding.

## Opt-in manual smoke test

Automated tests/CI use fake OAuth/Drive clients and synthetic data only. No live
connection was exercised for this implementation. To test locally deliberately:

1. Use an account and local disposable database you are authorized to inspect;
   configure/register its enabled identity and Desktop client outside Git as above.
2. Explicitly run `google-drive-connect`; verify the displayed email and metadata-only
   consent. Wrong identity or extra scopes must fail without saving a connection.
3. Start `ingest-google-drive --household demo_home --account alex_drive --page-size 2
   --max-pages 3`. Repeat with identical policy to complete baseline/catch-up. Default
   output is aggregate counts only; do not dump cursor/keyring/raw metadata or enable
   HTTP debug logging. `family-os status --household demo_home` is also count-only.
4. Optionally rename/move/trash a disposable test file yourself in Google Drive, then
   ingest again to observe aggregate updates. Family OS performs no provider writes.
5. Opt into one known exact Shared Drive ID only through the explicit migration
   command, then repeat bounded ingestion. Do not add other organizational drives.
6. Disable the account afterward if desired. Do not publish local databases, client
   JSON, tokens, resource keys, names or owner details with smoke results.

Future Drive-content access must compare broad content permission, feasible
user-selected/file-scoped approaches, provider-specific Workspace read scopes, and
hosted verification/security-assessment obligations. No option is adopted here.
