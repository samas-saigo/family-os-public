# Family OS v0.1 / Stage E1 — central security-action authorization

## Status and boundaries

This is a normative future contract plus an isolated, deterministic **synthetic-only**
preflight probe (`synthetic-security-preflight-v3`). It does not authorize or execute
mailbox changes. No real household data, private metadata, credentials, frozen
Development/Holdout, AI/Ollama, URLs, providers, OAuth, database, API, notifications,
tasks or production authentication is an input or deliverable. No Stage F pilot.
Stage A/B/C semantics and Stage D's design remain unchanged. E1 shipped no execution
simulation; a passing preflight is neither an executor nor a production grant.
The later [E2 disposable synthetic lifecycle](v0-1-synthetic-security-lifecycle.md)
reuses this contract without enabling real execution or authenticated grants.

References: [architecture](architecture.md#5-deployment-and-client-architecture),
[security](security.md#shared-action-decisions-and-notifications),
[Slice 3](v0-1-action-first-routing-email-safety.md#proposed-reversible-quarantine-contract--not-implemented),
[Stage A](v0-1-synthetic-routing-contract.md), [Stage B](v0-1-synthetic-phishing-policy.md),
[Stage C](v0-1-synthetic-action-first-demo.md), and
[Stage D](v0-1-household-first-authorization.md).

The long-term goal is automatic phishing protection with minimal household intervention,
recoverable false positives and one shared security workspace for two peer adults.
That goal does not waive authorization, independent risk evaluation or recoverability.
Stage B's **6/10** important-legitimate-mail hold/indeterminate proxy is a synthetic
usability/recovery warning, not a measured real-world performance rate or threshold.

## Central R0–R3 decision register

| Decision | Current rule / status | Future approval required |
| --- | --- | --- |
| R0 | Reads within effective source/field/purpose rights | No external mutation; no repeated sharing prompts for already authorized routine reads |
| R1 | Drafts/suggestions only | A suggestion, detector result or review confirmation grants no write/acceptance authority |
| R2 | External changes require confirmation under current central policy | A reversible move or label mutation is a write, never R0/R1; exact provider operation/risk mapping needs review |
| R3 | Send/delete/cancel/financial actions require explicit confirmation and audit | Never inherit authority from quarantine/restore; provider-specific risk classification cannot downgrade them |
| Alternative A | Future per-action explicit authorization, the only modeled approval route | Exact principal/mailbox/object/delta/evidence/policy/consent revision; fresh rights at dispatch |
| Alternative B | **DISABLED, unapproved:** proposed narrow revocable mailbox-specific standing authorization | Separate risk-policy and owner approval, independently verified high-risk policy, recovery/conditional-write/stop/reconciliation gates; cannot be enabled by this PR |
| Restore | Its own explicit operation authorization and fresh preflight | Quarantine consent, release, task rights or earlier approval are insufficient |

Automatic operation is only a future possibility after all B gates are approved.
Unknown, absent or revoked conditions mean no automatic provider mutation. Current
R2/R3 confirmations remain unchanged. In the probe, `STANDING_PROPOSED` always returns
awaiting explicit authorization; there is no approved-standing enum or enable switch.
Even `ELIGIBLE` means fictional preflight only, never permission to write a real mailbox.

## One household workspace, independent authority

Both peers centrally inspect every explicitly shared, authorized security source.
Source, member and assignment filters do not create separate authoritative systems.
Shared security-read access is not mailbox-write consent. Each mailbox and exact
operation require their own rights: Oak consent cannot transfer to Pine, even between
spouses. Source sharing, task publication/editing and operation consent are independent.
Membership, source ownership claims, OAuth, model output and a display client's risk
label cannot establish principal rights. The central authority decides, not the UI.

Apply current recipient/source rights before search, counts, summaries, history,
links, pagination and notification preparation. Recheck immediately before any future
dispatch and on destination opening; queued work or a cached preview is not a grant.
Unknown/revoked access withholds existence, not a suppressed-item counter. Equally
authorized peers must see complete shared aggregation, not owner-only projections.
Ordinary authorized read/review does not repeat sharing setup; an intentional review
Save, operation approval and acceptance remain separate confirmations.

## Exact preflight and independent evidence

A future immutable action proposal must bind all of:

1. Household, exact connected source/provider and provider object identity, operation
   and permitted principal. Titles, sender names or task identity cannot locate mail.
2. Source-read/field/purpose rights and exact operation scope; current source-grant and consent revisions,
   approved central policy version and the separate required approval state.
3. Current independently evaluated safety evidence, observation generation/snapshot,
   evidence/assessment definition and provenance. Reverted text is a new generation.
4. Fresh provider version and exact current folder/label facts, intended bounded delta,
   conditional-write support and absence of incompatible later user changes.
5. Verified quarantine location, coordinated recovery window/retention, protected
   original location/delta and outcome facts, emergency stop and reconciliation gates.
6. Idempotency request identity scoped to household/source/principal plus the entire
   immutable intent. Unresolved same-object effects from either peer block a new write. Delivery keys
   are not task identity or a license to repeat a write under another key.

Unknown/stale/revoked/conflicted/unsupported authority or proof rejects or abstains.
SPF/DKIM/DMARC success, familiarity, user release and detector output do not prove
safety or provide action authority. E1 models independent verification as explicitly
declared synthetic conditions; it neither performs those checks nor demonstrates
detector efficacy. Actual approved evidence acquisition remains future work.

Preflight must be repeated at the authoritative dispatch boundary, including approval,
evidence, rights, consent, provider state and recovery conditions. A local CAS/ingestion
cursor is not a provider conditional-write token. A check followed by an unprotected
remote write has a race; unsupported remote preconditions prohibit automation until
an independently reviewed safe contract exists. No such contract is implemented here.

### Current effective-rights collection and conflict policy

The synthetic aggregate accepts a finite exact tuple of at most four frozen `Rights`
values. Each **(household, source, principal)** key must assert one current value;
exactly identical duplicate values are permitted and add no authority. Identity,
read state, source revision, consent revision and operation tuple must agree in those
duplicates. A distinct value for the same key makes that source **inaccessible for that
principal for this evaluation**, including two ALLOWED entries with different revisions.
This is a conservative input contract, not a production grant resolver.

Resolve these assertions before examining source observations. An older ALLOWED plus
newer REVOKED, same-revision ALLOWED/REVOKED, or UNKNOWN/ALLOWED ambiguity never
selects the ALLOWED value. Input order does not matter; a later duplicate cannot revive
a key already conflicted. Numeric revision order is not independent proof of current
rights. E1 has no authenticated grant store, trusted timestamp or authority that could
choose a winner, so it never uses highest-revision or ALLOWED-wins resolution.

Missing, uniquely denied/unknown/revoked, or conflicted keys contribute no observations,
counts, links or hidden-source markers. This is a per-key failure, not a global error:
other independently permitted mailbox keys remain fully aggregated. Keys for another
principal/household do not shadow the requested member's rights. After this resolution,
apply effective source access, then exact source-object coalescing and the visible cap.
No pagination is implemented; any future pagination must use that same filtered set.
Malformed/untyped authorization envelopes or values outside the four-entry bound still
raise the existing content-free contract error; the bound applies to caller-supplied
rights assertions, not the population of hidden source observations.

A sole consistent ALLOWED value is only a declared synthetic current-rights assertion,
not proof of real current authorization. Future authoritative resolution and revocation
race guarantees require separate approval; no such mechanism or Stage E2 is added.

### Unique security items versus action attempts

`security_count()` projects a set of **(household, source, provider, object)** after
checking effective source permissions for the requested peer. Principal, request key,
action and generation are attempt/evidence attributes, not additional security items.
Authorized peer bindings and repeated observations of one source-specific provider
object coalesce into one count; the visible cap applies to the resulting unique set.
Different mailbox objects remain distinct even with the same fictional object marker;
no title, sender or other untrusted similarity participates in identity.

Action history remains distinct: it retains exact actor, request, evidence and approval
bindings; deduplicating display counts must never merge approvals or discard outcomes.
Hidden records are filtered before item deduplication/cap checks and cannot alter the
authorized count or trigger duplicate errors. Input envelopes still require finite
typed tuples, as previously specified; this is not a constant-time guarantee.

### Quarantine and restore deltas

Record original folder/label facts and the exact attributable delta before future
dispatch. Never describe provider Junk/Trash as a permanent recovery location without
independently verified retention; auto-purge or uncertain recovery blocks automation.
No permanent deletion, auto-release on age or blanket sender trust.

Restore requires independently supported clear/false-positive evidence, then separately
binds the recorded verified quarantine and **fresh** current state,
principal, consent and explicit restore approval. Reverse only that operation's delta;
do not overwrite subsequent user moves/labels, guess a missing destination or revive
deleted mail. If fresh proof is missing, restore is blocked/unknown, not successful.
The restore policy introduced in v2, unchanged in v3, models only a **single declared
complete quarantine episode**. A new restore
requires `history_complete=VERIFIED` and visible same-object history exactly equal to
the referenced verified quarantine record. Missing, duplicate, inconsistent or additional
same-object history blocks eligibility. The original must match the exact source/provider/
object, recorded delta and current authorized assessment/approval. Both current observation
generation and provider revision must be **strictly greater** than the original binding
values; older, equal or reversed chronology blocks. These bounded integers are monotonic
synthetic surrogates, not an interpretation of real provider ETags or atomicity proof.
No opaque-provider-version equivalence exception is modeled.

A verified previous restore, another quarantine episode or an unsupported multi-step
history cannot make the old quarantine eligible again, even with a new key, actor or
generation. E1 abstains (`BLOCKED`) rather than reconstruct a durable lifecycle. An
exact authorized replay may return only the previously recorded result (`REPLAY`),
never fresh eligibility or dispatch. Complete history is a declared synthetic proof
condition, not an authenticated ledger: E2 must independently establish completeness,
post-operation versions and causal transitions before any broader simulation is approved.

An important legitimate notice falsely assessed high-risk must remain recoverable
through authorized review. The probe deliberately demonstrates that an incorrect
independent high-risk assertion can pass all fictional gates: this is no accuracy claim.

## Future lifecycle, failure and stop contract — E2 boundary

These are required design states, not a ledger or executor shipped in E1.

| State/event | Required future behavior |
| --- | --- |
| Planned | Immutable scoped intent; no provider operation or success claim |
| Awaiting authorization | Explicit approval missing or B unapproved; retain safe authorized question only |
| Executing | Only after repeated preflight and protected intent/idempotency reservation; actual dispatch deferred |
| Verified quarantine | Independently verified exact object/location/delta outcome, not merely HTTP acceptance |
| Failed | Record bounded failure/outcome facts; reconcile effect before a new approved attempt |
| Outcome unknown | Timeout/ambiguous delivery is not success or a no-effect failure; stop blind retries |
| Reconciliation required | Independently determine remote effect and user changes before any new write; no assumed success |
| Restore planned/blocked | Fresh separate authority and verified original delta required; conflict or loss blocks dispatch |
| Verified restore | Independently verified reversal of only the attributable delta; no later user edits overwritten |
| Restore failed/unknown | Keep distinct from success; reconcile, do not blindly repeat or undo more state |
| Evidence changes before dispatch | Stale approval/proposal fails; new/reverted generation needs new assessment and bound intent |
| User changes provider state | Conditional conflict stops dispatch/restore; preserve the user's newer folder/labels |
| Consent revoked/emergency disabled | Stop queued/future dispatch; distinguish submitted revoke from committed revoke; reconcile in-flight outcomes, no bulk blind undo |
| Recovery-data expiry/loss | End unsupported guarantees, block new automatic quarantine under that contract and mark existing recovery unavailable/needs review |

Identical request replay returns only an authorized historical outcome without dispatch.
A reused key with different intent rejects. A new key cannot bypass unknown/failed work
or re-dispatch the same known completed snapshot. Revocation invalidates future access;
replay cannot resurrect it. Idempotency and audit state need their own future durable
transaction/remote reconciliation design; in-memory fictional records are not that design.

Coordinate recovery/audit retention with unresolved outcomes. Follow an explicitly
approved deletion policy, with authorized warnings/choices where permitted; do not
silently discard proof while promising recovery or assume indefinite retention.
Deletion rights are not automatically suspended for recovery. If required deletion or
lost evidence ends a guarantee, say so safely; no unsupported success or new automatic
quarantine. Trusted-channel verification and scoped revision-bound feedback from
[Slice 3](v0-1-action-first-routing-email-safety.md#trusted-official-verification-channels--separate-authority-contract)
remain separate; release cannot rewrite registry/global phishing policy.

## Stage D review findings carried forward

- A one-time task freshness warning following source revocation may reveal timing.
  Its visibility/cadence tradeoff is **not approved** by E1; no private updates may
  drive subsequent warnings. A later design must obtain explicit policy approval or
  suppress that signal without affecting independently approved task continuity.
- A revoke request is only **submitted** until its authoritative revision transaction
  commits. Failed/stale revoke must be prominently reported to the requester as
  **not applied**, with a deliberate fresh retry; no silent discard or automatic
  rebase. Revoke-first cannot be overridden by an old scope expansion.
- Sharing setup must identify exact source, named recipients, permitted fields,
  purpose, operations, retention/revocation terms and expected revision. Cancel
  creates no grant. Ordinary already-authorized reads do not repeat this setup.
- Current grants are checked on use/dispatch. Pending revocation is not falsely
  reported as committed; uncertainty at the authorization boundary fails closed.

Setup UX, grant transactions and warning timing are normative acceptance definitions
below, deliberately not production mechanisms or simplified grant-creation helpers.

## Newly authored synthetic conformance definitions

Fixed fictional peers Aster/Robin share Oak/Pine security-read access; operation
rights differ. A single invented school notice, its alternate object and finite
generation/version markers are the only payload identities. No actual mail text,
labels, URLs or private dataset is accepted. Truth labels in tests stay outside preflight.

| Case | Fictional change | Required result / executable coverage |
| --- | --- | --- |
| E01 | Both peers read Oak/Pine; only Robin may write Pine | Unified count 2 for each; Aster's Pine operation blocked; tested |
| E02 | High-risk assertion but no mailbox operation right | No mutation; blocked; tested |
| E03 | Proposed standing approval with every other gate verified | Awaiting explicit approval; B remains disabled; tested |
| E04 | Restore has only quarantine right or no fresh restore approval | Blocked/awaiting; tested |
| E05 | Source/consent revoked after assessment, before dispatch | No source existence/result or operation; fresh gate blocks; tested preflight, actual dispatch deferred |
| E06 | Any binding component or independent assessment/approval changed | No acceptance transfer, including changed/reverted generations; tested |
| E07 | Provider version/folder/label stale or conflicting | Blocked; no overwrite; tested |
| E08 | Retention/target/recovery data unknown or purging | No automatic move; blocked; tested |
| E09 | User moved or edited labels after the recorded quarantine | Restore blocked; tested |
| E10 | Exact duplicate delivery versus same key/different intent | Historical replay only versus rejection; new key cannot duplicate same snapshot; tested |
| E11 | Failed/unknown prior outcome, including a new delivery key | Reconciliation required, no success/blind retry; tested |
| E12 | Emergency stop with queued proposal | Blocked; no new operation; tested preflight, in-flight reconciliation deferred |
| E13 | Legitimate important school notice supplied a false high-risk finding | Explicit fictional gates can pass; restore has its own gates; demonstrates false-positive risk, not measured efficacy; tested |
| E14 | Pine revoked plus hidden duplicate/over-limit records | Only Oak in unified count; hidden collections do not affect visible decision/caps; tested |
| E15 | Oak consent applied to Pine | Withheld/blocked, no cross-mailbox transfer; tested |
| E16 | Sharing terms omit field/purpose/recipient or operator Cancels | No grant; complete terms must be explicitly confirmed; normative, setup simulation deferred |
| E17 | Concurrent revoke/expand at old revision; stale or failed revoke | At most one commit; prominent not-applied feedback; submitted is not committed; normative, grant transaction simulation deferred |
| E18 | Task warning after source revocation | Timing tradeoff unresolved/unapproved; task/source rights remain independent; normative, warning simulation deferred |
| E19 | Two authorized peer/attempt bindings for the same Oak object, plus distinct Pine/provider/object bindings | One item per authorized household/source/provider/object; no actor duplication or cross-mailbox merge; hidden population does not affect deduplication; tested |
| E20 | Restore generation/provider revision older than or equal to original, including reversed combinations | Block unless both are strictly newer under the explicit synthetic monotonic contract; no real-provider version equivalence inferred; tested |
| E21 | Missing/incomplete/duplicate history, stale original reference or another quarantine episode | No eligibility without the exact single verified original and complete-history condition; current provider snapshot/approval changes block; tested |
| E22 | Verified prior restore followed by a new key, actor or generation | New restore blocked; exact replay historical only; durable multi-episode transitions deferred to E2; tested |
| E23 | Older ALLOWED/newer REVOKED, same-revision contradiction, UNKNOWN ambiguity or two purported current revisions, in either order | Withhold the affected household/source/principal key, never select a grant by order/revision or let a later duplicate revive it; unrelated authorized mailbox remains aggregated; tested |
| E24 | Exact consistent grant duplicates and other-peer/household conflicts | Duplicates add no authority/count; effective permitted sources remain fully aggregated for each peer; hidden repeated observations do not change results; tested |

The implemented probe only evaluates immutable synthetic bindings/declared conditions,
scoped history and authorized counts. Fixed enums prevent private text/URL inputs;
revisions are 1–1,000, operation tuples at most 2, rights collections at most 4 and
visible action records at most 32 and unique counted source objects at most 32. Mixed collections must be finite typed tuples; authorized
item coalescing/cap checks and action-record bounds follow access filtering. Traversal is finite linear, not a
constant-time privacy guarantee or production resource boundary. No result includes
private content, hidden reasons or actual write authority.

Its move-only delta model does not simulate provider label APIs. Original/current
synthetic label sets and absence of subsequent user changes are checked conservatively.
Assessment/approval bindings are exact, while independent evidence/provenance and
provider versions are declared surrogates, not signed proof. Frozen Python values are
not a hostile-code sandbox. Production authentication, trusted source verification,
real operation idempotency, ledger/retention enforcement and dispatch remain absent.

## Validation, commands and E2 gates

Run isolated tests with Python 3.12 from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_security_preflight.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Tests use newly invented enums only, with no real DB, frozen corpus or model. Existing
SQLite/PostgreSQL regression suites use disposable synthetic test stores; never supply
a household database. Exact focused/full head-specific counts belong in the PR.
Import/production-wiring and I/O guards accompany binding/abstention tests.

E2 requires a separately approved **synthetic-only** execution/reconciliation design:
intent reservation/history, fresh dispatch authorization, provider-state surrogates,
conditional conflicts, uncertain-delivery reconciliation, own-delta restore,
emergency stop and coordinated retention/deletion. Include E16–E18, durable causal history/completeness proofs and real concurrency
probes against disposable synthetic state if that persistence scope is separately
approved. No real executor, provider permissions, auth/API, model, real-mail pilot or
standing-consent exception follows from E1 or E2 synthetic success.

Review questions for ChatGPT and independent Muse:

1. Are A and disabled B explicit, with R2/R3 and independent restore authority intact?
2. Are source/task/operation permissions separate while shared aggregation stays complete?
3. Do exact evidence/provider/approval/consent bindings and duplicate handling fail closed?
4. Are unknown outcomes, later user changes and failed recovery guarantees handled honestly?
5. Are Stage D's timing tradeoff, setup terms and submitted-versus-committed revoke retained?
6. Are synthetic declarations distinguished from real verification, with E2 deferred?

Keep the dedicated PR open for both independent reviews and final human-controlled
merge. No auto-merge or production enablement.
