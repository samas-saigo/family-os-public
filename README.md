# Samas Family OS — Architecture Starter

> Privacy-sanitized source snapshot. Read [publication and historical experiment limits](PUBLICATION_PRIVACY.md) before using archived commands or reports.

The separate [local Qwen3 thinking experiment](docs/local-thinking-benchmark.md)
reuses the original 37 synthetic cases with explicit ON/OFF controls and local-only
artifacts. Manual only; no household data, Development/Holdout access or app integration.

The [offline rules/AI complementarity analyzer](docs/rule-ai-complementarity.md)
validates one existing fixed synthetic report and separates retrospective Oracle
overlap from a conservative review-only proposal. It runs no models or split evaluation.

I9 [personal action Home](docs/stage-i9-personal-action-home.md) adds an opt-in
server-authorized, read-only four-region Home over existing T1/I8 state. Full counts
and three-card samples share one authorization transaction; no new task or permission system.

I8 [personal not-applicable / resume](docs/stage-i8-personal-not-applicable-resume.md)
extends the fictional I7 workbench with own reversible disposition and bounded private
reasons, original CAS/receipt recovery, and guarded history-preserving migration.
No household resolution, real data or task automation.

I7 [authorized fictional Pending handling](docs/stage-i7-pending-review-workflow.md)
adds personal Viewed / Handle later / Need information, with current-evidence state,
server-side filters and the shared T1 receipt/UNKNOWN gate. No global rejection or real data.

I6 [authorized fictional Pending explanations](docs/stage-i6-authorized-pending-explanations.md)
adds source-scoped, version-bound bilingual Details to the existing fictional workbench.
Explanation never grants acceptance or shares private evidence through Tasks.

I5 [fictional information → Pending → explicit Task](docs/stage-i5-information-to-pending.md)
adds an opt-in terminal feeder to the existing I4b workbench. A bounded producer ledger
and independent fixture plans preserve versions/privacy; no real data or automatic acceptance.

UX2 [authorized responsibility filters](docs/ux2-authorized-responsibility-filters.md) add
All / Mine / Partner’s / Joint to fictional I4b Tasks, before server count/pagination.
Assignment remains independent from readership; Home stays unfiltered.

UX2 [A1 Editorial Home](docs/ux2-a1-authorized-home.md) now reads authorized fictional
I4b Tasks and Pending together, with honest page-scoped dates, explicit confirmation
and fail-closed read coordination. No real data or production login is enabled.

UX2 [Connected UI Foundation](docs/ux2-connected-ui-foundation.md) applies the accepted
Calm Premium presentation to the existing synthetic-only I4b workbench, preserving its
session-bound T1 reads, explicit confirmations and UNKNOWN reconciliation. Its
original foundation scope is preserved; A1 integration is documented separately.

UX2 provides a separate [Calm Premium visual design proposal](docs/ux2-calm-premium-design.md)
and local-only preview. It does not replace the existing application or connect to
tasks, accounts or backend services; connected adoption is tracked in the slices above.

I1 completed a [safe frontend/backend connection readiness audit](docs/stage-i1-safe-read-connection.md).
I2 adds an opt-in [loopback fictional session lab](docs/stage-i2-local-session-boundary.md):
terminal-approved fictional identity, HttpOnly cookies and current internal session checks.
I3 adds a [fictional read-only task connection](docs/stage-i3-readonly-task-workbench.md)
over that same loopback boundary and existing T1 permissions. No production login or
task-write API exists in I3. The offline application remains independent.
I4a adds a separately started [fictional confirmed Pending acceptance](docs/stage-i4a-safe-pending-acceptance.md)
using existing T1 CAS and read-only UNKNOWN reconciliation; default I2/I3 remain unchanged.
I4b adds separately started [confirmed fictional task editing](docs/stage-i4b-safe-task-editing.md)
with shared ACCEPT/EDIT receipt coordination; old I4a remains acceptance-only.

A household operating system that turns email, calendar, documents, and financial data
into a structured, searchable, low-maintenance family knowledge and action layer.

## Design goals

