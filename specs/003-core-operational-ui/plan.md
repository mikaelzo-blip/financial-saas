# Implementation Plan: Web SaaS Application — Core Operational UI

**Branch**: `003-core-operational-ui` | **Date**: 2026-08-30 | **Spec**: [specs/003-core-operational-ui/spec.md](file:///c:/Projects/financial-saas/specs/003-core-operational-ui/spec.md)

**Input**: Feature specification from `specs/003-core-operational-ui/spec.md`

---

## Summary

Build the frontend single-page web application (SPA) for the Contractor Financial SaaS platform. The application provides an intuitive operational interface designed for non-accountants (no debit/credit exposure) using standard Indonesian contractor financial terminology. All accounting rules, posting logic, balance sheet equations, and approval workflows remain strictly authoritative in the existing FastAPI backend.

---

## Technical Context

- **Language / Runtime**: TypeScript 5.x, Node.js v24.x, npm 11.x
- **Framework & Build Tool**: React 19 + Vite 6
- **Styling & Icons**: TailwindCSS v4 + Lucide Icons
- **State Management & Data Fetching**: TanStack Query (React Query v5) + Axios
- **Forms & Validation**: React Hook Form + Zod
- **Testing**: Vitest + React Testing Library + MSW (Mock Service Worker)
- **Primary Locale**: Bahasa Indonesia (`id-ID`) with exact currency formatting (`Rp 150.000.000,00`)
- **Target Platform**: Desktop-first web (1280px+), responsive to tablet and mobile
- **Backend API**: FastAPI REST service exposing OpenAPI 3.1 at `/api/v1`

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment & Architectural Safeguard | Pass / Fail |
|---|---|---|
| **I. Single Input** | Form captures event once. UI renders derived AR, AP, Project Costs directly from backend responses without duplicate client tables. | ✅ **PASS** |
| **II. Project-Based Accounting** | Project code and metadata attached as analytical dimensions; UI displays derived cost breakdowns by category. | ✅ **PASS** |
| **III. Simple UX** | Zero debit/credit exposure in all user forms. Natural business terms used throughout. | ✅ **PASS** |
| **IV. Double-Entry Accounting** | Frontend does not invent or alter journals; backend enforces $\sum \text{Debit} == \sum \text{Credit}$. | ✅ **PASS** |
| **VII. Source Traceability** | Evidentiary documents attached during intake and previewed side-by-side in Review Queue. | ✅ **PASS** |
| **VIII. Duplicate Prevention** | Client displays SHA-256 duplicate warning modal on 409 responses. | ✅ **PASS** |
| **IX. Human Review** | Dedicated `/review-queue` interface for multi-flag inspection and resolution. | ✅ **PASS** |
| **X. Immutable Posted Records** | Posted transactions rendered in read-only mode with dedicated 3-step Reversal modal. | ✅ **PASS** |
| **XVIII. API Boundary** | Frontend communicates exclusively through authenticated REST APIs with JWT headers. Zero direct DB access. | ✅ **PASS** |

---

## Project Structure

```text
financial-saas/
├── backend/                  # Existing authoritative FastAPI financial service
└── frontend/                 # [NEW] Single Page React Application
    ├── public/               # Favicons, logo, static brand assets
    ├── src/
    │   ├── api/              # Typed API clients & Axios interceptors
    │   │   ├── client.ts     # Axios instance with auth & org-id interceptors
    │   │   ├── auth.ts       # Login, refresh, profile endpoints
    │   │   ├── projects.ts   # Project master, budgets, costs & profitability
    │   │   ├── transactions.ts # Intake, approval, posting, reversal
    │   │   ├── documents.ts  # Upload, preview, metadata
    │   │   ├── review.ts     # Review queue & flag resolution
    │   │   ├── receivables.ts # Customer invoices & AR payments
    │   │   ├── payables.ts   # Vendor bills & AP payments
    │   │   ├── master.ts     # Counterparties, payment accounts, COA
    │   │   └── dashboard.ts  # Operational summary metrics
    │   ├── components/       # Reusable design system primitives
    │   │   ├── ui/           # Buttons, Inputs, Selects, Badges, Modals, Cards
    │   │   ├── layout/       # AppShell, Sidebar, TopHeader, Breadcrumbs
    │   │   ├── tables/       # Dense DataTable with search, filters, pagination
    │   │   ├── forms/        # FormField, CurrencyInput, DatePicker, FileDropzone
    │   │   ├── feedback/     # Toast, SkeletonLoader, EmptyState, ConfirmDialog
    │   │   └── documents/    # DocumentPreviewModal, SplitViewDrawer
    │   ├── hooks/            # Custom React hooks (useAuth, useCurrency, useConfirm)
    │   ├── pages/            # Primary application route views
    │   │   ├── auth/         # LoginPage
    │   │   ├── dashboard/    # DashboardPage
    │   │   ├── projects/     # ProjectListPage, ProjectCreatePage, ProjectDetailPage
    │   │   ├── transactions/ # TransactionListPage, TransactionCreatePage, TransactionDetailPage
    │   │   ├── review/       # ReviewQueuePage
    │   │   ├── receivables/  # ReceivablesPage, InvoiceDetailPage
    │   │   ├── payables/     # PayablesPage, BillDetailPage
    │   │   ├── documents/    # DocumentListPage, DocumentUploadPage
    │   │   ├── master/       # CustomersPage, VendorsPage, PaymentAccountsPage, COAPage
    │   │   └── settings/     # SettingsPage, UsersPage, AuditLogsPage
    │   ├── router/           # React Router route configuration with ProtectedRoute guards
    │   ├── store/            # AuthContext / global UI session state
    │   ├── types/            # TypeScript interfaces & view models
    │   ├── utils/            # formatIDR, formatDate, validationSchemas
    │   ├── App.tsx           # Root application component
    │   ├── main.tsx          # Vite entrypoint
    │   └── index.css         # TailwindCSS root styles
    ├── tests/                # Vitest unit & component test suites
    │   ├── components/       # UI primitive tests
    │   ├── forms/            # Form validation & multi-project split tests
    │   ├── pages/            # Page integration tests
    │   └── mocks/            # MSW mock handlers
    ├── index.html            # HTML shell
    ├── package.json          # Dependencies & scripts
    ├── tsconfig.json         # TypeScript configuration
    ├── vite.config.ts        # Vite configuration with API proxy
    └── tailwind.config.js    # Tailwind theme & color tokens
```

---

## Complexity & Risk Mitigation

| Risk | Mitigation |
|---|---|
| Floating-point currency errors in frontend display | Frontend treats nominal amounts as strings / decimals from API, formatting strictly via `formatIDR` without arithmetic mutation. |
| Inadvertent client-side business logic | All calculations (e.g. margin %, gross profit, revised contract, trial balance) originate from backend endpoints. |
| Large transaction table latency | Server-side pagination and debounce search ensure fluid 60fps table interactions. |
| Unauthorized action execution | Frontend hides unauthorized buttons, and backend enforces 403 Forbidden on all state mutations. |
