# Per-Line Recording Category & Goods+Service HPP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one invoice be posted across several accounts per line item — project goods/services to HPP (5101), administrative fees and stamp duty to operational expense — while keeping a single HPP line in the P&L.

**Architecture:** Add an optional recording category to each `LineItem` (stored in the existing JSON, no new DB column). A new per-line classifier suggests a category from each description; the reviewer confirms or edits it per row in the review table. On approval, `document_posting_service` groups line items by `(project_id, cost_category, expense_category)` and passes them as `TransactionCreate.allocations`, which the existing `PostingRuleRegistry` already turns into the right journal legs.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / Pydantic v2 (backend), React + TypeScript + Vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-09-20-per-line-recording-category.md`

## Global Constraints

- Do NOT change `posting_rules.py` account mapping or add/modify COA accounts.
- Do NOT add a DB column: per-line category lives inside `extracted_data.line_items` JSON.
- `shared/recording-categories.json` is the single source of truth for the catalog; UI labels stay in the frontend.
- HPP categories (`MAT`, `SUB`, `LOG`, `TRN`, `EQP`) require a `project_id`; without one the entry must NOT silently fall to 6199 — it must be rejected with a clear message.
- The sum of allocations MUST equal `candidate.amount`; otherwise fail loudly.
- Backend tests use the repo venv: `cd backend && .venv/Scripts/python.exe -m pytest ... -p no:cacheprovider`.
- Existing backend suite is NOT all-green by default: `test_fin001_ar_ap_concurrency_postgresql.py` and `test_fin001_cp3_retry_postgresql.py` ERROR at setup (`FIN_001_TEST_DATABASE_URL is required`) — pre-existing, judge cleanliness by absence of `FAILED`.

## Review Focus

- A line description that matches BOTH a service word and a physical unit (e.g. "JASA ANGKUT 2 TRUK") — a reasonable person expects the freight/service category, not `MAT`.
- A line whose category is `STAMP`/materai on a document that HAS a project — expects operational expense (6199), NOT HPP, despite the project.
- A line with a HPP category (`LOG`) on a document with NO project — expects a clear rejection, not a silent 6199 booking.
- A document with line items where some lines have no category — expects the fallback (document-level category) so amounts still reconcile.
- An old document whose `line_items` predate this feature (no `cost_category` keys) — expects unchanged single-allocation behavior.

---

### Task 1: Add `LOG` to the shared recording-category catalog

**Files:**
- Modify: `shared/recording-categories.json`
- Modify: `frontend/src/utils/recordingCategories.ts`
- Test: `backend/tests/unit/test_recording_categories.py`

**Interfaces:**
- Produces: `LOG` becomes a selectable cost category (`requiresProject: true`), included in `PROJECT_REQUIRED_COST_CATEGORIES` and `RECORDING_CATEGORIES`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/unit/test_recording_categories.py`, update the two pinned assertions to include `LOG`:

```python
def test_loads_every_recording_category_in_order():
    entries = load_recording_categories()
    assert [e.value for e in entries] == [
        "MAT",
        "SUB",
        "TRN",
        "EQP",
        "LOG",
        "TRAVEL_OFFICE",
        "OFFICE_ADMIN",
        "OTHER_OPERATIONAL",
    ]


def test_project_required_cost_categories_matches_curated_business_rule():
    # LOG (logistics & freight) joined the project-required cost categories so
    # "JASA ANGKUT" lines can book to HPP 5101 instead of falling to 6199.
    assert PROJECT_REQUIRED_COST_CATEGORIES == {"MAT", "SUB", "TRN", "EQP", "LOG"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_recording_categories.py -v -p no:cacheprovider`
Expected: FAIL — lists are missing `LOG`.

- [ ] **Step 3: Add LOG to the catalog**

In `shared/recording-categories.json`, insert the LOG entry after `EQP`:

```json
[
  { "value": "MAT", "kind": "cost", "requiresProject": true },
  { "value": "SUB", "kind": "cost", "requiresProject": true },
  { "value": "TRN", "kind": "cost", "requiresProject": true },
  { "value": "EQP", "kind": "cost", "requiresProject": true },
  { "value": "LOG", "kind": "cost", "requiresProject": true },
  { "value": "TRAVEL_OFFICE", "kind": "expense", "requiresProject": false },
  { "value": "OFFICE_ADMIN", "kind": "expense", "requiresProject": false },
  { "value": "OTHER_OPERATIONAL", "kind": "expense", "requiresProject": false }
]
```

- [ ] **Step 4: Add the UI label**

In `frontend/src/utils/recordingCategories.ts`, add to the `LABELS` map:

```ts
  LOG: 'Jasa Angkut / Ekspedisi (proyek)',
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_recording_categories.py -v -p no:cacheprovider`
Expected: PASS (all 6).

- [ ] **Step 6: Commit**

```bash
git add shared/recording-categories.json frontend/src/utils/recordingCategories.ts backend/tests/unit/test_recording_categories.py
git commit -m "feat(documents): add LOG (freight) to the recording-category catalog"
```

---

### Task 2: Add optional recording category fields to `LineItem`

**Files:**
- Modify: `backend/src/schemas/document.py` (class `LineItem`, lines 20-36)
- Test: `backend/tests/unit/test_line_item_category_schema.py` (create)

**Interfaces:**
- Produces: `LineItem(description, amount, cost_category: Optional[CostCategory] = None, expense_category: Optional[ExpenseCategory] = None)`. Serialized into `extracted_data.line_items`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_line_item_category_schema.py`:

```python
from decimal import Decimal

from src.models.enums import CostCategory, ExpenseCategory
from src.schemas.document import LineItem


