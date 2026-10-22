# Synthetic email semantic comparison v2 — frozen plan

Base/latest main: `a7518006aae0e2dbe314739e80427eff08698a75` (PR109 merged; no later commit at start).
Identity: `synthetic-email-model-evidence-v2-ollama0406`. Config LF SHA256: `3088c54578456f242846164b8b121c3311f49d536c3f41789ff3dde04dc11042`.
This plan and full config (including unchanged prompt/schema) are committed and pushed
first; remote commit must be verified before runner implementation. Append the actual
freeze SHA and subsequent implementation identities later. This records ordering, not
a claim of a blind preregistration or independent authorship.

## Contract frozen before implementation

- Only existing frozen wording36: 36 /24 clear /12 ambiguous /12 correlated groups.
  Fixture LF SHA `067b041f142ce9892509f7024ff5d94c6a4a34be2fdd59d4d2e91a408a44b019`; original interpreter/reference/scorer
  unchanged. No Legacy37, Development, Holdout, Calendar or real inputs.
- Exact installed qwen3.5:4b-q4_K_M / digest `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`;
  runtime0.40.6. Prompt/schema and generation byte/value-equivalent to PR107/109:
  think=false,stream=false,temp0,seed0,ctx4096,predict512. No model downloads/change.
- New budgets: connect5s, metadata5s each, chat60s each, whole run600s. PR108/109's
  180s/240s diagnostic and all prior results stay independent and untouched.
- Explicit smoke selects WC01-1,WC02-1,WC03-1,WC10-1,WC11-1,WC10-3 in this order.
  Explicit full selects36 in frozen order. No automatic transition or pooled samples.
- Pinned PR109 compatibility response validator, including cache count and finite
  protocol reasons/independent telemetry. Same numeric-loopback/endpoint/size/deadline
  boundary. Each case gets its own one-chat transport instance; no counter resets,
  monkeypatching, retries, warmup, output repair or mixed rule/model routing.
- Before every chat and at end verify identity; any lost identity is permanent for
  this run, even if final metadata looks normal. Suppress model metrics/group/comparison
  on lost identity; finite predictions remain unattributed diagnostics.
- Existing ordinary invalid JSON/schema/refusal/truncation outcomes continue as failures.
  Transport/protocol/resource/thinking/identity failures stop subsequent chats. Never
  relabel failure as abstain. Keep all selected denominators, including not_attempted.
- Original scorer and compare on identical selections. Partial selected-denominator
  diagnostics are marked partial; complete comparison only when every case attempted,
  no fatal stop, verified identity and valid rule rows. Completed execution is not
  correctness. No single-case operator result is treated as accuracy or a cause diagnosis.
- Only finite minimized report data, same restrictions: no Task/Pending/authority,
  sender text claims only, separate safety/permission and human review mandatory.
  No raw title/prompt/response/thinking/input fingerprints. Residency is not utilization.
- Own UUID report namespace, full atomic publish/readback, cleanup on failure, old files
  preserved. Read-only recovery verifies original printed report SHA + run UUID, fixed
  namespace and bounded regular-file checks, without any inference/network. Hash is
  accidental-corruption evidence anchored to operator's original output, not authentication
  against a malicious local user who can alter that output.
- Windows interactive/stdin only under Restricted; no .ps1 loading/policy change.
  Exact approved checkout commit/tree/clean gate before Python, exact3.12.10 discovery,
  print/copy full minimized JSON for success/partial, restore environment, no retries.

## Verification plan

Mock HTTP only; fixed input/prompt/schema/model/budgets/source hashes; gold isolation;
6/36 selection and24/12/12 full denominators; semantic-error injection; complete/partial
metrics; cache field and finite protocol diagnostics; timeout/budget/identity taint;
no automatic retry/pooling; report atomic failure/isolation/readback/recovery; native
PowerShell5.1/7 Restricted startup/copy/failure/recovery without inference. Retain old
email and Windows tests and full SQLite/PostgreSQL16 CI. No Ollama startup or inference
in development/CI; operator runs manually only after ChatGPT/Hanabi review and her merge.

## Implementation and Windows instructions

To be appended after remote freeze verification; not an execution authorization.

## Runtime registration

Plan/config freeze: `5c82246c031a606c71b0f848f98053faf97d09e5`, independently pushed
and remote-verified before implementation. Config remains unchanged. Source pins
fix PR109's validator, its config, one-chat transport and PR107 parser/scorer. Each
new transport has one fixed projection; the inherited counter is never reset.
Execution commit/tree are recorded in a later docs-only commit to avoid self-reference.

