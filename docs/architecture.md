# Architecture

## 1. Layered design

### A. Connector layer

Every connection is an independent `source_account`.

Examples:

```text
operator / Gmail personal
operator / Gmail secondary
operator / Outlook
Spouse / Gmail personal
Spouse / Gmail secondary
Household / shared mailbox
Google Calendar / primary
Google Calendar / shared family calendar
Google Drive / personal
Finance / Plaid item
```

A source account belongs to one of:

- `person`
- `household`
- `unknown`

This prevents the common mistake of assuming "one mailbox = one person".

### B. Raw ingestion layer

Never discard original metadata.

Store:

- provider
- source account
- provider object ID
- thread ID
- received / created timestamp
- sender / recipients
- subject
- body checksum
- attachment metadata
- raw provider metadata
- ingestion timestamp

The canonical database should be reconstructable from raw source objects.

### C. Normalization layer

Convert provider-specific objects into normalized records.

Examples:

```text
gmail_message -> message
outlook_message -> message
google_event -> calendar_event
drive_file -> document
plaid_transaction -> financial_transaction
```

### Derived source analysis (Phase 2F)

Between normalization and future canonical processing, `family_os.analysis_services`
provides local callable analyze-one, bounded pending analysis, history and exact
current-snapshot queries. Frozen provider-independent input contains only persisted
minimized source fields. An analyzer protocol returns structured proposals. Phase 2G
adds a real conservative local `MetadataRulesAnalyzer` with explicit domain abstention,
versioned declarative rules and synthetic evaluation. It uses no external model,
provider calls or unpersisted content. The CLI delegates `analyze-metadata` to the
application service and prints aggregate counts only. Inference runs outside a DB
transaction, then a short locked transaction verifies the same raw snapshot before
atomically persisting validated analysis/facts. A stale source writes nothing.

Analysis is immutable, versioned inference about one exact source/raw snapshot,
never canonical household truth. Confidence thresholds only recommend future
review; no canonical entity, review queue, task or action is created. These services
are not authenticated APIs or background workers. Future entry points still need
Family OS household authorization and scheduling decisions.

External inference is a separate data-egress/security boundary: provider OAuth
consent does not authorize sharing household metadata with an AI vendor. Future
adapters must declare the persisted fields sent and obtain appropriate authorization.
Durable artifacts are validated structured results, versions, confidence and evidence
refs; never chain-of-thought or default full prompt/raw-response storage. See
[Phase 2F contracts and review questions](phase-2f-review.md).

Phase 2H adds callable local `audit_services` for deterministic bounded inspection,
append-only human evaluation labels, current-definition/current-snapshot quality
metrics and pure threshold simulation. Explicit local audit listing may show
minimized subject/sender and fixed allowlisted scalar metadata; `analyze-metadata`
remains aggregate-only. These are evaluation artifacts, not product review queues,
canonical truth or authenticated API endpoints. No provider/content/network access
is introduced. Inspect local labeled quality before canonical/external-model expansion;
see [Phase 2H boundaries and denominators](phase-2h-review.md).

Phase 2I adds local callable `coverage_services` for aggregate rule applicability and
provider/month/type-diverse inspection of current sources, including dry-run inference
for unanalyzed records. Diagnostics share the runtime matcher; explicit local samples
reuse the audit display allowlist. Analyze-one delegates to unchanged Phase 2F persistence
before human labels may be appended. No production rules, thresholds, schema, provider
calls or external data egress change. See [Phase 2I workflow](phase-2i-review.md).

Phase 2J adds local `review_services` plus a separate terminal presentation adapter.
Recent UTC-window sampling includes unanalyzed sources; only explicit human confirmation
atomically persists/reuses analysis and appends a label while guarding the displayed
snapshot/definition. Existing analysis/label persistence helpers are shared for that
transaction. No inference or keyboard input holds DB locks. This is local quality
measurement, not authenticated API/UI, training, product review queue or task execution.
See [Phase 2J safety and operator workflow](phase-2j-review.md).

Phase 2K is an architecture/privacy decision only. The recommended next experiment
is a bounded synthetic metadata reasoning contract and, after explicit hardware and
installation approval, a local model benchmark. Rules remain the default; a future
hybrid must preserve exact snapshot/versioned proposals and definition-aware evaluation.
Cloud reasoning, content extraction and automatic downstream processing are separate
decisions, with no egress enabled here. See the [decision matrix, input boundaries,
consent gates and next-phase criteria](phase-2k-review.md).

