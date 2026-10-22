# I9 — Smart Personal Action Home

Product contract v1.0; internal read DTO `i9-personal-action-home-v1`.
This is an opt-in **fictional localhost** extension of I8, not production login,
mail analysis, a new task lifecycle, or a source of permission. Finance is unchanged.
The fetched implementation base is merged I8 `0d31513e2cbeedd004338e2a37b1c074d904893a`.

## One authoritative read

`TaskService.action_home(bearer)` reuses `_transaction`, SessionService validation,
`_task_query`, `_pending_query` and the existing minimized domain projections.
It never calls `harness_context`, creates grants, or edits a Command fingerprint.

Within one existing household authorization transaction:

1. Validate the session, binding and current membership.
2. Apply independent current Task readership or Pending/source observation rights.
3. For Pending, additionally require current source security-read, `safety=clear`,
   unresolved resolution and own `can_review`. Existing kinds restrict results to
   action/question/independently important mixed service; ordinary ads and information
   never qualify. No private risk field affects an observation-only reader's Home.
4. Apply each region's predicates; count the **whole authorized query**, not a page.
5. Sort in SQL, then select at most three rows per region.
6. Minimize fields. Session activity is touched as in existing T1 reads. **No domain
   event, Pending/right, publication or Task is written by Home/navigation/detail.**

| Region | Exact predicate after authorization | Card explanation codes |
| --- | --- | --- |
| My confirmed tasks / 我的已确认待办 | Unfinished Task, actor solely assigned or joint | `my-task`, `joint-task` |
| For my decision / 待我确认 | Eligible Pending, effective own disposition active, viewed or unviewed | `undecided`, `viewed-undecided` |
| Follow-up / 后续跟进 | Eligible Pending, own deferred or needs-information | `deferred`, `needs-information` |
| Household collaboration / 家庭协作 | Unfinished Task, another person solely assigned | `other-task` |

Top counts are the first three regions' **full qualifying totals**. Region counts
include all qualifying rows even beyond 20; only the first three are displayed.
The four sets are disjoint. A shared Task is one Task, never one per recipient.
Completed Tasks are absent. Accepted Pending is absent even if its stored personal
annotation remains active. A Task's assignment does not change its readership.

I8's current-evidence projection is unchanged: REVIEW or NOT_APPLICABLE proves own
viewing at the exact generation/fingerprint/definition. Active + viewed remains a
question requiring a decision. Not-applicable is excluded only from Home, remains
in Pending All / Not applicable, and RESUME preserves valid viewing. Change/revert
cannot revive old annotations. Other people's private decisions/reasons never enter
this projection.

A clear-security **question with conflicting business/action evidence** may need
human review and can be shown as a question; that is not an acceptability claim.
Its existing `can_accept` remains false. High-risk/unknown or missing-security-scope
Pending is omitted from Home, **not deleted or silently resolved**; existing Pending
All and independent security boundaries remain. No new safety detector, freshness
clock, real-world risk accuracy or automatic task acceptance is claimed. Current
producer evidence invalidation remains the T1/I5 contract.

Published Tasks deliberately do not join private sources or Pending. They describe
human-confirmed household tracking, not current source safety or proof of payment,
booking or external completion. Source revocation does not revoke independent Task
publication. Current Task-grant or membership revocation does remove them.

## Dates and consistency

Tasks use `approved_date`; Pending uses its structured `supported_date`. No item date
is called a deadline. Null dates sort last and display “日期未提供 / Date not provided”.
Date ascending is followed, for Pending, by viewed=false before viewed=true, then
stable ID. Task ties use stable ID. There is no score, inferred urgency or AI summary.
Cards use only existing neutral Step descriptions and finite state explanations.

All four counts and samples share the existing database ordering contract: SQLite
`BEGIN IMMEDIATE`; PostgreSQL READ COMMITTED with the household row lock. Conforming
internal writers use the same lock. A concurrent revoke orders before or after the
whole Home read, not between its count and sample. Tests use both engines' real
transactions. This is **not** protection against out-of-contract direct SQL writers,
network dispatch races, or recall of information already returned before revocation.
There is no reusable client cache or permission lease.

## Local API and browser data flow

Only `prototypes/i9-workbench/serve_home.py --synthetic-only` adds:

```text
GET /api/action-home              # no query, body, or caller identity field
HttpOnly Cookie -> existing I2 lease -> T1 current session/membership/grants
 -> one action_home transaction -> strict explicit JSON -> Home renderer
```

The original I2 Host, Origin, Fetch Metadata, Cookie, CSRF, CSP, loopback and resource
limits apply. Headers require Accept application/json and X-Samas-Intent local-session.
Unknown/duplicate/encoded query parameters, bodies and POST are rejected. No CORS or
provider access is added. Canonical ASCII JSON is capped at the existing 16 KiB.

Envelope: `{schema, synthetic_only, member, sections}`; sections are exactly
`mine`, `decisions`, `followup`, `collaboration`, each `{total, items}`. Each card is
`{reason, item}`. `member` comes from the validated transaction and must match the
current browser session check; it is never an authority input.

Task items retain only I4b's `id, step, assignee, status, approved_date, revision,
can_edit`. Pending items retain I8's `id, revision, step, supported_date, can_accept,
can_review, can_resume, reviewed, disposition`. No source identity/content, raw
security assertion, binding, rights revision, audit history or personal reason is
serialized. Browser validation rejects extra fields, wrong member/version, illegal
state/reason/region, duplicate IDs, inconsistent counts, invalid dates and wrong order.
No new write API exists; all I3–I8 endpoints/allowlists remain as before.

The I9 runner serves the existing I4b application, not another task system. Small
optional hooks in shared `workbench.js` require the I9 runner's explicit HTML marker.
Missing I9 JavaScript fails closed with an error; it cannot fall back to the older
sampled A1 Home. Earlier runners never receive that marker or asset.
Task and Pending details reuse existing editing/explanation modules. Follow-up opens
the existing personal handling panel, with Back to details. Opening any panel is not
confirmation. Original previews, CAS, receipts, replay and UNKNOWN reconciliation
remain independent and unchanged.

“View all household tasks” opens the **existing Tasks All** list, and “View all
Pending” opens **Pending All**, resetting its personal filter. These destination
lists are intentionally broader than Home (including completed Tasks, not-applicable
Pending and independently authorized uncertain questions); their own counts/filters
are not presented as section pagination. Home's totals always retain their narrower
meaning. Task-list responsibility filtering cannot change Home.

Every card click first re-reads Home and verifies the current request sequence and
member before opening the existing flow. Five-second background checks preserve
unchanged DOM/focus. During a check, action-navigation controls announce busy/disabled
and cannot open old cards. Any failure clears cards, counts and details; no zero
substitution or offline fixture fallback. Late responses cannot replace newer
navigation/session results. Details leaving the bounded sample close conservatively,
even if they might remain authorized elsewhere. Already returned responses cannot
be recalled; detection remains bounded by polling/request timeouts.

## Windows dual-member acceptance

Use a clean, separate review clone. This creates only an owned temporary fictional
DB, never discovers an existing runtime database. Python 3.12 and Git are required.
Run this in a new PowerShell terminal:

```powershell
$i9Review = Join-Path $env:TEMP ("samas-i9-" + [guid]::NewGuid().ToString("N"))
git clone --single-branch --branch feat/stage-i9-smart-personal-action-home https://github.com/samas-saigo/family-os.git $i9Review
Set-Location $i9Review
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
& .\.venv\Scripts\python.exe -m pip install --no-deps -e .
& .\.venv\Scripts\python.exe -u prototypes\i9-workbench\serve_home.py --synthetic-only
```

In a second PowerShell terminal, open two independent Edge profiles (Chrome's
`chrome.exe` can replace `msedge.exe`). Paste the exact loopback URL printed above:

```powershell
$i9Origin = Read-Host "Paste the printed http://127.0.0.1:PORT/ URL"
$i9Clara = Join-Path $env:TEMP ("samas-i9-clara-" + [guid]::NewGuid().ToString("N"))
$i9Devon = Join-Path $env:TEMP ("samas-i9-devon-" + [guid]::NewGuid().ToString("N"))
Start-Process msedge.exe -ArgumentList "--user-data-dir=`"$i9Clara`" --no-first-run $i9Origin"
Start-Process msedge.exe -ArgumentList "--user-data-dir=`"$i9Devon`" --no-first-run $i9Origin"
```

1. Request a session in each browser; match the displayed request IDs in the server
   terminal and enter `approve REQUEST_ID clara` / `approve REQUEST_ID devon`.
   This is fictional terminal approval, **not** authentication against hostile callers.
2. Enter `process` in the server terminal to process the fixed approved I5 inputs.
   Refresh Home; compare current-member counts, private-source differences, three-card
   limits and all four regions. Empty regions are honest; no decorative fake numbers.
3. Review a school question: it remains in For my decision. Defer / Need information
   moves only your state to Follow-up. Not applicable hides it only from your Home;
   find it in Pending All / Not applicable, Resume and check it returns as viewed.
4. Separately accept the school proposal through the original preview/confirmation.
   It disappears from Pending regions, appears once as a shared Task. Assign Devon:
   Clara sees it in Collaboration; Devon sees it in My confirmed tasks. Both retain
   their original Task readership. Complete/reopen through the original confirmation.
5. Before accepting another supported case, use `change` / `revert` for the school
   input: unknown evidence must disappear from ordinary Home, and the new generation
   must not revive old viewing/disposition. For an already accepted Task, its neutral
   publication remains independent; no second Task appears.
6. Check 中文/English, Settings → Appearance, keyboard/Escape, 1440/390/320 widths,
   first-card visibility, unchanged polling focus and narrow-screen buttons. Close the
   service during a read: old cards/counts/details disappear with a connection error.
7. Enter `quit` (or Ctrl+C/EOF) to stop and clean up the owned DB. Sessions expire
   after the existing 600-second lab lease; pairing is two minutes, at most eight
   starts, total runtime 30 minutes. Restart only as a new disposable test, not as
   recovery/retry for an UNKNOWN write.

The `file://` offline prototype and earlier I3–I8 runners remain independent. I2's
HTTP-loopback Secure Cookie browser exception and **same-host cross-port Cookie
risk** remain; run no untrusted local web service alongside it. Windows direct
browser behavior remains an owner manual gate. No production use is approved.

