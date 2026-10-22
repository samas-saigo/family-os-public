# Outlook read-basic setup and recovery (Issue #4)

Phase 2B supports the signed-in user's **own** Microsoft mailbox: personal accounts
and work/school accounts when app registration and tenant policy allow. It does
not support delegated/shared Exchange mailboxes, attachments, bodies, calendar,
provider writes, classification, or canonical entity merging. A household owner
in the Family OS registry is an attribution choice; it does not grant access to
another Exchange mailbox. All automated tests use synthetic Graph/MSAL responses.
No live sign-in or Graph access was used to implement or validate this feature.

## Install and app registration

Use Python 3.12 and the development lock, or install the `outlook` optional extra
for a runtime-only setup. No web framework or background job service is required.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m alembic upgrade head
```

On Windows use `.venv\Scripts\python.exe` / `.venv\Scripts\family-os.exe`.
No Phase 2B schema migration is needed. Follow the existing `DATABASE_URL` guidance
for PostgreSQL. The app does not encrypt databases: protect metadata, backups,
and cursor continuation tokens using encrypted storage and OS access controls.

In Microsoft Entra app registration:

1. Register a public desktop/native client. For the default `common` authority,
   choose **accounts in any organizational directory and personal Microsoft
   accounts**, if available for your registration.
2. Enable a mobile/desktop redirect URI `http://localhost` suitable for MSAL's
   interactive loopback browser flow. Configure public-client authentication as
   required by your tenant/app; tenant consent rules can still block access.
3. Add only delegated Microsoft Graph **Mail.ReadBasic**. Remove the commonly
   pre-added User.Read permission if unnecessary. Do not add application mail
   permissions, Mail.Read, Mail.ReadWrite, Mail.Send, or Shared permissions.
4. Note the application's public client ID (UUID). **Do not create a client secret**.

The CLI accepts only a client ID and authority, never a secret or token argument.
MSAL manages protocol OpenID/offline scopes (`openid`, `profile`, `offline_access`).
The only requested Graph resource scope is
`https://graph.microsoft.com/Mail.ReadBasic`. Returned token scopes are checked:
full/read-write/send/shared and other resource permissions are rejected. If a
future metadata field needs broader permission, stop and review it separately.

Authorities are restricted to HTTPS `login.microsoftonline.com/<tenant>`:
`common` (default), `consumers` for personal accounts, `organizations` for work/
school, or your tenant UUID/domain. The same app must support the chosen audience.
This implementation targets the public Microsoft cloud and public Graph v1.0;
sovereign/national cloud authorities and Graph endpoints are unsupported.

## Secure cache and account identity

Use an unlocked supported OS keyring: Windows Credential Manager, macOS Keychain,
or Linux Secret Service/libsecret/KWallet. Plaintext/null/failing/chainer backends
are rejected with no fallback. On headless Linux, configure a supported unlocked
backend outside this repository or use a desktop machine; do not install a
plaintext fallback. Gmail's existing keyring service/behavior is unchanged.

Outlook's service is `family-os/outlook.Mail.ReadBasic/v1`. The entry key is a JSON
`[household_id, source_account_id]` pair. The secure payload contains the serialized
MSAL cache (access/refresh/ID tokens), stable `home_account_id`, normalized username,
client ID, authority, and household/account binding. Nothing is stored in a
plaintext cache file, YAML, environment token variable, or the household database.
Silent refreshes save changed cache state before Graph I/O; secure-save failures
fail the page and leave the cache dirty for a retry. Loading a connection never
launches an interactive sign-in.

Identity policy: `external_account` must be the **MSAL sign-in username**, trimmed
and case-folded. No dots/plus suffixes are stripped and no alias/UPN guesses are
made. Personal Microsoft aliases and organizational UPNs can differ from your
preferred mailbox address; deliberately register the username MSAL identifies.
The connect command displays that username before verifying/saving the binding.
A mismatch saves nothing: correct the intended registration via a new account ID
if needed (external identity is immutable), then explicitly reconnect.

