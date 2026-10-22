# Functions only. Dot-source after the documentation's approved commit/tree gate.
# No inference, filesystem change or process invocation occurs on dot-source.
function Assert-DiagnosticCheckout {
    param([string]$Root, [string]$ApprovedCommit, [string]$ApprovedTree)
    if ($ApprovedCommit -cnotmatch '^[0-9a-f]{40}$' -or $ApprovedTree -cnotmatch '^[0-9a-f]{40}$') {
        throw 'approved_checkout_mismatch'
    }
    $head = git -C $Root rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or "$head" -cne $ApprovedCommit) { throw 'approved_checkout_mismatch' }
    $tree = git -C $Root rev-parse 'HEAD^{tree}'
    if ($LASTEXITCODE -ne 0 -or "$tree" -cne $ApprovedTree) { throw 'approved_checkout_mismatch' }
    $dirty = git -C $Root -c core.fsmonitor=false status --porcelain --untracked-files=all
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'approved_checkout_dirty' }
}

function Get-DiagnosticPythonCandidates {
    # The exact previously verified executable is first. Do not require edits.
    $candidates = @(
        (Join-Path $env:TEMP 'samas-i9-56051b5dbf8443cfba3b2d55bbee16a9.venv\Scripts\python.exe'),
        (Join-Path $env:TEMP 'samas-i9-56051b5dbf8443cfba3b2d55bbee16a9\.venv\Scripts\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
    )
    $candidates += @(Get-Command python.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
    $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
}

function Test-DiagnosticPythonVersion {
    param([string]$Python)
    $probe = @'
import json, sys
print(json.dumps(list(sys.version_info[:3])))
'@
    try {
        $reply = $probe | & $Python -I -S -u - 2>$null | Out-String
        if ($LASTEXITCODE -ne 0) { return $false }
        $v = ConvertFrom-Json -InputObject $reply -ErrorAction Stop
        return (($v -is [array]) -and $v.Count -eq 3 -and $v[0] -eq 3 -and $v[1] -eq 12 -and $v[2] -eq 10)
    } catch { return $false }
}

function Invoke-DiagnosticPython {
    param([string]$Python)
    $program = @'
import pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
if sys.version_info[:3] != (3, 12, 10):
    print('{"error_code":"python_version_mismatch","workflow_exit_code":1}')
    raise SystemExit(1)
root = pathlib.Path.cwd()
sys.path[:0] = [str(root), str(root / "src")]
try:
    from experiments.collect_single_email_diagnostic import main
    raise SystemExit(main(["--synthetic-only", "single"]))
except SystemExit:
    raise
except (Exception, KeyboardInterrupt):
    print('{"error_code":"workflow_start_failed","workflow_exit_code":1}')
    raise SystemExit(1)
'@
    $output = $program | & $Python -I -S -u - 2>&1 | Out-String
    $code = $LASTEXITCODE
    return [pscustomobject]@{ Output = $output; Code = $code }
}

function Invoke-DiagnosticWindows {
    param([string]$Root, [string]$ApprovedCommit, [string]$ApprovedTree)
    $oldLocation = Get-Location
    $oldEncoding = $OutputEncoding
    $oldConsole = [Console]::OutputEncoding
    $oldPreference = $ErrorActionPreference
    $summary = "Checkout: $Root`nApproved commit: $ApprovedCommit`nApproved tree: $ApprovedTree`n"
    $failed = $false
    try {
        $ErrorActionPreference = 'Stop'
        $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        [Console]::OutputEncoding = $OutputEncoding
        # Before version probes or repository Python imports, not just printing SHA.
        Assert-DiagnosticCheckout -Root $Root -ApprovedCommit $ApprovedCommit -ApprovedTree $ApprovedTree
        Set-Location -LiteralPath $Root
        $python = $null
        foreach ($candidate in @(Get-DiagnosticPythonCandidates)) {
            if (Test-DiagnosticPythonVersion -Python $candidate) { $python = $candidate; break }
        }
        if (-not $python) { throw 'python_3_12_10_not_found' }
        $summary += "Python: $python`nVerified Python: 3.12.10`n"
        Write-Host '仅一次 WC01-1；不会重试；完整报告随后打印并复制。'
        $execution = Invoke-DiagnosticPython -Python $python  # Sole invocation.
        $summary += $execution.Output
        $summary += "`nProcess exit code: $($execution.Code)`n"
        if ([string]::IsNullOrWhiteSpace($execution.Output)) { throw 'workflow_output_missing' }
        if ($execution.Code -ne 0) { throw 'diagnostic_partial_or_failed_no_retry' }
    } catch {
        $failed = $true
        # Exceptions from known workflow gates are finite codes. Do not echo
        # arbitrary native/driver errors; already returned diagnostic stays intact.
        $known = @('approved_checkout_mismatch', 'approved_checkout_dirty', 'python_3_12_10_not_found', 'workflow_output_missing', 'diagnostic_partial_or_failed_no_retry')
        $code = if ($known -contains $_.Exception.Message) { $_.Exception.Message } else { 'windows_workflow_failed' }
        $summary += "`n操作停止：$code；禁止为补取报告重新推理。`n"
    } finally {
        if ([string]::IsNullOrWhiteSpace($summary)) { $summary = 'windows_workflow_failed_no_output' }
        Write-Output $summary
        try { Set-Clipboard -Value $summary -ErrorAction Stop }
        catch {
            $failed = $true
            Write-Output 'clipboard_failed；完整已有信息保留在上方，请手动复制；停止，不重跑诊断。'
        }
        try { Set-Location -LiteralPath $oldLocation.Path }
        finally {
            $OutputEncoding = $oldEncoding
            [Console]::OutputEncoding = $oldConsole
            $ErrorActionPreference = $oldPreference
        }
    }
    if ($failed) { throw 'windows_diagnostic_stopped_no_retry' }
}
