# Financial SaaS Agent Instructions

## Authority Order

For every change, resolve requirements in this order:

1. `.specify/memory/constitution.md`
2. `docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md`
3. Active feature `spec.md` under `specs/`
4. Approved clarifications
5. `plan.md`
6. `data-model.md`
7. `contracts/`
8. `tasks.md`
9. Completed feature specifications and existing implementation

Preserve all approved business, accounting, audit, security, and tenancy decisions. Do not invent unresolved accounting, tax, revenue-recognition, capitalization, cutoff, materiality, depreciation, inventory, or owner-transaction policies.

## Responsibilities

- Spec Kit owns specification, clarification, technical planning, task generation, and consistency analysis.
- Codex is the primary software engineering and execution agent: implementation, migrations, tests, debugging, builds, validation, and local git checkpoints.
- Hermes is a future operational automation/orchestration client. It is not the development agent or accounting engine and must use authenticated SaaS APIs.

## Required Workflow

For the active feature, continue from actual repository state and run the applicable lifecycle without manual prompt handoffs:

`speckit-clarify -> speckit-plan -> speckit-tasks -> speckit-analyze -> speckit-implement -> final speckit-analyze`

Resolve clarifications from authoritative artifacts when already implied. Stop for user input only when a genuinely new business policy or external credential/resource is required.

Use controlled implementation batches with hard verification checkpoints. Diagnose and fix failures before continuing. Do not weaken tests to make them pass.

## Financial and Document Invariants

- Single Input: one business event is entered once; AR, AP, project cost, journals, balances, and statements are derived.
- Cash movement is not automatically revenue or expense.
- AI may propose classifications and matches but may not choose debit/credit or bypass validation and approval.
- `TransactionType` plus deterministic backend accounting rules remain authoritative.
- Every posted journal has total debit equal to total credit.
- Financial statements must preserve Assets = Liabilities + Equity without synthetic balancing entries.
- Posted financial transactions are immutable; corrections use Original -> Reversal -> Correcting Transaction.
- Use exact Decimal/NUMERIC values for authoritative money calculations, never binary float.
- AR/AP derive from source records and allocations. Project cost derives from posted project dimensions.
- Project Profitability and Project Cash Position remain distinct.
- Contract Value, Revenue Recognized, Invoice Issued, and Cash Received remain distinct.
- Original source documents are immutable and tenant-isolated.
- Use cryptographic file hashes for exact duplicate detection.
- Extraction output must be structured, schema-validated, evidence-grounded, and provider-agnostic.
- Missing or uncertain critical fields, unknown projects, and unknown counterparties route to Review Queue with the appropriate flags.
- Transfer proof alone must never automatically become an expense.

## Safety and Delivery Gates

Do not modify production databases, deploy or push externally, expose secrets, commit `.env`, delete financial history, perform destructive migrations without explicit approval, create paid resources, or expand into unrelated features.

Local development commands, dependency installation, non-destructive migrations, tests, lint, type checks, builds, debugging, and local git commits are allowed when in scope.

Before feature completion require:

- all relevant tests passing;
- dependency checks passing;
- lint and type checks passing;
- frontend build passing when applicable;
- PostgreSQL migrations valid when applicable;
- zero Constitution violations;
- zero Critical or High consistency issues;
- 100% Spec Kit requirement coverage.


## Autonomous Git Workflow

Codex may autonomously:

- inspect git status and diff
- create local commits
- push the current `codex/*` feature branch to origin
- create multiple checkpoint commits while implementing a feature

Codex must only auto-push after the relevant checkpoint passes its required:
- tests
- lint
- type checks
- builds
- migration validation where applicable

Codex MUST NOT autonomously:

- push directly to `main`
- force-push
- rewrite published Git history
- delete remote branches
- merge into `main`
- create or merge production releases
- modify GitHub repository security/settings
- publish secrets
- deploy to production

If the current branch is `main`, create or switch to an appropriate
`codex/<feature-name>` branch before autonomous implementation.

Use concise checkpoint commits.

Examples:

feat(document-intelligence): add document intake pipeline
test(document-intelligence): cover duplicate detection
fix(document-intelligence): enforce confidence review gating

Push verified checkpoint commits automatically to the current `codex/*`
branch without asking the user each time.
