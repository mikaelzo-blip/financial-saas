# Feature Specification: Serialize AR/AP Allocations and Enforce Source-Balance Integrity

**Feature Branch**: `hermes/fin-001-ar-ap-concurrency`
**Created**: 2026-09-11
**Status**: CP1 COMPLETE — service-race evidence and endpoint characterization verified; CP2 not started
**Work item**: FIN-001 — Accounting-integrity remediation (P1)

## Clarifications and Evidence Boundary

- FIN-001 is a new remediation after merged Feature 012; it is not a continuation of Feature 012.
- **Service invariant defect**: the current `main` baseline was reproduced against disposable PostgreSQL 16 with two independent async sessions, two independent transactions, and `asyncio.Barrier(2)`. Two allocations of `60.00` against one `100.00` source both committed for both AR and AP; each final allocation total was `120.00`.
- PostgreSQL, not SQLite, is authoritative for this defect. The allocation services execute under PostgreSQL `READ COMMITTED`; separate transactions may both observe the same committed source state unless the authoritative source boundary is locked.
- **Endpoint characterization**: current same-tenant customer-payment and vendor-payment HTTP requests obtain Feature-012 `TRX` tenant-sequence allocation while transaction creation occurs before AR/AP allocation. The sequence upsert serializes those requests upstream, so both requests cannot naturally enter the service allocation race window together. This valid incidental serialization is not a FIN-001 fix and must not be bypassed or instrumented artificially.
- **Correctness requirement**: AR/AP allocation correctness must remain valid for independent service/database transactions even when no upstream transaction-code allocation serializes callers.
- The feature does not change accounting mappings, debit/credit rules, API request shape, frontend behavior, historical financial records, or database schema.
- A database aggregate constraint is not required for the smallest correct remediation because the authoritative source row can serialize validation and allocation in one transaction. A future constraint-based defense-in-depth design requires separate approval.

## User Scenarios & Testing

### User Story 1 — Prevent concurrent source over-allocation (Priority: P1)

As a finance operator, I need simultaneous independent allocation operations to serialize at the authoritative source boundary so an invoice or bill can never be allocated above its authoritative collectible/payable balance.

**Why this priority**: Over-allocation corrupts AR/AP derived balances and can cause more cash/payment value to be consumed than a source supports.

**Independent Test**: CP1 uses disposable PostgreSQL, two independent sessions/transactions, and a barrier to reproduce two committed `60.00` allocations against one `100.00` invoice or bill (`120.00` expected RED). CP2 turns this service-boundary evidence green by asserting at most one allocation commits and the final total is at most `100.00`.

**Acceptance Scenarios**:

1. **Given** two valid customer-payment operations target one collectible invoice, **when** they reach allocation concurrently, **then** the source-row lock makes one operation validate after the other and the committed allocation total does not exceed the collectible amount.
2. **Given** two valid vendor-payment operations target one unpaid bill, **when** they reach allocation concurrently, **then** the committed allocation total does not exceed the bill total.
3. **Given** an allocation loses the contention race, **when** it reads the locked, refreshed source state, **then** it fails with the existing invariant-validation response and does not create a transaction, journal, allocation, settlement, money movement, or audit effect.

---

### User Story 2 — Safely allocate one payment to multiple sources (Priority: P1)

As an integration or service caller, I need a payment that allocates to several invoices or bills to lock all source rows in a deterministic order so independently reversed source lists cannot deadlock or leave partial effects.

**Why this priority**: A multi-source allocation must remain atomic and deadlock-resistant while preserving exact source balances.

**Independent Test**: Start two independent PostgreSQL sessions with the same two sources in opposite input order. Synchronize execution and assert completion within the bounded timeout, no `40P01` deadlock, no over-allocation, and exactly the expected committed rows.

**Acceptance Scenarios**:

1. **Given** an AR or AP request contains duplicate source IDs, **when** validation begins, **then** amounts are first coalesced by source ID and each source row is locked once.
2. **Given** two requests name the same sources in reverse input order, **when** they acquire locks, **then** both lock `(organization_id, UUID)` ascending order rather than client input order.
3. **Given** any source is cancelled, unavailable in the tenant, mismatched to the payment counterparty, or lacks outstanding balance, **when** the operation has acquired locks, **then** the whole operation rolls back without partial allocations.

---

### User Story 3 — Preserve retry, tenant, and posting integrity (Priority: P1)

As an auditor, I need a retryable database conflict to roll back the complete financial operation before any retry so retries neither duplicate postings nor leak data across tenants.

**Why this priority**: The operation includes financial transactions, journals, allocations, money movements, settlements, and audit effects that must remain one atomic graph.

**Independent Test**: Force a classified retryable PostgreSQL conflict after financial graph creation, then assert one final authoritative graph, no rows from the failed attempt, tenant-scoped source lookup, and an unchanged debit/credit policy.

**Acceptance Scenarios**:

1. **Given** a retryable PostgreSQL serialization or deadlock error occurs before commit, **when** the bounded retry policy applies, **then** the failed attempt is rolled back and a clean retry may commit at most one financial graph.
2. **Given** another tenant supplies an invoice or bill UUID, **when** allocation is attempted under the current organization, **then** lookup fails closed and no side effect is committed.
3. **Given** PostgreSQL integration prerequisites are unavailable in CI, **when** the FIN-001 concurrency suite is selected, **then** the required gate fails rather than silently skipping.

## Edge Cases

