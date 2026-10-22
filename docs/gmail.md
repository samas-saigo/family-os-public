# Gmail read-only setup (Phase 2A / Issue #2)

This adapter reads one explicitly registered mailbox per source account. It does
not classify messages, merge household entities, download attachments, or write
to Gmail. All automated tests use synthetic responses and fake Gmail clients.
The procedure below is opt-in; it has not been run against a real mailbox.

## Local prerequisites

Use Python 3.12 and a supported unlocked OS credential store: Windows Credential
Manager, macOS Keychain, or Linux Secret Service/libsecret/KWallet. Headless Linux
may have no suitable keyring. The adapter fails closed; there is no plaintext,
file, environment-token, or database-token fallback. If keyring selects a chainer,
select your supported secure backend explicitly using keyring's configuration
outside the repository. Do not install `keyrings.alt` as a workaround.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m alembic upgrade head
```

On Windows use `.venv\Scripts\python.exe` and `.venv\Scripts\family-os.exe`.
For a runtime-only install use the `gmail` optional extra; the development lock
pins Gmail, test, and PostgreSQL dependencies for reproducible validation.

Enable the Gmail API in your Google Cloud project, configure an OAuth consent
screen, and create a **Desktop app** OAuth client. If the app is in testing, add
the intended user as a test user. Download the client JSON to a protected path
**outside this repository**, for example your private OS configuration directory.
Do not put client secrets in YAML, `.env`, the repo, or review uploads. Protect
that file with OS permissions. The connection checks the resolved path, including
symlinks, and rejects client files inside the checkout.

The only requested scope is
`https://www.googleapis.com/auth/gmail.readonly`. Broad or additional granted
scopes are rejected. The OAuth flow opens a browser, uses an ephemeral loopback
port on `127.0.0.1`, requests offline consent, and times out after 180 seconds.
A refresh token may expire under Google's test-app policies; explicitly reconnect
if necessary. No automated test opens a browser or contacts Google.

Metadata contains personal information (including subjects and addresses). The
application does not encrypt SQLite/PostgreSQL. Use encrypted storage, restricted
access, and protected backups before deliberately ingesting real household data.

## Register people and accounts

Copy `config/household.gmail.example.yaml` to ignored `config/household.yaml` and
replace the synthetic identifiers and addresses deliberately. Register before
connecting:

```sh
.venv/bin/family-os register config/household.yaml
```

- A person's second Gmail account gets a new account ID with the same person owner.
- A spouse's account gets a new ID with that spouse's person owner.
- A shared mailbox uses `owner_type: household` and the household ID as owner.
- An unresolved mailbox uses `owner_type: unknown` with no `owner_id`.
- Set `enabled: false` and register again to disable an account. Removing a YAML
  block does not disable it. Disabling retains raw history, normalized records,
  and cursor; it does not revoke Google's grant or erase the keyring entry.

`external_account` is required even for disabled Gmail registrations. Empty
identity is rejected; ingestion never fills it silently from OAuth. Once created,
provider, household, and external identity are immutable. Unknown ownership may
be resolved to a person or household; once explicit, the owner cannot change or
be cleared back to unknown. Use a new account ID for a different mailbox or
explicit owner. Enable/disable changes remain independent of ownership. Connection
verifies the Gmail profile before saving credentials, and every sync page verifies
it again before fetching messages.

Within a household, two enabled Gmail accounts cannot share a normalized mailbox
identity. Normalization trims/case-folds addresses and, for Gmail/Googlemail only,
removes dots and plus suffixes and maps Googlemail to Gmail. Workspace domains
retain dots/plus suffixes. Other Workspace aliases cannot be resolved offline;
register the canonical address returned by Gmail profile. There is no duplicate
override. To replace a registration, disable the old ID and add the new ID in one
registry update. Raw history remains attributed to the original account ID.

## Opt-in manual smoke test

Only run these commands when you intentionally want live read-only Gmail access.
Use one newly registered account in an empty/disposable local database on encrypted
storage, with a small query you choose. OAuth is initiated only by `gmail-connect`:

