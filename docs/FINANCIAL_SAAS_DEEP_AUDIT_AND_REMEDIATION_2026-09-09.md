# Financial SaaS — Deep Audit & Remediation Plan

**Repository:** `mikaelzo-blip/financial-saas`  
**Audit date:** 2026-09-09  
**Current GitHub baseline checked:** `62dd6c8bc6afc21c6ff6955c4bab17d1b7b3d319` — `chore(governance): prepare repository for Hermes Coder (#53)`  
**Primary codebase reviewed:** uploaded `financial-saas-main.zip` + key files cross-checked against GitHub `main`  
**Intended operator:** Hermes Coder profile  
**Purpose:** defensive code audit, remediation backlog, and implementation guardrail  
**Status:** review artifact only — **NOT** the source of current repository state and **NOT** a replacement for Spec Kit requirements

---

## 0. Executive Decision

[Certain] **Do not rewrite this application.**

[Certain] The current architecture already contains the right major building blocks:

- FastAPI backend;
- PostgreSQL + Alembic;
- React frontend;
- tenant-aware data model and services;
- deterministic double-entry accounting engine;
- Journal Entry / Journal Line based reporting;
- Accounts Receivable and Accounts Payable;
- project accounting;
- fixed assets;
- accounting periods;
- bank / money-movement reconciliation;
- immutable document intake;
- OCR / document intelligence;
- Review Queue;
- Hermes Runtime integration;
- local WhatsApp/Baileys intake;
- GitHub CI and repository governance.

[Certain] **Do not add new product features before the security and accounting-control boundary is hardened.**

[Certain] The main risk is not missing functionality. The main risk is that several authenticated API paths can currently mutate or post financial truth without consistently enforcing the application's intended role, human-review, accounting-period, and audit controls.

[Likely] For the current single-company, local-first operating model, the application is close to usable after the P0 fixes in this document.

[Likely] For broader multi-user or public SaaS use, P0 and the core P1 items should be completed before production exposure.

### Recommended next feature

```text
011-security-accounting-invariant-hardening
```

[Certain] This should be implemented as a controlled hardening feature using the existing Spec Kit + Hermes Coder workflow, not as one unrestricted refactor.

---

# 1. Audit Scope

## 1.1 Reviewed areas

[Certain] The audit covered:

1. authentication;
2. authorization / RBAC;
3. transaction approval and posting;
4. accounting-period enforcement;
5. Review Queue behavior;
6. reversals;
7. opening balances;
8. AR/AP posting;
9. document approval;
10. fixed assets and depreciation;
11. audit attribution;
12. tenant isolation;
13. uniqueness constraints;
14. sequence / code generation;
15. TransactionType-to-posting-rule contracts;
16. frontend role exposure;
17. browser authentication storage;
18. local WhatsApp and deferred edge relay;
19. CI / test structure;
20. repository governance;
21. integration with the user's Hermes Coder profile.

## 1.2 Evidence standard

[Certain] Findings marked **Confirmed** were observed directly in source code.

[Likely] Findings marked **Risk / Design concern** are strong engineering inferences from the observed implementation but may require runtime/concurrency reproduction before claiming an incident.

[Certain] No finding in this document should be treated as proof that unauthorized activity has actually occurred.

---

# 2. Verification Limitations

[Certain] Static Python compilation was successfully checked with:

```text
python -m compileall -q backend/src
```

[Certain] A complete backend `pytest` run could not be independently reproduced in the audit sandbox because the environment did not contain `asyncpg`.

[Certain] Frontend dependency installation / verification could not be fully reproduced in the sandbox within the available execution environment.

[Certain] `PROJECT_STATUS.md` reports the repository's own latest recorded verification as:

- 393 backend tests passed;
- 3 backend tests skipped;
- 66 frontend tests passed;
- 6 Node bridge/contract tests passed;
- frontend lint completed with pre-existing warnings;
- typecheck passed;
- production build passed;
- dependency and migration checks passed.

[Certain] Those repository-reported test counts are useful evidence, but they are **not independently reproduced by this audit**.

---

# 3. Current Architecture Assessment

| Area | Confidence | Assessment |
|---|---|---:|
| Accounting architecture | [Likely] | 8.5 / 10 |
| Backend modularity | [Likely] | 8 / 10 |
| Test / CI discipline | [Likely] | 9 / 10 |
| Authentication foundation | [Likely] | 8 / 10 |
| Backend RBAC | [Certain] | 4.5 / 10 |
| Financial-control consistency | [Likely] | 6 / 10 |
| Tenant isolation | [Likely] | 7.5 / 10 |
| Frontend completeness | [Likely] | 8 / 10 |
| Owner-focused UX | [Likely] | 7 / 10 |
| Local-first WhatsApp | [Likely] | 8 / 10 |
| Deferred PC-off relay | [Certain] | Do not activate yet |
| Repository governance | [Likely] | 9 / 10 |
| Maintainability | [Likely] | 8 / 10 |

---

# 4. What Is Already Correct

## 4.1 Deterministic accounting is the authority

[Certain] The application correctly separates Hermes/OCR assistance from the authoritative accounting engine.

[Certain] AI is used for extraction, classification, candidate generation, or orchestration; debit/credit generation remains deterministic in backend posting rules.

[Certain] This architecture should be preserved.

## 4.2 Journal-centric reporting

[Certain] Financial reports are built around `JournalEntry` / `JournalLine` rather than treating frontend transaction forms as the financial source of truth.

[Certain] This is the correct direction for maintaining:

```text
Assets = Liabilities + Equity
```

and preserving double-entry behavior.

## 4.3 Review Queue is conceptually correct

[Certain] The codebase already has:

- transaction review flags;
- human-review states;
- reviewer correction flow for documents;
- policy evaluation;
- approval metadata;
- audit services.

[Certain] The problem is **not** the absence of these controls.

[Certain] The problem is that not every mutation/posting path is forced through them.

## 4.4 Production configuration is fail-closed in important areas

[Certain] Production configuration validation rejects important unsafe settings such as weak/default secrets, wildcard CORS, and unsuitable database configuration.

[Likely] This is a good security foundation and should not be weakened during remediation.

## 4.5 Local-first WhatsApp matches the current operating model

[Certain] The current approved runtime is effectively:

```text
WhatsApp
→ Local Baileys Bridge
→ Financial SaaS
→ Document
→ OCR / Hermes Runtime
→ Review Queue
→ authorized accounting posting
```

