import uuid
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.enums import UserRole, TransactionType, WorkflowStatus, AccountingPeriodStatus
from src.models.transaction import Transaction
from src.models.accounting_period import AccountingPeriod
from src.services.processing_policy_service import ProcessingPolicyService
from src.services.accounting_period_service import AccountingPeriodService
from src.schemas.accounting_period import AccountingPeriodCreate, AccountingPeriodUpdate
from src.core.exceptions import InvariantViolationException, AuthorizationException


@pytest.mark.asyncio
async def test_accounting_period_posting_guards(db_session: AsyncSession):
    org_id = uuid.uuid4()
    period_service = AccountingPeriodService(db_session)
    policy_service = ProcessingPolicyService(db_session)

    # Create period 2026-01
    period = await period_service.create_period(
        org_id,
        AccountingPeriodCreate(
            period_name="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31)
        )
    )

    # Create staged transaction in 2026-01
    trx = Transaction(
        id=uuid.uuid4(),
        organization_id=org_id,
        transaction_code="TRX-PERIOD-001",
        transaction_date=date(2026, 1, 15),
        transaction_type=TransactionType.DIRECT_PURCHASE,
        amount=100000,
        description="Purchased office supplies",
        workflow_status=WorkflowStatus.STAGED
    )
    db_session.add(trx)
    await db_session.flush()

    # 1. Period OPEN: policy check should not raise period closed exception
    # (may fail later if no lines/accounts, but period guard passes)

    # 2. Hard close period
    await period_service.update_period_status(
        org_id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.CLOSED)
    )

    with pytest.raises(InvariantViolationException) as exc_info:
        await policy_service.authorize_and_post(
            organization_id=org_id,
            transaction_id=trx.id,
            actor_id=uuid.uuid4(),
            actor_role=UserRole.OPERATOR
        )
    assert "is CLOSED" in str(exc_info.value)

    # 3. Soft close period: Operator blocked, Admin allowed past period guard
    await period_service.update_period_status(
        org_id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.SOFT_CLOSED, reason="Soft close for audit")
    )

    with pytest.raises(AuthorizationException) as exc_info:
        await policy_service.authorize_and_post(
            organization_id=org_id,
            transaction_id=trx.id,
            actor_id=uuid.uuid4(),
            actor_role=UserRole.OPERATOR
        )
    assert "is SOFT_CLOSED" in str(exc_info.value)
