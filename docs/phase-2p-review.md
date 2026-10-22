# Phase 2P — controlled local Qwen3.5/Qwen3 synthetic comparison

Issue #44 enables an explicit, manual comparison of two already installed models.
It is not production inference, a model-quality decision, a training job, or permission
to process household metadata. No live model or household data was accessed here.

## Grounded context and experiment

The user reports Windows 11, RTX 2060 Max-Q 6 GB, 32 GB RAM, Ollama 0.40.1 and installed
qwen3:4b-instruct plus qwen3.5:4b-q4_K_M. A local casual Qwen3.5 run showed visible
thinking and non-JSON output; it was not the constrained benchmark. The reported
3.1 GB residency/100% GPU is an operator observation, not measured by this PR.

The user also reports a completed Qwen3 Flat-Domain synthetic run: 34 projected/sent
and valid, three expected projection rejections, relevance 17/18, action 5/14,
required-action misses 5/6, three correct decisive classifications where rules abstained,
and 17 additional classified cases with unknown human domain truth. These are tiny,
known-fixture measurements, not real-world accuracy or a Qwen3.5 quality prediction.

Only two exact tags are allowed:

- qwen3:4b-instruct — default, preserves both existing wire variants;
- qwen3.5:4b-q4_K_M — explicit candidate, requires explicit `--variant flat-domain`.

There is no implicit variant/model switch. Selecting the candidate with the baseline
wire contract fails safely before inventory/HTTP access. No arbitrary model, alias,
case normalization, file, prompt, host, URI, database, provider account or stdin input
is introduced. Missing/ambiguous/unidentified installed candidate fails without
falling back to Qwen3. No model pull, download, unload or service startup occurs.

For comparison, run **both models with the same Flat-Domain schema**. Prompt, taxonomy,
fixture/order, projection, validators, temperature=0, seed=0, num_ctx=4096,
num_predict=256, stream=false and keep_alive=1m are identical. Qwen3.5 differs only
in installed model artifact and explicit top-level thinking control. No extra prompt
heuristics, /no_think text, few-shot examples, model-specific label repairs or
threshold changes are added.

## Thinking control and compatibility gate

Qwen3.5 requests POST /api/generate with **top-level `think: false`**. `options.think`
is never sent. The HTTP boundary requires the field to be exactly boolean false;
missing, misplaced, true, null, numeric or extra controls are rejected before dispatch.
Qwen3 request keys remain unchanged, with no `think` field added. Tests compare the
serialized Qwen3 default/explicit-selection request bodies, manifests and metric results,
and pin its existing prompt/schema hashes.

No `/api/show` capability probe or `/api/chat` fallback is introduced. The chosen safe
compatibility test is the bounded five-case, strictly validated synthetic smoke below,
manual after review/merge. HTTP 400/422 or any other non-200 fails without retry,
dropping `format`, moving `think` into options, stripping content or changing endpoints.
A version string alone is not evidence that think:false plus structured format works.

The candidate envelope must name the selected exact model, have done=true and explicit
reason stop. Optional `thinking` must be absent or exactly an empty string; nonempty
text, whitespace, null, booleans and other malformed types fail closed. `<think>` or
`</think>` markers in response (case insensitive), empty/whitespace-only final response,
non-JSON, additional fields, truncation, token/telemetry/byte violations and malformed
labels also stop the run. Nothing is silently stripped or repaired. Hidden reasoning
consuming the output budget may manifest as truncation; do not raise limits merely to
force apparent success.

The unchanged independent validators still reject taxonomy-invalid labels. Safely
shaped unallowlisted paths remain explicit semantic quality failures/abstentions with
continuation; protocol/config/transport/identity/resource failures remain fail-fast.
Compatibility failure is not classification accuracy: inspect counts before scores.
All confidence is zero, all facts empty, all candidate proposals review-only and
never persisted. Reasoning, prompts, model responses and individual records are never
printed, logged or stored by the runner.

Actual Ollama 0.40.1 compatibility is **unverified by development/CI**. Even accepted
JSON without a thinking trace cannot prove the server honored the flag internally;
it establishes only observed request/output compatibility. Treat settings as requested
controls, not a claim about internal computation. If the local smoke fails, share only
aggregate counters/safe failure reason, stop, and investigate compatibility separately.
Do not try a full run, loosen validation, change limits, or add an unversioned chat mode.
A future endpoint-mode experiment would require explicit design/versioning for both
models and would be a different comparison.

## Model identity, versions and reporting

The selected tag is bound to the loaded client and request envelope. Lookup in /api/tags
requires exactly one matching installed tag with a full SHA-256 digest. Both tags may
be installed, but each run selects only one. Digest is verified before every request
and at final completion/abort; response model must match that selection. No automatic
switch is possible. The same final-unverified-identity count-only behavior is retained.
Optional /api/ps residency observes only the selected matching tag/digest.

Existing Qwen3 inference manifests remain exactly:

- four-label baseline: ollama-synthetic-e3;
- Flat-Domain: ollama-flat-domain-e1.

