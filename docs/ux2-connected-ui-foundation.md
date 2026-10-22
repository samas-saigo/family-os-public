# UX2 Connected UI Foundation — fictional I4b

Scope: the accepted Calm Premium **visual foundation**, applied to the existing
I4b local workbench. PR #90 was verified merged as
`618766673a4c398c4e9d2485eaefbcfdd37af467`; this work starts from that latest main.
The owner-selected A1 remains the future Home direction. This slice does **not**
implement its full business dashboard or make the independent preview production UI.

## Inspect first: the existing shared structure

| Resource | Existing use | Integration decision |
| --- | --- | --- |
| `prototypes/h0-workbench/styles.css` | Offline H0/H1/UX1 and connected I3/I4a/I4b baseline | Leave unchanged |
| `prototypes/i3-workbench/index.html` | All connected stages use the same shell and native dialog | Leave unchanged; no duplicate application |
| `prototypes/i3-workbench/connected.css` | Shared connection presentation | Append rules **only** under `html[data-connection="i4b"]` |
| `prototypes/i3-workbench/workbench.js` | Session-bound reads, polling, navigation, language/theme | Only add I4b navigation SVG/label/aria-current presentation; preserve mounted buttons and handlers |
| I4a `acceptance.js` | Existing acceptance JSON/confirmation/reconciliation | Leave unchanged |
| I4b `editing.js` | Existing ACCEPT/EDIT coordination, default assignee, receipts, UNKNOWN | Only focus the newly mounted Close control when a modal is replaced |
| Python entrypoints | I4b extends I4a → I3 → I2, serves controlled assets | All unchanged; no route, resource or API additions |

The stylesheet does not import the UX2 specimen CSS or JS. It maps approved warm
neutral / forest / charcoal roles to the **existing connected UI tokens**, then
styles its actual components. No sample tasks, dates, counts or confirmation
handlers are copied into the connected application. No new frontend data store. Fresh disposable databases generate new opaque task IDs,
so row order can differ between Before/After while the three neutral task/assignee/
status/date combinations stay the same; no frontend reorder was introduced.
The CSS guard prevents the new rules from applying to I3/I4a or file:// H0/H1.

## What is genuinely connected

```text
Explicit --synthetic-only startup → owned disposable SQLite / fixed fixture seed
Browser request → existing terminal approves exact public pairing request
HttpOnly Secure SameSite=Strict cookie → current SessionService identity
T1 tasks / Pending rights → strict existing JSON → existing I4b DOM
I4b-scoped Calm Premium CSS + navigation presentation

User selects an authorized assignee/status → existing server preview
→ separate explicit confirmation → original T1 command / CAS / exact receipt
→ server result or UNKNOWN → original-request verification → authorized reread
```

Nothing in the new presentation establishes identity, candidate eligibility,
source access, recipient sharing, write authority or success. The displayed member
comes from the current server session. Two browser profiles/contexts are independent;
two windows sharing one cookie are **not** two adults.

**Assignee is not visibility.** Changing the lead to Devon leaves Clara's existing
independent task-read grant intact. Task permission need not re-grant private source
access. No source identity, raw evidence or private provenance is added to cards.

Home keeps the existing authorized task total, and `—` for currently unsupported
summary dimensions. It does not substitute A1's specimen numbers or calendar/security
content. Calendar, Security, Information and Offers truthfully retain their existing
not-connected state. No promotions appear as household tasks. Pending keeps the
existing server eligibility and explicit acceptance. No new archive/defer/reopen
Pending commands or assignee-filter backend are supplied.

## Visual foundation and modest structural changes

- Samas typographic mark with an accessible existing full product name; local fonts.
- 208px desktop sidebar, the same five destinations and a usable secondary More
  entry. Mobile retains five fixed bottom destinations; local inline line icons
  reuse the approved navigation geometry and have no independent actions.
- Warm white / soft-neutral Light and charcoal Dark tokens; semantic warning,
  control, focus and disabled roles retained. Appearance remains Settings only;
  the single language control still moves to More on mobile.
- Shared top alignment: workspace `margin:0 auto; align-self:start`. No page-dependent
  vertical auto margins. At narrower desktop widths the toolbar deliberately wraps
  to two rows; it never squeezes identity/language/reload into clipped text.