def test_line_item_accepts_per_line_categories():
    item = LineItem(
        description="JASA ANGKUT GERMAN TO JAKARTA",
        amount=Decimal("19927250"),
        cost_category=CostCategory.LOG,
    )
    assert item.cost_category is CostCategory.LOG
    assert item.expense_category is None


def test_line_item_categories_default_to_none():
    item = LineItem(description="STAMP", amount=Decimal("10000"))
    assert item.cost_category is None
    assert item.expense_category is None


def test_line_item_round_trips_through_json():
    item = LineItem(
        description="STAMP",
        amount=Decimal("10000"),
        expense_category=ExpenseCategory.OTHER_OPERATIONAL,
    )
    dumped = item.model_dump(mode="json")
    assert dumped["expense_category"] == "OTHER_OPERATIONAL"
    assert LineItem.model_validate(dumped).expense_category is ExpenseCategory.OTHER_OPERATIONAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_line_item_category_schema.py -v -p no:cacheprovider`
Expected: FAIL — `LineItem` has no `cost_category` (extra="forbid").

- [ ] **Step 3: Add the fields**

In `backend/src/schemas/document.py`, add the import and the two fields. At the top of the file the enum import currently brings in other names; add:

```python
from src.models.enums import CostCategory, ExpenseCategory
```

Then inside `class LineItem`, after `line_total`:

```python
    amount: Optional[Decimal] = None
    line_total: Optional[Decimal] = None
    cost_category: Optional[CostCategory] = None
    expense_category: Optional[ExpenseCategory] = None
```

(Keep the existing `sync_amount_and_line_total` validator unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_line_item_category_schema.py -v -p no:cacheprovider`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add backend/src/schemas/document.py backend/tests/unit/test_line_item_category_schema.py
git commit -m "feat(documents): allow per-line recording categories on LineItem"
```

---

### Task 3: Add service / stamp-duty rules to the expense classifier

**Files:**
- Modify: `backend/src/services/documents/expense_classifier.py`
- Test: `backend/tests/unit/test_expense_classifier_services.py` (create)

**Interfaces:**
- Produces: `classify_expense("JASA ANGKUT ...")` → `cost_category=CostCategory.LOG`; `classify_expense("STAMP")` → `expense_category=ExpenseCategory.OTHER_OPERATIONAL`; `classify_expense("JASA PASANG BEARING")` → `cost_category=CostCategory.SUB`; `classify_expense("JASA PEMBUATAN DOKUMEN")` → `expense_category=ExpenseCategory.OFFICE_ADMIN`; `classify_expense("BIAYA PERIJINAN SBU")` → `expense_category=ExpenseCategory.PERMITS`. Consumed by Task 4.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_expense_classifier_services.py`:

```python
import uuid

from src.models.enums import CostCategory, ExpenseCategory
from src.services.documents.expense_classifier import classify_expense


def test_freight_is_logistics_cost():
    res = classify_expense(raw_description="JASA ANGKUT GERMAN TO JAKARTA")
    assert res.cost_category is CostCategory.LOG


def test_freight_with_a_physical_unit_stays_logistics_not_material():
    # A service word plus a unit ("2 TRUK") must not be read as material (MAT).
    res = classify_expense(raw_description="JASA ANGKUT 2 TRUK KE JAKARTA")
    assert res.cost_category is CostCategory.LOG


def test_stamp_duty_is_operational_expense():
    res = classify_expense(raw_description="STAMP")
    assert res.cost_category is None
    assert res.expense_category is ExpenseCategory.OTHER_OPERATIONAL


def test_stamp_duty_stays_operational_even_with_a_project():
    # Stamp duty is overhead, never HPP, even on a project document.
    res = classify_expense(raw_description="STAMP", matched_project_id=uuid.uuid4())
    assert res.cost_category is None
    assert res.expense_category is ExpenseCategory.OTHER_OPERATIONAL


def test_installation_service_is_subcontractor():
    res = classify_expense(raw_description="JASA PASANG BEARING POMPA")
    assert res.cost_category is CostCategory.SUB


def test_document_service_is_office_admin():
    res = classify_expense(raw_description="JASA PEMBUATAN DOKUMEN PROYEK")
    assert res.cost_category is None
    assert res.expense_category is ExpenseCategory.OFFICE_ADMIN


def test_permit_and_licensing_is_permits_expense():
    # The company's Laba Rugi carries a distinct "BIAYA PERIJINAN *SBU" line, so
    # permits map to the PERMITS account (6105), not OFFICE_ADMIN (6103).
    res = classify_expense(raw_description="BIAYA PERIJINAN SBU")
    assert res.cost_category is None
    assert res.expense_category is ExpenseCategory.PERMITS


def test_document_text_does_not_reclassify_an_unrelated_line():
    # Regression: the service rules must read the line's own text, never the
    # whole document, or a document-level "materai" keyword would hijack the
    # freight line (and the document-level candidate's category).
    res = classify_expense(
        raw_description="JASA ANGKUT GERMAN TO JAKARTA",
        document_text="INVOICE\nJASA ANGKUT GERMAN TO JAKARTA\nMETERAI TEMPEL 10.000",
    )
    assert res.cost_category is CostCategory.LOG
    assert res.expense_category is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_expense_classifier_services.py -v -p no:cacheprovider`
Expected: FAIL — freight/stamp fall through to the default (`OTHER_OPERATIONAL` or `MAT`).

- [ ] **Step 3: Add the regex matchers**

In `backend/src/services/documents/expense_classifier.py`, after `_RE_OFFICE_INDICATOR` (line ~80), add:

