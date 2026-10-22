# Phase 2V — synthetic human-review contract and repeat safety

## Decision and boundary

Issue #57 asks whether a human can understand and revisit a scoped proposal without
being asked to decide an unchanged, explicitly resolved proposal repeatedly. This is
an isolated, reversible **design simulation**, not a usability trial or deployment.
Continue isolated synthetic research only: the simulated policy annotates seven
unchanged resolved repeats, but all 39 visits still show the item and accessible
history. No observed human time saving or real-household safety claim follows.

`family_os.synthetic_review` is a pure, bounded, in-memory prototype. It reuses
Phase 2U's unchanged `CalendarProjection`, interpreter and independent proposal
validation. It imports no production service, classifier, database, provider,
OAuth/keyring, model or network interface. Import does not run the simulation.
There is no product CLI wiring, review queue, Phase 2H evaluation-label operation,
task, canonical state, scheduling, authentication or R0–R3 execution authority.
No migrations, persistence or arbitrary input paths/stdin are supported.

**No real household data or human-labeled real metadata may enter any AI, including
Codex, ChatGPT, Muse or local Ollama.** Only newly authored English synthetic design
sequences are used here; there is no AI, Holdout read, household access or model call.
Existing Phase 2Q–2U files, labels, prompts, fingerprints, semantic versions,
thresholds and LF checkout protections are unchanged. The simulator does not even
read their fixture files. Its input function is not a real-data sanitizer: its
contract is approved synthetic callers only, with fixed synthetic IDs.

## Client-independent conceptual review card

The following is a text-only wireframe specification, not a built client or API.
Future clients would render backend-owned contracts; this experiment's disposable
memory must never become a client-side task store or a second source of truth.

| Card field | Meaning / bound |
| --- | --- |
| Synthetic event / snapshot | Fixed synthetic ID; positive snapshot version 1–1,000; never words-as-identity |
| Evidence | Phase 2U minimized Calendar projection, at most 4,096 UTF-8 bytes; no body, account, sender, content or secrets |
| Suggestion | `required`, `not_required`, `uncertain`, or **invalid: no suggestion**; zero confidence; human review mandatory |
| Applicable condition | Phase 2U fixed condition enum, including unmet/unresolved/conflicting/missing signals |
| Named step and scope | Read the specific step from the referenced synthetic subject; fixed scope enum, never global event clearance |
| Evidence refs | At most two distinct refs: `subject`, `raw_metadata.status`; Phase 2U verifies resolution and grammar |
| Explanation | Fixed reason enum; unsupported/missing/conflicting evidence is explicit, not a free-text rationale |
| Provenance | Exact input/proposal fingerprint, snapshot, analyzer version, rule fingerprint, review-schema version |
| Review disposition | Pending / human-confirmed / human-rejected / needs-more-information / deferred, separate from the suggestion |
| Human decision | Explicit choice **and** `save`, bound to the displayed fingerprint, visit and expected revision |
| History / repeat annotation | Append-only revisions and their full original synthetic snapshots; unchanged resolved repeat annotation never hides the card |
| Authority | Always none: confirmation/rejection does not approve execution, create a task or assert canonical truth |

For a `not_required` suggestion, confirmation agrees only with the named step's
supported proposal; rejection disagrees with that proposal. Neither means an event
is globally completed or that no refund/rebooking/other obligation exists. Negative
conditions and unknown/conflicting status must remain legible. Unknown/invalid
evidence offers needs-information or defer, not a close/accept shortcut. No priority,
relevance or domain signal may filter the card or authorize a resolution.

The simulator scripts explicit decisions; it does not pretend to authenticate a
reviewer or interact with an actual operator. An explicit command is an experimental
input, not proof of user consent or future backend authorization.

## Versioned state and transition table

Contract: `synthetic-review-v1`. There are at most 128 visits and 128 total decisions
per simulation state, across 16 allowed synthetic IDs. Every observation is validated
again before acceptance; every save revalidates the current immutable proposal.
Policy fingerprint: `8aee87ce48d6b7682736de4777ed567451cc884debcd64bf55141de214dca45a`.

