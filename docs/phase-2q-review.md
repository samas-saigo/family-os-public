# Phase 2Q — independent synthetic Action evaluation and frozen holdout

Issue #46 establishes an evaluation standard before prompt/model optimization.
This is a new fixed dataset, adjudication rubric, strict validator and pure offline
rules report. It is not a model run, classifier upgrade, household evaluation or
production quality claim. No Ollama, network, provider, OAuth, keyring or runtime
household database is used. Existing 37-case Qwen benchmarks, prompts, models,
production rules/thresholds, persistence and human labels are unchanged.

## Authorship, distribution and split protocol

The 90 examples were independently authored from fictional household scenarios,
not sampled from household records or generated/paraphrased from the old corpus.
Addresses are literal `example.invalid`; no real names, accounts or links. IDs,
splits and dates are predeclared, without random sampling or accuracy-based selection.

| Slice | Required | Not required | Uncertain | Gmail | Outlook | Calendar | Drive |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 20 | 20 | 20 | 18 | 18 | 12 | 12 |
| Frozen holdout | 10 | 10 | 10 | 9 | 9 | 6 | 6 |
| Total | 30 | 30 | 30 | 27 | 27 | 18 | 18 |

There are 24 controlled counterfactual triads (16 development, eight holdout), plus
18 standalone challenges (12 development, six holdout). Entire families stay within
one split. Email/Drive triads change only the subject's explicit workflow status cue;
Calendar triads change only `raw_metadata.status` with the same conditional instruction.
Inputs otherwise match exactly. Sibling cases are correlated, not 90 independent trials.
Different scenario families remain separated even when the general task type recurs.

Scenarios: appointment 17, document workflow 16, renewal 11, payment nine, purchase
seven, reservation six, government six, maintenance six, security four, marketing four,
historical three, cancellation one. Historical provenance exists in four cases (one
archived receipt is counted under document); two generic cases have unknown purpose,
and 84 current-context cases. Visible Calendar status: four each confirmed/cancelled/
tentative; other cases omit status rather than invent a provider field.

Relevance is intentionally not balanced: 84 relevant, four irrelevant, two uncertain.
All required truth is relevant. All eight taxonomy categories are covered, with two
unknown domains. Development has 58 known domains/two unknown; holdout has 30 known.
Action-truth adjudication is explicit for 60 cases and intentionally ambiguous for
30. `truth_certainty` describes annotation support, not calibrated probability.
This is primarily an Action standard; its tiny relevance-negative slice is inadequate
for broad false-irrelevant generalization. Status/date/provider/domain counts and
relevance-by-action are printed to expose these limitations, not hide them.

## Observable-evidence annotation rubric

The fixed interpretation time is **2026-10-09 12:00 UTC**, not the machine clock.
Current scenarios have visible October 2026 provenance and explicitly applicable
pending steps. Do not reinterpret a frozen case because today's date changed.
`occurred_at` remains provenance, never event start or an inferred deadline.

- **required**: metadata explicitly asserts a specific outstanding recipient step,
  or preparation whose visible applicability condition is met. Urgency, `due`,
  `renewal`, PDF type, membership, sender, calendar presence or cancellation alone
  are insufficient. No body, unpaid balance lookup or hidden account state is assumed.
- **not_required**: metadata explicitly supports completion, closure, automatic
  settled processing or an informational/optional item without a requested step.
  This clears only the visible request, not every real-world obligation.
- **uncertain**: missing/completion-unspecified, tentative, unresolved conditional,
  draft, historical-without-current-status or weak topic-only evidence. Never infer
  either an obligation or clearance from age or missing message/file contents.

Household relevance is separate from action. A paid household invoice remains
relevant; an optional public advertisement can be irrelevant and not_required.
Domain is visible topic classification, not urgency or a task. Human null/null is
unknown domain truth; analyzer null/null is abstention. They are not missing labels
and do not create an `unknown` taxonomy category. Uncertain human action is not an
unlabeled case. Metrics must retain all these distinctions.

