# I8 — Personal not-applicable and resume

Internal semantic contract `i8-viewed-judgment-v2`; names a contract, not a historical deployment.
This opt-in localhost workbench uses disposable fictional SQLite/PostgreSQL state.
No real data, models, provider activity, household rejection, task automation or
production login is authorized. One authoritative T1 store and original I7
receipt/UNKNOWN coordinator remain. Finance is unchanged.

## Approved conditions and state

NOT_APPLICABLE records one person's opinion, not objective absence of an obligation,
safety clearance, completion or a household decision. Mandatory reason, no default:
`not-my-responsibility`, `not-participating`, `personal-judgment`. These are bounded
Python/DTO/UI/SQL enums, never free text. Reasons enter only the actor's event;
no private annotation/reason enters a Task or shared task history. This slice does
not display a previously saved current reason or introduce a history endpoint.

| Operation | Own reviewed | Own disposition |
| --- | --- | --- |
| REVIEW | true | unchanged |
| DEFER | unchanged | deferred |
| NEEDS_INFORMATION | unchanged | needs-information |
| NOT_APPLICABLE | true | not-applicable |
| RESUME | unchanged | active |

Explicit NOT_APPLICABLE confirmation is itself a viewed personal judgment. The
same transaction sets own `reviewed=true` and `disposition=not-applicable`, records
the finite reason in exactly one NOT_APPLICABLE event and increments Pending once.
No second REVIEW operation/receipt or confirmation is generated. Cancel/Back/Escape
and previews do not write. DEFER and NEEDS_INFORMATION still preserve viewed state.

### Current evidence and historical I8 events

After current authorization, a committed own REVIEW **or NOT_APPLICABLE** event
must match the exact household/Pending/actor/generation/fingerprint/definition to
prove viewed. The event existence is authoritative for the projected boolean;
`pending_member_right.reviewed` is a compatibility cache, never another current
state source. A cache alone cannot prove viewing or mask a matching event.

This applies consistently to earlier I8 NOT_APPLICABLE events as well: an unchanged
current-evidence judgment now projects viewed even if its earlier writer left the
cache false. No historical event, intent hash, reason, revision or cache is rewritten
by reading or exact replay. On a later personal write the cache is synchronized to
the effective viewed projection in the same transaction; RESUME/DEFER/NEEDS_INFORMATION
preserve that value rather than independently marking viewed. Source evidence
changes/reverts invalidate both event proofs; an old true cache cannot revive them.
Thus raw cache values are not exposed as competing current flags in UI/API/filters.

No new migration is needed: the existing boolean, operation enum and bound event
already encode these facts. Revision `063c9d841fe5` and all older revisions remain
unchanged, including downgrade refusal after any I8 event. The v1 DTO field shapes
remain unchanged; strict preview validation now requires viewed=true after a
NOT_APPLICABLE operation. Original I7 and earlier operation allowlists stay pinned.
All Command fingerprint bytes, including earlier I8 requests, remain unchanged;
exact replay reports historical outcome without reapplying or changing history.
The separate internal v2 name documents semantics, not a separately deployed service.
The frozen `i8-personal-v1` intent namespace remains byte-identical.

RESUME is allowed only from an **effective current-evidence** non-active state,
not the persisted cache alone. A new RESUME request from active is rejected.
An exact committed RESUME replay is recognized first, under current access,
and may report its historical result even though the state is now active.
All new personal decisions require unresolved Pending. No personal operation
reopens accepted Pending, cancels/recreates a Task, changes risk or grants access.
Not-applicable does not alter independent acceptance authority: an authorized
adult can still separately preview and explicitly accept a currently safe supported
suggestion. That is not combined with personal handling.

Current personal state requires own event evidence matching generation, fingerprint
and definition. Change/revert cannot revive old decisions. RESUME preserves viewed
for this generation and does not turn old viewed evidence into a current receipt.
No reset-viewed or clear-all operation exists. All includes all authorized unresolved
items, including not-applicable; Home always uses All. Non-all categories are disjoint:
active+not viewed, active+viewed, deferred, needs-information, not-applicable. A
non-active disposition determines the category regardless of reviewed.

## Authority, commands, replay and concurrency

Current session/binding/member -> existing G2a source observations -> Pending read
and independent can_review -> exact Binding/Pending/rights revisions -> operation
validation -> original CAS and actor audit. No browser actor/household/grant input.
Both prepare and apply use the same personal transition validator. Shared Pending
revision remains: two adults may get generic STALE; no silent rebase or disclosure
of a peer's choice. This does not eliminate inherited revision timing signals.