| Starting state / encounter | Allowed action | Result |
| --- | --- | --- |
| First valid Required or Not Required | No explicit save | Pending; visible; review prompt |
| Pending supported concrete proposal | Explicit `save` + human-confirmed or human-rejected | Append resolved revision for this exact scoped proposal only |
| Any current proposal, including invalid/uncertain | Explicit `save` + needs-more-information or deferred | Append unresolved revision; remains visible and requires review on repeat |
| Invalid or uncertain, or unsupported/missing scope/evidence | Confirm/reject/close | Rejected atomically; no history change |
| Any disposition | Explicit correction with current visit/fingerprint and correct expected revision | Append next revision; earlier record unchanged; same validity restrictions apply |
| Unchanged and latest revision explicitly resolved in this evidence epoch | Repeat encounter | Annotate already reviewed; no mandatory duplicate decision prompt; card/history remain visible; correction remains possible |
| Pending / deferred / needs-information / invalid / uncertain | Unchanged repeat | Visible unresolved carryover; another review prompt |
| Evidence, snapshot, condition, named step/scope, analyzer/rule/schema stamp changes | New encounter | New evidence epoch; pending again; no previous resolution transfer |
| Changed evidence later returns to old exact bytes | New encounter | Another epoch; old resolution still cannot revive |
| Older snapshot | Encounter | Reject before state changes |
| Stale visit/fingerprint or wrong revision / mismatched ID | Save | Reject before state changes; no lost correction or replay |
| Auto-save/auto-confirm/auto-reject, unknown transition, reviewer/confidence/priority/domain/relevance/task fields | Command | Reject with content-free error; no writes |

Corrections use increasing integer revisions, not timestamps. Frozen revision values
retain the original immutable synthetic record, including snapshot, projection,
proposal and versions. A latest revision applies only to its exact fingerprint and
evidence epoch. Changed evidence never erases history. Even a repeated unchanged
visit invalidates an earlier display receipt; an operator cannot save against a
stale display. This is a deterministic single-threaded simulator, not a distributed
concurrency/authentication contract or production approval policy.

The fingerprint uses canonical JSON over the exact allowed projection, event ID,
snapshot, invalidity marker, version stamp and validated proposal (including condition,
scope, refs, zero confidence and review signal). Punctuation that preserves semantics
still changes exact evidence and requires another review. Distinct IDs never merge,
even when all words match. Rule/analyzer/schema-change probes use explicitly named
synthetic stamps; they do not install another analyzer or modify Phase 2U rules.
Only one fixed malformed-input specimen is admitted as a visible invalid observation;
other invalid inputs are rejected safely before entering state.

## Pre-registered design sequences and aggregate results

Separately versioned `synthetic-review-sequences-v1` is authored as fixed literals
in the isolated module before its first simulation. Its canonical integrity pin is
`bfccc2cd7512d3b16d96cbc0b3a0bdce0bbe672c3f76f0e1c0a901026adbb059`.
The report verifies the pin before simulating. This is independent of Phase 2U's
12 development / 78 guardrail evaluation cases, not added coverage or retuned gold.

Twelve sequences cover confirmation/correction, Not Required pending until save,
uncertain and invalid carryovers, deferral followed by explicit rejection, exact-byte
change, condition cancellation/conflict, refund-to-rebooking scope, partial-step
completion, rule/analyzer invalidation, two distinct same-word events, and schema
invalidation. They contain 13 distinct synthetic events and 39 visits. First
suggestions: nine Required, two Not Required, one Uncertain, one invalid. Tests add
stale ordering, forged identity/confidence, Unicode/question/instruction attempts,
resource bounds, safe errors and failed suppression detection.

