import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import ProjectStatus, TransactionType, WorkflowStatus, CostCategory
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.reversal_service import ReversalService
from src.services.immutability_guard import ImmutabilityGuard
from src.core.exceptions import InvariantViolationException


@pytest.mark.asyncio
async def test_immutability_guard_on_posted_transaction(db_session: AsyncSession):
    """Verify posted transactions cannot be mutated or deleted."""
    org = Organization(slug="org-immutable-unit", legal_name="Org Immutable Unit")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)

    # 1. Create and Post transaction
    t = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("10000000.00"),
            description="Setoran Modal"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t.id)
    await db_session.commit()

    # Invariant Guard Check: Attempting to modify posted transaction raises InvariantViolationException
    with pytest.raises(InvariantViolationException) as exc:
        ImmutabilityGuard.assert_transaction_mutable(t)
    assert "is immutable and cannot be modified or deleted" in str(exc.value)
