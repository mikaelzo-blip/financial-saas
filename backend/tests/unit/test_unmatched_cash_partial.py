import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import AccountType, NormalBalance, SettlementType
from src.models.money_movement import MoneyMovement, Settlement
from src.services.reporting.dashboard_service import DashboardService


@pytest.mark.asyncio
async def test_unmatched_cash_partial_settlement(db_session: AsyncSession):
    org = Organization(slug=f"unmatched-org-{uuid.uuid4().hex[:6]}", legal_name="PT Test Unmatched")
    db_session.add(org)
    await db_session.flush()

    coa = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.01",
        account_name="Kas Utama",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank"
    )
    db_session.add(coa)
    await db_session.flush()

    pa = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa.id,
        name="Kas Kantor",
        is_active=True
    )
    db_session.add(pa)
    await db_session.flush()

    # Case 1: MoneyMovement with 0 settlements -> 1 unmatched, full amount (50,000,000)
    mm1 = MoneyMovement(
        organization_id=org.id,
        payment_account_id=pa.id,
        movement_code="MM-TEST-001",
        direction="IN",
        amount=Decimal("50000000.00"),
        movement_date=date(2026, 3, 1),
        source_type="MANUAL"
    )
    db_session.add(mm1)
    await db_session.flush()

    overview = await DashboardService.get_cash_bank_overview(db_session, org.id)
    actions = await DashboardService.get_action_items(db_session, org.id)
    assert overview.unmatched_movements_count == 1
    assert overview.unmatched_amount == Decimal("50000000.00")
    assert actions.unmatched_bank_movements == 1

    # Case 2: MoneyMovement of 100,000,000 with partial settlement of 40,000,000
    # Clean mm1 first or test alongside mm2: let's test with mm2 alone for precision
    await db_session.delete(mm1)
    await db_session.flush()

    mm2 = MoneyMovement(
        organization_id=org.id,
        payment_account_id=pa.id,
        movement_code="MM-TEST-002",
        direction="OUT",
        amount=Decimal("100000000.00"),
        movement_date=date(2026, 3, 2),
        source_type="MANUAL"
    )
    db_session.add(mm2)
    await db_session.flush()

    s1 = Settlement(
        organization_id=org.id,
        settlement_code="SET-TEST-001",
        money_movement_id=mm2.id,
        settlement_type=SettlementType.DIRECT_EXPENSE,
        amount=Decimal("40000000.00")
    )
    db_session.add(s1)
    await db_session.flush()

    overview = await DashboardService.get_cash_bank_overview(db_session, org.id)
    actions = await DashboardService.get_action_items(db_session, org.id)
    assert overview.unmatched_movements_count == 1
    assert overview.unmatched_amount == Decimal("60000000.00")
    assert actions.unmatched_bank_movements == 1

    # Case 3: Fully settled (remaining 60,000,000 settled -> total 100,000,000)
    s2 = Settlement(
        organization_id=org.id,
        settlement_code="SET-TEST-002",
        money_movement_id=mm2.id,
        settlement_type=SettlementType.DIRECT_EXPENSE,
        amount=Decimal("60000000.00")
    )
    db_session.add(s2)
    await db_session.flush()

    overview = await DashboardService.get_cash_bank_overview(db_session, org.id)
    actions = await DashboardService.get_action_items(db_session, org.id)
    assert overview.unmatched_movements_count == 0
    assert overview.unmatched_amount == Decimal("0.00")
    assert actions.unmatched_bank_movements == 0
