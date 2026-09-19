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
    *,
    type_confirmed: bool = False,
) -> DocumentProcessingStatus:
    """Canonical status resolver used by the pipeline and the corrections endpoint.

    ``type_confirmed`` marks an authoritative human confirmation of the document
    type (a reviewer explicitly saving/correcting the type). It substitutes for
    the OCR type-confidence gate, so an uncertain evidence document can still be
    archived once a person has vouched for its type.
    """
    flags = list(flags)
    dt = _coerce(document_type)

    if dt in FINANCIAL_DOCUMENT_TYPES:
        return document_status_for(candidate, flags)

    if dt is not None and dt in EVIDENCE_DOCUMENT_TYPES:
        if flags or not (type_confirmed or document_type_is_confident(confidence_scores)):
            return DocumentProcessingStatus.REVIEW_REQUIRED
        return DocumentProcessingStatus.PROCESSED

    # UNKNOWN or unclassifiable -> always review
    return DocumentProcessingStatus.REVIEW_REQUIRED
