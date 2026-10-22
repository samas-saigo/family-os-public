# Phase 2R — isolated development-only Action model benchmark

Issue #48 adds a separate, manual developer entrypoint:
`python -m family_os.action_model_benchmark`. It compares already-installed
`qwen3:4b-instruct` (default) and `qwen3.5:4b-q4_K_M` using the frozen Phase 2Q
**development** slice. This is an experiment harness, not a production analyzer,
classifier upgrade, task generator or household-data processing command.

No live model is executed during implementation or CI. Tests mock the actual HTTP
connection. No real household database, OAuth/keyring, provider API, cloud inference,
model downloads or output persistence is involved. Human operators may execute the
manual commands below only after review and merge, sharing aggregate JSON only.

## Fixed selection and holdout exclusion

Default smoke selects five predetermined development cases: a Gmail water-payment
request, an Outlook completed club renewal, Calendar vaccination confirmed and
tentative variants, and a generic Drive overview. Action truth mix is two required,
one not_required and two uncertain; all four providers are represented. Selection is
fixed before any model run and is not chosen based on scores.

`--full` explicitly selects all **60 development** cases (20 per action label;
18 Gmail, 18 Outlook, 12 Calendar, 12 Drive). There are 16 complete counterfactual
triads, 48 within-triad pairs and 12 standalone challenges. Smoke includes one pair
but no complete triad, so it is a setup gate rather than a quality estimate.

The existing Phase 2Q loader verifies the complete pinned manifest, rubric and both
files. The runner then filters development **before projection or prompt construction**.
A second canonical development projection pin prevents a relabeled holdout case
from being substituted at dispatch. The 30 holdout cases are never projected for
this benchmark, sent, scored or exposed in its report. There is no holdout flag,
repeat mode, arbitrary input file/stdin, URL/host, household, provider or prompt option.
The independent Phase 2Q offline rules holdout command remains unchanged; it does
not authorize model holdout inference here. A future Phase 2S requires a separately
reviewed issue before prompt experiments or a final holdout model evaluation.

## Reused model and privacy boundaries

Phase 2P's `LocalOllama`, payload builder, Flat-Domain taxonomy prompt/schema,
strict JSON parser, envelope and independent label validation are reused directly.
The old 37-case runner and its defaults remain unchanged.

- Numeric loopback `127.0.0.1:11434`, proxy-free, existing endpoint allowlist; no
  redirects, request retries, pulls, remote URLs or hidden fallback.
- Fixed Flat-Domain three-field JSON: relevance, action and domain_path. Valid paths
  map to existing taxonomy pairs; null maps to null/null. No coercion/correction.
- Unchanged temperature 0, seed 0, context 4,096, output cap 256; stream false,
  keep_alive 1m. Qwen3 payload is unchanged. Qwen3.5 requires top-level `think:false`;
  never `options.think` or stripping leaked reasoning.
- Existing 5s connect, 60s request, 600s total run budget; 3,072-byte prompt,
  32,768-byte request, 65,536-byte API envelope and 4,096-byte response caps.
- Projection is exactly `metadata_only_v1` / `synthetic-e1`. A model-facing helper
  takes only `MetadataProjection`, never a `SyntheticCase` or serialized AnalysisInput.
  IDs, split, expected labels, rationales, evidence refs and annotations stay strictly
  evaluation-side. Metadata values remain untrusted data, not instructions.
- Aggregate stdout contains no case IDs, subjects, synthetic addresses, inputs,
  per-case predictions, prompts, responses, reasoning, private paths or raw errors.
  Aggregated truth distributions and cue-type counters are evaluation results, not
  model inputs. The command does not log model/provider text or write result files.

Malformed JSON/protocol, extra fields, incomplete completion, reasoning leakage,
wrong model/digest, timeouts and resource failures abort without retry. A safely
parsed but semantically invalid label/path is rejected as an explicit model-quality
failure and the next development case runs, matching Phase 2P semantics. Such an
output never becomes a valid prediction, fallback abstention or corrected pair.
All accepted output confidences remain **zero**, facts empty, review recommended.
Nothing bypasses production analysis/provenance or creates canonical/task state.

