# Tasks: Document Intelligence & Financial Document Intake

**Input**: Design documents in `specs/005-document-intelligence-intake/`

**Tests**: Required by the Constitution and user quality gate. Test tasks precede corresponding implementation.

## Phase 1: Setup

- [X] T001 Verify and extend Python document-processing dependencies in `backend/pyproject.toml`
- [X] T002 [P] Create document intelligence service package exports in `backend/src/services/documents/__init__.py`
- [X] T003 [P] Add document-processing configuration defaults to `backend/src/core/config.py` and `backend/.env.example`
- [X] T004 Verify repository ignore rules protect `.env`, generated storage, caches, coverage, and build output in `.gitignore`, `backend/.gitignore`, and `frontend/.gitignore`

## Phase 2: Foundational

- [X] T005 Add document types, processing statuses, candidate statuses, source channels, and Feature 005 review flags in `backend/src/models/enums.py`
- [X] T006 Add processing fields and append-only correction model in `backend/src/models/document.py`
- [X] T007 Create non-destructive PostgreSQL migration with data backfill and constraints in `backend/alembic/versions/008_document_intelligence.py`
- [X] T008 [P] Define strict Decimal-based extraction, evidence, confidence, matching, candidate, correction, and API schemas in `backend/src/schemas/document.py`
- [X] T009 [P] Define provider protocol, provider-neutral result, factory, and deterministic test provider in `backend/src/services/documents/extraction.py`
- [X] T010 Harden generated-path immutable storage, content streaming, and path containment in `backend/src/services/storage_service.py`
- [X] T011 Harden streaming size/MIME/signature/PDF-encryption validation and tenant SHA-256 intake in `backend/src/services/document_service.py`
- [X] T012 Add foundational schema, migration, storage, validation, immutability, and provider-contract tests in `backend/tests/unit/test_document_intelligence_foundation.py` and `backend/tests/integration/test_document_intelligence_migration.py`

**Checkpoint**: Migration, strict contracts, immutable storage, and provider boundary pass independently.

## Phase 3: User Story 1 — Transfer Proof Upload & Extraction (P1) MVP

**Goal**: Upload bank transfer evidence, extract structured values, and never infer expense or journal entries.

**Independent Test**: Scripted BCA/Mandiri evidence yields Decimal amount/date/recipient/reference and a non-posted candidate; exact duplicate bytes are rejected before a second extraction.

- [X] T013 [P] [US1] Add failing transfer extraction, duplicate-before-extraction, retry-idempotency, and cash-not-expense tests in `backend/tests/unit/test_transfer_document_pipeline.py`
- [X] T014 [P] [US1] Add failing upload/process/detail/content API contract tests in `backend/tests/integration/test_document_intelligence_api.py`
- [X] T015 [US1] Implement local text/PDF/image extraction adapter without accounting behavior in `backend/src/services/documents/local_provider.py`
- [X] T016 [US1] Implement normalization and multi-dimensional confidence evaluation in `backend/src/services/documents/confidence.py`
- [X] T017 [US1] Implement idempotent lifecycle orchestration and safe failure handling in `backend/src/services/documents/pipeline.py`
- [X] T018 [US1] Implement transfer candidate proposal rules that forbid debit/credit and automatic expense classification in `backend/src/services/documents/candidate.py`
- [X] T019 [US1] Extend upload, detail, content, retry, and processing endpoints in `backend/src/api/v1/documents.py`
- [X] T020 [US1] Run and pass the User Story 1 backend checkpoint tests in `backend/tests/unit/test_transfer_document_pipeline.py` and `backend/tests/integration/test_document_intelligence_api.py`

## Phase 4: User Story 2 — Vendor Invoice & Project Matching (P1)

**Goal**: Extract vendor invoices, match existing tenant master data conservatively, flag ambiguity, and detect suspected business duplicates.

**Independent Test**: An invoice with exact project/SPK and vendor evidence produces high-confidence proposals; missing project produces `PROJECT_UNKNOWN`; similar transactions produce `DUPLICATE_SUSPECTED` without posting.

- [X] T021 [P] [US2] Add failing strict invoice/line/tax Decimal extraction and no-fabrication tests in `backend/tests/unit/test_invoice_extraction.py`
- [X] T022 [P] [US2] Add failing tenant-scoped project/counterparty/payment-account matching tests in `backend/tests/unit/test_document_matching.py`
- [X] T023 [P] [US2] Add failing ±1-day/reference business duplicate tests in `backend/tests/unit/test_document_business_duplicates.py`
- [X] T024 [US2] Implement exact-first and conservative fuzzy matching in `backend/src/services/documents/matching.py`
- [X] T025 [US2] Extend suspected duplicate detection to date windows and references in `backend/src/services/duplicate_service.py`
- [X] T026 [US2] Implement invoice/cost-category candidate proposals and required review flags in `backend/src/services/documents/candidate.py`
- [X] T027 [US2] Integrate matching, duplicate checks, confidence, and flags into `backend/src/services/documents/pipeline.py`
- [X] T028 [US2] Run and pass User Story 2 extraction, matching, duplicate, and pipeline tests in `backend/tests/unit/`

## Phase 5: User Story 3 — Review Workspace & Verified Corrections (P2)

**Goal**: Let authorized reviewers compare immutable evidence to extracted data, correct proposals with audit history, resolve flags, and hand off complete candidates through authoritative transaction validation.

