# I4b — 安全的家庭待办编辑 / Confirmed fictional task editing

Base main: `b917da7662b56b9e6f79cdee9141f83aa4195787`, merged I4a #88.
Internal preview contract: `t1-fictional-edit-preview-v1`; this is not a deployed
authentication version. **Only an owned disposable fictional database is used.**
No runtime database discovery/migration, real household records, provider calls,
models, OAuth changes or external actions are enabled.

## Existing capabilities reviewed

[T1](v0-1-durable-household-tasks.md) already implements EDIT, current task
read/edit/history rights, household transaction ordering, task/right CAS, exact
actor/request intent hashes and fresh-primary UNKNOWN verification. I4a already
provides a strict local transport, server-held commands, session-bound receipts,
explicit confirmation and sealed execution gates before proving absence.
[I1](stage-i1-safe-read-connection.md), [I2](stage-i2-local-session-boundary.md),
[I3](stage-i3-readonly-task-workbench.md), [I4a](stage-i4a-safe-pending-acceptance.md),
[Stage D](v0-1-household-first-authorization.md) and
[UX1](v0-1-unified-household-ux.md) remain the boundaries, not competing policies.

This slice exposes only assignment, pending → completed and completed → pending.
Reopening **the task** does not reopen Pending or undo its acceptance. Completion
records household tracking, not proof that payment, booking or a reply occurred.
Assignment does not grant task readership, source access or provider-operation rights.

## Data and permission flow

```text
explicit --synthetic-only → I2 owned temporary SQL store → trusted fixed setup
→ I2 terminal pairing → current HttpOnly Cookie / local lease
→ SessionService + T1 household transaction
→ current task grant, task revision and active recipient epochs
→ bounded server-held draft choices → neutral confirmation preview
→ independent explicit confirmation of one receipt
→ original TaskService.apply(EDIT), SQL CAS and actual-actor append-only event
→ fresh authorized TaskService.tasks read → UI (never local task mutation)
```

Both adults coordinate the same `household_task`, with independent grants. A valid
session is not edit authority. The member display cannot select identity. Edit
queries do not join Pending, sources, raw data or acceptance provenance. Source
revocation/private evidence changes cannot become neutral task-edit prerequisites.
Read-only tasks have no executable controls; denied and nonexistent resources have
the same generic error. Current task recipients are not a household directory.

`prepare_edits()` prepares at most four finite commands in one transaction. It
checks task read/edit before selecting recipient IDs/revisions. Only active allowed
read recipients at the current membership epoch are candidates (bounded to two;
over-cap setup rejects). Joint assignment is offered only with two current
recipients; it never adds a recipient. An unchanged assignment/status is not offered.
`_edit_plan()` is shared with the original apply path; it is not browser policy.

The immutable command pins task/right revisions plus ordered
`EditRecipient(person_id, revision, membership_revision)` assertions. The latter
are internal only and participate in the exact intent hash. Before apply, the
current eligible tuple must still match, including change/revert and re-enrollment.
Existing internal commands without this additional snapshot retain their original
fingerprints and behavior. No table or migration changes are needed.

The browser chooses a finite action/assignee from an opaque draft. It cannot supply
the command, request ID, revisions, recipients, grants, dates, titles or identity.
Before issuing a confirmation receipt, the server re-prepares with the same domain
validator and rejects a changed draft; it never silently rebinds the user's choice.
Confirmation invokes existing T1 current-session/access validation again, then CAS.

## Explicit API contracts

All I2 Host/origin, literal loopback, Cookie, Fetch Metadata, no-CORS, custom-header,
body/path and CSP restrictions remain. Fixed assets only; original file:// still
uses `connect-src 'none'`. Default I2 stays session-only, I3 read-only and I4a
acceptance-only. **Only the new I4b runner enables edit routes.**

| Endpoint | Exact input / result |
| --- | --- |
| GET `/api/tasks` | Existing bounded query and authorized SQL page, schema `i4b-task-page-v1`; only adds boolean `can_edit` to I3's neutral task fields |
| POST `/api/tasks/edit-options` | `{id}` → schema `i4b-edit-options-v1`, opaque draft, current neutral task, current permitted assignee symbols; no decision write |
| POST `/api/tasks/edit-preview` | `{draft,action:"assign",assignee}` OR `{draft,action:"complete"/"reopen"}` → schema `i4b-edit-preview-v1`, opaque receipt, before task and exact after assignee/status |
| POST `/api/tasks/edit-confirm` | `{receipt,confirm:true}` → one server-held EDIT attempt at most |
| POST `/api/tasks/edit-outcome` | `{receipt}` → seal gate, verify only the exact EDIT request |
| POST `/api/writes/recover` | `{}` → seal all outstanding gates and verify latest ACCEPT/EDIT preview for this exact session |
| Existing Pending list/preview/accept/outcome | Same minimal I4a inputs/projection; results use the operation-tagged I4b envelope in I4b only |

