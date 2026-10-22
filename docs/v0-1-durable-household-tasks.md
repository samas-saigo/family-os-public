# Stage T1 — durable household tasks and pending confirmation

Contract identifier: `t1-fictional-household-domain-v1`. This names this internal
contract, not a separately deployed historical system.

## Implemented boundary

T1 implements a persistent domain over existing SQLAlchemy, Alembic, G2a household
transactions and G2b2 sessions. It is callable without presentation callbacks.
Only disposable SQLite/PostgreSQL 16 databases and newly invented fictional records
are used. `TaskService` requires an existing internal `SessionService`, a trusted
household context and exact `synthetic_only=True`. There is no CLI command, HTTP
route, network listener, H1/H2 integration, automatic proposal producer or real
household enrollment. The flag is a scope guard, not authentication against hostile
Python callers. Production entrypoints must not expose these internal methods.

One household has two equal adults. Login, source ownership and membership do not
confer review, publication, edit or provider-operation authority. The pre-existing
G2a `effective_source_rights` query is extracted without changing grant resolution
or fixture-provider restrictions; current provider ingestion and keyrings are
unchanged. T1 does not promote E1/E2 research execution into a provider path.

## Six-table domain and migration

Migration `e41a9b720dc3`, after `c35b79a12e04`, adds:

| Table | Purpose |
| --- | --- |
| `household_pending_item` | Stable household proposal, exact evidence/definition/generation, resolution and revision |
| `pending_member_right` | Current independently provisioned read/review/publication capability and private annotation |
| `pending_task_publication` | Explicit preapproved recipient plan with read/edit/history permissions and revision |
| `household_task` | One accepted task per stable pending proposal, neutral fields and private acceptance provenance |
| `task_member_grant` | Independent current recipient read/edit/history rights, pinned to membership epoch |
| `task_domain_event` | Append-only actual-actor request ledger and immutable transition snapshots |

Composite foreign keys preserve household tenancy. Current grants have one row per
resource/recipient, separate from history; earlier allowed events cannot resurrect
revoked access. Unique pending/task revisions and household/actor/request keys
prevent duplicate transitions. Acceptance uniqueness is source-proposal identity,
not cross-source document or title deduplication. No competing Person/SourceAccount
registry or canonical entity is created.

Upgrade creates empty T1 tables without rewriting existing source, raw, analysis,
authorization or session records. Downgrade removes T1 derived domain data and
history; it does not mutate existing provenance. Do not run this research migration
against a real household database without separate deployment approval, backup,
restore rehearsal and an explicit policy for losing T1 history on downgrade.

## Separate review, resolution and task tracking

The trusted fictional harness provisions proposals and capabilities; a classifier,
page view or provider cannot create a task. Fixed supported neutral steps are
`school-session` and `home-visit`; no free-form private subject becomes a shared
title. Suggestions may be independently supported actions, questions or mixed
service/promotional notices. Ordinary information/promotions are excluded from
Pending, including when safety is unknown. Mixed service evidence is not advertising
urgency. Important unknown/high-risk questions remain discoverable but cannot be
accepted as safe suggestions.

| Explicit operation | Effect |
| --- | --- |
| Review | Private actor annotation; no task or safety clearance |
| Defer | Private actor disposition; remains unresolved and in Pending |
| Needs information | Private actor disposition; remains unresolved and in Pending |
| Accept | Separate confirmation creates one shared task and marks the proposal accepted |
| Edit | Separate task-edit authority changes assignment/status on that same task |

Private reviewed/disposition fields are orthogonal to shared resolution. A new
review after acceptance cannot demote, cancel or recreate the task. Current
annotations are displayed only when their audit evidence binding matches; evidence
change or revert cannot transfer an old review or deferral to a new generation.
Private review history shows only the current actor's entries. The shared pending
CAS revision can change after another authorized actor's operation; it is a neutral
concurrency version, not permission to retrieve that actor's private annotation.

Acceptance requires explicit `confirm=True`, current source observation/security
access, current proposal-publication authority, independently supported clear
evidence and exact recipient-plan revisions. The command names one or two approved
read recipients, including its publisher in this narrow slice. Assignment is either
`joint` or a current independently approved adult recipient. A date is optional and
must exactly match the supported fictional date when explicitly approved; urgency
claims never generate one. Each recipient's edit/history rights are copied only
from its separate approved publication plan.