```sh
.venv/bin/family-os gmail-connect --household demo_household --account demo_primary --client-file /absolute/private/path/gmail-desktop-client.json
.venv/bin/family-os ingest-gmail --household demo_household --account demo_primary --query 'newer_than:1d -in:spam -in:trash' --page-size 2 --max-pages 2
.venv/bin/family-os status --household demo_household
```

`gmail-connect` prints the verified mailbox and does no ingestion. Check that
identity before running `ingest-gmail`. The latter prints the authenticated mailbox
before ingestion, followed by aggregate inserted/updated/unchanged/page counts.
It never prints subjects, bodies, attachments, or complete payloads. Identity is
intentionally visible for this local verification; do not upload terminal output
containing your real address. OAuth prints an authorization URL for the user;
wire diagnostics and token/redirect logging are suppressed during private I/O.

A page-limit error is expected if more than two pages are needed. Completed pages
remain committed. Repeat the same command to resume. This sample bounds the
initial listing by query, page size, and page limit; history catch-up can include
other mailbox changes since the baseline. Pick a quiet mailbox for the smoke test.
No automatic live access is part of CI. Revoke the OAuth app through Google account
settings and remove its OS keyring entry when finished, if desired. Entries use
service `family-os/gmail.readonly/v1`, with a JSON household/account pair as key.

## Queries, cursors, and safe recovery

The default initial query is `newer_than:365d -in:spam -in:trash`; supply `--query`
for another lookback/search. Query is connector configuration, not a token or
registry secret. `--page-size` is 1–100 (default 25); `--max-pages` defaults to 100.
Gmail search is used only for initial listing. Incremental history reads all changes
since the initial baseline, including later label/trash changes and messages that
did not match that initial query. The query is not an ongoing retention filter.

The opaque JSON cursor binds its version, household, source account, normalized
mailbox, and query. Initial pages keep the profile history ID captured **before**
listing and carry the list page token. Completion transitions to history and
immediately catches up from that baseline, including changes during listing.
History pages retain the same start history ID until the final page, then commit
the returned tip. A failed page changes neither records nor cursor; a stale
concurrent sync loses the ingestion layer's version compare-and-swap.

Invalid/expired history IDs, rejected pagination tokens, malformed bound state,
query changes, backwards history tips, and repeated page tokens require controlled
resync. The adapter does not replace the cursor with "now" or delete records.
Authentication, request, and retryable failures use safe categories without raw
provider exception text.

Each synchronous Gmail HTTP client proactively spaces GET starts at least 0.30
seconds apart using monotonic time. The first GET has no startup delay; elapsed
request time and retry backoff count toward the interval, so a long backoff does
not add a second pacing wait. All waits occur before provider GETs, outside database
transactions and ingestion commits. This targets about 200 GETs/minute: even if
every GET is a 20-unit `messages.get`, about 4,000 quota units/minute, one-third
below the stated 6,000-unit/minute per-user/project budget for new projects.
Counting both endpoints of a 60-second window conservatively allows at most 201
client GET starts / 4,020 units, still with substantial headroom.
Profile (1 unit), messages.list (5) and history.list (2) use the same conservative
spacing. No quota weighting, CLI tuning or concurrent requests are introduced.

Large first-time syncs may intentionally take several minutes (1,000 message GETs
alone take about five minutes, plus other requests/latency). This is a per-client
pace, not a global quota reservation: other clients/project traffic and dynamic or
shared provider limits can still cause rate limits. The bounded retry below remains
the fallback; rate limiting does not require resetting the cursor.