## Identity and truthful partial runs

Each report binds a separate `action-development-e1` / `action-dev-metrics-v1`
identity to selected model/tag/digest and Ollama version; unchanged prompt/schema/
options/thinking and projection contract; taxonomy/threshold/rules versions and
hashes; frozen dataset/rubric/manifest/development input and annotated hashes;
selection and projected selection hashes; and uncalibrated-zero scoring policy.
Smoke/full and the two models have different effective version fingerprints.
Per-request model digest checks precede dispatch. A final check runs even after
an infrastructure abort. If final identity is unverifiable or changed, only safe
failure counts are returned: **no model-attributed manifest, metrics or performance**.
Optional residency failure yields null rather than replacing the primary failure.

Counters distinguish selected, attempted, projected, sent, validated envelopes,
JSON-valid, label-valid, semantic-invalid, infrastructure-failed and unattempted.
All canonical cases project successfully; a bad dataset/projection/preflight fails
before any HTTP request with no partial report. Projection-failed count is therefore
zero for accepted frozen runs; invalid fixture edits are not silently skipped.

A partial run is explicitly `partial_observed`, never a completed 60-case evaluation.
The rules baseline covers all selected cases; partial model metrics cover only observed
eligible responses, so they must not be compared as matched whole-corpus scores.

## Metric denominators

- Exact action confusion matrix uses the three truth labels × three predicted labels
  for **label-valid outputs only**. Cohort counts expose selected, evaluated, valid,
  invalid and not-evaluated records separately.
- Required recall = valid predicted required / attempted required cases with valid
  or semantic-invalid outputs. Misses include valid uncertainty/not_required and
  semantic-invalid required attempts. Infrastructure/projection/unattempted cases
  are not evaluated, and remain visible in cohort counters.
- Not-required false positives = valid required predictions on not_required truth;
  its rate uses valid not_required truth. Uncertain-to-concrete claims and preserved
  uncertainty use valid uncertain truth; rejected output is neither.
- Relevance/action accuracy uses decisive truth on valid outputs. False irrelevant,
  including the separate required-truth false-irrelevant count, remains explicit.
- Domain coverage on decisive truth uses classified valid predictions / known domain
  truth among valid outputs. Selective domain accuracy excludes abstained prediction
  and unknown human domain, using the existing Phase 2H evaluator. Overall domain
  abstention and classifier review rates describe valid outputs only. Observed-valid
  coverage and semantic validity expose rejected/unobserved cases alongside these
  conditional metrics. Classifier abstention, uncertain truth and invalid output are
  distinct states. Zero denominators are **null**, never invented 0%/100%.
- JSON validity = JSON-valid / validated envelopes; label validity = label-valid /
  validated envelopes. Envelope/transport failures are separate counters rather than
  successful JSON denominators. JSON validity is not semantic correctness.
- Provider breakdown repeats the same definitions; per-domain labeled/predicted/
  correct counts come from the reused evaluator.
- Triads report selected/scored/correct triads, distinct prediction triads, selected/
  scored/changed/correct pairs and breakdown by subject versus persisted status cue.
  All members/pair endpoints need valid outputs to be scored. Sensitivity (changing
  labels across a cue) is **not correctness**; a consistently wrong permutation can
  show perfect sensitivity and zero correct pairs.
- Wall latency includes failed dispatches. First and later request latency distributions
  are separate. Optional total/load/prompt/generation telemetry distributions retain
  missing values as missing. Tokens/sec uses only envelopes with nonmissing tokens
  and positive generation duration; absent telemetry yields null, not guessed speed.