1. Multi-person, multi-account from day one.
2. Separate **people** from **connected accounts**.
3. Read-only by default; write actions require explicit policy/approval.
4. Preserve provenance for every extracted fact.
5. Deduplicate repeated emails, shared/joint notifications, forwarded messages, and duplicate financial records.
6. Treat AI extraction/classification as probabilistic; route uncertain items to review.
7. Keep operational domains modular: Admin, Travel, Home, Vehicle, Pet, Purchase, Finance.
8. Build one canonical Household DB rather than one database per app.

## Core pipeline

```text
Connectors
  Gmail / Outlook / Drive / Calendar / Finance
          |
          v
Raw Ingestion Store
          |
          v
Normalization
          |
          v
Identity Resolution + Deduplication
          |
          v
Classification + Structured Extraction
          |
          v
Canonical Household DB
          |
          +--> Tasks / reminders
          +--> Search / chat
          +--> Dashboards
          +--> Reconciliation (receipt <-> transaction)
```

## Recommended v1 behavior

- Read Gmail / Calendar / Drive.
- Do not send mail, delete mail, move files, or create events automatically.
- Classify and extract first.
- Create a Review Queue for anything uncertain.
- Add write actions only after the classification logic is stable.

See:
- `docs/architecture.md`
- `docs/data-model.md`
- `docs/security.md`
- `db/schema.sql`
- `config/household.example.yaml`
- `config/classification.yaml`

## Phase 1 implementation

The repository now includes a Python 3.12 read-only ingestion foundation in
`src/family_os`. It supports SQLite for local synthetic development and
PostgreSQL through SQLAlchemy/Alembic. The existing architecture documents and
`db/schema.sql` remain design references; **Alembic migrations are the executable
schema**. Canonical entities, model inference, and UI are future phases.
Phase 2A adds a read-only Gmail adapter; Phase 2B adds Outlook delegated read-basic ingestion.
Phase 2C adds Google Calendar read-only discovery and event metadata. Phase 2D adds
Google Drive metadata-only ingestion. Phase 2E supplies callable provider services;
Phase 2F adds a [versioned analysis foundation](docs/phase-2f-review.md). Phase 2G
adds a conservative local metadata classifier with explicit domain abstention.
No external inference is connected. Other live providers remain future work.

