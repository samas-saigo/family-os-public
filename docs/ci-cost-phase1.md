# CI cost routing, phase 1

Base: `ec2016876a6d734cd8d3b46de92f2f241db65cd2` (latest main, PR110 merged).
Scope is CI only. No product, frozen configuration/prompt/sample/scorer/result
changes; no inference, Ollama startup, real accounts, or new runner/service types.

## Selection contract

Every PR runs the **entire SQLite suite** and the original Windows 3.12.10 suite.
Pushes to main and workflow_dispatch run both full database suites and both Windows
versions. Manual Actions **Run workflow** can select a branch and is the explicit
full-validation entry once this workflow_dispatch definition exists on main. Before
merge, this PR changes the workflow/router and therefore selects full automatically.
Ordinary label changes do not trigger or cancel CI.

Only an all-A/M change list contained in the exact EMAIL/OFFLINE sets in
[ci_route.py](../.github/scripts/ci_route.py) can omit PostgreSQL on a PR. Mixed
changes force full checks. No directory globs are exempt. All other paths,
including src, migrations/db, conftest, dependency/packaging files, CI/router,
configs, fixtures, unreviewed experiments and docs force full checks.

Full-history checkout + immutable PR event base/head SHAs + a checked NUL-delimited
`git diff base...head` avoids API pagination limits. Missing history/merge-base,
invalid SHA/UTF-8/records, errors/timeouts, empty list, renames/copies/deletions or
unknown status all choose full. Renames with edits that Git reports as deletion +
addition also choose full. Only a successful selection job can authorize omission
with an explicit `false` output. If selection fails, both optional jobs run while
the workflow is not cancelled, even if `false` outputs were already published
before the failure (for example, a subsequent summary write fails). Missing outputs
also select full checks. CI result ignores omission flags from unsuccessful selection
and still fails for that selection failure, even when the full checks pass.

Windows 3.12.0 is omitted only for changes to the pure report-analysis module
`experiments/rule_ai_complementarity.py` alone. Its test file contains mocked
Win32 handle checks, so changes to that test retain 3.12.0. Any email entry,
including its three executable Markdown instructions, keeps **both** Windows versions.
All unreviewed Python/platform/compatibility paths conservatively keep both too.
Native PowerShell 5.1/7 Restricted, clipboard/restoration/recovery, fixed-file metadata,
old experiment regressions, and twice-run CLI/report-isolation assertions are unchanged.
YAML anchors share identical Windows steps; no assertion or test was weakened.

## Dependency audit at base

The EMAIL set names exactly six standalone runner modules, seven corresponding
test modules and three instructions. `synthetic_email_evidence` and
`email_wording_challenge` depend on the pure `family_os._synthetic_email_evidence`;
`email_model_evidence` uses wording + that same interpreter;
`single_email_diagnostic` uses email_model_evidence;
`single_email_compat` uses the diagnostic; `email_model_compat` uses the compatibility
validator/transport. They read pinned synthetic fixtures/configs and write their
own report namespaces, with HTTP mocked by tests. No SQLAlchemy/database/migration
use or `engine` database fixture is present in these tests (`engine` in runner code
is the pure email interpreter alias). Product src has no reverse imports of these
experiment modules. Existing collectors/helpers/configs/fixtures stay outside the
allowlist. Execution docs are tested as source, including native mocked behavior,
not assumed inert Markdown.

The OFFLINE set contains only `experiments/rule_ai_complementarity.py` and its test.
It validates an existing fixed synthetic report using local_thinking_benchmark
(pure projection/rule/scoring helpers) and _fixed_report_io (bounded file access).
Its tests use mocks/tmp_path, no database fixture. No product reverse import exists.
Neither dependency is itself exempt: local_thinking_benchmark, _fixed_report_io,
development_rule_diagnostics and rule_evidence_gap remain full-check paths.

This is an audited dependency boundary, not a sandbox against malicious PR code.
Future imports/product consumers/platform coupling require re-auditing the allowlist;
reviewers must move such paths back to full selection when their role changes.

## Check results and controls

No workflow-level paths filters: existing sqlite, postgres and both named Windows
check contexts are retained. Optional jobs produce an explicit **skipped** result,
not a missing/pending check; summaries say **NOT RUN by audited rule (not a test pass)**.
`CI result` runs after success/failure (unless the workflow is cancelled) and verifies
all selected jobs succeeded and only intentional
omissions from successful selection were skipped. It rejects failures/cancellation/unexpected skips, including
selection failure. No continue-on-error. Repository protection is not changed;
branch-protection read was unavailable to the connected GitHub integration (403).
`CI result` is the stable aggregate context available for required-check policy.

PR concurrency cancellation is preserved verbatim. Dependent jobs use
`!cancelled()` rather than `always()` so a superseding PR run can stop them,
while selection failure still triggers full fallback. Pip cache uses setup-python's
OS/architecture/Python identity plus requirements-dev.lock hash, without changing
installation commands. Timeouts: routing/result 5m, SQLite 30m, PostgreSQL 35m,
Windows 15m. No cache or timeouts are claimed as measured savings.

Local fault regressions invoke `ci_route.main()` with a directory as the summary
destination: the two `false` outputs are written first, then summary publication
raises. Tests evaluate the actual optional-job conditions and result gate for this
partial publication, successful omission, missing outputs and workflow cancellation.
Cancellation blocks both optional jobs and the aggregate; it never starts full
fallback work for a superseded workflow. No cloud fault-demonstration run is needed.

## Existing cost baseline (no new baseline run)

[PR110 final successful run 39648326502](https://github.com/samas-saigo/family-os/actions/runs/39648326502),
head `666e6225470eddcdb8e5f445a377fc5644b4cbd3`, attempt 1:

| Job | Runner elapsed | Rounded job minutes |
| --- | ---: | ---: |
| sqlite | 695s / 11m35s | 12 Linux |
| postgres | 699s / 11m39s | 12 Linux |
| windows-wording (3.12.10) | 109s / 1m49s | 2 Windows |
| windows-wording (3.12.0) | 144s / 2m24s | 3 Windows |

Elapsed uses existing jobs' started_at/completed_at; queue time excluded. Baseline
runner total is 1,647s (27m27s), rounded usage 24 Linux + 5 Windows minutes. Logs
remain the evidence for actual tests, not a fresh benchmark run.

For comparable estimates let L/W be account-effective Linux/Windows per-minute
prices: baseline = **24L + 5W**. A qualifying EMAIL run at unchanged suite durations,
plus routing/aggregate jobs each fitting 1 minute, would be **14L + 5W**; OFFLINE
with only that pure module changed would be **14L + 2W**. These are scenarios, not measured savings. At illustrative
assumed L=$0.006 and W=$0.010, these are $0.194 / $0.134 / $0.104 respectively,
before included quota, tax, discounts or account-specific billing. GitHub billing
is authoritative; the assumed prices are not an account invoice or verified tariff.
First full validation also adds routing/aggregate overhead. Report its actual job
durations in the PR after completion; do not extrapolate a measured saving percentage
from a full run or promise future suite duration/cache behavior.

Review order: ChatGPT first review, then Hanabi independent review, operator manual merge.
Keep this PR open, with auto-merge disabled.

The additive [review evidence helper](ci-review-evidence-phase1.md) reuses these
checks and preserves this routing/result/cancellation contract; it adds bounded
checkout/commit metadata and single-invocation pytest statistics, with no artifact.
