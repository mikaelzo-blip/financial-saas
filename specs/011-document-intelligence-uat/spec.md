# UAT #11 Specification: Document Intelligence Intake Foundation

**Branch**: `hermes/uat-11-document-intelligence-intake`  
**Baseline**: origin/main after verified UAT #10  
**Status**: Active

## Scope

Extend the existing Feature 005 document aggregate and pipeline. Web and future WhatsApp media must enter one normalized `DocumentService` intake. Manual browser upload remains permanent. Real WhatsApp transport, paid AI providers, multi-currency accounting, and automatic master-data creation are out of scope.

## Requirements

- **U11-FR-001** Preserve one immutable tenant-scoped source document per SHA-256 hash with uploader, original filename, verified MIME, size, timestamp, source channel (`WEB` or dormant `WHATSAPP`), storage reference, and processing status.
- **U11-FR-002** Reject empty, oversized, unsupported, signature-mismatched, extension-mismatched, malformed/corrupt, unsafe-path, and cross-tenant inputs without replacing existing storage or data.
- **U11-FR-003** Classify payment proof, purchase receipt, vendor invoice, customer invoice, PO, SPK/contract, BAST, Surat Jalan, tax invoice, and other evidence through a provider-neutral result containing type, confidence, signals/reasons, and `needs_review`.
- **U11-FR-004** Represent extracted values as strict typed candidates with value, confidence, evidence location, and validation status. Missing values remain null.
- **U11-FR-005** Parse money with `Decimal`. Support `Rp 1.250.000`, `1.250.000,00`, and `1,250,000.00`; ambiguous separators are not authoritative.
- **U11-FR-006** Parse ISO, `DD/MM/YYYY`, and `DD-MM-YYYY`; ambiguous day/month dates require review.
- **U11-FR-007** Match only tenant-owned active customers, vendors, projects, invoices/bills, and payment accounts. Unknown evidence creates review flags; it never creates master data.
- **U11-FR-008** Transfer evidence may propose `CUSTOMER_PAYMENT` or `PAY_VENDOR_BILL`; purchase evidence may propose `DIRECT_PURCHASE` or `VENDOR_BILL`. Every proposal requires human review.
- **U11-FR-009** The document Review Queue shows original evidence, classification, fields, confidence, matches, unknowns, warnings, and candidate. Reviewer actions are approve, edit then approve, and reject.
- **U11-FR-010** Approval invokes existing transaction, payment-allocation, and accounting services exactly once. Rejection creates no transaction or journal. Document/provider code never creates journal lines.
- **U11-FR-011** Exact hash replay, future source-message replay, and duplicate approval cannot duplicate documents, transactions, allocations, payments, invoices, or journals.
- **U11-FR-012** Append audit events for receipt, classification, extraction, candidate, edits, reviewer decision, transaction, and journal identifiers. Audit history is never rewritten.
- **U11-FR-013** Every document read, match, correction, rejection, approval, allocation, and posting fails closed across tenants.
- **U11-FR-014** A normalized intake request contract allows Web and future WhatsApp adapters to call the same service; no WhatsApp-specific accounting logic exists.
- **U11-FR-015** Automated verification uses deterministic/scripted providers and no external credentials.

## Accounting invariants

Ingestion, classification, extraction, matching, and review routing cause no journal, cash, AR, AP, revenue, or project-cost change. Only approved validated events may post. Every resulting journal balances; reports preserve Assets = Liabilities + Equity; replay creates no financial duplication.

## Acceptance coverage

The UAT suite covers all 34 scenarios stated in the UAT handoff, including supported/corrupt/duplicate files, classification families, Indonesian money/date ambiguity, known/unknown tenant entities, queue/edit/approve/reject/replay, four transaction conversions, journal/no-journal assertions, audit reconstruction, and tenant isolation.

## Scenario traceability

| UAT scenarios | Automated evidence |
|---|---|
| 1-6 upload, safety, duplicate, tenant access | `test_document_upload.py`, `test_document_file_safety_uat11.py` |
| 7-11 classification families and ambiguity | `test_document_intake_uat11.py` |
| 12-14 Decimal and date normalization | `test_document_intake_uat11.py` |
| 15-20 tenant-scoped unknown/matched entities | `test_document_intelligence.py`, `test_document_intelligence_review.py` |
| 21-26 queue, edit, approve, reject, replay | `test_document_review_uat11.py`, `test_document_intelligence_review.py` |
| 27-30 payment/purchase conversion | candidate tests plus existing customer-payment, vendor-payment, direct-purchase, and vendor-bill integration suites; document approval delegates to those authoritative services |
| 31-32 balanced approval and no journal on rejection | `test_document_intelligence_review.py`, `test_document_review_uat11.py` |
| 33 audit trail | receipt, correction, approval, rejection assertions in UAT #11 integration suites |
| 34 tenant isolation | upload, queue, correction, and rejection cross-tenant assertions |

No test or migration resets, recreates, reseeds, or replaces the PostgreSQL UAT database.
