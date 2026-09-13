import re
import uuid
from enum import Enum
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.coa import PaymentAccount
from src.models.payable import VendorBill
from src.models.receivable import CustomerInvoice
from src.models.enums import DocumentType
from src.schemas.document import StructuredExtraction, LineItem


class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MatchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: str
    entity_id: uuid.UUID
    score: Decimal = Field(ge=0, le=1)
    confidence_band: ConfidenceBand
    positive_signals: List[str] = Field(default_factory=list)
    negative_signals: List[str] = Field(default_factory=list)
    explanation: str = ""
    scoring_details: Dict[str, Any] = Field(default_factory=dict)
    target_model: Optional[str] = None


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary_candidate: Optional[MatchCandidate] = None
    ranked_candidates: List[MatchCandidate] = Field(default_factory=list)
    ambiguous: bool = False
    requires_review: bool = False
    explanation: Optional[str] = None


def normalize(value: str | None) -> str:
    """Legacy strict alphanumeric normalization."""
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def normalize_doc_number(value: str | None) -> str:
    """Normalize invoice, bill, PO, or SPK numbers preserving meaningful separators."""
    if not value:
        return ""
    cleaned = value.strip().upper()
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def normalize_party_name(value: str | None) -> str:
    """Normalize legal/counterparty names with conservative punctuation cleanup."""
    if not value:
        return ""
    cleaned = (value or "").casefold()
    cleaned = re.sub(r"[.,\-–—_/()'\"]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_bank_reference(value: str | None) -> str:
    """Normalize bank transfer references and transaction hashes."""
    if not value:
        return ""
    cleaned = value.strip().upper()
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def compute_line_item_overlap(items: List[LineItem], reference_text: str | None) -> float:
    """Compute deterministic overlap ratio of extracted line item descriptions against reference text."""
    if not items or not reference_text:
        return 0.0
    ref_norm = normalize_party_name(reference_text)
    if not ref_norm:
        return 0.0

    matches = 0
    total = len(items)
    for item in items:
        desc_norm = normalize_party_name(item.description)
        tokens = [t for t in desc_norm.split() if len(t) > 2]
        if not tokens:
            continue
        # Count match if at least half of the description tokens appear in the reference text
        token_hits = sum(1 for t in tokens if t in ref_norm)
        if token_hits >= max(1, len(tokens) // 2):
            matches += 1

    return round(matches / total, 4) if total > 0 else 0.0


def _extract_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


async def match_counterparties(
    session: AsyncSession,
    organization_id: uuid.UUID,
    data: StructuredExtraction,
) -> List[MatchCandidate]:
    """Match counterparties scoped strictly to organization_id."""
    stmt = (
        select(Counterparty)
        .where(
            and_(
                Counterparty.organization_id == organization_id,
                Counterparty.is_active.is_(True),
            )
        )
    )
    parties = list((await session.scalars(stmt)).all())
    if not parties:
        return []

    name = data.issuer_name or data.recipient_name
    extracted_name_norm = normalize_party_name(name)
    raw_digits = _extract_digits(data.raw_text)
    dest_acc = normalize(data.destination_account_number)

    candidates: List[MatchCandidate] = []

    for p in parties:
        positive_signals: List[str] = []
        negative_signals: List[str] = []
        scores: Dict[str, float] = {}

        # 1. Tax ID (NPWP) matching
        p_tax_digits = _extract_digits(p.tax_id)
        if p_tax_digits and len(p_tax_digits) >= 15:
            if p_tax_digits in raw_digits:
                positive_signals.append("EXACT_TAX_ID")
                scores["tax_id"] = 1.0

        # 2. Bank account matching
        if dest_acc and p.bank_accounts:
            for acc in p.bank_accounts:
                acc_num = normalize(acc.get("account_number"))
                if acc_num and acc_num == dest_acc:
                    positive_signals.append("EXACT_BANK_ACCOUNT")
                    scores["bank_account"] = 1.0
                    break

        # 3. Name matching
        p_name_norm = normalize_party_name(p.name)
        if extracted_name_norm and p_name_norm:
            if p_name_norm == extracted_name_norm:
                positive_signals.append("EXACT_NAME")
                scores["name"] = 1.0
            else:
                ratio = SequenceMatcher(None, extracted_name_norm, p_name_norm).ratio()
                if ratio >= 0.90:
                    positive_signals.append("FUZZY_NAME")
                    scores["name"] = ratio
                elif ratio < 0.50:
                    negative_signals.append("NAME_MISMATCH")

        # Determine composite score and confidence band
        if "EXACT_TAX_ID" in positive_signals:
            total_score = Decimal("0.98")
            band = ConfidenceBand.HIGH
            explanation = f"Matched counterparty {p.name} via exact tax ID (NPWP)."
        elif "EXACT_BANK_ACCOUNT" in positive_signals:
            total_score = Decimal("0.95")
            band = ConfidenceBand.HIGH
            explanation = f"Matched counterparty {p.name} via exact bank account."
        elif "EXACT_NAME" in positive_signals:
            total_score = Decimal("0.95")
            band = ConfidenceBand.HIGH
            explanation = f"Matched counterparty {p.name} via exact normalized legal name."
        elif "FUZZY_NAME" in positive_signals:
            score_val = scores.get("name", 0.90)
            total_score = Decimal(str(round(score_val, 4)))
            band = ConfidenceBand.MEDIUM
            explanation = f"Fuzzy matched counterparty {p.name} with similarity {score_val:.2f}."
        else:
            continue

        candidate = MatchCandidate(
            entity_type="COUNTERPARTY",
            entity_id=p.id,
            score=total_score,
            confidence_band=band,
            positive_signals=positive_signals,
            negative_signals=negative_signals,
            explanation=explanation,
            scoring_details=scores,
            target_model="Counterparty",
        )
        candidates.append(candidate)

    # Rank: exact identifier signals first, then by score descending, then deterministic ID
    candidates.sort(
        key=lambda c: (
            1 if any(s in c.positive_signals for s in ("EXACT_TAX_ID", "EXACT_BANK_ACCOUNT", "EXACT_NAME")) else 0,
            c.score,
            str(c.entity_id),
        ),
        reverse=True,
    )
    return candidates


async def match_projects(
    session: AsyncSession,
    organization_id: uuid.UUID,
    data: StructuredExtraction,
    matched_counterparty_id: Optional[uuid.UUID] = None,
) -> List[MatchCandidate]:
    """Match projects scoped strictly to organization_id."""
    stmt = select(Project).where(Project.organization_id == organization_id)
    projects = list((await session.scalars(stmt)).all())
    if not projects:
        return []

    ref_norm = normalize_doc_number(data.project_reference)
    spk_norm = normalize_doc_number(data.spk_number)
    doc_norm = normalize_doc_number(data.document_number)
    text_content = ((data.description or "") + " " + (data.raw_text or "")).casefold()

    candidates: List[MatchCandidate] = []

    for proj in projects:
        positive_signals: List[str] = []
        negative_signals: List[str] = []
        scores: Dict[str, float] = {}

        p_code_norm = normalize_doc_number(proj.project_code)
        p_spk_norm = normalize_doc_number(proj.po_spk_no)
        p_name_norm = normalize_party_name(proj.project_name)

        # 1. Exact project code
        if p_code_norm and (p_code_norm == ref_norm or p_code_norm in text_content.upper()):
            positive_signals.append("EXACT_PROJECT_CODE")
            scores["code"] = 1.0

        # 2. Exact PO/SPK number
        if p_spk_norm and (p_spk_norm == spk_norm or p_spk_norm == ref_norm or p_spk_norm == doc_norm):
            positive_signals.append("EXACT_PO_SPK")
            scores["po_spk"] = 1.0

        # 3. Counterparty correlation
        if matched_counterparty_id and proj.customer_id == matched_counterparty_id:
            positive_signals.append("CUSTOMER_PROJECT_RELATION")
            scores["customer"] = 0.8

        # 4. Project name match (supporting only)
        if p_name_norm and (p_name_norm in text_content or SequenceMatcher(None, p_name_norm, text_content).ratio() > 0.60):
            positive_signals.append("PROJECT_NAME_MATCH")
            scores["name"] = 0.70

        if "EXACT_PROJECT_CODE" in positive_signals:
            total_score = Decimal("0.96")
            band = ConfidenceBand.HIGH
            explanation = f"Matched project {proj.project_code} via exact code."
        elif "EXACT_PO_SPK" in positive_signals:
            total_score = Decimal("0.95")
            band = ConfidenceBand.HIGH
            explanation = f"Matched project {proj.project_code} via exact PO/SPK ({proj.po_spk_no})."
        elif "PROJECT_NAME_MATCH" in positive_signals:
            total_score = Decimal("0.72")
            band = ConfidenceBand.MEDIUM
            explanation = f"Supporting match for project {proj.project_code} via name mention."
        else:
            continue

        candidate = MatchCandidate(
            entity_type="PROJECT",
            entity_id=proj.id,
            score=total_score,
            confidence_band=band,
            positive_signals=positive_signals,
            negative_signals=negative_signals,
            explanation=explanation,
            scoring_details=scores,
            target_model="Project",
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: (c.score, str(c.entity_id)), reverse=True)
    return candidates


async def match_vendor_bills(
    session: AsyncSession,
    organization_id: uuid.UUID,
    data: StructuredExtraction,
    matched_counterparty_id: Optional[uuid.UUID] = None,
    matched_project_id: Optional[uuid.UUID] = None,
) -> MatchResult:
    """Match open VendorBills scoped strictly to organization_id."""
    stmt = select(VendorBill).where(
        and_(
            VendorBill.organization_id == organization_id,
            VendorBill.status.in_(["UNPAID", "PARTIALLY_PAID"]),
        )
    )
    bills = list((await session.scalars(stmt)).all())
    if not bills:
        return MatchResult(ranked_candidates=[], requires_review=True, explanation="No open vendor bills found.")

    doc_num_norm = normalize_doc_number(data.invoice_number or data.document_number or data.transfer_reference)
    candidates: List[MatchCandidate] = []

    for bill in bills:
        positive_signals: List[str] = []
        negative_signals: List[str] = []
        scores: Dict[str, float] = {}

        # 1. Invoice number
        b_code_norm = normalize_doc_number(bill.bill_code)
        if doc_num_norm and b_code_norm:
            if b_code_norm == doc_num_norm:
                positive_signals.append("EXACT_INVOICE_NUMBER")
                scores["identifier"] = 1.0
            else:
                negative_signals.append("INVOICE_NUMBER_MISMATCH")
                scores["identifier"] = 0.0
        else:
            scores["identifier"] = 0.0

        # 2. Vendor identity
        if matched_counterparty_id:
            if bill.vendor_id == matched_counterparty_id:
                positive_signals.append("EXACT_VENDOR")
                scores["vendor"] = 1.0
            else:
                negative_signals.append("COUNTERPARTY_MISMATCH")
                scores["vendor"] = 0.0
        else:
            scores["vendor"] = 0.5 if data.issuer_name else 0.0

        # 3. Amount
        if data.total_amount is not None:
            if bill.total_amount == data.total_amount or bill.calculate_outstanding_amount() == data.total_amount:
                positive_signals.append("EXACT_AMOUNT")
                scores["amount"] = 1.0
            else:
                negative_signals.append("AMOUNT_MISMATCH")
                scores["amount"] = 0.0
        else:
            scores["amount"] = 0.0

        # 4. Date proximity
        if data.transaction_date and bill.bill_date:
            diff_days = abs((data.transaction_date - bill.bill_date).days)
            if diff_days <= 3:
                positive_signals.append("EXACT_OR_NEAR_DATE")
                scores["date"] = 1.0
            elif diff_days <= 14:
                positive_signals.append("PROXIMATE_DATE")
                scores["date"] = 0.7
            elif diff_days <= 30:
                scores["date"] = 0.4
            else:
                negative_signals.append("DATE_FAR")
                scores["date"] = 0.0
        else:
            scores["date"] = 0.3

        # 5. Project
        if matched_project_id and bill.project_id:
            if bill.project_id == matched_project_id:
                positive_signals.append("PROJECT_MATCH")
                scores["project"] = 1.0
            else:
                scores["project"] = 0.0
        else:
            scores["project"] = 0.0

        # Composite score calculation
        total = (
            0.35 * scores["identifier"]
            + 0.25 * scores["vendor"]
            + 0.25 * scores["amount"]
            + 0.10 * scores["date"]
            + 0.05 * scores["project"]
        )

        if "COUNTERPARTY_MISMATCH" in negative_signals:
            total = min(total, 0.30)
            band = ConfidenceBand.LOW
        elif "AMOUNT_MISMATCH" in negative_signals:
            total = min(total, 0.70)
            band = ConfidenceBand.MEDIUM
        elif "EXACT_INVOICE_NUMBER" in positive_signals and "EXACT_VENDOR" in positive_signals and "EXACT_AMOUNT" in positive_signals:
            total = max(total, 0.95)
            band = ConfidenceBand.HIGH
        elif total >= 0.85 and not negative_signals:
            band = ConfidenceBand.HIGH
        elif total >= 0.55:
            band = ConfidenceBand.MEDIUM
        else:
            band = ConfidenceBand.LOW

        if not positive_signals and total < 0.30:
            continue

        exp_parts = []
        if positive_signals:
            exp_parts.append(f"Matched signals: {', '.join(positive_signals)}")
        if negative_signals:
            exp_parts.append(f"Conflicts: {', '.join(negative_signals)}")
        explanation = f"VendorBill {bill.bill_code}: " + "; ".join(exp_parts)

        candidate = MatchCandidate(
            entity_type="VENDOR_BILL",
            entity_id=bill.id,
            score=Decimal(str(round(total, 4))),
            confidence_band=band,
            positive_signals=positive_signals,
            negative_signals=negative_signals,
            explanation=explanation,
            scoring_details=scores,
            target_model="VendorBill",
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: (c.score, str(c.entity_id)), reverse=True)

    ambiguous = False
    requires_review = False
    if len(candidates) >= 2:
        margin = abs(candidates[0].score - candidates[1].score)
        if margin <= Decimal("0.05"):
            ambiguous = True
            requires_review = True

    primary = candidates[0] if (candidates and not ambiguous and candidates[0].confidence_band != ConfidenceBand.LOW) else None
    if not primary or (primary and primary.confidence_band != ConfidenceBand.HIGH):
        requires_review = True

    return MatchResult(
        primary_candidate=primary,
        ranked_candidates=candidates,
        ambiguous=ambiguous,
        requires_review=requires_review,
        explanation=primary.explanation if primary else ("Ambiguous matches" if ambiguous else "No reliable match"),
    )


async def match_customer_invoices(
    session: AsyncSession,
    organization_id: uuid.UUID,
    data: StructuredExtraction,
    matched_counterparty_id: Optional[uuid.UUID] = None,
    matched_project_id: Optional[uuid.UUID] = None,
) -> MatchResult:
    """Match open CustomerInvoices scoped strictly to organization_id."""
    stmt = select(CustomerInvoice).where(
        and_(
            CustomerInvoice.organization_id == organization_id,
            CustomerInvoice.status.in_(["UNPAID", "PARTIALLY_PAID"]),
        )
    )
    invoices = list((await session.scalars(stmt)).all())
    if not invoices:
        return MatchResult(ranked_candidates=[], requires_review=True, explanation="No open customer invoices found.")

    doc_num_norm = normalize_doc_number(data.invoice_number or data.document_number or data.transfer_reference)
    candidates: List[MatchCandidate] = []

    for inv in invoices:
        positive_signals: List[str] = []
        negative_signals: List[str] = []
        scores: Dict[str, float] = {}

        # 1. Invoice number
        inv_code_norm = normalize_doc_number(inv.invoice_code)
        if doc_num_norm and inv_code_norm:
            if inv_code_norm == doc_num_norm:
                positive_signals.append("EXACT_INVOICE_NUMBER")
                scores["identifier"] = 1.0
            else:
                negative_signals.append("INVOICE_NUMBER_MISMATCH")
                scores["identifier"] = 0.0
        else:
            scores["identifier"] = 0.0

        # 2. Customer identity
        if matched_counterparty_id:
            if inv.customer_id == matched_counterparty_id:
                positive_signals.append("EXACT_CUSTOMER")
                scores["customer"] = 1.0
            else:
                negative_signals.append("COUNTERPARTY_MISMATCH")
                scores["customer"] = 0.0
        else:
            scores["customer"] = 0.5 if data.recipient_name else 0.0

        # 3. Amount
        if data.total_amount is not None:
            if inv.total_amount == data.total_amount or inv.calculate_outstanding_amount() == data.total_amount:
                positive_signals.append("EXACT_AMOUNT")
                scores["amount"] = 1.0
            else:
                negative_signals.append("AMOUNT_MISMATCH")
                scores["amount"] = 0.0
        else:
            scores["amount"] = 0.0

        # 4. Date proximity
        if data.transaction_date and inv.invoice_date:
            diff_days = abs((data.transaction_date - inv.invoice_date).days)
            if diff_days <= 3:
                positive_signals.append("EXACT_OR_NEAR_DATE")
                scores["date"] = 1.0
            elif diff_days <= 14:
                positive_signals.append("PROXIMATE_DATE")
                scores["date"] = 0.7
            elif diff_days <= 30:
                scores["date"] = 0.4
            else:
                negative_signals.append("DATE_FAR")
                scores["date"] = 0.0
        else:
            scores["date"] = 0.3

        # 5. Project
        if matched_project_id and inv.project_id:
            if inv.project_id == matched_project_id:
                positive_signals.append("PROJECT_MATCH")
                scores["project"] = 1.0
            else:
                scores["project"] = 0.0
        else:
            scores["project"] = 0.0

        # Composite score calculation
        total = (
            0.35 * scores["identifier"]
            + 0.25 * scores["customer"]
            + 0.25 * scores["amount"]
            + 0.10 * scores["date"]
            + 0.05 * scores["project"]
        )

        if "COUNTERPARTY_MISMATCH" in negative_signals:
            total = min(total, 0.30)
            band = ConfidenceBand.LOW
        elif "AMOUNT_MISMATCH" in negative_signals:
            total = min(total, 0.70)
            band = ConfidenceBand.MEDIUM
        elif "EXACT_INVOICE_NUMBER" in positive_signals and "EXACT_CUSTOMER" in positive_signals and "EXACT_AMOUNT" in positive_signals:
            total = max(total, 0.95)
            band = ConfidenceBand.HIGH
        elif total >= 0.85 and not negative_signals:
            band = ConfidenceBand.HIGH
        elif total >= 0.55:
            band = ConfidenceBand.MEDIUM
        else:
            band = ConfidenceBand.LOW

        if not positive_signals and total < 0.30:
            continue

        exp_parts = []
        if positive_signals:
            exp_parts.append(f"Matched signals: {', '.join(positive_signals)}")
        if negative_signals:
            exp_parts.append(f"Conflicts: {', '.join(negative_signals)}")
        explanation = f"CustomerInvoice {inv.invoice_code}: " + "; ".join(exp_parts)

        candidate = MatchCandidate(
            entity_type="CUSTOMER_INVOICE",
            entity_id=inv.id,
            score=Decimal(str(round(total, 4))),
            confidence_band=band,
            positive_signals=positive_signals,
            negative_signals=negative_signals,
            explanation=explanation,
            scoring_details=scores,
            target_model="CustomerInvoice",
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: (c.score, str(c.entity_id)), reverse=True)

    ambiguous = False
    requires_review = False
    if len(candidates) >= 2:
        margin = abs(candidates[0].score - candidates[1].score)
        if margin <= Decimal("0.05"):
            ambiguous = True
            requires_review = True

    primary = candidates[0] if (candidates and not ambiguous and candidates[0].confidence_band != ConfidenceBand.LOW) else None
    if not primary or (primary and primary.confidence_band != ConfidenceBand.HIGH):
        requires_review = True

    return MatchResult(
        primary_candidate=primary,
        ranked_candidates=candidates,
        ambiguous=ambiguous,
        requires_review=requires_review,
        explanation=primary.explanation if primary else ("Ambiguous matches" if ambiguous else "No reliable match"),
    )


async def match_entities(
    session: AsyncSession,
    organization_id: uuid.UUID,
    data: StructuredExtraction,
    document_type: Optional[DocumentType] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "counterparty_id": None,
        "counterparty_method": None,
        "counterparty_role": None,
        "entity_confidence": None,
        "project_id": None,
        "project_method": None,
        "project_confidence": None,
        "payment_account_id": None,
        "payment_account_method": None,
        "payment_account_confidence": None,
        "allocation_target_id": None,
        "allocation_target_type": None,
        "allocation_confidence": None,
        "alternatives": [],
        "match_candidates": [],
        "primary_candidate": None,
        "ambiguous": False,
        "requires_review": False,
    }

    # 1. Counterparty matching
    parties = list((await session.scalars(select(Counterparty).where(and_(
        Counterparty.organization_id == organization_id, Counterparty.is_active.is_(True))))).all())

    name = data.issuer_name or data.recipient_name
    if name and parties:
        ranked_names = sorted(((SequenceMatcher(None, normalize(name), normalize(p.name)).ratio(), p) for p in parties), reverse=True, key=lambda x: (x[0], str(x[1].id)))
        result["alternatives"] = [{"id": str(p.id), "name": p.name, "score": f"{score:.4f}"} for score, p in ranked_names[:3]]

    cp_candidates = await match_counterparties(session, organization_id, data)
    for c in cp_candidates:
        result["match_candidates"].append(c.model_dump(mode="json"))

    if cp_candidates:
        top_cp = cp_candidates[0]
        is_cp_ambig = len(cp_candidates) > 1 and abs(cp_candidates[0].score - cp_candidates[1].score) <= Decimal("0.05")
        if not is_cp_ambig and top_cp.confidence_band in (ConfidenceBand.HIGH, ConfidenceBand.MEDIUM):
            party_obj = next((p for p in parties if p.id == top_cp.entity_id), None)
            role = ("CUSTOMER" if party_obj and party_obj.is_customer and not party_obj.is_vendor else
                    "VENDOR" if party_obj and party_obj.is_vendor and not party_obj.is_customer else None)
            method = top_cp.positive_signals[0] if top_cp.positive_signals else "FUZZY"
            result.update(
                counterparty_id=str(top_cp.entity_id),
                counterparty_method=method,
                counterparty_role=role,
                entity_confidence=f"{top_cp.score:.4f}",
            )
        elif is_cp_ambig:
            result["ambiguous"] = True
            result["requires_review"] = True

    matched_cp_uuid = uuid.UUID(result["counterparty_id"]) if result["counterparty_id"] else None

    # 2. Project matching
    proj_candidates = await match_projects(session, organization_id, data, matched_counterparty_id=matched_cp_uuid)
    for c in proj_candidates:
        result["match_candidates"].append(c.model_dump(mode="json"))

    if proj_candidates:
        top_proj = proj_candidates[0]
        is_proj_ambig = len(proj_candidates) > 1 and abs(proj_candidates[0].score - proj_candidates[1].score) <= Decimal("0.05")
        if not is_proj_ambig and top_proj.confidence_band in (ConfidenceBand.HIGH, ConfidenceBand.MEDIUM):
            method = top_proj.positive_signals[0] if top_proj.positive_signals else "EXACT_ID"
            result.update(
                project_id=str(top_proj.entity_id),
                project_method=method,
                project_confidence=f"{top_proj.score:.4f}",
            )
        elif is_proj_ambig:
            result["ambiguous"] = True
            result["requires_review"] = True

    matched_proj_uuid = uuid.UUID(result["project_id"]) if result["project_id"] else None

    # 3. Payment account matching
    bank_hint = data.origin_bank or data.destination_bank
    acc_no_hint = data.destination_account_number
    if bank_hint or acc_no_hint:
        accounts = list((await session.scalars(select(PaymentAccount).where(
            and_(PaymentAccount.organization_id == organization_id, PaymentAccount.is_active.is_(True))
        ))).all())
        acc_matches = []
        for acc in accounts:
            if acc_no_hint and acc.account_number and normalize(acc_no_hint) == normalize(acc.account_number):
                acc_matches.append((acc, "EXACT_ACCOUNT_NO", "1.00"))
            elif bank_hint and acc.bank_name and normalize(bank_hint) in normalize(acc.bank_name):
                acc_matches.append((acc, "BANK_NAME", "0.90"))
            elif bank_hint and normalize(bank_hint) in normalize(acc.name):
                acc_matches.append((acc, "NAME_HINT", "0.85"))

        exact_acc = [m for m in acc_matches if m[1] == "EXACT_ACCOUNT_NO"]
        if len(exact_acc) == 1:
            acc, method, conf = exact_acc[0]
            result.update(payment_account_id=str(acc.id), payment_account_method=method, payment_account_confidence=conf)
        elif len(exact_acc) > 1:
            result["ambiguous"] = True
            result["requires_review"] = True
        elif len(acc_matches) == 1:
            acc, method, conf = acc_matches[0]
            result.update(payment_account_id=str(acc.id), payment_account_method=method, payment_account_confidence=conf)
        elif len(acc_matches) > 1:
            result["ambiguous"] = True
            result["requires_review"] = True

    # 4. Allocation target matching (CustomerInvoice vs VendorBill)
    target_match_result: Optional[MatchResult] = None
    role = result.get("counterparty_role")

    if document_type == DocumentType.CUSTOMER_INVOICE:
        target_match_result = await match_customer_invoices(
            session, organization_id, data, matched_counterparty_id=matched_cp_uuid, matched_project_id=matched_proj_uuid
        )
    elif document_type == DocumentType.VENDOR_INVOICE:
        target_match_result = await match_vendor_bills(
            session, organization_id, data, matched_counterparty_id=matched_cp_uuid, matched_project_id=matched_proj_uuid
        )
    elif document_type == DocumentType.TRANSFER_PROOF:
        if role == "CUSTOMER":
            target_match_result = await match_customer_invoices(
                session, organization_id, data, matched_counterparty_id=matched_cp_uuid, matched_project_id=matched_proj_uuid
            )
        elif role == "VENDOR":
            target_match_result = await match_vendor_bills(
                session, organization_id, data, matched_counterparty_id=matched_cp_uuid, matched_project_id=matched_proj_uuid
            )
        else:
            inv_res = await match_customer_invoices(session, organization_id, data, matched_project_id=matched_proj_uuid)
            bill_res = await match_vendor_bills(session, organization_id, data, matched_project_id=matched_proj_uuid)
            if inv_res.primary_candidate and not bill_res.primary_candidate:
                target_match_result = inv_res
            elif bill_res.primary_candidate and not inv_res.primary_candidate:
                target_match_result = bill_res
            elif inv_res.ambiguous or bill_res.ambiguous:
                result["ambiguous"] = True
                result["requires_review"] = True

    if target_match_result:
        for c in target_match_result.ranked_candidates:
            result["match_candidates"].append(c.model_dump(mode="json"))
        if target_match_result.ambiguous:
            result["ambiguous"] = True
            result["requires_review"] = True
            result["allocation_target_id"] = None
        elif target_match_result.primary_candidate:
            prim = target_match_result.primary_candidate
            result["primary_candidate"] = prim.model_dump(mode="json")
            result["allocation_target_id"] = str(prim.entity_id)
            result["allocation_target_type"] = prim.entity_type
            result["allocation_confidence"] = f"{prim.score:.4f}"
            if prim.confidence_band != ConfidenceBand.HIGH:
                result["requires_review"] = True
        else:
            result["requires_review"] = True

    if not result.get("counterparty_id"):
        result["requires_review"] = True
    if result["ambiguous"]:
        result["requires_review"] = True

    return result
