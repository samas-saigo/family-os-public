# Roadmap

This roadmap separates completed implementation from design references and future
work. The target is one authoritative household backend/core with desktop, web, and
mobile clients; current CLI/SQLite/native keyring operation is a local stage. See
[deployment/client architecture](architecture.md#5-deployment-and-client-architecture).

## Phase 0 — Architecture (design references)

- [x] multi-person / multi-account model
- [x] canonical schema
- [x] provenance
- [x] review queue
- [x] write-action policy
- [x] dedupe strategy

These checks record architecture/design artifacts, not implemented canonical
entities, classification, review UI, or write execution.

- [x] Issue #8 multi-client/backend architecture checkpoint

## Phase 1 — Read-only ingestion

- [x] source account registry with household/ownership/identity guards (foundation)
- [x] minimized raw ingestion, versioned history and provenance (foundation)
- [x] provider-independent source normalization and idempotent ingestion (foundation)
- [x] Gmail read-only adapter (Phase 2A / Issue #2)
- [x] Outlook own-mailbox read-basic adapter (Phase 2B / Issue #4)
- [x] Google Calendar read-only discovery/events adapter (Phase 2C / Issue #6)
- [x] Google Drive metadata-only adapter (Phase 2D / Issue #10)
- [x] provider-ingestion application services and Google credential-persistence
  stabilization (Phase 2E / Issue #12)

The completed adapters use local operator-triggered sync and account-scoped native
keyrings. This is source ingestion/normalization, not canonical entity dedupe. Existing
provider cursor, scope, privacy, and recovery behavior remains the baseline.

## Phase 2 — Classification

- [x] versioned source-analysis/provenance foundation (Phase 2F / Issue #14)

- [x] household relevance classifier — conservative local metadata baseline (Phase 2G / Issue #16)
- [x] domain classifier — conservative local metadata baseline with abstention (Phase 2G)
- [x] action-needed classifier — conservative local metadata baseline (Phase 2G)
- [x] local classifier audit / human-label evaluation foundation (Phase 2H / Issue #18)
- [x] local rule-coverage diagnostics and diverse inspection (Phase 2I / Issue #28)
- [x] recent-date interactive local metadata review (Phase 2J / Issue #30)
- [x] AI-assisted classification architecture/privacy decision checkpoint (Phase 2K / Issue #34; design only)
- [x] offline synthetic metadata reasoning contract/comparison spike (Phase 2L / Issue #36; fake only)
- [x] manual localhost Ollama synthetic benchmark (Phase 2M / Issue #38; no production integration)
- [x] opt-in synthetic flat-domain schema A/B experiment (Phase 2N / Issue #42; no production integration)
- [x] controlled allowlisted local-model synthetic comparison (Phase 2P / Issue #44; no production integration)
- [x] independent balanced synthetic Action evaluation dataset and frozen holdout (Phase 2Q / Issue #46; offline only)
- [x] isolated development-only Action model benchmark (Phase 2R / Issue #48; manual synthetic comparison, no holdout inference)
- [x] controlled Qwen3 prompt experiments and development-only diagnostics (Phase 2S / Issue #50; manual synthetic only)
- [x] paired synthetic diagnosis and classification architecture decision (Phase 2T / Issue #52; no production adoption)
- [x] isolated synthetic Calendar action-evidence interpreter and indicator comparison (Phase 2U / Issue #54; no AI or production integration)
- [x] isolated synthetic human-review contract and repeat-safety simulation (Phase 2V / Issue #57; no production review queue or action authority; [limits](phase-2v-human-review-workflow.md))
- [x] end-to-end review/follow-up product blueprint (Phase 2W / Issue #59; docs-only; [decisions and future gates](phase-2w-product-workflow.md))
- [ ] structured extraction
- [ ] confidence-threshold product behavior

These are deterministic rule baselines, not ML/LLM quality claims. Synthetic evaluation
does not establish real-world accuracy; content/model expansion remains a separate decision.
Use local human labels to inspect real metadata quality before trusting classifier
outputs as canonical-processing inputs. Evaluation labels are not the product review queue.
The [Phase 2K decision](phase-2k-review.md) recommends a synthetic-only reasoning spike,
then explicitly approved synthetic-only local benchmarking. Phase 2T AI experiments
remain limited to the frozen synthetic Development Set. Real household Gmail,
Outlook, Calendar, Drive and other source data must not enter any AI model, including
local Ollama; local human inspection/labeling is separate from AI evaluation.
No model integration, cloud egress, content expansion or automatic downstream
processing is implemented.

## Family OS v0.1 — isolated research and design

- [x] Slice 1: disposable synthetic review core (Issue #61; [contract](v0-1-single-user-review-core.md))
- [x] Slice 2: opt-in synthetic interactive review demo (Issue #63; [controls](v0-1-single-user-review-demo.md))
- [x] Slice 3: action-first routing and email safety architecture (Issue #65; **design only**; [decisions](v0-1-action-first-routing-email-safety.md))
- [x] Stage A: isolated deterministic synthetic routing contract ([boundaries](v0-1-synthetic-routing-contract.md)); no production routing or execution
- [x] Stage B: isolated synthetic phishing-policy evaluation ([methodology](v0-1-synthetic-phishing-policy.md)); no detector or actual quarantine/restore
- [x] Stage C: opt-in disposable synthetic action-first terminal demo ([walkthrough](v0-1-synthetic-action-first-demo.md)); no actual tasks or mailbox operations
- [x] Stage D: household-first privacy/authorization design and 22 synthetic conformance definitions ([contract](v0-1-household-first-authorization.md)); **design only**, no production authorization or tasks

- [x] Stage E1: central security-action specification and isolated synthetic preflight ([contract](v0-1-security-action-authorization.md)); no executor or production grants
- [x] Stage E2: disposable in-memory synthetic execution/reconciliation simulation ([contract](v0-1-synthetic-security-lifecycle.md)); no real executor, durability or provider writes
- [x] Stage G1: synthetic authorization-first shared read-service seam ([trust boundary and deployment gates](v0-1-household-read-service.md)); no production login, API, grants or task creation
- [x] Stage G2a: internal durable household authorization/CAS/audit foundation ([transaction and identity limits](v0-1-durable-household-authorization.md)); fictional harness and fixture reads only, no production authentication or provider access
- [x] Stage G2b1: offline verified identity and exact Person binding ([profile and limits](v0-1-verified-identity-boundary.md)); no login, session or authorized service handoff
- [x] Stage G2b2: internal durable sessions and current G2a-authorized unified reads ([contract and limitations](v0-1-session-service-boundary.md)); fictional identity/fixture records only, no login/API
- [x] Stage H0: disposable offline fictional browser workbench ([run guide and limitations](v0-1-offline-family-workbench.md)); no authentication, backend connection, real data or persistent tasks
- [x] Stage H1: Chinese-first bilingual offline presentation ([guide and review gates](v0-1-bilingual-offline-workbench.md)); fictional state only, unchanged H0 business/security model
- [x] Stage G3a: internal fictional OIDC code/PKCE/state/nonce foundation ([profile and production gates](v0-1-oidc-login-foundation.md)); simulator only, no real login/enrollment or API
- [x] Stage G3b: in-process authenticated fictional read-only ASGI contract ([schema, dispatch and deployment limits](v0-1-fictional-read-api.md)); existing sessions/rights, no listener, real data or production exposure
- [x] Stage H2: offline Chinese-first preview driven by actual fictional G3b responses ([mapping and Windows guide](v0-1-offline-backend-workbench.md)); historical synthetic assets only, no live login, task lifecycle or production frontend integration
- [x] Stage T1: internal durable fictional task/Pending domain ([lifecycle and privacy contract](v0-1-durable-household-tasks.md)); existing sessions, separate acceptance/publication/edit grants, CAS and immutable actor history; no production task extraction, API or H1/H2 connection
- [x] Stage UX1: Chinese-first unified household offline prototype redesign ([navigation, screenshots and T1 mapping](v0-1-unified-household-ux.md)); same H1 entry point and fictional model, no production frontend or backend connection; Windows manual verification required
- [x] UX2 Connected UI Foundation — [I4b-scoped Calm Premium presentation](ux2-connected-ui-foundation.md), existing fictional sessions/T1 confirmations preserved; no production or real data; Windows manual acceptance required
- [x] UX2 A1 Editorial Home — [authorized fictional I4b Tasks/Pending](ux2-a1-authorized-home.md), first-page/date scope, existing confirmations and fail-closed coordinated reads; no specimen data or real accounts
- [x] UX2 [authorized responsibility filters](ux2-authorized-responsibility-filters.md) — I4b-only All/Mine/Other/Joint over current task grants, server-side totals/pages; Home and shared readership unchanged; fictional local testing only
- [ ] A1 additional calendar/security projections and global unfinished/date metrics — separate backend contract/review; currently unavailable, never inferred from a partial page
- [x] Stage I1 readiness audit and isolated task-read conformance ([blockers and connection contract](stage-i1-safe-read-connection.md)); no browser/backend connection or listener implemented
- [x] Stage I2: opt-in loopback fictional session lab ([startup, cookies and limits](stage-i2-local-session-boundary.md)); current G2b2 sessions, no Tasks endpoint, real login or household data
- [x] Stage I3: fictional browser task-read integration ([API, Windows guide and limits](stage-i3-readonly-task-workbench.md)); current I2 cookies/T1 SQL rights, UX1 styling, no task writes or real data
- [x] Stage I4a: opt-in fictional Pending preview/explicit acceptance ([contract and recovery](stage-i4a-safe-pending-acceptance.md)); existing T1 CAS, fixed server-approved plans, no task editing/archive, real login or external execution
- [x] Stage I4b: opt-in confirmed fictional task assignment/completion/reopening ([contract](stage-i4b-safe-task-editing.md)); existing T1 EDIT/CAS, shared acceptance/edit UNKNOWN coordination, no archive, real data or external actions
- [x] Stage I5: [fictional information routing into T1 Pending](stage-i5-information-to-pending.md), independent preapproval, versioned producer ledger and original human ACCEPT; synthetic-only, no real data/model/provider operations
- [x] Stage I7: [authorized personal Pending handling](stage-i7-pending-review-workflow.md), existing T1 review/defer/needs-information, exact evidence, personal filters and shared write coordination; fictional-only, no global rejection or real data
- [x] Stage I6: [authorized fictional Pending explanations](stage-i6-authorized-pending-explanations.md), exact I5/T1 binding and observation/security field scopes; original explicit acceptance, no real data or private evidence in shared Tasks
- [ ] Approved real OIDC flow/MFA/invitation/recovery, authenticated read entrypoints and disclosure/deployment review before a **production** web workbench or multi-user exposure

Stage A models independent safety/business/authority states, quiet promotions and
simulated security handling only. Stage B evaluates newly authored threat evidence and
simulated recovery only. Stage C demonstrates the five views and separate explicit
synthetic intentions in memory, preserving all Slice 3 privacy and security gates.
Stage D specifies one unified workspace for two peer adults over all explicitly shared
sources, with independent source/task/operation permissions and revocation. Its matrix
is a prospective acceptance contract, not executed authorization tests. Exact sharing,
retention and implementation policies still need review. Stage E1 now specifies central security-action authority with isolated synthetic
preflight probes; proposed standing authorization remains disabled. E2 models a disposable synthetic lifecycle only. Durable execution, authenticated
grants and all real operations remain future, separately approved work.
G1 adds only a callable synthetic read seam over one household state; source permissions
and independently approved task fields remain separate. Authenticated context, authoritative
PostgreSQL permissions, backend credentials, background sync and transport/cache safety
remain future gated work. No existing research code is promoted to production.
Automatic reversible email quarantine is a future goal requiring separate central
R0–R3 policy, per-mailbox consent, provider write/OAuth, privacy and recovery review.
No tasks, quarantine, body access, consumption profiling or real-data AI is enabled;
Phase 3–5 and shared/network clients remain unimplemented.

## Phase 3 — Canonical entities

- [ ] identity resolution
- [ ] dedupe engine
- [ ] canonical entity merge
- [ ] review queue

## Backend/service deployment milestone — before UI/mobile implementation

- [ ] authenticated service boundary around shared core/domain operations; API
  transport/framework deliberately undecided
- [ ] separate Family OS client authentication and household/person authorization
- [ ] one authoritative household backend database, likely PostgreSQL; hosted or
  self-hosted deployment supported by design
- [ ] encrypted backend/provider credential store and explicit migration/re-consent
  strategy; provider refresh tokens excluded from normal client-facing state
- [ ] backend background ingestion independent of client activity, preserving cursor
  semantics, account-level CAS, safe retries, atomicity, and idempotent replay
- [ ] shared review/action approval state and centralized R0–R3 enforcement

No API/auth/worker/credential migration is implemented by the architecture checkpoint.

## Phase 4 — Family Admin clients (one backend)

- [ ] responsive web/desktop client consuming shared authenticated services
- [ ] iPhone/Android mobile app consuming the same API/domain contracts
- [ ] future UX/offline caches with backend reconciliation; no per-device canonical DB

Frontend frameworks and dedicated-app packaging remain undecided.

- [ ] Inbox
- [ ] Needs Action
- [ ] Upcoming
- [ ] Assets
- [ ] Documents
- [ ] Search

## Phase 5 — Controlled actions

- [ ] suggested tasks
- [ ] confirm-before-calendar-write
- [ ] draft-only email workflow
- [ ] document organization suggestions
- [ ] shared explicit confirmations and audit for R2/R3 execution across clients
- [ ] notifications derived from backend Needs Action/deadline/approval state;
  delivery does not create a separate task database

## Phase 6 — Finance reconciliation

- [ ] receipt <-> transaction matching
- [ ] recurring household cost references
- [ ] avoid duplicating Finance source-of-truth

## Recommended sequence after this checkpoint

1. Review the [Phase 2T evidence and architecture decision](phase-2t-classification-decision.md).
   After reviewed merge, use the manual development-only paired diagnostic if needed;
   existing summaries do not establish case-aligned repairs or root causes. Review the
   [Phase 2U synthetic Calendar evidence results](phase-2u-calendar-evidence.md): supported
   finite conditions improve the fixed synthetic probes, but human review remains
   mandatory for every proposal. Continue only isolated synthetic research or abstain;
   production adoption, real-data shadow mode and holdout inference remain unauthorized.
2. After explicit approval, benchmark a local candidate only on approved synthetic
   development cases, preserving the frozen holdout boundary. Evaluate important
   false positives/missed actions without sending real locally labeled household
   samples to any AI, including local Ollama. Real metadata inspection and human
   labeling remain local, human-only operations.
3. Decide any structured-extraction/content boundary separately. This roadmap does
   not authorize real household data in any AI or any cloud egress; synthetic-only
   experiments do not grant permission to expand that boundary.
4. Identity resolution, canonical dedupe and entities, only after classifier quality
   and upstream boundaries have been reviewed.
5. Authenticated backend API and background execution milestone, including the
   credential/auth boundaries above.
6. Responsive web/desktop client using that backend.
7. Mobile app sharing API/domain contracts with web.
8. Controlled write actions and notifications as later milestones, under the
   centralized R0–R3 confirmation/audit policy.

Finance reconciliation remains separate domain work and must preserve Finance as
its own source of truth. This sequence does not authorize implementing any of the
future milestones in the documentation-only checkpoint.

## I8 — fictional personal handling extension

- [x] [Own not-applicable / resume](stage-i8-personal-not-applicable-resume.md): finite private reasons, exact-evidence state, source-epoch-bound writes and guarded migration in the synthetic-only workbench.
- [ ] ChatGPT/Muse review, Windows owner acceptance and human-controlled merge.
- [ ] Real household deployment, production authentication and runtime migration approval.

This does not complete household rejection, canonical processing, provider actions or task automation.

## I9 — fictional personal action Home

- [x] [Smart Personal Action Home](stage-i9-personal-action-home.md): server-authorized
  own/joint unfinished Tasks, active Pending (including viewed), follow-up and
  authorized collaboration; full totals and bounded samples in one transaction.
- [ ] Independent code/security review and Windows dual-member acceptance.
- No real mail, production login, AI, notifications or automatic task execution.
