# Phase 2C / Issue #6: ChatGPT review handoff

## Result and scope

Google Calendar is an independent `google_calendar` source account using the existing
provider-independent ingestion/provenance contract. CalendarList discovery and
per-calendar event streams share one strictly validated opaque account cursor.
This PR preserves all 232 merged Gmail/Outlook/foundation tests and adds 122 synthetic
Calendar tests. No schema migration, canonical entity, classifier, UI, Finance logic,
Calendar write, watch channel, reminder, recurrence expansion, or cross-source merge
is introduced. The architecture/data-model/dedupe/security/roadmap design documents
are preserved; README/AGENTS now reflect merged Outlook and current Calendar scope.

## Decisions and boundaries

**Scopes:** exactly `calendar.calendarlist.readonly` and `calendar.events.readonly`
under `https://www.googleapis.com/auth/`. No `calendar.readonly`, write, Gmail, Drive,
profile/userinfo, ACL, or settings scopes. Requested, loaded, and granted credential
scope sets must equal the two approved scopes. HTTP 403 is a safe policy error;
permissions are not widened. HTTP 401/keyring failures are safe auth errors;
429/server/transport failures are safe retry categories. HTTP 410 identifies
CalendarList or the affected event stream as requiring explicit recovery.

**Account binding:** pre-registration/explicit external identity and enabled provider
checks precede OAuth. Desktop OAuth discovers exactly one live primary CalendarList
entry, displays its ID before secure saving, and verifies trim/casefold equality with
registration. No Gmail dot/plus/alias or Workspace alias guessing. Every ingestion
page independently scans CalendarList to re-verify identity, before persisting any
changes. This extra read cost is intentional; discovery sync tokens do not serve as
an account identity assertion. The primary entry must be readable to ingest events.
The provider-scoped household guard validates final transactional registry state and
account reads, allowing disabled-old/enabled-replacement swaps but rejecting direct
DB duplicate corruption. Existing immutable identity/explicit ownership rules remain.

**Credentials:** distinct native keyring service
`family-os/google-calendar.readonly/v1`, JSON `[household,account]` key. No Gmail keyring
reuse. Only approved secure backend modules with positive priority are accepted;
plaintext/null/chainer/failing stores have no fallback. Client JSON stays outside the
checkout. Existing connections load silently; only explicit connect performs OAuth.
Refresh credentials save to the same Calendar keyring entry. Tokens never enter
YAML, SQL, fixtures, Git, or disk token caches. Local native keyrings/live consent
have not been exercised; fakes test these boundaries.

**Selection:** primary always included; excluding it is a policy error rather than
silently omitting it. Visible selected calendars with `reader`,
`writerWithoutPrivateAccess`, `writer`, or `owner` access are included by default.
`writerWithoutPrivateAccess` is event-readable
but does not imply full writer privacy visibility: Google may omit private-event
details. Only fields actually returned are persisted; missing optional fields remain
absent, without fabrication or copying from prior snapshots. Explicit include opts
hidden/unselected calendars in; explicit exclude wins, and freeBusyReader/none access always remains excluded. Includes are
additive, not a whitelist. IDs drive policy and routing, not localized names.
Cursor metadata contains only primary/hidden/selected/accessRole plus active state.
Removed/unselected/excluded calendars retain history and event tokens while inactive.
Reappearance resumes the saved stream, subject to controlled token-expiry recovery.
Selection changes during an event queue take effect after the next discovery cycle.

**Cursor:** schema version, household, source account, normalized primary identity,
policy fingerprint, CalendarList page/sync/trail state, full-discovery seen IDs,
calendar metadata/active flags and event page/sync/trail state, phase, and pending
queue. Exact keys/types, binding, metadata policy, queue references, and continuation
invariants are checked; duplicate JSON fields and page-token cycles are rejected.
Opaque tokens are sent as parameters on fixed Google API routes, never decoded or
used as URLs. Route IDs are encoded as single path segments; dot path segments are
rejected. Failed pages retain prior state through the existing account-version CAS.
Tokens cannot be authenticated offline: valid-shaped edits cannot be distinguished
cryptographically from genuine state; keep the database trusted and backed up.

