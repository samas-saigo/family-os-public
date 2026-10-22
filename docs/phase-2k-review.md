# Phase 2K — AI-assisted classification architecture and privacy decision

Issue #34 is a documentation-only decision checkpoint. It authorizes no model calls,
installation, data upload, content access, rule/threshold change or runtime change.
The recommendation below is a staged design for review, not consent to implement it.
It builds on [analysis/provenance](phase-2f-review.md), [conservative rules](phase-2g-review.md),
[human evaluation](phase-2h-review.md), [coverage diagnostics](phase-2i-review.md) and
[terminal review](phase-2j-review.md), under the existing [architecture](architecture.md)
and [security boundaries](security.md).

## Decision and evidence

Keep the versioned rules as the zero-egress baseline. Next, specify and test a
metadata-only reasoning adapter on synthetic inputs, then benchmark an explicitly
approved local model on the user's hardware. If that is feasible, evaluate a bounded
local hybrid in shadow mode before proposing production use. Cloud reasoning is an
optional later branch requiring a separate signed-off transfer contract; it is never
an automatic fallback. Do not loosen thresholds to make coverage look better.

Issue #34 reports 1,000 analyzed records with domain abstention/review, and a separate
1,000-record diverse dry-run cohort with no strong matches. These are operator-reported
aggregate observations, not data inspected for this decision. Neither cohort is a
random household sample; a few saved labels cannot estimate quality or train ML.
Narrow phrase coverage, language/taxonomy gaps and missing evidence are competing
explanations. A more capable model cannot recover facts absent from metadata.

The goal is useful automatic understanding with review of important exceptions,
not manually labeling thousands of records. Start with a small diagnostic labeled
sample and stop expanding it unless the findings justify the effort.

## Options and decision matrix

| Approach | Likely value and limitations | Privacy | Cost / latency / maintenance | Decision gate |
| --- | --- | --- | --- | --- |
| Versioned rules / better phrases | Explainable, reproducible precision for narrow signals; weak multilingual/context coverage; more rules can conflict | Zero egress with current pure matcher | Cheapest compute; fast; growing rules require regression fixtures and version bumps | Add only independently justified rules from local error analysis in a separate issue; retain abstention |
| Traditional local ML, e.g. token features + linear model | Cheap inference and measurable scores after calibration; needs diverse decisive labels; tiny current sample is inadequate | Local features/model weights can retain private vocabulary; protect artifacts and backups | Training/feature maintenance and drift checks; usually CPU-friendly; labels are the main cost | Sufficient labels per target plus held-out temporal/account testing; never train on evaluation holdout |
| Local LLM | Potentially better paraphrase/language triage without training labels; still hallucinates, misses evidence and varies with quantization | No inference egress only if runtime/telemetry/update/tool access are contained | Hardware/model/license/storage burden; potentially seconds per record or slower on CPU; benchmark rather than assume | Explicit installation approval, supported hardware and resource/quality benchmark |
| Cloud LLM | Potentially strong language handling and low local hardware demand; quality remains empirical; vendor drift/outages | Sensitive subject/title/sender transfer to another trust boundary; opt-in mandatory | Metered tokens, network delay, quotas, retention/vendor dependency | Approved provider/region/retention and exact field/account/budget contract **before transmission** |
| Hybrid cascade | Rules for supported dimensions, authorized model for bounded ambiguous cases, then abstain/review; avoids calling a model for everything | Local by default; no cloud fallback without distinct authorization | Routing/version/evaluation complexity; savings depend on observed ambiguity, currently potentially almost all records | Compare against unchanged baseline on the same snapshots; disagreement must not silently become certainty |

For scale only: 4-bit weights require roughly `parameters × 0.5 bytes`, so a 3B model
has about 1.5 GB of weights and a 7B model about 3.5 GB. Runtime, KV cache, tokenizer,
context and OS add memory, sometimes substantially; these are not RAM/VRAM minimums
or laptop compatibility claims. Measure available RAM/VRAM, CPU/GPU support, disk,
power/thermal impact, cold load and p50/p95 latency on the actual device. At measured
2 s/item, 1,000 items take about 33 minutes serially; at 10 s/item, about 167 minutes.
Batching/concurrency and background execution are not authorized by this checkpoint.

## Exact input boundaries

