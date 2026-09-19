import uuid
from decimal import Decimal
from src.models.enums import (CandidateStatus, CostCategory, DocumentType,
                              ExpenseCategory, ReviewFlag, TransactionType)
from src.schemas.document import StructuredExtraction, TransactionCandidate
from src.services.documents.expense_classifier import classify_expense
from src.services.documents.line_item_classifier import classify_line_items


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
    expense_cat = None
    force_review = document_type in {DocumentType.TRANSFER_PROOF, DocumentType.RECEIPT}
    if document_type == DocumentType.TRANSFER_PROOF:
        # Direction is a proposal only; evidence of cash movement never proves expense.
        role = matches.get("counterparty_role")
        target_type = matches.get("allocation_target_type")
        if target_type == "VENDOR_BILL" or role == "VENDOR":
            proposed = TransactionType.PAY_VENDOR_BILL
        elif target_type in ("CUSTOMER_INVOICE", "CustomerInvoice") or role == "CUSTOMER":
            proposed = TransactionType.CUSTOMER_PAYMENT
        else:
            proposed = None
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
    elif document_type in {DocumentType.RECEIPT, DocumentType.VENDOR_INVOICE}:
        caption = matches.get("caption") or (matches.get("source_metadata") or {}).get("caption")
        proj_hint = data.project_reference
        raw_desc = data.description or (data.line_items[0].description if data.line_items else "") or data.raw_text or ""
        matched_pid = matches.get("project_id")
        if matched_pid and isinstance(matched_pid, str):
            try:
                matched_pid = uuid.UUID(matched_pid)
            except Exception:
                pass

        exp_res = classify_expense(
            raw_description=raw_desc,
            caption=caption,
            matched_project_id=matched_pid,
            vendor_name=data.issuer_name or data.recipient_name,
            document_text=data.raw_text,
            document_project_hint=proj_hint,
        )
        matches["expense_classification"] = exp_res.to_dict()

        if data.line_items:
            data.line_items = classify_line_items(
                data.line_items,
                project_id=matched_pid,
            )

        if exp_res.cost_category:
            category = exp_res.cost_category
            expense_cat = None
        elif exp_res.expense_category:
            category = None
            expense_cat = exp_res.expense_category
        else:
            category = CostCategory.MAT
            expense_cat = None

        if document_type == DocumentType.RECEIPT:
            proposed = TransactionType.DIRECT_PURCHASE
        else:
            proposed = TransactionType.VENDOR_BILL
    elif document_type == DocumentType.CUSTOMER_INVOICE:
        proposed = TransactionType.CUSTOMER_INVOICE

    status = CandidateStatus.REVIEW_REQUIRED if (flags or force_review) else CandidateStatus.READY_FOR_APPROVAL
    resolved_proj_id = None if expense_cat else matches.get("project_id")
    return TransactionCandidate(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"document:{document_id}"),
        proposed_transaction_type=proposed,
        counterparty_id=matches.get("counterparty_id"),
        project_id=resolved_proj_id,
        payment_account_id=matches.get("payment_account_id"),
        allocation_target_id=matches.get("allocation_target_id"),
        cost_category=category,
        expense_category=expense_cat,
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

    if matches.get("ambiguous"):
        flags.append(ReviewFlag.AMBIGUOUS_MATCH.value)

    if document_type in {DocumentType.VENDOR_INVOICE, DocumentType.TRANSFER_PROOF} and not matches.get("counterparty_id"):
        flags.append(ReviewFlag.VENDOR_UNKNOWN.value)
    if document_type == DocumentType.CUSTOMER_INVOICE and not matches.get("counterparty_id"):
        flags.append(ReviewFlag.CUSTOMER_UNKNOWN.value)
    if document_type in {DocumentType.VENDOR_INVOICE, DocumentType.CUSTOMER_INVOICE} and not matches.get("project_id"):
        flags.append(ReviewFlag.PROJECT_UNKNOWN.value)
    if document_type == DocumentType.TRANSFER_PROOF and not matches.get("allocation_target_id"):
        flags.append(ReviewFlag.ACCOUNT_REVIEW.value)

    # Expense classification checks
    exp_info = matches.get("expense_classification")
    if exp_info and exp_info.get("review_required"):
        if not matches.get("project_id") and exp_info.get("management_category") == "BBM / Transportasi":
            flags.append(ReviewFlag.PROJECT_UNKNOWN.value)
        if "CAPTION_PROJECT_MISMATCH" in exp_info.get("classification_conflicts", []):
            flags.append(ReviewFlag.AMBIGUOUS_MATCH.value)

    return list(dict.fromkeys(flags))
