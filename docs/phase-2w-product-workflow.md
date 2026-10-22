# Phase 2W — end-to-end household review and follow-up blueprint

## Status and design boundary

[Issue #59](https://github.com/samas-saigo/family-os/issues/59) is **documentation
and product architecture only**. Every screen, product review item, task, approval
and tracking behavior below is a future concept, not a working feature or permission
to implement it. This complements the Phase 0 design references rather than replacing
them: [architecture](architecture.md), [data model](data-model.md),
[dedupe](dedupe.md), [security](security.md), [roadmap](roadmap.md) and
[Issue #8](https://github.com/samas-saigo/family-os/issues/8) remain authoritative.

All examples are entirely invented English scenarios, not derived from household
data or frozen evaluation cases. No real household data or human-labeled real
metadata may enter any AI, including Codex, ChatGPT, Muse or local Ollama. This
checkpoint reads no household database, account, file, screenshot or Holdout; it
performs no model inference, provider call or local simulation. No code, policies,
schema, migrations, scopes, credentials, corpus, pins, labels or versions change.

The recommendation is one future authoritative household backend, with desktop/web
and phone as authenticated views of its state. Current local CLI/SQLite/native
keyring operation remains a different implementation stage. Provider credentials
belong in the future backend/provider-connection boundary; clients do not receive
refresh tokens. Client authentication and household/person authorization are
separate from provider OAuth. Finance remains its own source of truth.

### What exists and what is proposed

| Capability | Status today | Boundary in this blueprint |
| --- | --- | --- |
| Gmail / Outlook / Calendar / Drive minimized read-only ingestion | Implemented local operator services; account-specific identities/scopes/cursors | Source observations, not proven obligations or canonical dedupe |
| Exact source/raw snapshot and immutable versioned analysis | Implemented Phase 2F; conservative local rules in Phase 2G | Inference preserves provenance; it is not household truth |
| Metadata audit, human evaluation revisions and terminal labeling | Implemented local Phase 2H–2J | Quality evaluation, not product review or task approval |
| Calendar evidence suggestions | Isolated synthetic-only Phase 2U prototype | No production applicability or promotion |
| Explicit review/repeat simulation | Isolated, disposable Phase 2V memory | Design input only; not a shared review store |
| Canonical identity, cross-source dedupe and product review queue | Future Phase 3 design | Durable per-source review can be a separate narrow slice; validated canonical linkage gates cross-source grouping, not that slice |
| Authenticated backend, shared authorization/CAS, encrypted backend credentials | Future deployment milestone | Required before shared or network client access; a separately approved single-user local slice may retain the local operator boundary; no API/framework chosen |
| Inbox / Needs Action / Upcoming, desktop/web/phone clients | Future Phase 4 concepts | Views of one backend; no independent client task databases |
| Tasks, approvals, notifications and provider writes | Future Phase 5 | Separate intent, permissions, confirmation and audit; no automatic execution here |

[Phase 2V](phase-2v-human-review-workflow.md) reported 12 fixed synthetic sequences,
39 visits, seven unchanged resolved repeats annotated and eight changed-evidence
re-reviews; **all 39 visits remained visible**. These results establish neither
population accuracy nor actual human time saved. This blueprint does not wire that
simulator to real data. [Phase 2H](phase-2h-review.md) evaluation labels and
[Phase 2J](phase-2j-review.md) operator labeling also stay separate from product review.

## Workflow and information architecture — all future

The conceptual path is:

```text
read-only minimized source observation [implemented local ingestion]
  -> exact immutable source analysis [implemented local inference; not truth]
  -> scoped evidence proposal [future product contract; no promotion of 2U]
  -> visible review item [future product review queue]
  -> explicit authorized human disposition [future shared backend]
  -> separate optional R1 task suggestion / acceptance [future; no implied consent]
  -> tracked human-reported outcome [future; not proof of external execution]
  -> optional external-action proposal / separate approval [future R2/R3 gate]
```

Any branch can stop at uncertain, invalid, deferred, rejected or no follow-up.
There is no requirement to create a task for every notice. A confirmed Not Required
proposal settles only that named review step, not an event, household or task.
Source changes never mutate an old analysis, review revision or historical outcome.

| Future view | What the person finds | Visibility and ownership rule |
| --- | --- | --- |
| Inbox | Authorized source notices and their review status: pending, uncertain/invalid, deferred, needs-information, rejected and previously reviewed | Default All view keeps those states visible with badges. Explicit filters show their active scope and counts; no silent relevance/domain/priority dismissal |
| Needs Action | Separately labeled **Review needed** and **Accepted follow-ups** sections | The first asks for a decision, not a proven obligation. The second references explicit accepted backend tasks; it never creates another task store |
| Upcoming | Authorized explicit event times and confirmed task dates, with source/time provenance and cancellation/unverified-date badges | A start date is not an action deadline; a past date is not completion. Unknown dates stay unknown, not invented deadlines |
| Optional Documents / Assets / Search | Authorized provenance and later canonical links, when implemented | A Drive title/MIME type does not prove document contents, an asset or an obligation; search cannot bypass access policy |

A source account is not a person. The account's registered owner, the review's
responsible person, the task assignee and the person approving an external action
are distinct concepts. Missing responsibility may be shown as unassigned only to an
operator whose access to that source is already established. Unknown ownership or
an unresolved access policy does not grant visibility: default to no disclosure,
including no indication that the item exists. There is no default household-wide
unassigned queue or implied administrator access. Assignment must not expand source
access; household membership alone grants no other member's mailbox/history access.
The future permission model must be approved before shared views exist.

Rejected and previously reviewed items remain in Inbox All, with explicit status
filters and an accessible revision trail. Deferred items stay in Inbox and Review
needed with their disposition; a chosen revisit time does not hide unresolved
evidence. Needs-information, unknown identity and invalid observations remain
visible for permitted human handling. Upcoming links back to the same review/task
IDs. Notification dismissal changes delivery state only, never review/task truth.

### Desktop/web and phone text flow

These are conceptual text wireframes, not implemented UI:

```text
Desktop/Web: Inbox All -> source/proposal card + history -> choose disposition
             -> visible Save review confirmation -> backend checks current version
             -> shared disposition -> optional separate Suggest/accept follow-up

Phone:       same Inbox/Needs Action item ID -> compact card + expandable evidence
             -> same explicit choice/confirmation -> same backend validation
             -> accepted result visible on desktop (or stale/conflict warning)
```

Neither client owns classification, dedupe, resolution rules or approvals. The
future backend would return an authorized minimized view and enforce every transition.
For stale evidence the card says “Evidence changed; refresh and review again,” shows
the old decision as historical and disables submission against that old version.
No optimistic client banner may claim a save succeeded before backend acceptance.
Offline is initially read-only, with stale labeling; no queued approvals or independent
task changes. Cached metadata security/retention and any later offline editing need
separate design approval. Missing backend means no new saved decision or execution.

## Future review-card contract

| Visible field / control | Required meaning |
| --- | --- |
| Source and attribution | Provider/type, permitted account attribution and registered owner/unassigned state; separate intended reviewer/assignee |
| Identity and provenance | Stable source ID, exact raw snapshot ID and analysis ID/version; future linkage retains each source reference rather than equating similar titles |
| Time and freshness | Source occurrence time, snapshot observation time and explicit event dates distinguished; missing/stale values visible |
| Proposal definition | Analyzer/ruleset fingerprint, taxonomy/threshold versions where applicable, proposal schema version and exact evidence/proposal fingerprint |
| Step and scope | One named step plus its condition; separate preparation, attendance, cancellation, refund and rebooking; never global clearance |
| Suggestion / validity | Required / Not Required / Uncertain; invalid means no accepted suggestion, not Not Required |
| Evidence and explanation | Bounded resolvable refs and fixed missing/unsupported/conflicting/unmet/unknown reasons, with permitted minimized values |
| Review state | Pending / human-confirmed / human-rejected / needs-information / deferred; separate disagreement or changed-evidence attention marker |
| Explicit controls | Choose disposition, inspect scope, then Save review; Back/Cancel write nothing; correct appends a revision; no default-selected approval |
| History and stale warning | Earlier immutable decisions and their exact evidence/versions; current revision/display token for backend compare-and-swap |
| Separate follow-up / action | Optional task suggestion shown as a different object with owner/scope/date and its own acceptance; R2/R3 approval never shares the review Save button |

Use the existing minimized display boundary as the starting limit: bounded subject
and sender only where already permitted, and `status`, `eventType`, `start.dateTime`,
`start.date`, `end.dateTime`, `end.date`, `mimeType`, `trashed`, `removed`. No arbitrary
raw metadata, email bodies/snippets/previews, Drive contents, provider payloads,
tokens/cursors, chain-of-thought, prompt transcripts or model responses. Unsupported
or omitted fields remain absent. A title or source link is not proof of contents.
Any future provider navigation requires a separate safe-link/security design.

No fabricated probability appears on the card. If a future design exposes a stored
rule score, it must identify it as an uncalibrated rule score, with its version and
limitations; it cannot become authority to close, hide or execute. Source ownership
does not prove client authorization, and provider consent does not authorize AI use.

## Three entirely fabricated English journeys — future boundaries explicit

“Reviewer A” and “Reviewer B” below are fictional roles, not existing authenticated
users. All titles, dates, IDs and facts are invented for this document. Suggestions
outside the tiny Phase 2U grammar are illustrative future contracts, not claims that
today's classifier can produce or safely resolve them.

### A. Calendar preparation, then a changed condition

1. **Source metadata:** a fictional Calendar snapshot `example-calendar-A / raw-A1`
   has title “If status is confirmed bring the vaccination booklet,” confirmed
   status and start “2030-06-12 09:00 UTC.” First appearance belongs in Inbox and
   Upcoming; the date is an appointment time, not a fabricated deadline.
2. **Immutable analysis/evidence:** preserve raw-A1 and the exact rule definition.
   An illustrative Required preparation suggestion cites subject/status, scoped
   only to bringing the booklet. Recognizing this synthetic form does not authorize
   a real-data Phase 2U deployment.
3. **Future review item:** Reviewer A checks attribution, condition and evidence,
   chooses human-confirmed, and separately saves that scoped review. Before save,
   there is no resolution; afterward the review has no task/execution authority.
4. **Future proposed task:** a separate R1 suggestion “Bring the vaccination booklet”
   asks for an assignee and an explicitly chosen date. Reviewer A may accept it or
   leave it unaccepted. Acceptance creates one backend-owned follow-up only after
   that implementation/security gate; it neither creates nor alters the appointment.
5. **Future tracking:** after the visit, a human with the separately granted
   task-completion-report permission may report that the booklet step was completed.
   Store that as a human-reported task outcome, not automatic proof from a passed calendar date. An unchanged resolved repeat shows
   “Previously reviewed” and history; it must not generate a duplicate task.
6. **Changed evidence:** raw-A2 becomes tentative. Reopen the scoped review as
   uncertain; prior review/task history remains. The active follow-up displays
   “Evidence changed—check before proceeding.” Do not automatically complete,
   cancel or delete it. A stale phone save of raw-A1 fails; the person refreshes,
   then explicitly chooses needs-information or defer.

### B. Uncertain household notice, a Drive reference and no automatic task

1. **Source metadata:** a fictional Gmail message `example-notice-B / raw-B1` says
   “Household service update.” A separate fictional Drive item `example-file-B`
   is titled “Service update.pdf,” with `mimeType=application/pdf`. Neither title
   proves a bill, obligation, deadline or matching document contents.
2. **Immutable analysis/evidence:** each source retains its own snapshot/analysis.
   With no sufficient scoped evidence, use Uncertain/missing evidence. Do not merge
   these sources based on similar wording or make a canonical household fact.
3. **Future review item:** Reviewer B, already permitted to access this source,
   sees an unassigned notice and unknown step,
   chooses needs-information and saves. On a later visit the same unresolved item
   remains visible; B explicitly defers it without accepting, rejecting or closing
   an unknown obligation. A permitted person may later resolve attribution through
   a separate authorized process, without making the whole household see private data.
4. **Future task boundary:** no task is inferred or created from Uncertain. A
   possible separate human-authored information-gathering follow-up would need its
   own approved task contract and explicit acceptance; it would not resolve the
   original obligation. That optional design remains an open implementation decision.
5. **Future tracked outcome:** for now, only pending/deferred review is tracked;
   there is no task outcome to fabricate. If raw-B2 later supplies different minimized
   evidence, reopen with that exact snapshot. Do not carry forward an old disposition
   or copy missing facts from raw-B1. A future supported concrete Not Required
   proposal still needs explicit human review and would create no follow-up by itself.

### C. Cancellation, conflicting refund evidence and partial completion

1. **Source metadata:** a fictional Outlook notice `example-trip-C / raw-C1` says
   “Reservation cancelled; refund status unknown.” A separate fictional Calendar
   event is cancelled. Own-mailbox read-basic metadata is not a refund transaction
   or proof that no further action exists. Source-level records stay distinct.
2. **Immutable analysis/evidence:** an ambiguous refund step remains Uncertain,
   even though the reservation is cancelled. A future linkage proposal must preserve
   both provenance trails and require identity/dedupe validation; there is no existing
   cross-provider merge. A cancelled event cannot globally clear refund/rebooking.
3. **Future review item:** Reviewer A chooses needs-information, saves and later
   defers. If both reviewers are permitted to see the relevant evidence and
   revisions, disagreement remains visible, without “latest person wins” or a
   majority-vote automatic closure. Otherwise do not disclose inaccessible evidence
   or its existence through a disagreement badge, explanation or history. A shared
   resolution must wait for an approved permission-safe process.
4. **Changed evidence / future new review:** raw-C2 now explicitly says “Outstanding
   step: request refund.” A future validated scoped proposal could be Required;
   the previous unknown snapshot stays historical. A checks exact evidence and
   condition, explicitly confirms that refund-request step, then saves.
5. **Future proposed task:** separate R1 suggestion “Request the refund” requires
   its own acceptance/assignee. Merely confirming the review does not send a message.
   If A later requests sending a refund email, the backend must form a distinct R3
   action proposal and obtain separate authorized confirmation of recipient, content,
   effect and current version; read-only provider grants cannot execute it.
6. **Future tracking / correction:** if separately authorized to report completion,
   A may report “Refund request submitted.” That
   does not prove payment received; Finance remains financial truth. A new snapshot
   mentioning rebooking creates a different scoped review, not automatic reuse of
   the refund resolution. Completing one task cannot clear the other. If A corrects
   the review to human-rejected, append the correction; flag any linked task for
   explicit reconsideration rather than silently deleting it or undoing execution.

## Future transition and authorization matrix

For future shared/network use, every mutation below requires authenticated household
access, source visibility, the specific operation's permission and a current backend
revision. A separately approved single-user local MVP uses the local operator boundary
described below, with the same version/provenance safeguards and no shared access.
These checks do not exist as product authorization today. Review approval is distinct from task
acceptance, assignment, human-reported completion and external action approval.

| State / event | Permitted future human choice | Result / visibility / prohibition |
| --- | --- | --- |
| Pending supported concrete proposal | Confirm, reject, defer or needs-information, then explicit Save review | Append scoped disposition; no task/execution implied |
| Uncertain or invalid | Needs-information or defer | Remains unresolved and visible; no confirm/reject/close shortcut; invalid has no accepted prediction |
| Deferred / needs-information | Revisit, choose permitted disposition or explicitly revise revisit time | Remains in unresolved review; no automatic expiry dismissal |
| Human-confirmed / human-rejected, exact unchanged evidence | Inspect history; optionally correct with explicit save | Annotate previously reviewed; still visible; no new mandatory duplicate decision or task |
| Any changed evidence/snapshot/condition/step or rule/schema definition | Refresh and review new proposal | Old revision remains historical; no resolution transfer, including change then return to old bytes |
| Correction / member disagreement | Append authorized revision or disagreement, re-evaluate current scope | Preserve history; disclose only permitted revisions/evidence and permitted disagreement existence; no silent override; arbitration/access policy remains open |
| Separate R1 task suggestion | Inspect scope/assignee/date and explicitly accept or decline | Accepted task is a distinct backend object; Not Required or review confirmation cannot auto-create/complete it |
| Accepted task | Separately authorized progress, waiting, reported-complete or correction | Review permission, source ownership or assignment alone does not grant completion-report rights; tracking is human-reported, not execution proof |
| External R2/R3 action | Separate action-specific authorized confirmation after fresh validation | Requires central policy, permissions, appropriate provider grant and audit; no implicit consent from review/task/OAuth |
| Stale/conflicting/offline/revoked access | Refresh, stop or seek authorized resolution | No mutation/execution; no hidden uncertainty or queued approval that bypasses current checks |

The minimal future task lifecycle proposal is suggested (unaccepted), accepted,
in-progress/waiting, human-reported-complete, and explicit corrected/withdrawn state.
The exact lifecycle/schema is unresolved. Evidence changes or disputes add a visible
attention condition; they never imply completion or erase earlier work. Withdrawal
of a task is not cancellation of a provider event. A human-reported outcome is not
automatically a canonical fact or Finance transaction.

| Risk handoff, following existing R0–R3 design | Separate future gate |
| --- | --- |
| R0 authorized read | Central access policy; read-only ingestion; no new scopes or egress. Automatic authorized reads remain compatible with Issue #8 |
| R1 suggestion/draft | Automatic or one-click draft/suggestion generation remains permitted by the central policy; accepting an actual tracked task is a separate explicit choice in this blueprint, never inherited review consent |
| R2 event/file change | Separate confirmation bound to the exact target, operation, proposed effect and version; central permission and provider-scope checks |
| R3 send/delete/cancel/financial action | Separate explicit authorized confirmation and audit, exact payload/effect/version binding and execution-result handling; Finance boundary preserved |

Automatic R1 draft/suggestion generation and explicit task acceptance are different
operations. The former remains compatible with architecture.md's “automatic or
one-click” R1 policy; the latter is this blueprint's proposed gate for creating an
accepted, assigned/tracked follow-up. Neither implies R2/R3 approval or execution.
No generation, task acceptance or execution is implemented by this checkpoint;
all provider integrations remain read-only today.

Future action approval must bind the exact target, operation/payload, evidence
snapshot/proposal fingerprint and relevant task, approval and policy revisions.
Recheck current permissions and those bindings before execution. Changed evidence,
payload, task scope or relevant policy, and revoked permission invalidate executable
approval; retain its historical record and require fresh authorized confirmation.
Distinguish awaiting approval, approved-for-current-version, invalidated/reapproval
required, executing and outcome-unknown/reconciliation states. Exact state names,
expiry rules and schema remain open; invalidated is not rejected, completed or
silently renewed. Unknown external outcomes require reconciliation, not blind retry.

Request idempotency identifies a retry of the same operation with the same payload
and version: it must return the same committed result or a safe conflict. It does
not define task identity or prove that two requests with different keys describe
one obligation. Cross-request/task equivalence, uniqueness and correction semantics
need their own approved contract; no title-based or cross-source dedupe is implied.

## Safety and multi-user edge cases — desired future behavior

| Edge case | Desired behavior | Missing prerequisite today |
| --- | --- | --- |
| Unknown person / household attribution | Unassigned, unresolved; show only to a permitted operator; do not guess owner or expand sharing | Identity resolution and approved source/person authorization |
| One person, several Gmail/Outlook accounts | Preserve separate account bindings; task responsibility is a separate choice; do not treat account count as people count | Product attribution and authenticated assignment policy |
| Similar notice in Gmail, Calendar and Drive | Retain independent IDs/evidence; suggest possible relationship only after validated canonical linkage; no words-only merge or hidden notice | Canonical identity/dedupe and reversible linkage review |
| Household members disagree | Disclose opposing revisions/evidence only where each recipient is permitted to see them; do not reveal inaccessible data or its existence through conflict markers/counts; default to no disclosure when authorization is unresolved | Authenticated reviewer identity, shared persistence, approved disclosure and arbitration rules; no role hierarchy selected here |
| Stale desktop vs phone display | Reject stale revision/snapshot/definition, show historical decision, reload minimized current card | Backend CAS and shared authenticated review store |
| Simultaneous saves / double-click / two clients accepting one task | Conflict or converge for the same version-bound request; preserve revisions and prevent retry duplication. Different requests require a separately defined task-identity contract | Transactional review/request idempotency and approved task identity; no assumed semantic dedupe or distributed client logic |
| Unauthorized member or revoked session/source access | Deny reads/mutations and minimize cached disclosure; recheck grants at save and execution; membership alone does not expose personal mailbox data | Client auth, source/person access policy, revocation and cache handling |
| Cancelled/rebooked event plus refund follow-up | Treat attendance, preparation, refund and rebooking as distinct steps; retain unknown/conflicting evidence | Scoped canonical/review/task relationships and later controlled executor |
| Partial completion | Completing refund-request step does not prove refund paid or resolve rebooking; preserve each outcome's provenance | Task lifecycle and canonical step identity |
| Source updates after rejection | New snapshot requires review again; previous rejection remains historical; no permanent suppression | Exact version-bound product review persistence |
| Source unavailable/removed | Show permitted provenance as unavailable; do not infer real-world deletion, no-action or task completion | Approved source-availability/product lifecycle design |
| Backend unavailable / offline phone | Read-only permitted cache with stale marker, or unavailable view; no local authoritative save/execution | Backend availability, approved encrypted cache/retention design |
| Notification dismissed | Delivery acknowledgement only; Inbox/review/task state unchanged | Separate delivery state, shared backend and future notification policy |

Cross-source linking must preserve both data confidentiality and existence privacy.
No joined title, count, identifier, history, link, redacted placeholder or conflict
marker may reveal an inaccessible source or the fact that it exists. Check access
before constructing a linked view or shared disagreement summary, not just before
opening its details. Insufficient or unresolved authorization defaults to no
disclosure. A future shared projection requires separately approved disclosure
rules; linking or assignment cannot grant access. Canonical linkage is not an
access-control mechanism.
Source-account ownership and existing household FK/CAS integrity are useful building
blocks, not an implemented authentication or permission system. Future credential
migration needs separate security review/re-consent; no token is placed in a card,
client cache, notification, task or approval record.

## Design decisions, tradeoffs and unresolved approvals

Design recommendations grounded in existing architecture are: one backend-owned
state; exact snapshot/version-bound append-only review history; unresolved states
visible; no inference-based task authority; separate explicit task and R2/R3 gates;
minimal permitted metadata; no actual AI/real-data boundary expansion. Accepting
this document approves a blueprint only, not runtime work or data access.

| Topic | Options and tradeoff | Proposed starting point / decision still needed |
| --- | --- | --- |
| Notification cadence | Manual visits avoid interruptions; opt-in digest reduces repetition but may delay attention; immediate alerts increase noise and privacy exposure | Manual-only first client slice. Future cadence, recipient permissions and content-free lock-screen payload need user approval; no notifications built here |
| History visibility | Full expanded history gives context but crowds a phone; current card plus visible revision summary is compact; hiding resolved history would undermine correction | Visible current status and revision summary, expandable permitted original evidence; do not hide history. Validate layout with approved synthetic walkthroughs |
| Source vs obligation organization | Source-first preserves provenance but repeats notices; obligation-first simplifies tracking but risks false merges; linked views retain provenance with extra navigation | Source-first until canonical linkage is validated, then one obligation view with permitted source refs. Grouping must not create duplicate task stores or silently merge steps |

Still open: household/personal visibility and reviewer/assignee permissions;
disagreement/arbitration; task suggestion, assignment, due-date and completion
contracts; whether a separately human-authored information-gathering task is useful;
retention, correction/withdrawal and unavailable-source behavior; notification cadence;
deployment/auth choices, backend secret migration and offline cache policy. These
require separate architecture/security review and explicit implementation approval.

### Later UX decisions — not implementation commitments

- **Historical retrieval:** decide permitted search/filter/navigation across reviewed,
  rejected and superseded revisions. Results, counts and snippets must respect the
  same source and existence-privacy boundaries; history remains immutable.
- **Safe bulk triage:** decide which dispositions can be batched. Require a bounded
  permitted selection, per-item freshness/authorization checks, explicit preview and
  confirmation, and visible partial/conflict outcomes. No silent inclusion of hidden
  items, bulk approval of unknown obligations or implicit task/action acceptance.
- **Ordering:** compare recent-first, explicit dates and review-status sorting;
  show the chosen order/filter. Missing dates or uncertain priority must not become
  invented urgency, dismissal or clearance. Exact defaults remain to be tested.
- **First connection/consent:** design the local setup and later authenticated-client
  onboarding separately. Explain provider account binding/read-only scopes, Family
  OS access, revocation and failure states; provider OAuth does not grant household
  sharing, action approval or AI consent. No credential copying into client views.

Any later real local usability study requires a separately approved privacy plan:
human-only local inspection, defined access/retention and only safe aggregate feedback.
No real household record, label, screenshot or identifying path goes to any AI,
including local Ollama, under that plan. No live study is requested or run here.
Synthetic walkthroughs are the initial design check; synthetic metrics cannot
authorize a real-data trial, model deployment or production promotion.

## Proposed dependency order and small later slices

```text
existing source identity / exact provenance + approved local operator boundary
  -> separately approved single-user, no-sharing, per-source review MVP
     [durable version-bound core state; no canonical linkage needed]

shared/network clients -> approved auth + source/operation authorization
  -> one durable authoritative backend -> shared review and multi-client views
cross-source grouping -> separately validated canonical identity/linkage
accepted tasks -> separately approved task identity/lifecycle and R1 acceptance
external actions -> distinct centralized R2/R3 approval, audit and execution gates
```

These are dependency boundaries, not permission to implement any slice. A safe
single-user local MVP may review each source independently, with no sharing,
cross-source links/merge, tasks, provider writes or exposed network service. It may
use the existing local operator/machine access boundary after explicit design and
privacy approval; that boundary is not multi-user authentication. It still needs
source-access checks appropriate to that boundary, durable exact-version review
state, append-only corrections and CAS/retry safety in the authoritative core.
Do not reuse Phase 2V's disposable memory as production persistence or create
independent per-client truth. Canonical Dedupe is **not a hard prerequisite** for
this narrow MVP; it gates later cross-source grouping, not independent source review.

Shared or network access must wait for approved authentication and source/operation
permissions, including existence privacy. Canonical linkage, multi-user arbitration
and task identity are separate expansion decisions. No unresolved multi-user policy
is implicitly settled by choosing a local MVP, and roadmap Phase 3–5 remain future.

| Proposed separately approved slice | Prerequisites and acceptance/security gate |
| --- | --- |
| 1. Synthetic product-contract walkthrough | Review this blueprint; test ambiguous/changed/repeated steps and visibility in text. No real data, code promotion or usable client |
| 2. Single-user, no-sharing, independent per-source review MVP | Approve local operator boundary and durable review contract; prove version-bound saves, corrections, retry safety and no unauthorized disclosure. No canonical dedupe prerequisite, cross-source merge, tasks/writes, network or shared clients; schema work requires separate approval |
| 3. Authenticated backend and shared review expansion | Approve auth/roles, source/operation permissions, existence privacy, arbitration, CAS/idempotency, retention and hosting before shared/network reads or mutations. Credential migration/background execution remain separate work |
| 4. Canonical identity/linkage expansion | Approve reversible canonical links and step identity before cross-source grouping. Prove no incorrect suppression, disclosure or merge. This does not block slice 2 and need not precede unrelated per-source improvements |
| 5. Desktop/web then phone client review slice | Authenticated shared contracts enforced before network clients. Read-only cards/history, then explicit saves with stale warnings; no per-client truth or automatic accepted follow-ups |
| 6. Separate R1 task tracking slice | Approve task identity, request idempotency, assignee/date/reporting permissions and acceptance. Distinguish automatic suggestions from accepted tasks; prove retry safety and no automatic completion from changed evidence |
| 7. Phase 5 controlled R2/R3 actions, then notifications | Approve least-privilege scopes, version-bound action approval/invalidation, audit, idempotency, reconciliation and revocation; notifications are delivery only. No implicit review/task consent |

Existing ingestion/recovery, inference and human evaluation remain unchanged throughout
this checkpoint. Phase 3–5, API/auth/UI, worker/scheduler and task/execution work stay
unchecked on the roadmap. No new classifier, external model, content access or Finance
integration is a dependency granted by this document. Safe next work is a separately
reviewed narrow contract slice, not promotion of Phase 2V's disposable memory.

## Acceptance and ChatGPT review questions

1. Does the capability matrix distinguish implemented local operations, synthetic
   prototypes and future product/backend/UI/task functionality without implied promotion?
2. Do all three fictional journeys preserve the source → exact analysis/proposal →
   review → separate optional follow-up → tracked outcome boundaries, including no-task branches?
3. Can an authorized person find uncertain, invalid, rejected, deferred and previously
   reviewed items without silent dismissal or inferred household-wide clearance?
4. Are source-account identity, attribution, review responsibility and task assignment
   separate, with default-deny protection of data and existence through links/disagreements?
5. Are changed evidence, definition versions, stale displays, corrections and member
   disagreement handled without overwriting history or transferring old consent?
6. Does one backend enforce desktop/phone authorization, CAS and duplicate-prevention,
   with offline and revoked clients unable to mutate or execute independently?
7. Are preparation, cancellation, refund and rebooking distinct steps, with human
   reported completion separated from verified execution and Finance truth?
8. Are automatic R1 suggestions distinct from explicit task acceptance, and version-bound
   R2/R3 approvals separate from review/OAuth, with invalidation and no automatic execution?
9. Are privacy/display limits, notification tradeoffs and future study approval gates
   explicit, prohibiting real household data in every AI and preserving Holdout isolation?
10. Can a separately approved single-user/no-sharing per-source MVP precede Canonical
    Dedupe, while permission/task-identity decisions stay open and Phase 3–5 unimplemented?

## Documentation validation

The change is limited to this document and minimal README/roadmap links. Validate
relative link targets/anchors, three scenario paths, the capability/transition/risk
tables, ten review questions, untouched future implementation checkboxes and
`git diff --check`. No local evaluator, simulation, household DB or live model/provider
is run for this docs-only checkpoint. If the existing full-suite GitHub CI executes,
report its actual SQLite/PostgreSQL conclusions in the PR; that validates the retained
suite, not the proposed product UX or safety. There are no new executable tests.
The original checkpoint changed three Markdown files. This review follow-up changes
only this design document: permission/existence privacy, R1 suggestion vs acceptance,
approval/reporting/idempotency boundaries, a narrow local MVP dependency path and
future UX questions. Validate links, three fictional journeys, ten review questions,
balanced code fences, consistency with architecture/security and unchanged roadmap
implementation status. No new runtime behavior or executable tests are introduced.
