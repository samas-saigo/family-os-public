# Phase 2S — controlled Qwen3 development-only prompt experiments

Issue #50 studies three prompt hypotheses against a frozen Qwen3 control. This is
manual developer experimentation on synthetic development metadata only, not model
adoption, production classification, tasks, canonical state or household processing.

## Pre-registered plan: qwen3-prompt-plan-v1

Registered before any live experiment. Model: `qwen3:4b-instruct` only, same
Flat-Domain taxonomy/schema/options and frozen 60-case development set. Baseline is
the exact Phase 2R prompt. Each candidate adds only one independent clarification;
no stacking, fixture-specific examples, gold labels, answer distributions or ad hoc
corrections. Literal additions and SHA-256 identities are version-controlled.

| Variant | Hypothesis | Edit boundary |
| --- | --- | --- |
| baseline | Frozen control | No prompt edit |
| relevance-clarified | Household relevance is confused with urgency/action status | Only relevance clarification: household information may remain relevant after payment/cancellation or without a current step |
| action-evidence | Outstanding steps are mistaken for informational/cleared items | Only action clarification: explicit outstanding step vs explicit completion vs genuinely missing status; no keyword-only obligations or inferred completion |
| calendar-status | Visible status is ignored or used as a global veto | Only Calendar clarification: evaluate visible status with conditional instructions; preparation, cancellation-specific clearance, explicit refund/rebooking and tentative uncertainty |

Primary trade-offs: increase true-required recall and reduce false irrelevant,
including required truth falsely irrelevant, without new false required on
not_required/uncertain truth or collapse of honest uncertainty. Also inspect required
→ not_required versus required → uncertain, provider/status cohorts, relevance and
domain coverage/accuracy regressions, triad correctness and latency. Do not optimize
for overall action accuracy alone. No numeric success target or automatic winner.
Negative/inconclusive results are valid. A promising result requires human review
before further tuning; Phase 2T final holdout testing is a separate approval/issue.

The development set is small, English-only, largely templated and triad-correlated,
balanced in action and overwhelmingly relevant. Diagnostics describe patterns, not
proven root causes, calibrated probabilities, household prevalence or production
accuracy. Public holdout is procedural, not blinded. It is off-limits to model
inference, error analysis, prompt development, scoring or model selection here.

## Implementation and privacy boundary

Separate entrypoint: `python -m family_os.qwen3_prompt_experiment`. Default is
baseline five-case smoke. `--variant` accepts exactly the four names above; `--full`
explicitly selects all 60 development cases. `--model` accepts only the original
Qwen3 tag, not Qwen3.5, aliases, arbitrary prompts/paths/hosts/URLs or a holdout flag.
One invocation runs one variant, without automatic comparison, retries or winner
selection. The Phase 2R runner, including Qwen3.5 support and historical reports,
and the Phase 2P 37-case benchmark are unchanged.

Reuse boundaries:

- Phase 2Q validates the pinned whole corpus/rubric internally. Only integrity
  validation reads holdout; it never enters experiment projection, prompts, diagnostics,
  scoring or error analysis. Phase 2R development filtering/projection pins and fixed
  five-case selection are reused. No holdout mode exists in this entrypoint.
- Only approved frozen `MetadataProjection` reaches the builder. Whole SyntheticCase,
  AnalysisInput, IDs, expected labels, rationales, annotations and split are excluded.
  No synthetic fixture text or answer table is included in any prompt addition.
- Original Flat-Domain prompt/schema/taxonomy and payload builder provide the frozen
  base; exactly one named literal is appended before the untrusted metadata delimiter.
  Baseline payload bytes are identical to Phase 2R for every development case.
- Same proxy-free numeric `127.0.0.1:11434`, LocalOllama endpoint/identity checks and
  strict JSON/envelope/independent taxonomy validator. No new transport or parser.
  Existing 5s connect, 60s request, 600s run, 3,072-byte prompt, 32,768-byte request,
  65,536-byte API response and 4,096-byte final response limits remain unchanged.
- Same temperature=0, seed=0, num_ctx=4096, num_predict=256, keep_alive=1m,
  stream=false and original Qwen3 Thinking behavior (no new think option).
  No context/output-budget expansion, taxonomy truncation or hidden fallback.
- All selected prompts are preflighted before any HTTP. Changed unpinned literals or
  oversized prompts fail before model lookup. Accepted output confidence stays zero,
  facts empty and review recommended. Nothing is persisted or applied downstream.
- Protocol/security/identity/resource errors abort without retries; safe semantic-invalid
  labels remain explicit rejected quality outcomes, never corrected or replaced by
  fabricated abstentions. Final identity is checked even after abort; unverified final
  identity suppresses model-attributed manifest/metrics/diagnostics/performance.

