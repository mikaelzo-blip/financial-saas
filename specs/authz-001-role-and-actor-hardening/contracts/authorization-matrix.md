# Contract: Complete Authorization and Role Enforcement Matrix

**Remediation**: AUTHZ-001 & AUTH-002  
**Specification**: [specs/authz-001-role-and-actor-hardening/spec.md](../spec.md)  
**Baseline Commit**: `3d516096cc0085eb3e5e7273f6be57ec5c7d876c`  
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
2. **Machine Service Endpoints**: **14 routes** (1 Hermes OCR intake + 13 WhatsApp state machine routes).
3. **Verified Webhook Endpoints**: **2 routes** (`/api/v1/whatsapp/webhook` & `/api/v1/integrations/whatsapp/webhook`).
4. **Public Auth Endpoints**: **1 route** (`POST /api/v1/auth/login`).

---

## 2. The 19 Vulnerable Human Application Mutating Endpoints

These 19 endpoints currently lack effective backend role enforcement, allow `VIEWER` mutation, or rely on caller-controlled actor identity (`X-User-ID` / `get_current_user_id`):

| # | Method & Path | Router & Handler | Auth Source | Tenant Source | Actor Source | Role Check | Current Allowed Roles | Financial / Business Effect | Machine / Human | Current Test Coverage | Proposed Policy Matrix (ADMIN / MANAGER / OPERATOR / VIEWER) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `POST /api/v1/transactions` | `transactions:create_transaction:23` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Creates draft unposted transaction candidate | Human | `test_business_flows.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 2 | `POST /api/v1/projects` | `projects:create_project:23` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Creates Project master record (contract value, customer) | Human | `test_ai_isolation.py`, `test_counterparty_project_api.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 3 | `PATCH /api/v1/projects/{project_id}/status` | `projects:update_project_status:73` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Transitions project lifecycle status; enforces financial closure guards | Human | `test_uat10_project_completion_retention.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: DENY<br>VIEWER: DENY |
| 4 | `POST /api/v1/projects/{project_id}/budgets` | `projects:add_or_update_project_budget:108` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Sets cost category budget allocations for a project | Human | None | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: DENY<br>VIEWER: DENY |
| 5 | `POST /api/v1/counterparties` | `counterparties:create_counterparty:48` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Creates Counterparty master record (Customer/Vendor) | Human | `test_counterparty_project_api.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 6 | `POST /api/v1/coa` | `reference_data:create_coa:36` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Creates new Chart of Accounts general ledger account | Human | None | ADMIN: ALLOW<br>MANAGER: DENY<br>OPERATOR: DENY<br>VIEWER: DENY |
| 7 | `POST /api/v1/payment-accounts` | `reference_data:create_payment_account:69` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Creates bank account / cash register reference entity | Human | `test_payment_account_api.py` | ADMIN: ALLOW<br>MANAGER: DENY<br>OPERATOR: DENY<br>VIEWER: DENY |
| 8 | `POST /api/v1/money-movements` | `money_movements:create_money_movement:36` | JWT (`application_router`) | Header (`get_current_org_id`) | None (ignored) | None | Any authenticated (incl. VIEWER) | Creates MoneyMovement, settlements, & allocations | Human | `test_money_movement_p1.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 9 | `POST /api/v1/bank-reconciliation/imports` | `bank_reconciliation:upload_bank_statement:21` | JWT (`application_router`) | Header (`get_current_org_id`) | None (ignored) | None | Any authenticated (incl. VIEWER) | Ingests bank statement file/lines and creates import | Human | None | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 10 | `POST /api/v1/bank-reconciliation/imports/{import_id}/auto-match` | `bank_reconciliation:auto_match_statement:56` | JWT (`application_router`) | Header (`get_current_org_id`) | None (ignored) | None | Any authenticated (incl. VIEWER) | Executes automated match against ledger/money movements | Human | `test_ocr_pipeline_integrity_regression.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 11 | `POST /api/v1/bank-reconciliation/reconcile` | `bank_reconciliation:manual_reconcile:71` | JWT (`application_router`) | Header (`get_current_org_id`) | User ID (`matched_by`) | None | Any authenticated (incl. VIEWER) | Creates manual match between bank statement line & trx | Human | None | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 12 | `POST /api/v1/documents/upload` | `documents:upload_document:54` | JWT (`application_router`) | Header (`get_current_org_id`) | Caller Header (`get_current_user_id`) | None | Any authenticated (incl. VIEWER) | Ingests source document, calculates SHA-256, triggers OCR | Human | `test_document_upload.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 13 | `POST /api/v1/documents/{document_id}/retry` | `documents:retry_document:104` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Retries OCR extraction on failed/flagged document | Human | `test_document_upload.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 14 | `POST /api/v1/documents/{document_id}/corrections` | `documents:correct_document:118` | JWT (`application_router`) | Header (`get_current_org_id`) | Caller Header (`get_current_user_id`) | In-body `require_reviewer` | Spoofable via `X-User-ID` | Mutates extraction candidate fields & clears review flags | Human | `test_document_review_uat11.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: DENY<br>VIEWER: DENY |
| 15 | `POST /api/v1/documents/{document_id}/reject` | `documents:reject_document_candidate:268` | JWT (`application_router`) | Header (`get_current_org_id`) | Caller Header (`get_current_user_id`) | In-body `require_reviewer` | Spoofable via `X-User-ID` | Rejects document candidate; audit logged | Human | `test_document_review_uat11.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: DENY<br>VIEWER: DENY |
| 16 | `POST /api/v1/transactions/{transaction_id}/review-flags` | `review:add_review_flag:58` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Adds review flag to transaction; sets `REVIEW_REQUIRED` | Human | `test_review_queue.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 17 | `POST /api/v1/inbox/capture` | `inbox:capture_remote_message:21` | JWT (`application_router`) | Header (`get_current_org_id`) | None | None | Any authenticated (incl. VIEWER) | Ingests remote WhatsApp message into staging queue | Human | None | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 18 | `POST /api/v1/inbox/sync` | `inbox:sync_backlog:37` | JWT (`application_router`) | Header (`get_current_org_id`) | None (ignored) | None | Any authenticated (incl. VIEWER) | Pulls un-synced backlog messages from remote inbox | Human | `test_remote_inbox_p3.py` | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |
| 19 | `POST /api/v1/inbox/sessions/{session_id}/analyze` | `inbox:analyze_document_session:110` | JWT (`application_router`) | Header (`get_current_org_id`) | None (ignored) | None | Any authenticated (incl. VIEWER) | Triggers deferred analysis on inbox document session | Human | None | ADMIN: ALLOW<br>MANAGER: ALLOW<br>OPERATOR: ALLOW<br>VIEWER: DENY |

