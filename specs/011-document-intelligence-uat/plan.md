# UAT #11 Implementation Plan

## Architecture decision

Reuse `Document`, `DocumentService`, `StorageService`, `DocumentPipeline`, provider protocol, document review workspace, `TransactionService`, `AccountingEngine`, AR/AP services, and audit service. Add only missing contracts and durable review state. No duplicate document, review, payment, or accounting subsystem.

## Vertical slices

1. Harden normalized file intake and channel contract.
2. Add strict field candidates plus deterministic amount/date parsing and classification signals.
3. Expand tenant/role-aware matching and candidate intent while forcing review.
4. Centralize document review actions; add append-only rejection and lifecycle audit.
5. Convert approved candidates through existing transaction/accounting/allocation services with idempotency.
6. Extend review UI and run all repository gates.

## Constitution check

PASS: Single Input, source traceability, duplicate prevention, human ambiguity review, deterministic accounting, cash-is-not-expense, immutable posting, audit, API boundary, modularity, confidentiality, tenant isolation, and testability. No open accounting, tax, foreign-exchange, capitalization, revenue-recognition, or materiality policy is introduced.
