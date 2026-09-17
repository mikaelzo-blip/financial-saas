# Project Status

- **Last reconciled**: 2026-09-17
- **Current branch**: `hermes/whatsapp-lid-ocr-fix`
- **Main commit**: `fc149acde429925b7764bf25eea6248cbdfa2468` (`origin/main`, local ref)
- **Active feature**: Document-type-aware bank transfer extraction & review correction (verified locally). Project lifecycle status transition & error boundary fix committed (`5b2b1b3`).
- **Operating model**: Local-first. Local Baileys intake is supported while the Finance PC services are running; durable PC-off capture remains `DEFERRED_POST_RC1`.
- **Status**: Project lifecycle transition and document-type-aware bank transfer review verified across frontend and backend. Ready for push/PR workflow on `hermes/whatsapp-lid-ocr-fix`.

## Delivered Scope

- Document-type-aware bank transfer extraction & review:
  - Bank transfer proof (`TRANSFER_PROOF`) suppresses spurious goods line items table extraction and rendering.
  - Review form fields are fully editable: Total Nominal is always an editable input field (not fixed or hidden), with manual corrections authoritatively persisted to `total_amount`, candidate `amount`, and `transfer_details.principal`.
  - Form fields adapted: "Referensi Transfer" instead of "Nomor Faktur", transaction/application date instead of invoice/due date.
  - Foreign currency, principal in IDR, admin fees, and settlement/debit total tracked explicitly via `TransferDetails` without synthetic binary-float conversion.
  - Execution status verification (`REQUESTED` vs `EXECUTED`) and execution evidence tracking. Unconfirmed execution (`TRANSFER_EXECUTION_UNCONFIRMED`) and unverified nominal/fee differences (`TRANSFER_AMOUNT_REVIEW`) flag documents for review and block candidate approval fail-closed until reviewed and corrected.
  - Transfer proof approval transitions to `READY_TO_POST`, keeping approval distinct from posting. Bank transfer slips are never automatically assumed to be expenses or vendor advances without contextual matching.
- Project lifecycle transition & frontend crash resilience (`5b2b1b3`):
  - Backend `PATCH /projects/{id}/status` supports both `status` and `project_status` keys.
  - `PATCH /projects/{id}/variation-order` added for project contract adjustments.
  - Frontend project detail page supports complete lifecycle transitions (Aktifkan, Tunda, Selesai, Tutup) with robust error parsing and toast feedback.
  - Added React `ErrorBoundary` and safe `Toast` array/object formatting to prevent unhandled API validation error crashes.
- Canonical `DocumentPostingService` converts approved documents from `READY_TO_POST` to `POSTED` through existing `TransactionService`, `AccountingEngine`, AP, AR, and audit services.
- Authenticated manual posting is available at `POST /documents/{id}/post`.
- Approval remains asynchronous: it transitions to `READY_TO_POST` and only queues `DOCUMENT_POST` for explicit AUTO_SAFE candidates.
- AUTO_SAFE remains limited to `DIRECT_PURCHASE` and `BANK_CHARGE`; processable payment/billing types remain manual-only.
- Migration `028_document_posting_linkage` adds `documents.converted_transaction_id` with a unique index and `ON DELETE RESTRICT` foreign key to `transactions.id`.
- PostgreSQL-backed row locking and durable linkage make conversion/retry/concurrent posting idempotent.
- Fail-closed handling covers malformed candidates, unsupported types, reversals, unresolved review state, and tenant-invalid references.
- Frontend supports the `POSTED` state and displays **Sudah diposting**. Manual posting UX is deferred; the backend endpoint is available.

## Verification

- Backend unit & integration test suites:
  - Transfer document & review contracts: **10 passed** (`test_transfer_document_contract.py`, `test_transfer_review_contract.py`).
  - Project service & REST endpoints: **5 passed** (`test_project_service.py`).
  - Real document extraction UAT: **4 passed** (`test_uat13_real_document_extraction.py`).
  - Document posting & review security invariants: **87 passed** (`test_document_*.py`, `test_slice4_*.py`, `test_slice5_document_posting.py`, `test_fin_p1_102_transaction_type_contract.py`).
  - Backend unit suite: **349 passed**.
- Frontend test suite: **83 passed** across 30 files (`npm run test`).
- Frontend typecheck, lint, and production build: **all passed** (`npm run typecheck && npm run lint && npm run build`).
- Local backend suite (previous baseline): **814 passed, 75 skipped** (`uv run pytest -q --disable-warnings`).

## Delivery Record

- Feature branch commit: `e927908760b89c6d9f8d4283142c8c7e83eeb441`.
- Squash merge commit: `faec99bb40dc2911e2717e3dd7bfede2bf2ff23c`.
- Pull request: [#71](https://github.com/mikaelzo-blip/financial-saas/pull/71) — `MERGED`.

## Next Action

No Slice 6 work has begun. Select the next feature only through the required post-merge discovery and prioritization workflow.