**Independent Test**: A reviewer corrects a flagged field with a reason; original hash/bytes remain unchanged, old/new values are audited, status becomes ready only when all blockers clear, and conversion is idempotent.

- [X] T029 [P] [US3] Add failing correction, role, audit, flag-resolution, immutable-source, approval, and tenancy API tests in `backend/tests/integration/test_document_review_workspace.py`
- [X] T030 [P] [US3] Add frontend API/types and review-workspace component tests in `frontend/tests/pages/DocumentReviewWorkspace.test.tsx`
- [X] T031 [US3] Implement correction validation, append-only correction persistence, and existing AuditLog integration in `backend/src/services/documents/pipeline.py`
- [X] T032 [US3] Implement correction and candidate-approval endpoints with role and unresolved-flag gates in `backend/src/api/v1/documents.py`
- [X] T033 [US3] Implement idempotent candidate-to-transaction handoff through `backend/src/services/transaction_service.py` without journal instructions
- [X] T034 [US3] Extend document API methods and strict frontend types in `frontend/src/api/documents.ts` and `frontend/src/types/api.ts`
- [X] T035 [US3] Build accessible side-by-side source preview, confidence indicators, flags, correction form, and approval controls in `frontend/src/pages/documents/DocumentReviewPage.tsx` and `frontend/src/components/documents/DocumentReviewForm.tsx`
- [X] T036 [US3] Add the protected document review route and links in `frontend/src/App.tsx` and `frontend/src/pages/documents/DocumentListPage.tsx`
- [X] T037 [US3] Run and pass User Story 3 backend and frontend review-workspace tests

## Phase 6: User Story 4 — Project & Contract Intake (P3)

**Goal**: Classify and archive SPK, BAST, and Surat Jalan evidence against projects without forcing financial transaction creation.

**Independent Test**: Scripted project evidence classifies to the approved type, extracts document number/date, links only to a tenant project, and remains a project document when no financial candidate is appropriate.

- [X] T038 [P] [US4] Add failing project-document classification/linking and cross-tenant rejection tests in `backend/tests/integration/test_project_document_intelligence.py`
- [X] T039 [US4] Implement contract/project classification and archive-only candidate behavior in `backend/src/services/documents/candidate.py`
- [X] T040 [US4] Integrate tenant-safe project document linking into `backend/src/services/documents/pipeline.py`
- [X] T041 [US4] Add batch upload with per-file status and retry UX in `frontend/src/pages/documents/DocumentListPage.tsx` and `frontend/src/components/forms/FileDropzone.tsx`
- [X] T042 [US4] Run and pass User Story 4 backend and frontend document intake tests

## Phase 7: Polish & Cross-Cutting Quality Gate

- [X] T043 [P] Add security/tenant/idempotency regression coverage in `backend/tests/integration/test_document_intelligence_security.py`
- [X] T044 [P] Add frontend empty/loading/error/accessibility coverage in `frontend/tests/pages/DocumentIntelligenceStates.test.tsx`
- [X] T045 Validate OpenAPI shapes against implementation and update `specs/005-document-intelligence-intake/contracts/openapi.yaml`
- [X] T046 Validate PostgreSQL upgrade/downgrade/offline SQL for `backend/alembic/versions/008_document_intelligence.py`
- [X] T047 Run the complete backend test suite from `backend/`
- [X] T048 Run dependency checks and frontend tests, lint, typecheck, and production build from `frontend/`
- [X] T049 Execute every scenario in `specs/005-document-intelligence-intake/quickstart.md` and resolve regressions
- [X] T050 Verify FR-001..FR-022 and SC-001..SC-007 coverage, zero Constitution violations, and zero Critical/High analysis issues across Feature 005 artifacts

## Dependencies & Execution Order

- Phase 1 precedes Phase 2; Phase 2 blocks every user story.
- US1 and US2 are P1 increments. US2 uses the foundational provider contract and may be built after US1 pipeline orchestration.
- US3 depends on the candidate and flag results from US1/US2 but is independently testable with seeded records.
- US4 depends only on the foundation and classification pipeline; it does not require a financial candidate.
- Phase 7 follows all selected user stories.
- Within every story, tests are written first and must fail for the intended missing behavior before implementation.

## Parallel Opportunities

- T002/T003, T008/T009, and story test files marked `[P]` affect separate files.
- Backend correction API tests and frontend review tests (T029/T030) can run independently.
- Cross-cutting backend security and frontend state tests (T043/T044) can run independently.

## Implementation Strategy

1. Establish migration, schemas, provider boundary, and hardened immutable intake.
2. Deliver US1 as the MVP safety slice: structured transfer extraction with no accounting inference.
3. Add US2 matching/duplicates, then US3 human review/authoritative handoff, then US4 archival project evidence.
4. Run the full quality gate and requirement coverage analysis before completion.

All 52 tasks use the required checkbox, sequential ID, optional parallel marker, story label where applicable, and concrete repository path format.

## Post-Implementation Readiness Remediation

- [X] T051 [P] Make provider selection factory-based at the processing boundary in `backend/src/services/documents/extraction.py`
- [X] T052 Run upload and retry extraction asynchronously with isolated database sessions in `backend/src/services/documents/pipeline.py` and `backend/src/api/v1/documents.py`
