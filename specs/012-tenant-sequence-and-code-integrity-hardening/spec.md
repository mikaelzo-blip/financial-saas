# Feature Specification: Tenant Sequence and Code Integrity Hardening

**Feature Branch**: `012-tenant-sequence-and-code-integrity-hardening`  
**Created**: 2026-09-10  
**Status**: SPECIFIED, CLARIFIED, EVIDENCE-GATED & IMPLEMENTATION-READY
**Input**: FIN-P1-103, FIN-P1-104, and independently verified current-main identifier audit

## Clarifications

### Session 2026-09-10 — Audit evidence and implementation boundary

- **Q1: Is FIN-P1-103 a reproduced PostgreSQL incident?** → **Decision**: Yes, the unmodified current implementation reproduces the race on disposable PostgreSQL 16. N=50 same-tenant allocation probes returned duplicate candidates, and concurrent creates converted the race into PostgreSQL uniqueness failures. PostgreSQL remains authoritative; SQLite concurrency is not equivalent evidence.
- **Q2: What uniqueness scope applies to internal business codes?** → **Decision**: Preserve the existing tenant-local service semantics and current formats. Internal codes are tenant-unique unless an explicitly global domain rule already exists, such as organization slugs and inbound WhatsApp sender phone mappings.
- **Q3: Which FIN-P1-104 mismatches are in scope?** → **Decision**: `MoneyMovement.movement_code`, `Settlement.settlement_code`, and `FixedAsset.asset_code`. Their current service validation/generation is tenant-scoped while model/migration uniqueness is global.
- **Q4: May historical codes be changed?** → **Decision**: No. No renumbering, sequence reset, deletion, or destructive migration is allowed.
- **Q5: Must generated formats change?** → **Decision**: No. Preserve `TRX-YYYY-######`, `JE-YYYY-######`, `PRJ-YYYY-###`, `DOC-YYYY-######`, `INV-YYYY-######`, `BIL-YYYY-######`, `ADV-YYYY-######`, `REL-YYYY-######`, `MM-YYYY-######`, and `SET-######` unless a new approved policy makes the current format impossible to preserve.
- **Q6: Is a process-local Python lock acceptable?** → **Decision**: No. Authoritative allocation must be database-backed and transactionally safe across processes and workers.
- **Q7: Is `DocumentSession.session_code` a confirmed Feature 012 mismatch?** → **Decision**: No. Its generation and global constraint are aligned. Its truncated random entropy is recorded as a static related concern but is not migrated under this feature without separate scope approval.
- **Q8: What happens when PostgreSQL cannot be used for the required reproduction?** → **Decision**: The feature remains blocked and no claim of reproduced PostgreSQL failure may be made. In this evidence gate, disposable PostgreSQL was available and the race was reproduced. The Alembic baseline prerequisite is now resolved; tracked PostgreSQL tests and clean-retry behavior remain implementation checkpoints, not design blockers.
- **Q9: What is the exact counter scope and schema representation for SET settlement codes?** → **Decision**: SET settlement codes are TENANT-GLOBAL and DO NOT reset by year. Each organization has its own monotonically allocated SET namespace (`SET-000001`, `SET-000002`, ...). PostgreSQL NULL semantics MUST NOT be used to represent this scope. The counter design uses an explicit non-null `scope_key` representation: `organization_id`, `namespace`, `scope_key`, where year-scoped namespaces use an explicit year value (e.g. `'2026'`) and non-year tenant-global namespaces use the explicit non-null value `'GLOBAL'`. The visible `SET-######` format remains unchanged.
- **Q10: Are caller-supplied asset_code validation and fixed-asset depreciation transaction-code length validation in scope for Feature 012?** → **Decision**: No. They are confirmed OUT OF SCOPE for Feature 012 unless proven to block sequence/constraint remediation itself. They are recorded as deferred follow-up observations.

## User Scenarios & Testing

### User Story 1 - Allocate tenant business codes safely under concurrency (Priority: P1)

As an application worker creating a financial or operational record, I need the next business code allocated by the database so that simultaneous HTTP requests, retries, WhatsApp intake, and background work cannot create duplicate authoritative identifiers or partial records.

**Why this priority**: Duplicate identifiers can make records ambiguous and can turn financial creation/posting retries into failures or duplicate side effects.

**Independent Test**: With a real PostgreSQL database, run N independent sessions against each affected generator/creation path for a common organization and year; assert N committed records have unique codes, no partial records remain after failed allocation, and any journal side effect is at most once per authoritative transaction.

**Acceptance Scenarios**:

1. **Given** an empty tenant/year sequence and N concurrent valid creates, **When** all sessions allocate and commit, **Then** each committed record receives one unique code in the existing format and no session reports an unhandled collision.
2. **Given** two concurrent paths share the `TRX-YYYY-######` namespace, including a normal transaction and a reversal, **When** both allocate codes, **Then** the codes do not collide and the shared namespace remains in use.
3. **Given** a transaction fails after allocation but before its business record commits, **When** the database transaction rolls back, **Then** no partially committed business record or journal exists; later allocation remains unique even if a numeric gap is present.
4. **Given** two organizations allocate the same namespace/year concurrently, **When** both commit, **Then** each organization owns its own tenant-local code and neither can read or claim the other organization’s record.

