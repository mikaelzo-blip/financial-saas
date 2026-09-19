# Perbaikan Alur Posting Dokumen, Auto-Arsip Bukti, & Penyederhanaan Halaman Review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membuka jalan posting dokumen finansial (flag `AMOUNT_MISMATCH`/`DATE_MISMATCH` bisa diselesaikan), mengarsipkan otomatis dokumen bukti/pendukung yang jenisnya yakin, dan menyederhanakan halaman review.

**Architecture:** Satu resolver bersama `resolve_document_status()` di `backend/src/services/documents/status.py` menjadi satu-satunya penentu status dokumen. Jenis dokumen dikelompokkan menjadi tiga keranjang (`FINANCIAL`, `EVIDENCE`, `UNKNOWN`); hanya `FINANCIAL` yang membentuk kandidat transaksi. Pipeline, endpoint koreksi, dan endpoint approve memakai resolver yang sama. Frontend memakai daftar jenis yang sama untuk memilih tombol aksi.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy async / pytest; React 18 / TypeScript / Vite / Vitest / Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-20-document-review-simplification.md`

## Global Constraints

- Bahasa UI: Indonesia. Semua label & pesan galat berbahasa Indonesia.
- Tidak mengubah `backend/src/services/posting_rules.py`, `backend/src/services/accounting_engine.py`, dan alur alokasi AR/AP (non-goal spec).
- Alasan koreksi otomatis di seluruh form: `'Verifikasi dokumen sumber'`.
- Ambang keyakinan jenis dokumen: `0.85` (selaras `DOCUMENT_CONFIDENCE_THRESHOLD` di `backend/src/core/config.py:29`).
- Tes backend: `backend/.venv/Scripts/python.exe -m pytest` dijalankan dari direktori `backend/`.
- Tes frontend: `npm test` dijalankan dari direktori `frontend/`.
- `PROCESSED` tetap status terminal: worker (`backend/src/worker.py:46`) & endpoint `retry` (`documents.py:208-213`) melewatinya, `can_review=false`.
- Keranjang `EVIDENCE` = 11 jenis `SUPPORTING_DOCUMENT_TYPES` **+** `BANK_STATEMENT`, `QUOTATION`, `VARIATION_ORDER`, `SUBCONTRACT_AGREEMENT`, `PETTY_CASH_PROOF`, `CUSTOMER_RECEIPT` (total 17).
- `UNKNOWN` selalu `REVIEW_REQUIRED` (tidak masuk `EVIDENCE`).

## Review Focus

- **Koreksi nominal pada dokumen ber-flag `AMOUNT_MISMATCH`** → flag hilang; dokumen lanjut bisa disetujui (jalur yang hari ini buntu).
- **Koreksi tanggal pada dokumen ber-flag `DATE_MISMATCH`** → flag hilang.
- **Dokumen `EVIDENCE` yakin (≥0,85, tanpa flag)** → `PROCESSED`, tidak muncul di antrean review.
- **Dokumen `EVIDENCE` dengan flag apa pun** → tetap `REVIEW_REQUIRED` walau jenis yakin.
- **Koreksi dokumen `EVIDENCE` (kandidat `{}`)** → 200 dan tersimpan, bukan 500.
- **Approve dokumen `EVIDENCE`** → 409 dengan pesan jelas, bukan 500.
- **Mengubah jenis dokumen `EVIDENCE` menjadi jenis finansial** → `REVIEW_REQUIRED` (perlu proses ulang), bukan `PROCESSED`.
- **`document_type_confidence` tepat 0,85** → yakin (batas inklusif).
- **`document_type_confidence` kosong/`None`** → tidak yakin → `REVIEW_REQUIRED`.
- **Baris rincian sampah pada dokumen bukti** → tidak lagi memicu `AMOUNT_MISMATCH`.
- **Setujui dengan perubahan belum tersimpan** → koreksi tersimpan lebih dulu, lalu disetujui.

---

### Task 1: Modul resolver status dokumen

**Files:**
- Create: `backend/src/services/documents/status.py`
- Test: `backend/tests/unit/test_document_status.py`

**Interfaces:**
- Consumes: `SUPPORTING_DOCUMENT_TYPES` dari `src.services.documents.candidate`; `CandidateStatus`, `DocumentProcessingStatus`, `DocumentType` dari `src.models.enums`.
- Produces:
  - `EVIDENCE_DOCUMENT_TYPES: frozenset[DocumentType]`
  - `is_evidence_document(document_type: DocumentType | str | None) -> bool`
  - `is_supporting_document(document_type: DocumentType | str | None) -> bool`
  - `document_type_is_confident(confidence_scores: dict | object | None) -> bool`
  - `document_status_for(candidate, flags: list[str]) -> DocumentProcessingStatus`
  - `resolve_document_status(document_type, candidate, flags, confidence_scores=None) -> DocumentProcessingStatus`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_document_status.py
import uuid
from datetime import date
from decimal import Decimal

from src.models.enums import DocumentProcessingStatus, DocumentType
from src.schemas.document import ConfidenceScores, TransactionCandidate
from src.services.documents.status import (
    EVIDENCE_DOCUMENT_TYPES,
    document_type_is_confident,
    is_evidence_document,
    is_supporting_document,
    resolve_document_status,
)

CONFIDENT = {"document_type_confidence": "0.95"}
BORDERLINE = {"document_type_confidence": "0.85"}
WEAK = {"document_type_confidence": "0.30"}
MISSING = {}


def _candidate(document_type=DocumentType.TRANSFER_PROOF, proposed=None):
    return TransactionCandidate(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "t"),
        proposed_transaction_type=proposed,
        transaction_date=date(2026, 9, 2),
        amount=Decimal("1000000.00"),
        currency_code="IDR",
        description="x",
    )


def test_evidence_document_types_cover_supporting_plus_orphans():
    for t in (
        DocumentType.SPK, DocumentType.BAST, DocumentType.TAX_INVOICE,
        DocumentType.BANK_STATEMENT, DocumentType.QUOTATION,
        DocumentType.VARIATION_ORDER, DocumentType.SUBCONTRACT_AGREEMENT,
        DocumentType.PETTY_CASH_PROOF, DocumentType.CUSTOMER_RECEIPT,
    ):
        assert is_evidence_document(t) is True, t
    for t in (DocumentType.TRANSFER_PROOF, DocumentType.RECEIPT,
              DocumentType.VENDOR_INVOICE, DocumentType.CUSTOMER_INVOICE,
              DocumentType.UNKNOWN):
        assert is_evidence_document(t) is False, t


def test_evidence_document_types_accepts_strings():
    assert is_evidence_document("BANK_STATEMENT") is True
    assert is_evidence_document("VENDOR_INVOICE") is False
    assert is_evidence_document(None) is False


def test_supporting_document_is_subset_of_evidence():
    assert is_supporting_document(DocumentType.SPK) is True
    assert is_supporting_document(DocumentType.BANK_STATEMENT) is False
    assert len(EVIDENCE_DOCUMENT_TYPES) == 17


def test_document_type_is_confident_uses_inclusive_threshold():
    assert document_type_is_confident(CONFIDENT) is True
    assert document_type_is_confident(BORDERLINE) is True
    assert document_type_is_confident(WEAK) is False
    assert document_type_is_confident(MISSING) is False
    assert document_type_is_confident(None) is False


def test_document_type_is_confident_accepts_confidence_scores_object():
    scores = ConfidenceScores(
        ocr_confidence=".9", document_type_confidence=".9",
        entity_confidence=".9", project_confidence=".9", amount_confidence=".9",
    )
    assert document_type_is_confident(scores) is True


def test_financial_document_keeps_legacy_behavior():
    assert resolve_document_status(
        DocumentType.VENDOR_INVOICE, _candidate(DocumentType.VENDOR_INVOICE, "VENDOR_BILL"), [], CONFIDENT
    ) == DocumentProcessingStatus.READY_FOR_APPROVAL
    assert resolve_document_status(
        DocumentType.VENDOR_INVOICE, _candidate(DocumentType.VENDOR_INVOICE, "VENDOR_BILL"), ["VENDOR_UNKNOWN"], CONFIDENT
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_evidence_confident_without_flags_is_archived():
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], CONFIDENT
    ) == DocumentProcessingStatus.PROCESSED
    assert resolve_document_status(
        DocumentType.SPK, None, [], BORDERLINE
    ) == DocumentProcessingStatus.PROCESSED


def test_evidence_with_flag_stays_in_review():
    assert resolve_document_status(
        DocumentType.SPK, None, ["OCR_LOW_CONFIDENCE"], CONFIDENT
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_evidence_with_weak_or_missing_confidence_stays_in_review():
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], WEAK
    ) == DocumentProcessingStatus.REVIEW_REQUIRED
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], MISSING
    ) == DocumentProcessingStatus.REVIEW_REQUIRED
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], None
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_unknown_type_always_review_required():
    assert resolve_document_status(
        DocumentType.UNKNOWN, None, [], CONFIDENT
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_evidence_type_renamed_to_financial_returns_review():
    assert resolve_document_status(
        DocumentType.VENDOR_INVOICE, None, [], CONFIDENT
    ) == DocumentProcessingStatus.REVIEW_REQUIRED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/unit/test_document_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.documents.status'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/documents/status.py
"""Single source of truth for document processing status routing.

Documents fall into three baskets:

* FINANCIAL -- documents that become accounting transactions
  (TRANSFER_PROOF, RECEIPT, VENDOR_INVOICE, CUSTOMER_INVOICE).
* EVIDENCE  -- supporting documents that never become transactions; they are
  archived (PROCESSED) once their type is confidently classified, and routed to
  review otherwise.
* UNKNOWN   -- not classifiable yet; always routed to review.

Only FINANCIAL documents can reach READY_FOR_APPROVAL / READY_TO_POST.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from src.models.enums import (
    CandidateStatus,
    DocumentProcessingStatus,
    DocumentType,
)
from src.services.documents.candidate import SUPPORTING_DOCUMENT_TYPES

DOCUMENT_TYPE_CONFIDENCE_THRESHOLD = Decimal("0.85")

# Orphan types: they never produce a transaction candidate and were not part of
# SUPPORTING_DOCUMENT_TYPES, so they used to dead-end in REVIEW_REQUIRED.
_ORPHAN_EVIDENCE_TYPES = {
    DocumentType.BANK_STATEMENT,
    DocumentType.QUOTATION,
    DocumentType.VARIATION_ORDER,
    DocumentType.SUBCONTRACT_AGREEMENT,
    DocumentType.PETTY_CASH_PROOF,
    DocumentType.CUSTOMER_RECEIPT,
}

EVIDENCE_DOCUMENT_TYPES = frozenset(SUPPORTING_DOCUMENT_TYPES | _ORPHAN_EVIDENCE_TYPES)

FINANCIAL_DOCUMENT_TYPES = frozenset({
    DocumentType.TRANSFER_PROOF,
    DocumentType.RECEIPT,
    DocumentType.VENDOR_INVOICE,
    DocumentType.CUSTOMER_INVOICE,
})


def _coerce(document_type: DocumentType | str | None) -> DocumentType | None:
    if document_type is None:
        return None
    if isinstance(document_type, DocumentType):
        return document_type
    try:
        return DocumentType(document_type)
    except (ValueError, KeyError):
        return None


def is_supporting_document(document_type: DocumentType | str | None) -> bool:
    dt = _coerce(document_type)
    return dt in SUPPORTING_DOCUMENT_TYPES if dt is not None else False


def is_evidence_document(document_type: DocumentType | str | None) -> bool:
    dt = _coerce(document_type)
    return dt in EVIDENCE_DOCUMENT_TYPES if dt is not None else False


def document_type_is_confident(confidence_scores: Any) -> bool:
    """True when the document *type* confidence is at or above threshold.

    Accepts a dict, a ConfidenceScores-like object, or None. Missing value is
    treated as not confident.
    """
    if confidence_scores is None:
        return False
    if isinstance(confidence_scores, dict):
        raw = confidence_scores.get("document_type_confidence")
    else:
        raw = getattr(confidence_scores, "document_type_confidence", None)
    if raw is None or raw == "":
        return False
    try:
        return Decimal(str(raw)) >= DOCUMENT_TYPE_CONFIDENCE_THRESHOLD
    except (InvalidOperation, ValueError):
        return False


def document_status_for(candidate, flags: Iterable[str]) -> DocumentProcessingStatus:
    """Legacy financial routing: based on candidate readiness and review flags."""
    flags = list(flags)
    if flags or not candidate or not candidate.proposed_transaction_type or (
        candidate.status == CandidateStatus.REVIEW_REQUIRED
    ):
        return DocumentProcessingStatus.REVIEW_REQUIRED
    return DocumentProcessingStatus.READY_FOR_APPROVAL


def resolve_document_status(
    document_type: DocumentType | str | None,
    candidate,
    flags: Iterable[str],
    confidence_scores: Any = None,
) -> DocumentProcessingStatus:
    """Canonical status resolver used by the pipeline and the corrections endpoint."""
    flags = list(flags)
    dt = _coerce(document_type)

    if dt in FINANCIAL_DOCUMENT_TYPES:
        return document_status_for(candidate, flags)

    if dt is not None and dt in EVIDENCE_DOCUMENT_TYPES:
        if flags or not document_type_is_confident(confidence_scores):
            return DocumentProcessingStatus.REVIEW_REQUIRED
        return DocumentProcessingStatus.PROCESSED

    # UNKNOWN or unclassifiable -> always review
    return DocumentProcessingStatus.REVIEW_REQUIRED
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/unit/test_document_status.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/documents/status.py backend/tests/unit/test_document_status.py
git commit -m "feat(documents): single resolver for document status routing"
```

