<!--
Sync Impact Report
- Version: Uninitialized -> 1.0.0
- Modified Principles: N/A (Initial ratification)
- Added Sections:
  - Core Accounting & Domain Principles (Principles I–XVI)
  - System Architecture & Integration Invariants (Principles XVII–XXII)
  - Security, Quality & Governance Invariants (Principles XXIII–XXV)
  - Governance & Enforcement
- Removed Sections: Template placeholders
- Deferred Items: None
-->

# Financial SaaS Constitution

## Core Principles

### I. Single Input
A business event MUST be captured exactly once. Users and external systems MUST NEVER manually duplicate the same financial fact into transactions, receivables, payables, project cost, general ledger journals, or reports. All downstream records MUST be derived automatically from the authoritative single entry upon posting.

### II. Project-Based Accounting
`Project_ID` is the primary analytical dimension for project-related transactions. The system MUST track project revenue, costs, profitability, billing status, collection status, and project cash positions using the project dimension without requiring fragmented, duplicate Chart of Accounts (COA) accounts for individual projects.

### III. Simple User Experience
Normal operational users MUST NOT be required to manually select debit and credit accounts. The user experience for daily transaction entry, document submission, and operational review MUST remain accessible to non-accountants, while preserving strict accounting rigor beneath the surface.

### IV. Double-Entry Accounting
Internally, all posted financial transactions MUST generate deterministic double-entry accounting records. Every posted journal entry MUST satisfy the fundamental invariant:
```text
Total Debit = Total Credit
```
Posting MUST be strictly blocked if this invariant is not satisfied.

### V. Deterministic Accounting Engine
The combination of `Transaction_Type` and approved transaction allocations MUST deterministically dictate the applicable accounting rules. Neither AI agents nor human operators may freely invent or assign ad-hoc debit/credit accounts for standard operational transactions.

### VI. Cash Movement is Not Expense
The physical or electronic movement of money MUST NEVER automatically be classified as revenue or expense. The accounting treatment MUST reflect the true economic substance of the transaction (e.g., settling payables, funding advances, executing interbank transfers, capital expenditure, or direct purchasing).

### VII. Source Document Traceability
All posted financial transactions MUST retain traceable links to their source evidentiary documents where applicable. Raw source documents (e.g., invoices, receipts, transfer slips, bank statements) MUST be stored immutably and MUST NOT be silently modified or deleted.

### VIII. Duplicate Prevention
The system MUST proactively detect both exact document duplicates (via cryptographic content hashing such as SHA-256) and suspected duplicate business transactions (matching date, amount, counterparty, and payment account). A suspected duplicate MUST NOT silently create an additional posted financial record.

### IX. Human Review for Ambiguity
Any financial event that is ambiguous, conflicting, low-confidence, sensitive, or materially uncertain MUST be routed to a Review Queue. The system and automated agents MUST NOT silently guess critical financial classifications, project allocations, or counterparties.

### X. Immutable Posted Records
Posted financial transactions and their resulting journal entries MUST NOT be destructively edited or deleted. Corrections MUST strictly follow the audit-compliant correction lifecycle:
```text
Original Transaction → Reversal Transaction → Correcting Transaction
```

### XI. Audit Trail
All business-critical financial, administrative, and configuration changes MUST remain fully reconstructable. The system MUST record who performed an action, when it occurred, what data was altered (including old and new values for state changes), and the reason for adjustments or reversals.

### XII. Derived Financial Balances
Accounts Receivable (AR), Accounts Payable (AP), Project Costs, account balances, and financial statements MUST be derived from authoritative transactions, allocations, and journals. The system MUST NOT rely on manually entered or independently maintained balance totals.

### XIII. Financial Report Integrity
All financial reports (Balance Sheet, Profit and Loss, Cash Flow, Trial Balance, General Ledger) MUST originate directly from posted accounting data. If the balance sheet equation:
```text
Assets = Liabilities + Equity
```
fails to balance, the system MUST halt report finalization and flag an integrity error. The system MUST NEVER insert synthetic balancing adjustments.

