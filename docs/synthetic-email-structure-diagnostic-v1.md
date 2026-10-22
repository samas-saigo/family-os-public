# Synthetic email structure diagnostic v1 — frozen plan

Base latest main: `eb0e76b874b83b1557e8810616d46d7e4914d702` (PR111 merged).
New identity: `synthetic-email-structure-diagnostic-v1`; own config at
`experiments/configs/synthetic-email-structure-diagnostic-v1.json` and own report
namespace `.local/email-structure-diagnostic-v1`. Commit and push this plan/config
before implementation. Do not open a PR until local implementation/testing converges.
Record the remotely verified freeze commit and config hash below after publication.

## Frozen contract

- Exactly WC01-1, WC01-3, WC05-1, WC10-1, WC11-1, WC12-1, in that order.
  Each selected case gets at most one chat, no retries, warmup, inventory, smoke/full
  switching or automatic full. Only diagnose and read-only recover are exposed.
- Same installed qwen3.5:4b-q4_K_M, digest
  d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04,
  runtime0.40.6. Prompt/schema/model/generation equal PR110 config exactly.
  connect5s, metadata5s, chat60s, whole run600s; unchanged resource bounds.
- Pinned original strict prediction parser through the unchanged compatibility
  envelope validator is the only authority. Annotation runs only after structural
  rejection. It cannot change acceptance, status, protocol stop, or valid prediction.
- Fixed finite diagnostic codes in config: field set/type, enum, cardinality,
  duplicate action, state/steps, date value/action binding/state relation,
  notice-kind relation, encoding; unknown when unrecognized. Report one first
  recognized violated constraint in frozen parser order, not every possible issue
  and not a claim about the model's internal cause. Valid = none; nonstructure
  failure = not_applicable; not attempted = not_obtained. Classifier failure = unknown.
- No arbitrary invalid strings, field names or original values. No prompt, subject,
  raw response, thinking, predictions, gold/reference, or input fingerprint in report.
  Finite statuses/subreasons/categories, fixed six IDs, independently validated
  telemetry, times and software/candidate identities only. No scoring or accuracy.
- Permanent identity taint on any failed/interrupted identity observation or reply
  identity mismatch. A normal final observation never restores attribution.
  Attributed reason counts become null; bounded rows remain unattributed diagnostics.
  Timeouts/fatal protocol failures stop subsequent chats; ordinary output failures
  remain failures and can continue to the next fixed case. Failure never becomes abstain.
- Fresh UUID report directories, atomic complete publication/readback; preserve old
  files and in-memory report on publication failure. Read-only recovery requires
  original printed report SHA and exact UUID in the new namespace, zero network.
- Preserve PR107–110 source/config/parser/scorer/fixtures/reports. New code uses
  pinned dependencies; it does not modify or monkeypatch production validators.
- Windows: reuse verified interactive stdin PowerShell5.1/7 Restricted flow, exact
  approved commit/tree/clean-checkout gate before Python3.12.10, full result print
  and automatic clipboard copy, restore location/encodings/preferences, recovery
  never generates. No saved-script loading or execution-policy changes.

## Meaning and evidence limits

This is a new run's structure diagnostic. PR110's full36 took about44 seconds,
clear matches7/24, and20/36 were invalid_structure/prediction_structure according
to the supplied historical summary. Raw replies were not retained. Those aggregate
facts do not identify any individual violated constraint. Do not reconstruct, guess,
relabel, combine with, or modify those historical20 rows/results. This small selected
run is neither an accuracy evaluation nor an independent sample from unseen data.
No model tuning, real account, Holdout, Task/Pending or action authority is enabled.

## Validation and release

Mock HTTP only in development/CI; block real sockets. Differentially compare original
and annotated accept/reject/status/signature across valid and invalid JSON/structural
branches, cardinalities, enums, duplicates, dates, state/notice relations and adversarial
strings; inject classifier failure to verify unknown and unchanged rejection. Test
privacy, exact six wire requests, pinned payload/budgets, permanent identity loss,
timeouts/interruptions, report isolation/atomic failure/recovery and native Restricted
clipboard/restoration/commit/tree gates. Keep all old regressions. New native tests
must execute alongside the existing Windows suite without changing the CI allowlist.
CI routing belongs to PR111's conservative rules; unknown paths select full checks.
Freeze push occurs with no PR, then implement and converge locally, push in a batch,
then open one PR and retain it. No historical cloud baseline rerun or real inference.
ChatGPT first review → Hanabi independent review → operator manual merge and later
explicit manual six-case run. Runtime commit/tree instructions are registered only
once an implementation commit exists; that is not permission to run before merge.

## Freeze registration