Phase 2L adds only an isolated developer synthetic projection/manifest/fake-adapter
and paired comparison runner. It has no production CLI/service wiring, DB persistence,
model runtime or network transport. Candidate scores are uncalibrated zero and always
review-recommended under current thresholds. See [spike boundaries and validation](phase-2l-review.md).

### D. Identity resolution

Resolve:

```text
email address -> person
calendar attendee -> person
document owner -> person
financial account -> owner(s)
```

Do not require immediate resolution.
Unknown identities may remain unresolved until more evidence appears.

### E. Deduplication

Use multiple levels:

1. Provider object ID
2. Message/thread identity
3. Exact content hash
4. Semantic duplicate detection
5. Domain-level duplicate detection

Example:

- Same hotel confirmation sent to both spouses.
- One spouse forwards it to the other.
- Google Calendar creates an event from the same confirmation.

These should become **one canonical trip reservation** with multiple provenance records.

### F. AI classification/extraction

AI output should never overwrite provenance.

Each extraction stores:

```text
value
confidence
extractor_version
source_record
timestamp
```

Future review routing may send low-confidence proposals to `review_queue`. Phase 2F
only stores `review_recommended`; Phase 2G adds deterministic local metadata
classification, while review queues and ML/LLM classification remain future work.

### G. Canonical Household DB

This is the source of truth for household entities and actions.

Core domain objects:

- Person
- SourceAccount
- Asset
- Organization
- Document
- Message
- Event
- Reservation
- Purchase
- Policy
- Subscription
- MaintenanceRecord
- Task
- FinancialTransaction
- Relationship
- Provenance

## 2. Domain modules

### Admin
Generic household obligations and notices.

### Travel
Flights, hotels, rental cars, reservations, itinerary.

### Home
Lease/property, utilities, maintenance, renter/home insurance.

### Vehicle
Registration, insurance, service, tires, warranty, recalls.

### Pet
Vet visits, vaccinations, insurance, medication, documents.

### Purchase
Receipt, merchant, item, purchase date, return window, warranty.

### Finance
Financial accounts remain managed by the Finance subsystem.
Family OS stores references and reconciliations rather than duplicating financial truth.

## 3. Action policy

Every proposed action gets a risk class.

```text
R0 = read only
R1 = create draft / suggested task
R2 = create calendar event / move file
R3 = send email / cancel / delete / financial action
```

Recommended v1:

- R0 automatic
- R1 automatic or one-click
- R2 requires confirmation
- R3 always requires explicit confirmation

## 4. Event-driven future

Later, each new incoming item can trigger:

```text
new source record
  -> normalize
  -> dedupe
  -> classify
  -> extract
  -> reconcile
  -> decide whether action is needed
```

The first implementation can be batch-based. The data model does not need to change later.

## 5. Deployment and client architecture

### One household backend, multiple clients

Core ingestion, normalization, identity resolution, dedupe, canonical data, business
rules, AI/classification, review state, and action policy must be client-independent.
Desktop, web, and mobile interfaces are clients of the same household system. No
essential business logic belongs only in CLI formatting, a desktop/mobile UI, or a
provider-specific UI callback.

The target production shape is one authoritative household backend, reachable by
its authorized clients. It may be hosted or self-hosted; cloud hosting is not a
requirement. PostgreSQL is the likely production database for shared access. The
backend owns ingestion and domain processing, secure provider connections, shared
canonical state, and centralized action decisions.

```text
Gmail / Outlook / Google Calendar / Drive / Finance
                         |
                         v
                 Family OS Backend
          ingestion / normalization / dedupe
         canonical DB / AI / review / action policy
                         |
              authenticated service boundary
              /           |            \
       Desktop / Web    iPhone        Android
```

This diagram is the target, not a claim that all providers, canonical processing,
authentication, or clients are implemented. Finance remains its own source of truth;
the backend stores references/reconciliations rather than replacing that subsystem.

### Current local stage versus target deployment

