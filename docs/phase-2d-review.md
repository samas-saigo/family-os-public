# Phase 2D review handoff — Issue #10

## Scope and architecture

Phase 2D binds registered Google Drive accounts and ingests metadata only with
exactly `https://www.googleapis.com/auth/drive.metadata.readonly`. Metadata gives
provider identity/provenance and future selection/dedupe hints without accepting
the wider content-access boundary. No download/export, `alt=media`, Workspace
content API, write permission or provider mutation exists. `content_hash` stays
null. Content access needs a separate architecture/security decision comparing
broad content scopes, feasible selected-file access, Workspace read scopes, and
hosted verification/security-assessment implications; no option is chosen now.

The merged Issue #8 one-backend/multi-client design is preserved. Connector,
normalization, identity, and recovery logic are independent of CLI presentation.
The explicit connect display callback carries identity presentation only, not policy.
Native keyring remains the local implementation-stage provider credential store,
separate from future client authentication/authorization and client-facing state.
No API, auth service, worker, scheduler, credential migration, schema migration,
canonical document layer, classification/extraction, or UI is added. Existing
Gmail, Outlook, Calendar modules/tests are unchanged.

## Decisions and acceptance evidence

| Issue #10 requirement | Implementation / synthetic evidence |
| --- | --- |
| Explicit account and household ownership | `registry.py` final-state and read guards; Drive tests cover missing/disabled/wrong-provider, duplicates, transactional replacement, multiple people/accounts, cross-provider identity, direct corruption and existing ownership invariants |
| about.user identity binding | Require `me=true`, normalized email and stable permissionId; fake OAuth tests verify email display before save, wrong identity saves nothing, sync re-verifies both fields and rejects switching |
| Exact metadata-only OAuth | Dedicated `google_drive_auth.py`; exact granted scope tests reject broader/additional/missing scopes, including Drive and Workspace content scopes |
| Secure distinct account-scoped storage | Native keyring `family-os/google-drive.metadata.readonly/v1`, household/account key; stable permissionId only in secure envelope; cursor fingerprint; fake tests cover isolation, envelope corruption, backend rejection, silent load and refreshed saves |
| Race-safe personal baseline | Commit start token before files listing, paginate baseline, catch up from captured token; synthetic race/resume tests verify ordering, persistence and final-page adoption |
| Opt-in Shared Drives | Exact-ID policy, paginated read-only discovery without domain admin, independent per-drive token/baseline/change streams; tests cover default no-crawl, inaccessible IDs, new/inactive/reactivated streams, deliberate policy migration, and application-level exclusion of Shared Drive baseline/update/trash/removal observations from personal streams |
| Provider identity and history | File ID scoped by account, rename/move/parent/owner/Drive metadata updates same object, equal names remain distinct; raw history retained, replay idempotent, two accounts retain separate provenance |
| Shortcuts and folder semantics | Actual MIME types, shortcut targetId/targetMimeType metadata only; tests prohibit target fetch/merge/resource keys/path synthesis |
| Trash and sparse removal | Trashed remains current metadata; removed is stream-specific observation; tests retain old raw versions, avoid old-field backfill, cover current-resource removals and prevention of duplicate personal-stream overwrites |
| Metadata privacy and null content hash | Explicit request/persistence allowlists, Drive-specific forbidden-key defense; tests inject excluded nested payloads, verify fixed metadata endpoints/projections and null hashes despite provider checksums |
| Strict cursor and atomic pages | Bound version/account/household/email/binding/policy, stage/discovery/queue validation, duplicate-JSON and token-cycle defenses; tests verify failed pages roll back without advancing state |
| Stream-specific recovery | Typed affected-stream expiry, local validated version/CAS transform, fresh start→baseline→catch-up; tests verify unrelated tokens/history retained, unknown streams and wrong policy rejected |
| Safe diagnostics and CLI | Fake response/refresh/CLI tests cover redaction, sanitized error categories, count-only ingestion and local recovery without provider/OAuth calls |

## Cursor and recovery semantics

The versioned account cursor holds opaque personal and per-Shared-Drive tokens,
selected discovery IDs, active flags, a sequential pending queue, and bounded
10,000-entry page trails. Binding is a non-secret permission-ID fingerprint; actual
account credential binding remains keyring-only. Unexpected policy changes fail
closed. Explicit migration requires the full old/new sets, retains existing stream
state, starts new streams, and inactivates excluded streams without losing history.
Discovery validates configured access each completed sync cycle.

Personal/user and Shared Drive file-observation streams are intentionally disjoint.
Personal baseline files with a non-empty `driveId` are ignored. Personal catch-up
and incremental file changes with Shared Drive IDs in `change.driveId` or returned
`change.file.driveId` are ignored, including updates, trash and sparse removals,
regardless of selection. Selected Shared Drive files persist only through their
dedicated exact-ID stream. No extra file fetch or automatic selection occurs.
Ordinary directly shared items without Shared Drive membership still ingest via
personal streams; directly shared items inside a Shared Drive require explicit
selection of that Drive. Application logic enforces this boundary, independently
of the deprecated `includeItemsFromAllDrives=false` request flag.

