# Phase 2U — synthetic Calendar action-evidence experiment

## Pre-registered grammar v1 and semantic safety engine e2

This specification is written before the interpreter/evaluation. Only the existing
12 frozen Phase 2Q **development** Calendar projections and a separate v1 synthetic
guardrail cohort are eligible. No holdout file is read by this experiment. Existing
corpus, labels, prompts, models, production rules/thresholds and persistence are unchanged.
No actual household Gmail, Outlook, Calendar, Drive or other data may enter any AI,
including Codex, ChatGPT or local Ollama. This experiment has **no AI at all**.

The pure interpreter accepts only the Calendar subset of `metadata_only_v1`:
`provider=google_calendar`, `record_type=calendar_event`, optional subject (600 chars),
UTC occurred_at (32 chars), and raw_metadata containing status/eventType (256 chars),
start/end date/dateTime strings (256 chars). Unknown fields, wrong types, credentials,
links, invalid Unicode, oversized input (>4096 UTF-8 bytes), malformed dates and
simultaneous date/dateTime fail closed. Invalid status strings are bounded input,
but never interpreted as a known status. Sender/accounts/body/IDs/labels/domain are
not inputs. Dates are validated but do not establish obligations or completion.
The interpreter has no clock, date comparisons, account state or body interpretation.

Semantic engine e2 checks the original and NFKC-normalized title for Unicode characters
named QUESTION + MARK or INTERROBANG **before word normalization/matching**. Any such
marker, anywhere in the title, yields uncertain with unsupported-evidence review,
zero confidence and no concrete obligation/clearance. This includes ASCII/fullwidth/
small/inverted, Arabic/Armenian/Ethiopic/Greek/Adlam, double/combined question marks,
interrobangs and question ornaments. Original-character inspection matters: Greek
QUESTION MARK becomes an ordinary semicolon under NFKC; actual declarative semicolons
remain supported. Indicator-only inspection priority is unchanged and never action truth.

Normalization then uses NFKC + casefold, punctuation-separated word tokens, collapsed spaces.
Only **whole normalized titles** matching the finite forms below are supported.
Question marks, extra clauses, commands, quoted instructions, approximate synonyms and unmatched
negation/contradiction abstain. No substring match can create an action proposal.
Evidence references contain only `subject` and, where applicable, `raw_metadata.status`;
conditions/rule IDs/scopes/reasons are fixed enums, never captured title fragments.

Supported step vocabulary: `provide access at the scheduled time`, `bring the driving
licence`, `bring the vaccination booklet`, `bring the current allergy chart`,
`request refund`, `request rebooking`. It is deliberately narrow English-only research.

| Rule | Entire normalized title / condition | Proposal and scope |
| --- | --- | --- |
| conditional-preparation-v1 | `if this EVENT is confirmed STEP do not prepare while status is tentative`; EVENT/STEP pairs are exactly household boiler visit/access, family rental-car pickup/licence, pet vaccination visit/booklet | confirmed: required for preparation; cancelled: not_required for **that conditional preparation only**; tentative/missing/unknown: uncertain |
| status-condition-v1 | `if status is confirmed STEP` | same narrowly scoped condition handling; status alone never suffices |
| booked-preparation-v1 | `your pet consultation is booked bring the current allergy chart on DATE` (explicit day/month/year, valid date) | required for explicit preparation, not inferred attendance/date urgency; visible cancelled/tentative conflicts -> uncertain |
| completed-visit-v1 | `pet consultation completed on DATE visit record only no follow-up requested` | not_required for that completed visit step only |
| outstanding-step-v1 | `outstanding step STEP` or `condition met outstanding step STEP` | required for the explicit outstanding step; the latter cites visible met-condition assertion, not an account query |
| no-step-v1 | `completed step STEP no further step requested`, `cancelled step STEP no replacement step requested`, or `do not STEP no further step requested` | not_required for that named step only |
| unmet-step-v1 | `condition unmet step STEP not requested` | not_required for that named conditional step only |
| unknown-step-v1 | `condition unknown outstanding step STEP` or `superseded step STEP replacement step unknown` | uncertain; unresolved condition/replacement requires review |
| cancelled-followup-v1 | `event cancelled outstanding step request refund` / `... request rebooking` | required for explicit separate follow-up, even after cancellation; conflicting visible confirmed/tentative status -> uncertain |
| abstain-v1 | everything else | uncertain, reason missing/unsupported/conflicting evidence |

