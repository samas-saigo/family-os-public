# Phase 2M — manual localhost Ollama synthetic benchmark

Closes Issue #38. This implements a developer-only benchmark, not a production
classifier/model adapter. The installed model/hardware and single 0.79-second result
are user-reported context, not measurements made here. No live Ollama benchmark was
run during implementation; all automated HTTP tests are mocked.

## Manual use after review and merge

Use the existing repository and Python 3.12 environment on the user's Windows machine.
Ollama and `qwen3:4b-instruct` must already be installed and running; this tool never
starts a service or pulls/downloads a model. Update the repository normally after merge.
No database setup, migration, OAuth, keyring or source ingestion is required.
After merging the Issue #40 compatibility/accounting follow-up, update with
`git pull --ff-only` and rerun the same smoke command. Share only aggregate results.

**Smoke: five checked-in synthetic cases**, no extra arguments needed:

```powershell
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark
```

**Full: exactly the existing 37 synthetic cases**, explicitly requested:

```powershell
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark --full
```

Optional repeatability check: add `--repeat-check` to either command. It runs two
additional requests for each of the first two successful cases (three observations
per case total). Repeats never become additional unique evaluation records. Smoke is
at most 9 generation requests; a completed full run has 34 valid projections plus
at most 4 repeats. The three invalid projections are never sent.

Stop with **Ctrl+C**. The client closes its current connection and prints a safe
stopped message; no Family OS state is written. An already accepted Ollama request
may continue briefly server-side; the output token cap still applies. If desired,
run `ollama stop qwen3:4b-instruct` manually to unload the model. The tool never spawns
that command, changes models, restarts Ollama or resets ingestion cursors.

Expected stdout is one JSON aggregate report marked **SYNTHETIC / NOT PRODUCTION
ACCURACY**, or a fixed failure/stopped message. Only aggregate metrics, nonsecret model/
config digests and budgets are printed; no individual subject, sender, prompt,
response, reasoning, account identity or source record is exposed. Sharing aggregate
results is sufficient; no screenshots, fixture contents or household data are needed.
There is no implicit result/transcript file. The commands are instructions, not an
automatically executed benchmark on the user's machine.

## Transport, endpoint and identity

`ollama_synthetic_benchmark` is isolated from the `family-os` CLI, default analyzers,
provider/analysis/audit/review services, DB and production configuration. The runner
reads only the fixed checked-in Phase 2L fixture and existing tracked classification/
rules configs. It accepts `--full`, `--repeat-check` and an explicit allowlisted
`--variant` (default baseline) and an exact two-tag `--model` allowlist:
no arbitrary model, host, URL,
account, prompt, corpus path, database or stdin option.

Standard-library `HTTPConnection` connects directly to numeric **127.0.0.1:11434**.
Ambient HTTP/HTTPS/ALL_PROXY settings are not used, no hostname alternative is
resolved, and only GET `/api/tags`, GET `/api/version`, POST `/api/generate`, and
optional GET `/api/ps` are allowed. Any non-200 response, including a redirect, is
rejected without following Location, retrying or falling back. There is no `/api/pull`,
remote/model service, SDK, OAuth, credential or download operation.

Before generating, the exact installed `qwen3:4b-instruct` tag must exist once with a
full SHA-256 digest, and Ollama must report a bounded version identifier. Digest is
rechecked before every dispatch and at the end of every run, including aborted runs.
A detected change stops
processing; an end-of-run mismatch prevents publishing an apparently identified
comparison. When an aborted run's final identity changes or cannot be verified, only
safe aggregate failure/repeat counts are retained: model identity, definition, quality
metrics and performance are omitted, with `final_model_identity_unverified` reported.
Do not modify model tags during benchmarking. The Ollama generation API
returns the model name rather than an atomic artifact digest: checks bracket requests
but cannot prove an undetectable replace-and-restore between checks. No reproducibility
claim follows merely from temperature zero or repeated equal outputs.

## Projection, prompts, validation and budgets

Reuse unchanged Phase 2L `project_metadata`: exact local `metadata_only_v1` fields,
16 KiB projection bound, strict field types and lengths, canonical UTC timestamps,
no truncation, and the same defensive URL/credential-pattern checks. No full
AnalysisInput, IDs/owners/recipients, raw payload, arbitrary metadata or unavailable
content goes into a request. The fake script and synthetic expected labels are
retained only on the evaluation side; neither is part of the model prompt.

The system instructions include **every current taxonomy category and child** from
ClassificationPolicy, all relevance/action enums, null/null abstention, history/
cancellation and notification-versus-obligation guidance. Metadata is delimited as
untrusted JSON. No tools, external links, facts, reasoning text, actions or tasks are
requested. A complete Ollama JSON `format` schema constrains exactly four label keys;
category/child consistency remains independently checked, not assumed from decoding.
There is no silent plain-text fallback if the installed Ollama version rejects schema
format support. Report the failure and review compatibility separately.