**Sync:** CalendarList initial/incremental pages commit independently before building
the event queue. Each included calendar has a full initial stream and later incremental
stream; new calendars start without resetting others. CalendarList and events always
use showDeleted=true, events use singleEvents=false, and page/sync compatible fixed
projections. No timeMin/timeMax/orderBy/search/iCalUID filter. The old sync token
remains attached to incremental pages; only the final page replaces it with
nextSyncToken. `max_pages` bounds committed ingestion pages; identity scans are extra
requests with a 10,000-page safety bound. Reaching the limit is a resumable safe error.

**Recovery:** explicit local `google-calendar-resync --calendar-list` resets only
discovery continuation; `--calendar-id ID` resets only that event continuation.
Recovery validates the account and cursor/policy and increments the state version
with CAS, without OAuth/network or history deletion. Other stream tokens are retained;
unfinished queued work resumes. Unknown targets are rejected. A restored CalendarList
full scan deactivates absent calendars on completion. A full re-sync is idempotent
against retained snapshots but cannot reconstruct changes lost from Google's retained
sync history. Corrupt/wrong-account/wrong-policy cursors are not automatically repaired;
restore a known-good backup or deliberately register a replacement account retaining
old history. Policy migration is outside this PR.

**Identity and recurrence:** `gcal:v1:` plus compact JSON `[calendar_id,event_id]`
is the source identity. Both original IDs are also persisted. Equal event IDs or
iCalUIDs in different calendars/accounts remain distinct. Recurring series rules,
modified exceptions, cancelled exceptions, recurringEventId and originalStartTime
are preserved without generating instances. Date-only/all-day and zoned timed values
stay structurally intact. The normalized occurred_at is created/updated provenance
time; start/end stay in metadata for future domain matching.

**Cancellation:** status=cancelled updates current source metadata under the same
composite ID; sparse Google tombstones are accepted. Prior raw snapshots remain,
including prior summary/timing metadata. Current sparse snapshots do not fabricate
missing fields from old payloads. No canonical lifecycle/deletion or record removal.

## Persisted versus excluded data

| Persisted allowlist | Excluded from projection and persistence |
| --- | --- |
| Calendar/event IDs, iCalUID, status, eventType, created/updated | Description, raw API/error responses, OAuth/cache data |
| start/end, endTimeUnspecified, recurrence, recurringEventId, originalStartTime | Attachments, attachment URLs, extendedProperties, privateCopy, gadgets |
| summary, location, transparency, visibility | Arbitrary source payloads, conferenceData, hangoutLink/conference identifiers |
| organizer/creator email/displayName/self | Unlisted participant properties such as attendee comment |
| attendee email/displayName/self/responseStatus/optional/resource | Arbitrary nested time/participant fields |
| sequence and guest modification/invitation/visibility flags | Bodies, previews, secrets, token/sync/page values in diagnostics |

Raw snapshots and normalized metadata contain only the allowlisted projection;
`content_hash` is null. “Raw” is the existing minimized ingestion layer, not a copy
of provider JSON. Provider-independent forbidden-key checks add Calendar sensitive
names; the stricter Calendar-only defense excludes attachments/source/hangoutLink
without breaking Gmail's legitimate minimized MIME attachment metadata. Event summaries,
locations and participants remain intentionally sensitive stored metadata; operator
at-rest encryption is still required. Cursor sync/page tokens are persisted only as
opaque provider continuation state, never OAuth tokens or error/log content.

Transport suppresses synchronous OAuth/SDK diagnostics, restores the prior logging
level afterward, and emits typed sanitized errors without raw exception chains. The
single-user synchronous CLI prints only intentional primary identity confirmation
and aggregate counters; no event payloads. No new background/thread logging behavior.

## Acceptance evidence

