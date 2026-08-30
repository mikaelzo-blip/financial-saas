# Quickstart Validation: Document Intelligence & Financial Document Intake

## Prerequisites

- Python 3.11+ with backend development dependencies
- Node.js compatible with the frontend lockfile
- PostgreSQL for migration validation; automated integration tests use the existing SQLite fixture
- No cloud OCR credentials for the deterministic test suite

## Setup and migration

```powershell
Set-Location backend
python -m pip install -e ".[dev]"
alembic upgrade head
```

Expected: `008_document_intelligence` upgrades metadata without modifying stored originals.

## Backend quality gate

```powershell
Set-Location backend
python -m pytest
alembic upgrade head --sql
```

Expected coverage: MIME/size/content validation, safe immutable storage, tenant duplicate rejection, strict Decimal extraction, provider replacement, idempotent retry, matching/review flags, suspected duplicates, transfer-proof safety, correction audit, tenancy, and authoritative transaction handoff.

## Frontend quality gate

```powershell
Set-Location frontend
npm test
npm run lint
npm run typecheck
npm run build
```

Expected: batch upload and side-by-side review tests pass and the strict production bundle builds.

## End-to-end scenarios

1. Upload a supported transfer image under 25 MB; confirm SHA-256 metadata and no journal/expense creation.
2. Re-upload identical tenant bytes; confirm `409` before extraction. The same bytes in another tenant reveal nothing.
3. Process a scripted vendor invoice with `PRJ-2026-01`, vendor evidence, and `15000000.00`; confirm Decimal serialization and matches.
4. Process an invoice without project evidence; confirm `PROJECT_UNKNOWN`, review routing, and no guessed project.
5. Correct project/vendor with a reason; confirm unchanged source hash and old/new audit evidence.
6. Approve a complete candidate; confirm existing transaction validation runs and document/provider code supplies no debit/credit.

Canonical shapes are in [contracts/openapi.yaml](./contracts/openapi.yaml) and [data-model.md](./data-model.md).
