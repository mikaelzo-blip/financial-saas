# Slice 1 Implementation Plan: Inbox + Offline Queue

## 1. Objectives & Boundaries

The goal of **Slice 1** is to establish a unified, offline-durable intake gateway for all financial documents.
It eliminates ephemeral in-memory processing (such as FastAPI `BackgroundTasks`) and ensures every document uploaded via the Web UI or received via external relays is safely persisted, deduplicated, and queued in PostgreSQL before processing begins.

### Key Acceptance Criteria
1. **Web Upload to Durable Queue**: When a document is uploaded via Web UI, it is saved to local storage, assigned a sequential code (`DOC-YYYY-######`), hashed (SHA-256), and enqueued as a durable `BackgroundJob` (`DOCUMENT_PROCESS`). Ephemeral in-memory tasks are removed.
2. **Offline Durability**: If the background worker is stopped, uploaded documents safely remain in status `QUEUED` / `PENDING` in PostgreSQL. When the worker starts, it claims pending jobs and initiates extraction.
3. **Exact Deduplication**: Exact file duplicate uploads (identical SHA-256 within the same organization) are rejected immediately at the intake boundary.
4. **Worker Claim & Retry**: The PostgreSQL worker claims jobs using `FOR UPDATE SKIP LOCKED` with configurable lock leases and records error attempts with backoff if extraction fails.
5. **Unified Inbound Adapter**: `InboundDocumentAdapter` normalizes incoming document payloads from both Web Upload and future/existing WhatsApp sync into a single canonical pipeline.

---

## 2. Architecture & Design Details

### 2.1 Inbound Adapter Boundary
Create `src/services/documents/inbound_adapter.py`:
- `InboundDocumentPayload`:
  - `organization_id`: UUID
  - `file_obj`: BinaryIO
  - `file_name`: str
  - `mime_type`: str
  - `document_type`: DocumentType (optional, default UNKNOWN)
  - `source_channel`: `WEB` | `WHATSAPP` | `API`
  - `source_metadata`: Dict[str, Any]
  - `created_by`: Optional[UUID]
  - `project_id`: Optional[UUID]
- `InboundDocumentAdapter`:
  - Validates MIME signatures and file size.
  - Computes SHA-256.
  - Checks for exact duplicate (`file_hash` per `organization_id`).
  - Persists file using `StorageService`.
  - Creates `Document` with status `QUEUED`.
  - Enqueues `BackgroundJob(job_type="DOCUMENT_PROCESS", payload={"document_id": str(doc.id), "organization_id": str(org_id)})`.
  - Returns `Document`.

### 2.2 Worker Handler Registration
In `src/worker.py` and `src/services/job_worker.py`:
- Register handler for `DOCUMENT_PROCESS`:
  - Claims job.
  - Updates `Document.processing_status = DocumentProcessingStatus.EXTRACTING`.
  - Runs `DocumentPipeline.process(...)`.
  - On success: updates `Document.processing_status` to `EXTRACTED` / `READY_FOR_APPROVAL` / `REVIEW_REQUIRED`, marks `BackgroundJob` as `COMPLETED`.
  - On error: logs attempt, updates `Document.failure_code` and `Document.failure_message`, sets `BackgroundJob` for retry with backoff.

### 2.3 API Modernization
In `src/api/v1/documents.py`:
- Update `POST /documents/upload` to use `InboundDocumentAdapter` and `JobQueueService`.
- Replace `background_tasks.add_task(...)` with persistent PostgreSQL queue enqueueing.
- Add `GET /inbox` endpoint returning unified inbox document feed with queue status, processing attempts, and source channel.

---

## 3. Implementation Tasks & Checklist

- [ ] **Task 1: Adapter Layer & Inbound Normalization**
  - Implement `src/services/documents/inbound_adapter.py` with `InboundDocumentAdapter` and `InboundPayload`.
  - Unify MIME signature verification, filename sanitization, SHA-256 calculation, and storage persistence.
  - Enforce tenant isolation on all file and metadata operations.

- [ ] **Task 2: Persistent Queue Integration in Web Upload**
  - Refactor `POST /documents/upload` in `src/api/v1/documents.py` to route through `InboundDocumentAdapter`.
  - Replace FastAPI `BackgroundTasks` with `JobQueueService.enqueue(job_type="DOCUMENT_PROCESS", ...)`.
  - Set initial document status to `QUEUED`.

- [ ] **Task 3: Worker Handler for `DOCUMENT_PROCESS`**
  - In `src/worker.py`, register `handle_document_process` handler for `DOCUMENT_PROCESS`.
  - Ensure graceful handling of worker restarts, lease expiration, and retry backoffs.
  - Ensure processing errors update `Document.processing_status = FAILED` or `REVIEW_REQUIRED` without losing the original file or DB record.

- [ ] **Task 4: Inbox Listing API**
  - Ensure `GET /documents` or `GET /inbox` supports filtering by `source_channel`, `processing_status`, and queue state.
  - Return queue metadata (attempt count, last error) in the response schema.

- [ ] **Task 5: Automated Regression & Durability Tests**
  - Unit test: verify web upload enqueues `BackgroundJob` and does not require active worker.
  - Integration test: simulate worker offline -> upload 3 documents -> start worker -> verify all 3 claimed and processed in sequence.
  - Concurrency test: verify 2 workers claiming simultaneously with `SKIP LOCKED` do not double-process the same document.
  - Exact duplicate test: uploading the same file twice produces 409 conflict and zero duplicate queue jobs.

---

## 4. Verification & Gate Checklist

- [ ] Python syntax and static compilation pass (`compileall`).
- [ ] Backend tests pass without regression: `pytest backend/tests/unit/test_document*.py`.
- [ ] Offline durability simulation test passes.
- [ ] No direct journal entry insertion; zero financial invariant regressions.
- [ ] All code adheres to `AGENTS.md` and `constitution.md`.
