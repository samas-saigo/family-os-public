# I7 — Authorized fictional Pending handling

## Scope and trust boundary

This opt-in local runner extends [I6](stage-i6-authorized-pending-explanations.md)
with the existing [T1](v0-1-durable-household-tasks.md) personal REVIEW, DEFER and
NEEDS_INFORMATION operations. It owns a disposable fictional database, retains
[I2](stage-i2-local-session-boundary.md) same-origin loopback/session controls and
[I4b](stage-i4b-safe-task-editing.md) shared receipt coordination. No production
login, household data, provider/model access, real message preview, external action,
automatic acceptance, archive or global rejection is enabled. Old launchers keep
their existing schemas and deny the new routes. File-based offline H1 is unchanged.

There is one authoritative T1 Pending/Task store. There is no browser review store,
private persistent cache, new migration, fixture modification or new permission.
The fixed terminal feeder remains the only producer; the browser cannot create
fixtures, change grants or select an authenticated identity.

## Personal semantics

| Choice | Explicitly confirmed durable effect | Does not mean |
| --- | --- | --- |
| 标记已查看 / Mark viewed | Own `reviewed` flag and immutable REVIEW event for this exact evidence | Accepted task, safe information, shared read receipt or completed action |
| 稍后处理 / Handle later | Own `deferred` disposition and DEFER event | Resolved, hidden, automatic reminder or task |
| 需要更多信息 / Need more information | Own `needs-information` disposition and event | Inquiry sent, obligation disproved or safety clearance |
| Existing acceptance preview → confirm | Original T1 ACCEPT creates one independently shared neutral Task | Any provider execution, new source sharing or automatic task approval |

Opening/closing an explanation never applies a decision. Choosing a handling option
prepares a preview, not a save. Cancel, Escape, navigation, language changes and
refresh discard an unconfirmed preview. Theme selection remains visual only.
Preparing/reading may update session activity; it does not append a domain decision.

`reviewed` and `disposition` remain independent. Display reviewed when true, then
append the disposition when non-active: for example “我已查看 · 我已暂缓”. If
neither applies, display “尚未处理”. Never collapse these into mutually exclusive
stored states. REVIEW does not reset an existing disposition; DEFER and
NEEDS_INFORMATION replace only the own disposition. A new “resume active” command
is not part of this slice. Do not infer another member's behavior, or announce success before a verified
COMMITTED/REPLAY result followed by a successful authorized reread.

## Current evidence, permissions and concurrency

Each read uses current SessionService identity, membership/binding epochs, source
observation rights and independent Pending read rights. Review preparation and apply
also require current `can_review`. Review does not imply publication/security rights;
acceptance retains its original security/publication/recipient-plan checks.

`TaskService.prepare_review()` creates a server-owned immutable existing Command
with the exact operation, Pending revision, independent rights revision, evidence
generation/fingerprint/definition and random request ID. It requires an unresolved
Pending and the displayed revision; it cannot silently rebase a stale dialog.
Apply reuses existing T1 `_access`, CAS, evidence equality, atomic mutation/event
append and actual actor audit. No client-supplied actor, household, source, grant,
binding or arbitrary Command is accepted.

T1 still uses a **shared Pending revision** for annotations. Two peers preparing the
same revision can race: one commits and the other receives STALE, reloads and makes
an explicit new choice. Neither silently overwrites the other's annotation. This is
not a member-independent revision redesign; a future change needs its own privacy/
CAS/idempotency contract and historical-event compatibility review. No cross-peer
history or reason for the generic stale result is disclosed. Already visible shared
revisions are not claimed to hide all timing signals from peer activity.

T1's exact-evidence own-event predicate makes old annotations non-current after
I5 `change` and `revert`, including a return to the same business bytes. Append-only
history remains intact. I5's all-reader revocation invalidation remains unchanged:
regrant cannot revive old acceptance. If a Task was already accepted, I7 refuses new
personal previews for that resolved Pending; late previews encounter CAS/current
rights checks. No annotation reopens, deletes or recreates the Task. Published Task
reads/editing remain independent from source-read permission and private annotations.

## API and shared write coordinator

Only `prototypes/i7-workbench/serve_reviews.py --synthetic-only` extends these paths:

| Method/path | Strict input | Safe result |
| --- | --- | --- |
| GET `/api/pending` | Existing bounded limit/offset/step, optional enum `state` | `i7-personal-pending-page-v1`, exact query echo, own current state/capabilities |
| POST `/api/pending/review-preview` | Exact `{id, revision, operation}`; operation only review/defer/needs-information | `i7-personal-preview-v1`: id/revision/operation and opaque session-bound receipt |
| POST `/api/pending/review-confirm` | Exact `{receipt, confirm: true}` | `i7-write-result-v1`, original operation and authoritative outcome |
| POST `/api/pending/review-outcome` | Exact `{receipt}` | Read-only exact-request verification; seals late execution |
| POST `/api/writes/recover` | Existing empty object | Same latest receipt/operation recovery across personal/Accept/Edit |

No personal history API/UI is added. Existing internal T1 history remains current-
authorization-checked and actor-scoped for Pending. Shared Task history never copies
personal review entries. No full ledger, private source ID, evidence fingerprint,
rights revision, arbitrary metadata or another member's annotation reaches new JSON.
Unknown resource and unauthorized resource retain the same generic failure.

Bodies retain the existing 256-byte bound; JSON is canonical ASCII with exact key,
type and enum validation. Pages retain 20 maximum items and 16 KiB response bound.
Query rejects duplicate/empty/encoded/unknown parameters. Original Host/Origin,
Cookie, Fetch Metadata, CSRF intent, CSP, no-store and runtime/lease limits remain.
Preview receipts remain exact-session-bound, finite (16), short-lived (120 seconds)
and operation-tagged. A review receipt cannot pass an accept/edit endpoint or vice
versa; the result parser cannot mistake an old accept success for a review success.

I7 reuses the same `Receipt`, `last_attempt`, `guard_preview`, `issue`, retirement,
apply and verification code. It does not introduce another write scheduler. A
possibly submitted personal/Accept/Edit request blocks new writes while unresolved.
UNKNOWN is never auto-submitted again or rebound under another request ID. Explicit
outcome/recovery seals the old execution gate **before** fresh same-primary database
verification proves absence. Durable audit yields COMMITTED/replay; verified absence
yields NOT_APPLIED; unavailable verification stays UNKNOWN. Refresh may recover only
the original exact-session request; logout/re-pair cannot inherit it.

This is the existing controlled file-SQLite/PostgreSQL fictional database contract,
not proof against arbitrary replica routing, malicious DB operators, browser process
memory inspection or real network failure. Lost in-process receipts cannot be
recreated by guessing a request ID. Stop the disposable lab if unresolved state cannot
be reconciled. Real deployment needs durable dispatch/recovery and authenticated
transport review.

## Server-side personal filters and counts

Default **All** includes every currently readable unresolved Pending, including
viewed, deferred and needs-information items. No unresolved backlog is silently
removed. Native select “我的处理状态 / My handling status” provides:

- `all`: all authorized unresolved items;
- `unhandled`: effective disposition active and reviewed false;
- `viewed`: effective disposition active and reviewed true;
- `deferred`: effective disposition deferred, regardless of reviewed;
- `needs-information`: effective disposition needs-information, regardless of reviewed.

These four non-all buckets are disjoint display categories, not a replacement for
the two independent fields. The authorized T1 query first resolves source/Pending
rights, then exact-evidence own annotation, then state and optional step predicates,
then total, deterministic ID order and limit/offset. Hidden rows never enter counts
or pagination. Existing Task responsibility/type filters are untouched.

The browser validates the query echo, expected page and own-state fields, rejects
late sequence/session responses, and does not filter a partial page as a global
collection. Changing a personal filter resets offset. Leaving/reentering Pending or
changing session resets All. Ordinary reload/polling preserves the current filter.
Home always queries All independently. No per-category global counts are fabricated.
An empty category says it has no authorized matching Pending, not permission denied.

## Browser behavior and limitations

I7 alone uses a unified Pending dialog: fixed title/date/own-state header and
Close control, independently scrolling explanation body, and a persistent footer.
The footer contains acceptance preview only when current can_accept permits it,
and “记录处理方式 / Record my handling” only when can_review permits it. There are
no inline explanation action buttons or three-button handling block in the main view.
Default I6 keeps its original presentation; only I7 serves `reviews.css`. Cards show a
compact own-state line and a Details button; acceptance still has its separate preview
and confirmation. Existing legacy synthetic Pending has neutral handling details,
without pretending to have an I5 explanation. Security/high-risk/unknown/conflicting
items that are otherwise readable can be annotated but never cleared by annotation.
Promotion-only, pure information and I5 security-held records never enter ordinary
Pending through the new routes/filters.

