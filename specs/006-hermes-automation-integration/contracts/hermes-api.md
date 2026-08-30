# Hermes API Contract

## `POST /api/v1/hermes/documents/upload`

Authenticated machine endpoint for evidentiary document intake only.

### Required headers

| Header | Value |
|---|---|
| `Authorization` | `Bearer <runtime-provisioned-machine-token>` |
| `Idempotency-Key` | Stable non-empty client key, 16–200 characters |

### Multipart fields

| Field | Required | Notes |
|---|---|---|
| `file` | yes | Original evidence; Feature 005 validates signature, size and SHA-256 hash. |
| `document_type` | no | Candidate document type; default `UNKNOWN`. |
| `process` | no | Defaults true and schedules Feature 005 processing. |

`source_channel` is fixed to `API`; the authenticated server principal fixes the tenant. Callers cannot provide organization or user identifiers.

### Responses

| Status | Meaning |
|---|---|
| 202 | New immutable source document accepted and processing scheduled. |
| 200 | Same idempotency key replayed; returns original document. |
| 401 | Missing or invalid machine credential. |
| 422 | Invalid idempotency key or evidence. |
| 409 | Exact content duplicate or prior incomplete submission conflict. |
| 503 | Machine endpoint disabled or tenant configuration invalid. |

No approve, post, journal, or transaction-creation contract exists.
