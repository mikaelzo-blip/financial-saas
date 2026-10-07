---
name: financial-saas-workflow-audit
description: Project-specific active E2E workflow audit for Financial SaaS with mandatory backend trace, accounting verification, workflow registry, and delta-aware revalidation.
version: 3.0.0
platforms: [windows]
metadata:
  hermes:
    category: project-specific
    tags: [financial-saas, workflow, ux, qa, accounting, browser, e2e, graphify, registry]
    related_skills: [dogfood, adversarial-ux-test, impeccable, systematic-debugging]
---

# Financial SaaS Workflow Audit v3

## Scope

Only for:

`C:\Projects\financial-saas`

Install project-locally at:

`C:\Projects\financial-saas\.hermes\skills\financial-saas-workflow-audit\SKILL.md`

Registry:

`C:\Projects\financial-saas\docs\workflows\WORKFLOW_REGISTRY.yaml`

Audit evidence:

`C:\Projects\financial-saas\docs\audits\<RUN_ID>\`

Do not install globally.

## Core model

Every financial workflow is evaluated through:

`Browser → Frontend → API → Auth/Policy → Service → Accounting → Persistence → Journal/Report → Browser`

Evidence priority:

1. actual browser behavior
2. current app/database/accounting result
3. current live source
4. tests/CI
5. Graphify
6. historical registry

If Graphify or the registry disagrees with current live evidence, current live evidence wins.

## Critical rule: scope claims correctly

Never generalize a journey-scoped finding into an application-wide claim.

Allowed:

`No direct AccountingEngine bypass was observed in J1 document-to-journal.`

Not allowed without repository-wide evidence:

`There are no direct AccountingEngine bypasses in the application.`

Every architecture/security/accounting claim must be marked:

- JOURNEY-SCOPED
- MODULE-SCOPED
- APPLICATION-WIDE

Application-wide claims require application-wide evidence.

## Active testing

Default mode:

`ACTIVE TESTING WITH DISPOSABLE TEST DATA`

In local/staging/sandbox environments Hermes should actually use the web app to:

- upload synthetic documents
- exercise OCR
- correct extracted data
- approve
- post
- inspect transaction/journal/report
- pay/receive/reconcile when auditing those journeys
- reverse/void/cancel through supported product flows

A source-only audit cannot be marked FULLY_VERIFIED.

## Environment safety

Preferred:

1. E2E/test tenant
2. local + disposable DB
3. staging + synthetic data
4. sandbox
5. production last

Local/staging/sandbox: automatic synthetic mutations allowed.

Production: browsing allowed, but explicit user approval is required before the first financial mutation.

Use `E2E-TEST-` records and a unique run ID such as `E2E-TEST-YYYYMMDD-HHMM`.

## Workflow Registry

Before every audit read:

`docs/workflows/WORKFLOW_REGISTRY.yaml`

The registry stores only previously proven facts:

- last verified SHA
- last run ID
- environment
- browser path
- backend trace
- accounting contract
- source files
- relevant Graphify paths
- known findings
- evidence
- freshness state

Never write speculative architecture into the registry.

Statuses:

- FULLY_VERIFIED
- PASS_WITH_FRICTION
- PARTIAL
- FAILED
- BLOCKED
- NOT_TESTED
- STALE
- REVALIDATION_REQUIRED

Evidence states:

- OBSERVED_UI
- SOURCE_VERIFIED
- ACCOUNTING_VERIFIED
- CI_VERIFIED
- INFERRED
- NOT_VERIFIED

INFERRED must never be silently promoted to VERIFIED.

## Delta-aware revalidation

Before re-running an existing journey:

1. read `last_verified_sha`
2. get current SHA
3. run `git diff --name-only <last_verified_sha>..<current_sha>`
4. compare changed files against the journey's known:
   - frontend components/API clients
   - backend routes/services/policies
   - accounting services/rules
   - models/migrations
   - reports
   - auth/tenant boundaries
   - tests/contracts
5. use Graphify to inspect impacted relationships
6. verify important Graphify conclusions against live source

### FULL revalidation

Required when relevant changes touch:

- AccountingEngine/posting rules
- reversal/journal logic
- route/service owning the workflow
- auth/tenant policy
- financial state machine
- relevant model/migration
- Git history no longer contains the prior verified SHA

FULL means browser E2E + backend trace + accounting verification + duplicate/error case + UX review.

### TARGETED revalidation

Use when relevant UI/API/report/error-handling/dependency files changed.

Retest only affected steps plus their accounting invariants.

### SMOKE revalidation

Use when code changed elsewhere and the journey's direct/indirect dependencies remain unchanged.

Confirm one critical path and final visible state.

### CURRENT

If current SHA equals last verified SHA and environment/config is materially unchanged, no full repeat is required.

## Automatic staleness

Mark only affected journeys REVALIDATION_REQUIRED when relevant:

- source files change
- migrations change
- auth/tenant policy changes
- API contract changes
- posting/accounting rules change
- report classification changes
- reversal/idempotency changes
- Graphify is stale for relevant files
- framework/runtime configuration materially changes workflow behavior

Do not invalidate every journey because an unrelated file changed.

## Browser-first mandate

For every audited journey:

1. run app
2. navigate with Hermes browser
3. fill actual forms
4. click real actions
5. inspect console
6. capture meaningful screenshots
7. verify resulting app/accounting state

Browser use is mandatory for FULLY_VERIFIED.

## Mandatory backend trace

For EVERY state-changing financial action:

`Browser action → frontend handler → API client → endpoint → auth/authz → policy/review → domain/service → accounting/posting/reversal → models/tables → transaction → journal → report → final UI`

Record:

- browser evidence
- component/handler
- API endpoint/payload
- auth/authz
- policy checks
- service chain
- accounting rule
- affected tables/models
- transaction/journal IDs
- debit/credit
- idempotency
- final UI state

If this trace is incomplete, status is PARTIAL.

## Graphify rules

Use Graphify for cross-file relationships and change-impact analysis.

Known limitation: code-only AST graphs may not encode HTTP network edges from React/API clients to FastAPI routes.

Therefore frontend → HTTP → backend must also be verified through endpoint strings and live source.

If Graphify differs from source: LIVE SOURCE WINS.

## Accounting invariants

For every financial mutation verify:

`Debit == Credit`

Where relevant also verify:

`Assets = Liabilities + Equity`

Special checks:

- AP payment reduces AP and cash/bank without recreating expense
- AR receipt reduces AR and increases cash/bank according to configured rules
- repeated submit/post does not duplicate financial effects
- reversal follows supported compensating/immutable-ledger behavior

Do not directly delete posted journals for cleanup.

## Cleanup

Preferred:

1. supported reversal
2. void/cancel
3. supported deletion of non-posted test records
4. retain clearly tagged E2E data and report it

Cleanup status:

- CLEANED
- REVERSED
- RETAINED_TEST_DATA
- BLOCKED

## Critical journey IDs

- J1 document-to-journal
- J2 duplicate-document-protection
- J3 ap-vendor-payment
- J4 ar-customer-receipt
- J5 bank-reconciliation
- J6 error-recovery
- J7 reporting-traceability
- J8 whatsapp-to-web-review

## UX pass

For each journey record:

- click count
- screens
- time
- manual re-entry
- context switches
- dead ends
- terminology
- confirmations
- error recovery
- next-action clarity

After functional verification, use dogfood, adversarial-ux-test, and impeccable.

Adversarial findings must be filtered as RED / YELLOW / GREEN / WHITE.

## Known issue lifecycle

Stable IDs: `WF-001`, `WF-002`, etc.

Store:

- severity
- status: OPEN / FIXED / ACCEPTED / WONT_FIX / NEEDS_RETEST
- journey
- first_seen_run
- last_seen_run
- evidence
- affected/retest paths

If relevant files change, mark issue NEEDS_RETEST.

Never delete fixed issues from history.

## Initial v3 baseline from verified audit

Baseline:

- Run ID: `E2E-TEST-20260920-1139`
- SHA: `26ab5affee58`
- Branch: `hermes/document-review-simplification-v2`
- Environment: Local Development

Verified:

- J1 document-to-journal: PASS_WITH_FRICTION
- J2 duplicate-document-protection: FULLY_VERIFIED
- J6 error-recovery: PARTIAL
- J7 reporting-traceability: PASS_WITH_FRICTION
- J3 AP payment: NOT_TESTED
- J4 AR receipt: NOT_TESTED
- J5 bank reconciliation: NOT_TESTED
- J8 real WhatsApp transport: NOT_TESTED

J1 baseline accounting:

Vendor bill:
- Dr 5101 Harga Pokok Proyek Rp 5.550.000
- Cr 2101 Utang Usaha Rp 5.550.000

Reversal:
- Dr 2101 Utang Usaha Rp 5.550.000
- Cr 5101 Harga Pokok Proyek Rp 5.550.000
- Net impact Rp 0

Known findings:

- WF-001 HIGH — AMOUNT_MISMATCH requires nominal re-entry
- WF-002 HIGH — raw backend/Pydantic error leaks to UI
- WF-003 MEDIUM — general ledger journal has no transaction drilldown
- WF-004 MEDIUM — Approve → Post two-step flow confuses non-accountants

## Baseline J1 trace

Journey-scoped verified path:

`Document approval → READY_TO_POST → DocumentPostingService → TransactionService.create_transaction → AccountingEngine.post_transaction → journal_entries`

Reversal:

`TransactionDetailPage → POST /transactions/{id}/reverse → ReversalService.reverse_transaction → compensating journal → POSTED → REVERSED`

Duplicate protection:

`upload → SHA-256 → service duplicate check → unique (organization_id, file_hash) → HTTP 409`

These are journey-scoped baseline facts, NOT application-wide guarantees.

## Revalidation triggers for current findings

WF-001: retest if DocumentReviewForm/Page, correction payload, correction backend, or AMOUNT_MISMATCH clearing changes.

WF-002: retest if frontend error mapping, API/Pydantic serialization, or document-review error handling changes.

WF-003: retest if general-ledger UI, journal row rendering, transaction navigation, or report traceability changes.

WF-004: retest if approval CTA, READY_TO_POST UX, posting action, or combined approve/post workflow changes.

## Registry update after each completed audit

After a successful run:

1. preserve history
2. update last verified SHA/run
3. record environment
4. store browser path
5. store backend trace
6. store accounting result
7. store source files
8. store tests/CI evidence
9. store Graphify paths and limitations
10. update findings
11. set freshness
12. save evidence/report path

Never update registry with unverified hypotheses.

## FULLY_VERIFIED gate

Requires:

- real browser path executed
- console checked
- meaningful UI states captured
- backend trace completed
- auth/policy boundary verified
- accounting result verified
- transaction/journal linkage verified
- duplicate/idempotency checked where relevant
- final UI state reconciled
- cleanup documented
- registry updated

Otherwise status cannot exceed PARTIAL or PASS_WITH_FRICTION as appropriate.

## Final report must include

- journey
- revalidation mode
- prior/current SHA
- relevant changed files
- registry freshness
- browser execution
- backend trace
- accounting verification
- UX metrics
- findings
- scope boundary:
  - verified in this journey
  - NOT established application-wide
- cleanup
- registry update
- what was not tested
- final journey status

## Do not auto-fix

Audit first. Report defects. Do not modify application source until user explicitly approves implementation.

## Key principle

Registry remembers what was proven.
Git diff tells what changed.
Graphify shows likely code relationships.
Browser testing proves current user behavior.
Live source proves current implementation.
Accounting verification proves current financial effect.

None replaces the others.
