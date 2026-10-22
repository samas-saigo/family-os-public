# Phase 2I — local rule coverage diagnostics and diverse inspection

Closes Issue #28. A high review rate with no human labels is a coverage question,
not evidence that thresholds should be lowered. This change adds local rule
applicability measurement and small human inspection. It changes no production
rules, thresholds, engine version, provider behavior, schema or migration.
No real household data was accessed in development or committed to this repository.

## Shared runtime semantics

`MetadataRulesAnalyzer.analyze()` now returns the output of `diagnose()`; there is
one matcher, normalizer, caution veto and resolver. The diagnostic value contains
only safe configured rule IDs, dimension evidence states and structured output.
No matched words, sender domains, provider object IDs or evidence text are returned.
The existing effective analyzer version remains
`metadata-v1-e1-98b9e7219a73125b7292bd89`; predictions are unchanged.

Each dimension distinguishes no evidence, weak-only unanimous evidence, competing
targets, and strong unanimous evidence. Scores remain 0 / 0.55 / 0.90 deterministic
rule strengths, not statistical probabilities. Weak-only retains semantic abstention;
strong/weak disagreement still abstains. The caution-veto count reports records
where an otherwise matching positive rule was vetoed. Those rules are excluded from
actual match counts. Missing and oversized titles produce no matches.

`metadata-coverage` returns only aggregates over bounded dry-run current inputs:
provider population and inspected counts; present/missing/oversized titles; record
types; UTC month counts (including undated); any/strong match counts; every configured
rule ID including zero counts; per-dimension evidence outcomes and concrete/uncertain
or classified/abstained totals; review counts; missing sender/allowlisted metadata
availability; exact analyzer/policy versions and definition/rules fingerprints.
Missing-field counts are availability measurements, not proof that a particular
rule would match if that field were supplied. Fields irrelevant to a provider will
normally be absent. No-match outcomes are not described as threshold failures.

## Bounded deterministic sampling

Both commands select from **all household current source records**, including
unanalyzed sources, across every provider present and every account for that provider.
SQL window functions rank rows chronologically (UTC occurred_at, null last, ID ties)
within provider / UTC calendar-month / record-type strata. A second rank round-robins
month/type strata within each provider; the final order round-robins providers.
Only the final bounded rows' normalized metadata are fetched into the application.
There is no SQL randomness, retry loop or seed. Identical DB state produces identical
selection on SQLite and PostgreSQL. Diagnostics allow 1–1,000 rows; explicit display
allows 1–100. With three sufficiently populated providers, limit 45 gives 15 each;
with four, limit 60 gives 15 each. Sparse providers contribute fewer and spare capacity
is redistributed. A limit smaller than the provider count cannot cover every provider;
aggregate population counts make that omission visible.

The month order is ascending, so a bound too small for all strata favors earlier
months. Within one month/type it favors earlier records. This is a diverse convenience
inspection aid, **not statistically representative population sampling**. It avoids
leading UUID order and an already-analyzed-only prefix, but does not implement random
sampling, stratified weights, pagination or a configurable time range. SQL must rank
the household population; fetch/inference and application memory are bounded by
limit, while DB ranking cost still grows with population. Read snapshots are held
only for local SQL selection/counts, not classifier inference. No writes occur.

## Exact provenance and local display boundary

`coverage_services` selects normalized source fields and public account provider/owner
fields only. It never reads raw payloads, source account secrets/identities, sync state,
credentials or keyrings, constructs provider clients, or calls network/model APIs.
The aggregate CLI never prints subjects, senders, URLs, object IDs or input metadata.

Only `metadata-coverage-sample` explicitly displays minimized local metadata, after a
sensitive-output warning on stderr. It reuses Phase 2H limits and allowlist: subject
8,192 chars, sender 320; scalar display strings 256; status, eventType,
start.dateTime/date, end.dateTime/date, mimeType, trashed and removed. Recipients,
arbitrary metadata, bodies/snippets/previews/content and raw payloads are excluded.
No output file is created. Protect local console history and any deliberate redirects;
**do not paste or upload individual records to Codex, ChatGPT, GitHub or CI**.

