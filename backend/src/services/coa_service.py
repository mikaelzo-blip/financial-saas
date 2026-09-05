import uuid
from decimal import Decimal
from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, exists

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import AccountType
from src.schemas.coa import (
    ChartOfAccountCreate,
    ChartOfAccountUpdate,
    PaymentAccountCreate,
    PaymentAccountUpdate,
)
from src.core.exceptions import EntityNotFoundException, DuplicateEntityException


class COAService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_account_by_code(
        self,
        organization_id: uuid.UUID,
        account_code: str
    ) -> Optional[ChartOfAccount]:
        stmt = select(ChartOfAccount).where(
            and_(
                ChartOfAccount.organization_id == organization_id,
                ChartOfAccount.account_code == account_code
            )
        )
        return await self.session.scalar(stmt)

    async def get_account(
        self,
        organization_id: uuid.UUID,
        account_id: uuid.UUID
    ) -> ChartOfAccount:
        stmt = select(ChartOfAccount).where(
            and_(
                ChartOfAccount.organization_id == organization_id,
                ChartOfAccount.id == account_id
            )
        )
        account = await self.session.scalar(stmt)
        if not account:
            raise EntityNotFoundException("Chart of Account", account_id)
        return account

    async def list_accounts(
        self,
        organization_id: uuid.UUID,
        account_type: Optional[AccountType] = None,
        active_only: bool = True
    ) -> List[ChartOfAccount]:
        filters = [ChartOfAccount.organization_id == organization_id]
        if account_type:
            filters.append(ChartOfAccount.account_type == account_type)
        if active_only:
            filters.append(ChartOfAccount.is_active == True)

        stmt = select(ChartOfAccount).where(and_(*filters)).order_by(ChartOfAccount.account_code.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_account(
        self,
        organization_id: uuid.UUID,
        data: ChartOfAccountCreate
    ) -> ChartOfAccount:
        existing = await self.get_account_by_code(organization_id, data.account_code)
        if existing:
            raise DuplicateEntityException(
                f"Chart of Account with code '{data.account_code}' already exists in this organization.",
                details={"account_code": data.account_code, "organization_id": str(organization_id)}
            )

        account = ChartOfAccount(
            organization_id=organization_id,
            account_code=data.account_code,
            account_name=data.account_name,
            account_type=data.account_type,
            normal_balance=data.normal_balance,
            report_group=data.report_group,
            is_active=True
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def update_account(
        self,
        organization_id: uuid.UUID,
        account_id: uuid.UUID,
        data: ChartOfAccountUpdate
    ) -> ChartOfAccount:
        account = await self.get_account(organization_id, account_id)
        if data.account_name is not None:
            account.account_name = data.account_name
        if data.report_group is not None:
            account.report_group = data.report_group
        if data.is_active is not None:
            account.is_active = data.is_active

        await self.session.flush()
        return account


class PaymentAccountService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_payment_account(
        self,
        organization_id: uuid.UUID,
        payment_account_id: uuid.UUID
    ) -> PaymentAccount:
        stmt = select(PaymentAccount).where(
            and_(
                PaymentAccount.organization_id == organization_id,
                PaymentAccount.id == payment_account_id
            )
        )
        account = await self.session.scalar(stmt)
        if not account:
            raise EntityNotFoundException("Payment Account", payment_account_id)
        return account

    async def list_payment_accounts(
        self,
        organization_id: uuid.UUID,
        active_only: bool = True
    ) -> List[PaymentAccount]:
        filters = [PaymentAccount.organization_id == organization_id]
        if active_only:
            filters.append(PaymentAccount.is_active == True)

        stmt = (
            select(PaymentAccount)
            .options(selectinload(PaymentAccount.coa_account))
            .where(and_(*filters))
            .order_by(PaymentAccount.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_payment_account(
        self,
        organization_id: uuid.UUID,
        data: PaymentAccountCreate
    ) -> PaymentAccount:
        # Validate parent COA exists in organization
        coa_stmt = select(ChartOfAccount).where(
            and_(
                ChartOfAccount.id == data.coa_account_id,
                ChartOfAccount.organization_id == organization_id
            )
        )
        parent_coa = await self.session.scalar(coa_stmt)
        if not parent_coa:
            raise EntityNotFoundException("Parent Chart of Account", data.coa_account_id)

        account = PaymentAccount(
            organization_id=organization_id,
            coa_account_id=data.coa_account_id,
            name=data.name,
            bank_name=data.bank_name,
            account_number=data.account_number,
            is_active=True
        )
        account.coa_account = parent_coa
        self.session.add(account)
        await self.session.flush()
        return account

    async def get_payment_account_balance(
        self,
        organization_id: uuid.UUID,
        payment_account_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> Decimal:
        """
        Calculates the authoritative ledger balance for a specific payment account
        from journal lines joined with journal entries.
        Dr increases asset/cash, Cr decreases asset/cash.
        """
        from src.models.journal import JournalEntry, JournalLine
        from sqlalchemy import func

        # First verify payment account exists
        account = await self.get_payment_account(organization_id, payment_account_id)

        # Base query on JournalLine
        stmt = (
            select(
                func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
                func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
            )
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .where(
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalLine.payment_account_id == payment_account_id
                )
            )
        )
        if as_of_date:
            stmt = stmt.where(JournalEntry.posting_date <= as_of_date)

        result = await self.session.execute(stmt)
        total_dr, total_cr = result.one()
        return Decimal(str(total_dr)) - Decimal(str(total_cr))

    async def list_payment_accounts_with_balances(
        self,
        organization_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        accounts = await self.list_payment_accounts(organization_id, active_only=False)
        res = []
        for acc in accounts:
            bal = await self.get_payment_account_balance(organization_id, acc.id, as_of_date)
            res.append({
                "id": acc.id,
                "name": acc.name,
                "bank_name": acc.bank_name,
                "account_number": acc.account_number,
                "is_active": acc.is_active,
                "coa_account_id": acc.coa_account_id,
                "balance": bal
            })
        return res