`AnalysisInput` remains the internal frozen persisted source projection. A model gets
an explicitly built **smaller** `metadata_only_v1` projection, never its full
serialization. The following is the proposed local reasoning maximum, not an enabled
cloud transfer policy. Unavailable fields are omitted, never fetched or fabricated.

| Field | Source and bound | Proposed model use |
| --- | --- | --- |
| `provider`, `record_type` | Persisted identifiers from supported source types | Context, not proof of relevance |
| `subject` | Persisted Gmail/Outlook subject, Calendar summary or Drive filename; at most 8,192 characters | Untrusted sensitive text; no body, preview or content substitution |
| `sender` | Persisted message sender, at most 320 characters | Local-only maximum; exclude from default cloud proposal |
| `occurred_at` | Persisted UTC provenance timestamp or absent | Not Calendar start, ingestion time, deadline or proof of a current obligation |
| `raw_metadata.status`, `raw_metadata.eventType`, `raw_metadata.mimeType` | Exact persisted strings, each at most 256 characters | Context only |
| `raw_metadata.start.dateTime`, `raw_metadata.start.date`, `raw_metadata.end.dateTime`, `raw_metadata.end.date` | Exact persisted strings, each at most 256 characters | Calendar event context; no date invention |
| `raw_metadata.trashed`, `raw_metadata.removed` | Persisted booleans only | Preserve trash versus stream removal; neither proves canonical deletion |

No arbitrary metadata traversal or minimized-header bundle is allowed: any future
additional header must be enumerated and reviewed separately. Exclude recipients,
owner/person/household/account IDs, provider object/source/raw IDs, raw payload,
permissions, resource keys, links, OAuth/keyring/credential state, cursors, model
secrets and financial account/transaction data. Provenance IDs stay inside Family OS;
use an ephemeral request correlation handle outside it. Existing internal fingerprints
still bind the full `AnalysisInput`; do not replace them with an outbound hash.

A potential cloud `metadata_only_v1` proposal permits only the table's fields **except
sender**. No cloud bytes are authorized now. Sender/domain inclusion, even derived
from sender, requires a revised field contract and consent. Subjects, filenames and
event summaries may themselves contain PII, health details, secrets, addresses or
embedded URLs. Dropping names/IDs or pseudonymizing them does not reliably anonymize
context. No URL is followed; secret detection/redaction is defense in depth, not a
promise of safe disclosure. The user must approve the remaining sensitive text risk.

Future adapters enforce types, the above bounds, a fixed total/token input budget
and field allowlists before invocation. Oversized input becomes a safe rejection or
abstention, not silent truncation into a confident positive. No provider fetch is used
to fill missing metadata. The local audit display allowlist remains unchanged.

**Content extraction is a separate decision:** Gmail bodies/snippets, Outlook
bodies/previews, Calendar descriptions/attachments, Drive download/export/document
contents, OCR and attachment processing remain excluded. Any expansion needs explicit
source/account/field consent, least-privilege provider-scope review, retention/egress
policy, new projection/output contracts and evaluation. Metadata reasoning does not
implicitly authorize structured facts, canonical dedupe, a review queue or actions.
Finance remains its financial source of truth; `finance_reference` classifies notices.

## Versioned model contract and service compatibility

Reuse `Analyzer.name`, `Analyzer.version` and
`analyze(AnalysisInput, ClassificationPolicy) -> AnalysisOutput`. A future adapter
owns projection and bounded inference; it has no provider client, cursor or DB access.
The core does not import a vendor SDK or depend on CLI callbacks. A hosted model
transport belongs behind a consent/credential boundary in the authoritative core,
not independently in web/mobile/desktop clients. No HTTP endpoint is designed here.

A proposed immutable definition manifest includes model artifact digest or pinned
vendor revision, runtime/tokenizer/quantization version, projection schema, prompt
and output-schema digests, decoding settings/seed, routing/rules fingerprints and
score/calibration policy. Canonicalize/hash the manifest into an effective analyzer
version within the existing 64-character limit; keep the nonsecret manifest locally
for audit. Any meaningful change creates a new version. Mutable vendor aliases with
undetectable changes are unsuitable for claiming exact replay. Repeatability must be
measured; temperature zero/seed alone does not guarantee determinism.

