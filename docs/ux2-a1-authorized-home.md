# UX2 A1 Editorial — authorized fictional I4b Home

Base main: `53f687c96d91d277e421f2228e2e79081ec38ce2`, merged #91.
PR #90's Calm Premium / A1 direction and #91's connected foundation are retained.
This is the existing I4b local workbench, **not another preview or task system**.
Only its Home is connected to the two existing independently authorized collections.
No real household data, accounts, providers, AI, credentials or frozen datasets are used.

## Existing architecture and small integration seam

[I3](stage-i3-readonly-task-workbench.md) owns the controlled HTML/CSS/JS and strict
Task JSON parser. [I4a](stage-i4a-safe-pending-acceptance.md) adds the independently
authorized Pending parser and acceptance. [I4b](stage-i4b-safe-task-editing.md) adds
task edit capability, current permitted assignees, independent confirmation and one
cross-operation receipt/UNKNOWN coordinator. [Connected Foundation](ux2-connected-ui-foundation.md)
scopes Calm Premium presentation to `html[data-connection="i4b"]`.

We reuse these assets and modules; no Python runtime, server route, permission,
SQL, migration, Cookie, CSRF, Host/Origin, CSP or contract parser is changed.
Only I4b Home performs the extra Pending read and final member check. I3/I4a keep
their existing Home behavior. The offline file:// application and independent
[UX2 design preview](ux2-calm-premium-design.md) remain independent.

| Changed resource | Purpose |
| --- | --- |
| `prototypes/i3-workbench/workbench.js` | I4b-only pair coordination, trusted-member welcome and A1 projection of existing neutral fields |
| `prototypes/i3-workbench/connected.css` | I4b A1-only editorial layout; no shared-page density changes |
| `tests/browser/a1-coordination.test.js` | Deterministic faults against the actual refresh function; synthetic API substitutes, no browser/server claim |
| `tests/browser/a1-home.js` | Actual-origin browser matrix, failures, real confirmations, polling and revocation |
| `tests/browser/a1-fixture-host.py` | Trusted stdin-only test controls over an owned temporary DB; never browser-callable |
| `tests/test_a1_connected_home.py` | SQLite/PostgreSQL authorization/input regressions plus the Node coordination suite |
| README / roadmap / design references | Implemented scope, accurate counts and remaining gates |

## Exact data flow, no new API

```text
Explicit --synthetic-only startup → existing owned fictional SQLite / seed
→ independent browser profiles → existing terminal-approved pairing
→ HttpOnly session Cookie → current SessionService + T1 authorization

I4b Home refresh, one frontend request sequence:
  POST /api/session                          current active member
  GET /api/tasks?limit=12&offset=0            strict SamasEditing.taskParse
  GET /api/pending?limit=12&offset=0          strict SamasAcceptance.parse
  POST /api/session                          fresh same-member check
→ publish both validated pages together → A1 DOM
```

All four requests use the original same-origin, no-store, bounded transport. Tasks
and Pending independently reauthorize through SessionService / TaskService. No
member selector, URL parameter, frontend role, source owner or welcome text grants
authority. The welcome name comes only from the checked current server session.
Neither adult's page is combined with the other's page.

The original sequence checks after every await reject late responses after navigation,
reload or a changed context. Existing session epochs continue to bind previews and
write results. A final member mismatch rejects the entire pair and resets frontend
session-bound intent. Unchanged successful background projections keep the DOM mounted,
including keyboard controls and open details; changed pages trigger the original
Pending/task revalidation. Any transport, parser, status or session failure clears
**both** collections, member display and details. There is no partial Home, previous-
member fallback, specimen fallback, storage/cache or fabricated zero on error.

### Ordering and revocation limits

This is **bounded sequential authorization, not a database-atomic combined snapshot**.
Each GET is authoritative at its own transaction. The final session read narrows
member-change races; the current API does not expose a session identity/epoch token
or a common collection revision. It cannot prove a single atomic Tasks/Pending
snapshot, detect arbitrary change-and-revert cookie exchanges, or recall an already
built response. Known read failures/revocations clear content; subsequent successful
reads reflect the current grants. This does not claim zero-latency revocation.

The original background check starts five seconds after success. Each existing
request is bounded to five seconds; four sequential Home requests can consume up to
approximately twenty seconds before success/failure. Existing DOM remains only during
that bounded background check; explicit navigation/reload clears it first. Failures
stop the polling chain until an explicit read. No write is automatically retried.
A production common-snapshot/response-dispatch guarantee needs a separately reviewed
backend contract; this PR does not smuggle one in or enable real data.