## Validation and evidence

- Focused SQL/API/DTO tests cover two-person privacy, exact-evidence I8 state,
  >20 records (27 Tasks and Pending), date/viewed/ID ordering, unsafe/advertising
  omission, independent source/task grants, membership/session denial, read-only
  domain snapshots, strict requests, old I8 isolation and ordered revoke/read.
- Actual Chromium uses the I9 server and disposable SQL state, not the visual
  proposal: both peers × two languages × two themes × 1440/390/320, plus review,
  not-applicable/resume, follow-up, independent accept/edit, keyboard, polling,
  revoked grants, malformed responses, failure, logout and late-response checks.
- [Clara desktop Light](screenshots/i9-personal-action-home/clara-zh-CN-light-1440.png),
  [Dark](screenshots/i9-personal-action-home/clara-zh-CN-dark-1440.png),
  [390](screenshots/i9-personal-action-home/clara-zh-CN-light-390.png),
  [320](screenshots/i9-personal-action-home/clara-zh-CN-light-320.png).
- [Devon English Dark desktop](screenshots/i9-personal-action-home/devon-en-US-dark-1440.png),
  [390](screenshots/i9-personal-action-home/devon-en-US-dark-390.png),
  [320](screenshots/i9-personal-action-home/devon-en-US-dark-320.png),
  [Follow-up state](screenshots/i9-personal-action-home/clara-followup-zh-CN-light-1440.png).

Commands used (full results and exact CI runs are recorded in the PR):

```bash
.venv/bin/python -m pytest -q tests/test_i9_action_home.py tests/test_i9_workbench.py
node tests/browser/i9-contract.test.js
NODE_PATH=/opt/codex/runtimes/cua/lib/node_modules node tests/browser/i9-action-home.js --synthetic-only --screenshots
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
git diff --check
```

All original I3–I8/A1/responsibility browser regressions are also run. GitHub's
SQLite and PostgreSQL 16 push/PR jobs execute the complete pytest suite, including
existing migration/metadata/frozen fingerprint compatibility tests. No migration,
real data access, model call, provider operation, new authentication or external
execution is introduced. Independent ChatGPT and Muse review plus Windows
owner acceptance and human-controlled merge remain required.
