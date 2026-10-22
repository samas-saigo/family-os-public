# 单条合成邮件运行诊断 v1 — frozen plan

This is an independent, manual runtime diagnostic, not a semantic evaluation or a
rerun of PR #107. Its original 60-second failure remains an observation; it is not
replaced by this separate 180-second request budget. The existing timeout, HTTP
500, later full-GPU residency and layer-offload observations do not establish a
cause: no VRAM, CPU-fallback, cold-start or model-quality conclusion is justified.

## Configuration frozen before implementation

Base: `d4f9ce8980cab76364766de3ab5378721142f277` (PR #107 merge).
The separately committed `experiments/configs/single-email-runtime-diagnostic-v1.json`
contains the full unchanged prompt/schema, exact tag/digest and generation settings.
Its LF SHA256 is `fced8bb829337db363ba3bb738beac4034df66bb662468f23420817fe2b80544`.
The original config LF SHA is `c4e774ce7a8a81b2bb80f77588126cd515fe3dd0496eecb09836b3330729d17f`.
The frozen wording input LF SHA is
`067b041f142ce9892509f7024ff5d94c6a4a34be2fdd59d4d2e91a408a44b019`.

This plan/config is committed and pushed, and its remote SHA verified before the
new runner is implemented. The subsequent implementation records that freeze SHA.
This is a developer-authored registration of a seen synthetic case, not a blind
study or independent timestamp proof.

## Fixed procedure and limits

- The only possible generation input is the original authorized projection of
  **WC01-1**. Gold, ID, group and variant never enter the request.
- At most one chat, no probes, warmup, retry, smoke/full, arbitrary input, model,
  host, prompt or path option. Serial numeric loopback `127.0.0.1:11434` only;
  exact existing version/tags/show/ps/chat allowlist, no proxy or redirect.
- Initial identity and residency; repeat identity just before chat; check identity
  again at end/abort, within the same total budget. Identity failure is permanent.
- Connect <=5 seconds; each metadata operation <=5 seconds; sole chat <=180
  seconds; whole diagnostic <=240 seconds. All use monotonic absolute deadlines.
- Same think=false, stream=false, temperature=0, seed=0, ctx=4096, predict=512.
  No model/hardware/environment changes. Initial residency may be null; this
  neither guarantees nor measures a cold start. Capability declarations and
  think:false are not proof of internal computation.
- Preserve bounded requests/headers/body, strict exact JSON/schema, no thinking,
  context or tools, and all original structural cross-constraints.

## Outcomes and report contract

One selected case remains in every report, including not-attempted/timeout/failure.
`complete` means a full, structurally valid response was received and end identity
was verified; it does **not** mean correct semantic evidence. Other outcomes are
`partial`. Finite failure codes never imply abstain or successful completion.

Record total monotonic duration, per-request client connect/send/headers/body/parse
phases (elapsed and completion), chat response-received duration, and available
response total/load/prompt-eval/eval durations and counts. Unknown server telemetry
is null, especially on timeout; client wait cannot identify server load/inference
stages. Phase timing excludes neither network nor scheduling delay and is not a
server trace. End verification shares the total budget and may be unavailable.

No scoring, references, correct/incorrect result, model quality ranking or full
comparison. Keep only finite validated evidence/telemetry and configuration/model
identity; no subject, raw response, prompt, input fingerprint, thinking, sender,
body, URL or credentials. If attribution fails, observed identity is null and any
validated prediction is explicitly unattributed. Reports use a new ignored local
directory, unique runs, fsync + atomic rename; failure cleans temporary output and
never reports successful publication. Existing reports are untouched.

## Verification plan

Mock-only HTTP/CLI tests: fixed input and gold isolation, exact unchanged request,
no retry even on timeout/HTTP 500, connect/chat/metadata/total deadlines including
slow trickle, initial/final identity failure and recovery cannot restore attribution,
partial/unattempted reports, valid telemetry, missing telemetry=null, strict output
and thinking boundaries, atomic publish/cleanup/collision isolation, actual CLI
invocation and refused extra options. Linux full SQLite/PostgreSQL and existing
Windows 3.12.0/3.12.10专项 plus these new Mock tests; no inference in implementation
or CI. operator runs only after review/merge. No forbidden dataset/model/product reads
or writes; no Holdout, database, accounts, Task/Pending or permission changes.

## Implementation and evidence

Frozen plan/config commit: `09916e959bda2a719a5ef962017a1f56cb3f7b72`, pushed
and independently read back with `git ls-remote` before runner implementation.
Configuration LF SHA: `fced8bb829337db363ba3bb738beac4034df66bb662468f23420817fe2b80544`.
The PR contains the separate subsequent implementation commit(s); exact final HEAD
and CI evidence are recorded in its description rather than a self-referential hash.

`experiments.single_email_diagnostic` reuses the original strict prediction parser,
model-identity/residency methods, payload constructor and absolute-deadline socket.
It checks the unchanged original runner LF SHA
`b0b1dc39f974af8c6f3c74cefeee4950663e83f8bc7bacff006a9c05aa035fd8`.
A small isolated transport explicitly applies the new, separately frozen budgets;
its allowlist contains only WC01-1 and it consumes its sole chat attempt even on
connect/send failure. No runtime monkeypatching, old config override, scorer or
rule interpreter invocation occurs. The original pinned wording loader validates
its fixed 36-case file; only WC01-1's minimal input is selected, and neither the
reference nor other cases are sent, scored or saved. File pins still validate the
interpreter file; validation is not interpretation or a rerun of the frozen study.

New reports: `.local/single-email-runtime-diagnostic/<random-run-id>/report.json`.
All earlier report directories and experiment identities remain independent.
Completed phases include elapsed time plus `completed=true`; a failed phase records
its elapsed time and `completed=false`, and later phases are absent. These are
client-side intervals, not server phase attribution. `chat_response_seconds` is
null unless a full bounded envelope with verifiable reply identity was received;
the failed request's duration remains in `requests`. No server telemetry is
reconstructed from that duration. A valid inner response can still be semantically
wrong: there is intentionally no reference comparison. Structural failures, timeout
and not-attempted outcomes are never reclassified as abstain. Normal metadata at
end cannot repair a preceding identity failure. Already validated finite evidence
then remains only `unattributed_diagnostic`.

Absolute deadlines cap network operations including slow headers/body reads, not
just individual socket waits. They are not a hard-real-time OS/process kill or a
guarantee against OS scheduling, filesystem stalls or cleanup latency. Publication
happens after network timing and is not part of the measured response latency.
No signal, background worker, model cancellation, server unload or restart is added;
a client timeout cannot prove server-side inference stopped.

## operator: Windows PowerShell, after review and merge only

Do **not** run this while reviewing the PR. CI/development runs Mock tests only.
The block below is an explicit request for **one real local chat**, only after
ChatGPT/Hanabi review and operator's merge. It does **not** execute latest main: it
fetches exactly the runtime/workflow commit below, verifies both commit and tree,
and requires a clean checkout before dot-sourcing the helper or starting any
Python process. The helper repeats that gate before even version probes.

Execution pin (subject to approval of this PR):

- commit: `2ecfcf74e4c632756bc6c72c3c530c4b63978e98`
- tree: `ca346f4eb0b8566b657505270c012889b00bf24f`

This commit contains the complete runtime and workflow helper. The later documentation
commit only records these already-existing identities; it cannot refer to itself.
A future main change does not change what this command runs. Any unavailable pin,
wrong commit/tree or dirty checkout stops before Python/imports/requests, with no
fallback to main. These pins become approved only through the reviews/owner approval
of this PR; a commit hash is not a substitute for that approval. This assumes a
trusted Git/Python installation and fresh checkout, not defense against a malicious
local process changing files after verification.

No Python path or code edits are needed. Discovery first tries the previously verified
`%TEMP%\samas-i9-56051b5dbf8443cfba3b2d55bbee16a9.venv\Scripts\python.exe`,
then the equivalent checkout `.venv` location, the per-user Python312 installation,
and existing `python.exe` entries on PATH. Every candidate is checked through a
stdlib-only stdin probe and must be **exactly 3.12.10**; the execution bootstrap
checks again before importing repository modules. No installation/download occurs.
Python uses `-I -S` to ignore Python environment/site startup configuration, and
all multiline Python is passed on standard input, never PowerShell `-c`.

The helper calls the existing diagnostic exactly once, atomically publishes its
unchanged minimized report, reads back that **same new report**, and compares it
to the validated in-memory result. The printed/copied JSON includes diagnostic and
workflow exit codes, experiment/config identity, report path, run/result status,
identity attribution, initial residency, total time, every request/phase, all available
load/prompt_eval/eval durations/counts, and finite prediction. Success and partial
both include the full report. On missing/unreadable/changed report it retains the
in-memory diagnostic with `report_read_verified=false`, `report_source=retained_in_memory`
and an error code, stops, and never runs again. Clipboard failure retains all printed
information, stops with an error, and never reruns inference to recover output.
There is no arbitrary report path or historical report selection.

Ollama must already run with the fixed candidate installed. This workflow never
warms/unloads/restarts/downloads models or changes drivers/environment settings.
No pip install is needed. The fresh temporary checkout/reports are retained for operator;
working directory, output encodings and error preference are restored on exit.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $diagOldLocation = Get-Location
    $diagOldEncoding = $OutputEncoding
    $diagOldConsole = [Console]::OutputEncoding
    $diagCommit = '2ecfcf74e4c632756bc6c72c3c530c4b63978e98'
    $diagTree = 'ca346f4eb0b8566b657505270c012889b00bf24f'
    $diagRoot = Join-Path $env:TEMP ('samas-single-runtime-' + [guid]::NewGuid().ToString('N'))
    try {
        $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        [Console]::OutputEncoding = $OutputEncoding
        try {
            if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git_missing' }
            if (Test-Path -LiteralPath $diagRoot) { throw 'checkout_exists' }
            $diagIgnored = git init --quiet $diagRoot 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw 'git_init_failed' }
            $diagIgnored = git -C $diagRoot remote add origin https://github.com/samas-saigo/family-os.git 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw 'git_remote_failed' }
            $diagIgnored = git -C $diagRoot fetch --quiet --depth 1 origin $diagCommit 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw 'approved_commit_unavailable' }
            $diagIgnored = git -C $diagRoot -c core.autocrlf=false checkout --quiet --detach FETCH_HEAD 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw 'checkout_failed' }
            $diagHead = git -C $diagRoot rev-parse HEAD
            if ($LASTEXITCODE -ne 0 -or "$diagHead" -cne $diagCommit) { throw 'approved_commit_mismatch' }
            $diagActualTree = git -C $diagRoot rev-parse 'HEAD^{tree}'
            if ($LASTEXITCODE -ne 0 -or "$diagActualTree" -cne $diagTree) { throw 'approved_tree_mismatch' }
            $diagDirty = git -C $diagRoot -c core.fsmonitor=false status --porcelain --untracked-files=all
            if ($LASTEXITCODE -ne 0 -or $diagDirty) { throw 'approved_checkout_dirty' }
            # Only now may approved repository code be loaded. No Python ran yet.
            . (Join-Path $diagRoot 'experiments/single_email_windows.ps1')
        } catch {
            $diagFailure = "启动停止：approved_checkout_preparation_failed；未执行 Python 或推理。`nCheckout: $diagRoot`nCommit: $diagCommit`nTree: $diagTree"
            Write-Output $diagFailure
            try { Set-Clipboard -Value $diagFailure -ErrorAction Stop }
            catch { Write-Output 'clipboard_failed；请复制上方信息。停止，不重跑。' }
            throw 'approved_checkout_preparation_failed_no_retry'
        }
        # This function handles printing/copying success, partial and failure once.
        # Its exceptions propagate; no outer handler overwrites or recopies its report.
        Invoke-DiagnosticWindows -Root $diagRoot -ApprovedCommit $diagCommit -ApprovedTree $diagTree
    } finally {
        try { Set-Location -LiteralPath $diagOldLocation.Path }
        finally {
            $OutputEncoding = $diagOldEncoding
            [Console]::OutputEncoding = $diagOldConsole
        }
    }
}
```

Reports stay in the printed temporary checkout until operator removes it manually.
Do not remove it before review. No cleanup command deletes previous experiment
reports or files. If initial residency is null, report that fact only; do not label
it a guaranteed cold start. If timeout persists, preserve null telemetry and logs
as separate observations. This diagnostic cannot establish GPU load, memory
pressure, server phase durations absent from the response, or real model quality.

## Offline developer verification

```text
python -m pytest -q tests/test_single_email_windows_workflow.py tests/test_single_email_diagnostic.py tests/test_email_model_evidence.py tests/test_email_wording_challenge.py tests/test_synthetic_email_evidence.py
```

All generation and metadata requests in these tests use Mock HTTP/sockets; an
autouse test guard rejects real socket connections. The Windows 3.12.0/3.12.10 job
includes these same tests; its existing deterministic rule-only CLI checks remain
unchanged. Full SQLite/PostgreSQL CI retains all prior tests. No real diagnostic
command, Ollama startup or model inference is run by CI or during implementation.

Model identity checks are observations of the local API, not cryptographic proof
of which weights performed computation. Existing host-local/Ollama trust limits
remain; this diagnostic does not expand them or infer a timeout cause.

## Windows review corrections

The original latest-main command was removed: printing HEAD/module existence was
not an execution approval gate. Current instructions fetch the fixed commit/tree
before any Python, and never run changed main. The workflow files use UTF-8 BOM
where needed for Windows PowerShell 5.1. Both PowerShell 5.1 and 7 execute native
Mock behavioral tests; the existing syntax check remains an additional check.
Tests cover zero generation on wrong version/approval, preferred Python discovery,
success/partial full report transfer, report readback and clipboard failure without
retry, and restored working directory/encodings/preferences. Linux Mock tests also
exercise the real one-shot helper/diagnostic/HTTP/readback chain. Real model inference
remains strictly manual after review/merge. PR107, the diagnostic core/config, budgets,
prompt/schema, fixture, reference, scorer and interpreter remain unchanged.
