# Implementation Plan: Production Readiness Foundation

## Constitution Check

PASS. Authentication and operations hardening do not alter accounting rules. All financial mutations remain behind the deterministic backend, review/approval controls, immutable posted-record rules, and tenant-scoped APIs.

## Minimal delivery plan

1. Add fail-closed environment validation and configurable PostgreSQL pool controls.
2. Add a shared JWT principal dependency and authenticated login endpoint; apply it to general SaaS routers while preserving machine/webhook boundaries.
3. Remove frontend mock-login fallback and add failure tests.
4. Add security/correlation middleware and database readiness probe.
5. Add an atomic bootstrap CLI for organization, initial admin, COA, and default payment accounts.
6. Add operator runbooks and update the production-readiness audit/status.
7. Run full tests, dependency checks, migration validation, frontend gates, repository safety, and final consistency analysis.

## Architecture decisions

- Use existing FastAPI, SQLAlchemy, JWT, bcrypt, logging, and CLI-capable stdlib. No new dependencies.
- Keep bearer authentication rather than introducing cookies; CSRF remains not applicable.
- Keep liveness database-independent. Readiness performs `SELECT 1` through the configured engine.
- Add auth at router composition for all general application routers. Exclude `/auth`, public WhatsApp webhook, and machine Hermes/WhatsApp-state boundaries, which enforce their own authentication.
- Keep structured logs minimal: method, route path, status, duration, correlation ID. Never log query strings, request/response bodies, auth headers, or user-provided financial data.
- Bootstrap remains a local operator CLI, not a public endpoint.
