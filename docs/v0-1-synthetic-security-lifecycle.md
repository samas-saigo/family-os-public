# Family OS v0.1 / Stage E2 — disposable synthetic security lifecycle

## Scope, lineage and approval

`synthetic-security-lifecycle-v2` follows merged E1 PR #71 at main commit
`d1233d5bd876c8ae387d8976e32c646db0b0dc1f`.
It is a private, in-memory, deterministic research module with no production wiring.
`Session(..., synthetic_only=True)` requires an exact opt-in before initialization;
False, strings and integer 1 reject. Closing the session clears its owned objects, receipts,
grants, intent/result events, sharing terms and checks. There is no persistence or
secure memory erasure; caller-held immutable synthetic snapshots remain ordinary
Python values until discarded. Process/session disposal is not a real retention policy.

Read alongside [E1 authority and conflict policy](v0-1-security-action-authorization.md),
[Stage D household-first contract](v0-1-household-first-authorization.md),
[Slice 3 safety design](v0-1-action-first-routing-email-safety.md),
[Stage A](v0-1-synthetic-routing-contract.md), [Stage B](v0-1-synthetic-phishing-policy.md),
[Stage C](v0-1-synthetic-action-first-demo.md),
[architecture](architecture.md#5-deployment-and-client-architecture) and
[security](security.md#shared-action-decisions-and-notifications).

No real household metadata, mail, credentials, frozen Development/Holdout, provider
SDK, network, OAuth, AI/Ollama, database, worker, production authentication/API,
task, payment, notification or real quarantine/restore exists. There is no Stage F.
R0–R3 is unchanged: reversible mailbox writes would require their own authority.
Alternative B standing consent remains **DISABLED and unapproved**. E1 eligibility
authorizes only this explicitly opted-in fictional simulation, not a real executor.

## Values, new scenarios and E1 reuse

New enum-named fictional scenarios describe a Heron School response and Juniper Clinic
notice, including independently labeled legitimate-important false positives in tests.
They map into E1's closed household/source/provider/object vocabulary to reuse its
unchanged preflight. Neither the Stage B corpus nor frozen model datasets are inputs.
Scenario truth is outside the preflight and never influences authorization.

The sole runtime dependency is the private E1 module plus `dataclasses`/`enum`.
E1 code and retained behavior are untouched; its static isolation test admits exactly
this opted-in research consumer. Stage A/B/C code/tests are unchanged.

Physical fictional state has a fixed source-object identity, folder/label enum,
monotonic generation/version, object-local reservation revision, owner-change epoch
and fictional mutation counter. Actor/request/approval metadata in a Binding is not
physical identity or task authority. Counts use E1's exact authorized source-object
key, never title similarity or action-attempt identity.

Checks are out-of-band **declared fictional verification** values, not genuine evidence
or a detector. Policy/check injection methods are harness controls, not authenticated
client endpoints. The simulator rebuilds E1 Context from current stored physical state,
current effective rights, central policy, approvals, assessments and latest per-attempt
outcomes. Caller-provided current-provider state cannot replace these stored facts.

## State sequencing and append-only history

| Path | Required sequence / distinct result |
| --- | --- |
| Quarantine | Proposed → explicit assessment/approval → preflight eligible → intent reserved → simulated dispatch → verified quarantine, failed or outcome unknown |
| Missing approval | Awaiting explicit authorization; reserve/dispatch cannot skip approval |
| Restore | Restore requested → separate fresh assessment and restore approval → eligible → reserved → dispatch → verified restore, restore failed or restore outcome unknown |
| Stale or invalid preflight | Stopped before dispatch / restore blocked; no fictional mutation |
| Uncertain or failed outcome | Explicit reconciliation-required event followed by verified observed effect, verified failure/no-effect or still-unresolved state |
| Cancel | Proposed/awaiting/eligible/reserved can stop; no dispatch or implicit restore |

Every state transition appends a frozen Event. The latest Attempt is an immutable
projection replaced in memory; previous Events and returned snapshots stay unchanged.
Intent includes the entire exact E1 binding and original-quarantine reference for
restore. Approval and independent assessment bind that same intent. A request key is
household/source/principal/request scoped, not task identity.

Exact proposal replay returns existing state/revision without a new event or mutation.
Changed intent or changed original reference under that key rejects. Dispatch can
only consume Reserved once. New keys cannot bypass unresolved same-object effects.
An existing reservation cannot be displaced by a later proposal, even by the other
authorized peer. Revisions reject stale method calls and controlled competing intents.
No global session revision or hidden-source counter is exposed. A reservation event
is historical intent, not a continuing grant: a revoked/stale reservation cannot execute
or block a newly explicitly authorized peer intent. Still-current reservations and
unresolved dispatched effects cannot be displaced. A source-denied caller receives no
status disclosure; its stored intention is not implicitly granted authority again.

All required E1 checks run again immediately before reservation and fictional dispatch:
read/operation rights, consent/source revisions, exact evidence/assessment/approval,
policy, physical state, recovery/retention, conditional-write, emergency stop and
reconciliation readiness. Event capacity and version bounds are checked before a
fictional effect. A source-specific stop blocks only that source's queued/future work;
it does not grant undo authority or hide the other authorized mailbox.

## Fictional provider outcomes and independent inspection

The fixed fault choices are success, definite no-effect failure, conditional conflict,
timeout before effect and timeout after effect. Only success/timeout-after apply the
attributable folder move. Labels stay unchanged. Physical generation/version advance;
Junk/Trash or a purging target cannot be assumed recoverable.

The fake provider records a separate immutable before/after receipt. Response failure
and timeout do not determine effect. Reconciliation checks that receipt and current
physical state using a separately requested fictional inspection. Unknown/stale/
unavailable inspection, lost recovery facts or conflicting later user state never
earns success credit. Receipt verification is within one simulation, not independent
real-world channels or provider atomicity. No URL, remote API or actual write occurs.

Timeouts stay unknown until explicit reconciliation; dispatch cannot blindly retry.
Failed/no-effect attempts remain terminal blockers under E1's conservative episode
rules. E2 does not invent a retry policy or discard a failure record to enable another
mutation. Further causal reconciliation when receipts/state disagree is unsupported
and stays unresolved, rather than guessing success or automatically undoing changes.

## One episode, attributable restore and later user changes

Only one quarantine episode per source object is supported. A later owner move or a
new key cannot authorize another quarantine episode. Restore must reference the exact
stored verified quarantine; E1 requires complete single-episode history and strictly
newer synthetic generation **and** provider version. These integers have no claimed
relationship to real Gmail/Outlook conditional tokens.

Fresh independently declared clear/false-positive evidence and separate restore consent
are mandatory. Reverse only the recorded move into the original folder, with unchanged
labels. The stored owner-change epoch detects any subsequent owner edits, including
move/label changes later reverted to the same apparent state. Such restoration blocks.
Read-only peers cannot invoke the owner-change control or borrow another actor's approval.
Source-specific write consent may nevertheless independently authorize a peer's Family
OS simulated operation; source-controller capability is not a household hierarchy.

A verified restore cannot be repeated under a new actor, key or generation. Unknown
restore/no-effect/failure history remains protected and requires reconciliation. No
automatic release at age, sender trust, task acceptance or task creation follows.
An important legitimate notice incorrectly held remains in authorized object/history
views and can take the separately approved restore path; no detector efficacy is claimed.
Stage B's 6/10 important-mail proxy remains a synthetic usability warning only.

## Household sharing, revocation and modeled notices

Both peers share one authoritative session and see all effectively authorized sources,
with source-object counts independent of actor/attempt. E1's rights conflict rule is
used: identical duplicates are harmless, distinct assertions for one key fail closed.
Unauthorized or ambiguous sources do not affect the other member's counts, histories,
status probes or source-local revisions. Hidden unknown outcomes have no withheld count.
A source permission conflict cannot suppress an independent permitted mailbox.
Summary counters explicitly separate unique objects, unresolved attempts, failed
attempts and historically verified quarantine/restore attempts. Historical verification
is not current folder state or a continuing recovery guarantee; inspect the permitted
physical snapshot separately. Unknown effects never increment verified counters.

Fictional controller capabilities are fixed per source (Oak/Aster, Pine/Robin), not
primary/secondary household roles or authentication. Grant changes bind expected current
revision. Submitted is explicitly **not committed**. Successful commit appends old/new
values; stale, ambiguous, invalid or capacity-limited changes return prominent
`NOT-APPLIED` results without partial grants. Revoke versus expansion interleavings
allow one commit only; no automatic rebase or resurrection after revocation.

One-time sharing terms explicitly bind household, source, named recipients, revisions,
fields, purpose, permitted operations, retention and revocation. The closed fields
profile is only fictional source/object IDs, physical folder/label/version values and
scoped action/actor/revision history. Purpose is household security review. Operations
are read/review only; sharing cannot add mailbox mutation rights. Previously independent
operation consent is not silently expanded. Retention terms mean disposable session
lifetime only, with no crash/after-close guarantee; revocation requires a committed
version change. Unknown/incomplete terms or stale recipients reject atomically.
Cancel adds no grant; successful terms are retained as immutable session audit values.
Ordinary authorized summaries/reads require no recurring sharing confirmations.

Prepared notices contain enum-only source references, not message text or active links.
Inspection/fictional delivery permission rechecks recipient, effective grant revision
and current object snapshot. Revocation or state change after preparation suppresses
the entire notice; another member cannot open it. This models checks, **sends nothing**
and emits no private preview, suppressed count or source-existence alert.

Task sharing is independent and **not implemented** here. The one-time freshness-warning
timing signal after source revocation remains an unresolved/unapproved policy tradeoff.
No task warning is emitted, and private source changes do not alter another member's
observable session summaries. Source-revoked actors cannot inspect/reconcile hidden
outcomes. A still-authorized peer may inspect the shared history; changing its result
requires **separate explicit source-scoped reconciliation permission**.

### Reconciliation authority and actor attribution

Current source-read rights and an explicit `ReviewerRights` ALLOWED assertion for the
exact household/source/principal are both required before attempt lookup, revision
validation or outcome disclosure through reconciliation. Read access, operation consent,
OAuth, sender familiarity and household membership never imply reviewer authority.
The trusted fictional harness supplies at most four current reviewer assertions via
`reviewers=()` (default denies all) or `configure_reviewers()`. Missing, unknown,
revoked or contradictory assertions fail closed; consistent duplicates are harmless.
Replacement is a harness-only current snapshot, not a grant store, trusted timestamp,
authentication system or approval mechanism. No per-message reviewer prompts exist.

An explicitly authorized peer can reconcile an ambiguous result after the initiator
loses source access, provided the reviewer retains current source access and independent
reviewer permission. Revoking either prerequisite withholds the result and causes zero
transitions, even for absent attempts or malformed expected revisions. This capability
only records inspected outcomes: it grants no quarantine/restore consent, dispatch,
blind retry, automatic restore or universal trust. Unknown/stale/conflicting inspection,
missing recovery data or receipt/state disagreement leaves reconciliation unresolved.

Every append-only `Event.binding.principal` preserves the initiating principal;
`Event.actor` separately records the actual caller performing each transition, including
cross-peer reconciliation and its verified result. Ordinary proposal/approval/dispatch
remain initiator-only. Both peers see the same source-authorized history, not separate
security histories. Returned historical events remain immutable.

## Recovery loss and limits

Retention stale/unavailable, deletion-obligation conflicts, lost original delta facts,
purging locations and failed readiness checks stop new quarantine/restore. Unknown
effects stay unresolved if their basis is unavailable. Emergency disable does not
delete records, erase uncertainty or auto-restore. No real retention/deletion policy
is implemented; no indefinite retention is assumed.

Harness envelopes are at most eight unique objects and four rights assertions.
Attempts are at most eight per source/household, action events and grant changes at
most 64 per source/household, and revisions obey E1's 1–1,000 bounds (zero initial
local counters). Caps follow access for operator calls and are source scoped, so hidden
mailboxes cannot consume another source's observable quota. Initial harness validation
is trusted fictional setup, not a privacy-safe production upload endpoint. Session
closure is explicit disposal, not a real retention/deletion workflow.

This is single-threaded controlled interleaving, **not** thread safety, database CAS,
crash durability, authenticated grants or real provider atomicity. Private Python
attributes are not a hostile-code sandbox. Synthetic fixtures/proof declarations
cannot establish production safety or consent. Failed terminal episodes, multi-episode
operation and ambiguous receipt attribution intentionally remain unsupported.

## Validation and developer usage

From the repository root with Python 3.12:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_security_lifecycle.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_security_lifecycle.py -k complete_single_episode
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_security_lifecycle.py tests/test_synthetic_security_preflight.py tests/test_synthetic_routing.py tests/test_synthetic_phishing_policy.py tests/test_synthetic_phishing_demo.py
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The single-episode test is a repeatable quarantine → independent verified outcome →
fresh explicit restore → verified own-delta reversal walkthrough. All state is invented
and discarded; no operator database, live model or provider is required. Full existing
SQLite/PostgreSQL 16 regressions use disposable synthetic stores; never supply a real
household database. Head-specific counts and actual CI results belong in the PR.

Review questions: Are all dispatch paths fresh and explicitly authorized? Can any
replay/interleaving create a duplicate effect or steal a reservation? Does unknown
delivery remain unknown until adequate inspection? Are user changes/reverted evidence
and repeated episodes safely blocked? Are all views access-first yet household-complete?
Are setup/NOT-APPLIED feedback, recovery limits and warning timing honest? Is E1 reuse
isolated without claiming genuine authorization, durability or real-mail readiness?

Leave the PR **open/unmerged** for ChatGPT review, independent Muse security review
and final human-controlled merge. No automatic standing-consent or real-mail rollout.
