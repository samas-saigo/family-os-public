# I5 — fictional information → authoritative Pending → explicit Task

Base: merged #93, `d5dfa1bd1689894aafa45e794adc8311773fca1b`.
Only the existing owned, disposable I2/I4b fictional lab is extended. No real data,
provider, model, OAuth, production login, background worker or external operation.

## Minimal design, before implementation

Stage A separates safety, business routing and simulated authority; its enum Access
is **not** a SessionService identity or grant. I5 reuses its pure business routing
with a constant fictional inspection context, no history/acceptance. Actual source,
Pending, publication and Task rights remain T1/SessionService database checks.

T1 has no producer processing ledger. Add one additive Alembic table,
`fictional_information_revision`, in the same database, with household/source/record/
generation identity, deterministic input/plan hashes, exact finite evidence JSON,
rule version, destination, effect and optional T1 Pending reference. No message text,
provider objects, credentials, model content or human identity assertions. Rows are
append-only through this internal service. Downgrade drops this ledger only; existing
Pending/Task/provenance/history remain. No runtime/user database is migrated here.

The coordinator cannot choose grants. A separately configured immutable fixture plan
pins record/source, allowed Pending readers/reviewers/publishers and neutral Task
recipients at membership epoch 1. It materializes only that preapproval on first
Pending insertion; updates never rewrite grants/plans or restore revoked rights.
Plans cannot be silently changed on retry/restart. Source grants are separately
configured by trusted fixture setup, never classification. This is a privileged
synthetic initialization seam, not production producer authorization.

Processing and acceptance share the existing household DB transaction lock. Same
record/generation/intent replays without mutation; changed intent at the same generation
or a non-sequential generation is rejected. Evidence/safety/rule changes require a new
generation, even for a revert. Existing unresolved Pending advances its CAS revision;
human events remain historical. Accepted Pending/Task is never overwritten: later
inputs are ledger history only, not a second obligation or duplicate task.

No new browser injection or permission endpoint. A separate --synthetic-only launcher
serves the unchanged I4b UI/API over the original I2 boundary, processing fixed newly
authored cases at startup and allowing only bounded, named stdin fixture experiments.
The ordinary I3/I4a/I4b launchers remain unchanged.

## Exact input, evidence and Stage A mapping

`Information` contains only three fixed fictional source enums, a bounded `i5-*`
record identity, generation 1–1000, strict Stage A safety/business enums, optional
T1 Step (`school-session` / `home-visit`), an optional fictional date with an
independent date-basis enum, fixed fixture origin and exact internal rule version.
There are no subjects, senders, bodies, URLs, model responses, arbitrary metadata
or free-text task titles. The fingerprint is computed from the finite evidence;
the intent additionally binds source, record, generation, rule and origin. An offer
expiry or unverified date **never** becomes a task date, including on mixed messages.

Stage A remains unchanged and pure. Its Access/Household/Source/Item placeholders
only allow exercising the pure routing function; **they do not map identities or
permissions into the actual database**. No Stage A Decision, simulated acceptance,
Stage B detector or Stage C state is imported as authoritative state. The current
Unmapped Stage A destinations (including `SIMULATED_ACCEPTED`) explicitly raise the
safe input error; simulated authority never becomes a T1 acceptance.
Stage A contract version is checked, so a future change requires explicit I5 review.

| Current independent evidence | Processing destination | New T1 Pending |
| --- | --- | --- |
| Safe-to-route + supported business action + supported Step + preapproved publisher | `pending` | Supported action / mixed-service; still requires T1 current access and explicit confirmation |
| Safe-to-route + conflicting/unsupported action, important service, or unknown obligation | `pending` | Non-acceptable question; no guessed Step/date |
| Supported business but missing Step / publisher plan | `pending` | Non-acceptable question, or blocked if no permitted reader |
| Independently important service overlapping promotion | `pending` | Service question or supported service; advertising urgency grants nothing |
| Ordinary promotion, even expired | `promotion` | None, no task/alert; Offers remains unconnected |
| Ordinary no-action information | `information` | None; no usable information archive is claimed |
| Suspicious / high-risk | `security-held` | None; ledger inspection only, no quarantine or detector claim |
| Unknown / stale / unavailable safety | `unassessed` | None; no implicit clearance |
| No usable business evidence | `abstained` | None |

