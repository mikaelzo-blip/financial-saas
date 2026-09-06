import uuid
from datetime import date, datetime
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.accounting_period import AccountingPeriod
from src.models.enums import AccountingPeriodStatus
from src.schemas.accounting_period import AccountingPeriodCreate, AccountingPeriodUpdate
from src.services.accounting_period_service import AccountingPeriodService
from src.core.exceptions import InvariantViolationException, EntityNotFoundException


@pytest.mark.asyncio
async def test_accounting_period_lifecycle(db_session: AsyncSession):
    org_id = uuid.uuid4()
    service = AccountingPeriodService(db_session)

    # 1. Create period
    create_dto = AccountingPeriodCreate(
        period_name="2026-01",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )
    period = await service.create_period(org_id, create_dto)
    assert period.period_name == "2026-01"
    assert period.status == AccountingPeriodStatus.OPEN
    assert period.closed_at is None

    # 2. List periods
    periods = await service.list_periods(org_id)
    assert len(periods) == 1
    assert periods[0].id == period.id

    # 3. Soft close
    updated = await service.update_period_status(
        org_id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.SOFT_CLOSED)
    )
    assert updated.status == AccountingPeriodStatus.SOFT_CLOSED

    # 4. Hard close
    admin_id = uuid.uuid4()
    closed = await service.update_period_status(
        org_id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.CLOSED), actor_id=admin_id
    )
    assert closed.status == AccountingPeriodStatus.CLOSED
    assert closed.closed_at is not None
    assert closed.closed_by == admin_id

    # 5. Reopen without reason should raise InvariantViolationException
    with pytest.raises(InvariantViolationException):
        await service.update_period_status(
            org_id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.OPEN, reason="")
        )

    # 6. Reopen with reason succeeds
    reopened = await service.update_period_status(
        org_id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.OPEN, reason="Audit adjustment required")
    )
    assert reopened.status == AccountingPeriodStatus.OPEN
    assert reopened.closed_at is None
    assert reopened.closed_by is None