---

## 3. Previously Hardened or Protected Human Application Mutating Endpoints (23 Routes)

| # | Method & Path | Router & Handler | Auth Source | Role Check Mechanism | Allowed Roles | Financial / Business Effect |
|---|---|---|---|---|---|---|
| 20 | `POST /api/v1/transactions/{transaction_id}/post` | `transactions:post_transaction:73` | JWT | `require_roles` + policy | ADMIN, MANAGER, OPERATOR (routine auto-safe only) | Posts transaction into double-entry journal (Dr == Cr) |
| 21 | `POST /api/v1/transactions/{transaction_id}/approve` | `transactions:approve_transaction:102` | JWT | `require_roles` + policy | ADMIN, MANAGER, OPERATOR (routine auto-safe only) | Authorizes and posts transaction |
| 22 | `POST /api/v1/transactions/opening-balances` | `transactions:establish_opening_balances:131` | JWT | `require_roles` | ADMIN only | Establishes starting general ledger account balances |
| 23 | `POST /api/v1/transactions/{transaction_id}/reverse` | `reversals:reverse_transaction:42` | JWT | `require_roles` | ADMIN, MANAGER | Generates reversal transaction & immutable reversal journal |
| 24 | `POST /api/v1/transactions/{transaction_id}/review-flags/{flag_id}/resolve` | `review:resolve_review_flag:82` | JWT | `require_roles` | ADMIN, MANAGER | Resolves review flag; unblocks transaction posting |
| 25 | `POST /api/v1/vendor-payments` | `payables:record_vendor_payment:118` | JWT | `require_roles` | ADMIN, MANAGER, OPERATOR | Records vendor payment, updates bill, posts journal to GL |
| 26 | `POST /api/v1/customer-invoices/retention-releases` | `receivables:release_customer_retention:142` | JWT | `require_roles` | ADMIN, MANAGER, OPERATOR | Releases retention receivable, posts journal to GL |
| 27 | `POST /api/v1/customer-payments` | `receivables:record_customer_payment:176` | JWT | `require_roles` | ADMIN, MANAGER, OPERATOR | Records customer payment, updates invoice, posts journal to GL |
| 28 | `POST /api/v1/fixed-assets` | `fixed_assets:create_asset:43` | JWT | `require_roles` | ADMIN, MANAGER, OPERATOR | Registers new fixed asset, depreciation parameters |
| 29 | `PATCH /api/v1/fixed-assets/{asset_id}` | `fixed_assets:update_asset:80` | JWT | `require_roles` | ADMIN, MANAGER, OPERATOR | Updates fixed asset details/cost |
| 30 | `PUT /api/v1/fixed-assets/{asset_id}` | `fixed_assets:update_asset:80` | JWT | `require_roles` | ADMIN, MANAGER, OPERATOR | Full update of fixed asset |
| 31 | `POST /api/v1/fixed-assets/{asset_id}/depreciate` | `fixed_assets:depreciate_single_asset:98` | JWT | `require_roles` | ADMIN, MANAGER | Posts depreciation transaction & journal (Dr 6108 / Cr 1502) |
| 32 | `POST /api/v1/fixed-assets/depreciate-batch` | `fixed_assets:depreciate_batch:121` | JWT | `require_roles` | ADMIN, MANAGER | Executes monthly batch depreciation into GL ledger |
| 33 | `POST /api/v1/fixed-assets/{asset_id}/dispose` | `fixed_assets:dispose_asset:142` | JWT | `require_roles` | ADMIN, MANAGER | Disposes asset, calculates gain/loss |
| 34 | `POST /api/v1/documents/{document_id}/approve` | `documents:approve_document_candidate:202` | JWT | `require_roles` + `require_reviewer` | ADMIN, MANAGER | Converts document candidate to Transaction and posts journal |
| 35 | `POST /api/v1/integrations/whatsapp/senders` | `whatsapp_state:create_sender:42` | JWT | `require_whatsapp_admin` | ADMIN only | Registers phone-to-user mapping; audit logged |
| 36 | `DELETE /api/v1/integrations/whatsapp/senders/{mapping_id}` | `whatsapp_state:disable_sender:59` | JWT | `require_whatsapp_admin` | ADMIN only | Deactivates sender mapping; audit logged |
| 37 | `POST /api/v1/periods` | `accounting_periods:create_period:30` | JWT | In-body check (`current_user.role`) | ADMIN, MANAGER | Creates accounting period (OPEN/SOFT_CLOSED/CLOSED) |
| 38 | `PATCH /api/v1/periods/{period_id}/status` | `accounting_periods:update_period_status:42` | JWT | In-body check (`current_user.role`) | ADMIN, MANAGER | Modifies period status; locks/unlocks ledger posting |
| 39 | `POST /api/v1/reports/consultant-reconciliation/reconcile-verified/{year}` | `consultant_reconciliation:reconcile_verified_year:36` | JWT | None (read-only calculation) | Any authenticated | Computes live ledger reconciliation against verified consultant report |
| 40 | `POST /api/v1/reports/consultant-reconciliation/compare` | `consultant_reconciliation:compare_consultant_statement:56` | JWT | None (read-only calculation) | Any authenticated | Compares live ledger against provided consultant data |
| 41 | `POST /api/v1/reports/consultant-reconciliation/upload` | `consultant_reconciliation:upload_consultant_statement:70` | JWT | None (read-only calculation) | Any authenticated | Parses consultant PDF/XLSX and computes reconciliation |
| 42 | `POST /api/v1/insights/query` | `insights:financial_query:52` | JWT (`require_insight_user`) | User-scoped | Any authenticated (incl. VIEWER) | Creates Q&A conversation session & message; runs financial grounding |

