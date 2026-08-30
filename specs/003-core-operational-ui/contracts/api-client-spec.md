# Frontend API Client Contract & Endpoint Mapping

**Feature**: `003-core-operational-ui`  
**Date**: 2026-08-30  
**Source OpenAPI**: [openapi.yaml](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/contracts/openapi.yaml)

---

## 1. Base Configuration & Interceptor Rules

- **Base URL**: `/api/v1` (Proxied via Vite dev server to backend `http://127.0.0.1:8000/api/v1`).
- **Default Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <token>` (injected from `auth` store if present)
  - `X-Organization-ID: <orgId>` (injected from active tenant session)
- **Response Handling**:
  - Unwraps standard JSON payloads.
  - Automatically handles 401 Unauthorized $\to$ clears token $\to$ routes to `/login`.
  - Normalizes 422 Unprocessable Entity & 400 Bad Request error detail messages into field-specific error maps.
  - Intercepts 409 Conflict $\to$ triggers duplicate warning dialog.

---

## 2. Typed API Endpoint Mapping Table

| UI View / Screen | Method | Backend Endpoint | Request Payload | Response Schema |
|---|---|---|---|---|
| **Auth** | `POST` | `/auth/login` | `{ email, password }` | `{ access_token, token_type }` |
| **Dashboard** | `GET` | `/dashboard/summary` | Query params (optional dates) | `DashboardSummary` |
| **Projects List** | `GET` | `/projects` | `?status=&page=&limit=` | `ProjectListItem[]` |
| **Create Project** | `POST` | `/projects` | `ProjectCreateInput` | `ProjectResponse` |
| **Project Details** | `GET` | `/projects/{id}` | Path param `id` | `ProjectResponse` |
| **Project Costs & PnL** | `GET` | `/projects/{id}/costs` | Path param `id` | `ProjectCostBreakdown` |
| **Project Profitability**| `GET`| `/projects/{id}/profitability` | Path param `id` | `ProjectProfitabilityResponse` |
| **Project Summary** | `GET` | `/projects/{id}/financial-summary` | Path param `id` | `ProjectFinancialDetail` |
| **Project Status** | `PATCH`| `/projects/{id}/status` | `{ project_status }` | `ProjectResponse` |
| **Transactions List** | `GET` | `/transactions` | `?status=&project_id=&page=` | `TransactionListItem[]` |
| **Create Transaction**| `POST`| `/transactions` | `TransactionFormData` | `TransactionResponse` |
| **Transaction Detail**| `GET` | `/transactions/{id}` | Path param `id` | `TransactionResponse` |
| **Approve Transaction**| `POST`| `/transactions/{id}/approve` | Path param `id` | `TransactionResponse` |
| **Post Transaction** | `POST` | `/transactions/{id}/post` | Path param `id` | `TransactionResponse` |
| **Reverse Transaction**| `POST`| `/transactions/{id}/reverse` | `{ reason: string }` | `TransactionResponse` |
| **Review Queue** | `GET` | `/review-queue` | Query filters | `ReviewQueueItem[]` |
| **Add Review Flag** | `POST` | `/transactions/{id}/review-flags` | `{ flag, message }` | `ReviewFlagItem` |
| **Resolve Review Flag**| `POST`| `/transactions/{id}/review-flags/{flag_id}/resolve` | `{ resolution_notes }` | `ReviewFlagItem` |
| **Upload Document** | `POST` | `/documents/upload` | `multipart/form-data` | `DocumentItem` |
| **Document Details** | `GET` | `/documents/{id}` | Path param `id` | `DocumentItem` |
| **Customer List** | `GET` | `/counterparties?is_customer=true` | Filter query | `CounterpartyItem[]` |
| **Vendor List** | `GET` | `/counterparties?is_vendor=true` | Filter query | `CounterpartyItem[]` |
| **Receivables (AR)** | `GET` | `/customer-invoices` | Query filters | `CustomerInvoiceItem[]` |
| **Payables (AP)** | `GET` | `/vendor-bills` | Query filters | `VendorBillItem[]` |
| **Payment Accounts** | `GET` | `/payment-accounts` | Query filters | `PaymentAccountItem[]` |
| **COA Master** | `GET` | `/coa` | Query filters | `ChartOfAccountItem[]` |
| **Audit Logs** | `GET` | `/audit-logs` | Query filters | `AuditLogItem[]` |