[Certain] Durable capture while the Finance PC is OFF is currently deferred.

[Certain] That decision should remain unchanged during the security/accounting hardening feature.

---

# 5. Severity Model

## P0 — Critical / release blocker

[Certain] A finding is P0 when it can allow an authenticated user or application path to bypass an intended financial authorization, review, posting, or closed-period invariant.

## P1 — High

[Certain] A finding is P1 when it can cause accounting misclassification, tenant collision, missing audit attribution, inconsistent financial behavior, or reliability failure under realistic application concurrency.

## P2 — Medium

[Certain] A finding is P2 when it should be hardened before broader/public deployment but does not need to block the current local-first internal remediation sequence.

## P3 — Clarification / future

[Certain] A P3 item requires product/accounting clarification or future architecture work and should not be guessed by Hermes Coder.

---

# 6. P0 Findings — Fix Before New Features

---

## FIN-P0-001 — Transaction `/post` and `/approve` bypass role authorization

**Status:** Confirmed  
**Severity:** P0  
**Confidence:** [Certain]

### Evidence

File:

```text
backend/src/api/v1/transactions.py
```

Observed behavior:

```python
await policy_svc.authorize_and_post(
    org_id,
    transaction_id,
    bypass_role_check=True,
)
```

used by both:

```text
POST /transactions/{transaction_id}/post
POST /transactions/{transaction_id}/approve
```

[Certain] `ProcessingPolicyService` already contains role logic for sensitive transactions.

[Certain] These API endpoints deliberately disable that logic.

### Impact

[Certain] An authenticated user can reach a financial posting path without the API supplying the actual user's role.

[Certain] The endpoint also does not supply `actor_id`, so approval attribution can be missing.

[Likely] This defeats the intended distinction between OPERATOR/VIEWER and MANAGER/ADMIN for sensitive financial actions.

### Required remediation

1. [Certain] Introduce or reuse an authenticated principal dependency containing:

```text
user_id
organization_id
role
```

2. [Certain] Pass real `actor_id` and `actor_role`.

3. [Certain] Remove the user-reachable use of:

```text
bypass_role_check=True
```

4. [Likely] Prefer removing the public `bypass_role_check` concept entirely, or restricting any exceptional internal bypass to a clearly isolated bootstrap/system-only service that cannot be reached from a normal authenticated API.

### Acceptance tests

```text
VIEWER   → approve/post sensitive transaction → 403
OPERATOR → approve/post sensitive transaction → 403
MANAGER  → permitted action according to approved role matrix
ADMIN    → permitted action according to approved role matrix
```

[Certain] Tests must call the real API endpoints, not only the service method.

---

## FIN-P0-002 — Any authenticated application user can resolve Review Flags

**Status:** Confirmed  
**Severity:** P0  
**Confidence:** [Certain]

### Evidence

Files:

```text
backend/src/api/v1/review.py
backend/src/services/review_service.py
```

[Certain] `resolve_review_flag()` records the supplied `resolved_by` user and, when the last unresolved flag is resolved, changes the transaction back to:

```text
STAGED
```

[Certain] The API endpoint is protected by application authentication but does not independently require a reviewer role.

### Risk chain

[Certain] The current code permits this logical chain:

```text
authenticated OPERATOR / VIEWER
→ resolve final review flag
→ transaction becomes STAGED
→ call transaction /approve or /post
→ bypass_role_check=True
→ ledger posting path
```

### Required remediation

[Certain] Resolving a financial review flag must require the approved reviewer role.

Recommended minimum existing-policy alignment:

```text
ADMIN
MANAGER
```

[Likely] OPERATOR may create or add a review flag as part of intake, but should not clear a financial exception unless product policy explicitly says otherwise.

### Acceptance tests

```text
VIEWER   → resolve flag → 403
OPERATOR → resolve flag → 403
MANAGER  → resolve flag → allowed
ADMIN    → resolve flag → allowed
```

and:

```text
unresolved flag exists → posting denied
last flag resolved by authorized reviewer → transaction may continue
```

---

## FIN-P0-003 — Opening-balance endpoint can create arbitrary balanced ledger entries without role enforcement

**Status:** Confirmed  
**Severity:** P0  
**Confidence:** [Certain]

### Evidence

Files:

```text
backend/src/api/v1/transactions.py
backend/src/services/opening_balance_service.py
```

Endpoint:

```text
POST /transactions/opening-balances
```

[Certain] The endpoint does not require an Admin role.

[Certain] The service accepts arbitrary account-code legs, checks that total debit equals total credit, builds a `JOURNAL_ADJUSTMENT`, and calls:

```python
authorize_and_post(..., bypass_role_check=True)
```

### Why this is critical

[Certain] Balanced double-entry is necessary but **not sufficient authorization**.

[Certain] A balanced journal can still materially change assets, liabilities, equity, revenue, and expenses.

### Required remediation

[Certain] Immediate minimum:

```text
Opening balances → ADMIN only
```

[Certain] Record:

```text
created_by
approved_by
actor_id
audit event
```

### Product decision required before expanding behavior

[Likely] One of these models should eventually be selected:

**Option A — one-time initialization**

```text
opening balance allowed only before normal ledger operation
```

**Option B — controlled administrative import**

```text
ADMIN + explicit import workflow + review + audit
```

[Certain] Hermes Coder must **not invent** which model is financially correct for the company.

### Acceptance tests

```text
VIEWER / OPERATOR / MANAGER → opening balance → 403
ADMIN → valid balanced batch → allowed
unbalanced batch → rejected
closed accounting period → rejected
audit actor must be non-null
```

---

## FIN-P0-004 — Reversal endpoint has no financial-role authorization and bypasses accounting-period policy

**Status:** Confirmed  
**Severity:** P0  
**Confidence:** [Certain]

### Evidence

Files:

```text
backend/src/api/v1/reversals.py
backend/src/services/reversal_service.py
```

Current endpoint:

```text
POST /transactions/{transaction_id}/reverse
```

[Certain] It passes organization and reason to `ReversalService`.

[Certain] It does not pass the authenticated actor.

[Certain] It does not require MANAGER/ADMIN.

[Certain] `ReversalService` constructs the reversal directly rather than going through the same accounting-period authorization path used in `ProcessingPolicyService`.

### Impact

[Certain] Reversal is a financial correction action that changes posted financial truth.

[Certain] It must not be available to every authenticated role.

[Certain] A CLOSED accounting period must remain an invariant regardless of which API/service initiates posting.

### Required remediation

