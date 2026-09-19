# Bukti Transfer sebagai Biaya Langsung (Jenis Pencatatan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membuat dokumen bukti transfer (`TRANSFER_PROOF`) dapat disetujui sebagai biaya langsung (`DIRECT_PURCHASE`) dengan pilihan Jenis Pencatatan (kategori COA) eksplisit, dilindungi pengaman anti double-count berbasis nomor referensi.

**Architecture:** Dua perubahan backend (longgarkan guard approve + modul guard duplikat baru) dan dua perubahan frontend (picker Jenis Pencatatan + validasi). Saran kategori dari OCR bersifat opsional (saran saja); reviewer memutuskan. Aturan jurnal & double-entry tidak disentuh — `posting_rules.py` sudah mendukung `DIRECT_PURCHASE` (Debit 5101/610x → Kredit 1101).

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy async / Pydantic v2 / pytest + pytest-asyncio; React 18 + TypeScript + Vite + Vitest / React Testing Library; PostgreSQL.

**Spec:** `docs/superpowers/specs/2026-09-19-transfer-proof-direct-expense-design.md`

## Global Constraints

- Balasan/komentar kode & pesan UI dalam bahasa Indonesia (mengikuti basis kode yang ada).
- Aturan jurnal, double-entry, dan alur alokasi **tidak diubah** — hanya menambah jalur eksplisit.
- Pengaman anti double-count **berbasis nomor referensi**, bukan nominal. Nominal mirip tanpa nomor cocok = **boleh**.
- Nomor referensi tidak ketemu = **boleh** (keunikan berkas dijamin `file_hash` + `created_at`).
- Normalisasi nomor memakai `normalize_doc_number` yang sudah ada (`backend/src/services/documents/matching.py:56`).
- Peta kategori → akun: `MAT`/`SUB`/`TRN`/`EQP` → 5101 (wajib proyek); `TRAVEL_OFFICE` → 6104, `OFFICE_ADMIN` → 6103, `OTHER_OPERATIONAL` → 6199 (tanpa proyek).
- Ambang "nominal mirip" = **±1%** (`Decimal`).
- Backend test: `cd backend && python -m pytest <path> -v`. Frontend test: `cd frontend && npx vitest run <path>`.
- Satu commit per task, pesan gaya Conventional Commits (bahasa Inggris, mengikuti riwayat repo).

## Review Focus

Kondisi yang tidak diuji langsung oleh spec tapi paling mungkin menggigit pengguna — tiap baris punya test di task pemiliknya:

1. **Nomor referensi kosong/null di dokumen** → guard tidak boleh crash (`None`/`""` dinormalisasi ke `""` lalu dilewati). Test: Task 4.
2. **Dua bukti transfer berbeda dengan nomor referensi identik** (nomor transfer bank yang sama, tanggal beda) → **tetap boleh** selama `file_hash`/`created_at` berbeda dan tidak ada nomor cocok di sistem. Test: Task 4.
3. **`allocation_target_id` terisi bersamaan dengan kategori** → `DIRECT_PURCHASE` ditolak (ambigu jalur). Test: Task 3.
4. **Kategori 5101 tanpa proyek** → ditolak dengan pesan spesifik, bukan diam-diam jadi 6199. Test: Task 2 & Task 5.
5. **Nominal persis sama tapi nomor referensi beda** → boleh (kebetulan nominal sama, bukan duplikat). Test: Task 4.

---

### Task 1: Modul guard duplikat berbasis nomor referensi (fungsi murni)

**Files:**
- Create: `backend/src/services/documents/expense_duplicate_guard.py`
- Test: `backend/tests/unit/test_expense_duplicate_guard.py`

**Interfaces:**
- Consumes: `normalize_doc_number` dari `backend/src/services/documents/matching.py:56`; `ReviewFlag.DUPLICATE_SUSPECTED` dari `backend/src/models/enums.py:48`.
- Produces:
  - `collect_reference_numbers(candidate: dict, extracted: dict) -> set[str]` — kumpulkan & normalisasi semua nomor (`transfer_reference`, `invoice_number`, `document_number`, `external_reference`), buang yang kosong.
  - `@dataclass DuplicateVerdict(duplicate: bool, flagged: bool, reason: str | None, matched_reference: str | None, matched_code: str | None)`
  - `evaluate_reference_duplicate(references: set[str], amount: Decimal, existing: list[tuple[str, Decimal]]) -> DuplicateVerdict` — `existing` = daftar `(kode_tercatat, nominal_tercatat)`.
  - `AMOUNT_TOLERANCE = Decimal("0.01")` (±1%).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_expense_duplicate_guard.py
from decimal import Decimal

from src.services.documents.expense_duplicate_guard import (
    DuplicateVerdict,
    collect_reference_numbers,
    evaluate_reference_duplicate,
)


def test_collect_reference_numbers_normalizes_and_dedupes():
    candidate = {"external_reference": "2070-8003-319"}
    extracted = {
        "transfer_reference": "20708003319",
        "invoice_number": "20708003319",
        "document_number": None,
    }
    refs = collect_reference_numbers(candidate, extracted)
    assert refs == {"20708003319"}


def test_collect_reference_numbers_empty_when_all_blank():
    assert collect_reference_numbers({}, {"invoice_number": "", "transfer_reference": None}) == set()


def test_matching_reference_and_similar_amount_is_duplicate():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("48930988.86"), [("BILL-001", Decimal("48930988.86"))]
    )
    assert isinstance(verdict, DuplicateVerdict)
    assert verdict.duplicate is True
    assert verdict.flagged is False
    assert verdict.matched_code == "BILL-001"


