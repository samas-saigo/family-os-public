# Phase 2T — paired synthetic diagnosis and classification architecture decision

Issue #52 is an evidence/architecture checkpoint plus an isolated manual paired
comparator. **No production model, policy switch, task, hiding/clearing rule, canonical
record or real-household inference is approved.** The deterministic production
pipeline, scopes, synchronization, source/analysis provenance and human labels remain
unchanged. This decision preserves one backend/core with multiple presentation clients.

## What Phase 2S established, and what it did not

The following is **reported manual evidence from Issue #52**, not a new run performed
for this PR. All four Qwen3 runs used Ollama 0.40.2, the same pinned 60-case synthetic
development set, prompts/schema/options, and verified model identity. Each completed
with 60/60 valid predictions and no infrastructure/projection/model failures. No
holdout was inferred. Valid JSON/taxonomy is not evidence of correct classification.

| Development measure | baseline | relevance-clarified | action-evidence | calendar-status |
| --- | ---: | ---: | ---: | ---: |
| Required recall | 7/20 | 4/20 | 6/20 | 13/20 |
| Required missed | 13 | 16 | 14 | 7 |
| Required → not_required | 3 | 9 | 0 | 4 |
| Required → uncertain | 10 | 7 | 14 | 3 |
| Uncertain truth preserved | 16/20 | 15/20 | 20/20 | 17/20 |
| False irrelevant | 16 | 2 | 20 | 22 |
| Required truth falsely irrelevant | 4 | 0 | 5 | 5 |
| Decisive action correct | 17/40 | 17/40 | 11/40 | 31/40 |
| Decisive relevance correct | 41/58 | 32/58 | 38/58 | 36/58 |
| Selective domain correct | 35/58 | 36/58 | 35/58 | 38/58 |
| Complete counterfactual triads correct | 1/16 | 2/16 | 2/16 | 8/16 |
| Calendar Required recall | 0/4 | 0/4 | 0/4 | 0/4 |

Trade-offs: relevance clarification reduces concrete false irrelevant decisions but
loses Required recall, increases explicit mistaken clearance and reduces overall
relevance correctness; movement to uncertainty is not equivalent to correct relevance.
Action-evidence avoids Required→not_required and preserves all uncertain truth, but
leaves 14 Required cases uncertain and increases false irrelevant. Calendar-status
improves overall recall/action/domain/triad correctness, while increasing false
irrelevant and retaining four dangerous Required→not_required errors. It is **not a
production-ready winner**. No prompt is automatically selected, stacked or applied.

The uncertainty-preservation counts imply 4/5/0/3 concrete assertions on uncertain
truth, respectively, but do **not** establish which were required versus not_required
without the actual predictions. The issue does not provide all not_required→required
cohorts: these remain unestablished here rather than invented as zero. Net recall
improvement is not a count of recovered cases: repairs and newly introduced mistakes
can coexist with identical marginal scores. Existing aggregate reports cannot identify
which cases changed, which errors persisted, or the causal mechanism behind a prompt.

The set is English-only, small, templated/triad-correlated, action-balanced and mostly
relevant (56/60). It measures descriptive synthetic differences, not household
prevalence, significance, population estimates, calibrated confidence or authenticity.
The public 30-case holdout is procedural, not blinded; its labels are not inspected
for this decision, error analysis or tuning. Existing integrity-only verification is
permitted. No live Ollama is executed during implementation/review/CI.

## Calendar failure analysis and remaining uncertainty

Reported calendar-status results: confirmed Required 0/3; cancelled not_required 3/3;
tentative uncertain 3/3. Across the full Calendar cohort Required is 0/4, including
the remaining Required example without a visible status. Status pairs changed
predictions in 6/9 comparisons, but only 3/9 pairs and 0/3 full status triads were
correct. Merely reacting to status is different from understanding the conditional
instruction. The overall triad gain is outside these Calendar status triads; it cannot
be described as Calendar recovery.

These observations are consistent with incomplete handling of conditional preparation
or outstanding steps, and possibly topic/status shortcuts. They do not prove a specific
internal reasoning failure, which exact wrong labels changed, or what unavailable body/
account context would reveal. No chain-of-thought is requested or stored to explain it.
Paired subject/status cohorts can localize observed error patterns after a reviewed
manual rerun; they cannot establish model causality. Those results are **not yet known**.

