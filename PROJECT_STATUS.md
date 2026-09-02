# Project Status

- **Current origin/main baseline**: `5a17495`
- **Completed features**: 001 Contractor Finance System; 002 Core Financial Domain; 003 Core Operational UI; 004 Financial Reporting; 005 Document Intelligence; 006 Hermes Automation; 007 WhatsApp Integration; 008 AI Management Insights; 009 Production Readiness Foundation; 010 Dependency Security Gates; UAT Findings #1-#3; UAT #4 Customer Invoice; UAT #5 Customer Payment & AR Allocation; UAT #5.1 Active Tenant Identity; UAT #6 Vendor Bill & Accounts Payable
- **Current feature**: Local UAT #6 — Vendor Bill & Accounts Payable
- **Current branch**: `hermes/uat-6-vendor-bill-ap`
- **Latest verified checkpoint**: `VENDOR_BILL` manual and API entry posts `Dr 5101 (Harga Pokok Proyek / MAT) Rp12,000,000 / Cr 2101 (Utang Usaha) Rp12,000,000`, generates subledger `VendorBill` (`VINV-DEMO-001`, status `UNPAID`, outstanding Rp12,000,000), preserves cash at Rp120,000,000, updates project cost to Rp17,000,000 and gross profit to Rp8,000,000, exposes tenant-scoped vendor bill & payment endpoints (`/api/v1/vendor-bills`, `/api/v1/vendor-payments`), validates payment allocations and reversal lifecycle (`CANCELLED`), and keeps document/WhatsApp candidates feeding the same domain workflows.
- **UAT data**: `VINV-DEMO-001`, Rp12,000,000, outstanding AP Rp12,000,000, cash Rp120,000,000, project cost Rp17,000,000, revenue Rp25,000,000, gross profit Rp8,000,000.
- **Tests**: 200 backend tests passed; 48 frontend tests passed; typecheck, lint, build, production audit, migration check, repository safety, and accounting consistency gates passed.
- **Accounting integrity**: total debit equals total credit (Rp137,000,000); Assets Rp120,000,000 = Liabilities Rp12,000,000 + Equity Rp108,000,000.
- **Outstanding blockers**: None.
- **Next UAT**: UAT #7 — Vendor Bill Payment and Cash Disbursement against `VINV-DEMO-001` (reduce AP to Rp0 and Cash to Rp108,000,000 without duplicating project cost).