Every later request selects only the keyring-bound stable MSAL account and
acquires a token silently. Cached identity and any returned identity claims are
verified; missing, ambiguous, or switched accounts fail closed. The database
cursor contains only a SHA-256 binding fingerprint of home ID + client ID +
authority, not the stable home ID or OAuth tokens. Reconnecting to the same stable
binding preserves cursor compatibility; changing it requires controlled resync.

## Registry and folder configuration

Copy `config/household.outlook.example.yaml` to ignored `config/household.yaml` and
replace its synthetic values deliberately, then register:

```sh
.venv/bin/family-os register config/household.yaml
```

A person can own a personal Outlook account, a second work/school account, and
Gmail simultaneously; each has a distinct source account ID with the same person
owner. A spouse gets their own person owner/account ID. Unknown ownership may be
resolved once; explicit person/household owners cannot be reassigned or cleared.
Set `enabled: false` and register again to disable a connection without deleting
raw history, normalized records, or cursor. Omitting a YAML block does not disable
it. Disabling does not revoke Microsoft's grant or remove the keyring entry.

Folder policy is connector configuration supplied **for the selected account**:
`--include-folder` and `--exclude-folder` are repeatable. Values are exact Graph
folder IDs or supported well-known names (`inbox`, `archive`, `sentitems`,
`junkemail`, `deleteditems`, `drafts`, `outbox`, `syncissues`, `conflicts`,
`localfailures`, `serverfailures`). Names resolve to provider IDs through Graph;
localized display names are never used to identify system folders.

Default: include normal visible folders (Inbox, Archive, custom/nested folders),
exclude Junk/Deleted/Drafts/Outbox/Sent and identifiable sync/failure folders,
including their descendants. Hidden folders are excluded. An explicit include
restricts sync to those exact folders (not their descendants) and may opt a
normally excluded folder itself in unless explicitly excluded. An explicitly
included nested folder under an excluded parent remains excluded: excluded/hidden
subtree propagation wins. A missing/removed configured folder is inactive; no
historical records are deleted. If a policy selects no current folders, the run
returns aggregate zero counts.

The folder policy fingerprint binds the cursor. Keep the same options on resumed
runs. Policy changes do not change account identity, but conservatively require
controlled resync; no cursor is reset silently. Discovery repeats each page;
newly discovered included folders start at initial delta, while existing folder
links are retained. Removed folders stay inactive in the cursor; if they reappear,
their retained links resume or produce a controlled-resync failure if invalid.
A previously inactive/removed folder that reappears may wait until the current
pending folder queue completes, possibly delaying it until the next run; its
retained continuation state preserves history during that delay.

## Opt-in manual smoke procedure

Only run this when you deliberately want live access to one own mailbox. Start
with a newly registered account in a dedicated local database on encrypted media.
The public client ID below is a placeholder; use your registration's UUID.

```sh
.venv/bin/family-os outlook-connect --household demo_household --account demo_outlook_personal --client-id YOUR-APP-UUID --authority https://login.microsoftonline.com/common
.venv/bin/family-os ingest-outlook --household demo_household --account demo_outlook_personal --include-folder inbox --page-size 2 --max-pages 1
.venv/bin/family-os status --household demo_household
```

Connect deliberately opens Microsoft's sign-in flow (180-second timeout), displays
`Signed-in Microsoft account: ...` before keyring binding, and rejects mismatches.
Check that identity. Ingestion displays only safe identity confirmation followed
by aggregate inserted/updated/unchanged/page counts. No subjects, recipients,
message bodies, Graph payloads, cache contents, or tokens are printed. Your sign-in
address is intentionally visible locally; do not upload it in review artifacts.

The sample includes only Inbox and commits at most one delta page. A page-limit
error is expected if more remain; repeat identical options to resume. There is no
lookback filter in this phase: initial delta enumerates the included folder, bounded
by page size and run page limit. Graph may require several runs to catch up. No
live OAuth/Graph access runs in CI. To revoke access, use Microsoft account/app
consent management and remove the account's OS keyring entry deliberately.