Output contains only the existing enum labels, a valid taxonomy category/child or
null/null domain abstention, finite bounded scores and **zero facts for the initial
spike**. Self-reported LLM confidence is not calibrated probability; document/version
its mapping and keep outputs review-only until held-out evidence supports promotion.
For the initial uncalibrated spike, map model confidences to 0.0 as an explicit
unknown-strength sentinel, not a probability; the unchanged 0.80 classification
thresholds therefore recommend review even for complete concrete proposals. Do not
relax thresholds or override stored flags to promote them. A later score mapping
requires a new manifest/version and held-out evaluation. Existing validation, safe
errors and review signals remain authoritative. Future fact extraction would require bounded resolvable refs to fields actually provided,
never evidence quoted from reasoning or invented body/file text. Classification does
not currently store per-dimension evidence refs; `analysis_fact` refs do not justify
adding narrative reasoning or trivial copied facts to classification.

Run through `analyze_source` / bounded `analyze_pending`, never a new direct-write
path: capture exact current raw ID/full input fingerprint, check reuse, release DB
connection, infer and validate, then household/writer → source → definition → exact
analysis → inserts. Stale input writes zero rows. Household definition consistency,
idempotency and concurrent duplicate convergence are unchanged. Identical keys reuse
an existing artifact without inference; changed definitions append new analysis
history. Replaying a stored result is not rerunning a stochastic model. Historical
inference must not be rebuilt from today's source fields; exact historical projection
reconstruction would need separate design, not an assumption about raw payloads.

Human revisions remain append-only and attached to their original analysis. Existing
Phase 2H–2J default audit/metrics/review explicitly load `MetadataRulesAnalyzer`; they
**cannot already evaluate an arbitrary model**. A future comparison helper must select
an explicit exact analyzer/taxonomy/threshold definition and current snapshot. Compare
baseline and candidate only on identical source/raw pairs and compatible taxonomy;
read the latest human revision as an explicit evaluation reference without copying or
retargeting labels to another analysis. Missing/current-ineligible pairs are reported,
not replaced with historical predictions. Any such helper is future implementation.

## Proposed local evaluation, not a production accuracy claim

1. Start with about **120 locally inspected records**, in sessions of 10–15:
   80 recent provider/type-balanced cases, 20 deliberate negative/ambiguous/high-impact
   challenges, and 20 historical cases in a separate time window. Include Gmail,
   Calendar and Drive; Outlook if present. Use existing Phase 2I diagnostics and
   Phase 2J explicit UTC windows, never leading source IDs or SQL random selection.
   Record selection/window/snapshot/definition locally so candidates see the same
   cohort. Existing occurrence-time semantics remain; inspect event start separately.
2. Include marketing, receipts, travel, account alerts, generic events, empty filenames,
   multilingual/negated subjects, cancellations and conflicts. Seek missed actionable
   billing/renewal/booking notices as well as confident false positives. A notice
   claiming fraud/payment does not prove fraud, debt, legitimacy or an obligation;
   historical, already-paid or canceled notices must not become current tasks.
3. Human labels use only visible minimized evidence, never AI as the gold labeler.
   Unknown/uncertain is valid. Locally diagnose absent content, unsupported wording,
   work/household ambiguity and taxonomy mismatch separately; do not force a domain.
   Keep that discussion local; current label rows gain no notes/reviewer identity.
4. Before tuning, separate 40 development cases from 80 frozen evaluation cases,
   retaining provider/time/challenge slices. Keep related threads/duplicates out of
   opposite splits. If a snapshot changes, report ineligible and explicitly refresh;
   never silently reuse its label. Do not train traditional ML on this tiny set or
   reuse the holdout for prompt/rule tuning; obtain a fresh small holdout after tuning.

This is judgmentally stratified inspection, not prevalence sampling. Stop or narrow
scope if decisive labels are too scarce. A provider/domain with no decisive support
has no measured quality. Report denominators and uncertainty; zero errors in a small
sample is not proof of safety (roughly, zero errors in 30 independent trials still
allows an error rate near 10% at 95% confidence, and these samples are not independent).

Report the existing latest-revision metrics separately from proposed comparison metrics:

- Per-provider/domain coverage, abstention and review volume; human unknown/uncertain,
  unlabeled and classifier abstention remain distinct. Zero denominators are null.
- Selective precision for concrete relevant/irrelevant and action-required claims;
  false-positive action count/rate on decisive labels, including any accepted dangerous
  overclaim. Accuracy must not conceal low coverage.