No real household data, database, provider, keyring, OAuth, model downloads, external
AI, cloud endpoints, production services or scheduling. Reports contain aggregates,
configuration hashes and safe model identifiers only: no subjects, senders, prompts,
raw model responses/reasoning, per-case IDs/predictions or private paths/errors.
The command writes no output files. Only aggregate JSON may be shared for review.

## Frozen prompt identities and reproducibility

Experiment engine `qwen3-prompt-experiment-e1`; diagnostics
`qwen3-prompt-diagnostics-v1`; plan `qwen3-prompt-plan-v1` (canonical SHA-256
`faea760e148ce40ef669a28fae74682371ac89587004dbd537fdda9725a89ae2`).

| Variant | Effective system-prompt SHA-256 | Maximum complete development prompt bytes |
| --- | --- | ---: |
| baseline | ce795381831bceed14df9ca29a30135d0b1293d1060e6a510208925bf5fac14e | 2059 |
| relevance-clarified | ffa86c21d6993fe79afad31a9dec569ea5e405996c2cd6f3eb30a7402061d2e7 | 2358 |
| action-evidence | 17b9ebaba795938a405652993950ea983c45938b1fbebd53aea1b717a2a6f0d8 | 2454 |
| calendar-status | 9a6f3a95e18cc90f0587f41a79070db986e287141697b4f129b94cef2d20873c | 2471 |

Hashes use the existing canonical-JSON SHA-256 function, including canonical JSON
string encoding for prompt/edit text (not an unquoted raw-text hash). System-prompt
identity excludes each case input, which is bound separately by projection hashes.
Source pins both edit and effective prompt hashes. Reports fingerprint variant/plan,
model digest/runtime, schema/options/thinking, taxonomy/threshold/rules, rubric and
frozen corpus/development input/annotation/projection and selected-case identities.
New prompt content requires an explicit reviewed version/pin change; accidental
literal edits fail preflight. There is no CLI override for hashes, prompts or budgets.
No live token/context or GPU claim follows from byte-budget checks.

Repeat the same command manually if needed; no automatic additional requests are
hidden in a reproducibility flag. Pure `check_reproducibility(first, second)` accepts
only complete verified label-valid same-configuration experiment reports and returns
aggregate metrics/diagnostics equality. Equality **does not establish per-case
prediction determinism**. Seed/temperature alone do not guarantee repeatability
across hardware/Ollama/model replacements. Latency includes loading/residency effects;
optional `ollama ps` is only a momentary observation, not whole-run GPU proof.

## Diagnostics, comparison and honest denominators

Phase 2R metrics remain intact: exact three-label confusion, valid/invalid/not-evaluated
truth cohorts, required recall/misses, false required, uncertain-to-concrete, relevance/
false irrelevant, domain selective accuracy/coverage, provider/domain breakdown,
abstention/review and triad/pair counts. Partial and invalid outputs retain their
original status; no fallback predictions enter a confusion matrix.

Additional diagnostics are aggregate development counts:

- Required truth → not_required and → uncertain, each with valid-required denominator.
  Semantic-invalid required attempts count as misses in Phase 2R recall, but are
  neither concrete clearance nor genuine uncertainty in these rates.
- Predicted relevance × predicted action; the same cross-table restricted to required
  truth. Predicted required + irrelevant is distinct from required truth falsely
  irrelevant. These expose disagreement patterns, not proof of a causal mechanism.
- Uncertain truth → required with valid-uncertain denominator, separate from → any
  concrete prediction. Honest uncertainty must not disappear from reports.
- Known-domain valid truth: abstained, wrong concrete and unknown human-domain counts
  remain separate. Undercoverage here is abstention / known truth among valid outputs,
  not wrong classification. Domain selective accuracy remains conditional on coverage.
- Provider, Calendar status (confirmed/cancelled/tentative/missing) and cue-family
  (subject/status/standalone) cohorts repeat confusion/coverage/triad diagnostics.
  Development Calendar status has three cases each for these four strata; controlled
  cue cohorts contain 39 subject, nine status and 12 standalone cases. They are small.
- Triad/pair correctness remains separate from changed/distinct predictions. Mere
  sensitivity to a status cue can be consistently wrong. A triad split by status
  cannot itself be scored in that status-only cohort; whole-corpus triads remain intact.

Zero denominators are null. Infrastructure/unattempted cases are visibly unevaluated;
JSON/label validity denominators and latency/throughput reuse Phase 2R conventions.
Compare full runs only after examining validity and complete cohort counts, not
just a favorable conditional accuracy number.