---

### Task 2: Batasi validasi konsistensi line item ke dokumen ber-rincian

**Files:**
- Modify: `backend/src/services/documents/candidate.py:142-150`
- Test: `backend/tests/unit/test_line_item_consistency_scope.py`

**Interfaces:**
- Consumes: `derive_flags(document_type, data, matches, low_confidence)` dari modul yang sama.
- Produces: flag `AMOUNT_MISMATCH` dari penjumlahan line item hanya muncul untuk `RECEIPT`, `VENDOR_INVOICE`, `CUSTOMER_INVOICE`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_line_item_consistency_scope.py
from decimal import Decimal

from src.models.enums import DocumentType, ReviewFlag
from src.schemas.document import LineItem, StructuredExtraction
from src.services.documents.candidate import derive_flags

ITEMS = [
    LineItem(description="a", quantity="1", unit_price="750.00", amount="750.00", line_total="750.00"),
    LineItem(description="b", quantity="1", unit_price="250.00", amount="250.00", line_total="250.00"),
]


def _extraction(total: str) -> StructuredExtraction:
    return StructuredExtraction(
        transaction_date="2026-09-16",
        total_amount=Decimal(total),
        currency_code="IDR",
        line_items=ITEMS,
    )


def test_line_item_mismatch_ignored_for_evidence_documents():
    flags = derive_flags(DocumentType.BANK_STATEMENT, _extraction("19939750.00"), {}, False)
    assert ReviewFlag.AMOUNT_MISMATCH.value not in flags


