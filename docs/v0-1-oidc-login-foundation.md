# Stage G3a — Internal fictional OIDC code-flow foundation

G3a follows merged H1 PR #78 (`1b62a000c6b9c880eaba4496b0ab2278164b96fe`).
It adds working **authorization-code + PKCE S256 + state + nonce** orchestration into
unchanged G2b1 verification and G2b2 durable sessions/authorized fixture reads. This
is an internal, fictional relying-party seam, **not deployed login**. No listener,
HTTP client transport, UI connection, real IDP/account, private data or provider call
is enabled. H1 remains the same offline fictional workbench.

Read alongside [G2b1](v0-1-verified-identity-boundary.md),
[G2b2](v0-1-session-service-boundary.md), [G2a](v0-1-durable-household-authorization.md),
[architecture](architecture.md), [security](security.md) and [roadmap](roadmap.md).
Central R0–R3 and unapproved/disabled Alternative B remain unchanged.

## Dependency decision

Authlib **1.8.0** was selected after checking available package-registry releases.
Authlib is a maintained OAuth/OIDC implementation with a transport-independent
`OAuth2Client`, S256 support and OIDC `CodeIDToken` claim checks. These match the
existing Python core without requiring Flask, FastAPI, a listener or a real provider.
Writing our own OAuth/PKCE/signature algorithms would add unnecessary security risk.
The existing OAuthlib provider dependency is not repurposed into a competing login
implementation; existing PyJWT/cryptography remain G2b1's signature/profile boundary.

Optional `oidc` dependencies declare Authlib >=1.8,<1.9 and the existing identity
requirements. `requirements-dev.lock` pins Authlib 1.8.0 and its joserfc 1.7.5
transitive dependency; existing pins remain unchanged. Upgrade needs protocol,
strict-envelope, claim, isolation and full regression review. Selection is not a
claim of exhaustive vulnerability assessment or production deployment approval.

Authlib constructs the authorize/code-exchange requests, encodes public-client token
endpoint authentication, parses state-bound code responses and computes S256. G2b1
owns signature and strict issuer/audience/profile verification. **Only after that
verification**, the exact same immutable token is decoded for Authlib's extra OIDC
nonce/azp/amr/optional at_hash validation. Post-verification claim decoding does not
establish authority itself. No custom signature verification, password, JWT session
scheme, PKCE hashing or model inference is implemented.

## Executable internal boundary

`_oidc_login.LoginFlow(config, verifier, sessions, exchange=local_function,
synthetic_only=True)` accepts exact existing verifier/session types and the **same
verifier instance**. The immutable configuration must match that verifier's exact
issuer/client audience. Symbolic HTTPS endpoints are limited to `.example.invalid`,
with authorization/token endpoints on the issuer's configured origin. No user info,
port, query, fragment, percent-encoded path or normalizing aliases are accepted in
configuration. Redirect and callback location must match exactly. There is no default
configuration, discovery, environment credential lookup or arbitrary endpoint input.

Public-client `none` token endpoint authentication and **only `openid`** are supported
for the fictional profile. No client secret, offline access, refresh token, userinfo
or provider OAuth is introduced. A real confidential-client authentication policy is
a separate decision, not silently inferred from this public-client test profile.

| Internal operation | Contract |
| --- | --- |
| begin(requested household) | Bounded ID syntax only, not authorization or existence check. Issue cryptographically random 256-bit state/verifier; use G2b1's issued nonce challenge. Return only an owned redacted attempt handle with its authorization URL. |
| cancel(attempt) | Discard unfinished owned attempt. No session, grant or audit write. |
| complete(attempt, callback URL) | Atomically consume exact owned handle before parsing/exchange/DB. Require current creation/expiry/config, exact callback, one code/state and optional exact issuer; reject duplicate/extra fields, fragments and implicit/client token input. Authlib constructs identical configured code exchange with the stored verifier. Validate returned ID token and then call existing session establishment. |

A caller-supplied token is **never** a completed login input. A callback's `id_token`,
extra parameters, foreign state/code, copied receipt or another flow's receipt rejects.
The authorization URL intentionally carries standard browser-visible state/nonce/S256
challenge, never the PKCE verifier, ID/access tokens or an identity. Do not log the URL.
The simulator doesn't open it: all protocol requests are direct local function calls.

`Completion` contains the server-generated exact request ID and existing G2b2 result.
A committed session bearer is an explicitly internal secret, repr-redacted and released
only after G2b2 commit. Never serialize it into ordinary diagnostics. ID/access tokens,
PKCE and raw claims are neither returned nor stored in session/audit/projection state.
Errors are generic `Login unavailable`, without provider/driver messages or identity
existence. No automatic retry occurs. COMMITTED/UNAVAILABLE/CONFLICT/UNKNOWN preserve
G2b2 meanings; a generic login error is not proof that a database operation did not apply.
After UNKNOWN retain that exact request/intent for independently authorized verification;
do not blindly retry/rebase under a new ID or assume the secret is recoverable. The
existing fresh-proof recovery seam remains internal; no browser recovery flow is added.

## Attempt ownership, bounds and concurrent completion

At most **16 pending attempts**, lifetime **300 monotonic seconds**, exact single-process
object ownership and an atomic consume lock. Creation/clock rollback/expiry equality,
cancel and reuse fail closed. No attempt lock is held during exchange or DB operations.
The owned receipt models an intended browser-bound server receipt, **not an implemented
browser cookie or defense against hostile in-process Python**. Same-process duplicate
callback tests prove one exchange/session/audit; they do not prove distributed replay
prevention or browser login-CSRF protection in an exposed service.

