# Phase 2N — opt-in synthetic flat-domain A/B experiment

Issue #42 tests one hypothesis: does replacing independently constrained category and
child fields with one valid domain-path enum reduce taxonomy-invalid predictions?
This is a developer-only experiment, not a classifier switch, task generator, training
run or authorization to process household metadata. No real model was executed here.

## Observation and experimental control

The user reported a completed Phase 2M e3 run on the existing 37 synthetic cases:
34 sent, three projection failures, zero infrastructure failures, 21 label-valid and
13 model-invalid predictions. Rules/model relevance correctness was 15/18 vs 9/18;
action correctness 12/14 vs 3/14, required-action misses 2/6 vs 5/6, and model output
speed approximately 52.8 tokens/sec. These are user-run synthetic observations, not
measurements from this PR or representative production accuracy. The set is small,
partly unknown-labeled, already seen during development and not a disjoint holdout.

The default `baseline` retains Phase 2M e3's exact four-key wire schema, prompt,
instructions, taxonomy, input projection, request options, fixed corpus, validation,
continuation/fail-fast semantics and inference manifest identity. New aggregate
reporting fields do not change those predictions. Tests pin the baseline prompt and
schema digests and compare default/explicit-baseline outputs. No fixture/truth label,
production rule or threshold was edited.

`flat-domain` is explicitly opt-in and changes only domain representation and the
necessary prompt syntax: three keys rather than four, one exact `domain_path` rather
than independent category/child fields, and the list of complete paths rather than
the category-to-children object. Relevance/action instructions, historical/provenance
cautions, notification-versus-obligation guidance and uncertainty guidance are shared
verbatim. No examples, extra action heuristics or few-shot answers are added.

Both modes use qwen3:4b-instruct, temperature=0, seed=0, num_ctx=4096,
num_predict=256, stream=false and keep_alive=1m. They process the same five-case smoke
or full 37-case set serially, without retries. Optional bounded repeats use each mode's
same wire contract, and never inflate unique-case evaluation denominators.
Phase 2P additionally allows an explicit Qwen3.5 candidate with this same Flat-Domain
contract; see [separate thinking configuration and model identity](phase-2p-review.md).
Existing Qwen3 inference behavior and identities remain unchanged.

## Exact mapping and independent validation

The variant schema has exactly `relevance_label`, `domain_path`, `action_label`, no
extra fields, and an enum generated from **all** current `category/subcategory` pairs
plus JSON null. Reused child names remain distinct paths, e.g. household_admin/insurance,
vehicle/insurance and pet/insurance. home/home_insurance is valid; home/insurance is not.
The model is never offered independent category/child fields in this variant.

JSON is strictly decoded with byte, duplicate-key, shape and field-type checks.
A non-null path must be a bounded identifier/identifier string and exactly match the
policy-derived lookup table. There is no splitting an arbitrary path into an accepted
pair, trimming, casefolding, sibling selection, fuzzy matching or automatic repair.
JSON null maps to null/null. Half-null representations and baseline fields in a flat
response are not accepted. Malformed paths, additional slashes, URLs, unexpected fields
and protocol text stop the run. Safely shaped but unallowlisted paths are explicit
`invalid_domain_path` quality failures, with uncertain/null fallbacks and continuation.

Exact paths map to the original four-field representation, then reuse unchanged
`validate_output` and Phase 2L `parse_response` through the original labels validator.
The adapter does not trust Ollama's schema enforcement. All confidence is 0.0,
uncalibrated and review-only, facts are empty, and nothing is persisted. Unsupported
relevance/action labels also remain rejected rather than being turned into obligations
or used to discard records.

Baseline inference identity remains `ollama-synthetic-e3`. The opt-in manifest uses
`ollama-flat-domain-e1`, `wire_variant=flat-domain` and
`wire_schema=three-label-domain-path-v1`, plus different prompt/schema hashes. Model
artifact digest, runtime, taxonomy/threshold/rules/projection hashes and options remain
identified as before. Variant effective versions cannot reuse the baseline version.
Report diagnostics are separately labeled `domain-diagnostics-v1`; they describe
aggregate measurements, not a new production analyzer/persistence definition.

## Aggregate diagnostics and denominators

The existing counts, JSON/label validity, provider/domain metrics, false-positive
precision, missed required actions, review rates and timing denominators remain
comparable between user-run outputs. Added relevance/action error rates are
(decisive count - correct count) / decisive count; uncertain human labels are excluded,
while classifier abstention against a decisive label remains an error. Zero denominators
are null. `false_irrelevant_count` counts wrong concrete irrelevant predictions against
decisive human relevance only. Unknown truth is not assumed relevant or irrelevant.

Primary `failure_reasons` and separate `repeat_failure_reasons` contain only fixed,
content-free buckets:

- cross_taxonomy_pair: supported relevance/action, known category, known child from
  another category (baseline), rejected independently;
- incomplete_domain_pair: one null domain field (baseline);
- invalid_domain_path: bounded path not in the flat variant's exact enum;
- other_semantic: other safely shaped unsupported enum/category/child labels;
- protocol: malformed JSON, envelope or wire shape/field types, including token or
  telemetry contract violations;
- request_identity_or_resource: request failures, model identity/budget failures or
  remaining HTTP/resource rejections. This is a safe coarse diagnostic, not an
  assertion of the remote cause.

