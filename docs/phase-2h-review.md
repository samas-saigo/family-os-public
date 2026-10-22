# Phase 2H review — local classifier audit and human evaluation

Closes Issue #18. Inspect real already-ingested metadata locally before treating
classifier output as trusted upstream canonical signals. This is a zero-egress
quality-measurement foundation, not proof of production accuracy, canonical truth,
Needs Action, a product review queue or an authenticated reviewer system.
Automated acceptance data remains entirely synthetic; no household audit was performed.

## Exact provenance and append-only labels

Alembic `913feab82c07` follows `7c19ad382ea1`. The executable
`analysis_evaluation_label` table stores only ID, household, exact analysis ID,
stable source ID, positive integer revision, three human label dimensions and UTC
creation time. A composite FK targets the existing analysis household/source/ID
unique key. Cross-household or cross-source references fail. There is no cascade,
reviewer identity, free-form notes, reasoning or source content in a label.

Relevance is relevant/irrelevant/uncertain; action is required/not_required/uncertain.
Domain is a taxonomy category/valid child or null/null for human unknown. Half-null
pairs fail. Application validation uses the selected validated classification policy;
SQL enforces label enums, paired domain shape, revision positivity/integrality and
unique `(analysis_id, revision)`. Taxonomy membership remains config-driven application
validation, just as for Phase 2F analyses. Direct trusted administrator SQL is outside
that contract; no DB roles or UPDATE/DELETE triggers are introduced.

`append_label` offers INSERT only. Corrections append revisions 1, 2, 3; old rows
and analysis/facts are never overwritten. Latest means **maximum revision**, not
latest timestamp. One revision supplies all three dimensions; unknown is explicit,
not an unlabeled dimension. The result contains safe ID/source/analysis/revision only.

PostgreSQL locks the target analysis row with SELECT FOR UPDATE before reading the
maximum revision and inserting. SQLite uses BEGIN IMMEDIATE before lookup/allocation.
The consistent order is writer reservation (SQLite), household existence lookup,
analysis row lock (PostgreSQL), definition/label validation, max revision, INSERT.
The transaction is short and uses no process mutex. Cooperative concurrent writers
receive distinct monotonic revisions. Uniqueness/operational contention can instead
raise safe typed `EvaluationRevisionConflictError` for an explicit retry; there is
no automatic retry loop or lost correction.

Historical analyses may be labeled by explicit ID. The selected taxonomy and
threshold policy must match their declared versions and definition content; an
explicit historical config is necessary when those versions differ. Historical
labels remain tied to the exact old analysis and never transfer to new inference.
Default audit/metrics still exclude all historical/noncurrent definitions.

Upgrade creates only the new child table/index. Downgrade drops evaluation revisions
as derived audit data, leaving source/raw/analysis/fact rows byte-for-value unchanged.
Back up labels before downgrade if needed. The Phase 2G blocked abstention downgrade
remains unchanged; crossing earlier migrations retains their documented restrictions.

## Current definition and snapshot selection

`family_os.audit_services` loads the current classification policy and exact same
MetadataRulesAnalyzer/rules parser as runtime. It resolves analyzer name/effective
version (including the rules content hash), taxonomy version, threshold-policy
version and policy definition fingerprint. Changed policy content without a version
bump fails closed through Phase 2F definition consistency checks.

Every eligible query joins immutable source_analysis to its stable source record
with **the same current raw_record_id**, exact declared definition and matching
fingerprint, in the requested household. Old snapshots, old analyzer/rule versions
and old taxonomy/threshold versions cannot substitute. Results include total current
sources, eligible count and missing count; missing means no exact current analysis,
not a fabricated historic/current prediction. Source-account provider alone is read;
account secrets, raw payloads and sync state are never selected.

Read services use one consistent transaction snapshot (PostgreSQL REPEATABLE READ;
SQLite explicit read transaction) for counts, records and highest label revisions.
A concurrent ingestion cannot mix counts from one snapshot with rows from another.
After a source update, its previous label leaves current metrics until its new exact
analysis exists and receives its own evaluation. These read transactions have no
provider or inference call.

## Deterministic bounded sampling

`audit_list` requires an integer limit 1–1000 and supports:

