# Family OS v0.1 / Stage G1 — shared read-service foundation

## Status and lineage

Stage G1 follows merged Stage E2 PR #72 at main commit
`32444031b7e22a87d864f1b9495032d677735147`. It supplies an executable,
**synthetic-only authorization-first read-service seam**, not a deployed backend,
authenticated network service, production login or real-mail pilot.

`family_os._synthetic_household_read_service` is independent of CLI formatting and
imports only `dataclasses` and `enum`. It neither calls nor copies the Stage A/B/C/E1/E2
runtime modules. Existing `family_os.services`, providers, scopes, keyring behavior,
identity verification, cursors, analysis and executable schema remain unchanged.
There is no CLI entry point, listener, API, database, credential movement, worker,
model, real task creation, notification, quarantine, restoration or other write.

All data is newly authored fictional enum-based Meadow School / Lantern equipment
booking material. No real household data, private labels, frozen Development/Holdout,
provider clients, OAuth, Finance, URLs or AI/Ollama are inputs. Real Gmail, Outlook,
Calendar, Drive and other household data must not enter any AI, including local models.

Read with [architecture](architecture.md#5-deployment-and-client-architecture),
[security](security.md#provider-oauth-and-family-os-client-access),
[data model](data-model.md), [Stage D](v0-1-household-first-authorization.md),
[E1](v0-1-security-action-authorization.md),
[E2](v0-1-synthetic-security-lifecycle.md) and [roadmap](roadmap.md).

`synthetic-household-read-contract-v2` names this source-code contract revision for
review/reproducibility. It does **not** imply historical versions are separately
installed/deployed services, or authorize a client to choose an obsolete policy.

## Trusted boundary: identity is not a query parameter

The future backend must establish authenticated client/session identity **before**
creating trusted request context. Client-supplied household/person IDs, email, source
ownership or risk values cannot establish authority. Provider OAuth, local OS access,
a source registry row and database foreign keys are not multi-client authentication.

| Boundary | Required separation | G1 executable scope |
| --- | --- | --- |
| Client authentication/session | Verify client identity, expiry, revocation, recovery and session binding outside domain queries | None; synthetic harness handles only |
| Trusted principal/household context | Derive principal from verified session; verify requested household membership before dispatch to services | Service-local handle issued by trusted test harness, checked on every call |
| Household membership | Two peer adults; no primary/secondary hierarchy; membership is not source access | Explicit current Membership assertion and revision |
| Source grants | Exact household/source/recipient, field/purpose scope and current effective rights | Minimized observation-read and security-read scopes only |
| Shared-task publication | Independently approved fields and task recipient grant; never source content laundering | Fixed neutral fictional fields, separate publication and TaskGrant |
| Source-operation consent | Exact mailbox, operation and consent revision; does not follow read/task grants | Not represented or returned by read service |
| Security reviewer permission | Explicit reconciliation capability plus current source access; not generic read or mailbox consent | Not represented or inferred by read service |
| Central R0–R3 approval/execution | Backend determines risk, binds approval, audits and rechecks before execution | No action/approval/executor entry points |

R0 permits authorized reads only. R1 drafts/suggestions are not task acceptance or
mailbox mutation. R2 requires confirmation; R3 requires explicit confirmation and
audit. Quarantine/restore would have distinct external-write consent and central
approval. Alternative B standing consent remains **disabled and unapproved**.
Source-read/security details, published task state and model/detector output confer
none of those rights. There is no production authentication shortcut in this slice.

## Executable service and one shared state

`ReadService(state, authorization, synthetic_only=True)` requires exact boolean True
before initialization. Its frozen `HouseholdState` contains current fictional
observations and separately published fictional task fields. Both Mara and Leon query
that **same** authoritative state. There are no owner-specific task stores/copies,
mandatory personal inboxes, per-message sharing prompts or client-side authority.

The trusted harness can issue `harness_context(household, principal)` only for a current
allowed membership. The service registers that exact context object; constructing a
dictionary, dataclass copy or another service's handle is insufficient. Each call also
rechecks current membership and its exact revision. Unknown/revoked/stale/conflicting
membership denies with the same content-free `Read access unavailable` error. A changed
membership revision needs a fresh issued handle; old prepared requests do not revive.
These in-memory object checks are **not** signed tokens, login, a hostile-Python sandbox
or authentication. Harness controls must never become client endpoints.

Two independent harness controls replace a frozen authorization snapshot or fictional
state snapshot. They model current declared state for deterministic tests; they do not
implement grant editing, authenticated publishers, CAS, task creation or an audit store.
Trust in those declarations is explicit. Real authorization must come from an independently
reviewed authoritative backend, not whichever assertions a client submits.

### Read contract and minimized results

- `project(context, Query(limit, offset, topic))` returns one frozen `Projection` with
  independent observation, task and security `Page` values. Each page contains rows,
  its **authorized, searched total** and `has_more`; no global/hidden count or revision.
- `prepare(context, query)` returns only a query plus context reference. It contains
  **no** rows, counts, links, previews, access lease or saved grant revision.
- `consume(context, prepared)` requires that same issued context and runs the current
  membership/source/task checks again. Reuse never bypasses revocation.
- `observation(context, SourceKey)` is a source-link-shaped lookup, not a URL.
  Inaccessible, other-household and nonexistent keys return the same `None` without
  an outcome, reason, source-existence marker or count. Membership failure remains
  the same generic context error regardless of the requested key.

Observation identity is exactly **household/source/provider/object**. Generation is
snapshot provenance, not a second source object; principal is request identity, not
an object multiplier. After current source access filtering, records are minimized to
**scope-authorized fields before deduplication or consistency validation**. Observation
scope compares only SourceKey, generation and Topic; unauthorized Safety differences
cannot change observation outputs, counts, search, pagination or errors. Direct
`observation()` lookup uses this same observation-only contract, even for a reader who
also has security permission. Inconsistent authorized generation/Topic assertions reject
with content-free `Synthetic read contract rejected`; no current snapshot is selected by
input order. Hidden inconsistencies never participate. Different mailboxes remain
separate even with matching object markers/topics; no title similarity or canonical
cross-source dedupe is performed.

Observation rows contain only SourceKey, generation and a fixed fictional Topic.
Security rows contain SourceKey, generation and fixed Safety. Its authorized internal
search/consistency fields are exactly SourceKey, generation, **Topic** and Safety:
Topic is permitted for the security query's fixed enum filter even though it is not a
returned security-row field. No other fields participate. Conflicting current Safety,
generation or Topic assertions reject before CLEAR exclusion or query filtering; neither
CLEAR nor HIGH_RISK wins by input order. A combined projection may therefore reject
when its authorized security lane is inconsistent; an observation-only reader cannot
observe that conflict. Security-read is a distinct explicit purpose scope;
observation-read alone never inspects Safety for projection/consistency or returns it. Unknown,
stale, suspicious, high-risk and indeterminate safety remain in authorized security
inspection; only declared current clear is omitted. None establishes clearance for an
action, task acceptance, Offers admission or detector efficacy. Promotions create no
new task or notification here.

Task rows are only the separately approved `TaskFields`: fixed task identity, neutral
step, assignment (either peer or joint), status and revision. Their internal provenance,
source IDs, contributor count and source-derived links are never returned, searched,
read to enrich those fields, or used for duplicate/consistency validation. An authorized
TaskGrant alone cannot expose an unknown/revoked/stale or contradictory publication.
Conflicting publication assertions withhold that task. Internal provenance differences
do not change the permitted task projection. No editable task lifecycle is implemented.

The fictional single booking task is seeded once under a separately declared approved
publication with two distinct source references. It is not created by classification,
title matching, review confirmation or read-service execution. Both peers see its same
assignment/status/revision. Task publication revocation removes it independently of
source grants. Source revocation can leave those approved task fields visible while
removing all now-private source/search/security/link results. Later private arrivals or
evidence changes cannot change that recipient's task fields, counts or warnings.
G1 emits no freshness warning: Stage D's one-time revocation timing tradeoff remains
unapproved. Continued publication is not fresh evidence or external action authority.

### Authorization-first collections and conflict policy

Each current **household/source/principal** key must have one consistent SourceGrant;
exact duplicate values are harmless. Different states, scopes or revisions fail closed
for that source, including older ALLOWED plus newer REVOKED, UNKNOWN versus ALLOWED,
or two ALLOWED assertions at different revisions. No highest-revision, timestamp,
input-order or ALLOWED-wins rule is independently authoritative. Membership and task
grants use the same conservative resolution for their own keys. Conflicts for another
member/household cannot shadow the requested peer's permissions.

Resolve source rights, then minimize each lane to its authorized fields before coalescing, consistency checks,
counts, search or paging. Then include **every** authorized source: an inaccessible or
ambiguous mailbox does not suppress unrelated shared mailboxes. Task authorization
and publication are resolved separately; neither expands source access. Hidden items
cannot change result values/order, duplicate errors or visible collection-cap behavior.
There are no suppressed-record badges, hidden placeholders or implicit existence links.

Query bounds are positive limit 1–8 and offset 0–16. Each page applies its own offset
and limit to its own authorized searched set; totals remain distinct. Order is stable
lexicographic source-object enum identity for source/security rows, and fixed task
identity for task rows. This is deterministic pagination, not time-based relevance
ranking or evidence of production usability. Search accepts only the fixed Topic enum,
not arbitrary user text or provider queries. At most 16 unique authorized observations
per purpose are processed into a projection; cap and inconsistency checks precede
search so a filter cannot bypass an authorized collection limit.

Harness input is a finite exact tuple of strictly typed frozen values. Authoritative
assertion envelopes are capped separately (16 memberships, 32 source grants, 16 task
grants); there are at most 16 issued context handles per disposable service. These
trusted setup limits are not derived from hidden observation population. No global
observation/task population cap is checked during a query. Traversal is finite linear,
not constant-time and not a production resource-exhaustion defense; a future repository
must push authorization into bounded database queries. Malformed values are rejected
at trusted fixture construction, not accepted through a public household-data endpoint.

### Revocation and the disclosure boundary

Already returned plain Python snapshots cannot be recalled, erased or made safe to
reuse by a later grant change. **Reusable stale projections are forbidden by this
design.** The only modeled preparation is an unevaluated query, consumed with fresh
checks; source links are freshly gated on use. No cache, notification or delayed
client renderer is implemented. A future authenticated transport must establish a
reviewed authoritative read/disclosure ordering and cache invalidation policy before
sending/consuming content; a successful old check is not a lease. G1's single-threaded
snapshot replacement is not a production concurrent revocation guarantee.

## Newly authored executable conformance

Mara and Leon are two peer adults in the fictional Cedar household. Meadow School and
Lantern equipment booking observations are fixed enum values, not texts copied from
any corpus. The Ridge household supplies only cross-tenancy probes.

| Case | Required executable behavior |
| --- | --- |
| G01 | Equal source/task grants yield the same full household projection for both peers, including search and pages |
| G02 | Both independently shared mailboxes appear in one source/security workspace; no owner-only filter |
| G03 | Consistent duplicate observations/grants do not multiply source-object counts; different mailboxes stay distinct |
| G04 | Independently approved one-task fields/revision/assignment remain common to both peers |
| G05 | Source revocation removes source/search/security/link disclosure, while independent task publication remains |
| G06 | Private source arrivals and protected provenance changes cannot alter published task output |
| G07 | Task revocation removes only that task; source access alone cannot publish it |
| G08 | Read scopes neither infer operation/reconciliation permission nor expose extra fields |
| G09 | Contradictory current grants withhold only the affected key, in either order; unrelated sources remain |
| G10 | Unknown membership, fabricated/copied/cross-service contexts and foreign households cannot establish access |
| G11 | Hidden conflicting duplicates/over-limit populations do not affect authorized counts, sorting, pagination, search or errors |
| G12 | Prepared queries reauthorize on every consumption; membership revision changes and source/task revocation apply |
| G13 | Unknown/stale safety remains inspectable without clear/action authority; no task from suspicious promotions |
| G14 | Current publication and recipient authorization are separate, provenance-free and fail closed on ambiguity |
| G15 | Frozen results, typed bounds and no-I/O/import/production-wiring tests preserve the read-only seam |
| G16 | Observation-only Safety conflicts/changes cannot alter projected results or direct lookups; authorized security contradictions still reject; generation/Topic conflicts remain conservative in either scope |

These probes test privacy **and complete unified management**, not real authentication
or detector quality. Existing Stage D/E1/E2 and A/B/C contracts/tests remain intact.

## Production deployment decision register — all gates remain future

No technology below is silently selected for implementation. Before any authenticated
network exposure, approve and test the complete authority/disclosure boundary.

| Decision/gate | Options and decision criteria | Required evidence before enablement |
| --- | --- | --- |
| Client identity and sessions | Reviewed identity provider versus a maintained self-hosted identity service; phishing-resistant login/MFA, session revocation, recovery, device compromise and operational burden | Verified principal establishment, expiry/refresh/logout, CSRF/replay protections appropriate to selected transport, no client ID substitution |
| Membership verification/recovery | Explicit peer invitations and mutually understood enrollment/recovery, without hierarchical spouse roles | Account/household proof, lost-device/recovery abuse tests, authoritative revision and conflict handling |
| Source sharing | One-time explicit peer sharing profile with optional private/restricted sources; not per-message prompts | Exact source, recipients, fields, purpose, operations, retention/revocation terms; Cancel creates no grant; committed revocation distinguished from submitted request; stale/failed revoke prominently not applied |
| Shared authoritative state | One PostgreSQL-backed household repository for all clients; transactional permissions/publications/provenance, no per-member task databases | Authorized query plans, exact source-object identity, snapshot/revision consistency, household tenancy, protected history and concurrent revoke/read/edit tests; G1 has no persistence |
| Task field publication | Separately approved neutral fields and recipient/task grants; shared state/assignment versus private evidence | Publisher's real authority at publication, field-by-field privacy review, independent revocation/deletion policy and no laundering through provenance or warnings |
| Backend credentials | Encrypted credential store with envelope/key management or reviewed secret manager; hosted and self-hosted operational access | Least privilege, separate provider bindings/services/scopes, rotation/revocation, backup protection, no tokens in responses/logs/caches; current native keyrings stay unchanged |
| Credential transition | Explicit safe migration versus separate provider re-consent; minimize exposure and verify stable account identity | User-approved plan, rollback/recovery and deletion handling, no sync-cursor resets or accidental account rebinding; no copying performed here |
| Background sync | Separate bounded backend worker/scheduler options, independent of any client being open | Preserve page atomicity, per-account CAS, opaque cursor/query policy, retry/pacing and idempotency; service credentials remain backend-only |
| Action/reconciliation authority | Central R0–R3 policy, exact operation-specific approval and independent reviewer capability, separate from read/publication | Durable actor-attributed audit/intent/version history, emergency stop, unknown-outcome reconciliation, fresh provider preconditions, recovery/retention and consent; standing B still separately unapproved |
| Transport/cache boundary | HTTP framework/API style undecided; evaluate maintenance, validation, authorization hooks and client needs | Fresh rights before every projection, serialization, dispatch/link open; no reusable stale snapshots; approved race/caching/notification policies and adversarial tests |
| Hosted versus self-hosted | Compare availability, patching, network isolation, encryption/key custody, backups/restore, cost and owner support | Named operational responsibilities, incident response, access/audit controls and deploy/rollback/security review before opening a listener |

Future grant-change audit must explicitly retain the **real initiating actor**, old/new
scopes and authoritative revisions; inferring actor identity from a source-controller
mapping is insufficient. This carries forward Muse's E2 observation without changing
that merged module. Contract version identifiers name reviewed definitions within
source history; they do not imply separately deployed historical authorization services.
Future clients cannot negotiate down to a historical contract as a permission bypass.

The trusted-channel registry and scoped revision-bound feedback protections remain
separate: mail, generated summaries, ordinary user release and source sharing cannot
establish universal trust or silently edit global phishing policy. Sharing, independent
verification, reviewer rights and central operation approval remain different gates.
Recovery/audit retention must honor approved deletion rights while ending unsupported
recovery claims; no automatic quarantine when guarantees fail. No real-mail Stage F
pilot is authorized by this design or by passing synthetic tests.

## Validation and review handoff

Run from the repository root using Python 3.12; no real household database or credentials:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_household_read_service.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_household_read_service.py tests/test_synthetic_security_preflight.py tests/test_synthetic_security_lifecycle.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

There is intentionally no operator/demo CLI or server launch command. The callable seam
is exercised only with newly authored synthetic test fixtures. Full SQLite and PostgreSQL
16 regressions use disposable synthetic test stores. Head-specific test counts, CI
links and actual conclusions belong in the PR handoff, not claims of production safety.

Review questions for ChatGPT and independent Muse:

1. Do equal grants yield one complete shared view for both peers, while every hidden
   source stays absent from values, errors, ordering, counts and link lookups?
2. Are task publication and source access genuinely independent, without protected
   provenance, private-arrival changes or revocation timing laundering into task fields?
3. Is context issuance clearly trusted-harness-only, with no invented login, local-OS
   authentication, caller-selected principal authority or rights inferred from revisions?
4. Do preparation/consumption recheck current rights, and are returned snapshot/cache
   limitations explicit rather than an unproven production revocation guarantee?
5. Are operation, reconciliation, R0–R3 and disabled standing-consent boundaries preserved?
6. Are deployment/auth/credentials/background-execution decisions and the E2 actor/version
   carry-forwards explicit enough before any genuine network service is approved?

Keep the dedicated PR **open and unmerged** for ChatGPT review, independent Muse security
review and final human-controlled merge. No auto-merge or production enablement.
