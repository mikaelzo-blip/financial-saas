import uuid
from datetime import date
from decimal import Decimal
from typing import List
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.payable import VendorBill, VendorPaymentAllocation, VendorAdvance
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.schemas.reporting import (
    AgingBucketSummary,
    APAgingBillLine,
    APAgingReportResponse
)
from src.services.reporting.base import get_organization_name


class APAgingService:
    @staticmethod
    async def get_ap_aging(
        session: AsyncSession,
        organization_id: uuid.UUID,
        as_of_date: date | None = None
    ) -> APAgingReportResponse:
        as_of = as_of_date or date.today()
        org_name = await get_organization_name(session, organization_id)

        # 1. Query bills with relationships
        stmt = select(VendorBill).options(
            selectinload(VendorBill.vendor),
            selectinload(VendorBill.project),
            selectinload(VendorBill.allocations)
        ).where(
            and_(
                VendorBill.organization_id == organization_id,
                VendorBill.bill_date <= as_of
            )
        ).order_by(VendorBill.due_date.asc())

        bills_list = (await session.execute(stmt)).scalars().all()

        current_tot = Decimal("0.00")
        tot_1_30 = Decimal("0.00")
        tot_31_60 = Decimal("0.00")
        tot_61_90 = Decimal("0.00")
        tot_over_90 = Decimal("0.00")
        grand_total = Decimal("0.00")

        lines: List[APAgingBillLine] = []

        for bill in bills_list:
            paid_amt = sum((Decimal(str(a.allocated_amount)) for a in bill.allocations), Decimal("0.00"))
            tot_amt = Decimal(str(bill.total_amount))
            outstanding = tot_amt - paid_amt

            if outstanding <= Decimal("0.00"):
                continue

            days_overdue = (as_of - bill.due_date).days

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
                APAgingBillLine(
                    vendor_id=str(bill.vendor_id),
                    vendor_name=bill.vendor.name if bill.vendor else "Pemasok",
                    project_code=bill.project.project_code if bill.project else None,
                    project_name=bill.project.project_name if bill.project else None,
                    bill_number=bill.bill_code,
                    bill_date=bill.bill_date,
                    due_date=bill.due_date,
                    days_overdue=days_overdue,
                    total_amount=tot_amt,
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

        # 2. Query unsettled vendor advances
        adv_stmt = select(
            func.coalesce(func.sum(VendorAdvance.remaining_balance), Decimal("0.00"))
        ).where(
            and_(
                VendorAdvance.organization_id == organization_id,
                VendorAdvance.advance_date <= as_of,
                VendorAdvance.remaining_balance > 0
            )
        )
        unsettled_adv = Decimal(str((await session.execute(adv_stmt)).scalar() or "0.00"))

        return APAgingReportResponse(
            organization_name=org_name,
            as_of_date=as_of,
            summary=summary,
            bills=lines,
            unsettled_advances_total=unsettled_adv
        )