G2b1's existing wall-clock ID-token/challenge lifetime and **32 challenge/proof handle
caps** also apply; its ownership/consumption rules are unchanged. Canceled/failed flow
attempts may leave an unreachable verifier challenge, or an extra-validation failure
may leave an unused proof, until verifier expiry pruning. This is bounded test-stage
backpressure, not production capacity/rate control. A restart loses pending attempts;
other process instances cannot consume them. No alternate identity store or migration
was added. Before a network/multi-instance rollout, review a durable atomic attempt
store, protected PKCE material, original browser binding, cancellation/cleanup, admission
limits, deadlines and distributed single-use ownership in the authoritative deployment.

Token replies have a 32 KiB byte bound, strict JSON without duplicate/non-finite values,
HTTP 200, exact bounded ID/access strings, Bearer type and requested scope. Unknown,
refresh-token or unsupported fields reject. No provider error body is logged or surfaced.
Injected exchange code is **trusted harness configuration**, not hostile code isolation;
the module itself imports no HTTP/socket client and has no real transport fallback.

## Restricted profile compatibility — no silent weakening

This flow does not make G2b1 a universal IDP verifier. It still requires RS256, exact
kid/typ=JWT/alg headers, exact single-string audience, matching optional azp, integer
iss/sub/iat/nbf/exp/nonce requirements and at most 300-second validity. **OIDC permits
optional nbf, longer validity and other JOSE/audience profiles; they remain unsupported**
and fail closed. Authlib validates optional access-token hash (a present empty/invalid value rejects); `c_hash` is explicitly
unsupported/rejected. Callback query mode supports optional RFC 9207 issuer, with
strict comparison when present; form-post/JARM/implicit flows are unsupported.

The fictional provider issues the documented compatible profile. Real provider token
profile, issuance policy and ID/access audience separation need independent approval;
synthetic signature-valid assertions cannot prove a real IDP's issuance provenance.
Static trusted keys, their rotation/removal and exact proof origin remain unchanged.
No proof is fabricated and no client can choose expected nonce/keys/profile.

## Exact authentication-to-read chain

New fictional Sable identities and generated RSA keys demonstrate:

1. State/nonce/S256 authorize request → local simulator code bound to client/redirect.
2. Single-use exact callback → code exchange enforcing PKCE and exact client/redirect.
3. Signature/profile/OIDC checks → actual same-verifier issued proof.
4. G2b2 transaction rechecks existing exact issuer/subject binding and membership epochs.
5. Durable hashed-bearer session → unchanged G2a-authorized fictional read projection.

Email/name/roles/household claims never select Person or provision anything. Membership,
source/security-read and task publication remain independent. No harness context is
issued from identity; no management, reviewer, operation or R2/R3 authority appears.
Both equal adults get distinct sessions over one shared household state. A private or
revoked source remains absent even after successful login. Revoked binding/membership
blocks establishment; later reads retain G2b2's fresh revocation/transaction checks.
Database transaction ordering does not solve response/cookie/cache disclosure races.

## Deployment decision register — unapproved

| Required gate | Decision/evidence before any real login/API |
| --- | --- |
| Actual IDP/client | Provider choice, issuer/client/redirect/profile, confidential/public client mode and audience separation; no paid vendor or credentials selected here |
| Phishing-resistant authentication | Passkeys/MFA, step-up semantics and verified assurance; signed amr/roles alone confer no authority |
| Both-adult enrollment | Secure invitations, current binding/member authority, no email linking or first-adult superuser |
| Recovery | Lost device/IDP/account recovery, peer-safe ownership verification, stolen bearer response and orphan-session cleanup |
| Discovery/key trust | Independently trusted metadata/JWKS, rotation/compromise invalidation, bounded cache/outage behavior; no token-chosen URLs |
| Browser callback | Authorization-code/PKCE/state/nonce original-browser binding, exact endpoints, Secure/HttpOnly/SameSite cookies, CSRF, TLS, CORS/origin and response-mode hardening |
| Sessions | Fixation prevention, rotation, cross-device logout, authoritative revocation and resource/rate limits |
| Operations | Hosting/operator access, protected audit, monitoring without secrets, patching, backup/restore and session/attempt retention/deletion |
| Disclosure | Response dispatch, revoke ordering and private-cache invalidation; no reusable stale authorized projections |

Next recommendation: a separately reviewed **authenticated read-only API adapter**
over the existing session/current-permission services, initially fictional transport
conformance. Before exposing it or connecting real identities/data, approve the real
OIDC/browser/MFA/recovery/deployment gates above. Do not expose harness methods, enable
provider access/writes, attach H1 to real data or start a real-mail pilot in this PR.

## Validation and review

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pytest -q tests/test_oidc_login.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_verified_identity.py tests/test_household_sessions.py tests/test_household_authorization.py tests/test_migrations.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

66 new adversarial cases cover protocol/profile/config, CSRF/state/nonce/replay,
PKCE, substituted code/token/keys, untrusted claims, current revocation, missing
permission, equal peers, concurrent completion, bounds, safe logs/audit and no network
or privileged harness handoff. Existing isolation tests allow exactly this additional
internal consumer, not arbitrary production imports. Existing metadata/migration
upgrade/downgrade/upgrade checks run on disposable SQLite/PostgreSQL 16 only; no schema
change or real migration occurs. Exact focused/full counts, CI and head belong in PR.

Review whether exchange provenance and proof ownership remain exact; whether bounded
single-process guarantees and profile incompatibilities are explicit; whether any
identity claim can enroll/grant; and whether UNKNOWN/secret handling remain conservative.
Leave open/unmerged for ChatGPT, Muse independent security review and human merge.