- Missed action-required count: decisive human `required` with predicted uncertain or
  `not_required`, with high-impact cases inspected locally as a separate challenge slice.
  No product priority/task inference is added. Report recall on that labeled slice only.
- Domain selective correctness includes category **and child**, not category alone;
  separate historical from recent errors and missing-content from taxonomy issues.
- Compared-to-baseline paired counts, p50/p95/cold-start latency, repeat-run disagreement,
  memory, processed/rejected counts, bytes leaving the process/device, and metered cost.

Existing metrics do not emit every proposed miss/latency/comparison measure. The
follow-on helper must define these explicitly; do not present them as current CLI
features. Threshold simulation remains pure counterfactual review/acceptance counts,
not changes to stored flags, labels or config. Favor reduced important misses at
measured precision over broad guesses or simply accepting more predictions.

## Threat model and controls required before external inference

All controls below are **future implementation requirements**, not protections added
by this documentation or an authorization to send data.

| Threat / failure | Required control and fail-safe |
| --- | --- |
| Subject/filename prompt injection or malicious provider text | Delimit data from instructions; no tools, browsing, code execution, retrieval or remote URL following; constrained output plus independent validation; injection challenge tests |
| Plausible invented obligation, fraud, deadline or entity | Valid enums/abstention; review-only proposals, explicit human evaluation; no source hiding/deletion, tasks, canonical truth or provider writes from unverified predictions |
| Unauthorized egress / cross-household mixing | Default off; household **and exact source-account** opt-in; field/purpose/model allowlist checked before each request; no mixed-household prompts; authorization independent of provider OAuth |
| Secret/text leakage via telemetry, logs or provider errors | Disable SDK traces/body logs, prompt caches and crash payload capture; fixed safe errors; allowlisted aggregate timing/token/error categories only; no subjects, sender, private URLs, tokens or raw output |
| Vendor training/retention, subcontractors, jurisdiction | Approve concrete provider/model/region/subprocessors and verifiable no-training/retention terms; disclose abuse/security retention exceptions; block if policy cannot be met |
| Unbounded spend, outage or hidden remote fallback | Per-record token caps; per-run/day/account/household spend and call limits; finite timeouts/retries with charged retries counted; budget exhaustion stops or abstains; no automatic cloud/provider fallback |
| Compromised credentials/model package or local telemetry | Separate model secret boundary from provider keyrings, restricted backend service access, rotation/revocation; verify local model artifacts/license and contain runtime egress; no client token distribution |
| Model drift / silent config change | Pinned manifests/effective versions, challenge regressions and held-out gate; changed version appends history; local rollback selects prior definition rather than overwriting rows |

Before a real-data external request, the user must approve a readable transfer record:
provider/model/revision, destination/region, exact fields/bounds/redaction limitations,
purpose, household/accounts and permitted record/date budget, retention/training and
subprocessor terms, access controls, pricing/caps, error/log policy, fallback and
revocation/deletion procedure. Opt-out takes effect before the next dispatch; recheck
after queuing, never broaden to another account. An in-flight accepted request cannot
be recalled: disclose that revocation prevents future sends, not retroactive receipt.
Future authenticated household/person roles must decide who may grant/revoke consent;
passing a household ID or owning a provider connection is not authorization. At the
current local stage a deliberate operator approval is still required, not implied
by CLI access or Google/Microsoft OAuth.

Default retention proposal: prompts/raw responses only in bounded process memory,
no disk transcript/cache, no chain-of-thought. Retain validated structured analyses
and their versions/provenance under the existing immutable local history contract.
Retain a minimal content-free local dispatch audit (consent version, internal safe IDs,
model/definition, time, permitted field names, token/cost counts and outcome) under an
explicit retention/access policy. Future deletion must distinguish local source and
analysis history/backups from vendor copies, respect provenance, and require separate
design; do not promise current automatic deletion or removal of already sent bytes.
A vendor unable to meet approved retention/deletion terms is a no-go.