Gmail can report quota/rate limits as HTTP 403 as well as 429. Each GET retries
only 403 responses whose structured reasons are all `rateLimitExceeded` or
`userRateLimitExceeded`, HTTP 429, and HTTP >=500. Quota 403/429 responses allow
at most eight total attempts, with nominal waits of 1, 2, 4, 8, 16, 32, and 32
seconds. HTTP >=500 retains five total attempts with waits of 1, 2, 4, and 8 seconds.
The existing [0, 1)-second jitter is added before capping each wait at 32 seconds;
quota waits total 95 seconds nominally and less than 100 seconds with jitter,
excluding request latency. A sync may intentionally appear paused for about
1–2 minutes while waiting for quota recovery. The attempt counter is shared per
GET: category changes do not restart it, and a server error at or beyond the fifth
attempt fails immediately. Proactive 0.30-second pacing remains enabled; elapsed
backoff satisfies that interval without a second wait.
Ordinary 400, 401 after AuthorizedSession handling,
permanent/unknown/malformed 403, and 404 are not retried by this layer. Provider
error bodies/messages are never logged or surfaced. Exact `gmail.readonly` scope
checks and changed-state OS-keyring persistence remain unchanged on each attempt.

Transient network failures during a GET (requests timeout/connection failures,
other transport `RequestException`s and Google-auth `TransportError`) use the short
five-attempt 1/2/4/8-second backoff plus bounded jitter, with the same pacing.
Deterministic URL/header/schema, TLS, redirect, JSON decoding/request-state errors and
raised HTTP errors are not transport-retried. Unknown exceptions fail closed.
True OAuth refresh rejection (`RefreshError`), other Google-auth credential errors,
scope mismatch, missing/corrupt credentials, serialization and keyring load/save
failures remain auth errors and are not transport-retried; an explicit reconnect
may be required. No automatic OAuth reconnect occurs. Raw network/provider details
are never logged or surfaced. Transport exhaustion uses the safe retryable Gmail
API category, preserves the saved cursor, and does not require a cursor reset.

Exhausted transient retries fail only the current page: its records and cursor
do not advance, and prior committed pages remain durable. Repeat the same ingestion
command later to resume from the saved cursor. **Transient quota errors do not
require a cursor reset.** There is no retry daemon or background scheduler.

For a controlled resync: stop all sync writers, protect a database backup, check
that the registered mailbox is still correct, and deliberately clear **only that
account's cursor**, incrementing its version. The following local script is an
explicit operator action, never automatic. Replace the identifiers after reviewing
them; use the same `DATABASE_URL` as the CLI (no URL is printed):

```python
import os
from datetime import datetime, timezone
from sqlalchemy import select, update
from family_os.db import create_db
from family_os.registry import get_account
from family_os.schema import source_sync_state

household_id, account_id = "demo_household", "demo_primary"
engine = create_db(os.environ.get("DATABASE_URL") or "sqlite:///data/family-os.sqlite3")
try:
    with engine.begin() as connection:
        account = get_account(connection, household_id, account_id)
        if account.provider != "gmail" or not account.enabled:
            raise ValueError("Expected an enabled Gmail account")
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

Then run `ingest-gmail` with your deliberately chosen bounded query. Existing
source IDs remain stable; metadata changes retain prior raw snapshots. A resync
cannot reconstruct changes that disappeared from Gmail history, and a bounded
query may omit older messages. It does not promise a complete historical rebuild.

## Retention and limits

Stored metadata: message/thread/history IDs, internal timestamp, label IDs, size
estimate, From/To/Cc/Bcc/Subject/Date/Message-ID/In-Reply-To/References headers, and
attachment filename/MIME type/size/reference. Raw metadata versions and normalized
records remain separate. Bodies, snippets, arbitrary headers/provider fields, and
attachment bytes are excluded. The HTTP field projection excludes `body.data`
at every requested MIME level and `snippet`; the allowlist also strips those fields
from synthetic/full responses before they cross the connector boundary.

MIME metadata is supported through 16 nested child levels. A sentinel detects
further nesting and fails the page rather than silently losing attachment metadata.
There is no attachment fetch endpoint. No body is fetched, so `content_hash` is
null. The existing domain contract needs no transient-body extension in Phase 2A.

Label changes refresh metadata, including TRASH labels. A message fetch returning
404 is treated as source-side disappearance: prior records/provenance remain.
Deletion events do not create tombstones or canonical lifecycle state; that is a
follow-up. Repeated history events fetch once per page and use existing account +
provider ID idempotency. The adapter is synchronous/local, with no UI, jobs,
classification, canonical dedupe, Finance behavior, or Gmail writes.
