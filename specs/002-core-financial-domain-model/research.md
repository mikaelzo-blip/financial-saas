# Phase 0 Research: Core Financial Domain & Technical Architecture

**Feature**: `002-core-financial-domain-model`  
**Date**: 2026-08-29  
**Status**: Completed  

---

## 1. Technical Decisions & Tradeoffs

### Decision 1: Backend Stack & Runtime
- **Decision**: Python 3.12+ with **FastAPI**, **SQLAlchemy 2.0 (Async/PostgreSQL via asyncpg)**, **Pydantic v2**, and **Alembic**.
- **Rationale**:
  - Financial domain modeling and double-entry accounting engines demand strict arbitrary-precision decimal arithmetic (`decimal.Decimal`) to prevent floating-point rounding errors. Python's standard library `Decimal` coupled with PostgreSQL `NUMERIC` provides native exact arithmetic.
  - FastAPI + Pydantic v2 offers automatic, high-performance schema validation, OpenAPI generation for client contracts, and modular service separation.
  - Python ecosystem aligns directly with future AI agent / Hermes orchestration integrations.
- **Alternatives Considered**:
  - *TypeScript / Node.js (NestJS / Prisma)*: While viable for web SaaS, JavaScript lacks a native arbitrary-precision decimal primitive, requiring external libraries (like `decimal.js`) which can leak into calculations or ORM conversions.
  - *Go*: High concurrency, but domain modeling, ORM migration flexibility, and future AI tooling integrations are significantly more verbose.

---

### Decision 2: Database Engine & Relational Strategy
- **Decision**: **PostgreSQL 16** with strict relational integrity constraints, transactional isolation (Read Committed / Serializable for Posting), and UUIDv7 / sequential business identifiers.
- **Rationale**:
  - PostgreSQL is the gold-standard transactional RDBMS, supporting CHECK constraints (e.g., `amount > 0`, `debit >= 0`), foreign key cascades/restrictions, atomic transaction blocks, and `NUMERIC(18, 2)` (or `NUMERIC(15, 0)` for pure IDR with decimal headroom).
  - Dual-identifier strategy:
    - Internal primary keys: `UUID` (specifically UUIDv7 for time-sorted indexing and performance).
    - Public human-readable business IDs: `PRJ-YYYY-###`, `TRX-YYYY-######`, `DOC-YYYY-######` generated via atomic sequence counters per organization.
- **Alternatives Considered**:
  - *MySQL / MariaDB*: Less strict with check constraints in older setups; PostgreSQL has superior JSONB and indexing for audit event queries.
  - *Document DB (MongoDB)*: Explicitly violates Constitution Principle XXI (Transactional Relational Database as System of Record) and Constitution Principle IV (Double-Entry Invariants).

---

### Decision 3: Accounting Engine & Journal Balancing Invariant
- **Decision**: Atomic, deterministic rule-based posting service inside a single database transaction.
- **Rationale**:
  - An operational transaction posting executes in a dedicated database transaction:
    1. Validate transaction status (must be `STAGED` or approved from `REVIEW_REQUIRED`).
    2. Lookup deterministic `Accounting_Rule` by `Transaction_Type`.
    3. Generate `Journal_Entry` header and child `Journal_Line` records.
    4. Enforce Invariant: $\sum \text{Debit} == \sum \text{Credit}$ in memory and verify via database trigger/check.
    5. Update derived AR / AP allocations, Advance records, and Project Cost records atomically.
    6. Transition Transaction `Workflow_Status` to `POSTED`.
    7. Commit transaction. If any step fails, roll back entirely.
- **Alternatives Considered**:
  - *Asynchronous Event-Driven Posting (Outbox/Kafka)*: Overkill for MVP, risks eventual consistency lag where users view unposted transactions or race conditions in AR/AP settlements. Synchronous atomic transactions guarantee instant financial consistency.

---

### Decision 4: Audit Trail Architecture
- **Decision**: Dual-layer audit strategy:
  1. *Current-state metadata* on business tables (`created_at`, `created_by`, `modified_at`, `modified_by`, `approved_at`, `approved_by`).
  2. *Immutable append-only `audit_logs` table* recording entity name, entity ID, action (`INSERT`, `UPDATE`, `STATE_CHANGE`, `REVERSAL`), old state JSON, new state JSON, changed fields, operator ID, timestamp, and optional reason.
- **Rationale**:
  - Meets Constitution Principle XI (Audit Trail) and Constitution Principle X (Immutable Posted Records).
  - Reversals create new audit events and new correcting transactions rather than overwriting historical rows.
- **Alternatives Considered**:
  - *Event Sourcing (rebuilding state entirely from event streams)*: Unnecessary complexity and high cognitive overhead for MVP; table-based state with immutable audit event logging achieves equal auditability with standard relational querying.

---

### Decision 5: Document Storage & Integrity Hashing
- **Decision**: Filesystem / Object Storage (S3-compatible) storage abstraction with database metadata persistence.
- **Rationale**:
  - Binary blobs are never stored directly in transactional relational tables (prevents database bloat).
  - Files are stored in structured paths: `/documents/{organization_id}/{year}/{month}/{doc_id}.ext`.
  - SHA-256 hash is computed at upload stream time and indexed with a unique constraint per organization to immediately catch `EXACT_DUPLICATE` documents (Constitution Principle VIII).
- **Alternatives Considered**:
  - *Database BYTEA columns*: Slows down table scans, increases backup size, degrades cache performance.

---

### Decision 6: Multi-Tenant & Security Boundary
- **Decision**: Single shared database with strict `organization_id` foreign keys on all business tables, enforced via repository/ORM query scopes and API authentication context.
- **Rationale**:
  - Satisfies Constitution Principle XXIII (Security & Confidentiality) and Constitution Principle XVIII (API Boundary).
  - Keeps initial deployment simple for single contractor operations while ensuring schema readiness for future SaaS multi-tenancy without database migrations.
- **Alternatives Considered**:
  - *Separate Database per Tenant*: Excessive infrastructure overhead for early-stage SaaS.
  - *Schema per Tenant*: High migration maintenance cost across dozens of tenants.