Freeze commit `0d1a2c80c1c4e1feababca56e2697b4bfe1124a2` was pushed and verified
with git ls-remote before implementation. Config LF SHA256:
`3d28de6beff0f193bb3dbbb4f7ccf3de5727f2c5faa47f5f348109d5e29f3bb8`.

## operator: approved six-case workflow (only after review and merge)

Use the final reviewed block pasted into interactive PowerShell5.1 or7, including
Restricted. Never save/load a script or alter ExecutionPolicy. Choose diagnose
explicitly once, or recover with the original checkout suffix/run UUID/report SHA.
Recovery verifies the original checkout without fetching or changing it and performs
no generation. Preserve the full console output; clipboard failure prints it and
stops. An expected local SHA detects corruption relative to that original console,
not a hostile user able to edit both. If it is lost, do not regenerate to recover it.
The registered execution candidate below must pass review and merge before operator
runs. Config and old experiments remain frozen.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $diagOldLocation = Get-Location
    $diagOldEncoding = $OutputEncoding
    $diagOldConsole = [Console]::OutputEncoding
    $diagCommit = '1b99466b802bc32feecb2d2d4efcde35641ea412'
    $diagTree = '994e2f7fee8a51f8ffd34b4bebbb3fd18951a937'
    $diagRoot = Join-Path $env:TEMP ('samas-email-structure-v1-' + [guid]::NewGuid().ToString('N'))
    $diagSummary = "Checkout: $diagRoot`nCommit: $diagCommit`nTree: $diagTree`n"
    $diagFailed = $false
    $diagMode = $null
    $diagRunId = $null
    $diagExpectedSha = $null
    function Get-ExistingPython {
        $paths = @(
            (Join-Path $env:TEMP 'samas-i9-56051b5dbf8443cfba3b2d55bbee16a9.venv\Scripts\python.exe'),
            (Join-Path $env:TEMP 'samas-i9-56051b5dbf8443cfba3b2d55bbee16a9\.venv\Scripts\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
        )
        $paths += @(Get-Command python.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
        $paths | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
    }
    function Invoke-ApprovedPython {
        param([string]$Python, [string]$Purpose)
        if ($Purpose -eq 'version') {
            $code = @'
import json, sys
print(json.dumps(list(sys.version_info[:3])))
'@
        } elseif ($Purpose -eq 'diagnostic') {
            $code = @'
import pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
if sys.version_info[:3] != (3, 12, 10):
    print('{"error_code":"python_version_mismatch","workflow_exit_code":1}')
    raise SystemExit(1)
root = pathlib.Path.cwd()
sys.path[:0] = [str(root), str(root / "src")]
try:
    from experiments.email_structure_diagnostic import main
    raise SystemExit(main(sys.argv[1:]))
except SystemExit:
    raise
except (Exception, KeyboardInterrupt):
    print('{"error_code":"workflow_start_failed","workflow_exit_code":1}')
    raise SystemExit(1)
'@
        } else { throw 'invalid_purpose' }
        $cliArgs = @()
        if ($Purpose -eq 'diagnostic') {
            $cliArgs = @('--synthetic-only', $diagMode)
            if ($diagMode -eq 'recover') { $cliArgs += @($diagRunId, $diagExpectedSha) }
        }
        $reply = $code | & $Python -I -S -u - @cliArgs 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
        [pscustomobject]@{ Output=$reply; Code=$exitCode }
    }
    # MOCK_BOUNDARY: native CI substitutes only process/Git/clipboard boundaries here.
    try {
        $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        [Console]::OutputEncoding = $OutputEncoding
        if ($diagCommit -cnotmatch '^[0-9a-f]{40}$' -or $diagTree -cnotmatch '^[0-9a-f]{40}$') { throw 'approval_pin_missing' }
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git_missing' }
        $diagMode = Read-Host '选择 diagnose 或 recover（只读恢复）'
        if ($diagMode -cnotin @('diagnose','recover')) { throw 'invalid_mode' }
        if ($diagMode -eq 'recover') {
            $checkoutId = Read-Host '原 Checkout 文件夹末尾32位字符'
            $diagRunId = Read-Host '原 report_path 中的32位运行 ID'
            $diagExpectedSha = Read-Host '原 report_sha256（64位）'
            if ($checkoutId -cnotmatch '^[0-9a-f]{32}$' -or $diagRunId -cnotmatch '^[0-9a-f]{32}$' -or $diagExpectedSha -cnotmatch '^[0-9a-f]{64}$') { throw 'invalid_recovery_identity' }
            $diagRoot = Join-Path $env:TEMP ('samas-email-structure-v1-' + $checkoutId)
            $diagSummary = "Checkout: $diagRoot`nCommit: $diagCommit`nTree: $diagTree`nMode: recover (no inference)`n"
            if (-not (Test-Path -LiteralPath $diagRoot -PathType Container)) { throw 'recovery_checkout_missing' }
        } else {
            $diagSummary += "Mode: $diagMode`n"
            if (Test-Path -LiteralPath $diagRoot) { throw 'checkout_exists' }
            $ignored = git init --quiet $diagRoot 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw 'git_init_failed' }
            $ignored = git -C $diagRoot remote add origin https://github.com/samas-saigo/family-os.git 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw 'git_remote_failed' }
            $ignored = git -C $diagRoot fetch --quiet --depth 1 origin $diagCommit 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw 'approved_commit_unavailable' }
            $ignored = git -C $diagRoot -c core.autocrlf=false checkout --quiet --detach FETCH_HEAD 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) { throw 'checkout_failed' }
        }
        $head = git -C $diagRoot rev-parse HEAD
        if ($LASTEXITCODE -ne 0 -or "$head" -cne $diagCommit) { throw 'approved_commit_mismatch' }
        $tree = git -C $diagRoot rev-parse 'HEAD^{tree}'
        if ($LASTEXITCODE -ne 0 -or "$tree" -cne $diagTree) { throw 'approved_tree_mismatch' }
        $dirty = git -C $diagRoot -c core.fsmonitor=false status --porcelain --untracked-files=all
        if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'approved_checkout_dirty' }
        Set-Location -LiteralPath $diagRoot
        $python = $null
        foreach ($candidate in @(Get-ExistingPython)) {
            try {
                $probe = Invoke-ApprovedPython -Python $candidate -Purpose version
                $v = ConvertFrom-Json -InputObject $probe.Output -ErrorAction Stop
                if ($probe.Code -eq 0 -and $v -is [array] -and $v.Count -eq 3 -and $v[0] -eq 3 -and $v[1] -eq 12 -and $v[2] -eq 10) { $python=$candidate; break }
            } catch { $probe=$null }
        }
        if (-not $python) { throw 'python_3_12_10_not_found' }
        $diagSummary += "Python: $python`nVerified version: 3.12.10`n"
        Write-Host '新结构诊断：固定六例、每例最多一次；无准确率评估或旧结果反推；recover 不推理；不重试。'
        $execution = Invoke-ApprovedPython -Python $python -Purpose diagnostic
        $diagSummary += $execution.Output + "`nProcess exit code: $($execution.Code)`n"
        if ([string]::IsNullOrWhiteSpace($execution.Output)) { throw 'workflow_output_missing' }
        if ($execution.Code -ne 0) { throw 'experiment_partial_or_failed_no_retry' }
    } catch {
        $diagFailed=$true
        $allowed=@('invalid_mode','invalid_recovery_identity','recovery_checkout_missing','approval_pin_missing','git_missing','checkout_exists','git_init_failed','git_remote_failed','approved_commit_unavailable','checkout_failed','approved_commit_mismatch','approved_tree_mismatch','approved_checkout_dirty','python_3_12_10_not_found','workflow_output_missing','experiment_partial_or_failed_no_retry')
        $code=if ($allowed -contains $_.Exception.Message) { $_.Exception.Message } else { 'windows_workflow_failed' }
        $diagSummary += "`n操作停止：$code；不得为补取数据重跑推理。`n"
    } finally {
        Write-Output $diagSummary
        try { Set-Clipboard -Value $diagSummary -ErrorAction Stop }
        catch {
            $diagFailed=$true
            Write-Output 'clipboard_failed；已有信息在上方，请手动复制；停止，不重跑。'
        }
        try { Set-Location -LiteralPath $diagOldLocation.Path }
        finally {
            $OutputEncoding=$diagOldEncoding
            [Console]::OutputEncoding=$diagOldConsole
        }
    }
    if ($diagFailed) { throw 'windows_experiment_stopped_no_retry' }
}
```

## Implementation registration and local evidence

Runtime candidate: commit `1b99466b802bc32feecb2d2d4efcde35641ea412`, tree
`994e2f7fee8a51f8ffd34b4bebbb3fd18951a937`. This subsequent docs-only commit
registers an existing implementation tree; use the final reviewed block above,
even though that runtime checkout contains the earlier placeholder documentation.
No execution before ChatGPT/Hanabi review and operator's manual merge is authorized.

New local diagnostic tests:92 passed/20 native Windows tests skipped on Linux.
Combined original email/diagnostic regressions plus new tests:746 passed/77 skipped.
The differential sweep covers3122 original-parser comparisons plus malformed JSON,
major rejection branches and annotation failure. Acceptance/status/signatures match;
classifier exceptions/unsupported categories give unknown. Twelve PR111 routing
and gate unit methods, actionlint1.7.11 and diff whitespace checks pass.
Frozen dependency/config/scorer bytes and CI routing/cancellation are unchanged.
Cloud results belong in the PR once its normal CI completes; no baseline rerun.