Pure `compare_reports(baseline, candidate)` performs no inference or file access.
It accepts only complete final-identity-verified, all-label-valid Phase 2S reports
with exact matching corpus/selection/model/runtime/schema/options/plan/configuration
identities; the reference must be baseline. No Phase 2R historical numbers are
silently imported. It returns a trade-off table and denominator counts, with no
winner. Invalid, partial, different-model/runtime/scope or tampered references fail
closed. Domain selective accuracy deltas are null when selective denominators differ;
absolute values and coverage counts remain visible. Other deltas require matched
valid truth cohorts. Reports are aggregate integrity checks, not cryptographic
attestation against fabricated reports. Manual comparisons can be sent to ChatGPT
as aggregate JSON; this harness has no input-file/reference CLI option.

The Issue #50 baseline findings motivate the hypotheses; they are not new results
from this PR and are not hardcoded reference scores. No live experiments are run
here. Negative/inconclusive results and safety regressions must be reported alongside
any gain; never silently choose only a favorable variant or collapse required misses
into overall accuracy.

## Exact Windows PowerShell commands after reviewed merge

Run from the existing repository/environment with the already-installed local
Ollama service and Qwen3 model. No installation/download or real-data setup is
required/authorized. Run one command at a time. Before each full run, its smoke must
report completed=true, final identity verified, selected=sent=valid=5, zero invalid/
infrastructure/unattempted cases. Exit code zero means completed, not correct.

```powershell
git checkout main
git pull --ff-only

# Frozen control: five-case smoke, then 60 development cases
.\.venv\Scripts\python.exe -m family_os.qwen3_prompt_experiment --variant baseline
.\.venv\Scripts\python.exe -m family_os.qwen3_prompt_experiment --variant baseline --full

# Independent relevance hypothesis
.\.venv\Scripts\python.exe -m family_os.qwen3_prompt_experiment --variant relevance-clarified
.\.venv\Scripts\python.exe -m family_os.qwen3_prompt_experiment --variant relevance-clarified --full

# Independent action-evidence hypothesis
.\.venv\Scripts\python.exe -m family_os.qwen3_prompt_experiment --variant action-evidence
.\.venv\Scripts\python.exe -m family_os.qwen3_prompt_experiment --variant action-evidence --full

# Independent Calendar-status hypothesis
.\.venv\Scripts\python.exe -m family_os.qwen3_prompt_experiment --variant calendar-status
.\.venv\Scripts\python.exe -m family_os.qwen3_prompt_experiment --variant calendar-status --full

# Optional local observation while loaded; not a benchmark or model download
ollama ps
```

Only Qwen3 is supported here; optional explicit `--model "qwen3:4b-instruct"` leaves
requests unchanged. If any smoke has rejected output, reasoning leakage, missing/
length completion, identity discrepancy, timeout or protocol failure, stop before
full runs and request review. Do not weaken validation, increase budgets or tune
against held-out labels. A 600s full-run timeout remains an explicit infrastructure
abort, never apparent poor accuracy from fabricated predictions.

Share all four full aggregate reports, including misses, false irrelevant, false
required on not_required/uncertain, uncertainty, provider/status and domain results,
validity and latency. Do not share prompts, responses or individual fixture records.
A material recall gain with worse false-required/uncertainty or false-irrelevant
behavior blocks progression until reviewed. Negative/inconclusive experiments are
acceptable. Stop and obtain human review before any further edits/tuning, production
shadow use, model adoption or separately proposed Phase 2T final holdout test.

## Validation and ChatGPT review

Python 3.12: **98 new tests**, **1,997 passed on SQLite** and **1,997 passed on
real PostgreSQL 16**, including existing migrations/concurrency/provider regressions.
`pip check` and `git diff --check` passed. CI job links/results are in the PR description.
All new tests use synthetic fixtures and mocked HTTP; no live Ollama is executed.
The only existing test change adds this named experiment to Phase 2R's isolation
exemption. The experiment has its own strict AST checks for both import forms and
production-wiring guard. No production-runtime/schema/provider/classifier/fixture changes.

Review questions:

1. Is baseline request serialization identical to Phase 2R for all 60 development
   inputs, and is each addition isolated, generic and within unchanged budgets?
2. Do relevance, outstanding-step and conditional Calendar hypotheses match the
   pre-registered trade-offs without relying on fixture answers or hidden content?
3. Does only development reach projection/dispatch/diagnostics, with holdout limited
   to existing internal integrity verification?
4. Are dangerous required→not_required, false irrelevant and uncertain→required
   separated from misses/abstention/invalid results with honest null denominators?
5. Do reference identity/cohort checks prevent misleading deltas, and do changed
   selective-domain denominators remain visible rather than produce false improvement?
6. Do digest/deadline/protocol failures preserve aggregate failure counts while
   preventing attribution to an unverified model, including aborted runs?
7. Are aggregate repeatability claims appropriately weaker than per-case determinism,
   with no automatic winner, tuning, holdout evaluation or downstream state changes?