Tasks begin `pending`; `completed` records household tracking intent only. Neither
state means a payment, booking, message, quarantine or calendar operation occurred.
No cancellation, deadlines, reminders, execution engine or R2/R3 approval is added.

## Authorization-first projections

Pending requires both current G2a fixture source-observation access and independent
proposal-read rights, before SQL counts, filters, ordering or pagination. Safety is
selected with an authorized-source CASE expression and omitted for observation-only
readers; it cannot change their output, error or accept capability. Review needs its
own capability; acceptance additionally requires security and publication rights.

Task reads select only neutral task fields and current recipient rights. They do
not select private pending IDs, accepted evidence, contributor counts or source
state and do not join source/proposal tables. Source revocation or private evidence
changes therefore cannot change an independently authorized task projection,
warning, count, history or error. Task visibility revocation independently removes
that task. Task edit does not require source access and cannot expand it. Neutral
task history separately requires history permission and contains actual task actors,
operation, revision, timestamp and neutral field snapshots, never private review
events. This is one authoritative task state, not one task store per member.

Pages have deterministic resource-ID ordering, a limit of 1–20, offset 0–1,000,000,
authorized total and `has_more`. An optional fixed-step filter is applied after
rights filtering. Deferred/needs-information backlog remains pageable, including
beyond small demo display caps. History is bounded to 1–100 entries. These are
internal bounded operations; comprehensive history pagination and larger-household
capacity are future decisions. No private source content, links, source IDs or
undisclosed freshness warnings are returned in task fields.

## Atomicity, exact replay and uncertain commits

Every confirmed mutation runs in the existing household transaction: SQLite
`BEGIN IMMEDIATE` writer reservation; PostgreSQL household `SELECT FOR UPDATE`.
Lock order is household → current session/binding/membership → current resource
and specific grant → own exact request → CAS/evidence/recipient validation →
domain writes and actor event → session activity → commit. Approved fictional
evidence/grant provisioning uses this same household ordering. Privileged hostile
SQL writes bypassing the contract are not defended by this internal service.

Pending operations bind generation, SHA-256 evidence fingerprint and definition.
The trusted producer must advance generation and revision even for A → B → A.
Task acceptance stores its original binding permanently and never transfers that
acceptance to changed evidence. Subsequent independently authorized neutral tracking
continues without claiming new source evidence was approved. No automatic private
freshness warning is emitted; a future warning policy requires separate privacy
review. All new changes also require current entity and capability revisions.

Exact request replay is scoped to household/actual actor/request and full intent
hash. It returns historical `COMMITTED-replay`, not fresh approval. Changed intent
is `NOT_APPLIED-changed-intent`. Replay still requires current operation access;
even a known historical task ID is withheld after independent task visibility
revocation. Concurrent acceptance/edit permits one committed change; the other
conflicting command is stale. Identical concurrent submissions converge to one
event and task. Existing events are never updated by service operations.

Cancel/nonconfirmation makes no database change. Definite prewrite authorization
rejection is `NOT_APPLIED-unavailable`; stale CAS is `NOT_APPLIED-stale`. Unexpected
database/transaction-exit failures, including potential commit-ack loss, return
`UNKNOWN-reconciliation-required` without driver detail. A controlled synthetic
fault test commits then loses acknowledgment; this is not proof of arbitrary
real-network failure detection.

`verify_outcome` opens a fresh same-primary physical connection, revalidates current
session and operation scope, and checks the exact protected ledger. Matching
committed intent proves historical COMMITTED; established absence proves
NOT_APPLIED; changed intent conflicts; unavailable/inconsistent evidence stays
UNKNOWN. It never reapplies/rebases a write, invents a new request or recovers a lost
session secret. Do not blindly repeat an UNKNOWN action with a new request ID.

Read/revoke tests verify database ordering: a read already holding the household
lock can finish before revocation commits; subsequent reads enforce committed
revocation. No reusable client permission lease is granted. Built responses cannot
be recalled, and network dispatch/cache invalidation remain unimplemented gates.

## Future unified UI data contract

