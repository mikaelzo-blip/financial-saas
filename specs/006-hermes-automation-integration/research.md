# Research: Hermes Automation Integration

## Decisions

### Machine boundary

**Decision**: use a dedicated bearer token configured at runtime and bind every successful request to the configured organization UUID.

**Rationale**: existing general API dependencies accept caller-provided organization headers and are not a suitable machine trust boundary. A dedicated disabled-by-default credential validates the request before tenant selection and avoids putting a token in source, jobs, or a database record.

**Alternatives considered**: reusing `X-Organization-ID` is unauthenticated; direct PostgreSQL violates Constitution XVIII; building user/role credential management creates an unapproved identity policy.

### Idempotency and correlation

**Decision**: hash the submitted idempotency key with SHA-256 and persist an additive, tenant-scoped `HermesSubmission` record.

**Rationale**: a stable key makes retries return the original document without storing a replayable raw key. The existing document hash remains the authority for exact content duplication.

### Retry behavior

**Decision**: retry only transport exceptions, HTTP 408, 429, and 5xx with a bounded exponential backoff; never retry 4xx review, auth, authorization, validation, or conflict responses.

### Review and accounting

**Decision**: expose document intake only, reuse Feature 005 processing, and return its processing/review status as authoritative. Transaction conversion, human approval, and deterministic posting remain existing backend workflows.

### Audit data minimization

**Decision**: append an `HERMES_DOCUMENT_SUBMITTED` audit event with tenant, submission UUID, key fingerprint, document UUID and safe status only.