- Actual tasks retain the existing responsive two-column desktop/one-column mobile
  collection. Home keeps its present data structure, with a lighter overview and
  single-column task area. This is not an A1 business-dashboard implementation.
- Clear 44px controls, 3px keyboard focus, natural label wrapping, 14–20px component
  radii, restrained surfaces. Operation reconciliation remains a distinct neutral
  status strip, not another task card or a safety-clearance claim.
- Native dialogs retain the authorized default assignee, dates/unknown dates,
  separated assignment controls and explicit before/after confirmation. No global
  preferences are introduced inside dialogs.
- Reduced-motion styling, no animation/dependency/font CDN/remote resources.

The real browser test found that replacing a loading/detail/confirmation dialog
body removed the focused Close button. The small `modal()` change explicitly focuses
its replacement Close button. It does not select Confirm, submit, alter pending drafts
or change epochs/receipt logic. Normal successful polling retains the existing DOM;
revocation/error paths still clear it through the original services.

## Real connected screenshots, not specimen screenshots

All images below were rendered from the existing I4b server with normal CSP/cookies,
terminal-approved fictional sessions and T1 SQL data. **Before** uses merged main
before these presentation changes; it is not an archived screenshot of another app.

| State | Before | Connected foundation |
| --- | --- | --- |
| Clara tasks, Chinese Light desktop | [1440](screenshots/ux2-connected-foundation/before-tasks-1440.png) | [1440](screenshots/ux2-connected-foundation/tasks-clara-zh-light-1440.png) |
| Clara tasks, Chinese Light mobile | [390](screenshots/ux2-connected-foundation/before-tasks-390.png) | [390](screenshots/ux2-connected-foundation/tasks-clara-zh-light-390.png) / [320](screenshots/ux2-connected-foundation/tasks-clara-zh-light-320.png) |
| Clara detail, current assignee/date | [1440](screenshots/ux2-connected-foundation/before-detail-1440.png) | [1440](screenshots/ux2-connected-foundation/detail-clara-zh-light-1440.png) / [320](screenshots/ux2-connected-foundation/detail-clara-zh-light-320.png) |
| Clara Chinese Dark | — | [1440](screenshots/ux2-connected-foundation/tasks-clara-zh-dark-1440.png) / [390](screenshots/ux2-connected-foundation/tasks-clara-zh-dark-390.png) |
| Devon English Light | — | [1440](screenshots/ux2-connected-foundation/tasks-devon-en-light-1440.png) / [390](screenshots/ux2-connected-foundation/tasks-devon-en-light-390.png) |
| Devon English Dark | — | [1440](screenshots/ux2-connected-foundation/tasks-devon-en-dark-1440.png) / [390](screenshots/ux2-connected-foundation/tasks-devon-en-dark-390.png) / [320](screenshots/ux2-connected-foundation/tasks-devon-en-dark-320.png) |
| English Dark detail | — | [1440](screenshots/ux2-connected-foundation/detail-devon-en-dark-1440.png) / [320](screenshots/ux2-connected-foundation/detail-devon-en-dark-320.png) |
| Actual EDIT confirmation | — | [Chinese 1440](screenshots/ux2-connected-foundation/confirm-clara-zh-light-1440.png) / [Chinese 390](screenshots/ux2-connected-foundation/confirm-clara-zh-light-390.png) / [English Dark 390](screenshots/ux2-connected-foundation/confirm-devon-en-dark-390.png) |
| Actual Pending projection | — | [1440](screenshots/ux2-connected-foundation/pending-clara-zh-light-1440.png) / [390](screenshots/ux2-connected-foundation/pending-clara-zh-light-390.png) |

## Verification and honest limits

The dedicated actual-origin browser harness covers 2 fictional adults × 2 languages ×
2 themes × 1440/1152/960/390/320 = **40 combinations**, with navigation, all page origins,
actual theme colors, task permissions/counts, detail/default assignee/date, independent
confirmation, cancellation without submission, keyboard focus, 44px controls, clipping,
mobile navigation obstruction and reduced motion. Its visual inspection run performs
**zero ACCEPT/EDIT confirmations**. Original I3/I4a/I4b browser regressions separately
exercise actual writes, polling focus, UNKNOWN, receipts, source/task revocation and
shared-task state. Final verified counts and CI links are reported on the PR.

