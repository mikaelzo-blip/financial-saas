# Project Status

- **Current origin/main baseline**: `eb650d6`
- **Completed features**: 001 Contractor Finance System; 002 Core Financial Domain; 003 Core Operational UI; 004 Financial Reporting; 005 Document Intelligence; 006 Hermes Automation; 007 WhatsApp Integration; 008 AI Management Insights; 009 Production Readiness Foundation; 010 Dependency Security Gates; UAT Findings #1-#3; UAT #4 Customer Invoice; UAT #5 Customer Payment & AR Allocation; UAT #5.1 Active Tenant Identity; UAT #6 Vendor Bill & Accounts Payable; UAT #7 Vendor Payment & Cash Disbursement Safety; UAT #8 Reversal Flow; UAT #9 Financial Reporting; UAT #10 Project Completion & Retention Release; UAT #11 Document Ingestion & Storage Reliability; UAT #12 WhatsApp Media Transport & Review Queue Intake; UAT #13 Real Document Extraction & Candidate Review Flow; UAT #14 End-to-End Operational Workflows & Edge-Case Stress Testing; UAT #15 WhatsApp Sandbox Integration & Production Deployment Dry Run; UAT #16 Real Meta WhatsApp Cloud API Sandbox Pilot.
- **Current feature**: UAT #16 — Real Meta WhatsApp Cloud API Sandbox Pilot
- **Current branch**: `hermes/uat-16-real-meta-whatsapp-pilot`
- **Latest verified checkpoint**: Real Meta WhatsApp Cloud API development sandbox adapter connected and verified via integration test suite; GET `hub.challenge` verification and POST `X-Hub-Signature-256` HMAC validation fail-closed; local HTTPS ingress tunneling architecture documented (`docs/meta-whatsapp-sandbox-pilot-guide.md`); zero direct journal creation from Meta webhook/OCR/classification; duplicate webhook message replay idempotency verified (`wamid` and content SHA-256 deduplication); local Windows PC offline operational model and cloud webhook ingress buffer architecture documented; Review Queue hard-stop preserved.
- **UAT data**: Organization `PT Kontraktor Utama Indonesia` (`9670673b-c0fd-4ebe-87e4-a646358084ea`), Project `PRJ-2026-001` preserved intact.
- **Tests**: 305 backend tests passed (including 5 comprehensive UAT-16 integration suites); 48 frontend tests passed; frontend production build passed, pip check passed, migration valid, npm audit passed (0 vulnerabilities).
- **Accounting integrity**: Total Debit == Total Credit; Assets = Liabilities + Equity; zero orphan AR/AP/retention; zero direct journals from transport ingestion; human review hard-stop preserved.
- **Real Provider Status**:
  - Meta Cloud API Sandbox Adapter: **READY**
  - Meta Developer App / Test Number Ingress Setup: **WAITING FOR USER META SETUP** (Stop point for developer dashboard credentials and local Cloudflare Tunnel execution)
  - Live External Meta Webhook Traffic: **NOT TESTED** (Awaiting user sandbox credentials; live connection will only be labeled LIVE VERIFIED after actual Meta webhook receipt)
  - Production WhatsApp Number: **NOT ACTIVATED** (Development sandbox only)
- **Outstanding blockers**: None.
- **Next Step**: User supplies Meta Developer App credentials and initiates local HTTPS tunnel to execute live sandbox webhook verification.