### XIV. Separation of Economic Concepts
The system MUST maintain distinct and uncoupled records for:
- Contract Value
- Revenue Recognized
- Invoice Issued (Billed)
- Cash Received (Collected)

Likewise, Project Profitability (accrual basis) and Project Cash Position (cash basis) MUST remain independent analytical concepts.

### XV. Accounting and Tax Separation
Accounting treatment and tax treatment MUST remain separate concerns. Tax rules, rates, and classification codes MUST NOT be hard-coded into the core accounting engine schema, ensuring adaptability to changing tax regulations.

### XVI. Open Policy Protection
The system MUST NOT invent or assume unresolved company accounting policies. Areas designated as open policy (including formal revenue recognition timing, asset capitalization thresholds, depreciation schedules, inventory valuation, owner draw treatments, fiscal cutoff, and materiality thresholds) MUST remain configurable and explicitly governed.

### XVII. Review Before Automation
Automation and AI agents MAY extract, match, classify, calculate, and recommend transactions. However, automation MUST NOT bypass validation checks or required human approvals for transactions flagged for review or categorized as sensitive.

### XVIII. API Boundary
The Financial SaaS backend is the sole authoritative system of record. External agents, integrations, and ingest channels (including WhatsApp or AI orchestration tools) MUST interact exclusively through authenticated, validated application APIs. Direct writes to the production database from external agents are strictly prohibited.

### XIX. Hermes Role
Hermes acts solely as an operational automation and orchestration agent (e.g., WhatsApp intake, document extraction, candidate staging, notification routing). Hermes is NOT the accounting engine, does NOT maintain an independent ledger, and MUST submit candidate records through the SaaS API for validation and posting.

### XX. Development Responsibility
Antigravity (AGY) is the primary software development and execution agent. Spec Kit specifications, architectural plans, tasks, and this constitution govern all implementation activities.

### XXI. Transactional Database as System of Record
The SaaS relational/transactional database is the authoritative system of record. Spreadsheets and Excel files are NOT the primary database; they serve exclusively as formats for import, export, reconciliation, offline analysis, and management reporting.

### XXII. Modular Architecture
Domain boundaries—including Accounting, Projects, Documents, AR/AP, Reporting, Authentication, Integrations, and AI Automation—MUST remain decoupled. Changes to integration channels or AI tooling MUST NOT compromise core accounting engine integrity.

### XXIII. Security & Confidentiality
Financial data and business documents are strictly confidential. The system MUST enforce authentication, role-based authorization, input validation, secure secret management, least-privilege access, and tenant data isolation.

### XXIV. Testability & Verification
All critical financial invariants and rules MUST be guarded by automated tests. Mandatory test suites include:
- Journal debit/credit balancing
- Accounting rule determinism and mapping
- Duplicate detection mechanisms
- Multi-project split allocations
- Reversal and correction workflows
- AR/AP balance consistency and partial settlement
- Project cost aggregation and profitability metrics

### XXV. Incremental Implementation
System implementation MUST proceed in small, verifiable, dependency-ordered stages governed by Spec Kit workflows (`specify` → `clarify` → `plan` → `tasks` → `implement`). AGY MUST NOT attempt monolithic, unrestricted implementation passes.

---

## Governance

1. **Supremacy**: This Constitution represents the highest-priority architectural and operational invariant. Any specification, design plan, task list, or code change that violates these principles is non-compliant and MUST be rejected.
2. **Amendments**: Modifications to this Constitution require explicit rationale, formal documentation, and a semantic version update:
   - **MAJOR**: Structural removal or backward-incompatible redefinition of core principles.
   - **MINOR**: Addition of new principles or material expansion of governance scope.
   - **PATCH**: Clarifications, non-semantic wording enhancements, and typographical corrections.
3. **Compliance Verification**: All Spec Kit plans (`/speckit-plan`), task breakdowns (`/speckit-tasks`), and implementations (`/speckit-implement`) MUST explicitly verify compliance with this constitution before proceeding.

**Version**: 1.0.0 | **Ratified**: 2026-08-29 | **Last Amended**: 2026-08-29
