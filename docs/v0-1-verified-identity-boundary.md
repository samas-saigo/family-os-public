# Family OS / Stage G2b1 — verified identity and trusted boundary

## Status and design decision

G2b1 follows G2a PR #74, merged at `6296d30333a1121cfb47bfaf2c5ee19713bd238c`.
It implements an **offline cryptographic verification seam and exact Person binding**,
not login, a secure multi-user application, a session or authorized provider access.
Only newly generated fictional keys/assertions and disposable test databases are used.
No real accounts, household data, frozen datasets, IDP/provider requests, AI/model calls,
listener, API, UI, task, worker, notification, credential movement or mailbox write exists.
The existing ingestion/classifier/G2a semantics and centralized R0–R3 policy are unchanged.
Alternative B standing consent remains disabled and unapproved.

References: [Stage D](v0-1-household-first-authorization.md),
[E1](v0-1-security-action-authorization.md), [E2](v0-1-synthetic-security-lifecycle.md),
[G1](v0-1-household-read-service.md), [G2a](v0-1-durable-household-authorization.md),
[architecture](architecture.md), [security](security.md), [data model](data-model.md)
and [roadmap](roadmap.md).

Standards-based OpenID Connect (OIDC) is preferred for future client authentication.
A reviewed managed OIDC provider can reduce patching/recovery operational burden;
a maintained self-hosted provider such as Keycloak offers more operator control but
requires secure patching, backups, key custody and recovery administration. Selection
must compare phishing-resistant MFA/passkeys, subject stability, account recovery,
privacy/retention, availability, regional hosting, cost and independent security review.
No provider or hosting vendor is selected. Authlib is a maintained option for a future
OIDC authorization-code client and discovery integration; it is not installed here.

For the narrow offline ID-token signature/claim seam, PyJWT with its cryptography backend
is already pinned in the development lock. An explicit optional `identity` dependency
makes this dependency intentional rather than relying on MSAL transitively. PyJWT owns
compact JWT parsing, signature algorithms and standard claim validation; cryptography
loads and validates RSA public keys. There is no custom signature verifier or password
implementation. This adapter is **not a complete OIDC relying party**. Actual code flow,
PKCE/state, trusted discovery, token endpoint verification and sessions are G2b2 gates.

## Independent identities and authorities

| Boundary | Proof/meaning | Does not establish |
| --- | --- | --- |
| Verified external issuer/subject | A signature-valid supported ID assertion under trusted configuration and a request-bound nonce | Person, household enrollment, email ownership, mailbox access or permissions |
| Exact external binding | Separately provisioned `(issuer, subject)` maps to one existing Person and its household | Active membership, automatic linking or source ownership |
| Current G2a membership | Existing current allowed household/member row and revision | Source reads, task publication, management, reviewer or operation authority |
| Source/publication rights | Independently authorized, current revision-bound G2a grants | Provider write consent or security reconciliation |
| Management/reviewer/operation | Future independently established exact capability and central policy | Universal household superuser or rights inferred from authentication |

Two adults are peers in **one** household state. First enrollment never makes a permanent
superuser; being authenticated or a household member cannot infer management authority.
Shared source reads and published task fields remain independently revocable; a person
can have several source accounts and, eventually, separately authorized external bindings.
Email, display name, a client-selected Person/household, source owner or OAuth identity
cannot substitute for the exact issuer/subject binding. Provider OAuth remains separate.

## Supported offline ID-token profile

`_verified_identity.OfflineIdentityVerifier` takes only trusted exact issuer, client
identifier/audience and **static public keys**. There is no default configuration,
environment lookup, token-selected issuer, discovery or JWKS network fetch.

| Rule | Implemented fail-closed contract |
| --- | --- |
| Issuer | Exact case-sensitive configured HTTPS issuer, no user info, query or fragment; no normalization/trailing-slash aliases |
| Audience/intended use | Exact single string client audience; arrays/multi-audience unsupported; optional azp must equal that audience |
| Algorithms/keys | RS256 only; 1–4 explicitly supplied kid/RSA public-key pairs, RSA 2048–4096 bits; unknown kid or unsupported algorithm rejects |
| JOSE header | Exactly alg, typ=JWT and kid; duplicate JSON names, jku/jwk/x5u/crit and other extras reject; no token-directed keys or URLs |
| Claims | Required iss/sub/aud/iat/nbf/exp/nonce; JSON object without duplicate names or non-finite constants; subject is exact bounded printable ASCII (1–255), no email/name linking |
| Time | PyJWT verifies exp/nbf/iat with zero leeway; strict integer timestamps, iat ≤ nbf ≤ now < exp, age and total lifetime at most 300 seconds |
| Request binding | Cryptographically random nonce from an internally issued Challenge; exact same-verifier receipt, unexpired ≤300 seconds; successful verification consumes it atomically |
| Bounds/errors | ASCII compact token ≤16 KiB, ≤32 live challenge/proof handles; generic Identity verification unavailable only; no token, provider/driver detail or raw claims logged/returned |

