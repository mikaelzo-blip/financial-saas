from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import InvariantViolationException
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import (
    AccountType,
    MovementDirection,
    NormalBalance,
    SettlementType,
    TransactionType,
    WorkflowStatus,
)
from src.models.journal import JournalLine
from src.models.money_movement import MoneyMovement, Settlement
from src.models.organization import Organization
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.coa_service import PaymentAccountService
from src.services.reversal_service import ReversalService
from src.services.transaction_service import TransactionService


async def setup_interbank_test_tenant(session: AsyncSession, slug: str):
    org = Organization(slug=slug, legal_name=f"Org {slug}")
    session.add(org)
    await session.flush()

    coa_1101 = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS",
        is_active=True,
    )
    session.add(coa_1101)
    await session.flush()

    bca = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="BCA Operasional",
        bank_name="BCA",
        account_number="1111222233",
        is_active=True,
    )
    mandiri = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="Mandiri Payroll",
        bank_name="Mandiri",
        account_number="4444555566",
        is_active=True,
    )
    session.add_all([bca, mandiri])
    await session.commit()
    return org, bca, mandiri


@pytest.mark.asyncio
async def test_interbank_transfer_full_lifecycle(client, db_session: AsyncSession):
    org, bca, mandiri = await setup_interbank_test_tenant(db_session, "interbank-lifecycle")

    # 1. Validation: Same source and destination must be rejected
    trx_svc = TransactionService(db_session)
    with pytest.raises(InvariantViolationException, match="must be different"):
        await trx_svc.create_transaction(
            org.id,
            TransactionCreate(
                transaction_type=TransactionType.INTERBANK_TRANSFER,
                transaction_date=date(2026, 9, 2),
                amount=Decimal("5000000.00"),
                payment_account_id=bca.id,
                destination_payment_account_id=bca.id,
                description="Invalid self transfer",
            ),
        )

    # 2. Valid Interbank Transfer: BCA -> Mandiri Rp 10.000.000
    created_trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.INTERBANK_TRANSFER,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("10000000.00"),
            payment_account_id=bca.id,
            destination_payment_account_id=mandiri.id,
            reference_no="TRF-BCA-MDR-001",
            description="Transfer operasional ke payroll",
        ),
    )
    await db_session.commit()

    # 3. Post transaction
    engine = AccountingEngine(db_session)
    je = await engine.post_transaction(org.id, created_trx.id)
    await db_session.commit()

    # Verify Journal Entry: Dr 1101 (Mandiri) Rp 10M, Cr 1101 (BCA) Rp 10M
    assert je.is_balanced is True
    assert je.total_debit == Decimal("10000000.00")
    assert je.total_credit == Decimal("10000000.00")

    lines = (await db_session.scalars(
        select(JournalLine).where(JournalLine.journal_entry_id == je.id).order_by(JournalLine.line_number)
    )).all()
    assert len(lines) == 2
    # Leg 1: Debit to destination (Mandiri)
    assert lines[0].debit_amount == Decimal("10000000.00")
    assert lines[0].credit_amount == Decimal("0.00")
    assert lines[0].payment_account_id == mandiri.id
    # Leg 2: Credit to source (BCA)
    assert lines[1].debit_amount == Decimal("0.00")
    assert lines[1].credit_amount == Decimal("10000000.00")
    assert lines[1].payment_account_id == bca.id

    # 4. Verify Per-Bank Balances
    pa_svc = PaymentAccountService(db_session)
    bca_bal = await pa_svc.get_payment_account_balance(org.id, bca.id)
    mandiri_bal = await pa_svc.get_payment_account_balance(org.id, mandiri.id)
    assert bca_bal == Decimal("-10000000.00")
    assert mandiri_bal == Decimal("10000000.00")

    # 5. Verify MoneyMovements synchronized
    mms = (await db_session.scalars(
        select(MoneyMovement).where(
            MoneyMovement.organization_id == org.id,
            MoneyMovement.reference_no == "TRF-BCA-MDR-001",
        ).order_by(MoneyMovement.direction)
    )).all()
    assert len(mms) == 2

    # One IN (Mandiri) and one OUT (BCA)
    in_mm = next(m for m in mms if m.direction == MovementDirection.IN)
    out_mm = next(m for m in mms if m.direction == MovementDirection.OUT)
    assert in_mm.payment_account_id == mandiri.id
    assert in_mm.amount == Decimal("10000000.00")
    assert out_mm.payment_account_id == bca.id
    assert out_mm.amount == Decimal("10000000.00")

    # Verify settlements
    settlements = (await db_session.scalars(
        select(Settlement).where(Settlement.transaction_id == created_trx.id)
    )).all()
    assert len(settlements) == 2
    for s in settlements:
        assert s.settlement_type == SettlementType.INTERBANK_TRANSFER
        assert s.amount == Decimal("10000000.00")

    # 6. Reversal Safety: Reverse the interbank transfer
    rev_svc = ReversalService(db_session)
    rev_trx, rev_je = await rev_svc.reverse_transaction(
        org.id, created_trx.id, reason="Correction of duplicate transfer"
    )
    await db_session.commit()

    assert rev_trx.workflow_status == WorkflowStatus.POSTED
    assert rev_je.is_balanced is True

    # Bank balances return to 0.00
    bca_bal_after = await pa_svc.get_payment_account_balance(org.id, bca.id)
    mandiri_bal_after = await pa_svc.get_payment_account_balance(org.id, mandiri.id)
    assert bca_bal_after == Decimal("0.00")
    assert mandiri_bal_after == Decimal("0.00")

    # Settlements and money movements cleaned up
    settlements_after = (await db_session.scalars(
        select(Settlement).where(Settlement.transaction_id == created_trx.id)
    )).all()
    assert len(settlements_after) == 0
