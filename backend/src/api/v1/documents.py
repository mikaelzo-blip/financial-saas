import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.api.auth import require_application_user, require_roles
from src.models.enums import (
    DocumentType, DocumentProcessingStatus, CandidateStatus, ProjectStatus,
    ReviewFlag, TransactionType,
)
from src.models.document import DocumentCorrection
from src.models.project import Project
from src.models.counterparty import Counterparty
from src.models.receivable import CustomerInvoice
from src.models.payable import VendorBill
from src.models.coa import PaymentAccount
from src.models.transaction import Transaction
from src.models.user import User
from src.models.enums import UserRole
from src.schemas.document import (DocumentResponse, DocumentCorrectionRequest,
                                  DocumentRejectionRequest, TransactionCandidate,
                                  StructuredExtraction, DocumentPostingResponse)
from src.services.document_posting_service import DocumentPostingService
from src.services.recording_categories import PROJECT_REQUIRED_COST_CATEGORIES
from src.services.documents.matching import match_entities
from src.services.documents.status import is_evidence_document, resolve_document_status
from src.services.documents.expense_duplicate_guard import (
    DuplicateScanner,
    collect_reference_numbers,
)
from src.schemas.transaction import TransactionCreate, TransactionResponse
from src.services.document_service import DocumentService
from src.services.documents.inbound_adapter import InboundDocumentAdapter, InboundDocumentInput
from src.services.job_queue_service import JobQueueService
from src.services.posting_rules import PostingRuleRegistry
from src.services.audit_service import AuditService
from src.services.transaction_retry import run_in_clean_transaction

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_CORRECTION_FIELDS = {
    "project_id", "counterparty_id", "payment_account_id", "allocation_target_id",
    "selected_candidate_id", "proposed_transaction_type", "cost_category",
    "expense_category", "transaction_date", "date", "amount", "total_amount",
    "subtotal", "tax", "vat_amount", "description", "external_reference",
    "transfer_reference", "document_number", "invoice_number", "spk_number",
    "bast_number", "due_date", "document_type", "origin_bank", "destination_bank",
    "destination_account_number", "line_items",
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
        if candidate.cost_category in PROJECT_REQUIRED_COST_CATEGORIES:
            return bool(candidate.project_id)
        return bool(candidate.project_id or candidate.expense_category)
    if t_type in {TransactionType.VENDOR_BILL, TransactionType.CUSTOMER_INVOICE}:
        return bool(candidate.counterparty_id and candidate.project_id)
    return True


# Bounded batch size for the duplicate scan: keeps memory flat regardless of how
# many transactions the tenant has accumulated.
_DUPLICATE_SCAN_BATCH = 500


async def _scan_existing_references(
    db: AsyncSession, org_id: uuid.UUID, scanner: "DuplicateScanner"
) -> bool:
    """Feed already-recorded reference numbers into the duplicate scanner.

    Reads VendorBill / CustomerInvoice / Transaction in bounded batches (keyset
    pagination on `id`) so the full history is never materialised in memory.
    Returns True as soon as the scanner reports a real duplicate (caller can
    stop), mirroring `evaluate_reference_duplicate`'s semantics exactly.
    """
    sources = (
        (VendorBill, VendorBill.bill_code, VendorBill.total_amount),
        (CustomerInvoice, CustomerInvoice.invoice_code, CustomerInvoice.total_amount),
        (Transaction, Transaction.reference_no, Transaction.amount),
    )
    for model, code_col, amount_col in sources:
        last_id = None
        while True:
            stmt = (
                select(model.id, code_col, amount_col)
                .where(model.organization_id == org_id, code_col.isnot(None))
                .order_by(model.id)
                .limit(_DUPLICATE_SCAN_BATCH)
            )
            if last_id is not None:
                stmt = stmt.where(model.id > last_id)
            rows = (await db.execute(stmt)).all()
            if not rows:
                break
            for row_id, code, amount in rows:
                if scanner.feed(code, amount):
                    return True
            last_id = rows[-1][0]
            if len(rows) < _DUPLICATE_SCAN_BATCH:
                break
    return False


async def validate_allocation_target(
    db: AsyncSession,
    org_id: uuid.UUID,
    candidate: TransactionCandidate,
) -> None:
    if not candidate.allocation_target_id:
        return

    allocation_models = (
        (CustomerInvoice,)
        if candidate.proposed_transaction_type == TransactionType.CUSTOMER_PAYMENT
        else (VendorBill,)
        if candidate.proposed_transaction_type == TransactionType.PAY_VENDOR_BILL
        else (CustomerInvoice, VendorBill)
    )
    for model in allocation_models:
        target = await db.scalar(select(model).where(and_(
            model.id == candidate.allocation_target_id,
            model.organization_id == org_id,
        )))
        if not target:
            continue
        if candidate.proposed_transaction_type == TransactionType.CUSTOMER_PAYMENT and (
            candidate.counterparty_id != target.customer_id
        ):
            raise HTTPException(status_code=422, detail="Allocation target does not belong to the selected customer")
        if candidate.proposed_transaction_type == TransactionType.PAY_VENDOR_BILL and (
            candidate.counterparty_id != target.vendor_id
        ):
            raise HTTPException(status_code=422, detail="Allocation target does not belong to the selected vendor")
        return
    raise HTTPException(status_code=422, detail="Allocation target is not available in this organization")


async def require_reviewer(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await db.scalar(select(User).where(and_(User.id == user_id, User.organization_id == org_id,
        User.role.in_([UserRole.ADMIN, UserRole.MANAGER]))))
    if not user:
        raise HTTPException(status_code=403, detail="Manager or administrator review permission required")
    return user


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Source Evidentiary Document"
)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.UNKNOWN),
    source_channel: str = Form("WEB"),
    project_id: Optional[uuid.UUID] = Form(None),
    process: bool = Form(True),
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db),
):
    async def ingest(session: AsyncSession):
        adapter = InboundDocumentAdapter(session)
        document = await adapter.ingest_and_enqueue(
            InboundDocumentInput(
                organization_id=org_id,
                file_obj=file.file,
                file_name=file.filename or "unknown_file",
                mime_type=file.content_type or "application/octet-stream",
                document_type=document_type,
                source_channel=source_channel,
                project_id=project_id,
                created_by=current_user.id,
            ),
            enqueue_job=process,
        )
        return document

    document = await run_in_clean_transaction(db, ingest)
    return await DocumentService(db).get_document(org_id, document.id)


