import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.transaction import Transaction
from src.models.enums import TransactionType, WorkflowStatus, UserRole, ReviewFlag
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.processing_policy_service import ProcessingPolicyService
from src.services.review_service import ReviewQueueService
from src.core.exceptions import InvariantViolationException, AuthorizationException


@pytest.mark.asyncio
async def test_processing_policy_blocks_unresolved_review_flags(db_session: AsyncSession):
    org = Organization(slug="org-policy-flags", legal_name="Org Policy Flags")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    trx = await trx_svc.create_transaction(
        organization_id=org.id,
        data=TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("1500000.00"),
            description="Beli Perlengkapan",
            cost_category=None,
        )
    )
    await db_session.commit()

    # Add review flag
    review_svc = ReviewQueueService(db_session)
    await review_svc.add_review_flag(
        organization_id=org.id,
        transaction_id=trx.id,
        flag=ReviewFlag.ACCOUNT_REVIEW,
        message="Need classification check"
    )
    await db_session.commit()

    policy_svc = ProcessingPolicyService(db_session)
    with pytest.raises(InvariantViolationException) as exc:
        await policy_svc.authorize_and_post(
            organization_id=org.id,
            transaction_id=trx.id
        )
    assert "Unresolved review flags exist" in str(exc.value)


@pytest.mark.asyncio
async def test_processing_policy_enforces_manager_role_for_sensitive(db_session: AsyncSession):
    org = Organization(slug="org-policy-role", legal_name="Org Policy Role")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    trx = await trx_svc.create_transaction(
        organization_id=org.id,
        data=TransactionCreate(
            transaction_type=TransactionType.OWNER_WITHDRAWAL,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("5000000.00"),
            description="Tarik Prive",
        )
    )
    await db_session.commit()

    policy_svc = ProcessingPolicyService(db_session)
    # Operator cannot approve sensitive
    with pytest.raises(AuthorizationException) as exc:
        await policy_svc.authorize_and_post(
            organization_id=org.id,
            transaction_id=trx.id,
            actor_role=UserRole.OPERATOR
        )
    assert "requires Manager approval" in str(exc.value)

    # Manager can approve sensitive
    posted_trx, je = await policy_svc.authorize_and_post(
        organization_id=org.id,
        transaction_id=trx.id,
        actor_role=UserRole.MANAGER
    )
    assert posted_trx.workflow_status == WorkflowStatus.POSTED
    assert je is not None
