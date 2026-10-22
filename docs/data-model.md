# Data Model Principles

## Household

Top-level tenancy boundary.

## Person

A real household member.

A person may have:
- many email addresses
- many calendars
- many cloud-storage accounts
- many financial accounts

## SourceAccount

A single connected account or integration instance.

Examples:

```yaml
provider: gmail
external_account: adult.personal@example.com
owner_type: person
owner_id: person_a
```

or

```yaml
provider: gmail
external_account: household.shared@example.com
owner_type: household
owner_id: household
```

## SourceRecord

Stable provider-object reference with a mutable latest normalized view. Its
`raw_record_id` points to the current minimized raw snapshot; older raw snapshots
remain stored. Source identity and snapshot identity are distinct.

This is crucial for:
- provenance
- reprocessing
- model upgrades
- deduplication
- auditing

## SourceAnalysis and AnalysisFact (Phase 2F)

An analysis is a versioned inference about one exact source snapshot, not canonical
household truth. Executable `source_analysis` stores the stable source ID, exact raw
ID, household/account/provider-object provenance, analyzer/config versions, input
fingerprint, three label/confidence groups and a review signal. Composite foreign
keys bind source and raw to the same household, account and provider object; there
is no cascade deletion of referenced provenance.

The unique key is `(source_record_id, raw_record_id, analyzer_name,
analyzer_version, taxonomy_version, threshold_policy_version)`. Existing results
are returned without inference or updates. Deliberate reprocessing needs new
versions. Historical results remain on their original raw snapshot even when the
source's current raw ID changes. Current queries require both current raw ID and
an exact requested analysis definition, rather than a global newest timestamp.

`analysis_fact` contains JSON proposals, confidence, bounded evidence paths into the
exact input, deterministic zero-based ordinals and per-fact review signals. Names
may repeat. Facts belong to one analysis and the same household/source record.
No free-form reasoning, prompts or raw model responses are stored.

Phase 2G permits explicit domain abstention: category and subcategory are both null,
with finite confidence and `review_recommended=true`. A classified pair must be an
existing taxonomy category/child; a half-null pair is invalid. Abstention is analysis
state, not a fake taxonomy domain. Existing classified history is unchanged.

Validated thresholds set `review_recommended` only. Classification uncertainty or
low classification confidence flags the analysis; low fact confidence flags only
that fact. This creates no review queue, canonical entity, task or action, and even
confidently irrelevant sources remain stored. See [Phase 2F review](phase-2f-review.md)
for input, validation, stale-source and privacy contracts.

## AnalysisEvaluationLabel (Phase 2H)

`analysis_evaluation_label` is local classifier-quality measurement, not canonical
truth or the product review queue. A composite FK binds household/source/analysis.
Corrections append immutable positive revisions; unique `(analysis_id, revision)`
and short database locks prevent lost/duplicate revisions. Latest means max revision,
not timestamp. Human uncertain/null-domain is distinct from no human label. No
notes, reasoning or reviewer identity is stored. Current audit requires the exact
classifier definition and source's current raw snapshot; historical labels never
transfer to newer analysis. Downgrade removes only evaluation rows, preserving all
source/analysis/fact history. See [Phase 2H review](phase-2h-review.md).

## CanonicalEntity (future design)

The real-world object inferred from one or more source records.

Examples:
- one hotel reservation
- one insurance policy
- one Amazon purchase
- one Volvo
- one veterinary appointment

A canonical entity can have many source records.

## Provenance

Never store only:

```text
renewal_date = 2026-11-15
```

Store:

```text
renewal_date = 2026-11-15
source = Gmail message XYZ
extractor = admin_extractor_v2
confidence = 0.97
```

## Review Queue (future design)

Use when:
- owner unclear
- duplicate match uncertain
- conflicting dates
- action required uncertain
- extraction confidence below threshold

The system should ask humans about exceptions, not normal cases.

## Internal household authorization (G2a)