Status interpretation must remain contextual:

- confirmed is neither proof that no work remains nor proof of an obligation; visible
  preparation/attendance instructions can support a suggestion requiring confirmation;
- cancelled can clear only a particular event-specific request, while visible refund/
  rebooking steps can remain outstanding; it is not a global no-action veto;
- tentative can involve an explicit decision or leave applicability unresolved;
- missing status, age, generic titles, silence and missing bodies cannot establish
  completion. Absence of explicit supported evidence must not become not_required.

## Paired comparator: actual predictions, in memory only

`python -m family_os.paired_synthetic_diagnosis` is a separate manual developer tool.
It collects all four **unchanged** Phase 2S variants in fixed variant-major order on
one fixed, aligned development selection. Five unique smoke cases means **20 generation requests**;
`--full` means 60 unique development cases and **240 generation requests**. Identity/version
verification adds bounded control HTTP requests within the same deadline. No single-case records
or predictions are returned by the CLI, written to files, or logged. The old Phase
2R/2S commands, reports, prompt hashes and Qwen3.5 support are unchanged.

The existing Phase 2Q loader validates frozen integrity internally; Phase 2R selects
and pins development before projection. Only approved MetadataProjection reaches the
unchanged Phase 2S builders. Expected labels/rationales/evidence/IDs/splits never enter
model payloads. All four variants are preflighted before **any** HTTP; no arbitrary
model, host, prompt, input file/stdin, household, account, holdout or variant option.
The sole scope option is `--full`.

Transport remains fixed proxy-free 127.0.0.1:11434 with exact Qwen3 tag, unchanged
Flat-Domain taxonomy/schema/options and strict envelopes/parser/output validation.
No retries, redirects, cloud, downloads, provider API, OAuth/keyring, database, workers
or real source data. All confidence stays zero, facts empty and suggestions review-only.
Irrelevant never erases a Required/Uncertain observation in these diagnostic counts.

All four runs share **one 600-second global deadline** (not four multiplied budgets),
existing 5s connect/60s request limits and unchanged prompt/request/response/token caps.
This intentionally conservative bound may abort a slow full comparison; it is not
permission to silently extend budgets or resume from saved predictions. Only the fixed
new manual command launches the requests, after reviewed merge. No launch in this PR.

Identity includes model digest/Ollama version, each pinned prompt/edit, plan, schema,
options/thinking, taxonomy/threshold/rules and corpus/rubric/development/selection
fingerprints, schedule and metrics version. Model digest is checked before each
request, runtime at variant boundaries, and both at finalization even after abort.
Observed swaps remain disqualifying even if identity is later restored. Incompatible
identities fail closed with an explicit warning and safe counts only, **no attributed
metrics/comparisons/performance**. This is observed API identity, not cryptographic
attestation or proof against an unseen restart/model nondeterminism.

### Predefined aggregate report and denominators

Each variant retains Phase 2R metrics and Phase 2S diagnostics, plus validity/failure
counts and latency/throughput. Semantic-invalid labels are rejected quality outcomes
and do not become model abstention. Protocol/security/resource failures stop later
requests; successful prior pairs can remain observable only with verified identity.
Partial reports say partial_observed, never a complete four-way study.

Baseline-to-each-candidate comparisons use actual same-position validated predictions:

- selected, paired-valid and unpaired counts/coverage, plus the full status-transition
  matrix (valid, semantic-invalid, infrastructure-failed, projection-failed, unattempted);
- predicted action/relevance transition matrices; recovery/new-miss counts on Required
  truth, distinguishing recovery from not_required/uncertain and newly introduced
  mistaken clearance versus uncertainty. Recovery rate divides by baseline misses
  **within valid pairs**; new-miss rate by baseline correct within valid pairs.
  Separate relevance-transition matrices for recovered Required and newly missed
  Required retain joint action/relevance attribution instead of inferring it from marginals;
- false irrelevant transitions require decisive relevant truth. "No" means not
  established false irrelevant, not guaranteed correct; uncertain human relevance
  remains separately stratified. Required recovery with candidate irrelevant is
  reported, not counted as permission to hide or execute anything;