## Cursor and recovery semantics

One opaque JSON cursor binds schema v1, household/account, registered username,
secure binding fingerprint, folder policy fingerprint, and each folder's identity,
display name, active flag, link/kind, plus the pending-stream queue. Graph link tokens
are **opaque provider sync state**, not parsed/reconstructed skip/delta tokens.
Stored links are never logged. Before use, host/scheme/API path must exactly match
public HTTPS Graph v1.0 `/me/mailFolders/<that-folder>/messages/delta` (equivalent encoded/OData folder routing forms are accepted; folder listing
links must match that listing path). Userinfo, ports, fragments, other accounts,
folders, API versions, unsafe projections/expansions, duplicate query keys, and
redirects are rejected. The token value itself is never inspected or modified.

Every message/delta/folder GET sends `Prefer: IdType="ImmutableId"`. Delta requests
select only basic metadata and use `odata.maxpagesize`. Each changed immutable ID
is re-fetched once per page with the same safe projection so partial/stale delta
snapshots cannot overwrite a newer folder move. `parent_folder_id` records the
current folder; account + immutable ID remains one normalized identity. Changed
metadata retains earlier raw versions; repeated appearances are idempotent.

A successful page atomically commits metadata and the updated multi-folder state.
Next pages retain exact `@odata.nextLink`; completed streams retain exact
`@odata.deltaLink`. A later folder/page failure changes nothing for that page;
earlier successful pages remain durable. HTTP 400/404/410 for delta and corrupt/
wrong-bound state produce `OutlookResyncRequiredError`, with an optional structured
folder ID for recovery. It never resets to now. Auth, policy/consent, and transient
failures are separate safe categories; retry transient/rate-limit failures later.
No scheduler/backoff loop is included.

For controlled recovery: stop all sync writers, make a protected database backup,
verify the account and folder policy, then deliberately reset the affected folder
stream to `link: null, kind: initial` and put its ID in `pending`; increment the
account sync-state version in the same transaction. Retain all other streams and
all raw/source records. If the binding/policy/cursor is corrupt or cannot be safely
reconciled, deliberately clear only that account's entire cursor, increment its
version, and re-run with the intended policy. This is an explicit local operator
procedure, not an automatic reset or provider write. The following account-level
reset uses the same `DATABASE_URL` as the CLI without printing it:

```python
import os
from datetime import datetime, timezone
from sqlalchemy import select, update
from family_os.db import create_db
from family_os.registry import get_account
from family_os.schema import source_sync_state
from family_os.outlook_identity import require_outlook_account

household_id, account_id = "demo_household", "demo_outlook_personal"
engine = create_db(os.environ.get("DATABASE_URL") or "sqlite:///data/family-os.sqlite3")
try:
    with engine.begin() as connection:
        require_outlook_account(get_account(connection, household_id, account_id))
        version = connection.scalar(select(source_sync_state.c.version).where(
            source_sync_state.c.source_account_id == account_id))
        changed = connection.execute(update(source_sync_state).where(
            source_sync_state.c.source_account_id == account_id,
            source_sync_state.c.version == version).values(
                cursor=None, version=version + 1, updated_at=datetime.now(timezone.utc)))
        if changed.rowcount != 1:
            raise RuntimeError("Concurrent sync; stop writers and retry")
finally:
    engine.dispose()
```

Re-listing preserves normalized IDs and historical raw snapshots. It cannot
reconstruct vanished items or changes beyond Graph's retained delta history.
Delta `@removed` markers and message-fetch 404 retain previous provenance without
creating canonical tombstones or deleting records; old metadata can remain stale.
Deletion/lifecycle modeling is a separate follow-up. Attachment presence is only
`has_attachments`; no attachment listing, metadata, or contents are accessed.
Bodies/previews/uniqueBody/MIME/headers/extended properties are excluded from
requests and persisted allowlists; `content_hash` remains null.