Five new executable tables reuse Household, Person and SourceAccount: current membership,
source-read grants, publication permission resources, recipient publication-read grants,
and append-only-through-service authorization audit. Composite FKs preserve household
scope; compound current-row keys prevent ambiguous duplicate grants. Source/publication
grants bind the current recipient membership revision. Audit separates actual actor from
affected person, old/new state/scopes and committed revision; historical allowed entries
are never effective permissions. Source-object identity excludes snapshot generation.

Publication resources are permission anchors, not canonical tasks or a task workflow.
No new person/account registry or provider record processing is introduced. See
[G2a migration, bootstrap and trust limits](v0-1-durable-household-authorization.md);
real authentication, protected DB roles and production field publication remain future work.

## G2b1 external identity binding

Migration `8a421d6c09be` adds `external_identity_binding`: global unique exact
`(issuer, subject)` maps to one existing `(household_id, person_id)` through a tenancy
FK, with allowed/revoked state and positive revision. Multiple separately approved
bindings may eventually map to one Person; no automatic linking/enrollment exists.
No token, email, password, session or provider credential is stored. Identity resolution
rechecks current G2a membership and confers no source/publication/action authority.
Downgrade removes bindings only, leaving authorization/provenance history unchanged.
See [trust profile and migration limitations](v0-1-verified-identity-boundary.md).

## G2b2 durable sessions

Migration `c35b79a12e04` adds `household_session` and append-only-through-service
`session_audit`, plus an exact external-binding tenancy uniqueness index. Sessions bind
existing household/Person/issuer/subject, membership/binding revisions, unique one-way
bearer verifier, CAS revision and server-controlled activity/expiry/revoked state.
Audit retains actual self actor, affected member, resulting/prior session, request/intent,
event, committed outcome and time. No plaintext secret/assertion/provider metadata is
stored. Downgrade removes only these sessions/audit/index, not earlier authorization or
source provenance; deletion/backup/retention need separate operator approval.
See [read integration, migration and disclosure limits](v0-1-session-service-boundary.md).

## T1 durable fictional household domain

Migration `e41a9b720dc3` adds six tables: `household_pending_item`,
`pending_member_right`, `pending_task_publication`, `household_task`,
`task_member_grant` and `task_domain_event`. Stable proposals carry private exact
generation/evidence/definition bindings and shared resolution; each member's review
and disposition are independent annotations. Explicit acceptance atomically creates
one task per proposal with approved neutral step/assignee/status/optional date and
separately approved recipient rights. Task origin stays private and is not selected
by task projections. History is append-only through services, actor-attributed,
household-tenanted and unique by exact request and resulting resource revision.
Current permission rows are separate from audit and pinned to membership epochs.
Upgrade does not rewrite source/analysis/session history; downgrade removes T1 data
and history only. [Contract, limitations and UI-facing fields](v0-1-durable-household-tasks.md)
describe the internal fictional scope; this does not enable real task extraction.

## I5 fictional producer ledger

Migration `f52b8c730ed4` adds only `fictional_information_revision`: household/source/record/generation
identity, bounded finite evidence, hashes, rule/origin and processing outcome, with an optional
T1 Pending FK. It is append-only through the isolated synthetic coordinator, not a new
Task store or production ingestion path. Downgrade drops only this ledger; existing source,
Pending, Task and human history remain. See [I5 contract and downgrade limitations](stage-i5-information-to-pending.md).

## I8 personal dispositions

Revision `063c9d841fe5` extends the T1 disposition/event CHECKs and adds nullable `task_domain_event.personal_reason`, constrained to three codes for NOT_APPLICABLE only. No new store or reason cache; old events keep NULL reasons and unchanged intent hashes. RESUME preserves viewed state/history. Any I8 event blocks destructive downgrade, even after return to active. See [I8 migration and privacy contract](stage-i8-personal-not-applicable-resume.md).

I8's owner-approved personal semantics treat exact-current-evidence own REVIEW or
NOT_APPLICABLE events as viewed proof. New NOT_APPLICABLE atomically sets both
reviewed and disposition in one event/revision; legacy I8 events use the same
projection without rewriting history. The compatibility boolean is not an independent
current-state source and is refreshed on a subsequent personal write. No additional
schema/migration is required; see the I8 contract for replay and change/revert rules.
