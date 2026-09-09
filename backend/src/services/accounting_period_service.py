import uuid
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.accounting_period import AccountingPeriod
from src.models.enums import AccountingPeriodStatus, UserRole
from src.schemas.accounting_period import AccountingPeriodCreate, AccountingPeriodUpdate
from src.core.exceptions import InvariantViolationException, EntityNotFoundException, AuthorizationException


class AccountingPeriodService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_periods(self, organization_id: uuid.UUID) -> List[AccountingPeriod]:
        stmt = (
            select(AccountingPeriod)
            .where(AccountingPeriod.organization_id == organization_id)
            .order_by(AccountingPeriod.start_date.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_period_by_id(self, organization_id: uuid.UUID, period_id: uuid.UUID) -> AccountingPeriod:
        stmt = select(AccountingPeriod).where(
            AccountingPeriod.organization_id == organization_id,
            AccountingPeriod.id == period_id
        )
        period = await self.session.scalar(stmt)
        if not period:
            raise EntityNotFoundException(f"Accounting period {period_id} not found.")
        return period

    async def create_period(
        self, organization_id: uuid.UUID, data: AccountingPeriodCreate
    ) -> AccountingPeriod:
        if data.start_date > data.end_date:
            raise InvariantViolationException("Start date must be before or equal to end date.")

        # Check unique period_name per org
        existing = await self.session.scalar(
            select(AccountingPeriod).where(
                AccountingPeriod.organization_id == organization_id,
                AccountingPeriod.period_name == data.period_name
            )
        )
        if existing:
            raise InvariantViolationException(f"Accounting period '{data.period_name}' already exists.")

        period = AccountingPeriod(
            id=uuid.uuid4(),
            organization_id=organization_id,
            period_name=data.period_name,
            start_date=data.start_date,
            end_date=data.end_date,
            status=AccountingPeriodStatus.OPEN
        )
        self.session.add(period)
        await self.session.flush()
        return period

    async def update_period_status(
        self,
        organization_id: uuid.UUID,
        period_id: uuid.UUID,
        update_data: AccountingPeriodUpdate,
        actor_id: Optional[uuid.UUID] = None
    ) -> AccountingPeriod:
        period = await self.get_period_by_id(organization_id, period_id)
        current_status = period.status
        target_status = update_data.status

        if current_status == target_status:
            return period

        # If reopening a closed or soft-closed period, require a reason
        if current_status in (AccountingPeriodStatus.CLOSED, AccountingPeriodStatus.SOFT_CLOSED) and target_status == AccountingPeriodStatus.OPEN:
            if not update_data.reason or not update_data.reason.strip():
                raise InvariantViolationException("A justification reason is required to reopen a closed or soft-closed accounting period.")

        period.status = target_status
        if target_status == AccountingPeriodStatus.CLOSED:
            period.closed_at = datetime.now()
            period.closed_by = actor_id
        elif target_status == AccountingPeriodStatus.OPEN:
            period.closed_at = None
            period.closed_by = None

        await self.session.flush()
        return period

    async def assert_period_allows_posting(
        self,
        organization_id: uuid.UUID,
        posting_date: date,
        actor_role: Optional[UserRole] = None,
    ) -> None:
        """
        Hard accounting period posting guard.
        Enforces:
        1. If posting_date falls in a CLOSED period -> InvariantViolationException (blocked for all callers/roles).
        2. If posting_date falls in a SOFT_CLOSED period -> AuthorizationException if actor_role not in (ADMIN, MANAGER).
        """
        await assert_period_allows_posting(
            self.session, organization_id, posting_date, actor_role
        )


async def assert_period_allows_posting(
    session: AsyncSession,
    organization_id: uuid.UUID,
    posting_date: date,
    actor_role: Optional[UserRole] = None,
) -> None:
    """
    Hard accounting period posting guard.
    Enforces:
    1. If posting_date falls in a CLOSED period -> InvariantViolationException (blocked for all callers/roles).
    2. If posting_date falls in a SOFT_CLOSED period -> AuthorizationException if actor_role not in (ADMIN, MANAGER).
    """
    stmt = select(AccountingPeriod).where(
        and_(
            AccountingPeriod.organization_id == organization_id,
            AccountingPeriod.start_date <= posting_date,
            AccountingPeriod.end_date >= posting_date,
            AccountingPeriod.status.in_([AccountingPeriodStatus.CLOSED, AccountingPeriodStatus.SOFT_CLOSED])
        )
    )
    period = await session.scalar(stmt)
    if not period:
        return

    if period.status == AccountingPeriodStatus.CLOSED:
        raise InvariantViolationException(
            f"Cannot post transaction dated {posting_date}. Accounting period '{period.period_name}' is CLOSED.",
            details={
                "posting_date": str(posting_date),
                "period_name": period.period_name,
                "period_status": period.status.value,
            }
        )
    elif period.status == AccountingPeriodStatus.SOFT_CLOSED:
        if actor_role not in (UserRole.ADMIN, UserRole.MANAGER):
            raise AuthorizationException(
                f"Cannot post transaction dated {posting_date}. Accounting period '{period.period_name}' is SOFT_CLOSED (requires Admin or Manager).",
                details={
                    "posting_date": str(posting_date),
                    "period_name": period.period_name,
                    "period_status": period.status.value,
                }
            )