Qwen3.5 uses ollama-qwen35-flat-domain-e1 and local-model-comparison-v1. Its manifest
identifies the exact model/tag/digest and Ollama runtime, thinking_setting=false,
thinking_location=top-level and generation_endpoint=/api/generate, plus the same wire
schema, prompt/schema/options, projection/taxonomy/threshold/rules fingerprints.
Existing effective version hashing therefore separates model, artifact, runtime and
configuration without reusing Qwen3's definition. No analysis rows or registrations
are created. The top-level control is distinct from the unchanged options hash.

Reports retain the same aggregate fields for manual comparison: JSON/label validity,
model-invalid reasons, infrastructure/protocol counts, provider/domain decisive
coverage/accuracy, relevance/action error rates, false irrelevant, required-action misses
and false positives, incremental correct/wrong domain coverage where rules abstain,
review rate, wall/load/prompt/generation p50/p95/mean, token throughput and optional
residency. Unknown human labels are excluded from correct/wrong claims. Repeats stay
separate and do not increase unique-case denominators. See Phase 2N for exact rates.
`completed=true` means bounded completion, not all-valid output or useful predictions.

## Exact Windows PowerShell commands — manual after review/merge

Use the existing repository, Python environment, installed models and local service.
No database setup or model download is needed. First run the smoke commands only:

```powershell
# Existing Qwen3, five cases, Flat-Domain
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark --variant flat-domain --model qwen3:4b-instruct

# Candidate Qwen3.5, same five, explicit top-level think:false supplied internally
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark --variant flat-domain --model qwen3.5:4b-q4_K_M
```

Before attempting Qwen3.5 full, inspect its **aggregate-only** smoke: completed=true,
sent=valid=5, zero model-invalid/infrastructure/protocol failures, final identity
verified (a normal identified manifest, not the count-only unverified report). Review
requested thinking/endpoint/runtime manifest fields. If smoke is invalid, stop here.
The full command is an explicit operator choice; the runner has no persisted smoke
history or automatic full-run dispatch. Only after that gate passes:

```powershell
# Existing Qwen3 full, fixed 37 cases
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark --full --variant flat-domain --model qwen3:4b-instruct

# Candidate Qwen3.5 full, same fixed 37 cases
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark --full --variant flat-domain --model qwen3.5:4b-q4_K_M
```

A completed full run normally sends 34 and reports three intentional projector
failures. Optional --repeat-check has the same at-most-four-extra-request policy.
The old commands without --model remain unchanged. Ctrl+C stops safely; an accepted
server request can briefly continue, still token-bounded. No state is written.

Manually inspect `ollama ps` locally during/after smoke to check which selected model
is loaded and actual GPU allocation. Residency is sampled, not a continuous GPU
utilization proof. With 6 GB VRAM, keeping both models loaded may cause eviction or
CPU offload; do not assume both can remain resident. If necessary, the operator can
explicitly run `ollama stop qwen3:4b-instruct` or `ollama stop qwen3.5:4b-q4_K_M` between
experiments; the runner never does this. Use comparable warm/load/repeat conditions,
inspect load telemetry, and avoid attributing thermal/order effects to model quality.
Share only aggregate reports, not terminal reasoning traces or household data.

## Isolation, validation and remaining decisions

Transport still uses only numeric 127.0.0.1:11434, bypasses proxies, rejects redirects
and allows only GET /api/tags, GET /api/version, POST /api/generate and GET /api/ps.
No HTTP operation was added. No provider APIs/OAuth/keyring, production DB/services,
classifier changes, cloud, model installations, workers or task/canonical processing.
Only the original 37 checked-in synthetic fixtures pass through the same strict
metadata_only_v1 projection; expected labels/fake scripts stay on evaluation side.
Prompt/response/context/token/deadline bounds remain unchanged.

Automated tests mock the actual HTTP boundary and never connect to Ollama or load a
model. They cover the exact allowlist, client/request/response/digest binding, byte-
equivalent Qwen3 requests/manifests, matching Flat-Domain prompt/options, top-level
thinking placement/types, unsupported HTTP configuration, reasoning/empty JSON leaks,
strict envelope/resource validation, safe semantic failures, repeat accounting,
truth isolation and no expanded endpoint/production wiring. Added 63 tests to the
merged 1,640-test suite. Full SQLite: 1,703 passed; full PostgreSQL 16: 1,703 passed,
including the existing migration and concurrency tests. `pip check` and
`git diff --check` passed. No live Ollama benchmark was executed; automated comparison
results use mocked responses and are not model-quality or hardware measurements.

Qwen3.5 quality, speed and actual server compatibility remain unmeasured here. The
known 37-case set is not held-out, representative, training data or a production
acceptance test. Separate permission and broader disjoint evaluation are required
before household shadow inference; no predictions may create tasks/canonical records
or hide obligations as irrelevant/not_required. No cloud or real-metadata consent is
implied by installation, local GPU readiness or this PR.

ChatGPT review questions: Are Qwen3 request/identity semantics unchanged? Is candidate
thinking control top-level, strict and separately versioned without implying server
capability? Do reasoning/config failures stop safely without stripping/fallback or
incorrect accuracy attribution? Are model/digest binding and shared Flat-Domain
comparability preserved? Are manual smoke/full gates, GPU caveats, aggregate-only
privacy and future consent limitations explicit enough?