I2's HTTP loopback/cross-port Cookie limitation, 600-second local lease, 1800-second
runtime, pairing/preview caps and trusted-local-process assumptions remain unchanged.
Two windows sharing a cookie are not two adults. There is no production login.

## Accurate Home semantics

| Display | Source and bounded meaning |
| --- | --- |
| Welcome | Current checked session member, Chinese/English; no browser identity selection |
| Household tasks | At most the actual first 12 authorized T1 tasks; neutral step title, assignee, tracking status, approved date or explicit no-date |
| Task prioritization | Stable pending-before-completed order **within this page only**; no inferred global incomplete total |
| Task count | Server `tasks.total`, **including completed**; label “当前可查看任务 / Authorized tasks” |
| Task range | Actual returned item count / server total; View all navigates to the existing paginated Tasks page |
| Pending summary | First at most 3 entries from its separately validated first 12-item page; shown / server `pending.total`; never inferred from task count |
| Pending capability | `can_accept=true`: may enter original confirmation; false: more verification needed. It is not a new rejected/deferred/archived state |
| View Pending | Goes to original Pending page and pagination; Home itself creates no preview/receipt or task |
| Approved dates | Only non-null `approved_date` from **this task page**, sorted as dates. No deadline, overdue/today urgency, calendar event or global coverage claim |
| Safety | Secondary navigation and honest “not connected”; no count, green clearance, detector claim or fake zero |
| Promotions | Never appear on Home or enter Tasks/Pending; Offers remains explicitly on-demand and unconnected |

The same neutral step can appear as both an accepted task and a distinct unaccepted
proposal; titles are not identity/dedupe evidence. The API does not return private
source titles or arbitrary task text, so this PR does not invent them. Counts may
coincide for two different authorized populations; equality of counts is not evidence
of equal permissions. This Home has no assignee filter or global unfinished/date count. The later
[Tasks responsibility filters](ux2-authorized-responsibility-filters.md) apply only on
the Tasks page; Home remains unfiltered.

Task details reuse I4b's current server options/preview, exact default assignee, clear
before/after and independent confirmation. Pending acceptance remains on its existing
page. Success navigates to Tasks and rereads T1; returning Home rereads both pages.
Changing the assignee does **not** remove the other adult's independent read grant.
Completion is household tracking only; it does not prove booking/payment/reply.
Cancel/navigation/language changes never save. UNKNOWN uses the original receipt and
operation-specific reconciliation, including refresh recovery; no repeat/rebase/new ID.
No personal archive/defer, source-sharing or mailbox operation is added.

## Actual connected screenshots

Rendered from the genuine loopback I4b host, normal CSP/Cookies and disposable T1 SQL.
The Before host serves #91's merged JS/CSS with the same approved seed; no standalone
specimens are imported. Random opaque task IDs may change row order across fresh runs.
Long-label stress changes a heading in test DOM only and is removed by an authorized
reread; regular images show the actual neutral backend projection.

| State | Screenshot |
| --- | --- |
| Before, Clara desktop / Devon phone | [1440](screenshots/ux2-a1-connected/before-clara-1440.png) / [390](screenshots/ux2-a1-connected/before-devon-390.png) |
| Clara Chinese Light | [1440](screenshots/ux2-a1-connected/home-clara-zh-light-1440.png) / [390](screenshots/ux2-a1-connected/home-clara-zh-light-390.png) / [320](screenshots/ux2-a1-connected/home-clara-zh-light-320.png) |
| Devon Chinese Light | [1440](screenshots/ux2-a1-connected/home-devon-zh-light-1440.png) |
| Clara Chinese Dark | [1440](screenshots/ux2-a1-connected/home-clara-zh-dark-1440.png) / [390](screenshots/ux2-a1-connected/home-clara-zh-dark-390.png) |
| Devon English Dark | [1440](screenshots/ux2-a1-connected/home-devon-en-dark-1440.png) / [390](screenshots/ux2-a1-connected/home-devon-en-dark-390.png) / [320](screenshots/ux2-a1-connected/home-devon-en-dark-320.png) |
| Explicit completion, then actual backend reread | [Home](screenshots/ux2-a1-connected/after-completed-home.png) |
| Authorized empty Pending | [Home](screenshots/ux2-a1-connected/empty-pending-home.png) |
| No dates in current page | [Home](screenshots/ux2-a1-connected/no-dates-home.png) |
| Tasks failure / Pending failure | [Tasks failure](screenshots/ux2-a1-connected/fail-tasks-safe.png) / [Pending failure](screenshots/ux2-a1-connected/fail-pending-safe.png) |
| Network connection failure | [Cleared UI](screenshots/ux2-a1-connected/connection-failed-safe.png) |
| Authorization no longer valid | [Cleared UI](screenshots/ux2-a1-connected/authorization-failed-safe.png) |