1. [Certain] MANAGER/ADMIN authorization for reversal according to the existing sensitive-transaction policy.
2. [Certain] Real actor attribution.
3. [Certain] Central accounting-period enforcement.
4. [Certain] Preserve existing:

```text
Original
→ Reversal
→ Correcting Transaction
```

pattern.

### Acceptance tests

```text
VIEWER / OPERATOR → reverse → 403
MANAGER / ADMIN → role permitted
reverse transaction in CLOSED period → denied
reverse already-reversed transaction → denied
reverse invoice with allocated payment → existing invariant remains enforced
audit actor → non-null
```

---

## FIN-P0-005 — Multiple financial flows call `AccountingEngine.post_transaction()` directly

**Status:** Confirmed  
**Severity:** P0  
**Confidence:** [Certain]

### Confirmed direct posting paths

```text
backend/src/api/v1/documents.py
backend/src/api/v1/payables.py
backend/src/api/v1/receivables.py
backend/src/services/receivable_service.py
backend/src/services/fixed_asset_service.py
```

Examples include:

```text
document approval
vendor payment
customer payment
retention release
fixed-asset depreciation
```

### Architectural problem

[Certain] `ProcessingPolicyService` contains important workflow controls such as:

```text
unresolved review flag guard
sensitive role guard
CLOSED period guard
SOFT_CLOSED role behavior
approval attribution
audit event
```

[Certain] `AccountingEngine.post_transaction()` is lower-level and does not itself enforce all of those business/security controls.

### Consequence

[Certain] A financial invariant is currently dependent on **which caller happened to invoke the engine**.

[Certain] That is unsafe architecture.

### Required architecture

[Certain] There should be one explicit financial posting boundary.

Recommended shape:

```text
API / Domain Service
        ↓
Financial Posting Policy / Coordinator
        ↓
hard invariant validation
        ↓
Accounting Engine
        ↓
Journal Entry + Journal Lines
```

### Important design nuance

[Certain] Do **not** blindly replace every direct call with the exact current policy call.

[Likely] Different domain flows may legitimately have different human-review semantics.

[Certain] However, hard accounting invariants must never be bypassable.

### Minimum invariant split

**AccountingEngine or immediately adjacent hard boundary**

```text
tenant ownership
valid workflow transition
supported posting rule
double-entry equality
valid COA
CLOSED-period prohibition
idempotent / no duplicate posting
```

**Policy / Coordinator**

```text
human-review requirement
role authorization
sensitive action authorization
actor attribution
approval metadata
source-specific policy
```

[Likely] This split keeps the engine deterministic while ensuring a caller cannot accidentally skip a closed-period invariant.

### Acceptance test strategy

[Certain] Every path below must be tested against a CLOSED accounting period:

```text
manual transaction
document approval
vendor payment
customer payment
retention release
fixed-asset depreciation
reversal
opening balances
```

Expected:

```text
all denied unless a specifically approved financial policy says otherwise
```

[Certain] No caller should be able to bypass the hard period invariant.

---

## FIN-P0-006 — Fixed-asset depreciation API hardcodes the actor role as ADMIN

**Status:** Confirmed  
**Severity:** P0  
**Confidence:** [Certain]

### Evidence

File:

```text
backend/src/api/v1/fixed_assets.py
```

Observed:

```python
actor_role=UserRole.ADMIN
```

for both:

```text
single depreciation
batch depreciation
```

### Impact

[Certain] The backend is not asking, "What role does this authenticated user have?"

[Certain] It is telling the service, "Treat this caller as ADMIN."

[Certain] This undermines SOFT_CLOSED-period authorization.

### Required remediation

[Certain] Pass the real authenticated role.

[Certain] Add explicit role policy for:

```text
create asset
update asset
depreciate
batch depreciate
dispose asset
```

[Likely] At minimum depreciation/disposal should not be available to VIEWER.

[Certain] The exact OPERATOR/MANAGER distinction should be confirmed as business policy instead of guessed.

---

# 7. P1 Findings — High Priority After P0

---

## FIN-P1-101 — Fixed-asset depreciation posts to the wrong expense account

**Status:** Confirmed  
**Severity:** P1  
**Confidence:** [Certain]

Current rule:

```text
FIXED_ASSET_DEPRECIATION
Debit  6105
Credit 1502
```

Authoritative financial concept:

```text
6105 = Perizinan
6108 = Penyusutan
```

### Impact

[Certain] The journal can remain mathematically balanced while the Profit & Loss classification is wrong.

### Required remediation

```text
Debit depreciation expense → 6108
Credit accumulated depreciation → 1502
```

[Certain] Add a regression test that specifically posts:

```text
TransactionType.FIXED_ASSET_DEPRECIATION
```

[Certain] A test using another transaction type that happens to reference 6108 is not sufficient.

---

## FIN-P1-102 — TransactionType contract is broader than the PostingRuleRegistry

**Status:** Confirmed  
**Severity:** P1  
**Confidence:** [Certain]

[Certain] The backend `TransactionType` enum currently contains **37** transaction types.

[Certain] Static comparison found these transaction types absent from the standard `posting_rules.py` registry:

```text
EMPLOYEE_ADVANCE
EMPLOYEE_SETTLEMENT
REIMBURSEMENT
PAY_REIMBURSEMENT
PETTY_CASH_EXPENSE
TOPUP_PETTY_CASH
RETURN_PETTY_CASH
INVENTORY_PURCHASE
INVENTORY_USAGE
REVENUE_RECOGNITION
CUSTOMER_REFUND
VENDOR_REFUND
LOAN_RECEIVED
LOAN_PAYMENT
OTHER_INCOME
OTHER_EXPENSE
REVERSAL
```

[Certain] `REVERSAL` is intentionally handled through the dedicated reversal mechanism, so it should not automatically be treated as a missing normal posting rule.

[Certain] The remaining mismatch still creates an application contract problem: a type can be accepted as a valid enum before the system knows whether it is actually postable.

### Important inconsistency

[Certain] `ProcessingPolicyService.AUTO_SAFE_TYPES` includes:

```text
PETTY_CASH_EXPENSE
```

while the standard PostingRuleRegistry does not contain a corresponding posting branch.

### Required remediation

[Certain] Create an explicit contract such as:

```text
SUPPORTED_STANDARD_POSTING_TYPES
SPECIAL_WORKFLOW_TYPES
UNIMPLEMENTED_OR_POLICY_PENDING_TYPES
```

[Certain] Validate candidate/manual transaction types before they reach posting.