- `unlabeled`: no evaluation revision for that exact current analysis.
- `needs_review`: stored classifier review recommendation is true.
- `accepted`: stored classifier review recommendation is false.
- `balanced`: round-robin joint strata of provider, relevance label, domain
  classified/abstained and action label. SQL row_number ranks stable source IDs
  inside strata, then selection orders rank/stratum/source ID and applies the limit.

The first three order stable source IDs. Balanced is deterministic without a seed
or SQL random ordering. Output is bounded; counts/window selection can scan eligible
rows in the database, but never loads the whole household's metadata into Python.
It is a convenience inspection aid, **not statistically representative sampling**.
Metrics stream prediction/latest-label rows with bounded buffering; content columns
are not selected. A caller supplies local household scope; this is not authenticated
client authorization and must not be exposed as an unauthenticated hosted endpoint.

## Local display boundary and CLI

From the repository root after migration and analysis:

```sh
family-os analyze-metadata --household HOUSEHOLD --limit 100
family-os metadata-audit-list --household HOUSEHOLD --limit 20 --strategy unlabeled
family-os metadata-audit-label --household HOUSEHOLD --analysis ANALYSIS_ID \
  --relevance relevant --domain-category home --domain-subcategory utility --action required
family-os metadata-audit-metrics --household HOUSEHOLD
family-os metadata-audit-simulate --household HOUSEHOLD \
  --relevance-threshold 0.90 --domain-threshold 0.90 --action-threshold 0.90
```

Omit both domain flags for human unknown; relevance/action remain required. Each
command can select `--classification-config`; list/metrics/simulation additionally
accept `--rules-config`. CLI parses, delegates to callable services and prints
structured JSON. No scheduler or provider operation is attached.

`analyze-metadata` stays aggregate-only. **Only the explicitly invoked local audit
list** exposes minimized subject (max 8192 chars), sender (max 320), provenance,
provider/type/time, predicted labels/scores/review and latest human revision. Its
metadata projection uses fixed scalar paths: status, eventType, start.dateTime,
start.date, end.dateTime, end.date, mimeType, trashed and removed. Strings are limited
to 256 chars; flags must be booleans. Missing, wrong-shaped or oversized display values
are omitted rather than recursively serialized. Display keys are flattened paths.
Record repr suppresses subject/sender/display values; errors never stringify SQL or
private exceptions. Other commands return IDs or aggregates only.

There is no raw_source_record.payload read, account metadata/credential/cursor read,
provider-client construction, keyring/OAuth call or network access. Gmail bodies and
snippets, Outlook bodies/previews, Drive contents, arbitrary metadata, prompts and
reasoning remain excluded. Console output is local household data: protect any
operator-created redirects/exports and never commit them. Nothing is sent externally.

## Metrics and honest denominators

Only the highest human revision for each **eligible current analysis** contributes.
Every metric uses current eligibility, including confidently irrelevant stored sources.
Provider breakdown repeats the same definitions. Counts always accompany rates;
zero denominators return null, never invented 0% or 100%.

| Metric | Denominator / semantics |
| --- | --- |
| label coverage | labeled / all eligible |
| classifier review rate | stored review=true / all eligible |
| classifier domain abstention rate | predicted null/null / all eligible |
| domain coverage | predicted concrete pair / all eligible |
| relevance/action accuracy | exact prediction matches / human decisive labels in that dimension |
| domain selective accuracy | exact category+child matches / predicted classified AND human known domain |
| concrete relevant/irrelevant/action-required precision | correct / matching concrete predictions with decisive human label in that dimension |
| concrete false positives | contradictory decisive human labels for those concrete predictions |
| per-domain labeled | human known category count (latest revisions) |
| per-domain predicted | concrete prediction category count across all eligible, including unlabeled |
| per-domain correct | exact category+child agreement with human known domain |

Human uncertain labels are counted separately and excluded from decisive correctness/
precision denominators, not treated as evidence of a false positive. Predictions
under human uncertainty have their own concrete-decision unknown counts. Classifier
uncertain/abstained predictions against decisive human labels count as misses for
relevance/action accuracy; domain selective accuracy explicitly excludes classifier
abstention. Completely unlabeled analyses count toward eligibility, prediction coverage
and review rates, never toward correctness. The separate buckets remain visible.