| Issue #6 requirement | Synthetic evidence |
| --- | --- |
| Contract, idempotence, versioned snapshots, cancellation, null hash | contract/history test; recurring and malformed-page tests |
| Multiple providers/persons, provider-only dedupe, transactional replacement, corruption read guard | registry combination, swap/rollback, DB-corruption, ownership tests |
| Pre-OAuth validation, primary display-before-save, wrong account no-save, re-verification | auth display/order, missing CLI registry, wrong identity and sync account-switch tests |
| Exact scopes, separate secure store, no auto OAuth, refresh/log safety | auth scope parametrizations, keyring separation/backends, load and refresh tests |
| Initial/incremental CalendarList and event paging | resumable opaque paging, incremental discovery/event tests |
| Primary/hidden/freeBusy policy, new/removed/reactivated calendars | policy matrix, readable-role default/explicit inclusion matrix, primary exclusion, discovery/reactivation tests |
| writerWithoutPrivateAccess and redacted private events | role acceptance/selection tests; redacted initial/incremental persistence with omitted-field and prior-history assertions |
| Composite IDs, recurring series/exceptions/cancellations/all-day values | paging collision and recurring metadata tests |
| 410/history preservation, isolated reset, committed-page rollback | expired stream/recovery, completed-queue reset, malformed/failed event pages |
| Strict corrupt/wrong-binding/wrong-policy cursor, no unsafe queries/URLs | cursor mutations/duplicate fields/cycles and HTTP routing/projection tests |
| Privacy/log exclusions | nested allowlist, forbidden-key tests, typed HTTP failure tests, safe CLI counts |
| Setup and opt-in smoke | docs/google-calendar.md and synthetic example YAML |

Validation uses Python 3.12.14, synthetic OAuth/Calendar/Gmail/Graph clients only,
and disposable databases. Full SQLite and real PostgreSQL 16 suites each pass 354 tests. `pip check` and
`git diff --check` pass. CI results are recorded in the PR description. No live Calendar, Gmail, Outlook, or interactive OAuth access
was initiated. Existing Gmail/Outlook connector/auth/test files are unchanged.

## Limits

Identity verification repeatedly reads CalendarList and is not counted by max_pages;
large account lists incur additional reads. Event streams are processed sequentially,
so a persistently failing calendar can block later queued calendars until explicitly
recovered or access corrected. Discovery changes wait until the pending queue ends.
Permission loss/403 does not silently deactivate or erase a stream. No push/watch,
caching, date window, recurrence expansion, automatic policy migration, secure backend
installation, or native keyring/live provider verification is included. Request quotas
and Google/Workspace consent policies remain operator constraints. Conference/link
metadata is deliberately omitted. Continued ingestion relies on Google's retained
sync history, with documented limits after 410 recovery.

## Exact ChatGPT review questions

1. Does this implement every Issue #6 criterion using only the two approved scopes,
   without calendar writes, canonical lifecycle/dedupe, recurrence expansion, or changes
   to merged Gmail/Outlook behavior?
2. Is the primary CalendarList trim/casefold binding (including display before secure
   save and per-page identity verification) sufficient without userinfo/alias guesses,
   and do final registry/read guards preserve attribution under replacement/corruption?
3. Does the separate native keyring/OAuth boundary reject broader scopes and unsafe
   backends, avoid interactive load/reuse of Gmail tokens, and keep secrets/logs private?
4. Are CalendarList plus independent event pagination/sync state and fixed query
   semantics correct for Google's incremental API, including strict cursor binding,
   page cycles, partial failures, operational bounds, and new/removed calendars?
5. Does calendar selection correctly preserve primary inclusion, explicit exclusion,
   hidden/unselected opt-in, and free/busy exclusion without relying on display names?
6. Do composite source identity, recurring definitions/exceptions, date-only/zoned
   values and sparse cancellations preserve future matching evidence and raw history
   without premature iCalUID merge or canonical lifecycle semantics?
7. Do explicit stream-specific 410 recovery and CAS preserve unrelated tokens/history,
   fail closed on invalid state/policy, and accurately document unrecoverable provider
   sync-history gaps?
8. Are the request/persistence allowlists, shared versus Calendar-only forbidden keys,
   null content hashes, safe errors/CLI output, and opt-in smoke test sufficient for
   Phase 2C privacy, with the stated storage/consent/request-cost limitations?