Only the two new operations carry reason/source-grant-revision fingerprint fields.
All original operations keep exactly the old intent bytes. Source revision is an
additional new-operation binding, not a second permission engine. Current access
is checked before historical lookup. Exact committed replay can prove historical
success; otherwise source revision change (including revoke/regrant), rights,
evidence or Pending revision mismatch prevents a new write. A replay does not
reapply its old state: the UI rereads current authorized state.

Original exact-session receipts remain opaque, finite and short-lived. New/old
operation routes cannot exchange receipts. UNKNOWN across Accept/Edit/personal
operations blocks new writes. No retry, new request ID or rebasing on timeout.
Explicit outcome checking retires the original gate before fresh same-primary
verification proves absence. Revocation may prevent disclosure of an old result;
verification then remains UNKNOWN. No client private-data cache or persistent state.

## Migration safety gate

New revision `063c9d841fe5`, parent `f52b8c730ed4`; no old migration changes.
Extend pending_member_right disposition CHECK and task_domain_event scope CHECK;
add nullable personal_reason with operation-specific finite CHECK. No extra reason
cache/table. Old rows/IDs/hashes/versions/events remain unchanged, old reasons NULL.
Both rebuilt SQLite tables are FK leaves; foreign_keys stays ON.

SQLite explicitly starts BEGIN IMMEDIATE when no physical transaction exists and
checks driver.in_transaction before DDL. It never uses autocommit_block. The two
leaf rebuilds and Alembic version update share the physical transaction. Tests
inject errors after each table and during version update and compare all old rows,
constraints and version after rollback. This is not a claim about atomicity of all
historical migrations. PostgreSQL uses transactional DDL and the same fault matrix.
A failure to prove this gate stops implementation, rather than allowing partial DDL.

Downgrade checks BEFORE schema mutation: any new operation event, non-null reason
or not-applicable cache rejects it, including RESUME followed by active. Never
coerce/drop/export events to fit I7. Only databases with no I8 state/history may downgrade; their downgrade/upgrade
keeps all old fields unchanged. FK/unique/index/check integrity and Alembic metadata
agreement must pass on fresh installs and populated I7 upgrades. Historical earlier
revisions have their original separate downgrade behavior; retain I8 whenever its
history exists. No migration is run on an actual runtime/household database.

## Interface and UI contract

Independent I8 opt-in runner/DTOs/operation allowlists; old I7 and earlier routes
keep their existing contracts. A legacy client seeing a new state must fail closed,
not map it to active/deferred. Permission precedes query, own-state selection,
counts, pagination, projection and historical lookup. No peer reasons or statistics.

Reuse the I7 fixed header, scrolling body, fixed footer, theme and filter spacing.
Fourth personal choice: 对我不适用 / Not applicable to me. No reason default;
changing option/reason invalidates old previews immediately. Save requires the
matching preview and explicit confirmation. Resume has its own preview/confirmation,
not a fifth radio choice or shared save shortcut. Back/Cancel/Escape/navigation,
language change and session change never save. Late results cannot revive controls.

## Required implementation validation

- Two peers: own state/reason only; All/Home and server total/pagination remain honest.
- Every transition, reviewed preservation, current binding/change/revert, accepted Task independence.
- Source/Pending/review/member/session revoke and source revoke/regrant; no receipt transfer.
- Shared CAS, duplicate concurrent submission, changed intent, exact historical replay,
  pre-write failure/rollback, lost commit response, UNKNOWN, fresh outcome, late retired POST.
- SQLite/PG16 fresh install and populated I7 upgrade; original fields, constraints,
  metadata agreement, failure rollback; reject downgrade even after resume.
- Real browser: both peers/languages/themes, desktop/390/320, keyboard/focus, dialog
  bounds, no default reason, option/late preview races, cancellation and separate acceptance.
- I3/I4a/I4b/I5/I6/I7 default routes and offline prototype unchanged; old-client new-state failure.

Implementation validation and Windows steps follow below. ChatGPT and Muse review plus owner Windows verification and
human merge remain mandatory. This contract grants no production deployment rights.


## Implemented API and data flow

