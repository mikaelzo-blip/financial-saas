# Production Readiness Audit

**Audit date**: 2026-09-01
**Baseline**: `origin/main` at `99a9279`
**Scope**: Application and repository readiness only. No production deployment, paid resource, real credential, real financial-data egress, WhatsApp registration, or DNS change was performed.

## Executive result

The system is **not production-ready**. Core financial invariants and automated quality gates are strong, but production authentication, fail-closed configuration, database readiness, durable storage operations, observability, deployment packaging, initialization, and operator runbooks require substantial work. Feature `009-production-readiness` is justified.

## Findings

| Area | Control | Status | Evidence / required action |
|---|---|---|---|
| Database | PostgreSQL production configuration | PARTIAL | Async PostgreSQL is configured, but defaults contain development credentials and no production validation. |
| Database | Connection pooling | PARTIAL | `pool_pre_ping` exists; pool size, overflow, recycle, and timeout are not configurable. |
| Database | Alembic migration reliability | PARTIAL | CI generates the complete PostgreSQL SQL chain; no live disposable PostgreSQL upgrade/downgrade test. |
| Database | Migration rollback strategy | MISSING | No operator decision tree or tested backup-before-migrate procedure. |
| Database | Backup | MISSING | No versioned `pg_dump` runbook/script. |
| Database | Restore testing | MISSING | No restore verification procedure or evidence. |
| Database | Disaster recovery | MISSING | No RPO/RTO, ownership, or failover runbook. |
| Security | Authentication | READY | Browser login verifies active users; production/staging general routes require a signed tenant-bound JWT; frontend login failure remains failure. |
| Security | Authorization | PARTIAL | Global production authentication is enforced and financial services retain approval rules; a complete endpoint-by-role permission matrix remains UAT work. |
| Security | Tenant isolation | READY | Production identity binds JWT user and organization; forged or missing tenant/user headers are rejected; machine routes retain fixed tenant credentials. |
| Security | Secrets management | PARTIAL | Production fails closed on unsafe defaults and the runbook requires a secret store; real secret-store integration is deployment-specific. |
| Security | HTTPS/TLS | DEFERRED | Must terminate at approved deployment ingress; no real infrastructure may be changed without approval. |
| Security | CORS | READY | Production/staging require an explicit origin allowlist; wildcard development mode disables credentials. |
| Security | CSRF | READY | Bearer-token API does not use cookie authentication. Reassess if auth moves to cookies. |
| Security | Security headers | READY | Frame, content-type, referrer, permissions, and CSP headers are emitted; HSTS remains ingress-owned after TLS approval. |
| Security | Rate limiting | PARTIAL | WhatsApp has bounded rate limiting; login and general API abuse controls are absent. |
| Security | Webhook authentication | READY | WhatsApp handshake and raw-body HMAC validation fail closed with size limits and tests. |
| Security | Dependency security | PARTIAL | Lockfiles and `pip check`/`npm audit` evidence exist; no automated vulnerability scanner or update policy. |
| Observability | Structured logging | READY | Metadata-only JSON request logs and correlation IDs exclude bodies, query strings, credentials, and financial values. |
| Observability | Health checks | READY | `/health` is a database-independent liveness probe. |
| Observability | Readiness checks | READY | `/ready` executes a database probe and returns 503 on failure. |
| Observability | Monitoring | DEFERRED | External monitoring service requires deployment/provider selection. Application metrics contract is absent. |
| Observability | Error tracking | DEFERRED | External service and financial-data redaction policy require approval/provider selection. |
| Observability | Audit retention | MISSING | Append-only application audit exists; retention, archival, access, and purge policy are undefined. |
| Storage | Document durability | MISSING | Local filesystem is a single-host storage implementation without durable object-storage adapter. |
| Storage | Document backup | MISSING | No storage backup/snapshot procedure. |
| Storage | SHA/hash verification | PARTIAL | SHA-256 duplicate detection exists; scheduled at-rest verification is absent. |
| Storage | Recovery procedures | MISSING | No document/database coordinated restore and reconciliation runbook. |
| Deployment | Development configuration | PARTIAL | Local environment examples exist but are incomplete. |
| Deployment | Staging configuration | MISSING | No explicit staging profile or acceptance gate. |
| Deployment | Production configuration | READY | Staging/production reject unsafe secrets, debug, CORS, database URLs, and relative storage. |
| Deployment | CI/CD | PARTIAL | PR and main quality gates exist; no artifact build, provenance, staging promotion, or deployment workflow. |
| Deployment | Environment separation | MISSING | Environment name exists but does not enforce separation. |
| Deployment | Dependency pinning | READY | Backend `uv.lock` and frontend `package-lock.json` are committed and CI uses locked installs. |
| Deployment | Rollback procedures | READY | Operations runbook defines immutable artifact rollback and restore-first database recovery. |
| Business initialization | Organization creation | READY | Atomic local-only bootstrap CLI creates one organization and rejects duplicates. |
| Business initialization | Initial admin creation | READY | Bootstrap prompts for and hashes the initial admin password. |
| Business initialization | User provisioning | MISSING | No authenticated admin API/runbook. |
| Business initialization | COA seeding | READY | Bootstrap invokes tested standard COA and payment-account seeders atomically. |
| Business initialization | Bank/payment account setup | PARTIAL | Seed service exists; real accounts require an operator workflow. |
| Business initialization | Project/customer/vendor setup | PARTIAL | APIs/models exist; onboarding checklist and authorization hardening are missing. |
| WhatsApp | Provider abstraction readiness | READY | Mock and Meta provider boundaries exist. |
| WhatsApp | Webhook security | READY | HMAC, token verification, media validation, and tenant-bound credentials are tested. |
| WhatsApp | Sandbox prerequisites | DEFERRED | Requires approved Meta sandbox/account resources. |
| WhatsApp | Meta/provider prerequisites | DEFERRED | Documented; external registration and credentials require approval. |
| WhatsApp | Production number requirements | DEFERRED | Real number registration requires approval. |
| AI | Provider abstraction | READY | Mock default and dormant fail-closed cloud codecs exist. |
| AI | Privacy/data-egress controls | PARTIAL | DTO allowlist and no active egress exist; production provider approval and DPA/redaction procedure are absent. |
| AI | Token limits | READY | Executive and Q&A output limits are configured and tested. |
| AI | Cost controls | PARTIAL | Content-addressed cache and limits exist; no spend budget because no paid provider is enabled. |
| AI | Provider timeout/fallback | READY | Bounded timeout and deterministic fallback are tested. |
| AI | Audit logging | READY | Tenant-scoped insight logs and audit events exist. |
| Operations | UAT | MISSING | No signed UAT plan or acceptance record. |
| Operations | Operator documentation | MISSING | Existing docs cover development and WhatsApp internals, not daily production operations. |
| Operations | Troubleshooting documentation | READY | Operations runbook covers probes, integrity errors, storage, credentials, WhatsApp, and AI incidents. |
| Operations | Backup runbook | READY | Versioned logical backup procedure and evidence requirements are documented. |
| Operations | Restore runbook | READY | Isolated restore test and financial/document reconciliation procedure are documented. |
| Operations | Deployment runbook | READY | Staging, migration, smoke, production, rollback, and approval sequence is documented. |