“Record my handling” opens a second view in the same native dialog. Three native
radio choices include their exact effects. Selecting one prepares the original
server-held review-preview receipt; it saves no decision. Confirm save starts
disabled and enables only after the matching preview is validated. Back discards
the choice and reopens an I5 explanation with a fresh authorized read. Legacy
fixture items return to their neutral list-based detail, with the existing periodic
revalidation; they do not acquire an I5 explanation. Save uses the
unchanged review-confirm/shared UNKNOWN coordinator. An option-request sequence,
dialog epoch and session epoch prevent a late old choice preview from enabling or
replacing the current choice. Acceptance retains its independent preview/confirmation.

The header and footer do not scroll with the body. Bounds follow available viewport
height, narrow buttons stack without clipping, new detail bodies reset scroll, and
background document scrolling is locked only while the I7 Pending modal is open.
Native dialog keyboard containment/Escape remains; Close restores the connected
launching control, or main when the old control is no longer available. No claim of
secure client memory erasure or stronger revocation/dispatch guarantees is added.

All text uses finite bilingual templates and textContent, native select/buttons,
existing dialog keyboard/Cancel handling and Calm Premium CSS. No real notification
content, new deadline or AI explanation is invented. Failed reads clear protected
lists/details; preview failure never implies a save. Known result feedback is
operation-specific and ARIA-live. Original 5-second polling/5-second request bounds
remain; already delivered bytes cannot be recalled. Cookie port-scope and HTTP
loopback limitations remain; this must never be used with real household data.

## Future “Not required” decision — not implemented

[I8](stage-i8-personal-not-applicable-resume.md) implements a separately opt-in personal
not-applicable/resume extension. The following preserves the original I7 boundary;
I7 itself keeps its old DTOs/operations and rejects unfamiliar personal states.

A person's “not applicable to me” is a reversible own disposition, not household
rejection or proof that nobody has an obligation. A global determination needs an
independently approved resolution/authority contract and a way to represent peer
disagreement without last-click-wins. Unknown/conflicting/unsupported evidence is
insufficient proof of no action. Missing sources and advertising must not supply
implicit closure authority; suspicious items remain governed by safety policy.

Candidate follow-up: a new explicitly named own NOT_APPLICABLE operation bound to
current member/source/Pending rights and exact evidence, with an explanatory preview,
append-only reason enum and revision/CAS/replay protection. It must remain retrievable,
reopenable only under fresh rights, and invalidated by changed/reverted evidence. It
must not change another adult's state, the global resolution, safety or an accepted
Task. Whether it leaves the main list and what constitutes sufficient human evidence
need product/privacy approval. Household rejection is a separate unresolved design.

This would require separately reviewed Operation/DTO/event and disposition constraint
changes, migration of the allowed enum without rewriting historical facts, and bounded
new tests. Backup disposable/approved data before upgrade; a downgrade must reject
or explicitly preserve/export new states/events rather than silently coerce them to
REVIEW/DEFER. Exact migration and rollback policy remains unapproved. I7 adds no
misleading “不需要处理” button, global close/reject, archive/reopen, schema change or
permanent suppression rule.

## Windows manual acceptance