## Tests and limitations

The actual-origin browser harness uses two independently approved fictional sessions,
40 adult/language/theme/width combinations (1440/1152/960/390/320), genuine JSON/T1 reads
and real ACCEPT/EDIT confirmations. Normal responses are not mocked. Test routes inject
malformed JSON, blocked/late responses and connection loss only for adversarial cases.
Trusted stdin controls change only the owned synthetic state; they are not product API.
Pagination extensions create new fictional tasks through actual T1 acceptance, not raw
task-row insertion. New fictional unresolved questions exercise Pending overflow.

Tests distinguish no-date/completed/Pending capability, shared assignment, cancellation,
UNKNOWN recovery without repeat submit, separate grant revocation, mixed-read member
change, late response, empty pages, overflow and failure clearing. Layout checks measure
actual DOM coordinates/44px controls and first mobile task visibility; screenshots alone
are not layout assertions. No external requests, models, provider SDKs or real DBs.

The deterministic Node suite executes the actual refresh function with a minimal test
DOM/render capture and synthetic transport faults; it is not a second runtime policy
engine or authentication simulation. Its source seam normalizes CRLF/LF for Windows
checkouts, with an explicit CRLF regression. Pytest exercises current routes/rights against
owned SQLite/PostgreSQL test stores. Existing I3/I4a/I4b suites remain intact. Final
actual totals, any corrected test failures and CI links are reported on the PR.

Windows native fonts/selects, system-theme changes, browser zoom, keyboard/touch and
owner visual acceptance remain manual gates. Unsupported A1 calendar/security data,
free-text task titles and production identity remain deferred, not filled with static
content. No Internet deployment or real-data readiness is implied.

## Windows PowerShell: standalone fictional test

Run from the existing repository root. No runtime DB migration/register/OAuth commands.

```powershell
git fetch origin
if ($LASTEXITCODE -ne 0) { throw '获取失败，请停止。' }
git switch feat/ux2-a1-authorized-home
if ($LASTEXITCODE -ne 0) { throw '请先保存本地修改，不要强制覆盖。' }
git pull --ff-only origin feat/ux2-a1-authorized-home
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

1. Open the printed 127.0.0.1 URL. Request access; in that same terminal match its public
   ID and enter `approve REQUEST_ID clara`. The browser cannot select a member identity.
2. In an **independent Chrome/Edge profile**, request/approve Devon. Initial task totals
   are 3 / 2. Pending totals can be equal while their authorized entries differ.
3. Check each welcome, task status/assignee and no-date text. Compare Pending with its
   full page: Clara cannot see Devon's private visit. No promotions or fake safety count.
4. From Home open the dated shared task. Choose Devon; cancel first. Repeat and explicitly
   confirm. Both adults still see it and the new assignee. Complete/reopen only records
   tracking; return Home to verify the actual reread.
5. View Pending; cancel a preview, then independently confirm the shared school proposal.
   It becomes one shared task and leaves Pending; Home counts are freshly reread.
6. Check Chinese/English, Light/Dark/system, 1440/1152/960/390/320, keyboard focus and zoom.
   Short pages start at the same top. Scroll to all lower entries above bottom navigation.
7. If UNKNOWN occurs, use the original operation check, not another submit. Stop the
   service with `quit`, EOF or Ctrl+C; it clears only its own temporary resources. A later
   browser read must clear old protected contents, not return offline fixtures.

Automated browser reproduction (existing approved Playwright and local Chrome only):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_a1_connected_home.py tests/test_i3_workbench.py tests/test_i4a_workbench.py tests/test_i4b_workbench.py tests/test_household_tasks.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
$env:I4B_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I4B_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node .\tests\browser\a1-home.js --synthetic-only --screenshots
node .\tests\browser\i4b-editing.js --synthetic-only
```

Original I3/I4a scripts retain their I3_TEST_PYTHON/I3_CHROMIUM and
I4A_TEST_PYTHON/I4A_CHROMIUM overrides. The evidence-only `--capture-before` flag serves
the exact merged predecessor; it is not a regression pass or another app.
Keep OPEN / UNMERGED for independent ChatGPT review and owner Windows acceptance.
