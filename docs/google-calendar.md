# Phase 2C: Google Calendar read-only setup and recovery

This adapter reads calendar discovery and event metadata for **one registered Google
account**. It preserves recurring series, modified exceptions, and cancellations
without expanding instances or merging events with Gmail. There are no Calendar
write, task, reminder, watch, classification, or canonical lifecycle commands.
All automated tests use synthetic clients and credentials.

## Prerequisites and scopes

Use Python 3.12 and install the pinned `requirements-dev.lock`, then install the
project with `python -m pip install --no-deps -e .`. The `google-calendar` extra
supports narrower installations; it uses the existing Google OAuth/keyring packages
and `tzdata` for Windows timezone validation. Run `python -m alembic upgrade head`
against the intended database. No new migration is required.

In Google Cloud Console enable Google Calendar API, configure the OAuth consent
screen/test users as appropriate, and create an OAuth **Desktop app** client. Store
the downloaded client JSON outside this repository, including outside tracked and
ignored repository directories. The CLI rejects client files inside the checkout.
Do not commit client JSON, personal YAML, tokens, or databases.

The Calendar connection requests and accepts exactly:

- `https://www.googleapis.com/auth/calendar.calendarlist.readonly`
- `https://www.googleapis.com/auth/calendar.events.readonly`

It rejects `calendar.readonly`, write scopes, Gmail/Drive scopes, and profile/userinfo
scopes. No ACL/settings API or identity endpoint is used. If Google/tenant consent
cannot grant exactly these scopes, stop and fix the consent configuration; do not
widen the scope set. Revoke a previously broader grant before reconnecting if needed.

A supported native OS keyring must be available: Secret Service/libsecret/KWallet
on Linux, Windows Credential Manager, or macOS Keychain. Null, plaintext, chainer,
unsupported, locked, and failing backends fail closed with no file fallback. Tokens
and refresh tokens live only in the separate
`family-os/google-calendar.readonly/v1` keyring service, keyed by the unambiguous JSON
pair `[household_id, source_account_id]`. Refreshes save back to that entry. Gmail's
keyring service is neither read nor changed. Cached credentials never initiate
interactive sign-in. Database encryption/backups remain the operator's responsibility;
event summaries, locations, and participant addresses are sensitive metadata.

## Register and connect

Copy `config/household.google-calendar.example.yaml` to ignored
`config/household.yaml` and replace synthetic values. Each Calendar source account
uses `provider: google_calendar` and an explicit `external_account` equal to the
Google account's **primary CalendarList ID**. For ordinary accounts this is their
Google email address; Workspace identities/aliases must match the ID Google returns.
Identity normalization is trim plus case-fold only. Gmail dot/plus and alias rewriting
are not applied. Do not register the literal API alias `primary` as your identity.

One person may own Gmail, Outlook, and multiple distinct Calendar accounts. Other
household members may each connect their own accounts; shared attribution uses
`owner_type: household` and the household ID. Provider/external identity/household
and explicit ownership cannot be reassigned in place. Register a new account ID
for a different identity. Duplicate enabled Calendar identities in one household
are rejected both on registration and account reads. Disable an old account and
register its replacement in the same YAML reload to make that transition atomic.
The same email in Gmail and Calendar is allowed because guards are provider-scoped.

Example commands from the repository root (use your Python 3.12 environment):

```powershell
family-os register config/household.yaml
family-os google-calendar-connect --household demo_home --account alex_calendar --client-file C:\Private\calendar-desktop-client.json
```

On Linux/macOS use an absolute client path outside the checkout instead. Only
`google-calendar-connect` initiates OAuth. Select the intended Google account in
the browser. The connection fetches all CalendarList pages, requires exactly one
non-deleted `primary: true` entry, **prints that identity before saving**, compares
it with registration, and saves only on a match. Failure saves no new credentials.
Before every ingestion page, CalendarList is scanned again to verify the primary
identity; mismatch stops ingestion without advancing the failed page. This costs
additional requests, intentionally avoiding account-switch inference.

## Calendar policy and bounded ingestion

```powershell
family-os ingest-google-calendar --household demo_home --account alex_calendar --page-size 25 --max-pages 100
```

The primary calendar is always included if readable. Other calendars are included
by default when selected and not hidden, with `reader`, `writerWithoutPrivateAccess`,
`writer`, or `owner` access. `writerWithoutPrivateAccess` permits event reads but
Google may hide private-event details; it does not grant full `writer` privacy
visibility. Only returned fields are persisted. Missing summary, location, organizer,
attendees, or other optional metadata stays absent and is not copied from older
snapshots.
Unselected/hidden calendars are inactive by default. Free/busy-only or no-access
calendars are never read for event details, even when explicitly included.
Repeat `--include-calendar ID` to opt specific hidden/unselected calendars in;
repeat `--exclude-calendar ID` to exclude a calendar. Explicit exclusion wins over
inclusion. Including IDs adds to the default selection; it is not a whitelist.
Excluding the primary calendar is a policy error so primary inclusion is preserved.
IDs, not localized names, control routing. Cursor state stores flags/access role,
not display names or CalendarList descriptions.

Keep the same include/exclude options on every run and recovery command. The policy
fingerprint binds the cursor; a changed policy fails closed. Policy migration and
repair of structurally corrupted/wrong-account cursors are not automated here:
restore a known-good cursor/backup, or deliberately create a fresh source account
while disabling the old one and retaining its history. Do not casually edit tokens.

