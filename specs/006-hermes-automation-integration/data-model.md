# Data Model: Hermes Automation Integration

## HermesSubmission

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | Primary key; correlation identifier. |
| `organization_id` | UUID FK | Required, indexed, tenant boundary. |
| `operation` | varchar(50) | Required. Current value: `DOCUMENT_INTAKE`. |
| `idempotency_key_hash` | char(64) | SHA-256 fingerprint; never raw key. |
| `document_id` | UUID FK nullable | Immutable Feature 005 source document. |
| `outcome_status` | varchar(50) | `ACCEPTED`; no approval/posting states. |
| `safe_error_code` | varchar(100) nullable | Non-sensitive operational outcome code. |
| `created_at`, `updated_at` | timestamp | Server timestamps. |

Unique constraint: `(organization_id, operation, idempotency_key_hash)`. A repeat request returns its original document rather than creating new evidence.

## Relationships

```text
Organization 1 ── * HermesSubmission * ── 0..1 Document
                         |
                         +── AuditLog (append-only event by submission UUID)
```

This feature introduces no transaction, journal, AR, AP, cash, or reporting data.
