# Financial SaaS Durable Capture Edge Relay (Cloudflare Worker + D1 + R2)

## Overview
The **Edge Relay** provides 24/7 durable intake for WhatsApp financial documents when the on-premise Finance PC is powered off or disconnected.

### Architecture & Security Invariants
- **No Accounting in Cloud**: The edge relay only stores encrypted raw payloads and media in durable storage (Cloudflare D1 metadata + Cloudflare R2 object storage).
- **Zero Ledger Mutation**: Edge capture NEVER creates journal entries, balances, or financial adjustments.
- **Evidentiary Grounding**: Every document attachment has its SHA-256 cryptographic hash calculated at ingress and verified upon local persistence.
- **Idempotency**: Webhooks are deduplicated by WhatsApp Message ID (`wamid`).
- **Sender Allowlist**: Only verified team and vendor phone numbers configured in `sender_allowlist` are accepted.

---

## Local Development & Simulation
The full capture workflow can be tested and verified **locally without any Cloudflare account or credentials** using the built-in emulator:

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/unit/test_r1_durable_pc_off_simulation.py
```

This simulates:
1. External WhatsApp receipt while Finance PC is OFF.
2. Durable edge capture with WAMID deduplication and media SHA-256 storage.
3. Finance PC boot and automated lease/sync via `RemoteInboxClient`.
4. Evidentiary file hash verification and Document persistence.
5. Invariant check: zero journal entries created during capture.

---

## Cloud Deployment Guide (When Ready for External Provisioning)

### Prerequisites
1. Node.js 18+ and `npm` installed.
2. Cloudflare account (free tier supports Workers, D1, and R2).
3. Cloudflare Wrangler CLI (`npm install -g wrangler`).

### 1. Authenticate with Cloudflare
```bash
npx wrangler login
```

### 2. Create D1 Database and R2 Bucket
```bash
# Create D1 database
npx wrangler d1 create financial-saas-inbox

# Note the database_id in the output and paste it into wrangler.toml:
# [[d1_databases]]
# database_id = "<your-d1-database-id>"

# Create R2 bucket for media files
npx wrangler r2 bucket create financial-saas-inbox-media
```

### 3. Apply D1 Schema
```bash
npx wrangler d1 execute financial-saas-inbox --remote --file=./schema.sql
```

### 4. Configure Environment Secrets
```bash
# Generate a secure 32+ character key for Finance PC synchronization
npx wrangler secret put RELAY_API_KEY

# Meta WhatsApp Webhook Verify Token
npx wrangler secret put WHATSAPP_VERIFY_TOKEN
```

### 5. Deploy Worker
```bash
npx wrangler deploy
```

---

## Finance PC Configuration
In the local Finance PC `.env` configuration:
```env
REMOTE_INBOX_RELAY_URL=https://financial-saas-edge-relay.<your-subdomain>.workers.dev
REMOTE_INBOX_API_KEY=<value-of-RELAY_API_KEY>
REMOTE_INBOX_POLL_INTERVAL_SECONDS=60
```
