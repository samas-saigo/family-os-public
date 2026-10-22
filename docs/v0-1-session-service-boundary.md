# Family OS / Stage G2b2 — durable sessions and authorized reads

## Implemented internal vertical slice

G2b2 follows G2b1 PR #75, merged at `bdfc014055373bdc3cdb132344fabddb8a7cccdb`.
A verifier-issued **fictional** identity now establishes a durable session over the
existing Person/binding/membership tables. Each session-bound call rechecks current
identity and membership, then projects independently granted source/security reads
and published fictional fields using **the same G2a authorization code**.

This is an internal database-backed slice, not production login or a multi-user app.
`SessionService(explicit_engine, verifier, FixtureRepository, synthetic_only=True)`
requires exact opt-in. There is no runtime database discovery, CLI, HTTP listener,
provider data repository, management capability provisioning or UI. Tests use newly
invented Marlin/Finch persons/sources and generated fictional signed assertions in
isolated temporary SQLite files/PostgreSQL schemas. No real data, private labels,
frozen Development/Holdout, IDP/provider/model call or OAuth change occurs.

References: [G2b1 verification](v0-1-verified-identity-boundary.md),
[G2a transactions/rights](v0-1-durable-household-authorization.md),
[G1 field-level scopes](v0-1-household-read-service.md),
[Stage D unified household](v0-1-household-first-authorization.md),
[E1 action policy](v0-1-security-action-authorization.md),
[E2 independent reviewer](v0-1-synthetic-security-lifecycle.md),
[architecture](architecture.md), [security](security.md), [data model](data-model.md),
[roadmap](roadmap.md).

## Identity, session and permissions remain independent

Two peer adults use one authoritative household database and independently issued
sessions. Equal source/publication grants yield the same household projection. A
person is not a source account; session issuance cannot enroll a person, link an
identity, grant mailbox access, publish a task or create a superuser. Membership,
binding and source/publication epochs are checked independently. Source sharing is
not operation consent or security-reviewer authority. R0–R3 and disabled/unapproved
Alternative B standing consent remain unchanged. No mailbox writes, actual tasks,
reconciliation reviewer capability, background execution or notifications are enabled.

The offline G2b1 verifier still does **not** complete OIDC login. Establishment and
self-session revocation from its issued proofs remain trusted, synthetic-only internal
operations. A client-supplied Person, email, role or household cannot establish authority.
The requested household is checked against the exact trusted binding and bearer row.
No session-derived identity is passed to `harness_context()`; no management capability
is inferred or created. Old G2a harness methods remain test setup, not client entrypoints.

## Persistence and secret boundary

Migration `c35b79a12e04` adds two empty tables after `8a421d6c09be`:

| Table | Persisted contract |
| --- | --- |
| household_session | Independent UUID ID, exact household/Person/issuer/subject association, unique SHA-256 bearer verifier, pinned binding/member epochs, revision, revoked flag, server timestamps for creation/activity/absolute/idle expiry |
| session_audit | Append-only service events: actual actor, affected member, resulting/affected session and prior session on rotation, scoped request ID, full intent hash, event, historical committed outcome and server time |

A composite FK binds session to the exact existing external identity/person/household,
backed by a new unique binding-scope index. A separate membership FK preserves tenancy.
Audit FKs bind current/prior sessions to the affected household/person. Session hash and
household/actor/request keys are unique; revisions/time ordering are constrained.
There is no competing household/person/task registry. No cascade deletes remove history.

`secrets.token_urlsafe(32)` produces 256-bit random opaque bearer values; SHA-256 is a
one-way verifier for that high-entropy secret, not a password KDF or custom encryption.
No plaintext bearer, ID token, extra assertion claims, provider tokens, titles, bodies,
financial fields or source metadata enter these tables. A bearer is returned **only
after a successful issuance/rotation commit**, in a repr-redacted result field. Do not
log/serialize that field indiscriminately. Projections, protected audit and errors never
contain it. Stored hashes cannot be presented as bearers (format/hash checks differ).