Precedence: validate projection first; multiple recognized outstanding/completion/
condition instructions or extra unsupported clauses cannot fall through to a shorter
match. Only full grammar match is accepted. A known cancellation is an unmet
confirmed-preparation condition, **never a global no-action clearance**. Explicit
refund/rebooking is a separate grammar and cannot be erased by cancellation. Unknown
status allows an independently sufficient direct outstanding/completed assertion;
it does not satisfy any status-dependent condition. All proposals mandate human
review; zero confidence, no facts, no authority and no relevance/domain output.

## Separately versioned guardrails, frozen before evaluation

The new `fixtures/calendar-evidence-guardrails-v1.json` cohort is not appended to the
60-case development set. Its 78 cases comprise 61 valid projected inputs (13 required,
7 not_required, 41 uncertain) and 17 deliberately invalid projections with **no action
truth**. This asymmetric set is a rule-vocabulary/negative safety probe, not a balanced
accuracy study. It covers status-only, keyword-only, missing/invalid status,
explicit preparation/steps, completion/negation/cancellation/supersession, separate
refund/rebooking, met/unmet/unknown conditions, conflicting or unsupported language,
extra instruction attempts, historical timestamps without completion inference,
and invalid field/type/privacy/resource cases. Gold action labels are based only on
visible metadata; input-invalid cases have no action truth/prediction. Every case has
a fixed family and supported-positive-control flag. Gold labels never enter the pure
interpreter. The frozen guardrail content and rule specification are fingerprinted.
No iteration toward perfect recall or holdout scoring is authorized. The missing-title
case is registered explicitly alongside the original status-only cases. Version/pins:

- interpreter: `calendar-evidence-e2-0ce116c96c390456`;
- rule fingerprint: `0ce116c96c390456ff106cfad82ec9763d2cc66f6bd91257f7609b5b49921662`;
- indicator: `inspection-indicator-v1`, fingerprint
  `bf9cee3e70dadd4513a427b001167ee0287df9fe2849cc0da77d6aa14b2645dc`;
- original development file SHA-256:
  `dca27d27aab7976c94be6572d7152e24342de11c804c47163a12ce735b35ca6d`;
- separate guardrail file SHA-256:
  `011b5437665a637d9c981d351977a5456b3a4fd4211ed042ae5672333e03b117`.

The rule fingerprint records the frozen vocabulary, contract, bounds, normalization
and semantic engine revision; intentional semantic changes require an engine revision.
Fixture pins reject edits before interpretation. No previous cohort is rewritten.

## Indicator comparator

The fixed `inspection-indicator-v1` suggests priority if a recognized Calendar status
is present or a normalized whole token is in {bring, provide, outstanding, refund,
rebooking, completed, cancelled, prepare}. These are **inspection cues, not required
predictions**. It emits no action label or clearance. Unflagged cases still need human
inspection; flags cannot hide/filter records. Report flag counts/rates and false alerts
on not_required/uncertain separately, plus required controls unflagged. All selected
cases, including invalid projections, contribute to manual inspection load. The
comparator and interpreter operate on identical projections, without relevance/domain.

## Results and decision

Actual deterministic offline evaluation (no model, network or database):

| Measure | Original development Calendar subset | Separate guardrails v1 |
| --- | ---: | ---: |
| Selected / evaluated | 12 / 12 | 78 / 78 |
| Valid / input-invalid | 12 / 0 | 61 / 17 |
| Required recall (numerator/denominator) | 4/4 | 13/13 |
| False required on not_required | 0/4 | 0/7 |
| False required on uncertain | 0/4 | 0/41 |
| Required -> not_required / uncertain | 0 / 0 | 0 / 0 |
| Valid uncertain proposals / valid denominator | 4/12 | 41/61 |
| Unsupported concrete output / unsupported-output count | 0 / 0 | 0 / 0 |
| Unsupported-language abstentions (subset of uncertain) | 1 | 29 |
| Missed explicit supported positive controls | 0/4 | 0/13 |
| Human inspection count / rate (interpreter AND indicator) | 12 / 100% | 78 / 100% |
| Indicator priority / valid denominator | 11/12 | 49/61 |
| Indicator alerts on not_required / uncertain | 4 / 3 | 7 / 29 |
| Required unflagged by indicator | 0/4 | 0/13 |