Topic adjudication prefers a specific supported child: household contents cover is
`home/home_insurance`; generic household insurance draft options stay
`household_admin/insurance`. This clarification changed only the unpublished
holdout annotations during authorship, before review/freeze, not any classifier or
score-driven tuning. The final hashes below cover the adjudicated version.

Use exactly `family-os-taxonomy-v1` in `config/classification.yaml`:

| Category | Valid children |
| --- | --- |
| household_admin | insurance, bill, renewal, membership, government_notice, apartment_or_property |
| travel | flight, hotel, rental_car, reservation, itinerary |
| home | lease, utility, maintenance, appliance, home_insurance |
| vehicle | registration, insurance, service, tire, warranty, recall |
| pet | vet_visit, vaccination, insurance, medication, lab, invoice |
| purchase | receipt, order, return, warranty, delivery |
| finance_reference | statement_notice, card_replacement, account_notice, tax_document_notice |
| ignore | marketing, newsletter, social, generic_promotion, market_price_alert |

Not all children are represented. Finance labels are notices/references only; Finance
remains financial truth. Nothing creates a canonical fact, Needs Action item or task.

### Synthetic tricky examples for adjudication review

These examples are evaluation-side review material, **not model prompt examples**:

| Visible synthetic evidence | Action | Reason / caveat |
| --- | --- | --- |
| Household subscription renewal date is approaching | uncertain | Automatic/paid/optional/outstanding status is absent; a date alone does not prove a step. |
| Same pet vaccination instruction: prepare only if confirmed; status confirmed / cancelled / tentative | required / not_required / uncertain | Only confirmed satisfies the preparation condition. Cancellation clears this event-specific instruction; tentative leaves it unresolved. |
| Family ferry cancelled; replacement/refund selection still pending, choose by 11 October 2026 | required | A cancelled reservation still has an explicit new outstanding choice; cancellation is not a global no-action veto. |
| Household heating instalment requested for November 2023; payment status unspecified | uncertain | Old provenance proves neither an unpaid current balance nor settlement. |
| Appliance warranty proof rejected; resubmit receipt by 14 October 2026 (Drive workflow title) | required | A specific missing submission is explicitly asserted; PDF type is not the evidence. It is not independent verification of authenticity. |
| Household insurance renewal draft options for discussion.pdf | uncertain | A draft comparison cannot establish obligation or completion despite a clear insurance domain. |

Drive required cases are narrowly explicit generated workflow titles with missing
recipient steps. Ordinary filenames do not imply obligations. Reviewers should
challenge whether this interpretation of title-level assertions is appropriate; no
signature, document body, owner, ACL or external workflow state is imagined.
Calendar confirmed status alone does not remove preparation/attendance obligations;
our not_required triads are cancelled event-specific requests, not generic confirmations.
Informational booking receipts must not be generalized into task clearance.

Short per-case rationales, bounded evidence references and ambiguity notes live only
in the annotated fixtures. They adjudicate what is asserted, not whether the message
is genuine or safe to act on. Labels never authorize provider or financial writes.

## Files, fingerprints and freeze controls

Fixed directory: `fixtures/action-evaluation-v1/`:

- `development.json`: 60 annotated cases;
- `holdout.json`: 30 annotated cases;
- `rubric.json`: versioned definitions, reference time, caveats and split protocol;
- `manifest.json`: full/split/rubric canonical SHA-256 identities and taxonomy/projection identity.

Dataset version: `action-evaluation-v1`; rubric: `action-rubric-v1`; evaluator:
`action-evaluation-e1`. Canonical JSON sorts keys and cases by ID; timestamps are UTC.
The source-only split hash excludes annotations, while the annotated hash includes
labels/rationales/notes/split. The corpus hash binds both split identities and rubric.
A separately pinned manifest hash makes editing fixtures and regenerating only the
file manifest insufficient. Reordering cases/JSON keys is not a content change.

The manifest records `metadata_only_v1` / `synthetic-e1` and the exact taxonomy hash.
Frozen canonical identities:

