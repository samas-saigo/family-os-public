# Phase 2J — recent local interactive metadata review

Closes Issue #30. This is a small local operator evaluation tool, not the product
review queue, a dashboard, a training pipeline or a network service. It makes the
existing analysis → human label → aggregate metrics workflow practical without
manual source IDs. No real household records were accessed during development.
One human label cannot establish classifier precision, recall or population accuracy.

## Date window and deterministic recent selection

`metadata-review` requires `--since YYYY-MM-DD`, inclusive at 00:00 UTC.
`--until YYYY-MM-DD` is exclusive at 00:00 UTC. If omitted, the upper bound is
tomorrow's UTC date, captured when the session starts; records later than that bound
are excluded. Dates must use the exact format, be valid and satisfy since < until.
No machine-local timezone conversion is applied. SQLite's normalized naive timestamps
are UTC; PostgreSQL comparisons use timezone-aware UTC bounds.

`occurred_at` is the persisted source occurrence/provenance timestamp, **not** the
ingestion time. Gmail/Outlook message occurrence and Calendar/Drive creation/update
provenance differ; Calendar event start/end remain display metadata. A recent event
start does not move an old provenance timestamp into the recent cohort. Missing
timestamps are excluded; no date is invented. A 1900 placeholder is excluded by a
2026 window and is never relabeled as current. Deliberately selecting a historical
window preserves its actual dates, including placeholders if explicitly in range.

Select from all current household source snapshots, including unanalyzed sources and
multiple accounts. Optional `--provider` selects gmail, outlook, google_calendar or
google_drive. Limit defaults to 15 and must be 1–50. Default selection excludes
human-labeled analyses only when their raw snapshot and exact current classifier
version/taxonomy/threshold/definition fingerprint match. Historical labels never
transfer to a new snapshot or definition. `--include-labeled` enables corrections.

Within each provider/record-type stratum, rows sort occurred_at descending, then
stable source ID for ties. A second ranking round-robins types inside each provider,
prioritizing the newest type candidates, then the final order round-robins providers
with recency and stable ties. Sparse strata redistribute slots. Providers are all
represented when the limit is at least the number present; a smaller limit favors
providers with the newest candidate dates. Selection is deterministic for the same
DB/config/window and has no randomness, retries or leading-UUID bias.

This intentionally favors recency and provider/type coverage. It is **not statistically
representative sampling**; rare types/providers may be overrepresented. Use explicit
recent versus historical cohorts and report label denominators. SQL ranking cost grows
with the date-window population; application metadata fetch and dry-run inference are
bounded by 50. Sampling happens once, not in an endless refill loop. Skipped records
are not marked reviewed and may reappear in a later session. Newly labeled current
records are skipped next time, allowing repeated small sessions to make progress.

## Terminal presentation and controls

The CLI is a presentation adapter over callable `review_services`. It checks both
stdin and stdout are interactive **before creating a DB engine**. Piping, redirected
stdout/stdin and noninteractive scripts fail with fixed guidance; no records are selected
or unexpectedly labeled. Automated tests supply synthetic in-memory TTY streams.

One record is shown at a time, with provider, type, occurrence, bounded subject/sender,
allowlisted display metadata, prediction labels/scores/review flag, persisted vs
dry_run status and latest human revision/labels. Safe classifier name/version is
shown for the session. Source/raw/analysis IDs are not needed or printed in the terminal.
Source text is JSON-escaped to prevent terminal-control characters from impersonating
prompts. No raw payload, account secrets, recipients, bodies/snippets/previews,
attachments, Drive contents or arbitrary metadata is displayed.

The fixed Phase 2H display allowlist remains status, eventType, start.dateTime/date,
end.dateTime/date, mimeType, trashed and removed. Subject max 8192, sender max 320,
scalar display strings max 256; wrong-shaped/oversized values are omitted. Sensitive
values are suppressed from service repr. No source content is logged or exported. Prediction confidence values remain
deterministic rule strengths, not calibrated probabilities.

- `s` / `skip`: advance, no writes and no implicit irrelevant/dismissed label.
- `l` / `label`: explicitly choose all three human dimensions. No model/human
  prediction is prefilled or silently inherited. Numbered choices or exact listed
  names work; invalid choices reprompt without echoing the input.
- Domain `unknown` sets both category and subcategory null. Otherwise select a
  validated taxonomy category and one of its valid children; no half-null domain.
- Relevance: relevant / irrelevant / uncertain. Action: required / not_required /
  uncertain. Always judge only the locally available minimized evidence.
