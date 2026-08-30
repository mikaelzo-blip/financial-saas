# Research & Technical Decisions: Web SaaS Application — Core Operational UI

**Feature**: `003-core-operational-ui`  
**Date**: 2026-08-30  
**Status**: Approved

---

## 1. Frontend Framework & Tooling

### Decision
Use **React 19 + TypeScript + Vite + TailwindCSS** as a single-page application (SPA).

### Rationale
- **Single Page App Simplicity**: The SaaS application is a dashboard-driven internal operational tool requiring high interactivity, rapid table filtering, reactive forms, and modal workflows. A Vite-powered React SPA provides lightning-fast HMR (<50ms), minimal bundle size, and clean client-side routing.
- **TypeScript Strict Mode**: Guarantees complete end-to-end type safety against the backend OpenAPI contract.
- **TailwindCSS**: Delivers a crisp, modern, high-contrast operational SaaS aesthetic with dense financial tables, standard responsive utilities, and custom status badge palettes without runtime CSS overhead.
- **Node.js Compatibility**: Fully supported in local environment (Node.js v24.19.0 / npm 11.17.0).

### Alternatives Evaluated
- *Next.js (App Router / SSR)*: Next.js adds unnecessary server complexity, SSR lifecycle management, and node server runtime for an authenticated operational tool that interacts exclusively with the FastAPI backend via REST JSON APIs.
- *Vue / Nuxt*: React has the broadest ecosystem for enterprise data tables, form state management (React Hook Form / Zod), and chart/dashboard primitives.

---

## 2. State Management & API Client

### Decision
Use **TanStack Query (React Query v5) + Axios** for server state, paired with a typed API client generated from the authoritative `openapi.yaml`.

### Rationale
- **Automatic Caching & Invalidation**: TanStack Query handles background refetching, query deduplication, optimistic updates, and cache invalidation upon mutations (e.g. invalidating `/review-queue` and `/transactions` after posting or resolving flags).
- **Axios Interceptors**:
  - Automatically attaches `Authorization: Bearer <token>` and `X-Organization-ID: <org_id>` headers on all outbound requests.
  - Automatically intercepts 401 Unauthorized errors and redirects to `/login`.
  - Normalizes FastAPI error responses (`detail` arrays and custom error objects) into user-friendly Bahasa Indonesia toast alerts.

### Alternatives Evaluated
- *Redux Toolkit / Zustand for Server State*: Storing server state in global client stores leads to cache synchronization bugs. TanStack Query specializes in server state synchronization.

---

## 3. Form Handling & Validation

### Decision
Use **React Hook Form + Zod**.

### Rationale
- **High Performance**: Uncontrolled components with micro-subscriptions prevent unnecessary re-renders in complex multi-project split forms.
- **Zod Schema Validation**: Mirrors FastAPI Pydantic schema validation on the client side, giving instant inline error messages for nominal mismatches ($\sum \text{Allocations} \neq \text{Total}$), missing fields, and date boundaries before network submission.

---

## 4. Financial Display & Currency Formatting

### Decision
Use custom utility `formatIDR(value: number | string | Decimal)` using `Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' })` with tabular font numbers (`font-mono` / `tabular-nums`).

### Rationale
- **Exact Visual Representation**: Formats `150000000.00` as `Rp 150.000.000,00` or compact `Rp 150 Jt` in metric summary cards.
- **No Client Accounting Computation**: The frontend strictly displays numbers returned by the backend. Calculations such as $\text{Revised Contract} = \text{Original} + \text{VO}$, $\text{Margin \%} = (\text{Profit} / \text{Revenue}) \times 100$, and $\text{Outstanding} = \text{Total} - \text{Paid}$ are computed and served by backend endpoints.

---

## 5. UI Component & Design System Architecture

### Decision
Custom component library built with **TailwindCSS + Lucide Icons + Headless UI / Radix Primitives**.

### Core Reusable Primitives:
1. `AppLayout`: Responsive sidebar, breadcrumbs, tenant switcher, user profile popover.
2. `DataTable`: Dense financial table with sorting, pagination, column search, loading skeletons, and empty state triggers.
3. `StatCard`: Operational KPI card with trend badges and drilldown navigation links.
4. `StatusBadge`: Semantic badge for `WorkflowStatus`, `ProjectStatus`, `ReviewFlag`, and `CollectionStatus`.
5. `Modal` / `Drawer`: High-performance modal overlay for payment allocations, flag resolutions, and document preview split-views.
6. `DocumentViewer`: In-browser PDF and image modal with zoom and metadata inspector.
7. `ConfirmDialog`: Safeguard confirmation modal for sensitive and destructive operations (Reversals, dirty form abandonment).

---

## 6. Testing Strategy

### Decision
- **Unit & Component Testing**: **Vitest + React Testing Library**.
- **Mocking**: **MSW (Mock Service Worker)** for network-level API mocking based on `openapi.yaml`.
- **E2E / Workflow Testing**: Component integration tests covering all 10 primary user journeys.
