# FIN-001 Data and Transaction Model

## Existing Authoritative Entities

| Entity | Authority | FIN-001 treatment |
|---|---|---|
| `CustomerInvoice` | AR source balance derives from collectible amount minus customer payment allocations | Lock selected row `FOR UPDATE`; do not add columns or constraints. |
| `VendorBill` | AP source balance derives from bill total minus vendor payment allocations | Lock selected row `FOR UPDATE`; do not add columns or constraints. |
| `Transaction` payment row | Posted payment amount bounds aggregate consumption | Lock selected payment row `FOR UPDATE` before allocation-total validation. |
| `CustomerPaymentAllocation` | Positive child allocation from payment to invoice | Insert only after locked revalidation; no schema change. |
| `CustomerRetentionRelease` | Changes the collectible portion of an invoice | Lock the same invoice source before changing released retention; preserve existing accounting policy. |
| `VendorPaymentAllocation` | Positive child allocation from payment to bill | Insert only after locked revalidation; no schema change. |
| Journal/money movement/settlement/audit | Existing derived financial-effect graph | Keep in same request transaction; no semantic change. |

## Derived Values

### AR

```text
collectible = invoice.total_amount - invoice.retention_amount
              + invoice.retention_released_amount
allocated = SUM(customer_payment_allocations.allocated_amount)
outstanding = max(0, collectible - allocated)
```

FIN-001 validates `requested_for_invoice <= outstanding` only after locking the invoice and executing a fresh SQL aggregate against `customer_payment_allocations`. It MUST NOT trust `invoice.allocations` if that relationship may already be present in the SQLAlchemy identity map. Invoice status derives from the post-insert authoritative total according to existing policy.

### AP

```text
allocated = SUM(vendor_payment_allocations.allocated_amount)
outstanding = bill.total_amount - allocated
```

FIN-001 validates `requested_for_bill <= outstanding` only after locking the bill and executing a fresh SQL aggregate against `vendor_payment_allocations`. It MUST NOT trust `bill.allocations` if that relationship may already be present in the SQLAlchemy identity map. Bill status derives from the post-insert authoritative total according to existing policy.

### Payment consumption

```text
payment_allocated = SUM(all allocation rows for payment_transaction_id)
remaining_payment = payment.amount - payment_allocated
```

FIN-001 locks the payment row before validation so concurrent uses of the same payment cannot both consume the same remaining amount.

## CP1 Observed Boundary

Before CP2, neither source nor payment rows are locked at the authoritative allocation boundary. The tracked independent-session PostgreSQL tests prove AR/AP `120.00` totals are possible. Current endpoint transaction-code allocation can serialize same-tenant HTTP requests upstream, but it does not protect direct service/database callers and is not an authoritative allocation invariant.

## Lock Contract

```text
payment lock: (organization_id, payment_transaction_id)
source lock:  (organization_id, source_uuid)
source order: organization_id ascending, source_uuid ascending
```

The organization is fixed by the authenticated request. Source UUID ordering is canonical and must be implemented consistently for `CustomerInvoice` and `VendorBill`; no database UUID collation assumption is relied upon without a test. The implementation sorts UUID objects in application code and acquires one `FOR UPDATE` row lock per UUID in that sequence; it must not rely on a bulk `IN (...) ORDER BY` query to impose physical lock-acquisition order.

## Transaction State Rules

| State | Allowed next state | Requirement |
|---|---|---|
| Attempt begins | Payment/source locks | No authoritative balance decision before locks. |
| Locks acquired | Validate | Every requested source belongs to organization and is present. |
| Validated | Add allocations/status effects | Payment/source amounts and counterparties remain compatible. |
| Flush failure / transient conflict | Rollback, clean retry | No access to expired ORM objects in retry closure. |
| Domain invariant failure | Rollback request | No retry; existing controlled domain response. |
| Successful operation | Request commit | One complete financial-effect graph commits. |

## Schema Decision

**No schema or migration change.** Existing parent and allocation tables are sufficient for row-level serialization. No balance materialization, trigger, allocation tenant column, unique constraint, or historical repair is authorized by FIN-001.

## Compatibility Rules

- Monetary calculations remain `Decimal`/PostgreSQL `NUMERIC`; no binary float is introduced.
- The source allocation check does not change invoice/bill, transaction, journal, settlement, or status domain semantics.
- Allocation rows are appended for new payments only; no historical allocation is modified.
