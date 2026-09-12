# Contract: Complete Authorization and Role Enforcement Matrix

**Remediation**: AUTHZ-001 (Reconciled Baseline)
**Specification**: [specs/authz-001-role-and-actor-hardening/spec.md](../spec.md)
**Baseline Commit**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`
**Scope**: 100% of all mutating endpoints (59 routes) in the application  

---

## 1. Executive Summary & Route Classification

An exhaustive audit of all FastAPI router definitions across `backend/src/api/` and `backend/src/api/v1/` identified **116 total API routes**:
- **GET (Read-Only)**: 57 routes
- **POST (Mutating / Action)**: 54 routes
- **PUT (Mutating)**: 1 route
- **PATCH (Mutating)**: 3 routes
- **DELETE (Mutating)**: 1 route
- **Total Mutating Endpoints**: **59 routes**

### Endpoint Classification Breakdown
1. **Human Application Endpoints**: **42 routes** (40 mounted under `application_router` + 2 sender admin endpoints under `whatsapp_state_router`).
   - **Category A (Actually Vulnerable)**: **17 routes** (no role check, VIEWER reaches mutation boundary).
   - **Category B (Protected In-Body)**: **4 routes** (denied to VIEWER via manual check in handler).
   - **Category C (Declaratively Protected)**: **17 routes** (protected via `require_roles` or `require_whatsapp_admin`).
   - **Category D (Reporting / Query Non-Mutating)**: **4 routes** (consultant reconciliation calculations + insights Q&A).
2. **Machine Service Endpoints**: **14 routes** (1 Hermes OCR intake + 13 WhatsApp state machine routes).
3. **Verified Webhook Endpoints**: **2 routes** (`/api/v1/whatsapp/webhook` & `/api/v1/integrations/whatsapp/webhook`).
4. **Public Auth Endpoints**: **1 route** (`POST /api/v1/auth/login`).

---

## 2. The 17 Actually Vulnerable Human Application Mutating Endpoints (Category A — CP1 RED Targets)

These 17 endpoints lack backend role enforcement and currently allow `VIEWER` mutation:

| # | Method & Path | Router & Handler | Auth Source | Tenant Source | Role Check | Current Allowed Roles | Financial / Business Effect | Proposed Policy Matrix (ADMIN / MANAGER / OPERATOR / VIEWER) |
|---|---|---|---|---|---|---|---|---|
| 1 | `POST /api/v1/transactions` | `transactions:create_transaction` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Creates draft unposted transaction candidate | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 2 | `POST /api/v1/projects` | `projects:create_project` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Creates Project master record (contract value, customer) | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 3 | `PATCH /api/v1/projects/{project_id}/status` | `projects:update_project_status` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Transitions project lifecycle status; enforces closure guards | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: DENY<br>VIEWER: DENY |
| 4 | `POST /api/v1/projects/{project_id}/budgets` | `projects:add_or_update_project_budget` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Sets cost category budget allocations for a project | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: DENY<br>VIEWER: DENY |
| 5 | `POST /api/v1/counterparties` | `counterparties:create_counterparty` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Creates Counterparty master record (Customer/Vendor) | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 6 | `POST /api/v1/coa` | `reference_data:create_coa` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Creates new Chart of Accounts general ledger account | ADMIN: ALLOW<br>MANAGER: DENY<br>OPERATOR: DENY<br>VIEWER: DENY |
| 7 | `POST /api/v1/payment-accounts` | `reference_data:create_payment_account` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Creates bank account / cash register reference entity | ADMIN: ALLOW<br>MANAGER: DENY<br>OPERATOR: DENY<br>VIEWER: DENY |
| 8 | `POST /api/v1/money-movements` | `money_movements:create_money_movement` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Creates MoneyMovement, settlements, & allocations | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 9 | `POST /api/v1/bank-reconciliation/imports` | `bank_reconciliation:upload_bank_statement` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Ingests bank statement file/lines and creates import | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 10 | `POST /api/v1/bank-reconciliation/imports/{import_id}/auto-match` | `bank_reconciliation:auto_match_statement` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Executes automated match against ledger/money movements | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 11 | `POST /api/v1/bank-reconciliation/reconcile` | `bank_reconciliation:manual_reconcile` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Creates manual match between bank statement line & trx | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 12 | `POST /api/v1/documents/upload` | `documents:upload_document` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Ingests source document, calculates SHA-256, triggers OCR | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 13 | `POST /api/v1/documents/{document_id}/retry` | `documents:retry_document` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Retries OCR extraction on failed/flagged document | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 14 | `POST /api/v1/transactions/{transaction_id}/review-flags` | `review:add_review_flag` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Adds review flag to transaction; sets `REVIEW_REQUIRED` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 15 | `POST /api/v1/inbox/capture` | `inbox:capture_remote_message` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Ingests remote WhatsApp message into staging queue | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 16 | `POST /api/v1/inbox/sync` | `inbox:sync_backlog` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Pulls un-synced backlog messages from remote inbox | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 17 | `POST /api/v1/inbox/sessions/{session_id}/analyze` | `inbox:analyze_document_session` | JWT (`application_router`) | Header (`get_current_org_id`) | None | Any authenticated (incl. VIEWER) | Triggers deferred analysis on inbox document session | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |

---

## 3. Protected Human Application Endpoints (21 Routes)

### Category B: Protected In-Body (4 Routes — PASS Characterization)

| # | Method & Path | Router & Handler | Role Check Mechanism | Allowed Roles | VIEWER Behavior | Financial / Business Effect |
|---|---|---|---|---|---|---|
| 18 | `POST /api/v1/documents/{document_id}/corrections` | `documents:correct_document` | In-body `require_reviewer(ADMIN, MANAGER)` | ADMIN, MANAGER | **403 Forbidden** | Mutates extraction candidate fields & clears review flags |
| 19 | `POST /api/v1/documents/{document_id}/reject` | `documents:reject_document_candidate` | In-body `require_reviewer(ADMIN, MANAGER)` | ADMIN, MANAGER | **403 Forbidden** | Rejects document candidate; audit logged |
| 20 | `POST /api/v1/periods` | `accounting_periods:create_period` | In-body `current_user.role` check | ADMIN, MANAGER | **403 Forbidden** | Creates accounting period (OPEN/SOFT_CLOSED/CLOSED) |
| 21 | `PATCH /api/v1/periods/{period_id}/status` | `accounting_periods:update_period_status` | In-body `current_user.role` check | ADMIN, MANAGER | **403 Forbidden** | Modifies period status; locks/unlocks ledger posting |

### Category C: Declaratively Protected (17 Routes)

| # | Method & Path | Router & Handler | Role Check Mechanism | Allowed Roles | VIEWER Behavior | Financial / Business Effect |
|---|---|---|---|---|---|---|
| 22 | `POST /api/v1/transactions/{transaction_id}/post` | `transactions:post_transaction` | `require_roles` + policy | ADMIN, MANAGER, OPERATOR | **403 Forbidden** | Posts transaction into double-entry journal (Dr == Cr) |
| 23 | `POST /api/v1/transactions/{transaction_id}/approve` | `transactions:approve_transaction` | `require_roles` + policy | ADMIN, MANAGER, OPERATOR | **403 Forbidden** | Authorizes and posts transaction |
| 24 | `POST /api/v1/transactions/opening-balances` | `transactions:establish_opening_balances` | `require_roles` | ADMIN only | **403 Forbidden** | Establishes starting general ledger account balances |
| 25 | `POST /api/v1/transactions/{transaction_id}/reverse` | `reversals:reverse_transaction` | `require_roles` | ADMIN, MANAGER | **403 Forbidden** | Generates reversal transaction & immutable reversal journal |
| 26 | `POST /api/v1/transactions/{transaction_id}/review-flags/{flag_id}/resolve` | `review:resolve_review_flag` | `require_roles` | ADMIN, MANAGER | **403 Forbidden** | Resolves review flag; unblocks transaction posting |
| 27 | `POST /api/v1/vendor-payments` | `payables:record_vendor_payment` | `require_roles` | ADMIN, MANAGER, OPERATOR | **403 Forbidden** | Records vendor payment, updates bill, posts journal to GL |
| 28 | `POST /api/v1/customer-invoices/retention-releases` | `receivables:release_customer_retention` | `require_roles` | ADMIN, MANAGER, OPERATOR | **403 Forbidden** | Releases retention receivable, posts journal to GL |
| 29 | `POST /api/v1/customer-payments` | `receivables:record_customer_payment` | `require_roles` | ADMIN, MANAGER, OPERATOR | **403 Forbidden** | Records customer payment, updates invoice, posts journal to GL |
| 30 | `POST /api/v1/fixed-assets` | `fixed_assets:create_asset` | `require_roles` | ADMIN, MANAGER, OPERATOR | **403 Forbidden** | Registers new fixed asset, depreciation parameters |
| 31 | `PATCH /api/v1/fixed-assets/{asset_id}` | `fixed_assets:update_asset` | `require_roles` | ADMIN, MANAGER, OPERATOR | **403 Forbidden** | Updates fixed asset details/cost |
| 32 | `PUT /api/v1/fixed-assets/{asset_id}` | `fixed_assets:update_asset` | `require_roles` | ADMIN, MANAGER, OPERATOR | **403 Forbidden** | Full update of fixed asset |
| 33 | `POST /api/v1/fixed-assets/{asset_id}/depreciate` | `fixed_assets:depreciate_single_asset` | `require_roles` | ADMIN, MANAGER | **403 Forbidden** | Posts depreciation transaction & journal |
| 34 | `POST /api/v1/fixed-assets/depreciate-batch` | `fixed_assets:depreciate_batch` | `require_roles` | ADMIN, MANAGER | **403 Forbidden** | Executes monthly batch depreciation into GL ledger |
| 35 | `POST /api/v1/fixed-assets/{asset_id}/dispose` | `fixed_assets:dispose_asset` | `require_roles` | ADMIN, MANAGER | **403 Forbidden** | Disposes asset, calculates gain/loss |
| 36 | `POST /api/v1/documents/{document_id}/approve` | `documents:approve_document_candidate` | `require_roles` + `require_reviewer` | ADMIN, MANAGER | **403 Forbidden** | Converts document candidate to Transaction and posts journal |
| 37 | `POST /api/v1/integrations/whatsapp/senders` | `whatsapp_state:create_sender` | `require_whatsapp_admin` | ADMIN only | **403 Forbidden** | Registers phone-to-user mapping; audit logged |
| 38 | `DELETE /api/v1/integrations/whatsapp/senders/{mapping_id}` | `whatsapp_state:disable_sender` | `require_whatsapp_admin` | ADMIN only | **403 Forbidden** | Deactivates sender mapping; audit logged |

---

## 4. Reporting & Query Non-Mutating Endpoints (Category D — 4 Routes)

| # | Method & Path | Router & Handler | Classification | Allowed Roles | Notes |
|---|---|---|---|---|---|
| 39 | `POST /api/v1/reports/consultant-reconciliation/reconcile-verified/{year}` | `consultant_reconciliation:reconcile_verified_year` | Reporting Calculation | All Authenticated | Non-mutating; computes reconciliation against verified annual statements. |
| 40 | `POST /api/v1/reports/consultant-reconciliation/compare` | `consultant_reconciliation:compare_consultant_statement` | Reporting Calculation | All Authenticated | Non-mutating; computes side-by-side reconciliation report. |
| 41 | `POST /api/v1/reports/consultant-reconciliation/upload` | `consultant_reconciliation:upload_consultant_statement` | Reporting Calculation | All Authenticated | Non-mutating; parses uploaded statement and returns report. |
| 42 | `POST /api/v1/insights/query` | `insights:financial_query` | User-Scoped Query | All Authenticated | Creates conversational Q&A message; does not mutate financial state. |

---

## 5. Machine Service, Webhook, and Public Endpoints (17 Routes)

| # | Method & Path | Router & Handler | Classification | Security Mechanism |
|---|---|---|---|---|
| 43 | `POST /api/v1/auth/login` | `auth:login` | Public Auth | Public credentials verification; issues JWT bearer token |
| 44 | `POST /api/v1/hermes/documents/upload` | `hermes:upload_document` | Machine Service | Machine token (`WHATSAPP_TENANT_TOKENS`) |
| 45 | `POST /api/v1/whatsapp/webhook` | `whatsapp:webhook` | Verified Webhook | Meta HMAC-SHA256 (`X-Hub-Signature-256`) |
| 46 | `POST /api/v1/integrations/whatsapp/webhook` | `whatsapp:webhook` | Verified Webhook | Meta HMAC-SHA256 (`X-Hub-Signature-256`) |
| 47 | `POST /api/v1/hermes/whatsapp/documents/get` | `whatsapp_state:channel_document` | Machine Service | Machine token (`require_whatsapp_machine`) |
| 48 | `POST /api/v1/hermes/whatsapp/resolve` | `whatsapp_state:resolve_sender` | Machine Service | Adapter bearer token (`WHATSAPP_ADAPTER_TOKEN`) |
| 49 | `POST /api/v1/hermes/whatsapp/rejections/claim` | `whatsapp_state:claim_rejection` | Machine Service | Adapter bearer token (`require_adapter`) |
| 50 | `POST /api/v1/hermes/whatsapp/rejections/finish` | `whatsapp_state:finish_rejection` | Machine Service | Adapter bearer token (`require_adapter`) |
| 51 | `POST /api/v1/hermes/whatsapp/messages/claim` | `whatsapp_state:claim_message` | Machine Service | Machine token (`require_whatsapp_machine`) |
| 52 | `POST /api/v1/hermes/whatsapp/messages/finish` | `whatsapp_state:finish_message` | Machine Service | Machine token (`require_whatsapp_machine`) |
| 53 | `POST /api/v1/hermes/whatsapp/status` | `whatsapp_state:operational_status` | Machine Service | Machine token + phone role check |
| 54 | `POST /api/v1/hermes/whatsapp/clarifications/expire` | `whatsapp_state:expire_clarifications` | Machine Service | Machine token (`require_whatsapp_machine`) |
| 55 | `POST /api/v1/hermes/whatsapp/clarifications/reply` | `whatsapp_state:clarification_reply` | Machine Service | Machine token (`require_whatsapp_machine`) |
| 56 | `POST /api/v1/hermes/whatsapp/clarifications/open` | `whatsapp_state:open_clarification` | Machine Service | Machine token (`require_whatsapp_machine`) |
| 57 | `POST /api/v1/hermes/whatsapp/notifications` | `whatsapp_state:pending_notifications` | Machine Service | Machine token (`require_whatsapp_machine`) |
| 58 | `POST /api/v1/hermes/whatsapp/notifications/claim` | `whatsapp_state:claim_notice` | Machine Service | Machine token (`require_whatsapp_machine`) |
| 59 | `POST /api/v1/hermes/whatsapp/notifications/finish` | `whatsapp_state:finish_notice` | Machine Service | Machine token (`require_whatsapp_machine`) |