- truth-uncertain transitions distinguish preserved uncertainty, newly concrete,
  regained uncertainty and concrete in both; new required/not_required are separate;
- known/unknown domain truth, regained/lost correctness and abstention are separate;
- provider, truth-action, truth-relevance, Calendar status (including missing) and cue
  family (subject/status/standalone) strata expose denominators without case IDs;
- complete-triad correctness transitions and pair correctness transitions require
  valid predictions for all endpoints in both variants. Pair sensitivity transitions
  are a separate matrix: consistently wrong permutations can have perfect sensitivity.
  Subject versus status triads remain distinguishable. A truth/status stratum may
  split a triad and therefore has no complete-triad denominator.

Zero denominators are null. Cases invalid/unattempted in either variant contribute
only to status/coverage counters, never fabricated uncertainty or pairwise repair.
The warning/coverage must accompany any partial comparisons. Earlier Phase 2S
summaries are context only and are never converted to paired data or reference scores.
A new paired run may differ from the old manual scores due to order/loading/runtime
and nondeterminism; do not present its transitions as reconstruction of old runs.
All outputs are aggregate synthetic descriptive statistics. No per-case export.

## Architecture alternatives and decision

| Option | Benefit | Main risk / review workload | Decision |
| --- | --- | --- | --- |
| Current joint relevance/action/domain pass | Simple, one call and existing versioned output | Cross-dimension coupling; concrete irrelevant can conceal an outstanding step if misused; observed misses and inconsistent status handling | Retain as experiment control; not production model |
| Independent relevance and action, domain as separate topic proposal | Clear dimension contracts, separate evaluation and abstention; no urgency-to-relevance shortcut | Extra calls/latency/maintenance and disagreement review; independence is not automatic accuracy | Recommended architectural direction, not implemented or approved for real data |
| Conservative deterministic Calendar evidence/status interpreter | Auditable visible-condition handling, zero egress and bounded cost | Brittle language/condition support, false alerts from keywords, missed implicit obligations and more abstention | Next isolated synthetic experiment, with human confirmation and measured workload |
| Optional gated local model suggestion after deterministic abstention | Could offer review context on unsupported evidence | Uncalibrated/model-dependent errors, duplicate review and latency; locality does not authorize real metadata inference | Future separate decision, synthetic only until explicitly authorized |
| Simple metadata indicators for high-priority inspection | Cheap, transparent detection of explicit outstanding-step cues | Keywords/status alone over-alert; priority is not proof and may overload review | Compare as baseline in the next synthetic Calendar-only experiment |

Recommendation: separate dimension decisions conceptually, with domain remaining a
versioned topic inference, never a permission/action signal. Retain exact source/raw
snapshot, input fingerprint, immutable analyzer/config identity, stale-input handling
and append-only evaluation labels if any future approved branch uses application
services. Core policy stays UI/CLI independent and backend-owned; no backend/API,
authentication, new reviewer identity or worker is added here.

Explicit consistency/audit rules for a future proposal:

1. Relevant does not imply required; irrelevant does not clear/hide Required or Uncertain.
   Conflicting concrete suggestions trigger inspection, not silent suppression.
2. Domain classification never determines obligation/clearance by itself. Missing or
   ambiguous observable evidence remains uncertain with review.
3. Deterministic Calendar suggestions cite bounded persisted evidence paths and the
   supported condition; status alone is insufficient. A model cannot override a
   contradictory or unsupported condition into automatic clearance/execution.
4. Suggestions, indicators and evaluation priority are not canonical facts, Needs Action,
   tasks, product review_queue or action authority. Human confirmation is mandatory;
   future action execution still uses centralized R0–R3 policy separately.
5. No real household metadata goes to any AI, local or external, under this issue.
   Provider OAuth, installed Ollama and valid JSON are not model consent. Any future
   real-data/content boundary needs separate explicit authorization/security design.

## One narrow, reversible next experiment (proposal only)

Propose a **synthetic-only Calendar action-evidence interpreter** in a separately
approved issue: pure metadata-only action suggestion, no model dependency or production
wiring. Compare it with simple indicator-only high-priority inspection and frozen
joint-model evidence where available; do not add another prompt/model experiment,
independent multi-model pipeline or household shadow rollout simultaneously.

