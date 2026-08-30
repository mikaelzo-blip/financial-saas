# Quickstart & Verification Guide: WhatsApp Operational Messaging

**Feature Branch**: `007-whatsapp-integration`  
**Date**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [specs/007-whatsapp-integration/spec.md](file:///c:/Projects/financial-saas/specs/007-whatsapp-integration/spec.md)

---

## 1. Prerequisites

1. Backend Python environment active (`pytest` and `httpx` installed).
2. Database test engine running (SQLite async or PostgreSQL test database).
3. Test environment variables configured:
   ```env
   WHATSAPP_PROVIDER=mock
   WHATSAPP_VERIFY_TOKEN=test_verify_token_123
   WHATSAPP_WEBHOOK_APP_SECRET=test_app_secret_456
   HERMES_AGENT_TOKEN=test_hermes_machine_token
   ```

---

## 2. End-to-End Verification Scenarios

### Scenario A: Meta Webhook GET Handshake
1. Send HTTP `GET /api/v1/integrations/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=test_verify_token_123&hub.challenge=88991122`.
2. **Expected Response**: Status `200 OK`, body text `88991122`.

### Scenario B: Registered Sender Media Intake (Nota Photo + Caption)
1. Pre-register sender `+6281234567890` for `Organization Alpha`.
2. Compute HMAC-SHA256 signature for the inbound mock webhook payload containing an image message with caption *"Nota 50 sak semen Proyek Ruko Thamrin"*.
3. Send HTTP `POST /api/v1/integrations/whatsapp/webhook` with header `X-Hub-Signature-256`.
4. **Expected Outcome**:
   - Webhook returns `200 OK` with status `{"status": "success"}`.
   - Mock provider receives outbound reply: *"✅ Nota diterima [DOC-xxxx]. Sedang diproses OCR."*
   - Document record created in Feature 005 Document Intelligence with `source_channel="WHATSAPP"` and caption in `source_metadata`.

### Scenario C: Webhook Idempotency & Replay Protection
1. Resend the exact same webhook payload and `X-Hub-Signature-256` from Scenario B (identical `wamid`).
2. **Expected Outcome**:
   - Webhook returns `200 OK` immediately.
   - Zero duplicate `Document` records created.
   - Zero duplicate outbound reply messages dispatched.

### Scenario D: Unregistered Sender Safe Rejection
1. Send an inbound mock webhook from unknown phone number `+6289999999999`.
2. **Expected Outcome**:
   - Webhook returns `200 OK`.
   - Outbound reply sent: *"Nomor Anda belum terdaftar pada sistem keuangan. Silakan hubungi Administrator organisasi Anda."*
   - Zero financial records created in database.

### Scenario E: Interactive Clarification Loop
1. Initialize a `WhatsAppClarificationSession` for `+6281234567890` linked to `DOC-002` (Review Queue item with options `1: Proyek Thamrin`, `2: Proyek BSD`).
2. Send an inbound mock webhook text message containing body `"1"`.
3. **Expected Outcome**:
   - Clarification session marked `ANSWERED`.
   - `DOC-002` project updated to Proyek Thamrin in Review Queue.
   - Outbound reply sent: *"✅ Terima kasih, proyek berhasil diperbarui."*

### Scenario F: Multi-Tenant Data Isolation
1. Register `+62811111111` under Tenant A and `+62822222222` under Tenant B.
2. Send simultaneous media intake webhooks for both senders.
3. **Expected Outcome**:
   - Tenant A's document is strictly associated with Tenant A's `organization_id`.
   - Tenant B's document is strictly associated with Tenant B's `organization_id`.
   - Cross-querying Tenant A with Tenant B credentials yields zero results.