[Certain] Do **not** invent debit/credit rules for missing transaction types.

[Certain] Missing accounting policies must remain blocked until approved.

---

## FIN-P1-103 — Human-readable code generation uses `COUNT + 1` and is race-prone

**Status:** Confirmed design pattern  
**Severity:** P1  
**Confidence:** [Likely]

Observed code-generation pattern exists in multiple services, including:

```text
TransactionService
AccountingEngine journal entry number
ProjectService
VendorAP
CustomerAR
MoneyMovementService
ReversalService
```

Typical pattern:

```text
SELECT COUNT(...)
next = count + 1
```

### Risk

[Likely] Two concurrent requests can read the same count and generate the same next code.

[Certain] The current local-first system can still have concurrency from:

```text
frontend requests
background worker
WhatsApp intake
retries
multiple browser actions
```

### Required remediation

[Likely] Prefer one of:

1. PostgreSQL-backed counter table;
2. database sequence where suitable;
3. transaction-scoped advisory lock + safe sequence allocation;
4. bounded retry after unique-constraint collision.

[Certain] Do not solve this using process-local Python locks; they will not be authoritative across processes.

### Acceptance test

```text
create N concurrent records for same organization/year
→ all succeed
→ all business codes unique
→ no duplicate journals
```

---

## FIN-P1-104 — Tenant-scoped code generation conflicts with global uniqueness constraints

**Status:** Confirmed  
**Severity:** P1  
**Confidence:** [Certain]

### Money movements

Model:

```text
movement_code → unique=True globally
settlement_code → unique=True globally
```

Service generation:

```text
COUNT filtered by organization_id
```

[Certain] Organization A can generate:

```text
MM-2026-000001
SET-000001
```

[Certain] Organization B can independently attempt to generate the same strings.

[Certain] The global database unique constraint can then reject the second organization.

### Fixed assets

Model:

```text
asset_code → unique=True globally
```

Service validation:

```text
uniqueness checked inside organization_id
```

[Certain] This is the same semantic mismatch.

### Required remediation

[Likely] If business codes are intended to be tenant-local, migrate to composite uniqueness:

```text
UNIQUE (organization_id, movement_code)
UNIQUE (organization_id, settlement_code)
UNIQUE (organization_id, asset_code)
```

[Certain] Migration must be non-destructive and validated against existing data.

[Certain] First run a duplicate/collision pre-check before changing constraints.

---

## FIN-P1-105 — Some cross-tenant references rely on service validation, and actual validation gaps remain

**Status:** Confirmed concern  
**Severity:** P1  
**Confidence:** [Certain]

[Certain] The repository already has tenant referential-integrity tests for important transaction references.

[Certain] The database generally uses ordinary UUID foreign keys rather than composite tenant-aware foreign keys.

[Certain] Therefore service-layer validation is currently a critical part of tenant safety.

### Confirmed gap examples requiring review/fix

```text
FixedAsset creation:
- vendor_id
- document_id

Project creation:
- pic_user_id
```

[Certain] These fields should be validated to belong to the same organization before being persisted.

### Required remediation

1. add service validation;
2. add cross-tenant negative tests;
3. reject foreign UUIDs even when the referenced row exists;
4. only consider composite database foreign keys later as a dedicated migration.

[Certain] Do not turn this hardening feature into a massive schema rewrite.

---

## FIN-P1-106 — Audit actor attribution is missing on several sensitive paths

**Status:** Confirmed  
**Severity:** P1  
**Confidence:** [Certain]

Examples include current flows where actor information is absent or can remain null:

```text
generic transaction post/approve
opening balances
reversal
vendor payment direct posting
customer payment direct posting
retention release direct posting
```

### Why this matters

[Certain] A financial audit trail should answer:

```text
who
did what
when
to which tenant
to which financial object
with what result
```

### Required remediation

[Certain] Create a reusable authenticated principal/context.

Example conceptual structure:

```python
CurrentPrincipal(
    user_id,
    organization_id,
    role,
)
```

[Certain] Every user-triggered mutation affecting financial truth should receive that principal explicitly.

[Certain] System/background actions should use a separately identifiable system actor/context rather than silently using `None`.

---

## FIN-P1-107 — Backend and frontend need one explicit permission matrix

**Status:** Confirmed architecture gap  
**Severity:** P1  
**Confidence:** [Certain]

[Certain] The frontend already contains `ProtectedRoute` support for allowed roles.

[Certain] Most application routes do not currently use per-route role restriction.

[Certain] The backend has role checks only in selected paths.

### Required principle

```text
Backend authorization = security authority
Frontend role filtering = UX convenience
```

[Certain] Never depend on hidden buttons as authorization.

### Proposed matrix — requires owner confirmation for non-critical operations

| Capability | ADMIN | MANAGER | OPERATOR | VIEWER |
|---|---:|---:|---:|---:|
| Read dashboard/reports | Yes | Yes | Yes* | Yes |
| Upload/intake documents | Yes | Yes | Yes | No/optional |
| Correct document extraction | Yes | Yes | Proposed No | No |
| Resolve financial review flag | Yes | Yes | No | No |
| Approve/post normal financial transaction | Yes | Yes | Proposed No | No |
| Sensitive owner transaction | Yes | Yes | No | No |
| Reverse posted transaction | Yes | Yes | No | No |
| Opening balances | Yes | No | No | No |
| Accounting period management | Yes | Yes* | No | No |
| Fixed asset depreciation/disposal | Yes | Proposed Yes | No | No |
| Maintain COA/configuration | Yes | Proposed limited | No | No |
| Read master/project data | Yes | Yes | Yes | Yes |

`*` = confirm business policy.

[Certain] Critical deny rules for VIEWER/OPERATOR should be implemented first.

[Likely] The complete convenience/operational matrix can be refined after the security boundary is secure.

---

## FIN-P1-108 — `PROJECT_STATUS.md` is stale relative to GitHub main

**Status:** Confirmed  
**Severity:** P1 governance  
**Confidence:** [Certain]

GitHub main checked:

```text
62dd6c8...
PR #53 merged
```

Current `PROJECT_STATUS.md` content still references an older baseline/branch state.

### Why this matters

[Certain] The project-level `AGENTS.md` explicitly instructs Hermes Coder to reconcile status against Git before selecting work.

### Required remediation

Before any code change:

```text
git fetch
git branch --show-current
git status
git rev-parse origin/main
compare PROJECT_STATUS.md
update stale operational facts
```

