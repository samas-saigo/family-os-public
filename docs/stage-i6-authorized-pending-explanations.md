# I6 — authorized fictional Pending evidence and explanation

Base: merged I5 / PR #94, `19aa0fe9f2c2ed0abb2fe64f68536c43db24ba1e`.
Contract: `i6-pending-explanation-v1`. **Fictional local testing only.**

## Implemented scope and architecture decision

The existing Calm Premium I4b application gains a separate opt-in I6 runner and one
read-only explanation endpoint. It uses the current T1 Pending and I5 ledger, not a
second proposal, task, classifier, permission store or source of truth. No migration
is necessary: the ledger already contains the finite structural evidence and exact
Pending reference needed to explain an I5 generation. No notification contents,
sender, school name, address, obligation text or confidence is invented.

The newly authored bilingual explanation templates describe the approved I5 fictional
inputs. Additional adversarial tests invent missing-step and changed/blocked cases;
no private data or frozen Development/Holdout samples are read or reused.

The only T1 refactor extracts the **unchanged** PendingView/candidate predicate into
`_pending_view`, shared by list and explanation under the existing transaction. The
I4b presentation gains optional Pending-details/preview callbacks and exposes its existing
`openPending` UI operation to that callback. Default I3/I4a/I4b/I5 assets and behavior
remain unchanged; only the I6 runner loads the new script and permits the new API.
The I4a receipt coordinator's original preview preparation is extracted unchanged
into a shared helper; I6 adds an expected-revision check before issuing a receipt.

I6 uses the existing opaque `i5_` Pending-ID namespace only to choose the explanation
presentation for already authorized list rows. This is a feature-routing hint, **not
source identity, evidence, authorization or acceptance**. Older I3/I4a fixture proposals
retain their original preview flow; I6 does not pretend they have I5 evidence. The
backend independently checks T1 authority and exact ledger links for every ID, even a
forged `i5_` identifier. No missing/stale I5 explanation falls back to a confirmation.

## Data and trust flow

```text
--synthetic-only → original owned disposable I2 database
→ original trusted fictional pairing + HttpOnly Cookie
→ original T1 authorized Pending list / counts
→ Details → I6 GET, expected exact Pending revision
→ T1 transaction: current session/binding/membership/source observation/Pending read
→ exact current I5 ledger/Pending binding + scope-specific business validation
→ explicit bounded JSON → finite bilingual explanation
→ optional “查看接受预览 / Review acceptance preview”
→ ORIGINAL I4b/T1 preview → independent confirmation → CAS/receipt/audit/UNKNOWN
→ ORIGINAL fresh Task read; no evidence copied into neutral Tasks
```

The central server decides access. Neither the resource ID, browser member display,
source owner, task assignee nor a candidate flag grants authority. No new grant,
producer, initialization, model or provider route exists. Ordinary promotions,
information and new security-held records still produce no ordinary Pending.

## Exact API and field whitelist

Only I6 accepts `GET /api/pending/explanation?id=ID&revision=N`.

I6 also requires `{id, revision}` on its existing `POST /api/pending/preview`:
T1 prepares the original command, and the shared coordinator rejects a mismatch
before issuing a receipt. The browser independently rejects a preview revision
different from the displayed row. This prevents an old explanation silently becoming
a newer preview between poll cycles. Original I4a/I4b still accept their original
`{id}` shape; no accept/edit/outcome route or command is changed. This binding is not
proof that a human read/understood the explanation, and creates no new authority.

- Exactly two unique parameters, lowercase bounded ID and canonical integer 1–1,000,000.
  Query length ≤100; reject empty/unknown/duplicate/percent-encoded parameters.
- Same original loopback Host/Origin, Fetch Metadata, Cookie, custom-header and CSP
  controls. Exact JSON Accept; empty request body; no transfer/content encodings,
  caller identity/forwarding headers, arbitrary bearer or CORS.
- Canonical ASCII JSON, ≤4 KiB. No-store headers inherited from I2. All denied,
  missing, withdrawn, stale or inconsistent requests use the same existing generic
  400/error body, without a source-specific reason or existence signal.

| Field | Meaning / origin |
| --- | --- |
| schema, synthetic_only | Exact I6 contract and true |
| id, revision | Existing authorized Pending and expected current CAS revision |
| generation, definition | Exact current I5/Pending binding; opaque version, not a risk assertion |
| source_kind | Fixed `structured-fictional-input`, never a provider/account/owner claim |
| step, supported_date | Current authorized materialized T1 fields; null remains unknown |
| action | Finite supported/conflicting/unsupported/none; unavailable for blocked materialization |
| reasons | One bounded business reason: structured-support, conflicting-action-evidence, missing-action-step, insufficient-action-evidence, independent-service-only, current-evidence-unavailable |
| safety | Current T1 clear/high-risk/unknown **only with security scope**, otherwise null |
| can_accept | Existing T1 candidate flag, permits requesting preview only; never write authority |

