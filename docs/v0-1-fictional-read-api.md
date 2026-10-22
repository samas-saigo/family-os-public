# Stage G3b — In-process authenticated fictional read API

G3b follows G3a PR #79, merged at
`92525b2c7f48c2b098754d581c729edf48172875`. This is an executable **fictional
transport conformance boundary**, not production login or a deployed API. All records,
identities and keys are newly invented Larch/Azalea test data in disposable databases.
No listener, port, HTTP client, real IDP, provider, model or household data is used.
H1 remains offline and unconnected. No migrations, provider behavior or credentials change.

Read with [G2a rights/transactions](v0-1-durable-household-authorization.md),
[G2b1 identity](v0-1-verified-identity-boundary.md),
[G2b2 sessions](v0-1-session-service-boundary.md),
[G3a code flow](v0-1-oidc-login-foundation.md),
[G1 field scopes](v0-1-household-read-service.md), [architecture](architecture.md),
[security](security.md) and [roadmap](roadmap.md).

## Dependency and trust decisions

`_fictional_read_api.FictionalReadAPI(existing_sessions, trusted_household_id,
synthetic_only=True)` is a small ASGI HTTP callable using the standard library.
No framework or dependency is added: one fixed resource needs no router, middleware,
automatic object serialization, cookie management or server package. Tests invoke
the ASGI scope/receive/send interface directly with an in-process client, never sockets.
This choice is bounded conformance code, not a general HTTP parser or framework choice
for future deployment. A maintained framework/server and transport security review
will be required before any listener; this callable must not be deployed as-is.

Exact opt-in and an exact existing `SessionService` are mandatory. Trusted setup binds
one household, existing verifier, explicit test engine and fixed fixture repository.
No environment/database discovery or client-configured household, repository or engine
is accepted. These Python construction controls are not isolation against hostile
in-process callers. Fictional provisioning and offline proof issuance remain privileged
test setup. There is no API session-issuance, enrollment or grant-management route.

Every valid request calls existing **G2b2 `read()`**, which checks the durable hashed
bearer, current identity binding, membership epochs, expiry and revocation, then uses
the existing G2a authoritative grants/projection within its transaction. No copied
authorization engine, session-derived `harness_context()`, claim-derived privileges
or new management/reviewer/operation rights exist. Authentication, source observation
scope, security scope and publication grants remain independent. R0–R3 is unchanged;
Alternative B standing authorization is disabled and unapproved.

## Strict request contract

Only `GET /v0/workbench`, with exact path (and raw path when supplied) and empty mount
prefix. Unsupported versions, methods, paths, encodings and private-function paths deny.
ASGI lifespan/WebSocket are unsupported; no server lifecycle is implemented.

| Input | Accepted fictional contract |
| --- | --- |
| Authorization | Exactly one lowercase ASGI `authorization` header, `Bearer ` plus 43 URL-safe ASCII characters; current G2b2 bearer validity is still required |
| Optional headers | `accept: application/json`, `content-length: 0`, `host: fictional.test`; any duplicate, unknown header or other value rejects |
| Header bounds | 1–4 entries; byte names/values; each value at most 256 bytes; no cookies, Origin, client identity/role/grant or proxy headers |
| Query | At most 128 ASCII bytes and three distinct supported parameters; no percent aliases, empty values, duplicate names or extra fields |
| limit | Canonical integer 1–20, default 20 |
| offset | Canonical integer 0–128, default 0 |
| topic | Exactly `fictional-booking` or `fictional-school`; applies only to observation/security lanes |
| Body | One empty final `http.request` event within one second; body chunks, pending bodies and disconnects deny before DB read |

An arbitrary ID token, Person, email, bearer hash or harness handle is never an API
session. Another household's valid bearer denies against trusted server household.
An identical copy of a valid bearer is necessarily the same usable credential;
this contract does not claim stolen-secret detection or device binding.
Ordinary Host/User-Agent/Accept negotiation, streaming, mounted apps, cookies, browser
CORS and HTTP parser/proxy behavior are intentionally not supported by this test profile.

All request/authentication/authorization/session/database/serialization rejections use
the same **400** JSON `{"error":"request_unavailable"}` and protection headers. Uniform
status is a deliberate content-free fictional contract, not a final production API
status convention. It exposes no reason, identity existence, hidden source count,
driver detail, URL, assertion, traceback or token. The adapter logs nothing.

## Explicit response schema: `g3b-fictional-read-v1`

Success is 200 JSON, ASCII-escaped, sorted keys, finite JSON, at most 32 KiB. Fixed
field mapping replaces ORM/dataclass serialization. The top-level fields are:

- `schema`, `synthetic_only: true`, `pagination: {limit, offset}`.
- `observations: {items, total, has_more}`: only authorized `source_id`, fixed
  `provider: fixture`, `object_id`, `generation`, `topic`.
- `security: {items, total, has_more}`: the same identity/generation/Topic fields plus
  separately permitted `safety`; Topic is an authorized security query dimension.
- `published_steps: {items, total, has_more}`: only independently approved
  `publication_id` and neutral fixed `step`. These are **fictional published steps**,
  not real accepted tasks, fresh evidence, execution or authority.