[Certain] Git remains authoritative for branch and commit facts.

---

## FIN-P1-109 — Preserve both current document storage trees until reconciled

**Status:** Repository-declared protection  
**Severity:** P1 operational  
**Confidence:** [Certain]

`PROJECT_STATUS.md` warns that both:

```text
backend/storage
backend/backend/storage
```

contain ignored source documents.

[Certain] They must not be casually deleted, moved, merged, or "cleaned up."

### Required precondition

Before touching either storage tree:

```text
DB document references
+
filesystem paths
+
SHA-256 hashes
```

must be reconciled.

[Certain] Hermes Coder must treat these directories as protected data during the hardening feature.

---

# 8. P2 Findings — Harden Before Wider Exposure

---

## FIN-P2-201 — Bearer session is stored in browser localStorage

**Status:** Confirmed  
**Severity:** P2 for current local-first use  
**Confidence:** [Certain]

Frontend:

```text
frontend/src/store/AuthContext.tsx
```

stores the serialized authenticated session in:

```text
localStorage
```

### Risk

[Certain] JavaScript-readable bearer tokens increase credential exposure if an XSS vulnerability exists.

[Likely] The current local-first/internal environment lowers urgency compared with a public internet SaaS.

### Future remediation

[Likely] Consider:

```text
HttpOnly + Secure + SameSite cookie
+
CSRF strategy
```

or another short-lived session architecture.

[Certain] Do not block the P0 financial-control remediation on this change.

---

## FIN-P2-202 — Login behavior is ambiguous if the same email belongs to multiple organizations

**Status:** Confirmed design behavior  
**Severity:** P2  
**Confidence:** [Certain]

[Certain] User email uniqueness is tenant-scoped.

[Certain] Login lookup is effectively email-based and expects one resolved user.

[Likely] If the same email exists in multiple tenants, login can become ambiguous/fail.

### Future product decision

Choose one:

```text
A. email globally unique across SaaS
B. login includes organization/company selector or slug
```

[Certain] Current single-company operation does not require immediate change.

---

## FIN-P2-203 — Deferred Cloudflare edge relay allowlist is not fail-closed for a missing sender row

**Status:** Confirmed  
**Severity:** P2 now / P0 before activation  
**Confidence:** [Certain]

Deferred component:

```text
edge-relay/src/index.ts
```

Current logic rejects an allowlist row when it exists and is inactive.

[Certain] A sender with **no row** can pass the shown condition.

### Current decision

[Certain] Do **not** activate remote PC-off relay in this remediation feature.

[Certain] RC1 remains local Baileys.

### Before any future activation

Required behavior:

```text
allowlist row missing → reject
allowlist inactive → reject
allowlist active → continue
```

plus tests.

---

## FIN-P2-204 — Frontend role exposure should be reduced after backend RBAC is fixed

**Status:** Confirmed UX architecture  
**Severity:** P2  
**Confidence:** [Certain]

[Certain] The same broad application navigation is currently available under the common protected layout.

### Recommended owner-facing navigation

[Likely] For normal owner operation, prioritize:

```text
Dashboard
WhatsApp Inbox
Review
Projects
Kas & Bank
Piutang
Utang
Laporan
```

[Likely] Put technical/accounting administration under an Advanced/Accounting area:

```text
Transactions
Documents
Chart of Accounts
Trial Balance
General Ledger
Accounting Periods
Consultant Reconciliation
```

[Certain] This should happen only after backend authorization is authoritative.

---

## FIN-P2-205 — Frontend/backend workflow-status contract contains drift

**Status:** Confirmed code-contract concern  
**Severity:** P2  
**Confidence:** [Certain]

[Certain] Frontend transaction-related types include a `REJECTED` workflow status while the backend transaction `WorkflowStatus` does not define the same general transaction state.

[Likely] This can create dead branches or misleading UI assumptions.

### Required remediation

- compare generated/API contract types;
- remove unsupported values or map them to the correct document/candidate state;
- add contract tests where practical.

---

# 9. Policy Questions Hermes Must Not Guess

[Certain] The following require an explicit product/accounting decision if existing authoritative artifacts do not already answer them.

## POL-001 — Opening balances after initialization

Choose whether they are:

```text
one-time only
or
reusable controlled Admin import
```

## POL-002 — Normal posting permission

[Certain] Sensitive transactions already imply MANAGER/ADMIN.

[Likely] Confirm whether a normal validated transaction can ever be posted by OPERATOR, or whether OPERATOR may only stage data.

## POL-003 — Accounting period management

Confirm:

```text
ADMIN only
or
ADMIN + MANAGER
```

for each of:

```text
open
soft-close
reopen
close
```

## POL-004 — Fixed assets

Confirm role permission for:

```text
create
edit
depreciate
dispose
```

## POL-005 — Missing TransactionType accounting rules

[Certain] Do not derive new accounting rules from enum names.

[Certain] Implement only after the authoritative accounting policy identifies debit/credit treatment.

---

# 10. Recommended Posting Architecture

## 10.1 Current problem

```text
                      ┌→ ProcessingPolicyService → AccountingEngine
API / Service calls ──┼→ AccountingEngine directly
                      ├→ ReversalService custom posting
                      └→ OpeningBalance bypass mode
```

[Certain] The outcome depends too much on which path is used.

## 10.2 Target

```text
Authenticated Principal / System Context
                ↓
        Domain Operation
                ↓
      Posting Coordinator
      ├─ tenant validation
      ├─ role authorization
      ├─ review requirement
      ├─ actor attribution
      └─ source-specific policy
                ↓
        Hard Ledger Guard
      ├─ supported posting type
      ├─ CLOSED-period invariant
      ├─ workflow/idempotency
      ├─ valid COA
      └─ double-entry invariant
                ↓
        Accounting Engine
                ↓
      JournalEntry / JournalLine
                ↓
        Reports / AR / AP / Project
```

[Likely] The exact class names can differ.

[Certain] The invariant boundaries should not.

---

# 11. Remediation Order

## Phase 0 — Repository preflight

**No business-code changes yet.**

Tasks:

```text
[ ] fetch and verify origin/main
[ ] reconcile PROJECT_STATUS.md
[ ] verify clean worktree
[ ] snapshot current test baseline
[ ] confirm protected storage directories remain untouched
[ ] create hermes/011-security-accounting-invariant-hardening
[ ] create/activate Spec Kit feature
```

Exit criteria:

```text
known baseline
clean branch
no protected-data changes
```

---

