# Family OS v0.1 / Stage C — isolated synthetic action-first UX

## Scope and status

`synthetic-action-first-demo-v2` is a disposable local terminal demonstration of
[Slice 3](v0-1-action-first-routing-email-safety.md), reusing the unchanged
[Stage A routing/authority](v0-1-synthetic-routing-contract.md) and
[Stage B safety/recovery](v0-1-synthetic-phishing-policy.md) contracts. It follows
the [Slice 2](v0-1-single-user-review-demo.md) opt-in, bounded-input, explicit-save
and safe-error patterns, but has **no database**, including no temporary SQLite
store. It does not import Slice 1/2 persistence or Phase 2U/2V interpreters.

This is not an Inbox, task manager, detector, authenticated household client or
production service. No Stage D, real-mail pilot, notification, provider operation,
framework or new dependency is implemented. One-backend/multi-client architecture,
centralized R0–R3 policy and independent per-mailbox consent remain future gates.

Ten newly invented English cards are authored directly in the module. No real
subjects, private metadata, credentials, Finance records, human labels, frozen
Development/Holdout or earlier evaluation corpus is read. No AI/LLM/Ollama, network,
URL inspection, redirect, attachment or HTML operation exists. No household data
enters any AI. `DATABASE_URL` and other database configuration are ignored, not read.

## Run locally — Windows PowerShell

