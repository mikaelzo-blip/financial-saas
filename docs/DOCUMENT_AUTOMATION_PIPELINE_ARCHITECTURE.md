# Document Automation Pipeline: End-to-End Product Architecture

## 1. Executive Summary & Product Objective

The **Document Automation Pipeline** provides an operational, offline-resilient document-to-accounting pipeline for Indonesian construction contractors.
It enables field operators and company owners to submit financial evidence (invoices, receipts, bank transfer screenshots, PO/SPKs, BAST, surat jalan) via WhatsApp or Web Upload. The system safely normalizes, extracts, classifies, matches, and either automatically posts or stages documents for web-based human review—without ever violating core financial, authorization, or accounting invariants.

### Authoritative Constraints Preserved
- **Single Input & Derived Financials**: One business event is entered once; AR, AP, project costs, journals, and balances are derived.
- **Cash Movement != Expense**: Bank transfers and cash receipts are not automatically expenses or revenues; transaction type and matching context govern classification.
- **Fail-Closed Accounting Gate (FIN-P1-102)**: AI/OCR proposals never directly insert journals. Generic automated posting routes exclusively through `TransactionService` and is gated by `PostingRuleRegistry.validate_generic_ingestion`. Unsupported or ambiguous transaction types fail closed to `REVIEW_REQUIRED`.
- **Tenant Isolation & Security (AUTHZ-001, FIN-P1-105)**: Every document, queue job, candidate, and foreign reference is strictly isolated and validated by `organization_id`.
- **Immutability & Cryptographic Proof**: Raw source documents and evidentiary files are immutable and verified with SHA-256 hashes. Corrections are append-only.

---

## 2. Target Workflow & Component Boundaries

```text
  [WhatsApp Webhook / Relay]          [Web File Upload]
              │                               │
              ▼                               ▼
     WhatsAppAdapter                  WebUploadAdapter
              │                               │
              └───────────────┬───────────────┘
                              ▼
                   InboundDocumentAdapter
                              │
                              ▼
            Canonical Inbound Document Storage
            (Durable PostgreSQL + Local File Storage)
            Status: RECEIVED -> HASHED -> QUEUED
                              │
                    PostgreSQL Job Queue
               (FOR UPDATE SKIP LOCKED lease)
                              │
                   [Offline PC Resilience]
         Worker offline: jobs wait safely in DB
         Worker online:  claims & processes
                              │
                              ▼
                 OCR & Extraction Provider
         (pypdf native + RapidOCR image / scanned PDF)
                              │
                              ▼
                  Structured Field Extraction
          (Pydantic Schema + Field-level Confidence)
                              │
                              ▼
                    Document Classification
            (21 Document Types + Header/Rule Scoring)
                              │
                              ▼
                    Entity Matching Engine
         (Counterparty, Project, Payment Account, AR/AP)
                              │
                              ▼
                   Confidence & Risk Policy
             ┌────────────────┴────────────────┐
             ▼                                 ▼
   [High Confidence & Safe]          [Ambiguous / High Risk]
   All auto-post criteria met        Unresolved flags / low score
             │                                 │
             │                                 ▼
             │                        Web Review Workspace
             │                        (Preview, Edit, Approve)
             │                                 │
             └────────────────┬────────────────┘
                              ▼
                  Approved Candidate Gate
                              │
                              ▼
                     TransactionService
                              │
                              ▼
                     PostingRuleRegistry
                              │
                              ▼
                      AccountingEngine
                              │
                              ▼
                   Double-Entry Journal & Ledger
                              │
                              ▼
                   Operational Dashboard
```

---

## 3. Canonical Domain Models & State Machines

### 3.1 Document Lifecycle State Machine

```text
    RECEIVED (raw payload accepted)
       │
       ▼
     HASHED (SHA-256 calculated, duplicate check passed)
       │
       ▼
     QUEUED (BackgroundJob created in PostgreSQL)
       │
       ▼
   EXTRACTING (Worker leased job, OCR in progress)
       │
       ▼
   EXTRACTED (Structured data, field confidence recorded)
       │
       ▼
    MATCHING (Entity, project, account, invoice matching)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
READY_FOR_APPROVAL               REVIEW_REQUIRED
(Safe, high confidence)         (Missing project, low OCR, etc.)
       │                                 │
       │                   [Human Review & Correction]
       │                                 │
       ├─────────────────────────────────┘
       ▼
   POSTING (Atomic transaction & journal creation)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
    POSTED                            FAILED
(Journal active)             (Permanent failure recorded)
```

### 3.2 Canonical Inbound Document Contract

An incoming document from any adapter is normalized into `InboundDocument`:
- `id`: UUID
- `organization_id`: UUID
- `document_code`: Sequential string (`DOC-YYYY-######`)
- `source_channel`: `WEB` | `WHATSAPP` | `API`
- `source_metadata`: JSON (sender phone, message ID, caption, sender name, upload user)
- `file_name`: Sanitized original filename
- `mime_type`: Validated MIME type
- `file_size_bytes`: Integer
- `file_hash`: Hex SHA-256 string (unique per org)
- `storage_path`: Relative filesystem storage path
- `processing_status`: `DocumentProcessingStatus`
- `converted_transaction_id`: Optional UUID (hard foreign key to `transactions.id`)

### 3.3 PostgreSQL Queue Contract (`BackgroundJob`)

