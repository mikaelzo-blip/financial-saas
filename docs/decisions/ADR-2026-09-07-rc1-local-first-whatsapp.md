# ADR: RC1 Local-First WhatsApp Operating Model

- **Status**: APPROVED
- **Decision date**: 2026-09-07
- **Owner**: Product Owner
- **Scope**: Financial SaaS RC1 and the interim 4–6 month operating period

## Decision

RC1 uses a local-first WhatsApp intake model:

```text
WhatsApp
-> Local Baileys Bridge
-> Financial SaaS
-> Document
-> OCR / Hermes
-> Review Queue
-> Accounting after explicit authorized review
```

The Finance PC, PostgreSQL, backend, background worker, frontend, and local Baileys bridge are expected to be running when WhatsApp documents need to be captured.

Supported behavior:

- **Finance PC ON**: WhatsApp document intake is supported through the local Baileys bridge.
- **Finance PC OFF**: durable WhatsApp capture is not guaranteed.

R1 Durable PC-Off Capture is not an RC1 release blocker. Its release status is `DEFERRED_POST_RC1` because the Owner does not want to purchase or operate a VPS or other external always-on Baileys host during the interim period.

## Owner Experience

The existing one-click Windows startup is the supported entry point. It starts or verifies PostgreSQL, FastAPI, the background worker, the frontend, and—when local WhatsApp is configured—the paired Baileys bridge. It fails closed when the local bridge is unpaired, disconnected, or has no active authorized sender.

Normal Owner-facing guidance is:

> WhatsApp aktif saat sistem keuangan sedang berjalan.

Owner screens must not promise offline capture or expose future infrastructure terminology.

## Preserved Post-RC1 Infrastructure

The following future-ready components remain in the repository but are not activated or required for RC1:

- Cloudflare Worker relay;
- D1 metadata schema;
- R2 media storage adapter;
- `RemoteInboxClient` and remote sync contracts;
- claim/lease and expired-lease recovery logic;
- WAMID idempotency;
- SHA-256 upload/download verification.

These components are classified as **POST-RC1 / FUTURE ALWAYS-ON CAPTURE INFRASTRUCTURE**. They contain no accounting logic and must not be treated as proof that PC-off capture works.

## Explicit Non-Decisions

- No VPS or external always-on Baileys host is required or deployed for RC1.
- No Cloudflare production resources are provisioned for this decision.
- Meta Cloud API remains inactive future-compatibility code.
- The Meta-only relay must not be deployed as the RC1 production path.
- WhatsApp intake, OCR, and Hermes candidate generation do not directly post accounting entries. Accounting remains behind deterministic backend validation and explicit authorized review.

## Consequences

- RC1 operation is simpler and has no new always-on hosting cost.
- Documents sent while the system is stopped may be delayed or lost by the transport; users must send documents while the system is running.
- Future PC-off durability requires a separately approved deployment decision, budget, live external receiver, security review, and end-to-end PC-off UAT.

## Historical Evidence

This decision changes RC1 scope; it does not delete or rewrite earlier implementation or UAT evidence. Earlier emulator, D1/R2, lease, idempotency, and hash-verification results remain evidence for future infrastructure components only, not evidence of live PC-off capture.
