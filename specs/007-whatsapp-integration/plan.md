# Implementation Plan: WhatsApp Operational Messaging Integration

**Branch**: `007-whatsapp-integration` | **Date**: 2026-08-30 | **Spec**: [specs/007-whatsapp-integration/spec.md](file:///c:/Projects/financial-saas/specs/007-whatsapp-integration/spec.md)

---

## 1. Summary

The **WhatsApp Operational Messaging Integration** bridges field operations (cashiers, site supervisors, and project managers) with the Financial SaaS via the Hermes automation client. Inbound WhatsApp media (receipts, bank transfer slips, invoices) and messages are received via a secured webhook, mapped to the corresponding organization and user, validated for idempotency, streamed to Feature 005 Document Intelligence via authenticated SaaS APIs, and acknowledged back to the user with actionable reference numbers.

---

## 2. Technical Context

- **Language/Version**: Python >= 3.11
- **Primary Frameworks**: FastAPI >= 0.115.0, SQLAlchemy 2.0 (async), Pydantic v2
- **HTTP & Transport Client**: `httpx` (async HTTP client for provider communication)
- **Database & Storage**: PostgreSQL 16+ (or SQLite async for tests), immutable local document storage
- **Cryptographic Security**: `hmac`, `hashlib` (HMAC-SHA256 signature verification)
- **Testing Framework**: `pytest`, `pytest-asyncio`, `httpx` test client
- **Target Architecture**: Modular Service Layer under `backend/src/services/integrations/whatsapp/` and API router at `backend/src/api/v1/whatsapp.py`

---

## 3. Constitution Check

*GATE: All 25 Principles from `.specify/memory/constitution.md` MUST pass.*

| Principle | Status | Alignment Rationale |
|---|---|---|
| **I. Single Input** | **PASS** | WhatsApp is solely an ingest pipeline; events flow into Feature 005 single-intake pipeline. Zero duplicate manual entries. |
| **III. Simple User Experience** | **PASS** | Field staff send photos/captions naturally; non-accountants never see debit/credit accounts. |
| **IV. Double-Entry Accounting** | **PASS** | WhatsApp adapter never creates journal entries; posting remains deterministic in core engine. |
| **V. Deterministic Accounting Engine** | **PASS** | AI/Hermes/WhatsApp cannot choose debit/credit accounts. |
| **VI. Cash Movement is Not Expense** | **PASS** | Bukti transfer received via WhatsApp is staged as intake evidence, never automatically posted as expense. |
| **VII. Source Document Traceability** | **PASS** | Original images/PDFs are stored immutably with SHA-256 hashes and linked to transaction candidates. |
| **VIII. Duplicate Prevention** | **PASS** | 3-layer deduplication: `wamid` cache, Hermes `Idempotency-Key`, and Feature 005 SHA-256 document hashing. |
| **IX. Human Review for Ambiguity** | **PASS** | Missing projects or low confidence route to Review Queue. WhatsApp interactive questions clarify data safely. |
| **X. Immutable Posted Records** | **PASS** | WhatsApp messages cannot alter posted transactions. |
| **XI. Audit Trail** | **PASS** | All inbound/outbound messages, sender phone numbers, timestamps, and outcomes logged in `WhatsAppMessageLog`. |
| **XVII. Review Before Automation** | **PASS** | WhatsApp cannot auto-approve or auto-post candidate transactions. |
| **XVIII. API Boundary** | **PASS** | WhatsApp adapter calls SaaS endpoints via `HermesApiClient`; NO direct SQL queries or database connections. |
| **XIX. Hermes Role** | **PASS** | Hermes orchestrates intake via SaaS API; does not act as ledger or database client. |
| **XXI. Transactional DB as Record** | **PASS** | Relational DB is the sole system of record; WhatsApp chat history is transient communication. |
| **XXIII. Security & Isolation** | **PASS** | Tenant isolation by `organization_id` via `WhatsAppSenderMapping`; HMAC-SHA256 signature verification. |
| **XXIV. Testability & Verification** | **PASS** | 100% testable offline via `MockWhatsAppProvider` without paid Meta credentials. |

---

## 4. Project Structure & Module Layout

```text
backend/src/
├── api/v1/
│   ├── whatsapp.py                       # REST & Webhook endpoints (GET handshake, POST webhook, admin mappings)
│   └── hermes.py                         # (Existing Feature 006 authenticated SaaS boundary)
├── models/
│   └── whatsapp.py                       # SQLAlchemy models: WhatsAppSenderMapping, WhatsAppMessageLog, WhatsAppClarificationSession
├── schemas/
│   └── whatsapp.py                       # Pydantic DTOs for webhooks, payloads, sender mappings, and replies
└── services/
    └── integrations/
        └── whatsapp/
            ├── __init__.py
            ├── provider.py               # Abstract WhatsAppProvider interface
            ├── mock_provider.py          # Mock provider for CI/CD and offline tests
            ├── meta_provider.py          # Meta Cloud API implementation
            ├── webhook_service.py        # Signature validation, idempotency check, payload dispatcher
            ├── sender_service.py         # Multi-tenant phone number to User/Org resolver
            ├── media_service.py          # Authenticated media downloader & streaming validator
            ├── outbound_service.py       # Formatted text & interactive button response dispatcher
            └── clarification_service.py  # Conversational review question state machine

backend/tests/
├── unit/
│   ├── test_whatsapp_signature.py       # HMAC verification & security tests
│   ├── test_whatsapp_sender_mapping.py   # Phone number to tenant mapping tests
│   ├── test_whatsapp_media_download.py   # MIME validation and byte stream tests
│   └── test_whatsapp_clarification.py    # Conversational state machine tests
└── integration/
    ├── test_whatsapp_webhook_flow.py     # End-to-end webhook to Feature 005 intake flow
    ├── test_whatsapp_idempotency.py      # Duplicate webhook delivery rejection tests
    └── test_whatsapp_isolation.py        # Strict multi-tenant isolation tests
```

---

## 5. Implementation Phases & Gateways

1. **Phase 1: Foundation & Security Boundary**:
   - `WhatsAppProvider` interface & `MockWhatsAppProvider`
   - Data models (`WhatsAppSenderMapping`, `WhatsAppMessageLog`, `WhatsAppClarificationSession`)
   - HMAC-SHA256 signature validator and webhook handshake endpoint
2. **Phase 2: Inbound Media & Hermes Intake Pipeline**:
   - Sender phone number mapping & tenant verification
   - Media streaming downloader (JPEG/PNG/PDF up to 25MB)
   - Forwarding to `/api/v1/hermes/documents/upload` with caption metadata and `Idempotency-Key`
3. **Phase 3: Outbound Messaging & Interactive Review Prompts**:
   - Responding to users with receipt numbers (`DOC-xxxx`)
   - Interactive clarification prompts for ambiguous OCR/Review Queue items
   - Handling numeric replies to update transaction candidate fields via Review API
4. **Phase 4: Multi-Tenant Isolation, Reliability & Regression Suite**:
   - Rate limiting middleware per sender
   - Comprehensive offline integration tests with `MockWhatsAppProvider`
   - Complete verification against quickstart scenarios
