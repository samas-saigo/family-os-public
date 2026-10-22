# Synthetic email relational schema v1 — preregistration

Base main: `6b4cac7b1f5672e814926939dc5eb7748cd9a767` (PR112 merged).
Identity: `synthetic-email-relational-schema-v1`; config:
`experiments/configs/synthetic-email-relational-schema-v1.json`.
Config LF SHA256: `0f6492ebaa67294de1f1c976df8d7387e8229a6fe94dfc46f6824673a82fa5e0`.
Own reports: `.local/email-relational-schema-v1/<UUID>/report.json`.
Commit and push this complete plan/config before implementing the runner. Append
freeze and implementation commit/tree identities afterwards; open PR after local
convergence. This records ordering, not blind or independent preregistration.

## Frozen intervention and selection

The **only generation variable is output_schema**. Preserve PR110 model/tag/digest,
Ollama0.40.6, exact prompt bytes, stream=false/think=false, temperature0, seed0,
num_ctx4096, num_predict512, request16384/response65536/content8192 bytes,
connect5s/metadata5s/chat60s/run600s. No runtime upgrade or schema fallback.
Original fixture36, strict parser, envelope validator, semantic scorer and all
PR107–112 implementations/configs/reports stay frozen. Pin reused sources.

Manual smoke: WC01-1, WC01-3, WC05-1, WC10-1, WC11-1, WC12-1 in that order.
Manual full: all original36 in frozen order. Independent modes, one generation per
case, no automatic full, retry, warmup, repair, completion or answer changes.
All selected cases, including unattempted and rejected, remain in denominators.
Use unchanged PR110 semantic score/compare plus PR112 finite structure_reason.
Only parser-validated predictions may be reported. No raw response, thinking,
prompt, subject, input fingerprint or rejected prediction. Unknown stays unknown.

## Exact runtime source evidence