| Artifact | SHA-256 |
| --- | --- |
| Manifest lock | f676baa523a8c7a9b187e8139be8e556244a09009ef674b7830a3729b831634f |
| Complete corpus + rubric | 48f1578ebe93a26c307b9e09c7aabf1b10f2127af3018f43815d15ac0a3f3aeb |
| Development annotated | d55c272c19dfa241ce4643c6ce8521cbe18befbdfccdd409163139c2b6dd23a2 |
| Holdout annotated | e9b7fe03ab4d4c5438ef98f8d7438841561fab8daa9fb30a70823fb370162e7a |
| Rubric | 258b0c09b8acb20066c3bd064b19f850829b1d6bf84cdb7f24885212f55cb613 |

All 90 project successfully; maximum projected input is **387 bytes**, under the
1,024-byte dataset ceiling and unchanged 16,384-byte projection ceiling. Tests also
build (but never send) the unchanged Flat-Domain payloads for both allowlisted models,
checking the existing 3,072-byte prompt and 32,768-byte request limits. No tokenization
or actual Ollama context/performance claim is made by a byte-budget check.

The holdout/rubric are proposed frozen in this PR, pending ChatGPT content review.
After reviewed merge, any edit requires new dataset/rubric version as appropriate,
explicit changelog, new manifest/lock and acknowledgement that previous holdout
comparability is invalidated. Never relabel holdout because a model missed it.
This public Git-tracked holdout is procedural, not a blinded or secret test set.
Review authors necessarily see its annotations; that does not authorize tuning on them.

## Validation and inference isolation

`family_os.action_evaluation` accepts only the fixed checked-in files in its developer
entrypoint. No input path, stdin, model, server, account, database or provider option.
JSON duplicate keys, nonfinite numbers, extra fields, wrong shapes/types, oversized
files/text, bad taxonomy/half-null pairs, bad dates/status, non-synthetic addresses,
wrong provider/record types and impossible provider metadata fail closed.

Every declared evidence path must resolve to a bounded scalar in the exact input.
Ambiguous action truth must remain uncertain; a historical request cannot be asserted
as currently outstanding. These guards cannot prove human semantic correctness;
the rubric and review spot-checks remain essential. The novelty guard rejects exact
normalized/obvious token-overlap subjects from the old corpus and across unrelated
new families. It is not a semantic paraphrase detector or proof of independent authorship.

`model_projection(SyntheticCase)` returns only Phase 2L's frozen metadata allowlist:
provider/type, subject/sender, provenance time and approved scalar/nested metadata.
No IDs, split, expected labels, rationales, evidence refs, ambiguity flags or scripted
responses can enter that projection. Tests mutate annotations and verify identical
projection bytes. Repr and errors suppress content. No model prompt is constructed
by this runner; tests only use the old pure payload builder for budget validation.
A future adapter must consume this projection explicitly, never serialize a whole case.
This structural boundary does not prevent a developer manually copying annotations;
holdout discipline is also a reviewed procedural requirement.

## Offline rule evaluation and honest denominators

Default reporting validates **both splits** but evaluates only development with the
unchanged runtime `MetadataRulesAnalyzer`. Final holdout evaluation is an explicit
separate flag, never a source of prompt examples or iterative error-driven tuning.
Reports are aggregate-only: manifest/distributions, definition identity, cohort
confusion counts, review/abstention, provider/domain metrics and zero egress.
No subjects, senders, case IDs, annotations or raw metadata are printed.

- Required recall = predicted required on required truth / required truth count;
  misses include uncertain and not_required. Required false-irrelevant is separate.
- Not-required false positives = predicted required on not_required truth.
- Uncertain concrete assertions are reported separately, not decisive-label errors.
- Relevance/action accuracy uses decisive human labels only; classifier uncertainty
  remains a miss rather than disappearing from the denominator.
- Domain selective accuracy uses known truth plus classified prediction; coverage on
  known truth is separately reported. Unknown truth cannot establish correctness.
- Concrete relevant/irrelevant/required precision and false positives retain Phase 2H
  denominators. Zero-denominator rates are null, never fabricated 0%/100%.
- Invalid rules output aborts the whole report; no silently skipped cases or invented
  valid predictions. No result is persisted or used downstream.

