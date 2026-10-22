# UX2 — Authorized household task responsibility filters

Based on main `57edaeefb056a382b844eb1b9750c218705c6f1b` (merged #92).
This extends the existing synthetic-only I4b workbench, not the independent UX2
preview, offline application, production login or provider integrations.
**Responsibility describes who leads a task; it never grants or removes readership.**

## Definitions and authorization/query order

| Mode | Meaning within the current actor’s authorized tasks |
| --- | --- |
| `all` / 全部 | Every currently readable task, including completed tracking records |
| `mine` / 我负责 | Person-assigned, with the sole assignee equal to the verified session actor |
| `other` / 对方负责 | Person-assigned, with the sole assignee different from that actor |
| `joint` / 共同负责 | Explicit `assignee_kind = joint`; neither sole-assignee category includes it |

`mine`, `other`, `joint` partition this two-peer fictional household’s readable
population. `all` is their union, **not a fourth disjoint population**. `other`
compares the already-authorized task’s neutral assignee, not a mailbox owner,
source identity or a second member’s task list. This assumes the approved two-adult
fixture; it does not design future arbitrary-size household assignment semantics.

```text
I2 current HttpOnly session Cookie / local lease
→ TaskService household authorization transaction
→ SessionService current identity / binding / membership
→ existing _task_query current allowed independent task-read grant + member epoch
→ optional sole-person/joint responsibility predicate + optional step predicate
→ COUNT over that exact authorized filtered query
→ deterministic task ID ordering → limit/offset → existing neutral TaskView
→ strict I4b JSON → exact-request checked UI
```

The new `Responsibility` enum is a query condition, not an authority assertion.
`TaskService.tasks(..., responsibility=Responsibility.ALL)` preserves old callers.
Limits remain 1–20 (UI 12); offset 0–1,000,000. `total` includes both tracking
statuses and counts the entire **filtered, currently authorized** population, not
just this page. `has_more = offset + returned_count < total`. No post-page client
filtering, peer-list merge, source/Pending join, new task store or migration.
Counts and pages share the original transaction; sequential browser requests are
not an atomic multi-request snapshot or a permanent permission lease.

## Minimal opt-in transport change

Only I4b accepts the new query parameter:

```text
GET /api/tasks?limit=12&offset=0&responsibility=mine&step=school-session
```

Allowed responsibility values are exactly `all|mine|other|joint`. The original
canonical ASCII query grammar and numeric/step checks remain. Duplicate, empty,
percent/plus-encoded, identity, household, arbitrary expression or extra parameters
are rejected. I3/I4a Tasks and all Pending routes continue to reject this parameter.
The shared I3 adapter has two small overridable parameter/response hooks; default
implementations still use the original parser, JSON and authorization service.

Explicit responsibility requests return `i4b-task-page-v2`, adding only:

```json
"query": {"responsibility": "mine", "step": "school-session"}
```

The row allowlist, pagination fields and 16 KiB cap are unchanged. The I4b parser
requires exact query echo, schema, pagination, canonical JSON and existing row
validation. Wrong/missing/extra filter fields fail closed. Unfiltered requests,
including Home, retain `i4b-task-page-v1`; the parser rejects v2 where v1 was expected
and vice versa. No new identity parameter or grant/permission details are returned.
Host/Origin, Fetch Metadata, no-store, CSP, Cookie, CSRF/write gates and timeouts remain.

## UI lifecycle and existing edits

Four compact native buttons, grouped and labelled for assistive technology, use
`aria-pressed`, visible focus and 44px minimum targets. Chinese and English have
identical semantics. Existing task-type select combines with responsibility; changing
either resets offset to zero. The selected mode persists during rereads/polling on
that Tasks visit. Navigation away/re-entry, Home’s View all, successful edits/acceptance
(which navigate back to Tasks), logout, session/member changes and a full browser
refresh reset to All. There is no local/session storage.

Home always requests its original unfiltered page/count. A Tasks filter never
changes Home’s source or date scope. No promotions, Pending or security events become
tasks. An authorized no-match page is an empty state, not an access error.

Existing request sequencing rejects late responses; strict query echo additionally
rejects another filter’s page. Unchanged successful polling keeps focused controls
mounted; failures clear protected rows/details rather than returning earlier pages
or offline fixtures. Existing already-built-response and I2 same-host cross-port
Cookie limitations remain; this is approved fictional local testing only.

Task details, current/default assignee and allowed choices, independent preview and
confirmation, actual-actor CAS/idempotency, receipt/UNKNOWN reconciliation and all
cancel behavior are reused. Assigning a joint task to Devon moves it to Clara’s
Other and Devon’s Mine; it remains in both All lists under unchanged read grants.
Source revocation does not revoke separately published task fields. Revoked task-read
rights cannot be bypassed by matching responsibility. No task-management/write rights
are added by selecting a filter. Completion still means household tracking only.

## Tests and connected screenshots

Newly authored fictional pagination fixtures create 42 shared tasks using actual T1
ACCEPT/EDIT: 14 Clara-only-responsibility, 14 Devon-only-responsibility, 14 joint;
each bucket includes both steps and completed/pending tracking. These are separate
from frozen evaluation sets and never read real data. Original startup data stay
unchanged. The extra population exists only under trusted automated-test setup, not
an HTTP initialization/authorization API.

Database tests run with the repository’s owned SQLite / isolated PostgreSQL schema
fixtures. They verify category partitions, step combinations, stable ordered offset
pages, total/has_more, hidden changes, independent grants/source revocation, actor
identity, rejected queries, unchanged writes/audit and I3/I4a isolation. Browser tests
use actual I4b sessions/SQL and two independent browser contexts. Fault interception
is only for malformed, failed, delayed and unavailable responses; regular data are
not mocked. Browser automation verifies 160 peer/language/theme/width/filter
combinations, geometry, keyboard focus across two polls, genuine confirmations,
filtered pagination, cancellation, late responses, member change and revocation.
Actual final counts and full CI results are recorded on the PR.

| Actual I4b state | Images |
| --- | --- |
| Clara All / Mine / Other / Joint | [All](screenshots/ux2-responsibility/clara-all-1440.png), [Mine](screenshots/ux2-responsibility/clara-mine-1440.png), [Other](screenshots/ux2-responsibility/clara-other-1440.png), [Joint](screenshots/ux2-responsibility/clara-joint-1440.png) |
| Devon All / Mine / Other / Joint | [All](screenshots/ux2-responsibility/devon-all-1440.png), [Mine](screenshots/ux2-responsibility/devon-mine-1440.png), [Other](screenshots/ux2-responsibility/devon-other-1440.png), [Joint](screenshots/ux2-responsibility/devon-joint-1440.png) |
| Actual joint → Devon edit, same shared task | [Clara Other](screenshots/ux2-responsibility/clara-after-devon-assignment.png), [Devon Mine](screenshots/ux2-responsibility/devon-after-assignment.png) |
| Combined type / responsibility | [Clara](screenshots/ux2-responsibility/clara-mine-combined.png), [Devon](screenshots/ux2-responsibility/devon-other-combined.png) |
| 390 / 320 Chinese Light | [390](screenshots/ux2-responsibility/clara-joint-zh-CN-light-390.png), [320](screenshots/ux2-responsibility/clara-joint-zh-CN-light-320.png) |
| 390 / 320 English Dark | [390](screenshots/ux2-responsibility/devon-joint-en-US-dark-390.png), [320](screenshots/ux2-responsibility/devon-joint-en-US-dark-320.png) |
| No-match / revoked grant empty | [No match](screenshots/ux2-responsibility/clara-other-1440.png), [Revoked](screenshots/ux2-responsibility/revoked-empty.png) |

## Windows PowerShell and owner acceptance

From the existing repository root (no runtime DB/OAuth/migration commands):

```powershell
git fetch origin
if ($LASTEXITCODE -ne 0) { throw '获取失败，请停止。' }
git switch feat/ux2-authorized-responsibility-filters
if ($LASTEXITCODE -ne 0) { throw '请先保存本地修改，不要强制覆盖。' }
git pull --ff-only origin feat/ux2-authorized-responsibility-filters
if ($LASTEXITCODE -ne 0) { throw '更新失败，请停止。' }
if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败。' }
}
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw '项目安装失败。' }
.\.venv\Scripts\python.exe -u .\prototypes\i4b-workbench\serve_editing.py --synthetic-only
```

1. Open the printed 127.0.0.1 URL in Chrome/Edge. Request access. In that terminal,
   match the public request ID and enter `approve REQUEST_ID clara`.
2. Use an **independent browser profile** (not another tab sharing Cookies) for Devon:
   request access and `approve REQUEST_ID devon`. No browser identity picker.
3. Tasks → compare all four filters with both task types. Initial Clara All/Mine/Other/Joint
   totals are **3/1/0/2**, Devon **2/0/0/2**. These are server totals including completed.
4. Clara: Joint → dated school task → select Devon → cancel; nothing saves. Repeat and
   explicitly confirm. Clara Other and Devon Mine now contain this same task. Both All
   lists retain it. Source access and task readership do not change.
5. Verify Home’s totals remain 3 / 2 and View all enters All. Navigate away/re-enter Tasks:
   All is restored. Changing task type/responsibility returns to the first page.
6. Inspect Chinese/English, Light/Dark/system, 1440/1152/960/390/320, Windows native fonts,
   browser zoom, keyboard and bottom-navigation reachability. Empty filters remain usable.
7. If UNKNOWN occurs, check the original operation, never resubmit. `quit`, EOF or Ctrl+C
   stops the service and cleans only its own temporary store. Failure must clear old rows.

Optional automated reproduction (existing approved Playwright/local browser installation):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_responsibility_filters.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
$env:I4B_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I4B_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node .\tests\browser\responsibility-filters.js --synthetic-only --screenshots
```

Real authentication, arbitrary household size, real data, persistent browser caches,
source management, new task creation controls, Pending archive/defer and provider writes
remain out of scope. Keep the PR open for ChatGPT review and owner Windows acceptance.