def test_matching_reference_but_far_amount_is_flagged_not_rejected():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("1000000.00"), [("BILL-001", Decimal("48930988.86"))]
    )
    assert verdict.duplicate is False
    assert verdict.flagged is True


def test_similar_amount_without_matching_reference_is_allowed():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("48930988.86"), [("BILL-999", Decimal("48930988.86"))]
    )
    assert verdict.duplicate is False
    assert verdict.flagged is False


def test_no_reference_match_at_all_is_allowed():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("48930988.86"), [("BILL-999", Decimal("1.00"))]
    )
    assert verdict.duplicate is False
    assert verdict.flagged is False


def test_empty_references_never_duplicate():
    verdict = evaluate_reference_duplicate(set(), Decimal("48930988.86"), [("BILL-001", Decimal("48930988.86"))])
    assert verdict.duplicate is False
    assert verdict.flagged is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_expense_duplicate_guard.py -v`
Expected: FAIL dengan `ModuleNotFoundError: No module named 'src.services.documents.expense_duplicate_guard'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/documents/expense_duplicate_guard.py
"""Anti double-count guard for transfer proofs recorded as direct expenses.

Reference-number based (NOT amount based): an identical normalized reference
number combined with a similar amount is a duplicate. A similar amount with no
matching reference is allowed -- two different transactions may coincidentally
share an amount. File uniqueness is guaranteed by Document.file_hash + created_at.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping, Optional, Sequence

from src.services.documents.matching import normalize_doc_number

AMOUNT_TOLERANCE = Decimal("0.01")  # +/-1%


@dataclass
class DuplicateVerdict:
    duplicate: bool
    flagged: bool
    reason: Optional[str] = None
    matched_reference: Optional[str] = None
    matched_code: Optional[str] = None


def collect_reference_numbers(
    candidate: Mapping[str, object], extracted: Mapping[str, object]
) -> set[str]:
    """Collect and normalize every reference number on the document.

    Sources are intentionally broad (transfer reference, invoice number,
    document number, external reference) because OCR currently copies the bank
    transfer reference into several fields.
    """
    raw_values = [
        extracted.get("transfer_reference"),
        extracted.get("invoice_number"),
        extracted.get("document_number"),
        candidate.get("external_reference"),
        candidate.get("invoice_number"),
    ]
    refs: set[str] = set()
    for value in raw_values:
        normalized = normalize_doc_number(str(value)) if value not in (None, "") else ""
        if normalized:
            refs.add(normalized)
    return refs


def _amounts_similar(a: Decimal, b: Decimal) -> bool:
    if a <= 0 or b <= 0:
        return False
    base = max(a, b)
    return abs(a - b) <= base * AMOUNT_TOLERANCE


def evaluate_reference_duplicate(
    references: set[str],
    amount: Decimal,
    existing: Sequence[tuple[str, Decimal]],
) -> DuplicateVerdict:
    """Compare document references against already-recorded (code, amount) pairs."""
    if not references:
        return DuplicateVerdict(duplicate=False, flagged=False)

    for code, recorded_amount in existing:
        code_norm = normalize_doc_number(str(code)) if code else ""
        if not code_norm or code_norm not in references:
            continue
        if _amounts_similar(Decimal(str(amount)), Decimal(str(recorded_amount))):
            return DuplicateVerdict(
                duplicate=True,
                flagged=False,
                reason=f"Reference {code_norm} already recorded as {code}; possible duplicate",
                matched_reference=code_norm,
                matched_code=code,
            )
        return DuplicateVerdict(
            duplicate=False,
            flagged=True,
            reason=f"Reference {code_norm} matches {code} but amount differs; review required",
            matched_reference=code_norm,
            matched_code=code,
        )

    return DuplicateVerdict(duplicate=False, flagged=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_expense_duplicate_guard.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/documents/expense_duplicate_guard.py backend/tests/unit/test_expense_duplicate_guard.py
git commit -m "feat(documents): add reference-number duplicate guard for direct expenses"
```

---

### Task 2: Longgarkan guard approve untuk TRANSFER_PROOF + DIRECT_PURCHASE

**Files:**
- Modify: `backend/src/api/v1/documents.py:39-49` (`is_candidate_ready_for_approval`)
- Modify: `backend/src/api/v1/documents.py:475-484` (guard `TRANSFER_PROOF`)
- Test: `backend/tests/integration/test_transfer_proof_direct_expense.py`

**Interfaces:**
- Consumes: `TransactionType`, `DocumentType`, `CostCategory`, `ExpenseCategory` dari `backend/src/models/enums.py`; `TransactionCandidate` dari `backend/src/schemas/document.py:76`.
- Produces: perilaku baru `is_candidate_ready_for_approval` untuk `DIRECT_PURCHASE`:
  - `payment_account_id` wajib;
  - kategori proyek (`cost_category` in `{MAT,SUB,TRN,EQP}`) → `project_id` wajib;
  - kategori operasional (`expense_category`) → `project_id` tidak wajib.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_transfer_proof_direct_expense.py
import io
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.document import Document, DocumentProcessingStatus, DocumentType
from src.models.enums import CostCategory, UserRole
from src.models.organization import Organization
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa
from src.services.document_service import DocumentService

pytestmark = pytest.mark.asyncio


async def _org_user_account(db_session):
    org = Organization(slug="tp-direct", legal_name="Transfer Proof Direct Org")
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org.id)
    manager = User(
        organization_id=org.id,
        email="tp-approver@test.local",
        full_name="TP Approver",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()
    coa = await db_session.scalar(
        select(ChartOfAccount).where(
            ChartOfAccount.organization_id == org.id,
            ChartOfAccount.account_code == "1101",
        )
    )
    account = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa.id,
        name="Mandiri",
        is_active=True,
    )
    db_session.add(account)
    await db_session.flush()
    return org, manager, account


async def _transfer_proof_doc(db_session, org, manager, candidate_extra: dict):
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\ntransfer-proof"),
        "bukti.pdf",
        "application/pdf",
        DocumentType.TRANSFER_PROOF,
        created_by=manager.id,
    )
    candidate = {
        "id": str(doc.id),
        "amount": "48930988.86",
        "transaction_date": "2026-08-13",
        "status": "READY_FOR_APPROVAL",
        "external_reference": "20708003319",
    }
    candidate.update(candidate_extra)
    doc.candidate_transaction = candidate
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()
    return doc


async def test_transfer_proof_with_category_and_account_is_approved(client: AsyncClient, db_session):
    org, manager, account = await _org_user_account(db_session)
    doc = await _transfer_proof_doc(
        db_session, org, manager,
        {
            "proposed_transaction_type": "DIRECT_PURCHASE",
            "cost_category": CostCategory.MAT.value,
            "payment_account_id": str(account.id),
            "project_id": None,
        },
    )
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["candidate_transaction"]["status"] == "READY_TO_POST"


async def test_transfer_proof_direct_purchase_without_category_is_rejected(client: AsyncClient, db_session):
    org, manager, account = await _org_user_account(db_session)
    doc = await _transfer_proof_doc(
        db_session, org, manager,
        {
            "proposed_transaction_type": "DIRECT_PURCHASE",
            "payment_account_id": str(account.id),
        },
    )
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
    assert "recording category" in resp.json()["detail"].lower()


async def test_transfer_proof_as_vendor_bill_still_rejected(client: AsyncClient, db_session):
    org, manager, account = await _org_user_account(db_session)
    doc = await _transfer_proof_doc(
        db_session, org, manager,
        {
            "proposed_transaction_type": "VENDOR_BILL",
            "payment_account_id": str(account.id),
        },
    )
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/integration/test_transfer_proof_direct_expense.py -v`
Expected: FAIL — test pertama & kedua dapat 422 `"Transfer proof cannot be approved as direct purchase..."` (guard lama masih menolak semua `DIRECT_PURCHASE`).

- [ ] **Step 3: Write minimal implementation**

Ubah `is_candidate_ready_for_approval` (`backend/src/api/v1/documents.py:39-49`) — ganti blok `DIRECT_PURCHASE`:

```python
PROJECT_COST_CATEGORIES = {
    CostCategory.MAT,
    CostCategory.SUB,
    CostCategory.TRN,
    CostCategory.EQP,
}


def is_candidate_ready_for_approval(candidate: TransactionCandidate) -> bool:
    if not candidate.proposed_transaction_type or not candidate.amount or not candidate.transaction_date:
        return False
    t_type = candidate.proposed_transaction_type
    if t_type in {TransactionType.CUSTOMER_PAYMENT, TransactionType.PAY_VENDOR_BILL}:
        return bool(candidate.counterparty_id and candidate.payment_account_id and candidate.allocation_target_id)
    if t_type == TransactionType.DIRECT_PURCHASE:
        if not candidate.payment_account_id:
            return False
        if candidate.cost_category in PROJECT_COST_CATEGORIES:
            return bool(candidate.project_id)
        return bool(candidate.project_id or candidate.expense_category)
    if t_type in {TransactionType.VENDOR_BILL, TransactionType.CUSTOMER_INVOICE}:
        return bool(candidate.counterparty_id and candidate.project_id)
    return True
```

Pastikan `CostCategory` sudah diimpor di berkas ini (tambahkan ke baris import `src.models.enums` bila belum).

Ubah guard `TRANSFER_PROOF` (`backend/src/api/v1/documents.py:475-484`):

```python
    if document.document_type == DocumentType.TRANSFER_PROOF:
        if candidate.proposed_transaction_type in {
            TransactionType.VENDOR_BILL,
            TransactionType.CUSTOMER_INVOICE,
        }:
            raise HTTPException(
                status_code=422,
                detail="Transfer proof cannot be approved as bill or invoice; it must be an allocation payment or an explicit direct expense",
            )
        if candidate.proposed_transaction_type == TransactionType.DIRECT_PURCHASE:
            has_category = bool(candidate.cost_category or candidate.expense_category)
            if not has_category:
                raise HTTPException(
                    status_code=422,
                    detail="Transfer proof as direct expense requires a recording category",
                )
            if candidate.allocation_target_id:
                raise HTTPException(
                    status_code=422,
                    detail="Transfer proof direct expense cannot also carry an allocation target",
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/integration/test_transfer_proof_direct_expense.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/v1/documents.py backend/tests/integration/test_transfer_proof_direct_expense.py
git commit -m "feat(documents): allow transfer proof as explicit direct expense"
```

---

### Task 3: Validasi kategori 5101 tanpa proyek + alokasi ganda

**Files:**
- Modify: `backend/src/api/v1/documents.py` (guard `TRANSFER_PROOF` dari Task 2)
- Test: `backend/tests/integration/test_transfer_proof_direct_expense.py` (tambahkan test)

**Interfaces:**
- Consumes: `PROJECT_COST_CATEGORIES` dari Task 2.
- Produces: dua pesan 422 spesifik:
  - kategori proyek tanpa `project_id` → `"Project is required for project cost categories (5101)"`;
  - `DIRECT_PURCHASE` dengan `allocation_target_id` → `"Transfer proof direct expense cannot also carry an allocation target"`.

- [ ] **Step 1: Write the failing test** (tambahkan ke berkas Task 2)

```python
async def test_transfer_proof_project_category_without_project_is_rejected(client: AsyncClient, db_session):
    org, manager, account = await _org_user_account(db_session)
    doc = await _transfer_proof_doc(
        db_session, org, manager,
        {
            "proposed_transaction_type": "DIRECT_PURCHASE",
            "cost_category": CostCategory.MAT.value,
            "payment_account_id": str(account.id),
            "project_id": None,
        },
    )
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
    assert "project" in resp.json()["detail"].lower()


async def test_transfer_proof_direct_purchase_with_allocation_target_is_rejected(client: AsyncClient, db_session):
    org, manager, account = await _org_user_account(db_session)
    doc = await _transfer_proof_doc(
        db_session, org, manager,
        {
            "proposed_transaction_type": "DIRECT_PURCHASE",
            "expense_category": "OFFICE_ADMIN",
            "payment_account_id": str(account.id),
            "allocation_target_id": str(account.id),
        },
    )
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
    assert "allocation" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/integration/test_transfer_proof_direct_expense.py -v`
Expected: FAIL — kategori 5101 tanpa proyek saat ini lolos lewat `is_candidate_ready_for_approval` yang mengembalikan `False`, tetapi pesan default `"Candidate is missing required fields for approval"` (bukan pesan "project"). Test `allocation` sudah lolos dari Task 2 (guard alokasi) — bila sudah hijau, itu wajar.

- [ ] **Step 3: Write minimal implementation**

Di guard `TRANSFER_PROOF` (setelah blok `has_category`), tambahkan sebelum validasi alokasi:

```python
        if candidate.proposed_transaction_type == TransactionType.DIRECT_PURCHASE:
            has_category = bool(candidate.cost_category or candidate.expense_category)
            if not has_category:
                raise HTTPException(
                    status_code=422,
                    detail="Transfer proof as direct expense requires a recording category",
                )
            if candidate.cost_category in PROJECT_COST_CATEGORIES and not candidate.project_id:
                raise HTTPException(
                    status_code=422,
                    detail="Project is required for project cost categories (5101)",
                )
            if candidate.allocation_target_id:
                raise HTTPException(
                    status_code=422,
                    detail="Transfer proof direct expense cannot also carry an allocation target",
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/integration/test_transfer_proof_direct_expense.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/v1/documents.py backend/tests/integration/test_transfer_proof_direct_expense.py
git commit -m "feat(documents): require project for 5101 categories on transfer proof"
```

---

### Task 4: Sambungkan guard duplikat ke endpoint approve

**Files:**
- Modify: `backend/src/api/v1/documents.py` (endpoint `approve`, sekitar baris 471-524)
- Test: `backend/tests/integration/test_transfer_proof_duplicate_guard.py`

**Interfaces:**
- Consumes: `collect_reference_numbers`, `evaluate_reference_duplicate`, `DuplicateVerdict` dari Task 1; model `VendorBill` (`backend/src/models/payable.py:28`, field `bill_code`, `total_amount`), `CustomerInvoice` (`backend/src/models/receivable.py:28`, field `invoice_code`, `total_amount`), `Transaction` (`backend/src/models/transaction.py:101`, field `reference_no`, `amount`).
- Produces: pemanggilan guard hanya pada jalur `TRANSFER_PROOF` + `DIRECT_PURCHASE`:
  - duplikat → HTTP 422 dengan detail dari `verdict.reason`;
  - flagged → tambahkan `ReviewFlag.DUPLICATE_SUSPECTED.value` ke `document.review_flags` (tidak menolak).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_transfer_proof_duplicate_guard.py
import io
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import DocumentProcessingStatus, DocumentType
from src.models.enums import UserRole
from src.models.organization import Organization
from src.models.payable import VendorBill
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa
from src.services.document_service import DocumentService

pytestmark = pytest.mark.asyncio


async def _setup(db_session, bill_code="BILL-DUP-001", bill_amount="48930988.86"):
    org = Organization(slug="tp-dup", legal_name="TP Dup Org")
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org.id)
    manager = User(
        organization_id=org.id, email="dup@test.local", full_name="Dup",
        password_hash="x", role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()
    coa = await db_session.scalar(
        select(ChartOfAccount).where(
            ChartOfAccount.organization_id == org.id,
            ChartOfAccount.account_code == "1101",
        )
    )
    account = PaymentAccount(
        organization_id=org.id, coa_account_id=coa.id, name="Mandiri", is_active=True,
    )
    db_session.add(account)
    await db_session.flush()
    vendor = Counterparty(organization_id=org.id, name="PT Vendor Dup", is_vendor=True)
    db_session.add(vendor)
    await db_session.flush()
    bill = VendorBill(
        organization_id=org.id,
        bill_code=bill_code,
        vendor_id=vendor.id,
        bill_date=date(2026, 8, 1),
        due_date=date(2026, 9, 1),
        total_amount=Decimal(bill_amount),
    )
    db_session.add(bill)
    await db_session.commit()
    return org, manager, account


async def _doc(db_session, org, manager, account, ref, amount="48930988.86"):
    doc = await DocumentService(db_session).ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\ndup"), "dup.pdf", "application/pdf",
        DocumentType.TRANSFER_PROOF, created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "expense_category": "OTHER_OPERATIONAL",
        "payment_account_id": str(account.id),
        "amount": amount,
        "transaction_date": "2026-08-13",
        "status": "READY_FOR_APPROVAL",
        "external_reference": ref,
    }
    doc.extracted_data = {"transfer_reference": ref, "invoice_number": ref}
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()
    return doc


async def test_matching_reference_and_similar_amount_is_rejected(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session)
    doc = await _doc(db_session, org, manager, account, "20708003319")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
    assert "duplicate" in resp.json()["detail"].lower()


async def test_matching_reference_but_far_amount_is_flagged_not_rejected(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session)
    doc = await _doc(db_session, org, manager, account, "20708003319", amount="1000000.00")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code in (200, 201), resp.text
    assert "DUPLICATE_SUSPECTED" in resp.json()["review_flags"]


async def test_different_reference_with_similar_amount_is_allowed(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session)
    doc = await _doc(db_session, org, manager, account, "99900011122")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code in (200, 201), resp.text


async def test_normalized_reference_variants_are_detected(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session, bill_code="20708003319")
    doc = await _doc(db_session, org, manager, account, "2070-8003-319")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/integration/test_transfer_proof_duplicate_guard.py -v`
Expected: FAIL — `test_matching_reference_and_similar_amount_is_rejected` mengembalikan 200/201 (guard belum dipanggil), bukan 422.

- [ ] **Step 3: Write minimal implementation**

Tambahkan import di `backend/src/api/v1/documents.py`:

```python
from src.services.documents.expense_duplicate_guard import (
    collect_reference_numbers,
    evaluate_reference_duplicate,
)
```

Di endpoint `approve`, tepat **setelah** blok guard `TRANSFER_PROOF` (setelah baris validasi alokasi `TRANSFER_PROOF`) dan sebelum `is_candidate_ready_for_approval`, tambahkan:

```python
    if (
        document.document_type == DocumentType.TRANSFER_PROOF
        and candidate.proposed_transaction_type == TransactionType.DIRECT_PURCHASE
    ):
        references = collect_reference_numbers(
            document.candidate_transaction or {},
            document.extracted_data or {},
        )
        if references:
            existing: list[tuple[str, Decimal]] = []
            bills = (await db.scalars(
                select(VendorBill).where(VendorBill.organization_id == org_id)
            )).all()
            existing.extend((b.bill_code, b.total_amount) for b in bills)
            invoices = (await db.scalars(
                select(CustomerInvoice).where(CustomerInvoice.organization_id == org_id)
            )).all()
            existing.extend((i.invoice_code, i.total_amount) for i in invoices)
            trxs = (await db.scalars(
                select(Transaction).where(
                    Transaction.organization_id == org_id,
                    Transaction.reference_no.isnot(None),
                )
            )).all()
            existing.extend((t.reference_no, t.amount) for t in trxs)

            verdict = evaluate_reference_duplicate(references, candidate.amount, existing)
            if verdict.duplicate:
                raise HTTPException(status_code=422, detail=verdict.reason)
            if verdict.flagged and ReviewFlag.DUPLICATE_SUSPECTED.value not in (document.review_flags or []):
                document.review_flags = [*(document.review_flags or []), ReviewFlag.DUPLICATE_SUSPECTED.value]
```

Pastikan `Decimal`, `ReviewFlag`, `Transaction`, `VendorBill`, `CustomerInvoice`, `select` sudah diimpor di berkas ini (tambahkan yang kurang). Perhatikan: guard `document.review_flags` di baris 457 dijalankan **sebelum** titik ini, jadi menambahkan flag di sini tidak akan memicu penolakan 409.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/integration/test_transfer_proof_duplicate_guard.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/v1/documents.py backend/tests/integration/test_transfer_proof_duplicate_guard.py
git commit -m "feat(documents): wire reference-number duplicate guard into approval"
```

---

### Task 5: Saran kategori OCR di blok TRANSFER_PROOF

**Files:**
- Modify: `backend/src/services/documents/candidate.py:34-41` (blok `if document_type == DocumentType.TRANSFER_PROOF` di `build_candidate`)
- Test: `backend/tests/unit/test_candidate_transfer_proof_suggestion.py`

**Interfaces:**
- Consumes: `classify_expense` dari `backend/src/services/documents/expense_classifier.py` (sudah diimpor di `candidate.py:6`); `build_candidate(document_id: uuid.UUID, document_type: DocumentType, data: StructuredExtraction, matches: dict, flags: list[str]) -> TransactionCandidate | None` (`candidate.py:24`).
- Produces: ketika `document_type == TRANSFER_PROOF` dan tidak ada target alokasi, `matches["expense_classification"]` terisi dan `matches["suggested_cost_category"]`/`matches["suggested_expense_category"]` diisi sebagai **usulan**; `candidate.proposed_transaction_type` tetap `None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_candidate_transfer_proof_suggestion.py
import uuid

from src.models.enums import DocumentType
from src.schemas.document import StructuredExtraction
from src.services.documents.candidate import build_candidate


def test_transfer_proof_without_allocation_suggests_category():
    data = StructuredExtraction(
        raw_text="Pembelian bensin operasional kendaraan kantor",
        description="Pembelian bensin operasional kendaraan kantor",
        issuer_name="PT Pertamina",
        invoice_number="20708003319",
    )
    matches: dict = {}
    result = build_candidate(
        uuid.uuid4(), DocumentType.TRANSFER_PROOF, data, matches, flags=[]
    )
    assert result is not None
    assert result.proposed_transaction_type is None
    assert "expense_classification" in matches
    assert matches.get("suggested_cost_category") or matches.get("suggested_expense_category")
```

Catatan: `StructuredExtraction` hanya butuh field yang dipakai; tambahkan field wajib lain bila validasi Pydantic menuntut (baca `backend/src/schemas/document.py:40-72`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_candidate_transfer_proof_suggestion.py -v`
Expected: FAIL — `matches["expense_classification"]` tidak ada (blok `TRANSFER_PROOF` saat ini hanya menetapkan `proposed`, tidak memanggil `classify_expense`).

- [ ] **Step 3: Write minimal implementation**

Di `backend/src/services/documents/candidate.py`, di dalam blok `if document_type == DocumentType.TRANSFER_PROOF:` (`candidate.py:34-41`), setelah logika `else: proposed = None`, tambahkan saran kategori:

```python
        if proposed is None:
            # Suggestion only: OCR proposes a recording category when no allocation
            # target exists. proposed_transaction_type stays None until the reviewer
            # explicitly confirms DIRECT_PURCHASE in the review form.
            matched_pid = matches.get("project_id")
            if matched_pid and isinstance(matched_pid, str):
                try:
                    matched_pid = uuid.UUID(matched_pid)
                except Exception:
                    pass
            raw_desc = data.description or data.raw_text or ""
            exp_res = classify_expense(
                raw_description=raw_desc,
                caption=(matches.get("source_metadata") or {}).get("caption"),
                matched_project_id=matched_pid,
                vendor_name=data.issuer_name or data.recipient_name,
                document_text=data.raw_text,
                document_project_hint=data.project_reference,
            )
            matches["expense_classification"] = exp_res.to_dict()
            if exp_res.cost_category:
                matches["suggested_cost_category"] = exp_res.cost_category.value
            elif exp_res.expense_category:
                matches["suggested_expense_category"] = exp_res.expense_category.value
```

Pastikan `uuid` dan `DocumentType` tersedia (sudah dipakai di berkas). `exp_res.to_dict()` mengembalikan `cost_category`/`expense_category` sebagai string (lihat `expense_classifier.py:35-47`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_candidate_transfer_proof_suggestion.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/documents/candidate.py backend/tests/unit/test_candidate_transfer_proof_suggestion.py
git commit -m "feat(documents): suggest recording category for transfer proofs"
```

---

### Task 6: Picker "Jenis Pencatatan" di form review (frontend)

**Files:**
- Modify: `frontend/src/components/documents/DocumentReviewForm.tsx` (state + render)
- Modify: `frontend/src/types/api.ts` (tambah konstanta `RECORDING_CATEGORIES`)
- Test: `frontend/tests/components/DocumentReviewForm.transferProof.test.tsx`

**Interfaces:**
- Consumes: `COST_CATEGORIES`, `ExpenseCategory` dari `frontend/src/types/api.ts:75-87`.
- Produces:
  - konstanta `RECORDING_CATEGORIES: { value: string; label: string; costCategory?: CostCategory; expenseCategory?: ExpenseCategory; requiresProject: boolean }[]` di `types/api.ts`.
  - state `recordingCategory` di form; saat berubah → set `cost_category`/`expense_category` + `proposed_transaction_type = 'DIRECT_PURCHASE'`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/components/DocumentReviewForm.transferProof.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';

const baseProps = {
  document: {
    id: 'doc-1',
    document_type: 'TRANSFER_PROOF',
    processing_status: 'READY_FOR_APPROVAL',
    extracted_data: { transfer_reference: '20708003319' },
    matching_results: {},
    review_flags: [],
    candidate_transaction: {
      id: 'doc-1',
      amount: '48930988.86',
      transaction_date: '2026-08-13',
      status: 'READY_FOR_APPROVAL',
    },
  } as never,
  projects: [] as never,
  counterparties: [] as never,
  paymentAccounts: [
    {
      id: 'acc-1',
      organization_id: 'o',
      coa_account_id: 'c',
      coa_account_code: '1101',
      coa_account_name: 'Kas',
      name: 'Mandiri',
      account_type: 'BANK',
      is_active: true,
      created_at: '',
    },
  ] as never,
  onSave: vi.fn().mockResolvedValue(undefined),
  onApprove: vi.fn().mockResolvedValue(undefined),
  onReject: vi.fn().mockResolvedValue(undefined),
};

describe('DocumentReviewForm - transfer proof recording category', () => {
  it('shows the Jenis Pencatatan picker for TRANSFER_PROOF', () => {
    render(<DocumentReviewForm {...baseProps} />);
    expect(screen.getByLabelText(/jenis pencatatan/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/components/DocumentReviewForm.transferProof.test.tsx`
Expected: FAIL — label "Jenis Pencatatan" tidak ditemukan.

- [ ] **Step 3: Write minimal implementation**

Di `frontend/src/types/api.ts` tambahkan:

```ts
export interface RecordingCategoryOption {
  value: string;
  label: string;
  costCategory?: CostCategory;
  expenseCategory?: ExpenseCategory;
  requiresProject: boolean;
}

export const RECORDING_CATEGORIES: RecordingCategoryOption[] = [
  { value: 'MAT', label: 'Beli Barang / Material', costCategory: 'MAT', requiresProject: true },
  { value: 'SUB', label: 'Jasa / Subkontraktor', costCategory: 'SUB', requiresProject: true },
  { value: 'TRN', label: 'Bensin & Transport (proyek)', costCategory: 'TRN', requiresProject: true },
  { value: 'EQP', label: 'Peralatan / Sewa Alat', costCategory: 'EQP', requiresProject: true },
  { value: 'TRAVEL_OFFICE', label: 'Bensin / Kendaraan (kantor)', expenseCategory: 'TRAVEL_OFFICE', requiresProject: false },
  { value: 'OFFICE_ADMIN', label: 'ATK / Operasional Kantor', expenseCategory: 'OFFICE_ADMIN', requiresProject: false },
  { value: 'OTHER_OPERATIONAL', label: 'Lain-lain', expenseCategory: 'OTHER_OPERATIONAL', requiresProject: false },
];
```

Di `DocumentReviewForm.tsx` tambahkan state (dekat baris 107-127):

```tsx
const [recordingCategory, setRecordingCategory] = useState<string>(
  String(
    candidate.cost_category ??
      candidate.expense_category ??
      (document.matching_results?.suggested_cost_category as string | undefined) ??
      (document.matching_results?.suggested_expense_category as string | undefined) ??
      '',
  ),
);
```

Tambahkan turunan & sertakan ke `buildCurrentChanges` (dekat baris 186-230):

```tsx
const selectedRecording = RECORDING_CATEGORIES.find((c) => c.value === recordingCategory);

if (selectedRecording) {
  const nextCost = selectedRecording.costCategory ?? null;
  const nextExpense = selectedRecording.expenseCategory ?? null;
  if (nextCost !== (candidate.cost_category ?? null) || nextExpense !== (candidate.expense_category ?? null)) {
    changes.cost_category = nextCost;
    changes.expense_category = nextExpense;
    changes.proposed_transaction_type = 'DIRECT_PURCHASE';
    isDirty = true;
  }
}
```

Render picker (letakkan dekat blok form TRANSFER_PROOF, sekitar baris 518):

```tsx
{document.document_type === 'TRANSFER_PROOF' && (
  <div className="form-field">
    <label htmlFor="recording-category">
      Jenis Pencatatan {selectedRecording?.requiresProject ? '*' : ''}
    </label>
    <select
      id="recording-category"
      aria-label="Jenis Pencatatan"
      value={recordingCategory}
      onChange={(e) => setRecordingCategory(e.target.value)}
    >
      <option value="">— Pilih jenis pencatatan —</option>
      {RECORDING_CATEGORIES.map((c) => (
        <option key={c.value} value={c.value}>{c.label}</option>
      ))}
    </select>
    <p className="helper-text">Pilih kategori COA laba rugi untuk biaya ini.</p>
  </div>
)}
```

Tambahkan `RECORDING_CATEGORIES` ke import dari `../../types/api`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/components/DocumentReviewForm.transferProof.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/components/documents/DocumentReviewForm.tsx frontend/tests/components/DocumentReviewForm.transferProof.test.tsx
git commit -m "feat(frontend): add recording category picker for transfer proofs"
```

---

### Task 7: Validasi form kategori 5101 tanpa proyek (frontend)

**Files:**
- Modify: `frontend/src/utils/documentReview.ts` (validasi + pesan)
- Test: `frontend/tests/utils/documentReview.recordingCategory.test.ts`

**Interfaces:**
- Consumes: `RECORDING_CATEGORIES` dari Task 6; `validateDocumentReview` yang ada di `documentReview.ts`.
- Produces: pesan galat baru `"Proyek wajib dipilih untuk kategori biaya proyek (5101)."` ketika kategori proyek dipilih tanpa proyek.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/tests/utils/documentReview.recordingCategory.test.ts
import { describe, expect, it } from 'vitest';
import { validateDocumentReviewForm } from '../../src/utils/documentReview';

describe('validateDocumentReviewForm - recording category', () => {
  it('requires project for project cost category', () => {
    const result = validateDocumentReviewForm('DIRECT_PURCHASE', 'TRANSFER_PROOF', {
      paymentAccountId: 'acc-1',
      projectId: '',
      costCategory: 'MAT',
      expenseCategory: '',
    });
    expect(result.isValid).toBe(false);
    expect(result.errorMessage).toMatch(/proyek/i);
  });

  it('allows operational category without project', () => {
    const result = validateDocumentReviewForm('DIRECT_PURCHASE', 'TRANSFER_PROOF', {
      paymentAccountId: 'acc-1',
      projectId: '',
      costCategory: '',
      expenseCategory: 'OFFICE_ADMIN',
    });
    expect(result.isValid).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/utils/documentReview.recordingCategory.test.ts`
Expected: FAIL — kategori proyek tanpa proyek saat ini dianggap valid (atau pesan bukan "proyek").

- [ ] **Step 3: Write minimal implementation**

Di `frontend/src/utils/documentReview.ts`, dalam cabang `else if (transactionType === 'DIRECT_PURCHASE')` (sekitar baris 74-81), setelah blok `hasProject`/`hasCategory`:

```ts
    const PROJECT_COST_CATEGORIES = ['MAT', 'SUB', 'TRN', 'EQP'];
    if (values.costCategory && PROJECT_COST_CATEGORIES.includes(values.costCategory) && !values.projectId?.trim()) {
      missingFields.push('project_id_for_category');
    }
```

Dan tambahkan pesan sebelum pesan default (setelah blok `missingFields.includes('project_id')`):

```ts
  } else if (missingFields.includes('project_id_for_category')) {
    errorMessage = 'Proyek wajib dipilih untuk kategori biaya proyek (5101).';
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/utils/documentReview.recordingCategory.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/documentReview.ts frontend/tests/utils/documentReview.recordingCategory.test.ts
git commit -m "feat(frontend): require project for 5101 recording categories"
```

---

### Task 8: Uji jurnal DIRECT_PURCHASE dari bukti transfer + regresi penuh

**Files:**
- Test: `backend/tests/integration/test_transfer_proof_direct_expense.py` (tambahkan test jurnal)
- Verify: seluruh suite backend & frontend.

**Interfaces:**
- Consumes: `PostingRuleRegistry.generate_journal_legs` (`backend/src/services/posting_rules.py:102`); alur post dari Task 2.
- Produces: bukti bahwa `DIRECT_PURCHASE` dari bukti transfer menghasilkan Debit 5101 (dengan proyek) / 610x (operasional) → Kredit 1101.

- [ ] **Step 1: Write the failing test**

```python
async def test_transfer_proof_direct_expense_generates_correct_journal(db_session):
    from src.models.transaction import Transaction
    from src.models.enums import TransactionType
    from src.services.posting_rules import PostingRuleRegistry

    trx = Transaction(
        organization_id=uuid.uuid4(),
        transaction_code="TRX-TP-1",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 8, 13),
        amount=Decimal("48930988.86"),
        currency="IDR",
        description="Bensin operasional",
        source_channel="WEB",
    )
    trx.allocations = []
    legs = PostingRuleRegistry.generate_journal_legs(trx)
    codes = {(leg.account_code, leg.debit_amount, leg.credit_amount) for leg in legs}
    assert ("5101", Decimal("48930988.86"), Decimal("0.00")) in codes
    assert ("1101", Decimal("0.00"), Decimal("48930988.86")) in codes
```

Tambahkan `import uuid` di bagian atas berkas test.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/integration/test_transfer_proof_direct_expense.py::test_transfer_proof_direct_expense_generates_correct_journal -v`
Expected: FAIL hanya bila `Transaction` butuh field wajib lain (perbaiki konstruksi objek sesuai model). Bila langsung PASS, jurnal sudah benar — lanjut.

- [ ] **Step 3: Fix minimal** (bila gagal)

Lengkapi field `Transaction` yang wajib (mis. `workflow_status`, `created_by`) sesuai `backend/src/models/transaction.py` agar objek valid. Jangan mengubah `posting_rules.py`.

- [ ] **Step 4: Run the full suites**

Run backend: `cd backend && python -m pytest -q`
Expected: PASS (semua; test lama "transfer proof cannot be direct purchase" — bila ada — sudah disesuaikan di Task 2/3).

Run frontend: `cd frontend && npx vitest run`
Expected: PASS (termasuk 126 test lama + test baru).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/test_transfer_proof_direct_expense.py
git commit -m "test(documents): verify direct purchase journal from transfer proof"
```

---

## Self-Review

**1. Spec coverage**

| Spec butir | Task |
|---|---|
| 1. Longgarkan guard (DIRECT_PURCHASE + kategori + tanpa alokasi) | Task 2 |
| 2. Saran kategori OCR (`candidate.py`) | Task 5 |
| 3. Guard anti double-count berbasis nomor referensi | Task 1 + Task 4 |
| 4. Validasi `is_candidate_ready_for_approval` (5101 wajib proyek) | Task 2 + Task 3 |
| 5. Field "Jenis Pencatatan" (frontend) | Task 6 |
| 6. Validasi form frontend | Task 7 |
| 7. Test backend (guard, duplikat, normalisasi, jurnal) | Task 1–5, 8 |
| 8. Test frontend | Task 6, 7 |
| D3b: file_hash + created_at sebagai pembeda | Task 1 (fungsi murni) + Task 4 (tidak memblokir saat nomor tak cocok) |

**2. Placeholder scan** — Tidak ada placeholder. Semua langkah memuat kode/tes konkret; nama fungsi & signature sudah diverifikasi ke berkas nyata (`build_candidate`, `validateDocumentReviewForm`, `Props`).

**3. Type consistency** — `collect_reference_numbers`, `evaluate_reference_duplicate`, `DuplicateVerdict`, `PROJECT_COST_CATEGORIES`, `RECORDING_CATEGORIES`, `RecordingCategoryOption` konsisten antar task.

**4. Review Focus** — 5 kondisi tercakup: (1) referensi kosong → Task 1 `test_empty_references_never_duplicate` + Task 4; (2) dua bukti transfer nomor sama → Task 1 `test_similar_amount_without_matching_reference_is_allowed` + Task 4 `test_different_reference_with_similar_amount_is_allowed`; (3) alokasi + kategori → Task 3; (4) 5101 tanpa proyek → Task 2/3 (backend) & Task 7 (frontend); (5) nominal sama nomor beda → Task 1 + Task 4.

**Catatan eksekusi:** Beberapa test di Task 5, 6, 7 meminta pembaca menyesuaikan nama fungsi/props ke signature nyata di berkas. Baca berkas target dulu (langkah yang diminta), lalu sesuaikan test — perilaku yang diuji (bukan nama) adalah kontraknya.