An **identical copy of a valid bearer is necessarily usable as that bearer**. This
slice rejects forged/copy-constructed identity contexts, changed/malformed/random
bearers and household substitution, not secret theft. It does not claim device binding
or clone detection. Cross-instance bearer use is intentional. Secure transport/storage,
MFA, fixation/replay defenses and optional proof-of-possession remain production gates.
G2b1's 32-handle bound is a disposable process verifier limit, **not durable session
capacity**. Session count/admission rate controls require deployment review.

## Lifecycle and safe results

The server clock defaults to epoch time; injection is trusted test configuration only.
No caller timestamp/lifetime is accepted. Clock values are finite/bounded; backward
movement relative to persisted last activity rejects. Absolute lifetime is 24 hours,
idle lifetime 30 minutes: conservative **internal test defaults, not approved production
session policy**. At expiry equality, access denies. Activity updates idle expiry only
up to the absolute deadline. Sessions are invalidated by any binding/member revision
change, not only revoked state. Re-enrollment cannot revive them or epoch-pinned grants.

| Internal method | Current checks and effects |
| --- | --- |
| establish(proof, household, request_id) | Same configured verifier's current proof; exact current allowed binding/member under lock; new random secret/ID; pins epochs; append establish event atomically; no enrollment/grants |
| resolve(bearer, household) | Hash lookup, exact binding/current membership/epochs/expiry/revoked checks; touch activity via revision CAS; returns safe own IDs/revisions/deadlines only |
| read(bearer, household, limit, offset, topic) | Same checks and transaction; shared G2a authorized projection; activity CAS; returns source/publication/security lanes only after transaction exit succeeds |
| logout / rotate(..., expected_revision, request_id) | Self bearer plus fresh binding/member/epochs/time; exact session revision CAS; logout revokes only that session; rotation atomically revokes old and inserts new, retaining original absolute deadline; audit ties both IDs |
| revoke_all(proof, household, request_id) | Independently verified current **self** identity; revoke all that member's sessions in this household, across bindings; no caller-selected other member or management role; append member-scoped event |
| history(bearer, household, limit) | Fresh valid session; only that member's protected audit, bounded 1–100; no bearer/hash/identity assertion/intent payload returned |
| verify_outcome(proof, household, request_id, intent_hash) | Read-only exact-request proof on a new physical connection to the same primary; fresh independently verified self identity; no bearer recovery, mutation retry, rebase or new ID |

Revoking all sessions does not indefinitely ban future issuance after a separately
verified identity. Concurrent issuance/rotation and revoke-all follow household lock
order: issuance before committed revoke-all is revoked; deliberate issuance after it
is a new session. It never revives an old bearer. Individual logout leaves peer sessions
and unrelated grants intact. No session action modifies permissions or source history.

Historical exact request replay returns REPLAY/IDs, **never the plaintext replacement
secret** or fresh session validity. Changed intent under the same actor/request yields
CONFLICT. No replay bypasses session revocation or expiry: logout/rotation invalidate
that bearer for every operation, including historical replay. An independently verified
current self identity may instead verify the exact historical request via verify_outcome;
this never revives a session or returns its secret. Failed expected revision
is STALE, without partial state. Replays do not append duplicate audit records.

Result semantics:

- COMMITTED means the transaction exit succeeded or its exact immutable ledger was
  independently proven. It is historical outcome, not current permission/session state.
- ACCESS_UNAVAILABLE means the invocation cannot authenticate/authorize, with no claim
  about a prior request's historical outcome. An invalidated bearer cannot verify an
  earlier UNKNOWN action; fresh independent identity is required.
- NOT_APPLIED means verified ledger absence after same-primary
  transaction ordering. STALE is verified CAS rejection; CONFLICT is a changed exact intent.
- Generic database/commit/connection-exit errors yield **UNKNOWN**, never guessed success
  or definite non-application. SessionError after a possible mutation/commit also stays
  UNKNOWN. Read failures return only generic access-unavailable and no built projection.

