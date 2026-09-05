# Project Status

- **Current origin/main baseline**: `ee83250` (PR #42 merged)
- **Completed features**: 001 Contractor Finance System; 002 Core Financial Domain; 003 Core Operational UI; 004 Financial Reporting; 005 Document Intelligence; 006 Hermes Automation; 007 WhatsApp Integration; 008 AI Management Insights; 009 Production Readiness Foundation; 010 Dependency Security Gates; UAT Findings #1-#3; UAT #4 Customer Invoice; UAT #5 Customer Payment & AR Allocation; UAT #5.1 Active Tenant Identity; UAT #6 Vendor Bill & Accounts Payable; UAT #7 Vendor Payment & Cash Disbursement Safety; UAT #8 Reversal Flow; UAT #9 Financial Reporting; UAT #10 Project Completion & Retention Release; UAT #11 Document Ingestion & Storage Reliability; UAT #12 WhatsApp Media Transport & Review Queue Intake; UAT #13 Real Document Extraction & Candidate Review Flow; UAT #14 End-to-End Operational Workflows & Edge-Case Stress Testing; UAT #15 WhatsApp Sandbox Integration & Production Deployment Dry Run; UAT #16 Real Meta WhatsApp Cloud API Sandbox Pilot; UAT #17 Real WhatsApp Media Intake (Baileys Bridge); PRD v2.0 Remediation Program (Phases P0–P7).
- **Current feature**: PRD v2.0 Remediation Program Complete (P0 through P7)
- **Current branch**: `hermes/prd-v2-remediation`
- **Execution state**: ACTIVE. All phases P0–P7 from `docs/PRD_Financial_SaaS_v2_Technical_Remediation_Plan.md` are fully implemented, verified, and passing.
- **Latest verified checkpoint**: P7 Reliability & Operations implemented with PostgreSQL-backed background job queue, sequence safety, and health/readiness endpoints. PostgreSQL migrations through `020_p7_background_jobs` applied. Total backend test suite: 165 unit tests, 151 integration tests (316 total, 0 failures). Frontend build and test passing.
- **UAT data**: Organization `PT Kontraktor Utama Indonesia` (`9670673b-c0fd-4ebe-87e4-a646358084ea`), Project `PRJ-2026-001`, registered sender Muhammad Fikri, journals, transactions, and balances preserved intact.
- **Tests**: 165 unit tests passing, 153 integration tests passing (including live PostgreSQL verification), 48 frontend tests passing; zero regressions. Frontend production build passing.
- **Accounting integrity**: Total Debit == Total Credit; Assets = Liabilities + Equity; zero orphan AR/AP/retention; zero direct journals from transport ingestion; human review hard-stop preserved; period closing guards enforced.
- **Real Provider Status**:
  - Meta Cloud API Sandbox Adapter: **PRESERVED AS INACTIVE/FUTURE TRANSPORT**
  - Hermes Baileys WhatsApp Web Bridge: **ACTIVE TRANSPORT FOR UAT #17**
  - Receiver / Bot Number: `+6285184549522` (Keuangan-CBL)
  - Allowed Sender Number: `+6285712342760` (Muhammad Fikri)
  - Pair Mode: Bot Mode (`WHATSAPP_MODE=bot`, `WHATSAPP_ALLOWED_USERS=+6285712342760`)
- **Outstanding blockers**: None. Implementation and automated verification complete. Ready for Phase 7 (QR pairing).
- **Next Step**: Launch Hermes Baileys bridge in bot mode with session directory and QR pairing display, user scans QR via WhatsApp Linked Devices on +6285184549522.
