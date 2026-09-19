"""Deterministic Multi-Signal Expense Classification Engine.

Implements Sections 14-20 & 30 of WhatsApp Document Session & Expense Classification:
- Distinguishes RAW DESCRIPTION, MANAGEMENT CATEGORY, ACCOUNTING CATEGORY/COA, and PROJECT ALLOCATION.
- Never stores only "Bensin" or "ATK" as the entire accounting decision.
- Direct Project Cost: CostCategory (TRN, SIT, MAT) -> Account 5101 (Harga Pokok Proyek).
- Operational Overhead: ExpenseCategory (TRAVEL_OFFICE, OFFICE_ADMIN) -> Accounts 6103, 6104.
- Ambiguous expenses (e.g. SPBU receipt with no context) -> REVIEW_REQUIRED.
- Caption project mismatch -> REVIEW_REQUIRED (caption is supporting, never overrides evidence).
"""
from dataclasses import dataclass, field
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional
import uuid

from src.models.enums import CostCategory, ExpenseCategory


@dataclass
class ExpenseClassificationResult:
    raw_description: str
    normalized_description: str
    project_id: Optional[uuid.UUID]
    project_confidence: Decimal
    management_category: str
    cost_category: Optional[CostCategory]
    expense_category: Optional[ExpenseCategory]
    proposed_account_or_rule: Optional[str]
    classification_confidence: Decimal
    classification_signals: List[str] = field(default_factory=list)
    classification_conflicts: List[str] = field(default_factory=list)
    review_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_description": self.raw_description,
            "normalized_description": self.normalized_description,
            "project_id": str(self.project_id) if self.project_id else None,
            "project_confidence": float(self.project_confidence),
            "management_category": self.management_category,
            "cost_category": self.cost_category.value if self.cost_category else None,
            "expense_category": self.expense_category.value if self.expense_category else None,
            "proposed_account_or_rule": self.proposed_account_or_rule,
            "classification_confidence": float(self.classification_confidence),
            "classification_signals": self.classification_signals,
            "classification_conflicts": self.classification_conflicts,
            "review_required": self.review_required,
        }


# Regex matchers for expense categories
_RE_FUEL = re.compile(
    r"\b(?:bensin|bbm|pertalite|pertamax|solar|dexlite|spbu|pom\s+bensin|isi\s+bensin)\b",
    re.IGNORECASE,
)
_RE_GENSET = re.compile(
    r"\b(?:genset|generator)\b",
    re.IGNORECASE,
)
_RE_PROJECT_TRANSPORT = re.compile(
    r"\b(?:antar\s+barang|angkut|kirim\s+barang|mobil\s+proyek|logistik|truk\s+proyek)\b",
    re.IGNORECASE,
)
_RE_OFFICE_VEHICLE = re.compile(
    r"\b(?:mobil\s+kantor|operasional\s+kantor|kendaraan\s+kantor|dinas\s+kantor)\b",
    re.IGNORECASE,
)
_RE_STATIONERY = re.compile(
    r"\b(?:kertas|kertas\s+a4|atk|pulpen|spidol|marker|alat\s+tulis|buku\s+tulis|map|toner|tinta\s+printer)\b",
    re.IGNORECASE,
)
_RE_SITE_INDICATOR = re.compile(
    r"\b(?:site|lapangan|proyek|projek)\b",
    re.IGNORECASE,
)
_RE_OFFICE_INDICATOR = re.compile(
    r"\b(?:kantor|office|administrasi)\b",
    re.IGNORECASE,
)
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