Focused regression tests cover unselected baseline files, selected/unselected
catch-up and incremental updates/trash/removals, both Drive-ID field locations,
ordinary personal/directly shared items, no duplicate personal overwrite/raw history,
and legitimate moves between selected Shared Drives under the same file ID.

A stream moves through start-token capture → baseline → catch-up → incremental.
Intermediate change pages do not replace the steady token; only `newStartPageToken`
at completion does. Invalid/expired tokens do not silently jump to now. Personal
and individual Shared Drive reset commands preserve unrelated streams and history,
then re-baseline. Missed provider history beyond Google's retention cannot be
reconstructed. Recovery validates the old cursor; structurally corrupt or differently
bound state needs trusted-state investigation rather than guessed continuation.

## Persisted versus excluded data

Persisted fields are enumerated in [Drive documentation](google-drive.md#metadata-and-provenance):
file ID/name/MIME, returned provenance timestamps, parents/Drive ID, trash/star/shared/
ownership flags, filename/extensions/size/version, provider checksums/headRevisionId,
minimized owners (permissionId/email/displayName/me), shortcut target ID/MIME,
capabilities.canDownload, and stream/removal routing. Optional unreturned fields
remain absent; permissions are never widened for missing fields. Owner permission
IDs in source metadata are not the secure bound-account credential field.

Excluded are content/exports/descriptions, properties/appProperties, permissions/
ACL lists, thumbnails, media metadata, links, resource keys (including shortcut
keys), labels, comments/replies, revisions, arbitrary payloads and credential/token
information. Metadata itself includes sensitive names and owner details: database
access protection and the existing future-backend security boundary remain necessary.

Sparse removal snapshots carry only returned current fields and routing. Shared
Drive observations have no duplicate personal-stream persistence; prior raw
snapshots retain provenance through legitimate moves. Neither trash nor stream
removal asserts canonical deletion. Shortcuts remain independent objects; no canonical dedupe is performed.

## Limits and validation

Full synthetic regression: **537 passed on SQLite and 537 passed on real PostgreSQL
16**, with Python 3.12.14. Of these, **183** are new Drive/OAuth tests; the **354**
existing tests remain unchanged. `pip check` and `git diff --check` pass. GitHub CI
runs the full SQLite/PostgreSQL suite; final CI status is recorded in the PR.
No real OAuth, Drive requests, or mailbox access occurred. The opt-in bounded manual
smoke procedure in `google-drive.md` is documented but not executed.

No incompleteSearch result is accepted. Shared Drive discovery may be costly on
large organizations. `max_pages` includes empty discovery/start pages; per-page
about.user checks add API requests. Authorized requests persist credentials to
keyring. Streams are sequential, so failures block pending work. Page trails are
bounded and cursor state is trusted local/database state, not a signed client token.
No retry scheduler or automatic reset is introduced. Metadata scope availability
of optional revision/checksum/capability fields has only synthetic coverage; missing
returned fields must be omitted, never solved by extra consent.

## Exact ChatGPT review questions

1. Does the exact requested/granted scope validation and fixed endpoint/field
   projection prevent all content/export/Workspace/write access without broadening
   consent for missing optional metadata?
2. Do preregistration, final-state/read duplicate guards, pre-save email display,
   and per-page email plus permissionId checks prevent wrong-account binding or
   silent account switching while preserving multi-person/multi-provider behavior?
3. Is credential/keyring isolation complete, with no secure account permission ID,
   OAuth information or provider credentials entering registry/cursor/client-facing
   state, and with existing silent loads incapable of starting interactive OAuth?
4. Does start-token capture before each baseline, resumable catch-up and final-page
   newStartPageToken adoption close initial race gaps for personal and selected
   Shared Drive streams under atomic/idempotent ingestion?
5. Does application-level Drive-ID filtering make personal and selected Shared
   Drive observations disjoint, including sparse removals and directly shared items
   inside Shared Drives, without relying on request flags? Are discoverability checks,
   explicit old/new policy migration and targeted recovery correct without resetting
   unrelated streams or silently claiming continuity after expired history?
6. Do file-ID identity, parent-ID metadata, independent shortcuts, null content hash
   and omitted-field handling avoid filesystem/canonical-dedupe assumptions and
   reconstructing unavailable private metadata?
7. Are trashed versus removed snapshots and prevention of duplicate personal
   observations clear and safe, preserving raw history without asserting canonical
   deletion or backfilling old fields?
8. Are strict cursor/queue/token-cycle validation, safe diagnostics, metadata
   allowlist defenses and synthetic acceptance coverage sufficient for Phase 2D,
   with the documented content/backend/client milestones still explicitly deferred?