Independent parsing rejects duplicate/extra/missing keys, invalid/non-JSON/trailing
text, invalid category/child/half-null pairs, malformed or oversized model envelopes,
non-string response, missing/non-`stop` completion reason, unrequested thinking text,
token-limit completion and invalid
telemetry. Valid four-label results are expanded with zero confidence and empty facts
and passed through unchanged Phase 2L `parse_response` and Phase 2F `validate_output`.
All proposals remain **0.0 uncalibrated strength and review-recommended**, not
calibrated probabilities or accepted tasks. No output is persisted.

Ollama 0.40.1's optional `prompt_eval_cached_count` is explicitly allowed only as an
actual integer in [0, 4,096]; booleans, null, negative/oversized values and other
types are rejected. It is validated but does not alter generation-token throughput
or the existing prompt-evaluation bound. All other unexpected envelope fields remain
rejected. The Issue #40 accounting/compatibility contract uses benchmark engine
`ollama-synthetic-e3`, changing the manifest and effective analyzer identity.

| Limit | Policy |
| --- | --- |
| Connect | <=5 seconds, further bounded by remaining session time |
| HTTP request | <=60 seconds after connect; a per-request socket watchdog interrupts blocking header/body reads |
| Entire run | 600-second monotonic budget; remaining time bounds every network operation |
| Serialized prompt | <=3,072 UTF-8 bytes, fail rather than truncate |
| Context / output | num_ctx=4,096 / num_predict=256; reject observed prompt eval count above 3,840 |
| Generation | temperature=0, seed=0, nonstreaming, serial, no retries |
| HTTP request / envelope | <=32 KiB / <=64 KiB |
| Model response | <=4 KiB |
| Keep-alive | 1 minute; no forced initial unload/load |

The prompt-byte cap leaves margin for output/chat framing under this model's context;
it is a conservative input bound, not a tokenizer benchmark. Server token telemetry
is checked where available; missing counts remain unknown. A request deadline uses
only a daemon timer to interrupt that one socket and is canceled/joined on exit; no
parallel inference, worker or scheduler is introduced. No long retry window is added.

The definition manifest identifies installed model name/digest, Ollama version,
benchmark/projection engine and schema, prompt/schema/options hashes, current taxonomy/
threshold fingerprints and rules fingerprint. The effective analyzer version hashes
the manifest into the existing length limit. Corpus digest separately identifies the
fixed synthetic set. Material config changes produce different identities; code changes
must bump the benchmark engine. This is reporting identity, not a persisted Analyzer
registration or a supported production adapter.

## Metrics, denominators and failure behavior

`counts` separates selected unique cases, attempted, projected, sent dispatch attempts,
valid, JSON-valid, failed, projection-failed, model-invalid, infrastructure-failed
and not-attempted. `failed = projection_failed + model_invalid + infrastructure_failed`.
A completed full run
normally attempts all 37 and projects/sends 34. Three existing malformed cases (URL,
oversized title, wrong-shaped metadata) are explicit failures, not corrected/skipped
out of the denominator. They are guardrail tests, not model quality evidence.

Projection failures continue to the next fixed fixture. A safely decoded exact
four-label object with bounded identifier strings (or domain nulls) that fails the
unchanged classification validation is a **model-quality failure**: increment
`model_invalid` and `failed`, retain an abstention, and continue without retrying.
This includes `home / insurance`, unsupported enum/category identifiers and half-null
pairs. No pair is corrected, coerced, copied from another case or accepted partially.
`home / home_insurance` remains valid; the taxonomy is unchanged.

A transport, identity, budget, envelope or malformed label protocol failure still
stops further requests with a fixed aggregate abort reason and nonzero exit.
`infrastructure_failed` includes these fail-fast protocol/security/resource failures;
it does not assert the failure was outside the model. Wrong field types, non-JSON,
duplicate/extra/missing keys and instruction-like/free-form label text do not qualify
for continuation. Primary fallback for failed/not-attempted cases is
uncertain/null-domain, review-only and **never persisted**. All selected cases remain
in aggregate denominators; `not_attempted` makes an incomplete run obvious. Do not
claim a full model-quality comparison from an aborted run. Missing service/model at
startup yields a safe message and no apparently successful benchmark.

`completed=true` means the bounded selected run finished without a fail-fast abort,
**not** that every prediction was valid. Exit 0 has that same completion meaning.
Inspect all failure/valid counters before interpreting quality. `json_validity_rate`
is syntactic JSON decoding success divided by primary sent attempts; model-invalid
JSON still counts as JSON-valid. `model_invalid_rate` and `label_validity_rate` also
use primary sent attempts, and zero denominators are null. Selected-case evaluation
keeps zero-confidence fallbacks in its denominators, visibly lowering coverage and
increasing missed-action counts. It is not an accuracy estimate for failed/unattempted
inferences; an aborted smoke cannot establish taxonomy-wide model accuracy.