The first four buckets sum to `model_invalid`; the last two sum to
`infrastructure_failed`. Projection failures remain in their existing counter, not
model-invalid reasons. Multi-defect outputs receive one first-detected reason, never
multiple per-case failures. No raw label, path, case ID, subject, sender, prompt,
response or exception text is printed. Final identity failure retains only safe counts
and reason buckets, not attributed quality/performance or model identities.

`incremental_domain_coverage` considers only **unique selected cases where rules
abstain**. It separates human-decisive and human-unknown cases, classified versus
abstained model output, correct/wrong complete pairs and unknown-human classifications.
Correct/wrong require an exact category+child match to a decisive fixture label.
Unknown human labels contribute to neither. Rules-classified cases are excluded;
repeats do not count. `correct_coverage = correct / human_decisive` and
`selective_accuracy = correct / decisive_model_classified`, or null on zero denominator.
Failure/unattempted fallbacks remain abstentions, with failures separately visible.
These fields show whether extra coverage is supported or merely unsupported guesses.

`completed=true` and exit 0 mean the bounded run finished without a fail-fast abort,
not that every prediction is valid or correct. Invalid model predictions keep
zero-confidence abstentions in the selected-case evaluation denominator; the three
malformed fixtures remain projection failures. Do not interpret an incomplete run's
fallback correctness as actual model accuracy. Schema validity improvement alone does
not establish improved action/relevance understanding or useful added domain coverage.

## Manual PowerShell A/B commands — only after review and merge

Use the existing local Python 3.12 environment and already installed/running Ollama
model. These are instructions for a later explicit operator run, not automatically
executed commands. Do not run against household data, a database, custom file or prompt.
No service/model install or download is performed. From the repository root:

```powershell
# Baseline smoke (five); existing default is unchanged
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark

# Variant smoke (same five)
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark --variant flat-domain

# Baseline full (all 37; normally 34 sent, three projection failures)
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark --full

# Variant full (same 37)
.\.venv\Scripts\python.exe -m family_os.ollama_synthetic_benchmark --full --variant flat-domain
```

`--variant baseline` is equivalent to the default. Optionally append `--repeat-check`
to either mode; at most four extra generation requests, accounted separately.
Ctrl+C stops safely without persistence; an already accepted server request may briefly
continue, still token-capped. The runner never starts/stops a service or model.

Compare aggregate outputs manually from separately invoked runs. Check model digest,
Ollama version, corpus/options/taxonomy/threshold/rules/projection hashes for agreement;
check the deliberate prompt/schema/engine difference. Compare sent/valid counts and
reason buckets before quality, then decisive denominators, action misses/false positives,
false irrelevant, selective domain correctness and incremental coverage, followed by
latency/load/token telemetry. There is no report-file loader or cross-run private-data
input. Temperature/seed do not guarantee reproducibility; order, warm state, GPU heat
and tiny denominators limit inference. Run with the same repeat options if comparing.

## Privacy, budgets, validation and future gates

Unchanged transport is numeric 127.0.0.1:11434, fixed model, no ambient proxies,
redirect following, remote fallback, pulls, provider APIs, OAuth/keyring, DB access,
production CLI/default wiring, actions or downstream state. Only the checked-in 37
synthetic inputs are used, through the exact Phase 2L projection. Expected labels and
fake scripts remain evaluation-side only. Outputs are aggregate-only and marked
SYNTHETIC / NOT PRODUCTION ACCURACY. No transcripts or implicit files are written.

Existing 5s connect / 60s request / 600s run budgets, 3,072 prompt bytes, 4,096 context,
256 output tokens, 32 KiB request, 64 KiB envelope and 4 KiB response bounds remain.
All 34 currently projectable fixtures fit: baseline maximum 1,661 prompt bytes;
flat-domain maximum 1,941 bytes, computed offline without a model. If a future policy
or input exceeds a bound, fail safely; do not silently truncate or increase limits.
Prompt bytes are not exact tokenizer/context-use guarantees. Identity is still checked
before every dispatch and at final completion or abort.

Automated tests mock the actual HTTP interface and require neither Ollama nor a model.
They cover every valid path, independent validation/null mapping, illegal paths,
half-null/tampered responses, baseline hashes/identity, unchanged instructions/options,
reason counters, decisive-only coverage/error metrics, unknown labels, repeat bounds,
truth/script/identity exclusion, argument gating and unchanged privacy/resource guards.
Python 3.12 validation: **1,640 passed on SQLite and 1,640 passed on real
PostgreSQL 16**, including 93 new regressions above the 1,547-test merged baseline.
`pip check` and `git diff --check` passed. GitHub CI independently runs both full
suites for this PR head. No local live benchmark or model quality measurements
were produced during implementation.

Next decisions require local synthetic A/B results, broader disjoint synthetic holdout
and separately approved local real-data shadow evaluation. Improvements here do not
permit household inference, trusting irrelevant/not_required to hide obligations,
canonical entities, tasks, content expansion or cloud egress.

ChatGPT review questions: Is domain representation the only inference variable changed?
Does exact enum lookup plus unchanged independent validation prevent invalid pairs
without repairs? Are identity/report versions honest and baseline e3 unchanged? Do
reason buckets and incremental correct/wrong coverage use decisive truth without
unknown-label assumptions or duplicate counting? Are all bounds/privacy/consent gates
preserved, and are modest synthetic conclusions distinguished from product quality?
