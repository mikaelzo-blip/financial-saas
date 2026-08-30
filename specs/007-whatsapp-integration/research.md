# Technical Research & Architecture Decisions: WhatsApp Operational Messaging

**Feature**: `007-whatsapp-integration`  
**Date**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [specs/007-whatsapp-integration/spec.md](file:///c:/Projects/financial-saas/specs/007-whatsapp-integration/spec.md)

---

## 1. Provider Abstraction & Decoupling Strategy

### Context & Challenge
WhatsApp business messaging requires interacting with an external provider (Meta Cloud API, Twilio, or on-premise WhatsApp Business API). In local development and automated CI/CD pipelines, live WhatsApp credentials, phone numbers, and webhooks are unavailable. Hardcoding a specific vendor API creates vendor lock-in and breaks offline testing.

### Decision
Implement a decoupled `WhatsAppProvider` abstract base class with two concrete implementations:
1. `MockWhatsAppProvider`: In-memory simulator for unit tests, integration tests, and local developer workflows. Stores outbound messages in an in-memory queue, supports simulated incoming webhooks, and returns mock media buffers.
2. `MetaCloudWhatsAppProvider`: Production-grade client using Meta Cloud API v20.0+ for sending text, interactive buttons, and fetching media URLs with `Bearer` access tokens.

### Rationale
- Allows 100% test coverage without external API access or paid developer accounts.
- Clear separation of concerns: The core business logic only interacts with domain events (`InboundMessage`, `OutboundMessage`), completely unaware of vendor-specific JSON payload quirks.

---

## 2. Webhook Security & Signature Verification

### Context & Challenge
Public webhook endpoints receive HTTP POST payloads from the internet. Attackers could forge fake financial receipts or spoof sender phone numbers if the payload is not cryptographically verified.

### Decision
1. **Handshake Verification**: Support Meta's `GET /webhook` challenge protocol (`hub.mode == "subscribe"` and `hub.verify_token`).
2. **HMAC-SHA256 Payload Verification**: Validate the `X-Hub-Signature-256` header on every incoming `POST` request:
   $$\text{Expected Signature} = \text{HMAC-SHA256}(\text{raw\_body}, \text{WHATSAPP\_APP\_SECRET})$$
   Use constant-time string comparison (`hmac.compare_digest`) to prevent timing attacks.
3. **Immediate Rejection**: Any request with an invalid or missing signature is rejected with `HTTP 401 Unauthorized` without reading the payload.

---

## 3. Webhook Idempotency & Duplicate Prevention

### Context & Challenge
WhatsApp webhooks guarantee *at-least-once* delivery. Network glitches, retries from Meta servers, or multiple webhook triggers can deliver the identical message payload multiple times. In a financial system, duplicate document uploads would pollute the database and consume redundant OCR resources.

### Decision
Multi-layer idempotency guard:
1. **Layer 1: Message ID Cache (`wamid`)**: On receiving a webhook, extract `message.id` (`wamid`). Query `WhatsAppMessageLog` using `organization_id` + `wamid`. If an entry exists, respond `HTTP 200 OK` immediately with cached status.
2. **Layer 2: Hermes Client Idempotency**: When forwarding to `/api/v1/hermes/documents/upload`, generate `Idempotency-Key: wa-msg-{wamid}`. Feature 006's `HermesSubmission` ensures database-level deduplication.
3. **Layer 3: Cryptographic File Hash (Feature 005)**: Even if a user sends the exact same image under two different messages, Feature 005's SHA-256 content deduplication rejects duplicate physical files.

---

## 4. Multi-Tenant Sender Mapping Architecture

### Context & Challenge
WhatsApp is an external public network where phone numbers are the only persistent sender identifier. The Financial SaaS is a strict multi-tenant system where data must be isolated by `organization_id`.

### Decision
1. **Sender Mapping Store (`WhatsAppSenderMapping`)**: Map verified international phone numbers (E.164 format: `+62...`) to `User` and `Organization`.
2. **Sender Validation Pipeline**:
   ```text
   Webhook Inbound (+628123456789)
         │
         ▼
   [Lookup WhatsAppSenderMapping by Phone]
         │
         ├── Found & Active ──► Extract (organization_id, user_id, role)
         │
         └── Not Found / Inactive
                   │
                   ▼
         [Send Safe Unregistered Notification via WhatsApp]
                   │
                   ▼
         [Log REJECTED to Audit, Halt Processing]
   ```
3. **Strict Isolation**: The extracted `organization_id` is passed as tenant context to the Hermes client, ensuring that incoming files and metadata cannot bleed into other organizations.

---

## 5. Media Download & Security Stream Pipeline

### Context & Challenge
WhatsApp images and PDFs are not embedded directly in the webhook payload; Meta sends a `media_id`. The application must fetch the temporary media download URL, download binary data, and forward it to Feature 005 without writing insecure files to public storage or exhausting memory.

### Decision
1. **Authenticated Media URL Retrieval**: Request `GET https://graph.facebook.com/v20.0/{media_id}` with `Bearer WHATSAPP_API_TOKEN` to retrieve the temporary download URL and MIME type.
2. **Memory-Safe Streaming**: Stream the binary content directly using `httpx.AsyncClient` with a strict byte limit ($25 \text{ MB}$).
3. **MIME Validation**: Verify MIME against allowed whitelist (`image/jpeg`, `image/png`, `image/webp`, `application/pdf`). Reject executables or unexpected file formats.
4. **Zero Local Persistence**: Forward bytes directly as an `io.BytesIO` / multipart upload to `/api/v1/hermes/documents/upload`, letting Feature 005 manage the immutable tenant storage.

---

## 6. Interactive Review Prompts & Session State

### Context & Challenge
When OCR detects an ambiguous transaction (e.g. nota without a project name), asking the user to choose from a list of active projects requires maintaining a short-lived conversational state so that when the user replies `"1"`, the system knows which document is being resolved.

### Decision
1. **Entity `WhatsAppClarificationSession`**: Stores active conversational questions with:
   - `document_id`: UUID
   - `phone_number`: String
   - `options_payload`: JSON mapping (e.g. `{"1": "uuid-proj-1", "2": "uuid-proj-2"}`)
   - `expires_at`: UTC Timestamp ($24 \text{ hours}$)
   - `status`: `PENDING` | `ANSWERED` | `EXPIRED`
2. **Resolution Lifecycle**: When an incoming text matches a pending session for that phone number, the adapter resolves the entity ID, calls the SaaS Review Queue API (`PUT /api/v1/review/{document_id}/fields`), marks the session `ANSWERED`, and sends a confirmation back to WhatsApp.
3. **Safe Fallback**: Free-form text that does not match expected option numbers prompts a gentle reminder message without corrupting transaction state.

---

## 7. Rate Limiting & DoS Protection

### Context & Challenge
Spam messages, malfunctioning automated senders, or deliberate flood attacks could overwhelm OCR and AI extraction services.

### Decision
Implement in-memory sliding window rate limiting per phone number:
- Maximum 20 requests per minute per sender.
- If exceeded, drop the message and send a single rate-limit warning: *"Mohon tunggu beberapa saat sebelum mengirimkan dokumen berikutnya."*
