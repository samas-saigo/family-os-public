# CI review evidence, phase 1

This adds bounded mechanical evidence to the existing Tests workflow. No AI,
model execution, new job/runner, API permission, artifact, routing exemption,
automatic fix or merge. Matrix, concurrency, optional-job conditions, router and
`ci_result.py` are unchanged. The stable CI result remains the execution authority.

## Sources and attribution

Selection's existing full-history checkout supplies immutable event base/head,
NUL-delimited Git changes and base..head new commits. PR file comparison uses
base...head; push uses before..after. Renames are displayed as delete/add without
changing the router's rename/full-fallback behavior. Dispatch/initial push has no
reliable new-commit range: explicitly NOT CHECKED, not a privacy pass.

Every test job records its own actual `git rev-parse HEAD` and `HEAD^{tree}`, event
PR head/base, job, run ID/attempt and attempt-log link. Checkout must equal the
workflow's GITHUB_SHA. For PRs this is normally the synthetic merge commit, **not**
the source branch head. Reports never substitute PR head for tested checkout.
The aggregate job records its own checkout too; it is not evidence that every
other job checked out the same tree. Inspect those jobs' individual summaries.

CI result's existing `needs` outcomes distinguish successful execution, failure,
cancellation and intentional omission from successful selection. No API/log download
is needed; link to the exact run attempt, then select the named job/step. A cancelled
workflow may have no final summary; cancellation never starts fallback work.

## Test evidence without repeated tests

The original pytest invocation runs **once** with its original arguments and two
report-only options: xunit1 and JUnit XML. Output still goes to the original detailed
job log. The helper reads the fresh XML from an exclusive runner-temp directory,
checks suite/testcase counts and exit-code consistency, then removes it. No log,
XML, workspace or model report is uploaded. Existing Windows native/Restricted,
clipboard/recovery and twice-run offline CLI assertions remain in the shared steps.

A short job-log line also records validated identities and finite test counts/status
(≤2KiB, no file list or raw metadata). Summary contains observed pass/fail/error/skip counts and unique failure file:line
locations, without failure messages, parameter values, stdout/stderr or XML bodies.
Missing locations are UNKNOWN. Absent/oversized/truncated/invalid XML, DTD/entity
content, count inconsistency, interrupted/collection-error/no-tests exits or
incomplete report publication are UNKNOWN, never success. Pytest nonzero always
stays nonzero; a successful pytest with unusable evidence also fails the job.
Skipping tests within pytest is a reported count, not a job omission.

Two exact existing JUnit testcase observations are labeled as existing regressions:
PR107 frozen configuration/input checks and PR114 pin/namespace checks. If not
observed they say NOT CHECKED; failed/skipped tests retain those outcomes. This
reuses their assertions, adds no model/fixture loading and asserts no per-file
semantic contract beyond the named regression. No regex scans pretend to validate
prompts, scores, privacy meaning or frozen experimental results.

## New commit metadata policy

After routing, selection inspects at most100 new commits from event base..head,
not the Actions-generated test merge. Both raw author and committer must be the
approved exact name/email pair: `Samas Maintainer` or `samas-saigo`, with
`337128921+samas-saigo@users.noreply.github.com`. Additionally, committer-only
`GitHub <noreply@github.com>` permits GitHub web merges. A familiar name with another
mailbox, arbitrary noreply address, bot or new maintainer is not silently approved.
Policy extension needs review; existing published snapshot policy is unchanged.

Git's `interpret-trailers --parse` supplies actual footer trailers. Supported identity
keys are Co-authored-by, Signed-off-by, Reviewed-by, Acked-by and Tested-by, requiring
the same maintainer/account pair. Unknown keys, malformed or unapproved values fail.
Violations print only commit SHA, author/committer/trailer category and finite code;
no name, email, raw key/value, message or Git stderr is emitted. Prose outside parsed
trailers is NOT CHECKED for personal information. This is metadata policy checking,
not authenticated identity or signature attestation, nor a whole-history privacy audit.

Identity/evidence failure fails selection. Existing `selection.result` fallback
still runs both optional jobs unless cancelled; CI result still fails selection even
if full tests subsequently pass. The existing result step also runs after aggregate
checkout-evidence failure, while the job remains failed. No continue-on-error.

## Limits and remaining human review

Each evidence summary ≤32KiB; no silent truncation. Changes ≤50 records, path ≤512
UTF-8 bytes; commits ≤100, each raw commit object ≤64KiB; Git output ≤1MiB, timeout30s.
JUnit ≤32MiB/20000 testcases; at most20 unique failure locations. Exceeding a limit
reports UNKNOWN and fails evidence rather than claiming a complete check. Paths are
escaped; no arbitrary names, emails, model prose or exception details are published.
Only strictly decoded UTF-8 XML (with an optional UTF-8 BOM) is accepted. Other
declared encodings, invalid UTF-8, NUL bytes and DTD/entity declarations are rejected
before parsing; ElementTree receives validated text, never raw bytes to autodetect.
Temporary XML may remain until runner disposal on hard cancellation; it is never an
artifact. Original pytest logs are unchanged and remain subject to normal log policy.

Replaces manual copying of head/merge/tree/run identities, changed-file/commit metadata
checks, pytest totals/failure navigation, and locating existing contract regressions.
Still requires human review of requirements, semantic correctness, test strength,
new dependencies, full diff/privacy (including filenames and commit prose), allowed
identity policy changes, model reports and all execution/merge authorization. PR code
can modify tests/helper or forge output: this is review assistance, not a sandbox or
independent attestation against malicious source changes.

Maintenance: one stdlib helper and its small unittest suite run in the existing
selection job; keep two named regression mappings current, schema/count compatibility
with pytest upgrades, and the explicit identity/trailer policy reviewed. JUnit writing
adds bounded I/O to the existing run; Git checks reuse existing history. No claimed
savings percentage or repeated cloud baseline. Validate fault cases locally and use
one normal final-HEAD CI run. ChatGPT → Hanabi → user manual merge; keep PR open.

The temporary XML bound is32MiB: offline collection of the existing8328 testcases
produced18,781,328 bytes of testcase metadata alone, mostly parameter IDs. An
initial8MiB bound correctly reported UNKNOWN despite passing tests; it was not
compatible with this existing matrix. The bounded input allowance now fits that
measured source; count/exit validation,32KiB summary and2KiB short-log limits remain
unchanged. No parameter IDs are copied into evidence, no test IDs/selection are
rewritten, and no full tests were rerun locally to obtain this measurement.