Long-label stress replaces a heading only in test DOM after a genuine authorized read,
then discards it on reread. It does not introduce a free-text task field, alter SQL or
present fake metadata as a backend record. Regular screenshots show only normal T1
fixture projections, not that stress text. Task creation still requires server eligibility
and the existing explicit confirmation; opening/choosing/cancelling cannot save.

Pytest adds all-rule I4b CSS scope checks, text/control contrast, exact synthetic opt-in
and PNG dimensions. Existing domain and I3/I4a/I4b tests remain. No dependency or lock
change, migration, authentication design or API change. Earlier test failures during
implementation are fixed and rerun; they are not skipped or counted as initial passes.

The same-host cross-port cookie limitation from I2 is **not solved** by a polished UI.
Loopback/fictional data only; no production login or real-mail permission. Windows
Chrome/Edge fonts, native select behavior, OS theme changes, browser zoom, real keyboard
and touch use remain owner acceptance gates. This does not certify production privacy,
real-world accessibility or an authenticated internet deployment.

## Windows: one startup from repository root

```powershell
git fetch origin
if ($LASTEXITCODE -ne 0) { throw '获取失败，请停止。' }
git switch feat/ux2-connected-ui-foundation
if ($LASTEXITCODE -ne 0) { throw '请先保存本地修改，不要强制覆盖。' }
git pull --ff-only origin feat/ux2-connected-ui-foundation
if ($LASTEXITCODE -ne 0) { throw '更新失败，请停止。' }
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { py -3.12 -m venv .venv }
if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败。' }
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw '项目安装失败。' }
.\.venv\Scripts\python.exe -u .\prototypes\i4b-workbench\serve_editing.py --synthetic-only
```

Open the printed **127.0.0.1 URL**, request a session, match its public ID in the same
terminal and enter `approve REQUEST_ID clara`. Use an independent browser profile for
Devon, with a separately requested/approved ID. Never paste cookies or tokens anywhere.
No file:// preview or static specimen is the connected workbench. Terminal `quit`,
EOF or Ctrl+C stops it and removes only its owned temporary database. Dependencies are
existing pinned requirements; no new external product/data service is contacted.

Owner walkthrough: tasks (3 for Clara / 2 for Devon in this fixed setup) → dated school
detail → choose Devon → cancel, then explicitly confirm → both still see the same task
and new lead → complete/reopen tracking independently → Pending acceptance independently
→ Settings language/theme → 390/320 width → unsupported pages without invented data.
For UNKNOWN do not repeat a write; use the original-operation check. Test service shutdown
and subsequent reload clearing the old UI. Match the original I4b instructions rather
than treating this UI adoption as new operation authority.

## Reproduce automated checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ux2_connected_foundation.py tests/test_i3_workbench.py tests/test_i4a_workbench.py tests/test_i4b_workbench.py tests/test_household_tasks.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
# Only with the existing approved Playwright / Chrome installation; no downloads:
$env:I4B_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I4B_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node .\tests\browser\ux2-connected.js --synthetic-only --screenshots
node .\tests\browser\i3-workbench.js --synthetic-only
node .\tests\browser\i4a-acceptance.js --synthetic-only
node .\tests\browser\i4b-editing.js --synthetic-only
```

The new harness uses I4B_TEST_PYTHON/I4B_CHROMIUM; original I3/I4a scripts have their
existing I3_TEST_PYTHON/I3_CHROMIUM and I4A_TEST_PYTHON/I4A_CHROMIUM overrides respectively.
The evidence-only --capture-before flag records the original connected UI; it is not
a regression pass and should not overwrite the baseline after adoption.

Next phases require separate approval: A1 dashboard business projections; assignee
filtering; personal Pending decision versions/archive/reopen semantics; production
OIDC/session deployment; any real source/data integration. Finance remains separate.
Keep this PR OPEN / UNMERGED for ChatGPT review and owner Windows acceptance.