The CLI, local OS-keyring connections, and SQLite workflow are the current
single-machine stage. The target is one authoritative household backend/core with
secure provider connections and centralized action policy, serving authenticated
desktop, web, and mobile clients. PostgreSQL is the likely shared backend store;
hosted and self-hosted deployment remain options. Client auth, service/API transport,
background execution, and token migration are future work. See the
[deployment/client architecture](docs/architecture.md#5-deployment-and-client-architecture)
and [security boundaries](docs/security.md#provider-oauth-and-family-os-client-access).

### Run the offline demo (PowerShell)

Run these commands from the repository root with Python 3.12 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\family-os.exe register config/household.demo.yaml
.\.venv\Scripts\family-os.exe ingest-fixture --household demo_household --account demo_mailbox --file fixtures/messages.json
.\.venv\Scripts\family-os.exe status --household demo_household
.\.venv\Scripts\python.exe -m pytest -q
```

The fixture contains two synthetic messages. The first ingestion inserts two
records; another run resumes at the saved cursor and inserts none. No external
accounts or credentials are needed. `config/household.example.yaml` is for future
provider adapters; the demo uses the `fixture` provider exclusively.

If `python` is absent on Windows, use your Python 3.12+ executable for the first
command. This checkout's `.venv` is already set up. The CLI deliberately has no
email, calendar, file, or financial write commands.

### Configuration and migrations

The default URL is `sqlite:///data/family-os.sqlite3`. Supply a PostgreSQL URL
through the `DATABASE_URL` environment variable with the `postgresql+psycopg`
driver. `.env.example` documents configuration; `.env` is **not automatically
loaded**. Never commit a real database URL containing credentials.

Copy household settings to the ignored `config/household.yaml` before editing
personal details. Account IDs and person IDs are globally unique in this local
database. Household scopes and composite foreign keys enforce ownership boundaries;
they do not replace API authentication or authorization in a future hosted service.
An account's provider, external identity, and household cannot be changed in place.
Create a new account ID when connecting a different mailbox.

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```

Migrations support downgrade, tested in disposable databases. Downgrading this
initial migration drops ingestion tables; use it only on disposable data or after
a backup. Do not execute `db/schema.sql` alongside migrations.

### Validation and review

`pytest` runs SQLite by default. CI also runs the same behavioral suite against
PostgreSQL 16. To run that suite yourself, set `TEST_DATABASE_URL` to a **dedicated
disposable PostgreSQL database**. Tests create isolated schemas and drop only those
schemas afterward; the test user needs schema creation permission.

See `docs/phase-1-review.md` for implementation decisions, security limits, and
the handoff to the ChatGPT architect. The [roadmap](docs/roadmap.md) distinguishes
completed registry/ingestion/normalization and Gmail/Outlook/Calendar adapters, and
Phase 2D Drive metadata ingestion, from future canonical processing, backend services,
and multi-client work.

## Phase 2A: read-only Gmail

Issue #2 adds explicit mailbox registration/verification, OS-keyring OAuth with
only `gmail.readonly`, bounded initial search, and resumable incremental Gmail
history. No bodies, snippets, or attachment bytes are persisted; Gmail content
hashes remain null. Existing raw history and normalized provenance are retained.

See [Gmail setup](docs/gmail.md) for secure prerequisites, multi-account/shared
configuration, disable/recovery procedures, and the **opt-in** small manual smoke
test. Start from `config/household.gmail.example.yaml`, whose identities are
synthetic. Gmail accounts require a deliberate `external_account`; the original
architecture example's null Gmail addresses must be filled before registration.
No live OAuth or mailbox access runs in tests or CI. See
[Phase 2A review](docs/phase-2a-review.md) for decisions and review questions.

## Phase 2B: Outlook / Microsoft Graph read-basic

Issue #4 adds personal and work/school Microsoft **own mailbox** ingestion with
`Mail.ReadBasic`, explicit MSAL desktop sign-in, OS-keyring token-cache/account
binding, immutable message IDs, and per-folder opaque Graph delta cursors. It
does not fetch bodies, previews, attachments, or extended properties. Existing
Gmail behavior and the provider-independent ingestion/provenance path are retained.

See [Outlook setup/recovery](docs/outlook.md) for public-client app registration,
identity/alias rules, account and folder configuration, and the opt-in smoke
procedure. `config/household.outlook.example.yaml` contains only synthetic account
examples. The [Phase 2B review handoff](docs/phase-2b-review.md) records decisions,
acceptance evidence, limits, and exact questions for ChatGPT. No live Microsoft
sign-in or Graph access occurs in automated tests or CI.

## Phase 2C: Google Calendar read-only

Issue #6 adds independent Desktop OAuth/keyring binding with exactly CalendarList
and event read-only scopes, primary CalendarList identity verification, provider-scoped
duplicate-account guards, and per-calendar opaque incremental state. Recurring series,
exceptions, cancellations, and composite calendar/event provenance are preserved.
Descriptions, attachments, arbitrary private payloads, recurrence expansion, and
Gmail↔Calendar canonical dedupe are excluded. Merged Gmail/Outlook behavior is retained.

See [Calendar setup/recovery](docs/google-calendar.md), the synthetic
`config/household.google-calendar.example.yaml`, and the
[Phase 2C review handoff](docs/phase-2c-review.md). Real OAuth/access is opt-in only;
automated tests and both database CI jobs use synthetic responses and fake clients.

## Phase 2D: Google Drive metadata-only

Issue #10 adds explicit email/permission-ID binding, separate native keyring storage
and exactly `drive.metadata.readonly`. Race-safe personal and exact-ID opt-in Shared
Drive baselines catch up through independent opaque change streams. File IDs,
shortcuts, trash/removal observations and minimized metadata retain provenance; no
contents, exports, paths, canonical documents or provider writes are introduced.

See [Drive setup/recovery](docs/google-drive.md), the synthetic
`config/household.google-drive.example.yaml`, and the
[Phase 2D review handoff](docs/phase-2d-review.md). OAuth/access is explicit and
opt-in; automated tests and CI use fake clients only.

## Phase 2E: callable ingestion and recovery

Issue #12 moves routine provider orchestration into `family_os.services`; the CLI
presents safe results over those callable local operations. Google keyrings save
only changed credential state. Provider scopes, cursors, privacy and recovery
semantics remain unchanged. Services are not authenticated API endpoints; client
auth and background execution remain future work. See the
[Phase 2E review handoff](docs/phase-2e-review.md).


## Phase 2G: conservative local metadata classification

After migrating and ingesting sources, run from the repository root:

```sh
family-os analyze-metadata --household HOUSEHOLD --limit 100
python -m family_os.metadata_evaluation
```

The first command classifies only current persisted minimized metadata through the
Phase 2F services and prints aggregate counters. It uses `config/classification.yaml`
and `config/metadata-classifier.yaml`; optional `--classification-config` and
`--rules-config` select validated local files. Rule edits change the effective analyzer
version automatically; intentional changes should also bump `ruleset_version`.
Unsupported/conflicting inputs abstain and recommend review. No external AI/provider
call, content fetching, facts/tasks/review queue or scheduler is added.

The second command evaluates the same runtime analyzer on committed synthetic cases,
not production accuracy. See [Phase 2G review](docs/phase-2g-review.md) for rules,
confidence semantics, limitations and migration/downgrade behavior.

## Phase 2H: local classifier audit

After migration and `analyze-metadata`, explicitly inspect minimized metadata locally:

```sh
family-os metadata-audit-list --household HOUSEHOLD --limit 20 --strategy unlabeled
family-os metadata-audit-label --household HOUSEHOLD --analysis ANALYSIS_ID --relevance relevant --domain-category home --domain-subcategory utility --action required
family-os metadata-audit-metrics --household HOUSEHOLD
family-os metadata-audit-simulate --household HOUSEHOLD --relevance-threshold 0.90 --domain-threshold 0.90 --action-threshold 0.90
```

Omit both domain flags for human unknown. Labels append revisions against an exact
analysis; metrics use highest revisions for the exact current classifier/snapshot.
Sampling also supports `needs_review`, `accepted`, and `balanced`. Unlike aggregate-only
analysis, audit list deliberately displays bounded subject/sender and fixed minimized
metadata to the local operator. Protect redirected output; never commit real audit data.
No provider/model/network call occurs. Metrics are labeled-sample measurements;
simulation changes no history or config. This is not the product review queue.
See [Phase 2H review](docs/phase-2h-review.md) for denominators, concurrency and limits.

## Phase 2I: diagnose rule coverage locally

Before changing rules or thresholds, run aggregate-only diagnostics across current
sources (including unanalyzed records):

```powershell
.\.venv\Scripts\family-os.exe metadata-coverage --household HOUSEHOLD --limit 1000
```

Explicit local inspection uses `metadata-coverage-sample --household HOUSEHOLD
--limit 45`: it displays sensitive minimized metadata locally, with provider/month/type
spread and dry-run predictions where current analysis is missing. Never share sample
output. For a chosen missing analysis, `analyze-metadata --household HOUSEHOLD
--source SOURCE_RECORD_ID` returns safe IDs for the existing append-only human-label
workflow. See [Phase 2I PowerShell workflow and limits](docs/phase-2i-review.md).
Production rules and thresholds are unchanged; no external data egress occurs.

## Phase 2J: interactive local metadata review

Run directly in a local PowerShell terminal:

```powershell
.\.venv\Scripts\family-os.exe metadata-review --household HOUSEHOLD --since 2026-01-01 --limit 15
```

The UTC date window starts inclusively; optional `--until` is exclusive (default:
tomorrow UTC). Recent candidates are balanced across providers/types; already-labeled
current analyses are skipped unless `--include-labeled` is supplied. One record at a
time: skip, label all dimensions, or quit; type `save` to confirm. During labeling,
`b` / `back` returns to the previous prompt; `c` / `cancel` discards the draft and
returns to the same record menu. Changing domain clears its old subcategory.
Confirmed analysis and append-only label commit together with stale-display protection. Other choices
write nothing. This intentionally shows sensitive minimized metadata **locally**;
no pipes, redirects, transcripts or AI uploads. See [Phase 2J](docs/phase-2j-review.md)
for provider filters, exact PowerShell steps, concurrency guarantees and limitations.

### Developer-only Ollama synthetic benchmark (Phase 2M)

After review/merge, manually benchmark the already installed local model against only
37 checked-in synthetic fixtures. No Samas Family OS database or production classifier is
connected. Default invocation uses five smoke cases; `--full` explicitly selects all
37. See [exact PowerShell commands, loopback isolation and limits](docs/phase-2m-review.md).
No model download or real household inference is authorized.
Phase 2N adds an opt-in `--variant flat-domain` synthetic A/B experiment; the
default baseline is unchanged. See [commands and diagnostic denominators](docs/phase-2n-review.md).
Phase 2P adds explicit selection of two installed model tags for a controlled
synthetic comparison; see [Thinking compatibility and smoke/full gates](docs/phase-2p-review.md).

Phase 2Q adds a separate 90-case synthetic Action dataset, frozen holdout and
offline-only rules evaluation; see [rubric, split protocol and commands](docs/phase-2q-review.md).

Phase 2R adds a separate manual development-only Action model benchmark: five-case
smoke or explicit 60-case development run, with no holdout inference. See
[exact PowerShell commands, metrics and safety gates](docs/phase-2r-review.md).

Phase 2S adds a separate Qwen3-only manual prompt experiment with baseline and three
independent development-only variants. See [pre-registered plan, diagnostics and
PowerShell commands](docs/phase-2s-review.md); no holdout or production inference.

Phase 2T adds a separate in-memory synthetic paired diagnosis and classification
architecture decision. See [evidence, Calendar protection and manual commands](docs/phase-2t-classification-decision.md);
no production adoption, real-household inference or holdout model evaluation.

Phase 2U adds a separate **no-AI**, synthetic-only deterministic Calendar evidence
interpreter and offline aggregate evaluation. All proposals require human review;
there is no production wiring or action authority. See
[rules, safety probes, limitations and PowerShell commands](docs/phase-2u-calendar-evidence.md).

Phase 2V adds an isolated, in-memory synthetic human-review simulation. Explicit
decisions and exact evidence/version matching govern repeat annotations; all items
remain visible, with no task authority or production wiring. See
[review contract, limitations and manual commands](docs/phase-2v-human-review-workflow.md).

Phase 2W documents the future end-to-end discovery, human review and separate
follow-up journey; it implements no product queue, UI, backend auth or tasks. See
[the product blueprint, decisions and dependencies](docs/phase-2w-product-workflow.md).

Samas Family OS v0.1 Slice 1 adds a private **disposable synthetic-only** durable review
core, with explicit saves, immutable history and version/CAS/retry protection. It is
not a live review queue or a production CLI/service; see the
[isolated contract and test commands](docs/v0-1-single-user-review-core.md).

Samas Family OS v0.1 Slice 2 adds an opt-in **synthetic-only terminal demonstration** over
that core, using a fresh disposable SQLite store per session. It remains separate
from the production CLI and reads no household data, providers, AI or frozen fixtures.
See [controls, PowerShell command and review boundaries](docs/v0-1-single-user-review-demo.md).

Samas Family OS v0.1 Slice 3 defines **action-first routing and email safety**, design only:
separate accepted tasks, pending confirmation, quiet information, on-demand promotions
and future gated reversible quarantine. No detector, tasks or mailbox writes are enabled.
See [routing, privacy gates and synthetic next steps](docs/v0-1-action-first-routing-email-safety.md).

Stage A adds only a private, pure **synthetic routing contract** with fixed enums and
unit tests. It has no production integration, UI, model, database or provider operations.
See [routing precedence, version binding and limitations](docs/v0-1-synthetic-routing-contract.md).

Stage B adds only a separate deterministic **synthetic phishing-policy evaluation**
and simulated recovery probes. No real detector or mailbox operations are enabled.
See [evidence boundaries, denominators and limitations](docs/v0-1-synthetic-phishing-policy.md).

Stage C adds a separate opt-in **in-memory synthetic action-first terminal demo**.
Review, simulated acceptance and simulated quarantine/restore have distinct confirmations;
no tasks or mailbox operations occur. See [PowerShell command, paginated backlog and
manual walkthrough](docs/v0-1-synthetic-action-first-demo.md).

Stage D specifies a **household-first unified workspace for two peer adults**, with
independent source grants, shared-task field permissions and operation consent. Its
22 newly authored synthetic conformance definitions require both privacy and complete
authorized aggregation. This is design only, not implemented authentication, tasks
or Stage E. See [sharing, revocation, continuity and review questions](docs/v0-1-household-first-authorization.md).

Stage E1 adds a **central security-action authorization specification** and isolated
synthetic preflight probes. Per-action approval is distinct from shared security-read
access; proposed standing authorization remains disabled. No executor, provider writes
or production permissions are enabled. See [policy register, synthetic cases and E2 gates](docs/v0-1-security-action-authorization.md).

Stage E2 adds a separate opt-in **disposable in-memory synthetic security lifecycle**
over unchanged E1 preflight: explicit intent reservation, fake outcomes/reconciliation,
own-delta restore and household access checks. No real provider or production authority
is enabled. See [simulation limits, sharing checks and test walkthrough](docs/v0-1-synthetic-security-lifecycle.md).

Stage G1 adds an opt-in **synthetic authorization-first shared read-service seam**.
Two peer adults query one fictional household state, with independent source-read
and task-publication grants and freshly authorized security/search/page projections.
There is no login, API, provider connection or production task system. See
[trust boundary, executable conformance and deployment decisions](docs/v0-1-household-read-service.md).

Stage G2a adds a private **durable authorization foundation** using the existing
SQLAlchemy/Alembic identities: current membership/read/publication grants, atomic CAS
revocation and actual-actor audit. It runs only with explicit fictional harness contexts
and fixed synthetic records, not provider data, login or an exposed service. See
[transaction guarantees, destructive downgrade limits and G2b gates](docs/v0-1-durable-household-authorization.md).

### Stage G2b1: offline verified identity boundary

The [G2b1 contract](docs/v0-1-verified-identity-boundary.md) adds a restricted offline
OIDC signature/claim verifier and exact external identity-to-Person binding. Fictional
signed assertions/disposable databases only; no login, session, G2a capability handoff,
API, real household access or provider change. G2b2 session/recovery gates remain future.

### Stage G2b2: internal durable sessions and reads

The [session/read contract](docs/v0-1-session-service-boundary.md) connects fictional
verified identity to SQL-backed hashed-bearer sessions and current G2a permissions.
One shared authorized projection serves both peers; no harness context is issued.
No production login/API/provider data access is enabled. Real OIDC/MFA, browser and
response-disclosure gates remain required before a usable network workbench.

### Stage H0: offline fictional browser workbench

Open `prototypes/h0-workbench/index.html` directly in a modern local browser. The
[Windows run guide and walkthrough](docs/v0-1-offline-family-workbench.md) covers
seven interactive views, two fictional peers, separate review/task confirmations,
quiet offers and source-sharing demonstrations. No server/install/login, real data,
network calls or persistence; all state resets on reload. This isolated product
prototype does not enable a production Web client or connect to backend services.

### Stage H1: 中文优先 / bilingual offline workbench

The same local HTML entry point now defaults to **简体中文**, with **English** selectable
per fictional member. [双语操作指南 / bilingual guide](docs/v0-1-bilingual-offline-workbench.md)
covers translated cases, safe confirmation cancellation on language changes and
permissions-first search. No production backend, login, data or persistence is added.

### Stage G3a: internal fictional OIDC code flow

The [login-flow foundation](docs/v0-1-oidc-login-foundation.md) adds Authlib-based
code/PKCE/state/nonce orchestration into unchanged verified identity, durable sessions
and authorized fictional reads. In-process simulator only: no HTTP transport, listener,
real account/enrollment, H1 integration or provider change. Real OIDC/MFA/browser and
read-only API deployment gates remain independently unapproved.

### Stage G3b: in-process fictional read API

The [authenticated read contract](docs/v0-1-fictional-read-api.md) adds one strict
ASGI resource over existing durable sessions and current household permissions,
tested through an in-process client only. No listener, login/mutation route, H1
connection, real records or provider call. Request preparation retains no private
projection; dispatch rechecks current rights. Production browser/deployment and
end-to-end response-revocation gates remain unapproved.

### Stage H2: offline backend-to-workbench preview

The [Chinese-first read-only preview](docs/v0-1-offline-backend-workbench.md) generates
fictional historical browser assets through actual G3b requests, durable sessions and
current database grants. It uses a new disposable DB; no runtime database discovery,
listener or real account. Original H1 stays separate and unchanged. Published neutral
steps are not accepted tasks; static member switching is not authentication. See the
guide for PowerShell generation/opening and the remaining Windows manual gate.

### Stage T1: internal durable household domain

The [task/Pending contract](docs/v0-1-durable-household-tasks.md) adds persistent
fictional proposals, separate explicit acceptance, one shared task, independent
recipient/edit/history grants and actor-attributed CAS/replay history. Existing
sessions and household transactions enforce current rights. No H1/H2 integration,
real enrollment, automatic extraction, API route or provider operation is enabled.

### Stage UX1: 一个家庭，一个应用

原 H1 入口现采用 [UX1 中文优先家庭体验](docs/v0-1-unified-household-ux.md)：五项主导航、
移动底栏、按需信息与优惠、设置与隐私，以及需单独确认的虚构任务分工。
PowerShell：`Start-Process (Resolve-Path '.\prototypes\h0-workbench\index.html').Path`。
仍只在标签页内存运行，未连接 T1/G3b。Windows 直接打开必须由用户在合并前验证。

外观仅在 **设置与隐私 → 外观** 提供跟随系统（默认）/浅色/深色；选择保留在
当前标签页内存中。[配色、截图与 Windows 验收](docs/offline-workbench-appearance.md)。

Development-only 离线规则诊断（60 条固定合成案例；不读取 Holdout、不运行模型）：
[使用说明与信任边界](docs/development-only-rule-diagnostics.md)。

规则为何 abstain：独立的[规则行动证据缺口诊断](docs/rule-evidence-gap-analysis.md)，
对照 Development 60 与原始 37 条的真实匹配/veto 轨迹；不修改分类行为、不运行模型。

[合成邮件行动证据 v1](docs/synthetic-email-action-evidence-v1.md) 是独立纯函数研究：
仅用新冻结标题探针区分具名步骤、完成声称、观察与促销；无 AI、旧基准输入或 Task 接线。

[冻结解释器的新合成措辞挑战](docs/synthetic-email-wording-challenge-v1.md) 用独立新编写的
36 条改写/歧义标题量化有限语法的覆盖限制；先远端冻结再运行，不调规则、不读旧基准。

[合成邮件语义证据模型对照](docs/synthetic-email-model-evidence-v1.md) 提供独立手动
inventory / smoke / full；只允许固定 wording 36 条与唯一已安装模型，开发/CI 仅 Mock，
不接入家庭数据或产品流程，也不自动运行推理。

Independent manual [single-case runtime diagnostic](docs/single-email-runtime-diagnostic-v1.md)
uses a separate 180-second chat budget; no scoring, real inference in CI, or change
to the frozen PR #107 experiment. Run only after owner review/merge.

The separately versioned [Ollama0.40.6 compatibility diagnostic](docs/single-email-runtime-diagnostic-v2.md)
accepts only the verified optional cache counter extension, records finite protocol
subreasons and independently validated telemetry, and offers a Restricted-compatible
stdin-only Windows workflow. PR107/108 remain frozen; historical failure cause unknown.

The independent [compatible wording36 semantic comparison](docs/synthetic-email-model-evidence-v2.md)
uses pinned PR109 validation with the original60s/600s semantic budgets, explicit
smoke/full and read-only report recovery. Old experiments/diagnostics stay frozen;
development/CI use Mock HTTP only, and operator runs manually after review/merge.