Action confusion matrices are diagonal for these fixed cohorts: original truth
required/not_required/uncertain -> corresponding proposal 4/4/4; guardrails -> 13/7/41.
All other matrix cells are zero. Invalid inputs have **no prediction**, not uncertainty,
and remain part of the inspection load. No invalid/missing case is silently dropped.
Required recall denominator is selected truth Required, even if an output fails
validation; rejected outputs count as invalid, not accepted concrete suggestions.
Null is returned for every zero denominator (including guardrail triads).

Original Calendar status cohorts: confirmed/cancelled/tentative/missing each 3, with
Required support 3 confirmed + 1 missing. Original three status triads are fully
evaluated: 3/3 correct complete triads, 9/9 correct pairs and 9/9 changed pairs.
These are **actually computed interpreter** predictions, not historical model repairs.
Guardrail status selected/valid counts: confirmed 5/5, cancelled 5/5, tentative 2/2,
missing 57/44, unknown 6/5, malformed 3/0. The report also exposes fixed cue/family
strata and all three truth-cohort denominators. No individual titles/case IDs are
exported. Relevance/domain are out of scope: neither is an input, output or filter;
silent suppression is zero by construction and tests, not inferred relevance accuracy.

Exit decision: **continue isolated synthetic research only**, and abstain outside the
registered grammar. No unsupported concrete decisions or missed supported controls
were observed in these probes, but inspection burden remains 100%. This is not a
production win, general-language coverage, real-world recall or permission to skip
review. The grammar intentionally names three synthetic event/step combinations;
perfect scores on these correlated structures and designed positive controls do not
establish generalization. Implicit obligations, synonyms, other languages, ambiguous
multi-step relationships and missing body/account context remain unsupported.
Any unsupported concrete output, mistaken clearance, false required or missed explicit
supported control blocks continuation (`stop_abstain`); raising recall by over-alerting
is not accepted. No product integration or real-data shadow mode is authorized.

Historical Phase 2T model comparison is descriptive context only, not paired with this interpreter:
240/240 valid across four variants; calendar-status repaired 6 baseline Required misses,
all non-Calendar, with 0 newly missed Required. Calendar Required stayed 0/4. Calendar
status pair changes 6/9, correct pairs 3/9, complete triads 0/3. False-irrelevant was
16 -> 21 in that aligned run; three mistaken clearances repaired and three different
ones introduced. These are user-reviewed aggregate observations, not new inference,
causal explanations, tests to reproduce, or per-case model predictions available here.

## Isolation and manual commands

The interpreter is standard-library-only and import-safe. The separate offline runner
reads exactly two pinned checked-in synthetic JSON files, never stdin/arbitrary paths,
accounts, source databases, provider clients, keyrings, models or production classifiers.
It validates a narrower Calendar subset of the existing approved projection directly,
rather than importing old runners/model adapters or passing whole AnalysisInput/source
records. Frozen input/expected labels remain unchanged; occurred_at is accepted in UTC
with or without six fractional digits, but cannot affect action interpretation.
No filesystem export, persistence, scheduler, network, CLI product wiring or task is
added. Import and call-graph tests cover both import forms, prohibited effects,
fixed reads, no automatic run and no case-content stdout/logging. Disable/remove the
isolated tools to roll back; never modify source cursors, analysis history or labels.

After review/merge, from the repository root (no Ollama needed):

```powershell
.\.venv\Scripts\python.exe -m family_os.calendar_evidence_evaluation
.\.venv\Scripts\python.exe -m pytest -q tests/test_calendar_action_evidence.py tests/test_calendar_evidence_evaluation.py
```

