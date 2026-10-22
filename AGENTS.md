# Family OS development rules

Read README.md and docs/architecture.md, data-model.md, dedupe.md, security.md,
and roadmap.md before implementation. Preserve these architectural documents;
propose changes with reasons before rewriting them.

- Multi-client by design: one authoritative household backend/core serves desktop,
  web, and mobile clients; the CLI is the current operator/dev surface.
- Core/domain/provider logic must not depend on CLI/UI formatting or callbacks.
  Preserve API-ready logical service boundaries without choosing a framework early.
- Keep provider credentials in the provider-connection boundary, outside
  client-facing state; provider OAuth is separate from future Family OS client auth.
- Preserve centralized R0–R3 policy across clients and shared household state.
- A person is not a source account. Support multiple accounts and shared accounts.
- Keep raw source records separate from normalized records and canonical entities.
- Preserve provider identity and fact provenance. Ingestion must be idempotent.
- Finance remains its own source of truth.
- Read-only by default. No automatic email, calendar, file, or financial writes.
- Never commit secrets, OAuth tokens, personal configs, or household databases.
- Current scope: read-only ingestion infrastructure, merged Gmail (Phase 2A), and
  merged Outlook Mail.ReadBasic for signed-in own mailboxes (Phase 2B), and
  Google Calendar read-only discovery/events (Phase 2C / Issue #6), and Google Drive
  metadata-only with exactly drive.metadata.readonly (Phase 2D / Issue #10). No Drive
  contents/exports, automatic Shared Drive crawling, paths, production AI, UI,
  shared/delegated Exchange mailboxes, email bodies, Calendar descriptions/attachments,
  recurrence expansion, canonical dedupe/lifecycle, or provider writes.
- Routine provider ingestion/recovery uses callable `family_os.services` (Phase 2E /
  Issue #12); CLI owns presentation, services own loaded-client cleanup. Preserve
  provider-specific policies/cursors/OAuth and changed-state Google keyring saves.
- Phase 2F / Issue #14 adds local, model-neutral versioned source analysis only.
  Keep exact raw-snapshot provenance, immutable definitions, stale-input protection
  and zero-egress analyzer contracts; no external inference, canonical/review/task layers.
- Phase 2G / Issue #16 adds conservative local metadata rules and explicit domain
  abstention. Keep inference pure, versions content-sensitive and CLI aggregate-only;
  no content/model access, structured facts, canonical/review/task layers.
- Run relevant tests after meaningful changes. Use focused commits on a feature branch.
- Summarize decisions and unresolved questions for the ChatGPT reviewer.