- `b` / `back`: previous logical label prompt. Relevance returns to the same
  record's action menu; domain returns to relevance; subcategory returns to domain;
  action returns to subcategory (or domain when unknown); confirmation returns to
  action. Keep going back to change earlier fields. Re-entered fields require an
  explicit new choice; changing domain clears the old subcategory and action.
- `c` / `cancel`: discard every unfinished choice and return to the same record's
  action menu. Start labeling again from relevance, skip, or quit. No prediction or
  discarded label is prefilled.
- A complete proposed label is shown; **type `save`** to confirm. At confirmation,
  Back edits the action; Cancel, empty input, `yes` or any other unconfirmed response
  discards the draft and returns to the same record's action menu without writing.
- `q` / `quit`, EOF or Ctrl+C aborts the current unsaved record and ends the session.
  Previously confirmed commits remain durable; a current interrupted transaction
  rolls back. Overlong input also aborts safely.

The final JSON summary contains only displayed / skipped / labeled / aborted /
changed_source / failed counts and per-provider counts. Each displayed item has one
outcome. Back/Cancel do not redisplay or count the record again, and do not increment
failed, labeled or aborted counts; its eventual skip/save/quit determines the outcome.
Unvisited items after quit are not counted as displayed. No titles, senders,
metadata or IDs appear in the summary. It is aggregate session activity, not accuracy.
Keep the earlier **sensitive record display local**; never paste, upload or record it
in Codex/ChatGPT, GitHub or CI. No file is produced by default.

## Confirmed persistence and exact-display race protection

A displayed ticket binds household + stable source + raw snapshot + full Phase 2F input
fingerprint + exact analyzer/taxonomy/threshold/rules and definition fingerprints.
Selection/dry-run inference and all keyboard interaction hold no DB connection or lock.
Merely displaying, skipping, quitting or canceling does not create analyses or labels.

On confirmed save, current local config must match the displayed definition; all human
labels validate against that taxonomy before inference. The service uses the shared
preparation phase of `analyze_source`, checking the displayed input fingerprint before
any inference. Existing exact immutable analysis skips inference; missing analysis is
prepared through the unchanged runtime analyzer outside a DB transaction.

The final transaction reuses the extracted `analyze_source` persistence code and
`append_label` revision allocator, **rather than two separately committed operations**:

1. SQLite BEGIN IMMEDIATE writer reservation, or PostgreSQL household row FOR UPDATE.
2. Lock/re-read source and require displayed raw ID and full input fingerprint.
3. Household-scoped definition consistency and exact-analysis idempotency checks.
4. Insert analysis/facts if missing; otherwise reuse the immutable exact analysis.
5. Revalidate bounded local config after waiting for locks and before labeling.
6. Lock analysis for revision allocation, then append validated human revision.
7. Commit together, retaining the source lock through label insertion.

This closes the display → analysis → label gap: an external ingestion writer cannot
change the source between the final check and label commit. A changed/deleted source
or changed definition raises safe `ReviewChangedError`; the entire attempt writes
zero new analysis/fact/label rows, while existing history stays intact. A label failure
or typed revision conflict rolls back a newly inserted analysis as well. Restart the
review for an explicit refresh/retry; no automatic retry, cursor reset or source edit.

The public Phase 2F analyze_source and Phase 2H append_label contracts remain unchanged.
Only their internal preparation/persistence/allocation helpers are shared to coordinate
the atomic operation. Analysis input now selects only provider/owner account fields,
not the entire account row; raw lookup selects only its ID, never payload. Lock order
is household/writer → source → definition/exact analysis → analysis/facts → analysis
label allocation → label. Existing historical-label API remains intentionally available;
interactive review adds an exact-current display guard without changing that API.

Concurrent confirmations for one snapshot reuse one analysis and append revisions
1 and 2, rather than overwriting or losing a label. Legacy append_label locks only
its analysis; it never acquires household/source locks in reverse order. No process
mutex, schema change, DB migration or credential migration is introduced.

Config is read at selection, confirmation, after inference and before label insertion.
These are validated snapshots of bounded local files, not OS locks on editors; make
intentional config edits **between sessions** and restart review afterwards. Inference
and human input never hold transaction locks; only the final small config check runs
inside persistence. A hard process kill may prevent printing a complete summary; the
DB transaction still determines whether a confirmed commit completed.

## Exact Windows PowerShell steps after merge

On the user's own local machine, from the existing repository root:

```powershell
git switch main
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install --no-deps -e .

$household = 'HOUSEHOLD'
# Interactive local terminal only: no pipe, tee, redirection or transcript recording.
.\.venv\Scripts\family-os.exe metadata-review --household $household --since 2026-01-01 --limit 15

# A narrower recent window: Oct 1 inclusive to Oct 9 exclusive, UTC.
.\.venv\Scripts\family-os.exe metadata-review --household $household --since 2026-10-01 --until 2026-10-09 --limit 15

# Optional provider-specific cohort, or corrections using the explicit override.
.\.venv\Scripts\family-os.exe metadata-review --household $household --since 2026-01-01 --provider gmail --limit 10
.\.venv\Scripts\family-os.exe metadata-review --household $household --since 2026-01-01 --limit 15 --include-labeled

# Aggregate-only metrics after deliberate human labels have been saved.
.\.venv\Scripts\family-os.exe metadata-audit-metrics --household $household
```

Replace HOUSEHOLD locally. Preserve the existing intended DATABASE_URL or normal local
SQLite configuration. Do not reset/create/copy a runtime DB or use onboarding/demo data
as real validation. No new migration is needed for this phase; the merged Phase 2H
schema is required. Provider keyrings/browser OAuth are not used. Config overrides
`--classification-config` and `--rules-config` select validated local files when needed.
The commands above are alternatives/cohorts; start with one small recent session,
inspect false positives as well as uncertainty, then inspect aggregate labeled-sample
metrics. Do not feed individual metadata to AI for labeling or generalize from one label.

## Boundaries, validation and exact ChatGPT questions

Classifier rules/thresholds/effective analyzer identity are unchanged, as are provider
scopes, keyring behavior, ingestion/query/cursor/page/CAS and immutable source history.
No external model/AI, network service, dashboard, review queue, task/action creation,
canonical facts/dedupe, scheduler, training, content expansion or Finance work is added.
This is zero-egress local evaluation under operator DB access, not authenticated client
authorization. A future backend adapter still needs explicit auth/household policy.

Python 3.12.14 validation: **1,308 tests passed on SQLite and 1,308 on real
PostgreSQL 16** (1,240 existing + **68 new**). Both full suites include migration
upgrade/downgrade and existing concurrency/provenance/label metrics regressions.
`pip check` and `git diff --check` passed. The same 30-case synthetic classifier
evaluation remains unchanged, with 14 classified / 16 abstained and zero confident
false positives; these are not production-quality claims. Final GitHub CI run/status
is recorded in the PR description.

Synthetic acceptance covers UTC/null/1900 boundaries, recent type/provider fairness, multiple
accounts, exact labeled exclusion, empty cohorts, controls/invalid choices/confirmation,
TTY/redirect safety, escapes/display bounds, repr/log/privacy, no clients/keyrings/raw
payloads, no inference/prompt transactions, changed sources/config, atomic rollback,
concurrent confirmations, source-lock coverage and explicit retry. Full suites retain
existing provider, migration, household-definition and label/metrics regressions.

1. Do the date boundaries, occurrence-time meaning, missing/placeholder handling and
   recent provider/type ranking resolve the old-cohort problem without statistical claims?
2. Do exact snapshot/version/fingerprint tickets and the shared final transaction prevent
   labeling a different source/definition, including races after inference and before append?
3. Does helper extraction preserve analyze_source idempotency/stale/household-definition
   invariants and append_label historical/revision/concurrency behavior?
4. Are no-write skip/quit/unconfirmed/failed-save semantics and no-transaction prompts
   explicit, with only safe aggregate session statistics and deliberate human choices?
5. Are the reused allowlist, control escaping, TTY checks and local-only instructions
   sufficient for this operator workflow without private logs, exports or data egress?
6. Are current-config snapshot limitations and sampling/skip bias honest, with future
   dashboard/auth/model/content/canonical/action work still deferred?

## Navigation follow-up (Issue #32)

Only terminal prompts, synthetic tests and documentation change. The existing selection and save
services, final transaction, current-snapshot checks, classifier and database schema
remain unchanged. All drafts live in the terminal state machine; no connections or
locks are held while entering or navigating choices. Previously saved revisions
remain durable even if the next draft is canceled or the session quits.

Synthetic regression coverage includes both short/long Back and Cancel at every
label stage; unknown-domain action Back; changing category after choosing a child;
confirmation Back through all earlier fields; invalid/unconfirmed input; restarting
a discarded draft; quitting at every stage; prior committed revisions; aggregate-only
summaries, escaping and prompts without DB connections or writes before `save`.

Issue #32 validation on Python 3.12.14: **47 new tests**, **1,355 passed on SQLite**
and **1,355 passed on real PostgreSQL 16** (including existing migration and
concurrency regressions). `pip check` and `git diff --check` passed. No real
household databases, provider APIs, OAuth or external models were used.

Reviewer questions: Does each Back route reach the previous logical field? Can any
changed domain reuse a stale child? Does Cancel always return to the same record
without affecting counters or persistence? Does only explicit `save` enter the
unchanged atomic save service?