```python
_RE_STAMP_DUTY = re.compile(
    r"\b(?:materai|meterai|stamp|tempel)\b",
    re.IGNORECASE,
)
_RE_DOC_SERVICE = re.compile(
    r"\b(?:jasa\s+pembuatan\s+dokumen|pembuatan\s+dokumen|administrasi)\b",
    re.IGNORECASE,
)
_RE_PERMITS = re.compile(
    r"\b(?:perizinan|perijinan|izin|legalitas|notaris|sertifikasi|sbu)\b",
    re.IGNORECASE,
)
_RE_FREIGHT = re.compile(
    r"\b(?:jasa\s+angkut|angkut|kirim|pengiriman|ekspedisi|freight|logistik|ongkos\s+kirim|kargo)\b",
    re.IGNORECASE,
)
_RE_INSTALLATION = re.compile(
    r"\b(?:pasang|pemasangan|instalasi|instal|bearing|servis|perbaikan|maintenance|subkon|subkontraktor)\b",
    re.IGNORECASE,
)
```

- [ ] **Step 4: Add the classification section**

In `classify_expense`, insert this block immediately **before** `# 3. Default fallback classification` (line ~234):

```python
    # 2b. Service / stamp-duty classification (LINE-SCOPED: search `raw`, the
    # item's own text, never the whole document). A document-level keyword like
    # "materai" must not reclassify an unrelated "JASA ANGKUT" line, and must not
    # hijack the document-level candidate's category/project.
    # Stamp duty and document preparation are administrative overhead, never HPP,
    # even when the document carries a project.
    if _RE_STAMP_DUTY.search(raw):
        signals.append("STAMP_DUTY_KEYWORD_DETECTED")
        return ExpenseClassificationResult(
            raw_description=raw,
            normalized_description="Materai / Stamp Duty",
            project_id=None,
            project_confidence=Decimal("0.00"),
            management_category="Materai",
            cost_category=None,
            expense_category=ExpenseCategory.OTHER_OPERATIONAL,
            proposed_account_or_rule="6199 - Beban Operasional Lainnya",
            classification_confidence=Decimal("0.85"),
            classification_signals=signals,
            classification_conflicts=conflicts,
            review_required=review_required,
        )

    if _RE_DOC_SERVICE.search(raw):
        signals.append("DOCUMENT_SERVICE_KEYWORD_DETECTED")
        return ExpenseClassificationResult(
            raw_description=raw,
            normalized_description="Jasa Pembuatan Dokumen / Administrasi",
            project_id=None,
            project_confidence=Decimal("0.00"),
            management_category="Jasa Administrasi",
            cost_category=None,
            expense_category=ExpenseCategory.OFFICE_ADMIN,
            proposed_account_or_rule="6103 - Beban Operasional Kantor dan Administrasi",
            classification_confidence=Decimal("0.80"),
            classification_signals=signals,
            classification_conflicts=conflicts,
            review_required=review_required,
        )

    if _RE_PERMITS.search(raw):
        signals.append("PERMITS_KEYWORD_DETECTED")
        return ExpenseClassificationResult(
            raw_description=raw,
            normalized_description="Perizinan / Legalitas",
            project_id=None,
            project_confidence=Decimal("0.00"),
            management_category="Perizinan & Legalitas",
            cost_category=None,
            expense_category=ExpenseCategory.PERMITS,
            proposed_account_or_rule="6105 - Beban Legal, Perizinan, dan Sertifikasi Perusahaan",
            classification_confidence=Decimal("0.80"),
            classification_signals=signals,
            classification_conflicts=conflicts,
            review_required=review_required,
        )

    # Freight and installation are project services -> HPP (5101) when a project
    # is known; without a project the reviewer must supply one (approval rejects).
    if _RE_FREIGHT.search(raw):
        signals.append("FREIGHT_KEYWORD_DETECTED")
        return ExpenseClassificationResult(
            raw_description=raw,
            normalized_description="Jasa Angkut / Ekspedisi",
            project_id=matched_project_id,
            project_confidence=Decimal("0.90") if matched_project_id else Decimal("0.60"),
            management_category="Jasa Logistik Proyek",
            cost_category=CostCategory.LOG,
            expense_category=None,
            proposed_account_or_rule="5101 - Harga Pokok Proyek (Logistik)",
            classification_confidence=Decimal("0.85"),
            classification_signals=signals,
            classification_conflicts=conflicts,
            review_required=review_required or (matched_project_id is None),
        )

    if _RE_INSTALLATION.search(raw):
        signals.append("INSTALLATION_KEYWORD_DETECTED")
        return ExpenseClassificationResult(
            raw_description=raw,
            normalized_description="Jasa Pemasangan / Subkontraktor",
            project_id=matched_project_id,
            project_confidence=Decimal("0.90") if matched_project_id else Decimal("0.60"),
            management_category="Jasa Pemasangan Proyek",
            cost_category=CostCategory.SUB,
            expense_category=None,
            proposed_account_or_rule="5101 - Harga Pokok Proyek (Subkontraktor)",
            classification_confidence=Decimal("0.85"),
            classification_signals=signals,
            classification_conflicts=conflicts,
            review_required=review_required or (matched_project_id is None),
        )
```

- [ ] **Step 5: Run new tests, then reconcile any pinned expectations**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_expense_classifier_services.py -v -p no:cacheprovider`
Expected: PASS (8).

Then run the existing classifier suite:
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit -k "classif" -v -p no:cacheprovider`
If any existing test now fails because a fixture description intentionally changed category, update that assertion deliberately and note it in the commit message. If a failure is NOT explained by the new rules, STOP and investigate.

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/documents/expense_classifier.py backend/tests/unit/test_expense_classifier_services.py
git commit -m "feat(documents): classify freight, installation, stamp duty and document services"
```

---

### Task 4: Per-line classification service

**Files:**
- Create: `backend/src/services/documents/line_item_classifier.py`
- Test: `backend/tests/unit/test_line_item_classifier.py` (create)

**Interfaces:**
- Consumes: `classify_expense` (Task 3), `LineItem` (Task 2).
- Produces: `classify_line_items(items: List[LineItem], project_id: Optional[uuid.UUID]) -> List[LineItem]` — returns copies of the items with `cost_category`/`expense_category` filled when the item has none (an existing reviewer choice is never overwritten). Each line is classified from its OWN description only (no document text), so a document-level keyword never reclassifies an unrelated line. Consumed by Task 5.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_line_item_classifier.py`:

```python
import uuid
from decimal import Decimal

from src.models.enums import CostCategory, ExpenseCategory
from src.schemas.document import LineItem
from src.services.documents.line_item_classifier import classify_line_items


def test_suggests_log_for_freight_and_operational_for_stamp():
    items = [
        LineItem(description="JASA ANGKUT GERMAN TO JAKARTA", amount=Decimal("19927250")),
        LineItem(description="STAMP", amount=Decimal("10000")),
    ]
    out = classify_line_items(items, project_id=None)
    assert out[0].cost_category is CostCategory.LOG
    assert out[1].expense_category is ExpenseCategory.OTHER_OPERATIONAL
    assert out[1].cost_category is None


def test_never_overwrites_an_existing_reviewer_choice():
    items = [
        LineItem(
            description="JASA ANGKUT GERMAN TO JAKARTA",
            amount=Decimal("1000"),
            cost_category=CostCategory.SUB,
        )
    ]
    out = classify_line_items(items, project_id=None)
    assert out[0].cost_category is CostCategory.SUB


def test_preserves_amount_and_description():
    items = [LineItem(description="STAMP", amount=Decimal("10000"))]
    out = classify_line_items(items, project_id=uuid.uuid4())
    assert out[0].amount == Decimal("10000")
    assert out[0].description == "STAMP"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_line_item_classifier.py -v -p no:cacheprovider`
Expected: FAIL — module `line_item_classifier` does not exist.

- [ ] **Step 3: Write the module**

Create `backend/src/services/documents/line_item_classifier.py`:

```python
"""Suggest a recording category for each invoice line item.

OCR proposes, the reviewer decides: this only fills a category when the line has
none, so an explicit reviewer choice is never overwritten.
"""
import uuid
from typing import List, Optional

from src.schemas.document import LineItem
from src.services.documents.expense_classifier import classify_expense


def classify_line_items(
    items: List[LineItem],
    project_id: Optional[uuid.UUID] = None,
) -> List[LineItem]:
    classified: List[LineItem] = []
    for item in items:
        if item.cost_category is not None or item.expense_category is not None:
            classified.append(item)
            continue
        result = classify_expense(
            raw_description=item.description or "",
            matched_project_id=project_id,
        )
        classified.append(
            item.model_copy(
                update={
                    "cost_category": result.cost_category,
                    "expense_category": result.expense_category,
                }
            )
        )
    return classified
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_line_item_classifier.py -v -p no:cacheprovider`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/documents/line_item_classifier.py backend/tests/unit/test_line_item_classifier.py
git commit -m "feat(documents): suggest recording category per line item"
```

---

### Task 5: Fill per-line suggestions when building the candidate

**Files:**
- Modify: `backend/src/services/documents/candidate.py` (`build_candidate`, lines 66-100)
- Modify: `backend/src/services/documents/pipeline.py` (re-serialise `extracted_data` after `build_candidate`, line ~78)
- Test: `backend/tests/unit/test_candidate_line_item_categories.py` (create)

**Interfaces:**
- Consumes: `classify_line_items` (Task 4).
- Produces: after `build_candidate`, `data.line_items` each carry a suggested category, AND the caller persists them: `pipeline.py` re-serialises `document.extracted_data` from `data` after calling `build_candidate`, so `extracted_data["line_items"]` (what Task 6/7 read) carries the suggestions. The document-level `cost_category`/`expense_category` summary stays as today.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_candidate_line_item_categories.py`:

```python
import uuid
from decimal import Decimal

from src.models.enums import CostCategory, DocumentType, ExpenseCategory
from src.schemas.document import LineItem, StructuredExtraction
from src.services.documents.candidate import build_candidate


def _extraction():
    return StructuredExtraction(
        transaction_date="2026-09-14",
        total_amount=Decimal("19937250"),
        line_items=[
            LineItem(description="JASA ANGKUT GERMAN TO JAKARTA", amount=Decimal("19927250")),
            LineItem(description="STAMP", amount=Decimal("10000")),
        ],
    )


def test_build_candidate_suggests_category_per_line():
    data = _extraction()
    build_candidate(
        document_id=uuid.uuid4(),
        document_type=DocumentType.VENDOR_INVOICE,
        data=data,
        matches={},
        flags=[],
    )
    assert data.line_items[0].cost_category is CostCategory.LOG
    assert data.line_items[1].expense_category is ExpenseCategory.OTHER_OPERATIONAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_candidate_line_item_categories.py -v -p no:cacheprovider`
Expected: FAIL — line categories stay `None`.

- [ ] **Step 3: Call the per-line classifier**

In `backend/src/services/documents/candidate.py`, add the import:

```python
from src.services.documents.line_item_classifier import classify_line_items
```

In the `elif document_type in {DocumentType.RECEIPT, DocumentType.VENDOR_INVOICE}:` branch, after `matches["expense_classification"] = exp_res.to_dict()` (line ~85), add:

```python
        if data.line_items:
            data.line_items = classify_line_items(
                data.line_items,
                project_id=matched_pid,
            )
```

- [ ] **Step 3b: Persist the classified extraction in the pipeline**

`document.extracted_data` is serialised in `pipeline.py` (line ~49) BEFORE `build_candidate` runs (line ~78), so without this step the per-line suggestions live only in the in-memory `data` and never reach the persisted JSON that Task 6/7 read. Immediately after the `candidate = build_candidate(...)` line (~78) in `backend/src/services/documents/pipeline.py`, re-serialise:

