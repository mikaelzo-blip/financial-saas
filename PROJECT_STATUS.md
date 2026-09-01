# Project Status

- **Current origin/main baseline**: `f8e2dd8`
- **Completed features**: 001 Contractor Finance System; 002 Core Financial Domain; 003 Core Operational UI; 004 Financial Reporting; 005 Document Intelligence; 006 Hermes Automation; 007 WhatsApp Integration; 008 AI Management Insights; 009 Production Readiness Foundation; 010 Dependency Security Gates; UAT Findings #1-#3
- **Current feature**: Local UAT #4 — Customer Invoice and Accounts Receivable
- **Current branch**: `hermes/uat-4-customer-invoice`
- **Latest verified checkpoint**: `CUSTOMER_INVOICE` manual entry posts Policy B (Dr 1201 / Cr 4101), creates tenant-scoped AR, preserves cash and project cost, and keeps document/WhatsApp candidates on the same authoritative transaction workflow.
- **UAT data**: `INV-DEMO-001`, Rp25,000,000, outstanding Rp25,000,000, cash Rp95,000,000, project cost Rp5,000,000, revenue Rp25,000,000.
- **Tests**: 191 backend tests passed; frontend tests, typecheck, lint, build, production audit, migration SQL generation, repository safety, and accounting consistency gates passed.
- **Accounting integrity**: total debit equals total credit; Assets Rp120,000,000 = Liabilities Rp0 + Equity Rp120,000,000.
- **Outstanding blockers**: GitHub PR, mandatory CI, squash merge, and runtime worktree synchronization.
- **Next UAT**: UAT #5 — Customer Payment allocation and cash receipt against `INV-DEMO-001`; do not create duplicate revenue recognition.
