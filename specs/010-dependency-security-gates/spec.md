# Feature Specification: Dependency Security Gates

**Feature Branch**: `hermes/010-dependency-security-gates`

**Status**: SPECIFIED & CLARIFIED

## Purpose

Close the remaining repository-controlled dependency-security gap identified by the production-readiness audit. CI must audit the exact locked production dependency sets and fail on known vulnerabilities without weakening existing quality gates.

## Clarifications

- Backend audit input is exported from committed `uv.lock`; frontend audit uses committed `package-lock.json`.
- Audit tools are pinned in CI. Generated audit input is temporary and not committed.
- Known vulnerable dependencies must be upgraded or replaced. Vulnerability ignore flags require a separate documented risk-acceptance decision and are not permitted in this feature.
- Development-only frontend vulnerabilities are reported by the full audit; production dependency vulnerabilities block at high severity or above.
- This feature changes no accounting, posting, approval, reporting, document, AI, or WhatsApp behavior.

## Requirements

- **FR-001**: Backend CI MUST export locked production requirements and run pinned `pip-audit` in strict mode.
- **FR-002**: Frontend CI MUST run `npm audit --omit=dev --audit-level=high` against the committed lockfile.
- **FR-003**: The backend locked production graph MUST contain zero known vulnerabilities at verification time.
- **FR-004**: The frontend production graph MUST contain zero high/critical known vulnerabilities at verification time.
- **FR-005**: Existing tests, dependency validation, migration validation, lint, typecheck, build, and repository safety MUST remain unchanged and passing.
- **FR-006**: Security-gate commands and remediation evidence MUST be documented for local reproduction.

## Success Criteria

- Backend locked audit exits 0 with no known vulnerabilities.
- Frontend production audit exits 0 with no high/critical vulnerabilities.
- GitHub Quality Gates expose and pass the dependency audits.
- Existing JWT authentication behavior and full application test suites remain passing.
- Final analysis reports 0 Critical, 0 High, and 100% requirement coverage.