I4b result fields are exactly `schema, synthetic_only, outcome, receipt, operation`,
schema `i4b-write-result-v1`. Operation is `accept`, `edit`, or null only when the
receipt is withheld/absent. A committed result must have a valid receipt and operation.
Neither task ID nor private evidence is returned in write results. Submit and known
receipt reconciliation validate both operation and exact receipt; no cross-operation
reuse is permitted. The legacy Pending-only recover route is not exposed in I4b:
recovery is explicitly one session-wide write history, not two independent channels.

Requests remain ≤256 bytes; responses ≤16 KiB, canonical ASCII JSON. Exact field,
type, version, enum, identifier, date, order and page validation is independent in
the browser. No raw ORM/dataclass, private source, Pending evidence, annotations,
credential, hash or internal grant version is serialized. No new management route.

## Confirmation, focus and uncertainty

Opening details/choosing an assignee prepares a draft only. Assignment, completion
and reopening each get their own before/after confirmation. Cancel/Escape/navigation
or language change discards the UI draft without applying. Theme changes only paint.
Task details name the current assignee explicitly. Assignment selection and action
buttons occupy separate wrapping regions; the operation-check status strip is not
a task. Assignment changes the lead member only, never the task's existing audience.
Background authorization checks still run every five seconds; identical projections
do not remount the selection or modal. Changed task/capability, revocation or any
failed/invalid read clears the protected dialog/content. Request sequence and session
epochs reject late read/submit responses. No reusable private cache or fixture fallback.

Receipt coordination is shared with I4a, not copied. One session has one latest
preview and unresolved attempt across **both** ACCEPT and EDIT. Issuing a newer
preview retires prior unexecuted gates. A genuinely unresolved attempted UNKNOWN
blocks both kinds of replacement. A known committed/not-applied result stays internally
resolved: later loss of historical source access cannot turn it into an unresolved
write and prevent independently authorized neutral EDIT. Historical result responses
still reauthorize and may withhold that old source result as UNKNOWN.

The server consumes a receipt before apply. Duplicate confirm only verifies, never
applies again. SQL revision/unique request constraints additionally protect independent
adapter races. An unexpected exception, timeout, malformed response or lost reply is
UNKNOWN. There is no automatic write retry, rebase or replacement identity.

Explicit reconciliation first closes the original write gate under the adapter lock,
then uses T1's fresh same-primary connection. Verified absence cannot later become a
write through a delayed confirm. Refresh recovery uses the latest issued preview,
including its operation tag; a previous acceptance success cannot claim a newer edit
succeeded, nor the reverse. Withheld/unverifiable results remain UNKNOWN. Logout,
new pairing/member context and session errors clear frontend intent/details; receipts
remain scoped to exact opaque session, not just Person.

## Bounds and remaining production gates

Drafts/previews expire after 120 seconds; 16 retained receipts and 16 unexpired
drafts per session. They are process memory only; no distributed or durable receipt
service is claimed. I2's 600-second local lease, eight pairing starts and 1800-second
runtime stay unchanged. Exiting deletes the owned fictional store and clears adapter
state. Do not restart to resolve a real uncertain write: this environment has no real
writes or real data, and process loss cannot recover credentials or receipt history.

SQLite BEGIN IMMEDIATE / PostgreSQL READ COMMITTED household locks preserve tested
transaction ordering. Responses built/sent before revocation cannot be recalled.
Five-second polling and bounded request timeout are not zero-latency disclosure
revocation. The controlled post-commit acknowledgment-loss injector is not proof of
arbitrary real partitions, failover or distributed exactly-once delivery.

HTTP loopback is not TLS; Cookies are not port-scoped. Only trusted local processes
and independent browser profiles are suitable. No weakened Cookie/CSP fallback.
Production OIDC/MFA, deployment/DB roles, protected audit, backup/retention, durable
receipt coordination and operational UNKNOWN escalation remain separate gates.
R0–R3, independent restore/reviewer consent and disabled Alternative B are unchanged.

## PR #88 five non-blocking observations

| Finding | I4b disposition |
| --- | --- |
| N1 capability/type hint | Added explicit action/mixed-service condition to the T1 hint, matching the existing preview validator. The existing SQL `valid_pending_support` also rejects a supported question; no schema relaxation or new acceptance rule. Regression covers this constraint. |
| N2 in-memory receipts / cap | Retained, documented; drafts are also bounded per exact session. Durable/distributed stores are outside this fictional slice. |
| N3 long-lived UNKNOWN escalation | Retained fail-closed; shared blocker covers ACCEPT and EDIT. No unsafe override/restart-as-proof or new identity. Production escalation is deferred. |
| N4 adapter audit | Domain audit remains actual-actor, durable and append-only; no adapter telemetry/store added merely to clear a suggestion. Receipt issuance/recovery operational audit needs separate privacy/retention design. |
| N5 UNKNOWN blocks read-only details | I4b allows current-authorized task details and nonaccepting Pending inspection while unresolved; mutation/preview controls remain blocked. No extra protected history or source disclosure. |