| Concern | Current implementation | Target architecture / separate future work |
| --- | --- | --- |
| Operator interface | Local Python CLI triggers registration, explicit provider connection, and sync | CLI remains an operator/dev client; desktop, responsive web, and mobile share services |
| Core | Callable Python registry, provider ingestion/recovery application services, connectors, atomic ingestion, source normalization and versioned source analysis | Shared domain/services also own classification, identity/dedupe, canonical entities, review and actions |
| Database | SQLite for local use; PostgreSQL supported and tested for ingestion | One authoritative backend database for shared household state; likely PostgreSQL |
| Provider credentials | Separate account-scoped native OS-keyring entries on the local machine | Backend/provider-connection credential store with encryption and controlled access |
| Family OS client access | Local operator/database access; no Family OS login or service API | Separate client authentication plus server-enforced household/action authorization |
| Execution | Operator-invoked CLI sync | Backend scheduler/workers independent of a client being open |

SQLite and native keyrings remain appropriate for the current single-machine stage.
The CLI is an implementation surface, not the permanent system boundary. The current
source registry/provenance database must not be described as an implemented canonical
entity system. Hosted deployment, token migration, and the future clients are not
implemented by this checkpoint.

### Logical service boundary

Connectors and domain operations must remain callable independently of CLI/UI output.
Future service adapters invoke the same core rather than rebuilding ingestion or
household rules for each client. HTTP frameworks, REST versus GraphQL, and frontend
frameworks are deliberately undecided.

| Responsibility | Boundary |
| --- | --- |
| Household/source-account registration and ownership validation | Core services preserve person != account, tenancy, immutable identity/explicit ownership, and provider-scoped duplicate guards |
| Provider connection and source sync | Core orchestrates connector/auth adapters, identity/scope checks, minimized metadata, cursor recovery and transactions; provider SDK/OAuth types stay in that boundary |
| Queries, classification, canonical processing and review | Shared services apply domain/provenance rules and return client-appropriate state; clients render results and submit decisions |
| Action proposal, approval and execution | Backend services enforce authorization, R0–R3 policy, provider permissions, confirmation and audit requirements |
| CLI/web/desktop/mobile presentation | Clients collect input, display identity/consent or review prompts, and format responses; callbacks do not become the only enforcement of domain rules |

