import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.schemas.reporting import (
    AgingBucketSummary,
    ARAgingInvoiceLine,
    ARAgingReportResponse
)
from src.services.reporting.base import get_organization_name


class ARAgingService:
    @staticmethod
    async def get_ar_aging(
        session: AsyncSession,
        organization_id: uuid.UUID,
        as_of_date: date | None = None
    ) -> ARAgingReportResponse:
        as_of = as_of_date or date.today()
        org_name = await get_organization_name(session, organization_id)

        stmt = select(CustomerInvoice).options(
            selectinload(CustomerInvoice.customer),
            selectinload(CustomerInvoice.project),
            selectinload(CustomerInvoice.allocations).selectinload(CustomerPaymentAllocation.payment_transaction),
            selectinload(CustomerInvoice.retention_releases),
        ).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.invoice_date <= as_of,
                CustomerInvoice.status != "CANCELLED",
            )
        ).order_by(CustomerInvoice.due_date.asc())

        invoices_list = (await session.execute(stmt)).scalars().all()

        current_tot = Decimal("0.00")
        tot_1_30 = Decimal("0.00")
        tot_31_60 = Decimal("0.00")
        tot_61_90 = Decimal("0.00")
        tot_over_90 = Decimal("0.00")
        grand_total = Decimal("0.00")

        lines: List[ARAgingInvoiceLine] = []

        def _allocation_date(alloc) -> date:
            trx = getattr(alloc, "payment_transaction", None)
            if trx is not None and getattr(trx, "transaction_date", None) is not None:
                val = trx.transaction_date
                return val.date() if isinstance(val, datetime) else val
            val = getattr(alloc, "created_at", None)
            if isinstance(val, datetime):
                return val.date()
            if isinstance(val, date):
                return val
            return date.min

        for inv in invoices_list:
            sum_releases_as_of = sum(
                (
                    Decimal(str(r.release_amount))
                    for r in (inv.retention_releases or [])
                    if r.release_date <= as_of
                ),
                Decimal("0.00")
            )
            collectible = (
                Decimal(str(inv.total_amount)) - Decimal(str(inv.retention_amount or Decimal("0.00")))
            ) + sum_releases_as_of
            paid_amt = sum(
                (Decimal(str(a.allocated_amount)) for a in inv.allocations if _allocation_date(a) <= as_of),
                Decimal("0.00")
            )
            outstanding = max(Decimal("0.00"), collectible - paid_amt)

            if outstanding <= Decimal("0.00"):
                continue

            days_overdue = (as_of - inv.due_date).days

            if days_overdue <= 0:
                bucket = "CURRENT"
                current_tot += outstanding
            elif days_overdue <= 30:
                bucket = "1_30"
                tot_1_30 += outstanding
            elif days_overdue <= 60:
                bucket = "31_60"
                tot_31_60 += outstanding
            elif days_overdue <= 90:
                bucket = "61_90"
                tot_61_90 += outstanding
            else:
                bucket = "OVER_90"
                tot_over_90 += outstanding

            grand_total += outstanding

            lines.append(
                ARAgingInvoiceLine(
                    customer_id=str(inv.customer_id),
                    customer_name=inv.customer.name if inv.customer else "Pelanggan",
                    project_code=inv.project.project_code if inv.project else None,
                    project_name=inv.project.project_name if inv.project else None,
                    invoice_number=inv.invoice_code,
                    invoice_date=inv.invoice_date,
                    due_date=inv.due_date,
                    days_overdue=days_overdue,
                    total_amount=collectible,
                    paid_amount=paid_amt,
                    outstanding_amount=outstanding,
                    bucket=bucket
                )
            )

        summary = AgingBucketSummary(
            current=current_tot,
            days_1_30=tot_1_30,
            days_31_60=tot_31_60,
            days_61_90=tot_61_90,
            days_over_90=tot_over_90,
            total=grand_total
        )

        return ARAgingReportResponse(
            organization_name=org_name,
            as_of_date=as_of,
            summary=summary,
            invoices=lines
        )