Each lane's total is its authorized filtered unique-object count, before pagination.
`has_more` is `offset + returned rows < total`. Topic does not inspect publication
provenance or filter published steps. Each lane pages independently. Order comes from
G2a's stable scoped object identity / publication key, never hidden records or actors.
Household, principal, session identifiers, hashes, claims, readers, grant scopes/revisions,
private provenance, credentials and raw provider/source metadata are not returned.
One source object is not multiplied by two peers or duplicate observations; distinct
mailboxes remain distinct, without title-based canonical dedupe.

G2a filters effective access **before** field consistency, duplicates, counts, topic
filters or pages. Observation-only scope never checks/returns unauthorized Safety;
authorized security contradictions reject rather than choosing CLEAR. Two peers with
equivalent grants see identical JSON. Private grants change only their authorized view.
Source revocation may leave independently published neutral steps visible; publication
revocation removes those separately, without protected-source links or freshness signals.

Every success/error includes `Cache-Control: no-store, no-cache, max-age=0`,
`Pragma: no-cache`, `Expires: 0`, `X-Content-Type-Options: nosniff`, JSON content type
and exact content length. No cookies, ETags, shared caches, stored responses, client
storage, background serialization or notification-shaped outputs are implemented.

## Preparation, dispatch and tested ordering

1. Validate the bounded transport request. `_Prepared` contains only a repr-redacted
   bearer plus bounded query specification; **no prior projection or permission lease**.
2. Receive/reject the bounded empty-body event.
3. At `_dispatch`, execute a **fresh G2b2 read** on the authoritative database.
4. G2b2 uses SQLite BEGIN IMMEDIATE / PostgreSQL READ COMMITTED household row lock,
   checks current session/binding/member/source/publication rights, and commits the
   permitted activity update before returning. A failed/ambiguous read commit returns
   no projection; the adapter emits only the uniform error.
5. Serialize explicit permitted fields synchronously, with no await between read and
   serialization; only then start the response and send the bounded body.

Real two-thread/two-connection tests commit session, membership, binding, source or
publication revocation after request preparation and before dispatch. Dispatch reflects
that committed revocation. Subsequent requests also reauthorize; no prepared private
result is reused. A synthetic driver fault commits a real activity update and then
raises, demonstrating that acknowledgment failure yields an error without partial data.
It is not proof of real network partitions or failover correctness.

**A later revocation between the final committed read and send, or while the receiver
accepts bytes, cannot retract this response.** No DB lock is held across asynchronous
send, and no claim of end-to-end no-stale-disclosure is made. Send failure propagates;
there is no second response, data retry or guessed delivery outcome. Already delivered
bytes cannot be recalled. These guarantees assume all relevant writers follow G2a
ordering on the same primary. Response dispatch, browser caches, proxies, replicas,
failover and hostile DB modification remain deployment gates.

Synchronous DB calls intentionally block the event loop in this tiny in-process slice.
Database lock/deadline behavior is inherited from trusted test engine configuration.
Finite request/response bounds and finite trusted fixture traversal are not public-service
rate limiting or throughput guarantees. Public adapter concurrency, worker strategy,
admission limits and cancellation/timeout ordering need independent review.

## Deployment and recovery gates — still unapproved

Before any browser connection/listener, decide and independently verify: approved real
OIDC provider/profile, passkeys/phishing-resistant MFA and step-up; peer invitation and
account recovery; distributed single-use original-browser-bound login attempts; trusted
key discovery/rotation/outage; TLS and Secure/HttpOnly/SameSite cookies; CSRF and
Origin/CORS/browser transport; fixation prevention, logout/cross-device revocation;
resource/rate limits; protected audit/monitoring; DB roles/primary routing, operational
credentials, backups and rollback; response dispatch and private-cache revocation races.
There is no default production framework/hosting/IDP/vendor choice in this stage.

Carry forward Muse's G3a observation: an **UNKNOWN session-establishment outcome cannot
be blindly retried**, and the bearer cannot be recovered. Historical exact-request
verification requires a **fresh independently verified identity proof** through G2b2's
internal outcome method. This read API neither exposes recovery nor substitutes an
invalidated bearer for independent verification. No model/real-mail pilot, credential
movement, provider write, task mutation, reconciliation or standing consent is enabled.

## Validation and review handoff

From the repository root, Python 3.12, disposable test stores only:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_fictional_read_api.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_household_authorization.py tests/test_verified_identity.py tests/test_household_sessions.py tests/test_oidc_login.py tests/test_migrations.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

No launch command is provided: only the in-process test client is authorized. Full
SQLite/PostgreSQL 16 CI includes existing migration round-trip/metadata checks; no
schema or live migration changes. The only existing-test edit adds this exact private
consumer to the session isolation allowlist; no behavioral assertion is weakened.
Actual head/count/job conclusions belong in the PR handoff.

ChatGPT and independent Muse should verify: (1) no client field establishes authority;
(2) every request reuses the authoritative session/permission mechanism; (3) serialization
and hidden field/population errors preserve scope; (4) preparation has no private snapshot
and dispatch limits are honestly stated; (5) source/publication rights remain independent;
(6) the narrow ASGI contract cannot be mistaken for approved login or production hosting.
Leave open/unmerged for both reviews and final human-controlled merge.
