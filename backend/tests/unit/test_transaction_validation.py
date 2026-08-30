from decimal import Decimal
import pytest

from src.schemas.transaction import TransactionAllocationInput
from src.services.transaction_service import validate_transaction_allocations
from src.core.exceptions import InvariantViolationException


def test_transaction_allocation_sum_validation_success():
    """Verify sum(allocation amounts) == total_amount passes validation."""
    total = Decimal("10000000.00")
    allocations = [
        TransactionAllocationInput(amount=Decimal("6000000.00"), cost_category="MAT", notes="Project A Material"),
        TransactionAllocationInput(amount=Decimal("4000000.00"), cost_category="MAT", notes="Project B Material"),
    ]
    assert validate_transaction_allocations(total, allocations) is True


def test_transaction_allocation_sum_mismatch_fails():
    """Verify sum(allocation amounts) != total_amount raises InvariantViolationException."""
    total = Decimal("10000000.00")
    allocations = [
        TransactionAllocationInput(amount=Decimal("5000000.00"), cost_category="MAT"),
        TransactionAllocationInput(amount=Decimal("4000000.00"), cost_category="MAT"),
    ]
    with pytest.raises(InvariantViolationException) as exc:
        validate_transaction_allocations(total, allocations)
    assert "Sum of allocations (9000000.00) does not match transaction total (10000000.00)" in str(exc.value)
