# Data Model: Document Intelligence & Financial Document Intake

## Document

Existing evidence aggregate extended in migration `008_document_intelligence`.

| Field | Type | Rules |
|---|---|---|
| id / organization_id | UUID | PK / required tenant FK |
| document_code | varchar(50) | `DOC-YYYY-NNNNNN`, unique per organization |
| original_filename | varchar(255) | Display metadata; never storage name |
| mime_type / file_size_bytes | varchar / bigint | Content-verified allowlist; 1..26,214,400 |
| file_hash_sha256 | char(64) | Lowercase hex; unique per organization |
| storage_path | varchar(500) | Generated relative tenant path |
| source_channel / sender_metadata | enum / JSON | `WEB`, `API`; optional channel metadata |
| document_type | enum | 21 approved types plus `UNKNOWN` |
| processing_status | enum | State machine below |
| provider_name/version | varchar | Nullable until extraction |
| processing_attempts | integer | Non-negative |
| extracted_data | JSON | Validated `StructuredExtraction` |
| matching_results | JSON | Validated `MatchingResult` |
| confidence_scores | JSON | Five Decimal values in [0,1] |
| candidate_transaction | JSON | Validated proposal; never journal instructions |
| review_flags | JSON array | Approved flags; unresolved blocks approval |
| failure_code/message | varchar/text | Safe failure details |
| uploaded_by / timestamps | UUID / timestamptz | Actor and lifecycle timestamps |

Existing `file_name`, `file_hash`, `source_metadata`, and `raw_extraction` data are migrated/bridged without changing stored files.

## StructuredExtraction

Strict provider-neutral JSON. Money serializes as decimal strings. It contains nullable document/invoice/SPK/BAST numbers, transaction/due dates, issuer/recipient, description, ISO currency, subtotal/discount/PPN/PPh/admin fee/total, bank/account/transfer details, project reference, ordered line items, optional diagnostic raw text, and page/region/source/confidence evidence per field. Missing evidence remains null and extra provider fields are rejected.

## ConfidenceScores

`ocr_confidence`, `document_type_confidence`, `entity_confidence`, `project_confidence`, and `amount_confidence` are Decimal 0..1. Any required critical dimension below 0.85 adds `OCR_LOW_CONFIDENCE`; high confidence never overrides missing evidence or ambiguity.

## MatchingResult

Contains nullable tenant-scoped counterparty/project/payment-account/related-document IDs, methods (`EXACT_ID`, `EXACT_NAME`, `FUZZY`, `NONE`), ranked alternatives, and suspected duplicate document/transaction IDs.

## TransactionCandidate

Contains stable id, document/organization IDs, nullable proposed `TransactionType`, matched IDs, cost/expense category, dates, Decimal amount/tax/admin fee, currency, description/reference, and status (`PROPOSED`, `REVIEW_REQUIRED`, `READY_FOR_APPROVAL`, `CONVERTED`). It may reference one converted transaction exactly once. Debit, credit, journal, and posting instructions are forbidden.

## DocumentCorrection

Append-only record: UUID, tenant/document FKs, allowlisted field path, JSON old/new values, required reason, authenticated actor, and timestamp. It never alters source bytes and also emits existing `AuditLog` evidence.

## State Transitions

```text
UPLOADED -> HASHED -> EXTRACTING -> EXTRACTED -> MATCHING
MATCHING -> REVIEW_REQUIRED | READY_FOR_APPROVAL
REVIEW_REQUIRED -> REVIEW_REQUIRED | READY_FOR_APPROVAL
READY_FOR_APPROVAL -> PROCESSED
UPLOADED|HASHED|EXTRACTING|EXTRACTED|MATCHING -> FAILED
FAILED -> EXTRACTING (explicit idempotent retry)
```

Invalid transitions fail. `PROCESSED` is terminal; later financial corrections use reversal/correction.

## Relationships

- Organization 1:N Document and DocumentCorrection.
- Document N:M Project and N:M Transaction through existing link tables.
- Document 1:N DocumentCorrection and 0..1 active TransactionCandidate.
- Every match and relationship requires identical `organization_id`.