Queueing relies on the existing PostgreSQL `background_jobs` table:
- `id`: UUID (primary key)
- `organization_id`: UUID
- `job_type`: `DOCUMENT_PROCESS` | `DOCUMENT_DEFERRED_ANALYSIS` | `INBOX_SYNC`
- `payload`: JSON (`{"document_id": "...", "organization_id": "..."}`)
- `status`: `PENDING` | `RUNNING` | `COMPLETED` | `FAILED`
- `attempt_count`: Integer
- `max_attempts`: Integer (default 3)
- `available_at`: Timestamp (supports backoff retry)
- `locked_by`: Worker identifier string
- `locked_until`: Timestamp lease (default 300 seconds)
- `last_error`: Text

---

## 4. Subsystem Architectures

### 4.1 Inbound Adapter Boundary (`InboundDocumentAdapter`)
- Decouples external transports from the internal domain.
- `WebUploadAdapter`: Accepts direct multi-part file uploads from authenticated web users.
- `WhatsAppAdapter`: Accepts webhooks or synched payloads from Cloudflare Edge Relay or Baileys poller. Strips WhatsApp-specific metadata into `source_metadata` and extracts raw attachments.
- Neither adapter performs accounting or business matching. Both yield a persisted `Document` and enqueue a `BackgroundJob`.

### 4.2 Offline-First Queue & Worker Architecture
- **PC-Off Durability**: Incoming documents sent to WhatsApp while the Finance PC is off reside safely in Edge Relay (or pending sync state). When the local app / worker starts, pending documents are synced, persisted to DB, and enqueued.
- **Worker Lease**: Worker claims jobs with `SELECT ... FOR UPDATE SKIP LOCKED` and lease expiration recovery. If a worker crashes mid-OCR, the lease expires and another worker run picks it up cleanly.
- **Idempotency**: Retrying a job cannot create duplicate documents or duplicate transactions.

### 4.3 Advanced OCR & Structured Extraction
- Provider protocol: `ExtractionProvider` with `extract(path: Path, mime_type: str) -> ExtractionResult`.
- Hybrid extraction:
  1. PDF Native: Extract embedded text layer via `pypdf`. If valid text is found, skip heavy OCR.
  2. PDF Scanned: If PDF has no extractable text, render pages to images via `pypdfium2` or `pdf2image` and run RapidOCR.
  3. Images: Direct RapidOCR with automatic orientation check.
- Structured schema: `StructuredExtraction` captures typed fields (`total_amount`, `vat_amount`, `issuer_name`, `spk_number`, `line_items`) and field-level confidence scores.

### 4.4 Deterministic Matching Engine
- Multi-signal scoring across 4 entities:
  - **Counterparty**: Exact name match -> 1.0; Fuzzy sequence match (>= 0.90) -> scored.
  - **Project**: Match `project_code` or `po_spk_no` -> 1.0.
  - **PaymentAccount**: Match bank account number or bank name -> 0.85-1.0.
  - **Allocation Target (AR/AP)**: Match `invoice_number` to unpaid `VendorBill` or `CustomerInvoice`.
- Conflicting or ambiguous matches flag the document as `REVIEW_REQUIRED`.

### 4.5 Auto-Posting Eligibility Policy
Automated posting occurs ONLY when ALL of the following hold:
1. Overall document confidence >= configured threshold (default 0.90)
2. Amount confidence >= 0.90
3. Transaction date confidently parsed and within open accounting period
4. Required counterparty and project confidently resolved
5. No duplicate suspected by `DuplicateDetectionService`
6. Transaction type is supported by `PostingRuleRegistry` (e.g. `DIRECT_PURCHASE`, `PAY_VENDOR_BILL` with unambiguous bill allocation)
7. Non-sensitive transaction type (no `OWNER_WITHDRAWAL`, `OWNER_CONTRIBUTION`, `REVERSAL`, etc.)

If ANY condition is not met, the status is set to `REVIEW_REQUIRED`.

### 4.6 Web Review & Human Correction
- Screen displays: original document preview, extracted fields, field confidences, candidate matching suggestions, and review flags.
- Reviewer actions:
  - Correct fields (updates candidate, logs `DocumentCorrection` audit record).
  - Approve (transitions to `POSTING` -> creates Transaction & Journal).
  - Reject (marks document `REJECTED`, records reason).

### 4.7 Operational Dashboard
- Dedicated view for Document Automation Pipeline:
  - Counters: RECEIVED, QUEUED, PROCESSING, REVIEW_REQUIRED, READY_TO_POST, POSTED, FAILED, DUPLICATE_SUSPECTED.
  - Queue health: oldest pending job age, active worker heartbeats, retry distribution.
  - Failure log: latest error messages with one-click re-enqueue.

---

## 5. End-to-End Seven-Slice Roadmap

| Slice | Name | Scope Summary | Complexity |
|---|---|---|---|
| **Slice 1** | **Inbox + Offline Queue** | Inbound adapter boundary, durable PostgreSQL queue for web upload, worker claim/lease/retry, deduplication, inbox API | **M** |
| **Slice 2** | **Advanced OCR Pipeline** | Scanned PDF rasterization, rotation detection, line-item extraction, raw evidence retention, provider fallback | **M** |
| **Slice 3** | **Hermes Matching Engine** | PO/SPK matching, open AR/AP invoice matching, confidence policy service, anomaly flags | **M** |
| **Slice 4** | **Web Review & Approval** | Unified review API/UI, original document side-by-side preview, audit-logged corrections, candidate confirmation | **M** |
| **Slice 5** | **Automatic Posting Gate** | Deterministic auto-post eligibility policy, idempotent conversion constraint, TransactionService integration, fail-closed rule | **S** |
| **Slice 6** | **Operational Dashboard** | Pipeline metrics API, status counters, queue processing age, failure/retry visibility, filterable document log | **S** |
| **Slice 7** | **Integration Hardening** | WhatsApp input-only adapter hardening, attachment download resilience, local worker lifecycle daemon | **M** |