No live Qwen accuracy, latency, token speed or GPU result is asserted by this PR.
Mocked comparisons prove accounting/validation, not model quality. The unchanged
rules development baseline abstains on all 60: required recall 0/20, misses 20/20,
zero not_required false positives/uncertain concrete claims, review 60/60. This is
abstention, not evidence of useful coverage or safe automation.

## Exact Windows PowerShell commands

Run from the user's existing repository and Python environment **after this PR is
reviewed and merged**. Do not install/download a model via these commands. Start the
already-installed local Ollama service normally. Run the two smoke gates before
committing time to full comparisons; do not run the models concurrently.

```powershell
git checkout main
git pull --ff-only

# Qwen3: five development cases, then explicit 60-case development run
.\.venv\Scripts\python.exe -m family_os.action_model_benchmark --model "qwen3:4b-instruct"
.\.venv\Scripts\python.exe -m family_os.action_model_benchmark --model "qwen3:4b-instruct" --full

# Qwen3.5: five development cases, then explicit 60-case development run
.\.venv\Scripts\python.exe -m family_os.action_model_benchmark --model "qwen3.5:4b-q4_K_M"
.\.venv\Scripts\python.exe -m family_os.action_model_benchmark --model "qwen3.5:4b-q4_K_M" --full

# Optional local observation while a model is loaded; do not infer placement from tag alone
ollama ps
```

Before each full run, require the corresponding smoke JSON to show completed=true,
final_model_identity_verified=true, selected=sent=valid=5, and zero model_invalid/
infrastructure_failed/not_attempted. Exit code zero means the run completed, **not**
that every prediction was label-valid or correct; inspect the counters. Abort or
invalid output is not permission to relax validation or tune prompts in this phase.

Ollama 0.40.1 may not honor Qwen3.5 Thinking/structured-JSON combinations reliably.
Unsupported thinking, reasoning text, missing/length completion or invalid final
JSON fails closed. Use a separately reviewed compatibility change if necessary.
`ollama ps` is a momentary residency observation, not proof of whole-run GPU placement.
Changing runtime/model digest produces a different report identity. Temperature/seed
controls do not establish hardware-independent deterministic inference. A 600s run
budget may abort a slow 60-case run; no automatic continuation/retries are added.

## Validation and review handoff

Python 3.12: **86 new tests**, **1,899 passed on SQLite** and **1,899 passed on
real PostgreSQL 16**. `pip check` and `git diff --check` passed. GitHub CI job
results/links are recorded in the PR description. Existing migrations/concurrency/provider regressions
remain in the full suite. New tests use only synthetic files and mocked HTTP; no
live benchmark has been executed. Existing isolation tests exempt only this named
developer runner from their no-import check, and its own AST allowlist checks both
Import and ImportFrom plus absence of any production wiring.

The compact English, balanced, correlated and fixed-date development corpus is
procedural and known, not blinded, representative household prevalence or production
quality. Its few irrelevant/uncertain relevance cases limit relevance conclusions.
Metadata cannot establish authenticity, hidden body/file facts or actual unpaid
state. No thresholds, production rules, labels, original fixtures, model settings,
prompts or inference consent boundaries are changed.

ChatGPT review questions:

1. Does selection and dispatch structurally exclude every holdout case, including
   relabeled substitutions, without an option to bypass the frozen files?
2. Are model requests byte-equivalent to Phase 2P for each selected model, without
   annotations, labels, IDs or split leaking into prompts or aggregate output?
3. Do strict protocol/security aborts and semantic-quality rejection preserve the
   existing independent parser and taxonomy rather than silently correcting results?
4. Do partial cohorts, invalid outputs, required misses and uncertainty counters
   expose coverage honestly without fabricated abstentions or misleading denominators?
5. Are cue sensitivity and triad correctness separate, with valid-member requirements?
6. Do final identity checks and configuration hashes prevent attribution to a changed
   or unverifiable model, even after an aborted request?
7. Are localhost-only/manual-only limits and the explicit future Phase 2S gate sufficient
   to keep holdout, household processing and production model adoption out of scope?
