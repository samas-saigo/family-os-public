# Offline rules + AI complementarity — original synthetic 37

This independent tool reads **one existing local synthetic report**, performs no
inference, and changes no Family OS rules, prompts, fixtures, models, tasks, grants,
databases or providers. Base main `ff12b6b` contains merged PR #100. Codex cannot
read the owner's Windows report; all implementation tests use invented mock reports.
The supplied aggregate 12/14 versus 8/14, misses 2/6 versus 5/6, does **not** establish
which cases overlap. No actual overlap result is asserted in this PR.

## Exact artifact and trust boundary

Run `python -m experiments.rule_ai_complementarity --synthetic-only` from the repo.
There is no path, model, URL, dataset, report ID or clipboard-content argument.
The only accepted input is:

```text
.local/local-ai-benchmark/9d6d0ddd425541ff8bb029d246dbf5a8/report.json
```

Only a completed, identity-verified full 37-case PR #100 v1 report from
`qwen3:8b-q4_K_M`, explicit Thinking OFF, digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
is supported. Other artifacts need a separately reviewed allowlist/version change;
do not rename unrelated reports to bypass this boundary.

Validation includes exact model/digest/quantization/family/size, bounded runtime
metadata, requested thinking capability, original 256-token options, prompt/schema,
corpus/config/rules/taxonomy/threshold/projection/scoring fingerprints, complete IDs,
repeat coverage, and strict versioned fields. Duplicate JSON keys, nonfinite numbers,
excessive depth/size, extra fields, missing/duplicate/unknown IDs, smoke/partial/
aborted/identity-unverified reports and cached inconsistencies are rejected.
Raw responses are reparsed using the original validators. Each stored request must
exactly match the corresponding synthetic projection, with `think:false` and no
chat history. Cached predicted/correct/uncertainty fields and old score aggregates
must agree with independently recomputed values; they are not scoring authorities.
The three fixed safety-rejected records must have no request or response.

All report text, including apparent instructions in responses, is untrusted JSON
data. Nothing is evaluated as code, passed to a shell, rendered as HTML, fetched,
or sent to any model/API. The original report is never modified. A local report
hash identifies the exact bytes inspected. **Consistency checks and a self-hash
are not a digital signature**: this cannot prove that inference really occurred,
that the named weights were used, that internal Thinking OFF was honored, or that
a malicious local editor did not forge a mutually consistent report. The owner
must trust the original local artifact/OS. Historical weight equality is not claimed.

## File safety and output

The trusted root is the checked-out repository resolved by the existing runner;
every descendant component is fixed. POSIX opens directories relative to held
descriptors with `O_NOFOLLOW`, then rejects symlinks, nonregular files, hard links,
oversize reports and detected changes during the bounded read. No glob/discovery
or arbitrary path is used. A FIFO cannot block the read. The maximum report is 16MiB.

Windows uses stdlib ctypes/Win32: `CreateFileW` with `OPEN_REPARSE_POINT`, rejects
reparse points/junctions, locks every directory with share-read only to prevent
rename/delete replacement while in use, and rejects non-disk/nonregular or linked
files. The file is also read under a no-writer sharing contract. Existing writers
can cause safe refusal; close editors/writers first. UNC paths are unsupported.
Native Windows/NTFS behavior still requires owner acceptance; Linux CI verifies
POSIX behavior and mocked Win32 flags, rejection and handle cleanup, **not native
Windows ABI correctness**. This does not sandbox a hostile administrator or an
untrusted repository installation/filesystem.

Fresh detailed results use exclusive creation as
`complementarity-<random-id>.json` inside the **same fixed run directory**, already
ignored by Git. They contain fixed IDs, enum predictions, error flags and metrics,
not copied prompts, model prose or reasoning. Output names cannot traverse or
overwrite the input or earlier diagnostics. Failed validation creates no diagnostic.
A disk/write failure may leave an incomplete new diagnostic; no success summary
is printed. Protect local storage/backups/ACLs; no encryption is added.

Stdout is a short Chinese aggregate suitable for explicit PowerShell clipboard
copy. It includes four overlap counts, six-positive misses/recovery, false-irrelevant
counts, distinct error buckets, Oracle and conservative policy comparison, and the
relative diagnostic path. No case text or case IDs are printed.

## Scoring and policy specification (fixed before seeing the report)

The original corpus, labels and historical metrics are unchanged. The rule engine
is rerun independently for **every case**; AI outputs are aligned by fixed ID, not
list position. Valid bounded JSON taxonomy errors and invalid final JSON remain
invalid, not a model uncertain prediction. Truncation is its own failure state.
API/protocol/incomplete runs cannot support full-cohort comparison and are rejected.
Projection failures are separately counted and never become AI calls/predictions.

The primary four-way action table is on **14 decisive truth labels**, not all 37:

| Bucket | Rule action equals truth | Valid AI action equals truth |
| --- | --- | --- |
| Both correct | yes | yes |
| Rules only | yes | no |
| AI only | no | yes |
| Both wrong | no | no |

The six `required` cases have their own four-way table and explicit rule-missed /
AI-required recovery count, including a separate relevance-qualified recovery count.
Action correctness alone does not establish correct relevance, safety or authority.
The 23 uncertain truth labels do not enter the old 14-case decisive accuracy; they
remain inspectable, including uncertain-to-concrete claims in preserved diagnostics.
Required→not_required, required→uncertain, invalid, truncated and projection-rejected
states are distinct. Wrong irrelevant is counted only against known relevant truth,
matching the original metric; it is never assumed wrong/correct on unknown relevance.
Old metrics retain their zero-confidence uncertain fallback for invalid cases only
inside the legacy computation. Detailed AI predictions for invalid/gated cases are null.

