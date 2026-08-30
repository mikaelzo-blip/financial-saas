from decimal import Decimal
import uuid
import pytest

from src.models.enums import TransactionType, CostCategory, WorkflowStatus
from src.models.transaction import Transaction, TransactionAllocation
from src.services.posting_rules import PostingRuleRegistry
from src.core.exceptions import InvariantViolationException


def test_posting_rule_direct_purchase_split():
    """Verify Direct Purchase with split allocations generates balanced DR and CR legs."""
    trx_id = uuid.uuid4()
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()

    trx = Transaction(
        id=trx_id,
        organization_id=uuid.uuid4(),
        transaction_code="TRX-2026-000001",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date="2026-02-15",
        amount=Decimal("15000000.00"),
        description="Pembelian Material Gabungan",
        workflow_status=WorkflowStatus.STAGED,
        allocations=[
            TransactionAllocation(project_id=p1, cost_category=CostCategory.MAT, amount=Decimal("10000000.00")),
            TransactionAllocation(project_id=p2, cost_category=CostCategory.MAT, amount=Decimal("5000000.00")),
        ]
    )

    legs = PostingRuleRegistry.generate_journal_legs(trx)
    assert len(legs) == 3

    total_dr = sum(l.debit_amount for l in legs)
    total_cr = sum(l.credit_amount for l in legs)

    assert total_dr == Decimal("15000000.00")
    assert total_cr == Decimal("15000000.00")
    assert total_dr == total_cr


def test_posting_rule_vendor_bill_and_payment():
    """Verify Vendor Bill generates DR 5101 / CR 2101 and Bill Payment generates DR 2101 / CR 1101."""
    vendor_id = uuid.uuid4()
    p_id = uuid.uuid4()

    # 1. Vendor Bill
    bill = Transaction(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        transaction_code="TRX-2026-000002",
        transaction_type=TransactionType.VENDOR_BILL,
        transaction_date="2026-02-10",
        amount=Decimal("50000000.00"),
        counterparty_id=vendor_id,
        description="Tagihan Semen Proyek",
        workflow_status=WorkflowStatus.STAGED,
        allocations=[TransactionAllocation(project_id=p_id, cost_category=CostCategory.MAT, amount=Decimal("50000000.00"))]
    )
    bill_legs = PostingRuleRegistry.generate_journal_legs(bill)
    assert any(l.account_code == "5101" and l.debit_amount == Decimal("50000000.00") for l in bill_legs)
    assert any(l.account_code == "2101" and l.credit_amount == Decimal("50000000.00") for l in bill_legs)

    # 2. Bill Payment
    pay = Transaction(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        transaction_code="TRX-2026-000003",
        transaction_type=TransactionType.PAY_VENDOR_BILL,
        transaction_date="2026-02-25",
        amount=Decimal("50000000.00"),
        counterparty_id=vendor_id,
        description="Pelunasan Tagihan Semen",
        workflow_status=WorkflowStatus.STAGED
    )
    pay_legs = PostingRuleRegistry.generate_journal_legs(pay)
    assert any(l.account_code == "2101" and l.debit_amount == Decimal("50000000.00") for l in pay_legs)
    assert any(l.account_code == "1101" and l.credit_amount == Decimal("50000000.00") for l in pay_legs)