## operator: one interactive PowerShell block (after review and merge only)

Paste into PowerShell5.1, including Restricted. Do not save/load a script or change
ExecutionPolicy. Choose **smoke** or **full** explicitly; neither invokes the other.
Keep the complete console output. For a lost clipboard, choose **recover**, then
enter the32-character suffix from the original printed Checkout folder, the32-character
run ID from report_path and64-character report_sha256 from that output. It reads
that exact existing report only; it does not rerun anything. Do not use a different
run to fill missing data. All three modes verify the same approved checkout/tree
and clean worktree before Python. Recovery does not fetch/change the old checkout.
If report or console hash is lost/unreadable, stop; do not regenerate to recover it.

The full minimized JSON is printed and copied, even for partial/error reports.
Clipboard failure leaves it on screen. A local digest does not authenticate a
hostile checkout or local user. Durations are server claims in nanoseconds and client
phases in seconds; no guarantee of cold start, utilization or semantic correctness.
operator's previously successful WC01-1 diagnostic is not combined with these runs.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $diagOldLocation = Get-Location
    $diagOldEncoding = $OutputEncoding
    $diagOldConsole = [Console]::OutputEncoding
    $diagCommit = '63cd4a2e84df92f7331a4863a6137ac07f02bfaf'
    $diagTree = '2c2ecdb1df643b863a970bb436d97870ecd08f64'
    $diagRoot = Join-Path $env:TEMP ('samas-email-semantic-v2-' + [guid]::NewGuid().ToString('N'))
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
    from experiments.email_model_compat import main
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
        $diagMode = Read-Host '选择 smoke、full 或 recover（只读恢复）'
        if ($diagMode -cnotin @('smoke','full','recover')) { throw 'invalid_mode' }
        if ($diagMode -eq 'recover') {
            $checkoutId = Read-Host '原 Checkout 文件夹末尾32位字符'
            $diagRunId = Read-Host '原 report_path 中的32位运行 ID'
            $diagExpectedSha = Read-Host '原 report_sha256（64位）'
            if ($checkoutId -cnotmatch '^[0-9a-f]{32}$' -or $diagRunId -cnotmatch '^[0-9a-f]{32}$' -or $diagExpectedSha -cnotmatch '^[0-9a-f]{64}$') { throw 'invalid_recovery_identity' }
            $diagRoot = Join-Path $env:TEMP ('samas-email-semantic-v2-' + $checkoutId)
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
        Write-Host '独立语义对照：每例最多一次请求；recover 不推理；不重试。'
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

## Interpretation and review

Complete means all selected attempts finished without a fatal boundary and identity
remained attributable, not that all predictions were valid/correct. Ordinary invalid
JSON/schema, refusal and truncation retain separate failure counts and scorer invalid
output/missed evidence accounting. Partial reports keep the entire selected denominator;
model_metrics and by_group, when identity permits, are explicitly partial diagnostics.
comparison stays null until complete and every selected rule row is valid. Identity
failure suppresses all model metrics/group/comparison and final observed identity.
No Oracle/hybrid policy, automatic actions or semantic-quality threshold is introduced.

No raw response, title, full prompt, thinking or input fingerprint is retained. Run
IDs/hashes are diagnostic identifiers only; do not apply synthetic content fingerprints
to private data (dictionary recovery is possible). The fixed config/source hashes bind
software identity, not proof of actual weights used. The original scorer, parser, fixtures,
rule code and old reports are unchanged. Development/CI use only Mock HTTP.

Approved-execution candidate (pending review): commit
`63cd4a2e84df92f7331a4863a6137ac07f02bfaf`, tree
`2c2ecdb1df643b863a970bb436d97870ecd08f64`. This subsequent docs-only commit
records an existing runtime tree. Use the final reviewed command above, even if
the checkout contains the earlier placeholder documentation. Review is still required.

## Identity-interruption correction

KeyboardInterrupt during any identity observation (initial, before a selected chat,
or final) permanently removes model attribution before propagating the interruption.
A normal final observation cannot restore it: observed_identity/model_metrics/by_group/
comparison are null, prediction_attribution is unattributed_diagnostic, and the run
remains partial/interrupted with all selected denominators and finite diagnostics.
No extra chat is attempted. A KeyboardInterrupt in the chat path alone does not
prove identity loss: if independent final verification succeeds, attribution remains
valid while the interrupted attempt and partial status stay explicit. Frozen config,
prompt/schema, budgets, inputs, scorer and prior implementations/results are unchanged.