All eight newly authored named inputs are recorded in the ledger. Five generate
new Pending rows: supported school, uncertain question, independently important
mixed-service question, Clara-private visit and Devon-private visit. Promotion,
risk and ordinary information have **no Pending or Task row**. No automatic Task
is created by this producer. T1 creates one only on the original human ACCEPT path.
Only the two existing neutral Step labels are displayed; rich case descriptions,
routing reasons, audit ledger and security results are not new browser projections.

## Independent fictional preapproval

The trusted initializer configures sources before any processing. All are provider
`fixture`; the coordinator refuses another provider or household. The public I4b
browser has no route for initialization, input submission, processing, grants or
ledger inspection. Ordinary I3/I4a/I4b startup does not import or run I5.

| Source / record | Source observation + security | Pending readers / reviewers | Pending publishers | Neutral Task recipients |
| --- | --- | --- | --- | --- |
| Shared school | Clara + Devon | Both | Clara only | Both (read/edit/history) |
| Shared uncertain / mixed-service | Both | Both | None | None |
| Clara-private visit | Clara only | Clara only | Clara only | Both, separately preapproved |
| Devon-private visit | Devon only | Devon only | Devon only | Both, separately preapproved |
| Promotion / risk / information | Shared fixture source, independently configured | No Pending grants materialized | None | None |
| 14 newly authored pagination cases | Both | Both | Clara only | Both, separately preapproved |

Source, Pending read, review, publish and post-accept Task access are different gates.
A source grant or household membership does not imply publishing authority. A source
observation-only reader receives no risk value and cannot accept without security
scope. Independently supported business fields are retained when existing evidence
becomes unsafe; acceptance is separately blocked by T1 current safety/permissions.
The revision is an opaque exact-evidence version, not a disclosed risk assertion.

Every creation or ordinary update requires current epoch-1 planned members and **at
least one** independently authorized source-observation reader. ANY-reader is
intentional: Clara's revocation must not block Devon's independently authorized
processing. The fixed plan separately preapproves Pending/publication rights; these
are materialized only when the Pending is first inserted, including a planned peer
who may currently lack source access. Such rights alone reveal nothing: T1 rechecks
that peer's own current source access before every Pending read/preview/acceptance.
A later independently approved source grant may enable access to an existing Pending,
subject to current evidence/safety, membership and Pending rights. The producer never
issues that grant. This is a fixed two-adult lab preapproval, not implicit consent
from household membership, and does not require identical source permissions.

Later processing never rewrites source grants, Pending rights or publication plans,
and cannot regrant a revoked permission. Re-enrollment
fails the pinned epoch. A changed preapproval hash conflicts rather than silently
rebasing an existing record. Actual authenticated producer/grant-management authority
is not implemented or inferred from this fixture-only configuration.

## Transaction, history and recovery boundaries

A stable Pending ID hashes **household + source + record**, never title similarity.
Each processing generation is a separate append-only ledger row. Exactly repeated
inputs return their historical producer receipt; they never resurrect a withdrawn
or accepted item. A conflicting same-generation intent, generation gap, missing
producer history, or inconsistent materialized Pending evidence fails closed.

The same household transaction lock orders human ACCEPT and producer updates:
acceptance either commits first and later processing is history-only, or the producer
advances the Pending revision and the old acceptance becomes stale. Rights remain
independent. Review/defer annotations and Task events are never overwritten; exact
evidence matching prevents an old annotation becoming current after a revert.

For an existing **unaccepted** Pending:

- Fresh evidence updates its generation/fingerprint/definition and increments its CAS
  revision. Same-content revert still requires a new generation and confirmation.
- If readiness fails (including all source readers revoked), normal business
  materialization is **blocked**. An existing unresolved Pending receives only a
  restricted invalidation: advance generation/fingerprint/definition and CAS revision,
  set safety to `unknown`, retain its prior business fields. No kind, step, date,
  recipients or permissions are imported from the blocked input. The ledger records
  `effect=blocked` with the exact existing Pending link in the same transaction.
  This is invalidation, not authorized normal processing or a new safety evaluation.
  With no prior Pending, blocked processing creates only a ledger row with no link.