```python
            document.extracted_data = data.model_dump(mode="json")
```

Add a regression test `backend/tests/integration/test_pipeline_line_item_categories.py` that drives `DocumentPipeline` with a scripted provider (copy the `ScriptedExtractionProvider` pattern from `tests/integration/test_uat13_real_document_extraction.py`) returning a 2-line VENDOR_INVOICE (`JASA ANGKUT...` + `STAMP`), runs `.process(...)`, and asserts the persisted `document.extracted_data["line_items"][0]["cost_category"] == "LOG"` and `["line_items"][1]["expense_category"] == "OTHER_OPERATIONAL"`. This test fails without Step 3b.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_candidate_line_item_categories.py tests/integration/test_pipeline_line_item_categories.py -v -p no:cacheprovider`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/documents/candidate.py backend/src/services/documents/pipeline.py backend/tests/unit/test_candidate_line_item_categories.py backend/tests/integration/test_pipeline_line_item_categories.py
git commit -m "feat(documents): attach and persist per-line category suggestions"
```

---

### Task 6: Accept `line_items` through the corrections endpoint

**Files:**
- Modify: `backend/src/api/v1/documents.py` (`allowed` set line 251-259; sync block lines 339-357)
- Test: `backend/tests/unit/test_corrections_accepts_line_items.py` (create)

**Interfaces:**
- Consumes: nothing new.
- Produces: `POST /documents/{id}/corrections` accepts a `changes["line_items"]` list and stores it in `document.extracted_data["line_items"]` (so Task 7 can read it). Without this, sending line items returns 422.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_corrections_accepts_line_items.py`:

```python
"""The corrections endpoint must accept a corrected line_items list.

Regression guard: `line_items` was absent from the `allowed` whitelist, so a
reviewer editing per-line categories got a 422 and the change was lost.
"""
from src.api.v1.documents import ALLOWED_CORRECTION_FIELDS


def test_line_items_is_an_allowed_correction_field():
    assert "line_items" in ALLOWED_CORRECTION_FIELDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_corrections_accepts_line_items.py -v -p no:cacheprovider`
Expected: FAIL — `ALLOWED_CORRECTION_FIELDS` does not exist.

- [ ] **Step 3: Extract the whitelist to a module constant and add line_items**

In `backend/src/api/v1/documents.py`, replace the inline `allowed = { ... }` set (lines 251-259) with a module-level constant defined near the top of the file (after `router = APIRouter(...)`):

```python
ALLOWED_CORRECTION_FIELDS = {
    "project_id", "counterparty_id", "payment_account_id", "allocation_target_id",
    "selected_candidate_id", "proposed_transaction_type", "cost_category",
    "expense_category", "transaction_date", "date", "amount", "total_amount",
    "subtotal", "tax", "vat_amount", "description", "external_reference",
    "transfer_reference", "document_number", "invoice_number", "spk_number",
    "bast_number", "due_date", "document_type", "origin_bank", "destination_bank",
    "destination_account_number", "line_items",
}
```

Then in the endpoint replace the local `allowed` usage:

```python
    if not data.changes or set(data.changes) - ALLOWED_CORRECTION_FIELDS:
        raise HTTPException(status_code=422, detail="Correction contains unsupported fields")
