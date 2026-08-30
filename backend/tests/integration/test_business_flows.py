import io
import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.user import User
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.transaction import Transaction
from src.models.enums import (
    ProjectStatus,
    TransactionType,
    CostCategory,
    WorkflowStatus,
    ReviewFlag,
    DocumentType,
    UserRole,
)
from src.schemas.transaction import TransactionCreate, TransactionAllocationCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.payable_service import VendorAPService
from src.services.receivable_service import CustomerARService
from src.services.reversal_service import ReversalService
from src.services.document_service import DocumentService
from src.services.review_service import ReviewQueueService
from src.services.project_cost_service import ProjectCostService
from src.services.balance_service import BalanceService
from src.core.exceptions import (
    DuplicateEntityException,
    InvariantViolationException,
    EntityNotFoundException,
)


@pytest.mark.asyncio
async def test_ten_core_business_flows(db_session: AsyncSession):
    """
    Comprehensive End-to-End Test Suite for all 10 Core Financial Business Flows.
    """
    # ----------------------------------------------------
    # Tenant 1 Setup
    # ----------------------------------------------------
    org1 = Organization(slug="org-primary", legal_name="PT Kontraktor Utama Indonesia")
    db_session.add(org1)
    await db_session.flush()

    await seed_standard_coa(db_session, org1.id)
    await seed_standard_payment_accounts(db_session, org1.id)
    await db_session.commit()

    cust1 = Counterparty(organization_id=org1.id, name="PT Pemberi Tugas Utama", is_customer=True)
    vend1 = Counterparty(organization_id=org1.id, name="PT Supplier Besi Beton", is_vendor=True)
    db_session.add_all([cust1, vend1])
    await db_session.flush()

    projA = Project(
        organization_id=org1.id,
        project_code="PRJ-2026-001",
        project_name="Pembangunan Gedung Kantor A",
        customer_id=cust1.id,
        start_date=date(2026, 1, 1),
        original_contract_value=Decimal("1000000000.00"),
        revised_contract_value=Decimal("1000000000.00"),
        project_status=ProjectStatus.ACTIVE
    )
    projB = Project(
        organization_id=org1.id,
        project_code="PRJ-2026-002",
        project_name="Pembangunan Ruko B",
        customer_id=cust1.id,
        start_date=date(2026, 1, 1),
        original_contract_value=Decimal("500000000.00"),
        revised_contract_value=Decimal("500000000.00"),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add_all([projA, projB])
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    ap_svc = VendorAPService(db_session)
    ar_svc = CustomerARService(db_session)
    rev_svc = ReversalService(db_session)
    doc_svc = DocumentService(db_session)
    review_svc = ReviewQueueService(db_session)
    cost_svc = ProjectCostService(db_session)
    balance_svc = BalanceService(db_session)

    # Initial Capital Injection: Rp 1.000.000.000 (Dr 1101 / Cr 3101)
    t_cap = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("1000000000.00"),
            description="Setoran Modal Awal"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org1.id, t_cap.id)
    await db_session.commit()

    # ====================================================
    # FLOW 1: DIRECT PROJECT PURCHASE
    # ====================================================
    t_flow1 = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("50000000.00"),
            counterparty_id=vend1.id,
            description="Beli Semen Proyek A Cash",
            project_id=projA.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    je_flow1 = await engine.post_transaction(org1.id, t_flow1.id)
    await db_session.commit()

    assert je_flow1.is_balanced is True
    assert je_flow1.total_debit == Decimal("50000000.00")
    costA_1 = await cost_svc.get_project_cost_breakdown(org1.id, projA.id)
    assert costA_1["total_actual_cost"] == Decimal("50000000.00")

    # ====================================================
    # FLOW 2: VENDOR BILL & PARTIAL PAYMENT (NO EXPENSE DUPLICATION)
    # ====================================================
    t_bill = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 1, 12),
            amount=Decimal("100000000.00"),
            counterparty_id=vend1.id,
            description="Tagihan Baja Proyek A Kredit",
            project_id=projA.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    await engine.post_transaction(org1.id, t_bill.id)
    await db_session.commit()

    bill = await ap_svc.register_vendor_bill(
        org1.id, vend1.id, date(2026, 1, 12), date(2026, 2, 12),
        Decimal("100000000.00"), project_id=projA.id, transaction_id=t_bill.id
    )
    await db_session.commit()

    # Pay 40M of 100M
    t_pay_bill = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=date(2026, 1, 20),
            amount=Decimal("40000000.00"),
            counterparty_id=vend1.id,
            description="Cicilan Tagihan Baja 40M"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org1.id, t_pay_bill.id)
    await db_session.commit()
    await ap_svc.allocate_vendor_payment(org1.id, t_pay_bill.id, [(bill.id, Decimal("40000000.00"))])
    await db_session.commit()

    reloaded_bill = await ap_svc.get_bill(org1.id, bill.id)
    assert reloaded_bill.status == "PARTIALLY_PAID"
    assert reloaded_bill.calculate_outstanding_amount() == Decimal("60000000.00")
    # Invariant: Project Cost is 50M + 100M = 150M (Payment did NOT add another 40M cost)
    costA_2 = await cost_svc.get_project_cost_breakdown(org1.id, projA.id)
    assert costA_2["total_actual_cost"] == Decimal("150000000.00")

    # ====================================================
    # FLOW 3: CUSTOMER INVOICE & PAYMENT
    # ====================================================
    t_inv = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 1, 25),
            amount=Decimal("300000000.00"),
            counterparty_id=cust1.id,
            description="Tagihan Termin 1 Proyek A",
            project_id=projA.id
        )
    )
    await db_session.commit()
    await engine.post_transaction(org1.id, t_inv.id)
    await db_session.commit()

    inv = await ar_svc.issue_customer_invoice(
        org1.id, cust1.id, projA.id, date(2026, 1, 25), Decimal("300000000.00"), transaction_id=t_inv.id
    )
    await db_session.commit()

    # Customer pays 200M of 300M
    t_cust_pay = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 1, 28),
            amount=Decimal("200000000.00"),
            counterparty_id=cust1.id,
            description="Pembayaran Sebagian Termin 1 (200M)"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org1.id, t_cust_pay.id)
    await db_session.commit()
    await ar_svc.allocate_customer_payment(org1.id, t_cust_pay.id, [(inv.id, Decimal("200000000.00"))])
    await db_session.commit()

    reloaded_inv = await ar_svc.get_invoice(org1.id, inv.id)
    assert reloaded_inv.status == "PARTIALLY_PAID"
    assert reloaded_inv.calculate_outstanding_amount() == Decimal("100000000.00")

    # ====================================================
    # FLOW 4: CUSTOMER OVERPAYMENT (REVIEW ROUTING)
    # ====================================================
    t_overpay = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 1, 29),
            amount=Decimal("150000000.00"),
            counterparty_id=cust1.id,
            description="Pembayaran Melebihi Sisa Tagihan (150M vs 100M)"
        )
    )
    await db_session.commit()
    # Attempting to allocate 150M against 100M invoice MUST raise InvariantViolationException
    with pytest.raises(InvariantViolationException):
        await ar_svc.allocate_customer_payment(org1.id, t_overpay.id, [(inv.id, Decimal("150000000.00"))])

    # ====================================================
    # FLOW 5: VENDOR ADVANCE & EXCESS SETTLEMENT REJECTION
    # ====================================================
    t_adv_trx = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_ADVANCE,
            transaction_date=date(2026, 2, 1),
            amount=Decimal("20000000.00"),
            counterparty_id=vend1.id,
            description="Kasbon Vendor 20M"
        )
    )
    await db_session.commit()
    adv = await ap_svc.register_vendor_advance(org1.id, vend1.id, date(2026, 2, 1), Decimal("20000000.00"), t_adv_trx.id)
    await db_session.commit()
    # Settle partial 15M
    await ap_svc.settle_vendor_advance(org1.id, adv.id, Decimal("15000000.00"))
    await db_session.commit()
    # Settle excess (attempting 10M on remaining 5M) -> MUST RAISE
    with pytest.raises(InvariantViolationException):
        await ap_svc.settle_vendor_advance(org1.id, adv.id, Decimal("10000000.00"))

    # ====================================================
    # FLOW 6: MULTI-PROJECT SPLIT TRANSACTION
    # ====================================================
    t_split = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 2, 5),
            amount=Decimal("30000000.00"),
            counterparty_id=vend1.id,
            description="Beli Alat Gabungan Proyek A & B",
            allocations=[
                TransactionAllocationCreate(project_id=projA.id, cost_category=CostCategory.EQP, amount=Decimal("20000000.00")),
                TransactionAllocationCreate(project_id=projB.id, cost_category=CostCategory.EQP, amount=Decimal("10000000.00")),
            ]
        )
    )
    await db_session.commit()
    je_split = await engine.post_transaction(org1.id, t_split.id)
    await db_session.commit()

    costA_split = await cost_svc.get_project_cost_breakdown(org1.id, projA.id)
    costB_split = await cost_svc.get_project_cost_breakdown(org1.id, projB.id)
    assert costA_split["category_breakdown"]["EQP"] == Decimal("20000000.00")
    assert costB_split["category_breakdown"]["EQP"] == Decimal("10000000.00")

    # ====================================================
    # FLOW 7: REVERSAL & IMMUTABILITY
    # ====================================================
    # Post a wrong transaction
    t_wrong = await trx_svc.create_transaction(
        org1.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 2, 8),
            amount=Decimal("5000000.00"),
            description="Salah Input Biaya",
            project_id=projB.id,
            cost_category=CostCategory.OTH
        )
    )
    await db_session.commit()
    await engine.post_transaction(org1.id, t_wrong.id)
    await db_session.commit()

    # Reverse it
    rev_trx, rev_je = await rev_svc.reverse_transaction(
        org1.id, t_wrong.id, reason="Koreksi salah input"
    )
    await db_session.commit()
    assert rev_trx.workflow_status == WorkflowStatus.POSTED
    assert t_wrong.workflow_status == WorkflowStatus.REVERSED

    # ====================================================
    # FLOW 8: CRYPTOGRAPHIC DOCUMENT DEDUPLICATION
    # ====================================================
    file_bytes = b"SPK-PROYEK-ASLI-2026"
    doc1 = await doc_svc.ingest_document(
        org1.id, io.BytesIO(file_bytes), "spk.pdf", "application/pdf", DocumentType.SPK
    )
    await db_session.commit()
    # Re-upload exact same file -> MUST FAIL with DuplicateEntityException
    with pytest.raises(DuplicateEntityException):
        await doc_svc.ingest_document(
            org1.id, io.BytesIO(file_bytes), "spk_duplicate.pdf", "application/pdf", DocumentType.SPK
        )

    # ====================================================
    # FLOW 9: MULTI-FLAG REVIEW QUEUE
    # ====================================================
    user_op = User(
        organization_id=org1.id,
        email="operator.flow@example.com",
        full_name="Staff Op",
        password_hash="dummy_hash",
        role=UserRole.OPERATOR
    )
    db_session.add(user_op)
    await db_session.flush()

    t_review = Transaction(
        organization_id=org1.id,
        transaction_code="TRX-2026-999999",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 2, 10),
        amount=Decimal("10000000.00"),
        description="Nota Belanja Bermasalah",
        workflow_status=WorkflowStatus.REVIEW_REQUIRED
    )
    db_session.add(t_review)
    await db_session.flush()

    rf1 = await review_svc.add_review_flag(org1.id, t_review.id, ReviewFlag.PROJECT_UNKNOWN, "Proyek tidak ada")
    rf2 = await review_svc.add_review_flag(org1.id, t_review.id, ReviewFlag.MISSING_DOCUMENT, "Nota fisik hilang")
    await db_session.commit()

    # Blocked
    with pytest.raises(InvariantViolationException):
        await review_svc.approve_and_post(org1.id, t_review.id, user_op.id, user_op.role)

    # Resolve 1 of 2
    await review_svc.resolve_review_flag(org1.id, t_review.id, rf1.id, user_op.id, "Proyek A")
    await db_session.commit()
    # Still blocked because rf2 unresolved
    with pytest.raises(InvariantViolationException):
        await review_svc.approve_and_post(org1.id, t_review.id, user_op.id, user_op.role)

    # Resolve 2 of 2
    await review_svc.resolve_review_flag(org1.id, t_review.id, rf2.id, user_op.id, "Nota ditemukan")
    await db_session.commit()
    assert t_review.workflow_status == WorkflowStatus.STAGED

    # ====================================================
    # FLOW 10: MULTI-TENANT ORGANIZATION ISOLATION
    # ====================================================
    org2 = Organization(slug="org-competitor", legal_name="PT Kontraktor Pesaing")
    db_session.add(org2)
    await db_session.flush()

    # Tenant 2 attempts to access Tenant 1's project -> MUST FAIL
    with pytest.raises(EntityNotFoundException):
        await cost_svc.get_project_cost_breakdown(org2.id, projA.id)

    # Tenant 2 attempts to reverse Tenant 1's transaction -> MUST FAIL
    with pytest.raises(EntityNotFoundException):
        await rev_svc.reverse_transaction(org2.id, t_flow1.id, reason="Malicious reversal")