## Phase 1 — Principal + authorization foundation

Tasks:

```text
[ ] create/reuse CurrentPrincipal dependency
[ ] expose user_id + org_id + role together
[ ] implement reusable role requirement helpers
[ ] remove fake UserRole.ADMIN
[ ] add API-level role tests
```

Do not yet redesign frontend.

Exit criteria:

```text
backend has one reliable caller identity
```

---

## Phase 2 — Close the critical posting bypass

Tasks:

```text
[ ] fix /transactions/{id}/post
[ ] fix /transactions/{id}/approve
[ ] remove user-reachable bypass_role_check=True
[ ] protect review-flag resolution
[ ] protect opening balances
[ ] protect reversal
[ ] pass real actor identity
```

Exit criteria:

```text
VIEWER/OPERATOR cannot clear-and-post or reverse financial truth
```

---

## Phase 3 — Central hard accounting invariants

Tasks:

```text
[ ] define one posting boundary
[ ] enforce CLOSED period below all ordinary caller paths
[ ] migrate document approval to controlled boundary
[ ] migrate vendor payment
[ ] migrate customer payment
[ ] migrate retention release
[ ] migrate fixed-asset depreciation
[ ] verify no unauthorized direct AccountingEngine callers remain
```

Recommended static gate:

```text
search for ".post_transaction(" against AccountingEngine
```

[Likely] Allow only explicitly documented internal caller(s).

Exit criteria:

```text
all financial posting paths enforce same hard ledger invariants
```

---

## Phase 4 — Accounting correctness fixes

Tasks:

```text
[ ] depreciation 6105 → 6108
[ ] targeted depreciation regression test
[ ] classify TransactionType support state
[ ] block unsupported standard posting types early
```

[Certain] Do not create missing accounting mappings without approved policy.

---

## Phase 5 — Tenant and reliability hardening

Tasks:

```text
[ ] fix tenant/global uniqueness mismatches
[ ] add fixed-asset foreign-tenant validations
[ ] add project PIC tenant validation
[ ] add regression tests
[ ] replace or protect COUNT+1 code generation
[ ] concurrency test critical business codes
```

---

## Phase 6 — Audit completeness

Tasks:

```text
[ ] actor non-null for user-triggered financial mutations
[ ] system actions use explicit system context
[ ] verify audit logs for approve/post/reverse/opening balances/AP/AR
```

---

## Phase 7 — Frontend RBAC + UX simplification

Only after backend protection is complete.

Tasks:

```text
[ ] role-aware routes
[ ] role-aware navigation
[ ] hide/disable forbidden actions
[ ] Owner-facing progressive disclosure
[ ] retain backend enforcement
```

Use:

```text
UI/UX Pro Max → design direction
Impeccable → post-implementation review
Anti-Slop → final quality gate
```

---

## Phase 8 — Final verification

Required:

```text
backend tests
frontend tests
API authorization matrix
lint
typecheck
frontend build
Alembic upgrade/downgrade or offline-chain validation as applicable
dependency audit
repository safety checks
security diff review
accounting invariant review
GitHub CI
```

No completion claim until the gates are actually executed.

---

# 12. Required API Security Regression Matrix

The following should become automated tests.

| Operation | VIEWER | OPERATOR | MANAGER | ADMIN |
|---|---:|---:|---:|---:|
| Read reports | allow | allow* | allow | allow |
| Create staged transaction | deny/proposed | allow* | allow | allow |
| Resolve review flag | deny | deny | allow | allow |
| Approve/post normal trx | deny | deny* | allow | allow |
| Post sensitive owner trx | deny | deny | allow | allow |
| Opening balances | deny | deny | deny | allow |
| Reverse | deny | deny | allow | allow |
| Vendor payment | deny | proposed | allow | allow |
| Customer payment | deny | proposed | allow | allow |
| Retention release | deny | deny | allow | allow |
| Depreciate asset | deny | deny | proposed | allow |
| Dispose asset | deny | deny | proposed | allow |
| Close accounting period | deny | deny | proposed | allow |

`*` = requires policy confirmation.

[Certain] All denied actions must be denied by the backend even if the user manually calls the API.

---

# 13. Required Accounting Invariant Tests

## INV-001 — Double entry

```text
total_debit == total_credit
```

## INV-002 — No duplicate posting

```text
same transaction cannot produce two authoritative journals
```

## INV-003 — CLOSED period

```text
no ordinary financial posting path can mutate CLOSED period
```

## INV-004 — Review hard stop

```text
unresolved financial flag → no posting
```

## INV-005 — Reversal integrity

```text
Original + Reversal = net zero effect
```

while preserving linked AR/AP constraints.

## INV-006 — Tenant isolation

```text
tenant A cannot reference tenant B:
project
counterparty
payment account
document
fixed-asset vendor/document
PIC user
journal
```

## INV-007 — Audit identity

```text
user-triggered financial mutation → actor_id exists
```

## INV-008 — Depreciation mapping

```text
FIXED_ASSET_DEPRECIATION
Dr 6108
Cr 1502
```

## INV-009 — Unsupported transaction type

```text
unsupported/policy-pending type
→ rejected before ledger generation
→ no partial journal
```

## INV-010 — Concurrent code generation

```text
parallel create
→ unique codes
→ no failed collision
→ no duplicate ledger event
```

---

# 14. Hermes Coder Integration

## 14.1 Important decision

[Certain] **Do not replace the repository's current `AGENTS.md` with the generic `AGENTS.md` from the Hermes Coder tutorial.**

[Certain] The generic profile instructions are useful for ordinary projects.

[Certain] This Financial SaaS repository already has stronger domain-specific governance:

```text
.specify/memory/constitution.md
docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md
AGENTS.md
specs/
.hermes/skills/financial-saas-orchestrator/SKILL.md
PROJECT_STATUS.md
```

[Certain] Those project rules should remain authoritative.

## 14.2 Keep the profile-level SOUL.md

[Certain] The uploaded Hermes Coder `SOUL.md` is suitable because it requires:

```text
inspect before editing
understand before designing
plan before large implementation
implement incrementally
test what you change
debug root causes
review the diff
simplify when justified
verify before completion
```

[Certain] That behavior is appropriate for this repository.

## 14.3 Skill routing for this remediation

### Core orchestration

```text
financial-saas-orchestrator
Spec Kit
Hermes native planning
```

### Deep inspection

```text
Hermes native repo tools
Understand Anything — only if useful for broad dependency mapping
Codebase Memory MCP — only if already verified stable
```