## Feature 009 remediation checkpoint

Application-controlled Critical and High findings are now remediated on `hermes/009-production-readiness`:

- production/staging configuration fails closed for debug, JWT secret, PostgreSQL URLs, CORS, and storage;
- browser login verifies active users and returns tenant-bound JWTs;
- general SaaS routers require verified production identity and reject forged tenant/user headers;
- frontend login failure no longer creates a mock session;
- liveness/readiness probes, security headers, correlation IDs, structured metadata-only logs, and pool controls exist;
- atomic local bootstrap and production operations runbook exist.

Remaining readiness is **PARTIAL/DEFERRED**, not a code-gate blocker: live PostgreSQL migration/restore drills, durable object storage, external monitoring/error tracking, managed TLS/DNS, UAT sign-off, approved retention/RPO/RTO policies, Meta activation, and external AI activation require selected infrastructure, company policy, credentials, or explicit approval.

## Priority

1. **Critical**: none remaining in repository-controlled scope.
2. **High**: none remaining in repository-controlled scope.
3. **Medium**: dependency scanning policy, audit retention approval, durable storage adapter, staging promotion and UAT evidence.
4. **Deferred approval-bound**: real deployment, TLS/DNS, managed database/object storage, monitoring/error-tracking vendors, paid AI, and Meta WhatsApp activation.