After UNKNOWN, retain the original request/intent hash and verify its outcome; do not
blindly replay/rebase under a new request. Matching committed audit proves the atomic
session change occurred; absence proves non-application only within the same-primary,
append-only audited protocol. Unavailable proof, invalid current identity, corrupted or
unestablished evidence stays UNKNOWN. Verification uses recreated trusted pool/config,
not a replica/new supplied URL or failed connection. It is one read attempt, not retry.

If issuance/rotation committed but its secret response was lost, no API retrieves the
secret. An independently verified member can explicitly revoke all own sessions to
invalidate the orphan, then deliberately establish a fresh session. This is an internal
recovery option, not automatic client retry or a production account-recovery policy.
Synthetic faults invoke real database commit then raise, modeling acknowledgment loss;
they do not prove network partitions, primary failover or storage-loss behavior.

## One shared permission/read mechanism

G2a's existing transaction helper and projection body are extracted **in that same
module**, not cloned into another policy engine. G2a still checks its issued harness
actor; G2b2 instead validates the durable bearer/binding/member under the same lock.
Only then call the shared projection with authoritative Person/member revision.
The helper is internal and not an authentication entrypoint accepting arbitrary IDs.

Current source grants and independently approved publication-recipient grants are
queried from SQL. Filter effective permissions before inspecting fictional observations,
field minimization, consistency, counts, dedupe, search or pages. Observation-only fields
exclude Safety; security scope authorizes generation/Topic/Safety. Hidden populations
cannot change counts/order/errors; authorized contradictions reject conservatively.
Identity is household/source/provider object; generation is provenance, actors are not
object multipliers. Different mailboxes remain distinct; no title-based cross-source merge.

A private mailbox is not accessible merely because a session is valid. Source revocation
may leave independently published neutral fields visible with no source IDs, links,
contributor count or new private provenance. Publication revocation removes those fields
independently. They are fixed fictional permission resources, not created product tasks.
The existing G2a limit 1–20, offset 0–128, visible unique cap 128 and fixed Topic filter
remain. Fixture traversal is trusted finite setup, not production repository/DoS defense.

## Ordering, concurrency and disclosure limitations

All participating read, session and G2a grant operations use:

1. SQLite BEGIN IMMEDIATE writer reservation or PostgreSQL READ COMMITTED household
   SELECT FOR UPDATE (other isolation/autocommit rejects).
2. Current session/exact binding/membership validation.
3. Current source/publication rights and authorized projection, or session revision CAS.
4. Activity/session mutation and atomic audit where applicable.
5. Commit/exit before returning secret/projection; error means no returned projection.

No in-process authorization mutex substitutes for DB ordering. PostgreSQL serializes
per household, SQLite globally reserves the writer even for reads. Activity updates
advance revision on every successful resolve/read/history; concurrent accesses serialize,
never move activity backward. A rotation based on an older observed revision can reject;
the internal caller must make deliberate current-revision intent, not automatic rebase.
Provider actions and security-result reconciliation are not part of this lock contract.

Tests hold a real read lock while logout/member/binding/source revocation attempts the
same lock, then prove subsequent reads reflect the committed change. Concurrent rotation
yields one replacement only; exact duplicate establishment yields one mutation/replay.
Independent service instances share revocation from SQL. These guarantees assume **all
relevant writers follow this ordering**, including future binding management. Privileged
non-participating SQL, replicas, failover and hostile DB owners are outside the proof.

A read already built/committed before later revocation may be delivered afterward; its
plain Python result cannot be recalled. **Database ordering is not end-to-end disclosure
linearizability.** There are no reusable client caches, prepared private snapshots,
notifications or delayed renderers. Every new read rechecks permissions. Future API
response dispatch, cache invalidation and session/source revoke races require review.
Connection/lock deadlines inherit explicit engine configuration; public transport deadlines,
rate limits, indexed domain repositories and operational denial-of-service gates are future.

## Migration and deployment responsibilities

