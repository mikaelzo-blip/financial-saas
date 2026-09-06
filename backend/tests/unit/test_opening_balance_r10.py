import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.services.coa_seeder import seed_standard_coa
from src.services.opening_balance_service import OpeningBalanceService
from src.models.enums import WorkflowStatus
from src.core.exceptions import InvariantViolationException


@pytest.mark.asyncio
async def test_opening_balance_posting_success(db_session: AsyncSession):
    # Setup organization & COA
    org = Organization(
        id=uuid.uuid4(),
        slug="pt-konstruksi-perkasa",
        legal_name="PT Konstruksi Perkasa TBK"
    )
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await db_session.commit()

    service = OpeningBalanceService(db_session)
    
    # Opening balance: Kas (1101) 100k, Piutang (1201) 50k, Utang (2101) 30k, Modal (3101) 120k
    entries = [
        {"account_code": "1101", "debit": Decimal("100000.00"), "credit": Decimal("0.00")},
        {"account_code": "1201", "debit": Decimal("50000.00"), "credit": Decimal("0.00")},
        {"account_code": "2101", "debit": Decimal("0.00"), "credit": Decimal("30000.00")},
        {"account_code": "3101", "debit": Decimal("0.00"), "credit": Decimal("120000.00")},
    ]

    posted_trx = await service.post_opening_balances(
        organization_id=org.id,
        as_of_date=date(2026, 1, 1),
        balance_entries=entries,
        notes="Migrasi Saldo Awal 2026"
    )

    assert posted_trx is not None
    assert posted_trx.workflow_status == WorkflowStatus.POSTED
    assert posted_trx.amount == Decimal("150000.00")


@pytest.mark.asyncio
async def test_opening_balance_posting_unbalanced_rejected(db_session: AsyncSession):
    org = Organization(
        id=uuid.uuid4(),
        slug="pt-konstruksi-perkasa-2",
        legal_name="PT Konstruksi Perkasa 2"
    )
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await db_session.commit()

    service = OpeningBalanceService(db_session)
    
    # Unbalanced: 100k debit != 80k credit
    entries = [
        {"account_code": "1101", "debit": Decimal("100000.00"), "credit": Decimal("0.00")},
        {"account_code": "2101", "debit": Decimal("0.00"), "credit": Decimal("80000.00")},
    ]

    with pytest.raises(InvariantViolationException) as exc_info:
        await service.post_opening_balances(
            organization_id=org.id,
            as_of_date=date(2026, 1, 1),
            balance_entries=entries
        )

    assert "must balance" in str(exc_info.value)