These describe **only the labeled local convenience sample**, not automatically
household-population precision, recall or calibrated probabilities. Selection bias,
small denominators and misleading/missing metadata remain material limitations.

## Pure threshold simulation

`audit.simulate_thresholds` takes existing predictions/latest labels and validated
finite [0,1] candidate relevance/domain/action thresholds. `audit_simulate` selects
the same exact-current data as metrics. A simulated accepted record requires three
concrete predictions and all corresponding confidences >= candidate thresholds.
Uncertain/abstained predictions cannot become accepted even at threshold zero.
Stored review flags supply baseline accepted/review counts; simulation reports
candidate counts and deltas without changing a row, config or analysis version.

Observed joint precision = correct in all dimensions / accepted with decisive human
labels in all three dimensions. Observed labeled coverage = accepted fully decisive
labeled / all fully decisive labeled. Unknown/unlabeled are excluded from these
quality denominators, while still included in accepted/review totals. Acceptance here
is only counterfactual analysis, never a product review/task/action decision.

The six-record synthetic acceptance corpus intentionally includes a wrong accepted
prediction, classifier abstention, human unknown, unlabeled data and a corrected
revision across all four providers. After the correction:

- 6 eligible; 5 labeled (coverage 5/6); 2 review; 2 domain abstentions.
- Relevance accuracy 2/4; action accuracy 1/4; domain selective accuracy 2/3.
- Concrete relevant precision 2/3 with 1 false positive; required precision 0/2
  with 2 false positives. Concrete irrelevant precision is null because its only
  human label is uncertain.
- At thresholds 0.80: 4 accepted / 2 review, observed joint precision 1/3,
  decisive labeled coverage 3/4.
- At thresholds 0.90: 3 accepted / 3 review, observed joint precision 1/2,
  decisive labeled coverage 2/4. This is not an automatic recommendation to raise
  thresholds; it shows a precision/coverage tradeoff on a tiny synthetic sample.

## Validation and review questions

Python 3.12.14 validation: **1,006 tests passed on SQLite and 1,006 on real
PostgreSQL 16** (941 existing tests + 65 new Phase 2H tests). `pip check` and
`git diff --check` passed. Both suites include migration upgrade/downgrade/upgrade,
Alembic schema checks and preservation of populated analysis/fact history. Actual
concurrent writers are synchronized before database lock acquisition and produce
distinct revisions 1 and 2 on both databases. A concurrent-ingestion regression
verifies consistent audit counts/rows under each database's read snapshot.
Final GitHub CI status is recorded in the PR description.

Coverage includes
migration upgrade/downgrade, unchanged parent history, composite FK/label constraints,
concurrent append, max-revision selection, exact definitions/snapshots, bounded strata,
no-content/no-network SQL and API guards, denominator/provider/domain metrics and
pure simulation. Existing provider scopes/cursors/services and Phase 2F/2G runtime
behavior remain unchanged. One existing Phase 2G migration regression explicitly
starts at that revision now that a later child-table migration exists.

Questions for ChatGPT:

1. Do label FKs and append allocation preserve exact household/source/analysis
   provenance and distinct revisions under real SQLite/PostgreSQL concurrency?
2. Are current raw + exact analyzer/taxonomy/threshold/fingerprint joins and
   consistent read snapshots sufficient to prevent historical substitution or mixed metrics?
3. Are highest revision, human uncertainty, classifier abstention and unlabeled
   counts distinguished correctly, including zero-denominator and false-positive semantics?
4. Is fixed-path scalar display sufficiently minimized for explicitly local operator
   inspection, with no raw payload, account secrets or provider/keyring/network access?
5. Is deterministic joint-stratum sampling an appropriate bounded inspection aid,
   with its convenience-sample limitations stated clearly?
6. Does pure threshold simulation expose the tradeoff without altering definitions,
   persisted review flags, labels, config or any product task/action/review state?
7. Does the migration preserve all analysis/fact/source provenance in both directions,
   dropping only evaluation labels on downgrade?
8. Are external-model/content, authenticated API, canonical/dedupe and product review
   boundaries still deferred, so actual local labeled quality is inspected first?
