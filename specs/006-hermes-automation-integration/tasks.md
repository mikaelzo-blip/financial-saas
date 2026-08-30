# Tasks: Hermes Automation Integration

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contract](contracts/hermes-api.md)

## Phase 1: Foundation

- [x] T001 [P] [FR-001,FR-002] Add disabled-by-default Hermes machine configuration in `backend/src/core/config.py`.
- [x] T002 [P] [FR-004,FR-009] Add the tenant-scoped `HermesSubmission` ORM model and expose it from `backend/src/models/__init__.py`.
- [x] T003 [FR-004,FR-009] Add non-destructive Alembic revision `backend/alembic/versions/009_hermes_submissions.py` with unique idempotency constraint and indexes.
- [x] T004 [P] [FR-004,FR-009] Add safe machine principal/submission schemas in `backend/src/schemas/hermes.py`.

## Phase 2: User Story 1 — Authenticated operational submission (P1)

**Goal**: accept original evidence only through a tenant-bound machine API and reuse Feature 005 intake.

- [x] T005 [P] [US1,FR-001,FR-002] Add failing authentication tests in `backend/tests/unit/test_hermes_auth.py`.
- [x] T006 [P] [US1,FR-003,FR-004,FR-009] Add failing endpoint/idempotency/audit tests in `backend/tests/integration/test_hermes_api.py`.
- [x] T007 [US1,FR-001,FR-002] Implement constant-time machine credential validation and fixed tenant resolution in `backend/src/api/v1/hermes.py`.
- [x] T008 [US1,FR-003,FR-004,FR-009] Implement idempotent Feature 005 document submission, safe correlation, and append-only audit event in `backend/src/api/v1/hermes.py`.
- [x] T009 [US1,FR-001] Register the narrow Hermes router in `backend/src/api/v1/__init__.py`.

## Phase 3: User Story 2 — Safe orchestration and retry (P1)

**Goal**: give Hermes a replaceable, authenticated SaaS-only client that preserves idempotency through bounded retries.

- [x] T010 [P] [US2,FR-004,FR-005,FR-010] Add failing retry and API-only dependency tests in `backend/tests/unit/test_hermes_orchestration.py`.
- [x] T011 [US2,FR-010] Implement transport protocol and validated API client in `backend/src/services/hermes/client.py`.
- [x] T012 [US2,FR-004,FR-005] Implement retry classification and bounded orchestration in `backend/src/services/hermes/retry.py`.

## Phase 4: User Story 3 — Review-aware routing (P2)

**Goal**: retain review outcomes and explicitly prevent approval/posting behavior.

- [x] T013 [US3,FR-006,FR-007,FR-008] Add tests that review/authorization/validation outcomes are not retried and client exposes no approval/posting calls in `backend/tests/unit/test_hermes_orchestration.py`.
- [x] T014 [US3,FR-006,FR-007,FR-008] Constrain the Hermes API/client surface to document intake and return authoritative document status only.

## Phase 5: Validation and delivery

- [x] T015 [P] [SC-001,SC-005] Run focused backend unit/integration tests and verify Hermes package has no ORM, database, document service, or WhatsApp imports.
- [x] T016 [P] [SC-002,SC-003,SC-004] Run the full backend suite, offline migration validation, dependency checks, and source hygiene checks.
- [x] T017 [P] [SC-005] Run frontend tests, lint, type check, and production build; verify no frontend work was necessary.
- [x] T018 [SC-001,SC-002,SC-003,SC-004,SC-005] Reconcile task coverage, re-run Spec Kit analysis, commit and push the verified `codex/006-hermes-automation` checkpoint, then create a non-merging PR to `main`.

## Dependencies and execution order

`T001–T004` → `T005–T009` → `T010–T014` → `T015–T018`. Tests are written before their implementation tasks. The migration is additive only. No task authorizes a direct Hermes database connection, a financial posting action, WhatsApp, credentials, production activity, or a merge.