Upgrade creates empty session/audit tables and a binding uniqueness index; no identities,
memberships, source grants, data, cursors, provider tokens or audit are rewritten/enrolled.
Downgrade to 8a421d6c09be removes **sessions and their audit**, leaving earlier bindings,
authorization and provenance unchanged. Re-upgrade has no sessions: fail-closed. That is
not a production rollback/retention plan. Both engines run metadata agreement and round
trips/history preservation only in disposable test stores. No user database was migrated.

Before real use: approve target and migration, encrypted backups and restore rehearsal,
least-privilege roles, protected/tamper-evident audit and operational rollback. Session
hashes, identities and audit require backup access controls and approved retention/deletion.
Audit FKs deliberately prevent deleting referenced binding/person/session provenance;
coordinated expiry/purge/deletion rights and minimum protected recovery history must be
approved before operators delete rows. No indefinite retention is presumed or purge job added.
Secrets rotate through explicit fresh issuance/atomic invalidation, never reusing old
bearers; no plaintext secret recovery from backups. Provider keyrings stay unchanged.

## Remaining real-login gates and next step

No vendor/framework is selected. Prefer an approved maintained OIDC provider and relying
party library; compare managed operational simplicity versus self-hosted control/patching,
phishing-resistant MFA/passkeys, subject stability, recovery, availability and privacy.
Next narrow phase: approve and implement verified authorization-code + PKCE/state and
protected callback/nonce/token provenance, then authenticated **read-only** service
entrypoints with complete adversarial authorization tests. Only after that, a minimal
web workbench over authorized household projections; do not bypass gates to reach UI.

Required decisions/evidence before exposure:

- Exact OIDC provider/profile/client audience separation, maintained callback library,
  trusted discovery/key rotation/outage behavior; offline ID acceptance is not login.
- Session fixation prevention, rotation/expiry policies, cross-device sign-out, secure
  storage, replay/secret-theft treatment and step-up controls; no client-chosen session ID.
- Passkeys/phishing-resistant MFA, second-adult peer invitation, membership proof and
  lost-device/account recovery without first-enrollee superuser or email auto-linking.
- TLS, Secure/HttpOnly/SameSite cookies, CSRF, origin/CORS, protected callbacks, resource
  limits and deployment hardening before any listener; no browser transport implemented.
- Independently authoritative management/source-sharing/reviewer/action consent, actual
  actor audit, current R0–R3 and emergency stop; Alternative B remains unapproved.
- Response dispatch/revoke/cache ordering, authoritative DB roles/backups and protected
  audit, retention/deletion, hosting responsibilities and operational reconciliation.

G2a's existing CONFLICT historically covers **both** verified no-effect ledger absence
and changed-intent request conflict; its enum/semantics are preserved. Do not interpret
all such results as an intention collision. G2b2 distinguishes NOT_APPLIED absence from
CONFLICT changed intent. G2a/G2b1/G2b2 explicit CONTRACT_VERSION constants name reviewed
source definitions only; they do not imply separately deployed historical versions or
permit negotiation to an older policy. Real authentication/authorization must not use
harness capability provisioning. Stage F real-mail pilot remains unauthorized.

## Validation and independent review

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_household_sessions.py tests/test_household_authorization.py tests/test_verified_identity.py tests/test_migrations.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Actual head-specific counts/results belong in the PR. Tests cover equal peers/private
sources/publication independence, secret minimization, signature-proof origin, current
epochs/expiry, rotation/replay, cross-instance and real thread interleavings, acknowledgment
loss/fresh outcome proof, rollback and migration agreement/history. No real household or
external transport is used. Existing providers/classification/security research are intact.

Review questions:

1. Does the integrated slice establish sessions only from verified current bindings,
   without manufacturing G2a contexts or independently granting permission?
2. Do all source/security/publication fields/counts/errors use the same current G2a
   authorization-first projection, including field-level Safety privacy?
3. Are self-session capabilities, exact replay/CAS/rotation and UNKNOWN/fresh proof
   semantics safe without leaking/recovering a bearer or blindly retrying?
4. Are DB ordering and real-login/secret-theft/disclosure limitations explicit enough
   before a network service or first workbench is proposed?

Keep OPEN and UNMERGED for ChatGPT, independent Muse security review and human merge.