- Regranting source access cannot restore the previous clearance or old preview:
  generation 1 safe → revoke all → generation 2 blocked/unknown → regrant remains
  non-acceptable. Exact generation-2 replay stays blocked. Only a new, currently
  authorized generation can rematerialize fields, followed by fresh human confirmation.
  Blocked generations are included in exact materialization-binding checks, so repeated
  blocks and later lawful updates preserve ledger/Pending continuity. Accepted Tasks
  remain on their independent history-only path, even after all source readers revoke.
- A new promotional/informational result retains the row/history under its matching
  existing T1 kind, which the current ordinary Pending query excludes.
- A newly unknown/unsafe assessment retains the previously materialized neutral
  business record, with current unknown/high-risk safety and **no acceptance**. It
  does not add a new risky proposal or pretend to implement a Security interface.
- The private ledger retains the exact routing destination. No fabricated security
  counts, notifications, archive or Offers data are added to the household UI.

For an **accepted** Pending, subsequent evidence is recorded only in the producer
ledger. The original Pending, Task, accepted evidence binding and human audit stay
unchanged. The item is never reopened as a new obligation. Whether later evidence
requires a separate obligation, task freshness warning, reassessment or resolution
needs a future approved identity/lifecycle contract; this prototype does not guess.

Any ambiguous producer commit returns `UNKNOWN`; this coordinator fences subsequent
processing. Exact `verify()` uses a fresh same-primary connection and the same intent
and preapproval. Supported verification configurations are the owned **file-backed
SQLite** and standard PostgreSQL test engines. `pool.recreate()` preserves the original
connection creator (including PostgreSQL schema options); a separate pool opens a new
DBAPI connection to the same authoritative database, with the original execution
options. Tests hold an original connection open and verify distinct connection identity,
same PostgreSQL schema / SQLite foreign-key enforcement, and the matching durable
receipt. In-memory/empty SQLite and SQLite memory URI configurations explicitly remain
UNKNOWN without opening an alternate database. No replica, custom connection-routing
or production engine configuration is certified by this fixture test.
A durable ledger receipt can establish COMMITTED; absent/unavailable
records remain UNKNOWN, never guessed NOT_APPLIED. An unavailable verifier cannot
clear the fence. There is no automatic replay, rebase or background retry.

The fence is **not a durable production dispatcher**. Do not replace/restart a
coordinator against the same DB after an unresolved outcome. While producer uncertainty is unresolved, do not restore access and continue the lab
as if invalidation had succeeded. The supplied launcher
uses an owned disposable DB and instructs stopping that lab on uncertainty. A future
resumable producer requires separately reviewed durable intent/execution gates.
Browser ACCEPT/EDIT continues to use the existing T1/I4b exact receipt, CAS, retired
write gate and UNKNOWN recovery. If a changed kind/current access prevents historical
receipt verification, it stays UNKNOWN rather than bypassing current authorization.

The migration adds only the ledger (`f52b8c730ed4`, parent `e41a9b720dc3`). Its downgrade
removes only producer history. A later upgrade cannot reconstruct that history from
an existing Pending; processing rejects such an orphan rather than resetting it.
Upgrade/downgrade/upgrade tests compare all existing tables and check Alembic metadata
agreement. No actual user database migration/reset is performed by this work.

SQLite/PostgreSQL ordering is inherited from `authorization_transaction`, not a
process-local mutex. Tests exercise duplicate/conflicting producer submissions and
producer versus human ACCEPT on the real engines. A returned read is not a permanent
authorization lease; existing response-dispatch/cross-port Cookie limitations remain.

## Browser data flow and validation