---

### User Story 2 - Align uniqueness constraints with tenant ownership (Priority: P1)

As a tenant administrator, I need tenant-owned business identifiers to be unique within my organization rather than globally so that another organization using the same valid local code does not receive an avoidable database collision.

**Why this priority**: The current global constraints contradict the service’s tenant-scoped generation and validation and can reject valid cross-tenant records.

**Independent Test**: Against a non-production PostgreSQL database at the current migration head, run preflight duplicate queries, apply the non-destructive constraint migration, and create the same valid movement, settlement, and asset codes in two organizations. Assert both succeed and same-tenant duplicates remain rejected.

**Acceptance Scenarios**:

1. **Given** organization A owns `MM-YYYY-000001`, **When** organization B creates its own first movement, **Then** B may also own `MM-YYYY-000001`.
2. **Given** organization A owns `SET-000001`, **When** organization B creates its own first settlement, **Then** B may also own `SET-000001`.
3. **Given** organization A owns `AST-001`, **When** organization B creates `AST-001`, **Then** B succeeds, while a second `AST-001` in A is rejected.
4. **Given** existing rows satisfy the current global uniqueness constraints, **When** the composite constraints are introduced, **Then** no existing business code is changed, deleted, or renumbered.

---

### User Story 3 - Preserve compatibility and fail safely (Priority: P2)

As an auditor or integrator, I need existing business-code formats, API behavior, tenant ownership, and accounting invariants preserved while collision and allocation errors fail transactionally and observably.

**Why this priority**: Hardening must not alter posted history or silently change identifiers consumed by users and downstream workflows.

**Independent Test**: Run format, retry/error, rollback, tenant-isolation, accounting-balance, and migration offline-chain tests against the complete affected set.

**Acceptance Scenarios**:

1. **Given** a generated code is externally visible, **When** allocation is hardened, **Then** its prefix, year placement, and zero-padding remain unchanged.
2. **Given** a bounded retryable uniqueness collision occurs, **When** the operation retries, **Then** it uses a fresh transaction-safe allocation and either commits one complete record or returns a controlled failure without partial financial state.
3. **Given** an existing posted transaction, journal, document, invoice, bill, or asset, **When** the feature is deployed, **Then** its code and posted accounting history remain unchanged.
4. **Given** an unsupported or ambiguous identifier policy is encountered, **When** implementation would require a format or financial-semantics decision, **Then** the operation remains blocked and the policy is escalated rather than guessed.

## Edge Cases

- The sequence scope has no existing row and multiple sessions attempt first allocation simultaneously.
- A transaction rolls back after counter allocation; gaps are acceptable, duplicate codes are not.
- The year changes while old-year records remain present; allocation uses the requested business date and never counts another year.
- Existing records have non-canonical but valid historical code formats; migration does not rewrite them.
- A caller-supplied external invoice/bill/reference or asset code exceeds its storage/embedded-code limits; implementation must validate without silently truncating it.
- A movement contains multiple settlements; all settlement codes must be allocated within the same tenant transaction.
- A normal transaction and reversal allocate from the same transaction-code namespace.
- A database uniqueness violation occurs after a process or worker retry; no duplicate journal or partially committed parent/child records may remain.
- PostgreSQL is unavailable in local development; tests must clearly skip/block PostgreSQL-specific evidence rather than substitute SQLite claims.
- The protected document storage directories remain out of scope and untouched.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST inventory and route every internal generated business identifier through a database-authoritative allocation mechanism before production implementation is considered complete.
- **FR-002**: The system MUST allocate tenant/year-scoped identifiers atomically for the existing year-coded namespaces: `TRX`, `JE`, `PRJ`, `DOC`, `INV`, `BIL`, `ADV`, `REL`, and `MM`.
- **FR-003**: The system MUST allocate the tenant-scoped non-year `SET` namespace atomically without inventing a new external format.
- **FR-004**: The system MUST make the normal transaction and reversal generators use one collision-safe `TRX-YYYY-######` namespace per tenant/year.
- **FR-005**: The system MUST preserve existing generated code formats, externally visible values, API compatibility, and existing historical identifiers.
- **FR-006**: The system MUST retain tenant isolation in allocation, persistence, reads, retries, and error handling; organization A MUST NOT allocate, read, or claim organization B’s codes or records.
- **FR-007**: The system MUST change only the confirmed FIN-P1-104 global uniqueness mismatches to tenant-scoped composite uniqueness: `(organization_id, movement_code)`, `(organization_id, settlement_code)`, and `(organization_id, asset_code)`, subject to verified live constraint names and preflight checks.
- **FR-008**: The system MUST preserve same-tenant duplicate rejection after the constraint changes.
- **FR-009**: Allocation and the associated business record MUST participate in one database transaction; failed operations MUST not leave partially committed records or journals.
- **FR-010**: Any collision retry MUST be bounded, use fresh transaction-safe state, and return a controlled error when exhausted; retries MUST NOT duplicate authoritative financial posting.
- **FR-011**: The system MUST preserve deterministic accounting, double-entry equality, immutable posted records, reversal correction flow, and audit attribution; this feature MUST NOT invent or alter debit/credit rules.
- **FR-012**: The system MUST execute PostgreSQL-specific concurrency and migration tests before implementation completion; SQLite-only tests MUST NOT be reported as equivalent.
- **FR-013**: The migration MUST run preflight duplicate checks, fail closed if `(organization_id, code)` duplicates exist or expected constraints are absent, and avoid deleting, renumbering, or regenerating historical codes.
- **FR-014**: The system MUST keep global uniqueness for identifiers whose current domain semantics require global resolution, including organization slugs and WhatsApp sender phone mappings.
- **FR-015**: The system MUST leave `backend/storage` and `backend/backend/storage` untouched.
- **FR-016**: The system MUST classify `DocumentSession.session_code`, UUID-derived opening-balance/document-session codes, caller-supplied references, and depreciation embedded codes separately from the confirmed FIN-P1-104 migration scope unless an approved clarification expands it.
- **FR-017**: The implementation MUST provide tests for same-tenant concurrency, cross-tenant same-code success, same-tenant duplicate rejection, rollback, no duplicate posting, correct ownership, year rollover, bounded retry, format compatibility, and migration chain validity.