@router.get("/{document_id}/content", summary="Stream Immutable Original")
async def get_document_content(
    document_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_application_user),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user
    service = DocumentService(db)
    document = await service.get_document(org_id, document_id)
    path = service.storage.get_file_path(document.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored document content not found")
    return FileResponse(path, media_type=document.mime_type, filename=document.file_name)


@router.post("/{document_id}/retry", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_document(document_id: uuid.UUID,
                         org_id: uuid.UUID = Depends(get_current_org_id),
                         current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
                         db: AsyncSession = Depends(get_db)):
    async def retry(session: AsyncSession):
        service = DocumentService(session)
        document = await service.get_document(org_id, document_id)
        if document.processing_status not in {
            DocumentProcessingStatus.FAILED,
            DocumentProcessingStatus.REVIEW_REQUIRED,
            DocumentProcessingStatus.QUEUED,
        }:
            raise HTTPException(status_code=409, detail="Document is not in a retryable state")
        document.processing_status = DocumentProcessingStatus.QUEUED
        await session.flush()

        queue = JobQueueService(session)
        await queue.enqueue(
            job_type="DOCUMENT_PROCESS",
            payload={"document_id": str(document.id)},
            organization_id=org_id,
            idempotency_key=f"DOCUMENT_PROCESS:{document.id}",
        )
        await session.flush()
        return document

    document = await run_in_clean_transaction(db, retry)
    return document


@router.post("/{document_id}/corrections", response_model=DocumentResponse)
async def correct_document(document_id: uuid.UUID, data: DocumentCorrectionRequest,
                           org_id: uuid.UUID = Depends(get_current_org_id),
                           current_user: User = Depends(require_application_user),
                           db: AsyncSession = Depends(get_db)):
    user_id = current_user.id
    service = DocumentService(db)
    document = await service.get_document(org_id, document_id, for_update=True)
    await require_reviewer(db, org_id, user_id)
    if document.processing_status in {
        DocumentProcessingStatus.PROCESSED,
        DocumentProcessingStatus.REJECTED,
        DocumentProcessingStatus.READY_TO_POST,
    } or document.processing_status not in {
        DocumentProcessingStatus.REVIEW_REQUIRED,
        DocumentProcessingStatus.READY_FOR_APPROVAL,
    }:
        raise HTTPException(status_code=409, detail="Document is not awaiting review")

    if not data.changes or set(data.changes) - ALLOWED_CORRECTION_FIELDS:
        raise HTTPException(status_code=422, detail="Correction contains unsupported fields")

    candidate = dict(document.candidate_transaction or {})
    extracted = dict(document.extracted_data or {})
    matching_results = dict(document.matching_results or {})

    # Capture old values before mutation
    old = {}
    for key in data.changes:
        if key in candidate:
            old[key] = candidate.get(key)
        elif key in extracted:
            old[key] = extracted.get(key)
        elif key == "document_type":
            old[key] = document.document_type.value
        else:
            old[key] = None

    # Handle candidate selection
    if "selected_candidate_id" in data.changes:
        selected_id_val = data.changes["selected_candidate_id"]
        if selected_id_val:
            try:
                selected_uuid = uuid.UUID(str(selected_id_val))
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="Invalid selected_candidate_id UUID")

            bill = await db.scalar(select(VendorBill).where(and_(
                VendorBill.id == selected_uuid, VendorBill.organization_id == org_id
            )))
            invoice = await db.scalar(select(CustomerInvoice).where(and_(
                CustomerInvoice.id == selected_uuid, CustomerInvoice.organization_id == org_id
            )))
            party = await db.scalar(select(Counterparty).where(and_(
                Counterparty.id == selected_uuid, Counterparty.organization_id == org_id,
                Counterparty.is_active.is_(True)
            )))
            proj = await db.scalar(select(Project).where(and_(
                Project.id == selected_uuid, Project.organization_id == org_id
            )))
            acc = await db.scalar(select(PaymentAccount).where(and_(
                PaymentAccount.id == selected_uuid, PaymentAccount.organization_id == org_id,
                PaymentAccount.is_active.is_(True)
            )))

            if bill:
                candidate["allocation_target_id"] = str(bill.id)
                candidate["proposed_transaction_type"] = TransactionType.PAY_VENDOR_BILL.value
                if not candidate.get("counterparty_id") and bill.vendor_id:
                    candidate["counterparty_id"] = str(bill.vendor_id)
                if not candidate.get("project_id") and bill.project_id:
                    candidate["project_id"] = str(bill.project_id)
            elif invoice:
                candidate["allocation_target_id"] = str(invoice.id)
                candidate["proposed_transaction_type"] = TransactionType.CUSTOMER_PAYMENT.value
                if not candidate.get("counterparty_id") and invoice.customer_id:
                    candidate["counterparty_id"] = str(invoice.customer_id)
                if not candidate.get("project_id") and invoice.project_id:
                    candidate["project_id"] = str(invoice.project_id)
            elif party:
                candidate["counterparty_id"] = str(party.id)
            elif proj:
                candidate["project_id"] = str(proj.id)
            elif acc:
                candidate["payment_account_id"] = str(acc.id)
            else:
                raise HTTPException(status_code=422, detail="Selected candidate is not available in this organization")
            matching_results["ambiguous"] = False
            if document.review_flags:
                document.review_flags = [f for f in document.review_flags if f != ReviewFlag.AMBIGUOUS_MATCH.value]

    # Synchronize extracted fields
    if "document_type" in data.changes and data.changes["document_type"]:
        try:
            document.document_type = DocumentType(data.changes["document_type"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid document_type")

    for ext_field in ("invoice_number", "document_number", "spk_number", "bast_number",
                      "due_date", "subtotal", "vat_amount", "origin_bank", "destination_bank",
                      "destination_account_number", "transfer_reference"):
        if ext_field in data.changes:
            extracted[ext_field] = data.changes[ext_field]
    if "line_items" in data.changes:
        extracted["line_items"] = data.changes["line_items"]
    if "tax" in data.changes:
        extracted["vat_amount"] = data.changes["tax"]
    if "total_amount" in data.changes:
        extracted["total_amount"] = data.changes["total_amount"]
        candidate["amount"] = data.changes["total_amount"]
    if "amount" in data.changes:
        extracted["total_amount"] = data.changes["amount"]
        candidate["amount"] = data.changes["amount"]
    if "date" in data.changes:
        extracted["transaction_date"] = data.changes["date"]
        candidate["transaction_date"] = data.changes["date"]
    if "transaction_date" in data.changes:
        extracted["transaction_date"] = data.changes["transaction_date"]
        candidate["transaction_date"] = data.changes["transaction_date"]

    for cand_field in ("project_id", "counterparty_id", "payment_account_id", "allocation_target_id",
                       "proposed_transaction_type", "cost_category", "expense_category",
                       "description", "external_reference"):
        if cand_field in data.changes:
            candidate[cand_field] = data.changes[cand_field]

    if "invoice_number" in data.changes and not data.changes.get("external_reference"):
        candidate["external_reference"] = data.changes["invoice_number"]

    document.extracted_data = extracted

    # Material corrections invalidate any prior allocation unless the reviewer
    # explicitly selects a replacement during this same correction.
    material_fields = {
        "invoice_number", "document_number", "spk_number", "counterparty_id",
        "project_id", "amount", "total_amount", "document_type"
    }
    material_correction = any(key in material_fields for key in data.changes)
    selected_candidate = data.changes.get("selected_candidate_id")
    if material_correction and not selected_candidate and "allocation_target_id" not in data.changes:
        candidate["allocation_target_id"] = None
        matching_results.pop("selected_candidate_id", None)

    if material_correction:
        try:
            extraction_obj = StructuredExtraction.model_validate(document.extracted_data)
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail="Corrected extraction data cannot be rematched",
            ) from error
        matching_results = await match_entities(
            db, org_id, extraction_obj, document_type=document.document_type
        )
        if "counterparty_id" not in data.changes and matching_results.get("counterparty_id"):
            candidate["counterparty_id"] = matching_results["counterparty_id"]
        if "project_id" not in data.changes and matching_results.get("project_id"):
            candidate["project_id"] = matching_results["project_id"]
    if selected_candidate:
        matching_results["ambiguous"] = False
        matching_results["selected_candidate_id"] = str(selected_candidate)

    document.matching_results = matching_results

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

    if is_evidence_document(document.document_type):
        # Evidence documents carry no transaction candidate; skip candidate
        # validation (an empty {} would raise) and re-resolve the status.
        # Saving the document is an authoritative human confirmation of its
        # type, so a below-threshold OCR type confidence no longer blocks
        # archiving (type_confirmed=True); any remaining flag still does.
        document.extracted_data = extracted
        document.matching_results = matching_results
        document.review_flags = [f for f in document.review_flags if f not in cleared]
        document.processing_status = resolve_document_status(
            document.document_type,
            None,
            document.review_flags,
            document.confidence_scores,
            type_confirmed=True,
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

    validated = TransactionCandidate.model_validate(candidate)
    if validated.proposed_transaction_type is not None:
        PostingRuleRegistry.validate_generic_ingestion(validated.proposed_transaction_type)
    if validated.project_id:
        project = await db.scalar(select(Project).where(and_(
            Project.id == validated.project_id, Project.organization_id == org_id,
            Project.project_status.in_([ProjectStatus.PLANNED, ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD]),
        )))
        if not project:
            raise HTTPException(status_code=422, detail="Project is no longer available for new transactions")
    if validated.counterparty_id:
        counterparty = await db.scalar(select(Counterparty).where(and_(
            Counterparty.id == validated.counterparty_id, Counterparty.organization_id == org_id,
            Counterparty.is_active.is_(True),
        )))
        if not counterparty:
            raise HTTPException(status_code=422, detail="Counterparty is not available in this organization")
        vendor_types = {
            TransactionType.VENDOR_BILL, TransactionType.PAY_VENDOR_BILL, TransactionType.VENDOR_ADVANCE,
            TransactionType.SETTLE_VENDOR_ADVANCE, TransactionType.SUBCONTRACTOR_BILL,
            TransactionType.PAY_SUBCONTRACTOR, TransactionType.VENDOR_REFUND,
        }
        customer_types = {
            TransactionType.CUSTOMER_INVOICE, TransactionType.CUSTOMER_PAYMENT,
            TransactionType.CUSTOMER_ADVANCE, TransactionType.CUSTOMER_REFUND,
        }
        if validated.proposed_transaction_type in vendor_types and not counterparty.is_vendor:
            raise HTTPException(status_code=422, detail="Counterparty must be an active vendor for this transaction")
        if validated.proposed_transaction_type in customer_types and not counterparty.is_customer:
            raise HTTPException(status_code=422, detail="Counterparty must be an active customer for this transaction")
    if validated.payment_account_id and not await db.scalar(select(PaymentAccount.id).where(and_(
        PaymentAccount.id == validated.payment_account_id, PaymentAccount.organization_id == org_id,
        PaymentAccount.is_active.is_(True),
    ))):
        raise HTTPException(status_code=422, detail="PaymentAccount is not available in this organization")
    await validate_allocation_target(db, org_id, validated)

    document.candidate_transaction = validated.model_dump(mode="json")
    if data.changes.get("allocation_target_id") or data.changes.get("selected_candidate_id"):
        cleared.add(ReviewFlag.ACCOUNT_REVIEW.value)
        cleared.add(ReviewFlag.AMBIGUOUS_MATCH.value)
    # A reference- or amount-related correction is the reviewer's resolution of a
    # suspected duplicate; clear the warning so the document can be re-approved
    # (the duplicate guard re-runs on approve against the corrected data).
    if any(
        key in data.changes
        for key in ("amount", "total_amount", "external_reference", "invoice_number",
                    "transfer_reference", "document_number")
    ):
        cleared.add(ReviewFlag.DUPLICATE_SUSPECTED.value)
    document.review_flags = [flag for flag in document.review_flags if flag not in cleared]
    if matching_results.get("ambiguous"):
        if ReviewFlag.AMBIGUOUS_MATCH.value not in document.review_flags:
            document.review_flags.append(ReviewFlag.AMBIGUOUS_MATCH.value)
    else:
        document.review_flags = [
            flag for flag in document.review_flags if flag != ReviewFlag.AMBIGUOUS_MATCH.value
        ]
    if not document.review_flags and is_candidate_ready_for_approval(validated):
        validated.status = CandidateStatus.READY_FOR_APPROVAL
        document.candidate_transaction = validated.model_dump(mode="json")
        document.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL

    for key, value in data.changes.items():
        db.add(DocumentCorrection(
            organization_id=org_id,
            document_id=document.id,
            field_path=key,
            old_value=old.get(key),
            new_value=value,
            reason=data.reason,
            corrected_by=user_id
        ))

    await AuditService(db).log_event(
        org_id, "Document", document.id, "CORRECT_EXTRACTION", user_id,
        old_values=old, new_values=data.changes, reason=data.reason
    )
    await db.flush()
    return document


@router.post("/{document_id}/approve", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
async def approve_document_candidate(
    document_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id
    service = DocumentService(db)
    document = await service.get_document(org_id, document_id, for_update=True)
    await require_reviewer(db, org_id, user_id)

    if document.processing_status in {
        DocumentProcessingStatus.PROCESSED,
        DocumentProcessingStatus.REJECTED,
        DocumentProcessingStatus.READY_TO_POST,
    }:
        raise HTTPException(status_code=409, detail="Document review decision is already final")
    if document.processing_status not in {
        DocumentProcessingStatus.REVIEW_REQUIRED,
        DocumentProcessingStatus.READY_FOR_APPROVAL,
    }:
        raise HTTPException(status_code=409, detail="Document is not awaiting review")

    if document.review_flags:
        raise HTTPException(
            status_code=409,
            detail=f"Document has unresolved review requirements: {', '.join(document.review_flags)}"
        )
    if (document.matching_results or {}).get("ambiguous"):
        raise HTTPException(
            status_code=409,
            detail="Document has ambiguous matching results requiring an explicit candidate selection",
        )

    if is_evidence_document(document.document_type):
        raise HTTPException(
            status_code=409,
            detail="Dokumen pendukung tidak perlu disetujui; dokumen ini diarsipkan otomatis.",
        )

    if not document.candidate_transaction:
        raise HTTPException(status_code=422, detail="Document candidate is missing")

    candidate = TransactionCandidate.model_validate(document.candidate_transaction)
    if not candidate.proposed_transaction_type or not candidate.transaction_date or not candidate.amount:
        raise HTTPException(status_code=422, detail="Candidate is incomplete")

    duplicate_flagged = False

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
            if candidate.cost_category in PROJECT_REQUIRED_COST_CATEGORIES and not candidate.project_id:
                raise HTTPException(
                    status_code=422,
                    detail="Project is required for project cost categories (5101)",
                )
            if candidate.allocation_target_id:
                raise HTTPException(
                    status_code=422,
                    detail="Transfer proof direct expense cannot also carry an allocation target",
                )

    if (
        document.document_type == DocumentType.TRANSFER_PROOF
        and candidate.proposed_transaction_type == TransactionType.DIRECT_PURCHASE
    ):
        references = collect_reference_numbers(
            document.candidate_transaction or {},
            document.extracted_data or {},
        )
        if references:
            scanner = DuplicateScanner(references, candidate.amount)
            await _scan_existing_references(db, org_id, scanner)
            verdict = scanner.result()
            if verdict.duplicate:
                raise HTTPException(status_code=422, detail=verdict.reason)
            if verdict.flagged:
                duplicate_flagged = True
                if ReviewFlag.DUPLICATE_SUSPECTED.value not in (document.review_flags or []):
                    document.review_flags = [*(document.review_flags or []), ReviewFlag.DUPLICATE_SUSPECTED.value]

    if candidate.proposed_transaction_type == TransactionType.CUSTOMER_PAYMENT and not candidate.allocation_target_id:
        raise HTTPException(status_code=409, detail="Customer payment requires an invoice allocation")
    if candidate.proposed_transaction_type == TransactionType.PAY_VENDOR_BILL and not candidate.allocation_target_id:
        raise HTTPException(status_code=409, detail="Vendor payment requires a bill allocation")

    if not is_candidate_ready_for_approval(candidate):
        raise HTTPException(status_code=422, detail="Candidate is missing required fields for approval")

    PostingRuleRegistry.validate_generic_ingestion(candidate.proposed_transaction_type)

    if candidate.counterparty_id:
        party = await db.scalar(select(Counterparty).where(and_(
            Counterparty.id == candidate.counterparty_id,
            Counterparty.organization_id == org_id,
            Counterparty.is_active.is_(True)
        )))
        if not party:
            raise HTTPException(status_code=422, detail="Counterparty is not available in this organization")

    if candidate.project_id:
        project = await db.scalar(select(Project).where(and_(
            Project.id == candidate.project_id,
            Project.organization_id == org_id,
            Project.project_status.in_([ProjectStatus.PLANNED, ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD]),
        )))
        if not project:
            raise HTTPException(status_code=422, detail="Project is not available or not active in this organization")

    if candidate.payment_account_id:
        account = await db.scalar(select(PaymentAccount).where(and_(
            PaymentAccount.id == candidate.payment_account_id,
            PaymentAccount.organization_id == org_id,
            PaymentAccount.is_active.is_(True)
        )))
        if not account:
            raise HTTPException(status_code=422, detail="Payment account is not available in this organization")

    await validate_allocation_target(db, org_id, candidate)

    previous_status = document.processing_status.value
    if duplicate_flagged:
        # Spec D3: a reference match with a differing amount is a warning, not a
        # rejection -- but it must NOT advance to READY_TO_POST, or the document
        # dead-ends (auto-post and manual post both refuse while a review flag is
        # present). Keep it reviewable so the flag can be resolved, then approved.
        candidate.status = CandidateStatus.REVIEW_REQUIRED
        document.candidate_transaction = candidate.model_dump(mode="json")
        document.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    else:
        candidate.status = CandidateStatus.READY_TO_POST
        document.candidate_transaction = candidate.model_dump(mode="json")
        document.processing_status = DocumentProcessingStatus.READY_TO_POST

    await AuditService(db).log_event(
        org_id,
        "Document",
        document.id,
        "APPROVE_CANDIDATE",
        user_id,
        old_values={"processing_status": previous_status},
        new_values={
            "processing_status": document.processing_status.value,
            "candidate_status": candidate.status.value,
        }
    )
    if not duplicate_flagged:
        posting_svc = DocumentPostingService(db)
        await posting_svc.enqueue_auto_post_if_eligible(org_id, document, candidate)

    await db.flush()
    return document


@router.post(
    "/{document_id}/post",
    response_model=DocumentPostingResponse,
    status_code=status.HTTP_200_OK,
    summary="Post Approved Document into General Ledger",
)
async def post_document_candidate(
    document_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    async def _do_post(session: AsyncSession):
        service = DocumentPostingService(session)
        return await service.post_document(
            organization_id=org_id,
            document_id=document_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            is_worker=False,
        )

    result = await run_in_clean_transaction(db, _do_post)
    return DocumentPostingResponse(
        document_id=result.document_id,
        processing_status=result.processing_status,
        transaction_id=result.transaction_id,
        transaction_code=result.transaction_code,
        already_posted=result.already_posted,
        posting_outcome=result.posting_outcome,
        journal_entry_id=result.journal_entry_id,
        entry_number=result.entry_number,
    )


@router.get("/review-queue", response_model=List[DocumentResponse], summary="List Document Candidates Requiring Review")
async def list_document_review_queue(org_id: uuid.UUID = Depends(get_current_org_id),
                                     db: AsyncSession = Depends(get_db)):
    return await DocumentService(db).list_documents(
        org_id, processing_status=DocumentProcessingStatus.REVIEW_REQUIRED
    )


@router.post("/{document_id}/reject", response_model=DocumentResponse)
async def reject_document_candidate(document_id: uuid.UUID, data: DocumentRejectionRequest,
                                    org_id: uuid.UUID = Depends(get_current_org_id),
                                    current_user: User = Depends(require_application_user),
                                    db: AsyncSession = Depends(get_db)):
    user_id = current_user.id
    document = await DocumentService(db).get_document(org_id, document_id, for_update=True)
    await require_reviewer(db, org_id, user_id)
    if document.processing_status in {
        DocumentProcessingStatus.PROCESSED,
        DocumentProcessingStatus.REJECTED,
        DocumentProcessingStatus.READY_TO_POST,
    }:
        raise HTTPException(status_code=409, detail="Document review decision is already final")
    if document.processing_status not in {DocumentProcessingStatus.REVIEW_REQUIRED,
                                           DocumentProcessingStatus.READY_FOR_APPROVAL}:
        raise HTTPException(status_code=409, detail="Document is not awaiting review")
    previous_status = document.processing_status.value
    document.processing_status = DocumentProcessingStatus.REJECTED
    candidate = dict(document.candidate_transaction)
    if candidate:
        candidate["status"] = CandidateStatus.REJECTED.value
        document.candidate_transaction = candidate
    await AuditService(db).log_event(org_id, "Document", document.id, "REJECT_CANDIDATE", user_id,
                                     old_values={"processing_status": previous_status},
                                     new_values={"processing_status": "REJECTED"}, reason=data.reason)
    await db.flush()
    return document


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get Document Metadata"
)
async def get_document(
    document_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = DocumentService(db)
    return await service.get_document(org_id, document_id)


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List Documents"
)
async def list_documents(
    document_type: Optional[DocumentType] = Query(None),
    processing_status: Optional[DocumentProcessingStatus] = Query(None),
    source_channel: Optional[str] = Query(None),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = DocumentService(db)
    return await service.list_documents(
        org_id,
        document_type=document_type,
        processing_status=processing_status,
        source_channel=source_channel,
    )
