param([string]$Scenario)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $root 'experiments/single_email_windows.ps1')
$script:calls = 0
$script:copies = 0
$script:copied = ''
$script:selected = ''
$script:gate = $false
$script:probes = 0
function Assert-DiagnosticCheckout {
    param($Root,$ApprovedCommit,$ApprovedTree)
    if ($Scenario -eq 'checkout_bad') { throw 'approved_checkout_mismatch' }
    $script:gate = $true
}
function Get-DiagnosticPythonCandidates {
    if (-not $script:gate) { throw 'version_probe_before_gate' }
    @('verified-python','fallback-python')
}
function Test-DiagnosticPythonVersion {
    param($Python)
    if (-not $script:gate) { throw 'version_probe_before_gate' }
    $script:probes++
    if ($Scenario -eq 'version_bad') { return $false }
    if ($Scenario -eq 'fallback' -and $Python -eq 'verified-python') { return $false }
    return $true
}
function Invoke-DiagnosticPython {
    param($Python)
    if (-not $script:gate) { throw 'inference_before_gate' }
    $script:calls++
    $script:selected = $Python
    $code = if ($Scenario -eq 'partial') { 2 } elseif ($Scenario -eq 'report_error') { 1 } else { 0 }
    $json = @{ workflow_exit_code=$code; diagnostic_exit_code=0; report_path='.local/single-email-runtime-diagnostic/synthetic/report.json'; report=@{ requests=@(@{ phases=@{ connect=@{ elapsed_seconds=0.1; completed=$true } } }); result=@{ telemetry=@{ load_duration=80000000000 } } } } | ConvertTo-Json -Depth 15
    if ($Scenario -eq 'empty_output') { $json = '' }
    [pscustomobject]@{ Output=$json; Code=$code }
}
function Set-Clipboard {
    param($Value,$ErrorAction)
    $script:copies++
    if ($Scenario -eq 'clipboard_error') { throw 'clipboard unavailable' }
    $script:copied = $Value
}
$originalLocation = (Get-Location).Path
$temporary = Join-Path $env:TEMP ('samas-workflow-mock-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $temporary
Set-Location -LiteralPath $temporary
$oldLocation = (Get-Location).Path
$oldEncoding = $OutputEncoding
$oldConsole = [Console]::OutputEncoding
$oldPreference = $ErrorActionPreference
$printed = New-Object System.Collections.Generic.List[string]
$failed = $false
try {
    Invoke-DiagnosticWindows -Root $root -ApprovedCommit ('a'*40) -ApprovedTree ('b'*40) |
        ForEach-Object { $printed.Add("$_") }
} catch { $failed = $true }
$restored = (Get-Location).Path -eq $oldLocation -and $OutputEncoding.CodePage -eq $oldEncoding.CodePage -and [Console]::OutputEncoding.CodePage -eq $oldConsole.CodePage -and $ErrorActionPreference -eq $oldPreference
Set-Location -LiteralPath $originalLocation
Remove-Item -LiteralPath $temporary -Force
# Suppress host messages from the production workflow; JSON is last output line.
@{ version_probes=$script:probes; calls=$script:calls; clipboard_attempts=$script:copies; copied=$script:copied; selected=$script:selected; printed=($printed -join "`n"); restored=$restored; failed=$failed } | ConvertTo-Json -Compress -Depth 15