OIDC permits optional nbf and longer lifetimes; those profiles are deliberately unsupported
here. typ=JWT is an ID-token profile convention, **not by itself a universal ID/access-token
discriminator**. A future relying party must obtain the ID token from its verified OIDC
flow, with a client-specific audience and bound nonce; never accept arbitrary bearer access
tokens as login. Offline tests cannot prove issuer issuance policy or token provenance.
Extra signed profile claims (email/name/roles/household) have no authority and are discarded.
No external token or full assertion is retained in the verified value or database.

The adapter uses PyJWT payload/header extension hooks solely to reject ambiguous JSON
names/constants; library compact/base64 parsing and signature validation remain authoritative.
These hooks are covered by regression tests and require review when upgrading PyJWT.
Clock correctness is a deployment responsibility; no caller-supplied clock, audience,
expected nonce, issuer, key URL or algorithm can change request validation.

`VerifiedIdentity` is a frozen, redacted internal value holding only issuer/subject/expiry.
Binding resolution accepts only the **exact proof object issued by that configured
verifier**, still unexpired. Copied, constructed or other-verifier values reject. Proof
handles and nonce consumption are bounded single-process seam controls, not signed sessions,
durable replay storage, distributed login or protection against hostile in-process Python.
No handles can be accepted through a future client API. A process restart loses them.

Trusted key rotation requires an independently authenticated operator/configuration process:
construct a new verifier with reviewed current public keys, optionally an explicitly bounded
overlap. Removed/unknown keys reject; old proof/challenge handles do not transfer to the new
verifier. There is no automatic refresh or fallback to stale keys. Production discovery,
rotation authentication, compromise invalidation and outage/cache limits require G2b2.

## Exact binding persistence and deliberately isolated handoff

Migration `8a421d6c09be` adds **one empty table** after `4e82a1c70d39`:
`external_identity_binding(issuer, subject, household_id, person_id, state, revision)`.
Global composite primary key `(issuer, subject)` prevents mapping one declared identity
to several people/households. Household/person composite FK reuses the existing Person
registry and enforces tenancy; state is allowed/revoked and revision positive integral.
An index supports household/person binding lookup. Multiple separately provisioned identities
may reference one Person; there is no account-linking/enrollment/update service in this PR.
Provisioning in tests is privileged fictional setup SQL, **not an approved production linking
flow**. Real enrollment/linking/revocation must verify existing identity, explicit intention,
independent authority, CAS and actor-attributed history before any production use. Provider
mailboxes, emails and names never create bindings. There is no competing person registry.

`IdentityBindingResolver(engine, verifier, synthetic_only=True)` requires an explicit test
engine and exact opt-in. `resolve(proof, requested_household)` performs only:

1. Check same-verifier proof origin and expiry.
2. Find the exact unique issuer/subject binding; missing, ambiguous or revoked rejects.
3. Require exact requested household and existing same-household Person.
4. Re-read current allowed G2a membership and return its authoritative revision, then
   recheck proof expiry. Errors disclose no binding/household existence or database details.

The safe internal result contains only household ID, Person ID, membership revision and
binding revision. It is **not an authorized service context, login session, source projection
or permission lease**. No source/provider records, credentials, grant contents or audit are
read; no grants are created. Returning it does not authorize a subsequent action. Membership
or binding may change immediately after the query; fresh authoritative checks and disclosure
ordering are mandatory at every future service use. This query is not an end-to-end
revoke/disclosure guarantee or stronger transaction contract than G2a.

A complete authenticated handoff would require G2b2 sessions and independent capability
resolution. It is deliberately deferred: this module neither imports G2a nor issues
`harness_context()`. No new code can convert a verified proof/resolved member into G2a
management/source/publication handles. Existing G2a harness provisioning remains isolated
trusted fictional test setup, not an authentication bypass to expose through an API. G2a
read/revoke CAS, UNKNOWN outcome handling and recipient membership-revision binding remain
unchanged. Re-enrollment returns the new member revision; old source/publication grants
remain ineffective until separately renewed, never revived by authentication.