### Security/accounting bug work

```text
systematic-debugging
test-driven-development
requesting-code-review
simplify-code
```

### Research

```text
Hermes native Web/GitHub → official facts
Agent Reach → only when community evidence is actually useful
```

[Certain] Community research is not required to decide the application's own accounting policy.

### Frontend phase only

```text
UI/UX Pro Max
Impeccable
Anti-Slop
```

[Certain] Taste should not drive accounting dashboard remediation unless a genuinely creative visual-design problem exists.

### Diagramming

```text
Diagram Design
```

Recommended for:

```text
posting boundary
RBAC flow
review state machine
transaction lifecycle
```

---

# 15. How Hermes Coder Should Work on This Audit

## Step 1 — Treat this audit as evidence, not authority

[Certain] The authoritative order remains the repository `AGENTS.md`.

This file is:

```text
audit evidence
+
remediation input
```

not a replacement for:

```text
Constitution
Financial Concept
Spec Kit feature spec
approved clarifications
```

## Step 2 — Reproduce every P0 before editing

For each finding:

```text
inspect source
identify reachable API
write or update failing regression test
prove failure
apply smallest correct fix
rerun targeted tests
```

## Step 3 — Formalize the hardening feature

Suggested:

```text
specs/011-security-accounting-invariant-hardening/
```

Use:

```text
research
→ specify
→ clarify
→ plan
→ tasks
→ analyze
→ implement
```

## Step 4 — Split implementation into checkpoints

Do not make one giant PR.

Suggested checkpoint sequence:

```text
A. principal + RBAC infrastructure
B. critical API authorization
C. central posting / period boundary
D. accounting correctness
E. tenant + concurrency hardening
F. frontend RBAC/UX
```

[Likely] Depending on diff size, these can become separate PRs or tightly isolated commits within one feature branch.

---

# 16. Copy-Paste Prompt for Hermes Coder — Start With Analysis, Not Code

```text
You are working on mikaelzo-blip/financial-saas.

Use the repository's existing AGENTS.md, Constitution, Financial SaaS
orchestrator, PROJECT_STATUS.md, and Spec Kit as authoritative governance.
Do not replace them with generic profile instructions.

Read:
1. AGENTS.md
2. PROJECT_STATUS.md
3. .specify/memory/constitution.md
4. docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md
5. .hermes/skills/financial-saas-orchestrator/SKILL.md
6. FINANCIAL_SAAS_DEEP_AUDIT_AND_REMEDIATION_2026-09-09.md

First reconcile PROJECT_STATUS.md with actual git branch, git status,
and origin/main. Git wins for operational branch/commit facts.

Then independently reproduce and verify the audit's P0 findings.
Do not trust the audit blindly and do not implement yet.

For every P0:
- identify the exact call path
- identify the violated invariant
- inspect existing tests
- determine the smallest safe correction
- identify any business-policy question that cannot be resolved from
  authoritative artifacts
- propose a regression test

Create or update the Spec Kit feature:
011-security-accounting-invariant-hardening

Produce:
1. confirmed findings
2. rejected/incorrect audit findings, if any
3. security/accounting invariants
4. RBAC decisions already authoritative
5. unresolved policy questions
6. technical plan
7. ordered tasks
8. test matrix
9. migration impact
10. safe checkpoint strategy

Hard constraints:
- no production deployment
- no destructive production DB action
- do not touch protected document storage trees
- no new accounting policy invented
- no fake roles
- no bypass_role_check from user-reachable endpoints
- no direct financial posting path may bypass hard CLOSED-period invariants
- posted transactions remain immutable; use reversal
- tenant isolation remains mandatory
- double-entry equality remains mandatory
- do not weaken existing tests
- do not add unrelated features

Stop before implementation only if a genuinely new accounting/business
policy is required. Otherwise continue through the repository's normal
Spec Kit analysis workflow and present the implementation-ready checkpoint.
```

---

# 17. Suggested Implementation Prompt After Spec Approval

Use only after the Spec Kit analysis is internally consistent.

```text
Continue feature 011-security-accounting-invariant-hardening from the
approved Spec Kit artifacts.

Work in small verified checkpoints.

Checkpoint A:
- implement authenticated principal / role plumbing
- add API role regression matrix for the P0 endpoints
- remove hardcoded ADMIN actor role
- do not change accounting mappings yet
- run targeted tests and repository-required quality gates
- review the diff

Checkpoint B:
- close transaction approve/post bypass
- protect review-flag resolution
- protect opening balances
- protect reversal
- preserve all existing accounting behavior except the authorization defect
- run targeted tests and review the diff

Checkpoint C:
- enforce one hard financial posting boundary
- CLOSED accounting period must be impossible to bypass from documents,
  AP, AR, retention, fixed assets, reversals, or opening balances
- preserve source-specific human-review behavior
- add path-by-path period regression tests

Checkpoint D:
- fix FIXED_ASSET_DEPRECIATION debit mapping from 6105 to authoritative 6108
- add a transaction-type-specific regression test
- classify supported vs special vs policy-pending TransactionType values
- do not invent missing debit/credit policies

Checkpoint E:
- repair confirmed tenant-scoped uniqueness mismatches
- add missing tenant-reference validation
- harden concurrent business-code generation
- use non-destructive migrations and preflight existing data

After each checkpoint:
- tests
- lint/typecheck/build where applicable
- migration validation where applicable
- security/accounting review
- diff review
- concise checkpoint commit

Do not continue past a failed checkpoint.
Do not push directly to main.
Follow AGENTS.md for PR/CI/merge behavior.
```

---

# 18. Files That Should Be Inspected First During Remediation

```text
backend/src/api/auth.py
backend/src/api/deps.py
backend/src/api/v1/__init__.py

backend/src/api/v1/transactions.py
backend/src/api/v1/review.py
backend/src/api/v1/reversals.py
backend/src/api/v1/documents.py
backend/src/api/v1/payables.py
backend/src/api/v1/receivables.py
backend/src/api/v1/fixed_assets.py
backend/src/api/v1/accounting_periods.py

backend/src/services/processing_policy_service.py
backend/src/services/accounting_engine.py
backend/src/services/posting_rules.py
backend/src/services/review_service.py
backend/src/services/opening_balance_service.py
backend/src/services/reversal_service.py
backend/src/services/receivable_service.py
backend/src/services/payable_service.py
backend/src/services/fixed_asset_service.py
backend/src/services/transaction_service.py
backend/src/services/money_movement_service.py

backend/src/models/enums.py
backend/src/models/transaction.py
backend/src/models/journal.py
backend/src/models/money_movement.py
backend/src/models/fixed_asset.py
backend/src/models/project.py
backend/src/models/user.py

frontend/src/App.tsx
frontend/src/store/AuthContext.tsx
frontend/src/components/auth/ProtectedRoute.tsx
frontend/src/layouts/AppLayout.tsx
frontend/src/types/api.ts

backend/tests/
frontend/src/**/*.test.*
```