The report is aggregate-only: no titles, subjects, event/case/record IDs, raw metadata,
labels by case, paths or text-bearing evidence. Errors are content-free. Numerical
confidence is fixed zero; no probabilities or automatic priority-to-task conversion.

### Windows checkout refresh

The two pinned JSON inputs have explicit `text eol=lf` Git attributes, including
when `core.autocrlf=true`. Their contents, SHA-256 pins and evaluator's strict
byte checks are unchanged. Adding attributes does not necessarily rewrite files
already checked out as CRLF. After pulling the reviewed change, run this once
from the repository root in PowerShell. Stop if either fixture has local edits;
preserve and review those edits before proceeding.

```powershell
$fixturePaths = @(
    "fixtures/action-evaluation-v1/development.json",
    "fixtures/calendar-evidence-guardrails-v1.json"
)
git diff --quiet -- $fixturePaths
if ($LASTEXITCODE -gt 1) { throw "Could not compare fixture contents" }
$changes = @(git status --porcelain -- $fixturePaths)
if ($LASTEXITCODE -ne 0) { throw "Could not check fixture status" }
if ($changes.Count -ne 0) { throw "Stop: preserve local fixture edits before refresh" }

$attributes = @(git check-attr text eol -- $fixturePaths)
if ($LASTEXITCODE -ne 0) { throw "Could not check fixture attributes" }
foreach ($path in $fixturePaths) {
    if ($attributes -notcontains "${path}: text: set" -or
        $attributes -notcontains "${path}: eol: lf") {
        throw "Stop: pull the reviewed LF checkout rules first"
    }
}
Remove-Item -LiteralPath $fixturePaths -ErrorAction Stop
git checkout-index --force -- $fixturePaths
if ($LASTEXITCODE -ne 0) { throw "Fixture checkout refresh failed" }
git ls-files --eol -- $fixturePaths
.\.venv\Scripts\python.exe -m family_os.calendar_evidence_evaluation
```

After the clean-status and attribute checks, the targeted refresh removes only the
two working copies and restores them from the unchanged Git index. Removal ensures
Git cannot skip stat-clean CRLF copies. If checkout fails, rerun the checkout-index
command to restore them; never change the pins. `git ls-files --eol` should show
`i/lf w/lf` and `text eol=lf` for both.
No global Git setting, fingerprint update, dataset renormalization, database,
Holdout or model access is needed. Regression tests exercise actual isolated Git
checkouts with `core.autocrlf=true`, `input` and `false`, including existing CRLF
copies, unchanged pins, detection of local edits and continued integrity rejection.
This verifies Git's Windows-style conversion policy, not a native Windows test host.

## Validation

293 new deterministic synthetic tests, including 69 question-safety regressions,
protect the grammar/condition transitions,
negative controls, independent evidence/output validation, immutable values, Unicode,
privacy/resource bounds, exact metric denominators, rejected-output coverage, null
denominators, indicator-only behavior, import/call-graph isolation and safe CLI errors.
All 2,364 tests passed in the complete SQLite and real PostgreSQL 16 suites after
the e2 question-safety fix; the frozen cohort metrics above remain unchanged.
The Windows LF-checkout follow-up adds six Git regression tests; all 2,370 tests
passed in both complete suites. Fixture bytes, pins and semantic versions are unchanged.
`pip check` and `git diff --check` passed; GitHub CI evidence is recorded in the PR.
No model/provider inference or real
household access is part of validation. Existing provider, schema, classification,
analysis, human-label, cursor and migration tests remain unchanged.

## Review questions

1. Do full-title grammar and field-level evidence support every concrete proposal,
   including narrow cancelled preparation versus separate refund/rebooking?
2. Do malformed/unknown inputs, conflicts and extra instructions fail closed without
   suppressing required/uncertain inspection or inferring completion from dates?
3. Are all 12 original Calendar cases (four Required) included unchanged, and guardrail
   denominators/invalid cases separated without holdout access or score inflation?
4. Are priority flags distinct from action truth and all review-load/error denominators
   explicit, with null for zero denominators and no model per-case reconstruction?
5. Is the exit decision limited to isolated synthetic research/abstention, without
   production adoption, real-data shadow mode, AI permission or downstream authority?