I8 alone serves `/personal.js` and `/personal.css` before the existing I7 wrapper.
I7 gains small default-preserving presentation/DTO hooks, not new permissions.
The I3 orchestration uses the wrapper's personal-operation classification only for
success navigation/feedback. Without I8, original operation lists and DTOs remain.
An old I7 response containing not-applicable is rejected, never coerced; unrelated
hidden own-state populations do not affect another reader's responses.

| Endpoint | Strict body/query | Versioned result |
| --- | --- | --- |
| GET `/api/pending` | Existing bounds and optional six-value `state` enum | `i8-personal-pending-page-v1`, own can_resume plus original minimized fields |
| POST `/api/pending/review-preview` | id/revision/operation; reason required only for not-applicable, forbidden otherwise | `i8-personal-preview-v1`: own before/after state, exact selected reason or null, opaque receipt |
| POST `/api/pending/review-confirm` | receipt, confirm:true only | `i8-write-result-v1` with exact operation/outcome |
| POST `/api/pending/review-outcome` | exact original receipt | Same result, read-only verification/retirement |
| POST `/api/writes/recover` | empty object | Original exact-session recovery across Accept/Edit/personal operations |

The browser cannot supply an actor, household, source grant revision, evidence,
rights, recipients or arbitrary Command. New source epochs remain server-held.
Session -> current authoritative rights -> single T1 prepare snapshot/transition
validator -> short-lived server receipt -> independent confirmation -> same T1
validator/CAS/atomic own event -> authorized reread. No browser mutation substitutes
for a database result. Preparing may touch session activity, never a domain decision.

Original 256-byte bodies, 16KiB JSON/page bound,20-item maximum and deterministic
server pagination remain. No new endpoint returns saved reasons, private history,
source identifiers or other members' decisions. An in-flight old option response
cannot reenable Save after a reason/option/dialog/session change. A detached or
disabled old confirmation control cannot submit a new Resume preview; an actual
browser regression invokes the old Save after opening Resume. An incomplete
reason clears the client's submit-capable preview; publishing the next valid
server preview retires previous unexecuted receipts through the original coordinator.
Cancel does not recall an already submitted operation; UNKNOWN must be reconciled.

## Initial implementation validation

- Complete local SQLite: **7,048 passed in443.50s (0:07:23)**, including97 new
  cases beyond the6,951 merged baseline.
- 97 focused new pytest cases:42 domain,14 migration,41 adapter; includes both leaf
  table failure boundaries and version-update failure, original event preservation,
  source revoke/regrant and committed historical replay. Exact PG16/full-suite
  results, final SHA and all CI job links are recorded in the PR after completion.
- 90 strict Node DTO/reason/legacy-client checks; I7 and I6 retain30 cases each.
- 24 real-browser peer/language/theme/width combinations and16 interaction/privacy
  scenarios. Reasons have no default; a changed reason cannot reuse the previous
  receipt. Both pending and task permission boundaries remain server-owned.
- Real I7 and I4b browser regressions passed, including separate acceptance/editing;
  other default launchers, Home and responsibility-filter results are listed in PR.
- The old I5 migration preservation test now explicitly omits only the new nullable
  column at the historical T1 target, first proving it has no values. Every original
  field is still compared. No safety assertion is removed to accommodate I8.
- Browser matrix groups use fresh independent sessions within the unchanged8-pair
  startup and16-preview/session caps. Neither limit is raised for testing or UI.

### Owner-approved viewed semantics follow-up

This supersedes the earlier Windows-feedback expectation that not-applicable could
resume unviewed. Both initially viewed and initially unviewed NOT_APPLICABLE → RESUME
paths now finish viewed+active. Regression coverage includes legacy false caches,
no read/replay mutation, one-event atomicity, cancellation, peer privacy, current
proofs/change/revert, deferred/needs-information preservation and frozen I7/I8 intent
hashes. Actual final test counts and both SQLite/PostgreSQL CI links are on PR #97.

Repeat locally using owned fictional test DBs only:

```sh
.venv/bin/python -m pytest -q tests/test_i8_personal.py tests/test_i8_migrations.py tests/test_i8_workbench.py
node tests/browser/i8-contract.test.js
NODE_PATH=/opt/codex/runtimes/cua/lib/node_modules node tests/browser/i8-personal.js --synthetic-only --screenshots
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
git diff --check
```