---

# 19. Do-Not-Touch List During the First Security Pass

[Certain] The first security pass should not:

```text
rewrite the whole app
replace FastAPI
replace PostgreSQL
replace React
introduce microservices
replace the journal engine
introduce a second ledger
replace Spec Kit
replace repo AGENTS.md
replace the Financial SaaS orchestrator
activate Cloudflare PC-off relay
buy or provision a VPS
change real WhatsApp credentials
delete financial history
delete storage trees
rewrite published migrations
invent tax/accounting policy
redesign the entire frontend
```

[Certain] The goal is to **tighten the existing architecture**, not create another architecture.

---

# 20. Definition of Done for Feature 011

Feature 011 is not done until all applicable items are true.

## Security

```text
[ ] no user-reachable bypass_role_check
[ ] no fake ADMIN actor role
[ ] review resolution requires authorized role
[ ] opening balances protected
[ ] reversals protected
[ ] backend permission matrix tested
[ ] frontend never treated as authorization authority
```

## Financial invariants

```text
[ ] CLOSED period cannot be bypassed
[ ] double-entry equality preserved
[ ] no duplicate posting
[ ] reversal pattern preserved
[ ] unsupported posting types fail before ledger mutation
[ ] depreciation uses authoritative account 6108
```

## Audit

```text
[ ] user-triggered financial actions have actor identity
[ ] sensitive approval/post/reversal events are auditable
```

## Tenant isolation

```text
[ ] confirmed cross-tenant reference gaps closed
[ ] tenant-scoped uniqueness semantics match DB constraints
```

## Reliability

```text
[ ] critical business-code generation safe under concurrency
[ ] no partial financial state after failed posting
```

## Quality gates

```text
[ ] backend tests pass
[ ] frontend tests pass
[ ] lint passes or only explicitly documented existing warnings remain
[ ] typecheck passes
[ ] frontend production build passes
[ ] migration validation passes
[ ] dependency checks pass
[ ] repository safety checks pass
[ ] GitHub CI passes
[ ] zero Critical findings remain
[ ] zero High findings remain within approved feature scope
```

---

# 21. Proposed Final Architecture Score After Remediation

[Likely] If the P0 findings and core P1 items are fixed without weakening existing invariants:

| Area | Current estimate | Target |
|---|---:|---:|
| Accounting architecture | 8.5 | 9 |
| Backend architecture | 8 | 9 |
| Backend RBAC | 4.5 | 9 |
| Financial-control consistency | 6 | 9 |
| Tenant safety | 7.5 | 8.5–9 |
| Auditability | 7 | 9 |
| Reliability | 7 | 8.5 |
| Internal production readiness | ~8 after P0 | 9 |
| Wider multi-user readiness | ~5.5–6 now | ~8–9 |

[Likely] The largest improvement will come from **enforcing existing rules consistently**, not from adding more features.

---

# 22. Final Recommendation

[Certain] Freeze unrelated feature development.

[Certain] Reconcile Git state first.

[Certain] Create/continue a dedicated hardening feature.

[Certain] Fix backend authorization before frontend role hiding.

[Certain] Establish one non-bypassable hard financial posting boundary.

[Certain] Fix the confirmed depreciation account mapping.

[Certain] Close tenant-reference and uniqueness mismatches.

[Likely] Then address code-generation concurrency.

[Likely] Only after the backend is secure should the Owner-facing UX be simplified.

[Certain] Keep the current local-first Baileys operating model while PC-off relay remains deferred.

[Certain] Keep Hermes Runtime and Hermes Coder separated.

[Certain] Keep deterministic accounting in the SaaS backend.

[Certain] Use Hermes Coder as the orchestrator, but let the project's Constitution, AGENTS.md, Financial Concept, Spec Kit, tests, and GitHub CI constrain what it is allowed to change.

---

# Appendix A — Finding Index

| ID | Severity | Finding | Confidence |
|---|---|---|---|
| FIN-P0-001 | P0 | `/post` + `/approve` bypass role | [Certain] |
| FIN-P0-002 | P0 | review flag can be resolved without reviewer role | [Certain] |
| FIN-P0-003 | P0 | opening balances insufficiently authorized | [Certain] |
| FIN-P0-004 | P0 | reversal insufficiently authorized / period bypass | [Certain] |
| FIN-P0-005 | P0 | direct AccountingEngine callers bypass policy boundary | [Certain] |
| FIN-P0-006 | P0 | depreciation endpoint hardcodes ADMIN | [Certain] |
| FIN-P1-101 | P1 | depreciation mapped to 6105 instead of 6108 | [Certain] |
| FIN-P1-102 | P1 | TransactionType vs PostingRuleRegistry mismatch | [Certain] |
| FIN-P1-103 | P1 | COUNT+1 code generation race | [Likely] |
| FIN-P1-104 | P1 | tenant-local generators vs global unique constraints | [Certain] |
| FIN-P1-105 | P1 | tenant referential validation gaps | [Certain] |
| FIN-P1-106 | P1 | missing actor attribution | [Certain] |
| FIN-P1-107 | P1 | incomplete permission matrix | [Certain] |
| FIN-P1-108 | P1 | PROJECT_STATUS stale | [Certain] |
| FIN-P1-109 | P1 | protected storage trees require reconciliation | [Certain] |
| FIN-P2-201 | P2 | bearer token in localStorage | [Certain] |
| FIN-P2-202 | P2 | multi-org login ambiguity | [Certain] |
| FIN-P2-203 | P2 now | deferred edge-relay allowlist fail-open for missing row | [Certain] |
| FIN-P2-204 | P2 | frontend role exposure / UX density | [Certain] |
| FIN-P2-205 | P2 | frontend/backend workflow-status drift | [Certain] |

---

# Appendix B — Remediation Principle

```text
Do not make the system smarter first.

Make it impossible for the existing system
to violate its own accounting, authorization,
tenant, review, and audit invariants.

Then simplify the Owner experience.

Then add features.
```
