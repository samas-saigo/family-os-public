# Family OS v0.1 / Slice 2 — disposable synthetic interactive review demo

## Purpose and non-production boundary

[Issue #63](https://github.com/samas-saigo/family-os/issues/63) adds a private terminal
presentation adapter over the merged [Slice 1 core](v0-1-single-user-review-core.md).
It exercises the [Phase 2W product contract](phase-2w-product-workflow.md) and
[Phase 2V boundaries](phase-2v-human-review-workflow.md) without importing either
research interpreter or simulation. It is not Inbox, Needs Action, an authenticated
service, a classifier, a task manager or a real household review workflow.

Only newly authored fixed English enum-only examples are admitted. No real source,
account, database, private metadata, human-labeled household record, frozen fixture,
Holdout, model, OAuth/keyring or provider interface is read. No household information
enters any AI, including local Ollama. There is no network, shell launch, telemetry,
new framework or dependency. The target remains one authoritative backend with
multiple authenticated clients; this local single-process research adapter chooses
no client framework and grants no authorization for a network/shared UI.

## Run locally (Windows PowerShell)

From the repository root, with the existing Python 3.12 environment installed:

```powershell
.\.venv\Scripts\python.exe -m family_os._synthetic_review_demo --synthetic-only
```

The **exact sole flag** `--synthetic-only` is required before core import or store
initialization. `--help` prints instructions without opening a store. Other flags,
paths, URLs, account IDs or free-form metadata are rejected without echoing them.
There is no production `family-os` command or service integration. Do not register
accounts, migrate a database, connect OAuth or install/run a model for this demo.

Every invocation creates its own factory-owned temporary SQLite store, ignoring
`DATABASE_URL` and `TEST_DATABASE_URL`, even in PostgreSQL-configured test runs.
No external engine/path is accepted. Quit, EOF, interruption and session failure
leave the factory context and dispose its store. History survives connections within
the running session **only**; restarting begins empty. This is not durable end-user
storage, crash recovery or a security sandbox against a hostile Python caller/admin.

## Controls and a suggested walkthrough

1. The initial **All** view is empty. Type `load` to explicitly create eight encounters.
   Repeating `load` browses existing examples rather than reinitializing them.
2. Select `1`–`8` to inspect a card. `history` reads immutable decision history;
   `refresh` reads the existing receipt. Neither creates an encounter or rotates its
   token. `back` returns to All. All loaded items remain visible regardless of status.
3. `review` asks for an intention with **no default**. A supported concrete suggestion
   permits `human_confirmed`, `human_rejected`, `needs_more_information` or `deferred`.
   Uncertain/invalid/missing/unsupported/conflicting suggestions permit only the latter
   two. These controls follow the core's proposal; the core independently enforces saves.
4. After choosing an intention, inspect the **Save review confirmation**, then type
   exactly `save`. `back` revisits the intention prompt; `cancel` returns to the card
   without saving. Invalid confirmation discards the intention. `q`/`quit`, EOF or
   Ctrl+C exits without saving the unfinished intention. `b`/`c` are navigation aliases.
5. After successful acknowledgment, read history and optionally correct the decision
   through another explicit intention and Save. The next revision appends; nothing
   overwrites or globally clears another step/account/event.
6. `update` opens a fixed menu: `repeat` explicitly creates an unchanged encounter;
   `change` increments the synthetic snapshot and changes status/condition to
   tentative/unknown; `revert` restores the original enum fields at a **new** snapshot.
   Each is an explicit encounter, not an automatic refresh. Back/Cancel does not update.
7. Try confirming card 1, then `update` → `repeat`: it stays visible and already reviewed.
   Next `change` reopens uncertainty; `revert` restores a concrete suggestion requiring
   fresh review. The old decision remains historical and never regains current authority.
8. Compare card 7 (account B's refund) and card 8 (account A's rebooking): neither inherits
   card 1's refund decision. Inspect card 2's Not Required suggestion and cards 3–6's
   missing/invalid/conflicting/unsupported cases. Then `quit` discards the session store.

| Card | Fixed synthetic scope | Initial suggestion |
| --- | --- | --- |
| 1 | account A / event 01 / refund | Required, supported |
| 2 | account A / event 02 / attendance | Not Required, supported |
| 3 | account A / event 03 / preparation | Uncertain, missing |
| 4 | account A / event 04 / refund | Invalid |
| 5 | account B / event 02 / preparation | Uncertain, conflicting |
| 6 | account B / event 03 / attendance | Uncertain, unsupported |
| 7 | account B / event 01 / refund | Required, independent account |
| 8 | account A / event 01 / rebooking | Required, independent named step |

These are authored proposals, not outputs of a classifier. Confirm means agreement
with this exact suggestion; reject means disagreement. Confirming Not Required is
not completion or whole-event clearance. Needs-information and defer stay unresolved.
Account surrogates are source identities, **not authenticated people**. No disposition
creates a task, proves an obligation, authorizes execution or modifies any provider.

## State, transactions and safe presentation

The unchanged core owns receipts, epochs, permitted dispositions, CAS, request
idempotency, append-only observations/decisions, limits and atomic transactions.
The adapter retains only its finite scenario selection and aggregate session counters;
it implements no alternate review state or database query/persistence layer. Keyboard
input and presentation happen outside core transactions. Navigation never calls
`encounter` or `save`; only explicit `load`/`update` and confirmed `save` do so.

An intention copies the **displayed** receipt's identity, token, evidence/proposal
fingerprints, epoch and expected revision, with one bounded unique synthetic request
ID. The core remains the authority. Double `save` input is not a second intention;
identical command delivery converges under core idempotency. Different intentions use
new request IDs and append revisions. A save banner appears only after acknowledgment.
A replay of an old decision cannot claim to resolve changed current evidence.

Stale or competing writes discard the unfinished intention and require a fresh card
before another Save. A changed snapshot outside the curated adapter is not rendered
with cached proposal fields: the card fails closed and disables review. The ordinary
demo does not offer external clients or arbitrary snapshot loading; recovering such
an unsupported test mutation may require ending the disposable session. Research
receipt tokens bind displayed versions and are not user authentication.

Cards expose only fixed synthetic account/event/step enums, snapshot/version stamps,
status/condition/scope, suggestion/reason/evidence refs, disposition, visibility,
review annotation, epoch and revision. History shows original synthetic snapshots and
versions. Opaque tokens, request IDs, hashes, connection URLs and environment values
are never printed. Controls are bounded to 64 characters; oversized input stops the
session so a truncated tail cannot become a Save command. Unknown/control/Unicode
input is not echoed or persisted. Storage/internal failures emit a generic safe error
and stop; typed stale/idempotency/capacity rejections retain committed history. All
storage is still removed on exit; crash cleanup is not a production guarantee.

The final session summary is aggregate-only: explicit encounters, saved decisions,
acknowledged replays, cancelled intentions and rejected writes. It is not an accuracy,
usability, time-saved or production-safety measurement. EOF/quit before Save performs
no implicit decision; existing acknowledged decisions remain in-session until cleanup.

## Validation and review handoff

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_review_demo.py tests/test_synthetic_review_core.py tests/test_synthetic_review.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The full retained SQLite/PostgreSQL 16 suites use disposable synthetic test databases;
**the demo's tests always use factory-owned SQLite**, never the PG engine fixture.
Two existing isolation guards add an exact exception for this private adapter, while
continuing to forbid any production import of the core/demo. New AST/fresh-process
checks bound demo imports and verify absent/incorrect opt-in does not load the core.
85 new scripted tests cover opt-in/import isolation, all dispositions, readonly
navigation, Back/Cancel/EOF, correction, repeat/change/revert, independent identities,
stale/competing saves, duplicate delivery, resource limits, privacy and cleanup.
Local SQLite and dedicated PostgreSQL 16 suites each passed all 2,696 tests
(2,611 retained + 85 new); the focused demo/core/Phase 2V group passed 326.
`pip check`, documentation links/fences and `git diff --check` passed.
No existing core implementation, production CLI/service, migration, classifier,
fixture, rule/model, scope or dependency pin changes. Exact test totals and GitHub
run/job links are recorded in the PR after complete validation.

ChatGPT initial review and independent Muse architecture/privacy review are required,
followed by corrections, ChatGPT re-review and a human manual merge decision. This PR
must remain unmerged; it does not authorize automatic merge or a real-data trial.

Review questions:

1. Does the exact opt-in gate precede all store access, with no production/env DB path?
2. Can read-only navigation, invalid controls, Back/Cancel/EOF ever create a decision
   or rotate an encounter receipt?
3. Is Save separate, version-bound and core-enforced, with acknowledgment before success?
4. Do changed/reverted evidence, independent accounts/steps, corrections and retries
   preserve visible unresolved states, immutable history and zero execution authority?
5. Are safe errors, bounded input, session cleanup and isolation guards sufficient for
   this disposable research interface without implying auth or production retention?