Development baseline: all 60 action/relevance predictions uncertain, all 60 domains
abstained, review 60/60. Required recall **0/20**, misses **20/20**, not-required false
positives **0/20**, uncertain concrete assertions **0/20**. Decisive action correct
**0/40**, relevance correct **0/58**; domain coverage **0/58** known truths, selective
accuracy null. No concrete precision denominator exists. A zero false-positive count
here reflects abstention, not demonstrated safety/quality at useful coverage.
The unchanged rules are narrow; this new corpus is not edited to improve those scores.
The fixed baseline was also explicitly evaluated once in final-holdout mode:
30/30 action/relevance/domain abstentions, required recall **0/10**, misses **10/10**,
not-required false positives **0/10**, uncertain concrete assertions **0/10**,
decisive action correct **0/20**, relevance **0/30**, domain coverage **0/30** known
truths, review **30/30**. This is a frozen-baseline observation, not holdout-driven
tuning or evidence that a future model has been evaluated. Contract tests exercise
both report modes using unchanged rules, without fitting against either split.

## Exact offline commands

From the repository root with the existing Python environment; no database setup,
Ollama service or model install is needed:

```powershell
# Validate both frozen slices; distributions + development-only rules report
.\.venv\Scripts\python.exe -m family_os.action_evaluation

# Final-only offline holdout report; never use it to iterate prompts/rules
.\.venv\Scripts\python.exe -m family_os.action_evaluation --final-holdout

# Dedicated dataset contracts and all regression tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_action_evaluation.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Linux equivalents: `.venv/bin/python -m family_os.action_evaluation` and optional
`--final-holdout`. Full PostgreSQL tests use only a disposable synthetic test database
via TEST_DATABASE_URL. These commands do not access a runtime database.

## Review handoff, limitations and future gate

Python 3.12 validation: **110 new tests**, **1,813 passed on SQLite** and
**1,813 passed on real PostgreSQL 16**, including existing migration/concurrency
regressions. `pip check` and `git diff --check` passed. GitHub CI evidence is recorded
in the PR description. The preexisting spike isolation test adds only this exact
offline runner to its explicit exemption; the new runner's own AST test inspects
both import forms with a strict pure-module allowlist and checks production isolation.
No model evaluation was executed. Automated tests remain synthetic and cover balance,
novelty, cue isolation, bad annotations, changed holdout/rubric, projection/privacy,
metric denominators and network/production isolation.

This compact English set is task-heavy, partly template/triad-correlated, dated at a
fixed reference and limited to visible metadata assertions. It omits many taxonomy
children and contains very few irrelevant/uncertain-relevance cases. It cannot
estimate household prevalence, phishing/authenticity, multilingual quality, body/file
understanding, calibrated confidence or production model quality. Do not collapse
abstention into correctness, market a balanced score as real-world accuracy, or treat
Action Required recall alone as safe automation.

Next implementation requires a **separately reviewed issue** for a manual fixed-file
model harness: exact dataset/split/manifest pins, this projection-only boundary,
independent output validation, identical controlled parameters, explicit dev vs final
holdout mode, no oracle labels/rationales in prompts, versioned reference-time semantics,
separate cohort/false-irrelevant metrics and no arbitrary corpus paths or production
processing. Prompt development may use development data only; preserve untouched
holdout for a final comparison. No new model or prompt changes are authorized here.

ChatGPT review questions:

1. Are the required/not_required assertions supported only by visible metadata,
   especially Drive workflow titles, preparation conditions and cancellation choices?
2. Are renewal dates, old requests, missing statuses and draft files appropriately
   uncertain, without inventing body/account state or clearing unseen obligations?
3. Are taxonomy/domain/relevance assumptions defensible and limitations transparent?
4. Are counterfactual families disjoint across splits and controlled at one visible cue?
5. Are freeze/version/hash controls and the annotation-to-projection boundary sufficient
   for the future separately reviewed dev/final-holdout model harness?
6. Do cohort/unknown/abstention denominators expose missed required actions without
   misleading overall accuracy or claims from zero false positives?