The SQL fault injector is an intentional exception after real database operations,
not proof of every disk/network failure. Local browsers are Linux Chromium;
Windows/Chrome/Edge native controls, cookie behavior, zoom and fonts require owner
manual acceptance. The inherited HTTP loopback cookie port-scope, process-local
receipts, read-to-dispatch races, shared revision timing and unable-to-recall-delivered
bytes limitations remain. Stop the disposable lab if an UNKNOWN cannot be resolved.

## Windows owner acceptance

From repository root with the existing Python3.12 virtual environment:

```powershell
git fetch origin
git switch feat/i8-personal-not-applicable-resume
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Editable installation failed.' }
.\.venv\Scripts\python.exe -u .\prototypes\i8-workbench\serve_personal.py --synthetic-only
```

No DATABASE_URL or runtime DB path is needed or discovered. Keep the terminal open;
use its printed exact loopback origin in two independent Chrome/Edge profiles.

1. Request pairing in each profile; in terminal approve the matching public request
   with `approve REQUEST_ID clara` / `approve REQUEST_ID devon`; run `process`.
2. On Clara's school item, without first marking viewed, open personal handling, choose
   Not applicable: Save must stay disabled until an explicit reason is selected.
   First Back/Escape without saving; repeat and explicitly confirm.
3. Devon's own state must remain unchanged. Clara sees Viewed by me · Not applicable
   to me and can find it in both All and Not applicable; Home's All count does not shrink. No Task is created.
4. Inspect Resume, first cancel, then explicitly confirm. Clara stays viewed and
   becomes active; the item belongs to Viewed by me, not Not handled. Devon is
   unchanged. There is no reset-viewed or global dismissal control.
   Repeat on an item already marked viewed: Not applicable → Resume also ends
   viewed+active. Before saving, test Back, Close and Escape on an unviewed item:
   they must leave both fields unchanged. Not applicable itself now records viewing;
   Resume only preserves the effective viewed flag. Plain deferred/needs-information
   items without viewed proof still resume unviewed. The entry has no ellipsis.
5. Record another personal choice, then terminal `change`, followed by `revert`.
   Neither old viewed/disposition may become current again. Do this BEFORE task
   acceptance: accepted tasks deliberately have an independent history lifecycle.
6. On current safe school evidence, Not applicable must not auto-accept or prevent
   an independently authorized acceptance preview. Cancel acceptance first, then
   explicitly accept. Exactly one shared Task appears; no new personal decision
   can be made on that accepted Pending. No outside activity executes.
7. On an uncertain item, personal handling never creates safety clearance or an
   acceptance button. Verify Chinese/English, Light/Dark, desktop390/320, scrolling,
   fixed header/footer, Tab/Escape/Back and complete native control labels.
8. `pages` tests the preserved authorized backlog; filters reset page offset. No
   browser grant/producer endpoint exists. Automated fault/revoke cases use the
   trusted test host, not additional product controls.
9. `quit` / Ctrl+C closes and cleans the owned temporary lab; refreshed browser
   must not continue showing unverifiable data. Old file-based offline demo remains.

Do not raise caps for manual use: each run has at most8 pairing starts, receipts
are at most16 per session with120-second preview expiry, and runtime is bounded.
Restart the disposable lab for another test round rather than bypassing guards.

## Actual connected I8 screenshots

All images are real browser renders from the owned fictional I8 server:

- [Chinese not-applicable desktop](screenshots/i8-personal/not-applicable-zh-CN-light-1440.png)
- [Chinese not-applicable390](screenshots/i8-personal/not-applicable-zh-CN-light-390.png)
- [Chinese not-applicable320](screenshots/i8-personal/not-applicable-zh-CN-light-320.png)
- [English dark not-applicable desktop](screenshots/i8-personal/not-applicable-en-US-dark-1440.png)
- [English dark not-applicable320](screenshots/i8-personal/not-applicable-en-US-dark-320.png)
- [Chinese resume desktop](screenshots/i8-personal/resume-zh-CN-light-1440.png)
- [Chinese resume390](screenshots/i8-personal/resume-zh-CN-light-390.png)
- [Chinese resume320](screenshots/i8-personal/resume-zh-CN-light-320.png)
- [English dark resume desktop](screenshots/i8-personal/resume-en-US-dark-1440.png)
- [Own not-applicable list desktop](screenshots/i8-personal/own-not-applicable-zh-CN-1440.png)
- [Own not-applicable list390](screenshots/i8-personal/own-not-applicable-zh-CN-390.png)
- [Own not-applicable list320](screenshots/i8-personal/own-not-applicable-zh-CN-320.png)