### Key Entities

- **Tenant sequence allocation scope**: A database-owned `(organization_id, namespace, year-or-non-year-scope)` counter identity used to reserve the next number without process-local coordination.
- **Transaction**: Tenant-owned financial candidate/posted record using the shared `TRX-YYYY-######` namespace for normal and reversal transactions.
- **JournalEntry**: Tenant-owned authoritative journal header using `JE-YYYY-######`; allocation must not produce duplicate entries during retries.
- **MoneyMovement**: Tenant-owned cash/bank movement using `MM-YYYY-######`; its code uniqueness must be tenant-scoped.
- **Settlement**: Tenant-owned settlement child using `SET-######`; its code uniqueness must be tenant-scoped.
- **FixedAsset**: Tenant-owned asset register record using a caller-supplied `asset_code`; uniqueness must be tenant-scoped and validated transactionally.
- **Sequence allocation result**: The namespace, effective year scope, numeric value, rendered code, and transaction context needed by services without exposing database internals through public APIs.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A PostgreSQL test with N=50 concurrent valid creates for each selected year-coded generator produces N committed records with N unique codes and zero unhandled duplicate-code failures.
- **SC-002**: PostgreSQL tests for two organizations create the same valid movement, settlement, and asset code successfully, while same-tenant duplicate attempts are rejected.
- **SC-003**: All failed allocation/create attempts leave zero partial parent, child, journal, or posting records after rollback.
- **SC-004**: Repeating an idempotent or retryable financial operation produces at most one authoritative posting and preserves debit equals credit.
- **SC-005**: 100% of pre-existing historical code values remain byte-for-byte unchanged after migration validation.
- **SC-006**: Existing public generated formats remain unchanged for every inventoried generator; no truncation or silent renumbering occurs.
- **SC-007**: The migration’s duplicate preflight returns zero conflicting tenant/code tuples before constraints are changed, and offline Alembic validation passes.
- **SC-008**: The final consistency analysis reports 100% requirement coverage, zero Critical/High consistency findings, and zero Constitution violations.

## Assumptions

- PostgreSQL is the authoritative database for concurrency and migration semantics; SQLite remains a unit-test convenience only.
- The current repository’s tenant-local service behavior and existing code formats are the compatibility baseline.
- Sequence gaps caused by rolled-back allocations are acceptable; duplicate or reused authoritative codes are not.
- A database-backed tenant/year counter table is the provisional simplest mechanism, subject to PostgreSQL reproduction and design verification.
- Unique constraints remain defense-in-depth; they do not replace atomic allocation.
- Global organization slug and WhatsApp sender phone uniqueness remains intentional because those identifiers resolve tenant context before a tenant is known.
- No real production database, protected storage tree, or external paid resource is accessed during this feature’s design phase.

## Out of Scope

- Accounting-rule changes, financial classification, tax policy, revenue recognition, capitalization, depreciation policy, or posting semantics.
- Renumbering, regenerating, deleting, or rewriting historical business codes.
- Changes to `backend/storage` or `backend/backend/storage`.
- Reworking all foreign-key tenant semantics or unrelated authentication/RBAC issues.
- Activating remote WhatsApp/Cloudflare infrastructure.
- Migrating `DocumentSession.session_code` solely because of its entropy concern.
- Changing caller-supplied external invoice, bill, PO, reference, or asset-code formats without an approved policy.
