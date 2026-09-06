import uuid
from decimal import Decimal
from datetime import date
from typing import List, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.money_movement import MoneyMovement, Settlement, SettlementAllocation
from src.models.coa import PaymentAccount
from src.models.project import Project
from src.models.transaction import Transaction
from src.models.receivable import CustomerPaymentAllocation
from src.models.payable import VendorPaymentAllocation
from src.models.enums import (
    MovementDirection,
    MovementSourceType,
    SettlementType,
    CostCategory,
    TransactionType,
    WorkflowStatus,
)
from src.schemas.money_movement import (
    MoneyMovementCreate,
    SettlementCreate,
    SettlementAllocationCreate,
)
from src.core.exceptions import InvariantViolationException, EntityNotFoundException



class MoneyMovementService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def synchronize_payment_money_movement(
        self,
        organization_id: uuid.UUID,
        payment_transaction_id: uuid.UUID,
    ) -> Optional[MoneyMovement]:
        """
        Synchronizes an authoritative MoneyMovement and Settlement record
        for a posted CUSTOMER_PAYMENT or PAY_VENDOR_BILL transaction.
        Guarantees that Journal, AP/AR settlement, and operational MoneyMovement cannot diverge.
        """
        stmt = (
            select(Transaction)
            .where(
                and_(
                    Transaction.organization_id == organization_id,
                    Transaction.id == payment_transaction_id,
                    Transaction.workflow_status == WorkflowStatus.POSTED,
                )
            )
        )
        trx = await self.session.scalar(stmt)
        if not trx or not trx.payment_account_id:
            return None

        if trx.transaction_type == TransactionType.CUSTOMER_PAYMENT:
            direction = MovementDirection.IN
            # Get invoice allocations
            cpa_stmt = (
                select(CustomerPaymentAllocation)
                .options(selectinload(CustomerPaymentAllocation.invoice))
                .where(CustomerPaymentAllocation.payment_transaction_id == trx.id)
            )
            cpas = (await self.session.scalars(cpa_stmt)).all()
            alloc_items = []
            for cpa in cpas:
                alloc_items.append(
                    SettlementAllocationCreate(
                        project_id=cpa.invoice.project_id if cpa.invoice else None,
                        invoice_id=trx.id,
                        amount=cpa.allocated_amount,
                        cost_category=None,
                        notes=f"Customer Payment for Invoice {cpa.invoice.invoice_code if cpa.invoice else ''}",
                    )
                )

        elif trx.transaction_type in (TransactionType.PAY_VENDOR_BILL, TransactionType.PAY_SUBCONTRACTOR):
            direction = MovementDirection.OUT
            # Get bill allocations
            vpa_stmt = (
                select(VendorPaymentAllocation)
                .options(selectinload(VendorPaymentAllocation.bill))
                .where(VendorPaymentAllocation.payment_transaction_id == trx.id)
            )
            vpas = (await self.session.scalars(vpa_stmt)).all()
            alloc_items = []
            for vpa in vpas:
                bill_trx = None
                if vpa.bill and vpa.bill.transaction_id:
                    bill_trx = vpa.bill.transaction_id
                alloc_items.append(
                    SettlementAllocationCreate(
                        project_id=vpa.bill.project_id if vpa.bill else None,
                        invoice_id=bill_trx,
                        amount=vpa.allocated_amount,
                        cost_category=CostCategory.MAT if trx.transaction_type == TransactionType.PAY_VENDOR_BILL else CostCategory.SUB,
                        notes=f"Vendor Payment for Bill {vpa.bill.bill_code if vpa.bill else ''}",
                    )
                )
        else:
            return None

        # Check if already exists for this transaction
        existing_settlement = await self.session.scalar(
            select(Settlement).where(
                and_(
                    Settlement.organization_id == organization_id,
                    Settlement.transaction_id == trx.id,
                )
            )
        )
        if existing_settlement:
            return await self.session.scalar(
                select(MoneyMovement).where(MoneyMovement.id == existing_settlement.money_movement_id)
            )

        settlement_create = SettlementCreate(
            settlement_type=SettlementType.INVOICE_PAYMENT,
            amount=trx.amount,
            transaction_id=trx.id,
            notes=trx.description or f"Settlement for {trx.transaction_code}",
            allocations=alloc_items,
        )

        source_type = MovementSourceType.TRANSFER_PROOF if trx.source_channel == "WHATSAPP" else MovementSourceType.MANUAL
        mm_create = MoneyMovementCreate(
            payment_account_id=trx.payment_account_id,
            direction=direction,
            amount=trx.amount,
            movement_date=trx.transaction_date,
            source_type=source_type,
            reference_no=trx.reference_no,
            description=trx.description,
            settlements=[settlement_create],
        )

        return await self.create_money_movement(organization_id, mm_create)

    async def _generate_movement_code(self, organization_id: uuid.UUID, movement_date: date) -> str:
        year = movement_date.year
        prefix = f"MM-{year}-"
        count_stmt = select(func.count(MoneyMovement.id)).where(
            and_(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.movement_code.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(count_stmt) or 0
        return f"{prefix}{count + 1:06d}"

    async def _generate_settlement_code(self, organization_id: uuid.UUID) -> str:
        prefix = "SET-"
        count_stmt = select(func.count(Settlement.id)).where(
            and_(
                Settlement.organization_id == organization_id,
                Settlement.settlement_code.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(count_stmt) or 0
        return f"{prefix}{count + 1:06d}"

    async def create_money_movement(
        self,
        organization_id: uuid.UUID,
        data: MoneyMovementCreate
    ) -> MoneyMovement:
        # 1. Validate payment account belongs to organization
        pa = await self.session.scalar(
            select(PaymentAccount).where(
                and_(
                    PaymentAccount.id == data.payment_account_id,
                    PaymentAccount.organization_id == organization_id
                )
            )
        )
        if not pa:
            raise EntityNotFoundException("PaymentAccount", data.payment_account_id)

        # 2. Validate settlements sum cannot exceed money movement amount
        if data.settlements:
            total_settlements = sum(s.amount for s in data.settlements)
            if total_settlements > data.amount:
                raise InvariantViolationException(
                    f"Total settlement amount ({total_settlements}) cannot exceed MoneyMovement amount ({data.amount})"
                )

            # Validate each settlement allocations
            for s in data.settlements:
                if s.allocations:
                    tot_alloc = sum(a.amount for a in s.allocations)
                    if tot_alloc > s.amount:
                        raise InvariantViolationException(
                            f"Total allocations ({tot_alloc}) cannot exceed settlement amount ({s.amount})"
                        )

                    # Validate project scoping
                    for alloc in s.allocations:
                        if alloc.project_id:
                            proj = await self.session.scalar(
                                select(Project).where(
                                    and_(
                                        Project.id == alloc.project_id,
                                        Project.organization_id == organization_id
                                    )
                                )
                            )
                            if not proj:
                                raise EntityNotFoundException("Project", alloc.project_id)
                        if alloc.invoice_id:
                            inv = await self.session.scalar(
                                select(Transaction).where(
                                    and_(
                                        Transaction.id == alloc.invoice_id,
                                        Transaction.organization_id == organization_id
                                    )
                                )
                            )
                            if not inv:
                                raise EntityNotFoundException("Invoice / Transaction", alloc.invoice_id)

        movement_code = await self._generate_movement_code(organization_id, data.movement_date)
        movement = MoneyMovement(
            organization_id=organization_id,
            movement_code=movement_code,
            payment_account_id=data.payment_account_id,
            direction=data.direction,
            amount=data.amount,
            movement_date=data.movement_date,
            source_type=data.source_type,
            reference_no=data.reference_no,
            description=data.description
        )
        self.session.add(movement)
        await self.session.flush()

        for s_data in data.settlements:
            settlement_code = await self._generate_settlement_code(organization_id)
            settlement = Settlement(
                organization_id=organization_id,
                settlement_code=settlement_code,
                money_movement_id=movement.id,
                transaction_id=s_data.transaction_id,
                settlement_type=s_data.settlement_type,
                amount=s_data.amount,
                notes=s_data.notes
            )
            self.session.add(settlement)
            await self.session.flush()

            for a_data in s_data.allocations:
                allocation = SettlementAllocation(
                    settlement_id=settlement.id,
                    project_id=a_data.project_id,
                    invoice_id=a_data.invoice_id,
                    amount=a_data.amount,
                    cost_category=a_data.cost_category,
                    notes=a_data.notes
                )
                self.session.add(allocation)
            await self.session.flush()

        # Reload full structure
        stmt = (
            select(MoneyMovement)
            .options(
                selectinload(MoneyMovement.settlements).selectinload(Settlement.allocations)
            )
            .where(MoneyMovement.id == movement.id)
        )
        result = await self.session.scalar(stmt)
        return result

    async def list_money_movements(
        self,
        organization_id: uuid.UUID,
        payment_account_id: Optional[uuid.UUID] = None
    ) -> List[MoneyMovement]:
        filters = [MoneyMovement.organization_id == organization_id]
        if payment_account_id:
            filters.append(MoneyMovement.payment_account_id == payment_account_id)

        stmt = (
            select(MoneyMovement)
            .options(
                selectinload(MoneyMovement.settlements).selectinload(Settlement.allocations)
            )
            .where(and_(*filters))
            .order_by(MoneyMovement.movement_date.desc(), MoneyMovement.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unallocated_cash_summary(
        self,
        organization_id: uuid.UUID
    ) -> Decimal:
        """
        Calculates total cash received (IN) that is not yet fully settled/allocated.
        Unallocated = Total MM(IN) - Total Settlement on MM(IN).
        """
        # Sum of all IN movements
        in_stmt = select(func.coalesce(func.sum(MoneyMovement.amount), Decimal("0.00"))).where(
            and_(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.direction == "IN"
            )
        )
        total_in = await self.session.scalar(in_stmt) or Decimal("0.00")

        # Sum of all settlements on IN movements
        settled_stmt = (
            select(func.coalesce(func.sum(Settlement.amount), Decimal("0.00")))
            .join(MoneyMovement, Settlement.money_movement_id == MoneyMovement.id)
            .where(
                and_(
                    MoneyMovement.organization_id == organization_id,
                    MoneyMovement.direction == "IN"
                )
            )
        )
        total_settled = await self.session.scalar(settled_stmt) or Decimal("0.00")

        return Decimal(str(total_in)) - Decimal(str(total_settled))
