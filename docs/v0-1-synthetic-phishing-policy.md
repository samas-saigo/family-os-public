# Family OS v0.1 / Stage B — synthetic phishing policy evaluation

## Scope and evidence contract

Implements only Stage B of [Slice 3](v0-1-action-first-routing-email-safety.md#staged-follow-up-and-unresolved-decisions),
following the unchanged [Stage A contract](v0-1-synthetic-routing-contract.md).
Policy `synthetic-phishing-policy-v1`; corpus `synthetic-phishing-corpus-v1`.
Two private modules contain pure standard-library value objects, policy/simulators,
and a separate corpus/aggregate evaluator. There is no CLI, database, production
service, detector, provider, network, model or UI connection. No Stage C is started.

All evidence is newly invented enum-only synthetic input, **not observed mail**.
Nothing reads real household data, private human labels, Finance or frozen
Development/Holdout. No actual subjects, URLs, attachments, HTML, instructions or
headers are accepted. No URL fetch, redirect, attachment opening, HTML rendering,
OAuth, AI/LLM/Ollama or actual provider operation exists.

Immutable bindings contain fixed source/item surrogates, a generation 1–1,000 and
fixed policy revision. A new episode or reverted evidence must use a new generation.
Claims are unique bounded tuples: claimed school/bank/healthcare identity, urgency,
identity/payment requests, advertising and policy-instruction/injection attempts.
They are **untrusted descriptions**, never commands or verified sender identity.
Authentication pass/fail/unknown, familiarity and prior user release are separate
fields. Authentication success is not benign intent; release/familiarity never
change this or install sender/domain trust. No scores or calibrated confidence exist.

Independent findings are separately supplied: checked-clear (no detected risk, not
a guarantee), validated impersonation, compromised sender, malicious destination
and unresolved anomaly. These enums model hypothetical approved independent checks;
they do not perform verification. Current/missing/stale/unavailable/conflicting
evidence states model limitations. Current Gmail/Outlook metadata does not supply
this full security evidence, and this work authorizes no additional fields/scopes.

## Prospective policy precedence

| Priority | Evidence | Outcome |
| --- | --- | --- |
| 1 | Unknown/denied/revoked/wrong source access | No result, including no existence-bearing reason/count |
| 2 | Binding mismatch or non-current evidence | Indeterminate; no inherited clearance/risk verdict |
| 3 | Checked-clear conflicts with any other independent finding | Indeterminate; disagreement cannot silently clear or quarantine |
| 4 | Current validated impersonation/compromise/malicious destination | Synthetic high-risk regardless of authentication/familiarity/release |
| 5 | Independent anomaly or authentication failure | Suspicious, not proven malicious |
| 6 | Current independent checked-clear | Safe-to-route, not a guarantee or action authority |
| 7 | Unverified urgency/identity/payment/injection claim | Suspicious question, not high-risk proof or instructions to execute |
| 8 | All remaining insufficient evidence | Indeterminate, including an authenticated familiar/released sender |

Checked-clear means the independent synthetic check adequately covered the evidence;
it can coexist with legitimate payment/urgency language. This assumption is tested
with an intentionally false-clear malicious case. The experiment does not establish
how a real check could be trusted. Prompt injection never changes policy or permissions;
no instruction text is interpreted or executed, including after a clear assessment.

## Independent labels and denominators

The separate evaluator holds 29 newly authored probes: **14 malicious, 11 legitimate,
4 truth-unknown**. Ten legitimate cases are independently labeled important. Policy
evaluation receives only binding/evidence/access, never specimen ID, truth or importance
labels. Ground truth is invented scenario intent, not the outcome of this policy.
Deliberate inaccurate findings include a legitimate clinic falsely flagged as
impersonation and a malicious message with a false-clear check. Missing/stale/outage
cases remain in the corpus; labels are not adjusted to manufacture perfect accuracy.

| Metric | Numerator / denominator |
| --- | --- |
| Coverage | Non-indeterminate predictions / all authorized probes (including truth-unknown) |
| False positives | Legitimate probes assessed suspicious/high-risk / all legitimate probes |
| False negatives | Malicious probes assessed safe-to-route / all malicious probes |
| Abstentions | Indeterminate probes, with separate malicious/legitimate counts |
| Important legitimate-mail misses | Important legitimate probes held (suspicious/high-risk) or indeterminate / all important legitimate probes |
| Restore success | Verified simulated restorations / dispatched simulated restore trials; include failed/unknown trials, exclude blocked trials and report them separately |

Error-rate denominators include labeled abstentions; do not misread these as
conditional accuracy among decisions. Report coverage and abstentions alongside rates.
Unknown truth is never labeled correct/incorrect. A malicious abstention is unresolved,
**not a true negative or safe outcome**. Important-mail misses are a routing-delay/hold
proxy in a simulation, not proof an email was lost or a real deadline missed.
Zero denominators return null. Authorized-source filtering happens before aggregate
counts; withheld items have no counter or placeholder. Recovery metrics recheck access.

Collection validation also obeys this boundary: the 64-record cap and specimen
uniqueness apply **only to authorized records**, not the mixed-source input.
Adding inaccessible duplicates or more than 64 inaccessible records cannot change
results or trigger a collection error, including when every source is denied.
The caller must supply a finite, exact tuple of the required immutable value type
and a valid access value; malformed envelopes/untyped objects still fail closed
because they have no validated source binding. The filter makes one finite linear
pass through that tuple and retains at most 64 authorized records. It does not
evaluate hidden evidence or labels. Input traversal time is not a constant-time
side-channel guarantee; future services must enforce their resource bounds after
authorization, without disclosing hidden-record counts or rejection reasons.

Fixed-corpus results: 6 safe-to-route, 6 suspicious, 10 high-risk, 7 indeterminate;
coverage **22/29**; false positives **3/11**; false negatives **1/14**; malicious
abstentions **1/14** and legitimate abstentions **3/11**; important misses **6/10**
(3 held, 3 indeterminate). These intentionally difficult synthetic probes are neither
representative sampling nor evidence of real-world phishing accuracy/readiness.

## Simulated recovery — no mailbox mutation

`quarantine` models a trial only for high-risk, exact binding, current unchanged
provider state, verified retention/recovery records and explicit **simulation** approval.
Every call rechecks these declared gates; uncertainty blocks it. Verified, failed and
unknown observed outcomes stay distinct; queued/unknown is not success. R0–R3 and
per-mailbox consent remain unchanged: an enum called simulation approval grants no
actual consent or write permission.

`restore` needs a verified prior simulated move, a fresh exact binding and the same
retention/access/explicit-approval gates. Later user changes, unknown provider state,
missing recovery basis or stale binding block restoration; nothing guesses a location
or overwrites later labels/moves. A prior unknown/failed move cannot justify undo.
Restore succeeds only on an explicitly verified synthetic outcome; failures/unknowns
are recorded as such. A previous restoration result cannot be blindly retried: further
reconciliation/recovery is outside this one-trial model. Previous values are immutable.

Recovery reports count supplied independent simulated trials, not unique real emails
or a persisted audit ledger. A four-trial test reports one verified, one failed, one
unknown and one blocked restore: success **1/3 dispatched trials**, never 1/4 or 100%.
No simulation changes assessment, source trust, business routing or action authority.
Both assessment and recovery expose immutable false action-authority properties;
recovery provider-write is always false.

## Stage A preservation, tests and commands

Stage A files/tests are untouched. Only test code maps Stage B outcomes onto Stage A
synthetic safety enums; there is no runtime adapter. This verifies unknown safety
abstains, held promotions never surface offers, important uncertain items remain
visible as unresolved holds/questions, and assessments do not create tasks or acceptance.
Unauthorized access remains non-disclosing. Real integration still requires independent
snapshot/policy binding and permission review; these declared synthetic grants are
not authentication or a sandbox against hostile Python code.

Tests cover all independent-finding subsets and orders, freshness/authentication
combinations, simulated gate/observed-outcome combinations, wrong bindings/access,
false-positive recovery, unknown outcomes, exact metrics/nulls and no I/O/production
imports. Only `dataclasses`/`enum` are imported by the policy core. Inputs are bounded
to enum tuple sizes, generations and at most 64 authorized evaluation samples/trials;
authorized specimens must be unique, while recovery trials may repeat.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_phishing_policy.py tests/test_synthetic_routing.py
.\.venv\Scripts\python.exe -c "import json; from family_os import _synthetic_phishing_evaluation as e; print(json.dumps(e.metrics(e.CASES), sort_keys=True))"
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The report command prints aggregates only and accepts no path, URL, database or
household input. Exact focused/full SQLite/PostgreSQL 16 CI counts are recorded in
the PR after actual execution. Existing full-suite tests use disposable synthetic
databases; no household database should be supplied.

Focused validation passed **2,059 tests**: 822 new Stage B cases and all 1,237 retained
Stage A cases. `pip check`, Markdown link/anchor/fence/table checks and
`git diff --check` passed. Head-specific full CI results are recorded in the PR;
these tests establish synthetic contract behavior only.

## Unresolved production decisions and review

No efficacy, automatic-quarantine readiness or real-mail rollout is claimed. Future
independent evidence acquisition, safe parsing, field consent, calibration, important
mail recovery budgets, auth/revocation races, retention revalidation, audit deletion,
provider atomicity, reconciliation and operation-specific R0–R3/write consent remain
separate approvals. No feedback/official-channel registry, scheduler, actual quarantine,
task or Stage C UX is delivered. Real household data must not enter any AI, local or
cloud; synthetic probes grant no exception or expanded provider access.

ChatGPT and independent Muse should check evidence provenance/precedence, label
separation, abstention/error denominators, false-positive recovery, unknown outcomes,
Stage A isolation and scope. Leave the dedicated PR unmerged for human decision.
