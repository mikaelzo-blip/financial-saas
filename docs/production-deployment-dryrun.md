# Production Deployment Dry Run & Local Windows PC Operating Model

## Overview
This document specifies the operational architecture, local PC operating model, and production deployment dry-run checklist for the Financial SaaS WhatsApp Integration and core financial backend.

---

## 1. Local-PC Operating Model (Current State)

Financial SaaS is designed to operate primarily on the user's local Windows workstation during development and initial UAT.

### Operating Characteristics:
- **Clean Start / Stop:** The application services (`backend`, `frontend`, `PostgreSQL`) start and stop cleanly without state corruption.
- **Resilience to Downtime:** Inbound webhooks from WhatsApp or other providers are buffered at the provider level (e.g. Meta Cloud API retains undelivered webhooks for up to 24 hours).
- **Zero In-flight Data Loss:** Document ingestion is idempotent based on `wamid` / content-hash (`SHA-256`). Reconnection and restart cleanly replay webhooks without duplicate journal or transaction creation.
- **PostgreSQL Durability:** All database state is persisted to local volume mounts (`pgdata`). No data reset, truncation, or re-seeding occurs on startup/shutdown.
- **No 24/7 Requirement:** Development and UAT do not require the local PC to run 24/7.

---

## 2. Requirements for Real WhatsApp Production Deployment

To transition from local sandbox to a live WhatsApp Business Number, the following components and operational infrastructure must be established:

### A. Network & Public Ingress
1. **Always-Online Public Endpoint:** Meta requires an HTTPS URL accessible 24/7 with valid TLS (Let's Encrypt / Cloudflare SSL).
2. **Reverse Proxy:** Nginx, Caddy, or AWS ALB with:
   - SSL Termination (TLS 1.3)
   - Webhook rate limiting (`200 req/min/org`, `20 req/min/sender`)
   - Max body size capped at 1 MiB for webhooks, 50 MiB for media uploads
3. **Domain & DNS:** Public FQDN (e.g., `https://api.contractor-saas.com`) with DNS A/AAAA records pointing to the ingress.

### B. Environment & Security Configuration
1. **Meta WhatsApp Cloud API Credentials:**
   - `WHATSAPP_PROVIDER=meta`
   - `WHATSAPP_API_TOKEN`: System User Bearer Token generated in Meta Business Manager.
   - `WHATSAPP_PHONE_NUMBER_ID`: Verified WhatsApp Business Phone Number ID.
   - `WHATSAPP_VERIFY_TOKEN`: Random 32+ character string for GET webhook challenge.
   - `WHATSAPP_WEBHOOK_APP_SECRET`: App Secret from Meta App Dashboard for HMAC-SHA256 signature verification.
2. **Tenant Token Secret Storage:**
   - `WHATSAPP_ADAPTER_TOKEN`: Machine token for sender resolution.
   - `WHATSAPP_TENANT_TOKENS`: JSON dictionary mapping tenant UUIDs to per-tenant secret keys.
3. **Zero Secrets in Git:** All keys injected strictly via environment variables, Docker secrets, or AWS Secrets Manager / Vault.

### C. Persistent Storage & Backup
1. **Object Storage:** AWS S3, Cloudflare R2, or durable mounted volume for immutable source documents (`STORAGE_DIR`).
2. **Database Backup Strategy:**
   - Automated daily WAL archiving and snapshots for PostgreSQL.
   - Recovery Point Objective (RPO) < 15 minutes.
   - Recovery Time Objective (RTO) < 1 hour.

---

## 3. Deployment Dry Run Verification Checklist

| Area | Checkpoint | Status | Notes |
|---|---|---|---|
| **Health / Ready** | `GET /health` & `GET /ready` | Verified | Checks app liveness & DB connection pools. |
| **Alembic Migration** | Auto-migration check | Verified | `alembic upgrade head` validates schema cleanly. |
| **Webhook Security** | HMAC SHA-256 Validation | Verified | Rejects missing/invalid signatures with 401. |
| **Phone-to-Tenant** | Server-side resolution | Verified | Fails closed on unknown/inactive phone numbers. |
| **Zero Auto-Post** | Review Queue Hard-Stop | Verified | WhatsApp intake NEVER creates journals without human approval. |
| **Container Build** | Multi-stage Docker config | Verified | Minimal distroless/alpine images for backend & frontend. |
| **Idempotency** | Webhook & Media Replay | Verified | Duplicate `wamid` / file hash creates 0 extra journals. |
