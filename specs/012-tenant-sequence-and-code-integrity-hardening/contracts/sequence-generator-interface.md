# Sequence Generator Internal Contract

This is an internal service contract. It is not a public API and must not expose database implementation details to callers.

## Types

```text
SequenceScope:
  organization_id: UUID
  namespace: str
  scope_key: str  # calendar year string (e.g. "2026") or "GLOBAL" for non-year tenant-global

SequenceAllocation:
  organization_id: UUID
  namespace: str
  scope_key: str
  value: positive int
  code: str

SequenceExhaustedError:
  controlled domain error when the configured numeric range cannot render a valid code

SequenceCollisionError:
  controlled domain error after bounded retry exhaustion or an unexpected legacy collision
```

## Protocol

```text
allocate_next(
    session: AsyncSession,
    organization_id: UUID,
    namespace: str,
    scope_key: str,  # calendar year (e.g. "2026") or "GLOBAL"
) -> SequenceAllocation
```

### Contract rules

1. `allocate_next` participates in the caller’s transaction and does not commit or roll back the caller’s session.
2. The scope key includes `organization_id` for every tenant-owned namespace.
3. Year-coded namespaces require the business date’s year as a string (e.g. `"2026"`). The non-year `SET` namespace requires the explicit sentinel `"GLOBAL"`; PostgreSQL-NULL semantics are prohibited.
4. The returned `code` preserves the existing namespace prefix and zero-padding. Rendering rules belong in one tested mapping, not duplicated across services.
5. The transaction-code namespace is shared by normal and reversal paths.
6. The allocator must be safe across HTTP requests, workers, retries, and multiple processes.
7. A uniqueness exception cannot be ignored in a failed transaction. Bounded retry must establish a clean transaction boundary and request a fresh allocation.
8. Allocation does not choose accounting accounts, debit/credit legs, classification, approval, or posting status.

## Namespace compatibility map

| Namespace | Format | Scope Key | Uniqueness Scope |
|---|---|---|---|
| `TRX` | `TRX-YYYY-######` | `YYYY` (e.g. `"2026"`) | organization + year |
| `JE` | `JE-YYYY-######` | `YYYY` (e.g. `"2026"`) | organization + year |
| `PRJ` | `PRJ-YYYY-###` | `YYYY` (e.g. `"2026"`) | organization + year |
| `DOC` | `DOC-YYYY-######` | `YYYY` (e.g. `"2026"`) | organization + year |
| `INV` | `INV-YYYY-######` | `YYYY` (e.g. `"2026"`) | organization + year |
| `BIL` | `BIL-YYYY-######` | `YYYY` (e.g. `"2026"`) | organization + year |
| `ADV` | `ADV-YYYY-######` | `YYYY` (e.g. `"2026"`) | organization + year |
| `REL` | `REL-YYYY-######` | `YYYY` (e.g. `"2026"`) | organization + year |
| `MM` | `MM-YYYY-######` | `YYYY` (e.g. `"2026"`) | organization + year |
| `SET` | `SET-######` | `"GLOBAL"` | organization + tenant-global (non-year) |

## Errors and observability

Errors must identify the namespace and tenant-safe operation context without exposing secrets or another tenant’s records. Existing API error conventions should map exhausted allocation/collision failures to a controlled retryable or validation response; the internal exception must not leak raw database URLs, credentials, or SQL containing sensitive values.
