import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import (
    AccountType,
    NormalBalance,
    TransactionType,
    WorkflowStatus,
    MovementDirection,
    MovementSourceType,
    SettlementType,
    CostCategory,
)



from src.schemas.money_movement import MoneyMovementCreate, SettlementCreate, SettlementAllocationCreate
from src.services.money_movement_service import MoneyMovementService
from src.services.coa_service import PaymentAccountService
from src.services.accounting_engine import AccountingEngine
from src.schemas.transaction import TransactionCreate
from src.models.enums import TransactionType, WorkflowStatus

from src.services.transaction_service import TransactionService


@pytest.mark.asyncio
async def test_per_bank_authoritative_balance(db_session: AsyncSession):
    # Setup Organization
    org = Organization(slug=f"bank-test-{uuid.uuid4().hex[:6]}", legal_name="Bank Test PT")
    db_session.add(org)

    await db_session.flush()

    # Setup 1101 parent account
    coa_1101 = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank",
        report_section="CURRENT_ASSETS",
        is_active=True
    )
    db_session.add(coa_1101)
    await db_session.flush()

    # Create Bank BCA and Bank Mandiri
    bank_bca = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="BCA Operasional",
        bank_name="BCA",
        account_number="1234567890",
        is_active=True
    )
    bank_mandiri = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="Mandiri Payroll",
        bank_name="Mandiri",
        account_number="9876543210",
        is_active=True
    )
    db_session.add_all([bank_bca, bank_mandiri])
    await db_session.flush()

    # Post Interbank Transfer: BCA (source: payment_account_id) -> Mandiri (destination: destination_payment_account_id)
    # Transfer Rp 10.000.000 from BCA to Mandiri
    trx_data = TransactionCreate(
        transaction_type=TransactionType.INTERBANK_TRANSFER,
        transaction_date=date(2026, 3, 1),
        amount=Decimal("10000000.00"),
        currency="IDR",
        description="Transfer kas operasional ke payroll",
        payment_account_id=bank_bca.id, # Outflow from BCA
        destination_payment_account_id=bank_mandiri.id # Inflow to Mandiri
    )

    trx_service = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    created_trx = await trx_service.create_transaction(org.id, trx_data)
    await engine.post_transaction(org.id, created_trx.id, posting_date=date(2026, 3, 1))

    # Check Bank Balances via PaymentAccountService

    pa_service = PaymentAccountService(db_session)
    mandiri_bal = await pa_service.get_payment_account_balance(org.id, bank_mandiri.id)
    bca_bal = await pa_service.get_payment_account_balance(org.id, bank_bca.id)

    # Mandiri received Dr 10.000.000 -> +10M
    # BCA received Cr 10.000.000 -> -10M
    assert mandiri_bal == Decimal("10000000.00")
    assert bca_bal == Decimal("-10000000.00")


@pytest.mark.asyncio
async def test_multi_project_settlement_allocation(db_session: AsyncSession):
    org = Organization(slug=f"multi-settle-{uuid.uuid4().hex[:6]}", legal_name="Multi Settlement PT")
    db_session.add(org)

    await db_session.flush()

    coa_1101 = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank",
        report_section="CURRENT_ASSETS",
        is_active=True
    )
    db_session.add(coa_1101)
    await db_session.flush()

    customer = Counterparty(
        organization_id=org.id,
        name="Pemilik Proyek Utama",
        is_customer=True
    )

    db_session.add(customer)
    await db_session.flush()

    bank_acc = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="BCA Utama",
        bank_name="BCA",
        account_number="555666",
        is_active=True
    )
    proj_a = Project(
        organization_id=org.id,
        customer_id=customer.id,
        project_name="Proyek Gedung A",
        project_code="PRJ-A",
        start_date=date(2026, 1, 1)
    )
    proj_b = Project(
        organization_id=org.id,
        customer_id=customer.id,
        project_name="Proyek Gedung B",
        project_code="PRJ-B",
        start_date=date(2026, 1, 1)
    )



    db_session.add_all([bank_acc, proj_a, proj_b])
    await db_session.flush()

    # Create Money Movement: Client wire transfer of Rp 100.000.000
    # Settling Rp 60M to Proyek A and Rp 40M to Proyek B
    movement_data = MoneyMovementCreate(
        payment_account_id=bank_acc.id,
        direction=MovementDirection.IN,
        amount=Decimal("100000000.00"),
        movement_date=date(2026, 3, 5),
        source_type=MovementSourceType.BANK_STATEMENT,
        reference_no="TRF-CLI-001",
        description="Termin Proyek A dan B",
        settlements=[
            SettlementCreate(
                settlement_type=SettlementType.PROJECT_ALLOCATION,
                amount=Decimal("100000000.00"),
                notes="Alokasi Termin ke 2 proyek",
                allocations=[
                    SettlementAllocationCreate(
                        project_id=proj_a.id,
                        amount=Decimal("60000000.00"),
                        cost_category=CostCategory.MAT,
                        notes="Alokasi termin tahap 1 gedung A"
                    ),
                    SettlementAllocationCreate(
                        project_id=proj_b.id,
                        amount=Decimal("40000000.00"),
                        cost_category=CostCategory.MAT,
                        notes="Alokasi termin tahap 1 gedung B"
                    )
                ]
            )
        ]
    )

    mm_service = MoneyMovementService(db_session)
    mm = await mm_service.create_money_movement(org.id, movement_data)

    assert mm.amount == Decimal("100000000.00")
    assert len(mm.settlements) == 1
    assert len(mm.settlements[0].allocations) == 2
    alloc_sum = sum(a.amount for a in mm.settlements[0].allocations)
    assert alloc_sum == Decimal("100000000.00")

    # Verify unallocated cash summary is 0
    unallocated = await mm_service.get_unallocated_cash_summary(org.id)
    assert unallocated == Decimal("0.00")