No raw ledger, source/record IDs, fingerprints, plan hashes, free text, internal grants,
private annotation/history, session secret or provider metadata is serialized. There
is no explanation collection or count through which hidden sources could appear.

## Authorization, consistency and field scopes

The explanation service uses the original T1 `_transaction` and `_pending` lookup.
Current session/binding/member, source observations **and** independent Pending read
are required before any ledger lookup, JSON parsing, binding validation or error.
Accepted proposals are rejected; Task read permission never enables this endpoint.
Independent source/task grants and two-peer household collaboration remain unchanged.

The ledger record's stable household/source/record identity must derive the exact
Pending ID; it cannot alias another record. The latest linked ledger must match its
exact generation, fingerprint and definition, with the approved fixture origin and
created/updated/blocked materialization effect. No historical substitute is used.
Business fields are finite and checked against the materialized step/date.

Security is a separate field scope. T1's authorized CASE supplies current safety.
The service parses the private internal ledger container only after source/Pending
authorization, discards security before validating the observation-only business
subset, and never emits that container. Observation-only results and validation do
not depend on the ledger's private safety value (including missing/invalid safety).
With security permission, full fingerprint and safety consistency are also checked;
inconsistent authorized assertions fail closed rather than choosing clearance.
Opaque stored binding equality is required for everyone; an incoherent generation
is unavailable, not a disclosed explanation of what private field changed.

An I5 blocked generation withheld new business materialization. Its explanation
therefore uses **only** the retained T1 step/date and a recheck reason, with action
unavailable. It never reinterprets the blocked payload as a current supported action
or displays its private incoming risk. Security readers see the materialized unknown
state; observation-only readers receive null. Source regrant does not revive acceptance;
a currently authorized new generation and fresh confirmation are still necessary.

Source grants do not imply publication, security or task rights. A fixed independently
preapproved neutral Task may later be shared, but source evidence, raw IDs, safety and
explanation are never copied into Task fields, details or history. Assignment does not
expand source access. Important mixed service/promotion questions explain only the
independent service concern; offer expiry is not a task date or household obligation.

## Product experience and invalidation

Cards stay compact; I6 Details has “发生了什么 / What happened”, “判断依据 / Basis for
the suggestion”, and “下一步 / Next step”. Input markers, the system's conservative
interpretation, unknown facts and human action are distinct. Unknown dates remain
unknown. Reading, Close, Escape, navigation, theme/language changes and failed reads
save no domain decision. Session activity is maintained by the existing read service.

Eligible suggestions offer a **separate preview**, not immediate acceptance. Questions,
conflicts, unknown/high-risk safety or observation-only readers get no executable
acceptance. The original shared unresolved-write gate and UNKNOWN recovery remain
in force; explanation is never permission to bypass them. Completion still means
tracking only; no booking, payment, mail or calendar operation is performed.

Each response is checked against its requested Pending ID/revision, current inspection,
request sequence and session/UI epoch. Dismissal/reset invalidates pending responses
and clears DOM identifiers and retained evidence references. This is not secure JavaScript memory erasure or
recall of already delivered bytes. Newer reads or another inspected
item reject late results. No localStorage/sessionStorage, reusable evidence cache or
browser task model is introduced. Accepted shared Tasks use the original neutral UI.

Every normal background revalidation also re-reads an open explanation. An unchanged
success leaves the dialog and focused Close button mounted; a changed version/scope,
failed read, removed row, logout or invalid session clears the old explanation.
Explicit reload/navigation/language switching closes unconfirmed details. A → B → A
advances generations and cannot restore an earlier preview or explanation.

### Limits honestly retained

Reads use existing SQLite BEGIN IMMEDIATE / PostgreSQL household-lock ordering.
Returned bytes cannot be recalled. Five-second polling and five-second requests,
including the original sequential Home reads, bound discovery rather than guarantee
instant revocation. A response authorized before a revoke may already be in transit;
known invalidation prevents its later restoration. No production cache/dispatch or
arbitrary same-member Cookie swap guarantee is claimed.

I2's cross-port Cookie / HTTP-loopback / trusted-local-process restrictions remain:
use only fictional data, independent trusted browser profiles and no untrusted local
services. There is no real OIDC login, enrolled household, production server, credential
migration, real-mail pilot, AI/model call or external operation. The I5 producer fence
remains in-process; unresolved uncertainty requires stopping the disposable lab.

