# Security & Privacy

## Principles

1. Never commit credentials.
2. Store provider OAuth tokens outside the repo.
3. Encrypt sensitive local data at rest.
4. Separate raw ingestion from user-facing views.
5. Maintain source-account ownership and access boundaries.
6. Log write actions.
7. Make destructive actions reversible where possible.

## Secrets

Use environment variables or a secret manager.

Never store:
- OAuth refresh tokens
- passwords
- API keys
- account numbers in plaintext config
- session cookies

## Suggested environment classes

```text
LOCAL_DEV
HOUSEHOLD_PROD
```

Use fake/sample data for development whenever possible.

## Data retention

Recommended:
- retain normalized metadata
- retain source IDs and checksums
- avoid copying full email bodies forever unless needed
- retain attachment hashes and references
- add configurable deletion/redaction policies later

## Provider OAuth and Family OS client access

Provider OAuth and Family OS client authentication answer different questions:

| Boundary | Question answered |
| --- | --- |
| Provider OAuth | Which external source/account may Family OS access, and with which read/write scopes? |
| Family OS client authentication | Which person/client is accessing Family OS? |
| Family OS authorization | Which household data and operations may that authenticated principal access, subject to ownership and action policy? |

A successful Google/Microsoft provider connection is not a Family OS login, household
membership grant, or approval for a write action. A person can own multiple provider
accounts, and a source account can have household or unresolved attribution. Those
ownership/provenance facts must remain separate from future client access permissions.

Current commands run under a local operator's machine/database access. There is no
Family OS authentication/API layer today. Database household scopes and foreign keys
protect data integrity; they do not replace service authorization. Future service
entry points must establish trusted principal/household context, enforce household
tenancy and person/household access rules on each operation, and preserve centralized
R0–R3 confirmation/audit policy. Client-supplied household, owner, or risk-class values
must not be treated as proof of access. Authentication mechanisms, membership/role
rules, and session management require separate design and implementation.

## Current keyrings and future backend credentials

Native OS-keyring storage is the correct credential boundary for the current local,
single-machine Gmail, Outlook, and Google Calendar adapters. Their account bindings,
separate keyring services, exact scopes, explicit consent and fail-closed behavior
remain unchanged. See [Gmail](gmail.md), [Outlook](outlook.md), and
[Google Calendar](google-calendar.md) for the provider-specific requirements.

The normal multi-client architecture keeps provider credentials at the
backend/provider-connection boundary. Desktop, web, and mobile clients should not
need or receive provider refresh tokens. Do not put tokens, credential caches, or
provider secrets in client-facing API results, UI state, offline caches, notifications,
or shared review/action state. Provider tokens also stay out of Git, plaintext
config/database fields and logs. Future provider consent interactions may involve a
client browser, but credential exchange/storage and provider access belong to the
backend boundary, independently of Family OS client sessions.

Moving to a reachable backend will require an encrypted server-side credential/secret
store, controlled service access to account-scoped credentials, and explicit token
migration or re-consent planning. Design must account for least-privilege provider
scopes, account identity verification, revocation, rotation, encryption/key management,
and hosted or self-hosted operational responsibilities. Provider refresh credentials
are distinct from opaque ingestion continuation cursors; neither belongs in ordinary
client diagnostics, and resetting sync state must not be used as token migration.

The current local OAuth/keyring setup must not be assumed portable to a backend or
to every user's device. No credential copying, token migration, new consent flow,
server secret store, or automatic conversion is performed by this checkpoint. Those
changes require explicit future work and review, alongside backend client auth and
background execution. Protect the backend database, credentials, and backups at rest;
sharing metadata across clients does not reduce its sensitivity.

## Shared action decisions and notifications

