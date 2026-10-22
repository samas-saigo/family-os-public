# Stage H2 — 离线后端只读工作台 / Offline backend read preview

H2 follows G3b PR #80 merged at `02e8f39deaa7ff52f848efa0f7f7b1662ccb1299`.
It connects **actual G3b ASGI responses** to Chinese-first bilingual presentation,
using newly authored Iris/Soren fiction and one disposable database. It is not a
static substitute API dataset, deployed login, secure browser session or real workbench.
No live provider, identity provider, AI, household records or financial data is involved.

Read alongside [G3b schema/dispatch](v0-1-fictional-read-api.md),
[G2a authoritative grants](v0-1-durable-household-authorization.md),
[G2b1 identity](v0-1-verified-identity-boundary.md),
[G2b2 sessions](v0-1-session-service-boundary.md),
[G3a code flow](v0-1-oidc-login-foundation.md),
[H1 independent demo](v0-1-bilingual-offline-workbench.md),
[architecture](architecture.md), [security](security.md) and [roadmap](roadmap.md).

## 本地生成与打开 / Windows PowerShell

From the repository root, with the project's Python 3.12 environment already installed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe .\prototypes\h2-workbench\generate_preview.py --synthetic-only --output-directory .\.local\h2-preview
if ($LASTEXITCODE -ne 0) { throw "H2 generation failed; no preview should be used." }
Start-Process (Resolve-Path '.\.local\h2-preview\index.html').Path
```

There is no npm build, Node requirement for generation, server, port, cloud credential,
browser OAuth or actual login. Node >=18 is used by developer tests only. No dependency
or production CLI entrypoint is added. Do **not** run Alembic against your runtime DB.

`--synthetic-only` must be the exact flag; no abbreviations or `=true` form. The command
offers no database URL, fixture file, household, identity, provider or credential input.
It does not discover `DATABASE_URL` or `data/family-os.sqlite3`. It creates a new
temporary SQLite database and applies existing migrations through an explicit Alembic
EnvironmentContext/connection, bypassing `env.py`'s runtime URL discovery. The Alembic
revision resolver is an internal library seam covered by generator tests; upgrades
require rerunning them. All DB connections close and the temporary DB is deleted.

Output must be a **new directory**; existing directories, symlinks/junctions and such
ancestors reject. Rerun using another name, e.g. `.\.local\h2-preview-2`, then open
that new entry page. No existing file/database is reset, deleted or replaced. Default
documented `.local/h2-*` outputs are Git-ignored; never add generated snapshots to Git.
Keep all seven generated assets together. A failure before capture/validation completes
publishes nothing. A disk-write failure can leave incomplete **fictional-only** output;
discard it manually and choose a new directory, never use it as a successful capture.

原始 `prototypes/h2-workbench/index.html` 是模板，不能直接作为预览打开。请打开
生成目录中的 `index.html`。如果本地文件被组织策略禁止打开，不要绕过策略、启动
服务器或上传到公共托管。Windows 直接打开和本地 CSP 实际执行必须由用户验证。

## 实际数据路径与安全边界 / Actual path

1. Privileged fixed-fiction setup uses the existing registry and empty migrated schema
   to provision one household, two peer Persons, three fixture SourceAccounts, bindings,
   membership and independent publication permission anchors.
2. Existing G2a submit/confirm/commit provisions read grants and records later source,
   publication and scope changes with its CAS/actor-attributed audit. The fictional
   controller capability is independently declared **before** identity/session issuance;
   it never follows from login and never enters the frontend/API request.
3. Generate an ephemeral RSA key in memory; existing G2b1 verifies a fresh signed
   fictional assertion/challenge for each adult. Existing G2b2 issues two different
   opaque sessions over that same database. This is the approved internal fictional
   issuance mechanism, not G3a browser/OIDC login or actual identity-provider traffic.
4. The in-process client invokes the **actual G3b callable** with each opaque bearer,
   exact GET and bounded limit/offset. No SQL query constructs UI records. G3b/G2b2/G2a
   alone resolve current identity/membership/source/security/publication rights.
5. Validate exact response bytes, then collect bounded backend pages for each fictional
   member/phase. A generic authentication, DB, UNKNOWN issuance/change or schema failure
   aborts; no blind retry, rebase or secret recovery is attempted.
6. Only permitted G3b JSON fields plus fixed fictional selector/phase control metadata
   enter `snapshot.js`. No bearer, hash, session identifier, key, assertion, subject,
   raw claims, audit ledger, grant list, secret configuration or provider payload appears.
7. Browser presentation validates the complete finite envelope and response shapes,
   translates enums, formats counts and uses plain `textContent`. It performs no
   authorization, SQL, API request, inference, task mutation, storage or external action.

The generated `styles.css` and `i18n.js` are byte-identical copies of H1's existing
styling/helper. H2's own short dictionary is compiled by that helper; H1 record fixtures,
model, app and translation dataset are not loaded into H2. All seven H1 views and its
existing files/tests remain unchanged. H2 has a separate entry page, labels and counts.
The developer harness lives under `prototypes/`, outside production services and the
isolated backend modules; no existing G2a/G2b1/G2b2/G3a/G3b runtime or test is changed.

## Explicit schema compatibility mapping

| G3b-authorized field | H2 presentation | What it does not establish |
| --- | --- | --- |
| observations items | 已授权的信息; raw fictional source/object identifiers, observation generation, localized fixed Topic | Email subject/content, task title, real deadline or obligation |
| security items | 安全审核信息; the same authorized identity/Topic plus localized fictional Safety | Detector efficacy, verified benign intent, review/restore/quarantine authority |
| published_steps items | 已共享的家庭事项（演示）; publication ID and localized neutral Step | Accepted task, assignment/status, fresh private evidence or execution |
| each lane total/has_more | Authorized total, shown rows and backend more-pages indicator | Hidden population count, household-global count or a combined H1/H2 count |
| pagination limit/offset | Recorded backend page navigation, independently preserving all lane totals | Client-side permission evaluation, dedupe, speculative query or live refresh |
| schema/synthetic_only | Exact `g3b-fictional-read-v1`, exact boolean true | Production authentication/deployment approval |

All fields are strict allowlists. Unknown schema/keys/enums, missing fields, half-shaped
rows, bool-as-int, nonfinite/ambiguous JSON, invalid bounded identifiers/generations,
duplicate row identities and inconsistent page totals/offsets reject. Python validates
actual JSON bytes (32 KiB); browser independently validates parsed response/envelope.
These are **schema/presentation checks, not a second grant policy**. No unknown enum is
silently coerced into a clear safety state. JSON serialization is ASCII-escaped; source
text is never parsed as executable HTML or converted into links.

Only fixed Topic labels and the exact neutral Step enum are translated. Generic card
headings are interface labels, not manufactured subjects or inferred task titles. No
ID is used to reconstruct omitted email content, person identity, due date, task state
or source provenance for a separately published step.

## Two adults and recorded revocations

Initial state: two independently shared fixture accounts each contribute two distinct
objects; consistent duplicates count once. Iris additionally has one private fixture
observation. Initial API totals are Iris **5 observations / 4 security / 1 publication**
and Soren **4 / 4 / 1**. Iris's private source/object never appears in Soren's API pages.
They share exactly the same four common observations and one neutral published step.

| Recorded phase | Iris totals: observations / security / published steps | Soren totals | Change performed before fresh API reads |
| --- | --- | --- | --- |
| Initial | 5 / 4 / 1 | 4 / 4 / 1 | Explicit initial grants |
| Source revoked | 3 / 2 / 1 | 4 / 4 / 1 | Revoke Iris's access to one previously shared source; publication remains independent |
| Publication revoked | 3 / 2 / 0 | 4 / 4 / 1 | Independently revoke Iris's neutral-step visibility |
| Observation only | 3 / 0 / 0 | 4 / 4 / 1 | Retain remaining observation scopes; remove Iris's security scope |

Each phase uses new authenticated API calls, limit **2**, offsets **0/2/4** where
needed. The fixed envelope has four phases, two adults and **17 actual G3b requests**;
at most six authorized fictional items and three pages per member/phase are allowed.
Capture is sequential under controlled fixture state, not an atomic cross-request
snapshot or proof of production multipage/revocation consistency. No browser selector
issues a grant, logs in, changes the database or re-fetches a page.

**所有文件都是历史虚构快照，不是实时授权视图。** 本地文件控制者可以看到双方全部
虚构快照，包括过去曾获准的记录。成员切换不是认证、不是防止恶意本地用户读取文件
的安全边界。撤权无法收回已生成文件；绝不能将此方法换成真实家庭数据导出或客户端
私人缓存。旧快照不代表当前权限。H2 是经明确批准的虚构历史展示，不放宽 G3b 的
生产禁缓存/撤权边界。真实部署仍必须解决最终读取到发送、缓存和撤权竞态。

## Repeatable manual walkthrough

1. Open the generated entry page. Chinese is default; read the global historical-file
   warning. See “已授权的信息” with Iris's total 5, two returned rows and backend offset 0.
2. Page forward twice: Iris's private identifier appears on the last recorded page.
   Switch to Soren: total 4, two pages, no Iris private identifier. This demonstrates
   distinct authorized API captures, not secure browser identity switching.
3. Switch to English and back. IDs/counts/pages retain their backend meanings; labels
   change only. All security labels explicitly remain fictional; UNKNOWN is not clear.
4. Select Iris + source-revoked phase: observation total 3, security total 2. Open shared
   steps: publication total remains 1, with no source IDs/private evidence or acceptance.
5. Select publication-revoked: neutral steps disappear independently. Then choose
   observation-only: ordinary information remains 3, security lane is empty.
6. Return to initial: old fictional results reappear **as history**, not renewed access.
   There is no accept/complete/review/restore/quarantine or grant-edit button.
7. Open original H1 separately using its documented entry point. Its rich seven-view
   fictional scenarios remain independent; never combine their figures with H2 counts.

## H1 features not supplied by this backend

G3b has no durable accepted-task lifecycle/assignment/status, task dates, pending questions,
confirmation queue, email summaries/bodies, original evidence display, calendar timeline,
promotion/offer eligibility, review/tracking history, grant controls or task mutation route.
H2 implements none of them. It also does not implement real browser authentication,
cookies, invitations, recovery, providers, notifications, AI or background execution.
Central R0–R3 is unchanged; Alternative B standing authorization stays disabled/unapproved.

Next recommendation: separately design/review **durable household task and confirmation
state** before adding task buttons. Use one authoritative task identity/publication state,
independent source versus task recipient permissions, immutable actor-attributed review/
acceptance history, exact evidence/definition/generation binding, CAS/idempotency and stale
zero-write protection. Suggestion, human review, explicit task acceptance and R2/R3 execution
must remain separate. Do not copy research modules into production or enable real-data AI.
Actual OIDC/profile/MFA/invitation/recovery, browser-bound attempts, TLS/cookies/CSRF/origin,
session/revocation/cache and deployment review still gate any usable network workbench.
UNKNOWN session issuance requires fresh independent proof for outcome verification,
never blind retry or bearer recovery. This document does not authorize the next phase.

## Validation and independent review

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_h2_workbench.py tests/test_h0_workbench.py tests/test_h1_workbench.py tests/test_fictional_read_api.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

69 new Python tests include actual G3b-to-JS display, independent sessions, current
grants/revocations, security scope, page totals, malformed schemas, bounded JSON,
no secret output, deterministic generated assets, fresh-only safe paths, opt-in,
runtime-environment isolation and no partial export. One of these tests executes
24 Node checks against **real captured** responses; no hand-authored API JSON supplies
the integration path. Existing H0/H1 and backend tests are unchanged. Both full database
suites include real SQLite/PostgreSQL authorization and migration regressions. Exact
verified counts/head/CI conclusions are reported in the PR.

Optional installed Chromium/Playwright checks (no install/download required or performed):

```powershell
node .\tests\browser\h2-interactions.js .\.local\h2-preview
```

Seven Chromium 151 interaction checks passed at 1440/390/320 px across both locales,
with zero application network requests and browser errors. Local-content injection
bypasses CSP; a separate direct file attempt was blocked by environment policy.
**Windows direct file opening and actual CSP are NOT VERIFIED** and remain the manual
gate. Passing offline injection does not prove production transport/browser privacy.

Review questions: Does every client record originate in actual current authorized G3b
output? Are shared steps independent and never promoted to accepted tasks? Do schema
errors withhold all partial display and never strip forbidden fields? Are historical
snapshots/member switching clearly non-authentication, with no real-data export option?
Are missing H1 capabilities and future task/browser/deployment gates explicit?

Keep the PR OPEN and UNMERGED for ChatGPT, independent Muse security review and final
human-controlled merge. No auto-merge or real functionality enablement.