| Aggregate | Observed synthetic count / denominator |
| --- | ---: |
| First-time required review prompts (all suggestion types) | 13 / 13 first encounters |
| Repeat proposals | 26 / 39 visits |
| Unchanged explicitly resolved repeats | 7 / 26 repeats |
| Mandatory re-reviews after change | 8 / 8 changed encounters |
| Unresolved carryovers | 11 / 26 repeats |
| Invalid / uncertain visits, kept visible | 3 / 5, respectively |
| Review-every-time baseline prompts | 39 / 39 visits |
| Policy review prompts | 32 / 39 visits (82.05%) |
| Explicit scripted human decisions | 23 / 39 visits (58.97%), including one correction |
| Unsupported automatic save attempts rejected | 39 / 39 attempts |
| Wrong reuse / silent suppression | Both zero; 39 visits checked |
| Visible inspection visits under either policy | 39 / 39 (100%) |

The baseline's 39 scripted decisions assumes one decision per visit solely as an
explicit comparator. The policy's 23 saves reflect authored choices, including
pending visits and unresolved repeats, rather than measured human effort. Seven
duplicate **mandatory decision prompts** are annotated as already resolved; the
remaining difference in decision counts is not attributable workload saving.
Effective review load is reported as mandatory prompts and visible visits separately;
it is not elapsed time. No card is hidden, no inferred permission to skip inspection,
no recall/accuracy/UX/safety claim and no production authorization follows. These
small, designed English sequences are not representative household workflows.
There is one current scoped proposal per synthetic event ID. Parallel multi-step
reviews, cross-provider matching, authenticated reviewers, concurrent clients,
real-world completion verification and durable review state are deliberately absent.

Ratios use their stated denominator; zero denominators return null, including an
empty hypothetical simulation in tests. Invalid is not Uncertain, and unresolved
is not resolved. Human dispositions do not change evidence action labels.

## Safety failure criteria and rollback

Unexpected reuse, hidden cards or accepted automatic saves produce `stop_abstain`
and a nonzero CLI exit; malformed state/input fails with content-free errors.
Tests also prohibit concrete resolution of invalid/uncertain evidence, forged
proposals, lost history, stale saves, suppression by classification/priority fields,
production imports/calls and external effects. Any failure in these invariants,
provenance loss, task authority, data/AI boundary violation or unmeasured workload
claim blocks continuation. Only isolated synthetic research is recommended.

Rollback is removal of this isolated module, its tests and documentation links.
Nothing has been persisted; do not touch household databases, cursors, source or
analysis history, evaluation labels, tasks, OAuth or model settings. Removing the
prototype does not require a migration. Existing Phase 2U evaluator LF/SHA behavior
remains intact.

## Manual PowerShell commands and validation

After reviewed merge, from the repository root (Python 3.12; no Ollama needed):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_review.py
.\.venv\Scripts\python.exe -m family_os.synthetic_review --simulate
```

The module invocation is explicit opt-in and prints one aggregate JSON report only:
no subjects, metadata, IDs, case text, prompts or paths. It reads no files, network,
database or stdin and writes no state. It is not an interactive human session.
Errors never echo arguments or private exception text.

100 new synthetic tests cover transition/repeat rules, exact evidence history,
safe errors, integrity, metrics/denominators, bounded state and isolation. The
complete suite contains 2,470 tests (2,370 retained tests plus 100 new ones). Full
SQLite and real PostgreSQL 16 results, `pip check`, `git diff --check` and both
GitHub CI conclusions are recorded in the PR. No real household or live
model/provider inference is part of validation; the simulator reads no Holdout,
and existing database tests use disposable synthetic stores.

## ChatGPT / human review questions

1. Do suggestion, review disposition and future action authority remain separate,
   especially for Not Required and explicit human rejection?
2. Are unchanged reuse and correction bound to the exact snapshot/proposal/versions
   and epoch, with every evidence/scope/version change reopening review?
3. Do invalid, uncertain, pending, deferred and needs-information remain visible,
   with no auto-resolution or whole-event clearance of partially completed steps?
4. Do stale display/revision checks and immutable history preserve the exact evidence
   under correction, changed snapshots and distinct similar-word events?
5. Are visits, prompts, explicit decisions and inspection load reported truthfully,
   without treating designed sequences as observed usability or household safety?
6. Is isolation complete: no production imports/wiring, AI, Holdout, household input,
   DB/network/persistence, task/review_queue integration or R0–R3 implementation?
