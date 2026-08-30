import uuid
from datetime import date
from decimal import Decimal
from typing import List
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.project import Project
from src.models.enums import NormalBalance
from src.schemas.reporting import GeneralLedgerEntry, GeneralLedgerResponse
from src.services.reporting.base import get_organization_name


class GeneralLedgerService:
    @staticmethod
    async def get_general_ledger(
        session: AsyncSession,
        organization_id: uuid.UUID,
        account_code: str,
        start_date: date,
        end_date: date,
        project_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> GeneralLedgerResponse:
        org_name = await get_organization_name(session, organization_id)

        # 1. Fetch Account info
        acc_stmt = select(ChartOfAccount).where(
            and_(
                ChartOfAccount.organization_id == organization_id,
                ChartOfAccount.account_code == account_code
            )
        )
        acc = (await session.execute(acc_stmt)).scalar_one_or_none()
        if not acc:
            raise ValueError(f"Akun dengan kode {account_code} tidak ditemukan.")

        # 2. Compute Opening Balance (before start_date)
        op_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.account_id == acc.id,
                JournalEntry.posting_date < start_date
            )
        )
        op_dr, op_cr = (await session.execute(op_stmt)).one()
        op_dr = Decimal(str(op_dr))
        op_cr = Decimal(str(op_cr))

        if acc.normal_balance == NormalBalance.DEBIT:
            opening_balance = op_dr - op_cr
        else:
            opening_balance = op_cr - op_dr

        # 3. Fetch period entries
        filter_conditions = [
            JournalEntry.organization_id == organization_id,
            JournalLine.account_id == acc.id,
            JournalEntry.posting_date >= start_date,
            JournalEntry.posting_date <= end_date
        ]
        if project_id:
            filter_conditions.append(JournalLine.project_id == project_id)

        count_stmt = select(func.count(JournalLine.id)).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).where(and_(*filter_conditions))
        total_records = (await session.execute(count_stmt)).scalar() or 0

        entries_stmt = select(
            JournalLine,
            JournalEntry,
            Project
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).outerjoin(
            Project, JournalLine.project_id == Project.id
        ).where(
            and_(*filter_conditions)
        ).order_by(
            JournalEntry.posting_date.asc(),
            JournalEntry.created_at.asc(),
            JournalLine.line_number.asc()
        )

        results = (await session.execute(entries_stmt)).all()

        current_running = opening_balance
        tot_debit = Decimal("0.00")
        tot_credit = Decimal("0.00")
        entries: List[GeneralLedgerEntry] = []

        for jl, je, proj in results:
            dr = Decimal(str(jl.debit_amount))
            cr = Decimal(str(jl.credit_amount))
            tot_debit += dr
            tot_credit += cr

            if acc.normal_balance == NormalBalance.DEBIT:
                current_running += (dr - cr)
            else:
                current_running += (cr - dr)

            entries.append(
                GeneralLedgerEntry(
                    date=je.posting_date,
                    journal_entry_id=str(je.id),
                    journal_entry_number=je.entry_number,
                    transaction_id=str(je.transaction_id) if je.transaction_id else None,
                    description=jl.notes or je.description,
                    project_code=proj.project_code if proj else None,
                    project_name=proj.name if proj else None,
                    debit=dr,
                    credit=cr,
                    running_balance=current_running,
                    document_ids=[]
                )
            )

        # Pagination slice
        offset = (page - 1) * page_size
        paginated_entries = entries[offset : offset + page_size]

        return GeneralLedgerResponse(
            organization_name=org_name,
            account_code=acc.account_code,
            account_name=acc.account_name,
            account_type=acc.account_type.value,
            normal_balance=acc.normal_balance.value,
            start_date=start_date,
            end_date=end_date,
            opening_balance=opening_balance,
            total_debit=tot_debit,
            total_credit=tot_credit,
            closing_balance=current_running,
            entries=paginated_entries,
            total_records=total_records,
            page=page,
            page_size=page_size
        )