**Oracle is retrospective, not executable**: action-correct upper bound is
`both_correct + rules_only + ai_only` out of 14. Required-recognition upper bound
uses the same union out of 6. Oracle selects winners using answers and must not be
presented as a routing policy or deployed result.

The executable offline conservative proposal is deliberately less ambitious:

1. Rule `required` stays required regardless of AI dismissal, irrelevance or failure.
2. Rule `not_required` plus a valid AI `not_required` produces an informational
   proposal, **never authority to discard data or close an obligation**.
3. Every other combination stays uncertain and review-only. AI required can add a
   possible-action review signal, but cannot turn rule uncertainty into confirmed
   required or bypass independent security evidence.
4. Gated cases receive no combined proposal. No result creates a Task or Pending,
   grants access, clears risk, performs an action or auto-dismisses anything.

The strategy sees no expected label. Its accuracy and required-recognition count
are reported separately from Oracle, along with manual-review proposal volume.
It may reduce decisive accuracy in exchange for conservative uncertainty; that is
reported honestly. A proposal is not a wired production policy. Report repeats
are analyzed separately with denominator **6/14 each**, never pooled into larger
independent samples. This small, already-known corpus supports no real-world claim.

## Windows PowerShell (owner-run after independent reviews)

No Ollama service or GPU is needed. Do not regenerate the report or copy private
records into it. From the existing repository root:

```powershell
git fetch origin
git switch feat/offline-rule-ai-complementarity
git pull --ff-only
$py = ".\.venv\Scripts\python.exe"
# Reuse the PR #100 environment; if absent, first follow its documented venv setup.
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONIOENCODING = "utf-8"
$summary = & $py -m experiments.rule_ai_complementarity --synthetic-only
if ($LASTEXITCODE -ne 0) { $summary | Out-Host; throw "Report rejected; no clipboard update. Check fixed local artifact." }
$summary | Out-Host
($summary -join [Environment]::NewLine) | Set-Clipboard
Write-Host "简短汇总已复制；逐案例诊断只保存在本地。"
```

Owner acceptance: keep the original file unchanged; verify 37 IDs, 34 requests,
three safety rejections and 6/14 denominators; inspect six positives and actual
overlaps; confirm clipboard contains only the aggregate; try a copied/incompatible
or linked test artifact only in a disposable clone and verify refusal. Do not
publish raw model reports. No overlap is inferred here from the supplied aggregates.

## Development evaluation preparation — design only

The existing approved Development split has 60 synthetic cases (20 per action
label), including 16 counterfactual triads. It is separately authored from the
old 37, but already used for historical prompt experiments, English-only and
templated: it is **not a new blinded holdout**. This PR neither reads its cases nor
dispatches inference. Rubric/source and split-manifest metadata were inspected;
no Holdout contents or labels are accessed by the analyzer or Development design
inspection. Existing repository CI keeps its previously approved offline dataset
integrity tests; those are not Holdout model evaluation, tuning or new analysis.

Important blocker: existing `action_evaluation.load_dataset()` reads **both**
splits before `action_model_benchmark.select_development()` filters them. The new
offline analyzer never calls either. Future work needs a reviewed Development-only
loader: open only development/rubric/manifest, verify the pinned manifest and
Development annotated/input hashes and 60-case/20-each distribution, validate
Development projections and 16 triads, and test that opening Holdout is impossible.
It cannot claim to recheck cross-split content without reading it; rely on the
previously reviewed freeze identity, without weakening the old full-dataset validator.

The PR #100 transport also deliberately allows only the original 34 projections;
its generation allowlist must **not** be loosened to sneak in Development. A future
separately versioned, dev-only model adapter must be reviewed for exact model/digest,
explicit thinking, same frozen prompt/schema/options, no answer/rationale leakage,
budgets and localhost-only transport. Existing Phase 2R transport has its own old
4B/3.5 model allowlist; do not silently change global production/model selection.

Before any new owner run, freeze the truth-free policy, scoring and model settings.
Use 20-positive recall, 40-decisive action accuracy, full uncertainty confusion,
false-irrelevant, invalidity and review-volume diagnostics, paired by case and by
counterfactual family; keep oracle separate, repeat denominators independent and
negative tradeoffs visible. Do not revise labels/prompts/answers based on this
37-case analysis and claim independent improvement. No execution route or model
experiment is implemented here. Holdout requires later owner approval after the
entire scheme is frozen; no default command or implicit loader access is permitted.

## Validation and review gates

Tests use invented scripted reports and no network/GPU: manifest/config changes,
row/summary mismatches, reordered/duplicate/missing IDs, all overlap groups,
required recovery, irrelevant vs uncertain errors, invalid/truncated outputs,
repetition independence, conservative policy, JSON/resource/path/link attacks,
POSIX mutation detection, mocked Win32 handles, CLI redaction/clipboard-safe output,
and no split/inference access. Exact focused/full SQLite/PostgreSQL CI results are
recorded in the PR. Existing inference runner, tests and fixtures stay unchanged.

Keep the PR open for ChatGPT review, Muse security review and owner's AMD Windows
artifact/clipboard acceptance. Codex has not analyzed the unavailable owner report.
