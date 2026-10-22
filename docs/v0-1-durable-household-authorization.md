# Family OS v0.1 / Stage G2a — durable internal authorization foundation

## Implemented boundary

G2a follows merged G1 PR #73 at main `b06ede91804a3f96825d65d863bfe74c05c1cb7d`.
It adds database-backed **membership and read/publication permissions**, not a secure
multi-user application. The private internal service uses an explicitly supplied
SQLAlchemy engine and newly invented fictional Copper booking / Willow school fixture
repository. It never discovers a runtime database or reads production provider records.
Tests use the established disposable SQLite files / isolated PostgreSQL schemas only.

References: [architecture](architecture.md#5-deployment-and-client-architecture),
[security](security.md#provider-oauth-and-family-os-client-access),
[data model](data-model.md), [Stage D](v0-1-household-first-authorization.md),
[E1](v0-1-security-action-authorization.md), [E2](v0-1-synthetic-security-lifecycle.md),
[G1 field scopes](v0-1-household-read-service.md) and [roadmap](roadmap.md).

One existing Household/Person/SourceAccount registry remains authoritative. A person
may control several accounts or share a household-owned account. Membership neither
implies source access nor a primary/secondary spouse hierarchy. No canonical tasks,
second person registry, authentication, service entrypoint, provider access, AI/Ollama,
frozen Development/Holdout, private samples, credentials, OAuth changes, workers,
notifications or mailbox writes are implemented. Finance remains separate.

## Persistence and tenancy

Migration `4e82a1c70d39` adds only five tables after `913feab82c07`:

| Table | Current identity / purpose |
| --- | --- |
| household_membership | One `(household, person)` row: allowed/revoked and positive authoritative revision; composite FK to existing Person |
| source_read_grant | One `(household, source account, recipient)` row: state, observation/security read scopes, revision and recipient membership-revision binding; composite FKs to account and membership |
| publication_scope | Household-scoped bounded permission-resource identifier with explicit approved flag; **not** a canonical task, task engine or task creation workflow |
| publication_read_grant | One `(household, publication key, recipient)` row: state, revision and membership-revision binding; composite FKs to scope and membership |
| authorization_audit | Append-only through service: actual actor, affected recipient, exact kind/resource, request/intent identity, prior/resulting states/read scopes/membership binding, old/new revisions, committed outcome and time |

All actor/recipient/source/publication references retain household tenancy. Compound
primary keys prevent simultaneous duplicate current assertions. Revision and state
checks constrain persisted values; audit uniqueness protects scoped revision and
household/actor/request identities. Service CAS advances exactly one revision per
committed change. This is not protection against a database owner issuing arbitrary
SQL: future least-privilege roles and audit tamper protection remain deployment gates.

Only allowed/revoked are stored. Missing rows mean no established authority; no
invented transitional ALLOWED state or highest-timestamp/history-wins resolver exists.
Historical audit rows are never current grants and cannot resurrect a revoked row.
Recipient membership must currently be allowed to grant source/publication access.
Those grants pin its revision. Revocation/re-enrollment or any membership revision
change makes earlier bindings ineffective until **fresh explicit** grant changes;
new membership alone does not revive source or task visibility.

The publication resource holds no source titles, evidence, task status or extracted
content. Its approved fictional fields come from the immutable fixture repository;
G2a does not implement a publisher-verification or field-editing workflow. Scope
provisioning and initial membership bootstrap are trusted test setup only, never
migration-created membership or automatic owner rights. Real bootstrap/publication
approval requires separately reviewed G2b operations and explicit actor audit.

## Trusted identity and narrowly scoped operations

`AuthorizationService(engine, FixtureRepository(...), synthetic_only=True)` requires
exact opt-in. It has no default DATABASE_URL, CLI, HTTP route or production caller.
Fixture metadata accepts fixed Object/Topic/Safety/Step enums only, not emails, titles,
bodies, financial values, private metadata, tokens or arbitrary raw payloads.

`harness_context()` explicitly declares a fictional principal, current membership
revision and independent membership/source/publication management capabilities.
Only the same service's issued handle is accepted; copied/fabricated handles fail.
Every database operation rechecks current membership. These handles/capabilities are
**not authentication**, credentials, signed sessions or protection against hostile
Python callers. Source ownership does not establish management authority. Tests
intentionally let fictional Eli change Nova's grant with independently declared scope
and record Eli as actor, never infer Nova from source ownership. Both peers can have
separately provisioned capabilities; no household hierarchy is imposed.

Never expose harness issuance, repository injection, context fields or trusted setup
SQL to clients. Client-supplied person/household/source IDs or risk claims cannot
establish authority. G2b must replace this trust mechanism with verified server-side
identity/session and current management-rights resolution before any network service.
Current provider OAuth/native keyrings remain separate and unchanged.

- `submit(context, Change(...))` validates the fictional actor/capability and captures
  recipient membership revision. It returns **SUBMITTED, not committed**; no grant or
  audit mutation, transaction/approval lease or stored pending authorization exists.
- `commit(..., confirm=True)` rechecks actor/current membership, household and exact
  target capability. Source targets must be same-household `fixture` accounts, and
  publication targets must be existing same-household bounded scopes.
- Expected revision 0 permits a new row only when absent. A change pins both grant
  revision and submitted recipient membership revision. A changed epoch cannot receive
  an old pending expansion. Explicit confirmation is exact boolean True; Cancel adds
  no mutation or audit outcome. A deliberate new regrant needs current expected revision.
- Current row transition and audit insertion share one transaction. Uniqueness/CAS
  verified rollback cannot leave a half-grant; commit acknowledgment loss can leave
  a complete durable change whose outcome must be reconciled. An identical previously committed
  household/actor/request/full intent returns historical **REPLAY** with no write;
  changed intent conflicts. Current actor authority is checked before replay disclosure.
- Prominent results distinguish COMMITTED/REPLAY, CANCELED and **NOT_APPLIED** stale,
  conflict, rejected and unavailable conditions, plus **UNKNOWN / reconciliation
  required** when a database outcome cannot be established. A stale revoke is not reported as
  applied and is never automatically rebased. No blind retry or silent regrant occurs.
- Rejected/canceled requests produce no audit rows or partial grant. The ledger covers
  committed grant transitions; it is not a durable rejected-request/access log. Service
  has no UPDATE/DELETE audit operation. Bootstrap/test SQL is outside this actor-verified
  change path; privileged SQL protections are explicitly not claimed.
- `history()` requires current membership and exact independent management capability,
  is household/resource scoped and bounded. Source-read alone cannot inspect grant audit.
  Audit exposes authorization configuration only, never source payloads.

Reconciliation permission and mailbox operation consent are not granted or modeled by
these tables. Read/security/publication permissions never imply them. R0–R3 stays central;
Alternative B standing consent remains **disabled/unapproved**. Grant audit retains the
actual initiating actor, addressing the E2 carry-forward. Contract/source revision names
are review identities, not separately deployed historical authorization services.

## Authorization-first fixture read seam

`read()` first checks current membership under the serialization transaction, then
selects only effective current source grant IDs/scopes and independent publication
visibility from the database. It never selects raw_source_record, source_record,
source_analysis, source_sync_state, account metadata/credentials or provider mail.
Non-fixture/disabled accounts do not supply observations, even with allowed grants.

The immutable fictional repository is not a second durable authorization store. It is
an explicitly trusted fixed test data source; persisted domain record queries remain
**deferred**. Two peers and independent service instances using the same repository
observe the same current SQL authorization state, not per-owner task copies.

Source-object identity is household/source account/provider object, with provider fixed
as `fixture`; generation is snapshot provenance, **not** another object. Filter rights
before touching content or consistency/count/search/page checks. Observation scope
compares only identity/generation/Topic; private Safety differences cannot affect that
lane. Security scope explicitly authorizes generation/Topic/Safety, including Topic
filtering; contradictory permitted assertions reject before clear exclusion, without
arbitrarily clearing risk. Hidden or cross-household populations cannot affect errors,
counts, ordering or pages. Identical authorized duplicates coalesce.

Source count means unique authorized source **objects**, not account count or grant count.
Search accepts only fixed Topic; stable order uses scoped object identity. Limit 1–20,
offset 0–128 and visible unique-item cap 128 bound output. Finite trusted fixture traversal
is not constant-time or a production repository/resource-exhaustion defense. Topic filters
apply to source/security lanes; publication has no source-derived search dimension.

Publication rows contain only its independently approved fixed key/neutral Step. Source
revocation does not revoke that independent recipient grant, reread private provenance,
create tasks, or publish source counts/links/warnings. Publication revocation removes
visibility while permitted source reads remain. G2a emits no freshness warning or
revocation-timing signal; that Stage D privacy tradeoff remains unapproved.

## Transactions, revocation and verified limits

Every G2a read, change and audit inspection uses the same ordering:

1. SQLite writer reservation or PostgreSQL household row lock.
2. Current actor membership and bound authority.
3. Exact recipient/grant/resource validation and expected revisions.
4. Current read projection **or** CAS grant transition plus audit append.
5. Commit/release, or rollback on body exceptions; a commit/exit error is not proof of non-application.

SQLite uses explicit **BEGIN IMMEDIATE** before reading authorization. This reserves the
single database writer even for G2a reads; parallel households are also serialized by
SQLite. PostgreSQL supports only verified **READ COMMITTED**, with **SELECT household
FOR UPDATE** before subsequent permission queries. Other isolation levels and autocommit
fail closed. Numeric revision order is not a substitute for these locks. No process-local
mutex is used. SQLAlchemy `engine.begin()` attempts commit on successful body exit and
rollback on body exceptions. A driver/ordinary exception during commit or connection
exit can occur **after** the database durably committed; it does not establish rollback.
Tests inject failure between grant update and audit insertion and verify no partial grant,
and separately simulate loss of acknowledgment after a real disposable-database commit.

Concurrent revoke versus expansion at the same expected revision yields one commit and
one stale rejection. Exact concurrent duplicate requests yield one commit and one replay,
with one audit outcome. A bounded interleaving test holds the read transaction, observes
an overlapping writer attempting the lock and confirms the writer cannot finish until
the read releases it. That read legitimately precedes revocation; later database reads
see the committed revocation. The test runs against both engines in CI.

`prepare_read()` contains only request specification/context, **no data or authorization
lease**. Consumption always executes a fresh database read and rechecks source/task/member
revisions. A second-thread test commits revocation between preparation and consumption.

**This is transaction ordering, not end-to-end no-stale-disclosure.** A committed read
can return its already-built plain Python snapshot while a later revocation commits;
previously returned data cannot be recalled. G2a has no network serialization, delayed
renderer, notifications or reusable client cache. Such reuse is prohibited. G2b must
review authoritative disclosure/dispatch ordering and session/cache revocation before
exposure. These tests do not prove remote delivery linearizability, serializable SQL
inference, multi-process context issuance or durable authentication. SQLite busy/database
conflicts return NOT_APPLIED only when non-application is established; unresolved database
outcomes remain UNKNOWN rather than silently retry. The feature stays internal.

## Ambiguous database outcomes and exact-request reconciliation

`Outcome.UNKNOWN` is explicitly `UNKNOWN-reconciliation-required`, with no guessed
revision. A generic SQLAlchemy/driver **or ordinary Python** exception is not a definite
NOT_APPLIED. Internal pre-write authorization/validation rejection remains a denied
invocation; if mutation was attempted or transaction exit/commit started, even an internal
Failure exception requires proof rather than claiming non-application.

`reconcile_change(context, submission)` performs **read-only grant-outcome verification**,
not provider/security-result reconciliation and not a mailbox operation capability.
It requires the exact issued context/submission, current membership and independently
scoped grant-management capability before inspecting the protected request ledger.
If current access is revoked, it cannot expose the outcome and returns UNKNOWN.

The service recreates the trusted engine pool/connection creator with the same database
configuration and execution options, using a **new physical connection**, not the failed
connection, a replica, a newly supplied URL or client-selected database. Under the same
household lock/writer reservation, it inspects the unique household/actual-actor/request
row. The original transaction must release that lock before verification can proceed.

- Matching full intent fingerprint, recipient, kind/resource, expected old/new revision,
  resulting state/read scopes, membership binding and committed audit outcome establish
  **historical COMMITTED** for that exact request. The atomic audited protocol means both
  grant transition and audit became durable. Later authorized changes may have occurred:
  historical COMMITTED does not mean the grant is currently allowed or still revoked.
- A different intent under the unique request key establishes a genuine changed-intent
  conflict. Definitive ledger absence after fresh primary/lock ordering establishes
  non-application **only under this same-database, atomic, append-only protocol**.
- Unavailable connection, unsupported isolation, failed proof query/transaction exit,
  lost current actor access, inconsistent matching audit, or any unestablished outcome
  yields UNKNOWN. No exception detail, SQL parameter, URL or private error text is returned
  or logged. Cleanup errors do not overwrite established outcomes.

Verification is one read attempt, not a mutation retry. It never creates a new request,
rebases expected revisions, changes a grant or appends an audit. After UNKNOWN, retain the
**original exact** request/submission for later verification; do not assume revoke succeeded
or failed, or blindly submit a new key/expansion. Normal exact committed-request replay
remains REPLAY with no second mutation/audit. Definitive NOT_APPLIED feedback requires
known rejection or verified non-application, not merely the presence of an exception.

Synthetic faults wrap the driver's commit call: one invokes the actual commit, then raises
SQLAlchemy, runtime or internal errors before the caller receives acknowledgment; another
raises before the real commit. Tests observe a distinct physical verification connection,
accurate revocation/expansion feedback, unavailable proof preserving UNKNOWN, later exact
verification, no duplicate effect, and before-update/before-audit rollback. This models
client acknowledgment loss; it is **not proof of real network partition/failover behavior**.

Trust in the authoritative primary, atomic grant/audit protocol and protected ledger is
required. Privileged SQL deletion/corruption, replica lag, database failover/loss, connection
routing and end-to-end disclosure remain deployment gates. Connection/lock deadlines are
inherited from the supplied trusted engine; public-service bounded deadline and operational
reconciliation procedures still need G2b review. No real household database is accessed.

## Migrations and operator responsibilities

Upgrade adds empty authorization tables only. It enrolls nobody, grants nothing and
rewrites no existing identity/source/raw/analysis/fact/cursor history. Migration tests
verify Alembic metadata agreement, upgrade/downgrade/upgrade and original history
preservation on both supported test engines. Downgrade to `913feab82c07` removes **all
G2a grants and authorization audit**, leaving old provenance intact; re-upgrade is empty
and fail-closed. That is destructive to authorization history, not an operational rollback
plan for future deployment. Never run test teardown/downgrade against a real database.

No real household database was used or migrated here. Before any actual migration:
approve the target, back up database/authorization/audit and credentials separately,
verify restore in isolation, review privileges and schema/lock behavior, schedule any
maintenance, and define audited enrollment/import and rollback/recovery responsibilities.
Do not reset ingestion cursors, migrate credentials or infer grants from ownership.

## G2b and production gates

Still required: real client identity verification; session expiry/logout/revocation;
phishing-resistant MFA; invitation, membership proof and recovery for two peer adults;
separately authorized source-control and publication authority; explicit sharing terms
and Cancel; current consent/reviewer management; backend PostgreSQL access roles and
protected audit; encrypted backend credentials and separately approved migration or
re-consent; authenticated entrypoint authorization; transport/disclosure races and
cache invalidation; operational backup, restore, incident and hosting responsibilities.
Framework, identity provider and hosting choices remain undecided. No public API,
provider-record read, background sync, real task engine or real-mail pilot is authorized
by G2a tests. Real household data must not enter any AI, local or cloud.

## Validation and review

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_household_authorization.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_household_authorization.py tests/test_migrations.py
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Full SQLite and PostgreSQL 16 CI uses existing disposable database conventions. Exact
head/test/job results belong in the PR; synthetic tests are not a production-security claim.
Review: are all FK/current-row/CAS/audit invariants sound? Can a stale recipient epoch or
old allowed audit entry regain permission? Are field scopes and independent publication
kept separate? Do transaction-order tests and snapshot-disclosure limitations accurately
bound the guarantees? Are trusted-harness, bootstrap and G2b deployment gates unmistakable?

Keep OPEN/UNMERGED for ChatGPT review, independent Muse security review and final human
merge. No auto-merge, production authentication or real household/provider enablement.

### G2b2 integration note

[Durable sessions](v0-1-session-service-boundary.md) now reuse this module's internal
transaction ordering and read projection; the G2a harness/grant mutation semantics remain
unchanged. CONTRACT_VERSION identifies this source contract, not a historical deployment.
CONFLICT still distinguishes neither verified ledger absence nor changed-intent internally;
read the reconciliation conditions above before interpreting it as an intent collision.
