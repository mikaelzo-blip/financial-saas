from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Set

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    AuthorizationException,
    EntityNotFoundException,
    InvariantViolationException,
)
from src.models.background_job import BackgroundJob
from src.models.coa import PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import Document
from src.models.enums import (
    CandidateStatus,
    CostCategory,
    DocumentProcessingStatus,
    ExpenseCategory,
    ProjectStatus,
    TransactionType,
    UserRole,
    WorkflowStatus,
)
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.transaction import Transaction
from src.schemas.document import TransactionCandidate
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.audit_service import AuditService
from src.services.job_queue_service import JobQueueService
from src.services.payable_service import VendorAPService
from src.services.posting_rules import PostingRuleRegistry
from src.services.processing_policy_service import ProcessingPolicyService
from src.services.receivable_service import CustomerARService
from src.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentPostingResult:
    document_id: uuid.UUID
    processing_status: DocumentProcessingStatus
    transaction_id: uuid.UUID
    transaction_code: str
    already_posted: bool
    posting_outcome: str
    journal_entry_id: Optional[uuid.UUID] = None
    entry_number: Optional[str] = None


class DocumentPostingService:
    """
    Canonical orchestration service for converting approved READY_TO_POST documents
    into posted financial transactions.

    Guarantees:
    - Exactly ONE accounting transaction per document
    - Deterministic idempotency and retry safety
    - Pessimistic locking to prevent concurrent double-conversion
    - Strict tenant reference revalidation
    - Fail-closed capability and policy verification
    - Integration with TransactionService, PostingRuleRegistry, and AccountingEngine
    - Zero direct JournalEntry/JournalLine insertions
    """

    POLICY_BLOCKED_TYPES: Set[TransactionType] = {
        TransactionType.VENDOR_ADVANCE,
        TransactionType.SETTLE_VENDOR_ADVANCE,
        TransactionType.CUSTOMER_ADVANCE,
        TransactionType.OWNER_WITHDRAWAL,
        TransactionType.OWNER_CONTRIBUTION,
        TransactionType.JOURNAL_ADJUSTMENT,
        TransactionType.FIXED_ASSET_DEPRECIATION,
        TransactionType.ASSET_PURCHASE,
    }

    DOCUMENT_SUPPORTED_TYPES: Set[TransactionType] = {
        TransactionType.DIRECT_PURCHASE,
        TransactionType.BANK_CHARGE,
        TransactionType.PAY_VENDOR_BILL,
        TransactionType.VENDOR_BILL,
        TransactionType.CUSTOMER_PAYMENT,
        TransactionType.CUSTOMER_INVOICE,
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.transaction_service = TransactionService(session)
        self.accounting_engine = AccountingEngine(session)
        self.audit_service = AuditService(session)
        self.ap_service = VendorAPService(session)
        self.ar_service = CustomerARService(session)
        self.queue_service = JobQueueService(session)

    async def enqueue_auto_post_if_eligible(
        self,
        organization_id: uuid.UUID,
        document: Document,
        candidate: Optional[TransactionCandidate] = None,
    ) -> Optional[BackgroundJob]:
        """
        Evaluates auto-post eligibility under canonical ProcessingPolicyService policy.
        If candidate is AUTO_SAFE and document has no unresolved review flags or ambiguity,
        enqueues a durable DOCUMENT_POST BackgroundJob with idempotency protection.
        Returns the enqueued/active BackgroundJob if eligible, None otherwise.
        """
        if document.processing_status != DocumentProcessingStatus.READY_TO_POST:
            return None

        if document.review_flags or (document.matching_results or {}).get("ambiguous"):
            return None

        if candidate is None:
            if not document.candidate_transaction:
                return None
            try:
                candidate = TransactionCandidate.model_validate(document.candidate_transaction)
            except Exception:
                return None

        if not candidate.proposed_transaction_type:
            return None

        # Must be canonically AUTO_SAFE
        if candidate.proposed_transaction_type not in ProcessingPolicyService.AUTO_SAFE_TYPES:
            return None

        job = await self.queue_service.enqueue(
            job_type="DOCUMENT_POST",
            payload={
                "document_id": str(document.id),
                "organization_id": str(organization_id),
            },
            organization_id=organization_id,
            max_attempts=3,
            idempotency_key=f"document-post:{document.id}",
        )
        return job

    async def post_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[UserRole] = None,
        is_worker: bool = False,
    ) -> DocumentPostingResult:
        # 1. Pessimistic lock on document row
        stmt = (
            select(Document)
            .execution_options(populate_existing=True)
            .where(
                Document.id == document_id,
                Document.organization_id == organization_id,
            )
            .with_for_update()
        )
        document = await self.session.scalar(stmt)
        if not document:
            raise EntityNotFoundException("Document", document_id)

        # 2. Idempotency guard: already converted/posted
        if (
            document.processing_status == DocumentProcessingStatus.POSTED
            or document.converted_transaction_id is not None
        ):
            trx = await self.session.scalar(
                select(Transaction).where(
                    Transaction.id == document.converted_transaction_id,
                    Transaction.organization_id == organization_id,
                )
            )
            if trx:
                from src.models.journal import JournalEntry
                je = await self.session.scalar(
                    select(JournalEntry).where(
                        JournalEntry.transaction_id == trx.id,
                        JournalEntry.organization_id == organization_id,
                    )
                )
                return DocumentPostingResult(
                    document_id=document.id,
                    processing_status=document.processing_status,
                    transaction_id=trx.id,
                    transaction_code=trx.transaction_code,
                    already_posted=True,
                    posting_outcome="ALREADY_POSTED",
                    journal_entry_id=je.id if je else None,
                    entry_number=je.entry_number if je else None,
                )

        # 3. Status eligibility gate
        if document.processing_status != DocumentProcessingStatus.READY_TO_POST:
            raise InvariantViolationException(
                f"Document {document.document_code} is in status '{document.processing_status.value}'. "
                "Only READY_TO_POST documents can be posted to the accounting ledger.",
                details={"status": document.processing_status.value, "failure_reason": "NOT_READY"},
            )

        if document.review_flags:
            raise InvariantViolationException(
                f"Document has unresolved review requirements: {', '.join(document.review_flags)}",
                details={"unresolved_flags": document.review_flags, "failure_reason": "UNRESOLVED_REVIEW"},
            )

        if (document.matching_results or {}).get("ambiguous"):
            raise InvariantViolationException(
                "Document has ambiguous matching results requiring an explicit candidate selection.",
                details={"failure_reason": "UNRESOLVED_REVIEW"},
            )

        # 4. Candidate parsing and structure check
        if not document.candidate_transaction:
            raise InvariantViolationException(
                "Document candidate transaction is missing.",
                details={"failure_reason": "NOT_READY"},
            )

        try:
            candidate = TransactionCandidate.model_validate(document.candidate_transaction)
        except Exception as exc:
            raise InvariantViolationException(
                f"Candidate transaction payload is invalid: {exc}",
                details={"failure_reason": "INVALID_CANDIDATE"},
            ) from exc
        if not candidate.proposed_transaction_type or not candidate.transaction_date or not candidate.amount:
            raise InvariantViolationException(
                "Candidate is missing required transaction fields (type, date, amount).",
                details={"failure_reason": "NOT_READY"},
            )

        if candidate.amount <= Decimal("0.00"):
            raise InvariantViolationException(
                "Transaction amount must be positive.",
                details={"failure_reason": "ALLOCATION_INVALID"},
            )

        # 5. Canonical capability & policy gate (FIN-P1-102)
        PostingRuleRegistry.validate_generic_ingestion(candidate.proposed_transaction_type)

        if candidate.proposed_transaction_type in self.POLICY_BLOCKED_TYPES:
            raise InvariantViolationException(
                f"Transaction type '{candidate.proposed_transaction_type.value}' is blocked by policy from "
                "automatic document conversion. Dedicated accounting workflow required.",
                details={
                    "transaction_type": candidate.proposed_transaction_type.value,
                    "failure_reason": "POLICY_REQUIRED",
                },
            )

        if candidate.proposed_transaction_type not in self.DOCUMENT_SUPPORTED_TYPES:
            raise InvariantViolationException(
                f"Transaction type '{candidate.proposed_transaction_type.value}' is not supported for document posting.",
                details={
                    "transaction_type": candidate.proposed_transaction_type.value,
                    "failure_reason": "UNSUPPORTED_TRANSACTION_TYPE",
                },
            )

        if is_worker and candidate.proposed_transaction_type not in ProcessingPolicyService.AUTO_SAFE_TYPES:
            raise InvariantViolationException(
                f"Transaction type '{candidate.proposed_transaction_type.value}' requires manual review/posting action.",
                details={
                    "transaction_type": candidate.proposed_transaction_type.value,
                    "failure_reason": "POLICY_REQUIRED",
                },
            )

        # 6. Tenant reference revalidation
        if candidate.counterparty_id:
            party = await self.session.scalar(
                select(Counterparty).where(
                    Counterparty.id == candidate.counterparty_id,
                    Counterparty.organization_id == organization_id,
                    Counterparty.is_active.is_(True),
                )
            )
            if not party:
                raise EntityNotFoundException("Counterparty", candidate.counterparty_id)
            if candidate.proposed_transaction_type in (
                TransactionType.PAY_VENDOR_BILL,
                TransactionType.VENDOR_BILL,
            ) and not party.is_vendor:
                raise InvariantViolationException(
                    "Counterparty must be a vendor.",
                    details={"failure_reason": "STALE_REFERENCE"},
                )
            if candidate.proposed_transaction_type in (
                TransactionType.CUSTOMER_PAYMENT,
                TransactionType.CUSTOMER_INVOICE,
            ) and not party.is_customer:
                raise InvariantViolationException(
                    "Counterparty must be a customer.",
                    details={"failure_reason": "STALE_REFERENCE"},
                )

        if candidate.project_id:
            project = await self.session.scalar(
                select(Project).where(
                    Project.id == candidate.project_id,
                    Project.organization_id == organization_id,
                    Project.project_status.in_([ProjectStatus.PLANNED, ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD]),
                )
            )
            if not project:
                raise EntityNotFoundException("Project", candidate.project_id)
            if (
                candidate.proposed_transaction_type == TransactionType.CUSTOMER_INVOICE
                and project.customer_id != candidate.counterparty_id
            ):
                raise InvariantViolationException(
                    "Customer invoice customer must match the customer assigned to the project.",
                    details={"failure_reason": "STALE_REFERENCE"},
                )

        if candidate.payment_account_id:
            pa = await self.session.scalar(
                select(PaymentAccount).where(
                    PaymentAccount.id == candidate.payment_account_id,
                    PaymentAccount.organization_id == organization_id,
                    PaymentAccount.is_active.is_(True),
                )
            )
            if not pa:
                raise EntityNotFoundException("Payment Account", candidate.payment_account_id)

        # 7. Allocation target revalidation (AR/AP settlement)
        if candidate.proposed_transaction_type == TransactionType.PAY_VENDOR_BILL:
            if not candidate.allocation_target_id:
                raise InvariantViolationException(
                    "Vendor payment requires an allocated vendor bill.",
                    details={"failure_reason": "ALLOCATION_INVALID"},
                )
            bill = await self.session.scalar(
                select(VendorBill)
                .where(
                    VendorBill.id == candidate.allocation_target_id,
                    VendorBill.organization_id == organization_id,
                )
                .with_for_update()
            )
            if not bill:
                raise EntityNotFoundException("Vendor Bill", candidate.allocation_target_id)
            if bill.status == "CANCELLED":
                raise InvariantViolationException(
                    f"Bill {bill.bill_code} is cancelled.",
                    details={"failure_reason": "ALLOCATION_INVALID"},
                )
            if bill.vendor_id != candidate.counterparty_id:
                raise InvariantViolationException(
                    "Vendor payment counterparty does not match bill vendor.",
                    details={"failure_reason": "STALE_REFERENCE"},
                )
            paid_sum = await self.session.scalar(
                select(func.coalesce(func.sum(VendorPaymentAllocation.allocated_amount), Decimal("0.00"))).where(
                    VendorPaymentAllocation.bill_id == bill.id
                )
            )
            outstanding = bill.total_amount - Decimal(str(paid_sum))
            if outstanding <= Decimal("0.00"):
                raise InvariantViolationException(
                    f"Bill {bill.bill_code} is already fully paid.",
                    details={"failure_reason": "ALLOCATION_INVALID"},
                )
            if candidate.amount > outstanding:
                raise InvariantViolationException(
                    f"Allocated payment amount ({candidate.amount}) exceeds outstanding balance ({outstanding}).",
                    details={"failure_reason": "ALLOCATION_INVALID"},
                )

        if candidate.proposed_transaction_type == TransactionType.CUSTOMER_PAYMENT:
            if not candidate.allocation_target_id:
                raise InvariantViolationException(
                    "Customer payment requires an allocated customer invoice.",
                    details={"failure_reason": "ALLOCATION_INVALID"},
                )
            invoice = await self.session.scalar(
                select(CustomerInvoice)
                .where(
                    CustomerInvoice.id == candidate.allocation_target_id,
                    CustomerInvoice.organization_id == organization_id,
                )
                .with_for_update()
            )
            if not invoice:
                raise EntityNotFoundException("Customer Invoice", candidate.allocation_target_id)
            if invoice.status == "CANCELLED":
                raise InvariantViolationException(
                    f"Invoice {invoice.invoice_code} is cancelled.",
                    details={"failure_reason": "ALLOCATION_INVALID"},
                )
            if invoice.customer_id != candidate.counterparty_id:
                raise InvariantViolationException(
                    "Customer payment counterparty does not match invoice customer.",
                    details={"failure_reason": "STALE_REFERENCE"},
                )
            paid_sum = await self.session.scalar(
                select(func.coalesce(func.sum(CustomerPaymentAllocation.allocated_amount), Decimal("0.00"))).where(
                    CustomerPaymentAllocation.invoice_id == invoice.id
                )
            )
            collectible = invoice.calculate_collectible_amount()
            outstanding = collectible - Decimal(str(paid_sum))
            if outstanding <= Decimal("0.00"):
                raise InvariantViolationException(
                    f"Invoice {invoice.invoice_code} is already fully paid.",
                    details={"failure_reason": "ALLOCATION_INVALID"},
                )
            if candidate.amount > outstanding:
                raise InvariantViolationException(
                    f"Allocated payment amount ({candidate.amount}) exceeds outstanding balance ({outstanding}).",
                    details={"failure_reason": "ALLOCATION_INVALID"},
                )

        # 8. Create Transaction via canonical TransactionService
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

        transaction = await self.transaction_service.create_transaction(
            organization_id=organization_id,
            data=trx_input,
            created_by=actor_id,
        )

        # 9. Post via AccountingEngine
        journal_entry = await self.accounting_engine.post_transaction(
            organization_id=organization_id,
            transaction_id=transaction.id,
            posting_date=transaction.transaction_date,
            actor_id=actor_id,
            actor_role=actor_role,
        )

        # 10. Execute AR / AP subledger allocation
        if candidate.proposed_transaction_type == TransactionType.PAY_VENDOR_BILL and candidate.allocation_target_id:
            await self.ap_service.allocate_vendor_payment(
                organization_id=organization_id,
                payment_transaction_id=transaction.id,
                bill_allocations=[(candidate.allocation_target_id, candidate.amount)],
            )

        if candidate.proposed_transaction_type == TransactionType.CUSTOMER_PAYMENT and candidate.allocation_target_id:
            await self.ar_service.allocate_customer_payment(
                organization_id=organization_id,
                payment_transaction_id=transaction.id,
                invoice_allocations=[(candidate.allocation_target_id, candidate.amount)],
            )

        # 11. Update Document state and durable conversion link
        document.converted_transaction_id = transaction.id
        document.processing_status = DocumentProcessingStatus.POSTED
        candidate.status = CandidateStatus.CONVERTED
        candidate.converted_transaction_id = transaction.id
        document.candidate_transaction = candidate.model_dump(mode="json")

        # 12. Audit event
        await self.audit_service.log_event(
            organization_id=organization_id,
            entity_name="Document",
            entity_id=document.id,
            action="DOCUMENT_POSTED",
            actor_id=actor_id,
            new_values={
                "processing_status": DocumentProcessingStatus.POSTED.value,
                "transaction_id": str(transaction.id),
                "transaction_code": transaction.transaction_code,
                "journal_entry_id": str(journal_entry.id),
                "entry_number": journal_entry.entry_number,
            },
        )

        await self.session.flush()

        return DocumentPostingResult(
            document_id=document.id,
            processing_status=DocumentProcessingStatus.POSTED,
            transaction_id=transaction.id,
            transaction_code=transaction.transaction_code,
            already_posted=False,
            posting_outcome="POSTED",
            journal_entry_id=journal_entry.id,
            entry_number=journal_entry.entry_number,
        )