---

## 4. Machine Service, Webhook, and Public Endpoints (17 Routes)

These endpoints use dedicated non-browser authentication protocols and are strictly out of scope for browser-user RBAC:

| # | Method & Path | Router & Handler | Classification | Security Mechanism | Notes |
|---|---|---|---|---|---|
| 43 | `POST /api/v1/auth/login` | `auth:login:67` | Public Auth | Public credentials | Verifies password hash; issues JWT bearer token |
| 44 | `POST /api/v1/hermes/documents/upload` | `hermes:upload_document:64` | Machine Service | Machine token (`WHATSAPP_TENANT_TOKENS`) | Ingests document from Hermes runtime; computes SHA-256 |
| 45 | `POST /api/v1/whatsapp/webhook` | `whatsapp:webhook:24` | Verified Webhook | Meta HMAC-SHA256 (`X-Hub-Signature-256`) | Inbound WhatsApp webhook payload ingestion |
| 46 | `POST /api/v1/integrations/whatsapp/webhook` | `whatsapp:webhook:24` | Verified Webhook | Meta HMAC-SHA256 (`X-Hub-Signature-256`) | Alias to route #45 |
| 47 | `POST /api/v1/hermes/whatsapp/documents/get` | `whatsapp_state:channel_document:78` | Machine Service | Machine token (`require_whatsapp_machine`) | Document inquiry from WhatsApp channel adapter |
| 48 | `POST /api/v1/hermes/whatsapp/resolve` | `whatsapp_state:resolve_sender:87` | Machine Service | Adapter bearer token (`WHATSAPP_ADAPTER_TOKEN`) | Resolves incoming phone number to tenant mapping |
| 49 | `POST /api/v1/hermes/whatsapp/rejections/claim` | `whatsapp_state:claim_rejection:98` | Machine Service | Adapter bearer token (`require_adapter`) | Claims rejection notice for unregistered sender |
| 50 | `POST /api/v1/hermes/whatsapp/rejections/finish` | `whatsapp_state:finish_rejection:123` | Machine Service | Adapter bearer token (`require_adapter`) | Finalizes rejection dispatch |
| 51 | `POST /api/v1/hermes/whatsapp/messages/claim` | `whatsapp_state:claim_message:139` | Machine Service | Machine token (`require_whatsapp_machine`) | Worker claims inbound message for OCR processing |
| 52 | `POST /api/v1/hermes/whatsapp/messages/finish` | `whatsapp_state:finish_message:167` | Machine Service | Machine token (`require_whatsapp_machine`) | Updates message status and links Document ID |
| 53 | `POST /api/v1/hermes/whatsapp/status` | `whatsapp_state:operational_status:188` | Machine Service | Machine token + phone role check | WhatsApp operational summary generation |
| 54 | `POST /api/v1/hermes/whatsapp/clarifications/expire` | `whatsapp_state:expire_clarifications:206` | Machine Service | Machine token (`require_whatsapp_machine`) | Periodic expiration of pending clarification sessions |
| 55 | `POST /api/v1/hermes/whatsapp/clarifications/reply` | `whatsapp_state:clarification_reply:218` | Machine Service | Machine token (`require_whatsapp_machine`) | Receives clarification reply from WhatsApp sender |
| 56 | `POST /api/v1/hermes/whatsapp/clarifications/open` | `whatsapp_state:open_clarification:291` | Machine Service | Machine token (`require_whatsapp_machine`) | Opens low-confidence clarification session |
| 57 | `POST /api/v1/hermes/whatsapp/notifications` | `whatsapp_state:pending_notifications:329` | Machine Service | Machine token (`require_whatsapp_machine`) | Worker retrieves pending notifications to deliver |
| 58 | `POST /api/v1/hermes/whatsapp/notifications/claim` | `whatsapp_state:claim_notice:392` | Machine Service | Machine token (`require_whatsapp_machine`) | Worker claims notification before delivery |
| 59 | `POST /api/v1/hermes/whatsapp/notifications/finish` | `whatsapp_state:finish_notice:413` | Machine Service | Machine token (`require_whatsapp_machine`) | Finalizes notification delivery status |