CalendarList discovery runs to completion before that cycle's pending event queue.
A new included calendar starts its own full event sync; existing stream tokens stay
intact. Removed, unselected, or excluded calendars become inactive, retaining both
saved event state and historical records. A reappearing calendar resumes its saved
stream on the next discovery cycle; an expired stream requires explicit recovery.
Calendar changes while an event queue is in progress are observed in the next cycle.

Page size is 1–250. `max_pages` limits committed ingestion pages, including discovery
pages. Each ingestion page also performs a full CalendarList scan for primary
identity verification, in addition to the persisted discovery stream (bounded at
10,000 discovery pages with cycle detection). Accounts with many calendars can
therefore generate materially more Calendar API requests than `max_pages` alone
suggests. Reaching the limit returns a safe resumable error;
previous successful pages remain committed. Run the same command again to resume.
Do not add date bounds: initial sync intentionally covers the provider's full event
collection, bounded by page/run limits, with `singleEvents=false` and `showDeleted=true`.

## State, recurrence, and privacy

One opaque, versioned account cursor contains household/account/normalized identity,
policy fingerprint, CalendarList page/sync state, minimized calendar metadata and
active flags, per-calendar event page/sync state, and pending work. Page tokens and
sync tokens are sent verbatim as query parameters, never interpreted as URLs or
reconstructed. Pagination retains the old sync token until the final page returns
`nextSyncToken`. Fixed sync-compatible query semantics/projections apply throughout.
Repeated/cyclic pages, malformed state, and wrong binding fail closed. Page records
and cursor updates commit atomically through the existing ingestion compare-and-swap.

Provider object IDs are `gcal:v1:` plus a compact JSON array `[calendar_id,event_id]`.
Original IDs are separately stored in metadata. `iCalUID` is a matching hint, never
source identity; equal event IDs in different calendars remain separate records.
Recurrence rules, `recurringEventId`, and `originalStartTime` preserve series and
exceptions. Date-only/all-day and timed values retain their original semantics;
normalized `occurred_at` uses created/updated provenance time, not an invented
UTC start time for an all-day event.

Requests and persistence allowlist IDs, iCalUID, status/type, created/updated,
start/end/originalStartTime, recurrence, summary/location, transparency/visibility,
organizer/creator and minimized attendee fields, sequence and guest flags.
Descriptions, attachments/URLs, extendedProperties, privateCopy, gadgets, arbitrary
source/conference data, hangout links, and raw provider response objects are excluded.
Conference identifiers are deliberately omitted in this phase. `content_hash` stays
null. Raw rows contain minimized snapshots, not full Google JSON. Cancelled events
produce a sparse source snapshot under the same composite identity; current metadata
status becomes `cancelled` while prior snapshots remain. Cancelled exceptions retain
recurring identifiers when provided. No canonical deletion/lifecycle is inferred.

SDK wire/OAuth diagnostics are suppressed during synchronous transport; public
errors contain no raw bodies, tokens, event subjects, locations, or participant data.
CLI output contains only the intentional identity confirmation and aggregate counts.

## Explicit 410 recovery

Google HTTP 410 produces a typed CalendarList or event-stream resync-required error.
The failed page leaves its cursor and history untouched. Do not replace a token with
“now”, delete records, or reset unrelated event streams. Back up the database before
operator recovery and stop other sync processes for the account.

For an expired CalendarList token:

```powershell
family-os google-calendar-resync --household demo_home --account alex_calendar --calendar-list
```

For an expired calendar event token, use the exact Calendar ID:

```powershell
family-os google-calendar-resync --household demo_home --account alex_calendar --calendar-id demo.primary@example.invalid
```

Supply the same policy options as ingestion. Recovery makes no OAuth/network calls,
checks the registered enabled account and strict cursor binding, and uses a version
compare-and-swap. CalendarList reset leaves all event stream tokens untouched;
event reset leaves CalendarList and other event tokens untouched. Pending unfinished
work remains resumable. Inactive streams can be reset but remain inactive until
selected again. Unknown event-stream IDs are rejected. Run ingestion again afterward.

A controlled full re-sync is idempotent against retained snapshots. It cannot
reconstruct changes Google has already dropped from retained sync history; unchanged
history is never physically deleted. Repeated 410/403 failures require checking
consent/calendar access instead of broadening scopes. To disable access, set
`enabled: false` and reload the registry; revoke the Calendar app grant/delete only
its account-scoped Calendar keyring entry using OS tools. Never delete Gmail's entry.

## Opt-in manual smoke test (never CI)

Only an operator who explicitly chooses real access should perform these steps.
Use a backed-up local database, an outside-repository Desktop client, and a native
keyring. Register exactly one intended Calendar source account, then invoke
`google-calendar-connect` yourself. Confirm the browser requests only the two scopes
above and the displayed primary ID matches registration before binding is saved.

Begin with a deliberately small run:

```powershell
family-os ingest-google-calendar --household demo_home --account alex_calendar --page-size 1 --max-pages 2
family-os status --household demo_home
```

Discovery may consume the entire run when many calendars exist; a page-limit message
is expected and saved pages resume with the same command. Inspect aggregate counts
only. Do not print/query event payloads, subjects, descriptions, attendees, locations,
tokens, or cursor strings. Repeat the bounded run to verify resume. Revocation or a
wrong-account test must stop safely; reconnect only by an explicit connect command.
Do not perform this smoke test from CI or with production fixture snapshots. No live
Google/OAuth access was used to implement or validate this PR.
