# Local Qwen3 thinking experiment — original 37 synthetic cases

`experiments/local_thinking_benchmark.py` is a manual, independent experiment, not
a Family OS integration. No provider, database, task, authentication or I9 code is
changed. Development and Holdout have **no input path or command** in this tool.
Any later Development extension needs a separate review. Holdout additionally
requires separate owner confirmation after model/prompt/parameter/scoring freeze.
No real household data may enter any AI, including local Ollama.

## Historical evidence and fixed experiment identity

Audited main: `79ccdda659e74fad52fc3a6db90ef0d69baa3be3` (PR #99 merged).
The existing Phase 2M/N/P runner and its versions remain unchanged.
Only `fixtures/metadata-reasoning.synthetic.json` is loaded. Its LF-byte SHA-256 is
`529f81a7adb293ecf89297996ea62237a65a931b8fead1f3f92a2ebea1ac2047`, identical
to initial commit `930aac5`. Windows CRLF is normalized **in memory for identity**;
the fixture is never rewritten. Both config files and prompt/schema digests are pinned.

37 selected cases include 6 required, 8 not_required, 23 uncertain. Only 34 pass
the unchanged strict metadata projection; URL, oversize and wrong-shape cases remain
rejected. They are not sent in either mode. Truth, fake script and case IDs never
enter model prompts. No new examples, labels or prompt tuning are introduced.

Historical reports in [Issue #42](https://github.com/samas-saigo/family-os/issues/42),
[Issue #44](https://github.com/samas-saigo/family-os/issues/44) and
[Issue #46](https://github.com/samas-saigo/family-os/issues/46) are operator summaries,
not recoverable raw prediction records. The original 4B quantization and run digest
were not recovered. A current digest pins **this new run**, never proves historical
weight equality. The manifest always says `historical_weights_verified=false`.

The original Qwen3 request **omitted `think`**. `legacy-omitted` preserves that
Flat-Domain request shape; explicit `off`/`on` are separately identified experiments.
The old four-field `baseline` is not this tool's wire variant. We reuse exactly the
historical Flat-Domain instruction + taxonomy + `UNTRUSTED_METADATA_JSON` prompt
and JSON schema through `/api/generate`, not new system/user chat messages.

## Matrix and compatibility gates

| Model | Mode | Request control |
| --- | --- | --- |
| `qwen3:8b-q4_K_M` | `off` | top-level `think:false` |
| same 8B digest | `on` | top-level `think:true` |
| `qwen3:4b-instruct` | `off` / `on` | same explicit booleans, only if compatible |
| exact 4B tag | `legacy-omitted` | no `think`, **not** explicit OFF |

No tag substitution, model download, unload, driver update or API fallback occurs.
The user must separately install any missing approved model. The optional historical
Qwen3.5 extension is deferred; it is not an accepted model here.

Inventory reads `/api/version`, `/api/tags`, `/api/show` on fixed numeric loopback.
Only bounded model details (format, family, parameter size, quantization), capabilities,
exact tag/digest and runtime are reported; template/modelfile paths are not emitted.
Generation requires an explicitly supplied SHA-256 matching current inventory;
Qwen3/gguf family, 4B or 8B size, and 8B Q4_K_M are checked. The 4B quantization is
recorded, not assumed. Check it manually against any recovered old manifest.
Identity is rechecked before every case and at end/abort. This is bracketed tag
verification, **not** atomic proof of which weights a server used mid-request.
Final identity failure withholds attributed scores, retaining local diagnostic rows.

Explicit modes require `/api/show`'s `thinking` capability. Missing capability means
unverified/incompatible, even if an older server might actually support the setting.
HTTP 400/422 on generation marks requested configuration incompatible. Other API
failures stop without retry. ON additionally requires nonempty separate `thinking`
on completed, untruncated responses; OFF and legacy require absent/empty thinking.
Wrong response identity, malformed envelopes and envelope resource violations stop
without publishing a completed score; they are not attributed as classification errors.
These are observed API compatibility gates, not proof of internal computation:
an empty trace cannot prove a server honored OFF. No runtime-version string alone
establishes support. Actual owner-reported Ollama 0.40.6 compatibility remains untested.

Generation settings stay `temperature=0, seed=0, num_ctx=4096, num_predict=256`,
`stream=false, keep_alive=1m`. Every case sends a fresh request with **no returned
context, message history or previous answer**. No seeds or prompts vary by result.
`done_reason=length` is reported as `budget_truncated`, even when the final response
is empty. It is not a successful answer or proof of ON compatibility. A larger
budget is not supported in this version; it would need an independent experiment
identity and equivalent budgets across comparison groups, never replace this control.

## Scores, failures and performance

Complete full runs retain the historical metrics from `metric_records()` for rules
and model, plus incremental domain coverage. Required miss denominator is **6**;
decisive action accuracy denominator is **14**. The legacy miss definition includes
both not_required and uncertain, and invalid/gated fallbacks remain uncertain solely
inside this legacy computation. JSON validity, action, relevance, domains and review
recommendation are distinct. All confidence values remain zero and facts empty.

Additional diagnostics preserve raw states: required→not_required (incorrect dismissal),
required→uncertain (missed decisive recognition, uncertainty retained), uncertain→concrete,
invalid/truncated/API failures, valid-only confusion matrix/accuracy, not_required
false-positive rate and required miss rate. Invalid outputs have `predicted=null`,
not a model uncertain label. A prediction of uncertain **creates no review item**.
Counts, numerator/denominator semantics and null zero-denominator rates prevent
failure from being mistaken for correct non-action. Smoke uses its actual subset
denominators, never the full 6/14 reference counts. Aborted repeats have coverage
and raw diagnostic rows, but no completed-run score; unattempted cases are explicit.

`completed=true` means bounded requests finished, not that predictions were valid,
thinking support was conclusively established, or the model was useful. Budget
truncation and invalid outputs may occur on every case. A full run is inappropriate
until the operator has examined smoke compatibility, validity and timing.

Each local row records case/expected/predicted/parse status, nullable correctness,
false-positive and uncertainty flags, exact request, original envelope, wall time,
available token/duration telemetry and rate. Model/think/digest/options are bound
by the enclosing manifest. Only the **separate** thinking field is evaluated apart
from the final response. Inline reasoning, malformed JSON, duplicate keys, unknown
fields and taxonomy violations are never stripped, repaired or counted successful.
Every valid classification still requires independent human confirmation before any
future action; `uncertainty_retained` separately identifies the uncertain label.

Ollama `eval_count/eval_duration` gives reported generation tokens/sec; the API does
not independently split thinking vs final tokens, so both split counts are null.
Latencies/rates include only available telemetry, with sample counts. First-case
timing is visible in rows. Never compare laptop NVIDIA speed as an AMD baseline.
Optional `/api/ps` before/after records matching tag/digest size and VRAM fraction.
Missing residency stays null. **100% residency is not measured RX 7600 utilization**
and does not establish GPU vendor. Record device identity/CPU/RAM separately below.

Up to three whole repetitions have separate denominators; they are not 18 positive
examples instead of 6. Temperature/seed do not guarantee deterministic GPU output.
Run models serially, close unrelated GPU workloads, record warm/cold conditions,
and alternate ON/OFF order across invocations rather than choosing the best run.

## Local safety and artifacts

Transport is stdlib `HTTPConnection` to **127.0.0.1:11434 only**, bypassing ambient
proxies/DNS, with five allowed API operations, no redirects, 5s connect/60s request
watchdog, 600s total deadline, 32KiB request, 64KiB envelope and 4KiB final response.
The transport additionally verifies generation payloads match only fixed projections.
Failures never echo response/driver details. No network listener or subprocess exists.

Raw synthetic results (including reasoning) go only to a new
`.local/local-ai-benchmark/<random-run-id>/report.json`, ignored by Git. Stdout is
aggregate-only with a relative artifact path. Reports are never read back as input,
resumed or overwritten. They contain no authorized route for private input.
They are **untrusted model text**, not instructions or HTML; view as plain text.
Do not publish raw artifacts by default. Protect the local directory and Windows
user ACL/backups yourself; directory mode is not a Windows encryption/ACL guarantee.
Ctrl+C after generation begins attempts final identity verification and saves partial
results; forced termination/disk failure can lose the report. No claim of durable
incremental checkpointing. Local Ollama inference may continue after a client timeout;
wait/check locally before manually starting another group. No automatic retries.

## Windows PowerShell — owner-run only, after review

From the checked-out repository root; no server installation or model pull is performed:

```powershell
git fetch origin
git switch feat/local-thinking-benchmark
git pull --ff-only
py -3.12 -m venv .venv
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -r requirements-dev.lock
& $py -m pip install --no-deps -e .
$tool = ".\experiments\local_thinking_benchmark.py"
$model = "qwen3:8b-q4_K_M"
& $py $tool --synthetic-only --model $model --inventory
if ($LASTEXITCODE -ne 0) { throw "Inventory failed: stop; do not substitute a model." }
$digest = Read-Host "Paste the exact 64-character digest from inventory"
& $py $tool --synthetic-only --model $model --thinking off --expected-digest $digest
if ($LASTEXITCODE -ne 0) { throw "OFF smoke failed: inspect local report; stop." }
& $py $tool --synthetic-only --model $model --thinking on --expected-digest $digest
if ($LASTEXITCODE -ne 0) { throw "ON smoke failed: inspect local report; stop." }
```

Before continuing, inspect both aggregate reports and local rows. All-invalid or
truncated output can exit normally; do not treat exit code alone as readiness.
No automatic full run follows the smoke. After acceptable smoke and owner decision:

```powershell
& $py $tool --synthetic-only --model $model --thinking off --expected-digest $digest --full --repeats 3
& $py $tool --synthetic-only --model $model --thinking on  --expected-digest $digest --full --repeats 3
```

For 4B, change `$model` to `qwen3:4b-instruct`, repeat inventory, and set its own
digest. Do not reuse 8B digest or replace the tag with `qwen3:4b`. Explicit modes
may be incompatible; `legacy-omitted` is a separate optional control, not a workaround
to claim explicit OFF. There is no bearer token or household account in this tool.

Optional local hardware evidence (do not post serial numbers/private machine names):

```powershell
ollama --version
ollama ps
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
```

At reported 46.6 tokens/s, 34 × 256 tokens is about 3.1 minutes of generation alone;
this is arithmetic, **not an AMD measurement by Codex**. Allow 15–30 minutes for
initial three-group checks, or 45–90 minutes for repeated comparisons, then revise
using smoke. The fixed 600s run budget may abort slow three-repeat invocations;
use independent one-repeat invocations, never silently raise the configured budget.

## Validation and review

CI uses only mocked HTTP/synthetic data; it never runs Ollama. Tests cover exact
corpus/projection gates, original prompts/options, legacy omission vs explicit flags,
unsupported modes, digest/quantization, truncation/invalid answers, missing telemetry,
failure/identity changes, repeat denominators, local artifact isolation and transport
bounds. Existing historical tests remain unchanged. Full SQLite/PostgreSQL results
and exact head are recorded in the PR; no GPU accuracy/compatibility claim is made.

Owner gates: ChatGPT code review, independent Muse security review, Windows smoke,
then human-controlled merge. No production model choice follows from this tiny,
previously inspected, partly uncertain-labeled synthetic dataset.
