import uuid
from src.models.enums import (CandidateStatus, CostCategory, DocumentType,
                              ReviewFlag, TransactionType)
from src.schemas.document import StructuredExtraction, TransactionCandidate


SUPPORTING_DOCUMENT_TYPES = {
    DocumentType.SPK,
    DocumentType.CONTRACT,
    DocumentType.BAST,
    DocumentType.SURAT_JALAN,
    DocumentType.PROGRESS_REPORT,
    DocumentType.TIMESHEET,
    DocumentType.PURCHASE_ORDER,
    DocumentType.PO_CUSTOMER,
    DocumentType.TAX_INVOICE,
    DocumentType.WITHHOLDING_DOCUMENT,
    DocumentType.OTHER_TAX_DOCUMENT,
}


def build_candidate(document_id: uuid.UUID, document_type: DocumentType,
                    data: StructuredExtraction, matches: dict, flags: list[str]) -> TransactionCandidate | None:
    if document_type in SUPPORTING_DOCUMENT_TYPES:
        return None
    proposed = None
    category = None
    force_review = document_type in {DocumentType.TRANSFER_PROOF, DocumentType.RECEIPT}
    if document_type == DocumentType.TRANSFER_PROOF:
        # Direction is a proposal only; evidence of cash movement never proves expense.
        role = matches.get("counterparty_role")
        proposed = (TransactionType.CUSTOMER_PAYMENT if role == "CUSTOMER" else
                    TransactionType.PAY_VENDOR_BILL if role == "VENDOR" else None)
    elif document_type == DocumentType.RECEIPT:
        proposed, category = TransactionType.DIRECT_PURCHASE, CostCategory.MAT
    elif document_type == DocumentType.VENDOR_INVOICE:
        proposed, category = TransactionType.VENDOR_BILL, CostCategory.MAT
    elif document_type == DocumentType.CUSTOMER_INVOICE:
        proposed = TransactionType.CUSTOMER_INVOICE

    status = CandidateStatus.REVIEW_REQUIRED if (flags or force_review) else CandidateStatus.READY_FOR_APPROVAL
    return TransactionCandidate(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"document:{document_id}"),
        proposed_transaction_type=proposed,
        counterparty_id=matches.get("counterparty_id"),
        project_id=matches.get("project_id"),
        payment_account_id=matches.get("payment_account_id"),
        cost_category=category,
        transaction_date=data.transaction_date,
        amount=data.total_amount,
        currency_code=data.currency_code or "IDR",
        description=data.description or f"Candidate from {document_type.value}",
        external_reference=data.invoice_number or data.transfer_reference or data.document_number,
        status=status,
    )


def derive_flags(document_type: DocumentType, data: StructuredExtraction, matches: dict,
                 low_confidence: bool) -> list[str]:
    flags: list[str] = []
    if low_confidence:
        flags.append(ReviewFlag.OCR_LOW_CONFIDENCE.value)

    # Check field evidence validation status
    for field_name, field_val in data.field_evidence.items():
        if field_val.validation_status == "AMBIGUOUS":
            if "amount" in field_name:
                flags.append(ReviewFlag.AMOUNT_MISMATCH.value)
            elif "date" in field_name:
                flags.append(ReviewFlag.DATE_MISMATCH.value)
            else:
                flags.append(ReviewFlag.OCR_LOW_CONFIDENCE.value)
        elif field_val.validation_status == "INVALID":
            flags.append(ReviewFlag.OCR_LOW_CONFIDENCE.value)

    if document_type in {DocumentType.VENDOR_INVOICE, DocumentType.TRANSFER_PROOF} and not matches.get("counterparty_id"):
        flags.append(ReviewFlag.VENDOR_UNKNOWN.value)
    if document_type == DocumentType.CUSTOMER_INVOICE and not matches.get("counterparty_id"):
        flags.append(ReviewFlag.CUSTOMER_UNKNOWN.value)
    if document_type in {DocumentType.VENDOR_INVOICE, DocumentType.CUSTOMER_INVOICE} and not matches.get("project_id"):
        flags.append(ReviewFlag.PROJECT_UNKNOWN.value)

    return list(dict.fromkeys(flags))