Cost estimate, not a vendor quote: for `N` eligible items, routed fraction `p`, average
input/output tokens `I`/`O`, prices per million tokens `Pi`/`Po`, expected bill is
`N × p × (I × Pi + O × Po) / 1,000,000`, plus charged retries/minimums if applicable.
With 1,000 candidate items at `p=1`, `I=600`, `O=100`, that is `0.6Pi + 0.1Po`.
The current high abstention means a cascade may route almost everything; do not assume
large savings. Approve numeric currency caps once pricing is known; reserve worst-case
request cost before dispatch so concurrent accounting cannot overspend. No billing
numbers, egress budget or implementation is approved in this PR.

Centralized R0–R3 remains authoritative. A metadata read is not permission to disclose
it to a vendor. Analysis/evaluation are distinct from structured extraction, entity
resolution/dedupe, product review queue, suggested tasks and write execution. This
checkpoint creates none of them. Future clients submit authorized decisions to the
one backend/core; they do not run independent models, hold provider/model credentials,
or establish separate canonical/task state.

## Next issue: bounded offline synthetic metadata reasoning spike

Proposed Phase 2L scope: versioned projection/manifest/output contract, fake model
transport, local synthetic comparison runner and adversarial fixtures. No production
command, default classifier switch, external SDK/call, private data, provider/scope
access, schema change, extraction/facts, task or canonical layer. An optional real
local-model benchmark is a distinct approval gate after hardware/license checks;
installation is not implicit in this recommendation. A subsequent controlled local
shadow evaluation on the user's machine is a separate authorized step.

Acceptance / go-no-go criteria for that future issue:

1. Same runtime analyzer/validator in spike and evaluation; bounded allowlisted inputs,
   strict schema/enum/null-pair validation and empty facts. Version changes for every
   manifest change; exact-key reuse, stale zero writes and household serialization
   remain covered by synthetic SQLite/PostgreSQL tests if persistence is exercised.
2. Synthetic fixtures span all current providers, missing/redacted evidence, conflicts,
   multilingual text, negation, historical/canceled records and malicious instructions.
   No network/tools/keyring/raw-payload access; no prompts/output/secrets in logs.
3. Comparison explicitly binds candidate definition, snapshot and latest human reference;
   no default audit behavior changes or relabeling. Synthetic results are not a claim
   of household accuracy. Fake-model success alone proves plumbing, not model quality.
4. For an approved local benchmark, publish measured resources/latency and repeat-run
   variability, not assumed device support. All unsupported/oversized/timeout cases
   must reject or abstain without inventing certainty; dangerous challenge overclaims
   block progression until resolved and retested.
5. Agree resource/time limits and target precision/missed-action tradeoff **before**
   inspecting held-out real results. Progress only to local review-only shadow use if
   it improves supported coverage or important misses without observed precision
   regression; insufficient decisive sample means inconclusive, not pass. No claim
   of auto-processing readiness from the small set, and no task automation gate here.

Open user decisions before implementation: acceptable local versus cloud processing;
OS/hardware and install/license/resource limits; languages and household-versus-work
interpretation; evaluation effort and harm priorities; whether sender is necessary;
any future content scope; and, only if cloud is proposed, concrete provider/region,
consent authority/accounts, exact transfer/retention terms and numeric cost caps.
Approving this architecture does not approve those implementation or egress decisions.

## Validation and ChatGPT review questions

This PR changes four Markdown files only. Relative file/fragment link checks and
`git diff --check` passed. Issue #34 requires no runtime test suite for this
documentation checkpoint; none was run locally. Existing
Phase 2F–2J code/config/schema/CLI/dependencies/CI remain unchanged. No real database,
provider, OAuth or model was accessed. Documentation checks are not validation of a
model's quality, a device's suitability or an external provider's terms.

1. Is the local-first staged hybrid justified by narrow evidence without claiming
   that cloud/local LLMs can solve missing content or sparse labels?
2. Are proposed metadata fields/bounds and excluded content exact, and external egress
   gated separately from OAuth and from architecture approval?
3. Does manifest versioning fit immutable snapshot/definition/idempotency semantics,
   with honest replay limits and explicit future evaluation-helper work?
4. Are high-impact false positives/misses, ambiguity, strata and denominators addressed
   without pretending 120 judgmentally selected labels are production statistics?
5. Are consent/revocation, prompt-injection, logging, retention/deletion and spend controls
   concrete enough to block unsafe future adapters while preserving one backend/R0–R3?
6. Is the proposed synthetic spike bounded enough, with hardware and user approvals
   still open and content/canonical/review-queue/task/API/worker work deferred?