Optional repeats follow the same semantic/protocol distinction, with separate
`model_invalid`/`infrastructure_failed` counts. Only valid repeated labels contribute
to disagreement counts; invalid repeats are explicit failures, not equal predictions.
There are still at most four repeats and no replacement requests or retries.

The existing JSON format schema enumerates categories and children independently and
therefore cannot enforce their relationship. Independent validation remains the
boundary; this patch measures invalid-pair rates honestly. A future `oneOf`/conditional
schema experiment must be separately versioned and compared rather than silently
hiding failures or changing the taxonomy.

The unchanged Phase 2H pure evaluator provides provider/domain coverage, abstention,
relevance/action exact correctness over decisive synthetic labels, category+child
selective correctness, review rate and concrete action-required false positives.
A separate missed-required count includes both uncertain and not_required predictions
against decisive required truth. Human unknown, classifier abstention and unlabeled
concepts remain distinct; zero denominators are null. Candidate confidence is always
zero, so concrete false-positive proposals are not confident accepted actions.
These synthetic labels are not read from a real label table or copied to another
analysis. Baseline rules and thresholds remain unchanged.

Performance aggregates include generation wall p50/p95/mean and sample count, first
request separately from later requests, Ollama total/load/prompt-eval/generation time,
observed generated tokens and total tokens divided by total generation seconds when
both counts/durations are available. Zero/missing timing denominators produce null.
Timing samples include valid envelopes even if labels are subsequently rejected;
repeats affect performance but not primary quality denominators. End-to-end metadata
identity checks are outside generation latency. No inference performance was measured
here; mocked timing fixtures validate formulas only.

The first request is not necessarily cold if the model was already loaded. Load
telemetry distinguishes observed load overhead without forcing eviction. Optional
`/api/ps` records matching digest's reported model size/VRAM fraction; unsupported or
missing observations are null. A sampled VRAM fraction does not prove continuous GPU
residency, GPU utilization or sustained thermal performance. Do not extrapolate the
user's one 0.79-second/65.9-token-per-second smoke to full taxonomy throughput.

## Tests, privacy and review gates

Automated tests mock the actual HTTP connection boundary, including model inventory,
generation, identity and telemetry. They require neither Ollama nor a model and cannot
escape to a real socket. Tests cover redirects/ambient proxies, malformed JSON/pairs,
timeouts/watchdog cleanup, budgets, missing/ambiguous/mismatched model, version changes,
no expected/scripted-label leakage, identity exclusion, bounded repeats, aggregation,
Ctrl+C and no DB/production wiring.

One existing Phase 2L isolation assertion now explicitly recognizes this separately
approved developer importer; it still rejects production imports. The original
projector, fake transport, parser, rules, schemas, services, review workflow and
fixtures are unchanged. No new dependency or workflow/service is added to CI.
Python 3.12 validation: **1,547 passed on SQLite and 1,547 passed on real
PostgreSQL 16**, including 107 mocked benchmark tests above the 1,440-test
merged baseline. `pip check` and `git diff --check` passed. GitHub's SQLite and
PostgreSQL jobs independently rerun these suites for the PR head.
Issue #40 adds 32 regressions over the merged 1,515 tests, including cached-count
bounds, the observed invalid pair followed by valid predictions, full-run denominators,
malformed protocol aborts and bounded repeat failure behavior. All network responses
are mocked; no real Ollama benchmark or household data was accessed here.

No real data is authorized: metadata can still contain sensitive text, pattern checks
are not complete secret detection, and local-model installation is not household data
consent. No external/cloud inference, provider APIs/scopes, financial data, content,
real model installation, source/analysis/label writes, canonical state, task/action,
API/UI or background sync is introduced. A future real-data shadow evaluation needs
separate explicit approval and stronger consent/access controls. Model performance,
quality and sustained runtime behavior remain unvalidated by a complete local run.
Issue #40 addresses the user's first synthetic smoke observations; manually rerun
the corrected benchmark after review/merge to assess compatibility and quality.

ChatGPT questions: Is the fixed numeric loopback/operation whitelist sufficiently
isolated from proxies, redirects, downloads and production state? Does taxonomy-complete
prompting plus independent four-field validation preserve abstention and zero-confidence
review? Are model identity, abort/denominator, bounded repeat and telemetry semantics
honest, especially incomplete runs and cold/GPU claims? Are manual-only commands and
real-data consent gates explicit enough to prevent accidental production use?

Phase 2N / Issue #42 adds a separately versioned opt-in domain-path experiment and
aggregate reason/incremental-coverage diagnostics. Baseline e3 inference is unchanged;
see [exact A/B commands, controls and denominators](phase-2n-review.md). The user has
now completed a baseline synthetic run; no live model was run during development.
Phase 2P adds explicit installed-model selection and a separately versioned Qwen3.5
Flat-Domain configuration; Qwen3 defaults remain unchanged. See
[Thinking compatibility and manual comparison gates](phase-2p-review.md).
