# Family OS v0.1 / Stage D — household-first privacy and authorization contract

## Status, scope and authority

This document specifies a prospective authorization and synthetic conformance
contract, not production authentication, a provider integration or enabled task
system. The owner has approved the product direction: one coordinated household
workspace for two peer adults. The sharing profile, grant-update UX, field publication
and retention details below are recommendations for review, not implemented policy.
No Stage E, OAuth change, schema migration, real-mail processing or real provider
write is authorized. Examples are newly invented and synthetic; no private data,
real human labels, frozen Development/Holdout or AI/model execution is an input.

Stage A/B retain independent safety, business evidence and action authority; Stage C
remains a disposable single-operator illustration. Their isolation choices are not a
requirement for two permanently separate household inboxes or task databases.

References: [Slice 3 design](v0-1-action-first-routing-email-safety.md),
[Phase 2W workflow](phase-2w-product-workflow.md),
[Stage A](v0-1-synthetic-routing-contract.md),
[Stage B](v0-1-synthetic-phishing-policy.md),
[Stage C](v0-1-synthetic-action-first-demo.md),
[one-backend architecture](architecture.md#5-deployment-and-client-architecture),
[security boundaries](security.md#provider-oauth-and-family-os-client-access),
[data model](data-model.md) and [roadmap](roadmap.md).

Two equally necessary acceptance criteria govern the design:

- **Privacy & Authorization:** no disclosure or operation outside effective rights;
  source access, task sharing and operation authorization are independent.
- **Unified Household Management:** both peer adults centrally coordinate all jointly
  authorized information and task state, without compulsory source-by-source isolation
  or recurring per-message sharing confirmation.

## One workspace with permission enforcement underneath

The target remains one authoritative household backend/core and shared state serving
its authorized clients. Both adults work in the same My To-do, Pending Confirmation,
Security Review, Information and explicitly queried Offers surfaces. Their ordinary
shared workflow aggregates every authorized contributing source. A source selector,
assignee, member or personal view is a filter, not another authoritative task store.
No hierarchy, primary partner, parent/child role or mandatory personal isolation is
introduced. A person is not a source account; household membership alone is not a
mailbox grant. Adding future members means explicit recipient membership in grants,
not a new hard-coded hierarchy or automatic access to prior sources.

Authorization is evaluated before projection, ranking, grouping, dedupe suggestions,
search, counts, summaries, pagination, cached results, notifications or links. Include
all currently authorized contributors: the privacy filter is not an owner-only filter
and must not hide a peer's explicitly shared sources. For members with equal effective
grants, equivalent queries and the same state revision return equivalent projections.
Do not require opening two source-specific pages to see the shared backlog.

## Recommended one-time source-sharing setup

At connection/configuration, offer a clear recommended **Share with household** path
and an optional **Keep private / restrict** path. No connection or household enrollment
silently grants access; cancellation or unknown scope means no new grant. The proposed
sharing confirmation identifies the exact source, recipients, minimized fields,
analysis purpose, permitted operations, retention boundary and revocation behavior.
A private/restricted source is a supported explicit choice, not mandatory isolation
of all accounts. No per-message sharing prompt is needed within an active grant.

Recommended household-read/review profile:

- Both named peer adults may inspect approved minimized observations, their eligible
  analyses and source review/security history in unified views.
- Authorized R0 queries/search/aggregation and approved local analysis require no
  repeated sharing confirmation. The profile includes ordinary source-review
  annotation capability only when explicitly selected in setup.
- Explicit human review Save and separate task acceptance still express an intention;
  these are not repeated requests for permission to share/read the source.
- Task publication/editing and any future provider operation are distinct permissions;
  source sharing never grants mailbox mutation, standing quarantine consent, payment,
  deletion, credentials or permission to send data to any AI, including local Ollama.

A conceptual grant binds household, exact source, explicit recipients, field/purpose
scope, permitted operations, positive revision and active/revoked/unknown state.
Per-operation checks intersect the authenticated principal's effective rights with
current grants, exact evidence versions and centralized R0–R3 policy. This is a data
contract; no authentication mechanism, storage schema or API is selected here.

Each peer may control sharing for sources they are independently entitled to configure;
this resource-specific capability is not a superior household role. One partner cannot
silently grant or expand another partner's source permissions. A peer's operation right
must be explicit. Changing recipients, purposes or operations creates a new grant
revision with controlled confirmation and audit; no invitation, provider OAuth or
sender address substitutes for this right. Exact source-control verification and
invitation/account-recovery UX remain decisions requiring implementation review.

### Concurrent grant changes

Source, task and operation grant changes use their own authoritative expected-revision
and short transaction/CAS boundary. Two changes against the same revision cannot both
commit: exactly one may establish the next revision; the stale contender rejects with
no partial recipient, field, operation or audit-state effects. Record successful
changes in append-only authorized history. Recheck the editor's current scope at commit.
A source-control capability does not imply task-grant or operation-consent control.

For revoke versus scope expansion, if revocation commits first, the old expansion
request cannot revive access. If expansion commits first, the stale revocation must
reject and require a deliberate retry against current state; it is not reported as
completed. Never automatically rebase/replay an expansion over a revocation. A fresh
regrant requires independently authorized explicit intent at the current revision,
not an old approval. No persistence or concurrency mechanism is implemented here.

## Central task coordination and controlled field publication

A future accepted task has one household identity and authoritative revision.
Assignee may be either adult; an explicitly jointly managed task has a shared assignment
state. Both authorized members observe the same task status and ownership. One adult's
assignment filter changes presentation only; accepting, editing or completing one
shared task must not create a second per-account/per-member task.

A separate task grant governs reading and editing approved task fields, recipients,
assignment and shared task history. It does not confer access to underlying sources.
The exact field publication and task grant must be approved by a principal entitled to
publish the evidence-derived fields. A task cannot be used to launder private subjects,
senders, source IDs, evidence counts or unapproved inference into shared state.
Suggested bounded publication: an explicitly accepted neutral named step, explicitly
chosen assignee(s), task status, approved date only when supported, task revision and
a content-minimized freshness warning. This is a proposal, not a production allowlist.

Underlying source evidence, links, search snippets and source-specific audit remain
independently gated by source grants. Shared task counts count authorized tasks;
source-record counts count authorized observations. Do not substitute one for the other
or infer inaccessible evidence from a provenance count or a suppressed-source badge.
Review confirmation is not task acceptance; source read/review rights do not grant
shared task edit/acceptance rights. Neither grants execution or task completion by a
provider. Centralized R0–R3 confirmation and audit requirements remain unchanged.

### Independent revocation and permitted task continuity

Revoking a source grant immediately removes unauthorized source content, analyses,
provenance detail, source history, links, source counts, search and security entries.
Invalidate affected recipient projections/caches and queued disclosures. Recheck access
on use and on any later dispatch; no hidden-entry placeholder or global withheld count.
The member who retains source rights can still inspect that source in the unified
workspace. Filtering does not remove their authorized information for the other member's
privacy decision.

Previously explicitly published task fields may remain under an independent active
task grant. Source revocation does not automatically revoke that grant, delete the shared
task, complete it, split it or create a copy. The task has only its permitted published
fields and a neutral warning such as **Evidence freshness cannot currently be verified;
recheck before an evidence-dependent action**. No private source identity, contributor
count, revocation reason, new record existence or private update is disclosed.

Do not reread the revoked source to enrich/rewrite those shared fields. Subsequent
private arrivals, security changes or evidence revisions must not alter the recipient's
visible task fields, warning timing, counts or task history. A prior independently
published fact is not a license to publish future source changes. A new task field
publication needs valid source/publish rights and task permissions again.

Revoking task sharing independently removes task fields, counts, history and links for
that recipient even if their source grant remains active. A source-sharing toggle must
not silently redefine task sharing. Show both scopes clearly during authorized setup
and revocation. Task edit/assignment can continue under its own explicit rights, but
source-dependent acceptance/revalidation/provider actions stop when required current
proof is unavailable. Exact retention/redaction/deletion rights for published fields,
including requests to withdraw a task publication, require an explicit future policy;
this proposal does not grant indefinite retention or retroactive deletion authority.

### Exact versions, review history and safe concurrent intentions

Future decisions bind the exact evidence generation/snapshot, assessment and policy
versions, effective grant revisions and expected shared-state revision. Recheck all
required rights at final commit; stale or unknown dependencies fail closed without
partial writes. A changed then reverted payload is a new generation: earlier acceptance
cannot regain authority merely because its text/fingerprint matches. Prior decisions
remain immutable history, with history projection independently authorized. Ordinary
review confirmation never implicitly withdraws existing accepted intent on unchanged
evidence; explicit cancellation/lifecycle policy remains undecided.

Concurrent task edits require a short authoritative CAS/transaction contract, not
last-writer overwrite or separate member copies. An exact replay may return its prior
authorized outcome without duplicate effects, but a reused request key with changed
intent must reject. Replay never bypasses current read access or resurrects revoked
authority. No transaction, task lifecycle or persistence is implemented by Stage D.

## Common analysis and cross-source identity

Approved sources may participate in common household analysis; keep immutable original
source IDs, provider object IDs, evidence snapshots, analysis definition versions,
grant/policy revisions and audit. Derived views requiring several sources are available
only when the recipient has effective access to every dependency, unless exact task
fields have been independently approved for publication under the separate contract.
A model result, generated summary or partial authorized evidence must not reveal the
existence of a hidden contributor. A backend's ability to read an input is not authority
to disclose its output to every household member. Real household data still cannot
enter any AI, local or cloud; common analysis does not expand that boundary.

Use an explicitly supported common event/obligation identity to link observations:
for example, the synthetic conformance cases independently confirm the same invented
reservation reference and named preparation step. Title similarity, shared senders,
arrival proximity or two recipients alone is insufficient. Keep unresolved identity
as uncertain source observations; do not auto-create two household tasks merely because
two accounts received similar mail, or silently merge unrelated obligations. An explicit
human-authorized association may use one existing task with separately retained evidence;
canonical dedupe is not a hard prerequisite for the minimum unified workflow. No
canonical entities, dedupe engine, extraction or actual task creation is implemented.

Link projection and linking operations themselves require access to every exposed
source and authorized task fields. If one source later becomes private, retain protected
internal provenance according to its separate retention contract but do not show the
other member a missing-source placeholder, link count or a private evidence-change event.
An idempotency request identifies a delivery/attempt; it is not the identity of a task.

## Unified security review, independently gated operations

Security Review aggregates all mailboxes the current member may inspect, irrespective
of which partner connected them. A per-source filter is optional. Admission still
preserves safety/business/authority dimensions: authenticated/familiar/released senders
are not necessarily safe; unknown/stale safety does not clear content; suspicious
promotions cannot become Offers or household tasks. Promotion-only safety uncertainty
is inspectable in Security, not a Pending household obligation. Important legitimate
uncertain notices remain discoverable, including beyond display caps.

The source-read/security grant and source-specific operation consent are different.
A unified page does not allow one mailbox's consent to be applied to another. Future
provider quarantine/restore needs current principal rights, exact source and operation
consent, centralized risk approval, bound evidence, retention/recovery verification,
remote-state preconditions and independent outcome reconciliation. Stage D enables
none of it, including automatic quarantine or deletion. No emergency role bypass or
cross-member disclosure exception is introduced. Alerts, summaries and audit entries
must pass each recipient/source check before generation and any eventual dispatch.

An active sharing grant avoids repeating source-permission prompts for ordinary
already-authorized reads and review. It never eliminates the distinct confirmation
required to save a human decision, accept a task or approve an R2/R3 external operation.
Changing purpose, scope, recipients or action policy requires its own controlled grant
update; detecting an unusual message does not silently enlarge permissions.

### Queued disclosure and destination checks

Carry forward Slice 3's [recipient/source checks before alert generation and
dispatch](v0-1-action-first-routing-email-safety.md#security-alerts-and-multi-member-privacy).
A prepared notification or cached preview is not a durable disclosure grant. Recheck
the recipient's effective source, field and notification-purpose rights immediately
before dispatch against the authoritative grant revision. Recheck destination access
again when a link is opened. Revocation between preparation and dispatch suppresses
all now-unauthorized content, counts, previews, cached links and source-existence
signals; do not send a "withheld item" notice. A mixed aggregate may be recomputed
from remaining authorized sources only, without a hidden-contributor marker.

The future dispatch/revocation boundary must prevent a successful precheck from
acting as a stale authorization lease. If current rights or ordering cannot be
verified, do not dispatch source-derived material. Exact queue/cache enforcement is
a future reviewed design; no notification implementation or race-safety claim is
made here. Task publication rights never authorize a queued private-source preview.

### Trusted channels and revision-bound feedback

The Slice 3 [trusted verification-channel authority contract](v0-1-action-first-routing-email-safety.md#trusted-official-verification-channels--separate-authority-contract)
and [scoped feedback/audit contract](v0-1-action-first-routing-email-safety.md#audit-retention-and-false-positive-handling)
remain binding constraints on this shared workspace. Email, attachments, generated
summaries, extracted contacts and ordinary user release cannot create, change or
promote a trusted-channel entry. A copied contact or familiar sender is not verification.
At most, such material is an explicitly untrusted candidate.

Channel establishment/change requires an independently obtained authoritative source
outside the message chain, recorded verification provenance/method/time and purpose,
a separately authorized explicit confirmation bound to the candidate/channel revision,
and append-only old/new revision history. Access to that protected history remains
scoped; household sharing does not enlarge registry-edit rights. Recheck validity
before recommendation; stale, disputed or tampered channels remain unavailable/untrusted
until independently reverified. Source-control or task-edit permission is not channel
verification authority. No trusted registry or verification tool is implemented here.

Feedback appends the exact source/object, evidence generation, decision, detector/policy
versions, permitted actor and correction scope. A release can resolve only its authorized
item-level simulated outcome, not establish universal sender/domain trust, change the
global phishing policy or reduce protections for other messages. Broader policy changes
need separate evaluation, authorization and an explicitly approved new version. Feedback,
independent channel verification, scope and action authorization remain separate; no
summary or review confirmation can transfer authority between them.

### Retention versus recovery guarantees

Carry forward Slice 3's [coordinated review/restore retention contract](v0-1-action-first-routing-email-safety.md#audit-retention-and-false-positive-handling).
Protected original-location/delta evidence, provider preconditions, consent and outcome
revisions are necessary throughout an approved recovery window and unresolved simulated
quarantine/restore reconciliation. Routine expiry cannot silently discard the recovery
basis while continuing to promise reversibility. Source revocation restricts disclosure;
it does not grant unreviewed evidence deletion or access to protected recovery history.

A retention deadline or deletion request conflicting with that necessity requires an
explicit approved retention/deletion policy and an authorized, source-scoped warning
and recovery/deletion choice before evidence removal where that policy permits. This
does not presume indefinite retention, suspend future approved deletion rights or
force restoration against later user changes. If evidence is lost/unavailable or the
conflict cannot be safely resolved, mark recovery unavailable/unknown/needs review as
appropriate; never claim restoration success without an independently verified outcome.
Failure to maintain/revalidate recovery guarantees blocks new automatic quarantine
under the affected contract, not a fallback irreversible move or automatic release.

Any removal required by a future approved deletion policy must honor that policy and
explicitly end unsupported recovery guarantees rather than claim evidence remains.
Exact coordinated windows, deletion obligations and safe warning/disposition remain
review decisions. Stage D models these failure requirements only: it retains/deletes
no actual records, sends no warning and performs no quarantine/restore or Stage E work.

## Newly authored synthetic conformance contract

All names/records below are fixed fictional symbols. This is a prospective acceptance
matrix, not executed production authentication or evidence of runtime security. Tests
for any later approved synthetic implementation must check both confidentiality and
complete inclusion of authorized sources. No real data or frozen corpus may be used.

Setup: adults **Aster** and **Robin** are peers in household H. Separately connected
mailboxes Oak (Aster) and Pine (Robin) each contain one permitted synthetic observation,
O1 and P1. Both exact source grants share minimized read/analysis/security/review with
both adults. Independent synthetic evidence binds O1 and P1 to invented reservation
REF-7 and its same named preparation step. A separately confirmed publication grants
both adults access/edit to one hypothetical task T1 (jointly managed), with approved
neutral step/status/assignee/freshness fields. No actual task exists.

| Case | Input/change | Required result for both success criteria |
| --- | --- | --- |
| D01 — shared dashboard | Both source grants active | Both see the same unified authorized observation set {O1,P1}; source-observation count 2, not two owner-isolated dashboards |
| D02 — common task | Both observations independently support REF-7's same step; T1 separately approved | Exactly one hypothetical household task T1; both authorized provenance paths remain distinct internally; task count 1 for each adult |
| D03 — ownership consistency | Approved T1 assignment changes from joint to Robin at a new task revision | Both see that same revision/assignment; member filters do not create/delete a task copy |
| D04 — no redundant permissions | Repeat authorized browse/search/analysis/security inspection within unchanged grants | No new source-sharing prompt; identical effective rights yield identical authorized results |
| D05 — explicit decision distinct | Review O1 within grant, then propose acceptance of T1 | Review Save records only review; task acceptance requires its own explicit authorized intention; no execution rights |
| D06 — Pine becomes private | Robin revokes Aster's Pine grant, leaving Robin's rights and T1 grant intact | Aster sees only O1 in minimized source search/counts/security; Robin sees {O1,P1}; both still see approved T1 fields, task count 1 and consistent ownership |
| D07 — safe continuity | Same revocation as D06 | Aster has a neutral task freshness limitation; no Pine identity, hidden evidence count, private revision or suppression badge is revealed |
| D08 — subsequent private update | After D06, P1 changes or a new Pine message arrives | Aster's permitted task fields/warning/history and source projection remain unchanged by that private event; Robin's source view may update within Robin's rights |
| D09 — independent task revocation | Remove Aster's T1 grant while Oak read grant remains | T1 disappears from Aster's task counts/search/history; O1 remains available under Oak; Robin's T1 remains intact |
| D10 — unsafe source link | Aster tries a stored Pine source link after D06 | Generic unavailable response with no source identity/record/reason; no link side channel or automatic task grant expansion |
| D11 — all source reads denied | Both source grants ineffective for Aster; approved T1 publication still independently shared | Source observations/counts/security/search are empty; approved task fields can remain; source/task counters stay distinct |
| D12 — similar titles only | Two newly invented mail subjects resemble each other, with no supported shared obligation identity | No automatic merge and no automatic duplicate tasks; uncertain source suggestions remain unresolved until independently associated/accepted |
| D13 — shared security | Both security-read grants active; O1 suspicious and P1 important/indeterminate | Both inspect one combined authorized security backlog of 2; not separate compulsory per-source workflows; no safety clearance/task from either |
| D14 — operation mismatch | A hypothetical future consent names only Oak; attempt names Pine | Reject operation even if Pine is readable; no provider call, wider scope or default consent; Stage D always performs no real writes |
| D15 — unknown/revoked revision | A source grant revision becomes unknown, stale or revoked before projection/save | No disclosure/operation from that source; stale saves fail without partial changes; changed/reverted evidence never revives old acceptance; another active source remains aggregated |
| D16 — hidden population | Add any number of inaccessible observations, duplicate markers or invalid hidden identity proposals | Authorized output/counts/ranking/pagination and observable collection validation do not change because of those records; filter before validation/grouping |
| D17 — mixed promotion | Important independently evidenced service question overlaps with an advertisement | Appropriate authorized household question remains available; advertising urgency creates neither task nor deadline; unsafe promotion stays security-held |
| D18 — routine collaboration | Both have authorized T1 coordination rights; one intentionally edits an approved field | Other sees the same new shared task revision; no recurring source-sharing confirmation or secondary owner approval imposed by a hierarchy |
| D19 — queued disclosure after revocation | A Pine notification for Aster is prepared while shared; Robin revokes Aster's Pine access before dispatch; an old cached link is also opened | Recheck authoritative effective rights immediately before dispatch and destination access on opening; deliver no Pine content, count, preview, cached link or existence signal, including no withheld-item notice; any remaining Oak aggregate includes only authorized observations; T1 publication does not authorize the private preview |
| D20 — conflicting grant revisions | Two independently permitted commands against grant revision g7 request revoke versus scope expansion; run both commit orderings | At most one establishes g8 at the authoritative revision/transaction boundary; the stale command rejects with zero partial effects; revoke-first never permits old expansion to resurrect access, expansion-first never reports the rejected revoke as applied; no automatic rebase; deliberate authorized fresh intent is required; source/task/operation grants remain independent |
| D21 — retention/recovery conflict | A simulated Pine hold/restore remains unresolved when protected evidence approaches routine expiry or an approved deletion obligation; repeat with evidence lost/unavailable | No silent expiry while still promising recovery; apply the separately approved retention/deletion policy and authorized warning/choice, without presuming indefinite retention or overriding approved deletion rights; if guarantees fail, block new automatic quarantine under that contract, mark restoration unavailable/unknown/needs review and claim no unsupported success; any required evidence removal ends its guarantee, never overwrites later user changes or auto-releases; no actual record deletion or provider operation |
| D22 — channel and feedback authority attack | An Oak email and its generated-summary candidate request replacing a trusted contact and trusting all sender mail; repeat through an ordinary authorized user release at evidence e4/policy p3 | No trusted-channel registry change, universal sender/domain trust or global phishing-policy mutation; content remains untrusted; release appends only scoped version-bound feedback/history; channel change separately requires independent outside-message verification, permitted authority, current candidate revision and explicit confirmation; any broader policy change needs separate evaluated approval/version; protected history is disclosed only within its own scope |

D01–D04 and D18 test **unified management**, not just absence of leakage. D06–D11 and
D14–D16 and D19–D22 test **privacy and adversarial safety**, not enforced
fragmentation. A compliant implementation must pass both. Equal grants must not produce owner-only projections; different grants may
legitimately produce different source counts while still sharing approved task state.

## Documentation validation and implementation limits

Review the 22 ordered cases as **definitions**, not executable permission tests or
proof of production enforcement. Document checks cover local Markdown links/anchors,
fences, case completeness and a change allowlist limited to this document plus
README, roadmap and the Slice 3 reference. Existing SQLite/PostgreSQL CI remains
regression evidence for unchanged runtime only; actual run/job conclusions and test
counts belong in the PR handoff. No new executable tests, model run, auth service,
provider operation, database/migration or Stage A/B/C behavior is added here.

Any later executable synthetic contract must test equal-grant aggregation and denied
access, cross-source task continuity, unknown rights, revision changes/reverts,
concurrent intents/grant changes, queued revocation before dispatch/opening, protected
recovery retention conflicts and channel/feedback authority attacks, not merely
owner-only filtering.
Passing it would still not authorize production or real-mail processing.

## Unresolved decisions and review gate

Owner-approved direction: unified workspace, two peer adults, simple explicit revocable
sharing, shared state with independent source/task permissions, no mandatory isolation.
Recommended but pending policy approval: exact setup profile and field publication,
source-controller proof/delegation, task edit/assignment/completion conflict handling,
revocation and cache invalidation mechanism, coordinated retention/deletion, independently
published task warnings and audit visibility. Authentication, APIs, production grants,
schema, providers and Stage E remain separate implementation decisions.

ChatGPT and independent Muse should assess:

1. Do equivalent grants yield complete shared household views rather than separate
   personal inboxes, while inaccessible sources never affect observable aggregates?
2. Does one-time explicit sharing avoid redundant prompts without bypassing intentional
   review Save, task acceptance, risk policy or source-specific operation consent?
3. Is task continuity independent from source access, without newly revealing private
   evidence, stale-event timing, source counts or provenance after revocation?
4. Are two peer adults equally able to coordinate one task, with no implicit household
   mailbox rights, hierarchy, invented canonical task identity or duplicate account tasks?
5. Are all recommendations, unresolved permissions/retention questions and synthetic
   versus implemented claims explicit enough before any production or Stage E work?
6. Do dispatch/revocation races, conflicting grant changes and recovery-evidence expiry
   fail closed without suppressing independently authorized household coordination?
7. Do independent trusted-channel verification and revision-bound feedback remain
   separate from source sharing, release and broader phishing-policy authority?

This amendment must remain unmerged until independent review and a human merge decision.