Pre-register supported visible conditions and failure/abstention rules. Use the current
12 development Calendar cases plus separately reviewed new synthetic guardrails if
needed, without editing frozen fixtures or inspecting holdout. Generic meetings,
confirmed-only, cancelled-only, tentative-only, missing status, negation, completed
steps and explicit refund/rebooking counterexamples must not yield invented obligation
or clearance. Explicit preparation with a met condition and direct outstanding steps
must be evaluated as targeted positive controls, not guessed from labels/status.

Testable acceptance: exact deterministic results/evidence refs for supported cases;
zero unsupported status/keyword-only concrete decisions in guardrails; uncertainty on
missing/contradictory conditions; measure all four known Calendar Required cases,
false required on not_required/uncertain, mistaken clearance, abstention and resulting
review count/workload. Publish confusion/cohort denominators and false alerts, not
only recall. Prove Required/Uncertain cannot be dropped by relevance, no side effects,
network, schema or live-data access, and easy disabling/removal of the isolated branch.
Model confidence remains uncalibrated/zero; there is no automatic application.

Blockers before progression: paired identity/coverage invalid; unsupported clearance
or obligation; recall gain with new false alerts/false irrelevant; unmeasured review
burden; opaque evidence or invented body/account state; altered frozen prompts/options/
fixtures/thresholds; real-data egress or production wiring; and lack of explicit human
review. If gains are weak or review workload excessive, retain abstention and stop.
Rollback is disabling the isolated proposal; never reset source cursors, rewrite
analysis history or remove human label revisions. No production approval is implied.

## Exact manual PowerShell commands — after review and merge only

Do not run inference to validate this PR. On the user's own machine, with the already
installed local service/model, after reviewed merge:

```powershell
git checkout main
git pull --ff-only

# Five unique development cases, all four fixed variants: 20 serial generation requests
.\.venv\Scripts\python.exe -m family_os.paired_synthetic_diagnosis

# Only after the smoke passes: 60 unique development cases, 240 serial generation requests
.\.venv\Scripts\python.exe -m family_os.paired_synthetic_diagnosis --full
```

Smoke gate: completed=true, configuration_comparable=true, final identity verified,
zero failures/unattempted for each variant, each sent=valid=5, and each comparison
paired_valid_count=5. Exit zero means completed, not correct; semantic-invalid outputs
must still block progression. No --model/--variant/host/file/holdout option exists.
A slow full run can hit the shared 600s limit; stop and report it rather than expand
budgets or claim a complete result. Share only aggregate JSON including warning,
coverage, all four validity blocks and all three comparisons. Do not share records,
case IDs, prompts, raw responses/reasoning or local data/paths. New paired results
support a human decision, never automated selection or policy promotion.

## Validation and review questions

Validation: 74 new tests; 2,071 total passed on SQLite and real PostgreSQL 16.
`pip check` and `git diff --check` passed; GitHub CI evidence is recorded in the PR.
New tests are deterministic synthetic/mock HTTP only. Existing migrations/concurrency/provider
and Phase 2R/2S regressions remain in the complete suites. No live Ollama, household
data or holdout label analysis was performed. Existing isolation test adds only the
named comparator exemption; the new module has its own Import/ImportFrom allowlist
and production-wiring guard. No production source or frozen fixture is changed.

ChatGPT review questions:

1. Does the evidence discussion distinguish known trade-offs from unknown paired
   recoveries/root causes, especially overall versus Calendar-specific gains?
2. Are pair alignment, valid-pair/triad denominators, partial aborts and incompatible
   identity warnings truthful rather than derived from old aggregate summaries?
3. Do unchanged prompts/configuration/budgets, development-only projection and no
   persistence preserve the existing security/privacy gates and historical runners?
4. Do the architecture rules keep relevance/domain separate from action authority,
   require evidence and human confirmation, and prevent silent clearing/hiding?
5. Is the proposed Calendar-only next experiment narrow/reversible, with false alerts,
   missing context, workload and abstention evaluated before production decisions?
6. Are holdout, real household AI input, production model adoption and downstream
   automation explicitly excluded, despite improved synthetic development metrics?