- A source has retention: AR must use `calculate_collectible_amount()` rather than gross invoice total; concurrent retention release and payment allocation share the locked invoice source protocol before either derived value is changed.
- Two requests use different payments against one source; source-row locking serializes the source balance check.
- Two requests reuse one payment against different sources; payment-row locking serializes the payment aggregate check.
- A request names several sources with duplicate IDs; the aggregate amount per source is validated once after coalescing.
- A transient PostgreSQL `40001`, `40P01`, or configured lock conflict occurs after an attempt has flushed rows; rollback precedes a new attempt.
- Two independently submitted requests are not client-idempotent merely because database retries are safe; duplicate-request idempotency is a separate concern.
- Any post-lock invariant failure is a normal business rejection, not a retry condition.

## Requirements

### Functional Requirements

- **FIN-001-R01**: Concurrent AR allocations MUST NOT allocate more than an invoice's currently collectible authoritative balance.
- **FIN-001-R02**: Concurrent AP allocations MUST NOT allocate more than a bill's currently payable authoritative balance.
- **FIN-001-R03**: The implementation MUST lock source rows within the authoritative transaction before calculating outstanding balance or inserting allocations.
- **FIN-001-R04**: Tenant isolation MUST remain enforced for payment, source, allocation, retry, error, and read paths; cross-tenant source IDs MUST fail closed.
- **FIN-001-R05**: A multi-source allocation MUST coalesce duplicate source IDs and acquire source locks in deterministic `(organization_id, source UUID ascending)` order.
- **FIN-001-R06**: A failed contention attempt or post-lock validation failure MUST roll back the complete operation with no orphan allocation, posting, settlement, money-movement, or audit row.
- **FIN-001-R07**: A classified clean retry MUST use a rolled-back transaction state and produce at most one committed financial-effect graph for its logical operation.
- **FIN-001-R08**: Existing sequential valid, partial-payment, overpayment-rejection, counterparty-mismatch, and status behavior MUST remain backward compatible.
- **FIN-001-R09**: FIN-001 MUST NOT alter accounting mappings, transaction types, debit/credit rules, journal balancing behavior, or revenue/expense recognition policy.
- **FIN-001-R10**: FIN-001 MUST NOT rewrite, delete, renumber, or otherwise modify historical allocations or posted financial records.
- **FIN-001-R11**: PostgreSQL-specific concurrent-session evidence is mandatory; SQLite tests MUST NOT be accepted as equivalent.
- **FIN-001-R12**: CI MUST fail closed when the required FIN-001 PostgreSQL concurrency gate cannot execute; it MUST NOT silently skip due to a missing test database URL.
- **FIN-001-R13**: CP1 MUST characterize, without production instrumentation, that current same-tenant customer/vendor payment endpoints serialize at Feature-012 transaction-code allocation before AR/AP allocation; this result MUST NOT be represented as source-invariant safety.
- **FIN-001-R14**: CP2 source/payment locking and fresh aggregate validation MUST remain required regardless of Feature-012 transaction-code serialization or any other incidental upstream serialization.

### Key Entities

- **AR source**: `CustomerInvoice`, whose collectible amount is derived from invoice total, retention, retention release, and payment allocations.
- **AP source**: `VendorBill`, whose outstanding amount is derived from bill total and payment allocations.
- **Payment transaction**: Posted `Transaction` of type `CUSTOMER_PAYMENT` or `PAY_VENDOR_BILL`; its amount bounds total allocation consumption.
- **Allocation**: `CustomerPaymentAllocation` or `VendorPaymentAllocation`, a positive amount linking one payment transaction to one source.
- **Financial-effect graph**: Payment transaction, journal entry/lines, allocation, money movement, settlement, settlement allocation, and audit effects created by one logical request.

## Success Criteria

- **SC-001**: CP1 executable PostgreSQL barrier tests reproduce AR and AP `120.00` committed totals from competing `60.00` allocations against `100.00` sources as tracked expected RED evidence; CP2 turns the invariant green.
- **SC-002**: Current same-tenant customer/vendor payment HTTP routes have bounded characterization tests demonstrating Feature-012 transaction-code serialization before allocation, without asserting AR/AP source safety.
- **SC-003**: A PostgreSQL reversed-input multi-source characterization records current behavior and the CP2 canonical ordering requirement without implementing locks.
- **SC-004**: Tenant isolation, transaction ownership, identity-map versus SQL-aggregate risk, and existing sequential AR/AP safety are covered without API or accounting-policy change.
- **SC-005**: Required FIN-001 PostgreSQL execution fails closed rather than substituting SQLite or silently skipping.
- **SC-006**: Consistency analysis reports 100% FIN-001 requirement traceability, zero Constitution violations, and zero Critical/High/Medium unresolved findings.

## Assumptions

- PostgreSQL row-level locks are held until the request transaction commits or rolls back.
- The FastAPI `get_db` dependency remains the final request commit/rollback owner unless implementation evidence requires a narrow transaction-owner change.
- Existing Feature 012 clean-transaction retry is the extension point; retry classification will remain bounded and explicit.
- This feature does not add a public multi-source payment endpoint; the service contract must nevertheless make multi-source locking safe for present or future direct callers.

## Out of Scope

- Client idempotency keys or duplicate-submission product policy.
- Aggregate database triggers, materialized balance columns, or cross-table database constraints.
- New tables, migration revisions, or changes to allocation-table tenant columns.
- Accounting mappings, debit/credit policy, revenue recognition, tax, capitalization, depreciation, or historical-data remediation.
- Frontend/API request-schema changes unless a later implementation blocker proves one is necessary and is separately approved.
