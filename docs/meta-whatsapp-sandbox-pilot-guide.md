# Meta WhatsApp Cloud API Sandbox Pilot Runbook (UAT #16)

This document provides operational instructions and requirements for connecting Financial SaaS to the real Meta WhatsApp Cloud API development/test environment (Sandbox Pilot) while running the application locally on a Windows PC.

---

## 1. Operating Architecture & Safety Constraints

- **Input Transport Only**: WhatsApp serves purely as an untrusted input ingestion transport.
- **Review Queue Hard-Stop**: Inbound messages, media download, OCR extraction, classification, and candidate creation **never** create `JournalEntry` rows or mutate AR/AP subledgers directly. Only an authorized human operator via the web UI / authenticated API (`POST /api/v1/documents/{id}/approve`) may post transactions into the accounting engine.
- **Zero Production Number Use**: Use **only** Meta's sandbox/test WhatsApp number provided in the Meta Developer Portal. Do **not** use or register production business phone numbers during pilot testing.
- **Fail-Closed Security**: Missing credentials, invalid signatures (`x-hub-signature-256`), invalid handshake tokens (`hub.verify_token`), unknown sender phone numbers, or cross-tenant attempts fail closed with 401/403/422 status codes and 0 side effects.

---

## 2. Configuration & Environment Variables

All secrets must be placed exclusively in `backend/.env` (which is git-ignored) and **never committed to version control**.

| Variable | Requirement | Description / Source |
| :--- | :--- | :--- |
| `WHATSAPP_PROVIDER` | `meta` | Activates `MetaCloudWhatsAppProvider` (defaults to `mock`). |
| `META_APP_SECRET` / `WHATSAPP_WEBHOOK_APP_SECRET` | Required for `meta` | App Secret from Meta App Settings > Basic. Used for `x-hub-signature-256` HMAC validation. |
| `META_VERIFY_TOKEN` / `WHATSAPP_VERIFY_TOKEN` | Required for `meta` | User-chosen secret string configured in Meta Webhooks dashboard. |
| `META_ACCESS_TOKEN` / `WHATSAPP_API_TOKEN` | Required for `meta` | User/System User token with `whatsapp_business_messaging` & `whatsapp_business_management` permissions. |
| `META_PHONE_NUMBER_ID` / `WHATSAPP_PHONE_NUMBER_ID` | Required for `meta` | Numeric Phone Number ID for the test number from WhatsApp > API Setup. |
| `META_WABA_ID` / `WHATSAPP_WABA_ID` | Optional / Tracked | WhatsApp Business Account ID. |
| `META_GRAPH_API_VERSION` / `WHATSAPP_GRAPH_VERSION` | Default: `v26.0` | Meta Graph API Version (e.g. `v26.0`). |
| `WHATSAPP_ADAPTER_TOKEN` | Required | Internal gateway token for adapter routing. |
| `WHATSAPP_TENANT_TOKENS` | Required | JSON mapping of `{ "<organization_id>": "<tenant_machine_token>" }`. |

---

## 3. Local HTTPS Tunnel Setup (Cloudflare Tunnel / ngrok)

Because Meta Cloud API requires a publicly accessible HTTPS URL to deliver webhooks and the Financial SaaS backend is running locally on Windows:

1. **Local Backend Port**: The backend runs on `http://127.0.0.1:8000` (or `http://localhost:8000`).
2. **Tunnel Command (Cloudflare Tunnel)**:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   *Alternative with ngrok:*
   ```bash
   ngrok http 8000
   ```
3. **Public Webhook Endpoint**:
   ```text
   https://<your-tunnel-subdomain>.trycloudflare.com/api/v1/integrations/whatsapp/webhook
   ```
4. **Safety Rule**: Do **not** open firewall ports or configure router port forwarding. Use a temporary, ephemeral HTTPS tunnel only during pilot sessions.

---

## 4. Meta Developer Dashboard Instructions

To configure the sandbox webhook in Meta for Developers:

1. Log in to [Meta for Developers](https://developers.facebook.com/).
2. Select your App (or create a *Business* type app).
3. Under **WhatsApp** > **Configuration** / **API Setup**:
   - Note the **Test Phone Number** (e.g. `+1 555 ...`).
   - Note the **Phone Number ID** (numeric ID).
   - Note the **WhatsApp Business Account ID (WABA ID)**.
   - Generate a **Temporary Access Token** (valid for 24h) or configure a System User Permanent Token.
4. Under **App Settings** > **Basic**:
   - Copy the **App Secret**.
5. Under **WhatsApp** > **Configuration** > **Webhook**:
   - Click **Edit**.
   - **Callback URL**: `https://<tunnel-domain>/api/v1/integrations/whatsapp/webhook`
   - **Verify Token**: Enter your chosen `META_VERIFY_TOKEN`.
   - Click **Verify and Save**. Meta will perform a `GET` handshake with `hub.challenge`.
   - Under Webhook Fields, subscribe to **`messages`**.
6. Under **To** recipient setup:
   - Add your recipient phone number to the allowed test numbers list in Meta API Setup and verify it via SMS/WhatsApp code.

---

## 5. End-to-End Verification Scenarios

### Scenario A: Webhook Handshake & Signature Validation
- Meta issues `GET /api/v1/integrations/whatsapp/webhook?hub.mode=subscribe&hub.challenge=...&hub.verify_token=...`.
- Backend validates token and echoes `hub.challenge` with HTTP 200.
- Tampered or incorrect `hub.verify_token` responds HTTP 403.
- Webhook `POST` with invalid or missing `x-hub-signature-256` responds HTTP 401.

### Scenario B: Multimodal Media Intake (JPG, PDF, PNG)
- Sender sends a JPG transfer proof or PDF invoice from an authorized registered phone number (`WhatsAppSenderMapping`).
- Backend receives webhook event, verifies `wamid`, downloads media bytes from Meta Graph API (`lookaside.fbsbx.com`).
- Backend validates MIME magic bytes, computes SHA-256 content hash, creates `Document` and `HermesSubmission` records (`source_channel=WHATSAPP`).
- Document is staged in Review Queue (`status=PENDING_REVIEW`).
- **Ledger Invariant**: Total Debit = Total Credit = 0; Journal Entries created = 0.

### Scenario C: Deduplication & Replay Resilience
- When Meta retries or duplicates a webhook with an identical `wamid`, the backend handles it idempotently without creating duplicate documents.
- When an identical file content (same SHA-256) is submitted, the system flags `EXACT_FILE_DUPLICATE_FOUND` without creating duplicate financial records.

---

## 6. PC Offline & Production Architecture Guidance

- **Pilot/Dev Model**: When the local Windows PC or tunnel is offline, Meta will retry webhook delivery with exponential backoff for up to 24-36 hours.
- **Production Architecture**:
  - Do **not** rely solely on provider retries in production.
  - The minimum production component required is a lightweight, high-availability, 24/7 ingress edge proxy/queue (e.g. AWS API Gateway + SQS, or a small cloud worker) that immediately acknowledges Meta webhooks (HTTP 200) and enqueues events into a durable broker before backend workers consume them.