The sample reports a persisted analysis ID only for the exact current raw snapshot
and analyzer/taxonomy/threshold versions/definition fingerprint. Otherwise predictions
are explicitly marked dry_run and analysis_id is null; historical analysis is never
substituted. Dry-run predictions cannot be labeled. An explicit analyze-one operation
uses unchanged `analyze_source`, then existing `metadata-audit-label` appends a revision
against that exact artifact. Capture and label the returned analysis ID, not an old
sample's ID. If ingestion races, the existing typed stale-input zero-write behavior
applies; inspect again explicitly. Label revisions, current metrics and history are
unchanged. No canonical facts, Needs Action, tasks or product review queue are created.

## Local Windows PowerShell workflow

Run only on the machine owning the existing runtime DB. From the repository root,
keep the intended DATABASE_URL configuration; these commands do not connect providers
or require keyrings. Replace HOUSEHOLD and safe IDs locally. Do not send sample stdout
to an AI service. Do not use a demo/onboarding DB as real evaluation data.

```powershell
$household = 'HOUSEHOLD'
# Aggregate-only: safe to share aggregate results, never individual records.
.\.venv\Scripts\family-os.exe metadata-coverage --household $household --limit 1000

# LOCAL SENSITIVE OUTPUT ONLY. Three providers: approximately 15 records each.
.\.venv\Scripts\family-os.exe metadata-coverage-sample --household $household --limit 45
# For four providers, use --limit 60 instead; do not run both as separate samples.

# For a sample with analysis_id=null, explicitly persist that chosen source first.
# Safe IDs only; capture the returned analysis_id. This is NOT a dry run.
.\.venv\Scripts\family-os.exe analyze-metadata --household $household --source 'SOURCE_RECORD_ID'

# Human judgment only. Replace all labels; omit BOTH domain flags if genuinely unknown.
.\.venv\Scripts\family-os.exe metadata-audit-label --household $household --analysis 'ANALYSIS_ID' --relevance relevant --domain-category home --domain-subcategory utility --action required
.\.venv\Scripts\family-os.exe metadata-audit-label --household $household --analysis 'ANALYSIS_ID' --relevance uncertain --action uncertain

# After human labels exist: aggregate-only labeled-sample metrics.
.\.venv\Scripts\family-os.exe metadata-audit-metrics --household $household
```

The two labeling commands are **alternative templates**, not instructions to label the
same record twice. A correction intentionally appends the next revision. Human labels
must reflect locally inspected minimized metadata; do not fabricate labels or send
subjects to AI for labeling. Inspect roughly 10–20/provider first, including supported
and unsupported outputs; review accepted predictions for confident false positives.
If coverage shows little evidence, propose separately versioned rule changes based on
local labels, with precision/false-positive safeguards and honest selective coverage.
Do not automatically loosen thresholds. Missing message/file contents and redacted or
misleading metadata constrain this baseline; external AI/content expansion requires
its own security decision. Zero labels means no precision/accuracy interpretation.

## Validation and ChatGPT questions

Python 3.12.14 validation uses synthetic inputs only:

- Full SQLite suite: **1,240 passed** (1,148 existing + **92 new** tests).
- Full real PostgreSQL 16 suite: **1,240 passed**, disposable per-test schemas.
- Both suites include existing migration upgrade/downgrade, concurrency, provenance,
  stale-source and append-only label/current metrics regressions.
- `pip check`: no broken requirements. `git diff --check`: clean.
- The same 30-case synthetic runtime evaluation remains unchanged: 14 classified,
  16 abstained, zero confident false positives; this is not real-world accuracy.
- Final GitHub CI conclusions and run link are recorded in the PR description.

1. Does the shared diagnose/analyze path preserve every existing match, veto,
   abstention, confidence and effective-version semantic without a second matcher?
2. Do aggregate diagnostics distinguish evidence strength/conflict/absence from
   metadata availability, without claiming accuracy or blaming thresholds?
3. Are provider/month/type ranking, UTC behavior, bounded fetch and documented
   ordering biases appropriate for a small diverse inspection aid?
4. Are exact-current persisted IDs and explicit dry-run outputs safe for the
   analyze-one → append-only label workflow, including ingestion races?
5. Does the reused display allowlist plus explicit warning maintain local-only
   metadata boundaries while aggregate commands/errors stay content-free?
6. Are production rules/thresholds, all providers, migrations, cursor/source history,
   immutable analyses and labels unchanged, with canonical/action layers deferred?