def classify_expense(
    raw_description: str,
    caption: Optional[str] = None,
    matched_project_id: Optional[uuid.UUID] = None,
    matched_project_name: Optional[str] = None,
    vendor_name: Optional[str] = None,
    document_text: Optional[str] = None,
    document_project_hint: Optional[str] = None,
) -> ExpenseClassificationResult:
    """Classify an expense document/item into management, accounting, and project dimensions."""
    raw = (raw_description or "").strip()
    cap = (caption or "").strip()
    doc_txt = (document_text or "").strip()
    full_text = f"{raw} {cap} {doc_txt}".lower()

    signals: List[str] = []
    conflicts: List[str] = []
    review_required = False

    # Check for Caption vs Document Project Conflict (Section 17)
    if cap and document_project_hint:
        from src.services.documents.caption_hints import extract_caption_hints
        cap_hints = extract_caption_hints(cap)
        cap_proj = cap_hints.get("project_hint")
        if cap_proj and document_project_hint.lower() not in cap_proj.lower() and cap_proj.lower() not in document_project_hint.lower():
            conflicts.append("CAPTION_PROJECT_MISMATCH")
            signals.append("CAPTION_VS_DOCUMENT_CONFLICT")
            review_required = True

    # 1. Fuel / BBM Classification (Section 15 & 30)
    if _RE_FUEL.search(full_text):
        signals.append("FUEL_KEYWORD_DETECTED")

        # Subcase A: Genset fuel for project
        if _RE_GENSET.search(full_text):
            signals.append("GENSET_KEYWORD_DETECTED")
            has_proj = matched_project_id is not None or _RE_SITE_INDICATOR.search(full_text)
            if has_proj:
                signals.append("PROJECT_SITE_MATCHED")
                return ExpenseClassificationResult(
                    raw_description=raw,
                    normalized_description="Solar Genset Proyek",
                    project_id=matched_project_id,
                    project_confidence=Decimal("0.90") if matched_project_id else Decimal("0.70"),
                    management_category="Bahan Bakar Proyek",
                    cost_category=CostCategory.SIT,
                    expense_category=None,
                    proposed_account_or_rule="5101 - Harga Pokok Proyek (Site Cost)",
                    classification_confidence=Decimal("0.90"),
                    classification_signals=signals,
                    classification_conflicts=conflicts,
                    review_required=review_required or (matched_project_id is None),
                )

        # Subcase B: Project transport / delivery fuel ("Bensin antar barang proyek Ancol")
        has_proj_transport = _RE_PROJECT_TRANSPORT.search(full_text)
        has_proj_context = matched_project_id is not None or _RE_SITE_INDICATOR.search(full_text)

        if has_proj_transport or (has_proj_context and not _RE_OFFICE_VEHICLE.search(full_text)):
            signals.append("PROJECT_TRANSPORT_MATCHED")
            return ExpenseClassificationResult(
                raw_description=raw,
                normalized_description="BBM / Transportasi Proyek",
                project_id=matched_project_id,
                project_confidence=Decimal("0.90") if matched_project_id else Decimal("0.70"),
                management_category="Transportasi Proyek / BBM Proyek",
                cost_category=CostCategory.TRN,
                expense_category=None,
                proposed_account_or_rule="5101 - Harga Pokok Proyek (Transportasi Proyek)",
                classification_confidence=Decimal("0.90"),
                classification_signals=signals,
                classification_conflicts=conflicts,
                review_required=review_required or (matched_project_id is None),
            )

        # Subcase C: Office vehicle fuel ("Bensin mobil kantor")
        if _RE_OFFICE_VEHICLE.search(full_text) or (_RE_OFFICE_INDICATOR.search(full_text) and not has_proj_context):
            signals.append("OFFICE_VEHICLE_MATCHED")
            return ExpenseClassificationResult(
                raw_description=raw,
                normalized_description="BBM Operasional Kantor",
                project_id=None,
                project_confidence=Decimal("0.00"),
                management_category="Operasional Kendaraan",
                cost_category=None,
                expense_category=ExpenseCategory.TRAVEL_OFFICE,
                proposed_account_or_rule="6104 - Beban Transport dan Perjalanan Dinas Non-Proyek",
                classification_confidence=Decimal("0.90"),
                classification_signals=signals,
                classification_conflicts=conflicts,
                review_required=review_required,
            )

        # Subcase D: Ambiguous SPBU receipt with no context (Section 19 & 30)
        signals.append("SPBU_RECEIPT_NO_CONTEXT")
        conflicts.append("PROJECT_OR_OVERHEAD_UNCERTAIN")
        return ExpenseClassificationResult(
            raw_description=raw,
            normalized_description="BBM / Bahan Bakar",
            project_id=None,
            project_confidence=Decimal("0.00"),
            management_category="BBM / Transportasi",
            cost_category=None,
            expense_category=None,
            proposed_account_or_rule=None,
            classification_confidence=Decimal("0.50"),
            classification_signals=signals,
            classification_conflicts=conflicts,
            review_required=True,
        )

    # 2. Stationery / ATK Classification (Section 16 & 30)
    if _RE_STATIONERY.search(full_text):
        signals.append("STATIONERY_KEYWORD_DETECTED")

        # Project / site consumable ("Marker dan kertas untuk site Ancol")
        has_site = _RE_SITE_INDICATOR.search(full_text) or matched_project_id is not None
        if has_site and not _RE_OFFICE_INDICATOR.search(full_text):
            signals.append("SITE_CONSUMABLE_MATCHED")
            return ExpenseClassificationResult(
                raw_description=raw,
                normalized_description="ATK / Perlengkapan Site Proyek",
                project_id=matched_project_id,
                project_confidence=Decimal("0.85") if matched_project_id else Decimal("0.65"),
                management_category="Consumable / ATK Proyek",
                cost_category=CostCategory.SIT,
                expense_category=None,
                proposed_account_or_rule="5101 - Harga Pokok Proyek (Perlengkapan Site)",
                classification_confidence=Decimal("0.85"),
                classification_signals=signals,
                classification_conflicts=conflicts,
                review_required=review_required or (matched_project_id is None),
            )

        # Office stationery ("Kertas A4 printer kantor" or default ATK)
        signals.append("OFFICE_ATK_MATCHED")
        return ExpenseClassificationResult(
            raw_description=raw,
            normalized_description="Perlengkapan / ATK Kantor",
            project_id=None,
            project_confidence=Decimal("0.00"),
            management_category="ATK Kantor",
            cost_category=None,
            expense_category=ExpenseCategory.OFFICE_ADMIN,
            proposed_account_or_rule="6103 - Beban Operasional Kantor dan Administrasi",
            classification_confidence=Decimal("0.90"),
            classification_signals=signals,
            classification_conflicts=conflicts,
            review_required=review_required,
        )

    # 2b. Service / stamp-duty classification (line-item aware)
    # Stamp duty and document preparation are administrative overhead, never HPP,
    # even when the document carries a project.
    if _RE_STAMP_DUTY.search(full_text):
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
            review_required=False,
        )

    if _RE_DOC_SERVICE.search(full_text):
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
            review_required=False,
        )

    if _RE_PERMITS.search(full_text):
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
            review_required=False,
        )

    # Freight and installation are project services -> HPP (5101) when a project
    # is known; without a project the reviewer must supply one (approval rejects).
    if _RE_FREIGHT.search(full_text):
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

    if _RE_INSTALLATION.search(full_text):
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

    # 3. Default fallback classification
    if matched_project_id:
        signals.append("PROJECT_DEFAULT_DIRECT_COST")
        return ExpenseClassificationResult(
            raw_description=raw,
            normalized_description=raw or "Biaya Proyek",
            project_id=matched_project_id,
            project_confidence=Decimal("0.80"),
            management_category="Biaya Langsung Proyek",
            cost_category=CostCategory.MAT,
            expense_category=None,
            proposed_account_or_rule="5101 - Harga Pokok Proyek",
            classification_confidence=Decimal("0.75"),
            classification_signals=signals,
            classification_conflicts=conflicts,
            review_required=review_required,
        )

    signals.append("UNCLASSIFIED_EXPENSE")
    return ExpenseClassificationResult(
        raw_description=raw,
        normalized_description=raw or "Beban Operasional",
        project_id=None,
        project_confidence=Decimal("0.00"),
        management_category="Beban Operasional",
        cost_category=None,
        expense_category=ExpenseCategory.OTHER_OPERATIONAL,
        proposed_account_or_rule="6199 - Beban Operasional Lainnya",
        classification_confidence=Decimal("0.50"),
        classification_signals=signals,
        classification_conflicts=conflicts,
        review_required=True,
    )
