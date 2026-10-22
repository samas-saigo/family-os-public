# Family OS v0.1 / Stage A — isolated synthetic routing contract

## Scope and status

Implements only Stage A of the merged [Slice 3 design](v0-1-action-first-routing-email-safety.md#staged-follow-up-and-unresolved-decisions).
Contract: `synthetic-routing-v2`. The private module
`family_os._synthetic_routing` imports only standard-library `dataclasses` and `enum`.
There is no CLI, UI, provider/client, classifier, database, file loader, environment
lookup, network/model transport, production service integration or import-time I/O.
Slice 1/2 are neither imported nor redesigned; their persistence remains unchanged.

This is a deterministic table of **authored synthetic inputs**, not a phishing
detector or classifier. No real mail, household metadata, human labels, Finance
records, frozen Development/Holdout or existing model fixtures are inputs. No data
is sent to any AI, including local Ollama. Twelve newly invented English walkthroughs
live only in the unit tests; they describe enum probes, not text to be classified.
Their hypothetical safety/action evidence does not claim current ingestion can
observe it or establish detection efficacy.

## Three independent dimensions

- **Safety:** adequate evidence/no detected risk (`SAFE_TO_ROUTE`, not a guarantee),
  suspicious, synthetic high-risk, unknown, unavailable or stale.
- **Business evidence:** promotion, action support (none/supported/unsupported/conflicting),
  importance (important/not-important/unknown), informational flag and offer expiry
  (none/upcoming/expired). Flags allow service/promotion overlap without dedupe.
  `IMPORTANT` specifically means independently evidenced **non-promotional service
  importance**, not an advertising urgency/expiry claim. This is a supplied synthetic
  signal; no text parser or model infers it here.
- **Human authority annotation:** none, review-confirmed or explicitly simulated
  acceptance. Every annotation is non-authoritative and has zero execution rights.

All inputs are frozen values using exact enum types, booleans and bounded integers;
no arbitrary strings, dictionaries, subject, sender, URL, body or provider payload
can enter the contract. Identity consists of two fixed household surrogates, two
source surrogates and two item surrogates. These are not people, mailboxes or verified
provider identities. A declared `Access` grant models an access outcome in tests;
it is not authentication, consent or a production authorization mechanism.

### Precedence

| Order | Condition | Result |
| --- | --- | --- |
| 1 | Denied, unknown, revoked or wrong household/source grant | `None`, with no identity, reason, history, placeholder, link or count |
| 2 | Assessment has different exact snapshot or policy | Stale safety; unassessed abstention; no offers or current authority |
| 3 | Suspicious or synthetic high-risk | Synthetic security **view hold**, before every suggestion or offer |
| 4 | Missing/unknown/unavailable/stale safety | Unassessed abstention, not clearance or quiet archive |
| 5 | Supported action with adequate current safety | Pending suggestion; only separate explicit synthetic acceptance changes the simulated annotation |
| 6 | Unsupported/conflicting action with adequate current safety | Pending clarification; concrete confirmation/acceptance blocked |
| 7 | Independently important service evidence, including an overlapping ad without a known action | Pending service clarification; no concrete action invented, no surfaced offer |
| 8 | Promotion without a separate action signal or independently important service evidence | Quiet promotions; visible as an offer only under an explicit offer-query intent |
| 9 | Importance-unknown non-ad item | Pending clarification, never an invented deadline or immediate alert |
| 10 | Explicit informational, not-important non-ad item | Quiet information view, never provider archive |
| 11 | Remaining insufficient business evidence | Unresolved abstention |

An offer query cannot bypass security, access, stale safety or a pending service
question. A promotion-only item cannot be reviewed as a supported action or accepted.
Expiry never changes routing or creates urgency. Mixed service/advertising evidence
is conservatively routed to the separate pending service question, with no surfaced
offer. There are no dates or urgency-text parsing in this contract.

In particular, `promotion=True`, `action=NONE`, `importance=IMPORTANT` preserves the
separately evidenced service question in Pending rather than hiding it as an ad.
The absence of a supported action still blocks concrete review/acceptance. An ad's
deadline language or expiry cannot supply `IMPORTANT`; with importance unknown or
not-important and no separate action, it stays quiet. Safety and access take precedence
over all these cases. This clarifies existing enums without adding a new signal.

Every projection has immutable `proactive_alert`, `creates_task` and `provider_write`
properties equal to **false**. Nothing sends notifications, creates tasks, performs
quarantine/restore, saves a decision to storage or modifies another system. The
`SIMULATED_ACCEPTED` destination is an annotation, not a task or canonical obligation.
Security holds are non-authoritative simulated view states, not mailbox movement.

## Exact evidence and policy binding

A snapshot binds household/source/item, a positive generation (1–1,000), fixed
evidence enum and all business fields. An assessment additionally binds the exact
policy enum and safety outcome. A decision binds that entire assessment. Current
authority requires exact equality, not similar evidence, titles or timestamps.
Foreign-source/item history cannot establish authority or an acceptance warning.

`advance` returns a new observation generation and removes the old safety assessment,
preserving the immutable history tuple. A revert restores original enum values at a
**new generation**, never the original generation. `reassess` also advances generation
for a new safety/policy evaluation episode, even when the policy/outcome is unchanged
or later reverted. This counter represents a synthetic observation/assessment
episode, **not** a production raw-record ID or cursor format.

Old decisions remain historical. After change/revert, fresh adequate safety may permit
a new pending suggestion, but cannot restore old acceptance. Projections for the
authorized source retain a historical-acceptance/revalidation annotation; they do
not silently complete or delete anything. Suspect/unavailable safety overrides an
existing simulated acceptance. Without separate acceptance for the current assessment,
explicit review confirmation remains pending, even after repeated confirmations; it
never becomes acceptance. Once explicit simulated acceptance exists for that exact
assessment, later ordinary review confirmations **preserve it** and do not set
revalidation merely because a review was appended. Reviews neither grant nor withdraw
acceptance. New evidence/safety/policy episodes still invalidate old current authority.

`decide` requires current adequate safety, supported action, matching access and the
explicit confirmation enum. It returns a new case with one appended decision,
bounded to 32 decisions; failure leaves the original untouched. Among exact matching
annotations, any explicit simulated acceptance takes precedence over review-only
annotations. Historical reviews are still appended, never rewritten. There is no
withdrawal/cancellation transition or task lifecycle in this contract.
Unconfirmed input is rejected. The caller can continue inspecting the unchanged case;
there is no interactive save, persistence, queue or production replay/CAS service here.

This pure research contract trusts its synthetic harness to use monotonically new
episodes and declared grants. Arbitrary Python code can construct an old case or forge
an allowed enum: the module is **not** a security sandbox, receipt authenticator or
proof that live authorization/version races are solved. Production principal checks,
storage/CAS, idempotency, audit and revocation need separately approved contracts.

## Fixtures and validation

New probes cover optional ribbon promotions (including expiry), a suspicious promotion,
an ambiguous art-club notice, a supported library pickup suggestion, unavailable
assessment, a mixed service/ad, high-risk action evidence, quiet information, unknown
importance and conflicting instructions. Independent tests cover unauthorized sources,
changed/reverted evidence, policy/safety reverts and immutable history. No external
fixture is read and no existing frozen dataset is edited.

The exhaustive enum matrix covers all 144 business combinations against all six safety
states and both inspection/query intents. Other matrices cover permission/household/
source/safety combinations and action/safety/authority/confirmation gates. Tests also
exercise bounded fields/history, generic errors without logs, no production wiring,
both AST import forms and successful pure execution with filesystem/network calls
blocked. These are contract invariants, not measured household or phishing accuracy.

From the repository root (Python 3.12):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_routing.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Full-suite database tests use temporary synthetic stores only; PostgreSQL CI uses its
existing disposable PostgreSQL 16 service. Do not supply a household database URL.
Actual counts/results are recorded in the PR after validation; no live model or
household demo is part of these commands.

Review-fix validation: **1,237 focused cases passed**, including 56 new regression
cases for acceptance preservation, evidence/safety/policy changes and mixed important
service/promotional evidence. Full SQLite/PostgreSQL 16 current-head CI counts and
checks are recorded in the PR; synthetic results establish contract
behavior only, not phishing efficacy or production authorization safety.

## Explicit limitations and independent review

Only Stage A exists. There is no backlog store, pagination, age timer, digest, alert
delivery, trusted-channel registry, detector, feedback system, quarantine retention,
restore ledger or real risk scoring. Slice 3's reviewed backlog, permission-before-
notification, official-channel, continuous-recoverability and record-retention
contracts remain requirements for later independently approved stages, not enabled
features. No R0–R3 exception, standing mailbox consent, widened OAuth, provider write
or real-data AI permission is created. No Stage B–F or production rollout is enabled.

ChatGPT and independent Muse review are required before a human decides whether to
merge this research PR. Leave it unmerged and keep production functionality disabled.

Review questions:

1. Do access failures reveal neither item existence nor decisions, and is the declared
   test grant clearly separated from real authentication/authorization?
2. Do safety holds/abstention override all unsafe action and offer paths, including
   mixed promotion/service evidence and explicit shopping queries?
3. Are promotions always quiet, including expiry, with no tasks or external effects?
4. Does review remain distinct from simulated acceptance, with changed/reverted
   episodes and policy definitions unable to regain old authority?
5. Are fixed synthetic inputs, bounded deterministic processing, no production imports
   and deferred persistence/notification/security contracts explicit enough?