Phase 2E adds callable provider ingestion/recovery application operations in
`family_os.services`. They own account validation, secure client loading, existing
provider policies/verification, atomic ingestion and client cleanup. The CLI is a
presentation adapter over them; interactive connect remains provider-specific.
Results contain aggregate counters and optional verified operator identity, never
credentials, provider clients, cursors or raw metadata. Recovery remains local and
version/CAS protected. These functions are not authenticated HTTP/API endpoints;
Family OS client authentication/authorization and background scheduling remain future
work. A callable function is not yet an authenticated API. Future entry points must establish trusted client/household/person
context before invoking services, enforce authorized access to each operation, and
return no provider secrets in client-facing state. Passing a household ID or owning a
source account is not itself authentication or an authorization policy. See
[security boundaries](security.md#provider-oauth-and-family-os-client-access).

### Authoritative state, background sync, and clients

The backend database will hold authoritative canonical entities, provenance, review,
and action approval state. All clients observe the same household decisions; a phone
approval must be visible on desktop. Clients may later cache for UX/offline support,
but caches are not independent sources of truth or per-device canonical databases.
Offline edits/conflict handling require a future design that reconciles through the
backend's authorization and domain rules.

Provider ingestion should eventually run in backend background execution rather
than depend on opening a desktop/mobile app. Scheduler/worker design is separate
work. It must retain existing per-source and provider sub-stream cursor semantics,
account-level concurrency/version compare-and-swap, page atomicity, idempotent replay,
safe retries, typed explicit recovery and history retention. A scheduler must not
silently reset expired cursors, skip history, or bypass least-privilege read-only
provider behavior. Writes require the centralized action policy and provider grants.

The R0–R3 policy in section 3 remains authoritative in the backend. R0 reads may run
automatically within authorized access. R1 suggestions/drafts may be displayed or
accepted by clients under that policy. R2 calendar/file changes require explicit
confirmation; R3 send/delete/cancel/financial actions require explicit confirmation
and audit. Clients present and submit approvals, while the backend validates and
records shared approval state and enforces execution policy. Repeated requests from
different devices must not duplicate an approved action. Future approval/audit design
must bind confirmation to the proposed action; a client cannot downgrade its risk
class or turn a provider OAuth grant into approval to act.

Notifications are a future client capability derived from backend Needs Action,
deadlines, and approval state. Push delivery or dismissal must not create a separate
task database or become the source of truth. No notification infrastructure, worker,
API, auth layer, deployment, or new runtime behavior is added in Issue #8. See the
[roadmap](roadmap.md) for the staged path before desktop/web/mobile implementation.

### Internal durable authorization foundation (G2a)

G2a adds SQL-backed membership, source-read and independent publication-recipient
permissions plus actor-attributed change audit over the existing household/person/account
identities. Its private service has only trusted fictional harness contexts and a fixed
synthetic read repository; it does not read provider records or expose an API. Current-row
uniqueness, membership-revision binding and transactional CAS/audit replace simulated grant
replacement for this isolated path. PostgreSQL READ COMMITTED household locks and SQLite
writer reservation establish transaction ordering, not reusable disclosure leases.
See [verified behavior, migration limits and G2b gates](v0-1-durable-household-authorization.md).
Authentication, public entrypoint authorization, real domain reads, credential transition
and deployment remain unimplemented; existing provider application services are unchanged.

### Offline verified identity seam (G2b1)

G2b1 verifies a restricted OIDC ID-token profile using maintained PyJWT/cryptography,
then resolves exact issuer/subject to existing Person and current G2a membership.
It neither establishes sessions nor issues G2a harness capabilities. Authentication,
membership, source/publication rights, management, reviewer and action authority remain
independent. The explicit-engine resolver is fictional-test-only; no API or provider
path is wired. See [profile, binding and G2b2 gates](v0-1-verified-identity-boundary.md).

### Internal session-bound reads (G2b2)

G2b2 integrates verified fictional identity, durable hashed-bearer sessions and current
G2a membership/source/publication rights. Both paths share G2a's transaction/projection
mechanism; session identity never issues a harness or management context. One authoritative
household state serves both peers. The explicit-engine service is synthetic-only and
internal, with no network or provider-record path. See [lifecycle, tested ordering and
remaining real-login/workbench gates](v0-1-session-service-boundary.md).

### Stage G3a: code-exchange seam, not exposed login

The [internal fictional OIDC flow](v0-1-oidc-login-foundation.md) consumes an exact
single-use attempt and uses Authlib code/PKCE orchestration before unchanged G2b1
proof and G2b2 session establishment. No authenticated household capability is inferred
from profile claims; reads still use current G2a grants. The injected exchange is
in-process only, with no listener, production transport, frontend connection or enrollment.
Real provider/profile, browser-bound durable attempts, MFA/recovery and authenticated
read-service entrypoints require separate approval and deployment review.

### Stage G3b: in-process fictional transport

The [read-only ASGI seam](v0-1-fictional-read-api.md) binds a trusted test household
and calls G2b2's existing current session/G2a-authorized read on every request. Explicit
JSON allowlists keep source, security and independent published-step lanes separate.
Preparation stores only a query specification; dispatch performs the fresh DB read.
No competing authorization engine, public listener, H1 integration or production login
is enabled. Database ordering cannot retract delivered bytes; browser, transport,
response/cache revocation and deployment gates remain separately required.

### Stage H2: fictional offline presentation integration

The [H2 developer preview](v0-1-offline-backend-workbench.md) invokes actual G3b through
an in-process client over a newly provisioned disposable household DB and two existing-
mechanism fictional sessions. Only exact authorized responses drive three read-only
presentation lanes; H1's richer task/pending/date model remains separate and unsupported
by G3b. Static fictional captures are explicitly historical, never live permission
leases or approved private client caches. No production service or frontend is connected.

### Stage T1: internal durable task and pending domain

[T1](v0-1-durable-household-tasks.md) uses the existing G2b2 session validation and
G2a household transaction/source-right resolution for callable fictional-only
domain services. Independent proposal-review/publication and task-read/edit/history
grants keep review, explicit acceptance and progress tracking separate. One stable
accepted task serves both authorized adults; private origin is excluded from neutral
projections even after source revocation. Evidence-bound annotations and acceptance,
CAS, exact actor/request replay and UNKNOWN-outcome verification preserve history.
No production producer, API, UI wiring, canonical dedupe or external action is added.
H2 preview publications remain a separate read-only presentation contract.

### Stage UX1: unified fictional household presentation

[UX1](v0-1-unified-household-ux.md) redesigns the same H1 offline application rather
than adding an admin site. Navigation, Chinese/English copy and responsive controls
remain over its existing fictional model; assignment uses the same confirmed
revision-bound task edit path. T1/G2a/G2b2/G3b are unchanged and disconnected. The
future mapping requires server-authorized capabilities and exact revisions; browser
controls are not authority. H2 remains a developer artifact. Windows manual opening,
authenticated integration and production deployment remain separate review gates.

### Stage I2: bounded local fictional browser-session test

The opt-in [I2 loopback lab](stage-i2-local-session-boundary.md) serves three fixed
test assets and session-only APIs from one literal 127.0.0.1 origin using Waitress.
A terminal operator approves a one-time browser pairing for fixed fictional peers;
existing verifier/SessionService establish and recheck durable sessions in an owned
temporary database. No second authorization engine, H1 model authority, G3b deployment,
T1 task route, provider path or production authentication is introduced. Cookie/Origin
controls are experimentally tested on loopback; production TLS/browser/login and
response-disclosure gates remain. The original file:// application stays independent.

### Stage I3: read-only fictional Tasks connection

The [I3 connection mode](stage-i3-readonly-task-workbench.md) reuses UX1 styles and
I2's loopback/session boundary, then calls unchanged T1 TaskService for current SQL
authorization, counts and pages. Explicit minimal task JSON excludes private origin,
evidence, history and grant metadata. The browser loads no H1 fixture/model; unsupported
views stay unconnected rather than importing simulated tasks. Trusted initialization
uses the existing T1 acceptance/edit lifecycle only in an owned disposable database.
No production login, write API, provider or real-data access is enabled. Source and
task rights remain independent; response/revocation and Windows gates remain explicit.

### Stage I4a: confirmed fictional Pending acceptance

The [I4a opt-in adapter](stage-i4a-safe-pending-acceptance.md) reuses I2 sessions and
I3 presentation/Tasks reads. A narrow T1 preparation method uses the same acceptance
validation to bind a server-held immutable command; the browser confirms an opaque
session-bound receipt and cannot choose recipient grants. Original T1 apply/CAS/audit
and fresh-connection outcome verification remain authoritative. Default I2/I3 and
file:// behavior stay separate. No production authentication, provider writes, task
extraction, edit/archive API or real household data is enabled.

### Stage I4b: confirmed fictional task tracking edits

The [I4b opt-in runner](stage-i4b-safe-task-editing.md) adds minimal server-held
assignment/status previews over the same T1 EDIT validator, with exact task/right/
recipient epoch snapshots. ACCEPT and EDIT share the existing receipt coordinator;
an unresolved intent cannot be bypassed by another operation. Current task grants
remain independent from private source access. Default I4a is acceptance-only. No
schema, production auth, provider operation or personal archive lifecycle is added.

### Stage I5: opt-in fictional producer into the existing task domain

The [I5 coordinator](stage-i5-information-to-pending.md) maps bounded, independently
asserted fictional safety/business evidence through unchanged Stage A routing into
existing T1 Pending, under the same household transaction ordering. Independent
fixture preapproval supplies permissions, never classifier output. An additive producer
ledger preserves versions/idempotency; only original human ACCEPT creates a Task.
No real source discovery, production producer identity, model, new browser route or
external execution is enabled. Durable producer delivery and post-accept evidence
reassessment remain separate gates; ordinary I3/I4a/I4b startup is unchanged.

### Stage I6: authorized fictional Pending explanations

[I6](stage-i6-authorized-pending-explanations.md) adds one opt-in explanation GET over
existing T1 transactions/current source and Pending rights, plus exact I5 ledger binding.
Finite bilingual reason templates preserve observation/security field separation; the
original I4b preview/confirmation remains the sole acceptance path. No second domain,
migration, real-source integration or production endpoint is introduced.

## I8 personal workflow extension

The [I8 contract](stage-i8-personal-not-applicable-resume.md) reuses the authoritative T1 domain and I7 receipt coordinator. New own NOT_APPLICABLE/RESUME are opt-in only; source/Pending/review authority, exact evidence and source-grant revision precede new writes. Shared Pending CAS remains; personal decisions never create a household resolution or modify accepted Tasks.