## Windows PowerShell: independent test run

From the repository root, existing Python 3.12 environment. Do not run runtime DB
Alembic/register/OAuth or set a real database target:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Editable installation failed.' }
.\.venv\Scripts\python.exe -u .\prototypes\i4b-workbench\serve_editing.py --synthetic-only
```

1. Open the printed 127.0.0.1 URL, request a fictional session. In the same terminal,
   match its public ID: `approve REQUEST_ID clara`. In a truly independent Chrome/Edge
   profile, request/approve Devon. A second window sharing Cookie is not another adult.
2. Initial task totals are Clara=3, Devon=2. Open the dated school task. Choose Devon:
   no save yet. Inspect before/after, cancel once, then repeat and confirm. Both adults
   reload the same task/assignment, with totals unchanged.
3. Mark completed, cancel/Escape once; repeat and confirm. Then independently confirm
   restoring pending. Same task, no duplicate and no external completion claim.
4. Pending acceptance remains independently confirmed. Accept the shared school
   suggestion: totals become 4/3; this is not a task edit. High-risk/questions cannot
   be accepted. No personal archive/defer buttons are connected.
5. If a submit is interrupted, do not repeat it. Use “核对最近操作 / Check latest
   operation”, including after refresh under the same session. Unknown stays unknown;
   proven absence requires a fresh preview and confirmation, never automatic retry.
6. Check Chinese/English, system/light/dark, 320/390, keyboard focus and cancellation.
   Terminal `quit`, EOF or Ctrl+C stops the service and deletes only its temporary DB.
   Windows actual fonts, zoom, Cookie support and UX remain manual merge gates.

## Verification and screenshots

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_i4b_workbench.py tests/test_i4a_workbench.py tests/test_household_tasks.py tests/test_i3_workbench.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
# Existing approved Playwright installation and local Chrome; no downloads.
$env:I4B_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I4B_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node .\tests\browser\i4b-editing.js --synthetic-only
```

Local verification: **80 new pytest cases passed**, plus the existing T1 migration
roundtrip/metadata probe. Actual-origin Chromium: **17 I4b + 15 I4a + 28 I3 checks
passed**. Existing ACCEPT/EDIT fingerprints were also compared against merged main
and preserved. `pip check`, JS/Python syntax and 137 local Markdown targets passed.
These are synthetic checks, not Windows or production certification.

Automated tests use pytest-owned SQLite/PostgreSQL schemas; no runtime database or
frozen dataset. The browser uses normal CSP, real Cookie and owned SQL, with controlled
synthetic fault/revocation stdin commands unavailable to browser clients. Final exact
test totals and CI links are reported on the PR, not borrowed from #88.

| Actual synthetic UI | Screenshot |
| --- | --- |
| Assignment confirmation, desktop | [Preview](screenshots/i4b/assignment-preview-desktop.png) |
| Clara authorized SQL task page | [Light desktop](screenshots/i4b/tasks-clara-desktop.png) |
| Clara dark theme | [Dark desktop](screenshots/i4b/tasks-clara-dark-desktop.png) |
| Devon authorized page | [Light 390](screenshots/i4b/tasks-devon-light-390.png) |
| Independent completion confirmation | [Chinese 390](screenshots/i4b/completion-preview-zh-390.png) |
| Independent reopen confirmation | [English dark 320](screenshots/i4b/reopen-dark-en-320.png) |
| Devon shared task results | [English dark 390](screenshots/i4b/tasks-devon-dark-en-390.png) |

## Next: personal Pending persistence, not part of I4b

T1 already has REVIEW, DEFER and NEEDS_INFORMATION annotations, exact evidence binding
and actor history. Those are unresolved personal annotations, not archive or acceptance;
the current shared Pending revision can still cause independent personal decisions to
conflict. UX1's in-memory personal categories are not durable T1 states.

Before browser integration: define independent member decision revisions, current
source/review rights, evidence generation invalidation, authorized active/later/archived
queries/counts/pages and exact request/UNKNOWN handling. ARCHIVE/REOPEN need explicit
new semantics, original-actor permission, no deletion/safety clearance and no effect on
the partner's independent decision or accepted task. No reviewed=true reinterpretation.
Date/title editing, deletion, undoing acceptance, production auth and external activity
remain excluded. ChatGPT and Muse review plus Windows human verification precede any
human-controlled merge; no automatic merge or production enablement.
