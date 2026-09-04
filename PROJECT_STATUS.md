# Project Status

- **Current origin/main baseline**: `63d9eaddcd5edc4e95021ac80f150f14adfb3915`
- **Completed features**: 001 Contractor Finance System; 002 Core Financial Domain; 003 Core Operational UI; 004 Financial Reporting; 005 Document Intelligence; 006 Hermes Automation; 007 WhatsApp Integration; 008 AI Management Insights; 009 Production Readiness Foundation; 010 Dependency Security Gates; UAT Findings #1-#3; UAT #4 Customer Invoice; UAT #5 Customer Payment & AR Allocation; UAT #5.1 Active Tenant Identity; UAT #6 Vendor Bill & Accounts Payable; UAT #7 Vendor Payment & Cash Disbursement Safety; UAT #8 Reversal Flow; UAT #9 Financial Reporting; UAT #10 Project Completion & Retention Release; UAT #11 Document Ingestion & Storage Reliability; UAT #12 WhatsApp Media Transport & Review Queue Intake; UAT #13 Real Document Extraction & Candidate Review Flow; UAT #14 End-to-End Operational Workflows & Edge-Case Stress Testing; UAT #15 WhatsApp Sandbox Integration & Production Deployment Dry Run; UAT #16 Real Meta WhatsApp Cloud API Sandbox Pilot (Live Handshake & Routing Verified).
- **Current feature**: UAT #17 — Real WhatsApp Media Intake
- **Current branch**: `hermes/uat-17-real-whatsapp-media`
- **Latest verified checkpoint**: UAT #16 completed and merged via PR #40. Real Meta WhatsApp Cloud API sandbox adapter connected and verified via live Meta webhook handshake; GET `hub.challenge` verification and POST `X-Hub-Signature-256` HMAC validation fail-closed; public ingress tunnel via Cloudflare forwarding to `/api/v1/integrations/whatsapp/webhook` verified live with Meta Developers Dashboard; messages field v26.0 subscribed; synthetic Meta dashboard test payload verified safe and fail-closed; zero direct journal creation or transaction mutation from transport ingestion; Review Queue hard-stop preserved.
- **UAT data**: Organization `PT Kontraktor Utama Indonesia` (`9670673b-c0fd-4ebe-87e4-a646358084ea`), Project `PRJ-2026-001` preserved intact.
- **Tests**: 305 backend tests passed (including unit and integration suites for WhatsApp media transport and Meta sandbox pilot); frontend tests passed; zero regressions.
- **Accounting integrity**: Total Debit == Total Credit; Assets = Liabilities + Equity; zero orphan AR/AP/retention; zero direct journals from transport ingestion; human review hard-stop preserved.
- **Real Provider Status**:
  - Meta Cloud API Sandbox Adapter: **READY**
  - Meta Developer App / Test Number Ingress Setup: **VERIFIED LIVE** (Cloudflare Tunnel handshake accepted; messages field subscribed; test webhook acknowledged)
  - Live External Meta Webhook Traffic: **VERIFIED HANDSHAKE & TEST PAYLOAD** (Live GET challenge verified; POST HMAC fail-closed verified)
  - Production WhatsApp Number: **NOT ACTIVATED** (Development sandbox only)
- **Outstanding blockers**: Meta App must allow real webhook traffic / be published before real phone media intake (Meta Developer Dashboard indicates unpublished apps only deliver test webhooks generated from the dashboard).
- **Next Step**: Prepare sender registration prerequisites, publish/configure Meta App permissions to deliver live phone webhook traffic, register test phone under active tenant organization (`POST /api/v1/integrations/whatsapp/senders`), then verify real WhatsApp image/PDF intake into Document Review Queue.