From the repository root using the existing Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe -m family_os._synthetic_phishing_demo --help
.\.venv\Scripts\python.exe -m family_os._synthetic_phishing_demo --synthetic-only
```

The **exact sole flag** `--synthetic-only` is required before contract imports or
scenario initialization. Wrong flags, extra arguments, paths and URLs are rejected
without echoing them. Help initializes nothing. There is no production `family-os`
command, file input/output or DB option. Do not migrate/register/connect anything.
All state lives in memory and is discarded on quit, EOF, interruption or failure.
Restarting begins with no decisions or simulated moves. Crash recovery is not promised.

## Five views and the retained backlog

| Home command | View | Admission and meaning |
| --- | --- | --- |
| `todo` | My To-do | Explicit simulated accepted steps only; old acceptance remains with an evidence-change warning, never current authority after a new episode |
| `pending` | Pending Confirmation | Supported but unaccepted steps, ambiguous/conflicting service questions and unassessed household evidence; promotion-only safety uncertainty is excluded |
| `security` | Security Review | Suspicious/high-risk and indeterminate items; includes legitimate important notices and outage cases, not just malicious examples |
| `information` | Information | Quiet sufficiently assessed non-action information; no provider archive operation |
| `offers` | Offers | This command is the explicit offer-query intent; only current permitted quiet promotions, never a held promotion or mixed service question |

Views may overlap: an important indeterminate bank notice appears in Pending and
Security; historical acceptance with unsafe new evidence appears in My To-do with
a warning and Security. These are three independent dimensions, not exclusive bins.
Authentication pass, familiarity and earlier release are supplied even for held
scenarios and cannot override their independent risk finding. An expired offer is
quiet; it creates no task, alert or urgency. No card initializes as accepted.

Security assessment and actionable household review are distinct. A promotion with
neither independently important service evidence nor a supported action does **not**
enter Pending merely because safety is unknown, unavailable or stale. It remains
retained and accessible in authorized Security Review, with no offer, task or
clearance implied. A mixed service/advertisement may still enter Pending when its
independent service importance or supported action warrants a household question;
suspicious/high-risk safety still takes precedence. Advertising urgency, expiry and
unsupported action claims cannot supply that evidence. A new, adequately assessed
revert may return the ordinary promotion to explicitly queried Offers, never Pending.

The **demo-only display cap is two cards**. Each view shows its authorized retained
count, count outside the displayed page and page number. `all` (View all pending)
and `next` advance one page; `previous` returns. Continue until the last page to
inspect the whole retained set. Page-end navigation never discards an item. Defer,
repeated browsing, overflow, uncertain importance and detector outage do not resolve
or delete anything. There is no production age threshold, deadline inference,
re-presentation timer, scheduling or notification cadence.

Nine source-A cards are initially accessible. An independent fixed source-B card is
internally present but denied. It has no placeholder, title, count, navigation slot,
history or summary contribution. `revoke` then `confirm-revoke` revokes source A for
the remainder of the session; all subsequent projections, histories and aggregates
recheck the declared grants and become empty. There is no UI grant-sharing mechanism,
authenticated person, or emergency override. Declared enums are a synthetic harness,
not proof of real authentication or dispatch/revocation-race safety.

## Separate intentions and exact binding

Select `1` or `2` on a page. Inspection, history and navigation do not save.
`b`/`back` goes to the previous logical prompt; `c`/`cancel` discards the unfinished
intention and returns to the card/view. `q`/`quit`, EOF and Ctrl+C exit the session.
Each operation has its **own** confirmation phrase; plain `save` grants nothing.

| Card command | Required confirmation | Result |
| --- | --- | --- |
| `review` | `confirm-review` | Supported clear step only: append review agreement, never task acceptance or acceptance withdrawal |
| `accept` | `confirm-accept` | Separately append simulated acceptance for supported clear step only; no actual task/execution |
| `defer` | `confirm-defer` | Append unresolved deferral; retained in its views, no invented revisit deadline |
| `quarantine` | `confirm-quarantine` | Separate gate prompts and a simulated outcome, never a mailbox move or action approval |
| `restore` | `confirm-restore` | Fresh independently prompted state/retention/outcome gates; no clearance or acceptance from restoration |
| `change` / `revert` | `confirm-change` / `confirm-revert` | New monotonic evidence episode, preserved history; change models missing safety; revert uses original evidence at a new episode |
| `replay` | `confirm-replay` | Acknowledge last exact saved request, no new annotation; historical acknowledgment never resolves newer evidence |

Recovery asks separately for simulated provider state (unchanged/user-changed/unknown),
retention and recovery-record verification (verified/uncertain), and observed outcome
(verified/failed/unknown). These are authored synthetic selections, not real checks.
Back revisits the preceding gate, including from confirmation; Cancel/EOF saves none
of them. Unknown/failed outcomes remain explicit, never claimed success. Later user
changes, retention uncertainty, new evidence and unverified prior moves block restore.
An existing quarantine trial cannot be blindly repeated; a previous restore outcome
cannot be retried into success. Full reconciliation is deliberately absent.

The adapter delegates routing/decisions to Stage A and evaluation/recovery to Stage B.
Its Stage A/B mapping is confined to this private demo. Each card is an independent
fixed synthetic namespace; the card enum supplements the contracts' intentionally
small source/item enums. No cross-card identity, canonical dedupe or task identity
is inferred. A command binds card, exact displayed case/evidence/recovery/deferral,
revision, monotonic episode, policy and bounded per-card request number. The displayed
state is captured **before** collecting the intention or recovery choices. Commit
rechecks source access, exact state and revision; stale attempts write nothing.

Immutable events append; old case decisions and simulated outcomes are not edited.
Each card is limited to 32 events independently of inaccessible history. Matching
request replay returns an acknowledgment without consuming capacity; a changed
command using that number is rejected. Old exact request replay can acknowledge
history but cannot restore authority. Review after acceptance preserves acceptance
only for that exact current assessment. Evidence changes/reverts and safety/policy
episodes invalidate it; historical My To-do entries carry a warning until separately
accepted against current evidence. No cancellation/completion/task lifecycle exists.

Session totals contain only counts of currently authorized saved annotations,
acceptance annotations and recovery annotations. They are historical annotation
counts, not current task counts, successful moves, accuracy or productivity measures.
Permission revocation filters those counts without deleting internal history.
Input is bounded to 64 ASCII characters; oversized input ends the session to prevent
truncated tails becoming confirmations. Invalid input is not echoed. Unexpected
failures produce a generic error and dispose the session without claiming success.

## Repeatable manual walkthrough

1. Start a fresh demo. `pending` shows four retained questions with two on the first
   page. Select `1` (equipment return), `review`, `confirm-review`. Read the card:
   review is confirmed but no acceptance. `back`, `back`, `todo` shows no steps.
2. Return Home with `back`, then `pending`, `1`, `accept`, `confirm-accept`.
   `history` shows two distinct annotations. `replay`, `confirm-replay` acknowledges
   the same request without a new revision. Another review does not revoke acceptance.
3. On that card, `change`, `confirm-change` shows missing safety and a historical
   evidence-change warning. `revert`, `confirm-revert` restores the original fields
   in a new episode, **not** old acceptance. Back to Home, `todo`, `1` shows the warning;
   separately accepting that new clear episode is a new intention.
4. Home → `pending` → `all` reaches the second page. Select `2` (conflicting workshop),
   `defer`, `confirm-defer`. Back/previous/next still find it and its history. Bank
   outage appears in both Pending and Security; it is never quiet information.
5. Home → `security` → `2` (invented legitimate clinic falsely held). `quarantine`,
   `unchanged`, `verified`, `verified`, `confirm-quarantine` records a simulated move.
   `restore`, `user_changed`, `verified`, `verified`, `confirm-restore` is **BLOCKED**,
   not restored. Restart for independent trials with `failed` or `unknown` observed
   outcomes, or fully verified unchanged gates; none grants acceptance or sender trust.
6. Home → `offers` explicitly queries the expired gardening offer. The compromised
   reward promotion is absent; inspect it on Security's second page instead. Back,
   Cancel, EOF or Quit before any confirmation creates no annotation.
7. Home → `revoke` → `confirm-revoke`, then browse all views: zero permitted backlog,
   no card/title/history disclosure. Quit prints only currently authorized totals.

Promotion regression walkthrough (fresh session): `offers` → `1` → `change` →
`confirm-change` → `back` → `back`, then `pending` and `all`/`previous`/`next`.
Its retained household backlog stays four; the gardening advertisement is absent.
Home → `security` → `next` → `2` reaches the unassessed promotion for authorized
inspection/history. `revert` → `confirm-revert` restores adequate current assessment
in a new episode; it returns only to explicitly queried Offers. It creates neither
a household review obligation nor acceptance. The important mixed service/ad still
remains a Pending question when its household evidence applies.

Stage B's authored **6/10 important legitimate-mail hold/indeterminate proxy** is a
design stress case motivating discoverability and safe recovery. It is not a live
metric, production target, detector claim or permission to loosen security. This
demo deliberately includes legitimate urgent school, healthcare and financial
service notices that can be incorrectly held or remain unassessed.

## Validation, limitations and review questions

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_phishing_demo.py tests/test_synthetic_routing.py tests/test_synthetic_phishing_policy.py tests/test_synthetic_review_demo.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Tests use new synthetic interaction scripts only. Stage A/B policy implementations
and retained behavioral tests are unchanged. Stage A's isolation guard adds exactly
one private adapter exception; new AST/fresh-process guards verify its two gated
contract imports and absence of production wiring. Actual focused and full
SQLite/PostgreSQL 16 counts and job evidence are recorded in the PR after execution.
Those full-suite databases are existing dedicated disposable synthetic test stores;
the demo itself never connects to them.

Focused validation: **2,402 passed**, including 258 new Stage C interaction cases,
all 1,237 Stage A cases, 822 Stage B cases and 85 Slice 2 demo cases. `pip check`
and `git diff --check` passed. The first test collection caught an unmatched
parenthesis in the new test file; it was corrected before these passing runs.

Limits: no persistent ledger, crash durability, multi-process CAS, real principal,
concurrent provider-state verification, security efficacy, deadlines, retention
guarantee or automatic quarantine readiness. The single-threaded check/append models
stale-display handling, not distributed transactions. Direct hostile Python code can
forge synthetic grants/state; this is not a sandbox. No real data trial or Stage D
is approved. All future auth, consent, provider/write, persistence, reconciliation,
UX accessibility and production task identity choices require separate review.

ChatGPT and independent Muse should review:

1. Does exact opt-in precede initialization, with no production/database/model input?
2. Are view counts, card navigation, histories, summaries and saves permission-first,
   including after revocation, with no hidden population contribution?
3. Are review, simulated acceptance and simulated recovery independently confirmed,
   with no shared Save or implication of task/provider authority?
4. Do display-bound stale checks, historical replay and new/reverted episodes retain
   history without transferring acceptance or overwriting later user changes?
5. Does the capped/paginated backlog keep deferred and important uncertain notices
   discoverable while quiet/suspicious promotions cannot become alerts or tasks?

Leave the PR unmerged for ChatGPT review, independent Muse review and human manual merge.
