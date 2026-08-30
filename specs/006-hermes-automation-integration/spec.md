# Feature Specification: Hermes Automation Integration

**Feature Branch**: `codex/006-hermes-automation`
**Created**: 2026-08-30
**Status**: Specified

## Executive Summary

Hermes is an operational automation and orchestration client for the Financial SaaS. It submits document and transaction-candidate work through the same authenticated SaaS APIs used by other clients, receives only tenant-scoped responses, and records traceable submission outcomes. Hermes is not an accounting engine, ledger, source of record, or approval authority.

## User Scenarios & Testing

### User Story 1 — Authenticated operational submission (Priority: P1)

An authorized automation operator configures Hermes with an existing SaaS API credential and organization context. Hermes submits an evidentiary document or a structured transaction draft through authenticated APIs and receives the authoritative API response.

**Independent Test**: A mocked authenticated API accepts one valid request; Hermes forwards the organization context, preserves the returned identifier/status, and never accesses database services directly.

### User Story 2 — Safe orchestration and retry (Priority: P1)

When an API request times out or returns a transient failure, Hermes records a non-sensitive failure outcome and retries only idempotent operations using the API idempotency key. It does not create duplicate financial facts.

**Independent Test**: A transient failure followed by success produces one logical submission; a permanent authorization or validation failure is not retried.

### User Story 3 — Review-aware candidate routing (Priority: P2)

Hermes presents the SaaS API’s authoritative review outcome to an operator. A candidate requiring review remains pending; Hermes does not approve, post, or generate debit/credit instructions.

**Independent Test**: A `REVIEW_REQUIRED` response remains review-required and has no posting call; only the regular SaaS review workflow may advance it.

## Functional Requirements

- **FR-001**: Hermes MUST communicate with the Financial SaaS only through authenticated HTTPS SaaS APIs; it MUST NOT open database connections, call repository services, or write database records directly.
- **FR-002**: Hermes MUST use an existing authenticated SaaS principal and tenant context for every request; it MUST NOT embed credentials in source code, logs, or persisted job payloads.
- **FR-003**: Hermes MUST submit document intake and transaction-candidate inputs through the applicable SaaS API contracts and treat API responses as authoritative.
- **FR-004**: Hermes MUST attach a stable idempotency key to retryable submission requests and retain only the minimum submission metadata needed to correlate outcomes.
- **FR-005**: Hermes MUST retry only transient transport/server failures. Authentication, authorization, validation, conflict, and review-required outcomes MUST not be retried as a way to bypass controls.
- **FR-006**: Hermes MAY propose document type, transaction type, project, counterparty, category, and matching context, but MUST NOT create debit/credit lines, journals, AR/AP balances, project-cost balances, or financial statements.
- **FR-007**: Hermes MUST preserve the distinction between document submission, candidate staging, approval, posting, and cash movement; it MUST NOT infer expense from transfer evidence.
- **FR-008**: Hermes MUST surface API review outcomes and unknown/low-confidence/duplicate conditions without auto-approval or auto-posting.
- **FR-009**: Hermes MUST record auditable, tenant-scoped operational outcomes without retaining source-document bytes or secrets outside the SaaS source of record.
- **FR-010**: The integration MUST use a replaceable transport/client boundary so orchestration code remains independent of a particular job runner or future channel.
- **FR-011**: The integration MUST exclude WhatsApp ingestion, WhatsApp credentials, webhooks, message persistence, and provider setup; those belong exclusively to Feature 007.

## Key Entities

- **HermesSubmission**: tenant-scoped correlation record containing submission kind, idempotency key, SaaS resource identifier, state, safe error code, timestamps, and initiating SaaS principal.
- **HermesApiClient**: replaceable authenticated transport boundary that invokes SaaS endpoints and returns validated responses.
- **HermesOrchestrationJob**: in-memory/requested operational work item; it carries no source-document bytes or secrets after API submission.

## Success Criteria

- **SC-001**: 100% of Hermes integration calls in automated tests use the authenticated API-client boundary; no database service is imported by the integration package.
- **SC-002**: 100% of retry tests show a stable idempotency key and no duplicate logical submission.
- **SC-003**: 100% of review-required, authorization, and validation outcomes result in zero approval or posting requests from Hermes.
- **SC-004**: 100% of persisted operational outcomes are tenant-scoped, redact secrets, and correlate to the SaaS API resource identifier.
- **SC-005**: All integration tests run without WhatsApp credentials, paid services, or production SaaS access.

## Assumptions & Dependencies

- Feature 002’s authenticated API and transaction workflow remain authoritative.
- Feature 005’s document-intelligence API contract is a compatible future target, but this feature does not require WhatsApp or provider credentials.
- Hermes is implemented as a replaceable client/orchestration boundary and uses test doubles for SaaS API validation.

## Out of Scope

- WhatsApp integration, webhooks, provider credentials, message storage, or paid messaging services (Feature 007).
- New accounting rules, direct database access, automatic approval, automatic journal posting, or automated resolution of open accounting policies.