Ollama tag v0.40.6 resolves to
[`2476d5ead197abe04629651028f83d48dc75d2b2`](https://github.com/ollama/ollama/tree/2476d5ead197abe04629651028f83d48dc75d2b2).
At that revision, [llm/server.go](https://github.com/ollama/ollama/blob/2476d5ead197abe04629651028f83d48dc75d2b2/llm/server.go#L104)
serves all GGUF models via llama-server; [llm/llama_server.go](https://github.com/ollama/ollama/blob/2476d5ead197abe04629651028f83d48dc75d2b2/llm/llama_server.go#L1707)
passes format as json_schema (or derives its GBNF before a thinking boundary).
The alternative OpenAI chat path also passes the same schema. Windows NVIDIA GGUF
is not the MLX xgrammar path. [LLAMA_CPP_VERSION](https://github.com/ollama/ollama/blob/2476d5ead197abe04629651028f83d48dc75d2b2/LLAMA_CPP_VERSION)
pins b11669, resolved to llama.cpp
[`620d2225cc436ab0b001e3200e590e3b286ef9ab`](https://github.com/ggml-org/llama.cpp/tree/620d2225cc436ab0b001e3200e590e3b286ef9ab).
Ollama's llama/server/CMakeLists.txt fetches that pin; its compatibility patch does
not modify schema/grammar sources. LLAMA_LLGUIDANCE defaults OFF upstream and is not
enabled by Ollama's build configuration.

At that exact llama.cpp revision:

- [common/json-schema.cpp](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/common/json-schema.cpp#L175)
  builds same-document refs, anyOf, required closed objects, enum, homogeneous arrays
  with min/maxItems, tuple arrays from items lists, null and anchored string patterns.
- [common/json-schema-to-grammar.cpp](https://github.com/ggml-org/llama.cpp/blob/620d2225cc436ab0b001e3200e590e3b286ef9ab/common/json-schema-to-grammar.cpp#L875)
  converts that intermediate representation to GBNF. Tuple conversion emits an
  exact-length tuple; therefore each candidate tuple explicitly has minItems=maxItems=2
  and additionalItems=false, so standard schema meaning and conversion agree.
- The candidate uses only these inspected features. It does not use contains,
  if/then/else, dependentSchemas, uniqueItems or dynamic cross-field references;
  arbitrary unsupported keywords can be ignored by this converter, so they cannot
  establish constraints. No assumption is taken from current/latest documentation.
  Offline source compilation/conversion evidence will be registered after validation;
  it is not binary attestation of the user's installed executable or model inference.

## Candidate schema and remaining parser constraints

Five disjoint state object branches, with shared local definitions:

- outstanding: exactly one outstanding step, or exactly two steps with an outstanding
  first or second step; the other step may have **any original status**. Both orders
  and all distinct action combinations remain legal. Optional due_date has nonnull action.
- completion: one or two completed steps; optional reported_completion_date has nonnull action.
- informational: zero to two failed/cancelled steps; optional event_date/available_date,
  action=null. promotional: zero steps, optional offer_expiry, action=null.
- abstain: zero steps and zero dates. Every state keeps the original field set,
  all original actions and at most one date. Dates remain optional, including when
  steps are present. No subject/gold-dependent schema specialization.

The original strict parser remains the **only acceptance authority**. It still checks
real calendar validity and inclusive2015–2035, distinct step actions, date action
binding to an existing correctly-statused step, notice_kind compatibility, strict
JSON/encoding/size and all original structure. Textual/semantic correctness remains
separate from schema compliance and is evaluated by the frozen scorer. Schema may
permit outputs that the parser rejects; no such rejection becomes abstain.

## Execution, privacy and validation contract

Retain permanent identity taint, before-each/final observations, fatal stopping,
selected-denominator partial reports, bounded numeric-loopback one-chat transport,
atomic UUID save/readback, original printed SHA verification and read-only recover.
Unknown errors use finite codes. Identity loss suppresses attributable model metrics,
comparison and reason counts even if a final observation looks normal.
Windows: verified interactive PowerShell5.1/7 Restricted stdin flow, approved
commit/tree/clean gate before exact Python3.12.10, full print and automatic clipboard,
restore environment; never change execution policy. No saved script execution.

Offline/Mock-only development and CI: assert actual wire payload differs from PR110
only at format/schema for every36 cases and fits unchanged request budget; cover
all states, one/two-step legal status/action/order combinations and optional roles;
assert invalid relations still rejected by original parser, finite private reasons,
source pins, permanent identity loss, timeout, partial save, recovery/isolation and
native Restricted behavior. No real Ollama, real account, Holdout, Task/Pending or
action authority. Normal PR111 CI routing, no allowlist expansion, no cloud demo or
historical baseline rerun. Batch push after local convergence.

PR112's reported six-case run (21.547s, valid1/rejected5; state_steps1,
date_state_relation3,date_action_binding1) motivates this new schema hypothesis.
It is not accuracy, does not identify PR110's old20 failures and is not modified,
reconstructed or pooled. This candidate makes no improvement claim before a future
manual run. Seen correlated synthetic36 scores are not independent real-world accuracy.
ChatGPT first review, Hanabi independent review, user manual merge; only then may the
user explicitly start smoke or full on their machine. Never auto-merge or auto-run.

## Freeze registration and manual Windows workflow

Freeze `3e31bb36df6c8602c5ab3b6bbb95dc2c778dbbe2` was pushed and remotely
verified before runner implementation. The config above remains unchanged.
Execution commit/tree will be registered after the implementation commit exists.
Only after review and merge, paste the whole block into interactive PowerShell5.1/7
under the existing Restricted policy. Choose smoke or full explicitly; smoke never
starts full. For recover, enter the original32-character checkout suffix, report UUID
and original64-character report SHA. Recovery reads the same checkout without
fetching/modifying it and never generates. Preserve the complete output. Clipboard
failure prints it and stops; never regenerate missing results. Partial/error output
is also printed/copied. No execution-policy changes or saved script loading.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $diagOldLocation = Get-Location
    $diagOldEncoding = $OutputEncoding
    $diagOldConsole = [Console]::OutputEncoding
    $diagCommit = '81c0610e1ce20c05e3ba4b89596f65b985be2c08'
    $diagTree = 'e5319f302596059ae045a4fd49de7e1ef3073142'
    $diagRoot = Join-Path $env:TEMP ('samas-email-relational-schema-v1-' + [guid]::NewGuid().ToString('N'))
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
    from experiments.email_relational_schema import main
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
            $diagRoot = Join-Path $env:TEMP ('samas-email-relational-schema-v1-' + $checkoutId)
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
        Write-Host '独立 Schema 候选：每例最多一次请求；recover 不推理；不重试。'
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

## Offline converter evidence and coverage

The exact pinned upstream C++ sources were compiled locally without a model,
server, network request or inference. `experiments/schema_support/convert.cpp`
is a stdin JSON-to-GBNF harness; it links upstream helpers and uses an abort-only
GGML assertion stub, with LLGuidance absent. It does not implement a replacement
converter. For reproducibility, with the above exact llama.cpp checkout as CWD:

```sh
g++ -std=c++17 -O1 -ffunction-sections -fdata-sections -Wl,--gc-sections \
  -Icommon -Iinclude -Iggml/include -Ivendor -Ivendor/nlohmann \
  /path/to/family-os/experiments/schema_support/convert.cpp \
  common/common.cpp common/json.cpp common/json-schema.cpp \
  common/json-schema-to-grammar.cpp common/trie.cpp common/unicode.cpp \
  -o /tmp/schema-convert
/tmp/schema-convert < /path/to/family-os/experiments/configs/synthetic-email-relational-schema-v1.json > /tmp/candidate-schema.gbnf
```

Conversion exited0, with no stderr warnings. Source file SHA256:

| File at llama.cpp620d2225 | SHA256 |
| --- | --- |
| common/json-schema.cpp | 68ba2adbb6e0578c0d89e99cc9a9a7aa9c0b554b555bcd3908da71789045509d |
| common/json-schema-to-grammar.cpp | d5a82fff5d611abd1198ff27c328b20376ffe9f110b4771d579c8bd20c70541f |

The resulting9,751-byte grammar is retained at
`experiments/schema_support/relational-v1.gbnf`, SHA256
`fc620e5fd1d625b24ed9e79470cb2853752e64ce422ccc6c8f67b7b9e54ddaf0`.
It is generated grammar evidence, never a model response or historical result.
CI consumes this fixed offline artifact; it does not fetch/build/run Ollama.
The tests translate only this artifact's acyclic literal/class/union/repetition/ref
GBNF subset to regex, fail on unknown syntax, and independently check the candidate's
JSON Schema subset against the unchanged parser. Converter grammar orders object
properties as declared and restricts whitespace; object-key order is not a different
prediction. All legal step **array orders** are preserved and tested.

Exhaustive distinct-action zero/one/two-step enumeration finds301 outstanding,
49 completion,183 informational,1 promotional and1 abstain legal step combinations.
All remain possible in both the schema and actual converted grammar, with no date
and with each legal date role/bound-step option. All original actions/statuses and
both mixed-step orders are included. Explicit negative tests separate newly encoded
state/role/nullability relations from intentionally parser-only constraints.
Actual full36 Mock HTTP requests are7,147–7,210 UTF-8 bytes; format replacement
restores the exact PR110 request and prompt bytes. No generation setting or budget
was changed. Local candidate suite:82 passed,22 native Windows cases skipped on
Linux; native5.1/7 behavior is delegated to the normal Windows CI jobs, not inferred
from those skips. Final CI and implementation identities are recorded below.

## Implementation identity registration

Frozen implementation/execution commit:
`81c0610e1ce20c05e3ba4b89596f65b985be2c08`.
Execution tree: `e5319f302596059ae045a4fd49de7e1ef3073142`.
The executable instructions above pin that existing commit/tree; this registration
is documentation only. The full console/clipboard envelope records both, while each
report includes freeze/config/source/schema identities and the runner's LF SHA256.
Runner LF SHA256: `97e54a9bc39b46c45f7d8b973803843168553d78cbf32252ceb4e8f7ba2eccb6`.
Schema canonical SHA256: `e0e6d820eb846139116df553962b5d884d0a94e9192df892f6f71b0cf9799083`.
Prompt bytes retain SHA256: `4f691eb278ac8158b4a72ee3b602bb86bbe8af04fa0829cd45346657cb059bda`.
Review and merge must precede any manual run; registration does not authorize a run.

Local full regression on Python3.12.14:8,176 passed,99 skipped in383.62s;
two existing I2/I3 loopback-service tests failed because the default sandbox denied
socket creation (PermissionError). With the required local network permission,
those exact two tests passed in3.02s. No product/test assertion was changed.
Candidate requests remain mocked and real sockets are blocked by its test fixture.
The operator still requires exact3.12.10; native Windows CI tests both configured
versions and the documented Restricted boundaries. Existing router/failure tests:
12 passed,44 subtests passed. actionlint/diff checks passed. Normal final-HEAD CI
results will be attached to the PR; no extra cloud baseline/demo run is requested.