def test_line_item_mismatch_still_flagged_for_receipt():
    flags = derive_flags(DocumentType.RECEIPT, _extraction("19939750.00"), {}, False)
    assert ReviewFlag.AMOUNT_MISMATCH.value in flags


def test_line_item_match_never_flags_for_invoice():
    flags = derive_flags(DocumentType.VENDOR_INVOICE, _extraction("1000.00"), {}, False)
    assert ReviewFlag.AMOUNT_MISMATCH.value not in flags
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/unit/test_line_item_consistency_scope.py -v`
Expected: FAIL pada `test_line_item_mismatch_ignored_for_evidence_documents`

- [ ] **Step 3: Write minimal implementation**

Ganti blok di `backend/src/services/documents/candidate.py` baris 142-150:

```python
    # Consistency validation: line items sum vs total_amount / subtotal.
    # Only meaningful for documents that actually carry an itemised breakdown;
    # bank statements, transfer proofs and other evidence documents contain
    # OCR noise in line_items that must not raise AMOUNT_MISMATCH.
    LINE_ITEM_TYPES = {
        DocumentType.RECEIPT,
        DocumentType.VENDOR_INVOICE,
        DocumentType.CUSTOMER_INVOICE,
    }
    if document_type in LINE_ITEM_TYPES and data.line_items and data.total_amount is not None:
        valid_line_amounts = [it.amount for it in data.line_items if it.amount is not None]
        if valid_line_amounts and len(valid_line_amounts) == len(data.line_items):
            line_sum = sum(valid_line_amounts)
            matches_total = abs(line_sum - data.total_amount) <= Decimal("1.00")
            matches_subtotal = (data.subtotal is not None and abs(line_sum - data.subtotal) <= Decimal("1.00"))
            if not matches_total and not matches_subtotal:
                flags.append(ReviewFlag.AMOUNT_MISMATCH.value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/unit/test_line_item_consistency_scope.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/documents/candidate.py backend/tests/unit/test_line_item_consistency_scope.py
git commit -m "fix(documents): scope line-item amount mismatch to itemised document types"
```

---

### Task 3: Pipeline memakai resolver bersama

**Files:**
- Modify: `backend/src/services/documents/pipeline.py:11,22-25,97`
- Modify: `backend/tests/unit/test_document_intelligence.py:11,71,77`
- Test: `backend/tests/unit/test_document_status.py` (tambahan)

**Interfaces:**
- Consumes: `resolve_document_status`, `document_status_for` dari Task 1.
- Produces: `src.services.documents.pipeline.document_status_for` tetap dapat diimpor (re-export) dengan signature lama `(candidate, flags)`.

- [ ] **Step 1: Write the failing test**

Tambahkan ke `backend/tests/unit/test_document_status.py`:

```python
def test_pipeline_reexports_document_status_for():
    from src.services.documents.pipeline import document_status_for as pipeline_status_for
    assert pipeline_status_for(_candidate(DocumentType.VENDOR_INVOICE, "VENDOR_BILL"), []) == \
        DocumentProcessingStatus.READY_FOR_APPROVAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/unit/test_document_status.py::test_pipeline_reexports_document_status_for -v`
Expected: PASS bila re-export sudah ada; bila masih definisi lama, tetap PASS (tes mengunci kompatibilitas signature).

- [ ] **Step 3: Write minimal implementation**

Di `backend/src/services/documents/pipeline.py`:

**Tambahkan** impor baru setelah baris 19 (`from src.models.enums import ReviewFlag`) — jangan mengubah baris 11 yang mengimpor `build_candidate, derive_flags`:

```python
from src.services.documents.status import document_status_for, resolve_document_status  # noqa: F401
```

**Hapus** definisi `document_status_for` lama (baris 22-25) — sekarang berasal dari `status.py`.

Ganti baris 97 menjadi:

```python
            document.processing_status = resolve_document_status(
                effective_type, candidate, flags, document.confidence_scores
            )
```

Di `backend/tests/unit/test_document_intelligence.py`, ganti impor baris 11 menjadi:

```python
from src.services.documents.status import document_status_for
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/unit/test_document_status.py tests/unit/test_document_intelligence.py tests/unit/test_line_item_consistency_scope.py -v`
Expected: PASS semua

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/documents/pipeline.py backend/tests/unit/test_document_intelligence.py backend/tests/unit/test_document_status.py
git commit -m "refactor(documents): pipeline routes status through shared resolver"
```

---

### Task 4: Flag `AMOUNT_MISMATCH`/`DATE_MISMATCH` dapat diselesaikan lewat koreksi

**Files:**
- Modify: `backend/src/api/v1/documents.py:440-463`
- Test: `backend/tests/integration/test_document_correction_flag_resolution.py`

**Interfaces:**
- Consumes: endpoint `POST /api/v1/documents/{id}/corrections` yang sudah ada; `DocumentCorrectionRequest`.
- Produces: koreksi `amount`/`total_amount` menghapus `AMOUNT_MISMATCH` + `OCR_LOW_CONFIDENCE`; koreksi `date`/`transaction_date` menghapus `DATE_MISMATCH` + `OCR_LOW_CONFIDENCE`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_document_correction_flag_resolution.py
import io

import pytest
from httpx import AsyncClient

from src.models.enums import (
    DocumentProcessingStatus,
    DocumentType,
    ReviewFlag,
    UserRole,
)
from src.models.organization import Organization
from src.models.user import User
from src.services.document_service import DocumentService


@pytest.fixture
async def correction_env(db_session):
    org = Organization(slug="flag-resolution", legal_name="Flag Resolution Org")
    db_session.add(org)
    await db_session.flush()
    manager = User(
        organization_id=org.id,
        email="manager@flag.test",
        full_name="Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()
    return {"org": org, "manager": manager}


async def _make_doc(db_session, env, flags, amount="19939750.00", ttype="DIRECT_PURCHASE"):
    doc = await DocumentService(db_session).ingest_document(
        env["org"].id,
        io.BytesIO(b"%PDF-1.4\nx"),
        "x.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=env["manager"].id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": ttype,
        "amount": amount,
        "transaction_date": "2026-09-16",
        "currency_code": "IDR",
        "description": "x",
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = list(flags)
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.flush()
    return doc


@pytest.mark.asyncio
async def test_amount_correction_clears_amount_mismatch(client: AsyncClient, db_session, correction_env):
    doc = await _make_doc(db_session, correction_env, [ReviewFlag.AMOUNT_MISMATCH.value])
    headers = {
        "X-Organization-ID": str(correction_env["org"].id),
        "X-User-ID": str(correction_env["manager"].id),
    }
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"amount": "19939750.00"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert resp.status_code == 200
    assert ReviewFlag.AMOUNT_MISMATCH.value not in resp.json()["review_flags"]


@pytest.mark.asyncio
async def test_date_correction_clears_date_mismatch(client: AsyncClient, db_session, correction_env):
    doc = await _make_doc(db_session, correction_env, [ReviewFlag.DATE_MISMATCH.value])
    headers = {
        "X-Organization-ID": str(correction_env["org"].id),
        "X-User-ID": str(correction_env["manager"].id),
    }
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"transaction_date": "2026-09-16"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert resp.status_code == 200
    assert ReviewFlag.DATE_MISMATCH.value not in resp.json()["review_flags"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/integration/test_document_correction_flag_resolution.py -v`
Expected: FAIL — flag masih ada setelah koreksi

- [ ] **Step 3: Write minimal implementation**

Di `backend/src/api/v1/documents.py`:

**(a) Pindahkan perhitungan `resolved`/`cleared` ke lebih awal.** Sisipkan blok berikut tepat setelah baris 400 (`document.matching_results = matching_results`):

```python
    resolved = {
        "project_id": ["PROJECT_UNKNOWN"],
        "counterparty_id": ["VENDOR_UNKNOWN", "CUSTOMER_UNKNOWN"],
        "selected_candidate_id": ["AMBIGUOUS_MATCH"],
        "allocation_target_id": ["AMBIGUOUS_MATCH"],
        "amount": ["OCR_LOW_CONFIDENCE", "AMOUNT_MISMATCH"],
        "total_amount": ["OCR_LOW_CONFIDENCE", "AMOUNT_MISMATCH"],
        "transaction_date": ["OCR_LOW_CONFIDENCE", "DATE_MISMATCH"],
        "date": ["OCR_LOW_CONFIDENCE", "DATE_MISMATCH"],
    }
    cleared = set()
    for key, value in data.changes.items():
        if key in resolved and value:
            cleared.update(resolved[key])
```

**(b) Hapus definisi `resolved`/`cleared` yang lama** (baris 440-450). Blok setelahnya — penambahan `ACCOUNT_REVIEW`/`AMBIGUOUS_MATCH` dan `DUPLICATE_SUSPECTED` ke `cleared` (baris 451-463) — tetap dipertahankan karena kini memakai variabel `cleared` yang sudah dihitung di langkah (a).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/integration/test_document_correction_flag_resolution.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/v1/documents.py backend/tests/integration/test_document_correction_flag_resolution.py
git commit -m "fix(documents): let amount/date corrections resolve mismatch flags"
```

---

### Task 5: Koreksi & approve aman untuk dokumen bukti (EVIDENCE)

**Files:**
- Modify: `backend/src/api/v1/documents.py` (endpoint `correct_document` ~231-492; endpoint `approve_document_candidate` ~495-528)
- Test: `backend/tests/integration/test_evidence_document_review.py`

**Interfaces:**
- Consumes: `is_evidence_document`, `resolve_document_status` dari Task 1.
- Produces: endpoint koreksi mengembalikan 200 untuk dokumen `EVIDENCE`; endpoint approve mengembalikan 409 dengan pesan `"Dokumen pendukung tidak perlu disetujui..."`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_evidence_document_review.py
import io

import pytest
from httpx import AsyncClient

from src.models.enums import DocumentProcessingStatus, DocumentType, UserRole
from src.models.organization import Organization
from src.models.user import User
from src.services.document_service import DocumentService


@pytest.fixture
async def evidence_env(db_session):
    org = Organization(slug="evidence-org", legal_name="Evidence Org")
    db_session.add(org)
    await db_session.flush()
    manager = User(
        organization_id=org.id,
        email="m@evidence.test",
        full_name="Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()
    return {"org": org, "manager": manager}


@pytest.mark.asyncio
async def test_correcting_evidence_document_does_not_500(client: AsyncClient, db_session, evidence_env):
    doc = await DocumentService(db_session).ingest_document(
        evidence_env["org"].id,
        io.BytesIO(b"%PDF-1.4\nmutasi"),
        "mutasi.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=evidence_env["manager"].id,
    )
    doc.candidate_transaction = {}
    doc.review_flags = ["OCR_LOW_CONFIDENCE"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.flush()

    headers = {
        "X-Organization-ID": str(evidence_env["org"].id),
        "X-User-ID": str(evidence_env["manager"].id),
    }
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"document_type": "BANK_STATEMENT"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert resp.status_code == 200
    assert resp.json()["processing_status"] == "REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_approving_evidence_document_is_rejected_clearly(client: AsyncClient, db_session, evidence_env):
    doc = await DocumentService(db_session).ingest_document(
        evidence_env["org"].id,
        io.BytesIO(b"%PDF-1.4\nmutasi"),
        "mutasi.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=evidence_env["manager"].id,
    )
    doc.candidate_transaction = {}
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.flush()

    headers = {
        "X-Organization-ID": str(evidence_env["org"].id),
        "X-User-ID": str(evidence_env["manager"].id),
    }
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 409
    assert "Dokumen pendukung" in resp.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/integration/test_evidence_document_review.py -v`
Expected: FAIL — koreksi mengembalikan 500

- [ ] **Step 3: Write minimal implementation**

Di `backend/src/api/v1/documents.py`:

(a) Tambahkan impor di bagian atas file (dekat impor service lain):

```python
from src.services.documents.status import is_evidence_document, resolve_document_status
```

(b) Di `correct_document`, tepat sebelum baris `validated = TransactionCandidate.model_validate(candidate)` (baris ~402), sisipkan:

```python
    if is_evidence_document(document.document_type):
        # Evidence documents carry no transaction candidate; skip candidate
        # validation (an empty {} would raise) and re-resolve the status.
        document.extracted_data = extracted
        document.matching_results = matching_results
        document.review_flags = [f for f in document.review_flags if f not in cleared]
        document.processing_status = resolve_document_status(
            document.document_type, None, document.review_flags, document.confidence_scores
        )
        for key, value in data.changes.items():
            db.add(DocumentCorrection(
                organization_id=org_id,
                document_id=document.id,
                field_path=key,
                old_value=old.get(key),
                new_value=value,
                reason=data.reason,
                corrected_by=user_id,
            ))
        await AuditService(db).log_event(
            org_id, "Document", document.id, "CORRECT_EXTRACTION", user_id,
            old_values=old, new_values=data.changes, reason=data.reason
        )
        await db.flush()
        return document
```

(c) Di `approve_document_candidate`, sisipkan sebelum `if not document.candidate_transaction:` (baris ~530):

```python
    if is_evidence_document(document.document_type):
        raise HTTPException(
            status_code=409,
            detail="Dokumen pendukung tidak perlu disetujui; dokumen ini diarsipkan otomatis.",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/integration/test_evidence_document_review.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/v1/documents.py backend/tests/integration/test_evidence_document_review.py
git commit -m "fix(documents): handle evidence documents in corrections and approve"
```

---

### Task 6: Daftar jenis dokumen bukti di frontend

**Files:**
- Modify: `frontend/src/utils/documentReview.ts`
- Test: `frontend/tests/utils/documentReviewEvidence.test.ts`

**Interfaces:**
- Consumes: —
- Produces: `EVIDENCE_DOCUMENT_TYPES: ReadonlySet<string>` dan `isEvidenceDocument(documentType: string | undefined) => boolean`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/tests/utils/documentReviewEvidence.test.ts
import { describe, expect, it } from 'vitest';
import { EVIDENCE_DOCUMENT_TYPES, isEvidenceDocument } from '../../src/utils/documentReview';

describe('isEvidenceDocument', () => {
  it('recognises supporting and orphan evidence types', () => {
    for (const t of ['SPK', 'BAST', 'TAX_INVOICE', 'BANK_STATEMENT', 'QUOTATION', 'PETTY_CASH_PROOF', 'CUSTOMER_RECEIPT']) {
      expect(isEvidenceDocument(t)).toBe(true);
    }
  });

  it('excludes financial and unknown types', () => {
    for (const t of ['TRANSFER_PROOF', 'RECEIPT', 'VENDOR_INVOICE', 'CUSTOMER_INVOICE', 'UNKNOWN', undefined]) {
      expect(isEvidenceDocument(t)).toBe(false);
    }
  });

  it('has 17 evidence types', () => {
    expect(EVIDENCE_DOCUMENT_TYPES.size).toBe(17);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/utils/documentReviewEvidence.test.ts`
Expected: FAIL — `isEvidenceDocument is not a function`

- [ ] **Step 3: Write minimal implementation**

Tambahkan di `frontend/src/utils/documentReview.ts` (setelah blok `PAYMENT_ACCOUNT_REQUIRED_TRANSACTION_TYPES`):

```ts
// Keep in sync with backend/src/services/documents/status.py (EVIDENCE_DOCUMENT_TYPES).
export const EVIDENCE_DOCUMENT_TYPES: ReadonlySet<string> = new Set<string>([
  // Supporting documents
  'SPK',
  'CONTRACT',
  'BAST',
  'SURAT_JALAN',
  'PROGRESS_REPORT',
  'TIMESHEET',
  'PURCHASE_ORDER',
  'PO_CUSTOMER',
  'TAX_INVOICE',
  'WITHHOLDING_DOCUMENT',
  'OTHER_TAX_DOCUMENT',
  // Evidence-only orphans
  'BANK_STATEMENT',
  'QUOTATION',
  'VARIATION_ORDER',
  'SUBCONTRACT_AGREEMENT',
  'PETTY_CASH_PROOF',
  'CUSTOMER_RECEIPT',
]);

export const isEvidenceDocument = (documentType: string | undefined | null): boolean =>
  Boolean(documentType && EVIDENCE_DOCUMENT_TYPES.has(documentType));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/utils/documentReviewEvidence.test.ts`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/documentReview.ts frontend/tests/utils/documentReviewEvidence.test.ts
git commit -m "feat(frontend): recognise evidence document types"
```

---

### Task 7: Sederhanakan halaman review (hapus panel debug, tombol per keranjang)

**Files:**
- Modify: `frontend/src/components/documents/DocumentReviewForm.tsx`
- Modify: `frontend/tests/pages/DocumentReviewSlice4.test.tsx:153,208`
- Modify: `frontend/tests/pages/DocumentReviewWorkspace.test.tsx:97,121`
- Modify: `frontend/tests/pages/DocumentReviewApprovalWorkflow.test.tsx:370,389`
- Modify: `frontend/tests/pages/DocumentReviewNavigation.test.tsx:190,194`
- Test: `frontend/tests/pages/DocumentReviewSimplified.test.tsx`

**Interfaces:**
- Consumes: `isEvidenceDocument` dari Task 6.
- Produces: form tanpa panel "Riwayat Koreksi"/"Detail Teknis"/input alasan; tombol "Simpan Dokumen" (evidence) atau "Setujui untuk Diposting" + "Tolak Kandidat" (financial).

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/pages/DocumentReviewSimplified.test.tsx
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import type { DocumentResponse } from '../../src/types/api';

const baseDoc = (overrides: Partial<DocumentResponse> = {}): DocumentResponse =>
  ({
    id: 'doc-1',
    document_code: 'DOC-1',
    document_type: 'VENDOR_INVOICE',
    processing_status: 'REVIEW_REQUIRED',
    file_name: 'x.pdf',
    mime_type: 'application/pdf',
    file_size_bytes: 1,
    file_hash: 'h',
    source_channel: 'UPLOAD',
    source_metadata: {},
    created_at: '2026-09-16T00:00:00Z',
    extracted_data: {},
    matching_results: {},
    confidence_scores: {},
    candidate_transaction: {
      id: 'c1',
      proposed_transaction_type: 'VENDOR_BILL',
      amount: '1000000.00',
      transaction_date: '2026-09-16',
      status: 'REVIEW_REQUIRED',
    },
    review_flags: [],
    corrections: [{ id: 'k1', field_path: 'amount', old_value: '1', new_value: '2', reason: 'x', corrected_at: '2026-09-16T00:00:00Z' }],
    ...overrides,
  }) as unknown as DocumentResponse;

const noop = async () => {};

describe('simplified review form', () => {
  it('hides debug panels and reason input for financial documents', () => {
    render(
      <DocumentReviewForm document={baseDoc()} projects={[]} counterparties={[]} onSave={noop} onApprove={noop} onReject={noop} />,
    );
    expect(screen.queryByText('Riwayat Koreksi')).not.toBeInTheDocument();
    expect(screen.queryByText('Detail Teknis')).not.toBeInTheDocument();
    expect(screen.queryByText('Mengapa data ini diubah?')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Setujui untuk Diposting' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Simpan Koreksi' })).not.toBeInTheDocument();
  });

  it('shows a single save button for evidence documents', () => {
    render(
      <DocumentReviewForm
        document={baseDoc({ document_type: 'BANK_STATEMENT', candidate_transaction: { id: 'c', status: 'REVIEW_REQUIRED' } as never })}
        projects={[]}
        counterparties={[]}
        onSave={noop}
        onApprove={noop}
        onReject={noop}
      />,
    );
    expect(screen.getByRole('button', { name: 'Simpan Dokumen' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Setujui untuk Diposting' })).not.toBeInTheDocument();
  });

  it('keeps approve enabled while review flags exist', () => {
    render(
      <DocumentReviewForm document={baseDoc({ review_flags: ['AMOUNT_MISMATCH'] })} projects={[]} counterparties={[]} onSave={noop} onApprove={noop} onReject={noop} />,
    );
    expect(screen.getByRole('button', { name: 'Setujui untuk Diposting' })).toBeEnabled();
  });

  it('hides the line-items table for evidence documents', () => {
    render(
      <DocumentReviewForm
        document={baseDoc({
          document_type: 'BANK_STATEMENT',
          candidate_transaction: { id: 'c', status: 'REVIEW_REQUIRED' } as never,
          extracted_data: { line_items: [{ description: 'IDR', line_total: '750.00' }] },
        })}
        projects={[]}
        counterparties={[]}
        onSave={noop}
        onApprove={noop}
        onReject={noop}
      />,
    );
    expect(screen.queryByText('Daftar Rincian Barang / Jasa')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/pages/DocumentReviewSimplified.test.tsx`
Expected: FAIL — panel masih tampil / tombol belum sesuai

- [ ] **Step 3: Write minimal implementation**

Di `frontend/src/components/documents/DocumentReviewForm.tsx`:

(a) Impor: tambahkan `isEvidenceDocument` dari `'../../utils/documentReview'`; hapus `History` dari impor `lucide-react`.

(b) Tambahkan konstanta setelah impor:

```tsx
const AUTO_CORRECTION_REASON = 'Verifikasi dokumen sumber';
```

(c) Ganti state `reason` (baris 133) menjadi konstanta lokal:

```tsx
  const reason = AUTO_CORRECTION_REASON;
```

(d) Ganti definisi `isEvidenceOnly` (baris 341-343) menjadi:

```tsx
  const isEvidenceOnly = isEvidenceDocument(document.document_type);
```

(e) Tabel rincian (baris 684): ganti kondisi menjadi:

```tsx
      {lineItems.length > 0 && !isEvidenceOnly && document.document_type !== 'TRANSFER_PROOF' && (
```

(f) Hapus blok input alasan (baris 1062-1072).

(g) Hapus blok "Riwayat Koreksi" (baris 1075-1098) dan "Detail Teknis" (baris 1100-1109); hapus variabel `corrections` (baris 358) bila tak terpakai.

(h) Ganti blok Action Buttons (baris 1111-1132) menjadi:

```tsx
      {/* Action Buttons */}
      <div className="flex flex-wrap gap-2">
        {isEvidenceOnly ? (
          <Button onClick={save} isLoading={busy}>
            Simpan Dokumen
          </Button>
        ) : (
          <>
            <Button
              variant="secondary"
              onClick={handleApprove}
              isLoading={busy}
              disabled={approvalLookupLoading || !!approvalLookupError}
            >
              Setujui untuk Diposting
            </Button>
            <Button variant="danger" onClick={() => onReject(reason)}>
              Tolak Kandidat
            </Button>
          </>
        )}
      </div>
```

- [ ] **Step 4: Update existing tests**

`frontend/tests/pages/DocumentReviewSlice4.test.tsx`:
- Baris 153: hapus `expect(screen.getByText('Riwayat Koreksi')).toBeInTheDocument();`
- Baris 208: ganti tombol `'Simpan Koreksi'` menjadi `'Setujui untuk Diposting'` (koreksi kini tersimpan lewat tombol Setujui).

`frontend/tests/pages/DocumentReviewWorkspace.test.tsx`:
- Baris 97: ganti `'Simpan Koreksi'` menjadi `'Setujui untuk Diposting'`.
- Baris 121: hapus `expect(screen.getByText('Detail Teknis')).toBeInTheDocument();`

`frontend/tests/pages/DocumentReviewApprovalWorkflow.test.tsx`:
- Baris 370: ganti nama tes & tombol menjadi `'Setujui untuk Diposting'`; hapus ekspektasi "without calling onApprove".

`frontend/tests/pages/DocumentReviewNavigation.test.tsx`:
- Baris 190-194: ganti `'Simpan Koreksi'` menjadi `'Setujui untuk Diposting'`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/pages/DocumentReviewSimplified.test.tsx tests/pages/DocumentReviewSlice4.test.tsx tests/pages/DocumentReviewWorkspace.test.tsx tests/pages/DocumentReviewApprovalWorkflow.test.tsx tests/pages/DocumentReviewNavigation.test.tsx`
Expected: PASS semua

- [ ] **Step 6: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: exit 0

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/documents/DocumentReviewForm.tsx frontend/tests/pages/
git commit -m "feat(frontend): simplify review page and add evidence save button"
```

---

### Task 8: Tes regresi alur nyata (koreksi → approve → post lewat API) & verifikasi penuh

**Files:**
- Test: `backend/tests/integration/test_document_flag_dead_end_regression.py`
- Modify: `backend/tests/integration/test_uat12_whatsapp_media_transport.py:531`

**Interfaces:**
- Consumes: seluruh perubahan Task 1-7.
- Produces: bukti jalur yang dulu buntu kini tuntas end-to-end.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_document_flag_dead_end_regression.py
import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.coa import PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import (
    DocumentProcessingStatus,
    DocumentType,
    ReviewFlag,
    TransactionType,
    UserRole,
)
from src.models.organization import Organization
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_amount_mismatch_document_can_be_resolved_and_posted(client: AsyncClient, db_session):
    org = Organization(slug="dead-end-org", legal_name="Dead End Org")
    db_session.add(org)
    await db_session.flush()
    manager = User(
        organization_id=org.id, email="m@deadend.test", full_name="M",
        password_hash="x", role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()
    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)

    cash = await db_session.scalar(select(PaymentAccount).where(
        PaymentAccount.organization_id == org.id, PaymentAccount.is_active.is_(True)
    ))
    vendor = Counterparty(
        id=uuid.uuid4(), organization_id=org.id, name="PT Uji",
        is_vendor=True, is_customer=False, is_active=True,
    )
    db_session.add(vendor)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\nnota"), "nota.pdf", "application/pdf",
        DocumentType.RECEIPT, created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": TransactionType.DIRECT_PURCHASE.value,
        "counterparty_id": str(vendor.id),
        "payment_account_id": str(cash.id),
        "cost_category": "MAT",
        "project_id": None,
        "amount": "1000.00",
        "transaction_date": "2026-09-16",
        "currency_code": "IDR",
        "description": "Nota uji",
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = [ReviewFlag.AMOUNT_MISMATCH.value]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.flush()

    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}

    # 1. Approve while the flag exists must fail closed.
    blocked = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert blocked.status_code == 409

    # 2. Resolve the flag THROUGH THE API (not by writing to the DB).
    corrected = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"amount": "1000.00"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert corrected.status_code == 200
    assert ReviewFlag.AMOUNT_MISMATCH.value not in corrected.json()["review_flags"]

    # 3. Approve now succeeds.
    approved = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["processing_status"] in {"READY_TO_POST", "POSTED"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/integration/test_document_flag_dead_end_regression.py -v`
Expected: FAIL sebelum Task 4 selesai; PASS setelahnya (mengunci regresi)

- [ ] **Step 3: Update the stale policy test**

Di `backend/tests/integration/test_uat12_whatsapp_media_transport.py` baris 531, dokumen SPK dengan `document_type_confidence=0.95` kini diarsipkan:

```python
    assert doc.processing_status == DocumentProcessingStatus.PROCESSED
```

Periksa juga skenario 8 (`BAST`/`SURAT_JALAN`, sekitar baris 545-575): tambahkan assertion status `PROCESSED` bila jenisnya yakin, atau `REVIEW_REQUIRED` bila tidak yakin — sesuaikan dengan `document_type_confidence` yang dipakai skenario tersebut.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest -q`
Expected: seluruh tes lulus (kecuali 26 error env-gate `FIN_001_TEST_DATABASE_URL` — bukan regresi)

- [ ] **Step 5: Run the full frontend suite + typecheck + build**

Run: `cd frontend && npm test -- --run && npx tsc -b && npx vite build`
Expected: semua lulus, `tsc -b` exit 0, `vite build` exit 0

- [ ] **Step 6: Commit**

```bash
git add backend/tests/ frontend/tests/
git commit -m "test(documents): pin end-to-end flag resolution and update policy expectations"
```

---

## Catatan Eksekusi

- Restart backend setelah perubahan: `uvicorn` dijalankan **tanpa** `--reload` di mesin ini, jadi kode lama tetap melayani sampai di-restart (ini akar insiden "peringatan merah" sebelumnya). Restart backend + worker sebelum verifikasi manual.
- Verifikasi manual: buka `http://127.0.0.1:5173/documents` → dokumen `DOC-2026-000015` (BANK_STATEMENT) harus hilang dari antrean "Perlu Diperiksa" (terarsip) setelah diproses ulang; `DOC-2026-000016` (VENDOR_INVOICE) harus bisa disetujui setelah nominal dikoreksi.