---

## 5. Policy Decisions & Authority Mapping

| Decision ID | Target Endpoint(s) | Recommended Allowed Roles | Alternative Option | Authoritative Precedent & Justification |
|---|---|---|---|---|
| **DECISION-1** | `POST /api/v1/coa` | **ADMIN** | ADMIN, MANAGER | **Constitution Principle V**: Deterministic Accounting Engine. The Chart of Accounts defines allowable financial accounts and mapping rules. Creating GL accounts is a high-privilege administrative action, identical to `POST /transactions/opening-balances` (Admin only per Feature 011). |
| **DECISION-2** | `POST /api/v1/payment-accounts` | **ADMIN** | ADMIN, MANAGER | Setting up corporate bank accounts and cash registers alters the treasury foundation. Restricting to **ADMIN** prevents unauthorized financial accounts. |
| **DECISION-3** | `PATCH /api/v1/projects/{id}/status` | **ADMIN, MANAGER** | ADMIN, MANAGER, OPERATOR | Project status transitions (specifically `COMPLETED` and `CLOSED`) enforce strict financial closure guards, lock out new expense allocations, and trigger retention receivables. Managerial review authority is required. |
| **DECISION-4** | `POST /api/v1/projects/{id}/budgets` | **ADMIN, MANAGER** | ADMIN, MANAGER, OPERATOR | Setting or amending cost category budgets establishes the financial threshold against which project profitability and cost overruns are monitored. |
| **DECISION-5** | `POST /api/v1/bank-reconciliation/reconcile` | **ADMIN, MANAGER, OPERATOR** | ADMIN, MANAGER | Linking a bank statement line to a transaction is routine operational matching; it does not alter transaction postings or create journal entries. |
| **DECISION-6** | `POST /api/v1/documents/{id}/corrections` | **ADMIN, MANAGER** | ADMIN, MANAGER, OPERATOR | **Existing Code Precedent**: `require_reviewer` explicitly checks `User.role.in_([UserRole.ADMIN, UserRole.MANAGER])`. Feature 011 established that resolving flags and review queue actions belong to managerial roles. |
| **DECISION-7** | `POST /reports/consultant-reconciliation/*` | **ADMIN, MANAGER** (or Read-Only) | All Authenticated | These endpoints are non-mutating reporting calculations. If role restrictions are applied, **ADMIN, MANAGER** aligns with access to audited annual statements. |