Clients may display or submit an action confirmation; backend services enforce the
central R0–R3 policy, authorized household context, provider permissions, and shared
approval/audit state. R2 requires explicit confirmation, and R3 requires explicit
confirmation and audit. Provider grants or device-local decisions cannot bypass these
checks. Notifications are derived views of backend state, not independent approval,
task, or authorization records. Their payload/access policy is future work; this
checkpoint introduces no client auth, action executor, background worker, or push
infrastructure. See [deployment/client architecture](architecture.md#5-deployment-and-client-architecture).

## Future AI classification boundary (Phase 2K decision)

Metadata can contain private information or secrets; provider OAuth and local audit
access do not authorize transfer to an AI vendor. No external inference is enabled.
Any future adapter needs explicit household/account/field/purpose consent, approved
provider/region/retention terms, safe logging, budget controls and revocation handling
before dispatch. Local models also need artifact/license checks and telemetry/egress
containment. No content access or automatic tasks/canonical records are authorized.
See [Phase 2K exact projections, threat model and decision gates](phase-2k-review.md).

## G2a internal authorization: durable data, untrusted identity boundary

Current household membership, source read scopes and separate publication grants now
have a transactional SQL foundation, with exact actor/recipient audit and no history-wins
grant resolution. This is **not a secure multi-user service**: identity/control capabilities
are explicitly declared by an isolated fictional test harness. Never expose those methods
to clients or treat local OS access/provider OAuth as login. G2b must establish identity,
sessions, MFA/recovery, management authority, protected audit and service authorization.

The [G2a contract](v0-1-durable-household-authorization.md) specifies tested SQLite/PostgreSQL
lock ordering, stale/replay/revoke handling, field scopes and the remaining read/disclosure
race. Already-returned snapshots are not authorization leases; no client cache or network
service is implemented. Real migration needs approved targets, backup/restore, privileged
operator and rollback planning; downgrade drops authorization audit/grants. Existing native
keyrings and provider scopes remain unchanged. No real source or AI access is enabled.

## G2b1 offline identity boundary

The [offline OIDC seam](v0-1-verified-identity-boundary.md) checks exact issuer/audience,
RS256/static trusted keys, bounded validity and a request-bound one-use nonce. It maps
issuer/subject to an independently provisioned existing Person, never email/name/source
ownership. Verified identity is not membership, source sharing, write/reviewer consent
or management authority. No sessions, real enrollment, public endpoint or G2a harness
handoff exist. Tokens/extra claims are neither logged nor persisted. G2b2 must establish
verified OIDC flow, sessions/MFA/recovery, independent current capabilities and safe
revocation/disclosure ordering before any multi-user exposure.

## G2b2 durable internal sessions

The [session contract](v0-1-session-service-boundary.md) uses 256-bit opaque random
bearers with stored SHA-256 verifiers, current binding/member epochs and persistent
expiry/revocation. Each read resolves authoritative G2a rights under the same DB lock.
Sessions confer no management, reviewer or provider-write consent. Generic commit errors
remain UNKNOWN with read-only exact-request verification; secrets are never recovered
from the ledger. An identical stolen bearer is usable: device binding is not implemented.
No public login/API exists; OIDC flow, MFA/recovery, cookie/CSRF/TLS and end-to-end
revocation/disclosure gates still require review. No real household access is enabled.

## G3a internal fictional OIDC flow

[Code-flow conformance](v0-1-oidc-login-foundation.md) now binds single-use random
state/nonce/PKCE to exact trusted fictional configuration and code exchange before
same-verifier proof/session issuance. No arbitrary client token completes login, and
no email/name/role claim grants household/source/action authority. Generic errors,
strict bounded envelopes and unchanged session UNKNOWN semantics protect secrets.
Attempt ownership is single-process only; real original-browser binding, distributed
storage, trusted discovery/key rotation, MFA/recovery, cookies/CSRF/TLS and disclosure
remain mandatory gates. No real login, IDP call, provider scope or H1 change is enabled.

## G3b fictional authenticated read transport

The [in-process API contract](v0-1-fictional-read-api.md) checks G2b2 opaque sessions
and current G2a grants, with strict bounded requests, explicit JSON fields, content-free
errors and no-store responses. No caller-selected identity/household or ID token confers
authority. Dispatch reauthorizes an unevaluated request; no old private projection is
cached. The final read-to-send race remains an explicit production gate. This is not
approved network exposure or real login; no listener, browser cookies, providers or
real data exist. UNKNOWN issuance needs fresh independent identity outcome verification,
never blind retry or bearer recovery. Existing R0–R3 and disabled Alternative B remain.

## H2 fictional offline integration exception

[H2](v0-1-offline-backend-workbench.md) exports only newly authored fictional G3b fields
after actual session/current-grant checks. Keys, assertions, bearers and temporary DB
state never enter assets. Its two-adult static files are historical demonstrations,
not protected client caches: anyone controlling them can inspect both snapshots.
Never substitute real data or assume member switching enforces privacy. Existing
G3b no-cache/disclosure production gates, R0–R3 and disabled Alternative B are unchanged.

## T1 internal fictional task-domain boundary

[T1](v0-1-durable-household-tasks.md) requires current session/binding/membership
and specific current operation rights inside the existing household transaction.
Proposal observation, security, private review, task publication, task read/edit
and history permissions remain separate. Neither login nor source ownership grants
them. Unsafe/unknown evidence cannot be accepted, review cannot create a task, and
completion cannot execute or claim an external action. Neutral task projections
never read source/proposal provenance or emit hidden-source freshness warnings.
Task and source revocation are independent; known revoked access wins over replay.
Ambiguous commit outcomes remain UNKNOWN until exact same-primary ledger verification
establishes an outcome. All provisioning is trusted fictional test setup; no new
production grant management, client routes, real data, AI or provider traffic exists.
Database ordering does not solve response-dispatch/cache revocation. Deployment,
retention/backup and authenticated producer/privacy decisions require separate review.

## I2 limited loopback browser exception

[I2](stage-i2-local-session-boundary.md) authorizes only a disposable fictional
session lab, not production G3b hosting or real login. Fixed loopback Host, exact
Origin/Fetch Metadata/custom-header checks, no CORS, static allowlists and HttpOnly
Secure Strict cookies protect this narrow browser test. Terminal approval is trusted
fictional provisioning, never authentication against hostile local callers. HTTP
loopback Secure-cookie support is browser-specific and does not supply TLS; cookies
are not port-scoped, so no untrusted local services may share this test environment.
No fallback to weaker cookies is permitted. Existing session UNKNOWN, membership/
binding checks and all operation permissions remain unchanged. No real data, tokens
from providers, private cache or task authority is exposed. Windows verification,
real OIDC/MFA, HTTPS, secure deployment and final response/revocation remain gates.

## I3 fictional task-read boundary

The [I3 read-only connection](stage-i3-readonly-task-workbench.md) adds only a current
Cookie-to-T1 Tasks GET over the approved local experiment. T1 rechecks current session,
binding/member epochs and independent task grants before SQL counts/filters/pages.
Neutral fields omit private provenance and grant metadata; source changes cannot
disclose private evidence through shared tasks. The browser has no fixture task model,
no task mutations, no fallback data and no reusable authorization lease. GET requires
same-origin Fetch Metadata and a non-safelisted header; optional Origin must match.
All I2 loopback, port-unscoped Cookie, trusted-terminal and production-auth restrictions
remain. Tests use owned fictional stores only; no real household/provider/model access.

## I4a fictional acceptance exception

[I4a](stage-i4a-safe-pending-acceptance.md) alone permits explicitly confirmed internal
T1 acceptance in the owned disposable lab. Same-origin bounded POST checks precede
current Cookie/session authorization; evidence, rights and approved recipient-plan
revisions remain server-held and are revalidated by T1. A receipt is neither identity
nor authority. Unknown or lost responses never trigger another apply: read-only
verification checks the exact protected ledger with current rights. Recovery cannot
bypass revoked access, recover a lost session or authorize provider operations.
Preview/Cancel do not save decisions. No weaker cookies, real accounts, extra OAuth,
private client cache or standing consent is introduced; I2 port/TLS and end-to-end
response/revocation limitations remain. Default I2/I3 still reject acceptance routes.

## I4b fictional task-edit exception

[I4b](stage-i4b-safe-task-editing.md) alone enables confirmed assignment and tracking
status changes using existing T1 EDIT/current task grants. Candidate permissions and
exact command/recipient revisions remain server-held; assignment cannot expand grants.
Acceptance/edit receipts are operation-tagged, exact-session-bound and coordinated
under one unresolved-write gate. Known resolved history never reimposes old private
source access on independently authorized task edits; historical results still require
fresh authority. Unknown writes only reconcile, sealing late execution before proving
absence. I2 transport/Cookie limits and all production gates remain; no real data,
provider mutation, personal archive or standing consent is authorized.

## I5 fictional producer boundary

[I5](stage-i5-information-to-pending.md) accepts no private metadata or model output;
its only launcher owns a disposable fictional database and finite terminal experiments.
Stage A's simulated Access/acceptance never becomes service identity or authorization.
Independent preapproval pins source/record/read/review/publish/task recipients; current
SessionService/T1 checks still govern every browser read and human acceptance. No
browser processing/grant endpoint or provider operation is added. Producer UNKNOWN
fences processing and requires exact fresh verification; its in-process fence is not
claimed as durable production delivery. Unresolved labs must be stopped rather than
restarted/rebased against the same DB. Original Cookie/response-revocation limits and
all real-data/model/provider restrictions remain.

## I6 fictional explanation boundary

[I6](stage-i6-authorized-pending-explanations.md) reads current T1 session/source/Pending
rights before any ledger lookup, and checks exact current generation/fingerprint/definition.
Only finite business reason codes and authorized T1 fields reach the browser; private safety
is omitted without security scope and cannot change business validation. Blocked I5 inputs
remain unavailable explanations, never restored clearance. Shared Task reads never join this
projection or acquire source evidence. Dialog/request/session epochs reject known stale
responses; failures clear old details. No private persistent client cache, new grants, producer
route, model/provider access or production authentication is enabled. Existing polling and
response-dispatch revocation limits, Cookie constraints and human-confirmation gates remain.

## I7 fictional personal-handling boundary

[I7](stage-i7-pending-review-workflow.md) exposes only existing T1 own REVIEW/DEFER/
NEEDS_INFORMATION through the same exact-session, operation-tagged receipt fence as
Accept/Edit. Source/Pending read and independent review rights are rechecked before
preparation/apply; exact evidence and CAS remain authoritative. Personal flags never
grant acceptance, clear risk or enter shared Task history. Filters/counts operate on
the current authorized own-state query; no peer history or hidden-source projection
is added. UNKNOWN permits only exact original-request verification, not blind retry.
Default launchers/production paths remain unchanged. Original loopback, polling,
response/revocation and trusted-fiction limitations remain; no real data/model/provider
access, new grants, global rejection, archive or real-world operation is enabled.

## I8 fictional personal handling

[I8](stage-i8-personal-not-applicable-resume.md) reasons are finite private actor judgments, never facts disproving an obligation or safety clearance. They never enter shared Task fields/history. New-operation source grant epochs prevent revoke/regrant replay of unexecuted previews; historical committed requests remain current-access checked. SQLite DDL/version atomicity is tested with injected interruptions; no runtime household database migration or production enablement is authorized.