Upgrade enrolls/grants nobody and rewrites no source, raw, analysis, label, cursor or G2a
audit history. Downgrade drops identity bindings only; old identity/authorization/provenance
remain. Re-upgrade is empty/unbound and fail-closed. Tests perform round trips only against
disposable databases. Any future real migration needs explicitly approved target, backup,
restore/rollback rehearsal, privileges and operator responsibilities; none is performed here.

## G2b2 session/recovery/deployment decision register — not activated

| Gate | Decision/evidence still required |
| --- | --- |
| OIDC flow and trusted profile | Approved provider/profile; maintained relying-party library; authorization-code + PKCE, state and durable nonce binding; verified endpoint/discovery metadata, audience separation, secure callbacks and token substitution tests |
| Sessions | Server-established sessions, rotation at login/privilege changes, fixation prevention, logout/server-side revocation, absolute/idle deadlines and distributed replay protection; ID-token expiry is not session management |
| Strong login | Passkeys/phishing-resistant MFA and step-up policy using independently verified authentication context; no custom passkey/MFA cryptography |
| Second adult invitation | Secure peer invitation/enrollment and explicit membership proof, no first-enrollee superuser; linking identities needs separate confirmation/current authentication and actor audit |
| Recovery | Lost device, account/IDP recovery, abuse prevention and changes to verified subject/binding; no automatic email matching, mailbox-based authority or silent re-enrollment |
| Current capabilities | Current authoritative membership, source/publication control, reviewer and operation consent separately resolved; no harness or client-supplied capability provisioning |
| Key rotation/outage | Authenticated discovery/key cache, kid rollover/compromise invalidation, bounded outage behavior and no unsupported fallback; remove stale trust deterministically |
| Monitoring/privacy | Content-free bounded security events, login anomaly handling, protected actor/session audit, minimization, retention/deletion and operator access; never log tokens, assertions or personal claims |
| Browser/API security | Approved authenticated entrypoint, TLS, cookie attributes/CSRF, origin/CORS policy, rate/resource limits, token storage and transport-specific replay controls before opening any listener |
| Revocation/disclosure | Recheck session/binding/membership/grants at authorized action and dispatch; reviewed response/cache ordering, no stale private projection leases; database transaction ordering alone is insufficient |
| Operations | Hosted/self-hosted responsibility, patches, authoritative primary/roles, backups/restore, encrypted credentials and separate approved migration/re-consent; no real login or provider access before review |

The privacy timing tradeoff for a shared task warning after source revocation remains
unapproved. Grant-change audit must retain the actual actor, scope and committed/unknown
outcome. A submitted/stale revoke is not a committed revoke; prominent accurate feedback
remains required. Sharing setup must bind exact source, recipients, fields, purpose,
operations and retention/revocation terms; Cancel creates no grant. No permissions silently
transfer between peers/mailboxes, and no production Alternative B exception is enabled.

## Validation and independent review

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_verified_identity.py tests/test_household_authorization.py tests/test_migrations.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Both database CI jobs run these adversarial tests with newly generated fictional RSA
keys. Tests cover exact issuer/audience/key/time/type/nonce, unsigned/algorithm substitution,
JSON ambiguity, bounded errors, cross-peer/household substitution, revoked membership/binding,
unique/FK binding constraints, no implicit linking/enrollment/rights, no network/providers,
isolation and migration agreement/round trips. These are verified offline contract results,
**not proof of production login, MFA, IDP outage handling or distributed session security**.
Actual head-specific counts and CI links are reported in the PR.

Questions for ChatGPT and independent Muse security review:

1. Is the restricted OIDC ID-token profile precise, with unsupported cases failing closed
   and ID/access-token provenance explicitly left to the future verified flow?
2. Can any unverified claim, copied value, wrong issuer/key/nonce or foreign household
   select another Person or gain source/management/reviewer/operation rights?
3. Are binding uniqueness, tenancy and membership revocation separate from authentication,
   with re-enrollment unable to revive old grants?
4. Is the lack of G2a/session handoff explicit, with no production harness bypass?
5. Are trust bootstrap/key rotation, errors/privacy and G2b2 recovery/disclosure gates
   sufficiently specified before a real multi-client deployment is considered?

Keep the PR open/unmerged for both independent reviews and final human-controlled merge.
No real login or production/provider functionality is enabled.

### G2b2 integration note

[Internal durable sessions](v0-1-session-service-boundary.md) now consume verifier-issued
fictional proofs and recheck binding/member state transactionally. The 32-handle limit is
this disposable verifier's in-process bound, not a production/durable session capacity.
CONTRACT_VERSION names the source profile only, not a separately deployed version.
The remaining OIDC flow/MFA/browser/disclosure gates above are still unimplemented.