From the checked-out PR root, with Python 3.12 and the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Editable installation failed.' }
.\.venv\Scripts\python.exe -u .\prototypes\i7-workbench\serve_reviews.py --synthetic-only
```

Do not run Alembic against a runtime database or set up provider OAuth. Startup owns
and cleans its temporary fictional DB. Open the printed loopback address in two
separate Chrome/Edge **profiles**, not two tabs sharing cookies. Request pairing in
each, match its public request ID in the terminal, then:

```text
approve CLARA_REQUEST_ID clara
approve DEVON_REQUEST_ID devon
process
```

1. Clara: Pending → school Details → 记录处理方式 → select 标记已查看. Back first; no state changes.
   Repeat and confirm save. Devon reloads; his own school state stays unhandled.
2. Clara: school Details → 记录处理方式 → 稍后处理 → 确认保存. Select 我已暂缓; both viewed/deferred
   markers remain visible. Return to All; the item remains unresolved.
3. Devon: conflicting question Details → 记录处理方式 → 需要更多信息 → 确认保存. Find it in that category;
   no Task is created. Opening any other Details alone changes nothing.
4. Before accepting school, terminal `change`, then `revert`, with reload after each.
   Old school annotations are no longer current in either generation; new handling
   requires an explicit save. Existing original history remains internal/immutable.
5. Clara: current safe school explanation → acceptance preview → Cancel, then repeat
   and confirm. Exactly one shared Task appears; Devon sees the same Task through
   his independent task grant. No action executes in the outside world.
6. `pages` creates the independently preapproved 14-item fictional pagination set;
   verify next/previous and switching personal filters resets to page one. Home's
   Pending summary stays All. Tasks' responsibility filters remain independent.
7. Check Chinese/English, light/dark, desktop/390/320, Tab focus, Escape and scroll.
   Test failure/revocation/UNKNOWN with the automated fixture host, **not browser
   grant/producer controls**; no such product endpoints exist.
8. `quit` or Ctrl+C stops and cleans the disposable environment. Refreshed browser
   must not display old authorized data after shutdown.

Windows native controls, fonts, zoom and two-profile cookie behavior require product
owner manual approval. Automated Chromium/Linux is not Windows manual validation.

## Validation and review gates

Commands used for owned fictional data:

```sh
.venv/bin/python -m pytest -q tests/test_i7_reviews.py
node tests/browser/i7-contract.test.js
NODE_PATH=/opt/codex/runtimes/cua/lib/node_modules node tests/browser/i7-reviews.js --synthetic-only --screenshots
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
git diff --check
```

Executed for this UX follow-up: 66 focused I7 pytest cases, 30 strict Node
contract cases, 24 actual-origin peer/language/theme/width combinations checking
both main and personal views, and 17 interaction/privacy checks. Geometry assertions
measure title/Close/footer visibility before and after independent body scrolling,
including a 320×600 short screen, background lock and scroll reset. Additional cases
cover Back/cancel/focus, no default radio choice, out-of-order successful previews,
revocation and user switching. Default I6's 24 layouts + 17 checks and I4b's 47
browser checks also passed. Final full-suite/other browser results and exact-head
SQLite/PostgreSQL16 CI links are recorded in the PR after execution. PostgreSQL16
runs the same complete suite (including disposable migration roundtrips and metadata
agreement); no runtime database migration is performed. Required independent gates:
ChatGPT, Muse security review, Windows human acceptance and human-controlled merge.
No automatic merge or production enablement.

### I7 filter spacing follow-up

The personal-state label and select share an I7-only wrapping flex row: 16px
horizontal gap, 12px row gap, vertical centering and 16px separation from the
current authorized count. Narrow layouts wrap without changing the native
label/control association, filter events or server pagination. The I7 stylesheet
is not served by default I6 or older launchers.

Actual-browser geometry checks cover both peers, Chinese/English, light/dark and
1440/390/320px: desktop label/control centers and gap, narrow wrapping, count
spacing, keyboard focus and no overflow. Capture the list-only comparison with
`node tests/browser/i7-reviews.js --synthetic-only --filter-screenshots` using the
same NODE_PATH as above. These screenshots use the real fictional I7 server.

- [Filter row desktop](screenshots/i7-reviews/filters-zh-CN-light-1440.png)
- [Filter row 390](screenshots/i7-reviews/filters-zh-CN-light-390.png)
- [Filter row 320](screenshots/i7-reviews/filters-zh-CN-light-320.png)
- [English dark desktop](screenshots/i7-reviews/filters-en-US-dark-1440.png)
- [English dark 390](screenshots/i7-reviews/filters-en-US-dark-390.png)
- [English dark 320](screenshots/i7-reviews/filters-en-US-dark-320.png)

### Actual browser screenshots

All screenshots below come from the I7 loopback server and owned fictional DB:

- [Clara Chinese desktop light](screenshots/i7-reviews/clara-zh-CN-light-1440.png)
- [Clara Chinese 390](screenshots/i7-reviews/clara-zh-CN-light-390.png)
- [Clara Chinese 320](screenshots/i7-reviews/clara-zh-CN-light-320.png)
- [Clara English dark desktop](screenshots/i7-reviews/clara-en-US-dark-1440.png)
- [Clara English dark 320](screenshots/i7-reviews/clara-en-US-dark-320.png)
- [Devon Chinese desktop](screenshots/i7-reviews/devon-zh-CN-light-1440.png)
- [Devon English dark 390](screenshots/i7-reviews/devon-en-US-dark-390.png)
- [Personal handling desktop](screenshots/i7-reviews/personal-handling-zh-CN-1440.png)
- [Personal handling 390](screenshots/i7-reviews/personal-handling-zh-CN-390.png)
- [Personal handling 320](screenshots/i7-reviews/personal-handling-zh-CN-320.png)
- [Selected personal handling](screenshots/i7-reviews/review-confirmation.png)
- [Clara deferred category](screenshots/i7-reviews/clara-deferred.png)
- [Devon needs-information category](screenshots/i7-reviews/devon-needs-information.png)
