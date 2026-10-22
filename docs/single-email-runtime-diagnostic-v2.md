# Ollama 0.40.6 compatibility diagnostic v2 — frozen plan

Base: `7a73477bb6b8e3aa95ab71ed23abe2fae292d5ae` (PR108 merge; latest main
at start, no intervening commits). New identity: `single-email-runtime-diagnostic-v2-ollama0406`.
Config: `experiments/configs/single-email-runtime-diagnostic-v2.json`, LF SHA256
`461b7e83eb51798aa261446c440c20a0908963b40fd4902bd14cd61ac1332aa7`.
This plan/config is separately committed, pushed and remote-verified **before**
implementation. It is a seen synthetic diagnostic, not preregistered blind quality evidence.

## Evidence and uncertainty

operator's v1 run received a complete chat envelope in15.563s (15.797s total), then
prediction validation rejected it. This is not a timeout or proof of hardware/model
quality. No reply-field summary was kept: **the actual failure cause remains unknown**.

Independent offline reproduction of the old validator: a valid envelope is valid
without `prompt_eval_cached_count`; adding0 or64 makes it protocol_error. This
establishes a compatibility defect, not the unique cause of operator's actual response.

Official v0.40.6 source inspected:

- [api/types.go](https://github.com/ollama/ollama/blob/v0.40.6/api/types.go): Metrics
  has `PromptEvalCachedCount *int` with `omitempty`. LF SHA256
  `e19aafa5065afa3ed058df9135d200527391e012349ed5955dd0cc09c0b33f7a`.
- [server/routes.go](https://github.com/ollama/ollama/blob/v0.40.6/server/routes.go):
  both chat paths forward the cached metric. LF SHA256
  `47c0bce03da44ba50c65e436f61538c67457282b9504a1ecc11d090461120855`.
- [llm/server.go](https://github.com/ollama/ollama/blob/v0.40.6/llm/server.go):
  response types carry the optional pointer. LF SHA256
  `5d6f9c808fa16900e5302f4de7084dc11a556f2480ef397de81efe3a94c9576d`.
- API reference: https://docs.ollama.com/api/chat (versioned source above governs
  this compatibility decision; live docs are not a frozen source pin).

The API forwards counters, and Metrics.Summary uses max(0,prompt-cached) for rate
presentation. It does not impose an API invariant cached<=prompt. Do not invent
that relationship, cached<=ctx, duration sums or absent=zero. The new field is
optional; when present it must be an exact non-bool integer0..2^63-1 (resource
bound, not a semantic assertion). Null/string/float/negative/overflow are rejected.
Existing eval<=512, prompt_eval<=4096 and thinking_count=0 budgets stay unchanged.
This runner explicitly requires observed runtime version0.40.6; no fallback/version upgrade.

## Fixed experiment boundary

Only WC01-1 from the unchanged wording36 fixture. At most one chat; no probes,
warmup, retry, smoke/full, alternate model/host/input, model download/unload/restart,
environment/driver change or server cancellation. Same exact tag/digest, original
prompt/schema, think=false, stream=false, temperature0, seed0, ctx4096, predict512.
Connect5s, metadata5s each, chat180s, total240s. Initial residency recorded without
assuming cold start or GPU utilization. Preserve loopback endpoint/size/deadline
boundaries and immutable identity taint. No raw output/partial JSON salvage.

Old PR107/108 code/config/report interpretation, scorer, fixture/gold/reference,
rule interpreter and product code stay frozen. New code reuses pinned v1 transport,
identity/payload/read safety and pure prediction parser. It has its own response
validator: it must not strip a field then force the envelope through the old one.

## Observability, not looser prediction acceptance

The config freezes finite protocol subreasons, fixed approved presence keys and two
unknown-field **counts**. Never save arbitrary field names/values. Identity takes
priority. Unknown top/message fields, done/role/content/end-reason errors, thinking,
context/tools and original structural boundaries continue to reject prediction.
Protocol reasons distinguish top-level fields, done, message shape/role, content
type, telemetry type/bounds, end reason and other listed finite conditions.

Independently validate each telemetry field before prediction acceptance. Store
only allowed bounded values, plus per-field state: not_obtained / absent /
unavailable / validated / invalid_type / out_of_bounds. Missing data before an
envelope is available is not_obtained, never evidence the server omitted it.
Explicit null on old optional metrics is unavailable; cached-count null is invalid.
Prediction rejection does not erase independently validated telemetry or imply a
successful prediction. Invalid/unavailable fields remain null; no inferred values.
Telemetry is a server claim validated for type/budget, not ground-truth timing or
weight-use attestation. Identity loss remains permanent and suppresses attribution.
All reports say root_cause=unknown and contain no semantic score/comparison.

New local-only report namespace, complete atomic publication/readback, unique runs,
failure cleanup and no overwrite. Full minimized JSON success/partial is printed
and copied, including states, subreason, approved markers/counts, telemetry states,
phase timings, initial residency, identities, finite prediction and exit codes.
No raw response, title, prompt, thinking, input fingerprint or arbitrary error text.

## Windows operational contract

Interactive PowerShell5.1 under Restricted, **no .ps1 loading and no ExecutionPolicy
change**. Use reviewed multiline Python via stdin only. As in v1, verify exact
approved commit/tree and clean checkout before any Python, prefer operator's previously
verified executable, require exact3.12.10, restore cwd/temporary encodings, copy
nonempty full report/errors, stop on partial/read/copy failure with no new inference.
A later documentation commit records the preceding runtime commit/tree to avoid
self-reference. Future main is not executed. Actual inference only after review,
operator's merge and explicit manual command.

## Frozen verification plan

Mock only: cache absent/zero/positive/null/bool/string/float/negative/overflow;
no undocumented counter relation; unknown-field rejection without key-name leakage;
every finite protocol reason; independently valid/invalid/missing telemetry on
rejected prediction; identity taint survives normal final metadata; one-chat/no
retry/timeouts/deadlines; success/partial atomic publish+readback and copy; file/input
pins and all old experiment tests. Native PowerShell5.1 Restricted stdin execution
must exercise the actual interactive command with Mock process/clipboard/Git
boundaries, not just parse syntax. Version/approval failures => zero generation;
report/copy failures preserve info and never retry. Full SQLite/PostgreSQL16 and
existing Windows Python3.12.0/3.12.10 CI remain. No Ollama startup, real inference,
accounts, Holdout or product/permission/database changes.

## Runtime registration

Plan/config freeze: `c6f8c7c65611b1a8e7d78578f92dc16a55734cad`, pushed and read
back with git ls-remote before implementation. Later commits implement the runner;
no real inference occurs in development/CI. The command below will be pinned to a
preceding implementation commit/tree, with only documentation changing afterward.
Pins take effect only after ChatGPT/Hanabi review and operator's approval/merge.

## operator: PowerShell5.1 Restricted, after approval/merge only

Copy the whole block into the interactive PowerShell prompt. Do not save/run it as
.ps1. No ExecutionPolicy change, Bypass or external script load is used. It fetches
only the approved implementation, validates commit/tree/cleanliness before Python,
automatically prefers the previously verified Python executable and requires3.12.10.
No path/code edits are needed. One generation at most; no automatic retry. All
multiline Python goes through stdin, isolated with -I -S. Reports remain in the
printed temporary checkout; directory/encoding/preferences are restored on exit.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $diagOldLocation = Get-Location
    $diagOldEncoding = $OutputEncoding
    $diagOldConsole = [Console]::OutputEncoding
    $diagCommit = '8c7e5d1f7652638c06e2b967373f3731d436441b'
    $diagTree = 'e6202b7f237c8e2cac61a85b9ec20495ccaa943e'
    $diagRoot = Join-Path $env:TEMP ('samas-email-compat-v2-' + [guid]::NewGuid().ToString('N'))
    $diagSummary = "Checkout: $diagRoot`nCommit: $diagCommit`nTree: $diagTree`n"
    $diagFailed = $false
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
    from experiments.collect_single_email_compat import main
    raise SystemExit(main(["--synthetic-only", "single"]))
except SystemExit:
    raise
except (Exception, KeyboardInterrupt):
    print('{"error_code":"workflow_start_failed","workflow_exit_code":1}')
    raise SystemExit(1)
'@
        } else { throw 'invalid_purpose' }
        $reply = $code | & $Python -I -S -u - 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
        [pscustomobject]@{ Output=$reply; Code=$exitCode }
    }
    # MOCK_BOUNDARY: native CI substitutes only process/Git/clipboard boundaries here.
    try {
        $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        [Console]::OutputEncoding = $OutputEncoding
        if ($diagCommit -cnotmatch '^[0-9a-f]{40}$' -or $diagTree -cnotmatch '^[0-9a-f]{40}$') { throw 'approval_pin_missing' }
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git_missing' }
        if (Test-Path -LiteralPath $diagRoot) { throw 'checkout_exists' }
        $ignored = git init --quiet $diagRoot 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw 'git_init_failed' }
        $ignored = git -C $diagRoot remote add origin https://github.com/samas-saigo/family-os.git 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw 'git_remote_failed' }
        $ignored = git -C $diagRoot fetch --quiet --depth 1 origin $diagCommit 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw 'approved_commit_unavailable' }
        $ignored = git -C $diagRoot -c core.autocrlf=false checkout --quiet --detach FETCH_HEAD 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw 'checkout_failed' }
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
        Write-Host 'V2 独立单条诊断：最多一次请求，不重试。'
        $execution = Invoke-ApprovedPython -Python $python -Purpose diagnostic
        $diagSummary += $execution.Output + "`nProcess exit code: $($execution.Code)`n"
        if ([string]::IsNullOrWhiteSpace($execution.Output)) { throw 'workflow_output_missing' }
        if ($execution.Code -ne 0) { throw 'diagnostic_partial_or_failed_no_retry' }
    } catch {
        $diagFailed=$true
        $allowed=@('approval_pin_missing','git_missing','checkout_exists','git_init_failed','git_remote_failed','approved_commit_unavailable','checkout_failed','approved_commit_mismatch','approved_tree_mismatch','approved_checkout_dirty','python_3_12_10_not_found','workflow_output_missing','diagnostic_partial_or_failed_no_retry')
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
    if ($diagFailed) { throw 'windows_diagnostic_stopped_no_retry' }
}
```

This is a trusted fresh-checkout workflow, not protection against hostile Git/Python
installations or concurrent local file tampering. Unavailable/mismatching pins stop
with no fallback to main. The pins cover all runtime code including this new entry;
a later docs-only commit names the already-existing runtime commit/tree, avoiding
self-reference. The local checkout may contain earlier documentation: use this
reviewed command, not an older command found in that checkout.

Full minimized report includes `telemetry_validation`, finite `subreason`, approved
presence markers/counts and root_cause=unknown. Validated telemetry means type/budget
checks only. Durations from Ollama are nanoseconds; client `*_seconds` fields are
seconds. No semantic correctness, actual server stages on missing telemetry, GPU
utilization or historical unique cause can be inferred. Do not rerun on partial or
read/copy failure. No report is rewritten or retrospectively regraded.

Execution commit: `8c7e5d1f7652638c06e2b967373f3731d436441b`; tree:
`e6202b7f237c8e2cac61a85b9ec20495ccaa943e`. The following documentation-only
commit records this existing tree; it does not change the runtime being reviewed.
Native CI imposes Restricted only on its disposable child test processes (never
changes user/machine policy); the actual interactive command has no policy switch.