## Windows PowerShell and two-profile acceptance

From the repository root with Python 3.12 and the existing project environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Editable installation failed.' }
.\.venv\Scripts\python.exe -u .\prototypes\i6-workbench\serve_explanations.py --synthetic-only
```

Do not run migrations/OAuth against a runtime DB. This launcher owns and removes its
own temporary DB and ignores the real runtime URL. Open the printed loopback URL in
two independent Chrome/Edge profiles (two windows sharing Cookies are not two people).

1. Request access in profile A; match the public request number in the terminal and
   enter `approve REQUEST_ID clara`. In profile B independently approve `devon`.
2. Enter `process` in the terminal. Existing I5 inputs create Pending, never Tasks.
   Open Pending: Clara's private visit is absent for Devon, and vice versa.
3. Clara opens the I5 school suggestion: structured support and 2040-09-18, no invented
   body/sender/urgency. Close/Escape leaves task count unchanged. Reopen → acceptance
   preview → Cancel; reopen again and explicitly confirm. One shared T1 Task results.
4. Open the conflicting question and mixed service question. Inspect explanations;
   neither offers executable acceptance. No promotions or new security-held items
   enter ordinary Pending. Unknown dates stay unknown.
5. Clara may accept her private visit under its independent plan. Devon sees the
   neutral shared Task, never the private Pending or its evidence via that Task.
   Repeat the privacy check in the reverse direction before accepting Devon's visit.
6. On a **fresh lab / before school acceptance**, use `change` while its explanation
   is open: the old detail closes and acceptance is unavailable. `revert` advances to
   generation 3; obtain a fresh preview/confirmation, never reuse the old one.
7. Check Chinese/English, Light/Dark, desktop/390/320, keyboard focus, scrolling and
   full Close/preview controls. UNKNOWN uses original “核对最近操作”, no resubmit.
8. `quit`, EOF or Ctrl+C stops only the owned lab. Later reads clear old contents.
   Restart creates a new fictional DB, not recovered household history.

Full revoke/regrant, malformed/late responses and scope changes are controlled only by
the isolated automated test host; no browser/product grant-management route is added.
Windows native Cookie/control/font/zoom and separate-profile checks remain human gates.

## Validation and review evidence

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_i6_explanations.py tests/test_i5_information.py tests/test_household_tasks.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
$env:I4B_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I4B_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node .\tests\browser\i6-explanations.js --synthetic-only --screenshots
```

Backend tests exercise actual owned SQLite/isolated PostgreSQL schemas: authority
before ledger SQL, scope-specific private safety, precise current bindings, blocked
and reverted generations, independent neutral Tasks, missing/conflicting/service
questions, strict routes/requests, default-adapter isolation and no inspection writes.
The Node contract suite checks malformed/extra/duplicate/oversized fields and bilingual
parity. Actual-browser tests cover two peers, 24 language/theme/width combinations,
separate preview/Cancel/confirmation, permission/version changes, late responses,
timeout/failure clearing, pairing/logout, UNKNOWN and original-request recovery.
Original I3/I4a/I4b/I5, A1 and responsibility-filter browser regressions remain required.
Exact final SQLite/PostgreSQL counts and CI links are recorded in the PR, not inferred
from predecessor CI. No existing security assertion is removed or skipped.

Screenshots below come from the actual I6 runner over disposable T1 SQL, not a static
UX2 design preview. All text/evidence is controlled fiction.

| Actual state | Screenshot |
| --- | --- |
| Clara Chinese Light school explanation | [1440](screenshots/i6-explanations/clara-zh-CN-light-1440.png) / [390](screenshots/i6-explanations/clara-zh-CN-light-390.png) / [320](screenshots/i6-explanations/clara-zh-CN-light-320.png) |
| Devon English Dark private visit | [1440](screenshots/i6-explanations/devon-en-US-dark-1440.png) / [390](screenshots/i6-explanations/devon-en-US-dark-390.png) / [320](screenshots/i6-explanations/devon-en-US-dark-320.png) |
| Conflicting evidence | [Desktop](screenshots/i6-explanations/conflicting-evidence.png) |
| Regrant after blocked generation | [Desktop](screenshots/i6-explanations/blocked-after-regrant.png) |

ChatGPT/Muse should independently inspect field-level scope validation, exact
ledger/Pending binding, stale/late-response clearing, the presentation-only I5 namespace
hint, unchanged default adapters, independent Task publication and the preserved
receipt/UNKNOWN gate. Production source descriptions, richer evidence, real producer
identity, disclosure/retention and authentication need separate approval.