```text
Explicit I5 --synthetic-only → owned disposable migrated database
→ independent fixed source/grant/plan initialization
→ terminal `process` supplies the eight bounded invented Information values
→ unchanged Stage A pure routing (no authority) + I5 coordination transaction
→ ledger + authorized T1 Pending/right/publication materialization
→ ordinary I4b same-origin Cookie API → current SessionService/T1 read
→ existing Pending page + A1 authorized summary
→ server-held ACCEPT preview → Cancel (no write) / explicit human confirmation
→ T1 CAS + human audit + one Task + independent task grants
→ original fresh task query, responsibility filters and EDIT/UNKNOWN mechanisms
```

There are **no new HTTP routes, response fields, client fixture lists or UI templates**.
Host/Origin/CSRF/CSP, HttpOnly Cookies, field allowlists, query limits, polling and
fail-closed clearing are unchanged. Private source existence, rows, counts and reasons
are never taken from the unfiltered producer ledger for a household response.

Automated I5 tests cover the finite routing matrix, strict input/date roles, separate
permissions, private source changes, source/member revocation, no regrant, publication,
real database idempotency/concurrency, stale/change-revert, accepted history, preapproval
conflicts, transaction rollback/acknowledgment loss, exact UNKNOWN checks, migration
preservation and import/runtime isolation. Three older static guards now permit only
the exact new fictional coordinator; their production/network/secret checks remain.
The new guard also rejects any production import of this module and has a strict
AST dependency allowlist. No provider/source payloads or frozen evaluation sets are read.

The actual-origin browser suite uses two independently approved sessions, 24 peer /
language / theme / width combinations (1440/390/320) and 13 pipeline/safety checks.
Inputs are processed by the actual coordinator, never inserted in frontend HTML/JS.
It covers fresh Pending, cancel/confirm, evidence updates, shared assignment/filters,
UNKNOWN reload recovery, private source revocation, >12 generated Pending, malformed
and failed network responses, keyboard dismissal and safe clearing. Existing I3,
I4a, I4b, A1 and responsibility-filter browser suites remain required. Actual test
counts, SQLite/PostgreSQL CI and final HEAD are reported on the PR.

## Actual connected screenshots

| State | Browser-rendered evidence |
| --- | --- |
| Before feeding I5 | [Clara Home, 1440](screenshots/i5-information/before-process-1440.png) |
| Generated Pending, Clara Chinese Light | [1440](screenshots/i5-information/pending-clara-zh-CN-light-1440.png) / [390](screenshots/i5-information/pending-clara-zh-CN-light-390.png) / [320](screenshots/i5-information/pending-clara-zh-CN-light-320.png) |
| Generated Pending, Devon English Dark | [1440](screenshots/i5-information/pending-devon-en-US-dark-1440.png) / [390](screenshots/i5-information/pending-devon-en-US-dark-390.png) / [320](screenshots/i5-information/pending-devon-en-US-dark-320.png) |
| Original human confirmation | [Preview](screenshots/i5-information/school-confirm-1440.png) |
| Accepted shared Task | [Clara Home](screenshots/i5-information/accepted-home-clara-1440.png) / [Devon phone](screenshots/i5-information/accepted-home-devon-320.png) |
| Assignment changed, readership retained | [Clara Other](screenshots/i5-information/assigned-devon-clara-other.png) |
| Regrant after blocked high-risk generation, no acceptance until fresh evidence | [Clara](screenshots/i5-information/regranted-blocked-generation.png) |
| Revoked shared source, own private Pending remains | [Devon](screenshots/i5-information/source-revoked-devon-pending.png) |

All are the genuine I4b server with disposable SQL, not the independent UX2 preview.
Only existing neutral descriptions are exposed; the UI is not a rich mail inbox,
archive, security detector or source-evidence viewer. Owner Windows verification is
still required for native controls, actual fonts, zoom, keyboard/touch and profile use.

## Independent-review follow-up

The update-after-revocation regression was first run against the reviewed head and
failed: generation 2 returned `updated` instead of `blocked`. The correction adds 18
pytest cases (112 I5 cases in total), covering restricted invalidation, regrant without
clearance revival, one-reader independence, exact blocked/rejected ledger continuity,
accepted Task independence, rollback/commit-acknowledgment loss, explicit unmapped
routing rejection and supported independent database verification. The actual-origin
browser suite now passes 24 layout combinations and 14 pipeline/safety checks,
including the all-revoked → high-risk → regranted → fresh-generation sequence.
Full SQLite/PostgreSQL results and exact final-head CI links are recorded in the PR.