| Area | Future input and T1 status |
| --- | --- |
| Home | Authorized task/Pending totals over the same household state; no new Home UI |
| Tasks | Neutral `TaskView`: task ID, fixed step, assignee, tracking state, optional approved date, revision and current capability flags |
| Pending Confirmation | `PendingView`: stable proposal ID, exact authorized binding, support, own review/disposition and available capabilities; no inbox mirror |
| Calendar | Separate future authorized calendar projection; T1 does not create calendar entries |
| Security Review | Separate source-security boundary; unknown/high-risk blocks acceptance, no detector/quarantine/restore integration |
| Information/Offers | Future quiet/on-demand reads; ordinary promotions/information do not become T1 review obligations |

`Command` expresses only one explicit operation with expected revisions and bounded
identifiers; a display flag does not grant authority. Source evidence and neutral
task publication are different contracts. H1/H2 remain unchanged and disconnected;
H2's published neutral preview steps are not T1 accepted tasks.

## Fictional walkthrough and validation

Run `.venv/bin/python -m pytest -q tests/test_household_tasks.py` in the developer
environment. The compact `test_compact_household_walkthrough_persists_after_service_recreation`
walkthrough proves: fictional school suggestion → Adult A reviews/no task → Adult B
explicitly accepts → one persistent shared task → Adult A changes assignment/status
→ Adult B sees the same revision after service recreation. Tests also cover current
session/member/binding revocation, private evidence changes/reverts, independent
task-grant revocation, concurrency/replay, rollback and ambiguous commit recovery,
privacy before SQL projection, backlog overflow, migration roundtrip/metadata and
no provider/network/production wiring. All 67 focused T1 tests passed on SQLite and
real PostgreSQL 16. Both include the T1 downgrade/upgrade and Alembic metadata check;
the full regression also exercises upgrade/downgrade to base/upgrade. See the PR for
exact final full-suite and GitHub CI counts.

## Remaining decisions and independent-review questions

Before real enrollment or UI/API integration: approve real OIDC/MFA/session and
entrypoint authorization, authenticated proposal/publication/grant management,
monotonic evidence producer, neutral-field privacy/retention, database role/audit
tamper protection, backup/rollback, response-dispatch revocation and optional
authorized freshness warnings. This slice supplies no real task extraction, AI,
canonical dedupe, notifications or provider-operation authority; Alternative B
remains disabled. No real household data is read or sent to any model.

ChatGPT and Muse should independently check: (1) Can any review or unsafe evidence
create acceptance? (2) Can another member's private evidence/history affect a task
view after source revoke? (3) Are publication, task edit/history and current session
rights independently enforced within the transaction? (4) Do exact replay and
changed/reverted evidence preserve history without renewed authority? (5) Does an
uncertain commit remain UNKNOWN until same-primary evidence proves its outcome?
(6) Are migration rollback loss and unimplemented deployment/response gates clear?

The subsequent [I3 fictional browser connection](stage-i3-readonly-task-workbench.md)
uses these unchanged task reads over I2's controlled loopback boundary. It adds no
production task access, write route or private provenance projection.

[I4a](stage-i4a-safe-pending-acceptance.md) adds an internal `prepare_acceptance`
read operation and shares the existing acceptance-plan validator with apply. It
returns a server-side immutable command, not new permissions; the isolated browser
adapter retains it behind a session-bound receipt. Original explicit apply, SQL
CAS, actor audit and UNKNOWN verification semantics are preserved.

[I4b](stage-i4b-safe-task-editing.md) adds internal `prepare_edits` and a shared edit-plan
validator. Prepared commands additionally pin ordered current recipient grant/member
revisions in their intent hash; legacy internal commands retain their hashes. Current
recipient changes/reverts invalidate prepared edits. The new runner alone exposes these
confirmed fictional tracking edits; task/source permission independence and original
CAS, audit, replay and UNKNOWN semantics remain. No migration or production task access.

## I8 opt-in extension

[Personal not-applicable/resume](stage-i8-personal-not-applicable-resume.md) adds
`i8-personal-v1` without changing old Command intent bytes. New operations bind
source-grant revisions and preserve independent reviewed/disposition state. Fresh
personal decisions on accepted Pending are now rejected, including the former
internal-only fresh REVIEW case; the existing regression is strengthened to require
no event and unchanged Task. Historical exact replay remains access-checked.
