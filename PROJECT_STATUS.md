# Project Status

- **Last reconciled**: 2026-09-13
- **Current branch**: `hermes/fin-p1-102-transaction-type-contract`
- **Base commit**: `befb74a9b60ab746e8ac779accccc151c5552047` (`origin/main` aligned at branch creation)
- **Active feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
- **Active checkpoint**: Specification, architecture, traceability, and checkpoint planning complete; CP1 has not started.
- **Verified baseline**:
  - `TransactionType`: 37 members.
  - `PostingRuleRegistry`: 20 normal executable posting paths.
  - Dedicated special workflow: `REVERSAL` only.
  - Policy-blocked / no executable generic posting path: 16 types.
  - Generic ingestion target: accept 20, reject 17 (16 unsupported + `REVERSAL`).
  - `PETTY_CASH_EXPENSE` is incorrectly AUTO_SAFE in baseline and will be removed in CP3 without inventing accounting policy.
- **Spec Kit**: `specs/fin-p1-102-transaction-type-contract/` contains `spec.md`, `research.md`, `plan.md`, `tasks.md`, `analysis.md`, `data-model.md`, `quickstart.md`, contract, and requirements checklist.
- **Design decision**: `PostingRuleRegistry` will own the canonical normal generic-ingestion capability manifest and validation API; `TransactionService.create_transaction` is the primary pre-sequence/pre-persistence gate; document correction and approval receive targeted protections.
- **Scope boundaries**: No posting rules, no accounting-policy decisions, no migration, no frontend product change, and no historical-row remediation.
- **Design review**: Independent read-only review passed all 16 requested criteria; 0 Critical, 0 High, 0 Medium, 0 Low findings. Source corrections applied: document correction is an API-route boundary, and the dedicated reversal route returns 201 Created.
- **Next action**: Begin FIN-P1-102 CP1 in a new turn: add only the executable characterization and strict-XFAIL RED suite, verify it, commit CP1, then stop.
