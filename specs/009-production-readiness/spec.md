# Feature Specification: Production Readiness Foundation

**Feature Branch**: `hermes/009-production-readiness`
**Status**: SPECIFIED & CLARIFIED
**Created**: 2026-09-01

## Scope

Resolve application-controlled Critical and High findings from `docs/production-readiness-audit.md` without deploying infrastructure or activating paid/external providers.

## Clarifications

- Production must fail closed when the JWT secret, database URLs, CORS origins, or storage path retain unsafe development defaults.
- Browser users authenticate with email/password through the SaaS API. Tenant and user identity come from the verified JWT, never client-selected headers in production.
- Machine endpoints retain their existing distinct tenant-bound credentials. Public WhatsApp webhook endpoints retain HMAC/token verification.
- Development may retain explicit demo conveniences only when they cannot activate in staging/production. The frontend must never convert a failed login into an authenticated session.
- HTTPS terminates at an approved reverse proxy/ingress; the application emits proxy-aware security headers but this feature does not change DNS or infrastructure.
- Backup/restore/deployment work is delivered as executable, operator-reviewed runbooks and validation commands. No real production data or infrastructure is touched.
- Monitoring, error-tracking vendors, durable object storage, Meta activation, and paid AI remain deferred approval-bound integrations.

## User Stories

### US1 — Fail-closed production configuration (P1)
An operator starting the application in production receives a clear startup failure if secrets, CORS, database, storage, or debug settings are unsafe.

### US2 — Authenticated tenant-bound API (P1)
A user logs in with email/password. General SaaS API requests derive user and organization from the signed JWT. A forged organization header cannot change tenant scope.

### US3 — Production probes and diagnostics (P1)
An orchestrator can distinguish liveness from database readiness. Operators receive structured request logs with correlation IDs and security headers without financial payloads.

### US4 — Controlled business bootstrap (P1)
An operator can atomically create one organization, initial admin, standard COA, and default payment accounts through an idempotent CLI, without exposing a public unauthenticated bootstrap API.

### US5 — Recoverable operations (P1)
Operators have exact backup, restore-test, migration, deployment, rollback, incident, UAT, and retention procedures with explicit approval boundaries.

## Functional Requirements

- **FR-001**: Production configuration MUST reject insecure default JWT secrets, wildcard CORS, debug mode, non-PostgreSQL database URLs, masked sync URLs, and relative storage paths.
- **FR-002**: `POST /api/v1/auth/login` MUST verify an active user password and return a signed expiring token plus tenant/user metadata.
- **FR-003**: Production general API identity MUST derive from JWT claims and active database user state; client headers MUST NOT select a different tenant or user.
- **FR-004**: Machine and public webhook routes MUST retain their existing independent authentication boundaries.
- **FR-005**: Frontend authentication failure MUST remain failure and MUST NOT create a mock session.
- **FR-006**: Production CORS MUST use an explicit allowlist; security headers MUST be emitted.
- **FR-007**: `/health` MUST remain a database-independent liveness probe; `/ready` MUST verify database connectivity and return 503 when unavailable.
- **FR-008**: Request logs MUST be structured, correlation-ID based, and exclude bodies, authorization values, and financial data.
- **FR-009**: Database pool size, overflow, timeout, and recycle MUST be configurable with safe bounds.
- **FR-010**: Bootstrap CLI MUST create organization/admin/COA/payment accounts atomically and reject ambiguous duplicate state.
- **FR-011**: Production operations documentation MUST cover backups, restore testing, migrations, deployment, rollback, incidents, UAT, initialization, audit retention, storage recovery, WhatsApp prerequisites, and AI egress approval.
- **FR-012**: CI MUST continue locked dependency, full test, migration, frontend, and repository-safety validation.

## Success Criteria

- Unsafe production settings fail before application startup in automated tests.
- Valid login succeeds; invalid credentials and inactive users fail without account enumeration.
- Production identity tests prove forged tenant/user headers cannot cross tenant boundaries.
- Readiness tests cover success and database failure.
- Frontend tests prove failed login creates no authenticated session.
- Bootstrap test proves idempotent-safe initialization and balanced standard master data creation.
- Full quality gates pass with zero Critical and zero High consistency findings.

## Out of Scope / Deferred

- Real production deployment or database mutation.
- Real DNS/TLS changes.
- Purchasing managed database, object storage, monitoring, error tracking, Meta, or AI services.
- Sending company financial data to an external provider.