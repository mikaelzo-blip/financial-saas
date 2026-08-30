# Implementation Plan: Document Intelligence & Financial Document Intake

**Branch**: `005-document-intelligence-intake` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-document-intelligence-intake/spec.md`

## Summary

Extend the existing immutable document intake into a tenant-isolated, provider-agnostic extraction pipeline. The pipeline validates uploads, hashes and stores originals, classifies and extracts evidence into strict typed schemas, matches existing projects/counterparties/payment accounts, detects exact and suspected duplicates, calculates field-specific confidence, and creates an auditable transaction candidate. Ambiguity always routes to review; only the existing transaction and accounting services may validate, approve, and post financial records.

## Technical Context

**Language/Version**: Python >=3.11 backend; TypeScript 6 / React 19 frontend

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Pydantic 2, Alembic, PostgreSQL; React Router, TanStack Query, React Hook Form, Zod; local PDF/image parsing behind an extraction-provider interface

**Storage**: PostgreSQL for metadata/state/audit records; immutable organization-partitioned filesystem storage for originals; JSON columns for evidence payloads with Pydantic validation at every boundary

**Testing**: pytest/pytest-asyncio/httpx with SQLite-compatible integration fixtures; Vitest/Testing Library; Alembic offline SQL validation

**Target Platform**: Linux-compatible web service and modern desktop/mobile browsers

**Project Type**: Existing backend API plus React SPA

**Performance Goals**: Duplicate hash decision completes before extraction; upload accepts supported files up to 25 MB; list/detail views remain responsive for normal operational use

**Constraints**: No paid provider or credential is required for core architecture/tests; originals are immutable; retries are idempotent; no auto-posting; unknown or low-confidence critical fields route to review; all access is organization-scoped

**Scale/Scope**: Four prioritized journeys, 22 functional requirements, 21 classified document types plus `UNKNOWN`, five confidence dimensions, and one review workspace

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Design evidence | Status |
|---|---|---|
| I Single Input | One candidate references one source document and hands off to existing transaction intake; no duplicate AR/AP/journal paths | PASS |
| III/V Simple UX and deterministic accounting | UI edits business fields only; candidates contain no debit/credit; posting rules remain authoritative | PASS |
| VI Cash movement is not expense | Transfer proofs never create expense or journal records automatically | PASS |
| VII/VIII Traceability and duplicates | Immutable originals, tenant SHA-256, evidence provenance, suspected-duplicate flags | PASS |
| IX/XVII Human review | Unknown entities/projects and low-confidence critical fields block approval | PASS |
| X/XI Immutability and audit | Source bytes are never overwritten; corrections append before/after audit events | PASS |
| XV/XVI Tax/open policy | Tax fields are evidence only and trigger review; no rate or policy is invented | PASS |
| XVIII/XIX API and Hermes boundary | Authenticated REST intake is reusable by future Hermes; no direct DB integration | PASS |
| XXII Modular architecture | Extraction, matching, confidence, candidate generation, and accounting remain separate | PASS |
| XXIII Security | MIME/size/path validation, tenant scoping, roles, non-public storage | PASS |
| XXIV Testability | Unit, integration, contract, UI, tenancy, idempotency, and migration tests planned | PASS |
| XXV Incremental delivery | Work is dependency ordered with verification checkpoints | PASS |

No Constitution violation or justified exception exists.

## Project Structure

### Documentation (this feature)

```text
specs/005-document-intelligence-intake/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/008_document_intelligence.py
├── src/
│   ├── api/v1/documents.py
│   ├── models/{document.py,enums.py}
│   ├── schemas/document.py
│   └── services/documents/
│       ├── extraction.py
│       ├── local_provider.py
│       ├── matching.py
│       ├── confidence.py
│       ├── candidate.py
│       └── pipeline.py
└── tests/{unit,integration}/

frontend/
├── src/
│   ├── api/documents.ts
│   ├── components/documents/
│   ├── pages/documents/
│   └── types/api.ts
└── tests/pages/
```

**Structure Decision**: Extend the existing modular monolith. Keep `DocumentService` responsible for immutable intake and persistence, and place intelligence pipeline concerns in a document-specific service package. Extend the existing Documents route rather than creating another application.

## Design Phases

1. Harden intake and migrate document processing/audit data.
2. Add strict extraction contracts and a replaceable provider boundary.
3. Add deterministic normalization, matching, confidence, duplicate detection, and candidate generation.
4. Add review/edit/approval handoff APIs with audit logging.
5. Build batch upload, status, and side-by-side review UI.
6. Validate migrations, tenancy, invariants, backend tests, frontend tests/lint/typecheck/build, and requirement coverage.

## Post-design Constitution Re-check

The data model stores proposals separately from authoritative transactions; the contract exposes no debit/credit fields; all evidence and corrections are traceable; originals cannot be updated or deleted; ambiguous candidates cannot transition past review; and provider adapters cannot call the accounting engine. All pre-design gates remain PASS.

## Complexity Tracking

No Constitution violations require justification.