No UI, API, migration or permission model changes are included in this follow-up.
Windows layout acceptance does not need to be repeated wholesale; the owner should
repeat the ordinary process → change → revert → fresh confirmation smoke flow.
The all-reader revoke/regrant scenario is driven only by the isolated automated test
host, not a new browser or product-terminal grant-management interface. ChatGPT and
Muse re-review and human-controlled Windows acceptance remain required.

## Windows PowerShell — independent I5 lab

From the existing repository root. This command never discovers a runtime DB,
connects an account, changes OAuth or invokes a model.

```powershell
git fetch origin
if ($LASTEXITCODE -ne 0) { throw '获取失败，请停止。' }
git switch feat/i5-fictional-information-to-pending
if ($LASTEXITCODE -ne 0) { throw '请先保存本地修改，不要强制覆盖。' }
git pull --ff-only origin feat/i5-fictional-information-to-pending
if ($LASTEXITCODE -ne 0) { throw '更新失败，请停止。' }
if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败。' }
}
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw '项目安装失败。' }
.\.venv\Scripts\python.exe -u .\prototypes\i5-workbench\serve_information.py --synthetic-only
```

1. Open the printed 127.0.0.1 URL, request a session, match the public ID in the
   terminal and enter `approve REQUEST_ID clara`. Use an independent Chrome/Edge
   **profile** for Devon and `approve REQUEST_ID devon`. No member selector/token input.
2. Observe the unchanged baseline (Clara 3 Tasks / 4 Pending; Devon 2 / 4). In the
   startup terminal enter `process`. Eight fixed fictional inputs are conservatively
   routed; five Pending are actually persisted, **zero Tasks automatically accepted**.
3. Reload each Home/Pending page. Each adult has four newly visible Pending, but
   different private visits. School dated **2040-09-18** is a new generated suggestion;
   Clara can preview/accept it, Devon can only inspect. Mixed/uncertain questions
   cannot be accepted. Promotions/risk/information have no new ordinary Pending.
4. Clara: preview the dated school suggestion, cancel, check Tasks unchanged. Preview
   again and explicitly confirm: exactly one shared Task appears; the Pending leaves
   the unresolved page. Both adults see the same task. Assign Devon with independent
   confirmation; Clara still sees it in All/Other and Devon sees it in Mine.
5. `repeat` processes the same identities/generations without duplicates or resurrecting
   accepted items. `pages` supplies 14 preapproved new inputs to test actual pagination.
6. To inspect change/revert **before accepting school**, enter `change`, reread Pending:
   safety is unavailable and acceptance is blocked. Enter `revert`, reread: generation
   3 needs a fresh explicit preview; an old confirmation is never restored. If already
   accepted, these commands record history only and never modify/recreate the task.
7. Check Chinese/English, Light/Dark/system, 1440/390/320 and keyboard/zoom. No dates or
   promotions are invented for Home. Security/Offers remain honestly unconnected.
8. If a Task outcome is UNKNOWN use the existing original-operation check, not a new
   submit. If producer processing becomes uncertain, stop this disposable lab; do not
   restart/rebase against that database. `quit`, EOF or Ctrl+C cleans only its owned
   temporary resources. Session/runtime limits remain I2's 600 / 1800 seconds.

Automated reproduction with the existing approved local Playwright/browser setup:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_i5_information.py tests/test_migrations.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
$env:I4B_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I4B_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node .\tests\browser\i5-information.js --synthetic-only --screenshots
```

## Remaining approval gates

This proves only the fictional pipeline, **not classification quality or real-mail
readiness**. Real producer trust/consent, evidence discovery, actual classifier
calibration, durable producer delivery/unknown recovery, independently revised plans,
post-accept evidence warnings/new obligation identity, historical receipt access,
security projection and ordinary information/Offers archives remain separate work.
No real providers, real login, new task text/types, cross-source dedupe, automatic
Task acceptance, notification, mailbox operation or production deployment is enabled.
Keep the PR open for independent ChatGPT review and owner Windows acceptance.
