# Implementation Plan: Hermes Automation Integration

**Branch**: `codex/006-hermes-automation` | **Date**: 2026-08-30 | **Spec**: [spec.md](spec.md)

## Summary

Introduce a narrow machine-to-machine SaaS API boundary for Hermes document intake. The backend authenticates an environment-supplied machine credential, fixes it to one configured tenant, persists an idempotent tenant-scoped submission correlation record, and reuses Feature 005's immutable document intake pipeline. A replaceable Hermes HTTP client and retry policy send only API requests, preserve an idempotency key, and surface authoritative review outcomes. No Hermes endpoint approves, posts, or constructs accounting entries.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Pydantic 2, httpx (test/client transport), pytest

**Storage**: PostgreSQL via additive Alembic migration; local immutable document storage is already owned by Feature 005

**Testing**: pytest + pytest-asyncio + httpx ASGI client; migration offline SQL generation

**Target Platform**: containerized/Linux SaaS backend; client is transport-agnostic Python code

**Project Type**: existing FastAPI backend with React frontend; this feature has no frontend or channel UI

**Performance Goals**: bounded retry attempts with no duplicate logical submission; no synchronous OCR work on request path

**Constraints**: HTTPS API client boundary, tenant isolation, no source bytes/secrets in correlation records, no direct Hermes database imports, exact Feature 005 hash duplicate protection, no WhatsApp artifacts

**Scale/Scope**: one service machine principal bound to one organization per deployment; credential rotation is deployment configuration, not a new policy or data store

## Constitution Check

| Gate | Design response | Status |
|---|---|---|
| Single Input / duplicate prevention | A unique `(organization, operation, idempotency_key_hash)` submission record returns its prior document rather than ingesting again. Feature 005 continues SHA-256 document duplicate detection. | PASS |
| API boundary and Hermes role | Hermes client depends only on an HTTP transport protocol. The server endpoint is authenticated and calls existing application services; the client has no ORM/service imports. | PASS |
| Deterministic accounting / review | The feature exposes intake only. It cannot call approval, posting, journals, or accounting rules. Existing backend remains authoritative. | PASS |
| Audit / tenant isolation / confidentiality | Correlation is tenant-scoped and audit events contain a key fingerprint, resource ID, status and safe code only—never bearer tokens or document bytes. | PASS |
| Immutable documents / Decimal | Existing Feature 005 raw-document workflow remains unchanged; this feature stores no monetary calculations. | PASS |

Re-check after design: no Constitution exception or complexity justification is needed.

## Project Structure

```text
backend/
├── alembic/versions/009_hermes_submissions.py
├── src/
│   ├── api/v1/hermes.py
│   ├── models/hermes.py
│   ├── schemas/hermes.py
│   └── services/hermes/
│       ├── client.py
│       └── retry.py
└── tests/
    ├── integration/test_hermes_api.py
    └── unit/test_hermes_auth.py
```

**Structure Decision**: retain the existing backend modules. The SaaS endpoint is an adapter around Feature 005, while the orchestration package remains API-only and can be used by a future worker without coupling a worker implementation to accounting or persistence.

## Complexity Tracking

No Constitution violations require justification.