```

In the extracted-field sync block, add `line_items` to the persisted fields. After the `for ext_field in (...)` loop (line ~343), add:

```python
    if "line_items" in data.changes:
        extracted["line_items"] = data.changes["line_items"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_corrections_accepts_line_items.py -v -p no:cacheprovider`
Expected: PASS (1).

Then confirm no regression in the correction tests:
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests -k "correction" -q -p no:cacheprovider`
Expected: no `FAILED` lines.

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/v1/documents.py backend/tests/unit/test_corrections_accepts_line_items.py
git commit -m "feat(documents): accept corrected line_items in the corrections endpoint"
```

---

### Task 7: Post one invoice across several accounts (multi-allocation on approve)

**Files:**
- Modify: `backend/src/services/document_posting_service.py` (add `build_line_allocations`, use it at line ~425-446)
- Test: `backend/tests/unit/test_posting_line_allocations.py` (create)

**Interfaces:**
- Consumes: `document.extracted_data["line_items"]` with per-line categories (Tasks 2, 5, 6); `TransactionAllocationInput` from `src/schemas/transaction.py`.
- Produces: `build_line_allocations(extracted_data: dict, candidate) -> Optional[List[TransactionAllocationInput]]` — groups lines by `(project_id, cost_category, expense_category)`, sums each group, returns `None` when there are no categorised lines (fallback to the current single-category path).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_posting_line_allocations.py`:

```python
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.exceptions import InvariantViolationException
from src.models.enums import CostCategory, ExpenseCategory
from src.services.document_posting_service import build_line_allocations


def _candidate(project_id=None):
    return SimpleNamespace(
        project_id=project_id,
        cost_category=CostCategory.MAT,
        expense_category=None,
        amount=Decimal("19937250"),
    )


def test_groups_lines_by_category_and_sums_each_group():
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "19927250", "cost_category": "LOG"},
            {"description": "STAMP", "amount": "10000", "expense_category": "OTHER_OPERATIONAL"},
        ]
    }
    allocs = build_line_allocations(extracted, _candidate(project_id=project_id))
    assert allocs is not None
    assert len(allocs) == 2
    by_cat = {a.cost_category or a.expense_category: a.amount for a in allocs}
    assert by_cat[CostCategory.LOG] == Decimal("19927250")
    assert by_cat[ExpenseCategory.OTHER_OPERATIONAL] == Decimal("10000")
    assert sum(a.amount for a in allocs) == Decimal("19937250")


def test_same_category_lines_are_merged_into_one_allocation():
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "SEMEN", "amount": "100", "cost_category": "MAT"},
            {"description": "BESI", "amount": "200", "cost_category": "MAT"},
            {"description": "JASA ANGKUT", "amount": "50", "cost_category": "LOG"},
        ]
    }
    cand = _candidate(project_id=project_id)
    cand.amount = Decimal("350")
    allocs = build_line_allocations(extracted, cand)
    assert len(allocs) == 2
    by_cat = {a.cost_category: a.amount for a in allocs}
    assert by_cat[CostCategory.MAT] == Decimal("300")
    assert by_cat[CostCategory.LOG] == Decimal("50")


def test_single_bucket_invoice_keeps_the_legacy_path():
    # Regression: the per-line classifier fills EVERY line, so a legacy invoice
    # (e.g. a PPN invoice whose extracted lines are the pre-VAT subtotal) would
    # otherwise be forced through the multi-allocation sum guard and hard-fail on
    # approve. A document whose lines all collapse to ONE bucket is not a
    # multi-account split — return None so the legacy path posts the full total.
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "SEMEN", "amount": "100000", "cost_category": "MAT"},
        ]
    }
    cand = _candidate(project_id=project_id)
    cand.amount = Decimal("111000")  # line 100000 != total 111000 (PPN)
    assert build_line_allocations(extracted, cand) is None


def test_multi_bucket_sum_mismatch_is_rejected():
    # A genuine multi-account split whose lines do not reconcile to the invoice
    # total must be refused (spec D5), not posted with a missing amount.
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "100", "cost_category": "LOG"},
            {"description": "STAMP", "amount": "10", "expense_category": "OTHER_OPERATIONAL"},
        ]
    }
    cand = _candidate(project_id=project_id)
    cand.amount = Decimal("200")
    with pytest.raises(InvariantViolationException):
        build_line_allocations(extracted, cand)


def test_returns_none_when_no_line_items():
    assert build_line_allocations({"line_items": []}, _candidate()) is None


def test_returns_none_when_no_category_anywhere():
    # No line category AND no document-level category -> keep legacy single path.
    extracted = {"line_items": [{"description": "X", "amount": "100"}]}
    bare = SimpleNamespace(
        project_id=None, cost_category=None, expense_category=None, amount=Decimal("100")
    )
    assert build_line_allocations(extracted, bare) is None


def test_uncategorised_lines_fall_back_to_document_category():
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "100", "cost_category": "LOG"},
            {"description": "NO CATEGORY", "amount": "50"},
        ]
    }
    cand = _candidate(project_id=project_id)
    cand.amount = Decimal("150")
    allocs = build_line_allocations(extracted, cand)
    by_cat = {a.cost_category or a.expense_category: a.amount for a in allocs}
    assert by_cat[CostCategory.LOG] == Decimal("100")
    assert by_cat[CostCategory.MAT] == Decimal("50")
    assert all(a.project_id == project_id for a in allocs)


def test_operational_line_does_not_inherit_the_project():
    # posting_rules debits 5101 when an allocation has a project_id, else the
    # expense category's own account. An operational line on a project invoice
    # must therefore keep project_id=None, or it would book to HPP (5101).
    project_id = uuid.uuid4()
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "19927250", "cost_category": "LOG"},
            {"description": "STAMP", "amount": "10000", "expense_category": "OTHER_OPERATIONAL"},
        ]
    }
    allocs = build_line_allocations(extracted, _candidate(project_id=project_id))
    by_cat = {a.cost_category or a.expense_category: a for a in allocs}
    assert by_cat[CostCategory.LOG].project_id == project_id
    assert by_cat[ExpenseCategory.OTHER_OPERATIONAL].project_id is None


def test_hpp_category_without_project_is_rejected():
    # A project-cost line with no project would silently book to 6199 in
    # posting_rules; refuse it here instead of posting to the wrong account.
    extracted = {
        "line_items": [
            {"description": "JASA ANGKUT", "amount": "100", "cost_category": "LOG"},
        ]
    }
    with pytest.raises(InvariantViolationException):
        build_line_allocations(extracted, _candidate(project_id=None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_posting_line_allocations.py -v -p no:cacheprovider`
Expected: FAIL — `build_line_allocations` does not exist.

- [ ] **Step 3: Add the allocation builder**

In `backend/src/services/document_posting_service.py`, the file already imports `uuid`, `Decimal`, `Optional`, `CostCategory` and `ExpenseCategory` (lines 3-30). Add ONLY the missing names:

```python
from typing import Dict, List, Set, Tuple   # was: from typing import Optional, Set
from src.schemas.transaction import TransactionAllocationInput
from src.services.recording_categories import PROJECT_REQUIRED_COST_CATEGORIES
```

(Keep the existing `from typing import Optional, Set` → extend it to include `Dict`, `List`, `Tuple`.)

Add the function at module level (e.g. after `DocumentPostingResult`):

```python
def build_line_allocations(
    extracted_data: dict,
    candidate,
) -> Optional[List[TransactionAllocationInput]]:
    """Group invoice line items into one allocation per (project, cost, expense) bucket.

    Returns None unless the invoice GENUINELY spans more than one allocation
    bucket — a single-bucket document is not a multi-account split, so the caller
    keeps the existing single-category behaviour. This matters because the
    per-line classifier fills EVERY line (MAT when a project is present, else
    OTHER_OPERATIONAL): a legacy invoice never reviewed per line must not be
    forced through the multi-allocation sum guard. Uncategorised lines inherit
    the document-level category so their amount is never dropped.
    """
    items = (extracted_data or {}).get("line_items") or []
    if not items:
        return None

    groups: Dict[Tuple[Optional[str], Optional[str], Optional[str]], Decimal] = {}
    for item in items:
        raw_amount = item.get("amount")
        if raw_amount is None:
            raw_amount = item.get("line_total")
        if raw_amount is None:
            continue

        cost_raw = item.get("cost_category") or (
            candidate.cost_category.value if candidate.cost_category else None
        )
        expense_raw = item.get("expense_category") or (
            candidate.expense_category.value if candidate.expense_category else None
        )
        # A line may not carry both; prefer the explicit cost category.
        if item.get("cost_category"):
            expense_raw = None
        elif item.get("expense_category"):
            cost_raw = None

        # posting_rules routes by PROJECT PRESENCE: a project-cost line (cost
        # category) debits 5101, an operational line (expense category) debits
        # its 610x/6199 account. So only a project-cost line may carry the
        # project; an operational line must NOT inherit it — otherwise it would
        # book to 5101 (HPP). Mirrors candidate.py's resolved_proj_id rule.
        if cost_raw:
            project_raw = str(candidate.project_id) if candidate.project_id else None
        else:
            project_raw = None
        key = (project_raw, cost_raw, expense_raw)
        groups[key] = groups.get(key, Decimal("0.00")) + Decimal(str(raw_amount))

    if not groups:
        return None
    # No category anywhere (neither line nor document): keep the legacy path.
    if all(key[1] is None and key[2] is None for key in groups):
        return None

    # A project-cost category (MAT/SUB/TRN/EQP/LOG) without a project would fall
    # through to 6199 in posting_rules; refuse rather than book to the wrong
    # account. Checked before the single-bucket gate so it holds for one-line
    # documents too.
    for project_raw, cost_raw, _expense_raw in groups:
        if cost_raw in PROJECT_REQUIRED_COST_CATEGORIES and not project_raw:
            raise InvariantViolationException(
                f"Project is required for project cost category {cost_raw}.",
                details={"failure_reason": "ALLOCATION_INVALID"},
            )

    # Only a genuine multi-bucket invoice is split across allocations. A document
    # whose lines all collapse to one (project, cost, expense) bucket posts via the
    # legacy single-category path instead — this avoids hard-failing legacy
    # invoices whose extracted lines (e.g. pre-PPN amounts) do not sum to the total.
    if len(groups) < 2:
        return None

    allocations = [
        TransactionAllocationInput(
            project_id=uuid.UUID(key[0]) if key[0] else None,
            cost_category=CostCategory(key[1]) if key[1] else None,
            expense_category=ExpenseCategory(key[2]) if key[2] else None,
            amount=amount,
        )
        for key, amount in groups.items()
    ]

    # Spec D5: a genuine multi-account split must reconcile to the invoice total,
    # or an amount would be silently dropped. Refuse rather than post a partial.
    allocation_sum = sum(a.amount for a in allocations)
    if allocation_sum != candidate.amount:
        raise InvariantViolationException(
            f"Sum of line allocations ({allocation_sum}) does not match invoice total ({candidate.amount}).",
            details={"failure_reason": "ALLOCATION_INVALID"},
        )

    return allocations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_posting_line_allocations.py -v -p no:cacheprovider`
Expected: PASS (9).

- [ ] **Step 5: Use the allocations in the approve path**

In `backend/src/services/document_posting_service.py`, replace the `trx_input = TransactionCreate(...)` block (lines ~426-440) with:

```python
        # 8. Create Transaction via canonical TransactionService
        # build_line_allocations returns None for documents that do not genuinely
        # span multiple accounts (and raises on a non-reconciling split), so the
        # legacy single-category path is used for everything else.
        line_allocations = build_line_allocations(document.extracted_data or {}, candidate)
        if line_allocations is not None:
            trx_input = TransactionCreate(
                transaction_type=candidate.proposed_transaction_type,
                transaction_date=candidate.transaction_date,
                amount=candidate.amount,
                currency=candidate.currency_code or "IDR",
                counterparty_id=candidate.counterparty_id,
                payment_account_id=candidate.payment_account_id,
                reference_no=candidate.external_reference,
                description=candidate.description or f"Converted from {document.document_code}",
                document_ids=[document.id],
                source_channel=document.source_channel,
                allocations=line_allocations,
            )
        else:
            trx_input = TransactionCreate(
                transaction_type=candidate.proposed_transaction_type,
                transaction_date=candidate.transaction_date,
                amount=candidate.amount,
                currency=candidate.currency_code or "IDR",
                counterparty_id=candidate.counterparty_id,
                payment_account_id=candidate.payment_account_id,
                project_id=candidate.project_id,
                cost_category=candidate.cost_category,
                expense_category=candidate.expense_category,
                reference_no=candidate.external_reference,
                description=candidate.description or f"Converted from {document.document_code}",
                document_ids=[document.id],
                source_channel=document.source_channel,
            )
```

Ensure `InvariantViolationException` is imported (it is used elsewhere in the file; if not, add `from src.core.exceptions import InvariantViolationException`).

- [ ] **Step 6: Run the backend tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit -q -p no:cacheprovider`
Expected: no `FAILED` lines (the new 9 pass; pre-existing skips remain).

- [ ] **Step 7: Commit**

```bash
git add backend/src/services/document_posting_service.py backend/tests/unit/test_posting_line_allocations.py
git commit -m "feat(documents): post one invoice across multiple accounts per line item"
```

---

### Task 8: Per-line "Jenis Pencatatan" picker in the review form

**Files:**
- Modify: `frontend/src/components/documents/DocumentReviewForm.tsx` (line-items table, lines ~682-720; `buildCurrentChanges`, lines ~202-258)
- Modify: `frontend/src/utils/documentReview.ts` (validation)
- Test: `frontend/tests/components/DocumentReviewLineItemCategories.test.tsx` (create)

**Interfaces:**
- Consumes: `RECORDING_CATEGORIES` (`frontend/src/utils/recordingCategories.ts`), `lineItems` from `extracted.line_items`.
- Produces: the review table shows a per-row category `<select>`; on save/approve the corrected `line_items` (with `cost_category`/`expense_category`) are sent in `changes`. No change to `frontend/src/api/documents.ts`: `correct(id, changes, reason)` already forwards the `changes` object verbatim.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/components/DocumentReviewLineItemCategories.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';

vi.mock('../../src/api/documents', () => ({
  documentsApi: { correct: vi.fn(), approve: vi.fn(), reject: vi.fn() },
}));

const document = {
  id: 'doc-1',
  document_code: 'DOC-2026-000016',
  document_type: 'VENDOR_INVOICE',
  processing_status: 'REVIEW_REQUIRED',
  review_flags: [],
  confidence_scores: {},
  extracted_data: {
    total_amount: '19937250',
    transaction_date: '2026-09-14',
    line_items: [
      { description: 'JASA ANGKUT GERMAN TO JAKARTA', amount: '19927250', cost_category: 'LOG' },
      { description: 'STAMP', amount: '10000', expense_category: 'OTHER_OPERATIONAL' },
    ],
  },
  candidate_transaction: { id: 'c1', amount: '19937250', transaction_date: '2026-09-14' },
  matching_results: {},
} as never;

describe('DocumentReviewForm per-line categories', () => {
  it('renders a category selector for each line item', () => {
    render(
      <DocumentReviewForm
        document={document}
        projects={[]}
        counterparties={[]}
        onSave={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    const rows = screen.getAllByTestId('line-item-row');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByLabelText(/jenis pencatatan/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/components/DocumentReviewLineItemCategories.test.tsx`
Expected: FAIL — no `line-item-row` test ids / no per-line selector.

- [ ] **Step 3: Add per-line state and the selector**

In `frontend/src/components/documents/DocumentReviewForm.tsx`:

Add near the other `useState` declarations (around line 129):

```tsx
  const [lineItemCategories, setLineItemCategories] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      (Array.isArray(extracted.line_items) ? (extracted.line_items as Record<string, unknown>[]) : []).map(
        (item, idx) => [idx, String(item.cost_category ?? item.expense_category ?? '')],
      ),
    ),
  );
```

In the line-items table `<tbody>` row, add `data-testid="line-item-row"` to the `<tr>` and insert a new cell after the description cell:

```tsx
                    <td className="px-3 py-1.5">
                      <select
                        aria-label="Jenis Pencatatan"
                        className="rounded border border-slate-300 text-[11px] px-1 py-0.5"
                        value={lineItemCategories[idx] ?? ''}
                        onChange={(e) =>
                          setLineItemCategories((prev) => ({ ...prev, [idx]: e.target.value }))
                        }
                      >
                        <option value="">— pilih —</option>
                        {RECORDING_CATEGORIES.map((c) => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    </td>
```

Add a table header cell matching the new column (after the description `<th>`):

```tsx
                  <th className="px-3 py-1.5">Jenis Pencatatan</th>
```

- [ ] **Step 4: Send the corrected line items on save/approve**

In `DocumentReviewForm.tsx`, inside `buildCurrentChanges` (the function that assembles `changes`, around line 202-258 — **not** the `validateDocumentReviewForm` call), add before `return { changes, isDirty };`:

```tsx
    const items = Array.isArray(extracted.line_items)
      ? (extracted.line_items as Record<string, unknown>[])
      : [];
    if (items.length > 0) {
      const corrected = items.map((item, idx) => {
        const selected = RECORDING_CATEGORIES.find((c) => c.value === lineItemCategories[idx]);
        return {
          ...item,
          cost_category: selected?.costCategory ?? null,
          expense_category: selected?.expenseCategory ?? null,
        };
      });
      changes.line_items = corrected;
      isDirty = true;
    }
```

(`lineItemCategories` is declared with the other `useState` hooks earlier in the component, so it is in scope here.)

- [ ] **Step 5: Validate HPP lines require a project**

In `frontend/src/utils/documentReview.ts`, add (and export) a helper and call it where the form validates before approve:

```ts
import { PROJECT_REQUIRED_COST_CATEGORIES } from './recordingCategories';

export function validateLineItemCategories(
  lineItems: Array<Record<string, unknown>>,
  projectId: string | null | undefined,
): string | null {
  const needsProject = lineItems.some((item) =>
    PROJECT_REQUIRED_COST_CATEGORIES.includes(String(item.cost_category ?? '')),
  );
  if (needsProject && !projectId) {
    return 'Setiap baris HPP (barang/jasa proyek) memerlukan proyek.';
  }
  return null;
}
```

- [ ] **Step 6: Run frontend tests and gates**

Run: `cd frontend && npx vitest run tests/components/DocumentReviewLineItemCategories.test.tsx`
Expected: PASS.

Then the full gates:
Run: `cd frontend && npx tsc -p tsconfig.json --noEmit && npx vitest run`
Expected: no failures. If a pre-existing review test asserts exact table markup, update it to include the new column.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/documents/DocumentReviewForm.tsx frontend/src/utils/documentReview.ts frontend/tests/components/DocumentReviewLineItemCategories.test.tsx
git commit -m "feat(documents): per-line recording category picker in the review form"
```

---

## Final Verification

- [ ] **Backend full unit + security suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit tests/security -q -p no:cacheprovider`
Expected: all pass except pre-existing skips; no `FAILED`.

- [ ] **Frontend gates**

Run: `cd frontend && npx tsc -p tsconfig.json --noEmit && npx vitest run && npx vite build`
Expected: clean type-check, all tests pass, successful build.

- [ ] **End-to-end sanity (real document)**

Re-run the extraction on `DOC-2026-000016`'s stored OCR text and confirm 2 line items, then confirm the approve path would build 2 allocations (LOG → 5101, OTHER_OPERATIONAL → 6199) summing to 19.937.250.
